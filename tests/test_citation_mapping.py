"""Tests for citation mapping functionality in analyst reports."""

import uuid


from igloo_mcp.living_reports.models import (
    DatasetSource,
    Insight,
)
from igloo_mcp.living_reports.service import ReportService


def test_build_citation_map_single_insight(tmp_path):
    """Test citation mapping with single insight."""
    service = ReportService(reports_root=tmp_path / "reports")

    # Create analyst report
    report_id = service.create_report("Test Report", template="analyst_v1")
    outline = service.get_report_outline(report_id)

    # Add insight with citation
    insight_id = str(uuid.uuid4())
    insight = Insight(
        insight_id=insight_id,
        summary="Test insight",
        importance=8,
        supporting_queries=[DatasetSource(execution_id="exec_123")],
    )

    outline.insights.append(insight)
    outline.sections[0].insight_ids.append(insight_id)
    service.update_report_outline(report_id, outline, actor="test")

    # Build citation map
    citation_map = service._build_citation_map(outline)

    assert len(citation_map) == 1
    assert citation_map["exec_123"] == 1


def test_build_citation_map_multiple_insights(tmp_path):
    """Test citation mapping with multiple insights."""
    service = ReportService(reports_root=tmp_path / "reports")

    # Create analyst report
    report_id = service.create_report("Test Report", template="analyst_v1")
    outline = service.get_report_outline(report_id)

    # Add multiple insights with different citations
    insight1_id = str(uuid.uuid4())
    insight1 = Insight(
        insight_id=insight1_id,
        summary="First insight",
        importance=8,
        supporting_queries=[DatasetSource(execution_id="exec_123")],
    )

    insight2_id = str(uuid.uuid4())
    insight2 = Insight(
        insight_id=insight2_id,
        summary="Second insight",
        importance=7,
        supporting_queries=[DatasetSource(execution_id="exec_456")],
    )

    outline.insights.extend([insight1, insight2])
    outline.sections[0].insight_ids.extend([insight1_id, insight2_id])
    service.update_report_outline(report_id, outline, actor="test")

    # Build citation map
    citation_map = service._build_citation_map(outline)

    assert len(citation_map) == 2
    assert citation_map["exec_123"] == 1
    assert citation_map["exec_456"] == 2


def test_build_citation_map_shared_citation(tmp_path):
    """Test citation mapping when multiple insights share same citation."""
    service = ReportService(reports_root=tmp_path / "reports")

    # Create analyst report
    report_id = service.create_report("Test Report", template="analyst_v1")
    outline = service.get_report_outline(report_id)

    # Add multiple insights with same citation
    insight1_id = str(uuid.uuid4())
    insight1 = Insight(
        insight_id=insight1_id,
        summary="First insight",
        importance=8,
        supporting_queries=[DatasetSource(execution_id="exec_123")],
    )

    insight2_id = str(uuid.uuid4())
    insight2 = Insight(
        insight_id=insight2_id,
        summary="Second insight",
        importance=7,
        supporting_queries=[DatasetSource(execution_id="exec_123")],  # Same citation
    )

    outline.insights.extend([insight1, insight2])
    outline.sections[0].insight_ids.extend([insight1_id, insight2_id])
    service.update_report_outline(report_id, outline, actor="test")

    # Build citation map
    citation_map = service._build_citation_map(outline)

    # Should only have one citation number for shared execution_id
    assert len(citation_map) == 1
    assert citation_map["exec_123"] == 1


def test_build_citation_map_ignores_insights_without_citations(tmp_path):
    """Test that insights without citations are ignored."""
    service = ReportService(reports_root=tmp_path / "reports")

    # Create analyst report
    report_id = service.create_report("Test Report", template="analyst_v1")
    outline = service.get_report_outline(report_id)

    # Add insight with citation
    insight1_id = str(uuid.uuid4())
    insight1 = Insight(
        insight_id=insight1_id,
        summary="Insight with citation",
        importance=8,
        supporting_queries=[DatasetSource(execution_id="exec_123")],
    )

    # Add insight without citation
    insight2_id = str(uuid.uuid4())
    insight2 = Insight(
        insight_id=insight2_id,
        summary="Insight without citation",
        importance=7,
        supporting_queries=[],  # No citation
    )

    outline.insights.extend([insight1, insight2])
    outline.sections[0].insight_ids.extend([insight1_id, insight2_id])
    service.update_report_outline(report_id, outline, actor="test")

    # Build citation map
    citation_map = service._build_citation_map(outline)

    # Should only include citation for insight1
    assert len(citation_map) == 1
    assert citation_map["exec_123"] == 1


def test_build_citation_map_preserves_order(tmp_path):
    """Test that citation numbers preserve section/insight order."""
    service = ReportService(reports_root=tmp_path / "reports")

    # Create analyst report
    report_id = service.create_report("Test Report", template="analyst_v1")
    outline = service.get_report_outline(report_id)

    # Add insights to different sections
    insight1_id = str(uuid.uuid4())
    insight1 = Insight(
        insight_id=insight1_id,
        summary="Network insight",
        importance=8,
        supporting_queries=[DatasetSource(execution_id="exec_123")],
    )

    insight2_id = str(uuid.uuid4())
    insight2 = Insight(
        insight_id=insight2_id,
        summary="DEX insight",
        importance=7,
        supporting_queries=[DatasetSource(execution_id="exec_456")],
    )

    outline.insights.extend([insight1, insight2])
    outline.sections[0].insight_ids.append(insight1_id)  # Network Activity
    outline.sections[1].insight_ids.append(insight2_id)  # DEX Trading
    service.update_report_outline(report_id, outline, actor="test")

    # Build citation map
    citation_map = service._build_citation_map(outline)

    # Citations should be numbered in order of appearance
    assert citation_map["exec_123"] == 1  # First section
    assert citation_map["exec_456"] == 2  # Second section
