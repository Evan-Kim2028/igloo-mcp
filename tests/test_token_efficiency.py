"""Tests for token efficiency enhancements to existing tools."""

from pathlib import Path

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool
from igloo_mcp.mcp.tools.render_report import RenderReportTool
from igloo_mcp.mcp.tools.search_report import SearchReportTool


@pytest.mark.asyncio
class TestEvolveReportResponseDetail:
    """Test response_detail parameter in evolve_report."""

    async def test_response_detail_minimal(self, tmp_path: Path):
        """Test minimal response detail level."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        # Create report
        report_id = report_service.create_report(title="Test", template="default")

        # Add section with minimal response
        result = await tool.execute(
            report_selector=report_id,
            instruction="Add test section",
            proposed_changes={"sections_to_add": [{"title": "Test Section", "order": 0}]},
            response_detail="minimal",
        )

        # Verify minimal response structure
        assert result["status"] == "success"
        assert result["report_id"] == report_id
        assert "outline_version" in result
        assert "summary" in result

        # Should have counts but not IDs
        assert "sections_added" in result["summary"]
        assert result["summary"]["sections_added"] == 1

        # Should NOT have detailed fields
        assert "changes_applied" not in result
        assert "warnings" not in result
        assert "timing" not in result

    async def test_response_detail_standard(self, tmp_path: Path):
        """Test standard response detail level (default)."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add test section",
            proposed_changes={"sections_to_add": [{"title": "Test Section", "order": 0}]},
            response_detail="standard",
        )

        # Verify standard response
        assert result["status"] == "success"
        assert "summary" in result
        assert "warnings" in result

        # Should have IDs
        assert "section_ids_added" in result["summary"]
        assert len(result["summary"]["section_ids_added"]) == 1

        # Should NOT have full echo
        assert "changes_applied" not in result
        assert "timing" not in result

    async def test_response_detail_full(self, tmp_path: Path):
        """Test full response detail level."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add test section",
            proposed_changes={"sections_to_add": [{"title": "Test Section", "order": 0}]},
            response_detail="full",
        )

        # Verify full response
        assert result["status"] == "success"
        assert "changes_applied" in result
        assert "summary" in result
        assert "warnings" in result
        assert "timing" in result

        # Should have all timing details
        assert "apply_duration_ms" in result["timing"]
        assert "storage_duration_ms" in result["timing"]

    async def test_response_detail_invalid(self, tmp_path: Path):
        """Test invalid response_detail raises validation error."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = EvolveReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        from igloo_mcp.mcp.exceptions import MCPValidationError

        with pytest.raises(MCPValidationError) as exc_info:
            await tool.execute(
                report_selector=report_id,
                instruction="Add test section",
                proposed_changes={"sections_to_add": [{"title": "Test", "order": 0}]},
                response_detail="invalid",
            )

        assert "Invalid response_detail" in str(exc_info.value)


@pytest.mark.asyncio
class TestSearchReportFields:
    """Test fields parameter in search_report."""

    async def test_fields_minimal(self, tmp_path: Path):
        """Test filtering to minimal fields."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = SearchReportTool(config, report_service)

        # Create test reports
        report_service.create_report(title="Test Report 1", tags=["test"])
        report_service.create_report(title="Test Report 2", tags=["test"])

        # Search with minimal fields
        result = await tool.execute(
            tags=["test"],
            fields=["report_id", "title"],
        )

        assert result["status"] == "success"
        assert len(result["reports"]) == 2

        # Should only have requested fields
        for report in result["reports"]:
            assert "report_id" in report
            assert "title" in report
            assert len(report.keys()) == 2  # Only 2 fields

            # Should NOT have other fields
            assert "created_at" not in report
            assert "tags" not in report
            assert "status" not in report

    async def test_fields_all_default(self, tmp_path: Path):
        """Test default behavior returns all fields."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = SearchReportTool(config, report_service)

        report_service.create_report(title="Test Report", tags=["test"])

        # Search without fields parameter
        result = await tool.execute(title="Test")

        assert len(result["reports"]) == 1
        report = result["reports"][0]

        # Should have all fields
        assert "report_id" in report
        assert "title" in report
        assert "created_at" in report
        assert "updated_at" in report
        assert "tags" in report
        assert "status" in report
        assert "path" in report

    async def test_fields_invalid(self, tmp_path: Path):
        """Test invalid fields raise validation error."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = SearchReportTool(config, report_service)

        report_service.create_report(title="Test", tags=["test"])

        from igloo_mcp.mcp.exceptions import MCPValidationError

        with pytest.raises(MCPValidationError) as exc_info:
            await tool.execute(
                title="Test",
                fields=["report_id", "invalid_field"],
            )

        assert "Invalid fields" in str(exc_info.value)
        assert "invalid_field" in str(exc_info.value)


@pytest.mark.asyncio
class TestRenderReportPreviewMaxChars:
    """Test preview_max_chars parameter in render_report."""

    async def test_preview_max_chars_custom(self, tmp_path: Path):
        """Test custom preview truncation length."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = RenderReportTool(config, report_service)

        # Create a report
        report_id = report_service.create_report(title="Test Report", template="default")

        # Render with small preview (dry run to avoid Quarto dependency)
        result = await tool.execute(
            report_selector=report_id,
            format="html",
            include_preview=True,
            preview_max_chars=100,
            dry_run=True,
        )

        assert result["status"] == "success"

        # Note: preview generation depends on actual rendered content
        # With dry_run, we just verify the parameter is accepted

    async def test_preview_default_length(self, tmp_path: Path):
        """Test default preview length is 2000 chars."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")
        tool = RenderReportTool(config, report_service)

        report_id = report_service.create_report(title="Test", template="default")

        # Render with default preview_max_chars
        result = await tool.execute(
            report_selector=report_id,
            dry_run=True,
        )

        assert result["status"] == "success"
        # Default parameter accepted without error
