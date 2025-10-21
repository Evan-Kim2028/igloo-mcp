from __future__ import annotations

import time
from typing import Any, Dict, Optional

import anyio

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.service_layer.query_service import QueryService


class FakeCursor:
    def __init__(self, work_seconds: float = 10.0) -> None:
        self._last_query: Optional[str] = None
        self._fetchone_result: Optional[Dict[str, Any]] = None
        self._rows: Optional[list[dict[str, Any]]] = None
        self._cancelled = False
        self._work_seconds = work_seconds
        self.sfqid: Optional[str] = None

    def execute(self, query: str) -> None:
        self._last_query = query

        # Handle session snapshot queries quickly
        q = query.upper().strip()
        if q.startswith("SELECT CURRENT_ROLE()"):
            self._fetchone_result = {"ROLE": "ANALYST"}
            return
        if q.startswith("SELECT CURRENT_WAREHOUSE()"):
            self._fetchone_result = {"WAREHOUSE": "TEST_WH"}
            return
        if q.startswith("SELECT CURRENT_DATABASE()"):
            self._fetchone_result = {"DATABASE": "TEST_DB"}
            return
        if q.startswith("SELECT CURRENT_SCHEMA()"):
            self._fetchone_result = {"SCHEMA": "PUBLIC"}
            return

        # Simulate a long-running query that can be cancelled
        self.sfqid = "FAKE_QID_123"
        deadline = time.time() + self._work_seconds
        while time.time() < deadline:
            if self._cancelled:
                # Simulate a cancelled query by returning early
                self._rows = []
                return
            time.sleep(0.05)

        # Completed normally
        self._rows = [{"A": 1}, {"A": 2}]

    def fetchone(self):
        return self._fetchone_result

    def fetchall(self):
        return self._rows or []

    def cancel(self):
        self._cancelled = True


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return (None, self._cursor)

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeService:
    def __init__(self, work_seconds: float) -> None:
        self._cursor = FakeCursor(work_seconds=work_seconds)

    def get_connection(
        self,
        *,
        use_dict_cursor: bool = True,
        session_parameters: Optional[dict[str, Any]] = None,
    ):
        return FakeConnection(self._cursor)

    def get_query_tag_param(self) -> dict[str, Any]:
        return {}


async def run_smoke():
    cfg = Config(snowflake=SnowflakeConfig(profile="test_profile"))
    query_service = QueryService(context=None)

    print("Case 1: Timeout + cancel path...")
    tool = ExecuteQueryTool(cfg, FakeService(work_seconds=5.0), query_service)
    try:
        await tool.execute(
            statement="SELECT LONG_RUNNING", timeout_seconds=1, verbose_errors=False
        )
    except RuntimeError as e:
        print("  -> Caught RuntimeError (expected timeout):", str(e)[:120])
    else:
        print("  -> Unexpected success (should have timed out)")

    print("Case 2: Success within timeout...")
    tool2 = ExecuteQueryTool(cfg, FakeService(work_seconds=0.2), query_service)
    res = await tool2.execute(
        statement="SELECT QUICK", timeout_seconds=3, verbose_errors=True
    )
    print("  -> Success rowcount:", res.get("rowcount"))
    print("  -> Query ID:", res.get("query_id"))
    print("  -> Duration ms:", res.get("duration_ms"))


if __name__ == "__main__":
    anyio.run(run_smoke)
