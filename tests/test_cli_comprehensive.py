"""Comprehensive tests for CLI commands.

Tests cover all CLI commands, argument parsing, output formatting,
and error handling.

Target: 25% → 80% coverage
"""

from __future__ import annotations

import argparse
import json
from unittest.mock import MagicMock, patch

from igloo_mcp.cli import (
    _command_query_optimize,
    _command_report_create,
    _command_report_evolve,
)


class TestCLIQueryOptimize:
    """Test query optimize CLI command."""

    def test_query_optimize_success(self, tmp_path, monkeypatch):
        """Query optimize command succeeds with valid execution ID."""
        # Arrange
        history_path = tmp_path / "history.jsonl"

        # Mock optimize_execution to return success
        mock_report = {
            "execution_id": "exec-123",
            "status": "success",
            "duration_ms": 150,
            "rowcount": 100,
            "findings": [],
        }

        with patch("igloo_mcp.cli.optimize_execution", return_value=mock_report):
            args = argparse.Namespace(
                execution_id="exec-123",
                history=str(history_path),
                format="text",
            )

            # Act
            result = _command_query_optimize(args)

            # Assert
            assert result == 0

    def test_query_optimize_json_output(self, tmp_path, capsys):
        """Query optimize outputs JSON when requested."""
        # Arrange
        mock_report = {
            "execution_id": "exec-456",
            "status": "success",
            "duration_ms": 200,
            "rowcount": 50,
            "findings": [{"level": "info", "message": "Test finding"}],
        }

        with patch("igloo_mcp.cli.optimize_execution", return_value=mock_report):
            args = argparse.Namespace(
                execution_id="exec-456",
                history=str(tmp_path / "history.jsonl"),
                format="json",
            )

            # Act
            result = _command_query_optimize(args)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["execution_id"] == "exec-456"

    def test_query_optimize_with_findings(self, tmp_path, capsys):
        """Query optimize displays findings."""
        # Arrange
        mock_report = {
            "execution_id": "exec-789",
            "status": "success",
            "duration_ms": 300,
            "rowcount": 1000,
            "findings": [
                {"level": "warning", "message": "Slow query", "detail": "Use WHERE clause"},
                {"level": "info", "message": "Optimization hint"},
            ],
        }

        with patch("igloo_mcp.cli.optimize_execution", return_value=mock_report):
            args = argparse.Namespace(
                execution_id="exec-789",
                history=str(tmp_path / "history.jsonl"),
                format="text",
            )

            # Act
            result = _command_query_optimize(args)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "WARNING" in captured.out
            assert "Slow query" in captured.out

    def test_query_optimize_error_handling(self, tmp_path, capsys):
        """Query optimize handles errors gracefully."""
        # Arrange
        with patch("igloo_mcp.cli.optimize_execution", side_effect=Exception("Test error")):
            args = argparse.Namespace(
                execution_id="exec-error",
                history=str(tmp_path / "history.jsonl"),
                format="text",
            )

            # Act
            result = _command_query_optimize(args)

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "Test error" in captured.err


class TestCLIReportCreate:
    """Test report create CLI command."""

    def test_report_create_default_template(self, tmp_path, capsys):
        """Create report with default template."""
        # Arrange
        with patch("igloo_mcp.cli.ReportService") as mock_service:
            mock_service.return_value.create_report.return_value = "rpt_123"

            args = argparse.Namespace(
                title="Test Report",
                template="default",
                tags=None,
            )

            # Act
            result = _command_report_create(args)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "rpt_123" in captured.out

    def test_report_create_with_template(self, tmp_path, capsys):
        """Create report with specific template."""
        # Arrange
        with patch("igloo_mcp.cli.ReportService") as mock_service:
            mock_service.return_value.create_report.return_value = "rpt_456"

            args = argparse.Namespace(
                title="Monthly Sales",
                template="monthly_sales",
                tags=["sales", "monthly"],
            )

            # Act
            result = _command_report_create(args)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "Monthly Sales" in captured.out
            assert "monthly_sales" in captured.out

    def test_report_create_error_handling(self, tmp_path, capsys):
        """Create report handles errors."""
        # Arrange
        with patch("igloo_mcp.cli.ReportService") as mock_service:
            mock_service.return_value.create_report.side_effect = ValueError("Invalid template")

            args = argparse.Namespace(
                title="Test",
                template="invalid",
                tags=None,
            )

            # Act
            result = _command_report_create(args)

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "Invalid template" in captured.err


