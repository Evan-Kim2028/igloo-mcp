"""Execute Query MCP Tool - Execute SQL queries against Snowflake.

Part of v1.8.0 Phase 2.2 - extracted from mcp_server.py.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import anyio

from igloo_mcp.config import Config
from igloo_mcp.mcp_health import MCPHealthMonitor
from igloo_mcp.service_layer import QueryService
from igloo_mcp.sql_validation import validate_sql_statement
from .base import MCPTool


class ExecuteQueryTool(MCPTool):
    """MCP tool for executing SQL queries against Snowflake."""

    def __init__(
        self,
        config: Config,
        snowflake_service: Any,
        query_service: QueryService,
        health_monitor: Optional[MCPHealthMonitor] = None,
    ):
        """Initialize execute query tool.

        Args:
            config: Application configuration
            snowflake_service: Snowflake service instance from mcp-server-snowflake
            query_service: Query service for execution
            health_monitor: Optional health monitoring instance
        """
        self.config = config
        self.snowflake_service = snowflake_service
        self.query_service = query_service
        self.health_monitor = health_monitor

    @property
    def name(self) -> str:
        return "execute_query"

    @property
    def description(self) -> str:
        return "Execute a SQL query against Snowflake"

    async def execute(
        self,
        statement: str,
        warehouse: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        role: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        verbose_errors: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute SQL query against Snowflake.

        Args:
            statement: SQL statement to execute
            warehouse: Optional warehouse override
            database: Optional database override
            schema: Optional schema override
            role: Optional role override
            timeout_seconds: Query timeout in seconds (default: 120s)
            verbose_errors: Include detailed optimization hints in errors

        Returns:
            Query results with rows, rowcount, and execution metadata

        Raises:
            ValueError: If profile validation fails or SQL is blocked
            RuntimeError: If query execution fails
        """
        # Validate profile health before executing query
        if self.health_monitor:
            profile_health = await anyio.to_thread.run_sync(
                self.health_monitor.get_profile_health,
                self.config.snowflake.profile,
                False,  # use cache
            )
            if not profile_health.is_valid:
                error_msg = (
                    profile_health.validation_error or "Profile validation failed"
                )
                available = (
                    ", ".join(profile_health.available_profiles)
                    if profile_health.available_profiles
                    else "none"
                )
                self.health_monitor.record_error(
                    f"Profile validation failed: {error_msg}"
                )
                raise ValueError(
                    f"Snowflake profile validation failed: {error_msg}. "
                    f"Profile: {self.config.snowflake.profile}, "
                    f"Available profiles: {available}. "
                    f"Check configuration with 'snow connection list' or verify profile settings."
                )

        # Validate SQL statement against permissions
        allow_list = self.config.sql_permissions.get_allow_list()
        disallow_list = self.config.sql_permissions.get_disallow_list()

        stmt_type, is_valid, error_msg = validate_sql_statement(
            statement, allow_list, disallow_list
        )

        if not is_valid and error_msg:
            if self.health_monitor:
                self.health_monitor.record_error(
                    f"SQL statement blocked: {stmt_type} - {statement[:100]}"
                )
            raise ValueError(error_msg)

        # Prepare session context overrides
        overrides = {
            "warehouse": warehouse,
            "database": database,
            "schema": schema,
            "role": role,
        }
        # Filter out None values
        overrides = {k: v for k, v in overrides.items() if v is not None}

        # Execute query with session context management
        timeout = timeout_seconds or getattr(self.config, "timeout_seconds", 120)

        try:
            result = await anyio.to_thread.run_sync(
                self._execute_query_sync,
                statement,
                overrides,
                timeout,
            )

            if self.health_monitor and hasattr(
                self.health_monitor, "record_query_success"
            ):
                self.health_monitor.record_query_success(statement[:100])  # type: ignore[attr-defined]

            return result

        except Exception as e:
            error_message = str(e)

            if self.health_monitor:
                self.health_monitor.record_error(
                    f"Query execution failed: {error_message[:200]}"
                )

            if verbose_errors:
                # Return detailed error with optimization hints
                raise RuntimeError(
                    f"Query execution failed: {error_message}\n\n"
                    f"Query: {statement[:200]}{'...' if len(statement) > 200 else ''}\n"
                    f"Timeout: {timeout}s\n"
                    f"Context: {overrides}"
                )
            else:
                # Return compact error
                raise RuntimeError(
                    f"Query execution failed: {error_message[:150]}. "
                    f"Use verbose_errors=true for details."
                )

    def _execute_query_sync(
        self,
        statement: str,
        overrides: Dict[str, Any],
        timeout: int,
    ) -> Dict[str, Any]:
        """Execute query synchronously with session context management."""
        try:
            # Use QueryService to execute the query
            result = self.query_service.execute_with_service(
                statement,
                service=self.snowflake_service,
                session=overrides,
                output_format="json",
                timeout=timeout
            )
            
            return {
                "statement": statement,
                "rowcount": len(result.rows) if result.rows else 0,
                "rows": result.rows or [],
            }
        except Exception as e:
            raise RuntimeError(f"Query execution failed: {e}") from e

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "statement": {
                    "type": "string",
                    "description": "SQL statement to execute",
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
                "role": {
                    "type": "string",
                    "description": "Role override",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Query timeout in seconds (default: 120s from config)",
                    "minimum": 1,
                    "maximum": 3600,
                },
                "verbose_errors": {
                    "type": "boolean",
                    "description": "Include detailed optimization hints in error messages",
                    "default": False,
                },
            },
            "required": ["statement"],
        }
