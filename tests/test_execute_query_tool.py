"""Integration-like tests for ExecuteQueryTool behavior."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pytest

from igloo_mcp.config import Config, SQLPermissions
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool


@pytest.mark.anyio
async def test_execute_query_allows_union_statement():
    """UNION queries should execute when SELECT is permitted."""

    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    snowflake_service = Mock()
    query_service = Mock()

    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=snowflake_service,
        query_service=query_service,
        health_monitor=None,
    )

    statement = "SELECT 1 UNION SELECT 2"
    expected = {
        "statement": statement,
        "rowcount": 2,
        "rows": [[1], [2]],
    }

    tool._execute_query_sync = Mock(return_value=expected)  # type: ignore[assignment]

    result = await tool.execute(statement=statement)

    assert result == expected
    assert tool._execute_query_sync.call_count == 1
