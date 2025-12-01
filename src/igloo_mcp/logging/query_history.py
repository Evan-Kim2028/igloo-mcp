from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
from collections.abc import Iterable
from datetime import UTC
from pathlib import Path
from threading import Lock
from typing import Any, ClassVar, TypedDict, cast

from igloo_mcp.path_utils import (
    DEFAULT_HISTORY_PATH,
    apply_namespacing,
    find_repo_root,
    get_global_base,
    resolve_history_path,
)

logger = logging.getLogger(__name__)


class Insight(TypedDict, total=False):
    """Normalized insight structure for post-query analysis."""

    summary: str
    key_metrics: list[str]
    business_impact: str
    follow_up_needed: bool
    source: str


def normalize_insight(value: str | dict[str, Any]) -> Insight:
    """Normalize insight value to structured Insight format.

    Args:
        value: Either a string summary or a dict with insight fields

    Returns:
        Normalized Insight dict with all required fields set
    """
    if isinstance(value, str):
        return {
            "summary": value,
            "key_metrics": [],
            "business_impact": "",
            "follow_up_needed": False,
        }
    norm = cast("Insight", dict(value))
    norm.setdefault("summary", "")
    norm.setdefault("key_metrics", [])
    norm.setdefault("business_impact", "")
    norm.setdefault("follow_up_needed", False)
    return norm


def truncate_insight_for_storage(insight: Insight, max_bytes: int = 16384) -> Insight:
    """Truncate insight to fit within storage size limit.

    Args:
        insight: Normalized insight dict
        max_bytes: Maximum size in bytes (default: 16KB)

    Returns:
        Truncated insight dict (or original if within limit)
    """
    serialized = json.dumps(insight, ensure_ascii=False)
    if len(serialized.encode("utf-8")) <= max_bytes:
        return insight

    # Truncate summary field if present and too large
    truncated = dict(insight)
    summary = str(truncated.get("summary", ""))
    if summary:
        # Estimate bytes and truncate with ellipsis
        summary_bytes = summary.encode("utf-8")
        if len(summary_bytes) > max_bytes - 100:  # Reserve space for other fields
            max_summary_bytes = max_bytes - 100
            truncated_summary = summary_bytes[:max_summary_bytes].decode("utf-8", errors="ignore")
            # Try to avoid cutting in the middle of a multi-byte character
            while len(truncated_summary.encode("utf-8")) > max_summary_bytes - 3:
                truncated_summary = truncated_summary[:-1]
            truncated["summary"] = truncated_summary + "..."
    return cast("Insight", truncated)


