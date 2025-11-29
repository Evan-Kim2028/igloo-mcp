"""Unit tests for API completeness: request_id and timing functionality.

Tests the request_id generation, custom request_id passthrough, and timing
metrics across catalog and health tools (build_catalog, get_catalog_summary,
search_catalog, health).
"""

from __future__ import annotations

import re
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from igloo_mcp.catalog import CatalogService
from igloo_mcp.config import Config
from igloo_mcp.mcp.tools.build_catalog import BuildCatalogTool
from igloo_mcp.mcp.tools.get_catalog_summary import GetCatalogSummaryTool
from igloo_mcp.mcp.tools.health import HealthCheckTool
from igloo_mcp.mcp.tools.search_catalog import SearchCatalogTool

# UUID4 pattern for validation
UUID4_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


@pytest.fixture
def mock_config():
    """Create mock config for testing."""
    config = Mock(spec=Config)
    config.snowflake_profile = "test_profile"
    config.reports_dir = Path(tempfile.mkdtemp())

    # Mock nested snowflake config for health tool
    mock_snowflake = Mock()
    mock_snowflake.profile = "test_profile"
    config.snowflake = mock_snowflake

    return config


@pytest.fixture
def mock_catalog_service(mock_config):
    """Create mock catalog service."""
    service = Mock(spec=CatalogService)

    # Mock build result
    build_result = Mock()
    build_result.output_dir = "/tmp/test_catalog"
    build_result.totals = Mock(
        databases=5,
        schemas=10,
        tables=50,
        views=20,
        materialized_views=5,
        dynamic_tables=3,
        tasks=2,
        functions=15,
        procedures=8,
        columns=500,
    )
    service.build = Mock(return_value=build_result)

    return service


@pytest.fixture
def temp_catalog_dir():
    """Create temporary catalog directory with test data."""
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create catalog.json file with empty catalog structure
        catalog_data = {
            "databases": [],
            "schemas": [],
            "tables": [],
            "views": [],
            "materialized_views": [],
            "dynamic_tables": [],
            "tasks": [],
            "functions": [],
            "procedures": [],
        }
        catalog_path = Path(tmpdir) / "catalog.json"
        catalog_path.write_text(json.dumps(catalog_data))
        yield tmpdir


@pytest.fixture
def catalog_service_for_summary(mock_config):
    """Create catalog service for summary tests."""
    service = Mock(spec=CatalogService)

    # Mock get_summary to return a proper summary
    mock_summary = Mock()
    mock_summary.databases = 0
    mock_summary.schemas = 0
    mock_summary.tables = 0
    service.get_summary = Mock(return_value=mock_summary)

    return service


class TestBuildCatalogRequestIdTiming:
    """Test request_id and timing for build_catalog tool."""

    @pytest.mark.asyncio
    async def test_auto_generated_request_id(self, mock_config, mock_catalog_service):
        """Test that request_id is auto-generated when not provided."""
        tool = BuildCatalogTool(mock_config, mock_catalog_service)

        result = await tool.execute(output_dir="./test_catalog")

        assert "request_id" in result
        assert UUID4_PATTERN.match(result["request_id"])

    @pytest.mark.asyncio
    async def test_custom_request_id_passthrough(self, mock_config, mock_catalog_service):
        """Test that custom request_id is preserved."""
        tool = BuildCatalogTool(mock_config, mock_catalog_service)
        custom_id = "custom-request-123"

        result = await tool.execute(output_dir="./test_catalog", request_id=custom_id)

        assert result["request_id"] == custom_id

    @pytest.mark.asyncio
    async def test_timing_structure(self, mock_config, mock_catalog_service):
        """Test timing metrics structure and accuracy."""
        tool = BuildCatalogTool(mock_config, mock_catalog_service)

        start = time.time()
        result = await tool.execute(output_dir="./test_catalog")
        elapsed = (time.time() - start) * 1000

        assert "timing" in result
        timing = result["timing"]

        # Check structure
        assert "catalog_fetch_ms" in timing
        assert "total_duration_ms" in timing

        # Check values are positive
        assert timing["catalog_fetch_ms"] > 0
        assert timing["total_duration_ms"] > 0

        # Check total is reasonable (should be close to measured elapsed)
        assert timing["total_duration_ms"] <= elapsed + 100  # Allow 100ms buffer

        # Check breakdown makes sense
        assert timing["catalog_fetch_ms"] <= timing["total_duration_ms"]

    @pytest.mark.asyncio
    async def test_warnings_field_present(self, mock_config, mock_catalog_service):
        """Test that warnings field is always present."""
        tool = BuildCatalogTool(mock_config, mock_catalog_service)

        result = await tool.execute(output_dir="./test_catalog")

        assert "warnings" in result
        assert isinstance(result["warnings"], list)
        assert result["warnings"] == []  # Empty by default


