"""Tests for evolve_report_batch MCP tool.

Tests the new batch evolution tool that allows multiple report operations
to be performed atomically in a single call.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.exceptions import MCPExecutionError, MCPSelectorError, MCPValidationError
from igloo_mcp.mcp.tools.evolve_report_batch import (
    OP_ADD_INSIGHT,
    OP_ADD_SECTION,
    OP_MODIFY_INSIGHT,
    OP_MODIFY_SECTION,
    OP_REMOVE_INSIGHT,
    OP_REMOVE_SECTION,
    OP_UPDATE_METADATA,
    OP_UPDATE_TITLE,
    VALID_OPERATIONS,
    EvolveReportBatchTool,
)


@pytest.fixture
def config():
    """Create test configuration."""
    return Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))


@pytest.fixture
def report_service(tmp_path: Path):
    """Create report service with temp storage."""
    return ReportService(reports_root=tmp_path / "reports")


@pytest.fixture
def batch_tool(config, report_service):
    """Create batch evolve report tool instance."""
    return EvolveReportBatchTool(config, report_service)


@pytest.fixture
def test_report_id(report_service):
    """Create a test report and return its ID."""
    return report_service.create_report(
        title="Test Report for Batch",
        template="default",
        tags=["test", "batch"],
    )


@pytest.fixture
def test_report_with_content(report_service):
    """Create a test report with existing sections and insights."""
    report_id = report_service.create_report(
        title="Report with Content",
        template="default",
    )

    # Add a section and insight manually
    outline = report_service.get_report_outline(report_id)

    from igloo_mcp.living_reports.models import Insight, Section

    insight_id = str(uuid.uuid4())
    section_id = str(uuid.uuid4())

    outline.insights.append(
        Insight(
            insight_id=insight_id,
            summary="Existing insight",
            importance=5,
            supporting_queries=[],
            citations=[],
        )
    )
    outline.sections.append(
        Section(
            section_id=section_id,
            title="Existing Section",
            order=0,
            insight_ids=[insight_id],
        )
    )

    report_service.update_report_outline(report_id, outline)

    return {
        "report_id": report_id,
        "section_id": section_id,
        "insight_id": insight_id,
    }


class TestEvolveReportBatchToolProperties:
    """Test tool properties and metadata."""

    def test_tool_name(self, batch_tool):
        """Test tool name is correct."""
        assert batch_tool.name == "evolve_report_batch"

    def test_tool_description(self, batch_tool):
        """Test tool description is informative."""
        assert "multiple" in batch_tool.description.lower()
        assert "atomic" in batch_tool.description.lower()

    def test_tool_category(self, batch_tool):
        """Test tool category."""
        assert batch_tool.category == "reports"

    def test_tool_tags(self, batch_tool):
        """Test tool tags include expected values."""
        assert "batch" in batch_tool.tags
        assert "atomic" in batch_tool.tags
        assert "reports" in batch_tool.tags

    def test_parameter_schema(self, batch_tool):
        """Test parameter schema structure."""
        schema = batch_tool.get_parameter_schema()

        assert schema["type"] == "object"
        assert "report_selector" in schema["properties"]
        assert "instruction" in schema["properties"]
        assert "operations" in schema["properties"]
        assert "dry_run" in schema["properties"]

        # Required fields
        assert "report_selector" in schema["required"]
        assert "instruction" in schema["required"]
        assert "operations" in schema["required"]


class TestEvolveReportBatchValidation:
    """Test validation of batch operations."""

    @pytest.mark.asyncio
    async def test_empty_operations_rejected(self, batch_tool, test_report_id):
        """Empty operations list should be rejected."""
        with pytest.raises(MCPValidationError) as exc_info:
            await batch_tool.execute(
                report_selector=test_report_id,
                instruction="Test empty ops",
                operations=[],
            )

        # Check for "no operations" or "empty" in error message
        error_msg = str(exc_info.value).lower()
        assert "no operations" in error_msg or "empty" in error_msg

    @pytest.mark.asyncio
    async def test_invalid_operation_type_rejected(self, batch_tool, test_report_id):
        """Invalid operation type should be rejected."""
        with pytest.raises(MCPValidationError) as exc_info:
            await batch_tool.execute(
                report_selector=test_report_id,
                instruction="Test invalid op",
                operations=[
                    {"type": "invalid_operation_type"},
                ],
            )

        assert "invalid" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_missing_type_field_rejected(self, batch_tool, test_report_id):
        """Operation without type field should be rejected."""
        with pytest.raises(MCPValidationError) as exc_info:
            await batch_tool.execute(
                report_selector=test_report_id,
                instruction="Test missing type",
                operations=[
                    {"summary": "Missing type field"},
                ],
            )

        # Check for "type" or "invalid" in error message
        error_msg = str(exc_info.value).lower()
        assert "type" in error_msg or "invalid" in error_msg

    @pytest.mark.asyncio
    async def test_invalid_response_detail_rejected(self, batch_tool, test_report_id):
        """Invalid response_detail should be rejected."""
        with pytest.raises(MCPValidationError) as exc_info:
            await batch_tool.execute(
                report_selector=test_report_id,
                instruction="Test invalid response_detail",
                operations=[{"type": OP_ADD_SECTION, "title": "Test", "order": 0}],
                response_detail="invalid_level",
            )

        assert "response_detail" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_report_not_found_error(self, batch_tool):
        """Non-existent report should raise selector, execution, or value error."""
        with pytest.raises((MCPSelectorError, MCPExecutionError, ValueError)):
            await batch_tool.execute(
                report_selector="nonexistent-report-id",
                instruction="Test not found",
                operations=[{"type": OP_ADD_SECTION, "title": "Test", "order": 0}],
            )


class TestEvolveReportBatchOperations:
    """Test actual batch operations."""

    @pytest.mark.asyncio
    async def test_add_single_insight(self, batch_tool, test_report_id, report_service):
        """Test adding a single insight via batch."""
        result = await batch_tool.execute(
            report_selector=test_report_id,
            instruction="Add single insight",
            operations=[
                {
                    "type": OP_ADD_INSIGHT,
                    "summary": "New insight from batch",
                    "importance": 8,
                    "supporting_queries": [],  # Required field
                },
            ],
            constraints={"skip_citation_validation": True},
        )

        assert result["status"] == "success"
        assert result["batch_info"]["operation_count"] == 1

        # Verify insight was added
        outline = report_service.get_report_outline(test_report_id)
        assert len(outline.insights) == 1
        assert outline.insights[0].summary == "New insight from batch"

    @pytest.mark.asyncio
    async def test_add_multiple_insights_atomic(self, batch_tool, test_report_id, report_service):
        """Test adding multiple insights atomically."""
        result = await batch_tool.execute(
            report_selector=test_report_id,
            instruction="Add multiple insights",
            operations=[
                {"type": OP_ADD_INSIGHT, "summary": "First insight", "importance": 9, "supporting_queries": []},
                {"type": OP_ADD_INSIGHT, "summary": "Second insight", "importance": 7, "supporting_queries": []},
                {"type": OP_ADD_INSIGHT, "summary": "Third insight", "importance": 5, "supporting_queries": []},
            ],
            constraints={"skip_citation_validation": True},
        )

        assert result["status"] == "success"
        assert result["batch_info"]["operation_count"] == 3

        # Verify all insights were added
        outline = report_service.get_report_outline(test_report_id)
        assert len(outline.insights) == 3

    @pytest.mark.asyncio
    async def test_add_section_with_insights(self, batch_tool, test_report_id, report_service):
        """Test adding a section with insights atomically."""
        insight_id = str(uuid.uuid4())

        result = await batch_tool.execute(
            report_selector=test_report_id,
            instruction="Add section with insight",
            operations=[
                {
                    "type": OP_ADD_INSIGHT,
                    "insight_id": insight_id,
                    "summary": "Insight for new section",
                    "importance": 8,
                    "supporting_queries": [],
                },
                {
                    "type": OP_ADD_SECTION,
                    "title": "New Section",
                    "order": 0,
                    "insight_ids_to_add": [insight_id],  # Use insight_ids_to_add, not insight_ids
                },
            ],
            constraints={"skip_citation_validation": True},
        )

        assert result["status"] == "success"

        # Verify both insight and section were added
        outline = report_service.get_report_outline(test_report_id)
        assert len(outline.insights) == 1
        assert len(outline.sections) == 1
        assert insight_id in outline.sections[0].insight_ids

    @pytest.mark.asyncio
    async def test_modify_existing_section(self, batch_tool, test_report_with_content, report_service):
        """Test modifying an existing section."""
        report_id = test_report_with_content["report_id"]
        section_id = test_report_with_content["section_id"]

        result = await batch_tool.execute(
            report_selector=report_id,
            instruction="Modify section title",
            operations=[
                {
                    "type": OP_MODIFY_SECTION,
                    "section_id": section_id,
                    "title": "Updated Section Title",
                },
            ],
        )

        assert result["status"] == "success"

        # Verify section was modified
        outline = report_service.get_report_outline(report_id)
        section = next(s for s in outline.sections if s.section_id == section_id)
        assert section.title == "Updated Section Title"

    @pytest.mark.asyncio
    async def test_remove_insight(self, batch_tool, test_report_with_content, report_service):
        """Test removing an insight."""
        report_id = test_report_with_content["report_id"]
        insight_id = test_report_with_content["insight_id"]

        result = await batch_tool.execute(
            report_selector=report_id,
            instruction="Remove insight",
            operations=[
                {
                    "type": OP_REMOVE_INSIGHT,
                    "insight_id": insight_id,
                },
            ],
        )

        assert result["status"] == "success"

        # Verify insight was removed
        outline = report_service.get_report_outline(report_id)
        assert len(outline.insights) == 0

    @pytest.mark.asyncio
    async def test_dry_run_validates_without_applying(self, batch_tool, test_report_id, report_service):
        """Test dry_run mode validates but doesn't apply changes."""
        result = await batch_tool.execute(
            report_selector=test_report_id,
            instruction="Dry run test",
            operations=[
                {"type": OP_ADD_INSIGHT, "summary": "Should not be added", "importance": 5, "supporting_queries": []},
            ],
            dry_run=True,
        )

        assert result["status"] == "dry_run_success"
        assert result["validation_passed"] is True

        # Verify no changes were made
        outline = report_service.get_report_outline(test_report_id)
        assert len(outline.insights) == 0

    @pytest.mark.asyncio
    async def test_batch_summary_counts_correct(self, batch_tool, test_report_id):
        """Test batch summary has correct operation counts."""
        result = await batch_tool.execute(
            report_selector=test_report_id,
            instruction="Multiple ops",
            operations=[
                {"type": OP_ADD_INSIGHT, "summary": "Insight 1", "importance": 5, "supporting_queries": []},
                {"type": OP_ADD_INSIGHT, "summary": "Insight 2", "importance": 6, "supporting_queries": []},
                {"type": OP_ADD_SECTION, "title": "Section 1", "order": 0},
            ],
            constraints={"skip_citation_validation": True},
        )

        assert result["status"] == "success"
        assert result["batch_info"]["operation_count"] == 3
        assert result["batch_info"]["operations_summary"][OP_ADD_INSIGHT] == 2
        assert result["batch_info"]["operations_summary"][OP_ADD_SECTION] == 1


