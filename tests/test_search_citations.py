"""Tests for search_citations MCP tool."""

import uuid

import pytest

from igloo_mcp.config import get_config
from igloo_mcp.living_reports.models import Citation, Insight
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.search_citations import SearchCitationsTool


@pytest.fixture
def search_tool(tmp_path):
    """Create SearchCitationsTool with temporary report service."""
    config = get_config()
    report_service = ReportService(reports_root=tmp_path / "reports")
    return SearchCitationsTool(config, report_service), report_service


@pytest.fixture
def sample_reports(tmp_path):
    """Create sample reports with various citation types."""
    service = ReportService(reports_root=tmp_path / "reports")

    # Report 1: Query citations
    report1_id = service.create_report("Data Analysis Report")
    outline1 = service.get_report_outline(report1_id)

    insight1 = Insight(
        insight_id=str(uuid.uuid4()),
        importance=9,
        summary="Revenue grew 25% YoY",
        citations=[
            Citation(
                source="query",
                provider="snowflake",
                execution_id="exec-123",
                description="Revenue analysis",
            )
        ],
    )
    outline1.insights.append(insight1)
    service.update_report_outline(report1_id, outline1)

    # Report 2: Mixed citations
    report2_id = service.create_report("Market Research Report")
    outline2 = service.get_report_outline(report2_id)

    insight2 = Insight(
        insight_id=str(uuid.uuid4()),
        importance=8,
        summary="TVL increased significantly",
        citations=[
            Citation(
                source="api",
                provider="defillama",
                endpoint="/tvl/monad",
                description="TVL data pull",
            ),
            Citation(
                source="url",
                url="https://monad.xyz/blog/tge",
                title="TGE Announcement",
            ),
        ],
    )
    outline2.insights.append(insight2)
    service.update_report_outline(report2_id, outline2)

    return service, [report1_id, report2_id]


@pytest.mark.asyncio
async def test_search_by_source_type(search_tool, sample_reports):
    """Test filtering citations by source type."""
    tool, _ = search_tool
    service, report_ids = sample_reports

    result = await tool.execute(source_type="query")

    assert result["status"] == "success"
    assert result["matches_found"] >= 1
    assert all(cit["citation"]["source"] == "query" for cit in result["citations"])


@pytest.mark.asyncio
async def test_search_by_provider(search_tool, sample_reports):
    """Test filtering citations by provider."""
    tool, _ = search_tool
    service, report_ids = sample_reports

    result = await tool.execute(provider="defillama")

    assert result["status"] == "success"
    assert result["matches_found"] >= 1
    assert all(cit["citation"].get("provider") == "defillama" for cit in result["citations"])


@pytest.mark.asyncio
async def test_search_url_substring(search_tool, sample_reports):
    """Test URL substring search."""
    tool, _ = search_tool
    service, report_ids = sample_reports

    result = await tool.execute(url_contains="monad.xyz")

    assert result["status"] == "success"
    assert result["matches_found"] >= 1
    assert all("monad.xyz" in cit["citation"].get("url", "").lower() for cit in result["citations"])


@pytest.mark.asyncio
async def test_search_exact_execution_id(search_tool, sample_reports):
    """Test exact execution_id match."""
    tool, _ = search_tool
    service, report_ids = sample_reports

    result = await tool.execute(execution_id="exec-123")

    assert result["status"] == "success"
    assert result["matches_found"] >= 1
    assert all(cit["citation"].get("execution_id") == "exec-123" for cit in result["citations"])


@pytest.mark.asyncio
async def test_group_by_source(search_tool, sample_reports):
    """Test grouping results by source type."""
    tool, _ = search_tool
    service, report_ids = sample_reports

    result = await tool.execute(group_by="source")

    assert result["status"] == "success"
    assert result["grouped_results"] is not None
    assert "groups" in result["grouped_results"]
    assert "summary" in result["grouped_results"]


@pytest.mark.asyncio
async def test_group_by_provider(search_tool, sample_reports):
    """Test grouping results by provider."""
    tool, _ = search_tool
    service, report_ids = sample_reports

    result = await tool.execute(group_by="provider")

    assert result["status"] == "success"
    assert result["grouped_results"] is not None
    assert "groups" in result["grouped_results"]


@pytest.mark.asyncio
async def test_empty_results_handling(search_tool, sample_reports):
    """Test handling of no matching citations."""
    tool, _ = search_tool
    service, report_ids = sample_reports

    result = await tool.execute(execution_id="nonexistent-exec")

    assert result["status"] == "success"
    assert result["matches_found"] == 0
    assert len(result["citations"]) == 0


@pytest.mark.asyncio
async def test_limit_parameter(search_tool, sample_reports):
    """Test limit parameter works correctly."""
    tool, _ = search_tool
    service, report_ids = sample_reports

    result = await tool.execute(limit=1)

    assert result["status"] == "success"
    assert result["returned"] <= 1


@pytest.mark.asyncio
async def test_invalid_source_type_raises_error(search_tool):
    """Test that invalid source_type raises validation error."""
    tool, _ = search_tool

    with pytest.raises(Exception):  # MCPValidationError
        await tool.execute(source_type="invalid")


@pytest.mark.asyncio
async def test_invalid_group_by_raises_error(search_tool):
    """Test that invalid group_by raises validation error."""
    tool, _ = search_tool

    with pytest.raises(Exception):  # MCPValidationError
        await tool.execute(group_by="invalid")


@pytest.mark.asyncio
async def test_citation_result_structure(search_tool, sample_reports):
    """Test that citation results have correct structure."""
    tool, _ = search_tool
    service, report_ids = sample_reports

    result = await tool.execute()

    assert result["status"] == "success"
    if result["matches_found"] > 0:
        first_result = result["citations"][0]
        assert "citation" in first_result
        assert "insight" in first_result
        assert "report" in first_result

        assert "insight_id" in first_result["insight"]
        assert "summary" in first_result["insight"]
        assert "importance" in first_result["insight"]

        assert "report_id" in first_result["report"]
        assert "title" in first_result["report"]
