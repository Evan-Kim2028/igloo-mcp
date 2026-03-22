"""Tests for ExportReportTool MCP functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.exceptions import MCPSelectorError
from igloo_mcp.mcp.tools.export_report import ExportReportTool


@pytest.fixture
def config():
    return Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))


@pytest.fixture
def temp_reports_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        reports_dir = Path(tmpdir) / "reports"
        reports_dir.mkdir()
        yield reports_dir


@pytest.fixture
def report_service(temp_reports_dir):
    return ReportService(reports_root=temp_reports_dir)


@pytest.fixture
def tool(config, report_service):
    return ExportReportTool(config, report_service)


def test_tool_properties(tool):
    assert tool.name == "export_report"
    assert "zip" in tool.description.lower()
    assert tool.category == "reports"
    assert "export" in tool.tags


def test_parameter_schema(tool):
    schema = tool.get_parameter_schema()
    assert schema["type"] == "object"
    assert schema["required"] == ["report_selector"]
    assert "output_path" in schema["properties"]
    assert "include_audit" in schema["properties"]
    assert "include_assets" in schema["properties"]


@pytest.mark.asyncio
async def test_export_report_execute_success(tool, report_service):
    report_id = report_service.create_report("Tool Export Test")

    result = await tool.execute(report_selector=report_id, include_assets=False)

    assert result["status"] == "success"
    assert result["report_id"] == report_id
    assert result["bundle"]["include_assets"] is False
    assert Path(result["output"]["output_path"]).exists()
    assert "request_id" in result
    assert "timing" in result


@pytest.mark.asyncio
async def test_export_report_execute_invalid_selector(tool):
    with pytest.raises(MCPSelectorError):
        await tool.execute(report_selector="does-not-exist")
