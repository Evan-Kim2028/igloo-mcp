"""Tests for living reports data models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from igloo_mcp.living_reports.models import (
    AuditEvent,
    IndexEntry,
    Insight,
    Outline,
    ReportId,
    Section,
)


class TestReportId:
    """Test ReportId class."""

    def test_new_creates_uuid(self) -> None:
        """Test creating a new ReportId generates a valid UUID."""
        report_id = ReportId.new()
        assert isinstance(report_id.uuid, uuid.UUID)
        assert str(report_id)

    def test_from_string_valid(self) -> None:
        """Test creating ReportId from valid UUID string."""
        test_uuid = "550e8400-e29b-41d4-a716-446655440000"
        report_id = ReportId(test_uuid)
        assert str(report_id) == test_uuid
        assert report_id.uuid == uuid.UUID(test_uuid)

    def test_from_string_invalid(self) -> None:
        """Test creating ReportId from invalid string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid UUID string"):
            ReportId("not-a-uuid")

    def test_from_uuid_object(self) -> None:
        """Test creating ReportId from UUID object."""
        test_uuid = uuid.uuid4()
        report_id = ReportId(test_uuid)
        assert report_id.uuid == test_uuid

    def test_equality(self) -> None:
        """Test ReportId equality."""
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        id1 = ReportId(uuid_str)
        id2 = ReportId(uuid_str)
        id3 = ReportId.new()

        assert id1 == id2
        assert id1 != id3
        assert id1 != "not-a-report-id"


class TestInsight:
    """Test Insight model."""

    def test_valid_insight(self) -> None:
        """Test creating a valid insight."""
        insight = Insight(
            insight_id="550e8400-e29b-41d4-a716-446655440000",
            importance=8,
            summary="Test insight summary",
        )
        assert insight.insight_id == "550e8400-e29b-41d4-a716-446655440000"
        assert insight.importance == 8
        assert insight.summary == "Test insight summary"
        assert insight.status == "active"
        assert insight.supporting_queries == []

    def test_invalid_insight_id(self) -> None:
        """Test insight with invalid UUID raises ValueError."""
        with pytest.raises(ValueError, match="insight_id must be valid UUID string"):
            Insight(
                insight_id="not-a-uuid",
                importance=5,
                summary="Test",
            )

    def test_importance_bounds(self) -> None:
        """Test importance score validation."""
        # Valid range
        Insight(insight_id=str(uuid.uuid4()), importance=0, summary="Test")
        Insight(insight_id=str(uuid.uuid4()), importance=10, summary="Test")

        # Invalid range
        with pytest.raises(ValueError):
            Insight(insight_id=str(uuid.uuid4()), importance=-1, summary="Test")
        with pytest.raises(ValueError):
            Insight(insight_id=str(uuid.uuid4()), importance=11, summary="Test")

    def test_status_validation(self) -> None:
        """Test status field validation."""
        # Valid statuses
        Insight(insight_id=str(uuid.uuid4()), importance=5, summary="Test", status="active")
        Insight(
            insight_id=str(uuid.uuid4()),
            importance=5,
            summary="Test",
            status="archived",
        )
        Insight(insight_id=str(uuid.uuid4()), importance=5, summary="Test", status="killed")

        # Invalid status
        with pytest.raises(ValueError):
            Insight(
                insight_id=str(uuid.uuid4()),
                importance=5,
                summary="Test",
                status="invalid",
            )


class TestSection:
    """Test Section model."""

    def test_valid_section(self) -> None:
        """Test creating a valid section."""
        section = Section(
            section_id="550e8400-e29b-41d4-a716-446655440000",
            title="Test Section",
            order=1,
        )
        assert section.section_id == "550e8400-e29b-41d4-a716-446655440000"
        assert section.title == "Test Section"
        assert section.order == 1
        assert section.insight_ids == []
        assert section.notes is None

    def test_invalid_section_id(self) -> None:
        """Test section with invalid UUID raises ValueError."""
        with pytest.raises(ValueError, match="section_id must be valid UUID string"):
            Section(
                section_id="not-a-uuid",
                title="Test",
                order=0,
            )

    def test_order_validation(self) -> None:
        """Test order field validation."""
        Section(section_id=str(uuid.uuid4()), title="Test", order=0)
        Section(section_id=str(uuid.uuid4()), title="Test", order=100)

        with pytest.raises(ValueError):
            Section(section_id=str(uuid.uuid4()), title="Test", order=-1)


