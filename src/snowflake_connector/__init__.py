"""Compatibility shim for the old package name `snowflake_connector`.

Please import from `igloo_mcp` going forward.
"""

from warnings import warn

from igloo_mcp import (
    Config,
    ParallelQueryConfig,
    ParallelQueryExecutor,
    SnowCLI,
    get_config,
    query_multiple_objects,
    set_config,
)

warn(
    "`snowflake_connector` is deprecated; use `igloo_mcp` instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "Config",
    "ParallelQueryConfig",
    "ParallelQueryExecutor",
    "SnowCLI",
    "get_config",
    "query_multiple_objects",
    "set_config",
]
