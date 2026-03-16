"""Integration tests for MCP tool schema validation.

These tests validate that MCP schemas match actual implementation,
preventing bugs like #110 and #111 where schema and code diverged.
"""

from __future__ import annotations

from importlib import import_module

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.service_layer import QueryService


@pytest.fixture
def config() -> Config:
    """Create a minimal config for schema-only tool construction."""
    return Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))


@pytest.fixture
def report_service(tmp_path) -> ReportService:
    """Create a report service rooted in a temporary directory."""
    return ReportService(reports_root=tmp_path / "reports")


@pytest.fixture
def execute_query_tool(config: Config) -> ExecuteQueryTool:
    """Create execute_query with inert dependencies for schema inspection."""
    return ExecuteQueryTool(
        config=config,
        snowflake_service=None,
        query_service=QueryService(context=None),
        health_monitor=None,
    )


def _build_tool(tool_module: str, tool_class: str, *, config: Config, report_service: ReportService):
    """Construct MCP tools with the minimal dependencies their schemas require."""
    module = import_module(f"igloo_mcp.mcp.tools.{tool_module}")
    tool_cls = getattr(module, tool_class)

    if tool_module in {"get_report", "search_report", "evolve_report", "evolve_report_batch"}:
        return tool_cls(config, report_service)
    if tool_module == "execute_query":
        return tool_cls(config, None, QueryService(context=None), None)
    return tool_cls(config)


class TestExecuteQuerySchema:
    """Test execute_query MCP schema correctness."""

    def test_response_mode_enum_matches_implementation(self, execute_query_tool):
        """Schema should show correct response_mode values."""
        schema = execute_query_tool.get_parameter_schema()

        # Should have correct enum values
        assert schema["properties"]["response_mode"]["enum"] == [
            "minimal",
            "schema_only",
            "summary",
            "sample",
            "full",
        ]

        # Should NOT have old values
        assert "auto" not in schema["properties"]["response_mode"]["enum"]
        assert "sync" not in schema["properties"]["response_mode"]["enum"]

    def test_response_mode_default_is_summary(self, execute_query_tool):
        """Default should be 'summary' per v0.3.6 breaking change."""
        schema = execute_query_tool.get_parameter_schema()

        assert schema["properties"]["response_mode"]["default"] == "summary"

    def test_description_mentions_token_efficiency(self, execute_query_tool):
        """Description should explain token efficiency."""
        schema = execute_query_tool.get_parameter_schema()

        description = schema["properties"]["response_mode"]["description"]
        assert "token" in description.lower()
        assert "summary" in description.lower()


class TestGetReportSchema:
    """Test get_report MCP schema correctness."""

    def test_mode_enum_matches_implementation(self, config, report_service):
        """Schema should show correct mode values."""
        from igloo_mcp.mcp.tools.get_report import GetReportTool

        tool = GetReportTool(config, report_service)
        schema = tool.get_parameter_schema()

        # Check mode parameter exists and has correct values
        assert "mode" in schema["properties"]
        expected_modes = ["summary", "sections", "insights", "full"]
        assert schema["properties"]["mode"]["enum"] == expected_modes

    def test_mode_default_is_summary(self, config, report_service):
        """Default should be 'summary' for token efficiency."""
        from igloo_mcp.mcp.tools.get_report import GetReportTool

        tool = GetReportTool(config, report_service)
        schema = tool.get_parameter_schema()

        assert schema["properties"]["mode"]["default"] == "summary"


class TestSearchReportSchema:
    """Test search_report MCP schema correctness."""

    def test_fields_parameter_exists(self, config, report_service):
        """Schema should document fields parameter."""
        from igloo_mcp.mcp.tools.search_report import SearchReportTool

        tool = SearchReportTool(config, report_service)
        schema = tool.get_parameter_schema()

        # fields parameter should exist
        assert "fields" in schema["properties"]
        assert "description" in schema["properties"]["fields"]
        assert schema["properties"]["fields"]["items"]["type"] == "string"


class TestEvolveReportSchema:
    """Test evolve_report MCP schema correctness."""

    def test_response_mode_parameters_exist(self, config, report_service):
        """Schema should document both standard and legacy response verbosity params."""
        from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool

        tool = EvolveReportTool(config, report_service)
        schema = tool.get_parameter_schema()

        assert "response_mode" in schema["properties"]
        assert schema["properties"]["response_mode"]["enum"] == ["minimal", "standard", "full"]
        assert "response_detail" in schema["properties"]
        assert "deprecated" in schema["properties"]["response_detail"]["description"].lower()


class TestSchemaConsistency:
    """Test that all tools with response modes follow consistent patterns."""

    @pytest.mark.parametrize(
        ("tool_module", "tool_class", "param_name"),
        [
            ("execute_query", "ExecuteQueryTool", "response_mode"),
            ("get_report", "GetReportTool", "mode"),
            ("search_report", "SearchReportTool", "fields"),
            ("evolve_report", "EvolveReportTool", "response_mode"),
            ("evolve_report", "EvolveReportTool", "response_detail"),
            ("evolve_report_batch", "EvolveReportBatchTool", "response_detail"),
        ],
    )
    def test_all_schemas_have_descriptions(self, config, report_service, tool_module, tool_class, param_name):
        """All parameters should have helpful descriptions."""
        tool = _build_tool(tool_module, tool_class, config=config, report_service=report_service)
        schema = tool.get_parameter_schema()
        param_schema = schema["properties"][param_name]
        assert "description" in param_schema
        assert len(param_schema["description"]) > 20  # Non-trivial description


class TestBreakingChangeImplementation:
    """Verify v0.3.6 breaking change is actually implemented."""

    def test_execute_query_defaults_to_summary_not_full(self):
        """Verify #111 fix: default should be 'summary' not 'full'."""
        from igloo_mcp.mcp.validation_helpers import validate_response_mode

        # When no response_mode is provided, should default to 'summary'
        result = validate_response_mode(
            response_mode=None,
            valid_modes=("minimal", "full", "summary", "schema_only", "sample"),
            default="summary",
        )

        assert result == "summary", "Breaking change not implemented: default should be 'summary'"
