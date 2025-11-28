"""Tests for FastMCP integration helpers."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from igloo_mcp import mcp_server
from igloo_mcp.config import Config


@pytest.fixture(autouse=True)
def reset_globals():
    original = (
        mcp_server._health_monitor,
        mcp_server._resource_manager,
        mcp_server._catalog_service,
    )
    yield
    (
        mcp_server._health_monitor,
        mcp_server._resource_manager,
        mcp_server._catalog_service,
    ) = original


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


class CapturingServer:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}
        self.resources: dict[str, Any] = {}

    def tool(self, *, name: str, description: str):  # noqa: D401
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator

    def resource(self, uri: str, **_: Any):  # noqa: D401
        def decorator(func):
            self.resources[uri] = func
            return func

        return decorator


def _register_with_stub_execute(
    monkeypatch: pytest.MonkeyPatch,
    *,
    execute_side_effect: Exception | dict[str, Any] | None = None,
):
    """Register igloo_mcp tools with stubbed execute functionality.

    Note: CLI bridge functionality was removed in v0.3.x.
    """
    server = CapturingServer()
    service = StubService()
    config = Config.from_env()
    original_create = mcp_server.create_service_context
    context = original_create(existing_config=config)

    monkeypatch.setattr("igloo_mcp.mcp_server.get_config", lambda: config)
    monkeypatch.setattr(
        "igloo_mcp.mcp_server.create_service_context",
        lambda *, existing_config=None: context,
    )

    execute_mock = AsyncMock()
    if isinstance(execute_side_effect, Exception):
        execute_mock.side_effect = execute_side_effect
    elif execute_side_effect is None:
        execute_mock.return_value = {"rows": []}
    else:
        execute_mock.return_value = execute_side_effect

    execute_stub = SimpleNamespace(execute=execute_mock)
    monkeypatch.setattr(
        "igloo_mcp.mcp_server.ExecuteQueryTool",
        lambda *args, **kwargs: execute_stub,
    )

    dummy_tool = SimpleNamespace(execute=lambda *_, **__: None)
    for attr in (
        "BuildCatalogTool",
        "BuildDependencyGraphTool",
        "ConnectionTestTool",
        "HealthCheckTool",
        "GetCatalogSummaryTool",
        "SearchCatalogTool",
        "EvolveReportTool",
    ):
        monkeypatch.setattr(
            f"igloo_mcp.mcp_server.{attr}",
            lambda *args, **kwargs: dummy_tool,
        )

    mcp_server.register_igloo_mcp(
        server,
        service,
    )
    return server, execute_mock, context


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


def test_get_catalog_summary_sync_success(tmp_path: Path):
    summary_file = tmp_path / "catalog_summary.json"
    summary_file.write_text('{"totals": {"tables": 1}}', encoding="utf-8")

    class StubCatalog:
        def __init__(self) -> None:
            self.called = False

        def load_summary(self, catalog_dir: str):
            self.called = True
            assert catalog_dir == str(tmp_path)
            return {"totals": {"tables": 1}}

    original = mcp_server._catalog_service
    try:
        stub = StubCatalog()
        mcp_server._catalog_service = stub  # type: ignore[assignment]
        result = mcp_server._get_catalog_summary_sync(str(tmp_path))
        assert result["totals"]["tables"] == 1
        assert stub.called is True
    finally:
        mcp_server._catalog_service = original


def test_register_igloo_mcp_registers_once():
    """Test that register_igloo_mcp doesn't duplicate tool registrations."""

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

    mcp_server.register_igloo_mcp(server, service)
    assert server.names  # ensure tools registered
    assert server.resources  # ensure resource registered

    # Second call should not duplicate registrations
    mcp_server.register_igloo_mcp(server, service)
    assert server.names == list(dict.fromkeys(server.names))


def test_register_igloo_mcp_sets_up_context(monkeypatch):
    """Test that register_igloo_mcp properly sets up service context.

    Note: CLI bridge functionality was removed in v0.3.x.
    """

    class DummyServer:
        def __init__(self) -> None:
            self.tools = {}
            self.resources = {}

        def tool(self, *, name: str, description: str):
            def decorator(func):
                self.tools[name] = func
                return func

            return decorator

        def resource(self, uri: str, **_: Any):
            def decorator(func):
                self.resources[uri] = func
                return func

            return decorator

    server = DummyServer()
    service = StubService()

    ctx = MagicMock()
    ctx.health_monitor = MagicMock()
    ctx.resource_manager = MagicMock()

    def fake_create_service_context(*, existing_config=None):
        return ctx

    monkeypatch.setattr(
        "igloo_mcp.mcp_server.create_service_context", fake_create_service_context
    )

    mcp_server.register_igloo_mcp(server, service)
    assert mcp_server._health_monitor is ctx.health_monitor
    assert mcp_server._resource_manager is ctx.resource_manager


