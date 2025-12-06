"""Tests for ValidateReportTool - Report quality validation.

Covers all quality checks: citations, empty_sections, orphaned_insights,
duplicate_orders, chart_references, insight_importance, section_titles, stale_content.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.models import DatasetSource, Insight, Section
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.exceptions import MCPSelectorError, MCPValidationError
from igloo_mcp.mcp.tools.validate_report import (
    AVAILABLE_CHECKS,
    CHECK_ERROR,
    CHECK_FIXED,
    CHECK_PASS,
    CHECK_WARNING,
    ValidateReportTool,
)


@pytest.fixture
def config():
    """Create test configuration."""
    return Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))


@pytest.fixture
def report_service(tmp_path: Path):
    """Create report service with temp storage."""
    return ReportService(reports_root=tmp_path / "reports")


@pytest.fixture
def validate_tool(config, report_service):
    """Create validate report tool instance."""
    return ValidateReportTool(config, report_service)


@pytest.fixture
def empty_report_id(report_service):
    """Create an empty test report."""
    return report_service.create_report(
        title="Empty Test Report",
        template="empty",
        tags=["test"],
    )


@pytest.fixture
def report_with_issues(report_service, tmp_path):
    """Create a report with various validation issues.

    Note: Due to Pydantic validation, we can only create issues that don't
    violate model constraints. Issues like empty titles or invalid importance
    values need to be tested separately with special setup.
    """
    report_id = report_service.create_report(
        title="Report with Issues",
        template="empty",
    )

    outline = report_service.get_report_outline(report_id)

    # Add insights (some without citations)
    insight_with_citations_id = str(uuid.uuid4())
    insight_without_citations_id = str(uuid.uuid4())
    orphaned_insight_id = str(uuid.uuid4())

    insights = [
        Insight(
            insight_id=insight_with_citations_id,
            summary="Insight with proper citations",
            importance=8,
            status="active",
            supporting_queries=[DatasetSource(execution_id="exec_123")],
        ),
        Insight(
            insight_id=insight_without_citations_id,
            summary="Insight missing citations - should fail validation",
            importance=7,
            status="active",
            supporting_queries=[],
            citations=[],
        ),
        Insight(
            insight_id=orphaned_insight_id,
            summary="Orphaned insight not linked to any section",
            importance=6,
            status="active",
            supporting_queries=[DatasetSource(execution_id="exec_456")],
        ),
    ]

    # Add sections (some with issues)
    section_normal_id = str(uuid.uuid4())
    section_empty_id = str(uuid.uuid4())
    section_duplicate_order_id = str(uuid.uuid4())

    sections = [
        Section(
            section_id=section_normal_id,
            title="Normal Section",
            order=0,
            insight_ids=[insight_with_citations_id, insight_without_citations_id],
            content="This section has content",
        ),
        Section(
            section_id=section_empty_id,
            title="Empty Section",
            order=1,
            insight_ids=[],  # No insights
            content="",  # No content
            notes="",  # No notes
        ),
        Section(
            section_id=section_duplicate_order_id,
            title="Duplicate Order Section",
            order=0,  # Same order as first section
            insight_ids=[],
        ),
    ]

    # Add chart reference pointing to non-existent file
    outline.metadata["charts"] = {
        "chart_1": {
            "path": "/nonexistent/path/chart.png",
            "description": "Missing chart",
        },
        "chart_2": {
            "path": str(tmp_path / "external_chart.png"),  # External path
            "description": "External chart",
        },
    }

    # Create the external chart file for chart_2
    (tmp_path / "external_chart.png").write_bytes(b"fake png data")

    outline.sections = sections
    outline.insights = insights
    report_service.update_report_outline(report_id, outline, actor="test")

    return {
        "report_id": report_id,
        "insight_with_citations_id": insight_with_citations_id,
        "insight_without_citations_id": insight_without_citations_id,
        "orphaned_insight_id": orphaned_insight_id,
        "section_normal_id": section_normal_id,
        "section_empty_id": section_empty_id,
        "section_duplicate_order_id": section_duplicate_order_id,
    }


class TestValidateReportToolProperties:
    """Test tool properties and metadata."""

    def test_tool_name(self, validate_tool):
        """Test tool name is correct."""
        assert validate_tool.name == "validate_report"

    def test_tool_description(self, validate_tool):
        """Test tool description is informative."""
        desc = validate_tool.description.lower()
        assert "validate" in desc
        assert "quality" in desc or "check" in desc

    def test_tool_category(self, validate_tool):
        """Test tool category."""
        assert validate_tool.category == "reports"

    def test_tool_tags(self, validate_tool):
        """Test tool tags include expected values."""
        assert "validation" in validate_tool.tags
        assert "quality" in validate_tool.tags
        assert "reports" in validate_tool.tags

    def test_parameter_schema(self, validate_tool):
        """Test parameter schema structure."""
        schema = validate_tool.get_parameter_schema()

        assert schema["type"] == "object"
        assert "report_selector" in schema["properties"]
        assert "checks" in schema["properties"]
        assert "stale_threshold_days" in schema["properties"]
        assert "fix_mode" in schema["properties"]

        # Required fields
        assert "report_selector" in schema["required"]


class TestValidateReportAvailableChecks:
    """Test available checks constant."""

    def test_available_checks_count(self):
        """Test AVAILABLE_CHECKS has expected checks."""
        assert len(AVAILABLE_CHECKS) == 8

    def test_all_check_types_present(self):
        """Test all documented check types are available."""
        expected = {
            "citations",
            "empty_sections",
            "orphaned_insights",
            "duplicate_orders",
            "chart_references",
            "insight_importance",
            "section_titles",
            "stale_content",
        }
        assert expected == AVAILABLE_CHECKS


@pytest.mark.asyncio
class TestValidateReportBasicExecution:
    """Test basic validation execution."""

    async def test_validate_empty_report_passes(self, validate_tool, empty_report_id):
        """Empty report should pass all checks (no content to fail)."""
        result = await validate_tool.execute(
            report_selector=empty_report_id,
            checks=["all"],
        )

        assert result["status"] == "valid"
        assert result["report_id"] == empty_report_id
        assert "summary" in result
        assert result["summary"]["errors"] == 0

    async def test_validate_nonexistent_report_fails(self, validate_tool):
        """Non-existent report should raise selector error."""
        with pytest.raises(MCPSelectorError):
            await validate_tool.execute(
                report_selector="nonexistent-report",
                checks=["all"],
            )

    async def test_validate_with_specific_checks(self, validate_tool, empty_report_id):
        """Test running only specific checks."""
        result = await validate_tool.execute(
            report_selector=empty_report_id,
            checks=["citations", "empty_sections"],
        )

        assert result["status"] == "valid"
        # Should only have 2 checks
        assert len(result["checks"]) == 2
        assert "citations" in result["checks"]
        assert "empty_sections" in result["checks"]

    async def test_validate_with_invalid_check_type(self, validate_tool, empty_report_id):
        """Invalid check type should raise validation error."""
        with pytest.raises(MCPValidationError) as exc_info:
            await validate_tool.execute(
                report_selector=empty_report_id,
                checks=["invalid_check_type"],
            )

        assert "invalid" in str(exc_info.value).lower()


@pytest.mark.asyncio
class TestCitationsCheck:
    """Test citations validation check."""

    async def test_citations_check_fails_missing_citations(self, validate_tool, report_with_issues):
        """Insights without citations should fail check."""
        result = await validate_tool.execute(
            report_selector=report_with_issues["report_id"],
            checks=["citations"],
        )

        check_result = result["checks"]["citations"]
        assert check_result["status"] == CHECK_ERROR
        assert "missing citations" in check_result["message"].lower()
        assert len(check_result["details"]) >= 1

    async def test_citations_check_passes_with_citations(self, validate_tool, report_service):
        """Report with all cited insights should pass."""
        report_id = report_service.create_report(title="Cited Report", template="empty")
        outline = report_service.get_report_outline(report_id)

        insight = Insight(
            insight_id=str(uuid.uuid4()),
            summary="Properly cited insight",
            importance=8,
            status="active",
            supporting_queries=[DatasetSource(execution_id="exec_123")],
        )
        outline.insights.append(insight)
        report_service.update_report_outline(report_id, outline, actor="test")

        result = await validate_tool.execute(
            report_selector=report_id,
            checks=["citations"],
        )

        assert result["checks"]["citations"]["status"] == CHECK_PASS


@pytest.mark.asyncio
class TestEmptySectionsCheck:
    """Test empty sections validation check."""

    async def test_empty_sections_check_warns(self, validate_tool, report_with_issues):
        """Empty sections should generate warning."""
        result = await validate_tool.execute(
            report_selector=report_with_issues["report_id"],
            checks=["empty_sections"],
        )

        check_result = result["checks"]["empty_sections"]
        assert check_result["status"] == CHECK_WARNING
        assert check_result["fix_available"] is True

    async def test_empty_sections_fix_mode_removes(self, validate_tool, report_with_issues, report_service):
        """Fix mode should remove empty sections."""
        report_id = report_with_issues["report_id"]

        # Get original section count
        original_outline = report_service.get_report_outline(report_id)
        original_count = len(original_outline.sections)

        result = await validate_tool.execute(
            report_selector=report_id,
            checks=["empty_sections"],
            fix_mode=True,
        )

        check_result = result["checks"]["empty_sections"]
        assert check_result["status"] == CHECK_FIXED
        assert "fixes_applied" in result
        assert "empty_sections" in result["fixes_applied"]

        # Verify section was removed
        new_outline = report_service.get_report_outline(report_id)
        assert len(new_outline.sections) < original_count


@pytest.mark.asyncio
class TestOrphanedInsightsCheck:
    """Test orphaned insights validation check."""

    async def test_orphaned_insights_check_warns(self, validate_tool, report_with_issues):
        """Orphaned insights should generate warning."""
        result = await validate_tool.execute(
            report_selector=report_with_issues["report_id"],
            checks=["orphaned_insights"],
        )

        check_result = result["checks"]["orphaned_insights"]
        assert check_result["status"] == CHECK_WARNING
        assert len(check_result["details"]) >= 1

    async def test_orphaned_insights_fix_mode_links(self, validate_tool, report_with_issues, report_service):
        """Fix mode should link orphaned insights to first section."""
        report_id = report_with_issues["report_id"]
        orphaned_id = report_with_issues["orphaned_insight_id"]

        result = await validate_tool.execute(
            report_selector=report_id,
            checks=["orphaned_insights"],
            fix_mode=True,
        )

        check_result = result["checks"]["orphaned_insights"]
        assert check_result["status"] == CHECK_FIXED

        # Verify insight is now linked
        outline = report_service.get_report_outline(report_id)
        all_linked_ids = []
        for section in outline.sections:
            all_linked_ids.extend(section.insight_ids)
        assert orphaned_id in all_linked_ids


@pytest.mark.asyncio
class TestDuplicateOrdersCheck:
    """Test duplicate order values validation check."""

    async def test_duplicate_orders_check_warns(self, validate_tool, report_with_issues):
        """Duplicate order values should generate warning."""
        result = await validate_tool.execute(
            report_selector=report_with_issues["report_id"],
            checks=["duplicate_orders"],
        )

        check_result = result["checks"]["duplicate_orders"]
        assert check_result["status"] == CHECK_WARNING
        assert check_result["fix_available"] is True

    async def test_duplicate_orders_fix_mode_reassigns(self, validate_tool, report_with_issues, report_service):
        """Fix mode should reassign unique order values."""
        report_id = report_with_issues["report_id"]

        result = await validate_tool.execute(
            report_selector=report_id,
            checks=["duplicate_orders"],
            fix_mode=True,
        )

        check_result = result["checks"]["duplicate_orders"]
        assert check_result["status"] == CHECK_FIXED

        # Verify orders are now unique
        outline = report_service.get_report_outline(report_id)
        orders = [s.order for s in outline.sections]
        assert len(orders) == len(set(orders))


@pytest.mark.asyncio
class TestChartReferencesCheck:
    """Test chart references validation check."""

    async def test_chart_references_check_warns_missing(self, validate_tool, report_with_issues):
        """Missing chart files should generate warning."""
        result = await validate_tool.execute(
            report_selector=report_with_issues["report_id"],
            checks=["chart_references"],
        )

        check_result = result["checks"]["chart_references"]
        assert check_result["status"] == CHECK_WARNING
        assert len(check_result["details"]) >= 1

    async def test_chart_references_identifies_external(self, validate_tool, report_with_issues):
        """External chart paths should be identified."""
        result = await validate_tool.execute(
            report_selector=report_with_issues["report_id"],
            checks=["chart_references"],
        )

        check_result = result["checks"]["chart_references"]
        # Should have issue about external path
        issues = check_result["details"]
        external_issues = [i for i in issues if "outside" in i.get("issue", "").lower()]
        assert len(external_issues) >= 1


@pytest.mark.asyncio
class TestInsightImportanceCheck:
    """Test insight importance values validation check."""

    async def test_importance_check_passes_valid_values(self, validate_tool, report_service):
        """Valid importance values should pass check."""
        report_id = report_service.create_report(title="Valid Importance", template="empty")
        outline = report_service.get_report_outline(report_id)

        insight = Insight(
            insight_id=str(uuid.uuid4()),
            summary="Valid importance insight",
            importance=8,  # Valid: 1-10
            status="active",
            supporting_queries=[DatasetSource(execution_id="exec_123")],
        )
        outline.insights.append(insight)
        report_service.update_report_outline(report_id, outline, actor="test")

        result = await validate_tool.execute(
            report_selector=report_id,
            checks=["insight_importance"],
        )

        check_result = result["checks"]["insight_importance"]
        assert check_result["status"] == CHECK_PASS

    async def test_importance_check_empty_report_passes(self, validate_tool, empty_report_id):
        """Empty report should pass importance check."""
        result = await validate_tool.execute(
            report_selector=empty_report_id,
            checks=["insight_importance"],
        )

        check_result = result["checks"]["insight_importance"]
        assert check_result["status"] == CHECK_PASS


@pytest.mark.asyncio
class TestSectionTitlesCheck:
    """Test section titles validation check."""

    async def test_section_titles_check_passes_valid(self, validate_tool, report_service):
        """Sections with valid titles should pass check."""
        report_id = report_service.create_report(title="Valid Titles", template="empty")
        outline = report_service.get_report_outline(report_id)

        section = Section(
            section_id=str(uuid.uuid4()),
            title="Valid Section Title",
            order=0,
            insight_ids=[],
        )
        outline.sections.append(section)
        report_service.update_report_outline(report_id, outline, actor="test")

        result = await validate_tool.execute(
            report_selector=report_id,
            checks=["section_titles"],
        )

        check_result = result["checks"]["section_titles"]
        assert check_result["status"] == CHECK_PASS

    async def test_section_titles_empty_report_passes(self, validate_tool, empty_report_id):
        """Empty report should pass section titles check."""
        result = await validate_tool.execute(
            report_selector=empty_report_id,
            checks=["section_titles"],
        )

        check_result = result["checks"]["section_titles"]
        assert check_result["status"] == CHECK_PASS


@pytest.mark.asyncio
class TestStaleContentCheck:
    """Test stale content validation check."""

    async def test_stale_content_check_with_old_content(self, validate_tool, report_service):
        """Old content should be flagged as stale."""
        report_id = report_service.create_report(title="Stale Report", template="empty")
        outline = report_service.get_report_outline(report_id)

        # Add section with old timestamp
        old_date = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        section = Section(
            section_id=str(uuid.uuid4()),
            title="Old Section",
            order=0,
            insight_ids=[],
            content="Old content",
            updated_at=old_date,
        )
        outline.sections.append(section)
        report_service.update_report_outline(report_id, outline, actor="test")

        result = await validate_tool.execute(
            report_selector=report_id,
            checks=["stale_content"],
            stale_threshold_days=30,
        )

        check_result = result["checks"]["stale_content"]
        assert check_result["status"] == CHECK_WARNING
        assert len(check_result["details"]) >= 1

    async def test_stale_content_fresh_passes(self, validate_tool, report_service):
        """Fresh content should pass stale check."""
        report_id = report_service.create_report(title="Fresh Report", template="empty")
        outline = report_service.get_report_outline(report_id)

        # Add section with recent timestamp
        recent_date = datetime.now(UTC).isoformat()
        section = Section(
            section_id=str(uuid.uuid4()),
            title="Fresh Section",
            order=0,
            insight_ids=[],
            content="Fresh content",
            updated_at=recent_date,
        )
        outline.sections.append(section)
        report_service.update_report_outline(report_id, outline, actor="test")

        result = await validate_tool.execute(
            report_selector=report_id,
            checks=["stale_content"],
            stale_threshold_days=30,
        )

        check_result = result["checks"]["stale_content"]
        assert check_result["status"] == CHECK_PASS


@pytest.mark.asyncio
class TestValidateReportRecommendations:
    """Test recommendations generation."""

    async def test_recommendations_generated_for_issues(self, validate_tool, report_with_issues):
        """Recommendations should be generated for failed checks."""
        result = await validate_tool.execute(
            report_selector=report_with_issues["report_id"],
            checks=["all"],
        )

        assert "recommendations" in result
        assert len(result["recommendations"]) > 0

    async def test_no_recommendations_for_clean_report(self, validate_tool, empty_report_id):
        """Clean report should have no recommendations."""
        result = await validate_tool.execute(
            report_selector=empty_report_id,
            checks=["all"],
        )

        # Empty report has no content to fail checks
        assert result["status"] == "valid"
        assert len(result["recommendations"]) == 0


@pytest.mark.asyncio
class TestValidateReportSummary:
    """Test validation summary."""

    async def test_summary_counts_correct(self, validate_tool, report_with_issues):
        """Summary should have correct counts for each status."""
        result = await validate_tool.execute(
            report_selector=report_with_issues["report_id"],
            checks=["all"],
        )

        summary = result["summary"]
        assert "total_checks" in summary
        assert "passed" in summary
        assert "warnings" in summary
        assert "errors" in summary
        assert "fixed" in summary

        # Total should match sum of statuses
        assert summary["total_checks"] == len(result["checks"])

    async def test_overall_status_errors(self, validate_tool, report_with_issues):
        """Overall status should be 'errors' when errors present."""
        result = await validate_tool.execute(
            report_selector=report_with_issues["report_id"],
            checks=["citations", "section_titles"],  # Both can produce errors
        )

        # At least one error should be present
        if result["summary"]["errors"] > 0:
            assert result["status"] == "errors"

    async def test_overall_status_warnings(self, validate_tool, report_service):
        """Overall status should be 'warnings' when only warnings present."""
        report_id = report_service.create_report(title="Warning Report", template="empty")
        outline = report_service.get_report_outline(report_id)

        # Add empty section (warning, not error)
        section = Section(
            section_id=str(uuid.uuid4()),
            title="Empty But Titled",
            order=0,
            insight_ids=[],
        )
        outline.sections.append(section)
        report_service.update_report_outline(report_id, outline, actor="test")

        result = await validate_tool.execute(
            report_selector=report_id,
            checks=["empty_sections"],
        )

        assert result["status"] == "warnings"

    async def test_overall_status_valid(self, validate_tool, empty_report_id):
        """Overall status should be 'valid' when all checks pass."""
        result = await validate_tool.execute(
            report_selector=empty_report_id,
            checks=["all"],
        )

        assert result["status"] == "valid"


@pytest.mark.asyncio
class TestValidateReportTiming:
    """Test timing information in response."""

    async def test_duration_included(self, validate_tool, empty_report_id):
        """Duration should be included in response."""
        result = await validate_tool.execute(
            report_selector=empty_report_id,
            checks=["all"],
        )

        assert "duration_ms" in result
        assert isinstance(result["duration_ms"], int | float)
        assert result["duration_ms"] >= 0

    async def test_request_id_included(self, validate_tool, empty_report_id):
        """Request ID should be included in response."""
        result = await validate_tool.execute(
            report_selector=empty_report_id,
            checks=["all"],
            request_id="test-request-123",
        )

        assert result["request_id"] == "test-request-123"
