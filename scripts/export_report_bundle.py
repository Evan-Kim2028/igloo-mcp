#!/usr/bin/env python3
"""Export a self-contained bundle of SQL executions from doc.jsonl."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from igloo_mcp.path_utils import (
    find_repo_root,
    resolve_artifact_root,
    resolve_history_path,
)


@dataclass
class SelectionCriteria:
    query_ids: list[str] | None = None
    reason_contains: str | None = None
    since: str | None = None
    until: str | None = None
    latest_per_sql: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.query_ids is not None:
            payload["query_ids"] = self.query_ids
        if self.reason_contains is not None:
            payload["reason_contains"] = self.reason_contains
        if self.since is not None:
            payload["since"] = self.since
        if self.until is not None:
            payload["until"] = self.until
        payload["latest_per_sql"] = self.latest_per_sql
        return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--doc",
        help="Path to doc.jsonl history (default: repo_local logs/doc.jsonl)",
        default=None,
    )
    parser.add_argument(
        "--artifact-root",
        help="Root directory for artifacts (default: repo_local logs/artifacts)",
        default=None,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--query-id",
        action="append",
        dest="query_ids",
        help="Specific query_id to include (repeatable)",
    )
    group.add_argument(
        "--reason-contains",
        help="Substring match (case-insensitive) on reason field",
    )
    parser.add_argument(
        "--since",
        help="ISO 8601 timestamp lower bound (inclusive) for ts field",
    )
    parser.add_argument(
        "--until",
        help="ISO 8601 timestamp upper bound (inclusive) for ts field",
    )
    parser.add_argument(
        "--latest-per-sql",
        action="store_true",
        help="Keep only the most recent entry per sql_sha256",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Bundle output path (JSON)",
    )
    return parser.parse_args()


def _resolve_doc_path(raw: str | None) -> Path:
    if raw is None:
        return resolve_history_path()
    return resolve_history_path(raw=raw)


def _resolve_artifact_root(raw: str | None) -> Path:
    if raw is None:
        return resolve_artifact_root()
    return resolve_artifact_root(raw=raw)


def _load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
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


def _ts_from_iso8601(raw: str | None) -> float | None:
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw).timestamp()
    except ValueError:
        raise ValueError(f"Invalid ISO 8601 timestamp: {raw}")


def _select_entries(
    records: Iterable[dict[str, Any]],
    criteria: SelectionCriteria,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    since_ts = _ts_from_iso8601(criteria.since)
    until_ts = _ts_from_iso8601(criteria.until)
    for record in records:
        query_id = record.get("query_id")
        reason = record.get("reason", "") or ""
        ts = record.get("ts")
        if criteria.query_ids is not None:
            if query_id not in criteria.query_ids:
                continue
        else:
            if criteria.reason_contains is not None:
                if criteria.reason_contains.lower() not in reason.lower():
                    continue
            else:
                continue
        if since_ts is not None and ts is not None and ts < since_ts:
            continue
        if until_ts is not None and ts is not None and ts > until_ts:
            continue
        selected.append(record)
    if criteria.latest_per_sql:
        latest: dict[str, dict[str, Any]] = {}
        for record in selected:
            sha = record.get("sql_sha256")
            if not sha:
                continue
            current = latest.get(sha)
            if current is None or (record.get("ts") or 0) >= (current.get("ts") or 0):
                latest[sha] = record
        return list(latest.values())
    return selected


def _read_sql_text(artifact_root: Path, sha: str, artifacts: dict[str, Any]) -> str | None:
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError(f"Invalid sql_sha256 '{sha}'")
    if artifacts:
        sql_path = artifacts.get("sql_path")
        if sql_path:
            candidate = Path(sql_path)
            if not candidate.is_absolute():
                repo_root = find_repo_root()
                candidate = (repo_root / sql_path).resolve()
            if candidate.exists() and candidate.is_file():
                return candidate.read_text(encoding="utf-8")
    candidate = (artifact_root / "queries" / "by_sha" / f"{sha}.sql").resolve()
    if candidate.exists() and candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return None


def main() -> int:
    args = parse_args()

    try:
        doc_path = _resolve_doc_path(args.doc)
        artifact_root = _resolve_artifact_root(args.artifact_root)
    except Exception as exc:
        print(f"Failed to resolve paths: {exc}", file=sys.stderr)
        return 1

    if not doc_path.exists():
        print(f"History file not found: {doc_path}", file=sys.stderr)
        return 1

    criteria = SelectionCriteria(
        query_ids=args.query_ids,
        reason_contains=args.reason_contains,
        since=args.since,
        until=args.until,
    )
    criteria.latest_per_sql = args.latest_per_sql

    records = list(_load_jsonl(doc_path))
    selected = _select_entries(records, criteria)

    if not selected:
        print("No matching entries found", file=sys.stderr)
        return 1

    failures: dict[str, str] = {}
    entries: list[dict[str, Any]] = []

    for record in selected:
        sha = record.get("sql_sha256")
        if not sha:
            continue
        artifacts = record.get("artifacts") or {}
        sql_text = _read_sql_text(artifact_root, sha, artifacts)
        if sql_text is None:
            failures[sha] = "SQL artifact not found"
            continue
        entry: dict[str, Any] = {
            "sql_sha256": sha,
            "mcp_uri": f"igloo://queries/by-sha/{sha}.sql",
            "sql_text": sql_text,
            "status": record.get("status"),
            "ts": record.get("ts"),
            "timeout_seconds": record.get("timeout_seconds"),
        }
        if record.get("query_id"):
            entry["query_id"] = record["query_id"]
        if record.get("reason"):
            entry["reason"] = record["reason"]
        if record.get("rowcount") is not None:
            entry["rowcount"] = record.get("rowcount")
        if record.get("duration_ms") is not None:
            entry["duration_ms"] = record.get("duration_ms")
        if record.get("overrides"):
            entry["overrides"] = record.get("overrides")
        entries.append(entry)

    if failures:
        for sha, msg in failures.items():
            print(f"Missing SQL for {sha}: {msg}", file=sys.stderr)
        return 1

    output_path = Path(args.output).expanduser()
    if not output_path.is_absolute():
        output_path = (find_repo_root() / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    bundle = {
        "bundle_metadata": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "doc_path": str(doc_path),
            "artifact_root": str(artifact_root),
            "selection": criteria.to_dict(),
        },
        "entries": entries,
    }

    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(bundle, fh, indent=2)
        fh.write("\n")

    print(f"Wrote bundle with {len(entries)} entries to {output_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main())
