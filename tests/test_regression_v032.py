"""Regression tests for v0.3.2 bug fixes.

This module contains regression tests for all bugs fixed in v0.3.2 to ensure
they don't reoccur in future releases.

Related issues:
- #48: timeout_seconds type error
- #57: sections_to_modify with inline insights
- #58: supporting_queries optional
- #59: evolve_report stale warnings
- #60: render_report include_preview parameter
"""

from pathlib import Path

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.mcp.tools.render_report import RenderReportTool
from igloo_mcp.service_layer.query_service import QueryService
from tests.helpers.fake_snowflake_connector import (
    FakeQueryPlan,
    FakeSnowflakeService,
)


class TestBug48TimeoutStringCoercion:
    """Regression tests for #48 - timeout_seconds accepts both int and string."""

    @pytest.mark.asyncio
    async def test_timeout_accepts_integer(self, tmp_path, monkeypatch):
        """Test that timeout_seconds accepts integer values."""
        # Disable history/cache to simplify test
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "")
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        cfg = Config(snowflake=SnowflakeConfig(profile="test"))
        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT 1",
                    rows=[{"col1": 1}],
                    duration=0.05,
                    sfqid="TEST_QID_INT",
                )
            ]
        )
        tool = ExecuteQueryTool(cfg, service, QueryService(context=None))

        result = await tool.execute(
            statement="SELECT 1",
            timeout_seconds=240,  # Integer
            reason="test integer timeout",
        )

        assert result["rowcount"] == 1
        assert result["query_id"] == "TEST_QID_INT"

    @pytest.mark.asyncio
    async def test_timeout_accepts_numeric_string(self, tmp_path, monkeypatch):
        """Test that timeout_seconds accepts numeric string values (#48)."""
        # Disable history/cache to simplify test
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "")
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        cfg = Config(snowflake=SnowflakeConfig(profile="test"))
        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT 1",
                    rows=[{"col1": 1}],
                    duration=0.05,
                    sfqid="TEST_QID_STR",
                )
            ]
        )
        tool = ExecuteQueryTool(cfg, service, QueryService(context=None))

        result = await tool.execute(
            statement="SELECT 1",
            timeout_seconds="240",  # String that can be coerced
            reason="test string timeout",
        )

        assert result["rowcount"] == 1
        assert result["query_id"] == "TEST_QID_STR"

    @pytest.mark.asyncio
    async def test_timeout_rejects_invalid_string(self, tmp_path, monkeypatch):
        """Test that timeout_seconds rejects non-numeric strings."""
        # Disable history/cache to simplify test
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "")
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        cfg = Config(snowflake=SnowflakeConfig(profile="test"))
        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT 1",
                    rows=[{"col1": 1}],
                    duration=0.05,
                )
            ]
        )
        tool = ExecuteQueryTool(cfg, service, QueryService(context=None))

        # Invalid timeout strings raise TypeError
        with pytest.raises(TypeError) as exc_info:
            await tool.execute(
                statement="SELECT 1",
                timeout_seconds="invalid",  # Invalid string
                reason="test invalid timeout",
            )

        assert "timeout_seconds" in str(exc_info.value).lower()


class TestBug57InlineInsights:
    """Regression tests for #57 - sections_to_modify with inline insights."""

    @pytest.mark.asyncio
    async def test_sections_to_add_with_inline_insights(self, tmp_path: Path):
        """Test that sections_to_add supports inline insights array."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        # Create a test report
        outline = report_service.create_report(
            title="Test Report for Bug 57", template="default"
        )
        report_id = outline.report_id

        tool = EvolveReportTool(config, report_service)

        # Add section with inline insights
        result = await tool.execute(
            report_selector=report_id,
            instruction="Add section with inline insights",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "New Section",
                        "insights": [
                            {  # Inline insights
                                "content": "Test insight",
                                "supporting_queries": [],
                            }
                        ],
                    }
                ]
            },
        )

        assert result["status"] == "success"
        assert result["insights_added"] == 1  # Inline insight should be counted
        assert result["sections_added"] == 1

    @pytest.mark.asyncio
    async def test_sections_to_modify_with_inline_insights(self, tmp_path: Path):
        """Test that sections_to_modify supports inline insights array."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        # Create a test report with a section
        outline = report_service.create_report(
            title="Test Report for Bug 57 Modify", template="default"
        )
        report_id = outline.report_id

        # Add a section first
        result1 = await EvolveReportTool(config, report_service).execute(
            report_selector=report_id,
            instruction="Add initial section",
            proposed_changes={"sections_to_add": [{"title": "Initial Section"}]},
        )
        section_id = result1["sections_added_details"][0]["section_id"]

        # Modify section with inline insights
        tool = EvolveReportTool(config, report_service)
        result = await tool.execute(
            report_selector=report_id,
            instruction="Modify section with inline insights",
            proposed_changes={
                "sections_to_modify": [
                    {
                        "section_id": section_id,
                        "insights": [
                            {  # Inline insights
                                "content": "Added insight",
                                "supporting_queries": [],
                            }
                        ],
                    }
                ]
            },
        )

        assert result["status"] == "success"
        assert result["insights_added"] == 1  # Inline insight should be counted


