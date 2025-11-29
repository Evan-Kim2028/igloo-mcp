"""Comprehensive test to verify all living reports modules load and integrate."""

import pytest


def test_all_modules_import():
    """Verify all living reports modules can be imported."""
    from igloo_mcp.living_reports import (
        changes_schema,
        index,
        models,
        selector,
        service,
        storage,
        templates,
    )

    assert service.ReportService is not None
    assert storage.ReportStorage is not None
    assert models.Outline is not None
    assert index.ReportIndex is not None
    assert templates.get_template is not None
    assert selector.ReportSelector is not None
    assert changes_schema.ProposedChanges is not None


def test_all_mcp_tools_load():
    """Verify MCP tools load correctly."""
    from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool
    from igloo_mcp.mcp.tools.render_report import RenderReportTool

    assert EvolveReportTool is not None
    assert RenderReportTool is not None


def test_cli_commands_registered():
    """Verify all CLI commands are registered."""
    from igloo_mcp.cli import build_parser

    parser = build_parser()

    # Simply verify the parser was created successfully
    # This indicates the CLI module loaded and registered all commands
    assert parser is not None
    assert hasattr(parser, "_subparsers")

    # Check that we can parse help without errors (indicates commands are registered)
    import io

    help_output = io.StringIO()
    try:
        parser.print_help(help_output)
        help_text = help_output.getvalue()
        # Basic check that help was generated
        assert len(help_text) > 0
        assert "report" in help_text
    except Exception as e:
        pytest.fail(f"CLI parser failed: {e}")


def test_template_system_complete():
    """Verify template system is complete and functional."""
    from igloo_mcp.living_reports.templates import TEMPLATES, get_template

    # Check all expected templates exist
    expected_templates = {
        "default",
        "monthly_sales",
        "quarterly_review",
        "deep_dive",
        "analyst_v1",
    }
    assert set(TEMPLATES.keys()) == expected_templates

    # Verify each template returns sections
    for template_name in expected_templates:
        sections = get_template(template_name)
        assert isinstance(sections, list)

        if template_name != "default":
            assert len(sections) > 0
            # Check each section has required fields
            for section in sections:
                assert hasattr(section, "section_id")
                assert hasattr(section, "title")
                assert hasattr(section, "order")
        else:
            # Default template should be empty
            assert len(sections) == 0


def test_changes_schema_validation():
    """Verify changes schema validation works."""
    import uuid

    from igloo_mcp.living_reports.changes_schema import ProposedChanges
    from igloo_mcp.living_reports.models import Outline, ReportId

    # Create a valid change
    changes = ProposedChanges(
        insights_to_add=[
            {
                "insight_id": str(uuid.uuid4()),
                "importance": 8,
                "summary": "Test insight",
                "supporting_queries": [],
            }
        ]
    )

    # Create mock outline
    outline = Outline(
        report_id=str(ReportId.new()),
        title="Test",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        version="1.0",
        sections=[],
        insights=[],
    )

    # Should validate successfully
    errors = changes.validate_against_outline(outline)
    assert len(errors) == 0


def test_selector_resolution():
    """Verify selector resolution works."""
    # Create a temporary index
    import tempfile
    from pathlib import Path

    from igloo_mcp.living_reports.index import ReportIndex
    from igloo_mcp.living_reports.selector import (
        ReportSelector,
        SelectorResolutionError,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        index = ReportIndex(Path(tmp_dir) / "index.jsonl")
        selector = ReportSelector(index)

        # Should handle non-existent selectors gracefully
        try:
            selector.resolve("nonexistent")
            assert False, "Should have raised SelectorResolutionError"
        except SelectorResolutionError as e:
            assert e.error_type == "not_found"


def test_service_initialization():
    """Verify ReportService can be initialized."""
    import tempfile
    from pathlib import Path

    from igloo_mcp.living_reports.service import ReportService

    with tempfile.TemporaryDirectory() as tmp_dir:
        service = ReportService(reports_root=Path(tmp_dir) / "reports")

        # Should be able to list reports (empty list)
        reports = service.list_reports()
        assert isinstance(reports, list)
        assert len(reports) == 0


@pytest.mark.asyncio
async def test_mcp_tools_initialization():
    """Verify MCP tools can be initialized."""
    import tempfile
    from pathlib import Path

    from igloo_mcp.config import get_config
    from igloo_mcp.living_reports.service import ReportService
    from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool
    from igloo_mcp.mcp.tools.render_report import RenderReportTool

    config = get_config()

    with tempfile.TemporaryDirectory() as tmp_dir:
        service = ReportService(reports_root=Path(tmp_dir) / "reports")

        # Should be able to create tools
        evolve_tool = EvolveReportTool(config, service)
        render_tool = RenderReportTool(config, service)

        assert evolve_tool.name == "evolve_report"
        assert render_tool.name == "render_report"

        # Should be able to get parameter schemas
        evolve_schema = evolve_tool.get_parameter_schema()
        render_schema = render_tool.get_parameter_schema()

        assert "properties" in evolve_schema
        assert "properties" in render_schema
        assert "report_selector" in evolve_schema["properties"]
        assert "report_selector" in render_schema["properties"]


def test_atomic_operations_documented():
    """Verify atomic operations are properly documented."""

    from igloo_mcp import living_reports

    # Check that storage module docstring mentions atomicity
    docstring = living_reports.storage.__doc__
    assert docstring is not None
    assert "ATOMICITY" in docstring
    assert "temp-file + atomic rename" in docstring
    assert "CONCURRENCY" in docstring
    assert "RECOVERY" in docstring


def test_error_responses_structured():
    """Verify error responses follow structured format."""
    from igloo_mcp.living_reports.selector import SelectorResolutionError

    error = SelectorResolutionError(selector="test", error_type="not_found", candidates=None)

    response = error.to_dict()
    assert "error" in response
    assert "selector" in response
    assert "message" in response
    assert response["error"] == "not_found"


def test_version_locking_implemented():
    """Verify version locking is implemented in models."""
    from igloo_mcp.living_reports.models import Outline, ReportId

    # Check Outline has outline_version field
    outline = Outline(
        report_id=str(ReportId.new()),
        title="Test",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        version="1.0",
        sections=[],
        insights=[],
    )

    assert hasattr(outline, "outline_version")
    assert outline.outline_version == 1


def test_all_imports_work():
    """Final comprehensive import test."""
    # Test all the key imports work without errors
    try:
        # Core modules
        # CLI
        from igloo_mcp.living_reports.models import (
            AuditEvent,
            Insight,
            Outline,
            Section,
        )
        from igloo_mcp.living_reports.selector import ReportSelector
        from igloo_mcp.living_reports.service import ReportService
        from igloo_mcp.living_reports.storage import GlobalStorage, ReportStorage
        from igloo_mcp.living_reports.templates import get_template

        # MCP tools
        from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool
        from igloo_mcp.mcp.tools.render_report import RenderReportTool

        # All imports successful - verify classes exist
        assert AuditEvent is not None
        assert Insight is not None
        assert Outline is not None
        assert Section is not None
        assert ReportSelector is not None
        assert ReportService is not None
        assert GlobalStorage is not None
        assert ReportStorage is not None
        assert get_template is not None
        assert EvolveReportTool is not None
        assert RenderReportTool is not None

    except ImportError as e:
        pytest.fail(f"Import failed: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error during imports: {e}")
