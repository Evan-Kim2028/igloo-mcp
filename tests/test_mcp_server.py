"""Tests for FastMCP integration helpers."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, List
from unittest.mock import MagicMock, patch

from igloo_mcp import mcp_server


class StubService:
    def __init__(self, cursor: MagicMock | None = None) -> None:
        self.cursor = cursor

    def get_query_tag_param(self) -> None:
        return None

    def get_connection(self, **_: Any):  # type: ignore[override]
        cursor = self.cursor or MagicMock()

        class _ConnCtx:
            def __enter__(self):
                return None, cursor

            def __exit__(self, exc_type, exc, tb):
                return False

        return _ConnCtx()


def test_execute_query_sync_applies_overrides():
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"COUNT": 1}]
    cursor.fetchone.side_effect = [
        {
            "ROLE": "DEFAULT_ROLE",
            "WAREHOUSE": "DEFAULT_WH",
            "DATABASE": "DEFAULT_DB",
            "SCHEMA": "DEFAULT_SCHEMA",
        }
    ]
    cursor.rowcount = 1

    service = StubService(cursor)

    original_state = {
        "role": "DEFAULT_ROLE",
        "warehouse": "DEFAULT_WH",
        "database": "DEFAULT_DB",
        "schema": "DEFAULT_SCHEMA",
    }

    with (
        patch(
            "igloo_mcp.mcp_server.ensure_session_lock",
            return_value=threading.Lock(),
        ),
        patch(
            "igloo_mcp.mcp_server.snapshot_session", return_value=original_state
        ) as snapshot,
        patch("igloo_mcp.mcp_server.apply_session_context") as apply_ctx,
        patch("igloo_mcp.mcp_server.restore_session_context") as restore_ctx,
    ):
        result = mcp_server._execute_query_sync(
            service,
            "SELECT COUNT(*) FROM FOO",
            {
                "role": "SYSADMIN",
                "warehouse": "COMPUTE_WH",
                "database": "TEST_DB",
                "schema": "PUBLIC",
            },
        )

    assert result["rowcount"] == 1
    assert result["rows"] == [{"COUNT": 1}]
    cursor.execute.assert_any_call("SELECT COUNT(*) FROM FOO")
    apply_ctx.assert_called_once_with(
        cursor,
        {
            "role": "SYSADMIN",
            "warehouse": "COMPUTE_WH",
            "database": "TEST_DB",
            "schema": "PUBLIC",
        },
    )
    restore_ctx.assert_called_once_with(cursor, original_state)
    snapshot.assert_called_once_with(cursor)


# Lineage functionality removed - test removed


def test_get_catalog_summary_sync_missing(tmp_path: Path):
    # Should raise FileNotFoundError instead of returning error object
    import pytest

    with pytest.raises(FileNotFoundError) as exc_info:
        mcp_server._get_catalog_summary_sync(str(tmp_path))

    assert "Catalog summary not found" in str(exc_info.value)
    assert str(tmp_path) in str(exc_info.value)


def test_register_igloo_mcp_registers_once():
    class DummyServer:
        def __init__(self) -> None:
            self.names: List[str] = []
            self.resources: List[str] = []

        def tool(self, *, name: str, description: str):  # noqa: ARG002, unused-argument
            def decorator(func):  # pragma: no cover - executed by registration
                self.names.append(name)
                return func

            return decorator

        def resource(self, uri: str, **_: Any):  # noqa: ARG002
            def decorator(func):  # pragma: no cover - executed by registration
                self.resources.append(uri)
                return func

            return decorator

    server = DummyServer()
    service = StubService()

    with patch("igloo_mcp.mcp_server.SnowCLI"):
        mcp_server.register_igloo_mcp(server, service)
        assert server.names  # ensure tools registered
        assert server.resources  # ensure resource registered

    # Second call should not duplicate registrations
    with patch("igloo_mcp.mcp_server.SnowCLI"):
        mcp_server.register_igloo_mcp(server, service)
    assert server.names == list(dict.fromkeys(server.names))
