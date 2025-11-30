"""Tests for GetReportSchemaTool - schema introspection."""

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.mcp.tools.get_report_schema import GetReportSchemaTool


@pytest.mark.asyncio
class TestGetReportSchemaTool:
    """Test suite for get_report_schema tool."""

    async def test_get_proposed_changes_json_schema(self):
        """Test JSON schema format for proposed_changes."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        tool = GetReportSchemaTool(config)

        result = await tool.execute(
            schema_type="proposed_changes",
            format="json_schema",
        )

        assert result["status"] == "success"
        assert result["schema_type"] == "proposed_changes"
        assert "json_schema" in result
        assert "schema_version" in result

        # Verify schema structure
        schema = result["json_schema"]
        assert "properties" in schema
        assert "insights_to_add" in schema["properties"]
        assert "sections_to_add" in schema["properties"]

    async def test_get_examples_format(self):
        """Test examples format returns copy-paste-ready payloads."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        tool = GetReportSchemaTool(config)

        result = await tool.execute(
            schema_type="proposed_changes",
            format="examples",
        )

        assert result["status"] == "success"
        assert result["schema_type"] == "proposed_changes"
        assert "examples" in result

        # Verify examples structure
        examples = result["examples"]
        assert "add_insight" in examples
        assert "add_section_with_insights" in examples
        assert "modify_insight" in examples

        # Verify example has valid structure
        add_insight = examples["add_insight"]
        assert "proposed_changes" in add_insight
        assert "insights_to_add" in add_insight["proposed_changes"]

    async def test_get_compact_format(self):
        """Test compact format returns quick reference."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        tool = GetReportSchemaTool(config)

        result = await tool.execute(
            schema_type="proposed_changes",
            format="compact",
        )

        assert result["status"] == "success"
        assert result["schema_type"] == "proposed_changes"
        assert "quick_reference" in result

        # Verify compact structure
        ref = result["quick_reference"]
        assert "insights_to_add" in ref
        assert "sections_to_add" in ref
        assert "status_change" in ref
        assert isinstance(ref["insights_to_add"], str)

    async def test_get_all_schemas(self):
        """Test retrieving all schemas at once."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        tool = GetReportSchemaTool(config)

        result = await tool.execute(
            schema_type="all",
            format="json_schema",
        )

        assert result["status"] == "success"
        assert result["schema_type"] == "all"
        assert "schemas" in result

        # Verify all expected schemas are present
        schemas = result["schemas"]
        assert "proposed_changes" in schemas
        assert "insight" in schemas
        assert "section" in schemas
        assert "outline" in schemas

    async def test_get_insight_schema(self):
        """Test retrieving insight model schema."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        tool = GetReportSchemaTool(config)

        result = await tool.execute(
            schema_type="insight",
            format="json_schema",
        )

        assert result["status"] == "success"
        assert result["schema_type"] == "insight"
        assert "json_schema" in result

        schema = result["json_schema"]
        assert "properties" in schema
        assert "insight_id" in schema["properties"]
        assert "summary" in schema["properties"]
        assert "importance" in schema["properties"]

    async def test_invalid_schema_type(self):
        """Test that invalid schema_type raises validation error."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        tool = GetReportSchemaTool(config)

        from igloo_mcp.mcp.exceptions import MCPValidationError

        with pytest.raises(MCPValidationError) as exc_info:
            await tool.execute(
                schema_type="invalid_type",
                format="json_schema",
            )

        assert "Invalid schema_type" in str(exc_info.value)

    async def test_invalid_format(self):
        """Test that invalid format raises validation error."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        tool = GetReportSchemaTool(config)

        from igloo_mcp.mcp.exceptions import MCPValidationError

        with pytest.raises(MCPValidationError) as exc_info:
            await tool.execute(
                schema_type="proposed_changes",
                format="invalid_format",
            )

        assert "Invalid format" in str(exc_info.value)

    async def test_examples_have_valid_structure(self):
        """Test that example payloads are valid against schema."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        tool = GetReportSchemaTool(config)

        # Get the schema
        _ = await tool.execute(
            schema_type="proposed_changes",
            format="json_schema",
        )

        # Get the examples
        examples_result = await tool.execute(
            schema_type="proposed_changes",
            format="examples",
        )

        # Verify examples can be validated against schema
        from igloo_mcp.living_reports.changes_schema import ProposedChanges

        for _example_name, example_data in examples_result["examples"].items():
            if "proposed_changes" in example_data:
                # This should not raise validation errors
                ProposedChanges(**example_data["proposed_changes"])

    async def test_compact_format_all_schemas(self):
        """Test compact format with all schemas."""
        config = Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))
        tool = GetReportSchemaTool(config)

        result = await tool.execute(
            schema_type="all",
            format="compact",
        )

        assert result["status"] == "success"
        assert result["schema_type"] == "all"
        assert "quick_reference" in result

        ref = result["quick_reference"]
        assert "proposed_changes" in ref
        assert "insight" in ref
        assert "section" in ref
