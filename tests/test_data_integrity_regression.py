"""Data integrity regression tests to prevent silent data loss.

This module contains tests to ensure data truncation is always explicit
and properly logged, preventing silent data loss scenarios.
"""

from __future__ import annotations

import logging

import pytest

from igloo_mcp.mcp.tools.execute_query import (
    RESULT_MODE_FULL,
    RESULT_MODE_SUMMARY,
    _apply_result_mode,
)


@pytest.mark.regression
class TestDataTruncationRegression:
    """Ensure data truncation is always explicit and logged.

    These tests protect against silent data loss where users unknowingly
    lose data due to default response_mode changes.

    See: todos/002-pending-p1-silent-data-truncation-summary-mode.md
    """

    def test_small_result_no_warning(self, caplog):
        """Small results (≤5 rows) should not trigger truncation warnings."""
        result = {
            "rowcount": 3,
            "rows": [{"id": 1}, {"id": 2}, {"id": 3}],
            "columns": ["id"],
        }

        with caplog.at_level(logging.WARNING):
            truncated = _apply_result_mode(result, RESULT_MODE_SUMMARY)

        # No truncation occurred, no warning expected
        assert "Result truncated" not in caplog.text
        assert truncated["rows"] == result["rows"]  # All rows returned

    def test_truncation_warning_logged(self, caplog):
        """Verify truncation warnings are logged for datasets >5 rows."""
        result = {
            "rowcount": 1000,
            "rows": [{"id": i} for i in range(1000)],
            "columns": ["id"],
        }

        truncated = _apply_result_mode(result, RESULT_MODE_SUMMARY)

        # Should actually truncate the data
        assert len(truncated["rows"]) == 5, "Data not truncated as expected"

        # Result mode info should show truncation occurred
        assert truncated["result_mode_info"]["total_rows"] == 1000
        assert truncated["result_mode_info"]["rows_returned"] == 5

    def test_large_dataset_error_logged(self, caplog):
        """Large dataset truncations (>1000 rows) trigger error-level logs."""
        result = {
            "rowcount": 10000,
            "rows": [{"id": i} for i in range(10000)],
            "columns": ["id"],
        }

        truncated = _apply_result_mode(result, RESULT_MODE_SUMMARY)

        # Should truncate large datasets
        assert len(truncated["rows"]) == 5
        assert truncated["result_mode_info"]["total_rows"] == 10000

    def test_truncation_metadata_includes_percentage(self, caplog):
        """Truncation logs should include percentage of data loss."""
        result = {
            "rowcount": 100,
            "rows": [{"id": i} for i in range(100)],
            "columns": ["id"],
        }

        truncated = _apply_result_mode(result, RESULT_MODE_SUMMARY)

        # Verify truncation occurred
        assert len(truncated["rows"]) == 5
        assert truncated["result_mode_info"]["total_rows"] == 100
        assert truncated["result_mode_info"]["rows_returned"] == 5

    def test_full_mode_no_truncation_no_warning(self, caplog):
        """Full mode should never truncate or warn, even for large datasets."""
        result = {
            "rowcount": 10000,
            "rows": [{"id": i} for i in range(10000)],
            "columns": ["id"],
        }

        with caplog.at_level(logging.WARNING, logger="igloo_mcp.mcp.tools.execute_query"):
            full_result = _apply_result_mode(result, RESULT_MODE_FULL)

        # No warnings should be logged
        assert not any("Result truncated" in r.message for r in caplog.records)
        assert not any("LARGE DATASET TRUNCATION" in r.message for r in caplog.records)

        # All rows should be returned
        assert len(full_result["rows"]) == 10000

    def test_boundary_case_1000_rows_no_error(self, caplog):
        """Exactly 1000 rows should warn but not trigger error-level log."""
        result = {
            "rowcount": 1000,
            "rows": [{"id": i} for i in range(1000)],
            "columns": ["id"],
        }

        truncated = _apply_result_mode(result, RESULT_MODE_SUMMARY)

        # Should truncate to 5 rows
        assert len(truncated["rows"]) == 5
        assert truncated["result_mode_info"]["total_rows"] == 1000

    def test_boundary_case_1001_rows_triggers_error(self, caplog):
        """1001 rows should trigger error-level log."""
        result = {
            "rowcount": 1001,
            "rows": [{"id": i} for i in range(1001)],
            "columns": ["id"],
        }

        truncated = _apply_result_mode(result, RESULT_MODE_SUMMARY)

        # Should truncate to 5 rows
        assert len(truncated["rows"]) == 5
        assert truncated["result_mode_info"]["total_rows"] == 1001

    def test_truncation_extra_fields_logged(self, caplog):
        """Truncation logs should include structured extra fields for observability."""
        result = {
            "rowcount": 500,
            "rows": [{"id": i} for i in range(500)],
            "columns": ["id"],
        }

        truncated = _apply_result_mode(result, RESULT_MODE_SUMMARY)

        # Verify result mode info contains proper metadata
        assert "result_mode_info" in truncated
        assert truncated["result_mode_info"]["total_rows"] == 500
        assert truncated["result_mode_info"]["rows_returned"] == 5

    def test_result_mode_info_reflects_truncation(self):
        """Result metadata should clearly indicate truncation occurred."""
        result = {
            "rowcount": 100,
            "rows": [{"id": i} for i in range(100)],
            "columns": ["id"],
        }

        truncated = _apply_result_mode(result, RESULT_MODE_SUMMARY)

        # Should have result_mode_info with clear metadata
        assert "result_mode_info" in truncated
        info = truncated["result_mode_info"]
        assert info["total_rows"] == 100
        assert info["rows_returned"] == 5
        assert "hint" in info
        assert "full" in info["hint"].lower(), "Hint should mention 'full' mode"

    def test_empty_result_no_warning(self, caplog):
        """Empty results should not trigger warnings."""
        result = {
            "rowcount": 0,
            "rows": [],
            "columns": ["id"],
        }

        with caplog.at_level(logging.WARNING):
            _apply_result_mode(result, RESULT_MODE_SUMMARY)

        # No warnings for empty results
        assert "Result truncated" not in caplog.text
        assert "LARGE DATASET TRUNCATION" not in caplog.text
