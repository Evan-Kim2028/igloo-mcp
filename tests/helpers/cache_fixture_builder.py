"""Utility to generate deterministic cache history fixtures using FakeSnowflake."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch


from igloo_mcp.cache.query_result_cache import QueryResultCache
from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.service_layer.query_service import QueryService
from tests.helpers.fake_snowflake_connector import (
    FakeQueryPlan,
    FakeSessionDefaults,
    FakeSnowflakeService,
)


class _TimeSequence:
    """Iterator-friendly helper to supply deterministic timestamps."""

    def __init__(self, values: List[float]) -> None:
        self._values = iter(values)
        self._last = values[-1] if values else 0.0

    def __call__(self) -> float:
        try:
            self._last = next(self._values)
        except StopIteration:
            self._last += 0.5
        return self._last


@contextmanager
def _patched_time(values: List[float]):
    seq = _TimeSequence(values)

    def fake_sleep(_seconds: float) -> None:
        # No-op; time progression is controlled by the sequence.
        return None

    with (
        patch("time.time", side_effect=seq),
        patch("time.sleep", side_effect=fake_sleep),
    ):
        yield


def generate_cache_fixture(output_dir: Path) -> Dict[str, Path]:
    """Produce deterministic cache/history artifacts for testing.

    Args:
        output_dir: Directory where artifacts will be written.

    Returns:
        Mapping with key file paths (history, manifest, rows, sql, csv).
    """

    output_dir = output_dir.resolve()
    history_path = output_dir / "history" / "doc.jsonl"
    artifact_root = output_dir / "artifacts"
    cache_root = artifact_root / "cache"

    if history_path.exists():
        history_path.unlink()
    if artifact_root.exists():
        shutil.rmtree(artifact_root)

    history_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)

    env = {
        "IGLOO_MCP_QUERY_HISTORY": str(history_path),
        "IGLOO_MCP_ARTIFACT_ROOT": str(artifact_root),
        "IGLOO_MCP_CACHE_ROOT": str(cache_root),
        "IGLOO_MCP_CACHE_MODE": "enabled",
        "IGLOO_MCP_CACHE_MAX_ROWS": "5000",
    }

    config = Config(snowflake=SnowflakeConfig(profile="fixture_profile"))
    service = FakeSnowflakeService(
        [
            FakeQueryPlan(
                statement="SELECT month, total_revenue FROM fixture_source",
                rows=[
                    {"MONTH": "2024-01", "TOTAL_REVENUE": 125000.25},
                    {"MONTH": "2024-02", "TOTAL_REVENUE": 132500.75},
                ],
                duration=0.02,
                sfqid="FIXTURE_QID_001",
            )
        ],
        session_defaults=FakeSessionDefaults(
            role="FIXTURE_ROLE",
            warehouse="FIXTURE_WH",
            database="FIXTURE_DB",
            schema="ANALYTICS",
        ),
    )

    async def _run() -> None:
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=service,
            query_service=QueryService(context=None),
            health_monitor=None,
        )

        first = await tool.execute(
            statement="SELECT month, total_revenue FROM fixture_source",
            warehouse="FIXTURE_WH",
            timeout_seconds=120,
            reason="Fixture baseline history",
            response_mode="sync",
            post_query_insight={
                "summary": "Fixture revenue sample",
                "key_metrics": ["jan_revenue:125000.25", "feb_revenue:132500.75"],
                "business_impact": "Used for unit testing",
                "follow_up_needed": False,
            },
        )

        # Second execution should hit the cache immediately.
        second = await tool.execute(
            statement="SELECT month, total_revenue FROM fixture_source",
            warehouse="FIXTURE_WH",
            timeout_seconds=120,
            reason="Fixture baseline history",
            response_mode="sync",
        )

    time_sequence = [
        1700000000.0,  # initial requested_ts
        1700000000.05,  # started
        1700000000.10,  # deadline base
        1700000000.12,  # loop check (below deadline)
        1700000000.18,  # loop check (exceeds deadline -> exit)
        1700000000.22,  # duration calculation
        1700000000.30,  # completed ts for success
        1700000100.0,  # cache-hit requested_ts
    ]

    uuid_values = [
        uuid.UUID("11111111111111111111111111111111"),
        uuid.UUID("22222222222222222222222222222222"),
    ]

    cache_isos = [
        "2024-01-01T00:00:00+00:00",
        "2024-01-01T00:10:00+00:00",
    ]

    with (
        patch.dict(os.environ, env, clear=False),
        _patched_time(time_sequence),
        patch("uuid.uuid4", side_effect=uuid_values),
        patch.object(QueryResultCache, "_iso_now", side_effect=cache_isos),
    ):
        asyncio.run(_run())

    manifest_paths = list(cache_root.rglob("manifest.json"))
    if not manifest_paths:
        raise RuntimeError("Failed to locate cache manifest for fixture generation")
    manifest_path = manifest_paths[0]

    cache_dir = manifest_path.parent
    sql_files = list((artifact_root / "queries" / "by_sha").rglob("*.sql"))
    if not sql_files:
        raise RuntimeError("Failed to locate SQL artifact for fixture generation")

    _normalize_history(history_path, output_dir)

    return {
        "history": history_path,
        "manifest": manifest_path,
        "rows_jsonl": cache_dir / "rows.jsonl",
        "rows_csv": cache_dir / "rows.csv",
        "sql": sql_files[0],
    }


def load_jsonl(path: Path) -> List[Dict[str, object]]:
    records: List[Dict[str, object]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _normalize_history(history_path: Path, base_dir: Path) -> None:
    records = load_jsonl(history_path)
    base_resolved = base_dir.resolve()

    def _normalize_value(value: str) -> str:
        candidate = Path(value)
        try:
            rel = candidate.resolve().relative_to(base_resolved)
            return rel.as_posix()
        except Exception:
            return value

    for record in records:
        if cache_manifest := record.get("cache_manifest"):
            record["cache_manifest"] = _normalize_value(cache_manifest)
        artifacts = record.get("artifacts")
        if isinstance(artifacts, dict):
            for key, value in list(artifacts.items()):
                if isinstance(value, str):
                    artifacts[key] = _normalize_value(value)

    with history_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False))
            fh.write("\n")
