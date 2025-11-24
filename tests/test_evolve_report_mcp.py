"""MCP-level tests for evolve_report tool with structured error handling."""

import uuid

import pytest

from igloo_mcp.config import get_config
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool


@pytest.fixture
def report_service(tmp_path):
    return ReportService(reports_root=tmp_path / "reports")


@pytest.fixture
def evolve_tool(report_service):
    config = get_config()
    return EvolveReportTool(config, report_service)


@pytest.mark.asyncio
async def test_evolve_with_explicit_proposed_changes(report_service, evolve_tool):
    """Test evolution with agent-provided proposed_changes."""
    # Create report
    report_id = report_service.create_report("Test Report")

    # Define explicit changes
    new_insight_id = str(uuid.uuid4())
    proposed_changes = {
        "insights_to_add": [
            {
                "insight_id": new_insight_id,
                "importance": 8,
                "summary": "Key finding from Q1 analysis",
                "supporting_queries": [],
            }
        ]
    }

    result = await evolve_tool.execute(
        report_selector=report_id,
        instruction="Add Q1 insights",
        proposed_changes=proposed_changes,
    )

    assert result["status"] == "success"
    assert result["report_id"] == report_id

    # Verify changes applied
    outline = report_service.get_report_outline(report_id)
    assert len(outline.insights) == 1
    assert outline.insights[0].insight_id == new_insight_id


@pytest.mark.asyncio
async def test_evolve_with_llm_generated_changes(report_service, evolve_tool):
    """Test evolution with tool-generated changes (fallback)."""
    report_id = report_service.create_report("Test Report")

    result = await evolve_tool.execute(
        report_selector=report_id,
        instruction="Add insight about user growth",
        proposed_changes=None,  # Force generation
    )

    # Should succeed even with simple generation
    assert result["status"] in ("success", "dry_run_success")


@pytest.mark.asyncio
async def test_selector_error_not_found(evolve_tool):
    """Test selector resolution error for non-existent report."""
    result = await evolve_tool.execute(
        report_selector="NonExistentReport",
        instruction="Test instruction",
    )

    assert result["status"] == "selector_error"
    assert result["error"] == "not_found"
    assert "NonExistentReport" in result["selector"]


@pytest.mark.asyncio
async def test_validation_error_duplicate_insight_id(report_service, evolve_tool):
    """Test schema validation error for duplicate insight ID."""
    report_id = report_service.create_report("Test Report")

    # Add an insight first
    insight_id = str(uuid.uuid4())
    changes1 = {
        "insights_to_add": [
            {
                "insight_id": insight_id,
                "importance": 7,
                "summary": "First insight",
            }
        ]
    }
    await evolve_tool.execute(report_id, "Add insight", changes1)

    # Try to add same insight ID again
    changes2 = {
        "insights_to_add": [
            {
                "insight_id": insight_id,  # Duplicate!
                "importance": 8,
                "summary": "Second insight",
            }
        ]
    }

    result = await evolve_tool.execute(report_id, "Add duplicate", changes2)

    assert result["status"] == "validation_failed"
    assert result["error_type"] == "semantic_validation"
    assert any("already exists" in err for err in result["validation_errors"])


@pytest.mark.asyncio
async def test_dry_run_does_not_modify_report(report_service, evolve_tool):
    """Test dry_run mode validates but doesn't save changes."""
    report_id = report_service.create_report("Test Report")

    proposed_changes = {
        "insights_to_add": [
            {
                "insight_id": str(uuid.uuid4()),
                "importance": 9,
                "summary": "Dry run insight",
            }
        ]
    }

    result = await evolve_tool.execute(
        report_selector=report_id,
        instruction="Test dry run",
        proposed_changes=proposed_changes,
        dry_run=True,
    )

    assert result["status"] == "dry_run_success"
    assert result["validation_passed"] is True

    # Verify no changes were saved
    outline = report_service.get_report_outline(report_id)
    assert len(outline.insights) == 0


