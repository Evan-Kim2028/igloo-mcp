import json
import time
from typing import Any, Dict, List, Literal, Optional, Tuple

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.service_layer.query_service import QueryService


class _FakeCursor:
    def __init__(self, work_seconds: float = 1.0):
        self._cancelled: bool = False
        self._fetchone_map: Dict[str, str] = {}
        self._rows: List[Dict[str, Any]] = []
        self.sfqid: Optional[str] = None
        self._work_seconds = work_seconds
        self.description: Optional[List[Tuple[str, ...]]] = None
        self._session_parameters: Dict[str, Optional[str]] = {
            "QUERY_TAG": None,
            "STATEMENT_TIMEOUT_IN_SECONDS": "0",
        }
        self.query_tags_seen: List[Optional[str]] = []
        self.statement_timeouts_seen: List[Optional[str]] = []

    def execute(self, query: str) -> None:
        q = query.strip().upper()
        if q.startswith("SHOW PARAMETERS LIKE 'QUERY_TAG'"):
            value = self._session_parameters["QUERY_TAG"]
            self.description = [("key",), ("value",)]
            self._rows = [{"KEY": "QUERY_TAG", "VALUE": value or ""}]
            return
        if q.startswith("SHOW PARAMETERS LIKE 'STATEMENT_TIMEOUT_IN_SECONDS'"):
            value = self._session_parameters["STATEMENT_TIMEOUT_IN_SECONDS"]
            self.description = [("key",), ("value",)]
            self._rows = [{"KEY": "STATEMENT_TIMEOUT_IN_SECONDS", "VALUE": value or ""}]
            return
        if q.startswith("ALTER SESSION SET QUERY_TAG"):
            raw = query.split("=", 1)[1].strip().rstrip(";")
            cleaned = raw.strip().strip("'").replace("''", "'")
            self._session_parameters["QUERY_TAG"] = cleaned or None
            self.description = None
            self._rows = []
            return
        if q.startswith("ALTER SESSION UNSET QUERY_TAG"):
            self._session_parameters["QUERY_TAG"] = None
            self.description = None
            self._rows = []
            return
        if q.startswith("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS"):
            raw_timeout = query.split("=", 1)[1].strip().rstrip(";")
            self._session_parameters["STATEMENT_TIMEOUT_IN_SECONDS"] = (
                raw_timeout or None
            )
            self.description = None
            self._rows = []
            return
        if q.startswith("ALTER SESSION UNSET STATEMENT_TIMEOUT_IN_SECONDS"):
            self._session_parameters["STATEMENT_TIMEOUT_IN_SECONDS"] = "0"
            self.description = None
            self._rows = []
            return
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
        if (
            q.startswith("USE ROLE")
            or q.startswith("USE WAREHOUSE")
            or q.startswith("USE DATABASE")
            or q.startswith("USE SCHEMA")
        ):
            self.description = None
            self._rows = []
            return

        # Simulate long/short query returning a result set
        self.sfqid = "FAKE_QID_123"
        self.query_tags_seen.append(self._session_parameters["QUERY_TAG"])
        self.statement_timeouts_seen.append(
            self._session_parameters["STATEMENT_TIMEOUT_IN_SECONDS"]
        )
        end = time.time() + self._work_seconds
        while time.time() < end:
            if self._cancelled:
                self._rows = []
                return
            time.sleep(0.01)
        # For SELECT-like result sets, DB-API sets a non-None description
        self.description = [("A",)]
        self._rows = [{"A": 1}, {"A": 2}]

    def fetchone(self) -> Dict[str, str]:
        return self._fetchone_map

    def fetchall(self) -> List[Dict[str, Any]]:
        return self._rows

    def cancel(self) -> None:
        self._cancelled = True


class _FakeConn:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor

    def __enter__(self) -> Tuple[None, _FakeCursor]:
        return (None, self._cursor)

    def __exit__(self, exc_type, exc, tb) -> Literal[False]:  # noqa: ANN001
        return False


class _FakeService:
    def __init__(self, work_seconds: float):
        self._cursor = _FakeCursor(work_seconds=work_seconds)

    def get_connection(
        self,
        *,
        use_dict_cursor: bool = True,  # noqa: FBT001
        session_parameters: Optional[Dict[str, Any]] = None,
    ) -> _FakeConn:
        return _FakeConn(self._cursor)

    def get_query_tag_param(self) -> Dict[str, Any]:
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
        await tool.execute(statement="SELECT LONG_RUNNING", timeout_seconds=1)
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


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_value", ["30", 12.5, True])
async def test_timeout_seconds_requires_integer(bad_value):
    cfg = Config(snowflake=SnowflakeConfig(profile="test"))
    tool = ExecuteQueryTool(
        cfg, _FakeService(work_seconds=0.05), QueryService(context=None)
    )

    with pytest.raises((TypeError, ValueError)):
        await tool.execute(statement="SELECT QUICK", timeout_seconds=bad_value)


@pytest.mark.asyncio
async def test_reason_query_tag_applied_per_request_and_restored():
    cfg = Config(snowflake=SnowflakeConfig(profile="test"))
    service = _FakeService(work_seconds=0.05)
    tool = ExecuteQueryTool(cfg, service, QueryService(context=None))

    await tool.execute(statement="SELECT QUICK", timeout_seconds=2, reason="First pass")
    await tool.execute(
        statement="SELECT QUICK", timeout_seconds=2, reason="Second pass"
    )

    cursor = service._cursor
    assert cursor.query_tags_seen == [
        "tool:execute_query; reason:First pass",
        "tool:execute_query; reason:Second pass",
    ]
    assert cursor._session_parameters["QUERY_TAG"] is None
    assert cursor.statement_timeouts_seen == ["2", "2"]
    assert cursor._session_parameters["STATEMENT_TIMEOUT_IN_SECONDS"] == "0"
