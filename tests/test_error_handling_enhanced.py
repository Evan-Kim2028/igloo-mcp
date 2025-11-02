"""Enhanced tests for structured error handling in execute_query."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from igloo_mcp.config import Config
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from tests.helpers.fake_snowflake_connector import (
    FakeQueryPlan,
    FakeSnowflakeService,
)


def _make_tool(
    config: Config,
    plan: FakeQueryPlan,
    *,
    monkeypatch: pytest.MonkeyPatch | None = None,
    tmp_path: Path | None = None,
) -> tuple[ExecuteQueryTool, FakeSnowflakeService]:
    if monkeypatch:
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "")
        if tmp_path is not None:
            artifact_root = tmp_path / "artifacts"
            artifact_root.mkdir(parents=True, exist_ok=True)
            monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(artifact_root))
    service = FakeSnowflakeService([plan])
    tool = ExecuteQueryTool(
        config=config,
        snowflake_service=service,
        query_service=Mock(),
        health_monitor=None,
    )
    return tool, service


class TestEnhancedErrorHandling:
    """Test enhanced structured error handling."""

    @pytest.mark.asyncio
    async def test_timeout_seconds_string_parameter_conversion(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config = Config.from_env()
        plan = FakeQueryPlan(
            statement="SELECT * FROM test",
            rows=[{"col": "val"}],
            duration=0.01,
        )
        tool, _ = _make_tool(config, plan, monkeypatch=monkeypatch, tmp_path=tmp_path)

        result = await tool.execute(
            statement="SELECT * FROM test", timeout_seconds="480"
        )

        assert result["rowcount"] == 1
        assert result["rows"] == [{"col": "val"}]
        assert result["cache"]["hit"] is False
        assert "audit_info" in result

    @pytest.mark.asyncio
    async def test_timeout_seconds_range_error(self) -> None:
        config = Config.from_env()
        plan = FakeQueryPlan(statement="SELECT * FROM test", rows=[{"col": 1}])
        tool, _ = _make_tool(config, plan)

        with pytest.raises(ValueError) as exc_info:
            await tool.execute(statement="SELECT * FROM test", timeout_seconds=0)

        assert "timeout_seconds must be between 1 and 3600" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_sql_validation_error_passthrough(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config = Config.from_env()
        plan = FakeQueryPlan(statement="DELETE FROM important_table")
        tool, _ = _make_tool(config, plan, monkeypatch=monkeypatch, tmp_path=tmp_path)

        with pytest.raises(ValueError) as exc_info:
            await tool.execute(statement="DELETE FROM important_table")

        msg = str(exc_info.value)
        assert "SQL statement type 'Delete' is not permitted" in msg
        assert "Safe alternatives:" in msg

    @pytest.mark.asyncio
    async def test_timeout_error_structured_response(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config = Config.from_env()
        plan = FakeQueryPlan(
            statement="SELECT * FROM large_table",
            error=TimeoutError("Query timeout"),
        )
        tool, _ = _make_tool(config, plan, monkeypatch=monkeypatch, tmp_path=tmp_path)

        with pytest.raises(RuntimeError) as exc_info:
            await tool.execute(
                statement="SELECT * FROM large_table", timeout_seconds=30
            )

        assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_generic_execution_error_handling(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config = Config.from_env()
        plan = FakeQueryPlan(
            statement="SELECT * FROM test",
            error=Exception("Database connection failed"),
        )
        tool, _ = _make_tool(config, plan, monkeypatch=monkeypatch, tmp_path=tmp_path)

        with pytest.raises(RuntimeError) as exc_info:
            await tool.execute(statement="SELECT * FROM test", verbose_errors=False)

        message = str(exc_info.value)
        assert "Query execution failed" in message
        assert len(message) <= 200

    @pytest.mark.asyncio
    async def test_verbose_errors_passthrough(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config = Config.from_env()
        plan = FakeQueryPlan(
            statement="SELECT * FROM test",
            error=Exception("Database connection failed: detailed error message"),
        )
        tool, _ = _make_tool(config, plan, monkeypatch=monkeypatch, tmp_path=tmp_path)

        with pytest.raises(RuntimeError) as exc_info:
            await tool.execute(statement="SELECT * FROM test", verbose_errors=True)

        assert "Database connection failed: detailed error message" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_parameter_validation_edge_cases(self) -> None:
        config = Config.from_env()
        plan = FakeQueryPlan(statement="SELECT * FROM test", rows=[{"col": 1}])
        tool, _ = _make_tool(config, plan)

        with pytest.raises((ValueError, TypeError)) as exc_info:
            await tool.execute(statement="SELECT * FROM test", timeout_seconds=True)

        assert "timeout_seconds" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_post_query_insight_parameter_handling(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config = Config.from_env()
        plan = FakeQueryPlan(
            statement="SELECT * FROM test",
            rows=[{"col": "val"}],
            rowcount=10,
        )
        tool, _ = _make_tool(config, plan, monkeypatch=monkeypatch, tmp_path=tmp_path)

        tool.history = Mock()
        tool.history.enabled = True
        tool.history.disabled = False
        tool.history.record = Mock()
        tool.history.pop_warnings.return_value = []
        tool.history.path = tmp_path / "history.jsonl"
        tool._history_enabled = True

        await tool.execute(
            statement="SELECT * FROM test",
            post_query_insight="Test shows positive trend",
        )

        tool.history.record.assert_called_once()
        payload = tool.history.record.call_args[0][0]
        assert (
            isinstance(payload["post_query_insight"], dict)
            and payload["post_query_insight"]["summary"] == "Test shows positive trend"
        )

    @pytest.mark.asyncio
    async def test_post_query_insight_as_dict_parameter_handling(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config = Config.from_env()
        plan = FakeQueryPlan(
            statement="SELECT * FROM test",
            rows=[{"col": "val"}],
            rowcount=10,
        )
        tool, _ = _make_tool(config, plan, monkeypatch=monkeypatch, tmp_path=tmp_path)

        tool.history = Mock()
        tool.history.enabled = True
        tool.history.disabled = False
        tool.history.record = Mock()
        tool.history.pop_warnings.return_value = []
        tool.history.path = tmp_path / "history.jsonl"
        tool._history_enabled = True

        insight_dict = {
            "summary": "Revenue increased 15%",
            "key_metrics": ["revenue:+15%", "customers:+200"],
            "business_impact": "Strong growth trajectory",
        }

        await tool.execute(
            statement="SELECT * FROM test", post_query_insight=insight_dict
        )

        tool.history.record.assert_called_once()
        payload = tool.history.record.call_args[0][0]
        assert all(
            payload["post_query_insight"].get(k) == insight_dict[k]
            for k in ("summary", "key_metrics", "business_impact")
        )

    def test_schema_includes_post_query_insight(self):
        """Ensure the tool schema advertises metric_insight."""
        config = Config.from_env()
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=Mock(),
            query_service=Mock(),
            health_monitor=None,
        )

        schema = tool.get_parameter_schema()
        metric_schema = schema["properties"]["post_query_insight"]

        assert "anyOf" in metric_schema
        assert any(option.get("type") == "string" for option in metric_schema["anyOf"])
        assert any(option.get("type") == "object" for option in metric_schema["anyOf"])
        assert "insights" in metric_schema["description"].lower()
        assert len(metric_schema["examples"]) > 0