class QueryHistory:
    """Lightweight JSONL history writer for queries.

    Enabled when IGLOO_MCP_QUERY_HISTORY is set to a writable file path.
    Writes one JSON object per line with minimal fields for auditing.
    """

    _DISABLE_SENTINELS: ClassVar[set[str]] = {"", "disabled", "off", "false", "0"}

    def __init__(
        self,
        path: Path | None,
        *,
        fallbacks: Iterable[Path] | None = None,
        disabled: bool = False,
    ) -> None:
        self._path: Path | None = None
        self._lock = Lock()
        self._enabled = False
        self._disabled = disabled
        self._warnings: list[str] = []

        if self._disabled:
            return

        candidates: list[Path] = []
        if path is not None:
            candidates.append(path)
        if fallbacks:
            for candidate in fallbacks:
                if candidate not in candidates:
                    candidates.append(candidate)

        for index, candidate in enumerate(candidates):
            try:
                candidate.parent.mkdir(parents=True, exist_ok=True)
                self._path = candidate
                self._enabled = True
                if index > 0:
                    warning = f"Query history path unavailable; using fallback: {candidate}"
                    self._warnings.append(warning)
                    logger.warning(warning)
                break
            except Exception as exc:
                warning = f"Failed to initialise query history path {candidate}: {exc}"
                self._warnings.append(warning)
                logger.warning(warning)

        if not self._enabled:
            if candidates:
                warning = "Query history disabled because no writable path was available."
                self._warnings.append(warning)
                logger.warning(warning)
            else:
                # No candidates means caller explicitly passed None; stay silent.
                pass

    @classmethod
    def from_env(cls) -> QueryHistory:
        """Create QueryHistory instance from environment configuration.

        Uses resolve_history_path() exclusively for path resolution.
        Honors IGLOO_MCP_LOG_SCOPE and IGLOO_MCP_NAMESPACED_LOGS.
        """
        raw = os.environ.get("IGLOO_MCP_QUERY_HISTORY")
        raw_clean = raw.strip() if raw is not None else None

        disabled = False
        if raw_clean is not None and raw_clean.lower() in cls._DISABLE_SENTINELS:
            disabled = True

        if disabled:
            return cls(None, disabled=True)

        def _fallback_candidates() -> list[Path]:
            candidates: list[Path] = []
            try:
                global_path = (get_global_base() / apply_namespacing(DEFAULT_HISTORY_PATH)).resolve()
                candidates.append(global_path)
            except Exception:
                pass
            try:
                repo_root = find_repo_root()
                repo_path = (repo_root / apply_namespacing(DEFAULT_HISTORY_PATH)).resolve()
                if repo_path not in candidates:
                    candidates.append(repo_path)
            except Exception:
                pass
            return candidates

        fallbacks = _fallback_candidates()

        try:
            path = resolve_history_path(raw=raw)
        except Exception:
            warning = "Unable to resolve query history path; attempting fallback"
            logger.warning(warning, exc_info=True)
            if not fallbacks:
                warning = "History disabled; no fallback paths available"
                logger.warning(warning)
                return cls(None, disabled=False)
            primary = fallbacks[0]
            remaining = [candidate for candidate in fallbacks[1:] if candidate != primary]
            return cls(primary, fallbacks=remaining or None)

        path = path.resolve()
        remaining_fallbacks = [candidate for candidate in fallbacks if candidate != path]
        return cls(path, fallbacks=remaining_fallbacks or None)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def disabled(self) -> bool:
        return self._disabled

    def pop_warnings(self) -> list[str]:
        warnings = list(self._warnings)
        self._warnings.clear()
        return warnings

    def record(self, payload: dict[str, Any]) -> None:
        """Record a query execution to the JSONL history file.

        Args:
            payload: Query execution payload with standard fields
        """
        if self._path is None or self._disabled:
            return

        # Ensure ISO timestamp format for better readability
        if "ts" in payload and isinstance(payload["ts"], (int, float)):
            import datetime

            # Use UTC timezone to ensure consistent timestamps across environments
            payload["timestamp"] = datetime.datetime.fromtimestamp(payload["ts"], tz=datetime.UTC).isoformat()

        try:
            line = json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            # Fallback: convert to string representation
            line = json.dumps(
                {
                    "error": f"Serialization failed: {e!s}",
                    "original_preview": str(payload)[:200],
                },
                ensure_ascii=False,
            )

        with self._lock:
            try:
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(line)
                    fh.write("\n")
            except Exception:
                warning = f"Failed to append query history entry to {self._path}"
                self._warnings.append(warning)
                logger.warning(warning, exc_info=True)

    def record_insight(
        self,
        execution_id: str,
        post_query_insight: str | dict[str, Any],
        *,
        source: str | None = None,
    ) -> dict[str, Any]:
        """Record a post-hoc insight for a prior query execution.

        Args:
            execution_id: Execution ID from execute_query.audit_info.execution_id
            post_query_insight: LLM-provided post-query insight (str or dict)
            source: Optional source identifier (e.g., "human", "agent:claude")

        Returns:
            Dict with execution_id, content_sha256, and deduped flag
        """
        if self._path is None or self._disabled:
            return {
                "execution_id": execution_id,
                "deduped": False,
                "content_sha256": None,
            }

        # Normalize insight
        normalized = normalize_insight(post_query_insight)
        truncated = truncate_insight_for_storage(normalized)

        # Compute content hash for deduplication
        content_json = json.dumps(truncated, ensure_ascii=False, sort_keys=True)
        content_sha256 = hashlib.sha256(content_json.encode("utf-8")).hexdigest()

        # Check for duplicate (execution_id, content_sha256)
        deduped = False
        if self._path.exists():
            try:
                with self._path.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if (
                                entry.get("execution_id") == execution_id
                                and entry.get("status") == "insight_recorded"
                                and entry.get("content_sha256") == content_sha256
                            ):
                                deduped = True
                                break
                        except (ValueError, KeyError, TypeError) as e:
                            # Skip malformed history entries
                            logger.debug(f"Skipping malformed history entry during dedup check: {e}")
                            continue
            except (OSError, ValueError) as e:
                # Best effort - if history file is corrupt, continue anyway
                logger.debug(f"Error reading history during dedup check: {e}")

        if not deduped:
            # Append new history entry
            import time
            from datetime import datetime

            payload = {
                "ts": time.time(),
                "timestamp": datetime.now(UTC).isoformat(),
                "execution_id": execution_id,
                "status": "insight_recorded",
                "post_query_insight": truncated,
                "content_sha256": content_sha256,
            }
            if source:
                payload["source"] = source

            try:
                line = json.dumps(payload, ensure_ascii=False)
            except Exception:
                # Fallback serialization
                payload_fallback = {
                    "execution_id": execution_id,
                    "status": "insight_recorded",
                    "error": "Serialization failed",
                }
                line = json.dumps(payload_fallback, ensure_ascii=False)

            with self._lock:
                try:
                    with self._path.open("a", encoding="utf-8") as fh:
                        fh.write(line)
                        fh.write("\n")
                except Exception:
                    warning = f"Failed to append insight record to {self._path}"
                    self._warnings.append(warning)
                    logger.warning(warning, exc_info=True)

        return {
            "execution_id": execution_id,
            "deduped": deduped,
            "content_sha256": content_sha256,
        }


def update_cache_manifest_insight(manifest_path: Path, post_query_insight: str | dict[str, Any]) -> bool:
    """Atomically update cache manifest with post_query_insight.

    Args:
        manifest_path: Path to cache manifest.json
        post_query_insight: LLM-provided insight (str or dict)

    Returns:
        True if update succeeded, False otherwise
    """
    if not manifest_path.exists():
        return False

    try:
        # Load existing manifest
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))

        # Normalize and truncate insight
        normalized = normalize_insight(post_query_insight)
        truncated = truncate_insight_for_storage(normalized)

        # Update manifest
        manifest_data["post_query_insight"] = truncated

        # Atomic write: temp file + os.replace
        temp_path = manifest_path.with_suffix(".tmp.json")
        try:
            temp_path.write_text(
                json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temp_path.replace(manifest_path)
            return True
        except Exception:
            # Clean up temp file on failure
            with contextlib.suppress(Exception):
                temp_path.unlink(missing_ok=True)
            return False
    except Exception:
        logger.debug("Failed to update cache manifest", exc_info=True)
        return False
