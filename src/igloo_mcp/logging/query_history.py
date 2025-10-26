from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Optional

from ..path_utils import resolve_history_path


class QueryHistory:
    """Lightweight JSONL history writer for queries.

    Enabled when IGLOO_MCP_QUERY_HISTORY is set to a writable file path.
    Writes one JSON object per line with minimal fields for auditing.
    """

    def __init__(self, path: Optional[Path]) -> None:
        self._path = path
        self._lock = Lock()
        self._enabled = self._path is not None
        if self._path is not None:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                # If directory creation fails, disable history silently
                self._path = None
                self._enabled = False

    @classmethod
    def from_env(cls) -> "QueryHistory":
        raw = os.environ.get("IGLOO_MCP_QUERY_HISTORY")
        if raw is not None and raw.strip() == "":
            return cls(None)

        try:
            path = resolve_history_path(raw=raw)
            return cls(path)
        except Exception:
            return cls(None)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def record(self, payload: dict[str, Any]) -> None:
        if self._path is None:
            return
        line = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            try:
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(line)
                    fh.write("\n")
            except Exception:
                # Best-effort logging; never raise to caller
                pass
