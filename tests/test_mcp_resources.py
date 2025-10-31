"""Tests for MCPResourceManager availability logic."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from igloo_mcp.mcp_health import HealthStatus
from igloo_mcp.mcp_resources import (
    MCPResourceManager,
    ResourceState,
)


@dataclass
class StubProfileHealth:
    is_valid: bool
    profile_name: str = "DEFAULT"
    config_path: Path = Path("/tmp/config.toml")
    available_profiles: list[str] = None  # type: ignore[assignment]
    config_exists: bool = True
    validation_error: str | None = None

    def __post_init__(self) -> None:
        if self.available_profiles is None:
            self.available_profiles = ["DEFAULT"]


@dataclass
class StubSystemStatus:
    status: str = "ok"
    is_healthy: bool = True
    error_count: int = 0
    warning_count: int = 0
    metrics: dict[str, int] = None  # type: ignore[assignment]
    recent_errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.metrics is None:
            self.metrics = {
                "total_queries": 1,
                "successful_queries": 1,
                "failed_queries": 0,
            }
        if self.recent_errors is None:
            self.recent_errors = []


class StubHealthMonitor:
    def __init__(self, profile_health: StubProfileHealth):
        self.profile_health = profile_health
        self.connection_status = HealthStatus.HEALTHY
        self.profile_checks = 0
        self.connection_checks = 0

    def get_profile_health(self):
        self.profile_checks += 1
        return self.profile_health

    def check_connection_health(self, snowflake_service=None):
        self.connection_checks += 1
        return self.connection_status


def test_resource_manager_all_available(tmp_path: Path):
    summary_path = tmp_path / "catalog_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps({"totals": {"tables": 1}}), encoding="utf-8")

    monitor = StubHealthMonitor(profile_health=StubProfileHealth(is_valid=True))
    manager = MCPResourceManager(health_monitor=monitor)

    response = manager.create_resource_status_response(
        ["catalog", "lineage"],
        catalog_dir=str(tmp_path),
    )

    assert response["overall_status"] == "healthy"
    resources = response["resources"]
    assert resources["catalog"]["state"] == ResourceState.AVAILABLE.value
    assert resources["lineage"]["state"] == ResourceState.AVAILABLE.value
    assert monitor.profile_checks >= 1
    assert monitor.connection_checks >= 1

    # Cached response should not trigger additional checks within TTL
    monitor.profile_checks = 0
    monitor.connection_checks = 0
    manager.get_resource_availability("catalog", catalog_dir=str(tmp_path))
    assert monitor.profile_checks == 0
    assert monitor.connection_checks == 0


def test_resource_manager_handles_dependency_failures(tmp_path: Path):
    monitor = StubHealthMonitor(
        profile_health=StubProfileHealth(
            is_valid=False,
            validation_error="profile missing",
        )
    )
    monitor.connection_status = HealthStatus.DEGRADED
    manager = MCPResourceManager(health_monitor=monitor)

    profile_availability = manager.check_profile_dependency()
    assert profile_availability.state == ResourceState.UNAVAILABLE
    assert "profile missing" in profile_availability.reason

    connection_availability = manager.check_connection_dependency()
    assert connection_availability.state == ResourceState.DEGRADED

    missing_catalog = manager.check_catalog_dependency(str(tmp_path / "nope"))
    assert missing_catalog.state == ResourceState.UNAVAILABLE

    partial_catalog_dir = tmp_path / "catalog_partial"
    partial_catalog_dir.mkdir()
    degraded_catalog = manager.check_catalog_dependency(str(partial_catalog_dir))
    assert degraded_catalog.state == ResourceState.DEGRADED

    response = manager.create_resource_status_response(
        ["catalog", "lineage"],
        catalog_dir=str(partial_catalog_dir),
    )
    assert response["overall_status"] == "unhealthy"
    resources = response["resources"]
    assert resources["catalog"]["state"] == ResourceState.UNAVAILABLE.value
    assert resources["lineage"]["state"] == ResourceState.UNAVAILABLE.value
