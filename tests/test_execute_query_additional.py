"""Additional ExecuteQueryTool coverage for artifact and tag handling."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from igloo_mcp.config import Config
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.path_utils import DEFAULT_ARTIFACT_ROOT
from igloo_mcp.snow_cli import QueryOutput
from tests.helpers.fake_snowflake_connector import (
    FakeQueryPlan,
    FakeSnowflakeService,
)


class StubQueryService:
    def __init__(self) -> None:
        self.calls: list[Dict[str, Any]] = []

    def session_from_mapping(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in mapping.items() if v}

    def execute_with_service(
        self,
        query: str,
        *,
        service: Any = None,  # noqa: ANN401
        session: Optional[Dict[str, Any]] = None,
        output_format: Optional[str] = None,
    ) -> QueryOutput:
        self.calls.append(
            {"query": query, "session": session, "output_format": output_format}
        )
        return QueryOutput(
            raw_stdout="",
            raw_stderr="",
            returncode=0,
            rows=[{"col": "value"}],
            columns=["col"],
        )


class DummyCache:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.mode = "disabled"

    def compute_cache_key(self, **kwargs: Any) -> str:  # pragma: no cover - not used
        return uuid.uuid4().hex

    def lookup(self, cache_key: str):  # pragma: no cover - not used
        return None

    def store(self, cache_key: str, *, rows, metadata):  # pragma: no cover - not used
        return None

    def pop_warnings(self) -> list[str]:
        return []


def _make_tool(
    config: Config,
    service: FakeSnowflakeService,
    query_service: Optional[StubQueryService] = None,
) -> ExecuteQueryTool:
    return ExecuteQueryTool(
        config=config,
        snowflake_service=service,
        query_service=query_service or StubQueryService(),
        health_monitor=None,
    )


@pytest.mark.asyncio
async def test_execute_query_merges_existing_query_tag_json(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(tmp_path / "history.jsonl"))
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("IGLOO_MCP_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

    config = Config.from_env()
    plan = FakeQueryPlan(
        statement="SELECT 1",
        rows=[{"value": 1}],
        sfqid="TAG_TEST",
        duration=0.01,
    )
    service = FakeSnowflakeService(
        [plan],
        query_tag_param={"QUERY_TAG": '{"foo":"bar"}'},
    )

    tool = _make_tool(config, service)
    await tool.execute(statement="SELECT 1", reason="First pass")

    cursor = service.cursors[0]
    assert cursor.query_tags_seen, "Expected query tag to be applied"
    merged_tag = cursor.query_tags_seen[0]
    loaded = json.loads(merged_tag)
    assert loaded["foo"] == "bar"
    assert loaded["tool"] == "execute_query"
    assert loaded["reason"] == "First pass"
    assert cursor._session_parameters["QUERY_TAG"] is None


def test_execute_query_artifact_root_fallback(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "off")
    monkeypatch.setattr(
        "igloo_mcp.mcp.tools.execute_query.resolve_artifact_root",
        lambda raw=None: (tmp_path / "primary"),
        raising=False,
    )
    monkeypatch.setattr(
        "igloo_mcp.mcp.tools.execute_query.QueryResultCache.from_env",
        lambda artifact_root=None: DummyCache(enabled=False),
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path, raising=False)

    original_mkdir = Path.mkdir

    def fake_mkdir(self, *args, **kwargs):
        if self == tmp_path / "primary":
            raise OSError("primary unavailable")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fake_mkdir, raising=False)

    config = Config.from_env()
    service = FakeSnowflakeService(
        [FakeQueryPlan(statement="SELECT 1", rows=[{"value": 1}])]
    )
    tool = _make_tool(config, service)

    expected_fallback = (tmp_path / ".igloo_mcp" / DEFAULT_ARTIFACT_ROOT).resolve()
    assert tool._artifact_root == expected_fallback
    assert tool._static_audit_warnings
    assert any("fallback" in msg for msg in tool._static_audit_warnings)


def test_persist_sql_artifact_failure_adds_warning(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "off")
    monkeypatch.setattr(
        "igloo_mcp.mcp.tools.execute_query.QueryResultCache.from_env",
        lambda artifact_root=None: DummyCache(enabled=False),
    )

    config = Config.from_env()
    service = FakeSnowflakeService(
        [FakeQueryPlan(statement="SELECT 1", rows=[{"value": 1}])]
    )
    tool = _make_tool(config, service)

    monkeypatch.setattr(
        "igloo_mcp.mcp.tools.execute_query._write_sql_artifact",
        lambda *a, **kw: None,
    )

    result = tool._persist_sql_artifact("abc", "SELECT 1")
    assert result is None
    assert any(
        "Failed to persist SQL text" in msg for msg in tool._transient_audit_warnings
    )


@pytest.mark.asyncio
async def test_history_disabled_skips_logging(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "off")
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("IGLOO_MCP_CACHE_ROOT", str(tmp_path / "cache"))

    config = Config.from_env()
    plan = FakeQueryPlan(
        statement="SELECT 2",
        rows=[{"value": 2}],
        duration=0.01,
    )
    service = FakeSnowflakeService([plan])
    tool = _make_tool(config, service)

    result = await tool.execute(statement="SELECT 2")
    assert result["cache"]["hit"] is False
    assert tool.history.disabled is True
    assert not (tmp_path / "history.jsonl").exists()


@pytest.mark.asyncio
async def test_cache_read_only_mode(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(tmp_path / "history.jsonl"))
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("IGLOO_MCP_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "read_only")

    config = Config.from_env()
    plan = FakeQueryPlan(
        statement="SELECT 3",
        rows=[{"value": 3}],
        duration=0.01,
    )
    service = FakeSnowflakeService([plan])
    tool = _make_tool(config, service)

    result = await tool.execute(statement="SELECT 3")
    assert result["cache"]["hit"] is False
    assert result["cache"]["cache_key"] is not None
    assert "manifest_path" not in result["cache"]
