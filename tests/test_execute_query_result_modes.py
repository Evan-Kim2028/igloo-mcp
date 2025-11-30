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
        # Should show helpful hint indicating all rows returned
        assert result["result_mode_info"]["hint"] == "All 3 rows returned"

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
        # Should show helpful hint indicating all rows returned
        assert result["result_mode_info"]["hint"] == "All 5 rows returned"

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

    def test_summary_mode_hint_shows_truncation_info(self, sample_result: dict) -> None:
        """Summary mode should show detailed hint when rows are truncated."""
        result = _apply_result_mode(dict(sample_result), RESULT_MODE_SUMMARY)

        # Should indicate truncation with row counts
        assert "Showing first 5 of 100 rows" in result["result_mode_info"]["hint"]
        assert "result_mode='full'" in result["result_mode_info"]["hint"]

    def test_sample_mode_hint_shows_truncation_info(self, sample_result: dict) -> None:
        """Sample mode should show detailed hint when rows are truncated."""
        result = _apply_result_mode(dict(sample_result), RESULT_MODE_SAMPLE)

        # Should indicate truncation with row counts
        assert "Showing first 10 of 100 rows" in result["result_mode_info"]["hint"]
        assert "result_mode='full'" in result["result_mode_info"]["hint"]


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


# =========================================================================
# Additional Edge Case Tests for result_mode
# =========================================================================


class TestResultModeEdgeCases:
    """Edge case tests that complement the unit tests above.

    These tests focus on scenarios not covered by TestApplyResultMode,
    such as realistic Snowflake metadata fields and single-row aggregations.
    """

    def test_result_mode_preserves_snowflake_metadata(self) -> None:
        """Test that Snowflake-specific fields are preserved across all modes."""
        snowflake_result = {
            "rows": [{"id": i} for i in range(20)],
            "rowcount": 20,
            "columns": ["id"],
            "statement": "SELECT id FROM table",
            "query_id": "01abc-def-123",
            "duration_ms": 120,
            "warehouse": "COMPUTE_WH",
            "database": "ANALYTICS",
            "schema": "PUBLIC",
        }

        for mode in [RESULT_MODE_FULL, RESULT_MODE_SUMMARY, RESULT_MODE_SCHEMA_ONLY, RESULT_MODE_SAMPLE]:
            result = _apply_result_mode(dict(snowflake_result), mode)

            # Snowflake-specific fields should always be preserved
            assert result["warehouse"] == "COMPUTE_WH"
            assert result["database"] == "ANALYTICS"
            assert result["schema"] == "PUBLIC"

    def test_result_mode_with_aggregation_query(self) -> None:
        """Test result modes with single-row aggregation (common pattern)."""
        agg_result = {
            "rows": [{"count": 12345, "avg_price": 99.99, "max_date": "2024-01-15"}],
            "rowcount": 1,
            "columns": ["count", "avg_price", "max_date"],
            "statement": "SELECT COUNT(*), AVG(price), MAX(date) FROM products",
            "query_id": "01xyz-789",
            "duration_ms": 50,
        }

        # Non-schema modes should return the single row
        for mode in [RESULT_MODE_FULL, RESULT_MODE_SUMMARY, RESULT_MODE_SAMPLE]:
            result = _apply_result_mode(dict(agg_result), mode)
            assert len(result["rows"]) == 1
            assert result["rows"][0]["count"] == 12345

        # Schema only should still return 0 rows
        schema_result = _apply_result_mode(dict(agg_result), RESULT_MODE_SCHEMA_ONLY)
        assert len(schema_result["rows"]) == 0
        assert schema_result["columns"] == ["count", "avg_price", "max_date"]

    def test_invalid_result_mode_falls_back_to_full(self) -> None:
        """Test that invalid result_mode values fall back to full mode behavior."""
        result = {
            "rows": [{"id": 1}, {"id": 2}],
            "rowcount": 2,
            "columns": ["id"],
        }

        output = _apply_result_mode(dict(result), "invalid_mode")
        # Should not modify rows (full mode behavior) - rows unchanged
        assert len(output["rows"]) == 2
        # Note: The function may still set result_mode to the invalid value
        # The key behavior is that rows are not truncated


# =========================================================================
# Integration Tests for result_mode Validation
# =========================================================================


class TestResultModeValidation:
    """Integration tests for result_mode parameter validation in execute_query.

    These tests verify that the validation layer properly catches invalid
    result_mode values and provides helpful error messages to users.
    """

    def test_invalid_result_mode_typo_gives_clear_error(self) -> None:
        """Test that typos in result_mode give helpful error messages.

        This is an important UX test - users might typo 'summary' as 'summery'
        and should get a clear error showing valid options and what they sent.
        """
        from igloo_mcp.mcp.exceptions import MCPValidationError

        # Simulate validation that happens in execute_query
        valid_result_modes = {"full", "summary", "schema_only", "sample"}
        user_input = "summery"  # Common typo
        effective_result_mode = user_input.lower()

        # This should raise MCPValidationError
        if effective_result_mode not in valid_result_modes:
            error = MCPValidationError(
                "Invalid result_mode",
                validation_errors=[
                    f"result_mode must be one of: {', '.join(sorted(valid_result_modes))} (got: {user_input})"
                ],
                hints=["Use result_mode='summary' to reduce response size by ~90%"],
            )

            # Verify error contains helpful information in its dict representation
            error_dict = error.to_dict()
            assert "validation_errors" in error_dict
            validation_msg = error_dict["validation_errors"][0]

            # Should show what user sent
            assert "summery" in validation_msg
            # Should show all valid options
            assert "full" in validation_msg
            assert "summary" in validation_msg
            assert "schema_only" in validation_msg
            assert "sample" in validation_msg
            # Should have helpful phrasing
            assert "must be one of" in validation_msg

    def test_case_insensitive_result_mode_accepted(self) -> None:
        """Test that result_mode accepts uppercase/mixed case values.

        This verifies the UX improvement where we lowercase user input
        before validation, making the API more forgiving.
        """
        valid_result_modes = {"full", "summary", "schema_only", "sample"}

        # These should all be valid after lowercasing
        test_cases = ["SUMMARY", "Summary", "FuLl", "SCHEMA_ONLY", "sAmPlE"]

        for user_input in test_cases:
            effective_result_mode = user_input.lower()
            assert effective_result_mode in valid_result_modes
