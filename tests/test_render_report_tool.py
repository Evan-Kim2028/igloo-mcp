"""Tests for RenderReportTool MCP functionality."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.models import Section
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.render_report import RenderReportTool


class TestRenderReportTool:
    """Test RenderReportTool class."""

    @pytest.fixture
    def config(self):
        """Create a test config."""
        return Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))

    @pytest.fixture
    def mock_report_service(self):
        """Create a mock ReportService."""
        return MagicMock(spec=ReportService)

    @pytest.fixture
    def tool(self, config, mock_report_service):
        """Create a RenderReportTool instance."""
        return RenderReportTool(config, mock_report_service)

    def test_tool_properties(self, tool):
        """Test tool properties."""
        assert tool.name == "render_report"
        assert (
            tool.description
            == "Render a living report to human-readable formats (HTML, PDF, etc.) using Quarto"
        )
        assert tool.category == "reports"
        assert "rendering" in tool.tags
        assert "quarto" in tool.tags

    def test_usage_examples(self, tool):
        """Test usage examples."""
        examples = tool.usage_examples
        assert len(examples) == 3

        # First example - HTML render
        assert examples[0]["description"] == "Render quarterly sales report to HTML"
        assert examples[0]["parameters"]["report_selector"] == "Q1 Sales Report"
        assert examples[0]["parameters"]["format"] == "html"
        assert examples[0]["parameters"]["include_preview"] is True

        # Second example - PDF with options
        assert (
            examples[1]["description"] == "Generate PDF report with table of contents"
        )
        assert examples[1]["parameters"]["format"] == "pdf"
        assert "toc" in examples[1]["parameters"]["options"]

    @pytest.mark.asyncio
    async def test_execute_success(self, tool, mock_report_service):
        """Test successful execution."""
        mock_report_service.render_report.return_value = {
            "status": "success",
            "report_id": "test-report-id",
            "output": {
                "format": "html",
                "output_path": "/path/to/report.html",
                "assets_dir": "/path/to/_files",
            },
            "warnings": ["Minor warning"],
            "audit_action_id": "audit-123",
        }

        result = await tool.execute(
            report_selector="Test Report",
            format="html",
            include_preview=True,
            options={"toc": True},
        )

        assert result["status"] == "success"
        assert result["report_id"] == "test-report-id"
        assert result["output"]["format"] == "html"
        assert result["warnings"] == ["Minor warning"]

        mock_report_service.render_report.assert_called_once_with(
            report_id="Test Report",
            format="html",
            options={"toc": True},
            include_preview=True,
            dry_run=False,
        )

    @pytest.mark.asyncio
    async def test_execute_with_defaults(self, tool, mock_report_service):
        """Test execution with default parameters."""
        mock_report_service.render_report.return_value = {
            "status": "success",
            "report_id": "test-report-id",
        }

        result = await tool.execute(report_selector="Test Report")

        assert result["status"] == "success"

        mock_report_service.render_report.assert_called_once_with(
            report_id="Test Report",
            format="html",  # default
            options=None,
            include_preview=False,  # default
            dry_run=False,  # default
        )

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, tool, mock_report_service):
        """Test error handling in execution."""
        mock_report_service.render_report.side_effect = Exception("Test error")

        result = await tool.execute(report_selector="Test Report")

        assert result["status"] == "error"
        assert "Test error" in result["error"]
        assert result["report_selector"] == "Test Report"

    @pytest.mark.asyncio
    async def test_execute_quarto_missing_status(self, tool, mock_report_service):
        """Test handling of quarto_missing status from service."""
        mock_report_service.render_report.return_value = {
            "status": "quarto_missing",
            "report_id": "test_id",
            "error": "Quarto not found",
        }

        result = await tool.execute(report_selector="Test Report")

        assert result["status"] == "quarto_missing"
        assert result["report_id"] == "test_id"
        assert "Quarto not found" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_validation_failed_status(self, tool, mock_report_service):
        """Test handling of validation_failed status from service."""
        mock_report_service.render_report.return_value = {
            "status": "validation_failed",
            "report_id": "test_id",
            "validation_errors": ["Invalid insight reference"],
        }

        result = await tool.execute(report_selector="Test Report")

        assert result["status"] == "validation_failed"
        assert result["report_id"] == "test_id"
        assert result["validation_errors"] == ["Invalid insight reference"]

    @pytest.mark.asyncio
    async def test_execute_render_failed_status(self, tool, mock_report_service):
        """Test handling of render_failed status from service."""
        mock_report_service.render_report.return_value = {
            "status": "render_failed",
            "report_id": "test_id",
            "error": "Quarto subprocess failed",
        }

        result = await tool.execute(report_selector="Test Report")

        assert result["status"] == "render_failed"
        assert result["report_id"] == "test_id"
        assert "Quarto subprocess failed" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_quarto_missing(self, tool, mock_report_service):
        """Test handling of quarto_missing status."""
        mock_report_service.render_report.return_value = {
            "status": "quarto_missing",
            "report_id": "test-report-id",
            "error": "Quarto not found",
        }

        result = await tool.execute(report_selector="Test Report")

        assert result["status"] == "quarto_missing"
        assert result["report_id"] == "test-report-id"
        assert "Quarto not found" in result["error"]

    def test_parameter_schema(self, tool):
        """Test parameter schema structure."""
        schema = tool.get_parameter_schema()

        assert schema["title"] == "Render Report Parameters"
        assert "report_selector" in schema["required"]
        assert "report_selector" in schema["properties"]
        assert "format" in schema["properties"]
        assert "options" in schema["properties"]

        # Test format enum
        format_prop = schema["properties"]["format"]
        assert "enum" in format_prop
        assert "html" in format_prop["enum"]
        assert "pdf" in format_prop["enum"]
        assert "markdown" in format_prop["enum"]
        assert "docx" in format_prop["enum"]

        # Test options structure
        options_prop = schema["properties"]["options"]
        assert "properties" in options_prop
        assert "toc" in options_prop["properties"]
        assert "code_folding" in options_prop["properties"]
        assert "theme" in options_prop["properties"]

    def test_parameter_schema_validation(self, tool):
        """Test parameter schema validation rules."""
        schema = tool.get_parameter_schema()

        # Required parameters
        required = schema["required"]
        assert "report_selector" in required
        assert len(required) == 1  # Only report_selector is required

        # Additional properties should be forbidden
        assert schema["additionalProperties"] is False

        # Test parameter constraints
        props = schema["properties"]

        # report_selector
        assert props["report_selector"]["type"] == "string"
        assert "examples" in props["report_selector"]

        # format
        assert props["format"]["default"] == "html"
        assert props["format"]["type"] == "string"

        # regenerate_outline_view
        assert props["regenerate_outline_view"]["type"] == "boolean"
        assert props["regenerate_outline_view"]["default"] is True

        # include_preview
        assert props["include_preview"]["type"] == "boolean"
        assert props["include_preview"]["default"] is False

        # options
        assert props["options"]["type"] == "object"
        assert "additionalProperties" in props["options"]


@pytest.mark.asyncio
async def test_render_report_quarto_missing(report_service, render_tool, monkeypatch):
    """Test graceful handling when Quarto is not installed."""
    report_id = report_service.create_report("Test Report")

    # Mock Quarto not found
    def mock_detect():
        from igloo_mcp.living_reports.quarto_renderer import QuartoNotFoundError

        raise QuartoNotFoundError("Quarto not found in PATH")

    monkeypatch.setattr(
        "igloo_mcp.living_reports.quarto_renderer.QuartoRenderer.detect", mock_detect
    )

    result = await render_tool.execute(report_selector=report_id)

    assert result["status"] == "quarto_missing"
    assert "Quarto" in result["error"]
    assert "report_id" in result


@pytest.mark.asyncio
async def test_render_report_not_found(render_tool):
    """Test error when report doesn't exist."""
    result = await render_tool.execute(report_selector="nonexistent")

    assert result["status"] == "validation_failed"
    assert "not found" in str(result.get("validation_errors", ""))


