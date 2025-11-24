"""Tests for report revert functionality."""

import uuid

import pytest

from igloo_mcp.living_reports.service import ReportService


def test_revert_to_previous_state(tmp_path):
    """Test basic revert operation."""
    service = ReportService(reports_root=tmp_path / "reports")

    # Create report
    report_id = service.create_report("Original Title")
    outline = service.get_report_outline(report_id)

    # Get initial action_id
    storage = service.global_storage.get_report_storage(report_id)
    events = storage.load_audit_events()
    first_action_id = events[0].action_id

    # Make first change
    outline.title = "Changed Title 1"
    service.update_report_outline(report_id, outline, actor="cli")
    action1_events = storage.load_audit_events()
    action1_id = action1_events[-1].action_id

    # Make second change
    outline = service.get_report_outline(report_id)
    outline.title = "Changed Title 2"
    service.update_report_outline(report_id, outline, actor="cli")

    # Revert to first change
    result = service.revert_report(report_id, action1_id)

    assert result["success"] is True
    assert result["reverted_to_action_id"] == action1_id

    # Verify state restored
    outline = service.get_report_outline(report_id)
    assert outline.title == "Changed Title 1"


def test_revert_nonexistent_action(tmp_path):
    """Test error when action_id doesn't exist."""
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test")

    fake_action_id = str(uuid.uuid4())

    with pytest.raises(ValueError, match="Action not found"):
        service.revert_report(report_id, fake_action_id)


def test_revert_audit_log(tmp_path):
    """Test that revert action is logged in audit trail."""
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test")

    # Make a change
    outline = service.get_report_outline(report_id)
    outline.title = "Changed"
    service.update_report_outline(report_id, outline)

    # Get action_id
    storage = service.global_storage.get_report_storage(report_id)
    events = storage.load_audit_events()
    change_action_id = events[-1].action_id

    # Revert
    service.revert_report(report_id, change_action_id)

    # Check audit log
    events = storage.load_audit_events()
    revert_event = events[-1]

    assert revert_event.action_type == "revert"
    assert revert_event.payload["reverted_from_action_id"] == change_action_id
    assert "backup_restored" in revert_event.payload
    assert "current_state_backup" in revert_event.payload


def test_revert_missing_backup(tmp_path):
    """Test error when backup file is missing."""
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test")

    # Make a change
    outline = service.get_report_outline(report_id)
    outline.title = "Changed"
    service.update_report_outline(report_id, outline)

    # Get action_id and corrupt the backup filename in payload
    storage = service.global_storage.get_report_storage(report_id)
    events = storage.load_audit_events()
    change_event = events[-1]

    # Manually modify the payload to have a non-existent backup
    change_event.payload["backup_filename"] = "nonexistent.bak"
    # Note: In real usage, we'd need to re-save the audit event, but for this test
    # we'll create a fake event with bad backup filename

    fake_action_id = str(uuid.uuid4())
    fake_event = {
        "action_id": fake_action_id,
        "report_id": report_id,
        "ts": change_event.ts,
        "actor": "cli",
        "action_type": "evolve",
        "payload": {"backup_filename": "nonexistent.bak"},
    }

    # This is a bit of a hack - in practice the audit events are immutable
    # But for testing, we can temporarily add a fake event
    events.append(fake_event)
    # Re-write audit log with fake event
    import json

    audit_path = storage.audit_path
    with audit_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    with pytest.raises(ValueError, match="Backup file missing"):
        service.revert_report(report_id, fake_action_id)


def test_revert_corrupted_backup(tmp_path):
    """Test error when backup file is corrupted."""
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test")

    # Make a change
    outline = service.get_report_outline(report_id)
    outline.title = "Changed"
    service.update_report_outline(report_id, outline)

    # Get action_id
    storage = service.global_storage.get_report_storage(report_id)
    events = storage.load_audit_events()
    change_event = events[-1]

    # Corrupt the backup file
    backup_filename = change_event.payload["backup_filename"]
    backup_path = storage.backups_dir / backup_filename
    backup_path.write_text("corrupted json data {{{{")

    with pytest.raises(ValueError, match="Backup file is corrupted"):
        service.revert_report(report_id, change_event.action_id)


def test_revert_no_backup_in_payload(tmp_path):
    """Test error when action has no backup filename in payload."""
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Test")

    # Manually create an audit event without backup_filename
    fake_action_id = str(uuid.uuid4())
    fake_event = {
        "action_id": fake_action_id,
        "report_id": report_id,
        "ts": "2024-01-01T00:00:00Z",
        "actor": "cli",
        "action_type": "manual_edit",  # Not evolve/update
        "payload": {"some": "data"},
    }

    storage = service.global_storage.get_report_storage(report_id)
    events = storage.load_audit_events()
    events.append(fake_event)

    # Re-write audit log
    import json

    audit_path = storage.audit_path
    with audit_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    with pytest.raises(ValueError, match="No backup associated with action"):
        service.revert_report(report_id, fake_action_id)


def test_revert_preserves_index(tmp_path):
    """Test that revert updates the index correctly."""
    service = ReportService(reports_root=tmp_path / "reports")

    report_id = service.create_report("Original Title", tags=["tag1"])

    # Make a change that includes tags
    outline = service.get_report_outline(report_id)
    outline.title = "Changed Title"
    outline.metadata["tags"] = ["tag2"]
    service.update_report_outline(report_id, outline)

    # Get action_id
    storage = service.global_storage.get_report_storage(report_id)
    events = storage.load_audit_events()
    change_action_id = events[-1].action_id

    # Revert
    service.revert_report(report_id, change_action_id)

    # Check index was updated
    entry = service.index.get_entry(report_id)
    assert entry.current_title == "Original Title"
    assert entry.tags == ["tag1"]


def test_revert_creates_current_backup(tmp_path):
    """Test that revert creates a backup of current state before restoring."""
    service = ReportService(reports_root=tmp_path / "reports")

    report_id = service.create_report("Original")

    # Make a change
    outline = service.get_report_outline(report_id)
    outline.title = "Changed"
    service.update_report_outline(report_id, outline)

    # Get action_id
    storage = service.global_storage.get_report_storage(report_id)
    events = storage.load_audit_events()
    change_action_id = events[-1].action_id

    # Count backups before revert
    initial_backup_count = len(list(storage.backups_dir.glob("*.bak")))

    # Revert
    result = service.revert_report(report_id, change_action_id)

    # Should have created an additional backup
    final_backup_count = len(list(storage.backups_dir.glob("*.bak")))
    assert final_backup_count == initial_backup_count + 1

    # Check that revert event mentions the current state backup
    revert_event = storage.load_audit_events()[-1]
    assert "current_state_backup" in revert_event.payload
    assert revert_event.payload["current_state_backup"] is not None
