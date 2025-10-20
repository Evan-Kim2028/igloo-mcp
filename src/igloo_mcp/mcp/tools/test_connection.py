"""Test Connection MCP Tool - Lightweight Snowflake connection test.

Part of v1.9.0 Phase 1 - simplified wrapper around HealthCheckTool for backward compatibility.
"""

from __future__ import annotations

from typing import Any, Dict

from igloo_mcp.config import Config

from .base import MCPTool
from .health import HealthCheckTool


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
        return "Quick Snowflake connection test (lightweight)"

    @property
    def category(self) -> str:
        return "diagnostics"

    @property
    def tags(self) -> list[str]:
        return ["connection", "health", "diagnostics"]

    @property
    def usage_examples(self) -> list[Dict[str, Any]]:
        return [
            {
                "description": "Check active profile connectivity before running queries",
                "parameters": {},
            }
        ]

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Test Snowflake connection.

        Returns:
            Connection test results with status and details
        """
        # Delegate to health check tool's connection test
        return await self._health_tool._test_connection()

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        }
