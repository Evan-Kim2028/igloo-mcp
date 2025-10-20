"""Get Catalog Summary MCP Tool - Retrieve catalog summary information.

Part of v1.8.0 Phase 2.2 - extracted from mcp_server.py.
"""

from __future__ import annotations

from typing import Any, Dict

import anyio

from igloo_mcp.catalog import CatalogService

from .base import MCPTool
from .schema_utils import string_schema


class GetCatalogSummaryTool(MCPTool):
    """MCP tool for getting catalog summary."""

    def __init__(self, catalog_service: CatalogService):
        """Initialize get catalog summary tool.

        Args:
            catalog_service: Catalog service instance
        """
        self.catalog_service = catalog_service

    @property
    def name(self) -> str:
        return "get_catalog_summary"

    @property
    def description(self) -> str:
        return "Retrieve summary information from existing catalog"

    @property
    def category(self) -> str:
        return "metadata"

    @property
    def tags(self) -> list[str]:
        return ["catalog", "summary", "metadata"]

    @property
    def usage_examples(self) -> list[Dict[str, Any]]:
        return [
            {
                "description": "Inspect default catalog directory",
                "parameters": {},
            },
            {
                "description": "Load summary from custom artifacts folder",
                "parameters": {"catalog_dir": "./artifacts/catalog"},
            },
        ]

    async def execute(
        self, catalog_dir: str = "./data_catalogue", **kwargs: Any
    ) -> Dict[str, Any]:
        """Get catalog summary.

        Args:
            catalog_dir: Catalog directory path (default: ./data_catalogue)

        Returns:
            Catalog summary with metadata and statistics

        Raises:
            FileNotFoundError: If catalog directory or summary file not found
            RuntimeError: If summary cannot be loaded
        """
        try:
            summary = await anyio.to_thread.run_sync(
                self.catalog_service.load_summary, catalog_dir
            )
            return {"status": "success", "catalog_dir": catalog_dir, "summary": summary}

        except FileNotFoundError:
            return {
                "status": "error",
                "error": f"No catalog found in '{catalog_dir}'. Run build_catalog first to generate the catalog.",
                "catalog_dir": catalog_dir,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to load catalog summary: {e}",
                "catalog_dir": catalog_dir,
            }

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Catalog Summary Parameters",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "catalog_dir": string_schema(
                    "Catalog directory path containing summary artifacts.",
                    title="Catalog Directory",
                    default="./data_catalogue",
                    examples=["./data_catalogue", "./artifacts/catalog"],
                ),
            },
        }
