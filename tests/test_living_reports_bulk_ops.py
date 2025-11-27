"""Tests for bulk report operations."""

from pathlib import Path

import pytest

from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.living_reports.storage import ReportStorage


def test_archive_report(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test Report")

    service.archive_report(report_id)

    # Verify status
    outline = service.get_report_outline(report_id)
    assert outline.metadata.get("status") == "archived"

    # Verify index
    entry = service.index.get_entry(report_id)
    assert entry.status == "archived"


def test_archive_audit_log(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test Report")

    service.archive_report(report_id, actor="agent")

    # Check audit log
    storage = service.global_storage.get_report_storage(report_id)
    events = storage.load_audit_events()

    archive_event = next((e for e in events if e.action_type == "archive"), None)
    assert archive_event is not None
    assert archive_event.actor == "agent"
    assert "backup_filename" in archive_event.payload


def test_delete_report(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test Report")

    trash_location = service.delete_report(report_id)

    # Verify report moved to trash
    assert Path(trash_location).exists()
    assert report_id in trash_location

    # Verify removed from index
    entry = service.index.get_entry(report_id)
    assert entry is None

    # Verify audit log in trash
    trash_storage = ReportStorage(Path(trash_location))
    events = trash_storage.load_audit_events()
    assert any(e.action_type == "delete" for e in events)


def test_delete_nonexistent_report(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    # Invalid report IDs raise validation errors before reaching the service logic
    with pytest.raises(
        (ValueError, Exception), match="(Report not found|valid ReportId)"
    ):
        service.delete_report("nonexistent")


def test_tag_report_add(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test Report")

    service.tag_report(report_id, tags_to_add=["q1", "sales"])

    outline = service.get_report_outline(report_id)
    assert set(outline.metadata["tags"]) == {"q1", "sales"}


def test_tag_report_remove(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test Report", tags=["q1", "q2", "draft"])

    service.tag_report(report_id, tags_to_remove=["draft"])

    outline = service.get_report_outline(report_id)
    assert set(outline.metadata["tags"]) == {"q1", "q2"}


def test_tag_report_add_and_remove(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test Report", tags=["existing"])

    service.tag_report(report_id, tags_to_add=["new_tag"], tags_to_remove=["existing"])

    outline = service.get_report_outline(report_id)
    assert set(outline.metadata["tags"]) == {"new_tag"}


def test_tag_report_empty_operations(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test Report", tags=["initial"])

    # Empty operations should not change anything
    service.tag_report(report_id, tags_to_add=[], tags_to_remove=[])

    outline = service.get_report_outline(report_id)
    assert outline.metadata["tags"] == ["initial"]


def test_tag_report_audit_log(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test Report", tags=["old"])

    service.tag_report(
        report_id, tags_to_add=["new"], tags_to_remove=["old"], actor="agent"
    )

    # Check audit log
    storage = service.global_storage.get_report_storage(report_id)
    events = storage.load_audit_events()

    tag_event = next((e for e in events if e.action_type == "tag_update"), None)
    assert tag_event is not None
    assert tag_event.actor == "agent"
    assert tag_event.payload["tags_added"] == ["new"]
    assert tag_event.payload["tags_removed"] == ["old"]
    assert set(tag_event.payload["final_tags"]) == {"new"}


def test_bulk_operations_update_index(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test Report", tags=["initial"])

    # Archive
    service.archive_report(report_id)
    entry = service.index.get_entry(report_id)
    assert entry.status == "archived"

    # Tag
    service.tag_report(report_id, tags_to_add=["archived"])
    entry = service.index.get_entry(report_id)
    assert "archived" in entry.tags


def test_archive_preserves_content(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test Report", tags=["test"])

    # Add some content
    outline = service.get_report_outline(report_id)
    outline.title = "Archived Report"
    service.update_report_outline(report_id, outline)

    # Archive
    service.archive_report(report_id)

    # Verify content is preserved
    outline = service.get_report_outline(report_id)
    assert outline.title == "Archived Report"
    assert outline.metadata.get("status") == "archived"


def test_delete_preserves_audit_in_trash(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test Report")

    # Make some changes to create audit history
    outline = service.get_report_outline(report_id)
    outline.title = "Modified"
    service.update_report_outline(report_id, outline)

    # Delete
    trash_location = service.delete_report(report_id)

    # Verify audit history is preserved in trash
    trash_storage = ReportStorage(Path(trash_location))
    events = trash_storage.load_audit_events()

    # Should have create, update, and delete events
    event_types = {e.action_type for e in events}
    assert "create" in event_types
    assert "evolve" in event_types
    assert "delete" in event_types
