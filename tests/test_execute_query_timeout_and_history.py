import json
import time

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.service_layer.query_service import QueryService


class _FakeCursor:
    def __init__(self, work_seconds: float = 1.0):
        self._cancelled = False
        self._fetchone_map = {}
        self._rows = []
        self.sfqid = None
        self._work_seconds = work_seconds
        self.description = None

    def execute(self, query: str) -> None:
        q = query.strip().upper()
        # Fast paths for session snapshot queries
        if q.startswith("SELECT CURRENT_ROLE()"):
            self._fetchone_map = {"ROLE": "TEST_ROLE"}
            return
        if q.startswith("SELECT CURRENT_WAREHOUSE()"):
            self._fetchone_map = {"WAREHOUSE": "TEST_WH"}
            return
        if q.startswith("SELECT CURRENT_DATABASE()"):
            self._fetchone_map = {"DATABASE": "TEST_DB"}
            return
        if q.startswith("SELECT CURRENT_SCHEMA()"):
            self._fetchone_map = {"SCHEMA": "PUBLIC"}
            return

        # Simulate long/short query returning a result set
        self.sfqid = "FAKE_QID_123"
        end = time.time() + self._work_seconds
        while time.time() < end:
            if self._cancelled:
                self._rows = []
                return
            time.sleep(0.01)
        # For SELECT-like result sets, DB-API sets a non-None description
        self.description = [("A",)]
        self._rows = [{"A": 1}, {"A": 2}]

    def fetchone(self):
        return self._fetchone_map

    def fetchall(self):
        return self._rows

    def cancel(self):
        self._cancelled = True


class _FakeConn:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor

    def __enter__(self):
        return (None, self._cursor)

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeService:
    def __init__(self, work_seconds: float):
        self._cursor = _FakeCursor(work_seconds=work_seconds)

    def get_connection(
        self, *, use_dict_cursor=True, session_parameters=None
    ):  # noqa: ARG002
        return _FakeConn(self._cursor)

    def get_query_tag_param(self):
        return {}


@pytest.mark.asyncio
async def test_timeout_cancels_and_logs_history(tmp_path, monkeypatch):
    history_path = tmp_path / "history.jsonl"
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(history_path))

    cfg = Config(snowflake=SnowflakeConfig(profile="test"))
    tool = ExecuteQueryTool(
        cfg, _FakeService(work_seconds=2.0), QueryService(context=None)
    )

    with pytest.raises(RuntimeError) as exc:
        await tool.execute(statement="SELECT LONG_RUNNING", timeout_seconds=0.1)
    assert "Query timeout" in str(exc.value)

    # History should have a timeout record
    data = history_path.read_text(encoding="utf-8").strip().splitlines()
    assert data, "expected at least one history line"
    event = json.loads(data[-1])
    assert event["status"] == "timeout"
    assert event.get("statement_preview", "").startswith("SELECT LONG_RUNNING")


@pytest.mark.asyncio
async def test_success_returns_query_id_and_logs(tmp_path, monkeypatch):
    history_path = tmp_path / "history.jsonl"
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(history_path))

    cfg = Config(snowflake=SnowflakeConfig(profile="test"))
    tool = ExecuteQueryTool(
        cfg, _FakeService(work_seconds=0.05), QueryService(context=None)
    )

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
