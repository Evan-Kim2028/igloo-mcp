"""Offline tests that exercise catalog services and tools using fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from igloo_mcp.catalog.catalog_service import CatalogService
from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.mcp.tools.build_catalog import BuildCatalogTool
from igloo_mcp.mcp.tools.get_catalog_summary import GetCatalogSummaryTool
from igloo_mcp.snow_cli import SnowCLIError
from tests.helpers.fixture_snow_cli import FixtureSnowCLI

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "snowflake_cli"


def _catalog_service_with_fixture_cli(
    *,
    raise_on: dict[str, Exception] | None = None,
) -> CatalogService:
    service = CatalogService(context=None)
    service.cli = FixtureSnowCLI(FIXTURE_DIR, raise_on=raise_on)
    return service


def test_catalog_service_build_with_fixtures(tmp_path: Path) -> None:
    service = _catalog_service_with_fixture_cli()
    output_dir = tmp_path / "catalog"

    result = service.build(output_dir=str(output_dir), database="ANALYTICS")

    assert result.success is True
    assert result.output_dir == str(output_dir)
    assert result.totals.databases == 1
    assert result.totals.schemas == 2
    assert result.totals.tables == 3
    assert result.totals.views == 1
    assert result.totals.materialized_views == 0
    assert result.totals.dynamic_tables == 0
    assert result.totals.tasks == 1
    assert result.totals.functions == 2
    assert result.totals.procedures == 1
    assert result.totals.columns == 3

    catalog_file = output_dir / "catalog.json"
    summary_file = output_dir / "catalog_summary.json"
    assert catalog_file.exists()
    assert summary_file.exists()

    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    assert summary["totals"]["tables"] == 3
    assert summary["format"] == "json"


def test_catalog_service_build_handles_cli_error(tmp_path: Path) -> None:
    service = _catalog_service_with_fixture_cli(
        raise_on={"SHOW TABLES": SnowCLIError("simulated failure")}
    )
    output_dir = tmp_path / "catalog"

    result = service.build(output_dir=str(output_dir))

    # Failures inside _build_real_catalog are logged and produce empty totals.
    assert result.success is True
    assert result.totals.tables == 0
    summary_file = output_dir / "catalog_summary.json"
    assert summary_file.exists()
    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    assert summary["totals"]["tables"] == 0


def test_catalog_service_build_account_scope_jsonl(tmp_path: Path) -> None:
    service = CatalogService(context=None)

    class StubCLI:
        def __init__(self):
            self.calls: list[str] = []

        def run_query(self, query: str, output_format: str | None = None):
            self.calls.append(query.strip())
            if "DATABASES" in query:
                rows = [{"name": "DB1"}, {"name": "DB2"}]
            elif "SCHEMAS" in query:
                rows = [{"schema": "PUBLIC"}]
            elif "TABLES" in query:
                rows = [{"table": "T1"}, {"table": "T2"}, {"table": "T3"}]
            elif "FUNCTIONS" in query:
                rows = [{"function_name": "F1"}]
            elif "COLUMNS" in query:
                rows = [{"column_name": "C1"}]
            else:
                rows = [{"value": query.strip()}]
            return SimpleNamespace(rows=rows)

    stub_cli = StubCLI()
    service.cli = stub_cli  # type: ignore[assignment]
    output_dir = tmp_path / "acct"

    result = service.build(
        output_dir=str(output_dir),
        account_scope=True,
        output_format="jsonl",
    )

    assert result.success is True
    assert result.totals.databases == 2
    assert result.totals.tables == 3
    assert output_dir.joinpath("catalog.jsonl").exists()
    assert "SHOW DATABASES" in stub_cli.calls[0]
    assert any("FUNCTIONS" in call for call in stub_cli.calls)


def test_catalog_service_build_handles_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _catalog_service_with_fixture_cli()
    output_dir = tmp_path / "catalog"
    original_open = open

    def fail_open(path, *args, **kwargs):
        if getattr(path, "name", str(path)).endswith("catalog_summary.json"):
            raise OSError("disk full")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fail_open, raising=False)

    result = service.build(output_dir=str(output_dir))
    assert result.success is False
    assert result.error == "disk full"


@pytest.mark.anyio
async def test_build_catalog_tool_execute_with_fixtures(tmp_path: Path) -> None:
    service = _catalog_service_with_fixture_cli()
    config = Config(snowflake=SnowflakeConfig(profile="TEST"))
    tool = BuildCatalogTool(config=config, catalog_service=service)

    output_dir = tmp_path / "tool_catalog"
    result = await tool.execute(
        output_dir=str(output_dir),
        database="ANALYTICS",
        account=False,
        output_format="json",
    )

    assert result["status"] == "success"
    assert result["output_dir"] == str(output_dir)
    assert result["totals"]["tables"] == 3
    assert output_dir.joinpath("catalog_summary.json").exists()


@pytest.mark.anyio
async def test_get_catalog_summary_tool_success(tmp_path: Path) -> None:
    service = _catalog_service_with_fixture_cli()
    output_dir = tmp_path / "catalog"
    service.build(output_dir=str(output_dir), database="ANALYTICS")

    tool = GetCatalogSummaryTool(catalog_service=service)
    result = await tool.execute(catalog_dir=str(output_dir))

    assert result["status"] == "success"
    assert result["summary"]["totals"]["tables"] == 3
    assert result["summary"]["format"] == "json"


@pytest.mark.anyio
async def test_get_catalog_summary_tool_missing_directory(tmp_path: Path) -> None:
    service = _catalog_service_with_fixture_cli()
    tool = GetCatalogSummaryTool(catalog_service=service)

    missing_dir = tmp_path / "missing"
    result = await tool.execute(catalog_dir=str(missing_dir))

    assert result["status"] == "error"
    assert "No catalog found" in result["error"]


def test_load_summary_missing_directory(tmp_path: Path) -> None:
    service = CatalogService(context=None)
    with pytest.raises(FileNotFoundError):
        service.load_summary(str(tmp_path / "missing"))


def test_load_summary_missing_file(tmp_path: Path) -> None:
    service = CatalogService(context=None)
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        service.load_summary(str(catalog_dir))
