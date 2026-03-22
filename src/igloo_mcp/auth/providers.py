"""Authentication providers for MCP Snowflake connectivity.

This module introduces a minimal provider abstraction so igloo-mcp can run with:
- snowflake-labs provider (existing behavior; default)
- direct keypair provider (server-friendly for Slack/API deployments)
"""

from __future__ import annotations

import argparse
import json
import os
import threading
from collections.abc import Mapping
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp_server_snowflake.server import (  # type: ignore[import-untyped]
    create_lifespan as create_snowflake_lifespan,
)
from snowflake.connector import DictCursor, connect

from igloo_mcp.session_utils import ensure_session_lock

try:
    from fastmcp import FastMCP
    from fastmcp.utilities.logging import get_logger
except ImportError:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped,assignment]
    from mcp.server.fastmcp.utilities.logging import (  # type: ignore[import-untyped,assignment]
        get_logger,
    )

logger = get_logger(__name__)

AUTH_MODE_SNOWFLAKE_LABS = "snowflake-labs"
AUTH_MODE_KEYPAIR = "keypair"
AUTH_MODE_AUTO = "auto"
SUPPORTED_AUTH_MODES = (AUTH_MODE_SNOWFLAKE_LABS, AUTH_MODE_KEYPAIR, AUTH_MODE_AUTO)
AUTH_MODE_ENV = "IGLOO_MCP_AUTH_MODE"

DEFAULT_RETRYABLE_ERROR_KEYWORDS = (
    "temporarily unavailable",
    "please retry",
    "try again",
    "connection reset",
    "connection aborted",
    "service unavailable",
    "gateway timeout",
    "too many requests",
    "rate limit",
    "session no longer exists",
    "session has been terminated",
    "lock timeout",
    "deadlock",
)
DEFAULT_NON_RETRYABLE_ERROR_KEYWORDS = (
    "sql compilation error",
    "syntax error",
    "invalid identifier",
    "object does not exist",
    "insufficient privileges",
    "access denied",
    "permission denied",
    "not authorized",
)


@dataclass(frozen=True)
class AuthProviderCapabilities:
    """Capability matrix for a concrete auth provider implementation."""

    supports_profile_validation: bool
    supports_sql_validation_middleware_patch: bool
    supports_timeout_cancellation: bool
    supports_retry_handling: bool
    supports_circuit_breaker: bool


@dataclass(frozen=True)
class AuthProviderReliability:
    """Provider-level reliability defaults used by execute_query."""

    retry_attempts: int
    retry_initial_backoff_seconds: float
    retry_backoff_multiplier: float
    retry_max_backoff_seconds: float
    cancel_grace_seconds: float
    circuit_breaker_failure_threshold: int
    circuit_breaker_recovery_timeout_seconds: float
    retryable_error_keywords: tuple[str, ...] = DEFAULT_RETRYABLE_ERROR_KEYWORDS
    non_retryable_error_keywords: tuple[str, ...] = DEFAULT_NON_RETRYABLE_ERROR_KEYWORDS


@dataclass(frozen=True)
class AuthProviderSpec:
    """Resolved provider spec for a given auth mode."""

    mode: str
    capabilities: AuthProviderCapabilities
    reliability: AuthProviderReliability


