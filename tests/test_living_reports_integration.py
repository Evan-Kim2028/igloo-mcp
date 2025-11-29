"""Integration tests for complete Living Reports workflows."""

import uuid

import pytest

from igloo_mcp.config import get_config
from igloo_mcp.living_reports.models import Insight
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool
from igloo_mcp.mcp.tools.render_report import RenderReportTool


@pytest.mark.asyncio
async def test_full_lifecycle_create_evolve_render_revert(tmp_path, monkeypatch):
    """Test complete report lifecycle."""
    service = ReportService(reports_root=tmp_path / "reports")

    # 1. Create with template
    report_id = service.create_report("Q1 Report", template="quarterly_review")

    # Verify template was applied
    outline = service.get_report_outline(report_id)
    assert len(outline.sections) == 4
    assert outline.sections[0].title == "Executive Summary"

    # 2. Evolve - add insight
    evolve_tool = EvolveReportTool(get_config(), service)

    # Get first section ID to reference the insight
    outline = service.get_report_outline(report_id)
    first_section_id = outline.sections[0].section_id

    insight_id = str(uuid.uuid4())
    result = await evolve_tool.execute(
        report_selector=report_id,
        instruction="Add Q1 revenue insight",
        proposed_changes={
            "insights_to_add": [
                {
                    "insight_id": insight_id,
                    "importance": 9,
                    "summary": "Revenue up 25% YoY",
                    "supporting_queries": [],
                }
            ],
            # Reference the insight in a section
            "sections_to_modify": [
                {
                    "section_id": first_section_id,
                    "insight_ids_to_add": [insight_id],
                }
            ],
        },
        constraints={"skip_citation_validation": True},
    )
    assert result["status"] == "success"

    # Verify insight was added
    outline = service.get_report_outline(report_id)
    assert len(outline.insights) == 1
    assert outline.insights[0].insight_id == insight_id

    # Get action_id for revert
    storage = service.global_storage.get_report_storage(report_id)
    events = storage.load_audit_events()
    evolve_action_id = events[-1].action_id

    # 3. Render (dry run to avoid Quarto dependency)
    render_tool = RenderReportTool(get_config(), service)

    result = await render_tool.execute(
        report_selector=report_id,
        dry_run=True,
    )
    assert result["status"] == "success"

    # 4. Revert
    revert_result = service.revert_report(report_id, evolve_action_id)
    assert revert_result["success"] is True

    # Verify reverted state
    outline = service.get_report_outline(report_id)
    assert len(outline.insights) == 0  # Insight removed by revert


def test_bulk_operations_workflow(tmp_path):
    """Test bulk operations workflow."""
    service = ReportService(reports_root=tmp_path / "reports")

    # Create multiple reports
    report_ids = []
    for i in range(3):
        report_id = service.create_report(f"Report {i}", tags=["bulk_test"])
        report_ids.append(report_id)

    # Archive all reports
    for report_id in report_ids:
        service.archive_report(report_id)

    # Verify all archived
    reports = service.list_reports(status="archived")
    archived_ids = {r["id"] for r in reports}
    assert archived_ids >= set(report_ids)

    # Tag reports
    for report_id in report_ids[:2]:
        service.tag_report(report_id, tags_to_add=["selected"])

    # Verify tags
    selected_reports = service.list_reports(tags=["selected"])
    selected_ids = {r["id"] for r in selected_reports}
    assert selected_ids == set(report_ids[:2])

    # Delete one report
    trash_location = service.delete_report(report_ids[0])

    # Verify deleted
    reports = service.list_reports()
    remaining_ids = {r["id"] for r in reports}
    assert report_ids[0] not in remaining_ids
    assert report_ids[1] in remaining_ids
    assert report_ids[2] in remaining_ids

    # Verify trash location exists
    import os

    assert os.path.exists(trash_location)


def test_fork_and_synthesize_workflow(tmp_path):
    """Test fork and synthesize operations."""
    service = ReportService(reports_root=tmp_path / "reports")

    # Create base report with template (has sections)
    base_id = service.create_report("Base Report", template="monthly_sales")

    # Add content to base - reference insight in section
    outline = service.get_report_outline(base_id)
    insight_id = str(uuid.uuid4())
    outline.insights.append(
        Insight(
            insight_id=insight_id,
            importance=8,
            summary="Base insight",
            supporting_queries=[],
            status="active",
        )
    )
    outline.sections[0].insight_ids = [insight_id]  # Reference insight in section
    service.update_report_outline(base_id, outline)

    # Fork the report
    forked_id = service.fork_report(base_id, "Forked Report")

    # Verify fork
    forked_outline = service.get_report_outline(forked_id)
    assert forked_outline.title == "Forked Report"
    assert len(forked_outline.insights) == 1
    assert forked_outline.metadata["forked_from"] == base_id

    # Create another report for synthesis with template
    other_id = service.create_report("Other Report", template="deep_dive")
    other_outline = service.get_report_outline(other_id)
    other_insight_id = str(uuid.uuid4())
    other_outline.insights.append(
        Insight(
            insight_id=other_insight_id,
            importance=7,
            summary="Other insight",
            supporting_queries=[],
            status="active",
        )
    )
    other_outline.sections[0].insight_ids = [other_insight_id]  # Reference insight
    service.update_report_outline(other_id, other_outline)

    # Synthesize reports
    synth_id = service.synthesize_reports([base_id, other_id], "Combined Report")

    # Verify synthesis
    synth_outline = service.get_report_outline(synth_id)
    assert synth_outline.title == "Combined Report"
    assert len(synth_outline.insights) == 2
    assert set(synth_outline.metadata["synthesized_from"]) == {base_id, other_id}
    assert "synthesis_note" in synth_outline.metadata


