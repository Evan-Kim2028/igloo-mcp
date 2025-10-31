"""Tests for DependencyService."""

from __future__ import annotations

from dataclasses import dataclass

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.service_layer.dependency_service import DependencyService


@dataclass
class StubContext:
    config: Config


def test_dependency_service_uses_context_profile():
    cfg = Config(snowflake=SnowflakeConfig(profile="DEV"))
    ctx = StubContext(config=cfg)
    service = DependencyService(context=ctx)
    assert service.profile == "DEV"


def test_dependency_service_build_graph_defaults():
    service = DependencyService()
    result = service.build_dependency_graph(
        database="ANALYTICS", schema="PUBLIC", account_scope=False, format="json"
    )
    assert result["database"] == "ANALYTICS"
    assert result["schema"] == "PUBLIC"
    assert result["account_scope"] is False
    assert result["format"] == "json"
    assert result["status"] == "success"
