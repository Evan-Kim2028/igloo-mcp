"""Tests for HealthCheckTool covering success and failure branches."""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from igloo_mcp.config import Config
from igloo_mcp.mcp.tools.health import HealthCheckTool
from igloo_mcp.mcp_health import HealthStatus
from igloo_mcp.profile_utils import ProfileValidationError


class _StubCursor:
    def __init__(self) -> None:
        self._current: Dict[str, Any] = {}

    def execute(self, query: str) -> None:
        key = query.split("CURRENT_", 1)[-1].split("()")[0].lower()
        self._current = {key: key.upper()}

    def fetchone(self) -> Dict[str, Any]:
        return self._current


class _StubConnection:
    def __init__(self, cursor: _StubCursor) -> None:
        self.cursor = cursor

    def __enter__(self) -> tuple[None, _StubCursor]:
        return None, self.cursor

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class StubSnowflakeService:
    def __init__(self, cursor: Optional[_StubCursor] = None) -> None:
        self._cursor = cursor or _StubCursor()

    def get_query_tag_param(self) -> Dict[str, Any]:
        return {}

    def get_connection(self, **kwargs: Any) -> _StubConnection:  # noqa: ANN401
        return _StubConnection(self._cursor)


@dataclass
class StubProfileHealth:
    is_valid: bool
    profile_name: str = "DEFAULT"
    config_path: Path = Path("/tmp/config.toml")
    available_profiles: list[str] = None  # type: ignore[assignment]
    config_exists: bool = True
    validation_error: Optional[str] = None

    def __post_init__(self) -> None:
        if self.available_profiles is None:
            self.available_profiles = ["DEFAULT"]


@dataclass
class StubSystemStatus:
    status: str = "ok"
    is_healthy: bool = True
    error_count: int = 0
    warning_count: int = 0
    metrics: Dict[str, int] = None  # type: ignore[assignment]
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
    def __init__(
        self, profile_health: StubProfileHealth, system_status: StubSystemStatus
    ):
        self._profile_health = profile_health
        self._system_status = system_status
        self.connection_status = HealthStatus.HEALTHY

    def get_profile_health(self) -> StubProfileHealth:
        return self._profile_health

    def check_connection_health(self, _service=None) -> HealthStatus:
        return self.connection_status

    def get_health_status(self) -> StubSystemStatus:
        return self._system_status


class StubResourceManager:
    def __init__(self, resources: list[str]):
        self._resources = resources

    def list_resources(self) -> list[str]:
        return list(self._resources)


class SummaryStub:
    def __init__(self) -> None:
        self.config_path = Path("/tmp/config.toml")
        self.config_exists = True
        self.available_profiles = ["DEFAULT"]
        self.default_profile = "DEFAULT"
        self.current_profile = "DEFAULT"
        self.profile_count = 1
        self.current_profile_authenticator = "externalbrowser"


@pytest.mark.asyncio
async def test_health_check_tool_success(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config.from_env()
    service = StubSnowflakeService()
    monitor = StubHealthMonitor(
        profile_health=StubProfileHealth(is_valid=True),
        system_status=StubSystemStatus(),
    )
    resource_manager = StubResourceManager(["catalog"])

    module = types.ModuleType("mcp_server_snowflake.cortex_services.tools")

    async def fake_complete_cortex(**kwargs: Any) -> None:  # pragma: no cover - stub
        return None

    module.complete_cortex = fake_complete_cortex
    monkeypatch.setitem(
        sys.modules,
        "mcp_server_snowflake.cortex_services.tools",
        module,
    )
    monkeypatch.setattr(
        "igloo_mcp.mcp.tools.health.validate_and_resolve_profile",
        lambda: "DEFAULT",
    )
    monkeypatch.setattr(
        "igloo_mcp.mcp.tools.health.get_profile_summary",
        lambda: SummaryStub(),
    )

    tool = HealthCheckTool(
        config=config,
        snowflake_service=service,
        health_monitor=monitor,
        resource_manager=resource_manager,
    )

    result = await tool.execute(include_cortex=True, include_catalog=True)

    assert result["connection"]["status"] == "connected"
    assert result["profile"]["status"] == "valid"
    assert result["cortex"]["available"] is True
    assert result["catalog"]["status"] == "available"
    assert result["system"]["healthy"] is True
    assert result["overall_status"] == "healthy"


@pytest.mark.asyncio
async def test_health_check_handles_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config.from_env()

    class FailingService(StubSnowflakeService):
        def get_connection(self, **kwargs: Any) -> _StubConnection:  # noqa: ANN401
            raise RuntimeError("connection refused")

    failing_monitor = StubHealthMonitor(
        profile_health=StubProfileHealth(
            is_valid=False,
            validation_error="invalid profile",
        ),
        system_status=StubSystemStatus(is_healthy=False, status="error"),
    )
    failing_monitor.connection_status = HealthStatus.UNHEALTHY

    def raise_validation() -> None:
        raise ProfileValidationError("profile error")

    monkeypatch.setattr(
        "igloo_mcp.mcp.tools.health.validate_and_resolve_profile",
        raise_validation,
    )
    monkeypatch.setattr(
        "igloo_mcp.mcp.tools.health.get_profile_summary",
        lambda: SummaryStub(),
    )
    monkeypatch.delitem(
        sys.modules,
        "mcp_server_snowflake.cortex_services.tools",
        raising=False,
    )

    class FailingResourceManager:
        def list_resources(self) -> list[str]:
            raise RuntimeError("catalog offline")

    tool = HealthCheckTool(
        config=config,
        snowflake_service=FailingService(),
        health_monitor=failing_monitor,
        resource_manager=FailingResourceManager(),
    )

    result = await tool.execute(include_cortex=True, include_catalog=True)

    assert result["connection"]["connected"] is False
    assert result["profile"]["status"] in {"invalid", "error"}
    assert result["catalog"]["status"] == "error"
    assert result["cortex"]["available"] is False
    assert result["system"]["status"] == "error"
    assert result["overall_status"] == "unhealthy"
