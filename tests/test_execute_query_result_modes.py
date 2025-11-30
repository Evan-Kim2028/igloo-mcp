"""Tests for execute_query result_mode parameter.

Tests the new result_mode feature that allows controlling response verbosity
to reduce token usage (inspired by Morph MCP's context pollution prevention).
"""

from __future__ import annotations

import pytest

from igloo_mcp.mcp.tools.execute_query import (
    RESULT_MODE_FULL,
    RESULT_MODE_SAMPLE,
    RESULT_MODE_SAMPLE_SIZE,
    RESULT_MODE_SCHEMA_ONLY,
    RESULT_MODE_SUMMARY,
    RESULT_MODE_SUMMARY_SAMPLE_SIZE,
    _apply_result_mode,
)


class TestApplyResultMode:
    """Tests for the _apply_result_mode helper function."""

    @pytest.fixture
    def sample_result(self) -> dict:
        """Create a sample query result for testing."""
        return {
            "rows": [{"id": i, "name": f"row_{i}", "value": i * 10} for i in range(100)],
            "rowcount": 100,
            "columns": ["id", "name", "value"],
            "key_metrics": {
                "total_rows": 100,
                "sampled_rows": 100,
                "num_columns": 3,
            },
            "statement": "SELECT * FROM test_table",
            "query_id": "test-query-id",
            "duration_ms": 150,
        }

    def test_full_mode_returns_all_rows(self, sample_result: dict) -> None:
        """Full mode should return all rows unchanged."""
        result = _apply_result_mode(dict(sample_result), RESULT_MODE_FULL)

        assert len(result["rows"]) == 100
        assert "result_mode" not in result  # Full mode doesn't add metadata
        assert "result_mode_info" not in result

    def test_summary_mode_returns_limited_rows(self, sample_result: dict) -> None:
        """Summary mode should return only RESULT_MODE_SUMMARY_SAMPLE_SIZE rows."""
        result = _apply_result_mode(dict(sample_result), RESULT_MODE_SUMMARY)

        assert len(result["rows"]) == RESULT_MODE_SUMMARY_SAMPLE_SIZE
        assert result["result_mode"] == "summary"
        assert result["result_mode_info"]["mode"] == "summary"
        assert result["result_mode_info"]["total_rows"] == 100
        assert result["result_mode_info"]["rows_returned"] == RESULT_MODE_SUMMARY_SAMPLE_SIZE
        assert result["result_mode_info"]["sample_size"] == RESULT_MODE_SUMMARY_SAMPLE_SIZE
        assert "hint" in result["result_mode_info"]

    def test_schema_only_mode_returns_no_rows(self, sample_result: dict) -> None:
        """Schema only mode should return empty rows but preserve metadata."""
        result = _apply_result_mode(dict(sample_result), RESULT_MODE_SCHEMA_ONLY)

        assert len(result["rows"]) == 0
        assert result["result_mode"] == "schema_only"
        assert result["result_mode_info"]["mode"] == "schema_only"
        assert result["result_mode_info"]["total_rows"] == 100
        assert result["result_mode_info"]["rows_returned"] == 0
        # Columns should still be present
        assert result["columns"] == ["id", "name", "value"]
        # Key metrics should still be present
        assert result["key_metrics"] is not None

    def test_sample_mode_returns_limited_rows(self, sample_result: dict) -> None:
        """Sample mode should return only RESULT_MODE_SAMPLE_SIZE rows."""
        result = _apply_result_mode(dict(sample_result), RESULT_MODE_SAMPLE)

        assert len(result["rows"]) == RESULT_MODE_SAMPLE_SIZE
        assert result["result_mode"] == "sample"
        assert result["result_mode_info"]["mode"] == "sample"
        assert result["result_mode_info"]["total_rows"] == 100
        assert result["result_mode_info"]["rows_returned"] == RESULT_MODE_SAMPLE_SIZE
        assert result["result_mode_info"]["sample_size"] == RESULT_MODE_SAMPLE_SIZE

    def test_small_result_with_summary_mode(self) -> None:
        """Summary mode with fewer rows than sample size should return all rows."""
        small_result = {
            "rows": [{"id": i} for i in range(3)],
            "rowcount": 3,
            "columns": ["id"],
        }
        result = _apply_result_mode(dict(small_result), RESULT_MODE_SUMMARY)

        assert len(result["rows"]) == 3
        assert result["result_mode_info"]["total_rows"] == 3
        assert result["result_mode_info"]["rows_returned"] == 3
        # No hint needed when all rows returned
        assert result["result_mode_info"]["hint"] is None

    def test_small_result_with_sample_mode(self) -> None:
        """Sample mode with fewer rows than sample size should return all rows."""
        small_result = {
            "rows": [{"id": i} for i in range(5)],
            "rowcount": 5,
            "columns": ["id"],
        }
        result = _apply_result_mode(dict(small_result), RESULT_MODE_SAMPLE)

        assert len(result["rows"]) == 5
        assert result["result_mode_info"]["total_rows"] == 5
        assert result["result_mode_info"]["rows_returned"] == 5
        # No hint needed when all rows returned
        assert result["result_mode_info"]["hint"] is None

    def test_empty_result_with_all_modes(self) -> None:
        """All modes should handle empty results gracefully."""
        empty_result = {
            "rows": [],
            "rowcount": 0,
            "columns": ["id", "name"],
        }

        for mode in [RESULT_MODE_FULL, RESULT_MODE_SUMMARY, RESULT_MODE_SCHEMA_ONLY, RESULT_MODE_SAMPLE]:
            result = _apply_result_mode(dict(empty_result), mode)
            assert len(result["rows"]) == 0
            assert result["rowcount"] == 0

    def test_preserves_other_fields(self, sample_result: dict) -> None:
        """Result mode filtering should preserve other result fields."""
        result = _apply_result_mode(dict(sample_result), RESULT_MODE_SUMMARY)

        # These fields should be preserved
        assert result["statement"] == "SELECT * FROM test_table"
        assert result["query_id"] == "test-query-id"
        assert result["duration_ms"] == 150
        assert result["key_metrics"] is not None

    def test_summary_mode_includes_columns_count(self, sample_result: dict) -> None:
        """Summary mode should include columns count in result_mode_info."""
        result = _apply_result_mode(dict(sample_result), RESULT_MODE_SUMMARY)

        assert result["result_mode_info"]["columns_count"] == 3


class TestResultModeConstants:
    """Tests for result mode constants."""

    def test_sample_size_is_reasonable(self) -> None:
        """Sample sizes should be reasonable values."""
        assert RESULT_MODE_SAMPLE_SIZE == 10
        assert RESULT_MODE_SUMMARY_SAMPLE_SIZE == 5
        assert RESULT_MODE_SAMPLE_SIZE > RESULT_MODE_SUMMARY_SAMPLE_SIZE

    def test_mode_constants_are_strings(self) -> None:
        """Mode constants should be lowercase strings."""
        assert RESULT_MODE_FULL == "full"
        assert RESULT_MODE_SUMMARY == "summary"
        assert RESULT_MODE_SCHEMA_ONLY == "schema_only"
        assert RESULT_MODE_SAMPLE == "sample"
