"""Build Dependency Graph MCP Tool - Build object dependency graph.

Part of v1.8.0 Phase 2.2 - extracted from mcp_server.py.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import anyio

from ...dependency import DependencyService
from .base import MCPTool


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
        if format not in ("json", "dot"):
            raise ValueError(f"Invalid format '{format}'. Must be 'json' or 'dot'")

        try:
            graph = await anyio.to_thread.run_sync(
                lambda: self.dependency_service.build(
                    database=database,
                    schema=schema,
                    account_scope=account_scope,
                )
            )

            if format == "dot":
                dot_output = self.dependency_service.to_dot(graph)
                return {
                    "format": "dot",
                    "content": dot_output,
                    "node_count": graph.counts.nodes,
                    "edge_count": graph.counts.edges,
                }
            else:
                return {
                    "format": "json",
                    "nodes": [node.model_dump() for node in graph.nodes],
                    "edges": [edge.model_dump() for edge in graph.edges],
                    "counts": graph.counts.model_dump(),
                    "scope": graph.scope.model_dump(),
                }

        except Exception as e:
            raise RuntimeError(f"Dependency graph build failed: {e}") from e

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "database": {
                    "type": "string",
                    "description": "Specific database to analyze",
                },
                "schema": {
                    "type": "string",
                    "description": "Specific schema to analyze",
                },
                "account_scope": {
                    "type": "boolean",
                    "description": "Use ACCOUNT_USAGE for broader coverage",
                    "default": True,
                },
                "format": {
                    "type": "string",
                    "description": "Output format",
                    "enum": ["json", "dot"],
                    "default": "json",
                },
            },
        }
