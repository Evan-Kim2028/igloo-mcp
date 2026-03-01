"""Authentication provider selection for igloo-mcp."""

from .providers import (
    AUTH_MODE_AUTO,
    AUTH_MODE_ENV,
    AUTH_MODE_KEYPAIR,
    AUTH_MODE_SNOWFLAKE_LABS,
    SUPPORTED_AUTH_MODES,
    create_auth_lifespan,
    create_keypair_lifespan,
    resolve_effective_auth_mode,
)

__all__ = [
    "AUTH_MODE_AUTO",
    "AUTH_MODE_ENV",
    "AUTH_MODE_KEYPAIR",
    "AUTH_MODE_SNOWFLAKE_LABS",
    "SUPPORTED_AUTH_MODES",
    "create_auth_lifespan",
    "create_keypair_lifespan",
    "resolve_effective_auth_mode",
]
