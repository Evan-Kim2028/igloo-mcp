"""Consolidated Health Check MCP Tool - Comprehensive system health validation.

Part of v1.9.0 Phase 1 - consolidates health_check, check_profile_config, and get_resource_status.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import anyio

from igloo_mcp.config import Config
from igloo_mcp.profile_utils import (
    ProfileValidationError,
    get_profile_summary,
    validate_and_resolve_profile,
)

from .base import MCPTool
from .schema_utils import boolean_schema


class HealthCheckTool(MCPTool):
    """Comprehensive MCP tool for checking system health.

    Consolidates functionality from:
    - health_check (system health)
    - check_profile_config (profile validation)
    - get_resource_status (catalog availability)
    """

    def __init__(
        self,
        config: Config,
        snowflake_service: Any,
        health_monitor: Optional[Any] = None,
        resource_manager: Optional[Any] = None,
    ):
        """Initialize health check tool.

        Args:
            config: Application configuration
            snowflake_service: Snowflake service instance
            health_monitor: Optional health monitoring instance
            resource_manager: Optional resource manager instance
        """
        self.config = config
        self.snowflake_service = snowflake_service
        self.health_monitor = health_monitor
        self.resource_manager = resource_manager

    @property
    def name(self) -> str:
        return "health_check"

    @property
    def description(self) -> str:
        return (
            "Comprehensive system health check including connection, "
            "profile, Cortex availability, and catalog status"
        )

    @property
    def category(self) -> str:
        return "diagnostics"

    @property
    def tags(self) -> list[str]:
        return ["health", "profile", "cortex", "catalog", "diagnostics"]

    @property
    def usage_examples(self) -> list[Dict[str, Any]]:
        return [
            {
                "description": "Full health check including Cortex availability",
                "parameters": {
                    "include_cortex": True,
                    "include_catalog": True,
                },
            },
            {
                "description": "Profile-only validation (skip Cortex and catalog)",
                "parameters": {
                    "include_cortex": False,
                    "include_catalog": False,
                },
            },
        ]

    async def execute(
        self,
        include_cortex: bool = True,
        include_profile: bool = True,
        include_catalog: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute comprehensive health check.

        Args:
            include_cortex: Check Cortex AI services availability
            include_profile: Validate profile configuration
            include_catalog: Check catalog availability

        Returns:
            Comprehensive health status
        """
        results: Dict[str, Any] = {}

        # Always test basic connection
        results["connection"] = await self._test_connection()

        # Optional: Check profile configuration
        if include_profile:
            results["profile"] = await self._check_profile()

        # Optional: Check Cortex availability
        if include_cortex:
            results["cortex"] = await self._check_cortex_availability()

        # Optional: Check catalog resources
        if include_catalog:
            results["catalog"] = await self._check_catalog_exists()

        # Include system health metrics if monitor available
        if self.health_monitor:
            results["system"] = self._get_system_health()

        # Overall status
        has_critical_failures = not results["connection"].get("connected", False) or (
            include_profile and results.get("profile", {}).get("status") == "invalid"
        )

        results["overall_status"] = "unhealthy" if has_critical_failures else "healthy"

        return results

    async def _test_connection(self) -> Dict[str, Any]:
        """Test basic Snowflake connectivity."""
        try:
            result = await anyio.to_thread.run_sync(self._test_connection_sync)
            return {
                "status": "connected",
                "connected": True,
                "profile": self.config.snowflake.profile,
                "warehouse": result.get("warehouse"),
                "database": result.get("database"),
                "schema": result.get("schema"),
                "role": result.get("role"),
            }
        except Exception as e:
            return {
                "status": "failed",
                "connected": False,
                "profile": self.config.snowflake.profile,
                "error": str(e),
            }

    def _test_connection_sync(self) -> Dict[str, Any]:
        """Test connection synchronously."""
        with self.snowflake_service.get_connection(
            use_dict_cursor=True,
            session_parameters=self.snowflake_service.get_query_tag_param(),
        ) as (_, cursor):
            # Get current session info
            cursor.execute("SELECT CURRENT_WAREHOUSE() as warehouse")
            warehouse_result = cursor.fetchone()

            cursor.execute("SELECT CURRENT_DATABASE() as database")
            database_result = cursor.fetchone()

            cursor.execute("SELECT CURRENT_SCHEMA() as schema")
            schema_result = cursor.fetchone()

            cursor.execute("SELECT CURRENT_ROLE() as role")
            role_result = cursor.fetchone()

            return {
                "warehouse": (
                    warehouse_result.get("warehouse") if warehouse_result else None
                ),
                "database": (
                    database_result.get("database") if database_result else None
                ),
                "schema": schema_result.get("schema") if schema_result else None,
                "role": role_result.get("role") if role_result else None,
            }

    async def _check_profile(self) -> Dict[str, Any]:
        """Validate profile configuration."""
        profile = self.config.snowflake.profile

        try:
            # Validate profile
            resolved_profile = await anyio.to_thread.run_sync(
                validate_and_resolve_profile
            )

            # Get profile summary (includes authenticator when available)
            summary = await anyio.to_thread.run_sync(get_profile_summary)

            # Derive authenticator details for troubleshooting
            auth = summary.current_profile_authenticator
            auth_info: Dict[str, Any] = {
                "authenticator": auth,
                "is_externalbrowser": (auth == "externalbrowser"),
                "is_okta_url": (isinstance(auth, str) and auth.startswith("http")),
            }
            if isinstance(auth, str) and auth.startswith("http"):
                auth_info["domain"] = auth.split("//", 1)[-1]

            return {
                "status": "valid",
                "profile": resolved_profile,
                "config": {
                    "config_path": str(summary.config_path),
                    "config_exists": summary.config_exists,
                    "available_profiles": summary.available_profiles,
                    "default_profile": summary.default_profile,
                    "current_profile": summary.current_profile,
                    "profile_count": summary.profile_count,
                },
                "authentication": auth_info,
                "warnings": [],
            }

        except ProfileValidationError as e:
            return {
                "status": "invalid",
                "profile": profile,
                "error": str(e),
            }
        except Exception as e:
            return {
                "status": "error",
                "profile": profile,
                "error": str(e),
            }

    async def _check_cortex_availability(self) -> Dict[str, Any]:
        """Check if Cortex AI services are available."""
        try:
            # Test Cortex Complete with minimal query
            async def test_cortex():
                try:
                    # Import inline to avoid dependency issues
                    from mcp_server_snowflake.cortex_services.tools import (
                        complete_cortex,
                    )

                    await complete_cortex(
                        model="mistral-large",
                        prompt="test",
                        max_tokens=5,
                        snowflake_service=self.snowflake_service,
                    )
                    return {
                        "available": True,
                        "model": "mistral-large",
                        "status": "responsive",
                    }
                except ImportError:
                    return {
                        "available": False,
                        "status": "not_installed",
                        "message": "Cortex services not available in current installation",
                    }
                except Exception as e:
                    return {
                        "available": False,
                        "status": "error",
                        "error": str(e),
                    }

            return await test_cortex()

        except Exception as e:
            return {
                "available": False,
                "status": "error",
                "error": str(e),
            }

    async def _check_catalog_exists(self) -> Dict[str, Any]:
        """Check if catalog resources are available."""
        if not self.resource_manager:
            return {
                "status": "unavailable",
                "message": "Resource manager not initialized",
            }

        try:
            resources = self.resource_manager.list_resources()
            return {
                "status": "available",
                "resource_count": len(resources) if resources else 0,
                "has_catalog": len(resources) > 0 if resources else False,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    def _get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics from monitor."""
        try:
            status = self.health_monitor.get_health_status()
            return {
                "status": status.status,
                "healthy": status.is_healthy,
                "error_count": status.error_count,
                "warning_count": status.warning_count,
                "metrics": {
                    "total_queries": status.metrics.get("total_queries", 0),
                    "successful_queries": status.metrics.get("successful_queries", 0),
                    "failed_queries": status.metrics.get("failed_queries", 0),
                },
                "recent_errors": (
                    status.recent_errors[-5:] if status.recent_errors else []
                ),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Health Check Parameters",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "include_cortex": boolean_schema(
                    "Check Cortex AI services availability",
                    default=True,
                    examples=[True, False],
                ),
                "include_profile": boolean_schema(
                    "Validate profile configuration and authenticator",
                    default=True,
                    examples=[True, False],
                ),
                "include_catalog": boolean_schema(
                    "Check catalog resource availability via resource manager",
                    default=False,
                    examples=[True, False],
                ),
            },
        }
