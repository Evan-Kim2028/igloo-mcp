#!/usr/bin/env python3
"""Simple test to verify igloo-mcp functionality."""

import subprocess
import sys
from pathlib import Path

def test_basic_functionality():
    """Test basic igloo-mcp functionality."""
    print("🧪 Testing igloo-mcp basic functionality...")
    
    # Test 1: Check if we can import the module
    try:
        sys.path.insert(0, str(Path(__file__).parent / "igloo-mcp" / "src"))
        import igloo_mcp
        print("✅ igloo-mcp module imports successfully")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    # Test 2: Check if catalog service works
    try:
        from igloo_mcp.catalog.catalog_service import CatalogService
        catalog_service = CatalogService({"profile": "mystenlabs-keypair"})
        result = catalog_service.build(output_dir="./test_catalog_simple")
        if result.success:
            print("✅ Catalog service works")
        else:
            print(f"❌ Catalog service failed: {result.error}")
            return False
    except Exception as e:
        print(f"❌ Catalog service test failed: {e}")
        return False
    
    # Test 3: Check if dependency service works
    try:
        from igloo_mcp.dependency.dependency_service import DependencyService
        dep_service = DependencyService({"profile": "mystenlabs-keypair"})
        result = dep_service.build_dependency_graph()
        if result.get("status") == "success":
            print("✅ Dependency service works")
        else:
            print(f"❌ Dependency service failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"❌ Dependency service test failed: {e}")
        return False
    
    print("🎉 Basic functionality tests passed!")
    return True

if __name__ == "__main__":
    success = test_basic_functionality()
    sys.exit(0 if success else 1)
