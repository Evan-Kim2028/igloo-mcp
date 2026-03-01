"""Authentication provider selection for igloo-mcp."""

from .providers import (
    AUTH_MODE_AUTO,
    AUTH_MODE_ENV,
    AUTH_MODE_KEYPAIR,
    AUTH_MODE_SNOWFLAKE_LABS,
    AUTH_PROVIDER_SPECS,
    SUPPORTED_AUTH_MODES,
    AuthProviderCapabilities,
    AuthProviderReliability,
    AuthProviderSpec,
    attach_provider_runtime_metadata,
    create_auth_lifespan,
    create_keypair_lifespan,
    get_auth_provider_spec,
    get_service_provider_spec,
    resolve_effective_auth_mode,
)

__all__ = [
    "AUTH_MODE_AUTO",
    "AUTH_MODE_ENV",
    "AUTH_MODE_KEYPAIR",
    "AUTH_MODE_SNOWFLAKE_LABS",
    "AUTH_PROVIDER_SPECS",
    "SUPPORTED_AUTH_MODES",
    "AuthProviderCapabilities",
    "AuthProviderReliability",
    "AuthProviderSpec",
    "attach_provider_runtime_metadata",
    "create_auth_lifespan",
    "create_keypair_lifespan",
    "get_auth_provider_spec",
    "get_service_provider_spec",
    "resolve_effective_auth_mode",
]
