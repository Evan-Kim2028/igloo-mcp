"""Tests for HealthCheckTool covering success and failure branches."""

from __future__ import annotations

import json
import os
import sys
import types
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from igloo_mcp.config import Config
from igloo_mcp.living_reports.models import IndexEntry
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.health import HealthCheckTool
from igloo_mcp.mcp_health import HealthStatus
from igloo_mcp.profile_utils import ProfileValidationError


class _StubCursor:
    def __init__(self) -> None:
        self._current: dict[str, Any] = {}

    def execute(self, query: str) -> None:
        key = query.split("CURRENT_", 1)[-1].split("()")[0].lower()
        self._current = {key: key.upper()}

    def fetchone(self) -> dict[str, Any]:
        return self._current


class _StubConnection:
    def __init__(self, cursor: _StubCursor) -> None:
        self.cursor = cursor

    def __enter__(self) -> tuple[None, _StubCursor]:
        return None, self.cursor

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class StubSnowflakeService:
    def __init__(self, cursor: _StubCursor | None = None) -> None:
        self._cursor = cursor or _StubCursor()

    def get_query_tag_param(self) -> dict[str, Any]:
        return {}

    def get_connection(self, **kwargs: Any) -> _StubConnection:
        return _StubConnection(self._cursor)


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
    def __init__(self, profile_health: StubProfileHealth, system_status: StubSystemStatus):
        self._profile_health = profile_health
        self._system_status = system_status
        self.connection_status = HealthStatus.HEALTHY

    def get_profile_health(self) -> StubProfileHealth:
        return self._profile_health

    def check_connection_health(self, _service=None) -> HealthStatus:
        return self.connection_status

    def get_health_status(self) -> StubSystemStatus:
        return self._system_status


class StubResourceAvailability:
    def __init__(self, state_value: str, reason: str | None = None):
        self.state = types.SimpleNamespace(value=state_value)
        self.reason = reason


class StubResourceManager:
    def __init__(self, resources: list[str]):
        self._resources = resources

    def list_resources(self) -> list[str]:
        return list(self._resources)

    def check_catalog_dependency(self) -> StubResourceAvailability:
        if self._resources:
            return StubResourceAvailability("available")
        return StubResourceAvailability("unavailable", reason="Catalog directory not found")


class SummaryStub:
    def __init__(self) -> None:
        self.config_path = Path("/tmp/config.toml")
        self.config_exists = True
        self.available_profiles = ["DEFAULT"]
        self.default_profile = "DEFAULT"
        self.current_profile = "DEFAULT"
        self.profile_count = 1
        self.current_profile_authenticator = "externalbrowser"


