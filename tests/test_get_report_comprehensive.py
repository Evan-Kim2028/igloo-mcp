"""Comprehensive tests for get_report tool - Phase 1.1 & 1.2 complete coverage."""

import uuid
from pathlib import Path

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.models import DatasetSource, Insight, Section
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.get_report import GetReportTool


@pytest.mark.asyncio
class TestGetReportModesCoverage:
    """Phase 1.1: Complete mode coverage tests."""

    async def test_get_report_full_mode(self, tmp_path: Path):
        """Test full mode returns complete outline structure."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        # Create report with sections and insights
        report_id = report_service.create_report(
            title="Full Test", template="quarterly_review"
        )

        # Add an insight
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
        assert result["report_id"] == report_id
        assert result["title"] == "Full Test"
        assert "sections" in result
        assert "insights" in result
        assert len(result["sections"]) == 4  # quarterly_review template
        assert len(result["insights"]) == 1
        assert result["insights"][0]["insight_id"] == insight_id
        assert result["total_sections"] == 4
        assert result["total_insights"] == 1

    async def test_get_report_sections_by_title_fuzzy_match(self, tmp_path: Path):
        """Test section title fuzzy matching."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        report_id = report_service.create_report(
            title="Test", template="quarterly_review"
        )

        # Search for sections with partial titles
        result = await tool.execute(
            report_selector=report_id,
            mode="sections",
            section_titles=["executive", "metrics"],  # Partial matches
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

        report_id = report_service.create_report(
            title="Test", template="quarterly_review"
        )
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
        outline = report_service.get_report_outline(report_id)
        section1_id = str(uuid.uuid4())
        section2_id = str(uuid.uuid4())

        section1 = Section(
            section_id=section1_id, title="Section 1", order=0, insight_ids=[]
        )
        section2 = Section(
            section_id=section2_id, title="Section 2", order=1, insight_ids=[]
        )

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
        result_with = await tool.execute(
            report_selector=report_id, mode="sections", include_content=True
        )

        assert result_with["status"] == "success"
        assert "content" in result_with["sections"][0]
        assert "Lorem ipsum" in result_with["sections"][0]["content"]

        # Get without content (default) - should omit for token efficiency
        result_without = await tool.execute(report_selector=report_id, mode="sections")

        assert result_without["status"] == "success"
        # Verify content is not included (token savings)
        assert (
            "content" not in result_without["sections"][0]
            or result_without["sections"][0].get("content") is None
        )

    async def test_get_report_mode_insights_with_citations(self, tmp_path: Path):
        """Test citation information in insights mode."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        # Add insights with citations
        outline = report_service.get_report_outline(report_id)
        section_id = str(uuid.uuid4())
        insight_id = str(uuid.uuid4())

        section = Section(
            section_id=section_id, title="Test", order=0, insight_ids=[insight_id]
        )

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

    # Pagination tests
    async def test_get_report_pagination_sections(self, tmp_path: Path):
        """Test pagination for sections mode."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        # Add 25 sections
        outline = report_service.get_report_outline(report_id)
        for i in range(25):
            section = Section(
                section_id=str(uuid.uuid4()),
                title=f"Section {i}",
                order=i,
                insight_ids=[],
            )
            outline.sections.append(section)
        report_service.update_report_outline(report_id, outline, actor="test")

        # Get first page
        result1 = await tool.execute(
            report_selector=report_id, mode="sections", limit=10, offset=0
        )

        assert result1["status"] == "success"
        assert result1["total_matched"] == 25
        assert result1["returned"] == 10
        assert result1["limit"] == 10
        assert result1["offset"] == 0

        # Get second page
        result2 = await tool.execute(
            report_selector=report_id, mode="sections", limit=10, offset=10
        )

        assert result2["returned"] == 10
        assert result2["offset"] == 10

        # Verify no overlap
        page1_ids = {s["section_id"] for s in result1["sections"]}
        page2_ids = {s["section_id"] for s in result2["sections"]}
        assert len(page1_ids & page2_ids) == 0  # No intersection

    async def test_get_report_pagination_insights(self, tmp_path: Path):
        """Test pagination for insights mode."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        # Add 30 insights
        outline = report_service.get_report_outline(report_id)
        for i in range(30):
            insight = Insight(
                insight_id=str(uuid.uuid4()),
                summary=f"Insight {i}",
                importance=i % 10 + 1,
                status="active",
                supporting_queries=[],
            )
            outline.insights.append(insight)
        report_service.update_report_outline(report_id, outline, actor="test")

        # Paginate through all
        all_insights = []
        for offset in [0, 15]:
            result = await tool.execute(
                report_selector=report_id, mode="insights", limit=15, offset=offset
            )
            all_insights.extend(result["insights"])

        assert len(all_insights) == 30
        # Verify no duplicates
        insight_ids = [i["insight_id"] for i in all_insights]
        assert len(insight_ids) == len(set(insight_ids))

    # Error handling tests
    async def test_get_report_invalid_section_ids(self, tmp_path: Path):
        """Test behavior with non-existent section IDs."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        # Request non-existent section IDs
        non_existent_id = str(uuid.uuid4())
        result = await tool.execute(
            report_selector=report_id, mode="sections", section_ids=[non_existent_id]
        )

        assert result["status"] == "success"
        assert result["total_matched"] == 0
        assert len(result["sections"]) == 0
        # Graceful handling - no error

    async def test_get_report_empty_report(self, tmp_path: Path):
        """Test getting empty report (no sections/insights)."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        report_id = report_service.create_report(title="Empty", template="default")

        # Test all modes with empty report
        summary_result = await tool.execute(report_selector=report_id, mode="summary")
        assert summary_result["status"] == "success"
        assert summary_result["summary"]["total_sections"] == 0
        assert summary_result["summary"]["total_insights"] == 0

        sections_result = await tool.execute(report_selector=report_id, mode="sections")
        assert sections_result["status"] == "success"
        assert sections_result["total_matched"] == 0

        insights_result = await tool.execute(report_selector=report_id, mode="insights")
        assert insights_result["status"] == "success"
        assert insights_result["total_matched"] == 0

        full_result = await tool.execute(report_selector=report_id, mode="full")
        assert full_result["status"] == "success"
        assert full_result["total_sections"] == 0
        assert full_result["total_insights"] == 0
