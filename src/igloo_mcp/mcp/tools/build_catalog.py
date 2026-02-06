"""Build Catalog MCP Tool - Build Snowflake catalog metadata.

Part of v1.8.0 Phase 2.2 - extracted from mcp_server.py.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import anyio

from igloo_mcp.catalog import CatalogService
from igloo_mcp.config import Config
from igloo_mcp.constants import CATALOG_CONCURRENCY, MAX_DDL_CONCURRENCY
from igloo_mcp.mcp.exceptions import MCPExecutionError, MCPValidationError
from igloo_mcp.path_utils import validate_safe_path

from .base import MCPTool, ensure_request_id, tool_error_handler
from .schema_utils import (
    boolean_schema,
    enum_schema,
    integer_schema,
    snowflake_identifier_schema,
    string_schema,
)

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TOOL_TIMEOUT_SECONDS = 60
MIN_TOOL_TIMEOUT_SECONDS = 1
MAX_TOOL_TIMEOUT_SECONDS = 3600


class BuildCatalogTool(MCPTool):
    """MCP tool for building Snowflake catalog metadata."""

    def __init__(self, config: Config, catalog_service: CatalogService):
        """Initialize build catalog tool.

        Args:
            config: Application configuration
            catalog_service: Catalog service instance
        """
        self.config = config
        self.catalog_service = catalog_service

    @property
    def name(self) -> str:
        return "build_catalog"

    @property
    def description(self) -> str:
        return (
            "Export Snowflake metadata to local catalog for fast offline search. "
            "Run ONCE per database, then use search_catalog for discovery. "
            "Use include_ddl=True for complete schema details."
        )

    @property
    def category(self) -> str:
        return "metadata"

    @property
    def tags(self) -> list[str]:
        return ["catalog", "metadata", "introspection", "documentation"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
        return [
            {
                "description": "Build account-wide catalog for governance export",
                "parameters": {
                    "output_dir": "./data_catalog",
                    "account": True,
                    "format": "jsonl",
                },
            },
            {
                "description": "Export product database catalog to docs folder",
                "parameters": {
                    "output_dir": "./artifacts/catalog",
                    "database": "PRODUCT",
                },
            },
        ]

    @tool_error_handler("build_catalog")
    async def execute(
        self,
        output_dir: str = "./data_catalogue",
        database: str | None = None,
        account: bool = False,
        format: str = "json",
        include_ddl: bool = True,
        timeout_seconds: int | str | None = None,
        request_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build comprehensive Snowflake catalog metadata.

        This tool queries Snowflake INFORMATION_SCHEMA to build a comprehensive
        metadata catalog including all database objects. It uses optimized
        queries and proper filtering to ensure accurate and relevant results.

        Key Features:
        - Real Snowflake metadata queries (not mock data)
        - Comprehensive coverage: databases, schemas, tables, views,
          materialized views, dynamic tables, tasks, functions, procedures,
          columns
        - Function filtering: Only user-defined functions (excludes built-in operators like !=, %, *, +, -)
        - Structured JSON output with detailed metadata
        - Account-wide or database-specific catalog building

        Args:
            output_dir: Catalog output directory (default: ./data_catalogue, resolves to unified storage)
            database: Specific database to introspect (default: current)
            account: Include entire account (default: False)
            format: Output format - 'json' or 'jsonl' (default: json)
            include_ddl: Include object DDL in catalog (default: True)
            timeout_seconds: Optional timeout for catalog build. Uses env/default fallback when omitted.
            request_id: Optional request correlation ID for tracing (auto-generated if not provided)

        Returns:
            Catalog build results with totals for each object type

        Raises:
            MCPValidationError: If parameters are invalid
            MCPExecutionError: If catalog build fails
        """
        # Validate format
        if format not in ("json", "jsonl"):
            raise MCPValidationError(
                f"Invalid format '{format}'. Must be 'json' or 'jsonl'",
                validation_errors=[f"Invalid format: {format}"],
                hints=["Use format='json' or format='jsonl'"],
            )

        # Timing and request correlation
        start_time = time.time()
        request_id = ensure_request_id(request_id)

        # Warnings collection
        warnings: list[dict[str, Any]] = []
        effective_timeout_seconds, timeout_source, timeout_warning = _resolve_tool_timeout(timeout_seconds)
        if timeout_warning:
            warnings.append(
                {
                    "code": "INVALID_TOOL_TIMEOUT_ENV",
                    "severity": "warning",
                    "message": timeout_warning,
                }
            )

        # Determine if using unified storage (when output_dir is default)
        # Handle both relative and normalized paths, and check if it's the default
        default_paths = ["./data_catalogue", "data_catalogue"]
        try:
            normalized_default = str(Path("./data_catalogue").resolve())
            default_paths.append(normalized_default)
        except Exception:
            pass

        use_unified_storage = output_dir in default_paths or (
            Path(output_dir).is_absolute()
            and Path(output_dir).name == "data_catalogue"
            and Path(output_dir).parent == Path.cwd()
        )

        # Log for debugging
        logger.debug(
            "build_catalog_path_resolution",
            extra={
                "output_dir": output_dir,
                "use_unified_storage": use_unified_storage,
                "default_paths": default_paths,
            },
        )

        # Validate output directory path (prevent path traversal)
        # Skip validation for default path when using unified storage (will be resolved internally)
        if not use_unified_storage:
            try:
                validated_output_dir = validate_safe_path(
                    output_dir,
                    reject_parent_dirs=True,
                )
                output_dir = str(validated_output_dir)
            except MCPValidationError:
                raise  # Re-raise validation errors
            except Exception as e:
                raise MCPValidationError(
                    f"Invalid output directory path: {e!s}",
                    validation_errors=[f"Path validation failed: {output_dir}"],
                    hints=[
                        "Use a relative path within the current directory",
                        "Do not use '..' in paths",
                    ],
                ) from e

        logger.info(
            "build_catalog_started",
            extra={
                "output_dir": output_dir,
                "database": database,
                "account": account,
                "format": format,
                "use_unified_storage": use_unified_storage,
                "timeout_seconds": effective_timeout_seconds,
                "timeout_source": timeout_source,
                "request_id": request_id,
            },
        )

        # Timing: Catalog build operation
        catalog_start = time.time()
        try:
            with anyio.fail_after(effective_timeout_seconds):
                result = await anyio.to_thread.run_sync(
                    lambda: self.catalog_service.build(
                        output_dir=output_dir,
                        database=database,
                        account_scope=account,
                        output_format=format,
                        include_ddl=include_ddl,
                        max_ddl_concurrency=MAX_DDL_CONCURRENCY,
                        catalog_concurrency=CATALOG_CONCURRENCY,
                        export_sql=False,
                        use_unified_storage=use_unified_storage,
                    ),
                    abandon_on_cancel=True,
                )
        except TimeoutError as exc:
            raise MCPExecutionError(
                f"Catalog build timed out after {effective_timeout_seconds} seconds.",
                operation="build_catalog",
                hints=[
                    "Increase timeout_seconds for large databases (e.g. 180-600)",
                    "Set IGLOO_MCP_TOOL_TIMEOUT_SECONDS to change default timeout globally",
                ],
                context={
                    "effective_timeout_seconds": effective_timeout_seconds,
                    "timeout_source": timeout_source,
                },
            ) from exc
        catalog_duration = (time.time() - catalog_start) * 1000

        # Log the actual resolved path for unified storage
        resolved_output_dir = result.output_dir

        # Calculate total duration
        total_duration = (time.time() - start_time) * 1000

        logger.info(
            "build_catalog_completed",
            extra={
                "output_dir": resolved_output_dir,
                "database": database or "current",
                "account": account,
                "request_id": request_id,
                "timeout_seconds": effective_timeout_seconds,
                "timeout_source": timeout_source,
                "catalog_duration_ms": catalog_duration,
                "total_duration_ms": total_duration,
                "totals": {
                    "databases": result.totals.databases,
                    "schemas": result.totals.schemas,
                    "tables": result.totals.tables,
                },
            },
        )

        return {
            "status": "success",
            "request_id": request_id,
            "warnings": warnings,
            "timing": {
                "catalog_fetch_ms": round(catalog_duration, 2),
                "total_duration_ms": round(total_duration, 2),
            },
            "output_dir": resolved_output_dir,
            "database": database or "current",
            "account_scope": account,
            "format": format,
            "timeout": {
                "seconds": effective_timeout_seconds,
                "source": timeout_source,
            },
            "totals": {
                "databases": result.totals.databases,
                "schemas": result.totals.schemas,
                "tables": result.totals.tables,
                "views": result.totals.views,
                "materialized_views": result.totals.materialized_views,
                "dynamic_tables": result.totals.dynamic_tables,
                "tasks": result.totals.tasks,
                "functions": result.totals.functions,
                "procedures": result.totals.procedures,
                "columns": result.totals.columns,
            },
        }

    def get_parameter_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Build Catalog Parameters",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "output_dir": string_schema(
                    "Target directory where catalog artifacts will be written. "
                    "Defaults to './data_catalogue' which resolves to unified storage "
                    "at ~/.igloo_mcp/catalogs/{database}/ or ~/.igloo_mcp/catalogs/account/ "
                    "for account-wide catalogs. Specify a custom path to override.",
                    title="Output Directory",
                    default="./data_catalogue",
                    examples=["./data_catalogue", "./artifacts/catalog"],
                ),
                "database": snowflake_identifier_schema(
                    "Specific database to introspect (defaults to current database).",
                    title="Database",
                    examples=["PIPELINE_V2_GROOT_DB", "ANALYTICS"],
                ),
                "account": boolean_schema(
                    "Include entire account metadata (ACCOUNT_USAGE). Must be false if database is provided.",
                    default=False,
                    examples=[True, False],
                ),
                "format": {
                    **enum_schema(
                        "Output file format for catalog artifacts.",
                        values=["json", "jsonl"],
                        default="json",
                        examples=["json"],
                    ),
                    "title": "Output Format",
                },
                "include_ddl": boolean_schema(
                    "Include object DDL (CREATE statements) in catalog artifacts.",
                    default=True,
                    examples=[True, False],
                ),
                "timeout_seconds": {
                    "title": "Timeout Seconds",
                    "description": (
                        "Optional timeout for catalog build operations. "
                        "If omitted, uses IGLOO_MCP_TOOL_TIMEOUT_SECONDS when set, "
                        f"otherwise defaults to {DEFAULT_TOOL_TIMEOUT_SECONDS}."
                    ),
                    "default": None,
                    "anyOf": [
                        integer_schema(
                            "Catalog build timeout in seconds.",
                            minimum=MIN_TOOL_TIMEOUT_SECONDS,
                            maximum=MAX_TOOL_TIMEOUT_SECONDS,
                            examples=[60, 180, 300],
                        ),
                        {
                            "type": "string",
                            "pattern": r"^[0-9]+$",
                            "description": "Numeric string timeout (e.g., '180').",
                            "examples": ["60", "180", "300"],
                        },
                    ],
                },
                "request_id": {
                    "type": "string",
                    "description": "Optional request correlation ID for tracing (auto-generated if not provided)",
                },
            },
            "allOf": [
                {
                    "if": {
                        "properties": {"account": {"const": True}},
                        "required": ["account"],
                    },
                    "then": {"not": {"required": ["database"]}},
                },
                {
                    "if": {"required": ["database"]},
                    "then": {
                        "properties": {"account": {"const": False}},
                    },
                },
            ],
        }


