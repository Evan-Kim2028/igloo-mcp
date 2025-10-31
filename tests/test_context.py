"""Tests for service context factory."""

from __future__ import annotations

from typing import Any

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.context import ServiceContext, create_service_context


def test_create_service_context_uses_existing_config():
    original = Config(snowflake=SnowflakeConfig(profile="test_profile"))
    ctx = create_service_context(existing_config=original)
    assert isinstance(ctx, ServiceContext)
    assert ctx.config is original
    assert ctx.health_monitor is not None
    assert ctx.resource_manager.health_monitor is ctx.health_monitor


def test_create_service_context_with_profile_override(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, Any] = {}

    def fake_load_config(config_path=None, cli_overrides=None):
        captured["config_path"] = config_path
        captured["overrides"] = cli_overrides
        return Config(snowflake=SnowflakeConfig(profile=cli_overrides["profile"]))

    monkeypatch.setattr("igloo_mcp.context.load_config", fake_load_config)
    ctx = create_service_context(profile="dev", config_path="/tmp/config.yaml")
    assert ctx.config.snowflake.profile == "dev"
    assert captured["config_path"] == "/tmp/config.yaml"
    assert captured["overrides"] == {"profile": "dev"}
