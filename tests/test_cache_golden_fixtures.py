"""Validate cache/history golden fixtures using FakeSnowflake outputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from tests.helpers.cache_fixture_builder import (
    generate_cache_fixture,
    load_jsonl,
)

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "cache_scenarios"
BASELINE_DIR = FIXTURE_ROOT / "baseline"


def _compare_json(expected_path: Path, actual_path: Path) -> None:
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    actual = json.loads(actual_path.read_text(encoding="utf-8"))
    assert actual == expected


def _compare_jsonl(expected_path: Path, actual_path: Path) -> None:
    expected_records = load_jsonl(expected_path)
    actual_records = load_jsonl(actual_path)
    assert len(actual_records) == len(expected_records)
    allowed_extra = {
        "columns",
        "key_metrics",
        "insights",
        "objects",
        "source_databases",
        "tables",
        "response_mode_requested",  # Added in v0.3.5 for telemetry
    }
    for expected, actual in zip(expected_records, actual_records, strict=False):
        extra_keys = set(actual) - set(expected)
        assert extra_keys <= allowed_extra
        filtered_actual = {key: actual[key] for key in expected}
        assert filtered_actual == expected


def _compare_csv(expected_path: Path, actual_path: Path) -> None:
    with (
        expected_path.open("r", encoding="utf-8") as exp,
        actual_path.open("r", encoding="utf-8") as act,
    ):
        expected_rows = list(csv.reader(exp))
        actual_rows = list(csv.reader(act))
        assert actual_rows == expected_rows


def test_cache_history_golden_fixture(tmp_path):
    assert BASELINE_DIR.exists(), "Golden fixtures are missing from the repository baseline"

    generated = generate_cache_fixture(tmp_path)

    expected_history = BASELINE_DIR / "history" / "doc.jsonl"
    _compare_jsonl(expected_history, generated["history"])

    expected_manifest = next(BASELINE_DIR.glob("artifacts/cache/*/manifest.json"), None)
    assert expected_manifest is not None, "Cache artifact baseline is missing from the repository baseline"
    _compare_json(expected_manifest, generated["manifest"])

    expected_rows_jsonl = expected_manifest.parent / "rows.jsonl"
    _compare_jsonl(expected_rows_jsonl, generated["rows_jsonl"])

    expected_rows_csv = expected_manifest.parent / "rows.csv"
    _compare_csv(expected_rows_csv, generated["rows_csv"])

    expected_sql = next(BASELINE_DIR.glob("artifacts/queries/by_sha/*.sql"), None)
    assert expected_sql is not None, "Query artifact baseline is missing from the repository baseline"
    assert generated["sql"].read_text(encoding="utf-8") == expected_sql.read_text(encoding="utf-8")
