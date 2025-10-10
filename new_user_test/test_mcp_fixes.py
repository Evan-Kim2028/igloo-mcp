#!/usr/bin/env python3
"""Test script to verify MCP tool fixes."""

import asyncio
import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "igloo-mcp" / "src"))

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.services import RobustSnowflakeService


async def test_mcp_tool_fixes():
    """Test MCP tool fixes."""
    print("🧪 Testing MCP tool fixes...")
    
    # Create config with snowflake profile
    config = Config(
        snowflake=SnowflakeConfig(profile="mystenlabs-keypair")
    )
    
    # Test 1: Health check with fixed ProfileSummary
    print("\n1. Testing health check with fixed ProfileSummary...")
    try:
        from igloo_mcp.mcp.tools.health import HealthCheckTool
        service = RobustSnowflakeService(profile="mystenlabs-keypair")
        health_tool = HealthCheckTool(config, service)
        result = await health_tool.execute()
        print(f"✅ Health check: {result.get('overall_status', 'unknown')}")
        if result.get('profile', {}).get('status') == 'valid':
            print("✅ Profile validation working")
        else:
            print(f"⚠️ Profile validation: {result.get('profile', {}).get('status')}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
    
    # Test 2: Connection test with context manager
    print("\n2. Testing connection test with context manager...")
    try:
        from igloo_mcp.mcp.tools.test_connection import ConnectionTestTool
        service = RobustSnowflakeService(profile="mystenlabs-keypair")
        connection_tool = ConnectionTestTool(config, service)
        result = await connection_tool.execute()
        print(f"✅ Connection test: {result.get('status', 'unknown')}")
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
    
    # Test 3: Query execution with context manager
    print("\n3. Testing query execution with context manager...")
    try:
        from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
        service = RobustSnowflakeService(profile="mystenlabs-keypair")
        query_tool = ExecuteQueryTool(config, service)
        result = await query_tool.execute(statement="SELECT CURRENT_VERSION()")
        print(f"✅ Query execution: {result.get('status', 'unknown')}")
    except Exception as e:
        print(f"❌ Query execution failed: {e}")
    
    # Test 4: Preview table with fixed method signature
    print("\n4. Testing preview table with fixed method signature...")
    try:
        from igloo_mcp.mcp.tools.preview_table import PreviewTableTool
        from igloo_mcp.service_layer.query_service import QueryService
        service = RobustSnowflakeService(profile="mystenlabs-keypair")
        query_service = QueryService({"profile": "mystenlabs-keypair"})
        preview_tool = PreviewTableTool(config, service, query_service)
        result = await preview_tool.execute(table_name="INFORMATION_SCHEMA.TABLES", limit=5)
        print(f"✅ Table preview: {result.get('status', 'unknown')}")
    except Exception as e:
        print(f"❌ Table preview failed: {e}")
    
    # Test 5: SnowCLI context manager
    print("\n5. Testing SnowCLI context manager...")
    try:
        from igloo_mcp.snow_cli import SnowCLI
        cli = SnowCLI("mystenlabs-keypair")
        with cli as snow_cli:
            print("✅ SnowCLI context manager works")
    except Exception as e:
        print(f"❌ SnowCLI context manager failed: {e}")
    
    print("\n🎉 MCP tool fixes testing completed!")


if __name__ == "__main__":
    asyncio.run(test_mcp_tool_fixes())