@pytest.mark.asyncio
async def test_execute_query_tool_handles_timeout(monkeypatch: pytest.MonkeyPatch):
    """Test that timeout errors are properly propagated."""
    server, _, _ = _register_with_stub_execute(
        monkeypatch,
        execute_side_effect=TimeoutError("timed out"),
    )
    tool = server.tools["execute_query"]

    with pytest.raises(TimeoutError) as exc_info:
        await tool("SELECT 1", timeout_seconds=12, reason="test timeout")

    assert "timed out" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_query_tool_handles_value_errors(monkeypatch: pytest.MonkeyPatch):
    """Test that validation errors are properly propagated for non-numeric timeout strings."""
    from igloo_mcp.mcp.exceptions import MCPValidationError

    server, _, _ = _register_with_stub_execute(
        monkeypatch,
        execute_side_effect=ValueError(
            "timeout_seconds must be an integer value in seconds."
        ),
    )
    tool = server.tools["execute_query"]

    with pytest.raises(MCPValidationError) as exc_info:
        await tool("SELECT 1", timeout_seconds="invalid", reason="test param error")

    assert "timeout_seconds" in str(exc_info.value)
    assert "invalid" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_query_tool_accepts_string_timeout(
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that numeric string timeouts are accepted and coerced to int (#48)."""
    server, execute_mock, _ = _register_with_stub_execute(monkeypatch)
    tool = server.tools["execute_query"]

    await tool("SELECT 1", timeout_seconds="45", reason="string timeout")

    # String should be coerced to int
    assert execute_mock.await_args.kwargs["timeout_seconds"] == 45


@pytest.mark.asyncio
async def test_execute_query_tool_handles_runtime_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that runtime errors are properly propagated."""
    server, _, _ = _register_with_stub_execute(
        monkeypatch,
        execute_side_effect=RuntimeError("bad failure"),
    )
    tool = server.tools["execute_query"]

    with pytest.raises(RuntimeError) as exc_info:
        await tool("SELECT 1", reason="test compact error")

    assert "bad failure" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_query_tool_verbose_errors(monkeypatch: pytest.MonkeyPatch):
    """Test that verbose errors include full details."""
    server, _, _ = _register_with_stub_execute(
        monkeypatch,
        execute_side_effect=RuntimeError("detailed failure"),
    )
    tool = server.tools["execute_query"]

    with pytest.raises(RuntimeError) as exc_info:
        await tool(
            "SELECT 1", verbose_errors=True, reason="test verbose error"
        )  # noqa: FBT003

    assert "detailed failure" in str(exc_info.value)


def test_apply_config_overrides_sets_env(monkeypatch: pytest.MonkeyPatch):
    args = SimpleNamespace(
        snowcli_config=None,
        profile="TEST_PROFILE",
        warehouse=None,
        database=None,
        schema=None,
        role=None,
    )

    config = Config.from_env()

    def fake_load_config(config_path=None, cli_overrides=None):
        assert cli_overrides == {"profile": "TEST_PROFILE"}
        return config

    monkeypatch.setattr("igloo_mcp.mcp_server.load_config", fake_load_config)
    cfg = mcp_server._apply_config_overrides(args)
    assert cfg is config
    assert os.environ["SNOWFLAKE_PROFILE"] == config.snowflake.profile


def test_apply_config_overrides_raises_on_failure(monkeypatch: pytest.MonkeyPatch):
    args = SimpleNamespace(
        snowcli_config=None,
        profile=None,
        warehouse=None,
        database=None,
        schema=None,
        role=None,
    )

    def fake_load_config(config_path=None, cli_overrides=None):  # noqa: ARG001
        raise mcp_server.ConfigError("boom")

    monkeypatch.setattr("igloo_mcp.mcp_server.load_config", fake_load_config)

    with pytest.raises(SystemExit) as exc_info:
        mcp_server._apply_config_overrides(args)

    assert "Failed to load configuration" in str(exc_info.value)
