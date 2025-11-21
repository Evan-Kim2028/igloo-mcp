from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from igloo_mcp import report_cli
from igloo_mcp.reporting.manifest import load_manifest


def test_build_arg_parser_has_subcommands() -> None:
    parser = report_cli.build_arg_parser()
    assert isinstance(parser, argparse.ArgumentParser)
    # Ensure the expected subcommands are registered
    subcommands = set()
    for action in parser._actions:  # type: ignore[attr-defined]
        if isinstance(action, argparse._SubParsersAction):  # type: ignore[attr-defined]
            subcommands.update(action.choices.keys())
    assert {"build", "lint", "scaffold"}.issubset(subcommands)


def test_report_cli_scaffold_lint_build_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end CLI workflow: scaffold -> lint -> build using cache artifacts."""

    repo_root = tmp_path

    # Prepare cache manifest + rows backing a single dataset
    cache_dir = repo_root / "cache"
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

    # Minimal history entry that points at the cache manifest
    history_path = repo_root / "history.jsonl"
    history_entry = {
        "execution_id": "exec-1",
        "status": "success",
        "duration_ms": 10,
        "rowcount": len(rows),
        "sql_sha256": "deadbeef",
        "artifacts": {},
        "cache_manifest": str(manifest_json_path),
    }
    history_path.write_text(json.dumps(history_entry) + "\n", encoding="utf-8")

    # Ensure both CLI and builder pick up the same history path
    monkeypatch.setattr(
        "igloo_mcp.report_cli.resolve_history_path",
        lambda: history_path,
        raising=True,
    )
    monkeypatch.setattr(
        "igloo_mcp.reporting.builder.resolve_history_path",
        lambda: history_path,
        raising=True,
    )

    # Provide a simple Jinja template used by the scaffolded manifest
    templates_dir = repo_root / "templates"
    templates_dir.mkdir()
    (templates_dir / "report.md").write_text(
        "Report for {{ manifest.id }} with {{ datasets['dataset_1'].rows | length }} rows",
        encoding="utf-8",
    )

    # 1) Scaffold a manifest from history
    manifest_path = repo_root / "report.yaml"
    scaffold_args = argparse.Namespace(manifest=str(manifest_path), limit=3)
    rc_scaffold = report_cli._command_scaffold(scaffold_args)
    assert rc_scaffold == 0
    assert manifest_path.exists()

    manifest = load_manifest(manifest_path)
    assert len(manifest.datasets) == 1
    ds = manifest.datasets[0]
    assert ds.name == "dataset_1"
    assert ds.source.cache_manifest == str(manifest_json_path)

    # 2) Lint the scaffolded manifest
    lint_args = argparse.Namespace(manifest=str(manifest_path))
    rc_lint = report_cli._command_lint(lint_args)
    assert rc_lint == 0

    # 3) Build the report to a JSON file
    output_path = repo_root / "report.json"
    build_args = argparse.Namespace(
        manifest=str(manifest_path),
        output=str(output_path),
        output_name="default",
        format=None,
        refresh=False,
    )
    rc_build = report_cli._command_build(build_args)
    assert rc_build == 0
    assert output_path.exists()

    body = output_path.read_text(encoding="utf-8")
    assert "report" in body.lower()
    assert "2 rows" in body
