"""Additional offline coverage for ExecuteQueryTool caching behaviour."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.service_layer.query_service import QueryService
from tests.helpers.fake_snowflake_connector import (
    FakeQueryPlan,
    FakeSessionDefaults,
    FakeSnowflakeService,
)


@pytest.mark.asyncio
async def test_cache_key_changes_with_session_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing Snowflake session defaults should invalidate cached rows."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        history_path = tmp_path / "logs" / "doc.jsonl"
        artifact_root = tmp_path / "artifacts"
        cache_root = tmp_path / "cache"

        env = {
            "IGLOO_MCP_QUERY_HISTORY": str(history_path),
            "IGLOO_MCP_ARTIFACT_ROOT": str(artifact_root),
            "IGLOO_MCP_CACHE_ROOT": str(cache_root),
        }

        config = Config(snowflake=SnowflakeConfig(profile="profile_one"))
        plan = FakeQueryPlan(
            statement="SELECT 1",
            rows=[{"value": 1}],
            duration=0.01,
            sfqid="CACHE_TEST",
        )

        with patch.dict("os.environ", env, clear=False):
            service = FakeSnowflakeService(
                [plan],
                session_defaults=FakeSessionDefaults(
                    warehouse="WH_A", database="DB_A", schema="PUBLIC", role="TEST_ROLE"
                ),
            )
            tool = ExecuteQueryTool(
                config=config,
                snowflake_service=service,
                query_service=QueryService(context=None),
            )

            first = await tool.execute(statement="SELECT 1", timeout_seconds=120)
            assert first["cache"]["hit"] is False
            first_key = first["cache"]["cache_key"]

            service.session_defaults = FakeSessionDefaults(
                warehouse="WH_B", database="DB_B", schema="PUBLIC", role="TEST_ROLE"
            )

            second = await tool.execute(statement="SELECT 1", timeout_seconds=120)
            assert second["cache"]["hit"] is False  # new context, no cache reuse
            second_key = second["cache"]["cache_key"]

            assert second_key != first_key

            # Two separate history entries should exist with distinct cache keys
            lines = history_path.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == 2
            payloads = [json.loads(line) for line in lines]
            observed_keys = {entry["cache_key"] for entry in payloads}
            assert observed_keys == {first_key, second_key}


@pytest.mark.asyncio
async def test_cache_skipped_when_snapshot_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the session snapshot fails, caching should be bypassed with a warning."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        history_path = tmp_path / "logs" / "doc.jsonl"
        artifact_root = tmp_path / "artifacts"

        env = {
            "IGLOO_MCP_QUERY_HISTORY": str(history_path),
            "IGLOO_MCP_ARTIFACT_ROOT": str(artifact_root),
            "IGLOO_MCP_CACHE_ROOT": str(tmp_path / "cache"),
        }

        config = Config(snowflake=SnowflakeConfig(profile="profile_two"))
        plan = FakeQueryPlan(statement="SELECT 2", rows=[{"value": 2}], duration=0.01)

        with patch.dict("os.environ", env, clear=False):
            service = FakeSnowflakeService([plan])
            tool = ExecuteQueryTool(
                config=config,
                snowflake_service=service,
                query_service=QueryService(context=None),
            )

            def fake_resolve(self, overrides):
                self._transient_audit_warnings.append(
                    "Snapshot failure injected for test"
                )
                return overrides, False

            with patch.object(ExecuteQueryTool, "_resolve_cache_context", fake_resolve):
                result = await tool.execute(statement="SELECT 2", timeout_seconds=30)

            assert result["cache"]["hit"] is False
            assert result["cache"].get("cache_key") is None
            audit_info = result.get("audit_info", {})
            warnings = audit_info.get("warnings", [])
            assert any("Snapshot failure injected" in msg for msg in warnings)
