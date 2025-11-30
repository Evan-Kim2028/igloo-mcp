"""Test Connection MCP Tool - Lightweight Snowflake connection test.

Part of v1.9.0 Phase 1 - simplified wrapper around HealthCheckTool for backward compatibility.
"""

from __future__ import annotations

from typing import Any

from igloo_mcp.config import Config

from .base import MCPTool, tool_error_handler
from .health import HealthCheckTool

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class ConnectionTestTool(MCPTool):
    """Lightweight MCP tool for testing Snowflake connection.

    This is a simplified wrapper around HealthCheckTool that only tests
    the basic connection without additional checks.
    """

    def __init__(self, config: Config, snowflake_service: Any):
        """Initialize test connection tool.

        Args:
            config: Application configuration
            snowflake_service: Snowflake service instance
        """
        self.config = config
        self.snowflake_service = snowflake_service
        # Create health check tool for delegation
        self._health_tool = HealthCheckTool(
            config=config,
            snowflake_service=snowflake_service,
        )

    @property
    def name(self) -> str:
        return "test_connection"

    @property
    def description(self) -> str:
        return (
            "Quick lightweight Snowflake connection test. Verifies basic connectivity "
            "and returns active warehouse/database/schema/role. Use this for simple "
            "connectivity checks before running queries. For comprehensive health "
            "validation including profile, Cortex, and catalog status, use health_check instead."
        )

    @property
    def category(self) -> str:
        return "diagnostics"

    @property
    def tags(self) -> list[str]:
        return ["connection", "health", "diagnostics"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
        return [
            {
                "description": "Check active profile connectivity before running queries",
                "parameters": {},
            }
        ]

    @tool_error_handler("test_connection")
    async def execute(self, request_id: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Test Snowflake connection.

        Args:
            request_id: Optional request correlation ID for tracing (auto-generated if not provided)

        Returns:
            Connection test results with status and details
        """
        logger.info(
            "test_connection_started",
            extra={
                "request_id": request_id,
            },
        )

        # Delegate to health check tool's connection test
        result = await self._health_tool._test_connection()

        logger.info(
            "test_connection_completed",
            extra={
                "connected": result.get("connected", False),
                "request_id": request_id,
            },
        )

        return result

    def get_parameter_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "request_id": {
                    "type": "string",
                    "description": "Optional request correlation ID for tracing (auto-generated if not provided)",
                },
            },
        }
