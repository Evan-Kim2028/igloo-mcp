"""Tests for large dataset handling and memory efficiency.

Tests truncation boundaries, wide tables, sampling behavior, and memory efficiency.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict

import pytest

from igloo_mcp.config import Config
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.post_query_insights import MAX_SAMPLE_ROWS, build_default_insights
from tests.helpers.fake_snowflake_connector import (
    FakeQueryPlan,
    FakeSnowflakeService,
)


class TestLargeDatasetTruncation:
    """Test dataset truncation at boundaries."""

    @pytest.mark.asyncio
    async def test_exact_max_sample_rows(self):
        """Test handling exactly MAX_SAMPLE_ROWS."""
        # Create exactly MAX_SAMPLE_ROWS rows
        rows = [{"id": i, "value": f"data_{i}"} for i in range(MAX_SAMPLE_ROWS)]

        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement=f"SELECT id, value FROM large_table LIMIT {MAX_SAMPLE_ROWS}",
                    rows=rows,
                    duration=0.1,
                )
            ]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(
            statement=f"SELECT id, value FROM large_table LIMIT {MAX_SAMPLE_ROWS}"
        )

        assert result["rowcount"] == MAX_SAMPLE_ROWS
        assert len(result["rows"]) == MAX_SAMPLE_ROWS

    @pytest.mark.asyncio
    async def test_over_max_sample_rows(self):
        """Test handling more than MAX_SAMPLE_ROWS."""
        total_rows = MAX_SAMPLE_ROWS + 100
        rows = [{"id": i, "value": f"data_{i}"} for i in range(total_rows)]

        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement=f"SELECT id, value FROM large_table LIMIT {total_rows}",
                    rows=rows,
                    duration=0.1,
                )
            ]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(
            statement=f"SELECT id, value FROM large_table LIMIT {total_rows}"
        )

        assert result["rowcount"] == total_rows
        # Should still return all rows (truncation is in insights, not results)
        assert len(result["rows"]) == total_rows

    def test_insights_truncation_at_boundary(self):
        """Test insight generation at truncation boundary."""
        # Create exactly MAX_SAMPLE_ROWS
        rows = [{"id": i, "value": i * 2.0} for i in range(MAX_SAMPLE_ROWS)]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=MAX_SAMPLE_ROWS, truncated=False
        )

        assert metrics is not None
        assert metrics["sampled_rows"] == MAX_SAMPLE_ROWS
        assert metrics["truncated_output"] is False
        assert len(insights) > 0

    def test_insights_truncation_over_boundary(self):
        """Test insight generation when over truncation boundary."""
        total_rows = MAX_SAMPLE_ROWS + 50
        rows = [{"id": i, "value": i * 2.0} for i in range(total_rows)]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=total_rows, truncated=True
        )

        assert metrics is not None
        assert metrics["sampled_rows"] == MAX_SAMPLE_ROWS  # Only sampled this many
        assert metrics["total_rows"] == total_rows
        assert metrics["truncated_output"] is True
        assert len(insights) > 0
        # Should mention truncation in insights
        assert any("Analyzed first" in insight for insight in insights)


class TestWideTables:
    """Test handling of very wide tables."""

    def create_wide_row(self, row_id: int, num_columns: int) -> Dict[str, int]:
        """Create a row with many columns."""
        return {f"col_{i}": row_id * i for i in range(num_columns)}

    @pytest.mark.asyncio
    async def test_100_column_table(self):
        """Test table with 100 columns."""
        num_columns = 100
        rows = [self.create_wide_row(i, num_columns) for i in range(10)]

        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT * FROM wide_table_100", rows=rows, duration=0.1
                )
            ]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement="SELECT * FROM wide_table_100")

        assert result["rowcount"] == 10
        assert len(result["rows"]) == 10

        # Check that all columns are present
        first_row = result["rows"][0]
        assert len(first_row) == num_columns
        assert all(f"col_{i}" in first_row for i in range(num_columns))

    @pytest.mark.asyncio
    async def test_500_column_table(self):
        """Test table with 500 columns (stress test)."""
        num_columns = 500
        rows = [self.create_wide_row(i, num_columns) for i in range(5)]

        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT * FROM wide_table_500",
                    rows=rows,
                    duration=0.2,  # Simulate slower query for wide table
                )
            ]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement="SELECT * FROM wide_table_500")

        assert result["rowcount"] == 5
        assert len(result["rows"]) == 5

        # Check that all columns are present
        first_row = result["rows"][0]
        assert len(first_row) == num_columns
        assert all(
            f"col_{i}" in first_row for i in range(0, num_columns, 50)
        )  # Spot check

    def test_wide_table_insights(self):
        """Test insight generation on wide tables."""
        num_columns = 200
        rows = [self.create_wide_row(i, num_columns) for i in range(20)]

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=20, truncated=False
        )

        assert metrics is not None
        assert metrics["num_columns"] == num_columns
        assert len(metrics["columns"]) == num_columns

        # Should generate insights about the data
        assert len(insights) > 0

    def test_wide_table_memory_efficiency(self):
        """Test that wide tables don't cause memory issues in insight generation."""
        num_columns = 1000
        num_rows = 100

        # Create a very wide table
        rows = []
        for i in range(num_rows):
            row = {f"col_{j}": (i + j) % 100 for j in range(num_columns)}
            rows.append(row)

        # This should not crash or use excessive memory
        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=num_rows, truncated=False
        )

        assert metrics is not None
        assert metrics["num_columns"] == num_columns
        assert metrics["sampled_rows"] == num_rows


