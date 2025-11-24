"""Comprehensive tests for post_query_insights module.

Tests column type detection, data coercion, edge cases, and insight generation.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from igloo_mcp.post_query_insights import (
    MAX_SAMPLE_ROWS,
    _coerce_datetime,
    _coerce_numeric,
    _compose_insights,
    _is_time_hint,
    _normalize_row,
    _stringify,
    _summarize_column,
    build_default_insights,
)


class TestNormalizeRow:
    """Test row normalization and column inference."""

    def test_normalize_dict_row(self):
        """Test normalizing a dict row."""
        row = {"name": "Alice", "age": 30}
        normalized, inferred = _normalize_row(row, None)
        assert normalized == row
        assert inferred == ["name", "age"]

    def test_normalize_list_row_with_columns(self):
        """Test normalizing a list row with column names provided."""
        row = ["Alice", 30]
        columns = ["name", "age"]
        normalized, inferred = _normalize_row(row, columns)
        assert normalized == {"name": "Alice", "age": 30}
        assert inferred is None

    def test_normalize_list_row_without_columns(self):
        """Test normalizing a list row without column names."""
        row = ["Alice", 30]
        normalized, inferred = _normalize_row(row, None)
        assert normalized == {"column_0": "Alice", "column_1": 30}
        assert inferred == ["column_0", "column_1"]

    def test_normalize_scalar_row(self):
        """Test normalizing a scalar value."""
        row = "single_value"
        normalized, inferred = _normalize_row(row, None)
        assert normalized == {"value": "single_value"}
        assert inferred == ["value"]

    def test_normalize_empty_row(self):
        """Test normalizing empty rows."""
        row = {}
        normalized, inferred = _normalize_row(row, None)
        assert normalized == {}
        assert inferred == []

        row = []
        normalized, inferred = _normalize_row(row, None)
        assert normalized == {}
        assert inferred == []


class TestCoerceNumeric:
    """Test numeric value coercion."""

    @pytest.mark.parametrize(
        "input_value,expected",
        [
            (42, 42.0),
            (42.5, 42.5),
            ("42", None),
            (True, None),  # Boolean should return None
            (False, None),
            (None, None),
            (Decimal("42.5"), 42.5),
        ],
    )
    def test_coerce_numeric_values(self, input_value, expected):
        """Test various numeric value coercions."""
        assert _coerce_numeric(input_value) == expected

    def test_coerce_numeric_overflow_decimal(self):
        """Test handling of overflow decimal values."""
        # Very large decimal that might overflow
        large_decimal = Decimal("1" + "0" * 1000)
        try:
            result = _coerce_numeric(large_decimal)
            # Should either succeed or return None gracefully
            assert result is None or isinstance(result, float)
        except (OverflowError, ValueError):
            # Expected for very large decimals
            pass


class TestCoerceDatetime:
    """Test datetime value coercion."""

    @pytest.mark.parametrize(
        "input_value,expected_type",
        [
            (datetime(2023, 1, 1), datetime),
            (date(2023, 1, 1), datetime),
            ("not_a_date", None),
            (None, None),
            (42, None),
        ],
    )
    def test_coerce_datetime_values(self, input_value, expected_type):
        """Test various datetime value coercions."""
        result = _coerce_datetime(input_value)
        if expected_type is None:
            assert result is None
        else:
            assert isinstance(result, expected_type)
            if isinstance(input_value, date) and not isinstance(input_value, datetime):
                # date should be converted to datetime at midnight
                assert result.hour == 0
                assert result.minute == 0
                assert result.second == 0


class TestIsTimeHint:
    """Test time hint detection in column names."""

    @pytest.mark.parametrize(
        "column_name,expected",
        [
            ("timestamp", True),
            ("created_ts", True),
            ("_time", True),
            ("time", True),
            ("date", True),
            ("_dt", True),
            ("at_ts", True),
            ("name", False),
            ("age", False),
            ("email", False),
            ("", False),
            ("TIMESTAMP", True),  # Case insensitive
            ("TimeStamp", True),
        ],
    )
    def test_time_hint_detection(self, column_name, expected):
        """Test detection of time-related column names."""
        assert _is_time_hint(column_name) == expected


class TestStringify:
    """Test string conversion of values."""

    @pytest.mark.parametrize(
        "input_value,expected_contains",
        [
            ("string", "string"),
            (42, "42"),
            (datetime(2023, 1, 1, 12, 30, 45), "2023-01-01T12:30:45"),
            (date(2023, 1, 1), "2023-01-01"),
            (None, "None"),
            ({}, "{}"),
        ],
    )
    def test_stringify_values(self, input_value, expected_contains):
        """Test string conversion of various value types."""
        result = _stringify(input_value)
        assert expected_contains in result


class TestSummarizeColumn:
    """Test column summarization logic."""

    def test_summarize_numeric_column(self):
        """Test summarization of numeric columns."""
        rows = [
            {"value": 10.0},
            {"value": 20.0},
            {"value": 30.0},
        ]
        summary = _summarize_column("value", rows, len(rows))
        assert summary["kind"] == "numeric"
        assert summary["min"] == 10.0
        assert summary["max"] == 30.0
        assert summary["avg"] == 20.0

    def test_summarize_time_column(self):
        """Test summarization of time columns."""
        dt1 = datetime(2023, 1, 1)
        dt2 = datetime(2023, 1, 2)
        rows = [
            {"timestamp": dt1},
            {"timestamp": dt2},
        ]
        summary = _summarize_column("timestamp", rows, len(rows))
        assert summary["kind"] == "time"
        assert summary["min_ts"] == dt1.isoformat()
        assert summary["max_ts"] == dt2.isoformat()

    def test_summarize_categorical_column(self):
        """Test summarization of categorical columns."""
        rows = [
            {"category": "A"},
            {"category": "B"},
            {"category": "A"},
            {"category": "C"},
            {"category": "A"},
        ]
        summary = _summarize_column("category", rows, len(rows))
        assert summary["kind"] == "categorical"
        assert summary["distinct_values"] == 3
        top_values = summary["top_values"]
        assert len(top_values) == 3
        # A should be most frequent
        assert top_values[0]["value"] == "A"
        assert top_values[0]["count"] == 3

    def test_summarize_empty_column(self):
        """Test summarization of empty columns."""
        rows = []
        summary = _summarize_column("value", rows, 0)
        assert summary is None

    def test_summarize_all_null_column(self):
        """Test summarization of columns with all null values."""
        rows = [
            {"value": None},
            {"value": None},
            {"value": None},
        ]
        summary = _summarize_column("value", rows, len(rows))
        assert summary is None

    def test_summarize_mixed_types_column(self):
        """Test summarization of columns with mixed types."""
        rows = [
            {"value": 10},
            {"value": "string"},
            {"value": None},
            {"value": 20.5},
        ]
        summary = _summarize_column("value", rows, len(rows))
        # Should default to categorical for mixed types
        assert summary["kind"] == "categorical"
        assert summary["distinct_values"] == 3  # 10, "string", 20.5

    def test_summarize_single_row(self):
        """Test summarization with single row (falls back to categorical)."""
        rows = [{"value": 42}]
        summary = _summarize_column("value", rows, len(rows))
        # Single numeric values are classified as categorical (requires >= 2 numeric values)
        assert summary["kind"] == "categorical"
        assert summary["distinct_values"] == 1
        assert summary["top_values"][0]["value"] == "42"

    def test_summarize_unicode_categorical(self):
        """Test summarization with Unicode categorical values."""
        rows = [
            {"emoji": "😀"},
            {"emoji": "🚀"},
            {"emoji": "😀"},
            {"emoji": "🌟"},
        ]
        summary = _summarize_column("emoji", rows, len(rows))
        assert summary["kind"] == "categorical"
        assert summary["distinct_values"] == 3
        top_values = summary["top_values"]
        assert top_values[0]["value"] == "😀"
        assert top_values[0]["count"] == 2


class TestComposeInsights:
    """Test insight composition from key metrics."""

    def test_compose_insights_basic(self):
        """Test basic insight composition."""
        key_metrics = {
            "total_rows": 100,
            "sampled_rows": 100,
            "num_columns": 3,
            "columns": [
                {
                    "name": "revenue",
                    "kind": "numeric",
                    "min": 100,
                    "max": 1000,
                    "avg": 550,
                },
                {
                    "name": "category",
                    "kind": "categorical",
                    "top_values": [{"value": "A", "count": 60, "ratio": 0.6}],
                },
            ],
        }
        insights = _compose_insights(key_metrics)
        assert len(insights) > 0
        assert any("revenue spans 100 → 1000" in insight for insight in insights)
        assert any("most frequent value 'A'" in insight for insight in insights)

    def test_compose_insights_truncated(self):
        """Test insight composition with truncated data."""
        key_metrics = {
            "total_rows": MAX_SAMPLE_ROWS + 100,  # More than MAX_SAMPLE_ROWS
            "sampled_rows": MAX_SAMPLE_ROWS,
            "num_columns": 2,
            "truncated_output": True,
            "columns": [],
        }
        insights = _compose_insights(key_metrics)
        assert len(insights) > 0
        assert any(
            "Analyzed first" in insight and "rows" in insight for insight in insights
        )

    def test_compose_insights_empty(self):
        """Test insight composition with empty metrics."""
        key_metrics = {
            "total_rows": 0,
            "sampled_rows": 0,
            "num_columns": 0,
            "columns": [],
        }
        insights = _compose_insights(key_metrics)
        assert len(insights) > 0  # Should still generate basic row count insight


class TestBuildDefaultInsights:
    """Test the main insight building function."""

    def test_build_insights_empty_data(self):
        """Test insight building with empty data."""
        metrics, insights = build_default_insights(
            None, columns=None, total_rows=0, truncated=False
        )
        assert metrics is None
        assert insights == []

    def test_build_insights_empty_rows(self):
        """Test insight building with empty rows."""
        metrics, insights = build_default_insights(
            [], columns=None, total_rows=0, truncated=False
        )
        assert metrics is None
        assert insights == []

    def test_build_insights_single_row(self):
        """Test insight building with single row."""
        rows = [{"name": "Alice", "age": 30, "salary": 50000.0}]
        metrics, insights = build_default_insights(
            rows, columns=["name", "age", "salary"], total_rows=1, truncated=False
        )
        assert metrics is not None
        assert metrics["total_rows"] == 1
        assert metrics["num_columns"] == 3
        assert len(metrics["columns"]) == 3
        assert len(insights) > 0

    def test_build_insights_large_dataset(self):
        """Test insight building with large dataset (over MAX_SAMPLE_ROWS)."""
        # Create more than MAX_SAMPLE_ROWS rows
        rows = []
        total_rows_count = MAX_SAMPLE_ROWS + 100
        for i in range(total_rows_count):
            rows.append({"id": i, "value": i * 2.0})

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=total_rows_count, truncated=True
        )
        assert metrics is not None
        assert metrics["total_rows"] == total_rows_count
        assert metrics["sampled_rows"] == MAX_SAMPLE_ROWS
        assert metrics["truncated_output"] is True
        assert len(insights) > 0

    def test_build_insights_mixed_types(self):
        """Test insight building with mixed data types."""
        rows = [
            {
                "id": 1,
                "name": "Alice",
                "active": True,
                "score": 95.5,
                "created": datetime(2023, 1, 1),
            },
            {
                "id": 2,
                "name": "Bob",
                "active": False,
                "score": 87.2,
                "created": datetime(2023, 1, 2),
            },
            {
                "id": 3,
                "name": "Charlie",
                "active": True,
                "score": 92.1,
                "created": datetime(2023, 1, 3),
            },
        ]
        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=3, truncated=False
        )
        assert metrics is not None
        assert len(metrics["columns"]) == 5

        # Check that different column types are detected
        kinds = {col["kind"] for col in metrics["columns"]}
        assert "numeric" in kinds  # score column
        assert "categorical" in kinds  # name, active columns
        assert "time" in kinds  # created column

    def test_build_insights_unicode_data(self):
        """Test insight building with Unicode data."""
        rows = [
            {"country": "🇺🇸", "city": "New York", "temperature": 25.0},
            {"country": "🇯🇵", "city": "東京", "temperature": 22.0},
            {"country": "🇺🇸", "city": "Los Angeles", "temperature": 30.0},
            {"country": "🇩🇪", "city": "Berlin", "temperature": 18.0},
        ]
        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=4, truncated=False
        )
        assert metrics is not None
        assert len(metrics["columns"]) == 3

        # Check Unicode handling in categorical columns
        country_col = next(
            col for col in metrics["columns"] if col["name"] == "country"
        )
        assert country_col["kind"] == "categorical"
        assert country_col["distinct_values"] == 3

        city_col = next(col for col in metrics["columns"] if col["name"] == "city")
        assert city_col["kind"] == "categorical"
        # Should handle Unicode strings properly
        top_values = city_col["top_values"]
        assert all(isinstance(tv["value"], str) for tv in top_values)

    def test_build_insights_malformed_data(self):
        """Test insight building with malformed data."""
        # Test with rows that have inconsistent column sets
        rows = [
            {"a": 1, "b": 2},
            {"a": 3, "c": 4},  # Missing b, has c
            {"b": 5, "c": 6},  # Missing a
        ]
        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=3, truncated=False
        )
        assert metrics is not None
        # Should handle missing columns gracefully - only includes columns from first row
        assert metrics["num_columns"] == 2  # a, b (c is missing from first row)

    def test_build_insights_decimal_overflow(self):
        """Test insight building with decimal overflow scenarios."""
        rows = [
            {"value": Decimal("1" + "0" * 50)},  # Very large decimal
            {
                "value": Decimal("0.0000000000000000000000000000001")
            },  # Very small decimal
        ]
        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=2, truncated=False
        )
        assert metrics is not None
        # Should handle decimal conversion gracefully
        value_col = next(col for col in metrics["columns"] if col["name"] == "value")
        assert (
            value_col["kind"] == "numeric"
        )  # Successfully converts decimals to numeric
