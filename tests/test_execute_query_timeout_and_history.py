import hashlib
import json
from pathlib import Path

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.mcp.exceptions import MCPExecutionError
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.service_layer.query_service import QueryService
from tests.helpers.fake_snowflake_connector import (
    FakeQueryPlan,
    FakeSnowflakeService,
)


@pytest.mark.asyncio
async def test_timeout_cancels_and_logs_history(tmp_path, monkeypatch):
    history_path = tmp_path / "history.jsonl"
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(history_path))
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(artifact_root))

    cfg = Config(snowflake=SnowflakeConfig(profile="test"))
    service = FakeSnowflakeService(
        [
            # Session parameter queries that execute_query makes
            FakeQueryPlan(
                statement="SHOW PARAMETERS LIKE 'STATEMENT\\_TIMEOUT\\_IN\\_SECONDS' IN SESSION",
                rows=[],
            ),
            FakeQueryPlan(
                statement="SELECT LONG_RUNNING",
                rows=[{"A": 1}],
                duration=2.0,
            ),
            # Restore parameter query
            FakeQueryPlan(
                statement="SHOW PARAMETERS LIKE 'STATEMENT\\_TIMEOUT\\_IN\\_SECONDS' IN SESSION",
                rows=[],
            ),
        ]
    )
    tool = ExecuteQueryTool(cfg, service, QueryService(context=None))

    with pytest.raises((RuntimeError, MCPExecutionError)) as exc:
        await tool.execute(statement="SELECT LONG_RUNNING", timeout_seconds=1)
    assert "Query timeout" in str(exc.value)

    # History should have a timeout record
    data = history_path.read_text(encoding="utf-8").strip().splitlines()
    assert data, "expected at least one history line"
    event = json.loads(data[-1])
    assert event["status"] == "timeout"
    assert event.get("statement_preview", "").startswith("SELECT LONG_RUNNING")
    expected_sha = hashlib.sha256(b"SELECT LONG_RUNNING").hexdigest()
    assert event["sql_sha256"] == expected_sha
    sql_path = event.get("artifacts", {}).get("sql_path")
    assert sql_path
    artifact = Path(sql_path)
    if not artifact.is_absolute():
        artifact = (Path.cwd() / artifact).resolve()
    assert artifact.exists()
    assert artifact.read_text(encoding="utf-8") == "SELECT LONG_RUNNING"


@pytest.mark.asyncio
async def test_success_returns_query_id_and_logs(tmp_path, monkeypatch):
    history_path = tmp_path / "history.jsonl"
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(history_path))
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(artifact_root))

    cfg = Config(snowflake=SnowflakeConfig(profile="test"))
    service = FakeSnowflakeService(
        [
            FakeQueryPlan(
                statement="SELECT QUICK",
                rows=[{"A": 1}, {"A": 2}],
                duration=0.05,
                sfqid="FAKE_QID_123",
            )
        ]
    )
    tool = ExecuteQueryTool(cfg, service, QueryService(context=None))

    res = await tool.execute(statement="SELECT QUICK", timeout_seconds=2)
    assert res["rowcount"] == 2
    assert res.get("query_id") == "FAKE_QID_123"
    assert isinstance(res.get("duration_ms"), int)

    # History should have a success record with query_id
    data = history_path.read_text(encoding="utf-8").strip().splitlines()
    assert data, "expected at least one history line"
    event = json.loads(data[-1])
    assert event["status"] == "success"
    assert event.get("query_id") == "FAKE_QID_123"
    expected_sha = hashlib.sha256(b"SELECT QUICK").hexdigest()
    assert event["sql_sha256"] == expected_sha
    sql_path = event.get("artifacts", {}).get("sql_path")
    assert sql_path
    artifact = Path(sql_path)
    if not artifact.is_absolute():
        artifact = (Path.cwd() / artifact).resolve()
    assert artifact.exists()
    assert artifact.read_text(encoding="utf-8") == "SELECT QUICK"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_value", ["30s", 12.5, True])
async def test_timeout_seconds_requires_integer(bad_value):
    cfg = Config(snowflake=SnowflakeConfig(profile="test"))
    service = FakeSnowflakeService([FakeQueryPlan(statement="SELECT QUICK", rows=[{"A": 1}, {"A": 2}])])
    tool = ExecuteQueryTool(cfg, service, QueryService(context=None))

    with pytest.raises((TypeError, ValueError)):
        await tool.execute(statement="SELECT QUICK", timeout_seconds=bad_value)


@pytest.mark.asyncio
async def test_timeout_seconds_accepts_numeric_string(tmp_path, monkeypatch):
    history_path = tmp_path / "history.jsonl"
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(history_path))

    cfg = Config(snowflake=SnowflakeConfig(profile="test"))
    service = FakeSnowflakeService([FakeQueryPlan(statement="SELECT QUICK", rows=[{"A": 1}, {"A": 2}])])
    tool = ExecuteQueryTool(cfg, service, QueryService(context=None))

    res = await tool.execute(statement="SELECT QUICK", timeout_seconds="45")
    assert res["rowcount"] == 2

    data = history_path.read_text(encoding="utf-8").strip().splitlines()
    event = json.loads(data[-1])
    assert event["timeout_seconds"] == 45


