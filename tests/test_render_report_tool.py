"""Tests for RenderReportTool MCP functionality."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.models import Section
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.exceptions import (
    MCPExecutionError,
    MCPSelectorError,
    MCPValidationError,
)
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
        service = MagicMock(spec=ReportService)
        index_mock = MagicMock()
        index_mock.rebuild_from_filesystem = MagicMock()
        service.index = index_mock
        return service

    @pytest.fixture(autouse=True)
    def selector_mock(self, monkeypatch):
        """Stub ReportSelector to avoid touching the real index."""
        selector = MagicMock()
        selector.resolve.return_value = "resolved-report-id"
        monkeypatch.setattr(
            "igloo_mcp.mcp.tools.render_report.ReportSelector",
            MagicMock(return_value=selector),
        )
        return selector

    @pytest.fixture
    def tool(self, config, mock_report_service):
        """Create a RenderReportTool instance."""
        return RenderReportTool(config, mock_report_service)

    def test_tool_properties(self, tool):
        """Test tool properties."""
        assert tool.name == "render_report"
        assert "Render a living report to human-readable formats" in tool.description
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
        assert examples[1]["description"] == "Generate PDF report with table of contents"
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
            report_id="resolved-report-id",
            format="html",
            options={"toc": True},
            include_preview=True,
            preview_max_chars=2000,
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
            report_id="resolved-report-id",
            format="html",  # default
            options=None,
            include_preview=False,  # default
            preview_max_chars=2000,
            dry_run=False,  # default
        )

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, tool, mock_report_service):
        """Test error handling in execution."""
        mock_report_service.render_report.side_effect = Exception("Test error")

        with pytest.raises(MCPExecutionError) as exc_info:
            await tool.execute(report_selector="Test Report")

        assert "Test error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_quarto_missing_status(self, tool, mock_report_service):
        """Test handling of quarto_missing status from service."""
        mock_report_service.render_report.return_value = {
            "status": "quarto_missing",
            "report_id": "test_id",
            "error": "Quarto not found",
        }

        with pytest.raises(MCPExecutionError) as exc_info:
            await tool.execute(report_selector="Test Report")

        assert "Quarto not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_validation_failed_status(self, tool, mock_report_service):
        """Test handling of validation_failed status from service."""
        mock_report_service.render_report.return_value = {
            "status": "validation_failed",
            "report_id": "test_id",
            "validation_errors": ["Invalid insight reference"],
        }

        with pytest.raises(MCPValidationError) as exc_info:
            await tool.execute(report_selector="Test Report")

        assert "Invalid insight reference" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_render_failed_status(self, tool, mock_report_service):
        """Test handling of render_failed status from service."""
        mock_report_service.render_report.return_value = {
            "status": "render_failed",
            "report_id": "test_id",
            "error": "Quarto subprocess failed",
        }

        with pytest.raises(MCPExecutionError) as exc_info:
            await tool.execute(report_selector="Test Report")

        assert "Quarto subprocess failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_quarto_missing(self, tool, mock_report_service):
        """Test handling of quarto_missing status."""
        mock_report_service.render_report.return_value = {
            "status": "quarto_missing",
            "report_id": "test-report-id",
            "error": "Quarto not found",
        }

        with pytest.raises(MCPExecutionError) as exc_info:
            await tool.execute(report_selector="Test Report")

        assert "Quarto not found" in str(exc_info.value)

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


@pytest.fixture
def report_service(tmp_path):
    """Provide a real ReportService backed by a temp directory."""
    reports_root = tmp_path / "reports"
    reports_root.mkdir(parents=True, exist_ok=True)
    return ReportService(reports_root=reports_root)


@pytest.fixture
def render_tool(report_service):
    """RenderReportTool wired to the real ReportService fixture."""
    config = Config(snowflake=SnowflakeConfig(profile="TEST"))
    return RenderReportTool(config, report_service)


@pytest.mark.asyncio
async def test_render_report_quarto_missing(report_service, render_tool, monkeypatch):
    """Test graceful handling when Quarto is not installed."""
    report_id = report_service.create_report("Test Report")

    # Mock Quarto not found
    def mock_detect():
        from igloo_mcp.living_reports.quarto_renderer import QuartoNotFoundError

        raise QuartoNotFoundError("Quarto not found in PATH")

    monkeypatch.setattr("igloo_mcp.living_reports.quarto_renderer.QuartoRenderer.detect", mock_detect)

    with pytest.raises(MCPExecutionError) as exc_info:
        await render_tool.execute(report_selector=report_id)

    assert "Quarto" in str(exc_info.value)


@pytest.mark.asyncio
async def test_render_report_not_found(render_tool):
    """Test error when report doesn't exist."""
    with pytest.raises(MCPSelectorError) as exc_info:
        await render_tool.execute(report_selector="nonexistent")

    assert "not found" in str(exc_info.value)


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

    with pytest.raises(MCPValidationError) as exc_info:
        await render_tool.execute(report_selector=report_id)

    assert "validation" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_render_dry_run_generates_qmd_only(report_service, render_tool, tmp_path):
    """Test dry_run mode generates QMD without calling Quarto."""
    report_id = report_service.create_report("Test Report")

    result = await render_tool.execute(
        report_selector=report_id,
        dry_run=True,
        include_preview=True,
    )

    # Should succeed even without Quarto
    assert result["status"] == "success"
    assert "dry run" in result.get("warnings", [""])[0].lower()
    output_path = result["output"].get("output_path")
    assert output_path
    assert Path(output_path).exists()
    assert result["output"].get("qmd_path") == output_path
    assert "preview" in result


