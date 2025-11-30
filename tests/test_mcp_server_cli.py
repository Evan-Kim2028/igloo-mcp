"""Additional coverage for mcp_server CLI wiring."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from igloo_mcp.mcp_server import ProfileValidationError


def test_parse_arguments_with_login_params(monkeypatch: pytest.MonkeyPatch):
    login_params = {
        "good": ("--foo", "--bar", "default", "help text"),
        "short": ("--only-help",),
        "no_default": ("--baz", "baz help"),
    }
    monkeypatch.setattr("igloo_mcp.mcp_server.get_login_params", lambda: login_params)
    monkeypatch.setenv("SNOWCLI_MCP_TRANSPORT", "http")
    monkeypatch.setenv("SERVICE_CONFIG_FILE", "/tmp/config.yml")

    args = __import__("igloo_mcp.mcp_server", fromlist=[""]).parse_arguments(["--profile", "DEV", "--foo", "value"])

    assert args.profile == "DEV"
    assert args.transport == "http"
    assert args.foo == "value"
    assert args.baz is None
    assert args.service_config_file == "/tmp/config.yml"


@pytest.mark.anyio
async def test_create_combined_lifespan_handles_health(monkeypatch: pytest.MonkeyPatch, tmp_path):
    module = __import__("igloo_mcp.mcp_server", fromlist=[""])
    args = SimpleNamespace(
        service_config_file=None,
        profile="DEV",
        enable_cli_bridge=False,
    )

    created = {}

    def make_fake_lifespan(_args):
        @asynccontextmanager
        async def cm(_server):
            created["service_config"] = _args.service_config_file
            yield SimpleNamespace(name="snow_service")

        return cm

    class StubMonitor:
        def __init__(self, server_start_time):
            self.errors: list[str] = []

        def get_profile_health(self, profile, force_refresh):
            return SimpleNamespace(
                is_valid=False,
                validation_error="missing warehouse",
                available_profiles=["DEV"],
            )

        def record_error(self, message):
            self.errors.append(message)

        def check_connection_health(self, service):
            raise RuntimeError("connect failed")

    class StubResourceManager:
        def __init__(self, health_monitor):
            pass

    async def run_sync(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("igloo_mcp.mcp_server.create_snowflake_lifespan", make_fake_lifespan)
    monkeypatch.setattr("igloo_mcp.mcp_server.MCPHealthMonitor", StubMonitor)
    monkeypatch.setattr("igloo_mcp.mcp_server.MCPResourceManager", StubResourceManager)
    monkeypatch.setattr(
        "igloo_mcp.mcp_server.get_config",
        lambda: SimpleNamespace(
            snowflake=SimpleNamespace(profile="DEV"),
        ),
    )
    monkeypatch.setattr("igloo_mcp.mcp_server.anyio.to_thread.run_sync", run_sync)

    register_calls: list[tuple] = []

    def fake_register(*a, **kwargs):
        register_calls.append((a, kwargs))

    monkeypatch.setattr("igloo_mcp.mcp_server.register_igloo_mcp", fake_register)

    lifespan = module.create_combined_lifespan(args)
    server = SimpleNamespace()
    async with lifespan(server) as service:
        assert service.name == "snow_service"

    assert register_calls
    assert "igloo_mcp" in created["service_config"]


def test_main_happy_path(monkeypatch: pytest.MonkeyPatch):
    module = __import__("igloo_mcp.mcp_server", fromlist=[""])
    args = SimpleNamespace(
        log_level="INFO",
        transport="stdio",
        name="server",
        instructions="hi",
        enable_cli_bridge=False,
    )
    monkeypatch.setattr("igloo_mcp.mcp_server.parse_arguments", lambda argv=None: args)
    monkeypatch.setattr("igloo_mcp.mcp_server.warn_deprecated_params", lambda: None)
    monkeypatch.setattr("igloo_mcp.mcp_server.configure_logging", lambda level: None)
    monkeypatch.setattr("igloo_mcp.mcp_server._apply_config_overrides", lambda args: None)
    monkeypatch.setattr("igloo_mcp.mcp_server.validate_and_resolve_profile", lambda: "DEV")
    monkeypatch.setattr("igloo_mcp.mcp_server.apply_config_overrides", lambda **kwargs: None)
    monkeypatch.setattr("igloo_mcp.mcp_server.get_profile_summary", lambda: {"profiles": []})

    @asynccontextmanager
    async def fake_lifespan(server):
        yield "service"

    monkeypatch.setattr("igloo_mcp.mcp_server.create_combined_lifespan", lambda args: fake_lifespan)

    run_calls = []

    class StubFastMCP:
        def __init__(self, *a, **kw):
            pass

        def run(self, **kwargs):
            run_calls.append(kwargs)

    monkeypatch.setattr("igloo_mcp.mcp_server.FastMCP", StubFastMCP)

    module.main([])
    assert run_calls == [{"transport": "stdio"}]
    assert __import__("os").environ["SNOWFLAKE_DEFAULT_CONNECTION_NAME"] == "DEV"


def test_main_profile_validation_failure(monkeypatch: pytest.MonkeyPatch):
    module = __import__("igloo_mcp.mcp_server", fromlist=[""])
    args = SimpleNamespace(log_level="INFO", transport="stdio")
    monkeypatch.setattr("igloo_mcp.mcp_server.parse_arguments", lambda argv=None: args)
    monkeypatch.setattr("igloo_mcp.mcp_server.warn_deprecated_params", lambda: None)
    monkeypatch.setattr("igloo_mcp.mcp_server.configure_logging", lambda level: None)
    monkeypatch.setattr("igloo_mcp.mcp_server._apply_config_overrides", lambda args: None)

    error = ProfileValidationError(
        "bad profile",
        available_profiles=["A", "B"],
        config_path="/tmp/config",
    )
    monkeypatch.setattr(
        "igloo_mcp.mcp_server.validate_and_resolve_profile",
        lambda: (_ for _ in ()).throw(error),
    )

    with pytest.raises(SystemExit) as exc_info:
        module.main([])

    assert exc_info.value.code == 1