class TestGetCatalogSummaryRequestIdTiming:
    """Test request_id and timing for get_catalog_summary tool."""

    @pytest.mark.asyncio
    async def test_auto_generated_request_id(self, catalog_service_for_summary, temp_catalog_dir):
        """Test that request_id is auto-generated when not provided."""
        tool = GetCatalogSummaryTool(catalog_service_for_summary)

        result = await tool.execute(catalog_dir=temp_catalog_dir)

        assert "request_id" in result
        assert UUID4_PATTERN.match(result["request_id"])

    @pytest.mark.asyncio
    async def test_custom_request_id_passthrough(self, catalog_service_for_summary, temp_catalog_dir):
        """Test that custom request_id is preserved."""
        tool = GetCatalogSummaryTool(catalog_service_for_summary)
        custom_id = "summary-request-456"

        result = await tool.execute(catalog_dir=temp_catalog_dir, request_id=custom_id)

        assert result["request_id"] == custom_id

    @pytest.mark.asyncio
    async def test_timing_structure_simple(self, catalog_service_for_summary, temp_catalog_dir):
        """Test timing metrics for simple operation (total only)."""
        tool = GetCatalogSummaryTool(catalog_service_for_summary)

        start = time.time()
        result = await tool.execute(catalog_dir=temp_catalog_dir)
        elapsed = (time.time() - start) * 1000

        assert "timing" in result
        timing = result["timing"]

        # Simple operation: only total_duration_ms
        assert "total_duration_ms" in timing
        assert timing["total_duration_ms"] > 0
        assert timing["total_duration_ms"] <= elapsed + 100


class TestSearchCatalogRequestIdTiming:
    """Test request_id and timing for search_catalog tool."""

    @pytest.mark.asyncio
    async def test_auto_generated_request_id(self, temp_catalog_dir):
        """Test that request_id is auto-generated when not provided."""
        tool = SearchCatalogTool()

        result = await tool.execute(catalog_dir=temp_catalog_dir)

        assert "request_id" in result
        assert UUID4_PATTERN.match(result["request_id"])

    @pytest.mark.asyncio
    async def test_custom_request_id_passthrough(self, temp_catalog_dir):
        """Test that custom request_id is preserved."""
        tool = SearchCatalogTool()
        custom_id = "search-request-789"

        result = await tool.execute(catalog_dir=temp_catalog_dir, request_id=custom_id)

        assert result["request_id"] == custom_id

    @pytest.mark.asyncio
    async def test_timing_structure_with_breakdown(self, temp_catalog_dir):
        """Test timing metrics with breakdown for search operation."""
        tool = SearchCatalogTool()

        start = time.time()
        result = await tool.execute(catalog_dir=temp_catalog_dir)
        elapsed = (time.time() - start) * 1000

        assert "timing" in result
        timing = result["timing"]

        # Search operation: breakdown + total
        assert "search_duration_ms" in timing
        assert "total_duration_ms" in timing

        assert timing["search_duration_ms"] > 0
        assert timing["total_duration_ms"] > 0
        assert timing["total_duration_ms"] <= elapsed + 100

        # Breakdown should be <= total
        assert timing["search_duration_ms"] <= timing["total_duration_ms"]

    @pytest.mark.asyncio
    async def test_warnings_field_present(self, temp_catalog_dir):
        """Test that warnings field is always present."""
        tool = SearchCatalogTool()

        result = await tool.execute(catalog_dir=temp_catalog_dir)

        assert "warnings" in result
        assert isinstance(result["warnings"], list)
        assert result["warnings"] == []