@pytest.mark.asyncio
async def test_render_report_with_invalid_format(report_service, render_tool):
    """Test error when invalid format is specified."""
    report_id = report_service.create_report("Test Report")

    # This should fail at the service level due to invalid format
    with pytest.raises(MCPValidationError) as exc_info:
        await render_tool.execute(report_selector=report_id, format="invalid_format")

    assert "invalid format" in str(exc_info.value).lower()


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


# =========================================================================
# HTML Standalone Format Tests (Issue #91)
# =========================================================================


@pytest.mark.asyncio
async def test_render_html_standalone_format(report_service, render_tool):
    """Test rendering with html_standalone format - no Quarto required."""
    report_id = report_service.create_report("HTML Standalone Test")

    # Add a section with content
    from igloo_mcp.config import Config, SnowflakeConfig
    from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool

    config = Config(snowflake=SnowflakeConfig(profile="TEST"))
    evolve_tool = EvolveReportTool(config, report_service)

    await evolve_tool.execute(
        report_selector=report_id,
        instruction="Add test section",
        proposed_changes={
            "sections_to_add": [
                {
                    "title": "Test Section",
                    "order": 0,
                    "content": "Test content for standalone HTML.",
                }
            ]
        },
    )

    # Render as html_standalone
    result = await render_tool.execute(
        report_selector=report_id,
        format="html_standalone",
        include_preview=True,
    )

    assert result["status"] == "success"
    assert result["output"]["format"] == "html_standalone"

    # Verify output file exists
    output_path = result["output"].get("output_path")
    assert output_path is not None
    assert Path(output_path).exists()

    # Verify it's a self-contained HTML file
    content = Path(output_path).read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "<style>" in content  # CSS is embedded
    assert "Test Section" in content
    assert "Test content for standalone HTML" in content


@pytest.mark.asyncio
async def test_render_html_standalone_with_theme(report_service, render_tool):
    """Test html_standalone format with theme option."""
    report_id = report_service.create_report("Theme Test")

    result = await render_tool.execute(
        report_selector=report_id,
        format="html_standalone",
        options={"theme": "dark"},
    )

    assert result["status"] == "success"

    # Verify dark theme CSS is applied
    output_path = result["output"].get("output_path")
    content = Path(output_path).read_text(encoding="utf-8")
    assert "--background: #0f172a" in content  # Dark theme background color


@pytest.mark.asyncio
async def test_render_html_standalone_without_toc(report_service, render_tool):
    """Test html_standalone format with TOC disabled."""
    report_id = report_service.create_report("No TOC Test")

    # Add a section first
    from igloo_mcp.config import Config, SnowflakeConfig
    from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool

    config = Config(snowflake=SnowflakeConfig(profile="TEST"))
    evolve_tool = EvolveReportTool(config, report_service)

    await evolve_tool.execute(
        report_selector=report_id,
        instruction="Add section",
        proposed_changes={"sections_to_add": [{"title": "Section 1", "order": 0}]},
    )

    result = await render_tool.execute(
        report_selector=report_id,
        format="html_standalone",
        options={"toc": False},
    )

    assert result["status"] == "success"

    # Verify TOC is not in the output
    output_path = result["output"].get("output_path")
    content = Path(output_path).read_text(encoding="utf-8")
    assert '<nav class="table-of-contents">' not in content


@pytest.mark.asyncio
async def test_render_html_standalone_includes_preview(report_service, render_tool):
    """Test html_standalone format with preview included."""
    report_id = report_service.create_report("Preview Test")

    result = await render_tool.execute(
        report_selector=report_id,
        format="html_standalone",
        include_preview=True,
        preview_max_chars=500,
    )

    assert result["status"] == "success"
    assert "preview" in result
    assert isinstance(result["preview"], str)
    # Preview should be present and include truncation indicator
    assert len(result["preview"]) > 0
    # Should contain truncation message when content exceeds limit
    if len(result["preview"]) > 500:
        assert "[Content truncated]" in result["preview"] or "truncated" in result["preview"].lower()


@pytest.mark.asyncio
async def test_render_html_standalone_no_quarto_required(report_service, render_tool):
    """Verify html_standalone doesn't require Quarto installation."""
    report_id = report_service.create_report("No Quarto Test")

    # This should work even if Quarto is not installed
    result = await render_tool.execute(
        report_selector=report_id,
        format="html_standalone",
    )

    assert result["status"] == "success"
    # The output should be a standalone HTML file, not a Quarto-generated one
    output_path = result["output"].get("output_path")
    assert "report_standalone.html" in output_path


@pytest.mark.asyncio
async def test_render_html_standalone_with_citations(report_service, render_tool):
    """Test html_standalone format includes citations appendix."""
    report_id = report_service.create_report("Citations Test")

    # Add an insight with citation
    from igloo_mcp.config import Config, SnowflakeConfig
    from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool

    config = Config(snowflake=SnowflakeConfig(profile="TEST"))
    evolve_tool = EvolveReportTool(config, report_service)

    await evolve_tool.execute(
        report_selector=report_id,
        instruction="Add insight with citation",
        proposed_changes={
            "sections_to_add": [
                {
                    "title": "Analysis",
                    "order": 0,
                    "insights": [
                        {
                            "summary": "Key finding",
                            "importance": 8,
                            "citations": [{"execution_id": "exec-test-001"}],
                        }
                    ],
                }
            ]
        },
    )

    result = await render_tool.execute(
        report_selector=report_id,
        format="html_standalone",
    )

    assert result["status"] == "success"

    # Verify the output contains the insight
    output_path = result["output"].get("output_path")
    content = Path(output_path).read_text(encoding="utf-8")
    assert "Key finding" in content
