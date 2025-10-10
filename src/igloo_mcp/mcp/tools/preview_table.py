"""Preview Table MCP Tool - Preview table contents with configurable limit.

Part of v1.8.0 Phase 2.2 - extracted from mcp_server.py.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ...config import Config
from ...service_layer import QueryService
from .base import MCPTool


class PreviewTableTool(MCPTool):
    """MCP tool for previewing table contents."""

    def __init__(
        self,
        config: Config,
        snowflake_service: Any,
        query_service: QueryService,
    ):
        """Initialize preview table tool.

        Args:
            config: Application configuration
            snowflake_service: Snowflake service instance
            query_service: Query service for execution
        """
        self.config = config
        self.snowflake_service = snowflake_service
        self.query_service = query_service

    @property
    def name(self) -> str:
        return "preview_table"

    @property
    def description(self) -> str:
        return "Preview table contents with configurable row limit"

    async def execute(
        self,
        table_name: str,
        limit: int = 100,
        warehouse: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Preview table contents.

        Args:
            table_name: Fully qualified table name
            limit: Row limit (default: 100, min: 1)
            warehouse: Optional warehouse override
            database: Optional database override
            schema: Optional schema override

        Returns:
            Table preview with rows and metadata

        Raises:
            ValueError: If limit is invalid or table name is empty
            RuntimeError: If query execution fails
        """
        if not table_name or not table_name.strip():
            raise ValueError("Table name cannot be empty")

        if limit < 1:
            raise ValueError("Limit must be at least 1")

        # Build preview query
        statement = f"SELECT * FROM {table_name} LIMIT {limit}"

        # Prepare context overrides
        overrides = {
            "warehouse": warehouse,
            "database": database,
            "schema": schema,
        }
        packed = {k: v for k, v in overrides.items() if v}

        try:
            from functools import partial

            import anyio

            session_ctx = self.query_service.session_from_mapping(packed)

            result = await anyio.to_thread.run_sync(
                partial(
                    self.query_service.execute_with_service,
                    statement,
                    service=self.snowflake_service,
                    session=session_ctx,
                    output_format="json",
                )
            )

            return {
                "status": "success",
                "table_name": table_name,
                "limit": limit,
                "preview": {
                    "columns": result.columns,
                    "rows": result.rows,
                    "limit": limit
                }
            }

        except Exception as e:
            raise RuntimeError(f"Failed to preview table '{table_name}': {e}") from e

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "Fully qualified table name (e.g., DATABASE.SCHEMA.TABLE)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of rows to return",
                    "minimum": 1,
                    "default": 100,
                },
                "warehouse": {
                    "type": "string",
                    "description": "Warehouse override",
                },
                "database": {
                    "type": "string",
                    "description": "Database override",
                },
                "schema": {
                    "type": "string",
                    "description": "Schema override",
                },
            },
            "required": ["table_name"],
        }
