from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any, Iterable, Optional

from ..path_utils import DEFAULT_HISTORY_PATH, resolve_history_path

logger = logging.getLogger(__name__)


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

        Enhanced to support optional metric_insight field for LLM-driven analysis.

        Args:
            payload: Query execution payload with enhanced fields:
                - metric_insight: Optional dict with key findings and insights
                - Other standard query execution fields
        """
        if self._path is None or self._disabled:
            return

        # Ensure ISO timestamp format for better readability
        if "ts" in payload and isinstance(payload["ts"], (int, float)):
            import datetime

            payload["timestamp"] = datetime.datetime.fromtimestamp(
                payload["ts"]
            ).isoformat()

        # Validate and structure metric_insight if present
        if "metric_insight" in payload and payload["metric_insight"]:
            insight = payload["metric_insight"]
            if isinstance(insight, str):
                # Convert string insights to structured format
                payload["metric_insight"] = {
                    "summary": insight,
                    "key_metrics": [],
                    "business_impact": "",
                    "follow_up_needed": False,
                }
            elif isinstance(insight, dict):
                # Preserve arbitrary caller-provided fields while ensuring documented defaults
                structured = dict(insight)
                structured.setdefault("summary", "")
                structured.setdefault("key_metrics", [])
                structured.setdefault("business_impact", "")
                structured.setdefault("follow_up_needed", False)
                payload["metric_insight"] = structured

        try:
            line = json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            # Handle non-serializable objects gracefully
            if "metric_insight" in payload:
                # Try to serialize metric_insight specifically
                try:
                    payload["metric_insight"] = str(payload["metric_insight"])
                    line = json.dumps(payload, ensure_ascii=False)
                except Exception:
                    # Fallback: remove problematic field
                    payload_copy = payload.copy()
                    payload_copy.pop("metric_insight", None)
                    line = json.dumps(payload_copy, ensure_ascii=False)
            else:
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
