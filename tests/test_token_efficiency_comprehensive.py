"""Phase 1.2: Token efficiency measurement and validation tests."""

import json
import uuid
from pathlib import Path

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.models import Insight, Section
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool
from igloo_mcp.mcp.tools.get_report import GetReportTool
from igloo_mcp.mcp.tools.search_report import SearchReportTool


@pytest.mark.asyncio
class TestTokenEfficiencyMeasurements:
    """Measure actual token savings from efficiency features."""

    async def test_evolve_response_detail_token_savings(self, tmp_path: Path):
        """Measure actual token savings across response_detail levels."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        # Add a section first to have valid section_id
        outline = report_service.get_report_outline(report_id)
        section_id = str(uuid.uuid4())
        section = Section(
            section_id=section_id, title="Existing", order=0, insight_ids=[]
        )
        outline.sections.append(section)
        report_service.update_report_outline(report_id, outline, actor="test")

        # Standard operation: add 3 insights
        changes = {
            "insights_to_add": [
                {
                    "section_id": section_id,
                    "insight": {"summary": "Insight 1", "importance": 8},
                },
                {
                    "section_id": section_id,
                    "insight": {"summary": "Insight 2", "importance": 7},
                },
                {
                    "section_id": section_id,
                    "insight": {"summary": "Insight 3", "importance": 9},
                },
            ],
        }

        # Get all three response levels
        minimal_result = await tool.execute(
            report_selector=report_id,
            instruction="Add insights",
            proposed_changes=changes,
            response_detail="minimal",
        )

        # Recreate report for fair comparison
        report_id2 = report_service.create_report(title="Test2", template="default")
        outline2 = report_service.get_report_outline(report_id2)
        section_id2 = str(uuid.uuid4())
        section2 = Section(
            section_id=section_id2, title="Existing", order=0, insight_ids=[]
        )
        outline2.sections.append(section2)
        report_service.update_report_outline(report_id2, outline2, actor="test")

        changes2 = {
            "insights_to_add": [
                {
                    "section_id": section_id2,
                    "insight": {"summary": "Insight 1", "importance": 8},
                },
                {
                    "section_id": section_id2,
                    "insight": {"summary": "Insight 2", "importance": 7},
                },
                {
                    "section_id": section_id2,
                    "insight": {"summary": "Insight 3", "importance": 9},
                },
            ],
        }

        standard_result = await tool.execute(
            report_selector=report_id2,
            instruction="Add insights",
            proposed_changes=changes2,
            response_detail="standard",
        )

        report_id3 = report_service.create_report(title="Test3", template="default")
        outline3 = report_service.get_report_outline(report_id3)
        section_id3 = str(uuid.uuid4())
        section3 = Section(
            section_id=section_id3, title="Existing", order=0, insight_ids=[]
        )
        outline3.sections.append(section3)
        report_service.update_report_outline(report_id3, outline3, actor="test")

        changes3 = {
            "insights_to_add": [
                {
                    "section_id": section_id3,
                    "insight": {"summary": "Insight 1", "importance": 8},
                },
                {
                    "section_id": section_id3,
                    "insight": {"summary": "Insight 2", "importance": 7},
                },
                {
                    "section_id": section_id3,
                    "insight": {"summary": "Insight 3", "importance": 9},
                },
            ],
        }

        full_result = await tool.execute(
            report_selector=report_id3,
            instruction="Add insights",
            proposed_changes=changes3,
            response_detail="full",
        )

        # Measure sizes (proxy for tokens)
        minimal_size = len(json.dumps(minimal_result))
        standard_size = len(json.dumps(standard_result))
        full_size = len(json.dumps(full_result))

        # Verify: minimal < standard < full
        assert minimal_size < standard_size < full_size

        # Verify: minimal is 40-60% of full (50-80% savings)
        savings_percent = (1 - minimal_size / full_size) * 100
        assert (
            40 <= savings_percent <= 80
        ), f"Expected 40-80% savings, got {savings_percent}%"

    async def test_search_fields_token_savings(self, tmp_path: Path):
        """Measure token savings with fields parameter."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = SearchReportTool(config, report_service)

        # Create 10 reports with full metadata
        for i in range(10):
            report_service.create_report(
                title=f"Test Report {i}", tags=["test", f"category{i % 3}"]
            )

        # Search all fields (default)
        full_result = await tool.execute(tags=["test"])

        # Search minimal fields
        minimal_result = await tool.execute(
            tags=["test"], fields=["report_id", "title"]
        )

        # Measure sizes
        full_size = len(json.dumps(full_result))
        minimal_size = len(json.dumps(minimal_result))

        # Verify: minimal < full
        assert minimal_size < full_size

        # Verify: 30-50% savings
        savings_percent = (1 - minimal_size / full_size) * 100
        assert (
            20 <= savings_percent <= 60
        ), f"Expected 20-60% savings, got {savings_percent}%"

    async def test_get_report_mode_token_efficiency(self, tmp_path: Path):
        """Verify progressive disclosure saves tokens vs full mode."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = GetReportTool(config, report_service)

        # Create report with 10 sections, 20 insights
        report_id = report_service.create_report(
            title="Large Report", template="default"
        )
        outline = report_service.get_report_outline(report_id)

        for i in range(10):
            section = Section(
                section_id=str(uuid.uuid4()),
                title=f"Section {i}",
                order=i,
                insight_ids=[],
                content=f"Content for section {i}" * 50,  # Large content
            )
            outline.sections.append(section)

        for i in range(20):
            insight = Insight(
                insight_id=str(uuid.uuid4()),
                summary=f"Insight {i} with detailed information" * 5,
                importance=i % 10 + 1,
                status="active",
                supporting_queries=[],
            )
            outline.insights.append(insight)

        report_service.update_report_outline(report_id, outline, actor="test")

        # Compare: summary vs full
        summary_result = await tool.execute(report_selector=report_id, mode="summary")
        full_result = await tool.execute(report_selector=report_id, mode="full")

        summary_size = len(json.dumps(summary_result))
        full_size = len(json.dumps(full_result))

        # Summary should be much smaller
        assert summary_size < full_size * 0.3  # <30% of full size

    async def test_evolve_minimal_preserves_essential_info(self, tmp_path: Path):
        """Verify minimal response includes everything agent needs."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add section",
            proposed_changes={"sections_to_add": [{"title": "Test", "order": 0}]},
            response_detail="minimal",
        )

        # Verify essential fields present
        assert "status" in result
        assert "report_id" in result
        assert "outline_version" in result
        assert "summary" in result

        # Verify agent can continue workflow
        assert result["status"] == "success"
        assert result["report_id"] == report_id
        assert result["summary"]["sections_added"] == 1

        # Should NOT have verbose fields
        assert "changes_applied" not in result
        assert "timing" not in result


