#!/usr/bin/env python3
"""Test script for catalog summary functionality."""

import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "igloo-mcp" / "src"))

from igloo_mcp.catalog.catalog_service import CatalogService


def test_catalog_summary():
    """Test catalog summary functionality."""
    print("🧪 Testing catalog summary functionality...")
    
    try:
        # Test catalog summary loading
        catalog_service = CatalogService({"profile": "mystenlabs-keypair"})
        summary = catalog_service.load_summary("./test_catalog_full")
        
        print("✅ Catalog summary loaded successfully")
        print(f"   Totals: {summary.get('totals', {})}")
        print(f"   Output dir: {summary.get('output_dir', 'unknown')}")
        print(f"   Format: {summary.get('format', 'unknown')}")
        
        # Test the MCP tool
        from igloo_mcp.mcp.tools.get_catalog_summary import GetCatalogSummaryTool
        
        summary_tool = GetCatalogSummaryTool(catalog_service)
        
        # Test synchronously since we can't easily run async here
        import asyncio
        async def run_test():
            result = await summary_tool.execute(catalog_dir="./test_catalog_full")
            return result
        
        result = asyncio.run(run_test())
        
        print(f"✅ MCP tool result: {result.get('status', 'unknown')}")
        if result.get('status') == 'success':
            summary_data = result.get('summary', {})
            totals = summary_data.get('totals', {})
            print(f"   Databases: {totals.get('databases', 0)}")
            print(f"   Schemas: {totals.get('schemas', 0)}")
            print(f"   Tables: {totals.get('tables', 0)}")
            print(f"   Views: {totals.get('views', 0)}")
            print(f"   Columns: {totals.get('columns', 0)}")
        else:
            print(f"❌ MCP tool failed: {result.get('error', 'unknown error')}")
            
    except Exception as e:
        print(f"❌ Catalog summary test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_catalog_summary()
