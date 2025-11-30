"""Consolidated Health Check MCP Tool - Comprehensive system health validation.

Part of v1.9.0 Phase 1 - consolidates health_check, check_profile_config, and get_resource_status.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import anyio

from igloo_mcp.config import Config
from igloo_mcp.mcp.validation_helpers import validate_response_mode
from igloo_mcp.profile_utils import (
    ProfileValidationError,
    get_profile_summary,
    validate_and_resolve_profile,
)

from .base import MCPTool, ensure_request_id, tool_error_handler
from .schema_utils import boolean_schema

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


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
            "Comprehensive system health check including connection, profile validation, "
            "Cortex availability, and catalog status. Use this for thorough diagnostics "
            "or troubleshooting. For quick connectivity checks, use test_connection instead. "
            "Supports optional checks via include_cortex, include_profile, and include_catalog parameters."
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

    @tool_error_handler("health_check")
    async def execute(
        self,
        response_mode: Optional[str] = None,
        detail_level: Optional[str] = None,  # DEPRECATED in v0.3.5
        include_cortex: bool = True,
        include_profile: bool = True,
        include_catalog: bool = False,
        request_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Comprehensive health check of system components.

        Args:
            response_mode: Response verbosity level (STANDARD):
                - "minimal": Just overall status and component health (~50 tokens)
                - "standard": + Remediation guidance (~200 tokens, default)
                - "full": + Diagnostic details (~400 tokens)
            detail_level: DEPRECATED - use response_mode instead
            include_cortex: Check Cortex AI services availability
            include_profile: Validate profile configuration
            include_catalog: Check catalog availability
            request_id: Optional request ID for tracing

        Returns:
            Health check results with optional detail levels
        """
        # Timing and request correlation
        start_time = time.time()
        request_id = ensure_request_id(request_id)

        # Validate response_mode with backward compatibility
        mode = validate_response_mode(
            response_mode,
            legacy_param_name="detail_level",
            legacy_param_value=detail_level,
            valid_modes=("minimal", "standard", "full"),
            default="standard",
        )

        logger.info(
            "health_check_started",
            extra={
                "include_cortex": include_cortex,
                "include_profile": include_profile,
                "include_catalog": include_catalog,
                "request_id": request_id,
            },
        )

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

        # Calculate total duration
        total_duration = (time.time() - start_time) * 1000

        logger.info(
            "health_check_completed",
            extra={
                "overall_status": results["overall_status"],
                "request_id": request_id,
                "total_duration_ms": total_duration,
            },
        )

        # Determine overall status
        overall_status = results.get("overall_status", "unknown")

        # Determine component statuses for summary mode
        snowflake_health = results.get("connection", {}).get("status", "unknown")
        catalog_health = results.get("catalog", {}).get("status", "unknown")
        profile_health = results.get("profile", {}).get("status", "unknown")

        # Build response based on response_mode
        if mode == "minimal":
            # Minimal response - just statuses
            return {
                "status": overall_status,
                "request_id": request_id,
                "components": {
                    "snowflake": snowflake_health,
                    "catalog": catalog_health,
                    "profile": profile_health,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "timing": {
                    "total_duration_ms": round(total_duration, 2),
                },
            }

        # Standard and full modes
        response = {
            "status": overall_status,
            "request_id": request_id,
            "checks": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "timing": {
                "total_duration_ms": round(total_duration, 2),
            },
        }

        # Add remediation for standard and full modes
        if mode in ("standard", "full"):
            # Add remediation guidance for degraded/unhealthy components
            remediation: Dict[str, Any] = {}

            # Catalog health remediation
            catalog_health = results.get("catalog", {}).get("status", "unknown")
            catalog_age_days = results.get("catalog", {}).get("age_days")
            catalog_exists = results.get("catalog", {}).get("exists")
            if catalog_health != "healthy":
                if catalog_age_days and catalog_age_days > 7:
                    remediation["catalog"] = (
                        f"Catalog is {catalog_age_days} days old. "
                        "Run build_catalog to refresh metadata and improve search accuracy"
                    )
                elif not catalog_exists:
                    remediation["catalog"] = "No catalog found. Run build_catalog to enable offline object search"

            # Snowflake connection remediation
            snowflake_health = results.get("connection", {}).get("status", "unknown")
            if snowflake_health != "healthy":
                remediation["snowflake"] = (
                    "Snowflake connection failed. Run test_connection for detailed diagnostics, "
                    "or check SNOWFLAKE_PROFILE environment variable"
                )

            # Profile health remediation
            profile_health = results.get("profile", {}).get("status", "unknown")
            profile_name = results.get("profile", {}).get("name")
            if profile_health != "healthy":
                remediation["profile"] = (
                    f"Profile '{profile_name}' configuration issues detected. "
                    "Check ~/.snowflake/config.toml or run test_connection"
                )

            if remediation:
                response["remediation"] = remediation
                response["next_steps"] = "Address remediation items to improve system health"

        # Add full diagnostics for full mode
        if mode == "full":
            # Add diagnostic details
            diagnostics = {}

            if "profile" in results:
                diagnostics["profile"] = {
                    "config_path": "~/.snowflake/config.toml",
                    "active_profile": results.get("profile", {}).get("name"),
                }

            if "catalog" in results and results["catalog"].get("exists"):
                diagnostics["catalog"] = {
                    "path": results["catalog"].get("path"),
                    "object_count": results["catalog"].get("object_count", 0),
                    "last_build": results["catalog"].get("created_at"),
                }

            if diagnostics:
                response["diagnostics"] = diagnostics

        return response

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
                "status": "error",
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

            def _pick(d: Dict[str, Any] | None, lower: str, upper: str) -> Any:
                if not isinstance(d, dict):
                    return None
                return d.get(lower) if lower in d else d.get(upper)

            return {
                "warehouse": _pick(warehouse_result, "warehouse", "WAREHOUSE"),
                "database": _pick(database_result, "database", "DATABASE"),
                "schema": _pick(schema_result, "schema", "SCHEMA"),
                "role": _pick(role_result, "role", "ROLE"),
            }

    async def _check_profile(self) -> Dict[str, Any]:
        """Validate profile configuration."""
        profile = self.config.snowflake.profile

        try:
            # Validate profile
            resolved_profile = await anyio.to_thread.run_sync(validate_and_resolve_profile)

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
        if not self.health_monitor:
            return {
                "status": "unavailable",
                "error": "health monitor not configured",
            }

        try:
            if hasattr(self.health_monitor, "get_comprehensive_health"):
                status = self.health_monitor.get_comprehensive_health(snowflake_service=self.snowflake_service)
                overall_status = getattr(status.overall_status, "value", str(status.overall_status))
                recent_errors = [status.last_error] if getattr(status, "last_error", None) else []
                return {
                    "status": overall_status,
                    "healthy": overall_status == "healthy",
                    "error_count": getattr(status, "error_count", 0),
                    "warning_count": 0,  # Not tracked in current monitor
                    "metrics": {
                        "uptime_seconds": getattr(status, "uptime_seconds", 0),
                    },
                    "recent_errors": recent_errors,
                }

            legacy_status = (
                self.health_monitor.get_health_status() if hasattr(self.health_monitor, "get_health_status") else None
            )
            if legacy_status is not None:
                return {
                    "status": getattr(legacy_status, "status", "unknown"),
                    "healthy": getattr(legacy_status, "is_healthy", False),
                    "error_count": getattr(legacy_status, "error_count", 0),
                    "warning_count": getattr(legacy_status, "warning_count", 0),
                    "metrics": getattr(legacy_status, "metrics", {}),
                    "recent_errors": getattr(legacy_status, "recent_errors", []),
                }

            return {
                "status": "unknown",
                "healthy": False,
                "error": "health monitor missing status methods",
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
                "request_id": {
                    "type": "string",
                    "description": "Optional request correlation ID for tracing (auto-generated if not provided)",
                },
            },
        }