@pytest.mark.asyncio
async def test_render_report_validation_failed(report_service, render_tool):
    """Test error when report has validation issues."""
    report_id = report_service.create_report("Test Report")

    # Create invalid state: section references non-existent insight
    outline = report_service.get_report_outline(report_id)
    outline.sections.append(
        Section(
            section_id=str(uuid.uuid4()),
            title="Bad Section",
            order=0,
            insight_ids=["nonexistent_insight_id"],
        )
    )
    report_service.update_report_outline(report_id, outline)

    result = await render_tool.execute(report_selector=report_id)

    assert result["status"] == "validation_failed"
    assert len(result["validation_errors"]) > 0


@pytest.mark.asyncio
async def test_render_dry_run_generates_qmd_only(report_service, render_tool, tmp_path):
    """Test dry_run mode generates QMD without calling Quarto."""
    report_id = report_service.create_report("Test Report")

    result = await render_tool.execute(
        report_selector=report_id,
        dry_run=True,
    )

    # Should succeed even without Quarto
    assert result["status"] == "success"
    assert "dry run" in result.get("warnings", [""])[0].lower()


@pytest.mark.asyncio
async def test_render_report_with_invalid_format(report_service, render_tool):
    """Test error when invalid format is specified."""
    report_id = report_service.create_report("Test Report")

    # This should fail at the service level due to invalid format
    result = await render_tool.execute(
        report_selector=report_id, format="invalid_format"
    )

    # The tool passes through service errors
    assert result["status"] in ("error", "render_failed")


@pytest.mark.asyncio
async def test_render_report_open_browser_flag(
    report_service, render_tool, monkeypatch
):
    """Test that open_browser flag is passed through."""
    report_id = report_service.create_report("Test Report")

    # Mock successful render
    mock_result = {
        "status": "success",
        "report_id": report_id,
        "output": {"format": "html", "output_path": "/tmp/test.html"},
        "warnings": [],
        "audit_action_id": "test-audit",
    }

    report_service.render_report = AsyncMock(return_value=mock_result)

    result = await render_tool.execute(
        report_selector=report_id, format="html", open_browser=True
    )

    # Verify the call included open_browser
    call_args = report_service.render_report.call_args
    assert call_args.kwargs.get("open_browser") is True


def test_render_tool_schema_completeness():
    """Test that parameter schema includes all expected parameters."""
    config = Config(snowflake=SnowflakeConfig(profile="TEST"))
    mock_service = MagicMock()
    tool = RenderReportTool(config, mock_service)

    schema = tool.get_parameter_schema()
    props = schema["properties"]

    # Check all expected parameters are present
    expected_params = [
        "report_selector",
        "format",
        "regenerate_outline_view",
        "include_preview",
        "dry_run",
        "options",
    ]

    for param in expected_params:
        assert param in props, f"Missing parameter: {param}"

    # Check parameter types
    assert props["report_selector"]["type"] == "string"
    assert props["format"]["type"] == "string"
    assert props["regenerate_outline_view"]["type"] == "boolean"
    assert props["include_preview"]["type"] == "boolean"
    assert props["dry_run"]["type"] == "boolean"
    assert props["options"]["type"] == "object"
