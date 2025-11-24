"""Constants used across igloo-mcp modules.

All constants can be overridden via environment variables with the prefix IGLOO_MCP_.
For example, CATALOG_CONCURRENCY can be set via IGLOO_MCP_CATALOG_CONCURRENCY.
"""

import os


def _get_int_env(key: str, default: int) -> int:
    """Get integer value from environment variable with default."""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


# Catalog building concurrency limits
CATALOG_CONCURRENCY: int = _get_int_env("IGLOO_MCP_CATALOG_CONCURRENCY", 16)
MAX_DDL_CONCURRENCY: int = _get_int_env("IGLOO_MCP_MAX_DDL_CONCURRENCY", 8)

# Query execution limits
MIN_QUERY_TIMEOUT_SECONDS: int = _get_int_env("IGLOO_MCP_MIN_QUERY_TIMEOUT_SECONDS", 1)
# Default max timeout: 3600 seconds (1 hour) - configurable via IGLOO_MCP_MAX_QUERY_TIMEOUT_SECONDS
MAX_QUERY_TIMEOUT_SECONDS: int = _get_int_env(
    "IGLOO_MCP_MAX_QUERY_TIMEOUT_SECONDS", 3600
)
MIN_REASON_LENGTH: int = _get_int_env("IGLOO_MCP_MIN_REASON_LENGTH", 5)
MAX_REASON_LENGTH: int = _get_int_env("IGLOO_MCP_MAX_REASON_LENGTH", 200)
MAX_SQL_STATEMENT_LENGTH: int = _get_int_env(
    "IGLOO_MCP_MAX_SQL_STATEMENT_LENGTH", 1_000_000
)

# Result size limits
RESULT_SIZE_LIMIT_MB: int = _get_int_env("IGLOO_MCP_RESULT_SIZE_LIMIT_MB", 100)
RESULT_KEEP_FIRST_ROWS: int = _get_int_env("IGLOO_MCP_RESULT_KEEP_FIRST_ROWS", 1000)
RESULT_KEEP_LAST_ROWS: int = _get_int_env("IGLOO_MCP_RESULT_KEEP_LAST_ROWS", 1000)
RESULT_TRUNCATION_THRESHOLD: int = _get_int_env(
    "IGLOO_MCP_RESULT_TRUNCATION_THRESHOLD", 10000
)
STATEMENT_PREVIEW_LENGTH: int = _get_int_env("IGLOO_MCP_STATEMENT_PREVIEW_LENGTH", 500)

# Allowed session parameters (whitelist for security)
ALLOWED_SESSION_PARAMETERS: set[str] = {
    "QUERY_TAG",
    "STATEMENT_TIMEOUT_IN_SECONDS",
    "AUTOCOMMIT",
    "ABORT_DETACHED_QUERY",
    "BINARY_INPUT_FORMAT",
    "BINARY_OUTPUT_FORMAT",
    "DATE_INPUT_FORMAT",
    "DATE_OUTPUT_FORMAT",
    "TIMESTAMP_INPUT_FORMAT",
    "TIMESTAMP_OUTPUT_FORMAT",
    "TIMESTAMP_LTZ_OUTPUT_FORMAT",
    "TIMESTAMP_NTZ_OUTPUT_FORMAT",
    "TIMESTAMP_TZ_OUTPUT_FORMAT",
    "TIME_INPUT_FORMAT",
    "TIME_OUTPUT_FORMAT",
}
