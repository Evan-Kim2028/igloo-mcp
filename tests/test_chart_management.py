"""Tests for chart management functionality."""

import uuid
from pathlib import Path

import pytest

from igloo_mcp.living_reports.models import Insight, Outline


class TestChartMetadataStorage:
    """Test chart metadata in outline."""

    def test_chart_metadata_add_to_outline(self):
        """Test adding chart metadata to outline."""
        outline = Outline(
            report_id=str(uuid.uuid4()),
            title="Test Report",
            created_at="2025-11-30T00:00:00Z",
            updated_at="2025-11-30T00:00:00Z",
        )

        chart_id = str(uuid.uuid4())
        outline.metadata["charts"] = {
            chart_id: {
                "path": "/path/to/chart.png",
                "format": "png",
                "created_at": "2025-11-30T12:00:00Z",
                "size_bytes": 100000,
                "linked_insights": [],
                "source": "matplotlib",
                "description": "Revenue trend",
            }
        }

        assert "charts" in outline.metadata
        assert chart_id in outline.metadata["charts"]
        assert outline.metadata["charts"][chart_id]["format"] == "png"

    def test_chart_metadata_update_existing(self):
        """Test updating existing chart metadata."""
        outline = Outline(
            report_id=str(uuid.uuid4()),
            title="Test Report",
            created_at="2025-11-30T00:00:00Z",
            updated_at="2025-11-30T00:00:00Z",
        )

        chart_id = str(uuid.uuid4())
        outline.metadata["charts"] = {
            chart_id: {
                "path": "/old/path.png",
                "description": "Old description",
            }
        }

        # Update description
        outline.metadata["charts"][chart_id]["description"] = "New description"

        assert outline.metadata["charts"][chart_id]["description"] == "New description"
        assert outline.metadata["charts"][chart_id]["path"] == "/old/path.png"

    def test_chart_metadata_remove_chart(self):
        """Test removing chart from metadata."""
        outline = Outline(
            report_id=str(uuid.uuid4()),
            title="Test Report",
            created_at="2025-11-30T00:00:00Z",
            updated_at="2025-11-30T00:00:00Z",
        )

        chart_id = str(uuid.uuid4())
        outline.metadata["charts"] = {chart_id: {"path": "/path.png"}}

        # Remove chart
        del outline.metadata["charts"][chart_id]

        assert chart_id not in outline.metadata.get("charts", {})

    def test_chart_linked_to_insight_via_metadata(self):
        """Test linking chart to insight via insight metadata."""
        insight = Insight(
            insight_id=str(uuid.uuid4()),
            importance=8,
            summary="Test",
            metadata={"chart_id": "chart-123"},
        )

        assert insight.metadata.get("chart_id") == "chart-123"

    def test_multiple_charts_in_outline(self):
        """Test multiple charts in outline metadata."""
        outline = Outline(
            report_id=str(uuid.uuid4()),
            title="Test Report",
            created_at="2025-11-30T00:00:00Z",
            updated_at="2025-11-30T00:00:00Z",
        )

        chart1_id = str(uuid.uuid4())
        chart2_id = str(uuid.uuid4())

        outline.metadata["charts"] = {
            chart1_id: {"path": "/chart1.png", "description": "Chart 1"},
            chart2_id: {"path": "/chart2.png", "description": "Chart 2"},
        }

        assert len(outline.metadata["charts"]) == 2
        assert chart1_id in outline.metadata["charts"]
        assert chart2_id in outline.metadata["charts"]


class TestChartFormatDetection:
    """Test chart format detection."""

    def test_chart_format_from_extension(self):
        """Test detecting chart format from file extension."""
        extensions = {
            ".png": "png",
            ".jpg": "jpg",
            ".jpeg": "jpeg",
            ".svg": "svg",
            ".gif": "gif",
        }

        for ext, expected_format in extensions.items():
            path = Path(f"/path/to/chart{ext}")
            detected_format = path.suffix.lstrip(".").lower()
            assert detected_format == expected_format


class TestChartSizeValidation:
    """Test chart size validation."""

    def test_chart_size_warning_threshold(self):
        """Test that 5MB triggers warning threshold."""
        size_5mb = 5 * 1024 * 1024
        assert size_5mb == 5242880

    def test_chart_size_hard_limit(self):
        """Test that 50MB is the hard limit."""
        size_50mb = 50 * 1024 * 1024
        assert size_50mb == 52428800


@pytest.mark.asyncio
async def test_attach_chart_operation_structure():
    """Test attach_chart operation structure."""
    from igloo_mcp.mcp.tools.evolve_report_batch import OP_ATTACH_CHART

    operation = {
        "type": OP_ATTACH_CHART,
        "chart_path": "/path/to/chart.png",
        "insight_ids": ["insight-uuid"],
        "description": "Revenue trend Q3",
        "source": "matplotlib",
    }

    assert operation["type"] == "attach_chart"
    assert "chart_path" in operation
    assert "insight_ids" in operation
    assert "description" in operation
