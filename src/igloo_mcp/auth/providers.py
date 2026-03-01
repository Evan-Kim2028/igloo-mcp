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
from pathlib import Path
from typing import Any

from mcp_server_snowflake.server import (  # type: ignore[import-untyped]
    create_lifespan as create_snowflake_lifespan,
)
from snowflake.connector import DictCursor, connect

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


def _arg_or_env(args: argparse.Namespace, key: str, env_name: str | None = None) -> str | None:
    env_key = env_name or f"SNOWFLAKE_{key.upper()}"
    value = getattr(args, key, None)
    if isinstance(value, str):
        value = value.strip() or None
    elif value is not None:
        value = str(value)
    if value:
        return value
    env_val = os.environ.get(env_key)
    if env_val is None:
        return None
    env_val = env_val.strip()
    return env_val or None


def _has_keypair_credentials(args: argparse.Namespace, env: Mapping[str, str] | None = None) -> bool:
    env_map = dict(env or os.environ)
    account = (getattr(args, "account", None) or env_map.get("SNOWFLAKE_ACCOUNT") or "").strip()
    user = (getattr(args, "user", None) or env_map.get("SNOWFLAKE_USER") or "").strip()
    private_key_file = (
        getattr(args, "private_key_file", None) or env_map.get("SNOWFLAKE_PRIVATE_KEY_FILE") or ""
    ).strip()
    private_key_inline = (getattr(args, "private_key", None) or env_map.get("SNOWFLAKE_PRIVATE_KEY") or "").strip()
    has_secret = bool(private_key_file or private_key_inline)
    return bool(account and user and has_secret)


def resolve_effective_auth_mode(
    args: argparse.Namespace,
    *,
    env: Mapping[str, str] | None = None,
) -> str:
    """Resolve effective auth mode from CLI/env with auto detection."""
    env_map = dict(env or os.environ)
    requested = (getattr(args, "auth_mode", None) or env_map.get(AUTH_MODE_ENV) or AUTH_MODE_SNOWFLAKE_LABS).strip()
    requested = requested.lower()

    if requested not in SUPPORTED_AUTH_MODES:
        raise ValueError(
            f"Unsupported auth_mode '{requested}'. Supported values: {', '.join(SUPPORTED_AUTH_MODES)}"
        )

    if requested == AUTH_MODE_AUTO:
        return AUTH_MODE_KEYPAIR if _has_keypair_credentials(args, env_map) else AUTH_MODE_SNOWFLAKE_LABS
    return requested


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
        self.connection_params = dict(connection_params)
        self.transport = "stdio"
        self.endpoint = "/mcp"
        self.query_tag = {"origin": "igloo_mcp", "name": "mcp_server", "auth_mode": AUTH_MODE_KEYPAIR}
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
            cursor.execute("SELECT 'igloo_mcp_keypair_auth'").fetchone()
        return connection

    def _ensure_connection(self, session_parameters: dict[str, Any] | None = None):
        with self._lock:
            if self._connection_alive():
                return self.connection
            self.connection = self._get_persistent_connection(session_parameters=session_parameters)
            return self.connection

    @contextmanager
    def get_connection(
        self,
        *,
        use_dict_cursor: bool = False,
        session_parameters: dict[str, Any] | None = None,
    ):
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
        with self._lock:
            conn = self.connection
            self.connection = None
            if conn is not None:
                try:
                    conn.close()
                except (AttributeError, RuntimeError):  # pragma: no cover - best effort cleanup
                    logger.debug("Failed to close keypair connection cleanly", exc_info=True)


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
