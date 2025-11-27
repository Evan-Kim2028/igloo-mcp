"""Tests for advanced report features (fork, synthesize)."""

import uuid

import pytest

from igloo_mcp.living_reports.models import Insight, Section
from igloo_mcp.living_reports.service import ReportService


def test_fork_report(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    # Create source report with content
    source_id = service.create_report("Original Report", tags=["source"])
    source_outline = service.get_report_outline(source_id)

    # Add some content
    section_id = str(uuid.uuid4())
    insight_id = str(uuid.uuid4())
    source_outline.sections.append(
        Section(
            section_id=section_id,
            title="Test Section",
            order=0,
            insight_ids=[insight_id],
        )
    )
    source_outline.insights.append(
        Insight(
            insight_id=insight_id,
            importance=8,
            summary="Test insight",
            supporting_queries=[],
        )
    )
    service.update_report_outline(source_id, source_outline)

    # Fork it
    forked_id = service.fork_report(source_id, "Forked Report")

    # Verify fork has same content (source has template section + added section)
    forked_outline = service.get_report_outline(forked_id)
    assert forked_outline.title == "Forked Report"
    assert len(forked_outline.sections) == len(
        source_outline.sections
    )  # Should match source
    assert len(forked_outline.insights) == 1
    assert forked_outline.metadata["forked_from"] == source_id

    # Verify it's a separate report
    assert forked_outline.report_id != source_outline.report_id
    assert forked_outline.outline_version == 1  # Reset version


def test_fork_report_preserves_audit_trail(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    source_id = service.create_report("Source")
    forked_id = service.fork_report(source_id, "Forked")

    # Check fork audit event
    forked_storage = service.global_storage.get_report_storage(forked_id)
    events = forked_storage.load_audit_events()

    fork_event = next((e for e in events if e.action_type == "fork"), None)
    assert fork_event is not None
    assert fork_event.payload["source_report_id"] == source_id


def test_fork_nonexistent_source(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    with pytest.raises(ValueError, match="Source report not found"):
        service.fork_report("nonexistent", "Forked")


def test_synthesize_reports(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    # Create two source reports
    id1 = service.create_report("Report 1", tags=["q1"])
    id2 = service.create_report("Report 2", tags=["q2"])

    # Add content to each
    outline1 = service.get_report_outline(id1)
    outline1.insights.append(
        Insight(
            insight_id=str(uuid.uuid4()),
            importance=7,
            summary="Insight from report 1",
            supporting_queries=[],
        )
    )
    service.update_report_outline(id1, outline1)

    outline2 = service.get_report_outline(id2)
    outline2.insights.append(
        Insight(
            insight_id=str(uuid.uuid4()),
            importance=9,
            summary="Insight from report 2",
            supporting_queries=[],
        )
    )
    service.update_report_outline(id2, outline2)

    # Synthesize
    synth_id = service.synthesize_reports([id1, id2], "Combined Report")

    # Verify synthesis
    synth_outline = service.get_report_outline(synth_id)
    assert synth_outline.title == "Combined Report"
    assert len(synth_outline.insights) == 2
    assert set(synth_outline.metadata["tags"]) >= {"q1", "q2", "synthesized"}
    assert synth_outline.metadata["synthesized_from"] == [id1, id2]


def test_synthesize_empty_source_list(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    with pytest.raises(ValueError, match="At least one source report is required"):
        service.synthesize_reports([], "Empty Synthesis")


def test_synthesize_nonexistent_source(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    valid_id = service.create_report("Valid Report")

    with pytest.raises(ValueError, match="Source report not found"):
        service.synthesize_reports([valid_id, "nonexistent"], "Synthesis")


def test_synthesize_preserves_section_order(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    # Create reports with multiple sections
    id1 = service.create_report("Report 1")
    outline1 = service.get_report_outline(id1)
    outline1.sections = [
        Section(
            section_id=str(uuid.uuid4()), title="Section A", order=0, insight_ids=[]
        ),
        Section(
            section_id=str(uuid.uuid4()), title="Section B", order=1, insight_ids=[]
        ),
    ]
    service.update_report_outline(id1, outline1)

    id2 = service.create_report("Report 2")
    outline2 = service.get_report_outline(id2)
    outline2.sections = [
        Section(
            section_id=str(uuid.uuid4()), title="Section C", order=0, insight_ids=[]
        ),
    ]
    service.update_report_outline(id2, outline2)

    # Synthesize
    synth_id = service.synthesize_reports([id1, id2], "Synthesis")

    # Check that sections are ordered correctly (0, 1, 2)
    synth_outline = service.get_report_outline(synth_id)
    orders = [s.order for s in synth_outline.sections]
    assert orders == [0, 1, 2]


def test_fork_creates_new_report_id(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    source_id = service.create_report("Source")
    forked_id = service.fork_report(source_id, "Forked")

    # IDs should be different
    assert source_id != forked_id

    # Both should exist in index
    source_entry = service.index.get_entry(source_id)
    forked_entry = service.index.get_entry(forked_id)

    assert source_entry is not None
    assert forked_entry is not None
    assert source_entry.current_title == "Source"
    assert forked_entry.current_title == "Forked"


def test_fork_updates_timestamps(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    source_id = service.create_report("Source")
    source_outline = service.get_report_outline(source_id)
    source_created = source_outline.created_at

    # Wait a tiny bit and fork
    import time

    time.sleep(0.001)

    forked_id = service.fork_report(source_id, "Forked")
    forked_outline = service.get_report_outline(forked_id)

    # Forked report should have new timestamps
    assert forked_outline.created_at != source_created
    assert forked_outline.updated_at == forked_outline.created_at


def test_synthesize_audit_trail(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    id1 = service.create_report("Source 1")
    id2 = service.create_report("Source 2")

    synth_id = service.synthesize_reports([id1, id2], "Synthesis")

    # Check that synthesis is recorded in metadata
    synth_outline = service.get_report_outline(synth_id)
    assert synth_outline.metadata["synthesized_from"] == [id1, id2]
    assert "synthesis_note" in synth_outline.metadata


def test_fork_preserves_tags(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    source_id = service.create_report("Source", tags=["original", "tag"])
    forked_id = service.fork_report(source_id, "Forked")

    # Check that tags are preserved
    forked_outline = service.get_report_outline(forked_id)
    assert set(forked_outline.metadata["tags"]) == {"original", "tag"}
