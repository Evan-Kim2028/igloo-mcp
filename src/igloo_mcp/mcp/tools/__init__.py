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
from .evolve_report_batch import EvolveReportBatchTool
from .execute_query import ExecuteQueryTool
from .export_report import ExportReportTool
from .get_catalog_summary import GetCatalogSummaryTool
from .get_report import GetReportTool
from .get_report_schema import GetReportSchemaTool
from .health import HealthCheckTool
from .list_profiles import ListProfilesTool
from .profile_setup_guide import ProfileSetupGuideTool
from .render_report import RenderReportTool
from .search_catalog import SearchCatalogTool
from .search_citations import SearchCitationsTool
from .search_report import SearchReportTool
from .switch_profile import SwitchProfileTool
from .test_connection import ConnectionTestTool
from .validate_report import ValidateReportTool

__all__ = [
    "BuildCatalogTool",
    "BuildDependencyGraphTool",
    "ConnectionTestTool",
    "CreateReportTool",
    "EvolveReportBatchTool",
    "EvolveReportTool",
    "ExecuteQueryTool",
    "ExportReportTool",
    "GetCatalogSummaryTool",
    "GetReportSchemaTool",
    "GetReportTool",
    "HealthCheckTool",
    "ListProfilesTool",
    "MCPTool",
    "MCPToolSchema",
    "ProfileSetupGuideTool",
    "RenderReportTool",
    "SearchCatalogTool",
    "SearchCitationsTool",
    "SearchReportTool",
    "SwitchProfileTool",
    "ValidateReportTool",
]
