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
        """Test get_report with invalid mode raises validation error."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        report_id = report_service.create_report(title="Test Report", template="default")

        from igloo_mcp.mcp.exceptions import MCPValidationError

        with pytest.raises(MCPValidationError) as exc_info:
            await tool.execute(
                report_selector=report_id,
                mode="invalid_mode",  # Legacy parameter, will be validated
            )

        # Should validate the mode value even when using legacy parameter
        assert "Invalid" in str(exc_info.value) or "invalid_mode" in str(exc_info.value).lower()

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

    # ===== PHASE 1.1: Mode Coverage Tests =====

    async def test_get_report_full_mode(self, tmp_path: Path):
        """Test full mode returns complete outline structure."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        # Create report with sections and insights
        report_id = report_service.create_report(title="Full Test", template="quarterly_review")

        # Add an insight
        from igloo_mcp.living_reports.models import Insight

        outline = report_service.get_report_outline(report_id)
        insight_id = str(uuid.uuid4())
        insight = Insight(
            insight_id=insight_id,
            summary="Test insight",
            importance=8,
            status="active",
            supporting_queries=[],
        )
        outline.insights.append(insight)
        outline.sections[0].insight_ids.append(insight_id)
        report_service.update_report_outline(report_id, outline, actor="test")

        # Get full mode
        result = await tool.execute(report_selector=report_id, mode="full")

        assert result["status"] == "success"
        assert "outline" in result
        assert result["outline"]["report_id"] == report_id
        assert len(result["outline"]["sections"]) == 4  # quarterly_review template
        assert len(result["outline"]["insights"]) == 1
        assert result["outline"]["insights"][0]["insight_id"] == insight_id

    async def test_get_report_sections_by_title_fuzzy_match(self, tmp_path: Path):
        """Test section title fuzzy matching."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="quarterly_review")

        # Search for sections with partial titles
        # quarterly_review has: "Executive Summary", "Key Metrics", "Strategic Initiatives", "Next Quarter Goals"
        result = await tool.execute(
            report_selector=report_id,
            mode="sections",
            section_titles=[
                "executive",
                "metrics",
            ],  # Partial matches for actual template sections
        )

        assert result["status"] == "success"
        # Should match "Executive Summary" and "Key Metrics"
        assert result["total_matched"] >= 2
        titles = [s["title"] for s in result["sections"]]
        assert any("Executive" in t for t in titles)
        assert any("Metrics" in t for t in titles)

    async def test_get_report_sections_by_id(self, tmp_path: Path):
        """Test section retrieval by exact IDs."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="quarterly_review")
        outline = report_service.get_report_outline(report_id)

        # Get specific sections by ID
        section_id_1 = outline.sections[0].section_id
        section_id_2 = outline.sections[1].section_id

        result = await tool.execute(
            report_selector=report_id,
            mode="sections",
            section_ids=[section_id_1, section_id_2],
        )

        assert result["status"] == "success"
        assert result["total_matched"] == 2
        returned_ids = {s["section_id"] for s in result["sections"]}
        assert section_id_1 in returned_ids
        assert section_id_2 in returned_ids

    async def test_get_report_insights_multiple_filters(self, tmp_path: Path):
        """Test combining multiple insight filters."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        # Add multiple insights with different attributes
        from igloo_mcp.living_reports.models import Insight, Section

        outline = report_service.get_report_outline(report_id)
        section1_id = str(uuid.uuid4())
        section2_id = str(uuid.uuid4())

        section1 = Section(section_id=section1_id, title="Section 1", order=0, insight_ids=[])
        section2 = Section(section_id=section2_id, title="Section 2", order=1, insight_ids=[])

        insights = [
            Insight(
                insight_id=str(uuid.uuid4()),
                summary="High importance in section 1",
                importance=9,
                status="active",
                supporting_queries=[],
            ),
            Insight(
                insight_id=str(uuid.uuid4()),
                summary="Low importance in section 1",
                importance=5,
                status="active",
                supporting_queries=[],
            ),
            Insight(
                insight_id=str(uuid.uuid4()),
                summary="High importance in section 2",
                importance=8,
                status="active",
                supporting_queries=[],
            ),
        ]

        section1.insight_ids = [insights[0].insight_id, insights[1].insight_id]
        section2.insight_ids = [insights[2].insight_id]

        outline.sections = [section1, section2]
        outline.insights = insights
        report_service.update_report_outline(report_id, outline, actor="test")

        # Filter: min_importance=8 AND section_ids=[section1]
        result = await tool.execute(
            report_selector=report_id,
            mode="insights",
            min_importance=8,
            section_ids=[section1_id],
        )

        assert result["status"] == "success"
        assert result["total_matched"] == 1  # Only one insight matches both criteria
        assert result["insights"][0]["importance"] == 9
        assert "section 1" in result["insights"][0]["summary"]

    async def test_get_report_mode_sections_with_content(self, tmp_path: Path):
        """Test include_content parameter in sections mode."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        # Add section with prose content
        from igloo_mcp.living_reports.models import Section

        outline = report_service.get_report_outline(report_id)
        section_id = str(uuid.uuid4())
        section = Section(
            section_id=section_id,
            title="Test Section",
            order=0,
            insight_ids=[],
            content="## This is prose content\n\nLorem ipsum dolor sit amet.",
            content_format="markdown",
        )
        outline.sections.append(section)
        report_service.update_report_outline(report_id, outline, actor="test")

        # Get with content
        result_with = await tool.execute(report_selector=report_id, mode="sections", include_content=True)

        assert result_with["status"] == "success"
        assert "content" in result_with["sections"][0]
        assert "Lorem ipsum" in result_with["sections"][0]["content"]

        # Get without content (default)
        result_without = await tool.execute(report_selector=report_id, mode="sections")

        assert result_without["status"] == "success"
        # Content should be omitted for token efficiency
        assert "content" not in result_without["sections"][0] or result_without["sections"][0].get("content") is None

    async def test_get_report_mode_insights_with_citations(self, tmp_path: Path):
        """Test citation information in insights mode."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        # Add insights with citations
        from igloo_mcp.living_reports.models import DatasetSource, Insight, Section

        outline = report_service.get_report_outline(report_id)
        section_id = str(uuid.uuid4())
        insight_id = str(uuid.uuid4())

        section = Section(section_id=section_id, title="Test", order=0, insight_ids=[insight_id])

        insight = Insight(
            insight_id=insight_id,
            summary="Insight with citations",
            importance=8,
            status="active",
            supporting_queries=[
                DatasetSource(execution_id="exec_123"),
                DatasetSource(execution_id="exec_456"),
            ],
        )

        outline.sections.append(section)
        outline.insights.append(insight)
        report_service.update_report_outline(report_id, outline, actor="test")

        # Get insights mode
        result = await tool.execute(report_selector=report_id, mode="insights")

        assert result["status"] == "success"
        assert result["total_matched"] == 1
        insight_result = result["insights"][0]
        assert insight_result["has_citations"] is True
        assert insight_result["citation_count"] == 2
        assert insight_result["section_id"] == section_id  # Shows ownership
