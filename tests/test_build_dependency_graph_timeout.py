"""Tests for build_dependency_graph timeout controls."""

from __future__ import annotations

import time
from unittest.mock import Mock

import pytest

from igloo_mcp.mcp.exceptions import MCPExecutionError
from igloo_mcp.mcp.tools.build_dependency_graph import BuildDependencyGraphTool


@pytest.mark.anyio
async def test_build_dependency_graph_timeout_defaults_to_60(base_config, monkeypatch):
    monkeypatch.delenv("IGLOO_MCP_TOOL_TIMEOUT_SECONDS", raising=False)
    service = Mock()
    service.build_dependency_graph.return_value = {"status": "success"}
    tool = BuildDependencyGraphTool(dependency_service=service)

    result = await tool.execute(database="ANALYTICS")

    assert result["timeout"]["seconds"] == 60
    assert result["timeout"]["source"] == "default"


@pytest.mark.anyio
async def test_build_dependency_graph_timeout_uses_env_fallback(base_config, monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_TOOL_TIMEOUT_SECONDS", "180")
    service = Mock()
    service.build_dependency_graph.return_value = {"status": "success"}
    tool = BuildDependencyGraphTool(dependency_service=service)

    result = await tool.execute(database="ANALYTICS")

    assert result["timeout"]["seconds"] == 180
    assert result["timeout"]["source"] == "env"


@pytest.mark.anyio
async def test_build_dependency_graph_timeout_parameter_overrides_env(base_config, monkeypatch):
    monkeypatch.setenv("IGLOO_MCP_TOOL_TIMEOUT_SECONDS", "180")
    service = Mock()
    service.build_dependency_graph.return_value = {"status": "success"}
    tool = BuildDependencyGraphTool(dependency_service=service)

    result = await tool.execute(database="ANALYTICS", timeout_seconds=240)

    assert result["timeout"]["seconds"] == 240
    assert result["timeout"]["source"] == "parameter"


@pytest.mark.anyio
async def test_build_dependency_graph_timeout_raises_execution_error(base_config):
    def _slow_build(*args, **kwargs):
        time.sleep(2)
        return {"status": "success"}

    service = Mock()
    service.build_dependency_graph.side_effect = _slow_build
    tool = BuildDependencyGraphTool(dependency_service=service)

    with pytest.raises(MCPExecutionError) as exc_info:
        await tool.execute(database="ANALYTICS", timeout_seconds=1)

    assert "timed out" in str(exc_info.value).lower()
