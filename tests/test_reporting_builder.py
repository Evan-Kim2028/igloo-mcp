from __future__ import annotations

import json
from pathlib import Path

import pytest

from igloo_mcp.reporting.builder import build_report, lint_report


def test_lint_report_flags_missing_cache_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Point history to an empty JSONL file to keep the index trivial.
    history_path = tmp_path / "history.jsonl"
    history_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "igloo_mcp.reporting.builder.resolve_history_path",
        lambda: history_path,
        raising=True,
    )

    manifest_path = tmp_path / "report.yaml"
    manifest_path.write_text(
        """
id: "demo-report"
templates:
  main: "templates/report.md"
datasets:
  - name: "unbound"
    source:
      cache_manifest: "nonexistent/manifest.json"
outputs:
  - name: "default"
    format: "json"
    path: "reports/demo.json"
""".lstrip(),
        encoding="utf-8",
    )

    issues = lint_report(manifest_path)
    assert issues, "Expected lint issues for unresolved dataset"
    assert any(
        issue.code == "dataset_resolution_error" and issue.dataset_name == "unbound"
        for issue in issues
    )


def test_build_report_json_with_cache_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Create a minimal cache manifest + rows payload
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    rows_path = cache_dir / "rows.jsonl"
    rows = [{"id": 1, "value": "a"}, {"id": 2, "value": "b"}]
    with rows_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row))
            fh.write("\n")

    manifest_json_path = cache_dir / "manifest.json"
    manifest_json_path.write_text(
        json.dumps(
            {
                "version": 1,
                "cache_key": "demo-key",
                "created_at": "2025-01-01T00:00:00Z",
                "profile": "test-profile",
                "context": {},
                "rowcount": len(rows),
                "duration_ms": 10,
                "statement_sha256": "deadbeef",
                "result_json": rows_path.name,
                "result_csv": None,
                "columns": ["id", "value"],
                "truncated": False,
                "key_metrics": {"total_rows": len(rows)},
                "insights": ["example insight"],
            }
        ),
        encoding="utf-8",
    )

    history_path = tmp_path / "history.jsonl"
    history_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "igloo_mcp.reporting.builder.resolve_history_path",
        lambda: history_path,
        raising=True,
    )

    report_manifest_path = tmp_path / "report.yaml"
    report_manifest_path.write_text(
        f"""
id: "demo-report"
templates:
  main: "templates/report.md"
datasets:
  - name: "cached_dataset"
    source:
      cache_manifest: "{manifest_json_path}"
outputs:
  - name: "default"
    format: "json"
    path: "reports/demo.json"
""".lstrip(),
        encoding="utf-8",
    )

    result = build_report(report_manifest_path, output_name="default")
    assert result["format"] == "json"
    body = result["body"]
    payload = json.loads(body)
    assert "datasets" in payload
    assert "cached_dataset" in payload["datasets"]
    ds = payload["datasets"]["cached_dataset"]
    assert ds["columns"] == ["id", "value"]
    assert ds["key_metrics"]["total_rows"] == len(rows)
    assert len(ds["rows"]) == len(rows)
