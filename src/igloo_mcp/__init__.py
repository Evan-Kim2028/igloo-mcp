"""igloo-mcp — AI-first Snowflake operations via Model Context Protocol."""

from .catalog import build_catalog
from .config import Config, get_config, set_config
from .parallel import ParallelQueryConfig, ParallelQueryExecutor, query_multiple_objects
from .snow_cli import SnowCLI

__version__ = "0.1.1"
__all__ = [
    "SnowCLI",
    "ParallelQueryConfig",
    "ParallelQueryExecutor",
    "query_multiple_objects",
    "build_catalog",
    "Config",
    "get_config",
    "set_config",
]
