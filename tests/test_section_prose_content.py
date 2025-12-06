"""Regression tests for section prose content feature (v0.3.2).

Sections now support optional prose content fields:
- content: str (markdown, html, or plain text)
- content_format: Literal["markdown", "html", "plain"] (default: "markdown")

This is a minimum viable test suite covering the critical functionality.
"""

import datetime as dt
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
    async def test_setting_content_clears_notes(self, tmp_path: Path):
        """Setting formatted content should drop legacy notes field automatically."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        report_id = report_service.create_report(title="Notes Cleanup", template="default")
        tool = EvolveReportTool(config, report_service)

        add_result = await tool.execute(
            report_selector=report_id,
            instruction="Seed notes",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Overview",
                        "order": 1,
                        "notes": "Raw scratch notes",
                    }
                ]
            },
        )
        section_id = add_result["summary"]["section_ids_added"][0]

        outline = report_service.get_report_outline(report_id)
        assert outline.sections[0].notes == "Raw scratch notes"
        assert outline.sections[0].content is None

        await tool.execute(
            report_selector=report_id,
            instruction="Promote to content",
            proposed_changes={
                "sections_to_modify": [
                    {
                        "section_id": section_id,
                        "content": "## Clean Content\n\nUp-leveled summary.",
                    }
                ]
            },
        )

        updated_outline = report_service.get_report_outline(report_id)
        section = updated_outline.sections[0]
        assert section.content == "## Clean Content\n\nUp-leveled summary."
        assert section.notes is None

    @pytest.mark.asyncio
    async def test_section_and_insight_timestamps_update_on_changes(self, tmp_path: Path):
        """Sections and insights should track created/updated timestamps."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        report_id = report_service.create_report(title="Timestamp Test", template="default")
        tool = EvolveReportTool(config, report_service)

        add_result = await tool.execute(
            report_selector=report_id,
            instruction="Add section and inline insight",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Exec Summary",
                        "order": 1,
                        "content": "Initial content",
                        "insights": [
                            {
                                "summary": "Finding",
                                "importance": 7,
                                "citations": [
                                    {
                                        "source": "query",
                                        "execution_id": "exec-ts-1",
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
        )

        assert add_result["status"] == "success"
        outline = report_service.get_report_outline(report_id)
        section = outline.sections[0]
        insight = outline.get_insight(outline.sections[0].insight_ids[0])

        section_created = dt.datetime.fromisoformat(section.created_at)
        section_updated = dt.datetime.fromisoformat(section.updated_at)
        insight_created = dt.datetime.fromisoformat(insight.created_at)
        insight_updated = dt.datetime.fromisoformat(insight.updated_at)

        assert section_updated >= section_created
        assert insight_updated >= insight_created

        modify_result = await tool.execute(
            report_selector=report_id,
            instruction="Update section and insight",
            proposed_changes={
                "sections_to_modify": [
                    {
                        "section_id": section.section_id,
                        "content": "Updated content",
                    }
                ],
                "insights_to_modify": [
                    {
                        "insight_id": insight.insight_id,
                        "importance": 9,
                    }
                ],
            },
        )

        assert modify_result["status"] == "success"
        updated_outline = report_service.get_report_outline(report_id)
        updated_section = updated_outline.sections[0]
        updated_insight = updated_outline.get_insight(insight.insight_id)

        assert updated_section.created_at == section.created_at
        assert dt.datetime.fromisoformat(updated_section.updated_at) > section_updated

        assert updated_insight.created_at == insight.created_at
        assert dt.datetime.fromisoformat(updated_insight.updated_at) > insight_updated

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

    @pytest.mark.asyncio
    async def test_notes_only_sections_render_in_html(self, tmp_path: Path):
        """Notes-only sections should still appear when rendering via Quarto dry run."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        report_id = report_service.create_report(title="Notes Render", template="default")
        evolve_tool = EvolveReportTool(config, report_service)
        await evolve_tool.execute(
            report_selector=report_id,
            instruction="Add notes",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Scratch",
                        "order": 1,
                        "notes": "Temporary finding awaiting formatting.",
                    }
                ]
            },
        )

        render_tool = RenderReportTool(config, report_service)
        result = await render_tool.execute(report_selector=report_id, format="html", dry_run=True, include_preview=True)

        assert result["status"] == "success"
        assert "Temporary finding awaiting formatting." in result["preview"]

    @pytest.mark.asyncio
    async def test_section_template_generation_and_feedback(self, tmp_path: Path):
        """Sections can be generated from markdown templates with clean formatting."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        report_id = report_service.create_report(title="Templates", template="default")
        tool = EvolveReportTool(config, report_service)

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add templated findings",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "North Star",
                        "order": 1,
                        "template": "findings_list",
                        "template_data": {
                            "heading": "North Star Metrics",
                            "findings": [
                                {
                                    "title": "Activation climbed",
                                    "metric": {"name": "Activation", "value": "62%", "trend": "+4 pp"},
                                    "description": "Week-over-week activation improved on the new onboarding path.",
                                }
                            ],
                        },
                    }
                ]
            },
        )

        assert result["status"] == "success"
        assert result["summary"]["sections_added"] == 1
        feedback = result["formatting_feedback"]
        assert feedback["score"] == 100

        outline = report_service.get_report_outline(report_id)
        section = outline.sections[0]
        assert "## North Star Metrics" in section.content
        assert "### 1. Activation climbed" in section.content

    @pytest.mark.asyncio
    async def test_formatting_feedback_detects_wall_of_text(self, tmp_path: Path):
        """Dense unstructured prose should surface formatting warnings."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        report_id = report_service.create_report(title="Formatting", template="default")
        tool = EvolveReportTool(config, report_service)

        long_paragraph = (
            "This is a very long paragraph without any markdown structure that keeps going and going to simulate a "
            "wall of text focused on burying the reader in detail without providing headings or bullet lists. "
        ) * 20

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add messy prose",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Dense Notes",
                        "order": 1,
                        "content": long_paragraph,
                    }
                ]
            },
        )

        assert result["status"] == "success"
        feedback = result["formatting_feedback"]
        assert feedback["score"] < 100
        assert any("very long paragraphs" in warning for warning in feedback["warnings"])
        assert feedback["section_feedback"], "Section-specific feedback should be populated"

    @pytest.mark.asyncio
    async def test_executive_summary_template(self, tmp_path: Path):
        """Executive summary template should generate structured content."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        report_id = report_service.create_report(title="Exec Summary", template="default")
        tool = EvolveReportTool(config, report_service)

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add executive summary",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Executive Summary",
                        "order": 1,
                        "template": "executive_summary",
                        "template_data": {
                            "headline": "Q4 Performance Summary",
                            "context": "This quarter saw significant growth across all business units.",
                            "key_points": [
                                {"title": "Revenue Growth", "detail": "Up 25% YoY"},
                                {"title": "Customer Retention", "detail": "Improved to 95%"},
                                "Expanded into 3 new markets",
                            ],
                            "recommendation": "Continue investment in customer success initiatives.",
                            "conclusion": "Overall, Q4 exceeded expectations.",
                        },
                    }
                ]
            },
        )

        assert result["status"] == "success"
        outline = report_service.get_report_outline(report_id)
        section = outline.sections[0]

        assert "## Q4 Performance Summary" in section.content
        assert "### Key Takeaways" in section.content
        assert "**Revenue Growth**" in section.content
        assert "### Recommendation" in section.content
        assert "> Continue investment" in section.content

    @pytest.mark.asyncio
    async def test_action_items_template_with_table(self, tmp_path: Path):
        """Action items template with owner/due data should render as table."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        report_id = report_service.create_report(title="Action Items", template="default")
        tool = EvolveReportTool(config, report_service)

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add action items",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Next Steps",
                        "order": 1,
                        "template": "action_items",
                        "template_data": {
                            "heading": "Follow-up Actions",
                            "actions": [
                                {
                                    "description": "Review Q4 metrics",
                                    "owner": "Alice",
                                    "due": "2024-01-20",
                                    "priority": "High",
                                },
                                {
                                    "description": "Schedule team retrospective",
                                    "owner": "Bob",
                                    "due": "2024-01-25",
                                    "priority": "Medium",
                                },
                            ],
                        },
                    }
                ]
            },
        )

        assert result["status"] == "success"
        outline = report_service.get_report_outline(report_id)
        section = outline.sections[0]

        assert "## Follow-up Actions" in section.content
        assert "| # | Action | Owner | Due | Priority |" in section.content
        assert "Alice" in section.content
        assert "High" in section.content

    @pytest.mark.asyncio
    async def test_action_items_template_simple_list(self, tmp_path: Path):
        """Action items without owner/due data should render as numbered list."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        report_id = report_service.create_report(title="Simple Actions", template="default")
        tool = EvolveReportTool(config, report_service)

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add simple actions",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Next Steps",
                        "order": 1,
                        "template": "action_items",
                        "template_data": {
                            "actions": [
                                "Complete documentation review",
                                "Submit final report",
                                "Schedule follow-up meeting",
                            ],
                        },
                    }
                ]
            },
        )

        assert result["status"] == "success"
        outline = report_service.get_report_outline(report_id)
        section = outline.sections[0]

        assert "## Action Items" in section.content
        assert "1. Complete documentation review" in section.content
        assert "2. Submit final report" in section.content
        # Should NOT have table headers for simple list
        assert "| # | Action |" not in section.content