def _patch_reports_root(monkeypatch: pytest.MonkeyPatch, reports_root: Path) -> None:
    monkeypatch.setattr("igloo_mcp.path_utils.resolve_reports_root", lambda *args, **kwargs: reports_root)


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

    result = await tool.execute(include_cortex=True, include_catalog=True, response_mode="full")

    assert result["checks"]["connection"]["status"] == "connected"
    assert result["checks"]["profile"]["status"] == "valid"
    assert result["checks"]["cortex"]["available"] is True
    assert result["checks"]["catalog"]["status"] == "available"
    assert result["checks"]["system"]["healthy"] is True
    assert result["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_check_handles_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config.from_env()

    class FailingService(StubSnowflakeService):
        def get_connection(self, **kwargs: Any) -> _StubConnection:
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

    result = await tool.execute(include_cortex=True, include_catalog=True, response_mode="full")

    assert result["checks"]["connection"]["connected"] is False
    assert result["checks"]["profile"]["status"] in {"invalid", "error"}
    assert result["checks"]["catalog"]["status"] == "error"
    assert result["checks"]["cortex"]["available"] is False
    assert result["checks"]["system"]["status"] == "error"
    assert result["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_health_check_full_mode_includes_storage_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that full mode includes storage paths diagnostics."""
    config = Config.from_env()
    service = StubSnowflakeService()
    monitor = StubHealthMonitor(
        profile_health=StubProfileHealth(is_valid=True),
        system_status=StubSystemStatus(),
    )

    # Mock profile validation to avoid dependency on real profile
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
    )

    result = await tool.execute(response_mode="full", include_profile=True, include_cortex=False, include_catalog=False)

    # Verify storage_paths is present in diagnostics
    assert "diagnostics" in result
    assert "storage_paths" in result["diagnostics"]

    storage = result["diagnostics"]["storage_paths"]

    # Verify required fields
    assert "scope" in storage
    assert "base_directory" in storage
    assert "query_history" in storage
    assert "artifacts" in storage
    assert "cache" in storage
    assert "reports" in storage
    assert "catalogs" in storage
    assert "namespaced" in storage

    # Verify scope value is valid
    assert storage["scope"] in ["global", "repo"]

    # Verify all paths are strings and non-empty
    assert isinstance(storage["base_directory"], str)
    assert storage["base_directory"]
    assert isinstance(storage["query_history"], str)
    assert storage["query_history"]
    assert isinstance(storage["artifacts"], str)
    assert storage["artifacts"]
    assert isinstance(storage["cache"], str)
    assert storage["cache"]
    assert isinstance(storage["reports"], str)
    assert storage["reports"]
    assert isinstance(storage["catalogs"], str)
    assert storage["catalogs"]

    # Verify namespaced is boolean
    assert isinstance(storage["namespaced"], bool)


@pytest.mark.asyncio
async def test_health_check_minimal_mode_excludes_storage_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that minimal mode does NOT include storage paths (token efficiency)."""
    config = Config.from_env()
    service = StubSnowflakeService()

    tool = HealthCheckTool(
        config=config,
        snowflake_service=service,
    )

    result = await tool.execute(response_mode="minimal", include_profile=False, include_cortex=False)

    # Minimal mode should not have diagnostics at all
    assert "diagnostics" not in result
    # Double-check storage_paths is not in the result anywhere
    assert "storage_paths" not in result.get("diagnostics", {})


@pytest.mark.asyncio
async def test_health_check_includes_query_circuit_breaker_status() -> None:
    config = Config.from_env()
    service = StubSnowflakeService()
    breaker_status = {
        "enabled": True,
        "state": "open",
        "failure_count": 3,
        "failure_threshold": 5,
        "recovery_timeout_seconds": 60.0,
        "time_until_retry_seconds": 42.5,
    }

    tool = HealthCheckTool(
        config=config,
        snowflake_service=service,
        query_circuit_breaker_status_provider=lambda: breaker_status,
    )

    minimal = await tool.execute(response_mode="minimal", include_profile=False, include_cortex=False)
    assert minimal["components"]["query_circuit_breaker"] == "open"

    full = await tool.execute(response_mode="full", include_profile=False, include_cortex=False)
    assert full["checks"]["query_circuit_breaker"] == breaker_status
    assert full["diagnostics"]["query_circuit_breaker"] == breaker_status
    assert "query_circuit_breaker" in full.get("remediation", {})


@pytest.mark.asyncio
async def test_health_check_reports_health_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = Config.from_env()
    service = StubSnowflakeService()
    reports_root = tmp_path / "reports"
    report_service = ReportService(reports_root)
    report_id = report_service.create_report("Healthy Report")
    storage = report_service.global_storage.get_report_storage(report_id)

    outline = storage.load_outline()
    outline.metadata["attachments"] = [{"path": "report_files/kept.png"}]
    storage._save_outline_atomic(outline)

    report_files_dir = storage.report_dir / "report_files"
    report_files_dir.mkdir(parents=True, exist_ok=True)
    (report_files_dir / "kept.png").write_text("ok", encoding="utf-8")

    _patch_reports_root(monkeypatch, reports_root)
    monkeypatch.setattr(
        "igloo_mcp.mcp.tools.health.shutil.disk_usage",
        lambda _path: types.SimpleNamespace(total=1000, free=600),
    )

    tool = HealthCheckTool(
        config=config,
        snowflake_service=service,
    )

    minimal = await tool.execute(
        response_mode="minimal",
        include_profile=False,
        include_cortex=False,
        include_catalog=False,
        include_reports_health=True,
    )
    assert minimal["components"]["reports"] == "healthy"

    full = await tool.execute(
        response_mode="full",
        include_profile=False,
        include_cortex=False,
        include_catalog=False,
        include_reports_health=True,
    )
    reports = full["checks"]["reports"]

    assert full["status"] == "healthy"
    assert reports["status"] == "healthy"
    assert reports["initialized"] is True
    assert reports["total_reports"] == 1
    assert reports["index_entries"] == 1
    assert reports["corrupted_index_lines"] == []
    assert reports["orphaned_index_entries"] == []
    assert reports["missing_index_entries"] == []
    assert reports["corrupted_audit_logs"] == []
    assert reports["orphaned_assets"] == []
    assert reports["warnings"] == []
    assert reports["total_audit_events"] >= 1


@pytest.mark.asyncio
async def test_health_check_reports_health_detects_storage_issues(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = Config.from_env()
    service = StubSnowflakeService()
    reports_root = tmp_path / "reports"
    report_service = ReportService(reports_root)

    indexed_report_id = report_service.create_report("Indexed Report")
    missing_index_report_id = report_service.create_report("Missing Index Report")

    indexed_storage = report_service.global_storage.get_report_storage(indexed_report_id)
    outline = indexed_storage.load_outline()
    outline.metadata["attachments"] = [{"path": "report_files/kept.png"}]
    indexed_storage._save_outline_atomic(outline)

    report_files_dir = indexed_storage.report_dir / "report_files"
    report_files_dir.mkdir(parents=True, exist_ok=True)
    (report_files_dir / "kept.png").write_text("ok", encoding="utf-8")
    (report_files_dir / "orphan.png").write_text("orphan", encoding="utf-8")

    with indexed_storage.audit_path.open("a", encoding="utf-8") as handle:
        handle.write("{not valid json}\n")

    old_backup = indexed_storage.backups_dir / "stale.bak"
    old_backup.write_text("old backup", encoding="utf-8")
    stale_timestamp = (datetime.now(UTC) - timedelta(days=HealthCheckTool.REPORT_BACKUP_RETENTION_DAYS + 5)).timestamp()
    os.utime(old_backup, (stale_timestamp, stale_timestamp))

    orphan_report_id = str(uuid.uuid4())
    index_entries = [
        IndexEntry(
            report_id=indexed_report_id,
            current_title="Indexed Report",
            created_at=datetime.now(UTC).isoformat(),
            updated_at=datetime.now(UTC).isoformat(),
            tags=[],
            status="active",
            path=f"by_id/{indexed_report_id}",
        ),
        IndexEntry(
            report_id=orphan_report_id,
            current_title="Orphaned Entry",
            created_at=datetime.now(UTC).isoformat(),
            updated_at=datetime.now(UTC).isoformat(),
            tags=[],
            status="active",
            path=f"by_id/{orphan_report_id}",
        ),
    ]
    index_path = reports_root / "index.jsonl"
    with index_path.open("w", encoding="utf-8") as handle:
        for entry in index_entries:
            handle.write(json.dumps(entry.model_dump()) + "\n")
        handle.write("{broken index line}\n")

    _patch_reports_root(monkeypatch, reports_root)
    monkeypatch.setattr(
        "igloo_mcp.mcp.tools.health.shutil.disk_usage",
        lambda _path: types.SimpleNamespace(total=1000, free=40),
    )

    tool = HealthCheckTool(
        config=config,
        snowflake_service=service,
    )

    result = await tool.execute(
        response_mode="full",
        include_profile=False,
        include_cortex=False,
        include_catalog=False,
        include_reports_health=True,
    )
    reports = result["checks"]["reports"]

    assert result["status"] == "unhealthy"
    assert reports["status"] == "unhealthy"
    assert reports["total_reports"] == 2
    assert reports["index_entries"] == 2
    assert len(reports["corrupted_index_lines"]) == 1
    assert reports["orphaned_index_entries"] == [orphan_report_id]
    assert reports["missing_index_entries"] == [missing_index_report_id]
    assert len(reports["corrupted_audit_logs"]) == 1
    assert reports["corrupted_audit_logs"][0]["report_id"] == indexed_report_id
    assert reports["orphaned_assets"] == [f"{indexed_report_id}/report_files/orphan.png"]
    assert reports["old_backups"][0]["path"] == f"{indexed_report_id}/backups/stale.bak"
    assert reports["disk_usage"]["used_percent"] == 96.0
    assert any("orphaned report asset" in warning for warning in reports["warnings"])
    assert any("backup file" in warning for warning in reports["warnings"])
    assert any("Disk usage" in warning for warning in reports["warnings"])
    assert "reports" in result.get("remediation", {})


@pytest.mark.asyncio
async def test_storage_paths_reflect_repo_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test storage paths correctly reflect repo scope configuration."""
    config = Config.from_env()
    service = StubSnowflakeService()
    monitor = StubHealthMonitor(
        profile_health=StubProfileHealth(is_valid=True),
        system_status=StubSystemStatus(),
    )

    # Mock profile validation
    monkeypatch.setattr(
        "igloo_mcp.mcp.tools.health.validate_and_resolve_profile",
        lambda: "DEFAULT",
    )
    monkeypatch.setattr(
        "igloo_mcp.mcp.tools.health.get_profile_summary",
        lambda: SummaryStub(),
    )

    # Mock repo scope environment
    monkeypatch.setenv("IGLOO_MCP_LOG_SCOPE", "repo")

    tool = HealthCheckTool(
        config=config,
        snowflake_service=service,
        health_monitor=monitor,
    )

    result = await tool.execute(response_mode="full", include_profile=True, include_cortex=False, include_catalog=False)

    storage = result["diagnostics"]["storage_paths"]

    # Verify scope is repo
    assert storage["scope"] == "repo"

    # Repo scope paths should NOT start with ~/.igloo_mcp
    home_igloo = str(Path.home() / ".igloo_mcp")
    assert not storage["base_directory"].startswith(home_igloo), (
        f"Repo scope should not use global base: {storage['base_directory']}"
    )
