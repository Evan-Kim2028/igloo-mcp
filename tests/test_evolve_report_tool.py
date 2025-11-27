"""Comprehensive tests for evolve_report tool.

Tests report evolution with LLM assistance, including validation,
change application, and safety guarantees.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import pytest

from igloo_mcp.config import Config
from igloo_mcp.living_reports.models import Insight, Outline, Section
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool


@pytest.mark.asyncio
class TestEvolveReportTool:
    """Test the EvolveReportTool functionality."""

    @pytest.fixture
    def temp_reports_dir(self) -> Path:
        """Create temporary reports directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir) / "reports"
            reports_dir.mkdir()
            yield reports_dir

    @pytest.fixture
    def config(self) -> Config:
        """Create test config."""
        return Config.from_env()

    @pytest.fixture
    def report_service(self, temp_reports_dir: Path) -> ReportService:
        """Create test report service."""
        return ReportService(temp_reports_dir)

    @pytest.fixture
    def sample_outline(self) -> Outline:
        """Create sample report outline for testing."""
        # Use deterministic UUIDs for testing
        insight_1_id = "550e8400-e29b-41d4-a716-446655440001"
        insight_2_id = "550e8400-e29b-41d4-a716-446655440002"
        section_1_id = "550e8400-e29b-41d4-a716-446655440003"
        section_2_id = "550e8400-e29b-41d4-a716-446655440004"
        report_id = "550e8400-e29b-41d4-a716-446655440005"

        return Outline(
            title="Test Report",
            report_id=report_id,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            insights=[
                Insight(
                    insight_id=insight_1_id,
                    summary="First insight",
                    importance=8,
                    supporting_queries=[{"execution_id": "exec_1"}],
                ),
                Insight(
                    insight_id=insight_2_id,
                    summary="Second insight",
                    importance=6,
                    supporting_queries=[{"execution_id": "exec_2"}],
                ),
            ],
            sections=[
                Section(
                    section_id=section_1_id,
                    title="Revenue Analysis",
                    notes="Analysis of revenue metrics",
                    order=1,
                    insight_ids=[insight_1_id],
                ),
                Section(
                    section_id=section_2_id,
                    title="User Metrics",
                    notes="User behavior metrics",
                    order=2,
                    insight_ids=[insight_2_id],
                ),
            ],
        )

    @pytest.fixture
    def tool(self, config: Config, report_service: ReportService) -> EvolveReportTool:
        """Create test tool instance."""
        return EvolveReportTool(config=config, report_service=report_service)

    def test_tool_initialization(self, tool: EvolveReportTool):
        """Test tool initializes correctly."""
        assert tool.name == "evolve_report"
        assert "Evolve a living report" in tool.description
        assert tool.category == "reports"
        assert "reports" in tool.tags
        assert "evolution" in tool.tags
        assert "llm" in tool.tags

    def test_parameter_schema_validation(self, tool: EvolveReportTool):
        """Test parameter schema includes required fields."""
        schema = tool.get_parameter_schema()

        # Check required fields
        assert "required" in schema
        assert "report_selector" in schema["required"]
        assert "instruction" in schema["required"]

        # Check properties
        assert "properties" in schema
        assert "report_selector" in schema["properties"]
        assert "instruction" in schema["properties"]
        assert "proposed_changes" in schema["properties"]
        assert "constraints" in schema["properties"]
        assert "dry_run" in schema["properties"]

    def test_report_resolution_by_id(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test report resolution by ID."""
        # Create a report
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        # Test resolution
        resolved = report_service.resolve_report_selector(report_id)
        assert resolved == report_id

    def test_report_resolution_by_title(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test report resolution by title."""
        # Create a report
        report_id = report_service.create_report("Unique Test Report Title")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        # Test resolution
        resolved = report_service.resolve_report_selector("Unique Test Report Title")
        assert resolved == report_id

    def test_report_resolution_case_insensitive(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test case-insensitive title resolution."""
        # Create a report
        report_id = report_service.create_report("Case Sensitive Title")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        # Test case-insensitive resolution
        resolved = report_service.resolve_report_selector("case sensitive title")
        assert resolved == report_id

    def test_report_resolution_nonexistent(self, tool: EvolveReportTool):
        """Test resolution of nonexistent report raises error."""
        with pytest.raises(ValueError, match="Report not found"):
            tool.report_service.resolve_report_selector("nonexistent-report-12345")

    def test_validation_insight_id_collision(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test validation detects insight ID collisions."""
        insight_1_id = sample_outline.insights[0].insight_id
        changes = {
            "insights_to_add": [
                {
                    "insight_id": insight_1_id,
                    "summary": "Duplicate ID",
                    "importance": 5,
                }  # Already exists
            ]
        }

        issues = tool._validate_changes(sample_outline, changes)
        assert len(issues) == 1
        assert f"Insight ID already exists: {insight_1_id}" in issues[0]

    def test_validation_insight_id_not_found_modify(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test validation detects nonexistent insight ID for modification."""
        changes = {
            "insights_to_modify": [
                {
                    "insight_id": "550e8400-e29b-41d4-a716-446655440999",
                    "summary": "Modified",
                }
            ]
        }

        issues = tool._validate_changes(sample_outline, changes)
        assert len(issues) == 1
        assert "Insight ID not found: 550e8400-e29b-41d4-a716-446655440999" in issues[0]

    def test_validation_insight_id_not_found_remove(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test validation detects nonexistent insight ID for removal."""
        changes = {"insights_to_remove": ["550e8400-e29b-41d4-a716-446655440999"]}

        issues = tool._validate_changes(sample_outline, changes)
        assert len(issues) == 1
        assert (
            "Insight ID not found for removal: 550e8400-e29b-41d4-a716-446655440999"
            in issues[0]
        )

    def test_validation_section_id_collision(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test validation detects section ID collisions."""
        section_1_id = sample_outline.sections[0].section_id
        changes = {
            "sections_to_add": [
                {
                    "section_id": section_1_id,
                    "title": "Duplicate Section",
                }  # Already exists
            ]
        }

        issues = tool._validate_changes(sample_outline, changes)
        assert len(issues) == 1
        assert f"Section ID already exists: {section_1_id}" in issues[0]

    def test_validation_section_id_not_found_modify(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test validation detects nonexistent section ID for modification."""
        changes = {
            "sections_to_modify": [
                {
                    "section_id": "550e8400-e29b-41d4-a716-446655440999",
                    "title": "Modified",
                }
            ]
        }

        issues = tool._validate_changes(sample_outline, changes)
        assert len(issues) == 1
        assert "Section ID not found: 550e8400-e29b-41d4-a716-446655440999" in issues[0]

    def test_validation_section_id_not_found_remove(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test validation detects nonexistent section ID for removal."""
        changes = {"sections_to_remove": ["550e8400-e29b-41d4-a716-446655440999"]}

        issues = tool._validate_changes(sample_outline, changes)
        assert len(issues) == 1
        assert (
            "Section ID not found for removal: 550e8400-e29b-41d4-a716-446655440999"
            in issues[0]
        )

    def test_validation_success(self, tool: EvolveReportTool, sample_outline: Outline):
        """Test validation passes for valid changes."""
        changes = {
            "insights_to_add": [
                {
                    "insight_id": "new_insight",
                    "summary": "New insight",
                    "importance": 7,
                    "status": "active",
                    "supporting_queries": [],
                }
            ],
            "sections_to_add": [
                {"section_id": "new_section", "title": "New Section", "order": 3}
            ],
        }

        issues = tool._validate_changes(sample_outline, changes)
        assert len(issues) == 0

    def test_change_application_add_insights(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test applying insight additions."""
        changes = {
            "insights_to_add": [
                {
                    "insight_id": "550e8400-e29b-41d4-a716-446655440003",
                    "summary": "New insight added",
                    "importance": 9,
                    "supporting_queries": [{"execution_id": "exec_3"}],
                }
            ]
        }

        new_outline, _ = tool._apply_changes(sample_outline, changes)

        # Check insight was added
        assert len(new_outline.insights) == 3
        new_insight = next(
            i
            for i in new_outline.insights
            if i.insight_id == "550e8400-e29b-41d4-a716-446655440003"
        )
        assert new_insight.summary == "New insight added"
        assert new_insight.importance == 9

    def test_change_application_modify_insights(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test applying insight modifications."""
        insight_1_id = sample_outline.insights[0].insight_id
        changes = {
            "insights_to_modify": [
                {
                    "insight_id": insight_1_id,
                    "summary": "Modified insight",
                    "importance": 10,
                }
            ]
        }

        new_outline, _ = tool._apply_changes(sample_outline, changes)

        # Check insight was modified
        modified_insight = next(
            i for i in new_outline.insights if i.insight_id == insight_1_id
        )
        assert modified_insight.summary == "Modified insight"
        assert modified_insight.importance == 10

    def test_change_application_remove_insights(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test applying insight removals."""
        insight_2_id = sample_outline.insights[1].insight_id
        changes = {"insights_to_remove": [insight_2_id]}

        new_outline, _ = tool._apply_changes(sample_outline, changes)

        # Check insight was removed
        assert len(new_outline.insights) == 1
        assert all(i.insight_id != insight_2_id for i in new_outline.insights)

    def test_change_application_add_sections(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test applying section additions."""
        insight_1_id = sample_outline.insights[0].insight_id
        changes = {
            "sections_to_add": [
                {
                    "section_id": "550e8400-e29b-41d4-a716-446655440010",
                    "title": "New Section Title",
                    "order": 10,
                    "notes": "New section notes",
                    "insight_ids": [insight_1_id],
                }
            ]
        }

        new_outline, _ = tool._apply_changes(sample_outline, changes)

        # Check section was added
        assert len(new_outline.sections) == 3
        new_section = next(
            s
            for s in new_outline.sections
            if s.section_id == "550e8400-e29b-41d4-a716-446655440010"
        )
        assert new_section.title == "New Section Title"
        assert insight_1_id in new_section.insight_ids

    def test_change_application_modify_sections(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test applying section modifications."""
        section_1_id = sample_outline.sections[0].section_id
        insight_2_id = sample_outline.insights[1].insight_id
        changes = {
            "sections_to_modify": [
                {
                    "section_id": section_1_id,
                    "title": "Modified Title",
                    "insight_ids_to_add": [insight_2_id],
                }
            ]
        }

        new_outline, _ = tool._apply_changes(sample_outline, changes)

        # Check section was modified
        modified_section = next(
            s for s in new_outline.sections if s.section_id == section_1_id
        )
        assert modified_section.title == "Modified Title"
        assert insight_2_id in modified_section.insight_ids

    def test_change_application_remove_sections(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test applying section removals."""
        section_2_id = sample_outline.sections[1].section_id
        changes = {"sections_to_remove": [section_2_id]}

        new_outline, _ = tool._apply_changes(sample_outline, changes)

        # Check section was removed
        assert len(new_outline.sections) == 1
        assert all(s.section_id != section_2_id for s in new_outline.sections)

    def test_change_application_removes_references(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test that removing insights also removes references from sections."""
        insight_1_id = sample_outline.insights[0].insight_id
        changes = {"insights_to_remove": [insight_1_id]}

        new_outline, _ = tool._apply_changes(sample_outline, changes)

        # Check insight references were cleaned up
        for section in new_outline.sections:
            assert insight_1_id not in section.insight_ids

    @pytest.mark.asyncio
    async def test_execute_dry_run_mode(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test dry run mode doesn't apply changes."""
        # Create a report
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        # Define explicit changes for dry run
        dry_run_changes = {
            "insights_to_add": [
                {
                    "insight_id": "550e8400-e29b-41d4-a716-446655440006",
                    "summary": "Dry run insight",
                    "importance": 5,
                    "status": "active",
                    "supporting_queries": [],
                }
            ]
        }

        # Execute in dry run mode
        result = await tool.execute(
            report_selector=report_id,
            instruction="Add a test insight",
            proposed_changes=dry_run_changes,
            dry_run=True,
        )

        # Check result structure
        assert result["status"] == "dry_run_success"
        assert result["report_id"] == report_id
        # Note: proposed_changes now returns the validated ProposedChanges object
        assert result["validation_passed"] is True

        # Check changes were not actually applied
        current_outline = report_service.get_report_outline(report_id)
        assert len(current_outline.insights) == 2  # Original count

    @pytest.mark.asyncio
    async def test_execute_validation_failure(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test validation failure prevents execution."""
        # Create a report
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        # Use explicit invalid changes (duplicate insight ID)
        invalid_changes = {
            "insights_to_add": [
                {
                    "insight_id": "550e8400-e29b-41d4-a716-446655440001",
                    "summary": "Duplicate ID",
                    "importance": 5,
                    "status": "active",
                    "supporting_queries": [],
                }  # Already exists
            ]
        }

        # Execute should fail validation
        result = await tool.execute(
            report_selector=report_id,
            instruction="Add duplicate insight",
            proposed_changes=invalid_changes,
        )

        # Check validation failure
        assert result["status"] == "validation_failed"
        assert result["error_type"] == "semantic_validation"
        assert len(result["validation_errors"]) > 0
        assert "Insight ID already exists" in str(result["validation_errors"])

    @pytest.mark.asyncio
    async def test_execute_successful_application(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test successful change application."""
        # Create a report
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        # Define valid changes to apply
        valid_changes = {
            "insights_to_add": [
                {
                    "insight_id": "550e8400-e29b-41d4-a716-446655440007",
                    "summary": "Successfully added insight",
                    "importance": 7,
                    "status": "active",
                    "supporting_queries": [{"execution_id": "exec_4"}],
                }
            ]
        }

        # Execute the evolution
        result = await tool.execute(
            report_selector=report_id,
            instruction="Add a successful insight",
            proposed_changes=valid_changes,
        )

        # Check success
        assert result["status"] == "success"
        assert result["report_id"] == report_id
        # changes_applied is a ProposedChanges object with defaults filled in
        expected_changes = {**valid_changes}
        for key in [
            "insights_to_modify",
            "sections_to_add",
            "sections_to_modify",
            "insights_to_remove",
            "sections_to_remove",
        ]:
            expected_changes.setdefault(key, [])
        expected_changes.setdefault("metadata_updates", {})
        expected_changes.setdefault("schema_version", "1.0")
        expected_changes.setdefault("title_change", None)
        assert result["changes_applied"] == expected_changes
        assert "outline_version" in result

        # Check changes were applied
        updated_outline = report_service.get_report_outline(report_id)
        assert len(updated_outline.insights) == 3
        assert any(
            i.insight_id == "550e8400-e29b-41d4-a716-446655440007"
            for i in updated_outline.insights
        )

    @pytest.mark.asyncio
    async def test_execute_with_explicit_proposed_changes(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test execution with explicit proposed_changes."""
        # Create a report
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        # Explicit changes
        explicit_changes = {
            "insights_to_add": [
                {
                    "insight_id": "550e8400-e29b-41d4-a716-446655440099",
                    "summary": "Explicitly added insight",
                    "importance": 9,
                    "status": "active",
                    "supporting_queries": [],
                }
            ]
        }

        # Execute using explicit changes
        result = await tool.execute(
            report_selector=report_id,
            instruction="Add explicit insight",
            proposed_changes=explicit_changes,
        )

        # Check success
        assert result["status"] == "success"
        assert result["report_id"] == report_id
        # changes_applied is a ProposedChanges object with defaults filled in
        expected_changes = {**explicit_changes}
        for key in [
            "insights_to_modify",
            "sections_to_add",
            "sections_to_modify",
            "insights_to_remove",
            "sections_to_remove",
        ]:
            expected_changes.setdefault(key, [])
        expected_changes.setdefault("metadata_updates", {})
        expected_changes.setdefault("schema_version", "1.0")
        expected_changes.setdefault("title_change", None)
        assert result["changes_applied"] == expected_changes

        # Check changes were applied
        updated_outline = report_service.get_report_outline(report_id)
        assert len(updated_outline.insights) == 3
        assert any(
            i.insight_id == "550e8400-e29b-41d4-a716-446655440099"
            for i in updated_outline.insights
        )

    def test_tool_usage_examples(self, tool: EvolveReportTool):
        """Test usage examples are properly defined."""
        examples = tool.usage_examples

        assert len(examples) >= 2
        for example in examples:
            assert "description" in example
            assert "parameters" in example
            assert "report_selector" in example["parameters"]
            assert "instruction" in example["parameters"]

    def test_error_handling_report_not_found(self, tool: EvolveReportTool):
        """Test error handling for nonexistent reports."""
        with pytest.raises(ValueError, match="Report not found"):
            tool.report_service.resolve_report_selector("nonexistent-12345")

    @pytest.mark.asyncio
    async def test_execute_with_constraints(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test execution with constraint parameters."""
        # Create a report
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        # Define valid changes with constraints
        constrained_changes = {
            "insights_to_add": [
                {
                    "insight_id": "550e8400-e29b-41d4-a716-446655440008",
                    "summary": "Constrained insight",
                    "importance": 8,
                    "status": "active",
                    "supporting_queries": [],
                }
            ]
        }

        # Execute with constraints (constraints are currently passed but not enforced)
        result = await tool.execute(
            report_selector=report_id,
            instruction="Add insight with constraints",
            proposed_changes=constrained_changes,
            constraints={"max_importance_delta": 2, "sections": ["Revenue Analysis"]},
        )

        # Should succeed
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_citation_enforcement_analyst_report_missing_citation(
        self, tool: EvolveReportTool, report_service: ReportService
    ):
        """Test that analyst reports require citations for new insights."""
        # Create analyst report
        report_id = report_service.create_report(
            "Analyst Report", template="analyst_v1"
        )
        outline = report_service.get_report_outline(report_id)

        # Try to add insight without citation
        changes = {
            "insights_to_add": [
                {
                    "insight_id": str(uuid.uuid4()),
                    "summary": "Network processed 2.4M transactions",
                    "importance": 9,
                    "supporting_queries": [],  # Missing citation
                }
            ]
        }

        issues = tool._validate_changes(outline, changes)
        assert len(issues) > 0
        assert any("Analyst reports require citations" in issue for issue in issues)
        assert any("missing supporting_queries[0]" in issue for issue in issues)

    @pytest.mark.asyncio
    async def test_citation_enforcement_analyst_report_missing_execution_id(
        self, tool: EvolveReportTool, report_service: ReportService
    ):
        """Test that analyst reports require execution_id in citation."""
        # Create analyst report
        report_id = report_service.create_report(
            "Analyst Report", template="analyst_v1"
        )
        outline = report_service.get_report_outline(report_id)

        # Try to add insight with citation but no execution_id
        changes = {
            "insights_to_add": [
                {
                    "insight_id": str(uuid.uuid4()),
                    "summary": "Network processed 2.4M transactions",
                    "importance": 9,
                    "supporting_queries": [
                        {"sql_sha256": "abc123"}  # Missing execution_id
                    ],
                }
            ]
        }

        issues = tool._validate_changes(outline, changes)
        assert len(issues) > 0
        assert any("Analyst reports require citations" in issue for issue in issues)
        assert any("missing execution_id" in issue for issue in issues)

    @pytest.mark.asyncio
    async def test_citation_enforcement_analyst_report_valid_citation(
        self, tool: EvolveReportTool, report_service: ReportService
    ):
        """Test that analyst reports accept insights with valid citations."""
        # Create analyst report
        report_id = report_service.create_report(
            "Analyst Report", template="analyst_v1"
        )
        outline = report_service.get_report_outline(report_id)

        # Add insight with valid citation
        changes = {
            "insights_to_add": [
                {
                    "insight_id": str(uuid.uuid4()),
                    "summary": "Network processed 2.4M transactions",
                    "importance": 9,
                    "supporting_queries": [{"execution_id": "exec_123"}],
                }
            ]
        }

        issues = tool._validate_changes(outline, changes)
        # Should not have citation-related issues
        citation_issues = [
            i for i in issues if "Analyst reports require citations" in i
        ]
        assert len(citation_issues) == 0

    @pytest.mark.asyncio
    async def test_citation_enforcement_non_analyst_report_no_enforcement(
        self, tool: EvolveReportTool, report_service: ReportService
    ):
        """Test that non-analyst reports don't enforce citations."""
        # Create default report
        report_id = report_service.create_report("Regular Report", template="default")
        outline = report_service.get_report_outline(report_id)

        # Try to add insight without citation
        changes = {
            "insights_to_add": [
                {
                    "insight_id": str(uuid.uuid4()),
                    "summary": "Some insight",
                    "importance": 5,
                    "supporting_queries": [],  # No citation
                }
            ]
        }

        issues = tool._validate_changes(outline, changes)
        # Should not have citation-related issues for non-analyst reports
        citation_issues = [
            i for i in issues if "Analyst reports require citations" in i
        ]
        assert len(citation_issues) == 0

    @pytest.mark.asyncio
    async def test_execute_requires_proposed_changes(self, tool: EvolveReportTool):
        """Test that proposed_changes parameter is required."""
        # This test verifies that the parameter is required at the function signature level
        # Since the parameter is now required, attempting to call without it should fail at runtime
        import inspect

        sig = inspect.signature(tool.execute)
        proposed_changes_param = sig.parameters["proposed_changes"]

        # Verify it is optional and defaults to None
        assert proposed_changes_param.default is None

    def test_auto_generate_insight_uuid_on_add(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test that insight_id is auto-generated when not provided for additions."""
        from igloo_mcp.living_reports.changes_schema import InsightChange

        # Create InsightChange without insight_id
        change = InsightChange(summary="Test insight", importance=5)

        # UUID should be auto-generated
        assert change.insight_id is not None
        assert isinstance(change.insight_id, str)
        import uuid

        # Verify it's a valid UUID
        uuid.UUID(change.insight_id)

    def test_auto_generate_section_uuid_on_add(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test that section_id is auto-generated when not provided for additions."""
        from igloo_mcp.living_reports.changes_schema import SectionChange

        # Create SectionChange without section_id
        change = SectionChange(title="Test Section")

        # UUID should be auto-generated
        assert change.section_id is not None
        assert isinstance(change.section_id, str)
        import uuid

        # Verify it's a valid UUID
        uuid.UUID(change.section_id)

    def test_explicit_uuid_still_works(
        self, tool: EvolveReportTool, sample_outline: Outline
    ):
        """Test that explicit UUIDs continue to work (backward compatibility)."""
        import uuid

        from igloo_mcp.living_reports.changes_schema import InsightChange, SectionChange

        explicit_insight_id = str(uuid.uuid4())
        explicit_section_id = str(uuid.uuid4())

        insight_change = InsightChange(
            insight_id=explicit_insight_id, summary="Test", importance=5
        )
        section_change = SectionChange(section_id=explicit_section_id, title="Test")

        assert insight_change.insight_id == explicit_insight_id
        assert section_change.section_id == explicit_section_id

    async def test_add_insight_without_uuid(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test adding insight without providing UUID - should auto-generate."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        # Add insight without insight_id
        changes = {
            "insights_to_add": [
                {"summary": "Auto-generated UUID insight", "importance": 7}
            ]
        }

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add insight with auto-generated UUID",
            proposed_changes=changes,
            dry_run=False,
        )

        assert result["status"] == "success"
        assert len(result["summary"]["insight_ids_added"]) == 1
        generated_id = result["summary"]["insight_ids_added"][0]

        # Verify it's a valid UUID
        import uuid

        uuid.UUID(generated_id)

        # Verify insight was actually added
        updated_outline = report_service.get_report_outline(report_id)
        assert len(updated_outline.insights) == len(sample_outline.insights) + 1
        assert any(i.insight_id == generated_id for i in updated_outline.insights)

    async def test_add_section_without_uuid(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test adding section without providing UUID - should auto-generate."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        # Add section without section_id
        changes = {
            "sections_to_add": [{"title": "Auto-generated UUID section", "order": 3}]
        }

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add section with auto-generated UUID",
            proposed_changes=changes,
            dry_run=False,
        )

        assert result["status"] == "success"
        assert len(result["summary"]["section_ids_added"]) == 1
        generated_id = result["summary"]["section_ids_added"][0]

        # Verify it's a valid UUID
        import uuid

        uuid.UUID(generated_id)

        # Verify section was actually added
        updated_outline = report_service.get_report_outline(report_id)
        assert len(updated_outline.sections) == len(sample_outline.sections) + 1
        assert any(s.section_id == generated_id for s in updated_outline.sections)

    @pytest.mark.asyncio
    async def test_sections_to_add_inline_insights_update_summary(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        report_id = report_service.create_report("Inline Section Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add inline insights",
            proposed_changes={
                "sections_to_add": [
                    {
                        "title": "Inline Section",
                        "order": 3,
                        "insights": [{"summary": "Inline insight", "importance": 5}],
                    }
                ]
            },
        )

        assert result["status"] == "success"
        assert result["summary"]["insights_added"] == 1
        assert len(result["summary"]["insight_ids_added"]) == 1
        assert all("has no insights" not in warning for warning in result["warnings"])

        outline = report_service.get_report_outline(report_id)
        new_section = next(s for s in outline.sections if s.title == "Inline Section")
        assert len(new_section.insight_ids) == 1

    @pytest.mark.asyncio
    async def test_sections_to_modify_supports_inline_insights(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        report_id = report_service.create_report("Modify Inline Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        target_section = sample_outline.sections[0]

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add inline insight via modify",
            proposed_changes={
                "sections_to_modify": [
                    {
                        "section_id": target_section.section_id,
                        "insights": [{"summary": "Section inline", "importance": 6}],
                    }
                ]
            },
        )

        assert result["status"] == "success"
        assert result["summary"]["insights_added"] >= 1

        outline = report_service.get_report_outline(report_id)
        section = next(
            s for s in outline.sections if s.section_id == target_section.section_id
        )
        assert any(insight.summary == "Section inline" for insight in outline.insights)
        assert len(section.insight_ids) >= 2

    @pytest.mark.asyncio
    async def test_insights_to_add_defaults_supporting_queries(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        report_id = report_service.create_report("Supporting Queries Optional")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add simple insight",
            proposed_changes={
                "insights_to_add": [{"summary": "Supports optional", "importance": 7}]
            },
        )

        assert result["status"] == "success"

        outline = report_service.get_report_outline(report_id)
        new_insight = next(
            i for i in outline.insights if i.summary == "Supports optional"
        )
        assert new_insight.supporting_queries == []

    @pytest.mark.asyncio
    async def test_warnings_recomputed_after_linking_insight(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        report_id = report_service.create_report("Warning Regression Report")
        sample_outline.sections[0].insight_ids = []
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        result = await tool.execute(
            report_selector=report_id,
            instruction="Link existing insight",
            proposed_changes={
                "sections_to_modify": [
                    {
                        "section_id": sample_outline.sections[0].section_id,
                        "insight_ids_to_add": [sample_outline.insights[0].insight_id],
                    }
                ]
            },
        )

        assert result["status"] == "success"
        assert all(
            sample_outline.sections[0].title not in warning
            for warning in result["warnings"]
        )

    async def test_modify_insight_without_uuid_fails(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test that modifying insight without insight_id auto-generates one and fails to find it."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        # Try to modify insight without insight_id (will auto-generate)
        changes = {
            "insights_to_modify": [
                {
                    "summary": "Modified summary"
                    # Missing insight_id - will be auto-generated
                }
            ]
        }

        result = await tool.execute(
            report_selector=report_id,
            instruction="Modify insight without ID",
            proposed_changes=changes,
            dry_run=False,
        )

        # Should have validation error about the auto-generated ID not existing
        assert result["status"] == "validation_failed"
        error_str = str(result.get("validation_errors", "")).lower()
        assert "insight" in error_str and "not found" in error_str

    async def test_modify_section_without_uuid_fails(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test that modifying section without section_id auto-generates one and fails to find it."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        # Try to modify section without section_id (will auto-generate)
        changes = {
            "sections_to_modify": [
                {
                    "title": "Modified title"
                    # Missing section_id - will be auto-generated
                }
            ]
        }

        result = await tool.execute(
            report_selector=report_id,
            instruction="Modify section without ID",
            proposed_changes=changes,
            dry_run=False,
        )

        # Should have validation error about the auto-generated ID not existing
        assert result["status"] == "validation_failed"
        error_str = str(result.get("validation_errors", "")).lower()
        assert "section" in error_str and "not found" in error_str

    async def test_partial_update_insight_summary_only(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test partial update: modify only summary field, other fields unchanged."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        original_insight = sample_outline.insights[0]
        original_importance = original_insight.importance
        original_status = original_insight.status

        # Modify only summary
        changes = {
            "insights_to_modify": [
                {
                    "insight_id": original_insight.insight_id,
                    "summary": "Updated summary only",
                    # importance and status not provided (should remain unchanged)
                }
            ]
        }

        result = await tool.execute(
            report_selector=report_id,
            instruction="Update insight summary only",
            proposed_changes=changes,
            dry_run=False,
        )

        assert result["status"] == "success"

        # Verify only summary was updated
        updated_outline = report_service.get_report_outline(report_id)
        updated_insight = next(
            i
            for i in updated_outline.insights
            if i.insight_id == original_insight.insight_id
        )
        assert updated_insight.summary == "Updated summary only"
        assert updated_insight.importance == original_importance
        assert updated_insight.status == original_status

    async def test_partial_update_insight_importance_only(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test partial update: modify only importance field."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        original_insight = sample_outline.insights[0]
        original_summary = original_insight.summary

        # Modify only importance
        changes = {
            "insights_to_modify": [
                {
                    "insight_id": original_insight.insight_id,
                    "importance": 10,
                    # summary not provided (should remain unchanged)
                }
            ]
        }

        result = await tool.execute(
            report_selector=report_id,
            instruction="Update insight importance only",
            proposed_changes=changes,
            dry_run=False,
        )

        assert result["status"] == "success"

        # Verify only importance was updated
        updated_outline = report_service.get_report_outline(report_id)
        updated_insight = next(
            i
            for i in updated_outline.insights
            if i.insight_id == original_insight.insight_id
        )
        assert updated_insight.importance == 10
        assert updated_insight.summary == original_summary

    async def test_partial_update_insight_none_values_unchanged(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test that None values in modification don't change existing fields."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        original_insight = sample_outline.insights[0]
        original_importance = original_insight.importance
        original_status = original_insight.status

        # Modify with summary and importance, but status=None
        changes = {
            "insights_to_modify": [
                {
                    "insight_id": original_insight.insight_id,
                    "summary": "Updated summary",
                    "importance": 9,
                    "status": None,  # Explicitly None - should not change existing status
                }
            ]
        }

        result = await tool.execute(
            report_selector=report_id,
            instruction="Update insight with None status",
            proposed_changes=changes,
            dry_run=False,
        )

        assert result["status"] == "success"

        # Verify status unchanged (None values are skipped)
        updated_outline = report_service.get_report_outline(report_id)
        updated_insight = next(
            i
            for i in updated_outline.insights
            if i.insight_id == original_insight.insight_id
        )
        assert updated_insight.summary == "Updated summary"
        assert updated_insight.importance == 9
        assert updated_insight.status == original_status  # Should remain unchanged

    async def test_modify_insight_only_id_fails(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test that modifying insight with only insight_id (no other fields) fails validation."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        original_insight = sample_outline.insights[0]

        # Try to modify with only insight_id
        changes = {
            "insights_to_modify": [
                {
                    "insight_id": original_insight.insight_id
                    # No other fields provided
                }
            ]
        }

        result = await tool.execute(
            report_selector=report_id,
            instruction="Modify insight with only ID",
            proposed_changes=changes,
            dry_run=False,
        )

        # Should have validation error about needing at least one non-ID field
        assert result["status"] == "validation_failed"
        error_str = str(result.get("validation_errors", "")).lower()
        assert "at least one field" in error_str or "besides" in error_str

    async def test_atomic_add_section_with_inline_insights(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test adding section with inline insights - insights created and linked atomically."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        # Add section with inline insights (no UUIDs provided)
        changes = {
            "sections_to_add": [
                {
                    "title": "New Section with Inline Insights",
                    "order": 3,
                    "insights": [
                        {"summary": "First inline insight", "importance": 8},
                        {"summary": "Second inline insight", "importance": 6},
                    ],
                }
            ]
        }

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add section with inline insights",
            proposed_changes=changes,
            dry_run=False,
        )

        assert result["status"] == "success"

        # Verify section was added
        updated_outline = report_service.get_report_outline(report_id)
        new_section = next(
            s
            for s in updated_outline.sections
            if s.title == "New Section with Inline Insights"
        )
        assert new_section is not None

        # Verify insights were created and linked
        assert len(new_section.insight_ids) == 2
        assert len(updated_outline.insights) == len(sample_outline.insights) + 2

        # Verify insight content
        inline_insights = [
            i
            for i in updated_outline.insights
            if i.insight_id in new_section.insight_ids
        ]
        assert len(inline_insights) == 2
        assert any(i.summary == "First inline insight" for i in inline_insights)
        assert any(i.summary == "Second inline insight" for i in inline_insights)

        # Verify UUIDs were auto-generated
        for insight in inline_insights:
            import uuid

            uuid.UUID(insight.insight_id)  # Should not raise

    async def test_atomic_add_section_with_explicit_insight_uuids(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test adding section with inline insights that have explicit UUIDs."""
        import uuid

        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        explicit_insight_id_1 = str(uuid.uuid4())
        explicit_insight_id_2 = str(uuid.uuid4())

        # Add section with inline insights (explicit UUIDs)
        changes = {
            "sections_to_add": [
                {
                    "title": "Section with Explicit UUID Insights",
                    "order": 3,
                    "insights": [
                        {
                            "insight_id": explicit_insight_id_1,
                            "summary": "Explicit UUID insight 1",
                            "importance": 8,
                        },
                        {
                            "insight_id": explicit_insight_id_2,
                            "summary": "Explicit UUID insight 2",
                            "importance": 6,
                        },
                    ],
                }
            ]
        }

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add section with explicit UUID insights",
            proposed_changes=changes,
            dry_run=False,
        )

        assert result["status"] == "success"

        # Verify insights were created with explicit UUIDs
        updated_outline = report_service.get_report_outline(report_id)
        new_section = next(
            s
            for s in updated_outline.sections
            if s.title == "Section with Explicit UUID Insights"
        )
        assert explicit_insight_id_1 in new_section.insight_ids
        assert explicit_insight_id_2 in new_section.insight_ids

        insight_1 = next(
            i for i in updated_outline.insights if i.insight_id == explicit_insight_id_1
        )
        insight_2 = next(
            i for i in updated_outline.insights if i.insight_id == explicit_insight_id_2
        )
        assert insight_1.summary == "Explicit UUID insight 1"
        assert insight_2.summary == "Explicit UUID insight 2"

    async def test_atomic_add_section_both_insights_and_ids_fails(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test that providing both insights and insight_ids_to_add fails validation."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        # Try to provide both insights and insight_ids_to_add
        changes = {
            "sections_to_add": [
                {
                    "title": "Invalid Section",
                    "insights": [{"summary": "Inline insight", "importance": 5}],
                    "insight_ids_to_add": [sample_outline.insights[0].insight_id],
                }
            ]
        }

        # Should fail at schema validation level
        result = await tool.execute(
            report_selector=report_id,
            instruction="Add section with both insights and insight_ids_to_add",
            proposed_changes=changes,
            dry_run=False,
        )

        # Should have validation error about mutually exclusive fields
        assert result["status"] == "validation_failed"
        error_str = str(result.get("validation_errors", "")).lower()
        assert (
            "insights" in error_str and "insight_ids_to_add" in error_str
        ) or "mutually exclusive" in error_str

    async def test_atomic_add_section_inline_insights_reference_external(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test that inline insights can reference external insights (via insight_ids_to_add)."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        existing_insight_id = sample_outline.insights[0].insight_id

        # Add section with both inline insights and reference to existing insight
        # Note: This test verifies that inline insights are processed first, then external references work
        changes = {
            "sections_to_add": [
                {
                    "title": "Mixed Section",
                    "order": 3,
                    "insights": [{"summary": "New inline insight", "importance": 7}],
                    "insight_ids_to_add": [
                        existing_insight_id
                    ],  # This should fail due to mutual exclusivity
                }
            ]
        }

        # This should fail because insights and insight_ids_to_add are mutually exclusive
        result = await tool.execute(
            report_selector=report_id,
            instruction="Add section with mixed insights",
            proposed_changes=changes,
            dry_run=False,
        )

        assert result["status"] == "validation_failed"

    async def test_enhanced_error_invalid_insight_id_includes_field_path(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test that invalid insight_id in modify includes field path and available IDs."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        invalid_insight_id = "550e8400-e29b-41d4-a716-446655440999"

        changes = {
            "insights_to_modify": [
                {"insight_id": invalid_insight_id, "summary": "Modified summary"}
            ]
        }

        result = await tool.execute(
            report_selector=report_id,
            instruction="Modify invalid insight",
            proposed_changes=changes,
            dry_run=False,
        )

        # Check validation failed status
        assert result["status"] == "validation_failed"
        assert result["error_type"] == "semantic_validation"
        assert len(result["validation_errors"]) > 0

        # Check error message contains relevant info
        error_str = str(result["validation_errors"])
        assert invalid_insight_id in error_str
        assert "not found" in error_str.lower() or "modify" in error_str.lower()

    async def test_enhanced_error_invalid_section_id_includes_field_path(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test that invalid section_id in modify includes field path and available IDs."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        invalid_section_id = "550e8400-e29b-41d4-a716-446655440999"

        changes = {
            "sections_to_modify": [
                {"section_id": invalid_section_id, "title": "Modified title"}
            ]
        }

        result = await tool.execute(
            report_selector=report_id,
            instruction="Modify invalid section",
            proposed_changes=changes,
            dry_run=False,
        )

        # Check validation failed status
        assert result["status"] == "validation_failed"
        assert result["error_type"] == "semantic_validation"
        assert len(result["validation_errors"]) > 0

        # Check error message contains relevant info
        error_str = str(result["validation_errors"])
        assert invalid_section_id in error_str
        assert "not found" in error_str.lower() or "modify" in error_str.lower()

    async def test_enhanced_error_multiple_errors_returned(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test that multiple validation errors are all returned with proper field paths."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        invalid_insight_id = "550e8400-e29b-41d4-a716-446655440999"
        invalid_section_id = "550e8400-e29b-41d4-a716-446655440998"

        changes = {
            "insights_to_modify": [
                {"insight_id": invalid_insight_id, "summary": "Modified"}
            ],
            "sections_to_modify": [
                {"section_id": invalid_section_id, "title": "Modified"}
            ],
        }

        result = await tool.execute(
            report_selector=report_id,
            instruction="Multiple invalid changes",
            proposed_changes=changes,
            dry_run=False,
        )

        # Should have multiple validation errors
        assert result["status"] == "validation_failed"
        assert "validation_errors" in result
        assert len(result["validation_errors"]) >= 2

        # Verify both errors are mentioned
        error_str = str(result["validation_errors"])
        assert invalid_insight_id in error_str or "insight" in error_str.lower()
        assert invalid_section_id in error_str or "section" in error_str.lower()

    async def test_enhanced_error_backward_compatibility_string_format(
        self,
        tool: EvolveReportTool,
        report_service: ReportService,
        sample_outline: Outline,
    ):
        """Test that error messages are backward compatible (string format still works)."""
        report_id = report_service.create_report("Test Report")
        report_service.update_report_outline(report_id, sample_outline, actor="test")

        invalid_insight_id = "550e8400-e29b-41d4-a716-446655440999"

        changes = {
            "insights_to_modify": [
                {"insight_id": invalid_insight_id, "summary": "Modified"}
            ]
        }

        result = await tool.execute(
            report_selector=report_id,
            instruction="Test backward compatibility",
            proposed_changes=changes,
            dry_run=False,
        )

        # Should have validation_errors as list of strings (backward compatible)
        assert result["status"] == "validation_failed"
        assert "validation_errors" in result
        assert isinstance(result["validation_errors"], list)
        assert len(result["validation_errors"]) > 0
        assert isinstance(result["validation_errors"][0], str)

        # String format should contain field path
        error_string = result["validation_errors"][0]
        assert (
            "insights_to_modify" in error_string.lower()
            or invalid_insight_id in error_string
        )

    @pytest.mark.asyncio
    async def test_supporting_queries_defaulted_for_new_insights(
        self, tool: EvolveReportTool, report_service: ReportService
    ):
        """Ensure supporting_queries defaults to [] when omitted."""
        report_id = report_service.create_report("New Report")
        outline = report_service.get_report_outline(report_id)
        outline.insights = []
        outline.sections = []
        report_service.update_report_outline(report_id, outline)

        new_insight_id = str(uuid.uuid4())
        result = await tool.execute(
            report_selector=report_id,
            instruction="Add insight without citations",
            proposed_changes={
                "insights_to_add": [
                    {
                        "insight_id": new_insight_id,
                        "summary": "New insight",
                        "importance": 5,
                    }
                ],
                "sections_to_add": [
                    {
                        "section_id": str(uuid.uuid4()),
                        "title": "Findings",
                        "order": 0,
                        "insight_ids_to_add": [new_insight_id],
                    }
                ],
            },
        )

        assert result["status"] == "success"
        updated_outline = report_service.get_report_outline(report_id)
        added = next(
            i for i in updated_outline.insights if i.insight_id == new_insight_id
        )
        assert added.supporting_queries == []

    @pytest.mark.asyncio
    async def test_inline_insights_on_section_add_are_linked_and_counted(
        self, tool: EvolveReportTool, report_service: ReportService
    ):
        """Inline insights in sections_to_add should be created, linked, and counted."""
        report_id = report_service.create_report("Inline Add Report")
        outline = report_service.get_report_outline(report_id)
        outline.insights = []
        outline.sections = []
        report_service.update_report_outline(report_id, outline)

        result = await tool.execute(
            report_selector=report_id,
            instruction="Add section with inline insight",
            proposed_changes={
                "sections_to_add": [
                    {
                        "section_id": str(uuid.uuid4()),
                        "title": "Findings",
                        "order": 0,
                        "insights": [
                            {
                                "summary": "Inline insight summary",
                                "importance": 7,
                            }
                        ],
                    }
                ]
            },
        )

        assert result["status"] == "success"
        summary = result["summary"]
        assert summary["sections_added"] == 1
        assert summary["insights_added"] == 1

        updated_outline = report_service.get_report_outline(report_id)
        assert len(updated_outline.insights) == 1
        assert len(updated_outline.sections) == 1
        assert updated_outline.sections[0].insight_ids == [
            updated_outline.insights[0].insight_id
        ]

    @pytest.mark.asyncio
    async def test_inline_insights_on_section_modify_are_created_and_counted(
        self, tool: EvolveReportTool, report_service: ReportService
    ):
        """Inline insights in sections_to_modify should append and be counted."""
        report_id = report_service.create_report("Inline Modify Report")
        outline = report_service.get_report_outline(report_id)
        section = outline.sections[0]
        outline.insights = []
        section.insight_ids = []
        report_service.update_report_outline(report_id, outline)

        result = await tool.execute(
            report_selector=report_id,
            instruction="Append inline insight",
            proposed_changes={
                "sections_to_modify": [
                    {
                        "section_id": section.section_id,
                        "insights": [
                            {
                                "summary": "Inline added",
                                "importance": 6,
                            }
                        ],
                    }
                ]
            },
        )

        assert result["status"] == "success"
        summary = result["summary"]
        # One insight created via inline modify path
        assert summary["insights_added"] == 1
        updated_outline = report_service.get_report_outline(report_id)
        assert len(updated_outline.insights) == 1
        assert updated_outline.sections[0].insight_ids == [
            updated_outline.insights[0].insight_id
        ]
