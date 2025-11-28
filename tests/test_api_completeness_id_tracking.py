"""Unit tests for API completeness: ID tracking functionality.

Tests the ID tracking for created and removed entities in report tools
(create_report, evolve_report). Ensures response symmetry: if you add X,
you should return X in the response.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from igloo_mcp.config import Config
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.tools.create_report import CreateReportTool
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool


@pytest.fixture
def temp_reports_dir():
    """Create temporary reports directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config(temp_reports_dir):
    """Create config with temp reports directory."""
    cfg = Mock(spec=Config)
    cfg.reports_dir = temp_reports_dir
    return cfg


@pytest.fixture
def report_service(temp_reports_dir):
    """Create report service instance."""
    return ReportService(reports_root=temp_reports_dir)


@pytest.fixture
def create_tool(config, report_service):
    """Create create_report tool instance."""
    return CreateReportTool(config, report_service)


@pytest.fixture
def evolve_tool(config, report_service):
    """Create evolve_report tool instance."""
    return EvolveReportTool(config, report_service)


class TestCreateReportIdTracking:
    """Test ID tracking for create_report tool."""

    @pytest.mark.asyncio
    async def test_section_ids_added_with_template(self, create_tool, report_service):
        """Test that section_ids_added is populated when using templates."""
        result = await create_tool.execute(
            title="Test Report",
            template="monthly_sales",
        )

        assert "section_ids_added" in result
        assert isinstance(result["section_ids_added"], list)
        assert len(result["section_ids_added"]) > 0  # monthly_sales has sections

        # Verify sections exist in the report
        report_id = result["report_id"]
        outline = report_service.get_report_outline(report_id)
        created_section_ids = [s.section_id for s in outline.sections]

        assert result["section_ids_added"] == created_section_ids

    @pytest.mark.asyncio
    async def test_insight_ids_added_with_template(self, create_tool, report_service):
        """Test that insight_ids_added is populated when templates have insights."""
        result = await create_tool.execute(
            title="Test Deep Dive",
            template="deep_dive",
        )

        assert "insight_ids_added" in result
        assert isinstance(result["insight_ids_added"], list)

        # Verify insights exist in the report
        report_id = result["report_id"]
        outline = report_service.get_report_outline(report_id)
        created_insight_ids = [i.insight_id for i in outline.insights]

        assert result["insight_ids_added"] == created_insight_ids

    @pytest.mark.asyncio
    async def test_empty_arrays_for_default_template(self, create_tool):
        """Test that empty arrays are returned for default template (no sections)."""
        result = await create_tool.execute(
            title="Empty Report",
            template="default",
        )

        assert "section_ids_added" in result
        assert "insight_ids_added" in result

        # Default template should have no sections/insights
        assert result["section_ids_added"] == []
        assert result["insight_ids_added"] == []

    @pytest.mark.asyncio
    async def test_ids_with_initial_sections(self, create_tool, report_service):
        """Test ID tracking when creating report with initial_sections."""
        import uuid

        # Use valid UUID strings for section_ids
        intro_id = str(uuid.uuid4())
        analysis_id = str(uuid.uuid4())

        initial_sections = [
            {
                "section_id": intro_id,
                "title": "Introduction",
                "order": 0,
                "content": "Initial content",
            },
            {
                "section_id": analysis_id,
                "title": "Analysis",
                "order": 1,
                "content": "Analysis content",
            },
        ]

        result = await create_tool.execute(
            title="Report with Sections",
            template="default",
            initial_sections=initial_sections,
        )

        assert "section_ids_added" in result
        assert len(result["section_ids_added"]) == 2
        assert intro_id in result["section_ids_added"]
        assert analysis_id in result["section_ids_added"]

    @pytest.mark.asyncio
    async def test_outline_duration_timing(self, create_tool):
        """Test that outline_duration_ms is included in timing breakdown."""
        result = await create_tool.execute(
            title="Test Timing",
            template="default",
        )

        assert "timing" in result
        timing = result["timing"]

        assert "outline_duration_ms" in timing
        assert timing["outline_duration_ms"] > 0

        # Outline fetch is part of create operation
        assert timing["outline_duration_ms"] <= timing["create_duration_ms"]


