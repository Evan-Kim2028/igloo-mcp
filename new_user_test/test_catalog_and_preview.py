#!/usr/bin/env python3
"""Test script for catalog build, summary, and table preview functionality."""

import asyncio
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skip(
    reason="manual integration scenario requiring Snowflake access"
)

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "igloo-mcp" / "src"))

from igloo_mcp.config import Config, SnowflakeConfig  # noqa: E402
from igloo_mcp.services import RobustSnowflakeService  # noqa: E402


async def test_catalog_and_preview():
    """Test catalog build, summary, and table preview functionality."""
    print("🧪 Testing igloo-mcp catalog and preview functionality...")

    # Create config with snowflake profile
    config = Config(snowflake=SnowflakeConfig(profile="mystenlabs-keypair"))

    # Test 1: Build full data catalog
    print("\n1. Testing full data catalog build...")
    try:
        from igloo_mcp.catalog.catalog_service import CatalogService
        from igloo_mcp.mcp.tools.build_catalog import BuildCatalogTool

        catalog_service = CatalogService({"profile": "mystenlabs-keypair"})
        catalog_tool = BuildCatalogTool(config, catalog_service)

        result = await catalog_tool.execute(
            output_dir="./test_catalog_full",
            database="PIPELINE_V2_GROOT_DB",
            account=False,
            format="json",
        )

        print(f"✅ Catalog build: {result.get('status', 'unknown')}")
        if result.get("status") == "success":
            totals = result.get("totals", {})
            print(f"   Databases: {totals.get('databases', 0)}")
            print(f"   Schemas: {totals.get('schemas', 0)}")
            print(f"   Tables: {totals.get('tables', 0)}")
            print(f"   Views: {totals.get('views', 0)}")
            print(f"   Columns: {totals.get('columns', 0)}")
            print(f"   Output: {result.get('output_dir', 'unknown')}")
        else:
            print(f"❌ Catalog build failed: {result.get('error', 'unknown error')}")

    except Exception as e:
        print(f"❌ Catalog build test failed: {e}")

    # Test 2: Get catalog summary
    print("\n2. Testing catalog summary...")
    try:
        from igloo_mcp.mcp.tools.get_catalog_summary import GetCatalogSummaryTool

        summary_tool = GetCatalogSummaryTool(catalog_service)
        result = await summary_tool.execute(catalog_dir="./test_catalog_full")

        print(f"✅ Catalog summary: {result.get('status', 'unknown')}")
        if result.get("status") == "success":
            summary = result.get("summary", {})
            totals = summary.get("totals", {})
            print(f"   Databases: {totals.get('databases', 0)}")
            print(f"   Schemas: {totals.get('schemas', 0)}")
            print(f"   Tables: {totals.get('tables', 0)}")
            print(f"   Views: {totals.get('views', 0)}")
            print(f"   Columns: {totals.get('columns', 0)}")
            print(f"   Format: {summary.get('format', 'unknown')}")
        else:
            print(f"❌ Catalog summary failed: {result.get('error', 'unknown error')}")

    except Exception as e:
        print(f"❌ Catalog summary test failed: {e}")

    # Test 3: Preview dex_trades_stable table
    print("\n3. Testing preview table on dex_trades_stable...")
    try:
        from igloo_mcp.mcp.tools.preview_table import PreviewTableTool
        from igloo_mcp.service_layer.query_service import QueryService

        service = RobustSnowflakeService(profile="mystenlabs-keypair")
        query_service = QueryService({"profile": "mystenlabs-keypair"})
        preview_tool = PreviewTableTool(config, service, query_service)

        result = await preview_tool.execute(
            table_name="PIPELINE_V2_GROOT_DB.PIPELINE_V2_GROOT_SCHEMA.dex_trades_stable",
            limit=10,
            warehouse="PRESET_WH",
            database="PIPELINE_V2_GROOT_DB",
            schema="PIPELINE_V2_GROOT_SCHEMA",
        )

        print(f"✅ Table preview: {result.get('status', 'unknown')}")
        if result.get("status") == "success":
            preview = result.get("preview", {})
            rows = preview.get("rows", [])
            columns = preview.get("columns", [])
            print(f"   Columns: {len(columns)}")
            print(f"   Rows: {len(rows)}")
            print(f"   Limit: {preview.get('limit', 0)}")

            if columns:
                print(
                    f"   Column names: {', '.join(columns[:5])}{'...' if len(columns) > 5 else ''}"
                )

            if rows:
                print(
                    f"   Sample data (first row): {dict(list(rows[0].items())[:3])}{'...' if len(rows[0]) > 3 else ''}"
                )
        else:
            print(f"❌ Table preview failed: {result.get('error', 'unknown error')}")

    except Exception as e:
        print(f"❌ Table preview test failed: {e}")

    # Test 4: Test with a simpler table name
    print("\n4. Testing preview table with simpler name...")
    try:
        result = await preview_tool.execute(table_name="dex_trades_stable", limit=5)

        print(f"✅ Simple table preview: {result.get('status', 'unknown')}")
        if result.get("status") == "success":
            preview = result.get("preview", {})
            rows = preview.get("rows", [])
            columns = preview.get("columns", [])
            print(f"   Columns: {len(columns)}")
            print(f"   Rows: {len(rows)}")
        else:
            print(
                f"❌ Simple table preview failed: {result.get('error', 'unknown error')}"
            )

    except Exception as e:
        print(f"❌ Simple table preview test failed: {e}")

    print("\n🎉 Catalog and preview testing completed!")


if __name__ == "__main__":
    asyncio.run(test_catalog_and_preview())
