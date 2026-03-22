"""Switch Profile MCP Tool - Change active Snowflake profile mid-session.

Allows switching the active Snowflake profile without restarting the MCP server.
Updates config and environment variables, then validates the new connection.
"""

from __future__ import annotations

import os
from typing import Any

from igloo_mcp import profile_utils
from igloo_mcp.config import Config, apply_config_overrides, get_config
from igloo_mcp.mcp.compat import get_logger
from igloo_mcp.profile_utils import ProfileValidationError

from .base import MCPTool, ensure_request_id, tool_error_handler

logger = get_logger(__name__)


class SwitchProfileTool(MCPTool):
    """MCP tool for switching the active Snowflake profile mid-session.

    Updates the active profile in config and environment, then optionally
    validates the new connection.
    """

    def __init__(self, config: Config, snowflake_service: Any):
        self.config = config
        self.snowflake_service = snowflake_service

    @property
    def name(self) -> str:
        return "switch_profile"

    @property
    def description(self) -> str:
        return "Switch active Snowflake profile mid-session. Validates before switching."

    @property
    def category(self) -> str:
        return "profile"

    @property
    def tags(self) -> list[str]:
        return ["profile", "connection", "configuration", "switch"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
        return [
            {
                "description": "Switch to production profile",
                "parameters": {"profile_name": "prod"},
            },
            {
                "description": "Switch profile and validate connection",
                "parameters": {"profile_name": "staging", "validate_connection": True},
            },
        ]

    @tool_error_handler("switch_profile")
    async def execute(
        self,
        profile_name: str,
        validate_connection: bool = True,
        request_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Switch the active Snowflake profile.

        Args:
            profile_name: Name of the profile to switch to
            validate_connection: Whether to test the new connection after switching
            request_id: Optional request correlation ID for tracing

        Returns:
            Switch result with previous/new profile info and validation status
        """
        request_id = ensure_request_id(request_id)

        logger.info(
            "switch_profile_started",
            extra={
                "target_profile": profile_name,
                "request_id": request_id,
            },
        )

        config = get_config()
        previous_profile = config.snowflake.profile

        # Don't switch if already on the requested profile
        if profile_name == previous_profile:
            return {
                "status": "no_change",
                "message": f"Already using profile '{profile_name}'",
                "active_profile": profile_name,
                "request_id": request_id,
            }

        # Validate the target profile exists in config.toml
        available = profile_utils.get_available_profiles()
        if profile_name not in available:
            return {
                "status": "error",
                "error": f"Profile '{profile_name}' not found",
                "available_profiles": sorted(available),
                "active_profile": previous_profile,
                "request_id": request_id,
            }

        # Validate profile configuration
        try:
            profile_utils.validate_profile(profile_name)
        except ProfileValidationError as e:
            return {
                "status": "error",
                "error": f"Profile '{profile_name}' validation failed: {e}",
                "active_profile": previous_profile,
                "request_id": request_id,
            }

        # Apply the profile switch
        os.environ["SNOWFLAKE_PROFILE"] = profile_name
        os.environ["SNOWFLAKE_DEFAULT_CONNECTION_NAME"] = profile_name
        apply_config_overrides(snowflake={"profile": profile_name})

        # Get details of the new profile
        details = profile_utils.get_profile_details(profile_name)

        result: dict[str, Any] = {
            "status": "switched",
            "previous_profile": previous_profile,
            "active_profile": profile_name,
            "details": details,
            "request_id": request_id,
            "note": (
                "Profile config and environment updated. "
                "Existing Snowflake connections may still use the previous profile "
                "until the server is restarted."
            ),
        }

        # Optionally validate the new connection
        if validate_connection:
            connection_result = await self._test_new_connection()
            result["connection_test"] = connection_result
            if not connection_result.get("connected", False):
                result["status"] = "switched_with_warning"
                result["warning"] = (
                    f"Switched to '{profile_name}' but connection test failed. "
                    "The profile config is valid but the connection may need attention."
                )

        logger.info(
            "switch_profile_completed",
            extra={
                "previous_profile": previous_profile,
                "new_profile": profile_name,
                "status": result["status"],
                "request_id": request_id,
            },
        )

        return result

    async def _test_new_connection(self) -> dict[str, Any]:
        """Test connectivity with the current (newly switched) profile."""
        import anyio

        try:

            def _test_sync() -> dict[str, Any]:
                with self.snowflake_service.get_connection(
                    use_dict_cursor=True,
                    session_parameters=self.snowflake_service.get_query_tag_param(),
                ) as (_, cursor):
                    cursor.execute("SELECT CURRENT_WAREHOUSE() as warehouse")
                    wh = cursor.fetchone()
                    cursor.execute("SELECT CURRENT_ROLE() as role")
                    rl = cursor.fetchone()
                    return {
                        "connected": True,
                        "warehouse": (wh or {}).get("warehouse") or (wh or {}).get("WAREHOUSE"),
                        "role": (rl or {}).get("role") or (rl or {}).get("ROLE"),
                    }

            return await anyio.to_thread.run_sync(_test_sync)
        except Exception as e:  # noqa: BLE001 - provider backends surface heterogeneous connection errors
            return {
                "connected": False,
                "error": str(e),
            }

    def get_parameter_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["profile_name"],
            "properties": {
                "profile_name": {
                    "type": "string",
                    "description": "Profile name (see list_profiles)",
                },
                "validate_connection": {
                    "type": "boolean",
                    "description": "Test connection after switch",
                    "default": True,
                },
            },
        }
