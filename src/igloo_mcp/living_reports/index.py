"""Global report index management and title resolution.

This module provides the global index that tracks all reports in the system,
enabling fast lookup by ID or title, and maintaining consistency across
report directories.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from .models import IndexEntry, Outline


class IndexError(RuntimeError):
    """Base exception for index-related errors."""


class IndexCorruptionError(IndexError):
    """Raised when index file is corrupted."""


class ReportIndex:
    """Global index of all reports in the system.

    Maintains a JSONL file with metadata for all reports, providing
    fast lookup and title resolution.
    """

    def __init__(self, index_path: Path) -> None:
        """Initialize report index.

        Args:
            index_path: Path to the index.jsonl file
        """
        self.index_path = index_path
        self._entries: Dict[str, IndexEntry] = {}
        self._title_to_id: Dict[str, str] = {}
        self._load_index()

    def _load_index(self) -> None:
        """Load index from disk."""
        if not self.index_path.exists():
            return

        entries = {}
        title_to_id = {}

        try:
            with self.index_path.open("r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        entry = IndexEntry(**data)
                        entries[entry.report_id] = entry

                        # Track title mapping (last entry wins for duplicates)
                        title_to_id[entry.current_title.lower()] = entry.report_id

                    except Exception as e:
                        raise IndexCorruptionError(
                            f"Corrupted index entry at line {line_num}: {e}"
                        ) from e

        except (json.JSONDecodeError, IOError) as e:
            raise IndexCorruptionError(f"Failed to load index: {e}") from e

        self._entries = entries
        self._title_to_id = title_to_id

    def rebuild_from_filesystem(self) -> None:
        """Rebuild index by scanning report directories.

        This method scans the by_id/ directory and rebuilds the index
        from the actual report directories on disk. Useful for recovery
        from index corruption or filesystem drift.
        """
        reports_root = self.index_path.parent
        by_id_dir = reports_root / "by_id"

        if not by_id_dir.exists():
            self._entries = {}
            self._title_to_id = {}
            return

        new_entries: Dict[str, IndexEntry] = {}
        title_to_id: Dict[str, str] = {}

        for report_dir in by_id_dir.iterdir():
            if not report_dir.is_dir():
                continue

            outline_path = report_dir / "outline.json"
            if not outline_path.exists():
                # Skip directories without an outline; may be incomplete reports
                continue

            try:
                raw = outline_path.read_text(encoding="utf-8")
                data = json.loads(raw)
                outline = Outline(**data)
            except Exception:
                # Skip corrupted outlines but continue with others
                continue

            report_id = report_dir.name
            entry = IndexEntry(
                report_id=outline.report_id,
                current_title=outline.title,
                created_at=outline.created_at,
                updated_at=outline.updated_at,
                tags=outline.metadata.get("tags", []),
                status="active",  # Assume active unless marked otherwise
                path=f"by_id/{report_id}",
            )

            new_entries[entry.report_id] = entry
            title_to_id[entry.current_title.lower()] = entry.report_id

        self._entries = new_entries
        self._title_to_id = title_to_id

        # Rewrite index file
        self._save_index()

    def _save_index(self) -> None:
        """Save current index to disk."""
        temp_path = self.index_path.with_suffix(".tmp")

        try:
            with temp_path.open("w", encoding="utf-8") as f:
                for entry in self._entries.values():
                    data = entry.model_dump()
                    line = json.dumps(data, ensure_ascii=False) + "\n"
                    f.write(line)
                f.flush()
                os.fsync(f.fileno())

            temp_path.replace(self.index_path)
            # Best-effort directory sync for index durability
            try:
                dir_fd = os.open(str(self.index_path.parent), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (OSError, AttributeError):
                pass

        except Exception as e:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise IndexError(f"Failed to save index: {e}") from e

    def add_entry(self, entry: IndexEntry) -> None:
        """Add or update an index entry.

        Args:
            entry: Index entry to add/update
        """
        self._entries[entry.report_id] = entry
        self._title_to_id[entry.current_title.lower()] = entry.report_id
        self._save_index()

    def remove_entry(self, report_id: str) -> None:
        """Remove an index entry.

        Args:
            report_id: Report ID to remove
        """
        if report_id in self._entries:
            entry = self._entries[report_id]
            del self._entries[report_id]

            # Remove title mapping if it points to this report
            if self._title_to_id.get(entry.current_title.lower()) == report_id:
                del self._title_to_id[entry.current_title.lower()]

        self._save_index()

    def get_entry(self, report_id: str) -> Optional[IndexEntry]:
        """Get index entry by report ID.

        Args:
            report_id: Report identifier

        Returns:
            Index entry or None if not found
        """
        return self._entries.get(report_id)

    def resolve_title(self, title: str, allow_partial: bool = True) -> Optional[str]:
        """Resolve a title to a report ID.

        Args:
            title: Title to resolve (case-insensitive)
            allow_partial: If True, allow partial matches

        Returns:
            Report ID or None if not found
        """
        title_lower = title.lower()

        # Exact match first
        if title_lower in self._title_to_id:
            return self._title_to_id[title_lower]

        if not allow_partial:
            return None

        # Partial match on active reports
        candidates = []
        for entry in self._entries.values():
            if entry.status != "active":
                continue
            if title_lower in entry.current_title.lower():
                candidates.append((entry.current_title, entry.report_id))

        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0][1]

        # Multiple matches - return None to force explicit selection
        # In a real implementation, this might raise an error or return
        # a list of candidates for user selection
        return None

    def list_entries(
        self,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        sort_by: str = "updated_at",
        reverse: bool = True,
    ) -> List[IndexEntry]:
        """List index entries with optional filtering.

        Args:
            status: Filter by status (active/archived)
            tags: Filter by tags (reports must have all specified tags)
            sort_by: Sort field (created_at, updated_at, current_title)
            reverse: Reverse sort order

        Returns:
            List of matching index entries
        """
        entries = list(self._entries.values())

        # Apply filters
        if status:
            entries = [e for e in entries if e.status == status]

        if tags:
            tag_set = set(tags)
            entries = [e for e in entries if tag_set.issubset(set(e.tags))]

        # Sort
        if sort_by == "created_at":
            key_func = lambda e: e.created_at
        elif sort_by == "current_title":
            key_func = lambda e: e.current_title.lower()
        else:  # updated_at (default)
            key_func = lambda e: e.updated_at

        entries.sort(key=key_func, reverse=reverse)

        return entries

    def validate_consistency(self) -> List[str]:
        """Validate index consistency with filesystem.

        Returns:
            List of validation error messages
        """
        errors = []
        reports_root = self.index_path.parent
        by_id_dir = reports_root / "by_id"

        # Check that all indexed reports exist on disk
        for report_id, entry in self._entries.items():
            report_dir = by_id_dir / report_id
            if not report_dir.exists():
                errors.append(f"Indexed report {report_id} not found on disk")

        # Check for unindexed reports on disk
        if by_id_dir.exists():
            for report_dir in by_id_dir.iterdir():
                if not report_dir.is_dir():
                    continue
                report_id = report_dir.name
                if report_id not in self._entries:
                    errors.append(f"Unindexed report directory: {report_id}")

        return errors


__all__ = [
    "IndexCorruptionError",
    "IndexError",
    "ReportIndex",
]
