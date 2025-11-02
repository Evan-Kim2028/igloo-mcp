from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any, Iterable, Optional, TypedDict, cast

from ..path_utils import DEFAULT_HISTORY_PATH, resolve_history_path

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
    norm = cast(Insight, dict(value))
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
            truncated_summary = summary_bytes[:max_summary_bytes].decode(
                "utf-8", errors="ignore"
            )
            # Try to avoid cutting in the middle of a multi-byte character
            while len(truncated_summary.encode("utf-8")) > max_summary_bytes - 3:
                truncated_summary = truncated_summary[:-1]
            truncated["summary"] = truncated_summary + "..."
    return cast(Insight, truncated)


class QueryHistory:
    """Lightweight JSONL history writer for queries.

    Enabled when IGLOO_MCP_QUERY_HISTORY is set to a writable file path.
    Writes one JSON object per line with minimal fields for auditing.
    """

    _DISABLE_SENTINELS = {"", "disabled", "off", "false", "0"}

    def __init__(
        self,
        path: Optional[Path],
        *,
        fallbacks: Optional[Iterable[Path]] = None,
        disabled: bool = False,
    ) -> None:
        self._path: Optional[Path] = None
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
                    warning = (
                        "Query history path unavailable; using fallback: "
                        f"{candidate}"
                    )
                    self._warnings.append(warning)
                    logger.warning(warning)
                break
            except Exception as exc:
                warning = "Failed to initialise query history path %s: %s" % (
                    candidate,
                    exc,
                )
                self._warnings.append(warning)
                logger.warning(warning)

        if not self._enabled:
            if candidates:
                warning = (
                    "Query history disabled because no writable path was available."
                )
                self._warnings.append(warning)
                logger.warning(warning)
            else:
                # No candidates means caller explicitly passed None; stay silent.
                pass

    @classmethod
    def from_env(cls) -> "QueryHistory":
        raw = os.environ.get("IGLOO_MCP_QUERY_HISTORY")
        raw_clean = raw.strip() if raw is not None else None

        disabled = False
        if raw_clean is not None and raw_clean.lower() in cls._DISABLE_SENTINELS:
            disabled = True

        fallbacks: list[Path] = []
        fallback_home = Path.home() / ".igloo_mcp" / DEFAULT_HISTORY_PATH

        try:
            fallback_home.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Best effort; QueryHistory.__init__ will surface warnings if used.
            pass

        try:
            if disabled:
                return cls(None, disabled=True)

            path = resolve_history_path(raw=raw)
            if path is not None and path != fallback_home:
                fallbacks.append(fallback_home)
            return cls(path, fallbacks=fallbacks)
        except Exception:
            warning = "Unable to resolve query history path; using fallback"
            logger.warning(warning, exc_info=True)
            return cls(fallback_home, fallbacks=[], disabled=False)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def path(self) -> Optional[Path]:
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

            payload["timestamp"] = datetime.datetime.fromtimestamp(
                payload["ts"]
            ).isoformat()

        try:
            line = json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            # Fallback: convert to string representation
            line = json.dumps(
                {
                    "error": f"Serialization failed: {str(e)}",
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
                warning = "Failed to append query history entry to %s" % (self._path,)
                self._warnings.append(warning)
                logger.warning(warning, exc_info=True)

    def record_insight(
        self,
        execution_id: str,
        post_query_insight: str | dict[str, Any],
        *,
        source: Optional[str] = None,
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
                        except Exception:
                            continue
            except Exception:
                pass

        if not deduped:
            # Append new history entry
            import time
            from datetime import datetime, timezone

            payload = {
                "ts": time.time(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
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
                    warning = "Failed to append insight record to %s" % (self._path,)
                    self._warnings.append(warning)
                    logger.warning(warning, exc_info=True)

        return {
            "execution_id": execution_id,
            "deduped": deduped,
            "content_sha256": content_sha256,
        }


def update_cache_manifest_insight(
    manifest_path: Path, post_query_insight: str | dict[str, Any]
) -> bool:
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
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            return False
    except Exception:
        logger.debug("Failed to update cache manifest", exc_info=True)
        return False