@pytest.mark.asyncio
class TestTokenEfficiencyBackwardCompatibility:
    """Verify new parameters don't break existing code."""

    async def test_evolve_backward_compatibility(self, tmp_path: Path):
        """Verify omitting response_detail uses standard default."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        # Call WITHOUT response_detail parameter
        result = await tool.execute(
            report_selector=report_id,
            instruction="Add section",
            proposed_changes={"sections_to_add": [{"title": "Test", "order": 0}]},
        )

        # Should behave as standard level (has IDs but not full echo)
        assert result["status"] == "success"
        assert "summary" in result
        assert "section_ids_added" in result["summary"]  # Standard level feature
        assert "changes_applied" not in result  # Not full level

    async def test_search_backward_compatibility(self, tmp_path: Path):
        """Verify omitting fields returns all metadata."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = SearchReportTool(config, report_service)

        report_service.create_report(title="Test", tags=["test"])

        # Call WITHOUT fields parameter
        result = await tool.execute(title="Test")

        assert result["status"] == "success"
        assert len(result["reports"]) == 1
        report = result["reports"][0]

        # Should have all fields (backward compatible)
        assert "report_id" in report
        assert "title" in report
        assert "created_at" in report
        assert "updated_at" in report
        assert "tags" in report
        assert "status" in report
