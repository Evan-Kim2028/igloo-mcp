"""Tests for changes schema validation."""

import uuid

import pytest

from igloo_mcp.living_reports.changes_schema import (
    CURRENT_CHANGES_SCHEMA_VERSION,
    InsightChange,
    ProposedChanges,
    SectionChange,
)
from igloo_mcp.living_reports.models import Insight, Outline, Section


def test_proposed_changes_validation():
    """Test ProposedChanges schema validation."""
    changes = ProposedChanges(
        insights_to_add=[
            InsightChange(
                insight_id=str(uuid.uuid4()),
                importance=8,
                summary="Test insight",
            )
        ],
        sections_to_add=[
            SectionChange(
                section_id=str(uuid.uuid4()),
                title="Test Section",
            )
        ],
        title_change="New Title",
    )

    assert changes.schema_version == CURRENT_CHANGES_SCHEMA_VERSION
    assert len(changes.insights_to_add) == 1
    assert len(changes.sections_to_add) == 1
    assert changes.title_change == "New Title"


def test_insight_change_schema():
    """Test InsightChange schema validation."""
    insight_id = str(uuid.uuid4())

    change = InsightChange(
        insight_id=insight_id,
        importance=9,
        summary="Key finding",
        status="active",
    )

    assert change.insight_id == insight_id
    assert change.importance == 9
    assert change.summary == "Key finding"
    assert change.status == "active"


def test_section_change_schema():
    """Test SectionChange schema validation."""
    section_id = str(uuid.uuid4())

    change = SectionChange(
        section_id=section_id,
        title="New Section",
        order=5,
        notes="Section notes",
        insight_ids_to_add=[str(uuid.uuid4())],
    )

    assert change.section_id == section_id
    assert change.title == "New Section"
    assert change.order == 5
    assert change.notes == "Section notes"
    assert len(change.insight_ids_to_add) == 1


def test_validate_against_outline():
    """Test validation against outline state."""
    # Create a mock outline
    outline = Outline(
        report_id=str(uuid.uuid4()),
        title="Test Report",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        version="1.0",
        sections=[
            Section(
                section_id=str(uuid.uuid4()),
                title="Existing Section",
                order=0,
                insight_ids=[],
            )
        ],
        insights=[
            Insight(
                insight_id=str(uuid.uuid4()),
                importance=7,
                summary="Existing insight",
                supporting_queries=[],
            )
        ],
    )

    # Test valid changes
    valid_changes = ProposedChanges(
        insights_to_modify=[
            InsightChange(
                insight_id=outline.insights[0].insight_id,
                importance=9,
            )
        ],
        sections_to_modify=[
            SectionChange(
                section_id=outline.sections[0].section_id,
                title="Modified Section",
            )
        ],
    )

    errors = valid_changes.validate_against_outline(outline)
    assert len(errors) == 0

    # Test invalid changes - duplicate insight ID
    invalid_changes = ProposedChanges(
        insights_to_add=[
            InsightChange(
                insight_id=outline.insights[0].insight_id,  # Duplicate!
                importance=8,
                summary="Duplicate insight",
            )
        ],
    )

    errors = invalid_changes.validate_against_outline(outline)
    assert len(errors) == 1
    assert "already exists" in errors[0].error


def test_schema_versioning():
    """Test schema versioning support."""
    changes = ProposedChanges()

    # Default version
    assert changes.schema_version == CURRENT_CHANGES_SCHEMA_VERSION

    # Custom version
    changes_v2 = ProposedChanges(schema_version="2.0")
    assert changes_v2.schema_version == "2.0"


def test_insight_change_uuid_validation():
    """Test insight_id UUID validation."""
    with pytest.raises(ValueError, match="insight_id must be valid UUID"):
        InsightChange(
            insight_id="not-a-uuid",
            importance=5,
            summary="Test",
        )


def test_section_change_uuid_validation():
    """Test section_id UUID validation."""
    with pytest.raises(ValueError, match="section_id must be valid UUID"):
        SectionChange(
            section_id="not-a-uuid",
            title="Test Section",
        )


