"""Integration tests for API completeness features.

Tests multi-tool workflows to verify request_id correlation, timing metrics,
ID tracking, and warnings infrastructure work correctly across tool boundaries.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from igloo_mcp.catalog import CatalogService
from igloo_mcp.config import Config
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.build_catalog import BuildCatalogTool
from igloo_mcp.mcp.tools.create_report import CreateReportTool
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool
from igloo_mcp.mcp.tools.get_catalog_summary import GetCatalogSummaryTool
from igloo_mcp.mcp.tools.search_catalog import SearchCatalogTool

UUID4_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


@pytest.fixture
def temp_reports_dir():
    """Create temporary reports directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_catalog_dir():
    """Create temporary catalog directory with test data."""
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create catalog.json file with empty catalog structure
        catalog_data = {
            "databases": [],
            "schemas": [],
            "tables": [],
            "views": [],
            "materialized_views": [],
            "dynamic_tables": [],
            "tasks": [],
            "functions": [],
            "procedures": [],
        }
        catalog_path = Path(tmpdir) / "catalog.json"
        catalog_path.write_text(json.dumps(catalog_data))
        yield tmpdir


@pytest.fixture
def config(temp_reports_dir):
    """Create config with temp directories."""
    cfg = Mock(spec=Config)
    cfg.reports_dir = temp_reports_dir
    cfg.snowflake_profile = "test_profile"
    return cfg


@pytest.fixture
def report_service(temp_reports_dir):
    """Create report service instance."""
    return ReportService(reports_root=temp_reports_dir)


@pytest.fixture
def mock_catalog_service(config):
    """Create mock catalog service."""
    service = Mock(spec=CatalogService)

    # Mock build result
    build_result = Mock()
    build_result.output_dir = "/tmp/test_catalog"
    build_result.totals = Mock(
        databases=5,
        schemas=10,
        tables=50,
        views=20,
        materialized_views=5,
        dynamic_tables=3,
        tasks=2,
        functions=15,
        procedures=8,
        columns=500,
    )
    service.build = Mock(return_value=build_result)

    return service


class TestRequestIdCorrelation:
    """Test request_id correlation across multi-tool workflows."""

    @pytest.mark.asyncio
    async def test_create_evolve_report_correlation(self, config, report_service):
        """Test request_id correlation in create → evolve workflow."""
        create_tool = CreateReportTool(config, report_service)
        evolve_tool = EvolveReportTool(config, report_service)

        # Use same request_id for related operations
        correlation_id = "workflow-create-evolve-001"

        # Step 1: Create report
        create_result = await create_tool.execute(
            title="Correlation Test Report",
            template="default",
            request_id=correlation_id,
        )

        assert create_result["request_id"] == correlation_id

        # Step 2: Evolve report with same correlation ID
        report_id = create_result["report_id"]
        changes = {
            "sections_to_add": [
                {
                    "section_id": "intro",
                    "title": "Introduction",
                    "order": 0,
                    "content": "Intro content",
                }
            ],
        }

        evolve_result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Add introduction section",
            proposed_changes=changes,
            request_id=correlation_id,
        )

        assert evolve_result["request_id"] == correlation_id

        # Both operations share same request_id for correlation
        assert create_result["request_id"] == evolve_result["request_id"]

    @pytest.mark.asyncio
    async def test_catalog_workflow_correlation(self, config, mock_catalog_service, temp_catalog_dir):
        """Test request_id correlation in build → search → summary workflow."""
        build_tool = BuildCatalogTool(config, mock_catalog_service)
        search_tool = SearchCatalogTool()
        summary_tool = GetCatalogSummaryTool(mock_catalog_service)

        correlation_id = "workflow-catalog-001"

        # Step 1: Build catalog
        build_result = await build_tool.execute(
            output_dir="./test_catalog",
            request_id=correlation_id,
        )
        assert build_result["request_id"] == correlation_id

        # Step 2: Search catalog
        search_result = await search_tool.execute(
            catalog_dir=temp_catalog_dir,
            name_contains="test",
            request_id=correlation_id,
        )
        assert search_result["request_id"] == correlation_id

        # Step 3: Get summary
        summary_result = await summary_tool.execute(
            catalog_dir=temp_catalog_dir,
            request_id=correlation_id,
        )
        assert summary_result["request_id"] == correlation_id

        # All operations share same correlation ID
        assert build_result["request_id"] == search_result["request_id"] == summary_result["request_id"]

    @pytest.mark.asyncio
    async def test_different_workflows_different_ids(self, config, report_service):
        """Test that different workflows can use different request_ids."""
        create_tool = CreateReportTool(config, report_service)

        # Workflow 1
        result1 = await create_tool.execute(
            title="Report 1",
            template="default",
            request_id="workflow-001",
        )

        # Workflow 2
        result2 = await create_tool.execute(
            title="Report 2",
            template="default",
            request_id="workflow-002",
        )

        assert result1["request_id"] != result2["request_id"]
        assert result1["request_id"] == "workflow-001"
        assert result2["request_id"] == "workflow-002"


