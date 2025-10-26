import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _write_history_line(path: Path, payload: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        json.dump(payload, fh)
        fh.write("\n")


def _artifact_path(root: Path, sha: str) -> Path:
    target = root / "queries" / "by_sha" / f"{sha}.sql"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def test_export_bundle_by_query_id(tmp_path):
    doc_path = tmp_path / "doc.jsonl"
    artifact_root = tmp_path / "artifacts"

    statement = "SELECT 1"
    sha = hashlib.sha256(statement.encode("utf-8")).hexdigest()
    _artifact_path(artifact_root, sha).write_text(statement, encoding="utf-8")

    record = {
        "ts": 1_700_000_000.0,
        "status": "success",
        "profile": "test",
        "statement_preview": statement,
        "timeout_seconds": 30,
        "query_id": "Q1",
        "rowcount": 1,
        "duration_ms": 50,
        "reason": "report section",
        "sql_sha256": sha,
        "artifacts": {"sql_path": str(_artifact_path(artifact_root, sha))},
    }
    _write_history_line(doc_path, record)

    output_path = tmp_path / "bundle.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_report_bundle.py",
            "--doc",
            str(doc_path),
            "--artifact-root",
            str(artifact_root),
            "--query-id",
            "Q1",
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    assert result.returncode == 0, result.stderr

    bundle = json.loads(output_path.read_text(encoding="utf-8"))
    entries = bundle["entries"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["sql_sha256"] == sha
    assert entry["sql_text"].strip() == statement
    assert entry["mcp_uri"].endswith(f"{sha}.sql")
    assert entry["query_id"] == "Q1"


def test_export_bundle_latest_per_sql(tmp_path):
    doc_path = tmp_path / "doc.jsonl"
    artifact_root = tmp_path / "artifacts"

    statement = "SELECT 2"
    sha = hashlib.sha256(statement.encode("utf-8")).hexdigest()
    _artifact_path(artifact_root, sha).write_text(statement, encoding="utf-8")

    older = {
        "ts": 1_700_000_000.0,
        "status": "success",
        "profile": "test",
        "statement_preview": statement,
        "timeout_seconds": 30,
        "reason": "flashcrash",
        "sql_sha256": sha,
        "artifacts": {},
    }
    newer = {
        "ts": 1_800_000_000.0,
        "status": "success",
        "profile": "test",
        "statement_preview": statement,
        "timeout_seconds": 30,
        "reason": "flashcrash",
        "sql_sha256": sha,
        "artifacts": {},
    }
    _write_history_line(doc_path, older)
    _write_history_line(doc_path, newer)

    output_path = tmp_path / "bundle_latest.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_report_bundle.py",
            "--doc",
            str(doc_path),
            "--artifact-root",
            str(artifact_root),
            "--reason-contains",
            "flash",
            "--latest-per-sql",
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    assert result.returncode == 0, result.stderr

    bundle = json.loads(output_path.read_text(encoding="utf-8"))
    entries = bundle["entries"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["sql_sha256"] == sha
    assert entry["ts"] == newer["ts"]
