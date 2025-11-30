"""Snapshot tests for MCP tool response schemas using inline-snapshot.

These tests ensure that tool response structures remain stable and don't
change unexpectedly, which would break client integrations.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from inline_snapshot import snapshot

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.create_report import CreateReportTool
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.service_layer.query_service import QueryService


class TestExecuteQueryResponseSchema:
    """Snapshot tests for execute_query tool response structure."""

    @pytest.mark.asyncio
    async def test_success_response_keys(self, tmp_path, monkeypatch):
        """Verify execute_query success response has stable schema."""
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        config = Config.from_env()
        snowflake_service = Mock()
        query_service = Mock(spec=QueryService)

        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=snowflake_service,
            query_service=query_service,
            health_monitor=None,
        )

        # Mock the sync execution
        tool._execute_query_sync = Mock(
            return_value={
                "statement": "SELECT 1",
                "rowcount": 1,
                "rows": [[1]],
                "duration_ms": 10,
            }
        )

        result = await tool.execute(
            statement="SELECT 1",
            reason="Snapshot test",
            response_mode="full",
        )

        # Verify response schema stability
        assert set(result.keys()) == snapshot(
            {
                "audit_info",
                "cache",
                "duration_ms",
                "insights",
                "key_metrics",
                "rowcount",
                "rows",
                "session_context",
                "statement",
            }
        )

        # Verify nested structures
        assert set(result["cache"].keys()) == snapshot({"cache_key", "hit"})

        assert set(result["audit_info"].keys()) == snapshot(
            {
                "artifact_root",
                "artifacts",
                "cache",
                "cache_hit",
                "execution_id",
                "history_enabled",
                "history_path",
                "session_context",
                "sql_sha256",
            }
        )

    @pytest.mark.asyncio
    async def test_cache_metadata_structure(self, tmp_path, monkeypatch):
        """Verify cache-related metadata has stable structure."""
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        config = Config.from_env()
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=Mock(),
            query_service=Mock(spec=QueryService),
            health_monitor=None,
        )

        tool._execute_query_sync = Mock(
            return_value={
                "statement": "SELECT 1",
                "rowcount": 1,
                "rows": [[1]],
                "duration_ms": 10,
            }
        )

        result = await tool.execute(
            statement="SELECT 1",
            reason="Cache test",
        )

        # Cache info should always have these fields
        cache_info = result["cache"]
        assert "hit" in cache_info
        assert isinstance(cache_info["hit"], bool)


class TestCreateReportResponseSchema:
    """Snapshot tests for create_report tool response structure."""

    @pytest.mark.asyncio
    async def test_create_report_success_schema(self, tmp_path):
        """Verify create_report success response has stable schema."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = CreateReportTool(config, report_service)

        result = await tool.execute(title="Test Report")

        # Verify response schema
        assert set(result.keys()) == snapshot(
            {
                "insight_ids_added",
                "message",
                "report_id",
                "request_id",
                "section_ids_added",
                "status",
                "tags",
                "template",
                "timing",
                "title",
            }
        )

        assert result["status"] == "success"
        assert isinstance(result["report_id"], str)
        assert isinstance(result["title"], str)

    @pytest.mark.asyncio
    async def test_create_report_with_template_schema(self, tmp_path):
        """Verify response schema when creating report with template."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = CreateReportTool(config, report_service)

        result = await tool.execute(
            title="Analyst Report",
            template="analyst_v1",
        )

        # Schema should be same regardless of template
        assert set(result.keys()) == snapshot(
            {
                "insight_ids_added",
                "message",
                "report_id",
                "request_id",
                "section_ids_added",
                "status",
                "tags",
                "template",
                "timing",
                "title",
            }
        )


class TestErrorResponseSchema:
    """Snapshot tests for error response structures."""

    def test_validation_error_structure(self):
        """Verify validation error response has stable structure."""
        from igloo_mcp.mcp.exceptions import MCPValidationError

        error = MCPValidationError(
            "Test validation error",
            validation_errors=["field1: error1", "field2: error2"],
            context={"request_id": "test-123"},
        )

        error_dict = error.to_dict()

        # Verify error response structure
        assert set(error_dict.keys()) == snapshot(
            {"context", "error_code", "error_type", "message", "validation_errors"}
        )

        assert error_dict["error_type"] == "MCPValidationError"
        assert isinstance(error_dict["validation_errors"], list)

    def test_execution_error_structure(self):
        """Verify execution error response has stable structure."""
        from igloo_mcp.mcp.exceptions import MCPExecutionError

        error = MCPExecutionError(
            "Test execution error",
            operation="test_op",
            context={"request_id": "test-456", "detail": "error detail"},
        )

        error_dict = error.to_dict()

        assert set(error_dict.keys()) == snapshot({"context", "error_code", "error_type", "message", "operation"})

        assert error_dict["error_type"] == "MCPExecutionError"
        assert error_dict["operation"] == "test_op"


class TestKeyMetricsSchema:
    """Snapshot tests for key_metrics structure in query results."""

    @pytest.mark.asyncio
    async def test_key_metrics_structure(self, monkeypatch):
        """Verify key_metrics has stable structure."""
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        config = Config.from_env()
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=Mock(),
            query_service=Mock(spec=QueryService),
            health_monitor=None,
        )

        # Mock with structured data
        tool._execute_query_sync = Mock(
            return_value={
                "statement": "SELECT amount FROM sales",
                "rowcount": 3,
                "rows": [
                    {"amount": 100},
                    {"amount": 200},
                    {"amount": 150},
                ],
                "duration_ms": 50,
            }
        )

        result = await tool.execute(
            statement="SELECT amount FROM sales",
            reason="Metrics test",
        )

        # Verify key_metrics structure
        metrics = result.get("key_metrics")
        assert metrics is not None
        assert set(metrics.keys()) == snapshot(
            {"columns", "num_columns", "sampled_rows", "total_rows", "truncated_output"}
        )

        # Verify column metadata structure
        if metrics["columns"]:
            first_col = metrics["columns"][0]
            assert set(first_col.keys()) == snapshot({"avg", "kind", "max", "min", "name", "non_null_ratio"})


class TestPostQueryInsightSchema:
    """Snapshot tests for post_query_insight structure."""

    def test_structured_insight_format(self):
        """Verify structured post_query_insight has stable schema."""
        # PostQueryInsight class was removed - skip this test
        pytest.skip("PostQueryInsight class no longer exists")

        insight_dict = {}

        # Verify structure
        assert set(insight_dict.keys()) == snapshot(
            {
                "summary",
                "key_metrics",
                "business_impact",
                "follow_up_needed",
            }
        )

        assert isinstance(insight_dict["key_metrics"], list)
        assert isinstance(insight_dict["follow_up_needed"], bool)