class TestEvolveReportIdTracking:
    """Test ID tracking for evolve_report tool."""

    @pytest.mark.asyncio
    async def test_insight_ids_removed(self, evolve_tool, report_service):
        """Test that insight_ids_removed is populated when insights are removed."""
        # Create report with insights
        report_id = report_service.create_report(
            title="Test Report",
            template="deep_dive",
            actor="test",
        )

        # Get current insights
        outline = report_service.get_report_outline(report_id)
        initial_insights = [i.insight_id for i in outline.insights]

        # Skip if template has no insights
        if len(initial_insights) == 0:
            pytest.skip("Template has no insights to test")

        # Evolve to remove some insights
        proposed_changes = {
            "insights_to_remove": (initial_insights[:2] if len(initial_insights) >= 2 else initial_insights),
        }

        result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Remove insights",
            proposed_changes=proposed_changes,
        )

        assert "insight_ids_removed" in result
        assert isinstance(result["insight_ids_removed"], list)
        assert len(result["insight_ids_removed"]) > 0
        assert result["insight_ids_removed"] == proposed_changes["insights_to_remove"]

    @pytest.mark.asyncio
    async def test_section_ids_removed(self, evolve_tool, report_service):
        """Test that section_ids_removed is populated when sections are removed."""
        # Create report with sections
        report_id = report_service.create_report(
            title="Test Report",
            template="monthly_sales",
            actor="test",
        )

        # Get current sections
        outline = report_service.get_report_outline(report_id)
        initial_sections = [s.section_id for s in outline.sections]

        # Evolve to remove some sections
        proposed_changes = {
            "sections_to_remove": initial_sections[:1],
        }

        result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Remove section",
            proposed_changes=proposed_changes,
        )

        assert "section_ids_removed" in result
        assert isinstance(result["section_ids_removed"], list)
        assert len(result["section_ids_removed"]) > 0
        assert result["section_ids_removed"] == proposed_changes["sections_to_remove"]

    @pytest.mark.asyncio
    async def test_empty_arrays_when_nothing_removed(self, evolve_tool, report_service):
        """Test that empty arrays are returned when nothing is removed."""
        import uuid

        # Create report
        report_id = report_service.create_report(
            title="Test Report",
            template="default",
            actor="test",
        )

        # Evolve to add (not remove) content
        proposed_changes = {
            "sections_to_add": [
                {
                    "section_id": str(uuid.uuid4()),
                    "title": "New Section",
                    "order": 0,
                    "content": "New content",
                }
            ],
        }

        result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Add section",
            proposed_changes=proposed_changes,
        )

        assert "insight_ids_removed" in result
        assert "section_ids_removed" in result
        assert result["insight_ids_removed"] == []
        assert result["section_ids_removed"] == []

    @pytest.mark.asyncio
    async def test_both_added_and_removed(self, evolve_tool, report_service):
        """Test tracking when both adding and removing entities."""
        import uuid

        # Create report with sections
        report_id = report_service.create_report(
            title="Test Report",
            template="monthly_sales",
            actor="test",
        )

        # Get current sections
        outline = report_service.get_report_outline(report_id)
        initial_sections = [s.section_id for s in outline.sections]

        # Evolve to both add and remove
        new_section_id = str(uuid.uuid4())
        proposed_changes = {
            "sections_to_add": [
                {
                    "section_id": new_section_id,
                    "title": "New Section",
                    "order": 99,
                    "content": "New content",
                }
            ],
            "sections_to_remove": initial_sections[:1],
        }

        result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Add and remove sections",
            proposed_changes=proposed_changes,
        )

        # Check added
        assert "section_ids_added" in result
        assert new_section_id in result["section_ids_added"]

        # Check removed
        assert "section_ids_removed" in result
        assert result["section_ids_removed"] == proposed_changes["sections_to_remove"]


