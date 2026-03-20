"""List Profiles MCP Tool - Discover available Snowflake profiles.

Lists all profiles from ~/.snowflake/config.toml with metadata about
which profile is active, which is default, and connection details.
"""

from __future__ import annotations

from typing import Any

from igloo_mcp import profile_utils
from igloo_mcp.config import Config, get_config
from igloo_mcp.mcp.compat import get_logger

from .base import MCPTool, ensure_request_id, tool_error_handler

logger = get_logger(__name__)


class ListProfilesTool(MCPTool):
    """MCP tool for listing available Snowflake profiles.

    Returns all profiles from the Snowflake CLI config with metadata
    including active status, default status, and connection details.
    """

    def __init__(self, config: Config):
        self.config = config

    @property
    def name(self) -> str:
        return "list_profiles"

    @property
    def description(self) -> str:
        return (
            "List all available Snowflake connection profiles. "
            "Shows which profile is active, which is default, and connection details "
            "(account, warehouse, database, role). Use to discover profiles before switching."
        )

    @property
    def category(self) -> str:
        return "profile"

    @property
    def tags(self) -> list[str]:
        return ["profile", "connection", "configuration", "discovery"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
        return [
            {
                "description": "List all available profiles with details",
                "parameters": {"include_details": True},
            },
            {
                "description": "Quick list of profile names only",
                "parameters": {"include_details": False},
            },
        ]

    @tool_error_handler("list_profiles")
    async def execute(
        self,
        include_details: bool = True,
        request_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """List available Snowflake profiles.

        Args:
            include_details: Include connection details (account, warehouse, etc.)
            request_id: Optional request correlation ID for tracing

        Returns:
            Dictionary with profile listing and metadata
        """
        request_id = ensure_request_id(request_id)

        logger.info(
            "list_profiles_started",
            extra={"request_id": request_id},
        )

        config = get_config()
        active_profile = config.snowflake.profile
        default_profile = profile_utils.get_default_profile()
        available = sorted(profile_utils.get_available_profiles())
        config_path = profile_utils.get_snowflake_config_path()

        profiles: list[dict[str, Any]] = []

        if include_details:
            all_details = profile_utils.get_all_profile_details()
            for name in available:
                entry: dict[str, Any] = {
                    "name": name,
                    "is_active": name == active_profile,
                    "is_default": name == default_profile,
                }
                details = all_details.get(name, {})
                if details:
                    entry["details"] = details
                profiles.append(entry)
        else:
            for name in available:
                profiles.append({
                    "name": name,
                    "is_active": name == active_profile,
                    "is_default": name == default_profile,
                })

        result: dict[str, Any] = {
            "active_profile": active_profile,
            "default_profile": default_profile,
            "profile_count": len(available),
            "profiles": profiles,
            "config_path": str(config_path),
            "request_id": request_id,
        }

        logger.info(
            "list_profiles_completed",
            extra={
                "profile_count": len(available),
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
                "include_details": {
                    "type": "boolean",
                    "description": "Include connection details (account, warehouse, database, role) for each profile",
                    "default": True,
                },
                "request_id": {
                    "type": "string",
                    "description": "Optional request correlation ID for tracing",
                },
            },
        }