class TestTimingMetricsIntegration:
    """Test timing metrics across multi-step operations."""

    @pytest.mark.asyncio
    async def test_create_evolve_timing_accumulation(self, config, report_service):
        """Test timing metrics in create → evolve workflow."""
        create_tool = CreateReportTool(config, report_service)
        evolve_tool = EvolveReportTool(config, report_service)

        # Create report
        create_result = await create_tool.execute(
            title="Timing Test",
            template="monthly_sales",
        )

        create_timing = create_result["timing"]
        assert "total_duration_ms" in create_timing
        assert "create_duration_ms" in create_timing
        assert "outline_duration_ms" in create_timing

        # Evolve report
        report_id = create_result["report_id"]
        changes = {
            "sections_to_add": [
                {
                    "title": "New Section",
                    "order": 99,
                    "content": "Content",
                }
            ],
        }

        evolve_result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Update report",
            proposed_changes=changes,
            response_detail="full",
        )

        evolve_timing = evolve_result["timing"]
        assert "total_duration_ms" in evolve_timing
        assert "apply_duration_ms" in evolve_timing
        assert "storage_duration_ms" in evolve_timing

        # Both operations have timing
        assert create_timing["total_duration_ms"] > 0
        assert evolve_timing["total_duration_ms"] > 0

    @pytest.mark.asyncio
    async def test_catalog_workflow_timing(self, config, mock_catalog_service, temp_catalog_dir):
        """Test timing metrics in catalog workflow."""
        build_tool = BuildCatalogTool(config, mock_catalog_service)
        search_tool = SearchCatalogTool()

        # Build
        build_result = await build_tool.execute(output_dir="./test_catalog")
        build_timing = build_result["timing"]

        assert "catalog_fetch_ms" in build_timing
        assert "total_duration_ms" in build_timing
        assert build_timing["catalog_fetch_ms"] <= build_timing["total_duration_ms"]

        # Search
        search_result = await search_tool.execute(catalog_dir=temp_catalog_dir)
        search_timing = search_result["timing"]

        assert "search_duration_ms" in search_timing
        assert "total_duration_ms" in search_timing
        assert search_timing["search_duration_ms"] <= search_timing["total_duration_ms"]


