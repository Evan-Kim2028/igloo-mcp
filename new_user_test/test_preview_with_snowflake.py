#!/usr/bin/env python3
"""Test script for preview table functionality with actual Snowflake CLI."""

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


async def test_preview_with_snowflake():
    """Test preview table functionality with actual Snowflake CLI."""
    print("🧪 Testing preview table functionality with Snowflake CLI...")

    # Create config with snowflake profile
    config = Config(snowflake=SnowflakeConfig(profile="mystenlabs-keypair"))

    # Test 1: Preview dex_trades_stable table with full name
    print("\n1. Testing preview table with full name...")
    try:
        from igloo_mcp.mcp.tools.preview_table import PreviewTableTool
        from igloo_mcp.service_layer.query_service import QueryService

        service = RobustSnowflakeService(profile="mystenlabs-keypair")
        query_service = QueryService({"profile": "mystenlabs-keypair"})
        preview_tool = PreviewTableTool(config, service, query_service)

        result = await preview_tool.execute(
            table_name="PIPELINE_V2_GROOT_DB.PIPELINE_V2_GROOT_SCHEMA.dex_trades_stable",
            limit=5,
            warehouse="PRESET_WH",
            database="PIPELINE_V2_GROOT_DB",
            schema="PIPELINE_V2_GROOT_SCHEMA",
        )

        print(f"✅ Table preview: {result.get('status', 'unknown')}")
        if result.get("status") == "success":
            preview = result.get("preview", {})
            rows = preview.get("rows", [])
            columns = preview.get("columns", [])
            print(f"   Columns: {len(columns) if columns else 0}")
            print(f"   Rows: {len(rows) if rows else 0}")
            print(f"   Limit: {preview.get('limit', 0)}")

            if columns:
                print(
                    f"   Column names: {', '.join(columns[:5])}{'...' if len(columns) > 5 else ''}"
                )
            else:
                print("   Columns: None")

            if rows:
                print(
                    f"   Sample data (first row): {dict(list(rows[0].items())[:3])}{'...' if len(rows[0]) > 3 else ''}"
                )
            else:
                print("   Rows: None")
        else:
            print(f"❌ Table preview failed: {result.get('error', 'unknown error')}")

    except Exception as e:
        print(f"❌ Table preview test failed: {e}")
        import traceback

        traceback.print_exc()

    # Test 2: Preview with simpler table name
    print("\n2. Testing preview table with simpler name...")
    try:
        result = await preview_tool.execute(table_name="dex_trades_stable", limit=3)

        print(f"✅ Simple table preview: {result.get('status', 'unknown')}")
        if result.get("status") == "success":
            preview = result.get("preview", {})
            rows = preview.get("rows", [])
            columns = preview.get("columns", [])
            print(f"   Columns: {len(columns) if columns else 0}")
            print(f"   Rows: {len(rows) if rows else 0}")
        else:
            print(
                f"❌ Simple table preview failed: {result.get('error', 'unknown error')}"
            )

    except Exception as e:
        print(f"❌ Simple table preview test failed: {e}")
        import traceback

        traceback.print_exc()

    # Test 3: Test a different table
    print("\n3. Testing preview table on INFORMATION_SCHEMA.TABLES...")
    try:
        result = await preview_tool.execute(
            table_name="INFORMATION_SCHEMA.TABLES", limit=3
        )

        print(f"✅ Information schema preview: {result.get('status', 'unknown')}")
        if result.get("status") == "success":
            preview = result.get("preview", {})
            rows = preview.get("rows", [])
            columns = preview.get("columns", [])
            print(f"   Columns: {len(columns) if columns else 0}")
            print(f"   Rows: {len(rows) if rows else 0}")
        else:
            print(
                f"❌ Information schema preview failed: {result.get('error', 'unknown error')}"
            )

    except Exception as e:
        print(f"❌ Information schema preview test failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n🎉 Preview table testing completed!")


if __name__ == "__main__":
    asyncio.run(test_preview_with_snowflake())
