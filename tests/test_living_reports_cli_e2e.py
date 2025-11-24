"""End-to-end tests for living reports CLI commands."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import pytest

from igloo_mcp.cli import (
    _command_report_create,
    _command_report_render,
)


class TestLivingReportsCLIE2E:
    """End-to-end CLI integration tests."""

    @pytest.fixture
    def temp_reports_dir(self) -> Path:
        """Create temporary reports directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir) / "reports"
            reports_dir.mkdir()
            yield reports_dir

    def test_cli_render_command_end_to_end_success(
        self, temp_reports_dir: Path, capsys
    ) -> None:
        """Test complete CLI render workflow with mocked Quarto."""
        # 1. Create report via CLI
        with patch("igloo_mcp.cli.ReportService") as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service
            mock_service.create_report.return_value = "test_report_123"

            create_args = Mock()
            create_args.title = "CLI E2E Test Report"
            create_args.tags = ["e2e", "cli"]

            exit_code = _command_report_create(create_args)
            assert exit_code == 0

        # 2. Skip evolve step for now - evolve_report is experimental/stub
        # The test focuses on render workflow, not evolve

        # 3. Render report via CLI
        with patch("igloo_mcp.cli.ReportService") as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            render_args = Mock()
            render_args.selector = "CLI E2E Test Report"
            render_args.format = "html"
            render_args.open = False
            render_args.dry_run = False
            render_args.options = None

            mock_service.render_report.return_value = {
                "status": "success",
                "report_id": "test_report_123",
                "output": {
                    "format": "html",
                    "output_path": "/mock/path/report.html",
                    "assets_dir": "/mock/path/_files",
                },
                "warnings": ["Test warning"],
                "audit_action_id": "audit_456",
            }

            exit_code = _command_report_render(render_args)

            assert exit_code == 0
            mock_service.render_report.assert_called_once_with(
                report_id=ANY,
                format="html",
                options=None,
                open_browser=False,
                dry_run=False,
            )

            # Check output messages
            captured = capsys.readouterr()
            assert (
                "✓ Report rendered successfully: /mock/path/report.html" in captured.out
            )
            assert "⚠️  Warnings:" in captured.out
            assert "Test warning" in captured.out

    def test_cli_render_dry_run_workflow(self, capsys) -> None:
        """Test CLI dry run workflow."""
        with patch("igloo_mcp.cli.ReportService") as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            mock_service.render_report.return_value = {
                "status": "success",
                "report_id": "test_report_123",
                "output": {"format": "html"},
                "warnings": ["Dry run mode"],
            }

            args = Mock()
            args.selector = "Test Report"
            args.format = "html"
            args.open = False
            args.dry_run = True
            args.options = {"toc": True}

            exit_code = _command_report_render(args)

            assert exit_code == 0
            mock_service.render_report.assert_called_once_with(
                report_id=ANY,
                format="html",
                options={"toc": True},
                open_browser=False,
                dry_run=True,
            )

            captured = capsys.readouterr()
            assert "✓ QMD file generated successfully (dry run)" in captured.out
            assert "Dry run mode" in captured.out

    def test_cli_render_quarto_missing_workflow(self, capsys) -> None:
        """Test CLI workflow when Quarto is missing."""
        with patch("igloo_mcp.cli.ReportService") as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            mock_service.render_report.return_value = {
                "status": "quarto_missing",
                "report_id": "test_report_123",
                "error": "Quarto not found. Install from https://quarto.org/docs/get-started/",
            }

            args = Mock()
            args.selector = "Test Report"
            args.format = "html"
            args.open = False
            args.dry_run = False
            args.options = None

            exit_code = _command_report_render(args)

            assert exit_code == 1

            captured = capsys.readouterr()
            assert "❌ Quarto not found" in captured.err
            assert "https://quarto.org/docs/get-started/" in captured.err

    def test_cli_render_validation_failed_workflow(self, capsys) -> None:
        """Test CLI workflow when report validation fails."""
        with patch("igloo_mcp.cli.ReportService") as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            mock_service.render_report.return_value = {
                "status": "validation_failed",
                "report_id": "test_report_123",
                "validation_errors": [
                    "Section 'Analysis' references unknown insight 'missing_insight_123'",
                    "Insight 'orphan_insight' not referenced by any section",
                ],
            }

            args = Mock()
            args.selector = "Test Report"
            args.format = "html"
            args.open = False
            args.dry_run = False
            args.options = None

            exit_code = _command_report_render(args)

            assert exit_code == 1

            captured = capsys.readouterr()
            assert "❌ Report validation failed" in captured.err
            assert "missing_insight_123" in captured.err
            assert "orphan_insight" in captured.err

    def test_cli_render_with_browser_open_flag(self) -> None:
        """Test CLI render with browser open flag."""
        with patch("igloo_mcp.cli.ReportService") as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            mock_service.render_report.return_value = {
                "status": "success",
                "report_id": "test_report_123",
                "output": {"format": "html"},
            }

            args = Mock()
            args.selector = "Test Report"
            args.format = "html"
            args.open = True
            args.dry_run = False
            args.options = None

            exit_code = _command_report_render(args)

            assert exit_code == 0
            mock_service.render_report.assert_called_once_with(
                report_id=ANY,
                format="html",
                options=None,
                open_browser=True,
                dry_run=False,
            )

    def test_cli_render_selector_resolution(self) -> None:
        """Test that CLI render properly resolves report selectors."""
        with patch("igloo_mcp.cli.ReportService") as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            mock_service.render_report.return_value = {
                "status": "success",
                "report_id": "resolved_id_456",
                "output": {"format": "pdf"},
            }

            args = Mock()
            args.selector = "My Important Report"
            args.format = "pdf"
            args.open = False
            args.dry_run = False
            args.options = {"toc": True, "theme": "default"}

            exit_code = _command_report_render(args)

            assert exit_code == 0
            mock_service.render_report.assert_called_once_with(
                report_id="My Important Report",  # Passed as-is for service resolution
                format="pdf",
                options={"toc": True, "theme": "default"},
                open_browser=False,
                dry_run=False,
            )

    def test_cli_render_error_exit_codes(self) -> None:
        """Test that CLI render returns appropriate exit codes for errors."""
        test_cases = [
            ("quarto_missing", 1),
            ("validation_failed", 1),
            ("render_failed", 1),
            ("success", 0),
        ]

        for status, expected_exit_code in test_cases:
            with patch("igloo_mcp.cli.ReportService") as mock_service_class:
                mock_service = Mock()
                mock_service_class.return_value = mock_service

                mock_service.render_report.return_value = {
                    "status": status,
                    "report_id": "test_report_123",
                    "error": "Test error" if status != "success" else None,
                    "validation_errors": (
                        ["Test validation error"]
                        if status == "validation_failed"
                        else None
                    ),
                    "output": {"format": "html"} if status == "success" else None,
                }

                args = Mock()
                args.selector = "Test Report"
                args.format = "html"
                args.open = False
                args.dry_run = False
                args.options = None

                exit_code = _command_report_render(args)
                assert (
                    exit_code == expected_exit_code
                ), f"Expected {expected_exit_code} for status {status}, got {exit_code}"
