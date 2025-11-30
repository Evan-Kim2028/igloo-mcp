"""Schema definitions for report evolution changes with versioning."""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

CURRENT_CHANGES_SCHEMA_VERSION = "1.0"

# Merge mode constants (matching merge_utils.py)
MERGE_MODE_REPLACE = "replace"
MERGE_MODE_MERGE = "merge"
MERGE_MODE_APPEND = "append"
MERGE_MODE_PREPEND = "prepend"


class ValidationErrorDetail(BaseModel):
    """Structured validation error with field path, value, and context."""

    field: str  # Field path (e.g., "insights_to_modify[0].insight_id")
    value: Any  # Actual value that failed
    error: str  # Error message
    available_ids: list[str] | None = None  # Available IDs for "not found" errors

    def to_string(self) -> str:
        """Convert to human-readable error message with structural hints."""
        base_error = f"{self.field}: {self.error}"

        # Detect nested structure issues
        if isinstance(self.value, dict):
            # Check for common nesting mistakes
            if "insight" in self.value:
                base_error += (
                    "\n  → Found nested 'insight' object. Fields like 'summary' and 'importance' "
                    "should be at the top level, not nested."
                    "\n  → Correct format: {'insight_id': '...', 'summary': '...', 'importance': 9}"
                    "\n  → To link to a section, use sections_to_modify separately."
                )
            elif "section_id" in self.value and self.field.startswith("insights_to_add"):
                base_error += (
                    "\n  → Found 'section_id' in insight. Insights cannot be directly "
                    "linked to sections in insights_to_add."
                    "\n  → First create the insight, then use sections_to_modify to link it."
                )

        # Show available IDs for "not found" errors
        if self.available_ids:
            ids_preview = ", ".join(self.available_ids[:5])
            if len(self.available_ids) > 5:
                ids_preview += f" (and {len(self.available_ids) - 5} more)"
            base_error += f"\n  → Available IDs: {ids_preview}"

        # Show value for context (but not for huge objects)
        if self.value is not None:
            value_str = str(self.value)
            if len(value_str) > 200:
                value_str = value_str[:200] + "..."
            base_error += f"\n  → Received value: {value_str}"

        return base_error


class InsightChange(BaseModel):
    """Schema for adding or modifying an insight.

    insight_id is optional for additions (will be auto-generated if None).
    insight_id is required for modifications.
    """

    insight_id: str | None = None
    importance: int | None = Field(None, ge=0, le=10)
    summary: str | None = None
    supporting_queries: list[dict[str, Any]] | None = None
    citations: list[dict[str, Any]] | None = None
    status: Literal["active", "archived", "killed"] | None = None

    @model_validator(mode="before")
    @classmethod
    def generate_uuid_if_missing(cls, data: Any) -> Any:
        """Auto-generate UUID if insight_id is None or missing."""
        if isinstance(data, dict):
            if data.get("insight_id") is None:
                data["insight_id"] = str(uuid.uuid4())
        return data

    @field_validator("insight_id")
    @classmethod
    def validate_uuid(cls, v: str | None) -> str | None:
        """Validate UUID format if provided."""
        if v is None:
            return v
        try:
            uuid.UUID(v)
        except ValueError as e:
            raise ValueError(f"insight_id must be valid UUID: {v}") from e
        return v


