"""Tests for living reports CLI commands."""

from __future__ import annotations

from unittest.mock import ANY, Mock, patch

import pytest

from igloo_mcp.cli import (
    _command_report_create,
    _command_report_evolve,
    _command_report_list,
    _command_report_render,
    _command_report_revert,
)


class TestReportCLI:
    """Test report CLI commands."""

    @pytest.fixture
    def mock_service(self) -> Mock:
        """Create mock report service."""
        service = Mock()
        return service

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_create_success(
        self, mock_service_class: Mock, mock_service: Mock
    ) -> None:
        """Test successful report creation."""
        mock_service_class.return_value = mock_service
        mock_service.create_report.return_value = "test_report_id"

        # Create mock args
        args = Mock()
        args.title = "Test Report"
        args.tags = ["tag1", "tag2"]

        exit_code = _command_report_create(args)

        assert exit_code == 0
        mock_service.create_report.assert_called_once_with(
            "Test Report", tags=["tag1", "tag2"]
        )

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_create_failure(
        self, mock_service_class: Mock, mock_service: Mock
    ) -> None:
        """Test report creation failure."""
        mock_service_class.return_value = mock_service
        mock_service.create_report.side_effect = Exception("Creation failed")

        args = Mock()
        args.title = "Test Report"
        args.tags = []

        exit_code = _command_report_create(args)

        assert exit_code == 1

    @patch("igloo_mcp.cli.ReportService")
    @patch("igloo_mcp.cli.get_config")
    @patch("igloo_mcp.mcp.tools.evolve_report.EvolveReportTool")
    def test_command_report_evolve_success(
        self,
        mock_tool_class: Mock,
        mock_get_config: Mock,
        mock_service_class: Mock,
        mock_service: Mock,
    ) -> None:
        """Test successful report evolution."""

        mock_service_class.return_value = mock_service
        mock_get_config.return_value = Mock()

        mock_tool = Mock()
        mock_tool_class.return_value = mock_tool

        async def mock_execute(**kwargs):
            return {"status": "success", "report_id": "test_id"}

        mock_tool.execute = mock_execute

        args = Mock()
        args.selector = "test-report"
        args.instruction = "Add insights"
        args.dry_run = False
        args.proposed_changes = {}

        exit_code = _command_report_evolve(args)

        assert exit_code == 0

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_evolve_validation_failure(
        self,
        mock_service_class: Mock,
        mock_service: Mock,
    ) -> None:
        """Test report evolution with validation failure."""

        mock_service_class.return_value = mock_service

        with (
            patch("igloo_mcp.cli.get_config"),
            patch(
                "igloo_mcp.mcp.tools.evolve_report.EvolveReportTool"
            ) as mock_tool_class,
        ):

            mock_tool = Mock()
            mock_tool_class.return_value = mock_tool

            async def mock_execute(**kwargs):
                return {
                    "status": "validation_failed",
                    "validation_issues": ["Invalid change"],
                }

            mock_tool.execute = mock_execute

            args = Mock()
            args.selector = "test-report"
            args.instruction = "Invalid instruction"
            args.dry_run = False
            args.proposed_changes = {}

            exit_code = _command_report_evolve(args)

            assert exit_code == 1

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_list_success(
        self, mock_service_class: Mock, mock_service: Mock
    ) -> None:
        """Test successful report listing."""
        mock_service_class.return_value = mock_service
        mock_service.list_reports.return_value = [
            {
                "id": "report1",
                "title": "Report One",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "status": "active",
                "tags": ["tag1"],
            }
        ]

        args = Mock()
        args.status = None
        args.tags = None

        exit_code = _command_report_list(args)

        assert exit_code == 0
        mock_service.list_reports.assert_called_once_with(status=None, tags=None)

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_list_empty(
        self, mock_service_class: Mock, mock_service: Mock
    ) -> None:
        """Test report listing with no reports."""
        mock_service_class.return_value = mock_service
        mock_service.list_reports.return_value = []

        args = Mock()
        args.status = None
        args.tags = None

        exit_code = _command_report_list(args)

        assert exit_code == 0

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_render_success_html(
        self, mock_service_class: Mock, mock_service: Mock, capsys
    ) -> None:
        """Test successful HTML report rendering."""
        mock_service_class.return_value = mock_service
        mock_service.render_report.return_value = {
            "status": "success",
            "report_id": "test_report_id",
            "output": {"format": "html", "output_path": "/path/to/report.html"},
            "warnings": [],
        }

        args = Mock()
        args.selector = "test-report"
        args.format = "html"
        args.open = False
        args.dry_run = False
        args.options = None

        exit_code = _command_report_render(args)

        assert exit_code == 0
        mock_service.render_report.assert_called_once_with(
            report_id=ANY,
            format="html",
            options=None,
            open_browser=False,
            dry_run=False,
        )

        captured = capsys.readouterr()
        assert "✓ Report rendered successfully: /path/to/report.html" in captured.out

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_render_success_with_warnings(
        self, mock_service_class: Mock, mock_service: Mock, capsys
    ) -> None:
        """Test successful rendering with warnings."""
        mock_service_class.return_value = mock_service
        mock_service.render_report.return_value = {
            "status": "success",
            "report_id": "test_report_id",
            "output": {"format": "pdf", "output_path": "/path/to/report.pdf"},
            "warnings": ["Version warning", "Dataset warning"],
        }

        args = Mock()
        args.selector = "test-report"
        args.format = "pdf"
        args.open = False
        args.dry_run = False
        args.options = {"toc": True}

        exit_code = _command_report_render(args)

        assert exit_code == 0
        mock_service.render_report.assert_called_once_with(
            report_id=ANY,
            format="pdf",
            options={"toc": True},
            open_browser=False,
            dry_run=False,
        )

        captured = capsys.readouterr()
        assert "✓ Report rendered successfully: /path/to/report.pdf" in captured.out
        assert "⚠️  Warnings:" in captured.out
        assert "Version warning" in captured.out
        assert "Dataset warning" in captured.out

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_render_dry_run(
        self, mock_service_class: Mock, mock_service: Mock, capsys
    ) -> None:
        """Test dry run rendering."""
        mock_service_class.return_value = mock_service
        mock_service.render_report.return_value = {
            "status": "success",
            "report_id": "test_report_id",
            "output": {"format": "html"},
            "warnings": ["Dry run mode"],
        }

        args = Mock()
        args.selector = "test-report"
        args.format = "html"
        args.open = False
        args.dry_run = True
        args.options = None

        exit_code = _command_report_render(args)

        assert exit_code == 0
        mock_service.render_report.assert_called_once_with(
            report_id=ANY, format="html", options=None, open_browser=False, dry_run=True
        )

        captured = capsys.readouterr()
        assert "✓ QMD file generated successfully (dry run)" in captured.out

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_render_with_browser_open(
        self, mock_service_class: Mock, mock_service: Mock
    ) -> None:
        """Test rendering with browser opening."""
        mock_service_class.return_value = mock_service
        mock_service.render_report.return_value = {
            "status": "success",
            "report_id": "test_report_id",
            "output": {"format": "html"},
        }

        args = Mock()
        args.selector = "test-report"
        args.format = "html"
        args.open = True
        args.dry_run = False
        args.options = None

        exit_code = _command_report_render(args)

        assert exit_code == 0
        mock_service.render_report.assert_called_once_with(
            report_id=ANY, format="html", options=None, open_browser=True, dry_run=False
        )

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_render_quarto_missing(
        self, mock_service_class: Mock, mock_service: Mock, capsys
    ) -> None:
        """Test rendering when Quarto is missing."""
        mock_service_class.return_value = mock_service
        mock_service.render_report.return_value = {
            "status": "quarto_missing",
            "report_id": "test_report_id",
            "error": "Quarto not found. Install from https://quarto.org/docs/get-started/",
        }

        args = Mock()
        args.selector = "test-report"
        args.format = "html"
        args.open = False
        args.dry_run = False
        args.options = None

        exit_code = _command_report_render(args)

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "❌ Quarto not found" in captured.err
        assert "https://quarto.org/docs/get-started/" in captured.err

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_render_validation_failed(
        self, mock_service_class: Mock, mock_service: Mock, capsys
    ) -> None:
        """Test rendering when report validation fails."""
        mock_service_class.return_value = mock_service
        mock_service.render_report.return_value = {
            "status": "validation_failed",
            "report_id": "test_report_id",
            "validation_errors": ["Section references unknown insight"],
        }

        args = Mock()
        args.selector = "test-report"
        args.format = "html"
        args.open = False
        args.dry_run = False
        args.options = None

        exit_code = _command_report_render(args)

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "❌ Report validation failed" in captured.err
        assert "Section references unknown insight" in captured.err

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_render_generic_failure(
        self, mock_service_class: Mock, mock_service: Mock, capsys
    ) -> None:
        """Test rendering with generic failure."""
        mock_service_class.return_value = mock_service
        mock_service.render_report.return_value = {
            "status": "render_failed",
            "report_id": "test_report_id",
            "error": "Rendering failed due to Quarto error",
        }

        args = Mock()
        args.selector = "test-report"
        args.format = "html"
        args.open = False
        args.dry_run = False
        args.options = None

        exit_code = _command_report_render(args)

        assert exit_code == 1

        captured = capsys.readouterr()
        assert (
            "❌ Rendering failed: Rendering failed due to Quarto error" in captured.err
        )

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_render_selector_resolution(
        self, mock_service_class: Mock, mock_service: Mock
    ) -> None:
        """Test that render command resolves selectors correctly."""
        mock_service_class.return_value = mock_service
        mock_service.render_report.return_value = {
            "status": "success",
            "report_id": "resolved_id_123",
            "output": {"format": "html"},
        }

        args = Mock()
        args.selector = "My Report Title"
        args.format = "html"
        args.open = False
        args.dry_run = False
        args.options = None

        exit_code = _command_report_render(args)

        assert exit_code == 0
        mock_service.render_report.assert_called_once_with(
            report_id="My Report Title",  # Selector passed as-is for service resolution
            format="html",
            options=None,
            open_browser=False,
            dry_run=False,
        )

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_render_json_options_parsing(
        self, mock_service_class: Mock, mock_service: Mock
    ) -> None:
        """Test JSON options parsing in render command."""
        mock_service_class.return_value = mock_service
        mock_service.render_report.return_value = {
            "status": "success",
            "report_id": "test_report_id",
            "output": {"format": "html"},
        }

        args = Mock()
        args.selector = "test-report"
        args.format = "html"
        args.open = False
        args.dry_run = False
        args.options = {"toc": True, "theme": "cosmo"}

        exit_code = _command_report_render(args)

        assert exit_code == 0
        mock_service.render_report.assert_called_once_with(
            report_id=ANY,
            format="html",
            options={"toc": True, "theme": "cosmo"},
            open_browser=False,
            dry_run=False,
        )

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_render_unexpected_error(
        self, mock_service_class: Mock, mock_service: Mock, capsys
    ) -> None:
        """Test handling of unexpected errors in render command."""
        mock_service_class.return_value = mock_service
        mock_service.render_report.side_effect = Exception("Unexpected error occurred")

        args = Mock()
        args.selector = "test-report"
        args.format = "html"
        args.open = False
        args.dry_run = False
        args.options = None

        exit_code = _command_report_render(args)

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "Failed to render report: Unexpected error occurred" in captured.err

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_revert_success(
        self, mock_service_class: Mock, mock_service: Mock
    ) -> None:
        """Test successful report revert."""
        mock_service_class.return_value = mock_service
        mock_service.resolve_report_selector.return_value = "test_report_id"

        args = Mock()
        args.selector = "test-report"
        args.action_id = "action_123"

        exit_code = _command_report_revert(args)

        assert exit_code == 0
        mock_service.resolve_report_selector.assert_called_once_with("test-report")
        mock_service.revert_report.assert_called_once_with(
            "test_report_id", "action_123"
        )

    @patch("igloo_mcp.cli.ReportService")
    def test_command_report_revert_failure(
        self, mock_service_class: Mock, mock_service: Mock
    ) -> None:
        """Test report revert failure."""
        mock_service_class.return_value = mock_service
        mock_service.revert_report.side_effect = ValueError("Revert failed")

        args = Mock()
        args.selector = "test-report"
        args.action_id = "action_123"

        exit_code = _command_report_revert(args)

        assert exit_code == 1
