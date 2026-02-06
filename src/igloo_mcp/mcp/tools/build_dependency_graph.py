"""Build Dependency Graph MCP Tool - Build object dependency graph.

Part of v1.8.0 Phase 2.2 - extracted from mcp_server.py.
"""

from __future__ import annotations

import os
import time
from typing import Any

import anyio

from igloo_mcp.mcp.exceptions import MCPExecutionError, MCPValidationError
from igloo_mcp.service_layer import DependencyService

from .base import MCPTool, ensure_request_id, tool_error_handler
from .schema_utils import boolean_schema, enum_schema, integer_schema, snowflake_identifier_schema

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TOOL_TIMEOUT_SECONDS = 60
MIN_TOOL_TIMEOUT_SECONDS = 1
MAX_TOOL_TIMEOUT_SECONDS = 3600


class BuildDependencyGraphTool(MCPTool):
    """MCP tool for building dependency graphs."""

    def __init__(self, dependency_service: DependencyService):
        """Initialize build dependency graph tool.

        Args:
            dependency_service: Dependency service instance
        """
        self.dependency_service = dependency_service

    @property
    def name(self) -> str:
        return "build_dependency_graph"

    @property
    def description(self) -> str:
        return (
            "Visualize table lineage and dependencies. "
            "Use after catalog is built to understand data flow. "
            "Returns DOT format for graph visualization."
        )

    @property
    def category(self) -> str:
        return "metadata"

    @property
    def tags(self) -> list[str]:
        return ["dependencies", "lineage", "graph", "metadata"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
        return [
            {
                "description": "Visualize dependencies across entire account",
                "parameters": {
                    "account": True,
                    "format": "json",
                },
            },
            {
                "description": "Generate DOT graph for analytics schema",
                "parameters": {
                    "database": "ANALYTICS",
                    "schema": "REPORTING",
                    "account": False,
                    "format": "dot",
                },
            },
        ]

    @tool_error_handler("build_dependency_graph")
    async def execute(
        self,
        database: str | None = None,
        schema: str | None = None,
        account: bool = False,
        format: str = "json",
        timeout_seconds: int | str | None = None,
        request_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build dependency graph.

        Args:
            database: Specific database to analyze
            schema: Specific schema to analyze
            account: Include ACCOUNT_USAGE for broader coverage (default: False)
            format: Output format - 'json' or 'dot' (default: json)
            timeout_seconds: Optional timeout for graph build operations.
                Falls back to IGLOO_MCP_TOOL_TIMEOUT_SECONDS or 60s default.
            request_id: Optional request correlation ID for tracing (auto-generated if not provided)

        Returns:
            Dependency graph with nodes and edges

        Raises:
            MCPValidationError: If format is invalid
            MCPExecutionError: If graph build fails
        """
        if format not in {"json", "dot"}:
            raise MCPValidationError(
                f"Invalid format '{format}'. Must be 'json' or 'dot'",
                validation_errors=[f"Invalid format: {format}"],
                hints=["Use format='json' or format='dot'"],
            )

        request_id = ensure_request_id(request_id)
        start_time = time.time()
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

        if "account_scope" in kwargs:
            account_scope = kwargs["account_scope"]
            if not isinstance(account_scope, bool):
                raise MCPValidationError(
                    "account_scope must be a boolean value.",
                    validation_errors=[f"Invalid account_scope value: {account_scope!r}"],
                    hints=["Use account_scope=true/false or account=true/false"],
                )
            if account != account_scope:
                if account is not False:
                    raise MCPValidationError(
                        "Conflicting values provided for account and account_scope.",
                        validation_errors=[f"account={account!r}", f"account_scope={account_scope!r}"],
                        hints=["Provide only account, or ensure both values match"],
                    )
                account = account_scope
            warnings.append(
                {
                    "code": "DEPRECATED_PARAMETER",
                    "severity": "warning",
                    "message": "account_scope is deprecated; use account instead.",
                }
            )

        logger.info(
            "build_dependency_graph_started",
            extra={
                "database": database,
                "schema": schema,
                "account": account,
                "format": format,
                "timeout_seconds": effective_timeout_seconds,
                "timeout_source": timeout_source,
                "request_id": request_id,
            },
        )

        try:
            with anyio.fail_after(effective_timeout_seconds):
                graph = await anyio.to_thread.run_sync(
                    lambda: self.dependency_service.build_dependency_graph(
                        database=database,
                        schema=schema,
                        account_scope=account,
                        format=format,
                        output_dir="./dependencies",
                    ),
                    abandon_on_cancel=True,
                )
        except TimeoutError as exc:
            raise MCPExecutionError(
                f"Dependency graph build timed out after {effective_timeout_seconds} seconds.",
                operation="build_dependency_graph",
                hints=[
                    "Increase timeout_seconds for large dependency scans (e.g. 180-600)",
                    "Set IGLOO_MCP_TOOL_TIMEOUT_SECONDS to change default timeout globally",
                ],
                context={
                    "effective_timeout_seconds": effective_timeout_seconds,
                    "timeout_source": timeout_source,
                    "database": database,
                    "schema": schema,
                    "account": account,
                },
            ) from exc

        total_duration = (time.time() - start_time) * 1000

        logger.info(
            "build_dependency_graph_completed",
            extra={
                "database": database,
                "schema": schema,
                "account": account,
                "format": format,
                "timeout_seconds": effective_timeout_seconds,
                "timeout_source": timeout_source,
                "total_duration_ms": total_duration,
                "request_id": request_id,
            },
        )

        response = dict(graph) if isinstance(graph, dict) else {"status": "success", "graph": graph}

        response.setdefault("status", "success")
        response["request_id"] = request_id
        response["warnings"] = warnings
        response["timing"] = {
            "total_duration_ms": round(total_duration, 2),
        }
        response["timeout"] = {
            "seconds": effective_timeout_seconds,
            "source": timeout_source,
        }
        return response

    def get_parameter_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Dependency Graph Parameters",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "database": snowflake_identifier_schema(
                    "Specific database to analyze (defaults to current database).",
                    title="Database",
                    examples=["ANALYTICS", "PIPELINE_V2_GROOT_DB"],
                ),
                "schema": snowflake_identifier_schema(
                    "Specific schema to analyze (defaults to current schema).",
                    title="Schema",
                    examples=["PUBLIC", "REPORTING"],
                ),
                "account": boolean_schema(
                    "Include ACCOUNT_USAGE views for cross-database dependencies.",
                    default=False,
                    examples=[True, False],
                ),
                "format": {
                    **enum_schema(
                        "Output format for the dependency graph.",
                        values=["json", "dot"],
                        default="json",
                        examples=["json"],
                    ),
                    "title": "Output Format",
                },
                "timeout_seconds": {
                    "title": "Timeout Seconds",
                    "description": (
                        "Optional timeout for dependency graph build operations. "
                        "If omitted, uses IGLOO_MCP_TOOL_TIMEOUT_SECONDS when set, "
                        f"otherwise defaults to {DEFAULT_TOOL_TIMEOUT_SECONDS}."
                    ),
                    "default": None,
                    "anyOf": [
                        integer_schema(
                            "Dependency graph timeout in seconds.",
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
