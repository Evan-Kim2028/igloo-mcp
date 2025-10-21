import pytest

from igloo_mcp.config import Config, SnowflakeConfig, SQLPermissions
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.service_layer.query_service import QueryService


class _DmlCursor:
    def __init__(self, affected: int = 3):
        self.description = None  # No result set for DML
        self.rowcount = affected
        self.sfqid = "FAKE_DML_QID"

    def execute(self, query: str) -> None:  # noqa: ARG002
        # Nothing else to do; rowcount is already set
        return

    def fetchone(self):
        # Snapshot queries might be run; return a minimal mapping as needed
        return {"ROLE": "TEST", "WAREHOUSE": "WH", "DATABASE": "DB", "SCHEMA": "PUBLIC"}

    def fetchall(self):
        # Should not be called for DML/DDL paths
        raise RuntimeError("fetchall() should not be called for DML without result set")

    def cancel(self):
        return


class _Conn:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return (None, self._cursor)

    def __exit__(self, exc_type, exc, tb):  # noqa: ARG002
        return False


class _Service:
    def __init__(self):
        self._cursor = _DmlCursor()

    def get_connection(
        self, *, use_dict_cursor=True, session_parameters=None
    ):  # noqa: ARG002
        return _Conn(self._cursor)

    def get_query_tag_param(self):
        return {}


@pytest.mark.asyncio
async def test_dml_does_not_fetch_rows():
    cfg = Config(
        snowflake=SnowflakeConfig(profile="test"),
        sql_permissions=SQLPermissions(insert=True),
    )
    tool = ExecuteQueryTool(cfg, _Service(), QueryService(context=None))

    res = await tool.execute(statement="INSERT INTO t VALUES (1)", timeout_seconds=2)

    assert res["rows"] == []
    assert res["rowcount"] == 3  # Comes from cursor.rowcount
    assert res["query_id"] == "FAKE_DML_QID"