class TestIdTrackingLifecycle:
    """Test ID tracking throughout entity lifecycle."""

    @pytest.mark.asyncio
    async def test_report_lifecycle_id_tracking(self, config, report_service):
        """Test ID tracking from creation through evolution."""
        create_tool = CreateReportTool(config, report_service)
        evolve_tool = EvolveReportTool(config, report_service)

        # Create with template (has sections)
        create_result = await create_tool.execute(
            title="Lifecycle Test",
            template="monthly_sales",
        )

        initial_sections = create_result["section_ids_added"]
        assert len(initial_sections) > 0

        # Evolve: add new, modify existing, remove one
        report_id = create_result["report_id"]
        changes = {
            "sections_to_add": [
                {
                    "title": "New",
                    "order": 99,
                    "content": "New",
                }
            ],
            "sections_to_modify": [
                {
                    "section_id": initial_sections[0],
                    "title": "Updated Title",
                }
            ],
            "sections_to_remove": (initial_sections[1:2] if len(initial_sections) > 1 else []),
        }

        evolve_result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Update report",
            proposed_changes=changes,
        )

        # Verify ID tracking
        assert len(evolve_result["section_ids_added"]) == 1
        assert initial_sections[0] in evolve_result["section_ids_modified"]

        if changes["sections_to_remove"]:
            assert evolve_result["section_ids_removed"] == changes["sections_to_remove"]

    @pytest.mark.asyncio
    async def test_multiple_evolutions_id_tracking(self, config, report_service):
        """Test ID tracking across multiple evolution operations."""
        create_tool = CreateReportTool(config, report_service)
        evolve_tool = EvolveReportTool(config, report_service)

        # Create empty report
        create_result = await create_tool.execute(
            title="Multi Evolution Test",
            template="default",
        )
        report_id = create_result["report_id"]

        # Evolution 1: Add sections
        changes1 = {
            "sections_to_add": [
                {
                    "title": "Section 1",
                    "order": 0,
                    "content": "C1",
                },
                {
                    "title": "Section 2",
                    "order": 1,
                    "content": "C2",
                },
            ],
        }

        evolve1 = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Update report",
            proposed_changes=changes1,
        )

        assert len(evolve1["section_ids_added"]) == 2
        # Capture auto-generated section IDs
        sec1_id = evolve1["section_ids_added"][0]
        sec2_id = evolve1["section_ids_added"][1]

        # Evolution 2: Modify one, remove one
        changes2 = {
            "sections_to_modify": [
                {"section_id": sec1_id, "title": "Updated Section 1"},
            ],
            "sections_to_remove": [sec2_id],
        }

        evolve2 = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Update report",
            proposed_changes=changes2,
        )

        assert sec1_id in evolve2["section_ids_modified"]
        assert sec2_id in evolve2["section_ids_removed"]

        # Evolution 3: Add new section
        changes3 = {
            "sections_to_add": [
                {
                    "title": "Section 3",
                    "order": 2,
                    "content": "C3",
                },
            ],
        }

        evolve3 = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Update report",
            proposed_changes=changes3,
        )

        assert len(evolve3["section_ids_added"]) == 1
        sec3_id = evolve3["section_ids_added"][0]

        # Final state: should have sec1 and sec3 (sec2 was removed)
        final_outline = report_service.get_report_outline(report_id)
        final_section_ids = [s.section_id for s in final_outline.sections]

        assert sec1_id in final_section_ids
        assert sec3_id in final_section_ids
        assert sec2_id not in final_section_ids


class TestWarningsInWorkflows:
    """Test warnings infrastructure in multi-tool workflows."""

    @pytest.mark.asyncio
    async def test_warnings_present_in_all_steps(self, config, mock_catalog_service, temp_catalog_dir):
        """Test that warnings field is present in all workflow steps."""
        build_tool = BuildCatalogTool(config, mock_catalog_service)
        search_tool = SearchCatalogTool()

        # Build
        build_result = await build_tool.execute(output_dir="./test_catalog")
        assert "warnings" in build_result

        # Search
        search_result = await search_tool.execute(catalog_dir=temp_catalog_dir)
        assert "warnings" in search_result

        # Both should be empty arrays (no warnings)
        assert build_result["warnings"] == []
        assert search_result["warnings"] == []

    @pytest.mark.asyncio
    async def test_warnings_independence_across_calls(self, config, mock_catalog_service):
        """Test that warnings from one call don't affect another."""
        build_tool = BuildCatalogTool(config, mock_catalog_service)

        # Call 1
        result1 = await build_tool.execute(output_dir="./test_catalog1")

        # Call 2
        result2 = await build_tool.execute(output_dir="./test_catalog2")

        # Each call should have independent warnings
        assert result1["warnings"] is not result2["warnings"]
        assert result1["warnings"] == []
        assert result2["warnings"] == []


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""

    @pytest.mark.asyncio
    async def test_complete_report_workflow(self, config, report_service):
        """Test complete workflow: create → evolve → evolve → verify."""
        create_tool = CreateReportTool(config, report_service)
        evolve_tool = EvolveReportTool(config, report_service)

        workflow_id = "e2e-report-workflow"

        # Step 1: Create report
        create_result = await create_tool.execute(
            title="E2E Workflow Test",
            template="quarterly_review",
            request_id=workflow_id,
        )

        assert create_result["status"] == "success"
        assert create_result["request_id"] == workflow_id
        assert "section_ids_added" in create_result
        assert "timing" in create_result

        report_id = create_result["report_id"]
        initial_sections = create_result["section_ids_added"]

        # Step 2: First evolution - add content
        changes1 = {
            "insights_to_add": [
                {
                    "summary": "Important discovery",
                    "importance": 8,
                }
            ],
        }

        evolve1 = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Update report",
            proposed_changes=changes1,
            constraints={"skip_citation_validation": True},
            response_detail="full",
            request_id=workflow_id,
        )

        assert evolve1["status"] == "success"
        assert evolve1["request_id"] == workflow_id
        assert len(evolve1["insight_ids_added"]) == 1
        assert "timing" in evolve1

        # Capture the auto-generated insight_id
        added_insight_id = evolve1["insight_ids_added"][0]

        # Step 3: Second evolution - modify and remove
        if initial_sections:
            changes2 = {
                "sections_to_modify": [
                    {
                        "section_id": initial_sections[0],
                        "content": "Updated content",
                    }
                ],
                "insights_to_remove": [added_insight_id],
            }

            evolve2 = await evolve_tool.execute(
                report_selector=report_id,
                instruction="Modify section content and remove insight",
                proposed_changes=changes2,
                request_id=workflow_id,
            )

            assert evolve2["status"] == "success"
            assert evolve2["request_id"] == workflow_id
            assert initial_sections[0] in evolve2["section_ids_modified"]
            assert added_insight_id in evolve2["insight_ids_removed"]

        # Verify final state
        final_outline = report_service.get_report_outline(report_id)
        assert final_outline is not None

        # All operations in workflow shared same request_id
        assert create_result["request_id"] == evolve1["request_id"]

    @pytest.mark.asyncio
    async def test_complete_catalog_workflow(self, config, mock_catalog_service, temp_catalog_dir):
        """Test complete workflow: build → search → summary."""
        build_tool = BuildCatalogTool(config, mock_catalog_service)
        search_tool = SearchCatalogTool()
        summary_tool = GetCatalogSummaryTool(mock_catalog_service)

        workflow_id = "e2e-catalog-workflow"

        # Step 1: Build catalog
        build_result = await build_tool.execute(
            output_dir="./test_catalog",
            database="TEST_DB",
            request_id=workflow_id,
        )

        assert build_result["status"] == "success"
        assert build_result["request_id"] == workflow_id
        assert "timing" in build_result
        assert "warnings" in build_result

        # Step 2: Search catalog
        search_result = await search_tool.execute(
            catalog_dir=temp_catalog_dir,
            name_contains="test",
            limit=10,
            request_id=workflow_id,
        )

        assert search_result["status"] == "success"
        assert search_result["request_id"] == workflow_id
        assert "timing" in search_result
        assert "warnings" in search_result

        # Step 3: Get summary
        summary_result = await summary_tool.execute(
            catalog_dir=temp_catalog_dir,
            request_id=workflow_id,
        )

        assert summary_result["status"] == "success"
        assert summary_result["request_id"] == workflow_id
        assert "timing" in summary_result

        # All operations share correlation ID
        assert build_result["request_id"] == search_result["request_id"] == summary_result["request_id"] == workflow_id


