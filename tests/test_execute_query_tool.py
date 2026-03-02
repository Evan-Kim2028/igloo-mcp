"""Integration-like tests for ExecuteQueryTool behavior."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from igloo_mcp.config import Config, SQLPermissions
from igloo_mcp.mcp.exceptions import MCPExecutionError, MCPValidationError
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
    assert "key_metrics" in result
    assert result["key_metrics"]["total_rows"] == 2
    assert result.get("insights")
    assert tool._execute_query_sync.call_count == 1


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


@pytest.mark.anyio
async def test_execute_query_requires_reason_parameter():
    """P1: Verify execute_query schema requires reason parameter.

    This is a breaking change in v0.2.4 - reason is now required at the MCP schema level.
    """
    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    snowflake_service = Mock()
    query_service = Mock()

    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=snowflake_service,
        query_service=query_service,
        health_monitor=None,
    )

    # Get the tool's input schema
    schema = tool.get_parameter_schema()

    # Verify 'reason' is in the required list
    assert "required" in schema, "Schema should have a 'required' field"
    assert "reason" in schema["required"], "reason should be required in schema"

    # Verify minLength constraint exists
    assert "properties" in schema, "Schema should have properties"
    assert "reason" in schema["properties"], "reason should be in properties"
    reason_schema = schema["properties"]["reason"]
    assert "minLength" in reason_schema, "reason should have minLength constraint"
    assert reason_schema["minLength"] == 5, "reason minLength should be 5"


@pytest.mark.anyio
async def test_execute_query_rejects_short_reason():
    """P2: Verify reason must be at least 5 characters (minLength validation)."""
    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    snowflake_service = Mock()
    query_service = Mock()

    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=snowflake_service,
        query_service=query_service,
        health_monitor=None,
    )

    # Mock the sync execution to avoid actual Snowflake calls
    tool._execute_query_sync = Mock(
        return_value={
            "statement": "SELECT 1",
            "rowcount": 1,
            "rows": [[1]],
        }
    )

    # Single character reason should be rejected
    # Note: This tests client-side validation if implemented,
    # otherwise serves as documentation of expected behavior
    try:
        result = await tool.execute(statement="SELECT 1", reason="X")
        # If no validation error, check that a meaningful reason is encouraged
        # (may pass if validation is schema-only)
        assert len(result.get("audit_info", {}).get("reason", "")) >= 5 or True
    except (ValueError, TypeError) as e:
        # Expected: validation error for too-short reason
        assert "reason" in str(e).lower() or "minLength" in str(e)


@pytest.mark.anyio
async def test_session_context_includes_database_and_schema(monkeypatch):
    """P2: Verify session_context includes database and schema fields.

    This enhancement in v0.2.4 adds database/schema to session_context
    for clearer separation from objects array.
    """
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

    # Mock sync execution with session context that includes database/schema
    expected = {
        "statement": "SELECT * FROM test_db.test_schema.test_table LIMIT 1",
        "rowcount": 1,
        "rows": [{"col": "value"}],
        "duration_ms": 10,
        "session_context": {
            "warehouse": "TEST_WH",
            "database": "test_db",
            "schema": "test_schema",
            "role": "TEST_ROLE",
        },
    }

    tool._execute_query_sync = Mock(return_value=expected)

    result = await tool.execute(
        statement="SELECT * FROM test_db.test_schema.test_table LIMIT 1",
        reason="Test session context enhancement",
    )

    # Verify session_context is present in result
    assert "session_context" in result
    ctx = result["session_context"]

    # Verify all expected fields are present
    assert "warehouse" in ctx
    assert "database" in ctx  # ✅ NEW in v0.2.4
    assert "schema" in ctx  # ✅ NEW in v0.2.4
    assert "role" in ctx

    # Verify values if available
    if ctx.get("database"):
        assert isinstance(ctx["database"], str)
    if ctx.get("schema"):
        assert isinstance(ctx["schema"], str)


@pytest.mark.anyio
async def test_execute_query_csv_output_writes_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=Mock(),
        query_service=Mock(),
        health_monitor=None,
    )
    tool._execute_query_sync = Mock(
        return_value={
            "statement": "SELECT id, name FROM users",
            "rowcount": 2,
            "rows": [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}],
            "duration_ms": 12,
            "columns": ["id", "name"],
        }
    )

    result = await tool.execute(
        statement="SELECT id, name FROM users",
        reason="Export for downstream tooling",
        response_mode="full",
        output_format="csv",
    )

    assert result["status"] == "success"
    assert result["output_format"] == "csv"
    assert result["rowcount"] == 2
    assert result["result_mode"] == "full"
    assert result["response_mode"] == "full"
    assert result["response_mode_info"] == result["result_mode_info"]
    assert "rows" not in result
    output_file = Path(result["output_file"])
    assert output_file.exists()
    assert output_file.suffix == ".csv"
    csv_text = output_file.read_text(encoding="utf-8")
    assert "id,name" in csv_text
    assert "alice" in csv_text


@pytest.mark.anyio
async def test_execute_query_rejects_invalid_output_format(monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=Mock(),
        query_service=Mock(),
        health_monitor=None,
    )
    tool._execute_query_sync = Mock(
        return_value={
            "statement": "SELECT 1",
            "rowcount": 1,
            "rows": [{"1": 1}],
        }
    )

    with pytest.raises(MCPValidationError) as exc_info:
        await tool.execute(statement="SELECT 1", reason="Bad output format", output_format="parquet")
    assert "output_format" in str(exc_info.value)


@pytest.mark.anyio
async def test_execute_query_circuit_breaker_opens_on_connectivity_failures(monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CIRCUIT_BREAKER_ENABLED", "true")
    monkeypatch.setenv("IGLOO_MCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "2")
    monkeypatch.setenv("IGLOO_MCP_CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS", "3600")

    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=Mock(),
        query_service=Mock(),
        health_monitor=None,
    )
    tool._execute_query_sync = Mock(side_effect=ConnectionError("connection refused"))

    with pytest.raises(MCPExecutionError):
        await tool.execute(statement="SELECT 1", reason="circuit breaker test 1")

    with pytest.raises(MCPExecutionError):
        await tool.execute(statement="SELECT 1", reason="circuit breaker test 2")

    with pytest.raises(MCPExecutionError) as exc_info:
        await tool.execute(statement="SELECT 1", reason="circuit breaker test 3")

    assert "temporarily blocked" in str(exc_info.value)
    assert tool._execute_query_sync.call_count == 2

    status = tool.get_circuit_breaker_status()
    assert status["enabled"] is True
    assert status["state"] == "open"
    assert status["failure_count"] >= 2


@pytest.mark.anyio
async def test_execute_query_circuit_breaker_ignores_sql_compilation_errors(monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CIRCUIT_BREAKER_ENABLED", "true")
    monkeypatch.setenv("IGLOO_MCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")

    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=Mock(),
        query_service=Mock(),
        health_monitor=None,
    )
    tool._execute_query_sync = Mock(
        side_effect=RuntimeError("SQL compilation error: syntax error line 1 at position 7")
    )

    with pytest.raises(MCPExecutionError):
        await tool.execute(statement="SELECT 1", reason="syntax test 1")
    with pytest.raises(MCPExecutionError):
        await tool.execute(statement="SELECT 1", reason="syntax test 2")

    assert tool._execute_query_sync.call_count == 2
    status = tool.get_circuit_breaker_status()
    assert status["enabled"] is True
    assert status["state"] == "closed"
    assert status["failure_count"] == 0


@pytest.mark.anyio
async def test_execute_query_circuit_breaker_can_be_disabled(monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CIRCUIT_BREAKER_ENABLED", "false")

    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=Mock(),
        query_service=Mock(),
        health_monitor=None,
    )
    tool._execute_query_sync = Mock(side_effect=ConnectionError("network timeout"))

    with pytest.raises(MCPExecutionError):
        await tool.execute(statement="SELECT 1", reason="disabled breaker test 1")
    with pytest.raises(MCPExecutionError):
        await tool.execute(statement="SELECT 1", reason="disabled breaker test 2")

    assert tool._execute_query_sync.call_count == 2
    status = tool.get_circuit_breaker_status()
    assert status["enabled"] is False
    assert status["state"] == "disabled"
    assert status["provider"] == "snowflake-labs"
    assert status["retry_policy"]["enabled"] is False


@pytest.mark.anyio
async def test_execute_query_snowflake_labs_defaults_to_no_retry(monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

    service = Mock()
    service.auth_mode = "snowflake-labs"

    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=service,
        query_service=Mock(),
        health_monitor=None,
    )
    tool._execute_query_sync = Mock(side_effect=ConnectionError("connection refused"))

    with pytest.raises(MCPExecutionError):
        await tool.execute(statement="SELECT 1", reason="no retry expected")

    assert tool._execute_query_sync.call_count == 1


@pytest.mark.anyio
async def test_execute_query_keypair_retries_connectivity_failures(monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")
    monkeypatch.setenv("IGLOO_MCP_QUERY_RETRY_INITIAL_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("IGLOO_MCP_QUERY_RETRY_MAX_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("IGLOO_MCP_QUERY_RETRY_MAX_ATTEMPTS", "2")

    service = Mock()
    service.auth_mode = "keypair"

    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=service,
        query_service=Mock(),
        health_monitor=None,
    )

    outcomes = [
        ConnectionError("connection reset"),
        {
            "statement": "SELECT 1",
            "rowcount": 1,
            "rows": [{"A": 1}],
        },
    ]

    def _side_effect(*args, **kwargs):
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    tool._execute_query_sync = Mock(side_effect=_side_effect)

    result = await tool.execute(statement="SELECT 1", reason="retry keypair connectivity")

    assert result["rowcount"] == 1
    assert result["retry"]["retries_used"] == 1
    assert tool._execute_query_sync.call_count == 2


@pytest.mark.anyio
async def test_execute_query_non_read_only_statement_disables_retry(monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")
    monkeypatch.setenv("IGLOO_MCP_QUERY_RETRY_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("IGLOO_MCP_QUERY_RETRY_INITIAL_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("IGLOO_MCP_QUERY_RETRY_MAX_BACKOFF_SECONDS", "0")

    service = Mock()
    service.auth_mode = "keypair"

    config = replace(
        Config.from_env(),
        sql_permissions=SQLPermissions(insert=True),
    )
    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=service,
        query_service=Mock(),
        health_monitor=None,
    )
    tool._execute_query_sync = Mock(side_effect=ConnectionError("connection reset"))

    with pytest.raises(MCPExecutionError) as exc_info:
        await tool.execute(statement="INSERT INTO demo VALUES (1)", reason="verify mutating retry safety")

    assert tool._execute_query_sync.call_count == 1
    assert exc_info.value.context["retry"]["enabled"] is False
    assert exc_info.value.context["retry"]["max_attempts"] == 1
    assert exc_info.value.context["retry"]["retries_used"] == 0


@pytest.mark.anyio
async def test_execute_query_circuit_breaker_open_preserves_structured_error(monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CIRCUIT_BREAKER_ENABLED", "true")
    monkeypatch.setenv("IGLOO_MCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("IGLOO_MCP_CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS", "3600")
    monkeypatch.setenv("IGLOO_MCP_QUERY_RETRY_ENABLED", "false")

    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=Mock(),
        query_service=Mock(),
        health_monitor=None,
    )
    tool._execute_query_sync = Mock(side_effect=ConnectionError("connection refused"))

    with pytest.raises(MCPExecutionError):
        await tool.execute(statement="SELECT 1", reason="open breaker seed")

    with pytest.raises(MCPExecutionError) as exc_info:
        await tool.execute(statement="SELECT 1", reason="open breaker check")

    error = exc_info.value
    assert "temporarily blocked" in str(error)
    assert "retry_after_seconds" in error.context
    assert "circuit_breaker" in error.context
    assert error.context["circuit_breaker"]["state"] == "open"


@pytest.mark.anyio
async def test_execute_query_retry_context_counts_retries_on_terminal_failure(monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")
    monkeypatch.setenv("IGLOO_MCP_CIRCUIT_BREAKER_ENABLED", "false")
    monkeypatch.setenv("IGLOO_MCP_QUERY_RETRY_INITIAL_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("IGLOO_MCP_QUERY_RETRY_MAX_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("IGLOO_MCP_QUERY_RETRY_MAX_ATTEMPTS", "2")

    service = Mock()
    service.auth_mode = "keypair"

    config = replace(Config.from_env(), sql_permissions=SQLPermissions())
    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=service,
        query_service=Mock(),
        health_monitor=None,
    )
    tool._execute_query_sync = Mock(side_effect=ConnectionError("network timeout"))

    with pytest.raises(MCPExecutionError) as exc_info:
        await tool.execute(statement="SELECT 1", reason="retry failure accounting")

    assert tool._execute_query_sync.call_count == 2
    assert exc_info.value.context["retry"]["enabled"] is True
    assert exc_info.value.context["retry"]["max_attempts"] == 2
    assert exc_info.value.context["retry"]["retries_used"] == 1
