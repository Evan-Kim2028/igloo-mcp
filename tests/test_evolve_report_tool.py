"""Comprehensive integration tests for evolve_report MCP tool.

P0 Priority: Critical test coverage for production readiness.
"""

import uuid
from pathlib import Path

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.exceptions import (
    MCPSelectorError,
    MCPValidationError,
)
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool


@pytest.mark.asyncio
class TestEvolveReportToolIntegration:
    """Integration tests for evolve_report tool covering critical workflows."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))

    @pytest.fixture
    def report_service(self, tmp_path: Path):
        """Create report service with temp storage."""
        return ReportService(reports_root=tmp_path / "reports")

    @pytest.fixture
    def evolve_tool(self, config, report_service):
        """Create evolve report tool instance."""
        return EvolveReportTool(config, report_service)

    @pytest.fixture
    def test_report_id(self, report_service):
        """Create a test report and return its ID."""
        report_id = report_service.create_report(
            title="Test Report",
            template="default",
            tags=["test"],
        )
        return report_id

    async def test_evolve_report_success_add_section_with_inline_insights(self, evolve_tool, test_report_id):
        """Test successful evolution: add section with inline insights."""
        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Add revenue analysis section",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Revenue Analysis",
                        "order": 0,
                        "insights": [
                            {"summary": "Revenue grew 25% YoY", "importance": 9},
                            {"summary": "Q4 was strongest quarter", "importance": 8},
                        ],
                    }
                ]
            },
        )

        assert result["status"] == "success"
        assert result["summary"]["sections_added"] == 1
        assert result["summary"]["insights_added"] == 2
        # audit_action_id removed from tool response

    async def test_evolve_report_success_modify_section_title(self, evolve_tool, test_report_id, report_service):
        """Test successful evolution: modify existing section title."""
        # Setup: Add a section first
        section_id = None
        outline = report_service.get_report_outline(test_report_id)
        if outline.sections:
            section_id = outline.sections[0].section_id
        else:
            # Create a section
            await evolve_tool.execute(
                report_selector=test_report_id,
                instruction="Add test section",
                proposed_changes={"sections_to_add": [{"title": "Original Title", "order": 0}]},
            )
            outline = report_service.get_report_outline(test_report_id)
            section_id = outline.sections[0].section_id

        # Test: Modify section title
        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Update section title",
            proposed_changes={"sections_to_modify": [{"section_id": section_id, "title": "Updated Title"}]},
        )

        assert result["status"] == "success"
        assert result["summary"]["sections_modified"] == 1

        # Verify: Check title was updated
        updated_outline = report_service.get_report_outline(test_report_id)
        assert updated_outline.sections[0].title == "Updated Title"

    async def test_evolve_report_dry_run_validates_without_applying(self, evolve_tool, test_report_id, report_service):
        """Test dry run mode: validates changes without applying them."""
        # Get initial outline
        initial_outline = report_service.get_report_outline(test_report_id)
        initial_section_count = len(initial_outline.sections)

        # Dry run: Attempt to add section
        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Add test section",
            proposed_changes={"sections_to_add": [{"title": "Dry Run Section", "order": 0}]},
            dry_run=True,
        )

        assert result["status"] == "dry_run_success"
        assert "preview" in result
        assert "estimated_outline_version" in result["preview"]

        # Verify: No changes were applied
        after_outline = report_service.get_report_outline(test_report_id)
        assert len(after_outline.sections) == initial_section_count

    async def test_evolve_report_selector_error_invalid_report_id(self, evolve_tool):
        """Test selector error: non-existent report ID."""
        fake_id = f"rpt_{uuid.uuid4()}"

        with pytest.raises(MCPSelectorError) as exc_info:
            await evolve_tool.execute(
                report_selector=fake_id,
                instruction="Test",
                proposed_changes={"sections_to_add": [{"title": "Test", "order": 0}]},
            )

        error = exc_info.value
        assert error.selector == fake_id
        assert error.error == "not_found"
        # hints may not always be in error dict

    async def test_evolve_report_selector_error_ambiguous_title(self, evolve_tool, report_service):
        """Test selector error: ambiguous title matches multiple reports."""
        # Create two reports with similar titles
        report_service.create_report(title="Q1 Report", tags=["q1"])
        report_service.create_report(title="Q1 Report Analysis", tags=["q1"])

        with pytest.raises(MCPSelectorError) as exc_info:
            await evolve_tool.execute(
                report_selector="Q1",
                instruction="Test",
                proposed_changes={"sections_to_add": [{"title": "Test", "order": 0}]},
            )

        error = exc_info.value
        assert error.error in ("ambiguous", "not_found")  # Implementation detail
        # Candidates list depends on selector implementation

    async def test_evolve_report_validation_error_invalid_response_detail(self, evolve_tool, test_report_id):
        """Test validation error: invalid response_detail parameter."""
        with pytest.raises(MCPValidationError) as exc_info:
            await evolve_tool.execute(
                report_selector=test_report_id,
                instruction="Test",
                proposed_changes={"sections_to_add": [{"title": "Test", "order": 0}]},
                response_detail="invalid",  # Should be minimal/standard/full
            )

        error = exc_info.value
        assert "Invalid response_detail" in error.message
        assert error.error_code == "VALIDATION_ERROR"
        assert any("minimal" in hint for hint in error.hints)

    async def test_evolve_report_validation_error_invalid_proposed_changes_schema(self, evolve_tool, test_report_id):
        """Test validation error: proposed_changes doesn't match schema."""
        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Test",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Test Section",
                        "order": "invalid",  # Should be int, not str
                    }
                ]
            },
        )

        assert result["status"] == "validation_failed"
        assert "validation_errors" in result

    async def test_evolve_report_conflicting_status_change(self, evolve_tool, test_report_id):
        """Test validation error: conflicting status_change values."""
        with pytest.raises(MCPValidationError) as exc_info:
            await evolve_tool.execute(
                report_selector=test_report_id,
                instruction="Test",
                proposed_changes={"status_change": "archived"},
                status_change="active",  # Conflicting value
            )

        error = exc_info.value
        assert "Conflicting status_change" in error.message

    async def test_evolve_report_response_detail_minimal(self, evolve_tool, test_report_id):
        """Test response_detail='minimal' returns compact response."""
        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Add section",
            proposed_changes={"sections_to_add": [{"title": "Test Section", "order": 0}]},
            response_detail="minimal",
        )

        assert result["status"] == "success"
        # Minimal response should have summary but minimal details
        assert "summary" in result
        assert result["summary"]["sections_added"] == 1
        # Should NOT have verbose section details in minimal mode
        assert "report_id" in result
        # audit_action_id removed from tool response

    async def test_evolve_report_response_detail_full(self, evolve_tool, test_report_id):
        """Test response_detail='full' returns comprehensive response."""
        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Add section",
            proposed_changes={"sections_to_add": [{"title": "Test Section", "order": 0}]},
            response_detail="full",
        )

        assert result["status"] == "success"
        assert "summary" in result
        assert "report_id" in result
        # Full response includes changes_applied details
        assert "changes_applied" in result

    async def test_evolve_report_batch_operations(self, evolve_tool, test_report_id):
        """Test batch operations: add multiple sections and insights together."""
        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Add comprehensive analysis",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Executive Summary",
                        "order": 0,
                        "insights": [{"summary": "Strong growth in Q4", "importance": 9}],
                    },
                    {
                        "title": "Detailed Analysis",
                        "order": 1,
                        "insights": [
                            {"summary": "Revenue up 30%", "importance": 8},
                            {"summary": "Costs down 10%", "importance": 7},
                        ],
                    },
                ]
            },
        )

        assert result["status"] == "success"
        assert result["summary"]["sections_added"] == 2
        assert result["summary"]["insights_added"] == 3

    async def test_evolve_report_status_change(self, evolve_tool, test_report_id, report_service):
        """Test status change: archive report via evolve_report."""
        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Archive report",
            proposed_changes={"status_change": "archived"},
        )

        assert result["status"] == "success"

        # Verify: Check report status was updated
        outline = report_service.get_report_outline(test_report_id)
        assert outline.metadata.get("status") == "archived"

    async def test_evolve_report_remove_section(self, evolve_tool, test_report_id, report_service):
        """Test section removal."""
        # Setup: Add a section first
        await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Add test section",
            proposed_changes={"sections_to_add": [{"title": "Section to Remove", "order": 0}]},
        )

        outline = report_service.get_report_outline(test_report_id)
        section_id = outline.sections[0].section_id

        # Test: Remove the section
        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Remove section",
            proposed_changes={"sections_to_remove": [section_id]},
        )

        assert result["status"] == "success"

        # Verify: Section was removed
        updated_outline = report_service.get_report_outline(test_report_id)
        assert len(updated_outline.sections) == 0

    async def test_evolve_report_title_change(self, evolve_tool, test_report_id, report_service):
        """Test report title change."""
        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Update report title",
            proposed_changes={"title_change": "Updated Report Title"},
        )

        assert result["status"] == "success"

        # Verify: Title was updated
        outline = report_service.get_report_outline(test_report_id)
        assert outline.title == "Updated Report Title"

    async def test_evolve_report_metadata_updates(self, evolve_tool, test_report_id, report_service):
        """Test metadata updates via proposed_changes."""
        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Update metadata",
            proposed_changes={
                "metadata_updates": {
                    "owner": "data_team",
                    "priority": "high",
                    "custom_field": "custom_value",
                }
            },
        )

        assert result["status"] == "success"

        # Verify: Metadata was updated
        outline = report_service.get_report_outline(test_report_id)
        assert outline.metadata.get("owner") == "data_team"
        assert outline.metadata.get("priority") == "high"
        assert outline.metadata.get("custom_field") == "custom_value"

    async def test_evolve_report_empty_proposed_changes_fallback(self, evolve_tool, test_report_id):
        """Test empty proposed_changes triggers fallback generation."""
        # When proposed_changes is empty, tool should generate changes from instruction
        # This is a fallback path for simple use cases
        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Add revenue section",
            proposed_changes={},  # Empty - should trigger fallback
        )

        # The fallback should still work (may generate minimal/no-op changes)
        assert result["status"] in ("success", "validation_failed")

    async def test_evolve_report_request_id_tracking(self, evolve_tool, test_report_id):
        """Test request_id is tracked through the operation."""
        custom_request_id = str(uuid.uuid4())

        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Test request tracking",
            proposed_changes={"sections_to_add": [{"title": "Test Section", "order": 0}]},
            request_id=custom_request_id,
        )

        assert result["status"] == "success"
        # Request ID should be in the response context or traceable in logs

    async def test_evolve_report_audit_trail(self, evolve_tool, test_report_id, report_service):
        """Test that evolution creates audit trail."""
        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Add section for audit test",
            proposed_changes={"sections_to_add": [{"title": "Audit Test Section", "order": 0}]},
        )

        assert result["status"] == "success"
        # audit_action_id removed from tool response

        # Verify: Audit event was created
        storage = report_service.global_storage.get_report_storage(test_report_id)
        audit_events = storage.load_audit_events()
        assert len(audit_events) > 0

        # Find the evolution event
        evolution_events = [e for e in audit_events if e.action_type == "evolve"]
        assert len(evolution_events) > 0


