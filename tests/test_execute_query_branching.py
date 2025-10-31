"""Additional branch coverage for ExecuteQueryTool."""

from __future__ import annotations

from collections import namedtuple
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from igloo_mcp.config import Config
from igloo_mcp.mcp.tools.execute_query import (
    ExecuteQueryTool,
    _relative_sql_path,
    _write_sql_artifact,
)
from tests.helpers.fake_snowflake_connector import FakeQueryPlan, FakeSnowflakeService


class SimpleQueryService:
    def session_from_mapping(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
        return mapping


class HealthyMonitor:
    class _Health:
        def __init__(self) -> None:
            self.is_valid = True
            self.validation_error: str | None = None
            self.available_profiles: List[str] = []

    def __init__(self) -> None:
        self.errors: List[str] = []
        self.successes: List[str] = []

    def get_profile_health(
        self, profile: str, use_cache: bool
    ) -> HealthyMonitor._Health:  # noqa: ARG002
        return self._Health()

    def record_error(self, message: str) -> None:
        self.errors.append(message)

    def record_query_success(self, statement_preview: str) -> None:
        self.successes.append(statement_preview)


def _make_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    plans: List[FakeQueryPlan],
    *,
    health_monitor: HealthyMonitor | None = None,
) -> ExecuteQueryTool:
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "off")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")
    config = Config.from_env()
    service = FakeSnowflakeService(plans)
    return ExecuteQueryTool(
        config=config,
        snowflake_service=service,
        query_service=SimpleQueryService(),
        health_monitor=health_monitor,
    )


def test_write_sql_artifact_handles_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True)
    original_write_text = Path.write_text

    def fail_write(self, *args, **kwargs):
        if self.name.endswith(".sql"):
            raise OSError("disk full")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_write, raising=False)
    result = _write_sql_artifact(artifact_root, "deadbeef", "SELECT 1")
    assert result is None


def test_relative_sql_path_fallback(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    artifact = tmp_path / "other" / "file.sql"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("SELECT 1", encoding="utf-8")
    rel = _relative_sql_path(repo_root, artifact)
    assert rel == artifact.resolve().as_posix()


def test_tool_name_property(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _make_tool(
        tmp_path, monkeypatch, [FakeQueryPlan(statement="SELECT 1", rows=[])]
    )
    assert tool.name == "execute_query"


@pytest.mark.asyncio
async def test_execute_accepts_string_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = FakeQueryPlan(statement="SELECT 1", rows=[{"VAL": 1}])
    tool = _make_tool(tmp_path, monkeypatch, [plan], health_monitor=HealthyMonitor())
    result = await tool.execute(statement="SELECT 1", timeout_seconds="45")
    assert result["rowcount"] == 1


@pytest.mark.asyncio
async def test_execute_rejects_boolean_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = FakeQueryPlan(statement="SELECT 1", rows=[{"VAL": 1}])
    tool = _make_tool(tmp_path, monkeypatch, [plan])
    with pytest.raises(TypeError):
        await tool.execute(statement="SELECT 1", timeout_seconds=True)  # noqa: FBT003


@pytest.mark.asyncio
async def test_execute_rejects_out_of_range_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = FakeQueryPlan(statement="SELECT 1", rows=[{"VAL": 1}])
    tool = _make_tool(tmp_path, monkeypatch, [plan])
    with pytest.raises(ValueError):
        await tool.execute(statement="SELECT 1", timeout_seconds=5000)


@pytest.mark.asyncio
async def test_timeout_records_reason_and_metric(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = FakeQueryPlan(statement="SELECT 1", rows=[{"VAL": 1}])
    monitor = HealthyMonitor()
    tool = _make_tool(tmp_path, monkeypatch, [plan], health_monitor=monitor)
    history_calls: List[Dict[str, Any]] = []
    tool.history.record = lambda payload: history_calls.append(payload)
    tool._collect_audit_warnings = MagicMock()

    def raise_timeout(*args, **kwargs):
        raise TimeoutError("boom")

    tool._execute_query_sync = raise_timeout  # type: ignore[assignment]

    with pytest.raises(RuntimeError):
        await tool.execute(
            statement="SELECT 1",
            timeout_seconds=5,
            reason="analysis",
            metric_insight={"score": 10},
        )

    assert monitor.errors
    assert any(payload.get("reason") == "analysis" for payload in history_calls)
    assert any(
        payload.get("metric_insight") == {"score": 10} for payload in history_calls
    )


@pytest.mark.asyncio
async def test_generic_error_verbose_includes_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = FakeQueryPlan(statement="SELECT 1", rows=[{"VAL": 1}])
    monitor = HealthyMonitor()
    tool = _make_tool(tmp_path, monkeypatch, [plan], health_monitor=monitor)
    tool.history.record = MagicMock()
    tool._collect_audit_warnings = MagicMock()

    def raise_failure(*args, **kwargs):
        raise RuntimeError("snowflake failure")

    tool._execute_query_sync = raise_failure  # type: ignore[assignment]

    with pytest.raises(RuntimeError) as exc_info:
        await tool.execute("SELECT 1", verbose_errors=True)

    assert "snowflake failure" in str(exc_info.value)
    assert monitor.errors


@pytest.mark.asyncio
async def test_execute_converts_mixed_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    RowNT = namedtuple("RowNT", ["b", "c"])
    rows = [
        {"A": 1},
        RowNT(2, 3),
        ("x", "y"),
        "scalar",
    ]

    def clone_mixed(self: FakeQueryPlan) -> FakeQueryPlan:
        rows_copy = None
        if self.rows is not None:
            rows_copy = []
            for row in self.rows:
                if isinstance(row, dict):
                    rows_copy.append(dict(row))
                elif hasattr(row, "_asdict"):
                    rows_copy.append(type(row)(*row))
                elif isinstance(row, (list, tuple)):
                    rows_copy.append(tuple(row))
                else:
                    rows_copy.append(row)
        return FakeQueryPlan(
            statement=self.statement,
            rows=rows_copy,
            rowcount=self.rowcount,
            duration=self.duration,
            sfqid=self.sfqid,
            error=self.error,
        )

    monkeypatch.setattr(FakeQueryPlan, "clone", clone_mixed, raising=False)
    plan = FakeQueryPlan(statement="SELECT MIXED", rows=rows)
    monitor = HealthyMonitor()
    tool = _make_tool(tmp_path, monkeypatch, [plan], health_monitor=monitor)
    tool.history.record = MagicMock()

    result = await tool.execute(
        statement="SELECT MIXED",
        timeout_seconds="30",
        reason="inspect",
    )

    assert result["rowcount"] == 4
    converted = result["rows"]
    assert {"A": 1} in converted
    assert {"b": 2, "c": 3} in converted
    assert any("column_1" in row for row in converted)
    assert any(row.get("value") == "scalar" for row in converted)
    assert monitor.successes


@pytest.mark.asyncio
async def test_execute_truncates_large_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    big_string = "x" * 2000
    rows = [{"VAL": big_string} for _ in range(1005)]
    plan = FakeQueryPlan(statement="SELECT BIG", rows=rows)
    tool = _make_tool(tmp_path, monkeypatch, [plan], health_monitor=HealthyMonitor())
    tool.history.record = MagicMock()

    result = await tool.execute("SELECT BIG", timeout_seconds=30)
    assert result["truncated"] is True
    assert result["cache"]["hit"] is False
    assert result["rows"][500]["__truncated__"] is True  # marker row
    assert result["original_rowcount"] == 1005
