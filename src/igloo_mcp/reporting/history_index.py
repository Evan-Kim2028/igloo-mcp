from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..path_utils import find_repo_root
from .manifest import DatasetRef, DatasetSource


def _load_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    """Yield JSON objects from a JSONL file.

    This mirrors the lightweight implementation used in scripts/export_report_bundle.py
    but lives in the library for reuse by reporting utilities.
    """

    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload


@dataclass
class ResolvedDataset:
    """Concrete dataset resolved from history/cache artifacts."""

    name: str
    rows: List[Dict[str, Any]]
    columns: List[str]
    key_metrics: Optional[Dict[str, Any]]
    insights: List[Any]
    provenance: Dict[str, Any]


class DatasetResolutionError(RuntimeError):
    """Raised when a manifest dataset cannot be bound to artifacts."""


class HistoryIndex:
    """Index over query history used for report dataset resolution.

    The index is intentionally simple: it keeps the raw history records plus
    lookups by execution_id and sql_sha256. Cache manifests are resolved lazily
    when datasets are bound.
    """

    def __init__(self, history_path: Path) -> None:
        self.history_path = history_path
        self._records: List[Dict[str, Any]] = list(_load_jsonl(history_path))
        self._by_execution_id: Dict[str, Dict[str, Any]] = {}
        self._by_sql_sha: Dict[str, Dict[str, Any]] = {}
        for record in self._records:
            exec_id = record.get("execution_id")
            if isinstance(exec_id, str) and exec_id not in self._by_execution_id:
                self._by_execution_id[exec_id] = record
            sha = record.get("sql_sha256")
            if isinstance(sha, str) and sha not in self._by_sql_sha:
                self._by_sql_sha[sha] = record

    @property
    def records(self) -> List[Dict[str, Any]]:
        return list(self._records)

    def _resolve_history_record(
        self, source: DatasetSource
    ) -> Optional[Dict[str, Any]]:
        if source.execution_id and source.execution_id in self._by_execution_id:
            return self._by_execution_id[source.execution_id]
        if source.sql_sha256 and source.sql_sha256 in self._by_sql_sha:
            return self._by_sql_sha[source.sql_sha256]
        return None

    @staticmethod
    def _resolve_manifest_path(cache_manifest: str, repo_root: Optional[Path]) -> Path:
        candidate = Path(cache_manifest).expanduser()
        if candidate.is_absolute():
            return candidate
        base = repo_root or find_repo_root()
        return (base / candidate).resolve()

    @staticmethod
    def _load_cache_manifest(
        manifest_path: Path,
    ) -> Tuple[Dict[str, Any], Path, Optional[Path]]:
        if not manifest_path.exists():
            raise DatasetResolutionError(f"Cache manifest not found: {manifest_path}")
        raw = manifest_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise DatasetResolutionError(
                f"Expected mapping in cache manifest {manifest_path}, got {type(data)!r}"
            )
        result_json = data.get("result_json")
        if not result_json:
            raise DatasetResolutionError(
                f"Cache manifest missing result_json field: {manifest_path}"
            )
        rows_path = manifest_path.parent / result_json
        if not rows_path.exists():
            raise DatasetResolutionError(
                f"Cache rows file declared in manifest not found: {rows_path}"
            )
        result_csv_rel = data.get("result_csv")
        result_csv_path: Optional[Path] = None
        if isinstance(result_csv_rel, str) and result_csv_rel:
            candidate = manifest_path.parent / result_csv_rel
            if candidate.exists():
                result_csv_path = candidate
        return data, rows_path, result_csv_path

    @staticmethod
    def _load_rows(rows_path: Path) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for entry in _load_jsonl(rows_path):
            rows.append(entry)
        return rows

    def resolve_dataset(
        self, dataset: DatasetRef, *, repo_root: Optional[Path] = None
    ) -> ResolvedDataset:
        """Resolve a single dataset reference into concrete rows + metadata.

        Resolution precedence:
        1. DatasetSource.cache_manifest if provided.
        2. History record's artifacts.cache_manifest.
        3. History record's cache_manifest field.
        """

        source = dataset.source
        repo_root = repo_root or find_repo_root()

        manifest_path: Optional[Path] = None
        history_record: Optional[Dict[str, Any]] = None

        if source.cache_manifest:
            manifest_path = self._resolve_manifest_path(
                source.cache_manifest, repo_root
            )
        else:
            history_record = self._resolve_history_record(source)
            if history_record is None:
                raise DatasetResolutionError(
                    f"No history entry found for dataset {dataset.name!r}"
                )
            artifacts = history_record.get("artifacts") or {}
            cache_manifest = artifacts.get("cache_manifest") or history_record.get(
                "cache_manifest"
            )
            if not cache_manifest:
                raise DatasetResolutionError(
                    f"History entry for dataset {dataset.name!r} lacks cache_manifest"
                )
            manifest_path = self._resolve_manifest_path(str(cache_manifest), repo_root)

        assert manifest_path is not None
        manifest_data, rows_path, _ = self._load_cache_manifest(manifest_path)
        rows = self._load_rows(rows_path)

        columns: List[str] = []
        raw_columns = manifest_data.get("columns")
        if isinstance(raw_columns, list):
            columns = [str(col) for col in raw_columns]

        key_metrics = manifest_data.get("key_metrics")
        if key_metrics is not None and not isinstance(key_metrics, dict):
            key_metrics = None
        insights_raw = manifest_data.get("insights") or []
        insights: List[Any] = (
            list(insights_raw) if isinstance(insights_raw, list) else []
        )

        provenance: Dict[str, Any] = {
            "dataset": dataset.name,
            "cache_manifest_path": str(manifest_path),
            "rows_path": str(rows_path),
            "created_at": manifest_data.get("created_at"),
            "rowcount": manifest_data.get("rowcount"),
            "duration_ms": manifest_data.get("duration_ms"),
            "statement_sha256": manifest_data.get("statement_sha256"),
        }

        if history_record is None:
            history_record = self._resolve_history_record(source)
        if history_record is not None:
            provenance.setdefault("execution_id", history_record.get("execution_id"))
            provenance.setdefault("sql_sha256", history_record.get("sql_sha256"))
            provenance.setdefault("status", history_record.get("status"))
            if "ts" in history_record:
                provenance.setdefault("ts", history_record.get("ts"))

        return ResolvedDataset(
            name=dataset.name,
            rows=rows,
            columns=columns,
            key_metrics=key_metrics,
            insights=insights,
            provenance=provenance,
        )


__all__ = ["HistoryIndex", "ResolvedDataset", "DatasetResolutionError"]