def test_concurrent_agents_version_conflict(tmp_path):
    """Test version conflict detection with concurrent modifications."""
    service = ReportService(reports_root=tmp_path / "reports")

    report_id = service.create_report("Test Report")

    # Get initial outline to capture version
    outline1 = service.get_report_outline(report_id)
    initial_version = outline1.outline_version

    # Simulate concurrent modification
    outline2 = service.get_report_outline(report_id)
    outline2.title = "Modified by Agent 2"
    service.update_report_outline(report_id, outline2, actor="agent")

    # Try to update with stale version
    outline1.title = "Modified by Agent 1"

    with pytest.raises(ValueError, match="Version mismatch"):
        service.update_report_outline(report_id, outline1, actor="agent", expected_version=initial_version)


def test_template_to_advanced_workflow(tmp_path):
    """Test workflow from template creation through advanced operations."""
    service = ReportService(reports_root=tmp_path / "reports")

    # Start with template
    report_id = service.create_report("Template Report", template="deep_dive", tags=["template"])

    # Verify template structure
    outline = service.get_report_outline(report_id)
    assert len(outline.sections) == 3
    assert outline.sections[0].title == "Topic Overview"

    # Evolve by adding insights
    insight1_id = str(uuid.uuid4())
    insight2_id = str(uuid.uuid4())

    outline.insights.extend(
        [
            Insight(
                insight_id=insight1_id,
                importance=9,
                summary="Key finding 1",
                supporting_queries=[],
                status="active",
            ),
            Insight(
                insight_id=insight2_id,
                importance=7,
                summary="Key finding 2",
                supporting_queries=[],
                status="active",
            ),
        ]
    )

    # Link insights to sections
    outline.sections[1].insight_ids = [insight1_id]
    outline.sections[2].insight_ids = [insight2_id]

    service.update_report_outline(report_id, outline)

    # Fork for variation
    variant_id = service.fork_report(report_id, "Variant Report")

    # Modify variant
    variant_outline = service.get_report_outline(variant_id)
    variant_outline.sections[0].title = "Modified Overview"
    service.update_report_outline(variant_id, variant_outline)

    # Archive original
    service.archive_report(report_id)

    # Verify final state
    reports = service.list_reports()
    active_reports = [r for r in reports if r["status"] == "active"]
    archived_reports = [r for r in reports if r["status"] == "archived"]

    assert len(active_reports) == 1
    assert len(archived_reports) == 1
    assert active_reports[0]["title"] == "Variant Report"
    assert archived_reports[0]["title"] == "Template Report"


@pytest.mark.asyncio
async def test_mcp_tool_integration_workflow(tmp_path):
    """Test MCP tools working together in sequence."""
    service = ReportService(reports_root=tmp_path / "reports")
    evolve_tool = EvolveReportTool(get_config(), service)
    render_tool = RenderReportTool(get_config(), service)

    # Create report via service with a template that has sections
    report_id = service.create_report("MCP Test Report", template="monthly_sales")

    # Get a section ID to reference the insight
    outline = service.get_report_outline(report_id)
    section_id = outline.sections[0].section_id

    # Evolve via MCP tool - add insight and reference it in section
    insight_id = str(uuid.uuid4())
    result = await evolve_tool.execute(
        report_selector=report_id,
        instruction="Add test insight",
        proposed_changes={
            "insights_to_add": [
                {
                    "insight_id": insight_id,
                    "importance": 8,
                    "summary": "MCP-generated insight",
                    "supporting_queries": [],
                }
            ],
            "sections_to_modify": [
                {
                    "section_id": section_id,
                    "insight_ids_to_add": [insight_id],
                }
            ],
        },
        constraints={"skip_citation_validation": True},
    )
    assert result["status"] == "success"

    # Render via MCP tool
    result = await render_tool.execute(report_selector=report_id, dry_run=True)
    assert result["status"] == "success"

    # Verify final state
    outline = service.get_report_outline(report_id)
    assert len(outline.insights) == 1
    assert outline.insights[0].summary == "MCP-generated insight"


def test_error_recovery_workflow(tmp_path):
    """Test error detection and recovery workflows."""
    service = ReportService(reports_root=tmp_path / "reports")

    # Create report
    report_id = service.create_report("Error Test Report")

    # Make a change
    outline = service.get_report_outline(report_id)
    outline.title = "Modified Title"
    service.update_report_outline(report_id, outline)

    # Get action for revert
    storage = service.global_storage.get_report_storage(report_id)
    events = storage.load_audit_events()
    modify_action = events[-1]

    # Simulate backup corruption (delete backup file)
    backup_filename = modify_action.payload.get("backup_filename")
    if backup_filename:
        backup_path = storage.backups_dir / backup_filename
        if backup_path.exists():
            backup_path.unlink()

    # Attempt revert should fail
    with pytest.raises(ValueError, match="Backup file missing"):
        service.revert_report(report_id, modify_action.action_id)

    # Create new change (should succeed)
    outline = service.get_report_outline(report_id)
    outline.title = "Recovered Title"
    service.update_report_outline(report_id, outline)

    # Verify recovery
    outline = service.get_report_outline(report_id)
    assert outline.title == "Recovered Title"
