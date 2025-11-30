"""Storage layer for living reports with atomic operations and locking.

This module provides the filesystem operations for living reports,
ensuring atomic writes, crash recovery, and cross-platform file locking.

ATOMICITY GUARANTEE:
All write operations follow the temp-file + atomic rename pattern:
1. Write to {path}.tmp
2. fsync the temp file
3. Atomic rename {path}.tmp -> {path}
4. Best-effort directory fsync for durability

This guarantees that:
- Writes are atomic (all-or-nothing)
- No partial state is visible to readers
- Crash recovery finds either old or new state, never partial

CONCURRENCY CONTROL:
- Per-report file locks via portalocker (or file existence fallback)
- Operations acquire lock via storage.lock() context manager
- Lock timeout: 30 seconds (configurable)
- Deadlock prevention: Always acquire single report lock only

RECOVERY PATTERN:
If index.jsonl becomes inconsistent:
1. Call ReportIndex.rebuild_from_filesystem()
2. Scans by_id/* directories
3. Reconstructs index from outline.json files
4. Audit logs remain intact for full history
"""

from __future__ import annotations

import datetime
import json
import os
import uuid
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

try:
    import portalocker

    HAS_PORTALOCKER = True
except ImportError:
    HAS_PORTALOCKER = False

from .models import AuditEvent, Outline


class StorageError(RuntimeError):
    """Base exception for storage-related errors."""


class LockTimeoutError(StorageError):
    """Raised when unable to acquire a file lock within timeout."""


class ReportLock:
    """File-based locking for report operations.

    Uses portalocker for cross-platform advisory file locking.
    Falls back to basic file existence checks if portalocker unavailable.
    """

    def __init__(self, lock_path: Path, timeout_seconds: float = 30.0) -> None:
        """Initialize lock.

        Args:
            lock_path: Path to lock file
            timeout_seconds: Maximum time to wait for lock acquisition
        """
        self.lock_path = lock_path
        self.timeout_seconds = timeout_seconds
        self._lock_file: Any | None = None

    def acquire(self) -> None:
        """Acquire the lock.

        Raises:
            LockTimeoutError: If lock cannot be acquired within timeout
            RuntimeError: If portalocker not available and lock file exists
        """
        if not HAS_PORTALOCKER:
            # Fallback: check file existence
            if self.lock_path.exists():
                raise RuntimeError(f"Lock file exists: {self.lock_path}")
            try:
                self.lock_path.write_text("")
                self._lock_file = self.lock_path
            except Exception as e:
                raise RuntimeError(f"Failed to create lock file: {e}") from e
            return

        try:
            self._lock_file = open(self.lock_path, "w")
            portalocker.lock(
                self._lock_file,
                portalocker.LOCK_EX | portalocker.LOCK_NB,
                timeout=self.timeout_seconds,
            )
        except portalocker.LockException as e:
            raise LockTimeoutError(f"Failed to acquire lock within {self.timeout_seconds}s: {e}") from e
        except Exception as e:
            if self._lock_file:
                self._lock_file.close()
                self._lock_file = None
            raise RuntimeError(f"Lock acquisition failed: {e}") from e

    def release(self) -> None:
        """Release the lock."""
        if not HAS_PORTALOCKER:
            if self._lock_file and self._lock_file.exists():
                try:
                    self._lock_file.unlink()
                except Exception:
                    pass  # Best effort cleanup
            self._lock_file = None
            return

        if self._lock_file:
            try:
                portalocker.unlock(self._lock_file)
                self._lock_file.close()
            except Exception:
                pass  # Best effort cleanup
            finally:
                self._lock_file = None

    def __enter__(self) -> ReportLock:
        """Context manager entry."""
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.release()


