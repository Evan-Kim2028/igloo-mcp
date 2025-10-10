"""MCP tools package - simplified and consolidated tool implementations.

Part of v1.9.0 Phase 1 - Health Tools Consolidation

Changes from v1.8.0:
- Consolidated health_check, check_profile_config, get_resource_status → health.HealthCheckTool
- Removed check_resource_dependencies (confusing, rarely used)
- Simplified test_connection to lightweight wrapper

Each tool is self-contained in its own file and follows the command pattern
using the MCPTool base class.
"""

from __future__ import annotations

from .base import MCPTool, MCPToolSchema
from .build_catalog import BuildCatalogTool
from .build_dependency_graph import BuildDependencyGraphTool
from .execute_query import ExecuteQueryTool
from .get_catalog_summary import GetCatalogSummaryTool
from .health import HealthCheckTool
from .preview_table import PreviewTableTool
# QueryLineageTool removed - lineage functionality not part of igloo-mcp
from .test_connection import ConnectionTestTool

__all__ = [
    "MCPTool",
    "MCPToolSchema",
    "BuildCatalogTool",
    "BuildDependencyGraphTool",
    "ExecuteQueryTool",
    "GetCatalogSummaryTool",
    "HealthCheckTool",
    "PreviewTableTool",
    # "QueryLineageTool",  # Removed - lineage functionality not part of igloo-mcp
    "ConnectionTestTool",
]