def test_insight_importance_bounds():
    """Test insight importance bounds validation."""
    from pydantic import ValidationError

    # Valid importance
    change = InsightChange(
        insight_id=str(uuid.uuid4()),
        importance=5,
        summary="Test",
    )
    assert change.importance == 5

    # Invalid importance - too high
    with pytest.raises(ValidationError):
        InsightChange(
            insight_id=str(uuid.uuid4()),
            importance=15,  # > 10
            summary="Test",
        )

    # Invalid importance - too low
    with pytest.raises(ValidationError):
        InsightChange(
            insight_id=str(uuid.uuid4()),
            importance=-1,  # < 0
            summary="Test",
        )


def test_new_insight_validation():
    """Test validation for new insights requiring importance and summary."""
    changes = ProposedChanges(
        insights_to_add=[
            InsightChange(
                insight_id=str(uuid.uuid4()),
                # Missing importance and summary
            )
        ]
    )

    # Create mock outline
    outline = Outline(
        report_id=str(uuid.uuid4()),
        title="Test",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        version="1.0",
        sections=[],
        insights=[],
    )

    errors = changes.validate_against_outline(outline)
    assert len(errors) == 1
    assert "must have importance" in errors[0].error
    assert "summary" in errors[0].error


def test_check_for_unrecognized_keys_detects_common_llm_mistakes():
    """Test that check_for_unrecognized_keys catches common LLM key name mistakes."""
    # "sections" instead of "sections_to_add" — the most common mistake
    warnings = ProposedChanges.check_for_unrecognized_keys({
        "sections": [{"title": "Overview"}],
        "insights": [{"summary": "Finding"}],
    })
    assert len(warnings) == 2
    assert any("sections_to_add" in w for w in warnings)
    assert any("insights_to_add" in w for w in warnings)


def test_check_for_unrecognized_keys_passes_valid_keys():
    """Test that check_for_unrecognized_keys returns no warnings for valid keys."""
    warnings = ProposedChanges.check_for_unrecognized_keys({
        "sections_to_add": [{"title": "Overview"}],
        "insights_to_add": [{"summary": "Finding", "importance": 8}],
    })
    assert warnings == []


def test_check_for_unrecognized_keys_passes_empty_dict():
    """Test that empty dict produces no warnings."""
    warnings = ProposedChanges.check_for_unrecognized_keys({})
    assert warnings == []


def test_check_for_unrecognized_keys_unknown_key_no_alias():
    """Test that completely unknown keys get a generic message with valid key list."""
    warnings = ProposedChanges.check_for_unrecognized_keys({
        "foobar": "baz",
    })
    assert len(warnings) == 1
    assert "foobar" in warnings[0]
    assert "Valid keys:" in warnings[0]


def test_has_any_operations_empty():
    """Test has_any_operations returns False for empty ProposedChanges."""
    changes = ProposedChanges()
    assert changes.has_any_operations() is False


def test_has_any_operations_with_sections():
    """Test has_any_operations returns True when sections_to_add is populated."""
    changes = ProposedChanges(
        sections_to_add=[SectionChange(section_id=str(uuid.uuid4()), title="Test")]
    )
    assert changes.has_any_operations() is True


def test_has_any_operations_with_title_change():
    """Test has_any_operations returns True for title_change."""
    changes = ProposedChanges(title_change="New Title")
    assert changes.has_any_operations() is True


def test_has_any_operations_with_status_change():
    """Test has_any_operations returns True for status_change."""
    changes = ProposedChanges(status_change="archived")
    assert changes.has_any_operations() is True


def test_new_section_validation():
    """Test validation for new sections requiring title."""
    changes = ProposedChanges(
        sections_to_add=[
            SectionChange(
                section_id=str(uuid.uuid4()),
                # Missing title
            )
        ]
    )

    outline = Outline(
        report_id=str(uuid.uuid4()),
        title="Test",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        version="1.0",
        sections=[],
        insights=[],
    )

    errors = changes.validate_against_outline(outline)
    assert len(errors) == 1
    assert "must have title" in errors[0].error
