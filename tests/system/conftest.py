"""Shared fixtures for system tests."""

import uuid
from pathlib import Path
from typing import Any

import pytest

from igloo_mcp.cache.query_result_cache import QueryResultCache
from igloo_mcp.config import get_config
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.logging.query_history import QueryHistory
from igloo_mcp.mcp.tools.create_report import CreateReportTool
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.mcp.tools.render_report import RenderReportTool
from tests.helpers.fake_snowflake_connector import FakeQueryPlan, FakeSnowflakeService


@pytest.fixture
def system_test_env(tmp_path: Path, monkeypatch):
    """Set up complete environment for system tests.

    Creates temporary directories for:
    - Reports storage
    - Query history
    - Query cache
    - Artifacts

    Returns paths dict for test access.
    """
    reports_root = tmp_path / "reports"
    history_file = tmp_path / "logs" / "doc.jsonl"
    cache_root = tmp_path / "cache"
    artifact_root = tmp_path / "artifacts"

    # Create necessary directories
    reports_root.mkdir(parents=True)
    history_file.parent.mkdir(parents=True)
    cache_root.mkdir(parents=True)
    artifact_root.mkdir(parents=True)

    # Set environment variables
    env_overrides = {
        "IGLOO_MCP_QUERY_HISTORY": str(history_file),
        "IGLOO_MCP_CACHE_ROOT": str(cache_root),
        "IGLOO_MCP_ARTIFACT_ROOT": str(artifact_root),
    }

    for key, value in env_overrides.items():
        monkeypatch.setenv(key, value)

    return {
        "reports_root": reports_root,
        "history_file": history_file,
        "cache_root": cache_root,
        "artifact_root": artifact_root,
        "tmp_path": tmp_path,
    }


@pytest.fixture
def full_service_stack(system_test_env: dict[str, Any]):
    """Complete service stack for system tests.

    Provides all services needed for end-to-end workflows:
    - ReportService: Living reports management
    - FakeSnowflakeService: Query execution (mocked)
    - QueryHistory: Query logging
    - QueryResultCache: Query caching
    - Config: System configuration

    Returns dict with all services and tools.
    """
    config = get_config()

    # Create services
    report_service = ReportService(reports_root=system_test_env["reports_root"])

    # Create Snowflake service with a dummy initial plan
    # Tests will add their own plans using add_query_plan method
    dummy_plan = FakeQueryPlan(
        statement="SELECT 1",
        rows=[{"col1": 1}],
        rowcount=1,
        duration=0.01,
        sfqid="dummy_query_id",
    )
    snowflake_service = FakeSnowflakeService([dummy_plan])

    # Create query history
    history = QueryHistory(system_test_env["history_file"])

    # Create query cache
    cache = QueryResultCache.from_env(artifact_root=system_test_env["artifact_root"])

    # Create MCP tools
    create_report_tool = CreateReportTool(config, report_service)
    evolve_report_tool = EvolveReportTool(config, report_service)
    render_report_tool = RenderReportTool(config, report_service)
    execute_query_tool = ExecuteQueryTool(
        config=config,
        snowflake_service=snowflake_service,
        query_service=None,  # Not needed for system tests
        health_monitor=None,  # Not needed for system tests
    )

    return {
        "config": config,
        "report_service": report_service,
        "snowflake_service": snowflake_service,
        "history": history,
        "cache": cache,
        "tools": {
            "create_report": create_report_tool,
            "evolve_report": evolve_report_tool,
            "render_report": render_report_tool,
            "execute_query": execute_query_tool,
        },
        "env": system_test_env,
    }


@pytest.fixture
def realistic_query_results():
    """Generate realistic query results for testing.

    Returns list of row dicts suitable for FakeQueryPlan.
    """
    # Q4 2024 revenue data
    return [
        {
            "month": "2024-10",
            "total_revenue": 1250000.00,
            "unique_customers": 450,
            "avg_order_value": 2777.78,
            "yoy_growth_pct": 23.5,
        },
        {
            "month": "2024-11",
            "total_revenue": 1380000.00,
            "unique_customers": 485,
            "avg_order_value": 2845.36,
            "yoy_growth_pct": 25.2,
        },
        {
            "month": "2024-12",
            "total_revenue": 1620000.00,
            "unique_customers": 520,
            "avg_order_value": 3115.38,
            "yoy_growth_pct": 28.1,
        },
    ]


@pytest.fixture
def realistic_cost_results():
    """Generate realistic cost query results."""
    return [
        {
            "category": "Engineering",
            "q4_2024_cost": 850000.00,
            "q4_2023_cost": 720000.00,
            "variance_pct": 18.1,
        },
        {
            "category": "Marketing",
            "q4_2024_cost": 320000.00,
            "q4_2023_cost": 280000.00,
            "variance_pct": 14.3,
        },
        {
            "category": "Operations",
            "q4_2024_cost": 450000.00,
            "q4_2023_cost": 410000.00,
            "variance_pct": 9.8,
        },
    ]


@pytest.fixture
def large_report_data():
    """Generate data for large report testing (50 sections, 200 insights).

    Returns dict with sections and insights structure.
    """
    sections = []
    insights = []

    # Create 50 sections
    for i in range(50):
        section_id = str(uuid.uuid4())
        sections.append(
            {
                "section_id": section_id,
                "title": f"Section {i+1}: Analysis Topic {i+1}",
                "order": i,
                "insight_ids": [],  # Will be populated below
            }
        )

    # Create 200 insights, distributed across sections
    for i in range(200):
        insight_id = str(uuid.uuid4())
        insights.append(
            {
                "insight_id": insight_id,
                "importance": (i % 10) + 1,  # 1-10
                "summary": f"Insight {i+1}: Key finding about topic {i+1}",
                "supporting_queries": [],
                "status": "active",
            }
        )

        # Assign insight to a section (distribute evenly)
        section_idx = i % 50
        sections[section_idx]["insight_ids"].append(insight_id)

    return {
        "sections": sections,
        "insights": insights,
    }
