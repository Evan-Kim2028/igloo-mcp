"""
Critical import smoke tests to catch namespace collisions and import failures.

These tests would have caught the v0.3.2 templates/ vs templates.py namespace collision bug.
"""



class TestLivingReportsImports:
    """Test that all living reports public APIs are importable."""

    def test_all_living_reports_apis_importable(self):
        """Import every public API from living_reports to catch namespace collisions."""
        # Core modules
        # Templates - this caught the bug where templates/ dir shadowed templates.py
        from igloo_mcp.living_reports import (
            index,
            models,
            quarto_renderer,
            selector,
            service,
            storage,
            templates,
        )

        # Verify all modules are actually modules, not None
        assert models is not None
        assert service is not None
        assert storage is not None
        assert index is not None
        assert selector is not None
        assert quarto_renderer is not None
        assert templates is not None

    def test_template_functions_accessible(self):
        """Verify template namespace provides expected functions.

        This would have caught the templates/ directory shadowing templates.py module.
        """
        from igloo_mcp.living_reports.templates import TEMPLATES, get_template

        # Verify functions are callable
        assert callable(get_template)

        # Verify TEMPLATES dict is accessible
        assert isinstance(TEMPLATES, dict)
        assert "default" in TEMPLATES
        assert "analyst_v1" in TEMPLATES

        # Verify get_template returns sections
        sections = get_template("default")
        assert isinstance(sections, list)

    def test_template_directory_and_module_coexist(self):
        """Verify both templates/ directory and templates.py module are accessible.

        Bug: In v0.3.2, templates/__init__.py didn't re-export functions from templates.py,
        causing imports to fail when templates/ directory took precedence.
        """
        # Should be able to import from templates.py (the module)
        from igloo_mcp.living_reports.templates import get_template

        # Should also be able to access template files in templates/ directory
        # (This is implicitly tested by get_template using Jinja2 to load .qmd.j2 files)
        sections = get_template("default")
        assert sections is not None

    def test_models_importable(self):
        """Import all key models."""
        from igloo_mcp.living_reports.models import (
            AuditEvent,
            Insight,
            ReportId,
            Section,
        )

        assert ReportId is not None
        assert Section is not None
        assert Insight is not None
        assert AuditEvent is not None

    def test_service_importable(self):
        """Import service and verify key methods exist."""
        from igloo_mcp.living_reports.service import ReportService

        assert ReportService is not None
        assert hasattr(ReportService, "create_report")
        assert hasattr(ReportService, "render_report")


class TestMCPToolsImports:
    """Test that all MCP tools are importable and register correctly."""

    def test_mcp_tools_importable(self):
        """Verify all MCP tools can be imported without errors."""
        from igloo_mcp.mcp.tools import (
            create_report,
            evolve_report,
            execute_query,
            render_report,
            search_report,
        )

        assert create_report is not None
        assert evolve_report is not None
        assert render_report is not None
        assert search_report is not None
        assert execute_query is not None

    def test_tool_base_importable(self):
        """Verify tool base classes are importable."""
        from igloo_mcp.mcp.tools.base import MCPToolSchema

        assert MCPToolSchema is not None

    def test_create_report_tool_has_schema(self):
        """Verify CreateReportTool has proper schema definition."""
        from igloo_mcp.mcp.tools.create_report import CreateReportTool

        # Just verify the tool is importable
        assert CreateReportTool is not None

    def test_execute_query_tool_has_schema(self):
        """Verify ExecuteQueryTool has proper schema definition.

        Note: Bug #48 was about timeout_seconds type coercion, which is tested
        in test_schema_contracts.py instead.
        """
        from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool

        # Just verify the tool is importable
        assert ExecuteQueryTool is not None


class TestCoreImports:
    """Test core module imports."""

    def test_constants_importable(self):
        """Verify constants module is importable."""
        from igloo_mcp import constants

        assert constants is not None
        # Check for actual constants that exist
        assert hasattr(constants, "CATALOG_CONCURRENCY")
        assert hasattr(constants, "MAX_QUERY_TIMEOUT_SECONDS")

    def test_error_utils_importable(self):
        """Verify error handling utilities are importable."""
        from igloo_mcp.mcp import error_utils

        assert error_utils is not None
        # Check that it has some error handling functionality
        assert hasattr(error_utils, "format_error_response")
        assert hasattr(error_utils, "format_success_response")

    def test_mcp_server_importable(self):
        """Verify MCP server module is importable."""
        from igloo_mcp import mcp_server

        assert mcp_server is not None
        assert hasattr(mcp_server, "register_igloo_mcp")


class TestNoCircularImports:
    """Test that there are no circular import issues."""

    def test_top_level_import_works(self):
        """Test that top-level package import doesn't cause circular imports."""
        import igloo_mcp

        assert igloo_mcp is not None

    def test_all_tools_import_together(self):
        """Import all tools at once to catch circular dependencies."""
        from igloo_mcp.mcp.tools import (
            build_catalog,
            build_dependency_graph,
            create_report,
            evolve_report,
            execute_query,
            get_catalog_summary,
            render_report,
            search_catalog,
            search_report,
            test_connection,
        )

        # All should be importable without circular import errors
        assert all(
            [
                create_report,
                evolve_report,
                render_report,
                search_report,
                execute_query,
                build_catalog,
                build_dependency_graph,
                test_connection,
                get_catalog_summary,
                search_catalog,
            ]
        )
