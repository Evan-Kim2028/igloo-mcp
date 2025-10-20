"""Build Dependency Graph MCP Tool - Build object dependency graph.

Part of v1.8.0 Phase 2.2 - extracted from mcp_server.py.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import anyio

from igloo_mcp.service_layer import DependencyService

from .base import MCPTool
from .schema_utils import boolean_schema, enum_schema, snowflake_identifier_schema


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
        return "Build object dependency graph from Snowflake metadata"

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
                    "account_scope": True,
                    "format": "json",
                },
            },
            {
                "description": "Generate DOT graph for analytics schema",
                "parameters": {
                    "database": "ANALYTICS",
                    "schema": "REPORTING",
                    "account_scope": False,
                    "format": "dot",
                },
            },
        ]

    async def execute(
        self,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        account_scope: bool = True,
        format: str = "json",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Build dependency graph.

        Args:
            database: Specific database to analyze
            schema: Specific schema to analyze
            account_scope: Use ACCOUNT_USAGE for broader coverage (default: True)
            format: Output format - 'json' or 'dot' (default: json)

        Returns:
            Dependency graph with nodes and edges

        Raises:
            ValueError: If format is invalid
            RuntimeError: If graph build fails
        """
        if format not in {"json", "dot"}:
            raise ValueError(f"Invalid format '{format}'. Must be 'json' or 'dot'")

        try:
            graph = await anyio.to_thread.run_sync(
                lambda: self.dependency_service.build_dependency_graph(
                    database=database,
                    schema=schema,
                    account_scope=account_scope,
                    format=format,
                    output_dir="./dependencies",
                )
            )
            return graph
        except Exception as e:
            raise RuntimeError(f"Dependency graph build failed: {e}") from e

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
                "account_scope": boolean_schema(
                    "Include ACCOUNT_USAGE views for cross-database dependencies.",
                    default=True,
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
            },
        }
