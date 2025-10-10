"""Query Lineage MCP Tool - Query cached lineage graph.

Part of v1.8.0 Phase 2.2 - extracted from mcp_server.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import anyio

from ...config import Config
from ...lineage import LineageQueryService
from ...lineage.identifiers import parse_table_name
from .base import MCPTool


class QueryLineageTool(MCPTool):
    """MCP tool for querying lineage graphs."""

    def __init__(self, config: Config):
        """Initialize query lineage tool.

        Args:
            config: Application configuration
        """
        self.config = config

    @property
    def name(self) -> str:
        return "query_lineage"

    @property
    def description(self) -> str:
        return "Query cached lineage graph for object dependencies"

    async def execute(
        self,
        object_name: str,
        direction: str = "both",
        depth: int = 3,
        format: str = "text",
        catalog_dir: str = "./data_catalogue",
        cache_dir: str = "./lineage",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Query lineage for an object.

        Args:
            object_name: Object name to analyze
            direction: Traversal direction - 'upstream', 'downstream', or 'both'
            depth: Traversal depth (1-10)
            format: Output format - 'text' or 'json'
            catalog_dir: Catalog directory path
            cache_dir: Lineage cache directory path

        Returns:
            Lineage query results

        Raises:
            ValueError: If object not found or parameters invalid
            RuntimeError: If lineage query fails
        """
        if direction not in ("upstream", "downstream", "both"):
            raise ValueError(
                f"Invalid direction '{direction}'. Must be 'upstream', 'downstream', or 'both'"
            )

        if not 1 <= depth <= 10:
            raise ValueError(f"Depth must be between 1 and 10, got {depth}")

        if format not in ("text", "json"):
            raise ValueError(f"Invalid format '{format}'. Must be 'text' or 'json'")

        try:
            result = await anyio.to_thread.run_sync(
                self._query_lineage_sync,
                object_name,
                direction,
                depth,
                format,
                catalog_dir,
                cache_dir,
            )
            return result

        except KeyError as e:
            raise ValueError(
                f"Object '{object_name}' not found in lineage graph. "
                f"Ensure catalog has been built for this object."
            ) from e
        except Exception as e:
            raise RuntimeError(f"Lineage query failed: {e}") from e

    def _query_lineage_sync(
        self,
        object_name: str,
        direction: str,
        depth: int,
        fmt: str,
        catalog_dir: str,
        cache_dir: str,
    ) -> Dict[str, Any]:
        """Query lineage synchronously."""
        service = LineageQueryService(
            catalog_dir=Path(catalog_dir), cache_root=Path(cache_dir)
        )

        default_db = self.config.snowflake.database
        default_schema = self.config.snowflake.schema
        qualified = parse_table_name(object_name).with_defaults(
            default_db, default_schema
        )
        base_key = qualified.key()
        candidates = [base_key]
        if not base_key.endswith("::task"):
            candidates.append(f"{base_key}::task")

        result = None
        resolved_key: Optional[str] = None
        for candidate in candidates:
            try:
                result = service.object_subgraph(
                    candidate, direction=direction, depth=depth
                )
                resolved_key = candidate
                break
            except KeyError:
                continue

        if result is None or resolved_key is None:
            raise KeyError(f"Object '{object_name}' not found in lineage graph")

        if fmt == "json":
            return {
                "object": resolved_key,
                "direction": direction,
                "depth": depth,
                "format": "json",
                "result": (
                    result.model_dump() if hasattr(result, "model_dump") else result
                ),
            }
        else:
            # Text format
            return {
                "object": resolved_key,
                "direction": direction,
                "depth": depth,
                "format": "text",
                "result": str(result),
            }

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Object name to analyze (e.g., DATABASE.SCHEMA.TABLE)",
                },
                "direction": {
                    "type": "string",
                    "description": "Traversal direction",
                    "enum": ["upstream", "downstream", "both"],
                    "default": "both",
                },
                "depth": {
                    "type": "integer",
                    "description": "Traversal depth",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 3,
                },
                "format": {
                    "type": "string",
                    "description": "Output format",
                    "enum": ["text", "json"],
                    "default": "text",
                },
                "catalog_dir": {
                    "type": "string",
                    "description": "Catalog directory",
                    "default": "./data_catalogue",
                },
                "cache_dir": {
                    "type": "string",
                    "description": "Lineage cache directory",
                    "default": "./lineage",
                },
            },
            "required": ["object_name"],
        }