class SectionChange(BaseModel):
    """Schema for adding or modifying a section.

    section_id is optional for additions (will be auto-generated if None).
    section_id is required for modifications.

    insights: Optional list of insight dictionaries for inline creation.
    When provided, insights are created atomically with the section and automatically linked.
    Mutually exclusive with insight_ids_to_add.

    content_merge_mode: Controls how content field is merged with existing content.
    - 'replace' (default): Replace existing content entirely
    - 'merge': Use placeholder-based merging (supports // ... existing ... patterns)
    - 'append': Append new content after existing
    - 'prepend': Prepend new content before existing
    """

    section_id: str | None = None
    title: str | None = None
    order: int | None = Field(None, ge=0)
    notes: str | None = None
    content: str | None = None
    content_format: Literal["markdown", "html", "plain"] | None = "markdown"
    content_merge_mode: Literal["replace", "merge", "append", "prepend"] | None = Field(
        default="replace",
        description="How to merge content with existing: replace, merge (placeholder-based), append, prepend",
    )
    insight_ids_to_add: list[str] | None = None
    insight_ids_to_remove: list[str] | None = None
    insights: list[dict[str, Any]] | None = None

    @model_validator(mode="before")
    @classmethod
    def generate_uuid_if_missing(cls, data: Any) -> Any:
        """Auto-generate UUID if section_id is None or missing."""
        if isinstance(data, dict):
            if data.get("section_id") is None:
                data["section_id"] = str(uuid.uuid4())
        return data

    @model_validator(mode="after")
    def validate_mutually_exclusive(self) -> "SectionChange":
        """Ensure insights and insight_ids_to_add are not both provided."""
        if self.insights is not None and self.insight_ids_to_add is not None:
            raise ValueError(
                "Cannot provide both 'insights' and 'insight_ids_to_add'. "
                "Use 'insights' for inline insight creation or 'insight_ids_to_add' for referencing existing insights."
            )
        return self

    @field_validator("section_id")
    @classmethod
    def validate_uuid(cls, v: str | None) -> str | None:
        """Validate UUID format if provided."""
        if v is None:
            return v
        try:
            uuid.UUID(v)
        except ValueError as e:
            raise ValueError(f"section_id must be valid UUID: {v}") from e
        return v


