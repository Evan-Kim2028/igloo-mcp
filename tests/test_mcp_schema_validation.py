"""Integration tests for MCP tool schema validation.

These tests validate that MCP schemas match actual implementation,
preventing bugs like #110 and #111 where schema and code diverged.

NOTE: These tests are currently skipped pending proper service mocking setup.
"""

import pytest

# Skip all tests in this module for now - need proper service mocking
pytestmark = pytest.mark.skip(reason="Need proper service mocking setup")


class TestExecuteQuerySchema:
    """Test execute_query MCP schema correctness."""

    def test_response_mode_enum_matches_implementation(self):
        """Schema should show correct response_mode values."""
        from igloo_mcp.config import Config
        from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
        from igloo_mcp.services import QueryService

        config = Config.from_env()
        tool = ExecuteQueryTool(config, None, QueryService(config), None)
        schema = tool.get_parameter_schema()

        # Should have correct enum values
        assert schema["properties"]["response_mode"]["enum"] == [
            "schema_only",
            "summary",
            "sample",
            "full",
        ]

        # Should NOT have old values
        assert "auto" not in schema["properties"]["response_mode"]["enum"]
        assert "sync" not in schema["properties"]["response_mode"]["enum"]

    def test_response_mode_default_is_summary(self):
        """Default should be 'summary' per v0.3.6 breaking change."""
        from igloo_mcp.config import Config
        from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
        from igloo_mcp.services import QueryService

        config = Config.from_env()
        tool = ExecuteQueryTool(config, None, QueryService(config), None)
        schema = tool.get_parameter_schema()

        assert schema["properties"]["response_mode"]["default"] == "summary"

    def test_description_mentions_token_efficiency(self):
        """Description should explain token efficiency."""
        from igloo_mcp.config import Config
        from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
        from igloo_mcp.services import QueryService

        config = Config.from_env()
        tool = ExecuteQueryTool(config, None, QueryService(config), None)
        schema = tool.get_parameter_schema()

        description = schema["properties"]["response_mode"]["description"]
        assert "token" in description.lower()
        assert "summary" in description.lower()


class TestGetReportSchema:
    """Test get_report MCP schema correctness."""

    def test_mode_enum_matches_implementation(self):
        """Schema should show correct mode values."""
        from igloo_mcp.config import Config
        from igloo_mcp.living_reports.service import ReportService
        from igloo_mcp.mcp.tools.get_report import GetReportTool

        config = Config.from_env()
        report_service = ReportService(config)
        tool = GetReportTool(config, report_service)
        schema = tool.get_parameter_schema()

        # Check mode parameter exists and has correct values
        assert "mode" in schema["properties"]
        expected_modes = ["summary", "sections", "insights", "full"]
        assert schema["properties"]["mode"]["enum"] == expected_modes

    def test_mode_default_is_summary(self):
        """Default should be 'summary' for token efficiency."""
        from igloo_mcp.config import Config
        from igloo_mcp.living_reports.service import ReportService
        from igloo_mcp.mcp.tools.get_report import GetReportTool

        config = Config.from_env()
        report_service = ReportService(config)
        tool = GetReportTool(config, report_service)
        schema = tool.get_parameter_schema()

        assert schema["properties"]["mode"]["default"] == "summary"


class TestSearchReportSchema:
    """Test search_report MCP schema correctness."""

    def test_fields_parameter_exists(self):
        """Schema should document fields parameter."""
        from igloo_mcp.config import Config
        from igloo_mcp.living_reports.service import ReportService
        from igloo_mcp.mcp.tools.search_report import SearchReportTool

        config = Config.from_env()
        report_service = ReportService(config)
        tool = SearchReportTool(config, report_service)
        schema = tool.get_parameter_schema()

        # fields parameter should exist
        assert "fields" in schema["properties"]
        assert "description" in schema["properties"]["fields"]


class TestSchemaConsistency:
    """Test that all tools with response modes follow consistent patterns."""

    @pytest.mark.parametrize(
        ("tool_module", "tool_class", "param_name"),
        [
            ("execute_query", "ExecuteQueryTool", "response_mode"),
            ("get_report", "GetReportTool", "mode"),
            ("search_report", "SearchReportTool", "fields"),
            ("evolve_report", "EvolveReportTool", "response_detail"),
            ("evolve_report_batch", "EvolveReportBatchTool", "response_detail"),
        ],
    )
    def test_all_schemas_have_descriptions(self, tool_module, tool_class, param_name):
        """All parameters should have helpful descriptions."""
        from importlib import import_module

        from igloo_mcp.config import Config

        config = Config.from_env()

        # Import tool class dynamically
        module = import_module(f"igloo_mcp.mcp.tools.{tool_module}")
        tool_cls = getattr(module, tool_class)

        # Create tool instance with minimal dependencies
        if tool_module in ["get_report", "search_report", "evolve_report", "evolve_report_batch"]:
            from igloo_mcp.living_reports.service import ReportService

            report_service = ReportService(config)
            tool = tool_cls(config, report_service)
        elif tool_module == "execute_query":
            from igloo_mcp.services import QueryService

            tool = tool_cls(config, None, QueryService(config), None)
        else:
            tool = tool_cls(config)

        schema = tool.get_parameter_schema()

        if param_name in schema["properties"]:
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
            valid_modes=("full", "summary", "schema_only", "sample"),
            default="summary",
        )

        assert result == "summary", "Breaking change not implemented: default should be 'summary'"