class TestProductionScenarios:
    """Test production-like scenarios with realistic workflows."""

    @pytest.mark.asyncio
    async def test_analyst_report_creation_workflow(self, config, report_service):
        """Test analyst workflow: create with analyst_v1 → add findings → update."""
        create_tool = CreateReportTool(config, report_service)
        evolve_tool = EvolveReportTool(config, report_service)

        # Analyst creates report
        create_result = await create_tool.execute(
            title="Q1 Network Analysis",
            template="analyst_v1",
            tags=["network", "q1", "2024"],
            description="Quarterly network performance analysis",
        )

        assert create_result["status"] == "success"
        report_id = create_result["report_id"]

        # Analyst adds key findings
        changes = {
            "insights_to_add": [
                {
                    "summary": "30% increase in transaction volume",
                    "importance": 9,
                },
                {
                    "summary": "15% reduction in average latency",
                    "importance": 6,
                },
            ],
        }

        evolve_result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Update report",
            proposed_changes=changes,
            constraints={"skip_citation_validation": True},
        )

        assert evolve_result["status"] == "success"
        assert len(evolve_result["insight_ids_added"]) == 2

        # Verify report state
        outline = report_service.get_report_outline(report_id)
        assert len(outline.insights) == 2

    @pytest.mark.asyncio
    async def test_parallel_report_creation(self, config, report_service):
        """Test creating multiple reports in parallel (different request_ids)."""
        create_tool = CreateReportTool(config, report_service)

        # Simulate parallel report creation by different users/workflows
        results = []

        for i in range(3):
            result = await create_tool.execute(
                title=f"Report {i + 1}",
                template="default",
                request_id=f"parallel-workflow-{i + 1}",
            )
            results.append(result)

        # All should succeed
        assert all(r["status"] == "success" for r in results)

        # All should have different request_ids
        request_ids = [r["request_id"] for r in results]
        assert len(set(request_ids)) == 3

        # All should have different report_ids
        report_ids = [r["report_id"] for r in results]
        assert len(set(report_ids)) == 3
