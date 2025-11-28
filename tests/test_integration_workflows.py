"""Phase 2: Integration tests - tools working together in workflows."""

import uuid
from pathlib import Path

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.models import Insight, Section
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.create_report import CreateReportTool
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool
from igloo_mcp.mcp.tools.get_report import GetReportTool
from igloo_mcp.mcp.tools.get_report_schema import GetReportSchemaTool
from igloo_mcp.mcp.tools.render_report import RenderReportTool
from igloo_mcp.mcp.tools.search_report import SearchReportTool


@pytest.mark.asyncio
class TestWorkflowIntegration:
    """Test complete workflows using multiple tools together."""

    async def test_search_get_evolve_workflow(self, tmp_path: Path):
        """Test: search → get → evolve flow."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        search_tool = SearchReportTool(config, report_service)
        get_tool = GetReportTool(config, report_service)
        evolve_tool = EvolveReportTool(config, report_service)

        # Setup: Create report
        report_id = report_service.create_report(
            title="Q1 Analysis", tags=["Q1", "analysis"]
        )

        # Step 1: search_report to find report
        search_result = await search_tool.execute(
            title="Q1", fields=["report_id", "title"]  # Token efficient
        )

        assert search_result["status"] == "success"
        assert len(search_result["reports"]) == 1
        found_id = search_result["reports"][0]["report_id"]
        assert found_id == report_id

        # Step 2: get_report (summary) to understand structure
        summary_result = await get_tool.execute(
            report_selector=found_id, mode="summary"
        )

        assert summary_result["status"] == "success"
        assert summary_result["title"] == "Q1 Analysis"

        # Step 3: get_report (sections) to get section_id for modification
        # For this test, add a section first
        outline = report_service.get_report_outline(report_id)
        section_id = str(uuid.uuid4())
        outline.sections.append(
            Section(section_id=section_id, title="Revenue", order=0, insight_ids=[])
        )
        report_service.update_report_outline(report_id, outline, actor="test")

        sections_result = await get_tool.execute(
            report_selector=found_id, mode="sections", section_titles=["revenue"]
        )

        assert sections_result["total_matched"] == 1
        target_section_id = sections_result["sections"][0]["section_id"]

        # Step 4: evolve_report to modify that section
        evolve_result = await evolve_tool.execute(
            report_selector=found_id,
            instruction="Add revenue insight",
            proposed_changes={
                "insights_to_add": [
                    {
                        "section_id": target_section_id,
                        "insight": {"summary": "Revenue grew 25%", "importance": 9},
                    }
                ]
            },
            response_detail="minimal",  # Token efficient
        )

        assert evolve_result["status"] == "success"
        assert evolve_result["summary"]["insights_added"] == 1

        # Step 5: get_report to verify changes
        verify_result = await get_tool.execute(
            report_selector=found_id, mode="insights"
        )

        assert verify_result["total_matched"] == 1
        assert "Revenue grew 25%" in verify_result["insights"][0]["summary"]

    async def test_schema_guided_evolution(self, tmp_path: Path):
        """Test: get_schema → construct change → evolve."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        schema_tool = GetReportSchemaTool(config)
        evolve_tool = EvolveReportTool(config, report_service)

        # Step 1: get_report_schema (examples format)
        schema_result = await schema_tool.execute(
            schema_type="proposed_changes", format="examples"
        )

        assert schema_result["status"] == "success"
        assert "examples" in schema_result
        assert "add_section_with_insights" in schema_result["examples"]

        # Step 2: Adapt example to actual report
        report_id = report_service.create_report(title="Test", template="default")
        example = schema_result["examples"]["add_section_with_insights"]

        # Step 3: evolve_report with constructed change
        evolve_result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Use schema example",
            proposed_changes=example["proposed_changes"],
        )

        # Schema should help agent build valid changes
        assert evolve_result["status"] == "success"

    async def test_progressive_disclosure_workflow(self, tmp_path: Path):
        """Test: summary → filter insights → get details (token efficient)."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        get_tool = GetReportTool(config, report_service)

        # Create report with varied content
        report_id = report_service.create_report(
            title="Complex Report", template="default"
        )
        outline = report_service.get_report_outline(report_id)

        # Add 5 sections
        for i in range(5):
            section = Section(
                section_id=str(uuid.uuid4()),
                title=f"Section {i}",
                order=i,
                insight_ids=[],
            )
            outline.sections.append(section)

        # Add 15 insights (varied importance)
        for i in range(15):
            insight = Insight(
                insight_id=str(uuid.uuid4()),
                summary=f"Insight {i}",
                importance=i % 10 + 1,  # 1-10
                status="active",
                supporting_queries=[],
            )
            outline.insights.append(insight)
            outline.sections[i % 5].insight_ids.append(insight.insight_id)

        report_service.update_report_outline(report_id, outline, actor="test")

        # Step 1: summary - get high-level structure (minimal tokens)
        summary = await get_tool.execute(report_selector=report_id, mode="summary")

        assert summary["summary"]["total_sections"] == 5
        assert summary["summary"]["total_insights"] == 15

        # Step 2: filter insights - get only important ones
        important = await get_tool.execute(
            report_selector=report_id, mode="insights", min_importance=8
        )

        # Should return subset
        assert important["total_matched"] < 15
        assert all(i["importance"] >= 8 for i in important["insights"])

        # Step 3: get details for specific sections
        section_ids = [s["section_id"] for s in summary["sections_overview"][:2]]
        details = await get_tool.execute(
            report_selector=report_id, mode="sections", section_ids=section_ids
        )

        assert details["total_matched"] == 2

        # Workflow uses far fewer tokens than getting full report upfront

    async def test_create_with_schema_workflow(self, tmp_path: Path):
        """Test: create → schema → initial structure → verify."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        create_tool = CreateReportTool(config, report_service)
        schema_tool = GetReportSchemaTool(config)
        get_tool = GetReportTool(config, report_service)
        evolve_tool = EvolveReportTool(config, report_service)

        # Step 1: create_report with template
        create_result = await create_tool.execute(
            title="New Report", template="deep_dive"
        )

        assert create_result["status"] == "success"
        report_id = create_result["report_id"]

        # Step 2: get_report_schema to learn structure
        schema_result = await schema_tool.execute(
            schema_type="proposed_changes", format="compact"
        )

        assert "quick_reference" in schema_result

        # Step 2.5: Get section_id from the template (deep_dive has 3 sections)
        outline = report_service.get_report_outline(report_id)
        section_id = outline.sections[0].section_id  # Use first section

        # Step 3: evolve_report to add initial content
        evolve_result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Add initial insights",
            proposed_changes={
                "insights_to_add": [
                    {
                        "section_id": section_id,  # Use actual section_id
                        "insight": {"summary": "Initial finding", "importance": 8},
                    }
                ]
            },
        )

        assert evolve_result["status"] == "success"

        # Step 4: get_report to verify structure
        verify_result = await get_tool.execute(
            report_selector=report_id, mode="summary"
        )

        assert verify_result["summary"]["total_insights"] == 1

    async def test_token_efficient_modification_workflow(self, tmp_path: Path):
        """Test: efficient search → targeted get → minimal evolve."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        search_tool = SearchReportTool(config, report_service)
        get_tool = GetReportTool(config, report_service)
        evolve_tool = EvolveReportTool(config, report_service)

        # Create report
        report_id = report_service.create_report(title="Efficiency Test", tags=["test"])

        # Add insight
        outline = report_service.get_report_outline(report_id)
        insight = Insight(
            insight_id=str(uuid.uuid4()),
            summary="Original",
            importance=5,
            status="active",
            supporting_queries=[],
        )
        outline.insights.append(insight)
        report_service.update_report_outline(report_id, outline, actor="test")

        # Step 1: search_report (fields=minimal)
        search_result = await search_tool.execute(
            tags=["test"], fields=["report_id", "title"]
        )

        assert len(search_result["reports"]) == 1

        # Step 2: get_report (insights, filtered)
        get_result = await get_tool.execute(
            report_selector=report_id, mode="insights", min_importance=5
        )

        insight_id = get_result["insights"][0]["insight_id"]

        # Step 3: evolve_report (response_detail=minimal)
        evolve_result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Update insight",
            proposed_changes={
                "insights_to_modify": [
                    {"insight_id": insight_id, "summary": "Updated", "importance": 9}
                ]
            },
            response_detail="minimal",
        )

        assert evolve_result["status"] == "success"
        # All steps used token-efficient parameters

    async def test_multi_section_editing_workflow(self, tmp_path: Path):
        """Test: editing multiple sections across turns."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        get_tool = GetReportTool(config, report_service)
        evolve_tool = EvolveReportTool(config, report_service)

        # Setup: Create report with 3 sections
        report_id = report_service.create_report(
            title="Multi-Edit", template="deep_dive"
        )

        # Turn 1: get_report (summary) - overview
        summary = await get_tool.execute(report_selector=report_id, mode="summary")
        assert summary["summary"]["total_sections"] == 3

        # Turn 2: get_report (specific section)
        section1_result = await get_tool.execute(
            report_selector=report_id, mode="sections", section_titles=["overview"]
        )
        section1_id = section1_result["sections"][0]["section_id"]

        # Turn 3: evolve_report (modify section 1)
        evolve1 = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Add to section 1",
            proposed_changes={
                "insights_to_add": [
                    {
                        "section_id": section1_id,
                        "insight": {"summary": "Finding 1", "importance": 8},
                    }
                ]
            },
        )
        assert evolve1["status"] == "success"
        version1 = evolve1["outline_version"]

        # Turn 4: get_report (different section)
        section2_result = await get_tool.execute(
            report_selector=report_id, mode="sections", section_titles=["methodology"]
        )
        section2_id = section2_result["sections"][0]["section_id"]

        # Turn 5: evolve_report (modify section 2)
        evolve2 = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Add to section 2",
            proposed_changes={
                "insights_to_add": [
                    {
                        "section_id": section2_id,
                        "insight": {"summary": "Finding 2", "importance": 7},
                    }
                ]
            },
        )
        assert evolve2["status"] == "success"
        version2 = evolve2["outline_version"]

        # Verify: outline_version incremented
        assert version2 > version1

    async def test_render_verification_workflow(self, tmp_path: Path):
        """Test: build → verify → render → review."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        create_tool = CreateReportTool(config, report_service)
        evolve_tool = EvolveReportTool(config, report_service)
        get_tool = GetReportTool(config, report_service)
        render_tool = RenderReportTool(config, report_service)

        # Step 1: create_report
        create_result = await create_tool.execute(
            title="Render Test", template="default"
        )
        report_id = create_result["report_id"]

        # Step 2: evolve_report (build content) - use inline insights
        await evolve_tool.execute(
            report_selector=report_id,
            instruction="Add content",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Summary",
                        "order": 0,
                        "insights": [  # Use inline insights feature
                            {"summary": "Key finding", "importance": 9}
                        ],
                    }
                ],
            },
        )

        # Step 3: get_report (full) - final verification
        verify_result = await get_tool.execute(report_selector=report_id, mode="full")

        assert verify_result["total_sections"] == 1
        assert verify_result["total_insights"] == 1

        # Step 4: render_report (dry run for quick check)
        render_result = await render_tool.execute(
            report_selector=report_id,
            format="html",
            dry_run=True,
            include_preview=False,  # Don't need preview in workflow
        )

        assert render_result["status"] == "success"
