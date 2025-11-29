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
from .create_report import CreateReportTool
from .evolve_report import EvolveReportTool
from .execute_query import ExecuteQueryTool
from .get_catalog_summary import GetCatalogSummaryTool
from .get_report import GetReportTool
from .get_report_schema import GetReportSchemaTool
from .health import HealthCheckTool
from .render_report import RenderReportTool
from .search_catalog import SearchCatalogTool
from .search_report import SearchReportTool
from .test_connection import ConnectionTestTool

__all__ = [
    "MCPTool",
    "MCPToolSchema",
    "BuildCatalogTool",
    "BuildDependencyGraphTool",
    "CreateReportTool",
    "ExecuteQueryTool",
    "EvolveReportTool",
    "GetCatalogSummaryTool",
    "GetReportTool",
    "GetReportSchemaTool",
    "HealthCheckTool",
    "RenderReportTool",
    "SearchCatalogTool",
    "SearchReportTool",
    "ConnectionTestTool",
]
