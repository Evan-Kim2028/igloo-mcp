"""Integration tests for complete LLM evolution workflow.

This module tests the end-to-end workflow that LLMs would follow when evolving reports:
1. Discovery phase (dry run to understand structure)
2. Generation phase (LLM creates proposed changes)
3. Application phase (changes are validated and applied)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from igloo_mcp.config import Config
from igloo_mcp.living_reports.models import DatasetSource, Insight, Outline, Section
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool


class TestLLMEvolutionWorkflow:
    """Test complete LLM evolution workflows."""

    @pytest.fixture
    def temp_reports_dir(self) -> Path:
        """Create temporary reports directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir) / "reports"
            reports_dir.mkdir()
            yield reports_dir

    @pytest.fixture
    def config(self) -> Config:
        """Create test config."""
        return Config.from_env()

    @pytest.fixture
    def report_service(self, temp_reports_dir: Path) -> ReportService:
        """Create test report service."""
        return ReportService(temp_reports_dir)

    @pytest.fixture
    def tool(self, config: Config, report_service: ReportService) -> EvolveReportTool:
        """Create test tool instance."""
        return EvolveReportTool(config=config, report_service=report_service)

    @pytest.fixture
    def initial_report(self, report_service: ReportService) -> str:
        """Create initial report with sample data."""
        report_id = report_service.create_report("Revenue Analysis Q1")

        # Create initial outline with basic structure
        initial_outline = Outline(
            title="Revenue Analysis Q1",
            report_id=report_id,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            insights=[
                Insight(
                    insight_id="550e8400-e29b-41d4-a716-446655440010",
                    summary="Q1 revenue shows 15% YoY growth",
                    importance=8,
                    supporting_queries=[DatasetSource(execution_id="exec_rev_q1")],
                ),
                Insight(
                    insight_id="550e8400-e29b-41d4-a716-446655440011",
                    summary="Customer base expanded by 23%",
                    importance=7,
                    supporting_queries=[DatasetSource(execution_id="exec_cust_q1")],
                ),
            ],
            sections=[
                Section(
                    section_id="550e8400-e29b-41d4-a716-446655440012",
                    title="Executive Summary",
                    notes="High-level revenue overview",
                    order=1,
                    insight_ids=["550e8400-e29b-41d4-a716-446655440010"],
                ),
                Section(
                    section_id="550e8400-e29b-41d4-a716-446655440013",
                    title="Customer Metrics",
                    notes="Customer acquisition and retention",
                    order=2,
                    insight_ids=["550e8400-e29b-41d4-a716-446655440011"],
                ),
            ],
        )

        report_service.update_report_outline(report_id, initial_outline, actor="test")
        return report_id

    @pytest.mark.asyncio
    async def test_llm_discovery_workflow(
        self, tool: EvolveReportTool, initial_report: str
    ):
        """Test LLM discovery phase - understanding report structure."""
        # Step 1: LLM performs discovery (dry run with empty changes)
        discovery_result = await tool.execute(
            report_selector=initial_report,
            instruction="Analyze current report structure to understand what insights and sections exist",
            proposed_changes={},  # Empty for discovery
            dry_run=True,
        )

        # Verify discovery succeeded
        assert discovery_result["status"] == "dry_run_success"
        assert discovery_result["report_id"] == initial_report
        assert discovery_result["validation_passed"] is True

        # Verify no changes were applied
        current_outline = tool.report_service.get_report_outline(initial_report)
        assert len(current_outline.insights) == 2
        assert len(current_outline.sections) == 2

    @pytest.mark.asyncio
    async def test_llm_evolution_workflow_add_insights(
        self, tool: EvolveReportTool, initial_report: str
    ):
        """Test complete LLM workflow: discover → generate → apply (adding insights)."""
        # Phase 1: Discovery (already tested above)

        # Phase 2: LLM generates changes based on analysis
        generated_changes = {
            "insights_to_add": [
                {
                    "insight_id": "550e8400-e29b-41d4-a716-446655440014",
                    "summary": "Customer churn rate decreased by 12% QoQ",
                    "importance": 9,
                    "status": "active",
                    "supporting_queries": [{"execution_id": "exec_churn_q1"}],
                },
                {
                    "insight_id": "550e8400-e29b-41d4-a716-446655440015",
                    "summary": "Market share increased to 18.5% in key segments",
                    "importance": 6,
                    "status": "active",
                    "supporting_queries": [{"execution_id": "exec_market_q1"}],
                },
            ],
            "sections_to_modify": [
                {
                    "section_id": "550e8400-e29b-41d4-a716-446655440013",
                    "insight_ids_to_add": [
                        "550e8400-e29b-41d4-a716-446655440014",
                        "550e8400-e29b-41d4-a716-446655440015",
                    ],
                }
            ],
        }

        # Phase 3: Apply changes
        evolution_result = await tool.execute(
            report_selector=initial_report,
            instruction="Add churn analysis and market share insights to customer metrics section",
            proposed_changes=generated_changes,
            dry_run=False,
        )

        # Verify evolution succeeded
        assert evolution_result["status"] == "success"
        assert evolution_result["report_id"] == initial_report
        assert evolution_result["changes_applied"] == generated_changes
        assert "outline_version" in evolution_result

        # Verify changes were applied correctly
        updated_outline = tool.report_service.get_report_outline(initial_report)
        assert len(updated_outline.insights) == 4  # 2 original + 2 new

        # Check new insights exist
        new_insight_ids = {i.insight_id for i in updated_outline.insights}
        assert "550e8400-e29b-41d4-a716-446655440014" in new_insight_ids
        assert "550e8400-e29b-41d4-a716-446655440015" in new_insight_ids

        # Check section was updated
        customer_section = next(
            s
            for s in updated_outline.sections
            if s.section_id == "550e8400-e29b-41d4-a716-446655440013"
        )
        assert "550e8400-e29b-41d4-a716-446655440014" in customer_section.insight_ids
        assert "550e8400-e29b-41d4-a716-446655440015" in customer_section.insight_ids

    @pytest.mark.asyncio
    async def test_llm_evolution_workflow_restructure(
        self, tool: EvolveReportTool, initial_report: str
    ):
        """Test complete LLM workflow: discover → generate → apply (restructuring)."""
        # Phase 2: LLM generates restructuring changes
        restructure_changes = {
            "sections_to_add": [
                {
                    "section_id": "550e8400-e29b-41d4-a716-446655440016",
                    "title": "Key Findings",
                    "order": 1,
                    "notes": "Most important insights and trends",
                    "insight_ids": [
                        "550e8400-e29b-41d4-a716-446655440010",
                        "550e8400-e29b-41d4-a716-446655440011",
                    ],
                }
            ],
            "sections_to_modify": [
                {
                    "section_id": "550e8400-e29b-41d4-a716-446655440012",
                    "title": "Executive Summary - Detailed",
                    "insight_ids_to_remove": ["550e8400-e29b-41d4-a716-446655440010"],
                },
                {
                    "section_id": "550e8400-e29b-41d4-a716-446655440013",
                    "order": 3,
                    "insight_ids_to_remove": ["550e8400-e29b-41d4-a716-446655440011"],
                },
            ],
        }

        # Phase 3: Apply restructuring
        restructure_result = await tool.execute(
            report_selector=initial_report,
            instruction="Restructure report with key findings section and reorganize insights",
            proposed_changes=restructure_changes,
            dry_run=False,
        )

        # Verify restructuring succeeded
        assert restructure_result["status"] == "success"

        # Verify structure changes
        updated_outline = tool.report_service.get_report_outline(initial_report)

        # Check new section exists
        key_findings = next(
            (
                s
                for s in updated_outline.sections
                if s.section_id == "550e8400-e29b-41d4-a716-446655440016"
            ),
            None,
        )
        assert key_findings is not None
        assert key_findings.title == "Key Findings"
        assert key_findings.order == 1
        assert set(key_findings.insight_ids) == {
            "550e8400-e29b-41d4-a716-446655440010",
            "550e8400-e29b-41d4-a716-446655440011",
        }

        # Check modified sections
        exec_summary = next(
            s
            for s in updated_outline.sections
            if s.section_id == "550e8400-e29b-41d4-a716-446655440012"
        )
        assert exec_summary.title == "Executive Summary - Detailed"
        assert "550e8400-e29b-41d4-a716-446655440010" not in exec_summary.insight_ids

        customer_metrics = next(
            s
            for s in updated_outline.sections
            if s.section_id == "550e8400-e29b-41d4-a716-446655440013"
        )
        assert customer_metrics.order == 3
        assert (
            "550e8400-e29b-41d4-a716-446655440011" not in customer_metrics.insight_ids
        )

    @pytest.mark.asyncio
    async def test_llm_evolution_workflow_validation_failure(
        self, tool: EvolveReportTool, initial_report: str
    ):
        """Test LLM workflow with validation failure (invalid changes)."""
        # Generate invalid changes (duplicate insight ID)
        invalid_changes = {
            "insights_to_add": [
                {
                    "insight_id": "550e8400-e29b-41d4-a716-446655440010",  # Already exists!
                    "summary": "This will fail validation",
                    "importance": 5,
                    "status": "active",
                    "supporting_queries": [],
                }
            ]
        }

        # Attempt to apply invalid changes
        failure_result = await tool.execute(
            report_selector=initial_report,
            instruction="Attempt to add insight with duplicate ID",
            proposed_changes=invalid_changes,
            dry_run=False,
        )

        # Verify validation failed
        assert failure_result["status"] == "validation_failed"
        assert failure_result["error_type"] == "semantic_validation"
        assert len(failure_result["validation_errors"]) > 0
        assert "already exists" in str(failure_result["validation_errors"])

        # Verify no changes were applied
        current_outline = tool.report_service.get_report_outline(initial_report)
        assert len(current_outline.insights) == 2  # Original count unchanged

    @pytest.mark.asyncio
    async def test_llm_workflow_with_dry_run_validation(
        self, tool: EvolveReportTool, initial_report: str
    ):
        """Test LLM workflow using dry run to validate before applying."""
        # Step 1: Dry run validation of proposed changes
        proposed_changes = {
            "insights_to_add": [
                {
                    "insight_id": "550e8400-e29b-41d4-a716-446655440016",
                    "summary": "Profit margins improved by 3.2% this quarter",
                    "importance": 8,
                    "status": "active",
                    "supporting_queries": [{"execution_id": "exec_profit_q1"}],
                }
            ],
            "sections_to_modify": [
                {
                    "section_id": "550e8400-e29b-41d4-a716-446655440012",
                    "insight_ids_to_add": ["550e8400-e29b-41d4-a716-446655440016"],
                }
            ],
        }

        # Dry run validation
        dry_run_result = await tool.execute(
            report_selector=initial_report,
            instruction="Validate profit margin insight addition",
            proposed_changes=proposed_changes,
            dry_run=True,
        )

        assert dry_run_result["status"] == "dry_run_success"
        assert dry_run_result["validation_passed"] is True

        # Step 2: Apply validated changes
        apply_result = await tool.execute(
            report_selector=initial_report,
            instruction="Apply validated profit margin insight",
            proposed_changes=proposed_changes,
            dry_run=False,
        )

        assert apply_result["status"] == "success"

        # Verify final state
        final_outline = tool.report_service.get_report_outline(initial_report)
        assert len(final_outline.insights) == 3

        profit_insight = next(
            i
            for i in final_outline.insights
            if i.insight_id == "550e8400-e29b-41d4-a716-446655440016"
        )
        assert profit_insight.summary == "Profit margins improved by 3.2% this quarter"
        assert profit_insight.importance == 8
