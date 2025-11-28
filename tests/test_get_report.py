"""Tests for GetReportTool - selective report retrieval."""

import uuid
from pathlib import Path

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.get_report import GetReportTool


@pytest.mark.asyncio
class TestGetReportTool:
    """Test suite for get_report tool."""

    async def test_get_report_summary_mode(self, tmp_path: Path):
        """Test summary mode returns lightweight overview."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        # Create a test report
        report_id = report_service.create_report(
            title="Test Report",
            template="default",
            tags=["test", "sample"],
        )

        # Get summary
        result = await tool.execute(
            report_selector=report_id,
            mode="summary",
        )

        assert result["status"] == "success"
        assert result["report_id"] == report_id
        assert result["title"] == "Test Report"
        assert "summary" in result
        assert result["summary"]["total_sections"] == 0
        assert result["summary"]["total_insights"] == 0
        assert result["summary"]["tags"] == ["test", "sample"]
        assert "sections_overview" in result

    async def test_get_report_sections_mode(self, tmp_path: Path):
        """Test sections mode returns section details."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        # Create report and add section via evolve
        report_id = report_service.create_report(
            title="Test Report",
            template="default",
        )

        # Add a section
        from igloo_mcp.living_reports.changes_schema import ProposedChanges

        outline = report_service.get_report_outline(report_id)
        section_id = str(uuid.uuid4())

        _ = ProposedChanges(
            sections_to_add=[
                {
                    "section_id": section_id,
                    "title": "Test Section",
                    "order": 0,
                }
            ]
        )

        # Apply changes manually to outline
        from igloo_mcp.living_reports.models import Section

        new_section = Section(
            section_id=section_id,
            title="Test Section",
            order=0,
            insight_ids=[],
        )
        outline.sections.append(new_section)
        report_service.update_report_outline(report_id, outline, actor="test")

        # Get sections
        result = await tool.execute(
            report_selector=report_id,
            mode="sections",
        )

        assert result["status"] == "success"
        assert result["total_matched"] == 1
        assert len(result["sections"]) == 1
        assert result["sections"][0]["section_id"] == section_id
        assert result["sections"][0]["title"] == "Test Section"

    async def test_get_report_insights_mode_with_filter(self, tmp_path: Path):
        """Test insights mode with min_importance filter."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        # Create report with insights
        report_id = report_service.create_report(
            title="Test Report",
            template="default",
        )

        # Add section and insights
        from igloo_mcp.living_reports.models import Insight, Section

        outline = report_service.get_report_outline(report_id)

        section_id = str(uuid.uuid4())
        insight1_id = str(uuid.uuid4())
        insight2_id = str(uuid.uuid4())

        section = Section(
            section_id=section_id,
            title="Test Section",
            order=0,
            insight_ids=[insight1_id, insight2_id],
        )

        insight1 = Insight(
            insight_id=insight1_id,
            summary="High priority insight",
            importance=9,
            status="active",
            supporting_queries=[],
        )

        insight2 = Insight(
            insight_id=insight2_id,
            summary="Low priority insight",
            importance=5,
            status="active",
            supporting_queries=[],
        )

        outline.sections.append(section)
        outline.insights.extend([insight1, insight2])
        report_service.update_report_outline(report_id, outline, actor="test")

        # Get insights with min_importance filter
        result = await tool.execute(
            report_selector=report_id,
            mode="insights",
            min_importance=8,
        )

        assert result["status"] == "success"
        assert result["total_matched"] == 1
        assert len(result["insights"]) == 1
        assert result["insights"][0]["insight_id"] == insight1_id
        assert result["insights"][0]["importance"] == 9
        assert result["filtered_by"]["min_importance"] == 8

    async def test_get_report_invalid_mode(self, tmp_path: Path):
        """Test that invalid mode raises validation error."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        from igloo_mcp.mcp.exceptions import MCPValidationError

        with pytest.raises(MCPValidationError) as exc_info:
            await tool.execute(
                report_selector=report_id,
                mode="invalid_mode",
            )

        assert "Invalid mode" in str(exc_info.value)

    async def test_get_report_not_found(self, tmp_path: Path):
        """Test that non-existent report raises selector error."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        from igloo_mcp.mcp.exceptions import MCPSelectorError

        with pytest.raises(MCPSelectorError) as exc_info:
            await tool.execute(
                report_selector="NonExistent Report",
                mode="summary",
            )

        assert "not found" in str(exc_info.value).lower()