@pytest.mark.asyncio
async def test_timeout_seconds_accepts_floatish_values(tmp_path, monkeypatch):
    history_path = tmp_path / "history.jsonl"
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(history_path))

    cfg = Config(snowflake=SnowflakeConfig(profile="test"))
    service = FakeSnowflakeService([FakeQueryPlan(statement="SELECT QUICK", rows=[{"A": 1}])])
    tool = ExecuteQueryTool(cfg, service, QueryService(context=None))

    res = await tool.execute(statement="SELECT QUICK", timeout_seconds=30.0)
    assert res["rowcount"] == 1

    event = json.loads(history_path.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert event["timeout_seconds"] == 30


@pytest.mark.asyncio
async def test_disabling_history_skips_sql_artifact(tmp_path, monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "")
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(artifact_root))

    cfg = Config(snowflake=SnowflakeConfig(profile="test"))
    service = FakeSnowflakeService([FakeQueryPlan(statement="SELECT QUICK", rows=[{"A": 1}, {"A": 2}])])
    tool = ExecuteQueryTool(cfg, service, QueryService(context=None))

    assert tool.history.enabled is False

    res = await tool.execute(statement="SELECT QUICK", timeout_seconds=2)
    assert res["rowcount"] == 2
    assert artifact_root.exists()
    sql_files = list(artifact_root.rglob("*.sql"))
    assert sql_files, "SQL artifact should be written even when history is disabled"


@pytest.mark.asyncio
async def test_reason_query_tag_applied_per_request_and_restored(tmp_path, monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "refresh")
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(tmp_path / "history.jsonl"))
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("IGLOO_MCP_CACHE_ROOT", str(tmp_path / "cache"))

    cfg = Config(snowflake=SnowflakeConfig(profile="test"))
    service = FakeSnowflakeService(
        [
            FakeQueryPlan(statement="SELECT QUICK", rows=[{"A": 1}, {"A": 2}]),
            FakeQueryPlan(statement="SELECT QUICK", rows=[{"A": 1}, {"A": 2}]),
        ]
    )

    tool = ExecuteQueryTool(cfg, service, QueryService(context=None))

    await tool.execute(statement="SELECT QUICK", timeout_seconds=2, reason="First pass")
    await tool.execute(statement="SELECT QUICK", timeout_seconds=2, reason="Second pass")

    executed_cursors = [cursor for cursor in service.cursors if cursor._main_executed]
    assert len(executed_cursors) == 2

    tags = [tag for cursor in executed_cursors for tag in cursor.query_tags_seen if tag is not None]
    assert tags == [
        "tool:execute_query; reason:First pass",
        "tool:execute_query; reason:Second pass",
    ]
    for cursor in executed_cursors:
        assert cursor._session_parameters["QUERY_TAG"] is None
        assert cursor.statement_timeouts_seen == ["2"]
        assert cursor._session_parameters["STATEMENT_TIMEOUT_IN_SECONDS"] == "0"


@pytest.mark.asyncio
async def test_large_result_triggers_truncation(tmp_path, monkeypatch):
    history_path = tmp_path / "history.jsonl"
    artifact_root = tmp_path / "artifacts"
    cache_root = tmp_path / "cache"

    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(history_path))
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("IGLOO_MCP_CACHE_ROOT", str(cache_root))

    cfg = Config(snowflake=SnowflakeConfig(profile="test"))

    mock_rows = [{"idx": i, "payload": "x" * 2048} for i in range(1, 1201)]

    plan = FakeQueryPlan(
        statement="SELECT BIG",
        rows=mock_rows,
        rowcount=len(mock_rows),
        duration=0.01,
        sfqid="BIG_QID",
    )
    service = FakeSnowflakeService([plan])
    tool = ExecuteQueryTool(cfg, service, QueryService(context=None))

    result = await tool.execute(
        statement="SELECT BIG",
        reason="Test large result truncation",
        response_mode="full",  # Explicitly request full mode (default changed to 'summary' in v0.3.7)
    )

    assert result["truncated"] is True
    assert result["original_rowcount"] == len(mock_rows)
    assert result["returned_rowcount"] == len(result["rows"])
    marker = result["rows"][500]
    assert marker.get("__truncated__") is True
    assert "Large result set truncated" in marker.get("__message__", "")

    manifest_path = Path(result["cache"]["manifest_path"])
    assert manifest_path.exists()
    rows_path = manifest_path.parent / "rows.jsonl"
    assert rows_path.exists()

    cached_result = await tool.execute(
        statement="SELECT BIG",
        reason="Test cache hit",
        response_mode="full",
        timeout_seconds=120,
    )
    assert cached_result["cache"]["hit"] is True
    executed_cursors = [cursor for cursor in service.cursors if cursor._main_executed]
    assert len(executed_cursors) == 1
    # Cache hit should not execute an additional query; the last cursor is the snapshot used for cache lookup.
    assert service.cursors[-1]._main_executed is False


@pytest.mark.asyncio
async def test_timeout_error_message_prioritizes_catalog_filtering(tmp_path, monkeypatch):
    """Test that timeout error messages prioritize catalog-based filtering before timeout increases."""
    history_path = tmp_path / "history.jsonl"
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(history_path))
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(artifact_root))

    cfg = Config(snowflake=SnowflakeConfig(profile="test"))
    service = FakeSnowflakeService(
        [
            FakeQueryPlan(
                statement="SELECT * FROM large_table",
                rows=[{"A": 1}],
                duration=2.0,
            )
        ]
    )
    tool = ExecuteQueryTool(cfg, service, QueryService(context=None))

    with pytest.raises((RuntimeError, MCPExecutionError)) as exc:
        await tool.execute(statement="SELECT * FROM large_table", timeout_seconds=1)

    error_msg = str(exc.value)

    # Check that catalog/clustering guidance comes before timeout increase
    assert "filter by clustering keys" in error_msg
    assert "catalog columns first" in error_msg

    # Timeout increase should be mentioned but not first
    timeout_mention = error_msg.find("increase timeout_seconds")
    clustering_mention = error_msg.find("clustering keys")

    if timeout_mention != -1 and clustering_mention != -1:
        assert clustering_mention < timeout_mention, "Clustering guidance should come before timeout increase"
