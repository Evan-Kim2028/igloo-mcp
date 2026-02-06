"""Tests for build_catalog timeout controls."""

from __future__ import annotations

import time
from unittest.mock import Mock

import pytest

from igloo_mcp.mcp.exceptions import MCPExecutionError
from igloo_mcp.mcp.tools.build_catalog import BuildCatalogTool


def _mock_build_result():
    result = Mock()
    result.output_dir = "/tmp/catalog"
    result.totals = Mock(
        databases=1,
        schemas=2,
        tables=3,
        views=1,
        materialized_views=0,
        dynamic_tables=0,
        tasks=0,
        functions=0,
        procedures=0,
        columns=10,
    )
    return result


@pytest.mark.anyio
async def test_build_catalog_timeout_defaults_to_60(base_config, monkeypatch):
    monkeypatch.delenv("IGLOO_MCP_TOOL_TIMEOUT_SECONDS", raising=False)
    catalog_service = Mock()
    catalog_service.build.return_value = _mock_build_result()
    tool = BuildCatalogTool(base_config, catalog_service)

    result = await tool.execute(output_dir="./catalog")

    assert result["timeout"]["seconds"] == 60
    assert result["timeout"]["source"] == "default"


@pytest.mark.anyio
async def test_build_catalog_timeout_uses_env_fallback(base_config, monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_TOOL_TIMEOUT_SECONDS", "180")
    catalog_service = Mock()
    catalog_service.build.return_value = _mock_build_result()
    tool = BuildCatalogTool(base_config, catalog_service)

    result = await tool.execute(output_dir="./catalog")

    assert result["timeout"]["seconds"] == 180
    assert result["timeout"]["source"] == "env"


@pytest.mark.anyio
async def test_build_catalog_timeout_parameter_overrides_env(base_config, monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_TOOL_TIMEOUT_SECONDS", "180")
    catalog_service = Mock()
    catalog_service.build.return_value = _mock_build_result()
    tool = BuildCatalogTool(base_config, catalog_service)

    result = await tool.execute(output_dir="./catalog", timeout_seconds=240)

    assert result["timeout"]["seconds"] == 240
    assert result["timeout"]["source"] == "parameter"


@pytest.mark.anyio
async def test_build_catalog_timeout_raises_execution_error(base_config):
    def _slow_build(*args, **kwargs):
        time.sleep(2)
        return _mock_build_result()

    catalog_service = Mock()
    catalog_service.build.side_effect = _slow_build
    tool = BuildCatalogTool(base_config, catalog_service)

    with pytest.raises(MCPExecutionError) as exc_info:
        await tool.execute(output_dir="./catalog", timeout_seconds=1)

    assert "timed out" in str(exc_info.value).lower()
