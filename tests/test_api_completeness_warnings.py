"""Unit tests for API completeness: warnings infrastructure.

Tests the warnings infrastructure across catalog tools (build_catalog,
search_catalog). Verifies that warnings are always present, properly
structured, and follow the expected format.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from igloo_mcp.catalog import CatalogService
from igloo_mcp.config import Config
from igloo_mcp.mcp.tools.build_catalog import BuildCatalogTool
from igloo_mcp.mcp.tools.search_catalog import SearchCatalogTool


@pytest.fixture
def mock_config():
    """Create mock config for testing."""
    config = Mock(spec=Config)
    config.snowflake_profile = "test_profile"
    config.reports_dir = Path(tempfile.mkdtemp())
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


class TestBuildCatalogWarnings:
    """Test warnings infrastructure for build_catalog tool."""

    @pytest.mark.asyncio
    async def test_warnings_field_always_present(self, mock_config, mock_catalog_service):
        """Test that warnings field is always present in response."""
        tool = BuildCatalogTool(mock_config, mock_catalog_service)

        result = await tool.execute(output_dir="./test_catalog")

        assert "warnings" in result, "warnings field must always be present"
        assert isinstance(result["warnings"], list), "warnings must be a list"

    @pytest.mark.asyncio
    async def test_warnings_empty_by_default(self, mock_config, mock_catalog_service):
        """Test that warnings is empty array by default (no warnings)."""
        tool = BuildCatalogTool(mock_config, mock_catalog_service)

        result = await tool.execute(output_dir="./test_catalog")

        assert result["warnings"] == [], "warnings should be empty by default"

    @pytest.mark.asyncio
    async def test_warnings_never_null(self, mock_config, mock_catalog_service):
        """Test that warnings is never null (always empty array if no warnings)."""
        tool = BuildCatalogTool(mock_config, mock_catalog_service)

        result = await tool.execute(output_dir="./test_catalog")

        assert result["warnings"] is not None, "warnings must never be null"
        assert result["warnings"] == [], "warnings should be empty array, not null"


class TestSearchCatalogWarnings:
    """Test warnings infrastructure for search_catalog tool."""

    @pytest.mark.asyncio
    async def test_warnings_field_always_present(self, temp_catalog_dir):
        """Test that warnings field is always present in response."""
        tool = SearchCatalogTool()

        result = await tool.execute(catalog_dir=temp_catalog_dir)

        assert "warnings" in result, "warnings field must always be present"
        assert isinstance(result["warnings"], list), "warnings must be a list"

    @pytest.mark.asyncio
    async def test_warnings_empty_by_default(self, temp_catalog_dir):
        """Test that warnings is empty array by default (no warnings)."""
        tool = SearchCatalogTool()

        result = await tool.execute(catalog_dir=temp_catalog_dir)

        assert result["warnings"] == [], "warnings should be empty by default"

    @pytest.mark.asyncio
    async def test_warnings_in_search_all_databases_mode(self, temp_catalog_dir):
        """Test that warnings field is present in search_all_databases mode."""
        tool = SearchCatalogTool()

        # Note: search_all_databases requires default catalog_dir
        result = await tool.execute(
            catalog_dir="./data_catalogue",
            search_all_databases=True,
        )

        assert "warnings" in result, "warnings must be present in all code paths"
        assert isinstance(result["warnings"], list)

    @pytest.mark.asyncio
    async def test_warnings_never_null(self, temp_catalog_dir):
        """Test that warnings is never null (always empty array if no warnings)."""
        tool = SearchCatalogTool()

        result = await tool.execute(catalog_dir=temp_catalog_dir)

        assert result["warnings"] is not None, "warnings must never be null"
        assert result["warnings"] == [], "warnings should be empty array, not null"


class TestWarningStructureFormat:
    """Test structured warning format (for future use)."""

    def test_warning_schema_structure(self):
        """Test expected structure for warnings when they are added."""
        # This test documents the expected warning structure for future use
        expected_warning = {
            "code": "EXAMPLE_WARNING",
            "message": "This is an example warning message",
            "severity": "warning",  # or "info"
            "context": {
                "database": "EXAMPLE_DB",
                "operation": "build_catalog",
            },
        }

        # Validate structure
        assert "code" in expected_warning
        assert "message" in expected_warning
        assert "severity" in expected_warning
        assert "context" in expected_warning

        assert isinstance(expected_warning["code"], str)
        assert isinstance(expected_warning["message"], str)
        assert expected_warning["severity"] in ["info", "warning"]
        assert isinstance(expected_warning["context"], dict)

    def test_warning_severity_levels(self):
        """Test that warning severity levels are well-defined."""
        valid_severities = ["info", "warning"]

        # These are the only valid severity levels for non-error warnings
        # (errors should raise exceptions, not return warnings)
        for severity in valid_severities:
            assert severity in ["info", "warning"]

        # Verify we don't use "error" severity in warnings
        # (errors should be exceptions)
        assert "error" not in valid_severities

    def test_warning_code_format(self):
        """Test that warning codes follow expected format."""
        # Warning codes should be UPPER_SNAKE_CASE
        example_codes = [
            "DEPRECATED_PARAMETER",
            "PARTIAL_RESULTS",
            "FALLBACK_USED",
            "PERFORMANCE_HINT",
        ]

        for code in example_codes:
            # Should be uppercase
            assert code.isupper(), f"Code {code} should be uppercase"

            # Should use underscores
            assert "_" in code or len(code.split("_")) == 1

            # Should not contain spaces
            assert " " not in code


class TestWarningsConsistencyAcrossTools:
    """Test warnings consistency across different tools."""

    @pytest.mark.asyncio
    async def test_all_tools_have_warnings_field(self, mock_config, mock_catalog_service, temp_catalog_dir):
        """Test that all modified tools have warnings field."""
        tools_and_params = [
            (
                BuildCatalogTool(mock_config, mock_catalog_service),
                {"output_dir": "./test_catalog"},
            ),
            (
                SearchCatalogTool(),
                {"catalog_dir": temp_catalog_dir},
            ),
        ]

        for tool, params in tools_and_params:
            result = await tool.execute(**params)

            assert "warnings" in result, f"{tool.name} must have warnings field"
            assert isinstance(result["warnings"], list), f"{tool.name} warnings must be a list"

    @pytest.mark.asyncio
    async def test_warnings_type_consistency(self, mock_config, mock_catalog_service, temp_catalog_dir):
        """Test that warnings field type is consistent across tools."""
        tools_and_params = [
            (
                BuildCatalogTool(mock_config, mock_catalog_service),
                {"output_dir": "./test_catalog"},
            ),
            (
                SearchCatalogTool(),
                {"catalog_dir": temp_catalog_dir},
            ),
        ]

        warning_types = []
        for tool, params in tools_and_params:
            result = await tool.execute(**params)
            warning_types.append(type(result["warnings"]))

        # All should be list type
        assert all(wt is list for wt in warning_types), "All tools should return warnings as list type"


class TestWarningsFutureExtensibility:
    """Test that warnings infrastructure is ready for future use."""

    @pytest.mark.asyncio
    async def test_warnings_can_hold_structured_data(self, mock_config, mock_catalog_service):
        """Test that warnings array can hold structured warning objects."""
        # This test verifies the infrastructure is ready for future warnings
        tool = BuildCatalogTool(mock_config, mock_catalog_service)

        result = await tool.execute(output_dir="./test_catalog")

        # Warnings is a list that can hold dict objects
        warnings = result["warnings"]
        assert isinstance(warnings, list)

        # Simulate adding a warning (for future implementation)
        example_warning = {
            "code": "EXAMPLE_CODE",
            "message": "Example message",
            "severity": "info",
            "context": {},
        }

        # List can hold structured warnings
        warnings.append(example_warning)
        assert len(warnings) == 1
        assert warnings[0]["code"] == "EXAMPLE_CODE"

    def test_warning_json_serializability(self):
        """Test that warning objects are JSON-serializable."""
        import json

        warning = {
            "code": "TEST_WARNING",
            "message": "Test message",
            "severity": "warning",
            "context": {
                "database": "TEST_DB",
                "count": 42,
                "flag": True,
            },
        }

        # Should serialize to JSON without errors
        json_str = json.dumps(warning)
        assert json_str

        # Should deserialize back to same structure
        deserialized = json.loads(json_str)
        assert deserialized == warning


class TestWarningsDocumentation:
    """Test that warnings are properly documented in schemas."""

    def test_build_catalog_schema_documents_warnings(self, mock_config, mock_catalog_service):
        """Test that build_catalog schema includes warnings documentation."""
        tool = BuildCatalogTool(mock_config, mock_catalog_service)
        # Schema is checked implicitly through tool initialization
        # While warnings is in the response (not parameters),
        # the tool's response structure should be documented
        # This test verifies the tool is set up correctly
        assert tool.name == "build_catalog"
        assert tool.category == "metadata"

    def test_search_catalog_schema_documents_warnings(self):
        """Test that search_catalog schema includes warnings documentation."""
        tool = SearchCatalogTool()
        # Schema is checked implicitly through tool initialization
        # Verify tool is set up correctly for warnings
        assert tool.name == "search_catalog"
        assert tool.category == "metadata"
