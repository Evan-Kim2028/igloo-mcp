"""ExecuteQueryTool failure-path coverage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from igloo_mcp.config import Config
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.snow_cli import QueryOutput
from tests.helpers.fake_snowflake_connector import FakeQueryPlan, FakeSnowflakeService


class StubQueryService:
    def session_from_mapping(self, mapping):  # noqa: D401
        return {k: v for k, v in mapping.items() if v}

    def execute_with_service(self, *args, **kwargs):  # noqa: D401
        return QueryOutput("", "", 0, rows=[{"value": 1}], columns=["value"])


class StubHealthMonitor:
    class ProfileHealth:
        def __init__(self, is_valid: bool, error: str = "invalid") -> None:
            self.is_valid = is_valid
            self.validation_error = error
            self.available_profiles = ["DEFAULT"]

    def __init__(self, valid: bool = True):
        self.valid = valid
        self.errors: list[str] = []

    def get_profile_health(self, profile: str, use_cache: bool):  # noqa: ARG002
        return self.ProfileHealth(self.valid)

    def record_error(self, message: str) -> None:
        self.errors.append(message)


def _tool(
    config: Config, snowflake_service: FakeSnowflakeService, **kwargs: Any
) -> ExecuteQueryTool:
    return ExecuteQueryTool(
        config=config,
        snowflake_service=snowflake_service,
        query_service=StubQueryService(),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_sql_validation_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "off")
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    config = Config.from_env()
    service = FakeSnowflakeService([FakeQueryPlan(statement="DELETE", rows=None)])

    with pytest.raises(ValueError) as exc_info:
        await _tool(config, service).execute(statement="DELETE FROM t")

    assert "not permitted" in str(exc_info.value)


@pytest.mark.asyncio
async def test_profile_validation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "off")
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    config = Config.from_env()
    service = FakeSnowflakeService(
        [FakeQueryPlan(statement="SELECT 1", rows=[{"v": 1}])]
    )
    monitor = StubHealthMonitor(valid=False)

    with pytest.raises(ValueError) as exc_info:
        await _tool(config, service, health_monitor=monitor).execute(
            statement="SELECT 1"
        )

    assert "profile validation failed" in str(exc_info.value).lower()
    assert monitor.errors


@pytest.mark.asyncio
async def test_cache_lookup_failure_records_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "off")
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    config = Config.from_env()
    plan = FakeQueryPlan(
        statement="SELECT 1",
        rows=[{"value": 1}],
        duration=0.01,
    )
    service = FakeSnowflakeService([plan])
    tool = _tool(config, service)

    class ExplodingCache:
        enabled = True
        mode = "enabled"
        root = None

        def pop_warnings(self):
            return []

        def compute_cache_key(self, **kwargs):  # noqa: D401
            return "abc"

        def lookup(self, cache_key):  # noqa: D401
            raise RuntimeError("boom")

        def store(self, *a, **kw):  # noqa: D401
            return None

    tool.cache = ExplodingCache()
    tool._cache_enabled = True

    result = await tool.execute(statement="SELECT 1")
    warnings = result["audit_info"].get("warnings", [])
    assert any("cache" in msg for msg in warnings)


@pytest.mark.asyncio
async def test_history_write_failure_is_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(tmp_path / "history.jsonl"))
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    config = Config.from_env()
    plan = FakeQueryPlan(statement="SELECT 1", rows=[{"value": 1}])
    service = FakeSnowflakeService([plan])
    tool = _tool(config, service)

    def fail_record(_payload):
        raise RuntimeError("history write failed")

    tool.history.record = fail_record

    await tool.execute(statement="SELECT 1")
    assert True  # no exception raised


@pytest.mark.asyncio
async def test_cache_store_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "off")
    config = Config.from_env()
    plan = FakeQueryPlan(statement="SELECT 1", rows=[{"value": 1}], duration=0.01)
    service = FakeSnowflakeService([plan])
    tool = _tool(config, service)

    class FailingCache:
        enabled = True
        mode = "enabled"

        def __init__(self, root: Path) -> None:
            self.root = root

        def pop_warnings(self):
            return []

        def compute_cache_key(self, **kwargs):
            return "abc"

        def lookup(self, cache_key):
            return None

        def store(self, *args, **kwargs):  # noqa: D401
            raise RuntimeError("store failed")

    tool.cache = FailingCache(tmp_path / "cache")
    tool._cache_enabled = True

    result = await tool.execute(statement="SELECT 1")
    warnings = result["audit_info"].get("warnings", [])
    assert any("persist query cache" in msg for msg in warnings)
