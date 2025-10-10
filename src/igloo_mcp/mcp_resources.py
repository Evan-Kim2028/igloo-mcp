"""MCP resource availability patterns based on configuration state.

This module implements resource management strategies that adapt to the current
configuration state, providing graceful degradation when configuration issues occur.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

from .mcp_health import HealthStatus, MCPHealthMonitor

logger = get_logger(__name__)


class ResourceState(Enum):
    """Resource availability states."""

    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass
class ResourceAvailability:
    """Resource availability information."""

    name: str
    state: ResourceState
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    last_checked: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "state": self.state.value,
            "reason": self.reason,
            "metadata": self.metadata or {},
            "last_checked": self.last_checked,
        }


class MCPResourceManager:
    """Manages MCP resource availability based on configuration state."""

    def __init__(self, health_monitor: Optional[MCPHealthMonitor] = None):
        self.health_monitor = health_monitor
        self.resource_cache: Dict[str, ResourceAvailability] = {}
        self.cache_ttl = 60.0  # Cache for 60 seconds
        self.dependencies = {
            "catalog": ["profile", "connection"],
            "lineage": ["profile", "connection", "catalog"],
            "cortex_search": ["profile", "connection"],
            "cortex_analyst": ["profile", "connection"],
            "cortex_agent": ["profile", "connection"],
            "query_manager": ["profile", "connection"],
            "object_manager": ["profile", "connection"],
            "semantic_manager": ["profile", "connection"],
        }

    def check_profile_dependency(self) -> ResourceAvailability:
        """Check if profile configuration is available."""
        if not self.health_monitor:
            return ResourceAvailability(
                name="profile",
                state=ResourceState.UNKNOWN,
                reason="Health monitor not available",
                last_checked=time.time(),
            )

        try:
            profile_health = self.health_monitor.get_profile_health()

            if profile_health.is_valid:
                return ResourceAvailability(
                    name="profile",
                    state=ResourceState.AVAILABLE,
                    metadata={
                        "profile_name": profile_health.profile_name,
                        "config_path": profile_health.config_path,
                        "available_profiles": profile_health.available_profiles,
                    },
                    last_checked=time.time(),
                )
            else:
                return ResourceAvailability(
                    name="profile",
                    state=ResourceState.UNAVAILABLE,
                    reason=profile_health.validation_error
                    or "Profile validation failed",
                    metadata={
                        "profile_name": profile_health.profile_name,
                        "available_profiles": profile_health.available_profiles,
                        "config_exists": profile_health.config_exists,
                    },
                    last_checked=time.time(),
                )
        except Exception as e:
            logger.error(f"Failed to check profile dependency: {e}")
            return ResourceAvailability(
                name="profile",
                state=ResourceState.UNAVAILABLE,
                reason=f"Profile check failed: {e}",
                last_checked=time.time(),
            )

    def check_connection_dependency(
        self, snowflake_service=None
    ) -> ResourceAvailability:
        """Check if Snowflake connection is available."""
        if not self.health_monitor:
            return ResourceAvailability(
                name="connection",
                state=ResourceState.UNKNOWN,
                reason="Health monitor not available",
                last_checked=time.time(),
            )

        try:
            connection_health = self.health_monitor.check_connection_health(
                snowflake_service
            )

            if connection_health == HealthStatus.HEALTHY:
                return ResourceAvailability(
                    name="connection",
                    state=ResourceState.AVAILABLE,
                    last_checked=time.time(),
                )
            elif connection_health == HealthStatus.DEGRADED:
                return ResourceAvailability(
                    name="connection",
                    state=ResourceState.DEGRADED,
                    reason="Connection issues detected",
                    last_checked=time.time(),
                )
            else:
                return ResourceAvailability(
                    name="connection",
                    state=ResourceState.UNAVAILABLE,
                    reason="Connection health check failed",
                    last_checked=time.time(),
                )
        except Exception as e:
            logger.error(f"Failed to check connection dependency: {e}")
            return ResourceAvailability(
                name="connection",
                state=ResourceState.UNAVAILABLE,
                reason=f"Connection check failed: {e}",
                last_checked=time.time(),
            )

    def check_catalog_dependency(
        self, catalog_dir: str = "./data_catalogue"
    ) -> ResourceAvailability:
        """Check if catalog data is available."""
        try:
            from pathlib import Path

            catalog_path = Path(catalog_dir)
            summary_path = catalog_path / "catalog_summary.json"

            if not catalog_path.exists():
                return ResourceAvailability(
                    name="catalog",
                    state=ResourceState.UNAVAILABLE,
                    reason="Catalog directory not found",
                    metadata={"catalog_dir": catalog_dir},
                    last_checked=time.time(),
                )

            if not summary_path.exists():
                return ResourceAvailability(
                    name="catalog",
                    state=ResourceState.DEGRADED,
                    reason="Catalog summary not found - may need rebuild",
                    metadata={"catalog_dir": catalog_dir},
                    last_checked=time.time(),
                )

            # Try to read summary
            try:
                with open(summary_path) as f:
                    summary = json.load(f)

                return ResourceAvailability(
                    name="catalog",
                    state=ResourceState.AVAILABLE,
                    metadata={
                        "catalog_dir": catalog_dir,
                        "summary": summary,
                    },
                    last_checked=time.time(),
                )
            except json.JSONDecodeError:
                return ResourceAvailability(
                    name="catalog",
                    state=ResourceState.DEGRADED,
                    reason="Catalog summary is corrupted",
                    metadata={"catalog_dir": catalog_dir},
                    last_checked=time.time(),
                )

        except Exception as e:
            logger.error(f"Failed to check catalog dependency: {e}")
            return ResourceAvailability(
                name="catalog",
                state=ResourceState.UNAVAILABLE,
                reason=f"Catalog check failed: {e}",
                last_checked=time.time(),
            )

    def get_resource_availability(
        self, resource_name: str, snowflake_service=None, **kwargs: Any
    ) -> ResourceAvailability:
        """Get availability for a specific resource."""
        now = time.time()

        # Check cache first
        if resource_name in self.resource_cache:
            cached = self.resource_cache[resource_name]
            if cached.last_checked and (now - cached.last_checked) < self.cache_ttl:
                return cached

        # Check dependencies first
        dependencies = self.dependencies.get(resource_name, [])
        for dep in dependencies:
            dep_availability = None

            if dep == "profile":
                dep_availability = self.check_profile_dependency()
            elif dep == "connection":
                dep_availability = self.check_connection_dependency(snowflake_service)
            elif dep == "catalog":
                catalog_dir = kwargs.get("catalog_dir", "./data_catalogue")
                dep_availability = self.check_catalog_dependency(catalog_dir)

            if dep_availability and dep_availability.state == ResourceState.UNAVAILABLE:
                # If a dependency is unavailable, the resource is unavailable
                availability = ResourceAvailability(
                    name=resource_name,
                    state=ResourceState.UNAVAILABLE,
                    reason=f"Dependency '{dep}' is unavailable: {dep_availability.reason}",
                    metadata={"failed_dependency": dep},
                    last_checked=now,
                )
                self.resource_cache[resource_name] = availability
                return availability

        # If all dependencies are available, the resource is available
        # (In a real implementation, you might check additional resource-specific conditions)
        availability = ResourceAvailability(
            name=resource_name,
            state=ResourceState.AVAILABLE,
            last_checked=now,
        )
        self.resource_cache[resource_name] = availability
        return availability

    def get_all_resource_availability(
        self, resource_names: List[str], snowflake_service=None, **kwargs: Any
    ) -> Dict[str, ResourceAvailability]:
        """Get availability for multiple resources."""
        return {
            name: self.get_resource_availability(name, snowflake_service, **kwargs)
            for name in resource_names
        }

    def filter_available_resources(
        self, resource_names: List[str], snowflake_service=None, **kwargs: Any
    ) -> List[str]:
        """Filter resource list to only include available resources."""
        availability = self.get_all_resource_availability(
            resource_names, snowflake_service, **kwargs
        )
        return [
            name
            for name, avail in availability.items()
            if avail.state == ResourceState.AVAILABLE
        ]

    def get_resource_recommendations(
        self, resource_name: str, availability: ResourceAvailability
    ) -> List[str]:
        """Get recommendations for making a resource available."""
        recommendations = []

        if availability.state == ResourceState.UNAVAILABLE:
            if "profile" in self.dependencies.get(resource_name, []):
                recommendations.append(
                    "Check Snowflake profile configuration with 'check_profile_config' tool"
                )
                recommendations.append(
                    "Ensure SNOWFLAKE_PROFILE environment variable is set correctly"
                )

            if "connection" in self.dependencies.get(resource_name, []):
                recommendations.append(
                    "Test Snowflake connectivity with 'test_connection' tool"
                )
                recommendations.append("Verify network connectivity and credentials")

            if "catalog" in self.dependencies.get(resource_name, []):
                recommendations.append("Build catalog data with 'build_catalog' tool")
                recommendations.append(
                    "Check catalog directory permissions and disk space"
                )

        elif availability.state == ResourceState.DEGRADED:
            recommendations.append(
                "Check server health with 'health_check' tool for detailed diagnostics"
            )

        return recommendations

    def create_resource_status_response(
        self, resource_names: List[str], snowflake_service=None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Create a comprehensive resource status response."""
        availability = self.get_all_resource_availability(
            resource_names, snowflake_service, **kwargs
        )

        available_count = sum(
            1
            for avail in availability.values()
            if avail.state == ResourceState.AVAILABLE
        )

        degraded_count = sum(
            1
            for avail in availability.values()
            if avail.state == ResourceState.DEGRADED
        )

        unavailable_count = sum(
            1
            for avail in availability.values()
            if avail.state == ResourceState.UNAVAILABLE
        )

        overall_status = "healthy"
        if unavailable_count > 0:
            overall_status = "unhealthy"
        elif degraded_count > 0:
            overall_status = "degraded"

        return {
            "overall_status": overall_status,
            "summary": {
                "total_resources": len(resource_names),
                "available": available_count,
                "degraded": degraded_count,
                "unavailable": unavailable_count,
            },
            "resources": {
                name: {
                    **avail.to_dict(),
                    "recommendations": self.get_resource_recommendations(name, avail),
                }
                for name, avail in availability.items()
            },
            "timestamp": time.time(),
        }
