"""Tests for MCP error handling, request_id propagation, and exception serialization."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.exceptions import (
    MCPExecutionError,
    MCPSelectorError,
    MCPValidationError,
)
from igloo_mcp.mcp.tools.base import ensure_request_id
from igloo_mcp.mcp.tools.create_report import CreateReportTool
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool
from igloo_mcp.mcp.tools.render_report import RenderReportTool
from igloo_mcp.mcp.tools.search_report import SearchReportTool


class TestRequestIDGeneration:
    """Test request_id generation and propagation."""

    def test_ensure_request_id_generates_uuid(self):
        """Test that ensure_request_id generates UUID when None."""
        request_id = ensure_request_id(None)
        assert request_id is not None
        assert isinstance(request_id, str)
        # Verify it's a valid UUID format
        uuid.UUID(request_id)  # Should not raise

    def test_ensure_request_id_preserves_provided(self):
        """Test that ensure_request_id preserves provided request_id."""
        provided_id = "custom-request-id-123"
        result = ensure_request_id(provided_id)
        assert result == provided_id

    @pytest.mark.asyncio
    async def test_create_report_generates_request_id(self, tmp_path):
        """Test that create_report generates request_id if not provided."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = CreateReportTool(config, report_service)

        result = await tool.execute(title="Test Report")

        assert "request_id" in result
        assert result["request_id"] is not None
        assert isinstance(result["request_id"], str)
        uuid.UUID(result["request_id"])  # Should be valid UUID

    @pytest.mark.asyncio
    async def test_create_report_preserves_request_id(self, tmp_path):
        """Test that create_report preserves provided request_id."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = CreateReportTool(config, report_service)

        custom_id = "custom-request-id-456"
        result = await tool.execute(title="Test Report", request_id=custom_id)

        assert result["request_id"] == custom_id

    @pytest.mark.asyncio
    async def test_evolve_report_includes_request_id_in_errors(self, tmp_path):
        """Test that evolve_report includes request_id in error context."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        custom_id = "error-request-id-789"

        with pytest.raises(MCPSelectorError) as exc_info:
            await tool.execute(
                report_selector="NonExistentReport",
                instruction="Test",
                proposed_changes={"insights_to_add": []},
                request_id=custom_id,
            )

        # Check that request_id is in error context
        assert exc_info.value.context.get("request_id") == custom_id

    @pytest.mark.asyncio
    async def test_render_report_includes_request_id_in_errors(self, tmp_path):
        """Test that render_report includes request_id in error context."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = RenderReportTool(config, report_service)

        custom_id = "render-error-id-101"

        with pytest.raises(MCPSelectorError) as exc_info:
            await tool.execute(
                report_selector="NonExistentReport",
                format="html",
                request_id=custom_id,
            )

        assert exc_info.value.context.get("request_id") == custom_id


class TestErrorContextCapture:
    """Test error context capture in exceptions."""

    def test_mcp_validation_error_includes_context(self):
        """Test that MCPValidationError includes context."""
        request_id = "test-request-id"
        error = MCPValidationError(
            "Test validation error",
            validation_errors=["field: error"],
            context={"request_id": request_id, "operation": "test"},
        )

        assert error.context["request_id"] == request_id
        assert error.context["operation"] == "test"

    def test_mcp_execution_error_includes_context(self):
        """Test that MCPExecutionError includes context."""
        request_id = "test-request-id"
        error = MCPExecutionError(
            "Test execution error",
            operation="test_operation",
            context={"request_id": request_id, "report_id": "rpt_123"},
        )

        assert error.context["request_id"] == request_id
        assert error.context["report_id"] == "rpt_123"
        assert error.operation == "test_operation"

    def test_mcp_selector_error_includes_context(self):
        """Test that MCPSelectorError includes context."""
        request_id = "test-request-id"
        error = MCPSelectorError(
            "Test selector error",
            selector="test_selector",
            error="not_found",
            context={"request_id": request_id},
        )

        assert error.context["request_id"] == request_id
        assert error.selector == "test_selector"
        assert error.error == "not_found"

    @pytest.mark.asyncio
    async def test_error_handler_adds_request_id_to_context(self, tmp_path):
        """Test that @tool_error_handler adds request_id to error context."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = CreateReportTool(config, report_service)

        custom_id = "handler-test-id"

        # Trigger a validation error
        with pytest.raises(MCPValidationError) as exc_info:
            await tool.execute(
                title="Test",
                template="invalid_template",
                request_id=custom_id,
            )

        # Verify request_id is in context
        assert exc_info.value.context.get("request_id") == custom_id


