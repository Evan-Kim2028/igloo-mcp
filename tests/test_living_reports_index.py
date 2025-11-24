"""Tests for living reports index management."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from igloo_mcp.living_reports.index import IndexCorruptionError, ReportIndex
from igloo_mcp.living_reports.models import IndexEntry, ReportId


class TestReportIndex:
    """Test ReportIndex functionality."""

    def test_index_creation_empty(self) -> None:
        """Test creating index when no index file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.jsonl"
            index = ReportIndex(index_path)

            assert index.index_path == index_path
            assert index._entries == {}
            assert index._title_to_id == {}

    def test_index_load_existing(self) -> None:
        """Test loading existing index file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.jsonl"

            # Create test index entries
            now = "2024-01-01T00:00:00Z"
            entry1 = IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Report One",
                created_at=now,
                updated_at=now,
                path="by_id/report1",
            )
            entry2 = IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Report Two",
                created_at=now,
                updated_at=now,
                path="by_id/report2",
            )

            # Write to index file
            with index_path.open("w") as f:
                f.write(json.dumps(entry1.model_dump(), ensure_ascii=False) + "\n")
                f.write(json.dumps(entry2.model_dump(), ensure_ascii=False) + "\n")

            # Load index
            index = ReportIndex(index_path)

            assert len(index._entries) == 2
            assert entry1.report_id in index._entries
            assert entry2.report_id in index._entries
            assert index._title_to_id["Report One".lower()] == entry1.report_id

    def test_index_corruption_invalid_json(self) -> None:
        """Test index loading with invalid JSON raises IndexCorruptionError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.jsonl"
            index_path.write_text("invalid json line\n")

            with pytest.raises(IndexCorruptionError):
                ReportIndex(index_path)

    def test_index_corruption_invalid_entry(self) -> None:
        """Test index loading with invalid entry raises IndexCorruptionError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.jsonl"
            index_path.write_text('{"invalid": "entry"}\n')

            with pytest.raises(IndexCorruptionError):
                ReportIndex(index_path)

    def test_add_entry(self) -> None:
        """Test adding an index entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.jsonl"
            index = ReportIndex(index_path)

            now = "2024-01-01T00:00:00Z"
            entry = IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Test Report",
                created_at=now,
                updated_at=now,
                path="by_id/test",
            )

            index.add_entry(entry)

            assert entry.report_id in index._entries
            assert index._entries[entry.report_id] == entry
            assert index._title_to_id["test report"] == entry.report_id

            # Check file was written
            assert index_path.exists()
            content = index_path.read_text()
            assert "Test Report" in content

    def test_remove_entry(self) -> None:
        """Test removing an index entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.jsonl"
            index = ReportIndex(index_path)

            now = "2024-01-01T00:00:00Z"
            entry = IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Test Report",
                created_at=now,
                updated_at=now,
                path="by_id/test",
            )

            index.add_entry(entry)
            assert entry.report_id in index._entries

            index.remove_entry(entry.report_id)
            assert entry.report_id not in index._entries
            assert entry.current_title.lower() not in index._title_to_id

    def test_get_entry(self) -> None:
        """Test getting an index entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.jsonl"
            index = ReportIndex(index_path)

            now = "2024-01-01T00:00:00Z"
            entry = IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Test Report",
                created_at=now,
                updated_at=now,
                path="by_id/test",
            )

            index.add_entry(entry)

            retrieved = index.get_entry(entry.report_id)
            assert retrieved == entry

            # Test nonexistent entry
            assert index.get_entry("nonexistent") is None

    def test_resolve_title_exact_match(self) -> None:
        """Test resolving title with exact match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.jsonl"
            index = ReportIndex(index_path)

            now = "2024-01-01T00:00:00Z"
            entry = IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Test Report",
                created_at=now,
                updated_at=now,
                path="by_id/test",
            )

            index.add_entry(entry)

            assert index.resolve_title("Test Report") == entry.report_id
            assert (
                index.resolve_title("test report") == entry.report_id
            )  # case insensitive

    def test_resolve_title_partial_match(self) -> None:
        """Test resolving title with partial match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.jsonl"
            index = ReportIndex(index_path)

            now = "2024-01-01T00:00:00Z"
            entry = IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Monthly Sales Report",
                created_at=now,
                updated_at=now,
                path="by_id/test",
            )

            index.add_entry(entry)

            assert index.resolve_title("Sales") == entry.report_id
            assert index.resolve_title("monthly") == entry.report_id

    def test_resolve_title_no_match(self) -> None:
        """Test resolving title with no match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.jsonl"
            index = ReportIndex(index_path)

            assert index.resolve_title("Nonexistent") is None

    def test_resolve_title_multiple_matches(self) -> None:
        """Test resolving title with multiple partial matches returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.jsonl"
            index = ReportIndex(index_path)

            now = "2024-01-01T00:00:00Z"

            entry1 = IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Sales Report Q1",
                created_at=now,
                updated_at=now,
                path="by_id/test1",
            )

            entry2 = IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Sales Report Q2",
                created_at=now,
                updated_at=now,
                path="by_id/test2",
            )

            index.add_entry(entry1)
            index.add_entry(entry2)

            # Should return None for ambiguous partial match
            assert index.resolve_title("Sales Report") is None

    def test_list_entries_filtering(self) -> None:
        """Test listing entries with filtering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.jsonl"
            index = ReportIndex(index_path)

            now = "2024-01-01T00:00:00Z"

            active_entry = IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Active Report",
                created_at=now,
                updated_at=now,
                status="active",
                path="by_id/active",
            )

            archived_entry = IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Archived Report",
                created_at=now,
                updated_at=now,
                status="archived",
                path="by_id/archived",
            )

            index.add_entry(active_entry)
            index.add_entry(archived_entry)

            # Test no filter
            all_entries = index.list_entries()
            assert len(all_entries) == 2

            # Test status filter
            active_only = index.list_entries(status="active")
            assert len(active_only) == 1
            assert active_only[0].status == "active"

            archived_only = index.list_entries(status="archived")
            assert len(archived_only) == 1
            assert archived_only[0].status == "archived"

    def test_list_entries_sorting(self) -> None:
        """Test listing entries with sorting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.jsonl"
            index = ReportIndex(index_path)

            now = "2024-01-01T00:00:00Z"
            later = "2024-01-02T00:00:00Z"

            older_entry = IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Older Report",
                created_at=now,
                updated_at=now,
                path="by_id/older",
            )

            newer_entry = IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Newer Report",
                created_at=now,
                updated_at=later,
                path="by_id/newer",
            )

            index.add_entry(older_entry)
            index.add_entry(newer_entry)

            # Default sort by updated_at descending
            entries = index.list_entries()
            assert entries[0].current_title == "Newer Report"
            assert entries[1].current_title == "Older Report"

            # Sort by title ascending
            entries = index.list_entries(sort_by="current_title", reverse=False)
            assert entries[0].current_title == "Newer Report"
            assert entries[1].current_title == "Older Report"

    def test_validate_consistency_missing_report(self) -> None:
        """Test consistency validation detects missing report directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.jsonl"
            index = ReportIndex(index_path)

            now = "2024-01-01T00:00:00Z"
            entry = IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Missing Report",
                created_at=now,
                updated_at=now,
                path="by_id/missing",
            )

            index.add_entry(entry)

            errors = index.validate_consistency()
            assert len(errors) == 1
            assert "not found on disk" in errors[0]

    def test_rebuild_from_filesystem(self) -> None:
        """Test rebuilding index from filesystem scan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_root = Path(tmpdir) / "reports"
            index_path = reports_root / "index.jsonl"

            # Create some report directories (stub - would need full outline files)
            by_id_dir = reports_root / "by_id"
            by_id_dir.mkdir(parents=True)

            report_dir = by_id_dir / "test_report"
            report_dir.mkdir()

            index = ReportIndex(index_path)

            # For now, rebuild should not crash (would need mock outlines)
            # This is a stub test - full implementation would create valid outlines
            index.rebuild_from_filesystem()
            # Should not raise any exceptions