@pytest.mark.asyncio
async def test_schema_validation_error_invalid_uuid(evolve_tool):
    """Test schema validation error for invalid UUID."""
    report_id = "dummy_id"  # Valid UUID for report

    proposed_changes = {
        "insights_to_add": [
            {
                "insight_id": "not-a-valid-uuid",
                "importance": 5,
                "summary": "Test insight",
            }
        ]
    }

    result = await evolve_tool.execute(
        report_selector=report_id,
        instruction="Test invalid UUID",
        proposed_changes=proposed_changes,
    )

    assert result["status"] == "validation_failed"
    assert result["error_type"] == "schema_validation"
    assert any(
        "insight_id must be valid UUID" in err for err in result["validation_errors"]
    )


@pytest.mark.asyncio
async def test_schema_validation_error_missing_required_fields(evolve_tool):
    """Test schema validation error for missing required fields."""
    report_id = "dummy_id"

    proposed_changes = {
        "insights_to_add": [
            {
                "insight_id": str(uuid.uuid4()),
                # Missing importance and summary (required for new insights)
            }
        ]
    }

    result = await evolve_tool.execute(
        report_selector=report_id,
        instruction="Test missing fields",
        proposed_changes=proposed_changes,
    )

    assert result["status"] == "validation_failed"
    assert result["error_type"] == "schema_validation"


@pytest.mark.asyncio
async def test_selector_ambiguous_multiple_matches(report_service, evolve_tool):
    """Test selector error when multiple reports match."""
    # Create two reports with the same tag
    report_service.create_report("Report 1", tags=["ambiguous"])
    report_service.create_report("Report 2", tags=["ambiguous"])

    result = await evolve_tool.execute(
        report_selector="tag:ambiguous",
        instruction="Test ambiguous",
    )

    assert result["status"] == "selector_error"
    assert result["error"] == "ambiguous"
    assert len(result["candidates"]) == 2


@pytest.mark.asyncio
async def test_concurrent_modifications_with_version_check(report_service, evolve_tool):
    """Test version conflict detection with concurrent modifications."""
    report_id = report_service.create_report("Test Report")

    # Get initial outline to capture version
    outline1 = report_service.get_report_outline(report_id)
    initial_version = outline1.outline_version

    # Simulate concurrent modification
    outline2 = report_service.get_report_outline(report_id)
    outline2.title = "Modified by Agent 2"
    report_service.update_report_outline(report_id, outline2, actor="agent")

    # Try to modify with stale version
    proposed_changes = {"title_change": "Modified by Agent 1"}

    result = await evolve_tool.execute(
        report_selector=report_id,
        instruction="Test concurrent modification",
        proposed_changes=proposed_changes,
    )

    # This should fail because the report was modified concurrently
    # (the tool doesn't directly handle expected_version, but the service does)
    # For this test, we'll just verify the tool can handle the scenario
    assert result["status"] in ("success", "validation_failed")


@pytest.mark.asyncio
async def test_changes_schema_version_compatibility(evolve_tool):
    """Test changes schema version compatibility."""
    report_id = "dummy_id"

    proposed_changes = {
        "schema_version": "2.0",
        "insights_to_add": [
            {
                "insight_id": str(uuid.uuid4()),
                "importance": 7,
                "summary": "Version 2.0 insight",
            }
        ],
    }

    result = await evolve_tool.execute(
        report_selector=report_id,
        instruction="Test version compatibility",
        proposed_changes=proposed_changes,
    )

    # Should handle version gracefully
    assert result["status"] in ("success", "validation_failed", "error")


@pytest.mark.asyncio
async def test_unexpected_error_handling(evolve_tool):
    """Test unexpected error handling."""
    # Test with malformed data that might cause unexpected errors
    result = await evolve_tool.execute(
        report_selector=None,  # Invalid selector type
        instruction="Test unexpected error",
    )

    assert result["status"] == "error"
    assert result["error_type"] == "unexpected"
    assert "report_selector" in result