class TestHealthRequestIdTiming:
    """Test request_id and timing for health tool."""

    @pytest.mark.asyncio
    async def test_auto_generated_request_id(self, mock_config):
        """Test that request_id is auto-generated when not provided."""
        # Create mock snowflake service
        mock_sf_service = Mock()
        tool = HealthCheckTool(mock_config, mock_sf_service)

        # Mock the connection test
        async def mock_test_connection():
            return {
                "status": "connected",
                "connected": True,
                "profile": "test",
            }

        tool._test_connection = mock_test_connection

        # Disable optional checks that require additional mocking
        result = await tool.execute(include_profile=False, include_cortex=False, include_catalog=False)

        assert "request_id" in result
        assert UUID4_PATTERN.match(result["request_id"])

    @pytest.mark.asyncio
    async def test_custom_request_id_passthrough(self, mock_config):
        """Test that custom request_id is preserved."""
        mock_sf_service = Mock()
        tool = HealthCheckTool(mock_config, mock_sf_service)

        async def mock_test_connection():
            return {
                "status": "connected",
                "connected": True,
                "profile": "test",
            }

        tool._test_connection = mock_test_connection

        custom_id = "health-request-999"
        result = await tool.execute(
            request_id=custom_id,
            include_profile=False,
            include_cortex=False,
            include_catalog=False,
        )

        assert result["request_id"] == custom_id

    @pytest.mark.asyncio
    async def test_timing_structure_simple(self, mock_config):
        """Test timing metrics for health check (simple operation)."""
        mock_sf_service = Mock()
        tool = HealthCheckTool(mock_config, mock_sf_service)

        async def mock_test_connection():
            return {
                "status": "connected",
                "connected": True,
                "profile": "test",
            }

        tool._test_connection = mock_test_connection

        start = time.time()
        result = await tool.execute(include_profile=False, include_cortex=False, include_catalog=False)
        elapsed = (time.time() - start) * 1000

        assert "timing" in result
        timing = result["timing"]

        # Simple operation: only total_duration_ms
        assert "total_duration_ms" in timing
        assert timing["total_duration_ms"] > 0
        assert timing["total_duration_ms"] <= elapsed + 100


class TestRequestIdFormat:
    """Test request_id format validation across all tools."""

    @pytest.mark.asyncio
    async def test_request_id_is_valid_uuid4(
        self, mock_config, mock_catalog_service, temp_catalog_dir, catalog_service_for_summary
    ):
        """Test that auto-generated request_id follows UUID4 format."""
        tools = [
            BuildCatalogTool(mock_config, mock_catalog_service),
            GetCatalogSummaryTool(catalog_service_for_summary),
            SearchCatalogTool(),
        ]

        for tool in tools:
            if isinstance(tool, BuildCatalogTool):
                result = await tool.execute(output_dir="./test_catalog")
            else:
                result = await tool.execute(catalog_dir=temp_catalog_dir)

            request_id = result["request_id"]

            # Check UUID4 format
            assert UUID4_PATTERN.match(request_id), f"{tool.name} request_id {request_id} is not valid UUID4"

            # Check version field (9th group should start with 4)
            assert request_id[14] == "4", f"{tool.name} request_id is not UUID version 4"

            # Check variant (17th char should be 8, 9, a, or b)
            assert request_id[19] in "89ab", f"{tool.name} request_id is not RFC 4122 variant"