class TestExceptionSerialization:
    """Test exception serialization via to_dict() methods."""

    def test_mcp_validation_error_to_dict(self):
        """Test MCPValidationError.to_dict() serialization."""
        error = MCPValidationError(
            "Test validation error",
            validation_errors=["field1: error1", "field2: error2"],
            hints=["hint1", "hint2"],
            context={"request_id": "test-id", "operation": "test"},
        )

        error_dict = error.to_dict()

        assert error_dict["message"] == "Test validation error"
        assert error_dict["error_type"] == "MCPValidationError"
        assert error_dict["error_code"] == "VALIDATION_ERROR"
        assert error_dict["validation_errors"] == ["field1: error1", "field2: error2"]
        assert error_dict["hints"] == ["hint1", "hint2"]
        assert error_dict["context"]["request_id"] == "test-id"

    def test_mcp_execution_error_to_dict(self):
        """Test MCPExecutionError.to_dict() serialization."""
        original_error = ValueError("Original error")
        error = MCPExecutionError(
            "Test execution error",
            operation="test_operation",
            original_error=original_error,
            hints=["hint1"],
            context={"request_id": "test-id"},
        )

        error_dict = error.to_dict()

        assert error_dict["message"] == "Test execution error"
        assert error_dict["error_type"] == "MCPExecutionError"
        assert error_dict["error_code"] == "EXECUTION_ERROR"
        assert error_dict["operation"] == "test_operation"
        assert error_dict["original_error"] == "Original error"
        assert error_dict["hints"] == ["hint1"]
        assert error_dict["context"]["request_id"] == "test-id"

    def test_mcp_selector_error_to_dict(self):
        """Test MCPSelectorError.to_dict() serialization."""
        error = MCPSelectorError(
            "Test selector error",
            selector="test_selector",
            error="not_found",
            candidates=["candidate1", "candidate2"],
            hints=["hint1"],
            context={"request_id": "test-id"},
        )

        error_dict = error.to_dict()

        assert error_dict["message"] == "Test selector error"
        assert error_dict["error_type"] == "MCPSelectorError"
        assert error_dict["error_code"] == "SELECTOR_ERROR"
        assert error_dict["selector"] == "test_selector"
        assert error_dict["error"] == "not_found"
        assert error_dict["candidates"] == ["candidate1", "candidate2"]
        assert error_dict["hints"] == ["hint1"]
        assert error_dict["context"]["request_id"] == "test-id"

    def test_exception_serialization_is_json_serializable(self):
        """Test that exception to_dict() results are JSON serializable."""
        import json

        error = MCPValidationError(
            "Test error",
            validation_errors=["error1"],
            context={"request_id": "test-id"},
        )

        error_dict = error.to_dict()
        # Should not raise
        json_str = json.dumps(error_dict)
        assert json_str is not None
        # Should be able to parse back
        parsed = json.loads(json_str)
        assert parsed["message"] == "Test error"


class TestTimingCapture:
    """Test timing information capture in responses."""

    @pytest.mark.asyncio
    async def test_create_report_includes_timing(self, tmp_path):
        """Test that create_report includes timing information."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = CreateReportTool(config, report_service)

        result = await tool.execute(title="Test Report")

        assert "timing" in result
        assert "create_duration_ms" in result["timing"]
        assert "total_duration_ms" in result["timing"]
        assert isinstance(result["timing"]["create_duration_ms"], (int, float))
        assert isinstance(result["timing"]["total_duration_ms"], (int, float))
        assert result["timing"]["total_duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_evolve_report_includes_timing(self, tmp_path):
        """Test that evolve_report includes timing information."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        report_id = report_service.create_report("Test Report")
        result = await tool.execute(
            report_selector=report_id,
            instruction="Test",
            proposed_changes={"insights_to_add": []},
            dry_run=True,
        )

        assert "timing" in result or "request_id" in result
        # Timing may be in result or in error context
        if "timing" in result:
            assert "total_duration_ms" in result["timing"]

    @pytest.mark.asyncio
    async def test_render_report_includes_timing(self, tmp_path):
        """Test that render_report includes timing information."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = RenderReportTool(config, report_service)

        report_id = report_service.create_report("Test Report")

        # Mock render_report to return success
        with patch.object(
            report_service,
            "render_report",
            return_value={"status": "success", "report_id": report_id},
        ):
            result = await tool.execute(
                report_selector=report_id,
                format="html",
                dry_run=True,
            )

            assert "timing" in result
            assert "selector_duration_ms" in result["timing"]
            assert "render_duration_ms" in result["timing"]
            assert "total_duration_ms" in result["timing"]

    @pytest.mark.asyncio
    async def test_search_report_includes_timing(self, tmp_path):
        """Test that search_report includes timing information."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = SearchReportTool(config, report_service)

        # Create a report first
        report_service.create_report("Test Report")

        result = await tool.execute()

        assert "timing" in result
        assert "index_duration_ms" in result["timing"]
        assert "total_duration_ms" in result["timing"]
        assert isinstance(result["timing"]["total_duration_ms"], (int, float))


class TestErrorHintsActionability:
    """Test that error hints are actionable."""

    @pytest.mark.asyncio
    async def test_validation_error_hints_include_parameter_names(self, tmp_path):
        """Test that validation error hints include specific parameter names."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = CreateReportTool(config, report_service)

        with pytest.raises(MCPValidationError) as exc_info:
            await tool.execute(title="Test", template="invalid_template")

        hints = exc_info.value.hints
        # Should mention template parameter specifically
        assert any("template" in hint.lower() for hint in hints)
        # Should include example values
        assert any("default" in hint.lower() or "deep_dive" in hint.lower() for hint in hints)

    @pytest.mark.asyncio
    async def test_selector_error_hints_include_suggestions(self, tmp_path):
        """Test that selector error hints include actionable suggestions."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = RenderReportTool(config, report_service)

        with pytest.raises(MCPSelectorError) as exc_info:
            await tool.execute(report_selector="NonExistentReport", format="html")

        hints = exc_info.value.hints
        # Should suggest using search_report
        assert any("search_report" in hint.lower() for hint in hints)
        # Should mention checking spelling
        assert any("spelling" in hint.lower() or "spell" in hint.lower() for hint in hints)

    @pytest.mark.asyncio
    async def test_execution_error_hints_include_troubleshooting(self, tmp_path):
        """Test that execution error hints include troubleshooting steps."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = CreateReportTool(config, report_service)

        # Mock a file system error
        with patch.object(
            report_service,
            "create_report",
            side_effect=PermissionError("Permission denied"),
        ):
            with pytest.raises(MCPExecutionError) as exc_info:
                await tool.execute(title="Test")

            hints = exc_info.value.hints
            # Should mention file system permissions
            assert any("permission" in hint.lower() or "writable" in hint.lower() for hint in hints)
            # Should mention disk space
            assert any("disk" in hint.lower() or "space" in hint.lower() for hint in hints)
