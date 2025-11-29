"""Tests for MCP health monitoring utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from igloo_mcp.mcp_health import (
    HealthStatus,
    MCPErrorCode,
    MCPHealthMonitor,
    ProfileHealthStatus,
    create_configuration_error_response,
    create_profile_validation_error_response,
)
from igloo_mcp.profile_utils import ProfileValidationError


class _StubSummary:
    def __init__(self) -> None:
        self.config_path = Path("/tmp/config.toml")
        self.config_exists = True
        self.available_profiles = ["DEV"]
        self.default_profile = "DEV"
        self.current_profile = "DEV"
        self.profile_count = 1
        self.current_profile_authenticator = "externalbrowser"


def _patch_profile_utils(monkeypatch: pytest.MonkeyPatch, *, valid: bool, error: str = "") -> None:
    monkeypatch.setattr(
        "igloo_mcp.mcp_health.get_profile_summary",
        lambda: _StubSummary(),
    )

    if valid:
        monkeypatch.setattr(
            "igloo_mcp.mcp_health.validate_profile",
            lambda name: name or "DEV",
        )
    else:

        def _raise(name: str | None) -> str:
            raise ProfileValidationError(error or "invalid")

        monkeypatch.setattr(
            "igloo_mcp.mcp_health.validate_profile",
            _raise,
        )

    monkeypatch.setattr(
        "igloo_mcp.mcp_health.get_snowflake_config_path",
        lambda: Path("/tmp/config.toml"),
    )


def test_profile_health_status_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_profile_utils(monkeypatch, valid=True)
    status = ProfileHealthStatus.from_profile_check(profile_name="DEV")
    assert status.status == HealthStatus.HEALTHY
    assert status.is_valid is True
    assert status.validation_error is None


def test_profile_health_status_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_profile_utils(monkeypatch, valid=False, error="missing profile")
    status = ProfileHealthStatus.from_profile_check(profile_name="MISSING")
    assert status.status == HealthStatus.UNHEALTHY
    assert status.is_valid is False
    assert status.validation_error == "missing profile"


def test_health_monitor_caches_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = {"count": 0}

    def _summary() -> Any:
        call_count["count"] += 1
        return _StubSummary()

    monkeypatch.setattr("igloo_mcp.mcp_health.get_profile_summary", _summary)
    monkeypatch.setattr(
        "igloo_mcp.mcp_health.validate_profile",
        lambda name: name or "DEV",
    )
    monkeypatch.setattr(
        "igloo_mcp.mcp_health.get_snowflake_config_path",
        lambda: Path("/tmp/config.toml"),
    )

    monitor = MCPHealthMonitor()
    first = monitor.get_profile_health("DEV")
    second = monitor.get_profile_health("DEV")
    assert first is second
    assert call_count["count"] == 1


class _CursorCtx:
    def __init__(self, succeed: bool = True):
        self.succeed = succeed

    def __enter__(self):
        cursor = MagicMock()
        if self.succeed:
            cursor.fetchone.return_value = {"1": "1"}
        else:

            def _raise(_):  # noqa: ANN001
                raise RuntimeError("boom")

            cursor.execute.side_effect = _raise
        return None, cursor

    def __exit__(self, exc_type, exc, tb):
        return False


class _Service:
    def __init__(self, succeed: bool):
        self.succeed = succeed

    def get_connection(self, **kwargs):  # noqa: ANN401
        return _CursorCtx(self.succeed)


def test_health_monitor_connection_health():
    monitor = MCPHealthMonitor()
    ok = monitor.check_connection_health(_Service(True))
    fail = monitor.check_connection_health(_Service(False))
    assert ok == HealthStatus.HEALTHY
    assert fail == HealthStatus.UNHEALTHY
    assert monitor.error_count == 1


def test_health_monitor_comprehensive(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_profile_utils(monkeypatch, valid=True)
    monitor = MCPHealthMonitor(server_start_time=0)
    result = monitor.get_comprehensive_health(
        profile_name="DEV",
        snowflake_service=_Service(True),
        server_resources=["catalog", "lineage"],
        version="1.0.0",
    )
    assert result.overall_status == HealthStatus.HEALTHY
    assert result.resource_availability["catalog"] is True
    assert result.version == "1.0.0"


def test_health_monitor_error_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_profile_utils(monkeypatch, valid=False, error="bad-profile")
    monitor = MCPHealthMonitor()
    profile_resp = create_profile_validation_error_response(monitor, profile_name="DEV", validation_error="bad-profile")
    assert profile_resp["code"] == MCPErrorCode.PROFILE_ERROR.value
    assert profile_resp["data"]["validation_error"] == "bad-profile"

    config_resp = create_configuration_error_response(monitor, config_issue="missing key", detail="info")
    assert config_resp["code"] == MCPErrorCode.CONFIGURATION_ERROR.value
    assert config_resp["data"]["configuration_issue"] == "missing key"