AUTH_PROVIDER_SPECS: dict[str, AuthProviderSpec] = {
    AUTH_MODE_SNOWFLAKE_LABS: AuthProviderSpec(
        mode=AUTH_MODE_SNOWFLAKE_LABS,
        capabilities=AuthProviderCapabilities(
            supports_profile_validation=True,
            supports_sql_validation_middleware_patch=True,
            supports_timeout_cancellation=True,
            supports_retry_handling=True,
            supports_circuit_breaker=True,
        ),
        reliability=AuthProviderReliability(
            retry_attempts=1,
            retry_initial_backoff_seconds=0.5,
            retry_backoff_multiplier=2.0,
            retry_max_backoff_seconds=2.0,
            cancel_grace_seconds=5.0,
            circuit_breaker_failure_threshold=5,
            circuit_breaker_recovery_timeout_seconds=60.0,
        ),
    ),
    AUTH_MODE_KEYPAIR: AuthProviderSpec(
        mode=AUTH_MODE_KEYPAIR,
        capabilities=AuthProviderCapabilities(
            supports_profile_validation=True,
            supports_sql_validation_middleware_patch=False,
            supports_timeout_cancellation=True,
            supports_retry_handling=True,
            supports_circuit_breaker=True,
        ),
        reliability=AuthProviderReliability(
            retry_attempts=2,
            retry_initial_backoff_seconds=0.5,
            retry_backoff_multiplier=2.0,
            retry_max_backoff_seconds=4.0,
            cancel_grace_seconds=5.0,
            circuit_breaker_failure_threshold=5,
            circuit_breaker_recovery_timeout_seconds=60.0,
        ),
    ),
}


