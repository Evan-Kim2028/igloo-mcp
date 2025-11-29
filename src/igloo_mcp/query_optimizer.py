"""Offline query optimization helper consuming cached manifest + history data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .path_utils import find_repo_root, resolve_history_path


@dataclass
class OptimizationFinding:
    level: str
    message: str
    detail: Optional[str] = None


def _read_history_entries(history_path: Path) -> List[Dict[str, Any]]:
    if not history_path.exists():
        raise FileNotFoundError(f"history file not found: {history_path}")
    entries: List[Dict[str, Any]] = []
    with history_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    return entries


def _select_entry(entries: List[Dict[str, Any]], execution_id: Optional[str]) -> Dict[str, Any]:
    if execution_id:
        for entry in reversed(entries):
            if str(entry.get("execution_id")) == execution_id:
                return entry
        raise ValueError(f"execution_id {execution_id} not found in history")

    # Default to latest successful or cache_hit entry
    for entry in reversed(entries):
        if entry.get("status") in {"success", "cache_hit"}:
            return entry
    if entries:
        return entries[-1]
    raise ValueError("history file is empty")


def _load_manifest(entry: Dict[str, Any]) -> Dict[str, Any]:
    manifest_path = entry.get("cache_manifest")
    artifacts = entry.get("artifacts") or {}
    manifest_path = manifest_path or artifacts.get("cache_manifest")
    if not manifest_path:
        return {}
    path = Path(manifest_path)
    if not path.is_absolute():
        repo_root = find_repo_root()
        path = (repo_root / path).resolve()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_sql_text(entry: Dict[str, Any]) -> Optional[str]:
    artifacts = entry.get("artifacts") or {}
    sql_path = artifacts.get("sql_path")
    if not sql_path:
        return None
    path = Path(sql_path)
    if not path.is_absolute():
        repo_root = find_repo_root()
        path = (repo_root / path).resolve()
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _detect_findings(
    sql: Optional[str],
    manifest: Dict[str, Any],
    entry: Dict[str, Any],
) -> List[OptimizationFinding]:
    findings: List[OptimizationFinding] = []
    duration = entry.get("duration_ms") or manifest.get("duration_ms") or 0
    rowcount = entry.get("rowcount") or manifest.get("rowcount") or 0
    objects = manifest.get("objects") or []

    if sql and "select *" in sql.lower():
        findings.append(
            OptimizationFinding(
                level="info",
                message="Replace SELECT * with explicit column list",
                detail="Selecting all columns prevents pruning and increases scan time.",
            )
        )

    if duration and duration > 60_000 and rowcount and rowcount < 5_000:
        findings.append(
            OptimizationFinding(
                level="warn",
                message="Query scanned a lot of data for few rows",
                detail="Add WHERE clauses or leverage clustering/filters to reduce scans.",
            )
        )

    if len(objects) > 3:
        names = [o.get("name") for o in objects if isinstance(o, dict)]
        findings.append(
            OptimizationFinding(
                level="info",
                message="Query joins many objects",
                detail=f"Referenced objects: {', '.join(filter(None, names))}",
            )
        )

    if entry.get("status") == "timeout":
        findings.append(
            OptimizationFinding(
                level="error",
                message="Query timed out",
                detail=(
                    "Consider filtering by clustering keys or adding WHERE clauses to reduce data scanned "
                    "before increasing timeout_seconds. Alternatively, run asynchronously or sample with LIMIT."
                ),
            )
        )

    if not findings:
        findings.append(
            OptimizationFinding(
                level="info",
                message="No obvious issues detected",
                detail=(
                    "Query metadata looks healthy. Review warehouse size or predicate selectivity if latency persists."
                ),
            )
        )

    return findings


def optimize_execution(
    execution_id: Optional[str] = None,
    *,
    history_path: Optional[str] = None,
) -> Dict[str, Any]:
    path = Path(history_path).expanduser() if history_path else resolve_history_path()
    entries = _read_history_entries(path)
    entry = _select_entry(entries, execution_id)
    manifest = _load_manifest(entry)
    sql = _load_sql_text(entry)
    findings = _detect_findings(sql, manifest, entry)
    return {
        "execution_id": entry.get("execution_id"),
        "status": entry.get("status"),
        "duration_ms": entry.get("duration_ms") or manifest.get("duration_ms"),
        "rowcount": entry.get("rowcount") or manifest.get("rowcount"),
        "objects": manifest.get("objects"),
        "sql_path": (entry.get("artifacts") or {}).get("sql_path"),
        "findings": [finding.__dict__ for finding in findings],
    }
