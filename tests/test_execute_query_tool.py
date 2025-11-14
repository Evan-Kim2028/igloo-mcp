"""Integration-like tests for ExecuteQueryTool behavior."""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime
from unittest.mock import Mock

import anyio
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

    assert result["rowcount"] == expected["rowcount"]
    assert result["rows"] == expected["rows"]
    assert result["statement"] == statement
    assert result["cache"]["hit"] is False
    assert "key_metrics" in result and result["key_metrics"]["total_rows"] == 2
    assert "insights" in result and result["insights"]
    assert tool._execute_query_sync.call_count == 1


@pytest.mark.anyio
async def test_execute_query_async_mode_returns_handle(monkeypatch):
    """response_mode=async should enqueue the query and allow polling."""

    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")
    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    snowflake_service = Mock()
    query_service = Mock()

    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=snowflake_service,
        query_service=query_service,
        health_monitor=None,
    )

    statement = "SELECT 1"
    expected = {
        "statement": statement,
        "rowcount": 1,
        "rows": [[1]],
        "query_id": "01ab",
        "duration_ms": 10,
    }

    tool._execute_query_sync = Mock(return_value=expected)  # type: ignore[assignment]

    response = await tool.execute(statement=statement, response_mode="async")
    assert response["status"] == "accepted"
    execution_id = response["execution_id"]

    poll = await tool.fetch_async_result(execution_id=execution_id)
    attempts = 0
    while poll["status"] != "success" and attempts < 10:
        await anyio.sleep(0.01)
        poll = await tool.fetch_async_result(execution_id=execution_id)
        attempts += 1
    assert poll["status"] == "success"
    assert poll["result"]["rowcount"] == 1
    assert poll["result"]["rows"] == [[1]]
    assert tool._async_jobs == {}


@pytest.mark.anyio
async def test_execute_query_auto_returns_result_within_rpc(monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")
    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    snowflake_service = Mock()
    query_service = Mock()

    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=snowflake_service,
        query_service=query_service,
        health_monitor=None,
    )

    tool._rpc_soft_timeout = 2  # seconds
    tool.AUTO_ASYNC_MARGIN_SECONDS = 0.5
    tool.AUTO_ASYNC_POLL_INTERVAL_SECONDS = 0.05

    expected = {
        "statement": "SELECT 1",
        "rowcount": 1,
        "rows": [[1]],
        "duration_ms": 10,
    }

    tool._execute_query_sync = Mock(return_value=expected)  # type: ignore[assignment]

    result = await tool.execute(statement="SELECT 1", timeout_seconds=60)

    assert result["rowcount"] == 1
    assert result["rows"] == [[1]]
    assert result["cache"]["hit"] is False
    assert tool._async_jobs == {}


@pytest.mark.anyio
async def test_execute_query_auto_falls_back_to_async(monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")
    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    snowflake_service = Mock()
    query_service = Mock()

    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=snowflake_service,
        query_service=query_service,
        health_monitor=None,
    )

    tool._rpc_soft_timeout = 0.2
    tool.AUTO_ASYNC_MARGIN_SECONDS = 0.05
    tool.AUTO_ASYNC_POLL_INTERVAL_SECONDS = 0.01

    expected = {
        "statement": "SELECT 1",
        "rowcount": 1,
        "rows": [[1]],
        "duration_ms": 300,
    }

    def slow_execute(*_args, **_kwargs):
        time.sleep(0.3)
        return expected

    tool._execute_query_sync = Mock(side_effect=slow_execute)  # type: ignore[assignment]

    response = await tool.execute(statement="SELECT 1", timeout_seconds=120)

    assert response["status"] == "accepted"
    assert response.get("inline_wait_seconds") is not None
    execution_id = response["execution_id"]

    poll = await tool.fetch_async_result(execution_id=execution_id)
    attempts = 0
    while poll["status"] != "success" and attempts < 20:
        await anyio.sleep(0.01)
        poll = await tool.fetch_async_result(execution_id=execution_id)
        attempts += 1

    assert poll["status"] == "success"
    assert poll["result"]["rowcount"] == 1
    assert tool._async_jobs == {}


@pytest.mark.anyio
async def test_execute_query_generates_key_metrics(monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    snowflake_service = Mock()
    query_service = Mock()

    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=snowflake_service,
        query_service=query_service,
        health_monitor=None,
    )

    rows = [
        {"amount": 10, "event_ts": datetime(2025, 1, 1), "owner": "alice"},
        {"amount": 15, "event_ts": datetime(2025, 1, 2), "owner": "bob"},
        {"amount": 12, "event_ts": datetime(2025, 1, 3), "owner": "alice"},
    ]
    expected = {
        "statement": "SELECT amount, event_ts, owner FROM metrics",
        "rowcount": len(rows),
        "rows": rows,
        "duration_ms": 50,
    }

    tool._execute_query_sync = Mock(return_value=expected)  # type: ignore[assignment]

    result = await tool.execute(statement=expected["statement"])

    metrics = result.get("key_metrics")
    assert metrics is not None
    assert metrics["total_rows"] == len(rows)
    kinds = {col["kind"] for col in metrics["columns"]}
    assert {"numeric", "time", "categorical"}.issubset(kinds)
    assert result.get("insights")
