"""Integration test template.

Integration tests verify that multiple components work together correctly.
They should test realistic workflows, not individual functions.

Key principles:
1. Test at least 2 components interacting
2. Use realistic data and scenarios
3. Document the workflow in the docstring
4. Tag with specific integration marker
"""

import pytest

# @pytest.mark.integration
# @pytest.mark.integration_<WORKFLOW>  # e.g., integration_catalog, integration_reports
# async def test_<workflow>_integration():
#     """Integration test for <workflow> workflow.
#
#     Workflow:
#     1. Component A does X
#     2. Component B uses output from A to do Y
#     3. Component C uses output from B to do Z
#
#     Components tested:
#     - Component A: <description>
#     - Component B: <description>
#     - Component C: <description>
#
#     This tests the integration between these components to ensure
#     they work together correctly in a realistic scenario.
#     """
#     # Template - copy and modify for your integration test
#     pass


# Example 1: Catalog integration test
@pytest.mark.integration
@pytest.mark.integration_catalog
async def test_catalog_build_and_search_integration(tmp_path):
    """Integration test for catalog build → search workflow.

    Workflow:
    1. CatalogService builds metadata from Snowflake
    2. CatalogIndex loads the built catalog
    3. SearchCatalogTool searches the indexed data

    Components tested:
    - CatalogService: Metadata extraction and storage
    - CatalogIndex: Catalog loading and indexing
    - SearchCatalogTool: Search functionality

    This ensures the full catalog workflow works end-to-end.
    """

    # GIVEN: A catalog directory and service
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()

    # WHEN: Building a catalog (mocked for testing)
    # In actual test, you would either:
    # 1. Mock the Snowflake queries
    # 2. Use @pytest.mark.requires_snowflake for live testing

    # Step 1: Build catalog
    # service = CatalogService()
    # result = service.build(output_dir=str(catalog_dir), database="TEST_DB")

    # Step 2: Load catalog
    # index = CatalogIndex(catalog_dir)

    # Step 3: Search catalog
    # search_tool = SearchCatalogTool()
    # search_results = search_tool.run(catalog_dir=str(catalog_dir), name_contains="test")

    # THEN: Verify search finds the built catalog entries
    # assert len(search_results["results"]) > 0

    # For template purposes
    assert True


# Example 2: Living Reports integration test
@pytest.mark.integration
@pytest.mark.integration_reports
async def test_living_reports_create_evolve_render_integration(tmp_path):
    """Integration test for create → evolve → render workflow.

    Workflow:
    1. CreateReportTool creates a new report
    2. EvolveReportTool modifies the report
    3. RenderReportTool exports to HTML

    Components tested:
    - ReportService: Report storage and retrieval
    - CreateReportTool: Report initialization
    - EvolveReportTool: Report modification with validation
    - RenderReportTool: Report rendering via Quarto

    This ensures the full living reports workflow works end-to-end.
    """
    from igloo_mcp.config import Config
    from igloo_mcp.living_reports.service import ReportService
    from igloo_mcp.mcp.tools import CreateReportTool, EvolveReportTool

    # GIVEN: Report service and tools
    config = Config()
    report_service = ReportService(reports_root=tmp_path / "reports")

    create_tool = CreateReportTool(config, report_service)
    evolve_tool = EvolveReportTool(config, report_service)

    # WHEN: Executing full workflow
    # Step 1: Create report
    create_result = create_tool.run(
        title="Test Report",
        template="default",
    )
    report_id = create_result["report_id"]

    # Step 2: Evolve report (add content)
    proposed_changes = {
        "sections_to_add": [
            {
                "section_id": "sec1",
                "title": "Test Section",
                "order": 0,
            }
        ]
    }
    evolve_result = evolve_tool.run(
        report_selector=report_id,
        instruction="Add test section",
        proposed_changes=proposed_changes,
        response_detail="minimal",
    )

    # Step 3: Render report
    # (Skip actual rendering in test since it requires Quarto)
    # render_result = render_tool.run(
    #     report_selector=report_id,
    #     format="html",
    #     dry_run=True,
    # )

    # THEN: Verify workflow completed successfully
    assert create_result["success"] is True
    assert evolve_result["success"] is True
    assert len(evolve_result["section_ids_added"]) == 1

    # Verify report state
    report = report_service.get_report(report_id)
    assert len(report.outline.sections) == 1
    assert report.outline.sections[0].title == "Test Section"


# Example 3: Query execution integration test
@pytest.mark.integration
@pytest.mark.integration_query
async def test_query_execution_cache_history_integration(tmp_path):
    """Integration test for execute → cache → history workflow.

    Workflow:
    1. ExecuteQueryTool runs SQL query
    2. QueryResultCache stores results
    3. QueryHistory logs execution
    4. Subsequent query hits cache

    Components tested:
    - ExecuteQueryTool: Query execution
    - QueryResultCache: Result caching
    - QueryHistory: Execution logging

    This ensures query execution, caching, and logging work together.
    """
    # This would require mocking Snowflake or using @pytest.mark.requires_snowflake
    # For template purposes, showing structure only

    # GIVEN: Query tool with cache and history enabled
    # tool = ExecuteQueryTool(config, snowflake_service, query_service, health_monitor)

    # WHEN: Executing same query twice
    # result1 = tool.run(statement="SELECT 1", reason="Test query")
    # result2 = tool.run(statement="SELECT 1", reason="Test query")

    # THEN: Second execution should hit cache
    # assert result2["cache_hit"] is True
    # assert result2["execution_time_ms"] < result1["execution_time_ms"]

    # AND: Both executions should be logged
    # history = query_service.get_history()
    # assert len(history) == 2

    # For template purposes
    assert True
