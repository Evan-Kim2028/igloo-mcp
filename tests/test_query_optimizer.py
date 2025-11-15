from __future__ import annotations

import json
from pathlib import Path

from igloo_mcp.query_optimizer import optimize_execution


def test_optimize_execution_reads_history(tmp_path: Path, monkeypatch) -> None:
    sql_file = tmp_path / "query.sql"
    sql_file.write_text("SELECT * FROM CORE.PUBLIC.TRADES", encoding="utf-8")

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "rowcount": 100,
                "duration_ms": 120000,
                "objects": [
                    {"database": "CORE", "schema": "PUBLIC", "name": "TRADES"},
                    {"database": "REF", "schema": "PUBLIC", "name": "DIM"},
                ],
            }
        ),
        encoding="utf-8",
    )

    history_entry = {
        "execution_id": "abc123",
        "status": "success",
        "duration_ms": 120000,
        "rowcount": 100,
        "artifacts": {"sql_path": str(sql_file)},
        "cache_manifest": str(manifest),
    }

    history_path = tmp_path / "history.jsonl"
    history_path.write_text(json.dumps(history_entry) + "\n", encoding="utf-8")

    report = optimize_execution("abc123", history_path=str(history_path))

    assert report["execution_id"] == "abc123"
    assert any(
        finding["message"].startswith("Replace SELECT *")
        for finding in report["findings"]
    )