class TestOperationsToProposedChanges:
    """Test the _operations_to_proposed_changes conversion."""

    def test_add_insight_conversion(self, batch_tool):
        """Test add_insight operation is converted correctly."""
        operations = [
            {"type": OP_ADD_INSIGHT, "summary": "Test", "importance": 5},
        ]

        changes = batch_tool._operations_to_proposed_changes(operations)

        assert len(changes["insights_to_add"]) == 1
        assert changes["insights_to_add"][0]["summary"] == "Test"
        assert changes["insights_to_add"][0]["importance"] == 5
        # Auto-generated ID should be present
        assert "insight_id" in changes["insights_to_add"][0]

    def test_add_section_conversion(self, batch_tool):
        """Test add_section operation is converted correctly."""
        operations = [
            {"type": OP_ADD_SECTION, "title": "Test Section", "order": 1},
        ]

        changes = batch_tool._operations_to_proposed_changes(operations)

        assert len(changes["sections_to_add"]) == 1
        assert changes["sections_to_add"][0]["title"] == "Test Section"
        assert changes["sections_to_add"][0]["order"] == 1
        # Auto-generated ID should be present
        assert "section_id" in changes["sections_to_add"][0]

    def test_modify_insight_conversion(self, batch_tool):
        """Test modify_insight operation is converted correctly."""
        insight_id = str(uuid.uuid4())
        operations = [
            {"type": OP_MODIFY_INSIGHT, "insight_id": insight_id, "importance": 10},
        ]

        changes = batch_tool._operations_to_proposed_changes(operations)

        assert len(changes["insights_to_modify"]) == 1
        assert changes["insights_to_modify"][0]["insight_id"] == insight_id
        assert changes["insights_to_modify"][0]["importance"] == 10

    def test_remove_operations_conversion(self, batch_tool):
        """Test remove operations are converted correctly."""
        insight_id = str(uuid.uuid4())
        section_id = str(uuid.uuid4())

        operations = [
            {"type": OP_REMOVE_INSIGHT, "insight_id": insight_id},
            {"type": OP_REMOVE_SECTION, "section_id": section_id},
        ]

        changes = batch_tool._operations_to_proposed_changes(operations)

        assert insight_id in changes["insights_to_remove"]
        assert section_id in changes["sections_to_remove"]

    def test_update_title_conversion(self, batch_tool):
        """Test update_title operation is converted correctly."""
        operations = [
            {"type": OP_UPDATE_TITLE, "title": "New Report Title"},
        ]

        changes = batch_tool._operations_to_proposed_changes(operations)

        assert changes["title_change"] == "New Report Title"

    def test_update_metadata_conversion(self, batch_tool):
        """Test update_metadata operation is converted correctly."""
        operations = [
            {"type": OP_UPDATE_METADATA, "metadata": {"key": "value", "priority": "high"}},
        ]

        changes = batch_tool._operations_to_proposed_changes(operations)

        assert changes["metadata_updates"]["key"] == "value"
        assert changes["metadata_updates"]["priority"] == "high"


class TestOperationConstants:
    """Test operation constants are correctly defined."""

    def test_all_operations_in_valid_set(self):
        """All operation constants should be in VALID_OPERATIONS."""
        assert OP_ADD_INSIGHT in VALID_OPERATIONS
        assert OP_MODIFY_INSIGHT in VALID_OPERATIONS
        assert OP_REMOVE_INSIGHT in VALID_OPERATIONS
        assert OP_ADD_SECTION in VALID_OPERATIONS
        assert OP_MODIFY_SECTION in VALID_OPERATIONS
        assert OP_REMOVE_SECTION in VALID_OPERATIONS
        assert OP_UPDATE_TITLE in VALID_OPERATIONS
        assert OP_UPDATE_METADATA in VALID_OPERATIONS

    def test_valid_operations_count(self):
        """VALID_OPERATIONS should have exactly 8 operations."""
        assert len(VALID_OPERATIONS) == 8
