from unittest.mock import patch

import pytest

from igloo_mcp.config import Config, SnowflakeConfig, SQLPermissions
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.service_layer.query_service import QueryService
from tests.helpers.fake_snowflake_connector import FakeQueryPlan, FakeSnowflakeService


@pytest.mark.asyncio
async def test_dml_does_not_fetch_rows():
    cfg = Config(
        snowflake=SnowflakeConfig(profile="test"),
        sql_permissions=SQLPermissions(insert=True),
    )
    service = FakeSnowflakeService(
        [
            FakeQueryPlan(
                statement="INSERT INTO t VALUES (1)",
                rows=None,
                rowcount=3,
                sfqid="FAKE_DML_QID",
            )
        ]
    )
    with patch.dict("os.environ", {"IGLOO_MCP_CACHE_MODE": "refresh"}, clear=False):
        tool = ExecuteQueryTool(cfg, service, QueryService(context=None))
        res = await tool.execute(
            statement="INSERT INTO t VALUES (1)", timeout_seconds=2
        )

    assert res["rows"] == []
    assert res["rowcount"] == 3  # Comes from cursor.rowcount
    assert res["query_id"] == "FAKE_DML_QID"
