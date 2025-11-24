"""Build Dependency Graph MCP Tool - Build object dependency graph.

Part of v1.8.0 Phase 2.2 - extracted from mcp_server.py.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import anyio

from igloo_mcp.mcp.exceptions import MCPValidationError
from igloo_mcp.service_layer import DependencyService

from .base import MCPTool, tool_error_handler
from .schema_utils import boolean_schema, enum_schema, snowflake_identifier_schema

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


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
            "Build object dependency graph from Snowflake metadata. "
            "Use this tool when you need to understand relationships between tables, views, and other objects, "
            "or to trace data lineage. Returns a graph structure showing dependencies between database objects."
        )

    @property
    def category(self) -> str:
        return "metadata"

    @property
    def tags(self) -> list[str]:
        return ["dependencies", "lineage", "graph", "metadata"]

    @property
    def usage_examples(self) -> list[Dict[str, Any]]:
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
        database: Optional[str] = None,
        schema: Optional[str] = None,
        account: bool = False,
        format: str = "json",
        request_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Build dependency graph.

        Args:
            database: Specific database to analyze
            schema: Specific schema to analyze
            account: Include ACCOUNT_USAGE for broader coverage (default: False)
            format: Output format - 'json' or 'dot' (default: json)
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

        logger.info(
            "build_dependency_graph_started",
            extra={
                "database": database,
                "schema": schema,
                "account": account,
                "format": format,
                "request_id": request_id,
            },
        )

        graph = await anyio.to_thread.run_sync(
            lambda: self.dependency_service.build_dependency_graph(
                database=database,
                schema=schema,
                account_scope=account,
                format=format,
                output_dir="./dependencies",
            )
        )

        logger.info(
            "build_dependency_graph_completed",
            extra={
                "database": database,
                "schema": schema,
                "request_id": request_id,
            },
        )

        return graph

    def get_parameter_schema(self) -> Dict[str, Any]:
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
                "request_id": {
                    "type": "string",
                    "description": "Optional request correlation ID for tracing (auto-generated if not provided)",
                },
            },
        }