def _coerce_positive_timeout(value: int | str) -> int:
    if isinstance(value, bool):
        raise MCPValidationError(
            "timeout_seconds must be an integer value in seconds.",
            validation_errors=["Boolean values are not valid timeout seconds."],
        )

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise MCPValidationError(
            "timeout_seconds must be an integer value in seconds.",
            validation_errors=[f"Invalid timeout value: {value!r}"],
        ) from None

    if not numeric.is_integer():
        raise MCPValidationError(
            "timeout_seconds must be an integer value in seconds.",
            validation_errors=[f"Invalid timeout value: {value!r}"],
        )

    timeout_int = int(numeric)
    if not MIN_TOOL_TIMEOUT_SECONDS <= timeout_int <= MAX_TOOL_TIMEOUT_SECONDS:
        raise MCPValidationError(
            f"timeout_seconds must be between {MIN_TOOL_TIMEOUT_SECONDS} and {MAX_TOOL_TIMEOUT_SECONDS}",
            validation_errors=[f"Invalid timeout value: {timeout_int}"],
            hints=[f"Use a timeout between {MIN_TOOL_TIMEOUT_SECONDS} and {MAX_TOOL_TIMEOUT_SECONDS} seconds"],
        )
    return timeout_int


def _resolve_tool_timeout(timeout_seconds: int | str | None) -> tuple[int, str, str | None]:
    if timeout_seconds is not None:
        return _coerce_positive_timeout(timeout_seconds), "parameter", None

    env_raw = os.environ.get("IGLOO_MCP_TOOL_TIMEOUT_SECONDS")
    if env_raw:
        try:
            return _coerce_positive_timeout(env_raw), "env", None
        except MCPValidationError:
            return (
                DEFAULT_TOOL_TIMEOUT_SECONDS,
                "default",
                (
                    "IGLOO_MCP_TOOL_TIMEOUT_SECONDS is invalid; "
                    f"falling back to default timeout ({DEFAULT_TOOL_TIMEOUT_SECONDS}s)."
                ),
            )

    return DEFAULT_TOOL_TIMEOUT_SECONDS, "default", None