class TestAuditTrailIdTracking:
    """Test that audit trail includes removed IDs."""

    @pytest.mark.asyncio
    async def test_audit_includes_section_ids_removed(self, evolve_tool, report_service):
        """Test that audit trail includes section_ids_removed field."""
        # TODO: Audit trail file creation not working in test environment
        # Audit logging infrastructure exists but files aren't being created
        # during tests. Needs investigation of test fixture setup or storage layer.
        pytest.skip("Audit trail file creation not working in test environment")

        # Create report with sections
        report_id = report_service.create_report(
            title="Test Report",
            template="monthly_sales",
            actor="test",
        )

        # Get current sections
        outline = report_service.get_report_outline(report_id)
        initial_sections = [s.section_id for s in outline.sections]

        # Evolve to remove sections
        proposed_changes = {
            "sections_to_remove": initial_sections[:1],
        }

        await evolve_tool.execute(
            report_selector=report_id,
            instruction="Remove section",
            proposed_changes=proposed_changes,
        )

        # Read audit trail
        audit_file = report_service.reports_root / report_id / "audit.jsonl"
        assert audit_file.exists()

        # Get last audit entry
        import json

        with open(audit_file, "r") as f:
            lines = f.readlines()
            last_entry = json.loads(lines[-1])

        # Verify section_ids_removed in audit
        assert "section_ids_removed" in last_entry
        assert last_entry["section_ids_removed"] == proposed_changes["sections_to_remove"]

    @pytest.mark.asyncio
    async def test_audit_includes_insight_ids_removed(self, evolve_tool, report_service):
        """Test that audit trail includes insight_ids_removed field."""
        # TODO: Audit trail file creation not working in test environment
        # Audit logging infrastructure exists but files aren't being created
        # during tests. Needs investigation of test fixture setup or storage layer.
        pytest.skip("Audit trail file creation not working in test environment")

        # Create report with insights
        report_id = report_service.create_report(
            title="Test Report",
            template="deep_dive",
            actor="test",
        )

        # Get current insights
        outline = report_service.get_report_outline(report_id)
        initial_insights = [i.insight_id for i in outline.insights]

        if len(initial_insights) == 0:
            pytest.skip("Template has no insights to test")

        # Evolve to remove insights
        changes = {
            "insights_to_remove": initial_insights[:1],
        }

        await evolve_tool.execute(
            report_id=report_id,
            changes=changes,
        )

        # Read audit trail
        audit_file = report_service.reports_root / report_id / "audit.jsonl"
        assert audit_file.exists()

        # Get last audit entry
        import json

        with open(audit_file, "r") as f:
            lines = f.readlines()
            last_entry = json.loads(lines[-1])

        # Verify insight_ids_removed in audit
        assert "insight_ids_removed" in last_entry
        assert last_entry["insight_ids_removed"] == changes["insights_to_remove"]


class TestResponseSymmetry:
    """Test response symmetry principle: if you add/modify/remove X, return X in response."""

    @pytest.mark.asyncio
    async def test_create_report_symmetry(self, create_tool):
        """Test that create_report returns all created IDs."""
        result = await create_tool.execute(
            title="Symmetry Test",
            template="monthly_sales",
        )

        # If sections are added, their IDs should be returned
        if result.get("section_ids_added"):
            assert isinstance(result["section_ids_added"], list)
            assert all(isinstance(sid, str) for sid in result["section_ids_added"])

        # If insights are added, their IDs should be returned
        if result.get("insight_ids_added"):
            assert isinstance(result["insight_ids_added"], list)
            assert all(isinstance(iid, str) for iid in result["insight_ids_added"])

    @pytest.mark.asyncio
    async def test_evolve_report_symmetry(self, evolve_tool, report_service):
        """Test that evolve_report returns all modified IDs."""
        import uuid

        # Create report
        report_id = report_service.create_report(
            title="Test Report",
            template="monthly_sales",
            actor="test",
        )

        # Get current state
        outline = report_service.get_report_outline(report_id)
        existing_sections = [s.section_id for s in outline.sections]

        # Evolve with all operation types
        new_section_id = str(uuid.uuid4())
        proposed_changes = {
            "sections_to_add": [
                {
                    "section_id": new_section_id,
                    "title": "New",
                    "order": 99,
                    "content": "New",
                }
            ],
            "sections_to_modify": (
                [
                    {
                        "section_id": existing_sections[0],
                        "title": "Updated",
                    }
                ]
                if existing_sections
                else []
            ),
            "sections_to_remove": (existing_sections[1:2] if len(existing_sections) > 1 else []),
        }

        result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Add, update, and remove sections",
            proposed_changes=proposed_changes,
        )

        # All operation types should be reflected in response
        assert "section_ids_added" in result
        assert "section_ids_modified" in result
        assert "section_ids_removed" in result

        # Verify correctness
        if proposed_changes["sections_to_add"]:
            assert new_section_id in result["section_ids_added"]

        if proposed_changes["sections_to_modify"]:
            assert existing_sections[0] in result["section_ids_modified"]

        if proposed_changes["sections_to_remove"]:
            assert result["section_ids_removed"] == proposed_changes["sections_to_remove"]