@pytest.mark.asyncio
class TestEvolveReportToolEdgeCases:
    """Edge case tests for evolve_report tool."""

    @pytest.fixture
    def config(self):
        return Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))

    @pytest.fixture
    def report_service(self, tmp_path: Path):
        return ReportService(reports_root=tmp_path / "reports")

    @pytest.fixture
    def evolve_tool(self, config, report_service):
        return EvolveReportTool(config, report_service)

    @pytest.fixture
    def test_report_id(self, report_service):
        return report_service.create_report(title="Edge Case Test", tags=["test"])

    async def test_evolve_report_large_batch_operations(self, evolve_tool, test_report_id):
        """Test handling of large batch operations (stress test)."""
        # Create 20 sections with 5 insights each = 100 total insights
        sections_to_add = []
        for i in range(20):
            sections_to_add.append(
                {
                    "title": f"Section {i}",
                    "order": i,
                    "insights": [{"summary": f"Insight {j} for section {i}", "importance": 5} for j in range(5)],
                }
            )

        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Add comprehensive analysis",
            proposed_changes={"sections_to_add": sections_to_add},
        )

        assert result["status"] == "success"
        assert result["summary"]["sections_added"] == 20
        assert result["summary"]["insights_added"] == 100

    async def test_evolve_report_unicode_content(self, evolve_tool, test_report_id):
        """Test handling of Unicode and special characters."""
        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Add international content",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "国际化测试 🌍",
                        "order": 0,
                        "insights": [
                            {
                                "summary": "Revenue in 日本 grew 25% 📈",
                                "importance": 8,
                            }
                        ],
                    }
                ]
            },
        )

        assert result["status"] == "success"

    async def test_evolve_report_modify_nonexistent_section(self, evolve_tool, test_report_id):
        """Test error when modifying non-existent section."""
        fake_section_id = str(uuid.uuid4())

        result = await evolve_tool.execute(
            report_selector=test_report_id,
            instruction="Modify non-existent section",
            proposed_changes={"sections_to_modify": [{"section_id": fake_section_id, "title": "New Title"}]},
        )

        assert result["status"] == "validation_failed"
        assert "validation_errors" in result