def _arg_or_env(
    args: argparse.Namespace,
    key: str,
    env_name: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> str | None:
    env_key = env_name or f"SNOWFLAKE_{key.upper()}"
    value = getattr(args, key, None)
    value = None if not isinstance(value, str) else value.strip() or None
    if value:
        return value
    env_map = os.environ if env is None else env
    env_val = env_map.get(env_key)
    if env_val is None:
        return None
    env_val = env_val.strip()
    return env_val or None


def _has_keypair_credentials(args: argparse.Namespace, env: Mapping[str, str] | None = None) -> bool:
    env_map = dict(os.environ if env is None else env)
    account = (_arg_or_env(args, "account", env=env_map) or env_map.get("SNOWFLAKE_ACCOUNT") or "").strip()
    user = (_arg_or_env(args, "user", env=env_map) or env_map.get("SNOWFLAKE_USER") or "").strip()
    private_key_file = (
        _arg_or_env(args, "private_key_file", env=env_map) or env_map.get("SNOWFLAKE_PRIVATE_KEY_FILE") or ""
    ).strip()
    private_key_inline = (
        _arg_or_env(args, "private_key", env=env_map) or env_map.get("SNOWFLAKE_PRIVATE_KEY") or ""
    ).strip()
    has_secret = bool(private_key_file or private_key_inline)
    return bool(account and user and has_secret)


def resolve_effective_auth_mode(
    args: argparse.Namespace,
    *,
    env: Mapping[str, str] | None = None,
) -> str:
    """Resolve effective auth mode from CLI/env with auto detection."""
    env_map = dict(os.environ if env is None else env)
    requested = (
        _arg_or_env(args, "auth_mode", AUTH_MODE_ENV, env=env_map)
        or env_map.get(AUTH_MODE_ENV)
        or AUTH_MODE_SNOWFLAKE_LABS
    ).strip()
    requested = requested.lower()

    if requested not in SUPPORTED_AUTH_MODES:
        raise ValueError(f"Unsupported auth_mode '{requested}'. Supported values: {', '.join(SUPPORTED_AUTH_MODES)}")

    if requested == AUTH_MODE_AUTO:
        return AUTH_MODE_KEYPAIR if _has_keypair_credentials(args, env_map) else AUTH_MODE_SNOWFLAKE_LABS
    return requested


def get_auth_provider_spec(mode: str | None) -> AuthProviderSpec:
    """Return the normalized provider spec for an auth mode."""
    normalized = (mode or AUTH_MODE_SNOWFLAKE_LABS).strip().lower()
    if normalized == AUTH_MODE_AUTO:
        normalized = AUTH_MODE_SNOWFLAKE_LABS
    spec = AUTH_PROVIDER_SPECS.get(normalized)
    if spec is not None:
        return spec
    logger.warning("Unknown auth mode %r; falling back to %s.", normalized, AUTH_MODE_SNOWFLAKE_LABS)
    return AUTH_PROVIDER_SPECS[AUTH_MODE_SNOWFLAKE_LABS]


def attach_provider_runtime_metadata(
    service: Any,
    *,
    mode: str | None = None,
) -> AuthProviderSpec:
    """Attach provider metadata to a service instance for downstream tools."""
    resolved_mode = mode or getattr(service, "auth_mode", AUTH_MODE_SNOWFLAKE_LABS)
    spec = get_auth_provider_spec(str(resolved_mode))
    assignments = {
        "auth_mode": spec.mode,
        "provider_spec": spec,
        "provider_capabilities": spec.capabilities,
        "provider_reliability": spec.reliability,
    }
    for key, value in assignments.items():
        try:
            setattr(service, key, value)
        except (AttributeError, TypeError):
            logger.debug("Could not set provider metadata field %s on %s", key, type(service).__name__, exc_info=True)
    return spec


def get_service_provider_spec(service: Any) -> AuthProviderSpec:
    """Get provider spec from a service, attaching defaults when absent."""
    existing = getattr(service, "provider_spec", None)
    if isinstance(existing, AuthProviderSpec):
        return existing
    return attach_provider_runtime_metadata(service, mode=getattr(service, "auth_mode", None))


def _build_keypair_connection_params(args: argparse.Namespace) -> dict[str, Any]:
    account = _arg_or_env(args, "account")
    user = _arg_or_env(args, "user")
    private_key_file = _arg_or_env(args, "private_key_file")
    private_key_inline = _arg_or_env(args, "private_key")

    if not account:
        raise ValueError("Keypair auth requires SNOWFLAKE_ACCOUNT (or --account).")
    if not user:
        raise ValueError("Keypair auth requires SNOWFLAKE_USER (or --user).")
    if not private_key_file and not private_key_inline:
        raise ValueError(
            "Keypair auth requires SNOWFLAKE_PRIVATE_KEY_FILE or SNOWFLAKE_PRIVATE_KEY "
            "(or --private-key-file/--private-key)."
        )

    params: dict[str, Any] = {
        "account": account,
        "user": user,
        # Keypair auth should default to JWT authenticator when not explicitly set.
        "authenticator": _arg_or_env(args, "authenticator") or "SNOWFLAKE_JWT",
    }

    if host := _arg_or_env(args, "host"):
        params["host"] = host

    for key in ("role", "warehouse", "database", "schema"):
        if value := _arg_or_env(args, key):
            params[key] = value

    if private_key_file:
        key_path = Path(private_key_file).expanduser()
        if not key_path.exists():
            raise ValueError(f"Key file does not exist: {key_path}")
        params["private_key_file"] = str(key_path)
    elif private_key_inline:
        params["private_key"] = private_key_inline

    if key_pwd := _arg_or_env(args, "private_key_file_pwd"):
        params["private_key_file_pwd"] = key_pwd

    return params


class KeyPairSnowflakeService:
    """Snowflake service compatible with the subset igloo tools use."""

    def __init__(self, connection_params: dict[str, Any]):
        self.auth_mode = AUTH_MODE_KEYPAIR
        self.provider_spec = get_auth_provider_spec(AUTH_MODE_KEYPAIR)
        self.provider_capabilities = self.provider_spec.capabilities
        self.provider_reliability = self.provider_spec.reliability
        self.connection_params = dict(connection_params)
        self.transport = "stdio"
        self.endpoint = "/mcp"
        self.query_tag: dict[str, Any] = {
            "origin": "igloo_mcp",
            "name": "mcp_server",
            "auth_mode": AUTH_MODE_KEYPAIR,
        }
        self.tag_major_version = 1
        self.tag_minor_version = 0
        self._lock = threading.RLock()
        self.connection = self._get_persistent_connection()

    def get_query_tag_param(self) -> dict[str, Any]:
        tag = dict(self.query_tag)
        tag["version"] = {"major": self.tag_major_version, "minor": self.tag_minor_version}
        return {"QUERY_TAG": json.dumps(tag)}

    def _connection_alive(self) -> bool:
        conn = self.connection
        if conn is None:
            return False
        is_closed = getattr(conn, "is_closed", None)
        if callable(is_closed):
            try:
                return not bool(is_closed())
            except (TypeError, RuntimeError):  # pragma: no cover - connector-specific edge cases
                return False
        return True

    def _get_persistent_connection(self, session_parameters: dict[str, Any] | None = None):
        merged_params = dict(self.connection_params)
        params = dict(self.get_query_tag_param())
        if session_parameters:
            params.update(session_parameters)

        connection = connect(
            **merged_params,
            session_parameters=params,
            client_session_keep_alive=True,
            paramstyle="qmark",
        )
        # Zero-compute ping for deterministic startup parity with upstream provider.
        with connection.cursor() as cursor:
            if cursor is None:  # pragma: no cover - defensive for connector protocol typing
                raise RuntimeError("Failed to acquire Snowflake cursor for keypair connection health probe.")
            cursor.execute("SELECT 'igloo_mcp_keypair_auth'")
            cursor.fetchone()
        return connection

    def _ensure_connection(self, session_parameters: dict[str, Any] | None = None):
        with self._lock:
            if self._connection_alive():
                return self.connection
            self.connection = self._get_persistent_connection(session_parameters=session_parameters)
            return self.connection

    def invalidate_connection(self) -> None:
        """Drop the current connector session so the next use reconnects cleanly."""
        with self._lock:
            conn = self.connection
            self.connection = None
        if conn is not None:
            try:
                conn.close()
            except (AttributeError, RuntimeError):  # pragma: no cover - best effort cleanup
                logger.debug("Failed to close invalidated keypair connection cleanly", exc_info=True)

    @contextmanager
    def get_connection(
        self,
        *,
        use_dict_cursor: bool = False,
        session_parameters: dict[str, Any] | None = None,
    ):
        session_lock = ensure_session_lock(self)
        with session_lock:
            connection = self._ensure_connection(session_parameters=session_parameters)
            cursor = connection.cursor(DictCursor) if use_dict_cursor else connection.cursor()
            try:
                yield connection, cursor
            finally:
                cursor.close()

    def get_api_headers(self) -> dict[str, str]:
        token = getattr(getattr(self.connection, "rest", None), "token", None)
        if not token:
            raise RuntimeError("Snowflake REST token unavailable on active connection.")
        return {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f'Snowflake Token="{token}"',
        }

    def get_api_host(self) -> str:
        host = getattr(self.connection, "host", None)
        if host:
            return str(host)
        if configured_host := self.connection_params.get("host"):
            return str(configured_host)
        account = self.connection_params.get("account")
        return f"{account}.snowflakecomputing.com" if account else ""

    def close(self) -> None:
        self.invalidate_connection()


def create_keypair_lifespan(args: argparse.Namespace):
    """Create lifespan for direct Snowflake keypair auth provider."""
    connection_params = _build_keypair_connection_params(args)

    @asynccontextmanager
    async def create_keypair_service(_: FastMCP):
        service = KeyPairSnowflakeService(connection_params=connection_params)
        try:
            yield service
        finally:
            service.close()

    return create_keypair_service


def create_auth_lifespan(
    args: argparse.Namespace,
    *,
    effective_mode: str | None = None,
):
    """Return the provider lifespan callable for the selected auth mode."""
    mode = effective_mode or resolve_effective_auth_mode(args)
    if mode == AUTH_MODE_KEYPAIR:
        logger.info("Using keypair auth provider for Snowflake connections")
        return create_keypair_lifespan(args)
    logger.info("Using snowflake-labs auth provider for Snowflake connections")
    return create_snowflake_lifespan(args)
