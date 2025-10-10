"""Build Catalog MCP Tool - Build Snowflake catalog metadata.

Part of v1.8.0 Phase 2.2 - extracted from mcp_server.py.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import anyio

from igloo_mcp.catalog import CatalogService
from igloo_mcp.config import Config
from .base import MCPTool


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
        return "Build comprehensive Snowflake catalog metadata from INFORMATION_SCHEMA. Includes databases, schemas, tables, views, materialized views, dynamic tables, tasks, user-defined functions, procedures, and columns. Only includes user-defined functions (excludes built-in Snowflake operators)."

    async def execute(
        self,
        output_dir: str = "./data_catalogue",
        database: Optional[str] = None,
        account: bool = False,
        output_format: str = "json",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Build comprehensive Snowflake catalog metadata.

        This tool queries Snowflake INFORMATION_SCHEMA to build a comprehensive
        metadata catalog including all database objects. It uses optimized
        queries and proper filtering to ensure accurate and relevant results.

        Key Features:
        - Real Snowflake metadata queries (not mock data)
        - Comprehensive coverage: databases, schemas, tables, views, materialized views, dynamic tables, tasks, functions, procedures, columns
        - Function filtering: Only user-defined functions (excludes built-in operators like !=, %, *, +, -)
        - Structured JSON output with detailed metadata
        - Account-wide or database-specific catalog building

        Args:
            output_dir: Catalog output directory (default: ./data_catalogue)
            database: Specific database to introspect (default: current)
            account: Include entire account (default: False)
            output_format: Output format - 'json' or 'jsonl' (default: json)

        Returns:
            Catalog build results with totals for each object type

        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If catalog build fails
        """
        if output_format not in ("json", "jsonl"):
            raise ValueError(f"Invalid output_format '{output_format}'. Must be 'json' or 'jsonl'")

        try:
            result = await anyio.to_thread.run_sync(
                lambda: self.catalog_service.build(
                    output_dir=output_dir,
                    database=database,
                    account_scope=account,
                    output_format=output_format,
                    include_ddl=True,
                    max_ddl_concurrency=8,
                    catalog_concurrency=16,
                    export_sql=False,
                )
            )

            return {
                "status": "success",
                "output_dir": output_dir,
                "database": database or "current",
                "account_scope": account,
                "format": output_format,
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

        except Exception as e:
            raise RuntimeError(f"Catalog build failed: {e}") from e

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "output_dir": {
                    "type": "string",
                    "description": "Catalog output directory",
                    "default": "./data_catalogue",
                },
                "database": {
                    "type": "string",
                    "description": "Specific database to introspect (default: current database)",
                },
                "account": {
                    "type": "boolean",
                    "description": "Include entire account",
                    "default": False,
                },
                "format": {
                    "type": "string",
                    "description": "Output format",
                    "enum": ["json", "jsonl"],
                    "default": "json",
                },
            },
        }