class TestOutline:
    """Test Outline model."""

    def test_valid_outline(self) -> None:
        """Test creating a valid outline."""
        now = datetime.now(timezone.utc).isoformat()
        outline = Outline(
            report_id="550e8400-e29b-41d4-a716-446655440000",
            title="Test Report",
            created_at=now,
            updated_at=now,
            sections=[
                Section(
                    section_id=str(uuid.uuid4()),
                    title="Section 1",
                    order=0,
                )
            ],
            insights=[
                Insight(
                    insight_id=str(uuid.uuid4()),
                    importance=7,
                    summary="Test insight",
                )
            ],
        )
        assert outline.report_id == "550e8400-e29b-41d4-a716-446655440000"
        assert outline.title == "Test Report"
        assert len(outline.sections) == 1
        assert len(outline.insights) == 1

    def test_invalid_report_id(self) -> None:
        """Test outline with invalid report ID raises ValueError."""
        now = datetime.now(timezone.utc).isoformat()
        with pytest.raises(ValueError, match="report_id must be valid ReportId"):
            Outline(
                report_id="not-a-uuid",
                title="Test",
                created_at=now,
                updated_at=now,
            )

    def test_get_insight(self) -> None:
        """Test getting insight by ID."""
        now = datetime.now(timezone.utc).isoformat()
        insight_id = str(uuid.uuid4())
        outline = Outline(
            report_id=str(ReportId.new()),
            title="Test",
            created_at=now,
            updated_at=now,
            insights=[
                Insight(
                    insight_id=insight_id,
                    importance=5,
                    summary="Test insight",
                )
            ],
        )

        insight = outline.get_insight(insight_id)
        assert insight.insight_id == insight_id

        with pytest.raises(ValueError, match="Insight not found"):
            outline.get_insight(str(uuid.uuid4()))

    def test_get_section(self) -> None:
        """Test getting section by ID."""
        now = datetime.now(timezone.utc).isoformat()
        section_id = str(uuid.uuid4())
        outline = Outline(
            report_id=str(ReportId.new()),
            title="Test",
            created_at=now,
            updated_at=now,
            sections=[
                Section(
                    section_id=section_id,
                    title="Test Section",
                    order=0,
                )
            ],
        )

        section = outline.get_section(section_id)
        assert section.section_id == section_id

        with pytest.raises(ValueError, match="Section not found"):
            outline.get_section(str(uuid.uuid4()))


class TestAuditEvent:
    """Test AuditEvent model."""

    def test_valid_audit_event(self) -> None:
        """Test creating a valid audit event."""
        now = datetime.now(timezone.utc).isoformat()
        event = AuditEvent(
            action_id=str(uuid.uuid4()),
            report_id=str(ReportId.new()),
            ts=now,
            actor="cli",
            action_type="create",
        )
        assert event.actor == "cli"
        assert event.action_type == "create"
        assert event.payload == {}

    def test_invalid_actor(self) -> None:
        """Test audit event with invalid actor raises ValueError."""
        now = datetime.now(timezone.utc).isoformat()
        with pytest.raises(ValueError):
            AuditEvent(
                action_id=str(uuid.uuid4()),
                report_id=str(ReportId.new()),
                ts=now,
                actor="invalid",
                action_type="create",
            )

    def test_invalid_action_type(self) -> None:
        """Test audit event with invalid action type raises ValueError."""
        now = datetime.now(timezone.utc).isoformat()
        with pytest.raises(ValueError):
            AuditEvent(
                action_id=str(uuid.uuid4()),
                report_id=str(ReportId.new()),
                ts=now,
                actor="cli",
                action_type="invalid",
            )


class TestIndexEntry:
    """Test IndexEntry model."""

    def test_valid_index_entry(self) -> None:
        """Test creating a valid index entry."""
        now = datetime.now(timezone.utc).isoformat()
        entry = IndexEntry(
            report_id=str(ReportId.new()),
            current_title="Test Report",
            created_at=now,
            updated_at=now,
            path="by_id/550e8400-e29b-41d4-a716-446655440000",
        )
        assert entry.current_title == "Test Report"
        assert entry.status == "active"
        assert entry.tags == []

    def test_invalid_report_id(self) -> None:
        """Test index entry with invalid report ID raises ValueError."""
        now = datetime.now(timezone.utc).isoformat()
        with pytest.raises(ValueError, match="report_id must be valid ReportId"):
            IndexEntry(
                report_id="not-a-uuid",
                current_title="Test",
                created_at=now,
                updated_at=now,
                path="test",
            )

    def test_status_validation(self) -> None:
        """Test status field validation."""
        now = datetime.now(timezone.utc).isoformat()

        # Valid statuses
        IndexEntry(
            report_id=str(ReportId.new()),
            current_title="Test",
            created_at=now,
            updated_at=now,
            path="test",
            status="active",
        )
        IndexEntry(
            report_id=str(ReportId.new()),
            current_title="Test",
            created_at=now,
            updated_at=now,
            path="test",
            status="archived",
        )

        # Invalid status
        with pytest.raises(ValueError):
            IndexEntry(
                report_id=str(ReportId.new()),
                current_title="Test",
                created_at=now,
                updated_at=now,
                path="test",
                status="invalid",
            )
