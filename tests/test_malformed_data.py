"""Tests for malformed data handling across the system.

Tests null propagation, type mismatches, empty results, mixed types, and edge cases.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.post_query_insights import build_default_insights
from tests.helpers.fake_snowflake_connector import (
    FakeQueryPlan,
    FakeSnowflakeService,
)


class TestNullPropagation:
    """Test null/None value propagation through the system."""

    @pytest.mark.asyncio
    async def test_null_values_in_result_rows(self):
        """Test handling of None/null values in result rows."""
        rows = [
            {"id": 1, "name": "Alice", "score": 95.5},
            {"id": 2, "name": None, "score": None},  # All nulls
            {"id": None, "name": "Bob", "score": 87.2},  # Partial nulls
        ]

        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT id, name, score FROM test_table",
                    rows=rows,
                    duration=0.01,
                )
            ]
        )

        from igloo_mcp.config import Config

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement="SELECT id, name, score FROM test_table")

        assert result["rowcount"] == 3
        assert len(result["rows"]) == 3

        # Check that None values are preserved
        assert result["rows"][0]["name"] == "Alice"
        assert result["rows"][1]["name"] is None
        assert result["rows"][1]["score"] is None
        assert result["rows"][2]["id"] is None

    def test_null_handling_in_insights(self):
        """Test insight generation with null-heavy data."""
        rows = [
            {"value": None},
            {"value": None},
            {"value": None},
            {"value": 42.0},  # One non-null value
        ]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=4, truncated=False
        )

        assert metrics is not None
        assert len(metrics["columns"]) == 1

        value_col = metrics["columns"][0]
        assert value_col["non_null_ratio"] == 0.25  # 1/4 non-null
        assert value_col["distinct_values"] == 1  # Only the 42.0 value

    def test_all_null_columns(self):
        """Test handling of columns that are entirely null."""
        rows = [
            {"all_null": None, "mixed": 1},
            {"all_null": None, "mixed": None},
            {"all_null": None, "mixed": 3},
        ]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=3, truncated=False
        )

        assert metrics is not None
        assert (
            len(metrics["columns"]) == 1
        )  # all_null column is excluded when all values are null

        # mixed column should have correct null ratio
        mixed_col = next(col for col in metrics["columns"] if col["name"] == "mixed")
        assert (
            abs(mixed_col["non_null_ratio"] - 2.0 / 3.0) < 0.001
        )  # 2/3 non-null (within rounding tolerance)


class TestTypeMismatches:
    """Test handling of type mismatches in data."""

    @pytest.mark.asyncio
    async def test_mixed_types_in_column(self):
        """Test columns with mixed data types."""
        # Snowflake can return mixed types in some cases
        rows = [
            {"mixed_col": 42},
            {"mixed_col": "string"},
            {"mixed_col": 42.5},
            {"mixed_col": True},
            {"mixed_col": None},
        ]

        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT mixed_col FROM mixed_table",
                    rows=rows,
                    duration=0.01,
                )
            ]
        )

        from igloo_mcp.config import Config

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement="SELECT mixed_col FROM mixed_table")

        assert result["rowcount"] == 5
        # Should handle mixed types without crashing
        assert len(result["rows"]) == 5

    def test_type_mismatch_in_insights(self):
        """Test insight generation with type mismatches."""
        rows = [
            {"value": 42},
            {"value": "not_a_number"},
            {"value": 42.5},
            {"value": None},
        ]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=4, truncated=False
        )

        assert metrics is not None
        value_col = next(col for col in metrics["columns"] if col["name"] == "value")

        # Should fall back to categorical for mixed types
        assert value_col["kind"] == "categorical"
        assert value_col["distinct_values"] == 3  # 42, "not_a_number", 42.5

    def test_invalid_decimal_values(self):
        """Test handling of invalid decimal values."""
        rows = [
            {"decimal_col": Decimal("123.45")},
            {"decimal_col": Decimal("NaN")},  # Invalid decimal
            {"decimal_col": Decimal("Infinity")},  # Invalid decimal
        ]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=3, truncated=False
        )

        assert metrics is not None
        decimal_col = next(
            col for col in metrics["columns"] if col["name"] == "decimal_col"
        )

        # Should handle invalid decimals gracefully
        # May be numeric or categorical depending on coercion success
        assert decimal_col["kind"] in ["numeric", "categorical"]


class TestEmptyResultSets:
    """Test handling of empty and edge case result sets."""

    @pytest.mark.asyncio
    async def test_empty_result_set(self):
        """Test handling of completely empty result sets."""
        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT * FROM empty_table", rows=[], duration=0.01
                )
            ]
        )

        from igloo_mcp.config import Config

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement="SELECT * FROM empty_table")

        assert result["rowcount"] == 0
        assert result["rows"] == []

    @pytest.mark.asyncio
    async def test_single_row_result(self):
        """Test handling of single-row results."""
        rows = [{"id": 1, "value": "test"}]

        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT id, value FROM single_row",
                    rows=rows,
                    duration=0.01,
                )
            ]
        )

        from igloo_mcp.config import Config

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement="SELECT id, value FROM single_row")

        assert result["rowcount"] == 1
        assert len(result["rows"]) == 1
        assert result["rows"][0]["id"] == 1

    @pytest.mark.asyncio
    async def test_result_with_only_nulls(self):
        """Test results containing only null values."""
        rows = [
            {"a": None, "b": None},
            {"a": None, "b": None},
        ]

        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT a, b FROM nulls_only", rows=rows, duration=0.01
                )
            ]
        )

        from igloo_mcp.config import Config

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement="SELECT a, b FROM nulls_only")

        assert result["rowcount"] == 2
        assert len(result["rows"]) == 2
        assert all(row["a"] is None and row["b"] is None for row in result["rows"])

    def test_insights_empty_result_set(self):
        """Test insight generation with empty result sets."""
        metrics, insights = build_default_insights(
            [], columns=None, total_rows=0, truncated=False
        )

        assert metrics is None
        assert insights == []

    def test_insights_single_row(self):
        """Test insight generation with single row."""
        rows = [{"value": 42}]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=1, truncated=False
        )

        assert metrics is not None
        assert metrics["sampled_rows"] == 1
        assert len(metrics["columns"]) == 1

        # Single numeric value should be categorical (requires >= 2 numeric for numeric)
        value_col = metrics["columns"][0]
        assert value_col["kind"] == "categorical"


class TestDatetimeEdgeCases:
    """Test datetime handling edge cases."""

    def test_timezone_aware_datetimes(self):
        """Test handling of timezone-aware datetimes."""
        rows = [
            {"timestamp": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)},
            {"timestamp": datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc)},
            {"timestamp": None},
        ]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=3, truncated=False
        )

        assert metrics is not None
        timestamp_col = next(
            col for col in metrics["columns"] if col["name"] == "timestamp"
        )

        # Should handle timezone-aware datetimes
        assert timestamp_col["kind"] == "time"
        assert "min_ts" in timestamp_col
        assert "max_ts" in timestamp_col

    def test_invalid_datetime_formats(self):
        """Test handling of invalid datetime-like data."""
        rows = [
            {"date_col": datetime(2023, 1, 1)},
            {"date_col": "not_a_date"},
            {"date_col": 1234567890},  # Unix timestamp as int
        ]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=3, truncated=False
        )

        assert metrics is not None
        date_col = next(col for col in metrics["columns"] if col["name"] == "date_col")

        # Should handle mixed valid/invalid dates
        # May be time (for valid datetime) or categorical (for mixed)
        assert date_col["kind"] in ["time", "categorical"]


class TestComplexMalformedData:
    """Test complex malformed data scenarios."""

    def test_extremely_large_values(self):
        """Test handling of extremely large numeric values."""
        rows = [
            {"big_num": 10**100},  # Very large integer
            {"big_num": float("inf")},  # Infinity
            {"big_num": float("-inf")},  # Negative infinity
            {"big_num": float("nan")},  # NaN
        ]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=4, truncated=False
        )

        assert metrics is not None
        # Should handle extreme values without crashing
        big_num_col = next(
            col for col in metrics["columns"] if col["name"] == "big_num"
        )
        assert big_num_col["kind"] in [
            "numeric",
            "categorical",
        ]  # May fall back to categorical

    def test_nested_structures(self):
        """Test handling of nested/dict structures (like VARIANT columns)."""
        rows = [
            {"variant_col": {"nested": {"value": 42}}},
            {"variant_col": [1, 2, 3]},
            {"variant_col": "simple_string"},
            {"variant_col": None},
        ]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=4, truncated=False
        )

        assert metrics is not None
        variant_col = next(
            col for col in metrics["columns"] if col["name"] == "variant_col"
        )

        # Complex objects should be handled as categorical
        assert variant_col["kind"] == "categorical"

    def test_binary_data_simulation(self):
        """Test handling of binary-like data."""
        # Simulate binary data as bytes objects
        rows = [
            {"data": b"binary_data_1"},
            {"data": b"binary_data_2"},
            {"data": "text_data"},  # Mixed with text
        ]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=3, truncated=False
        )

        assert metrics is not None
        data_col = next(col for col in metrics["columns"] if col["name"] == "data")

        # Mixed binary/text should be categorical
        assert data_col["kind"] == "categorical"
        assert data_col["distinct_values"] == 3

    def test_unicode_mixed_with_binary(self):
        """Test Unicode mixed with other complex data types."""
        rows = [
            {"mixed": "Hello 世界 🌟"},
            {"mixed": b"bytes_data"},
            {"mixed": 42},
            {"mixed": {"key": "value"}},
            {"mixed": None},
        ]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=5, truncated=False
        )

        assert metrics is not None
        mixed_col = next(col for col in metrics["columns"] if col["name"] == "mixed")

        # Extremely mixed data should be categorical
        assert mixed_col["kind"] == "categorical"
        assert mixed_col["distinct_values"] == 4  # None is excluded from distinct count


class TestErrorRecovery:
    """Test error recovery in malformed data scenarios."""

    def test_partial_row_failures(self):
        """Test handling when some rows have malformed data."""
        rows = [
            {"id": 1, "value": "good"},
            {"id": 2, "value": "also_good"},
            # Simulate a row that might cause issues
            {"id": 3, "value": "problematic" * 1000},  # Very long string
        ]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=3, truncated=False
        )

        assert metrics is not None
        # Should handle long strings without crashing
        assert len(metrics["columns"]) >= 2

    def test_column_name_edge_cases(self):
        """Test handling of unusual column names."""
        # Column names that might cause issues
        rows = [
            {"normal": 1, "with spaces": 2, "with.dots": 3, "with-dashes": 4},
            {"normal": 5, "with spaces": 6, "with.dots": 7, "with-dashes": 8},
        ]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=2, truncated=False
        )

        assert metrics is not None
        assert len(metrics["columns"]) == 4

        # Should handle various column name formats
        column_names = {col["name"] for col in metrics["columns"]}
        assert "normal" in column_names
        assert "with spaces" in column_names
        assert "with.dots" in column_names
        assert "with-dashes" in column_names
