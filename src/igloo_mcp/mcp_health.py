"""MCP server health monitoring and diagnostics for Snowflake profile configuration.

This module provides comprehensive health monitoring capabilities for the MCP server,
with particular focus on Snowflake profile configuration validation and error reporting
that follows MCP protocol standards.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

from .error_handling import ProfileConfigurationError
from .profile_utils import (
    get_profile_summary,
    get_snowflake_config_path,
    validate_profile,
)

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Standard health status values for MCP server components."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class MCPErrorCode(Enum):
    """MCP-compliant error codes for server errors."""

    # Standard JSON-RPC 2.0 error codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # MCP server error codes (32xxx range)
    SERVER_ERROR = -32000
    CONFIGURATION_ERROR = -32001
    CONNECTION_ERROR = -32002
    AUTHENTICATION_ERROR = -32003
    PROFILE_ERROR = -32004
    RESOURCE_UNAVAILABLE = -32005


@dataclass
class ProfileHealthStatus:
    """Detailed health status for Snowflake profile configuration."""

    status: HealthStatus
    profile_name: str | None
    is_valid: bool
    config_exists: bool
    config_path: str
    available_profiles: list[str]
    default_profile: str | None
    validation_error: str | None
    last_checked: float

    @classmethod
    def from_profile_check(cls, profile_name: str | None = None, force_validation: bool = True) -> ProfileHealthStatus:
        """Create profile health status from current configuration."""
        timestamp = time.time()
        profile_summary = get_profile_summary()

        config_path = str(profile_summary.config_path)
        config_exists = profile_summary.config_exists
        available_profiles = profile_summary.available_profiles
        default_profile = profile_summary.default_profile

        # Determine effective profile name
        effective_profile = profile_name or profile_summary.current_profile or default_profile

        # Validate profile if force_validation is True
        validation_error = None
        is_valid = False

        if force_validation:
            try:
                validated_profile = validate_profile(effective_profile)
                is_valid = True
                effective_profile = validated_profile
            except ProfileConfigurationError as e:
                validation_error = str(e)
                is_valid = False
        else:
            # Basic validation without throwing exceptions
            is_valid = (
                config_exists
                and bool(available_profiles)
                and (effective_profile in available_profiles if effective_profile else bool(default_profile))
            )

        # Determine overall status
        if not config_exists or not available_profiles or not is_valid:
            status = HealthStatus.UNHEALTHY
        elif validation_error:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        return cls(
            status=status,
            profile_name=effective_profile,
            is_valid=is_valid,
            config_exists=config_exists,
            config_path=config_path,
            available_profiles=available_profiles,
            default_profile=default_profile,
            validation_error=validation_error,
            last_checked=timestamp,
        )


@dataclass
class MCPServerHealth:
    """Comprehensive MCP server health status."""

    overall_status: HealthStatus
    profile_health: ProfileHealthStatus
    connection_status: HealthStatus | None
    resource_availability: dict[str, bool]
    last_error: str | None
    error_count: int
    uptime_seconds: float
    version: str | None

    def to_mcp_response(self) -> dict[str, Any]:
        """Convert to MCP-compliant health response."""
        return {
            "status": self.overall_status.value,
            "timestamp": time.time(),
            "components": {
                "profile": {
                    "status": self.profile_health.status.value,
                    "profile_name": self.profile_health.profile_name,
                    "is_valid": self.profile_health.is_valid,
                    "config_exists": self.profile_health.config_exists,
                    "available_profiles": self.profile_health.available_profiles,
                    "validation_error": self.profile_health.validation_error,
                },
                "connection": {
                    "status": (self.connection_status.value if self.connection_status else "unknown"),
                },
                "resources": {
                    "status": ("healthy" if all(self.resource_availability.values()) else "degraded"),
                    "available": self.resource_availability,
                },
            },
            "metrics": {
                "error_count": self.error_count,
                "uptime_seconds": self.uptime_seconds,
            },
            "metadata": {
                "version": self.version,
                "last_error": self.last_error,
            },
        }


class MCPHealthMonitor:
    """Health monitoring system for MCP server with Snowflake integration."""

    def __init__(self, server_start_time: float | None = None):
        self.server_start_time = server_start_time or time.time()
        self.error_count = 0
        self.last_error: str | None = None
        self.cached_profile_health: ProfileHealthStatus | None = None
        self.cache_ttl = 30.0  # Cache profile health for 30 seconds

    def record_error(self, error: str) -> None:
        """Record an error for health metrics."""
        self.error_count += 1
        self.last_error = error
        logger.error(f"MCP Health Monitor recorded error: {error}")

    def get_profile_health(self, profile_name: str | None = None, force_refresh: bool = False) -> ProfileHealthStatus:
        """Get current profile health status with caching."""
        now = time.time()

        # Use cached result if available and not expired
        if (
            not force_refresh
            and self.cached_profile_health
            and (now - self.cached_profile_health.last_checked) < self.cache_ttl
        ):
            return self.cached_profile_health

        # Refresh profile health
        try:
            self.cached_profile_health = ProfileHealthStatus.from_profile_check(
                profile_name=profile_name, force_validation=True
            )
        except Exception as e:
            logger.error(f"Failed to check profile health: {e}")
            # Create unhealthy status on failure
            self.cached_profile_health = ProfileHealthStatus(
                status=HealthStatus.UNHEALTHY,
                profile_name=profile_name,
                is_valid=False,
                config_exists=False,
                config_path=str(get_snowflake_config_path()),
                available_profiles=[],
                default_profile=None,
                validation_error=str(e),
                last_checked=now,
            )
            self.record_error(f"Profile health check failed: {e}")

        return self.cached_profile_health

    def check_connection_health(self, snowflake_service=None) -> HealthStatus:
        """Check Snowflake connection health."""
        if not snowflake_service:
            return HealthStatus.UNKNOWN

        try:
            # Use the existing connection test from the service
            with snowflake_service.get_connection(use_dict_cursor=True) as (_, cursor):
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
        except Exception as e:
            self.record_error(f"Connection health check failed: {e}")
            return HealthStatus.UNHEALTHY

    def check_resource_availability(self, server_resources: list[str]) -> dict[str, bool]:
        """Check availability of MCP server resources."""
        # In a real implementation, this would check each resource
        # For now, we'll assume resources are available if profile is valid
        profile_health = self.get_profile_health()
        is_available = profile_health.is_valid

        return dict.fromkeys(server_resources, is_available)

    def get_comprehensive_health(
        self,
        profile_name: str | None = None,
        snowflake_service=None,
        server_resources: list[str] | None = None,
        version: str | None = None,
        connection_health_override: HealthStatus | None = None,
    ) -> MCPServerHealth:
        """Get comprehensive health status for the MCP server."""
        profile_health = self.get_profile_health(profile_name)

        if connection_health_override:
            connection_status = connection_health_override
        else:
            connection_status = self.check_connection_health(snowflake_service)

        resources = server_resources or []
        resource_availability = self.check_resource_availability(resources)

        # Determine overall status
        if profile_health.status == HealthStatus.UNHEALTHY or connection_status == HealthStatus.UNHEALTHY:
            overall_status = HealthStatus.UNHEALTHY
        elif (
            profile_health.status == HealthStatus.DEGRADED
            or connection_status == HealthStatus.DEGRADED
            or not all(resource_availability.values())
        ):
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        uptime = time.time() - self.server_start_time

        return MCPServerHealth(
            overall_status=overall_status,
            profile_health=profile_health,
            connection_status=connection_status,
            resource_availability=resource_availability,
            last_error=self.last_error,
            error_count=self.error_count,
            uptime_seconds=uptime,
            version=version,
        )

    def create_mcp_error_response(
        self, error_code: MCPErrorCode, message: str, **additional_data: Any
    ) -> dict[str, Any]:
        """Create MCP-compliant error response."""
        error_data = {
            "error_type": error_code.name.lower(),
            "timestamp": time.time(),
            **additional_data,
        }

        # Add profile information for profile-related errors
        if error_code == MCPErrorCode.PROFILE_ERROR:
            profile_health = self.get_profile_health()
            error_data.update(
                {
                    "profile_name": profile_health.profile_name,
                    "available_profiles": profile_health.available_profiles,
                    "config_path": profile_health.config_path,
                    "config_exists": profile_health.config_exists,
                }
            )

        return {"code": error_code.value, "message": message, "data": error_data}


def create_profile_validation_error_response(
    monitor: MCPHealthMonitor, profile_name: str | None, validation_error: str
) -> dict[str, Any]:
    """Create a standardized MCP error response for profile validation failures."""
    return monitor.create_mcp_error_response(
        error_code=MCPErrorCode.PROFILE_ERROR,
        message=f"Snowflake profile validation failed: {validation_error}",
        profile_name=profile_name,
        validation_error=validation_error,
        suggestion="Check your Snowflake CLI configuration or run 'snow connection list'",
    )


def create_configuration_error_response(monitor: MCPHealthMonitor, config_issue: str, **context: Any) -> dict[str, Any]:
    """Create a standardized MCP error response for configuration issues."""
    return monitor.create_mcp_error_response(
        error_code=MCPErrorCode.CONFIGURATION_ERROR,
        message=f"Server configuration error: {config_issue}",
        configuration_issue=config_issue,
        **context,
    )