class TestBug58SupportingQueriesOptional:
    """Regression tests for #58 - supporting_queries defaults to []."""

    @pytest.mark.asyncio
    async def test_insights_to_add_without_supporting_queries(self, tmp_path: Path):
        """Test that insights_to_add works without explicit supporting_queries."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        # Create a test report
        outline = report_service.create_report(
            title="Test Report for Bug 58", template="default"
        )
        report_id = outline.report_id

        tool = EvolveReportTool(config, report_service)

        # Add insight without supporting_queries field
        result = await tool.execute(
            report_selector=report_id,
            instruction="Add draft insight",
            proposed_changes={
                "insights_to_add": [
                    {
                        "content": "Draft insight without queries"
                        # No supporting_queries field - should default to []
                    }
                ]
            },
        )

        assert result["status"] == "success"
        assert result["insights_added"] == 1


class TestBug59StaleWarnings:
    """Regression tests for #59 - warnings computed after changes applied."""

    @pytest.mark.asyncio
    async def test_no_stale_warning_after_linking_insights(self, tmp_path: Path):
        """Test that warnings don't show stale 'no insights' after linking."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        # Create a test report with section and insight
        outline = report_service.create_report(
            title="Test Report for Bug 59", template="default"
        )
        report_id = outline.report_id

        tool = EvolveReportTool(config, report_service)

        # Add section and insight separately
        result1 = await tool.execute(
            report_selector=report_id,
            instruction="Add section and insight",
            proposed_changes={
                "sections_to_add": [{"title": "Test Section"}],
                "insights_to_add": [{"content": "Test insight"}],
            },
        )

        section_id = result1["sections_added_details"][0]["section_id"]
        insight_id = result1["insights_added_details"][0]["insight_id"]

        # Link insight to section - should not warn about empty section
        result2 = await tool.execute(
            report_selector=report_id,
            instruction="Link insight to section",
            proposed_changes={
                "sections_to_modify": [
                    {"section_id": section_id, "insight_ids": [insight_id]}
                ]
            },
        )

        assert result2["status"] == "success"
        # Warnings should NOT contain "Section has no insights"
        warnings = result2.get("warnings", [])
        assert not any("no insights" in w.lower() for w in warnings)


class TestBug60RenderPreview:
    """Regression tests for #60 - render_report include_preview parameter."""

    @pytest.mark.asyncio
    async def test_render_with_preview_returns_content(self, tmp_path: Path):
        """Test that include_preview=True returns truncated content."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        # Create a test report
        outline = report_service.create_report(
            title="Test Report for Bug 60", template="default"
        )
        report_id = outline.report_id

        tool = RenderReportTool(config, report_service)

        # Render with preview (dry run to avoid Quarto dependency)
        result = await tool.execute(
            report_selector=report_id, format="html", dry_run=True, include_preview=True
        )

        assert result["status"] == "dry_run_success"
        # Should include preview content
        assert "preview" in result
        assert result["preview"] is not None
        assert len(result["preview"]) > 0

    @pytest.mark.asyncio
    async def test_render_output_path_is_absolute(self, tmp_path: Path):
        """Test that output_path is always absolute (#60)."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        report_service = ReportService(reports_root=tmp_path / "reports")

        # Create a test report
        outline = report_service.create_report(
            title="Test Report Output Path", template="default"
        )
        report_id = outline.report_id

        tool = RenderReportTool(config, report_service)

        # Render (dry run)
        result = await tool.execute(
            report_selector=report_id, format="html", dry_run=True
        )

        assert result["status"] == "dry_run_success"
        assert "output_path" in result

        # Path should be absolute
        output_path = Path(result["output_path"])
        assert output_path.is_absolute()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