class ProposedChanges(BaseModel):
    """Versioned schema for report evolution changes."""

    schema_version: str = Field(
        default=CURRENT_CHANGES_SCHEMA_VERSION,
        description="Schema version for forward compatibility",
    )
    insights_to_add: list[InsightChange] = Field(default_factory=list)
    insights_to_modify: list[InsightChange] = Field(default_factory=list)
    insights_to_remove: list[str] = Field(default_factory=list)
    sections_to_add: list[SectionChange] = Field(default_factory=list)
    sections_to_modify: list[SectionChange] = Field(default_factory=list)
    sections_to_remove: list[str] = Field(default_factory=list)
    title_change: str | None = None
    metadata_updates: dict[str, Any] = Field(default_factory=dict)
    status_change: Literal["active", "archived", "deleted"] | None = Field(
        default=None,
        description="Optional status change for the report",
    )

    def validate_against_outline(self, outline) -> list[ValidationErrorDetail]:
        """Validate changes against current outline state.

        Returns:
            List of ValidationErrorDetail objects (empty if valid)
        """
        errors = []

        existing_insight_ids = {i.insight_id for i in outline.insights}
        existing_section_ids = {s.section_id for s in outline.sections}

        # Track insights being added in this operation (for cross-validation)
        # Note: IDs are auto-generated by model_validator, so they should always be present here
        insights_being_added = {change.insight_id for change in self.insights_to_add if change.insight_id}

        # Track inline insights from sections_to_add (they'll be created atomically)
        for section_change in self.sections_to_add:
            if section_change.insights:
                for insight_dict in section_change.insights:
                    # Inline insights may have auto-generated UUIDs, but we need to track them
                    # For validation purposes, we'll check if they have insight_id or will get one
                    if isinstance(insight_dict, dict):
                        insight_id = insight_dict.get("insight_id")
                        if insight_id:
                            insights_being_added.add(insight_id)
                        # If no insight_id, it will be auto-generated during processing
                        # We can't track it here, but validation will happen during processing

        # Validate insight additions
        for idx, change in enumerate(self.insights_to_add):
            # insight_id should be auto-generated by now, but check just in case
            if change.insight_id is None:
                errors.append(
                    ValidationErrorDetail(
                        field=f"insights_to_add[{idx}].insight_id",
                        value=None,
                        error="insight_id is required (should be auto-generated)",
                    )
                )
            elif change.insight_id in existing_insight_ids:
                errors.append(
                    ValidationErrorDetail(
                        field=f"insights_to_add[{idx}].insight_id",
                        value=change.insight_id,
                        error="insight_id already exists",
                        available_ids=list(existing_insight_ids)[:10],  # Limit to first 10 for readability
                    )
                )
            if change.importance is None or change.summary is None:
                missing_fields = []
                if change.importance is None:
                    missing_fields.append("importance")
                if change.summary is None:
                    missing_fields.append("summary")
                errors.append(
                    ValidationErrorDetail(
                        field=f"insights_to_add[{idx}]",
                        value={"insight_id": change.insight_id},
                        error=f"New insight must have {', '.join(missing_fields)}",
                    )
                )

        # Validate insight modifications
        for idx, change in enumerate(self.insights_to_modify):
            if change.insight_id is None:
                errors.append(
                    ValidationErrorDetail(
                        field=f"insights_to_modify[{idx}].insight_id",
                        value=None,
                        error="insight_id is required for modifications",
                    )
                )
            elif change.insight_id not in existing_insight_ids:
                errors.append(
                    ValidationErrorDetail(
                        field=f"insights_to_modify[{idx}].insight_id",
                        value=change.insight_id,
                        error="insight_id not found",
                        available_ids=list(existing_insight_ids)[:10],
                    )
                )
            else:
                # Check that at least one non-ID field is provided for modification
                non_id_fields = [
                    k
                    for k in change.model_dump(exclude={"insight_id"}).keys()
                    if change.model_dump(exclude={"insight_id"}).get(k) is not None
                ]
                if not non_id_fields:
                    errors.append(
                        ValidationErrorDetail(
                            field=f"insights_to_modify[{idx}]",
                            value={"insight_id": change.insight_id},
                            error="At least one field besides insight_id must be provided for modification",
                        )
                    )

        # Validate insight removals
        for idx, insight_id in enumerate(self.insights_to_remove):
            if insight_id not in existing_insight_ids:
                errors.append(
                    ValidationErrorDetail(
                        field=f"insights_to_remove[{idx}]",
                        value=insight_id,
                        error="insight_id not found",
                        available_ids=list(existing_insight_ids)[:10],
                    )
                )

        # Validate section additions
        for idx, section_change in enumerate(self.sections_to_add):
            # section_id should be auto-generated by now, but check just in case
            if section_change.section_id is None:
                errors.append(
                    ValidationErrorDetail(
                        field=f"sections_to_add[{idx}].section_id",
                        value=None,
                        error="section_id is required (should be auto-generated)",
                    )
                )
            elif section_change.section_id in existing_section_ids:
                errors.append(
                    ValidationErrorDetail(
                        field=f"sections_to_add[{idx}].section_id",
                        value=section_change.section_id,
                        error="section_id already exists",
                        available_ids=list(existing_section_ids)[:10],
                    )
                )
            if section_change.title is None:
                errors.append(
                    ValidationErrorDetail(
                        field=f"sections_to_add[{idx}].title",
                        value=None,
                        error="New section must have title",
                    )
                )

            # Validate inline insights (if provided)
            if section_change.insights:
                for insight_idx, insight_dict in enumerate(section_change.insights):
                    if not isinstance(insight_dict, dict):
                        errors.append(
                            ValidationErrorDetail(
                                field=f"sections_to_add[{idx}].insights[{insight_idx}]",
                                value=insight_dict,
                                error="must be a dictionary",
                            )
                        )
                        continue

                    # Validate required fields
                    if insight_dict.get("summary") is None:
                        errors.append(
                            ValidationErrorDetail(
                                field=f"sections_to_add[{idx}].insights[{insight_idx}].summary",
                                value=None,
                                error="summary is required",
                            )
                        )
                    if insight_dict.get("importance") is None:
                        errors.append(
                            ValidationErrorDetail(
                                field=f"sections_to_add[{idx}].insights[{insight_idx}].importance",
                                value=None,
                                error="importance is required",
                            )
                        )

                    # Validate UUID format if provided
                    insight_id = insight_dict.get("insight_id")
                    if insight_id is not None:
                        try:
                            uuid.UUID(insight_id)
                        except ValueError:
                            errors.append(
                                ValidationErrorDetail(
                                    field=f"sections_to_add[{idx}].insights[{insight_idx}].insight_id",
                                    value=insight_id,
                                    error="insight_id must be valid UUID",
                                )
                            )
                        # Check for collisions
                        if insight_id in existing_insight_ids:
                            errors.append(
                                ValidationErrorDetail(
                                    field=f"sections_to_add[{idx}].insights[{insight_idx}].insight_id",
                                    value=insight_id,
                                    error="insight_id already exists",
                                    available_ids=list(existing_insight_ids)[:10],
                                )
                            )

            # Validate insight_ids_to_add reference existing insights or insights being added
            if section_change.insight_ids_to_add:
                for insight_idx, insight_id in enumerate(section_change.insight_ids_to_add):
                    if insight_id not in existing_insight_ids and insight_id not in insights_being_added:
                        errors.append(
                            ValidationErrorDetail(
                                field=f"sections_to_add[{idx}].insight_ids_to_add[{insight_idx}]",
                                value=insight_id,
                                error=(
                                    "references non-existent insight. Insight must exist in outline "
                                    "or be added in the same operation"
                                ),
                                available_ids=list(existing_insight_ids | insights_being_added)[:10],
                            )
                        )

        # Validate section modifications
        for idx, section_change in enumerate(self.sections_to_modify):
            if section_change.section_id is None:
                errors.append(
                    ValidationErrorDetail(
                        field=f"sections_to_modify[{idx}].section_id",
                        value=None,
                        error="section_id is required for modifications",
                    )
                )
            elif section_change.section_id not in existing_section_ids:
                errors.append(
                    ValidationErrorDetail(
                        field=f"sections_to_modify[{idx}].section_id",
                        value=section_change.section_id,
                        error="section_id not found",
                        available_ids=list(existing_section_ids)[:10],
                    )
                )
            else:
                # Check that at least one non-ID field is provided for modification
                non_id_fields = [
                    k
                    for k in section_change.model_dump(exclude={"section_id"}).keys()
                    if section_change.model_dump(exclude={"section_id"}).get(k) is not None
                ]
                if not non_id_fields:
                    errors.append(
                        ValidationErrorDetail(
                            field=f"sections_to_modify[{idx}]",
                            value={"section_id": section_change.section_id},
                            error="At least one field besides section_id must be provided for modification",
                        )
                    )

            # Validate insight_ids_to_add reference existing insights or insights being added
            if section_change.insight_ids_to_add:
                for insight_idx, insight_id in enumerate(section_change.insight_ids_to_add):
                    if insight_id not in existing_insight_ids and insight_id not in insights_being_added:
                        errors.append(
                            ValidationErrorDetail(
                                field=f"sections_to_modify[{idx}].insight_ids_to_add[{insight_idx}]",
                                value=insight_id,
                                error=(
                                    "references non-existent insight. Insight must exist in outline "
                                    "or be added in the same operation"
                                ),
                                available_ids=list(existing_insight_ids | insights_being_added)[:10],
                            )
                        )

            # Validate insight_ids_to_remove reference existing insights
            if section_change.insight_ids_to_remove:
                for insight_idx, insight_id in enumerate(section_change.insight_ids_to_remove):
                    if insight_id not in existing_insight_ids:
                        errors.append(
                            ValidationErrorDetail(
                                field=f"sections_to_modify[{idx}].insight_ids_to_remove[{insight_idx}]",
                                value=insight_id,
                                error="attempts to remove non-existent insight",
                                available_ids=list(existing_insight_ids)[:10],
                            )
                        )

        # Validate section removals
        for idx, section_id in enumerate(self.sections_to_remove):
            if section_id not in existing_section_ids:
                errors.append(
                    ValidationErrorDetail(
                        field=f"sections_to_remove[{idx}]",
                        value=section_id,
                        error="section_id not found",
                        available_ids=list(existing_section_ids)[:10],
                    )
                )

        return errors
