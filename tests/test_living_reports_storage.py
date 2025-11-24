"""Tests for living reports storage layer."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from igloo_mcp.living_reports.models import AuditEvent, Outline, ReportId
from igloo_mcp.living_reports.storage import (
    GlobalStorage,
    ReportLock,
    ReportStorage,
)


class TestReportLock:
    """Test ReportLock functionality."""

    def test_lock_creation(self) -> None:
        """Test creating a lock object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.lock"
            lock = ReportLock(lock_path, timeout_seconds=1.0)
            assert lock.lock_path == lock_path
            assert lock.timeout_seconds == 1.0

    def test_lock_context_manager_without_portalocker(self) -> None:
        """Test lock context manager when portalocker is not available."""
        with patch("igloo_mcp.living_reports.storage.HAS_PORTALOCKER", False):
            with tempfile.TemporaryDirectory() as tmpdir:
                lock_path = Path(tmpdir) / "test.lock"
                lock = ReportLock(lock_path)

                with lock:
                    assert lock_path.exists()

                # Lock file should be removed after context
                assert not lock_path.exists()

    def test_lock_fallback_on_existing_file(self) -> None:
        """Test fallback lock raises error when file exists."""
        with patch("igloo_mcp.living_reports.storage.HAS_PORTALOCKER", False):
            with tempfile.TemporaryDirectory() as tmpdir:
                lock_path = Path(tmpdir) / "test.lock"
                lock_path.write_text("existing")

                lock = ReportLock(lock_path)
                with pytest.raises(RuntimeError, match="Lock file exists"):
                    with lock:
                        pass


class TestReportStorage:
    """Test ReportStorage functionality."""

    def test_storage_creation(self) -> None:
        """Test creating storage for a report directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "report1"
            storage = ReportStorage(report_dir)

            assert storage.report_dir == report_dir
            assert storage.outline_path == report_dir / "outline.json"
            assert storage.audit_path == report_dir / "audit.jsonl"
            assert storage.backups_dir == report_dir / "backups"

    def test_load_outline_nonexistent(self) -> None:
        """Test loading outline when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "report1"
            storage = ReportStorage(report_dir)

            with pytest.raises(FileNotFoundError):
                storage.load_outline()

    def test_save_and_load_outline(self) -> None:
        """Test saving and loading an outline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "report1"
            storage = ReportStorage(report_dir)

            # Create test outline
            outline = Outline(
                report_id=str(ReportId.new()),
                title="Test Report",
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            )

            # Save outline
            storage.save_outline(outline)

            # Load outline
            loaded = storage.load_outline()
            assert loaded.title == "Test Report"
            assert loaded.report_id == outline.report_id

            # Check backup was created
            backup_files = list(storage.backups_dir.glob("*.bak"))
            assert len(backup_files) == 0  # No backup on first save

            # Save again to create backup
            outline.title = "Updated Report"
            storage.save_outline(outline)

            backup_files = list(storage.backups_dir.glob("*.bak"))
            assert len(backup_files) == 1

    def test_invalid_outline_json(self) -> None:
        """Test loading invalid JSON raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "report1"
            storage = ReportStorage(report_dir)

            # Write invalid JSON
            storage.outline_path.write_text("invalid json")

            with pytest.raises(ValueError):
                storage.load_outline()

    def test_invalid_outline_schema(self) -> None:
        """Test loading outline with invalid schema raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "report1"
            storage = ReportStorage(report_dir)

            # Write valid JSON but invalid Outline
            invalid_data = {"invalid_field": "value"}
            storage.outline_path.write_text(json.dumps(invalid_data))

            with pytest.raises(ValueError):
                storage.load_outline()

    def test_append_audit_event(self) -> None:
        """Test appending audit events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "report1"
            storage = ReportStorage(report_dir)

            event1 = AuditEvent(
                action_id="550e8400-e29b-41d4-a716-446655440000",
                report_id=str(ReportId.new()),
                ts="2024-01-01T00:00:00Z",
                actor="cli",
                action_type="create",
            )

            event2 = AuditEvent(
                action_id="550e8400-e29b-41d4-a716-446655440001",
                report_id=str(ReportId.new()),
                ts="2024-01-01T00:01:00Z",
                actor="agent",
                action_type="evolve",
            )

            storage.append_audit_event(event1)
            storage.append_audit_event(event2)

            events = storage.load_audit_events()
            assert len(events) == 2
            assert events[0].action_type == "create"
            assert events[1].action_type == "evolve"

    def test_load_audit_events_empty(self) -> None:
        """Test loading audit events when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "report1"
            storage = ReportStorage(report_dir)

            events = storage.load_audit_events()
            assert events == []

    def test_detect_manual_edits_valid(self) -> None:
        """Test manual edit detection with valid outline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "report1"
            storage = ReportStorage(report_dir)

            outline = Outline(
                report_id=str(ReportId.new()),
                title="Test Report",
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            )
            storage.save_outline(outline)

            assert not storage.detect_manual_edits()

    def test_detect_manual_edits_invalid_json(self) -> None:
        """Test manual edit detection with invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "report1"
            storage = ReportStorage(report_dir)

            storage.outline_path.write_text("invalid json")
            assert storage.detect_manual_edits()

    def test_lock_context_manager(self) -> None:
        """Test storage lock context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "report1"
            storage = ReportStorage(report_dir)

            # Should not raise any exceptions
            with storage.lock():
                pass


class TestGlobalStorage:
    """Test GlobalStorage functionality."""

    def test_global_storage_creation(self) -> None:
        """Test creating global storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_root = Path(tmpdir) / "reports"
            storage = GlobalStorage(reports_root)

            assert storage.reports_root == reports_root
            assert storage.index_path == reports_root / "index.jsonl"

    def test_get_report_storage(self) -> None:
        """Test getting report storage instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_root = Path(tmpdir) / "reports"
            storage = GlobalStorage(reports_root)

            report_storage = storage.get_report_storage("test_report")
            assert isinstance(report_storage, ReportStorage)
            assert report_storage.report_dir == reports_root / "by_id" / "test_report"

    def test_save_index_entry(self) -> None:
        """Test saving index entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_root = Path(tmpdir) / "reports"
            storage = GlobalStorage(reports_root)

            entry = {
                "report_id": str(ReportId.new()),
                "current_title": "Test Report",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "tags": ["test"],
                "status": "active",
                "path": "by_id/test",
            }

            storage.save_index_entry(entry)

            # Check file was created and contains entry
            assert storage.index_path.exists()
            content = storage.index_path.read_text()
            assert entry["current_title"] in content
