"""Tests for evolve_report MCP tool."""

from __future__ import annotations

import uuid
from unittest.mock import Mock

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.living_reports.models import Insight, Outline, ReportId, Section
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool


@pytest.mark.asyncio
class TestEvolveReportTool:
    """Test EvolveReportTool functionality."""

    @pytest.fixture
    def config(self) -> Config:
        """Create test config."""
        return Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))

    @pytest.fixture
    def mock_service(self) -> Mock:
        """Create mock report service."""
        service = Mock(spec=ReportService)
        return service

    @pytest.fixture
    def tool(self, config: Config, mock_service: Mock) -> EvolveReportTool:
        """Create test tool instance."""
        return EvolveReportTool(config, mock_service)

    @pytest.fixture
    def sample_outline(self) -> Outline:
        """Create sample outline for testing."""
        return Outline(
            report_id=str(ReportId.new()),
            title="Test Report",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            sections=[
                Section(
                    section_id=str(uuid.uuid4()),
                    title="Test Section",
                    order=0,
                    insight_ids=[],
                )
            ],
            insights=[],
        )

    def test_tool_properties(self, tool: EvolveReportTool) -> None:
        """Test tool properties."""
        assert tool.name == "evolve_report"
        assert "Evolve a living report" in tool.description
        assert tool.category == "reports"
        assert "reports" in tool.tags
        assert "evolution" in tool.tags
        assert isinstance(tool.usage_examples, list)
        assert tool.usage_examples

    def test_parameter_schema(self, tool: EvolveReportTool) -> None:
        """Test parameter schema generation."""
        schema = tool.get_parameter_schema()

        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert schema["required"] == ["report_selector", "instruction"]

        props = schema["properties"]
        assert "report_selector" in props
        assert "instruction" in props
        assert "constraints" in props
        assert "dry_run" in props

    @pytest.mark.asyncio
    async def test_execute_dry_run(
        self, tool: EvolveReportTool, mock_service: Mock, sample_outline: Outline
    ) -> None:
        """Test execute with dry run."""
        mock_service.resolve_report_selector.return_value = sample_outline.report_id
        mock_service.get_report_outline.return_value = sample_outline

        result = await tool.execute(
            report_selector="test-report",
            instruction="Add a new insight",
            dry_run=True,
        )

        assert result["status"] == "dry_run_success"
        assert result["report_id"] == sample_outline.report_id
        assert "proposed_changes" in result

        mock_service.update_report_outline.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_changes(
        self, tool: EvolveReportTool, mock_service: Mock, sample_outline: Outline
    ) -> None:
        """Test execute that applies changes."""
        mock_service.resolve_report_selector.return_value = sample_outline.report_id
        mock_service.get_report_outline.return_value = sample_outline

        result = await tool.execute(
            report_selector="test-report",
            instruction="Add a new insight",
        )

        assert result["status"] == "success"
        assert result["report_id"] == sample_outline.report_id
        assert "changes_applied" in result

        mock_service.update_report_outline.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_validation_failure(
        self, tool: EvolveReportTool, mock_service: Mock, sample_outline: Outline
    ) -> None:
        """Test execute with validation failure."""
        mock_service.resolve_report_selector.return_value = sample_outline.report_id
        mock_service.get_report_outline.return_value = sample_outline

        # Mock validation to fail
        with pytest.MonkeyPatch().context() as m:
            m.setattr(tool, "_validate_changes", lambda *args: ["Invalid change"])
            m.setattr(
                tool, "_generate_proposed_changes", lambda *args: {"invalid": "change"}
            )

            result = await tool.execute(
                report_selector="test-report",
                instruction="Invalid instruction",
            )

        assert result["status"] == "validation_failed"
        assert "validation_issues" in result

    def test_generate_proposed_changes_sample(
        self, tool: EvolveReportTool, sample_outline: Outline
    ) -> None:
        """Test generating sample proposed changes."""
        changes = tool._generate_proposed_changes(
            sample_outline,
            "Add insight about sales",
            {},
        )

        assert "type" in changes
        assert "description" in changes
        # Sample implementation may or may not add insights depending on instruction

    def test_validate_changes_valid(
        self, tool: EvolveReportTool, sample_outline: Outline
    ) -> None:
        """Test validating valid changes."""
        changes = {
            "insights_to_add": [],
            "sections_to_add": [],
            "insights_to_modify": [],
            "sections_to_modify": [],
            "insights_to_remove": [],
            "sections_to_remove": [],
        }

        issues = tool._validate_changes(sample_outline, changes)
        assert issues == []

    def test_validate_changes_invalid_insight_id(
        self, tool: EvolveReportTool, sample_outline: Outline
    ) -> None:
        """Test validating changes with invalid insight ID."""
        changes = {
            "insights_to_modify": [{"insight_id": "invalid-uuid"}],
            "insights_to_remove": [],
            "sections_to_add": [],
            "sections_to_modify": [],
            "sections_to_remove": [],
        }

        issues = tool._validate_changes(sample_outline, changes)
        assert len(issues) > 0
        assert "not found" in issues[0]

    def test_validate_changes_invalid_section_id(
        self, tool: EvolveReportTool, sample_outline: Outline
    ) -> None:
        """Test validating changes with invalid section ID."""
        changes = {
            "insights_to_add": [],
            "insights_to_modify": [],
            "insights_to_remove": [],
            "sections_to_modify": [{"section_id": "invalid-uuid"}],
            "sections_to_remove": [],
        }

        issues = tool._validate_changes(sample_outline, changes)
        assert len(issues) > 0
        assert "not found" in issues[0]

    def test_apply_changes_add_insight(
        self, tool: EvolveReportTool, sample_outline: Outline
    ) -> None:
        """Test applying changes that add an insight."""
        new_insight_id = str(uuid.uuid4())
        changes = {
            "insights_to_add": [
                {
                    "insight_id": new_insight_id,
                    "importance": 8,
                    "summary": "New insight",
                }
            ],
            "sections_to_modify": [
                {
                    "section_id": sample_outline.sections[0].section_id,
                    "insight_ids_to_add": [new_insight_id],
                }
            ],
            "insights_to_modify": [],
            "insights_to_remove": [],
            "sections_to_add": [],
            "sections_to_remove": [],
        }

        new_outline, _ = tool._apply_changes(sample_outline, changes)

        assert len(new_outline.insights) == 1
        assert new_outline.insights[0].insight_id == new_insight_id
        assert new_insight_id in new_outline.sections[0].insight_ids

    def test_apply_changes_remove_insight(self, tool: EvolveReportTool) -> None:
        """Test applying changes that remove an insight."""
        insight_id = str(uuid.uuid4())
        section_id = str(uuid.uuid4())

        outline = Outline(
            report_id=str(ReportId.new()),
            title="Test",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            sections=[
                Section(
                    section_id=section_id,
                    title="Test Section",
                    order=0,
                    insight_ids=[insight_id],
                )
            ],
            insights=[
                Insight(
                    insight_id=insight_id,
                    importance=5,
                    summary="Test insight",
                )
            ],
        )

        changes = {
            "insights_to_add": [],
            "insights_to_modify": [],
            "insights_to_remove": [insight_id],
            "sections_to_add": [],
            "sections_to_modify": [],
            "sections_to_remove": [],
        }

        new_outline, _ = tool._apply_changes(outline, changes)

        assert len(new_outline.insights) == 0
        assert insight_id not in new_outline.sections[0].insight_ids
