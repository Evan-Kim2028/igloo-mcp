"""Tests for CreateReportTool MCP functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.create_report import CreateReportTool


class TestCreateReportTool:
    """Test CreateReportTool class."""

    @pytest.fixture
    def config(self):
        """Create a test config."""
        return Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))

    @pytest.fixture
    def temp_reports_dir(self):
        """Create temporary reports directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir) / "reports"
            reports_dir.mkdir()
            yield reports_dir

    @pytest.fixture
    def report_service(self, temp_reports_dir):
        """Create a ReportService instance."""
        return ReportService(reports_root=temp_reports_dir)

    @pytest.fixture
    def tool(self, config, report_service):
        """Create a CreateReportTool instance."""
        return CreateReportTool(config, report_service)

    def test_tool_properties(self, tool):
        """Test tool properties."""
        assert tool.name == "create_report"
        assert "Create a new living report" in tool.description
        assert "template" in tool.description
        assert tool.category == "reports"
        assert "reports" in tool.tags
        assert "creation" in tool.tags
        assert "templates" in tool.tags

    def test_usage_examples(self, tool):
        """Test usage examples are provided."""
        examples = tool.usage_examples
        assert len(examples) > 0
        assert all("description" in ex for ex in examples)
        assert all("parameters" in ex for ex in examples)

    def test_parameter_schema(self, tool):
        """Test parameter schema structure."""
        schema = tool.get_parameter_schema()
        assert schema["type"] == "object"
        assert "title" in schema
        assert "properties" in schema
        assert "title" in schema["properties"]
        assert "template" in schema["properties"]
        assert "tags" in schema["properties"]
        assert "description" in schema["properties"]
        assert schema["required"] == ["title"]

    @pytest.mark.asyncio
    async def test_create_report_basic(self, tool, report_service):
        """Test basic report creation."""
        result = await tool.execute(title="Test Report")

        assert result["status"] == "success"
        assert "report_id" in result
        assert result["title"] == "Test Report"
        assert result["template"] == "default"
        assert result["tags"] == []

        # Verify report exists
        outline = report_service.get_report_outline(result["report_id"])
        assert outline.title == "Test Report"

    @pytest.mark.asyncio
    async def test_create_report_with_template(self, tool, report_service):
        """Test report creation with template."""
        result = await tool.execute(title="Sales Report", template="monthly_sales")

        assert result["status"] == "success"
        assert result["template"] == "monthly_sales"

        # Verify template sections were applied
        outline = report_service.get_report_outline(result["report_id"])
        assert len(outline.sections) > 0

    @pytest.mark.asyncio
    async def test_create_report_with_tags(self, tool):
        """Test report creation with tags."""
        result = await tool.execute(
            title="Tagged Report", tags=["q1", "revenue", "sales"]
        )

        assert result["status"] == "success"
        assert result["tags"] == ["q1", "revenue", "sales"]

    @pytest.mark.asyncio
    async def test_create_report_with_description(self, tool, report_service):
        """Test report creation with description."""
        result = await tool.execute(
            title="Described Report", description="This is a test report description"
        )

        assert result["status"] == "success"

        # Verify description is in metadata
        outline = report_service.get_report_outline(result["report_id"])
        assert (
            outline.metadata.get("description") == "This is a test report description"
        )

    @pytest.mark.asyncio
    async def test_create_report_full_metadata(self, tool, report_service):
        """Test report creation with all optional parameters."""
        result = await tool.execute(
            title="Complete Report",
            template="quarterly_review",
            tags=["q1", "business"],
            description="Complete quarterly business review",
        )

        assert result["status"] == "success"
        assert result["template"] == "quarterly_review"
        assert result["tags"] == ["q1", "business"]

        # Verify all metadata
        outline = report_service.get_report_outline(result["report_id"])
        assert (
            outline.metadata.get("description") == "Complete quarterly business review"
        )
        assert outline.metadata.get("template") == "quarterly_review"
        assert outline.metadata.get("tags") == ["q1", "business"]

    @pytest.mark.asyncio
    async def test_create_report_invalid_template(self, tool):
        """Test report creation with invalid template raises MCPValidationError."""
        from igloo_mcp.mcp.exceptions import MCPValidationError

        with pytest.raises(MCPValidationError) as exc_info:
            await tool.execute(
                title="Invalid Template Report", template="nonexistent_template"
            )

        assert "Invalid template" in str(exc_info.value)
        assert "nonexistent_template" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_report_actor_is_agent(self, tool, report_service):
        """Test that reports created via MCP tool have actor='agent' in audit trail."""
        result = await tool.execute(title="Agent Report")

        # Check audit trail
        storage = report_service.global_storage.get_report_storage(result["report_id"])
        events = storage.load_audit_events()

        # Find create event
        create_event = next((e for e in events if e.action_type == "create"), None)
        assert create_event is not None
        assert create_event.actor == "agent"

    @pytest.mark.asyncio
    async def test_create_report_index_synchronization(self, tool, report_service):
        """Test that created reports are immediately available in index."""
        result = await tool.execute(title="Index Test Report")

        # Verify report is in index
        reports = report_service.list_reports()
        report_ids = [r["id"] for r in reports]
        assert result["report_id"] in report_ids

    def test_parameter_schema_matches_implementation(self, tool):
        """Test that parameter schema matches actual implementation."""
        schema = tool.get_parameter_schema()

        # Check required fields
        assert "title" in schema["required"]

        # Check template enum values
        template_prop = schema["properties"]["template"]
        assert template_prop["enum"] == [
            "default",
            "monthly_sales",
            "quarterly_review",
            "deep_dive",
            "analyst_v1",
        ]
        assert template_prop["default"] == "default"

        # Check tags type
        tags_prop = schema["properties"]["tags"]
        assert tags_prop["type"] == "array"
        assert tags_prop["items"]["type"] == "string"