class TestSamplingBehavior:
    """Test sampling behavior in insight generation."""

    def test_sampling_preserves_data_types(self):
        """Test that sampling preserves column data types."""
        # Create mixed data types
        rows = []
        for i in range(100):
            row = {
                "id": i,
                "name": f"name_{i}",
                "score": float(i) / 10.0,
                "active": i % 2 == 0,
                "category": ["A", "B", "C"][i % 3],
            }
            rows.append(row)

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=100, truncated=False
        )

        assert metrics is not None
        assert len(metrics["columns"]) == 5

        # Check that different data types are detected
        kinds = {col["kind"] for col in metrics["columns"]}
        assert "numeric" in kinds  # score
        assert "categorical" in kinds  # name, active, category

    def test_sampling_with_nulls(self):
        """Test sampling behavior with null values."""
        rows = []
        for i in range(200):
            row = {
                "id": i if i % 10 != 0 else None,  # 10% nulls
                "value": float(i) if i % 5 != 0 else None,  # 20% nulls
                "category": f"cat_{i%5}" if i % 3 != 0 else None,  # ~33% nulls
            }
            rows.append(row)

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=200, truncated=False
        )

        assert metrics is not None
        assert len(metrics["columns"]) == 3

        # Check null ratios are reasonable
        for col in metrics["columns"]:
            assert "non_null_ratio" in col
            assert (
                0.5 <= col["non_null_ratio"] <= 0.95
            )  # Should reflect null percentages

    def test_sampling_large_dataset_truncation(self):
        """Test sampling when dataset exceeds MAX_SAMPLE_ROWS."""
        total_rows = MAX_SAMPLE_ROWS + 1000

        # Create dataset larger than MAX_SAMPLE_ROWS
        rows = []
        for i in range(total_rows):
            rows.append({"id": i, "value": i * 2.0, "category": f"group_{i % 10}"})

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=total_rows, truncated=True
        )

        assert metrics is not None
        assert metrics["sampled_rows"] == MAX_SAMPLE_ROWS
        assert metrics["total_rows"] == total_rows
        assert metrics["truncated_output"] is True

        # Should still generate meaningful insights from sample
        assert len(insights) > 0


class TestMemoryEfficiency:
    """Test memory efficiency with large datasets."""

    def test_large_numeric_dataset_memory(self):
        """Test memory handling of large numeric datasets."""
        num_rows = 50000
        num_cols = 20

        # Create large numeric dataset
        rows = []
        for i in range(num_rows):
            row = {f"col_{j}": float(i * j) for j in range(num_cols)}
            rows.append(row)

        # Should handle this without excessive memory usage
        # (This is a smoke test - in real scenarios we'd monitor memory)
        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=num_rows, truncated=False
        )

        assert metrics is not None
        assert metrics["sampled_rows"] == min(num_rows, MAX_SAMPLE_ROWS)

    def test_large_categorical_dataset_memory(self):
        """Test memory handling of large categorical datasets."""
        num_rows = 10000
        categories = [f"category_{i}" for i in range(100)]

        # Create large categorical dataset
        rows = []
        for i in range(num_rows):
            rows.append(
                {
                    "id": i,
                    "category": categories[i % len(categories)],
                    "subcategory": f"sub_{i % 50}",
                    "value": i % 100,
                }
            )

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=num_rows, truncated=False
        )

        assert metrics is not None
        # Should handle categorical columns with many distinct values
        category_col = next(
            col for col in metrics["columns"] if col["name"] == "category"
        )
        assert category_col["kind"] == "categorical"
        assert category_col["distinct_values"] <= len(categories)

    def test_mixed_large_dataset_memory(self):
        """Test memory handling of mixed large datasets."""
        num_rows = 25000

        rows = []
        for i in range(num_rows):
            row = {
                "id": i,
                "numeric_val": float(i) * 3.14,
                "category": f"type_{i % 20}",
                "flag": i % 2 == 0,
                "text": f"description_{i}",
                "timestamp": datetime(2024, 1, (i % 28) + 1),
            }
            rows.append(row)

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=num_rows, truncated=False
        )

        assert metrics is not None
        assert len(metrics["columns"]) == 6

        # Should detect mixed types correctly
        kinds = {col["kind"] for col in metrics["columns"]}
        assert "numeric" in kinds
        assert "categorical" in kinds
        assert "time" in kinds


class TestPerformanceBoundaries:
    """Test performance at boundary conditions."""

    def test_max_columns_boundary(self):
        """Test at maximum reasonable column count."""
        max_cols = 1000
        rows = []
        for i in range(10):  # Small row count, many columns
            row = {f"col_{j}": f"value_{i}_{j}" for j in range(max_cols)}
            rows.append(row)

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=10, truncated=False
        )

        assert metrics is not None
        assert metrics["num_columns"] == max_cols

    def test_max_rows_boundary(self):
        """Test at maximum sampling boundary."""
        rows = []
        for i in range(MAX_SAMPLE_ROWS):
            rows.append({"id": i, "data": f"value_{i}"})

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=MAX_SAMPLE_ROWS, truncated=False
        )

        assert metrics is not None
        assert metrics["sampled_rows"] == MAX_SAMPLE_ROWS
        assert not metrics["truncated_output"]

    def test_combined_boundaries(self):
        """Test at combined row and column boundaries."""
        max_cols = 500
        rows = []

        # Create MAX_SAMPLE_ROWS rows with many columns
        for i in range(MAX_SAMPLE_ROWS):
            row = {f"col_{j}": f"value_{i}_{j}" for j in range(max_cols)}
            rows.append(row)

        metrics, insights = build_default_insights(
            rows, columns=None, total_rows=MAX_SAMPLE_ROWS, truncated=False
        )

        assert metrics is not None
        assert metrics["sampled_rows"] == MAX_SAMPLE_ROWS
        assert metrics["num_columns"] == max_cols
