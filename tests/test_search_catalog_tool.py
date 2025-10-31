"""Tests for the search_catalog tool using offline catalog fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from igloo_mcp.catalog.catalog_service import CatalogService
from igloo_mcp.mcp.tools.search_catalog import SearchCatalogTool
from tests.helpers.fixture_snow_cli import FixtureSnowCLI

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "snowflake_cli"


def _catalog_service_with_fixture_cli() -> CatalogService:
    service = CatalogService(context=None)
    service.cli = FixtureSnowCLI(FIXTURE_DIR)
    return service


@pytest.mark.anyio
async def test_search_catalog_tables(tmp_path: Path) -> None:
    service = _catalog_service_with_fixture_cli()
    catalog_dir = tmp_path / "catalog"
    service.build(output_dir=str(catalog_dir), database="ANALYTICS")

    tool = SearchCatalogTool()
    result = await tool.execute(
        catalog_dir=str(catalog_dir),
        object_types=["table"],
        name_contains="sales",
        limit=5,
    )

    assert result["status"] == "success"
    assert result["total_matches"] >= 1
    table_names = {entry["name"] for entry in result["results"]}
    assert "SALES_FACT" in table_names
    first = result["results"][0]
    assert "columns" in first


@pytest.mark.anyio
async def test_search_catalog_by_column(tmp_path: Path) -> None:
    service = _catalog_service_with_fixture_cli()
    catalog_dir = tmp_path / "catalog"
    service.build(output_dir=str(catalog_dir), database="ANALYTICS")

    tool = SearchCatalogTool()
    result = await tool.execute(
        catalog_dir=str(catalog_dir),
        column_contains="customer",
    )

    assert result["status"] == "success"
    assert result["total_matches"] >= 1
    assert any("CUSTOMERS" in entry["name"] for entry in result["results"])


@pytest.mark.anyio
async def test_search_catalog_missing_dir(tmp_path: Path) -> None:
    tool = SearchCatalogTool()
    missing = tmp_path / "missing"
    result = await tool.execute(catalog_dir=str(missing))

    assert result["status"] == "error"
    assert "build_catalog" in result["error"].lower()
