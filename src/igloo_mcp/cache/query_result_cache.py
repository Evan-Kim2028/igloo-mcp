from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..path_utils import (
    DEFAULT_ARTIFACT_ROOT,
    DEFAULT_CACHE_SUBDIR,
    resolve_cache_root,
)

logger = logging.getLogger(__name__)


@dataclass
class CacheHit:
    """Represents a successful cache lookup."""

    cache_key: str
    rows: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    manifest_path: Path
    result_json_path: Path
    result_csv_path: Optional[Path]


class QueryResultCache:
    """Simple filesystem-backed cache for query results."""

    DEFAULT_MODE = "enabled"
    VALID_MODES = {"enabled", "disabled", "read_only", "refresh"}
    DISABLE_SENTINELS = {"disabled", "off", "false", "0"}
    DEFAULT_MAX_ROWS = 5_000

    def __init__(
        self,
        *,
        mode: str,
        root: Optional[Path],
        max_rows: int = DEFAULT_MAX_ROWS,
        fallbacks: Optional[Iterable[Path]] = None,
    ) -> None:
        self._mode = mode if mode in self.VALID_MODES else self.DEFAULT_MODE
        self._root: Optional[Path] = None
        self._max_rows = max_rows
        self._warnings: list[str] = []

        if self._mode == "disabled":
            return

        candidates: list[Path] = []
        if root is not None:
            candidates.append(root)
        if fallbacks:
            for candidate in fallbacks:
                if candidate not in candidates:
                    candidates.append(candidate)

        for index, candidate in enumerate(candidates):
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                self._root = candidate
                if index > 0:
                    warning = "Cache root unavailable; using fallback: %s" % candidate
                    self._warnings.append(warning)
                    logger.warning(warning)
                break
            except Exception as exc:
                warning = "Failed to initialise cache root %s: %s" % (candidate, exc)
                self._warnings.append(warning)
                logger.warning(warning)

        if self._root is None:
            warning = (
                "Query result cache disabled because no writable root was available."
            )
            self._warnings.append(warning)
            logger.warning(warning)
            self._mode = "disabled"

    @classmethod
    def from_env(
        cls,
        *,
        artifact_root: Optional[Path],
    ) -> "QueryResultCache":
        mode_raw = os.environ.get("IGLOO_MCP_CACHE_MODE", cls.DEFAULT_MODE)
        mode = (mode_raw or cls.DEFAULT_MODE).strip().lower()
        if not mode:
            mode = cls.DEFAULT_MODE
        if mode not in cls.VALID_MODES:
            logger.warning(
                "Unknown IGLOO_MCP_CACHE_MODE=%r; defaulting to %s",
                mode_raw,
                cls.DEFAULT_MODE,
            )
            mode = cls.DEFAULT_MODE

        root_raw = os.environ.get("IGLOO_MCP_CACHE_ROOT")
        disable_via_root = bool(
            root_raw and root_raw.strip().lower() in cls.DISABLE_SENTINELS
        )
        if disable_via_root:
            return cls(mode="disabled", root=None)

        try:
            resolved_root = resolve_cache_root(
                raw=root_raw,
                artifact_root=artifact_root,
            )
        except Exception as exc:
            logger.warning(
                "Failed to resolve cache root (raw=%r): %s",
                root_raw,
                exc,
                exc_info=True,
            )
            resolved_root = None

        fallback_root = (
            Path.home() / ".igloo_mcp" / DEFAULT_ARTIFACT_ROOT / DEFAULT_CACHE_SUBDIR
        )

        try:
            fallback_root.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Best effort; main constructor will surface if used.
            pass

        max_rows_env = os.environ.get("IGLOO_MCP_CACHE_MAX_ROWS")
        max_rows = cls.DEFAULT_MAX_ROWS
        if max_rows_env:
            try:
                candidate_rows = int(max_rows_env)
                if candidate_rows > 0:
                    max_rows = candidate_rows
            except ValueError:
                logger.warning(
                    "Invalid IGLOO_MCP_CACHE_MAX_ROWS=%r; using default %d",
                    max_rows_env,
                    max_rows,
                )

        fallbacks: list[Path] = []
        if resolved_root is None or resolved_root != fallback_root:
            fallbacks.append(fallback_root)

        return cls(
            mode=mode,
            root=resolved_root,
            max_rows=max_rows,
            fallbacks=fallbacks,
        )

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def enabled(self) -> bool:
        return self._mode != "disabled" and self._root is not None

    @property
    def root(self) -> Optional[Path]:
        return self._root

    @property
    def max_rows(self) -> int:
        return self._max_rows

    def pop_warnings(self) -> list[str]:
        warnings = list(self._warnings)
        self._warnings.clear()
        return warnings

    @staticmethod
    def _iso_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def compute_cache_key(
        self,
        *,
        sql_sha256: str,
        profile: str,
        effective_context: Dict[str, Optional[str]],
    ) -> str:
        payload = {
            "sql_sha256": sql_sha256,
            "profile": profile,
            "context": {k: effective_context.get(k) for k in sorted(effective_context)},
        }
        blob = json.dumps(payload, sort_keys=True, separators=("|", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _directory_for_key(self, cache_key: str) -> Optional[Path]:
        if self._root is None:
            return None
        return self._root / cache_key

    def lookup(self, cache_key: str) -> Optional[CacheHit]:
        if not self.enabled or self._mode == "refresh":
            return None

        key_dir = self._directory_for_key(cache_key)
        if key_dir is None:
            return None
        manifest_path = key_dir / "manifest.json"
        if not manifest_path.exists():
            return None

        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            warning = f"Failed to read cache manifest {manifest_path}: {exc}"
            self._warnings.append(warning)
            logger.warning(warning)
            return None

        if manifest_data.get("cache_key") != cache_key:
            warning = f"Cache manifest mismatch for {cache_key}; ignoring entry"
            self._warnings.append(warning)
            logger.warning(warning)
            return None

        result_json_rel = manifest_data.get("result_json")
        if not result_json_rel:
            return None

        result_json_path = key_dir / result_json_rel
        if not result_json_path.exists():
            warning = f"Cache rows file missing for {cache_key}"
            self._warnings.append(warning)
            logger.warning(warning)
            return None

        rows: List[Dict[str, Any]] = []
        try:
            with result_json_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    rows.append(json.loads(line))
        except Exception as exc:
            warning = f"Failed to load cached rows for {cache_key}: {exc}"
            self._warnings.append(warning)
            logger.warning(warning)
            return None

        result_csv_path: Optional[Path] = None
        result_csv_rel = manifest_data.get("result_csv")
        if result_csv_rel:
            result_csv_path = key_dir / result_csv_rel
            if not result_csv_path.exists():
                result_csv_path = None

        metadata = {
            key: manifest_data.get(key)
            for key in (
                "created_at",
                "profile",
                "context",
                "rowcount",
                "duration_ms",
                "statement_sha256",
                "truncated",
                "post_query_insight",
                "reason",
            )
        }
        metadata["cache_hit"] = True
        metadata["manifest_version"] = manifest_data.get("version")
        if "columns" in manifest_data:
            metadata["columns"] = manifest_data.get("columns")
        if "key_metrics" in manifest_data:
            metadata["key_metrics"] = manifest_data.get("key_metrics")
        if "insights" in manifest_data:
            metadata["insights"] = manifest_data.get("insights")
        return CacheHit(
            cache_key=cache_key,
            rows=rows,
            metadata=metadata,
            manifest_path=manifest_path,
            result_json_path=result_json_path,
            result_csv_path=result_csv_path,
        )

    def store(
        self,
        cache_key: str,
        *,
        rows: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> Optional[Path]:
        if not self.enabled:
            return None
        if self._mode == "read_only":
            return None
        if len(rows) > self._max_rows:
            warning = "Skipping cache store for %s (rows=%d exceeds limit %d)" % (
                cache_key,
                len(rows),
                self._max_rows,
            )
            self._warnings.append(warning)
            logger.info(warning)
            return None

        key_dir = self._directory_for_key(cache_key)
        if key_dir is None:
            return None

        try:
            key_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            warning = "Failed to create cache directory %s: %s" % (key_dir, exc)
            self._warnings.append(warning)
            logger.warning(warning)
            return None

        result_json_path = key_dir / "rows.jsonl"
        try:
            with result_json_path.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False))
                    fh.write("\n")
        except Exception as exc:
            warning = "Failed to persist cached rows for %s: %s" % (cache_key, exc)
            self._warnings.append(warning)
            logger.warning(warning)
            return None

        result_csv_path: Optional[Path] = None
        columns = metadata.get("columns")
        if not columns:
            # Derive columns from first row for CSV readability.
            column_set: List[str] = []
            if rows:
                column_set = list(rows[0].keys())
            metadata["columns"] = column_set
        try:
            if rows:
                result_csv_path = key_dir / "rows.csv"
                with result_csv_path.open("w", encoding="utf-8", newline="") as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=metadata["columns"])
                    writer.writeheader()
                    for row in rows:
                        writer.writerow(
                            {col: row.get(col) for col in metadata["columns"]}
                        )
        except Exception as exc:
            warning = "Failed to persist cached CSV for %s: %s" % (cache_key, exc)
            # CSV is optional; keep going but record warning.
            self._warnings.append(warning)
            logger.warning(warning)
            result_csv_path = None

        manifest = {
            "version": 1,
            "cache_key": cache_key,
            "created_at": self._iso_now(),
            "profile": metadata.get("profile"),
            "context": metadata.get("context"),
            "rowcount": metadata.get("rowcount"),
            "duration_ms": metadata.get("duration_ms"),
            "statement_sha256": metadata.get("statement_sha256"),
            "result_json": result_json_path.name,
            "result_csv": result_csv_path.name if result_csv_path else None,
            "columns": metadata.get("columns"),
            "truncated": metadata.get("truncated"),
            "post_query_insight": metadata.get("post_query_insight"),
            "reason": metadata.get("reason"),
            "key_metrics": metadata.get("key_metrics"),
            "insights": metadata.get("insights"),
        }

        manifest_path = key_dir / "manifest.json"
        try:
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            warning = "Failed to write cache manifest for %s: %s" % (cache_key, exc)
            self._warnings.append(warning)
            logger.warning(warning)
            return None

        return manifest_path