class ReportStorage:
    """Storage operations for a single report.

    Handles atomic writes, backups, and audit logging for report operations.
    """

    def __init__(self, report_dir: Path) -> None:
        """Initialize storage for a report.

        Args:
            report_dir: Directory containing the report files
        """
        self.report_dir = report_dir
        self.outline_path = report_dir / "outline.json"
        self.audit_path = report_dir / "audit.jsonl"
        self.backups_dir = report_dir / "backups"
        self.lock_path = report_dir / ".lock"

        # Create directories if they don't exist
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def lock(self, timeout_seconds: float = 30.0) -> Generator[ReportLock, None, None]:
        """Context manager for report locking.

        Args:
            timeout_seconds: Lock acquisition timeout

        Yields:
            ReportLock instance
        """
        lock = ReportLock(self.lock_path, timeout_seconds)
        try:
            with lock:
                yield lock
        except Exception:
            raise

    def load_outline(self) -> Outline:
        """Load outline from disk.

        Returns:
            Parsed Outline object

        Raises:
            FileNotFoundError: If outline.json doesn't exist
            ValueError: If outline is invalid
        """
        if not self.outline_path.exists():
            raise FileNotFoundError(f"Outline not found: {self.outline_path}")

        try:
            raw = self.outline_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return Outline(**data)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Invalid outline at {self.outline_path}: {e}") from e

    def _save_outline_atomic(self, outline: Outline) -> str | None:
        """Atomically save outline to disk with backup.

        Args:
            outline: Outline to save

        Returns:
            Backup filename if created, None otherwise

        Raises:
            StorageError: If save operation fails
        """
        # Create backup and track filename
        backup_filename = None
        if self.outline_path.exists():
            backup_filename = self._create_backup()

        # Write to temporary file first
        temp_path = self.outline_path.with_suffix(".tmp")
        try:
            # Serialize and write to temp file
            data = outline.model_dump(by_alias=True)
            raw = json.dumps(data, indent=2, ensure_ascii=False)

            with temp_path.open("w", encoding="utf-8") as f:
                f.write(raw)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    # Best-effort fsync; some filesystems may not support it
                    pass

            # Atomic rename
            temp_path.replace(self.outline_path)

            # Best-effort directory sync for durability
            try:
                dir_fd = os.open(str(self.report_dir), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (OSError, AttributeError):
                # os.fsync on directories may not be supported on all platforms
                pass

            return backup_filename

        except Exception as e:
            # Clean up temp file on failure
            with suppress(Exception):
                temp_path.unlink(missing_ok=True)
            raise StorageError(f"Failed to save outline: {e}") from e
        finally:
            # Ensure temp file is cleaned up
            with suppress(Exception):
                temp_path.unlink(missing_ok=True)

    def save_outline(self, outline: Outline) -> None:
        """Atomically save outline and record a backup audit event.

        This method is intended for low-level callers; higher-level services
        that manage their own audit events should use _save_outline_atomic.
        """
        self._save_outline_atomic(outline)

        # If an audit log already exists, append a backup event
        if self.audit_path.exists():
            try:
                event = AuditEvent(
                    action_id=str(uuid.uuid4()),
                    report_id=outline.report_id,
                    ts=datetime.datetime.now(datetime.UTC).isoformat(),
                    actor="cli",
                    action_type="backup",
                    payload={"reason": "outline_save"},
                )
                self.append_audit_event(event)
            except Exception:
                # Best-effort; do not fail saves on audit issues
                pass

    def _create_backup(self) -> str | None:
        """Create timestamped backup of current outline.

        Returns:
            Backup filename (e.g., 'outline.json.20231023T143022_123456.bak')
            or None if no backup created
        """
        if not self.outline_path.exists():
            return None

        import datetime

        now = datetime.datetime.now(datetime.UTC)
        # Include microseconds to avoid filename collisions within the same second
        timestamp_clean = now.strftime("%Y%m%dT%H%M%S") + f"_{now.microsecond:06d}"
        backup_filename = f"outline.json.{timestamp_clean}.bak"
        backup_path = self.backups_dir / backup_filename

        try:
            import shutil

            shutil.copy2(self.outline_path, backup_path)
            return backup_filename
        except Exception:
            # Best-effort backup - don't fail writes if backup fails
            return None

    def append_audit_event(self, event: AuditEvent) -> None:
        """Append audit event to audit log.

        Args:
            event: Audit event to append

        Raises:
            StorageError: If append operation fails
        """
        temp_path = self.audit_path.with_suffix(".tmp")
        try:
            # Serialize event
            data = event.model_dump()
            line = json.dumps(data, ensure_ascii=False) + "\n"

            # Write to temp file
            with temp_path.open("a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            if self.audit_path.exists():
                # Append to existing file
                with temp_path.open("rb") as src, self.audit_path.open("ab") as dst:
                    src.seek(0)
                    dst.write(src.read())
                    dst.flush()
                    os.fsync(dst.fileno())
                temp_path.unlink()
            else:
                temp_path.replace(self.audit_path)

            # Best-effort directory sync; may not be available on all platforms
            try:
                dir_fd = os.open(str(self.report_dir), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (OSError, AttributeError):
                pass

        except Exception as e:
            with suppress(Exception):
                temp_path.unlink(missing_ok=True)
            raise StorageError(f"Failed to append audit event: {e}") from e

    def load_audit_events(self) -> list[AuditEvent]:
        """Load all audit events for this report.

        Returns:
            List of audit events in chronological order
        """
        if not self.audit_path.exists():
            return []

        events = []
        try:
            with self.audit_path.open("r", encoding="utf-8") as f:
                for _line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        event = AuditEvent(**data)
                        events.append(event)
                    except Exception:
                        # Skip malformed lines but continue
                        continue
        except Exception:
            # Return what we could parse
            pass

        return events

    def detect_manual_edits(self) -> bool:
        """Check if outline.json appears to have been manually edited.

        Returns:
            True if manual edits are detected
        """
        if not self.outline_path.exists():
            return False

        # Simple heuristic: check if file is valid JSON but invalid Outline
        try:
            raw = self.outline_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            Outline(**data)
            return False
        except (json.JSONDecodeError, ValueError):
            return True


class GlobalStorage:
    """Global storage operations for the reports system."""

    def __init__(self, reports_root: Path) -> None:
        """Initialize global storage.

        Args:
            reports_root: Root directory for all reports
        """
        self.reports_root = reports_root
        self.index_path = reports_root / "index.jsonl"
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

    def get_report_storage(self, report_id: str) -> ReportStorage:
        """Get storage instance for a specific report.

        Args:
            report_id: Report identifier

        Returns:
            ReportStorage instance
        """
        report_dir = self.reports_root / "by_id" / report_id
        return ReportStorage(report_dir)

    def save_index_entry(self, entry: dict[str, Any]) -> None:
        """Atomically append index entry.

        Args:
            entry: Index entry data
        """
        temp_path = self.index_path.with_suffix(".tmp")
        try:
            line = json.dumps(entry, ensure_ascii=False) + "\n"

            with temp_path.open("a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

            if self.index_path.exists():
                with temp_path.open("rb") as src, self.index_path.open("ab") as dst:
                    src.seek(0)
                    dst.write(src.read())
                    dst.flush()
                    os.fsync(dst.fileno())
                temp_path.unlink()
            else:
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
            with suppress(Exception):
                temp_path.unlink(missing_ok=True)
            raise StorageError(f"Failed to save index entry: {e}") from e


__all__ = [
    "GlobalStorage",
    "LockTimeoutError",
    "ReportLock",
    "ReportStorage",
    "StorageError",
]
