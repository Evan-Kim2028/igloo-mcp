"""Regression tests for v0.3.3 bug fixes.

This module contains regression tests for all bugs fixed in v0.3.3 to ensure
they don't reoccur in future releases.

Related issues:
- #89: Citation enforcement should apply to all templates, not just analyst_v1
- #88: title_change and metadata_updates not applied in _apply_changes
"""

from pathlib import Path

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool


class TestBug89CitationEnforcement:
    """Regression tests for #89 - Citation enforcement for all templates."""

    @pytest.mark.asyncio
    async def test_citation_enforcement_for_default_template(self, tmp_path: Path):
        """Citations are required for default template reports."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        # Create report with default template
        report_service.create_report(title="Test Report", template="default")

        # Attempt to add insight without citations
        changes = {
            "insights_to_add": [
                {
                    "section_title": "Analysis",
                    "summary": "Revenue is $100M",
                    "content": "Detailed analysis...",
                    "importance": 8,
                    "tags": ["revenue"],
                    # NO citations field
                }
            ]
        }

        # Should return validation_failed
        result = await tool.execute(report_selector="Test Report", instruction="", proposed_changes=changes)

        assert result["status"] == "validation_failed"
        assert "validation_issues" in result or "validation_errors" in result
        validation_errors = result.get("validation_issues") or result.get("validation_errors", [])
        error_text = " ".join(str(e).lower() for e in validation_errors)
        assert "citation" in error_text
        assert "execution_id" in error_text

    @pytest.mark.asyncio
    async def test_citation_enforcement_for_analyst_template(self, tmp_path: Path):
        """Citations still required for analyst_v1 template (backward compatibility)."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        # Create report with analyst template
        report_service.create_report(title="Analyst Report", template="analyst_v1")

        # Attempt to add insight without citations
        changes = {
            "insights_to_add": [
                {
                    "section_title": "Findings",
                    "summary": "Transaction volume increased 34%",
                    "content": "Analysis...",
                    "importance": 9,
                    "tags": ["metrics"],
                    # NO citations field
                }
            ]
        }

        # Should return validation_failed
        result = await tool.execute(report_selector="Analyst Report", instruction="", proposed_changes=changes)

        assert result["status"] == "validation_failed"
        assert "validation_issues" in result or "validation_errors" in result
        validation_errors = result.get("validation_issues") or result.get("validation_errors", [])
        error_text = " ".join(str(e).lower() for e in validation_errors)
        assert "citation" in error_text

    @pytest.mark.asyncio
    async def test_citation_enforcement_can_be_disabled(self, tmp_path: Path):
        """Citation validation can be explicitly disabled via constraints."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        report_service.create_report(title="Test Report", template="default")

        changes = {
            "insights_to_add": [
                {
                    "section_title": "Draft",
                    "summary": "Placeholder insight",
                    "content": "TBD",
                    "importance": 1,
                    "tags": ["draft"],
                    # NO citations
                }
            ]
        }

        # Should succeed when validation is disabled
        result = await tool.execute(
            report_selector="Test Report",
            instruction="",
            proposed_changes=changes,
            constraints={"skip_citation_validation": True},
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_insights_with_citations_succeed(self, tmp_path: Path):
        """Insights with proper citations are accepted."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        report_id = report_service.create_report(title="Test Report", template="default")

        changes = {
            "insights_to_add": [
                {
                    "section_title": "Revenue Analysis",
                    "summary": "Q4 revenue reached $50M",
                    "content": "Detailed breakdown...",
                    "importance": 10,
                    "tags": ["revenue", "q4"],
                    "citations": [{"source": "query", "execution_id": "abc123-def456-789"}],
                }
            ]
        }

        # Should succeed with citations
        result = await tool.execute(report_selector="Test Report", instruction="", proposed_changes=changes)

        assert result["status"] == "success"
        # Check that insight was added
        outline = report_service.get_report_outline(report_id)
        assert len(outline.insights) == 1
        assert outline.insights[0].summary == "Q4 revenue reached $50M"


class TestBug88MetadataUpdates:
    """Regression tests for #88 - title_change and metadata_updates not applied."""

    @pytest.mark.asyncio
    async def test_title_change_applied(self, tmp_path: Path):
        """title_change is applied to report."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        # Create report
        report_id = report_service.create_report(title="Old Title", template="default")
        original_title = "Old Title"

        # Change title
        result = await tool.execute(
            report_selector="Old Title",
            instruction="",
            proposed_changes={"title_change": "New Title"},
        )

        assert result["status"] == "success"

        # Verify title changed
        updated_outline = report_service.get_report_outline(report_id)
        assert updated_outline.title == "New Title"
        assert updated_outline.title != original_title

    @pytest.mark.asyncio
    async def test_metadata_updates_applied(self, tmp_path: Path):
        """metadata_updates are merged into report metadata."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        # Create report with initial metadata
        report_id = report_service.create_report(title="Test Report", template="default")

        # Add some initial metadata
        await tool.execute(
            report_selector="Test Report",
            instruction="",
            proposed_changes={"metadata_updates": {"original_key": "original_value"}},
        )

        # Update metadata with new keys
        result = await tool.execute(
            report_selector="Test Report",
            instruction="",
            proposed_changes={
                "metadata_updates": {
                    "new_key": "new_value",
                    "custom_status": "in_progress",
                }
            },
        )

        assert result["status"] == "success"

        # Verify metadata updated
        updated_outline = report_service.get_report_outline(report_id)
        assert updated_outline.metadata["new_key"] == "new_value"
        assert updated_outline.metadata["custom_status"] == "in_progress"
        assert updated_outline.metadata["original_key"] == "original_value"  # Preserved

    @pytest.mark.asyncio
    async def test_title_and_metadata_updates_together(self, tmp_path: Path):
        """title_change and metadata_updates can be applied simultaneously."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        report_id = report_service.create_report(title="Old Title", template="default")

        result = await tool.execute(
            report_selector="Old Title",
            instruction="",
            proposed_changes={
                "title_change": "New Title",
                "metadata_updates": {"author": "Claude", "version": "2.0"},
            },
        )

        assert result["status"] == "success"

        # Verify both changes applied
        updated_outline = report_service.get_report_outline(report_id)
        assert updated_outline.title == "New Title"
        assert updated_outline.metadata["author"] == "Claude"
        assert updated_outline.metadata["version"] == "2.0"

    @pytest.mark.asyncio
    async def test_outline_version_incremented_on_metadata_change(self, tmp_path: Path):
        """Outline version increments when metadata is updated."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        report_id = report_service.create_report(title="Test Report", template="default")
        original_outline = report_service.get_report_outline(report_id)
        original_version = original_outline.outline_version

        await tool.execute(
            report_selector="Test Report",
            instruction="",
            proposed_changes={"metadata_updates": {"key": "value"}},
        )

        updated_outline = report_service.get_report_outline(report_id)
        assert updated_outline.outline_version == original_version + 1

    @pytest.mark.asyncio
    async def test_status_change_still_works(self, tmp_path: Path):
        """status_change is still applied correctly (regression check)."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        report_id = report_service.create_report(title="Test Report", template="default")

        result = await tool.execute(report_selector="Test Report", instruction="", status_change="archived")

        assert result["status"] == "success"
        updated_outline = report_service.get_report_outline(report_id)
        assert updated_outline.metadata.get("status") == "archived"
