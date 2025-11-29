"""Regression tests for section prose content feature (v0.3.2).

Sections now support optional prose content fields:
- content: str (markdown, html, or plain text)
- content_format: Literal["markdown", "html", "plain"] (default: "markdown")

This is a minimum viable test suite covering the critical functionality.
"""

from pathlib import Path

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool
from igloo_mcp.mcp.tools.render_report import RenderReportTool


class TestSectionProseContentSmoke:
    """Smoke tests for section prose content (minimum viable coverage)."""

    @pytest.mark.asyncio
    async def test_add_section_with_markdown_content(self, tmp_path: Path):
        """Smoke test: section can have markdown prose content."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        report_id = report_service.create_report(title="Prose Content Test", template="default")

        tool = EvolveReportTool(config, report_service)

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add section with prose content",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Executive Summary",
                        "order": 1,
                        "content": "## Key Findings\n\n- Revenue up 25%\n- Costs stable",
                        "content_format": "markdown",
                    }
                ]
            },
        )

        assert result["status"] == "success"
        assert result["summary"]["sections_added"] == 1

        # Verify content persisted
        outline = report_service.get_report_outline(report_id)
        section = outline.sections[0]
        assert section.content == "## Key Findings\n\n- Revenue up 25%\n- Costs stable"
        assert section.content_format == "markdown"

    @pytest.mark.asyncio
    async def test_content_format_defaults_to_markdown(self, tmp_path: Path):
        """Test that content_format defaults to 'markdown' when not specified."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        report_id = report_service.create_report(title="Test", template="default")
        tool = EvolveReportTool(config, report_service)

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add section with content but no format",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Summary",
                        "order": 1,
                        "content": "Plain text content",
                        # No content_format specified
                    }
                ]
            },
        )

        assert result["status"] == "success"

        outline = report_service.get_report_outline(report_id)
        section = outline.sections[0]
        assert section.content == "Plain text content"
        assert section.content_format == "markdown"  # Should default

    @pytest.mark.asyncio
    async def test_modify_section_prose_content(self, tmp_path: Path):
        """Test modifying existing section's prose content."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        report_id = report_service.create_report(title="Test", template="default")
        tool = EvolveReportTool(config, report_service)

        # Add section with initial content
        result1 = await tool.execute(
            report_selector=report_id,
            instruction="Add section",
            proposed_changes={"sections_to_add": [{"title": "Summary", "order": 1, "content": "Initial content"}]},
        )
        section_id = result1["summary"]["section_ids_added"][0]

        # Modify content
        result2 = await tool.execute(
            report_selector=report_id,
            instruction="Update content",
            proposed_changes={
                "sections_to_modify": [
                    {
                        "section_id": section_id,
                        "content": "Updated content with **bold** text",
                    }
                ]
            },
        )

        assert result2["status"] == "success"

        outline = report_service.get_report_outline(report_id)
        section = outline.sections[0]
        assert section.content == "Updated content with **bold** text"

    @pytest.mark.asyncio
    async def test_html_and_plain_content_formats(self, tmp_path: Path):
        """Test that html and plain content formats are supported."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        report_id = report_service.create_report(title="Test", template="default")
        tool = EvolveReportTool(config, report_service)

        # Add HTML section
        result1 = await tool.execute(
            report_selector=report_id,
            instruction="Add HTML section",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "HTML Summary",
                        "order": 1,
                        "content": "<h2>Findings</h2><p>Revenue <strong>increased</strong></p>",
                        "content_format": "html",
                    }
                ]
            },
        )

        assert result1["status"] == "success"

        # Add plain text section
        result2 = await tool.execute(
            report_selector=report_id,
            instruction="Add plain text section",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Plain Summary",
                        "order": 2,
                        "content": "Just plain text, no formatting",
                        "content_format": "plain",
                    }
                ]
            },
        )

        assert result2["status"] == "success"

        outline = report_service.get_report_outline(report_id)
        assert outline.sections[0].content_format == "html"
        assert outline.sections[1].content_format == "plain"

    @pytest.mark.asyncio
    async def test_prose_content_in_render_output(self, tmp_path: Path):
        """Smoke test: prose content appears in rendered output."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        # Create report with prose content
        report_id = report_service.create_report(title="Test", template="default")

        evolve_tool = EvolveReportTool(config, report_service)
        await evolve_tool.execute(
            report_selector=report_id,
            instruction="Add section with prose",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Executive Summary",
                        "order": 1,
                        "content": "## Q4 Performance\n\nRevenue exceeded targets by **15%**.",
                    }
                ]
            },
        )

        # Render and check QMD contains prose
        render_tool = RenderReportTool(config, report_service)
        result = await render_tool.execute(report_selector=report_id, format="html", dry_run=True, include_preview=True)

        assert result["status"] == "success"
        assert "preview" in result

        # Preview should contain the prose content
        preview = result["preview"]
        assert "Q4 Performance" in preview
        assert "Revenue exceeded targets" in preview