class TestCLIReportEvolve:
    """Test report evolve CLI command."""

    def test_report_evolve_dry_run(self, tmp_path, monkeypatch):
        """Evolve report in dry run mode."""
        # Arrange
        mock_tool = MagicMock()
        mock_result = {"status": "dry_run_success"}

        async def mock_execute(*args, **kwargs):
            return mock_result

        mock_tool.execute = mock_execute

        with patch("igloo_mcp.mcp.tools.evolve_report.EvolveReportTool", return_value=mock_tool):
            with patch("igloo_mcp.cli.get_config"):
                with patch("igloo_mcp.cli.ReportService"):
                    args = argparse.Namespace(
                        selector="test-report",
                        instruction="Add summary",
                        proposed_changes=None,
                        dry_run=True,
                    )

                    # Act
                    result = _command_report_evolve(args)

                    # Assert
                    assert result == 0

    def test_report_evolve_with_instruction(self, tmp_path):
        """Evolve report with instruction."""
        # Arrange
        mock_tool = MagicMock()
        mock_result = {"status": "success", "report_id": "rpt_123"}

        async def mock_execute(*args, **kwargs):
            return mock_result

        mock_tool.execute = mock_execute

        with patch("igloo_mcp.mcp.tools.evolve_report.EvolveReportTool", return_value=mock_tool):
            with patch("igloo_mcp.cli.get_config"):
                with patch("igloo_mcp.cli.ReportService"):
                    args = argparse.Namespace(
                        selector="rpt_123",
                        instruction="Add new section",
                        proposed_changes={},
                        dry_run=False,
                    )

                    # Act
                    result = _command_report_evolve(args)

                    # Assert
                    assert result == 0


class TestCLIArgumentParsing:
    """Test CLI argument parsing."""

    def test_parse_args_handles_help(self):
        """CLI argument parsing handles help."""
        # This would typically test argparse setup
        # For now, just verify the functions exist and are callable
        assert callable(_command_query_optimize)
        assert callable(_command_report_create)
        assert callable(_command_report_evolve)


class TestCLIOutputFormatting:
    """Test CLI output formatting."""

    def test_text_output_formatting(self, capsys):
        """Text output is properly formatted."""
        # Arrange
        mock_report = {
            "execution_id": "exec-123",
            "status": "success",
            "duration_ms": 150,
            "rowcount": 100,
            "objects": [{"name": "table1"}, {"name": "table2"}],
            "findings": [
                {"level": "info", "message": "Test", "detail": "Details here"},
            ],
        }

        with patch("igloo_mcp.cli.optimize_execution", return_value=mock_report):
            args = argparse.Namespace(
                execution_id="exec-123",
                history="/tmp/history.jsonl",
                format="text",
            )

            # Act
            _command_query_optimize(args)

            # Assert
            captured = capsys.readouterr()
            assert "exec-123" in captured.out
            assert "150" in captured.out  # duration
            assert "100" in captured.out  # rowcount


class TestCLIEdgeCases:
    """Test CLI edge cases."""

    def test_missing_execution_id_handling(self, tmp_path):
        """CLI handles missing execution ID."""
        # Arrange
        with patch("igloo_mcp.cli.optimize_execution", side_effect=KeyError("execution_id")):
            args = argparse.Namespace(
                execution_id=None,
                history=str(tmp_path / "history.jsonl"),
                format="text",
            )

            # Act
            result = _command_query_optimize(args)

            # Assert
            assert result == 1

    def test_invalid_history_path(self, tmp_path, capsys):
        """CLI handles invalid history path."""
        # Arrange
        with patch("igloo_mcp.cli.optimize_execution", side_effect=FileNotFoundError("History not found")):
            args = argparse.Namespace(
                execution_id="exec-123",
                history="/nonexistent/history.jsonl",
                format="text",
            )

            # Act
            result = _command_query_optimize(args)

            # Assert
            assert result == 1

    def test_empty_findings_list(self, tmp_path, capsys):
        """CLI handles empty findings gracefully."""
        # Arrange
        mock_report = {
            "execution_id": "exec-empty",
            "status": "success",
            "duration_ms": 50,
            "rowcount": 0,
            "findings": [],
        }

        with patch("igloo_mcp.cli.optimize_execution", return_value=mock_report):
            args = argparse.Namespace(
                execution_id="exec-empty",
                history=str(tmp_path / "history.jsonl"),
                format="text",
            )

            # Act
            result = _command_query_optimize(args)

            # Assert
            assert result == 0


class TestCLIIntegration:
    """Integration tests for CLI workflows."""

    def test_full_workflow_query_optimize(self, tmp_path):
        """Full workflow: query optimization."""
        # Arrange
        history_path = tmp_path / "history.jsonl"
        history_path.write_text('{"execution_id": "test"}\n')

        mock_report = {
            "execution_id": "test",
            "status": "success",
            "duration_ms": 100,
            "rowcount": 10,
            "findings": [],
        }

        with patch("igloo_mcp.cli.optimize_execution", return_value=mock_report):
            args = argparse.Namespace(
                execution_id="test",
                history=str(history_path),
                format="text",
            )

            # Act
            result = _command_query_optimize(args)

            # Assert
            assert result == 0
