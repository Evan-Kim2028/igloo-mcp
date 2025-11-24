"""Pydantic models for living reports data structures.

This module defines the core data models for the living reports system,
providing validation and serialization for all report components.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DatasetSource(BaseModel):
    """Source binding for a dataset within a report.

    At least one of execution_id, sql_sha256, or cache_manifest must be
    provided so the resolver can bind this dataset to concrete history/cache
    artifacts.
    """

    model_config = ConfigDict(extra="forbid")

    execution_id: Optional[str] = Field(
        default=None,
        description="Execution ID from audit_info.execution_id or history JSONL",
    )
    sql_sha256: Optional[str] = Field(
        default=None,
        description="SHA-256 hash of the SQL text (statement_sha256)",
    )
    cache_manifest: Optional[str] = Field(
        default=None,
        description=(
            "Path to a cache manifest.json (absolute or repo-relative). When "
            "provided, this takes precedence over history lookups."
        ),
    )
    cache_only: bool = Field(
        default=False,
        description="If true, do not attempt to re-run queries (reserved).",
    )

    # Future hints for profile/context overrides (stored but unused for now).
    profile: Optional[str] = Field(default=None)
    warehouse: Optional[str] = Field(default=None)
    database: Optional[str] = Field(default=None)
    db_schema: Optional[str] = Field(default=None, alias="schema")
    role: Optional[str] = Field(default=None)

    @field_validator("db_schema", mode="before")
    @classmethod
    def _validate_schema_alias(cls, v):
        """Allow 'schema' as an alias for 'db_schema'."""
        return v

    def __or__(self, other):
        """Merge two DatasetSource instances, preferring self's values."""
        if not isinstance(other, DatasetSource):
            return self
        merged = {}
        for field in self.model_fields:
            self_val = getattr(self, field)
            other_val = getattr(other, field)
            merged[field] = self_val if self_val is not None else other_val
        return DatasetSource(**merged)


class ResolvedDataset(BaseModel):
    """Concrete dataset resolved from history/cache artifacts."""

    name: str
    rows: List[Dict[str, Any]]
    columns: List[str]
    key_metrics: Optional[Dict[str, Any]]
    insights: List[Any]
    provenance: Dict[str, Any]


class ReportId:
    """Stable UUID-based identifier for reports.

    Provides string representation and validation for report identifiers.
    """

    def __init__(self, value: str | uuid.UUID) -> None:
        """Initialize ReportId from string or UUID.

        Args:
            value: UUID string or UUID object

        Raises:
            ValueError: If value is not a valid UUID
        """
        if isinstance(value, str):
            try:
                self._uuid = uuid.UUID(value)
            except ValueError as e:
                raise ValueError(f"Invalid UUID string: {value}") from e
        elif isinstance(value, uuid.UUID):
            self._uuid = value
        else:
            raise ValueError(f"ReportId must be string or UUID, got {type(value)}")

    @classmethod
    def new(cls) -> ReportId:
        """Create a new random ReportId."""
        return cls(uuid.uuid4())

    @property
    def uuid(self) -> uuid.UUID:
        """Get the underlying UUID object."""
        return self._uuid

    def __str__(self) -> str:
        """Return canonical UUID string representation."""
        return str(self._uuid)

    def __repr__(self) -> str:
        """Return detailed string representation."""
        return f"ReportId('{str(self)}')"

    def __eq__(self, other: object) -> bool:
        """Check equality with another ReportId."""
        if not isinstance(other, ReportId):
            return NotImplemented
        return self._uuid == other._uuid

    def __hash__(self) -> int:
        """Hash based on UUID."""
        return hash(self._uuid)


class Insight(BaseModel):
    """A single insight within a report section.

    Insights represent key findings or observations that are backed by
    supporting query results and have configurable importance levels.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    insight_id: str = Field(
        ...,
        description="Stable UUID for this insight",
        min_length=1,
    )
    importance: int = Field(
        ...,
        description="Importance score from 0 (lowest) to 10 (highest)",
        ge=0,
        le=10,
    )
    status: str = Field(
        "active",
        description="Insight status: active, archived, or killed",
        pattern="^(active|archived|killed)$",
    )
    summary: str = Field(
        ...,
        description="Human-readable summary of the insight",
        min_length=1,
    )
    supporting_queries: List[DatasetSource] = Field(
        default_factory=list,
        description="List of query references that support this insight",
    )
    draft_changes: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Pending changes from LLM evolution",
    )

    @field_validator("insight_id")
    @classmethod
    def _validate_insight_id(cls, v: str) -> str:
        """Validate insight_id is a valid UUID string."""
        try:
            uuid.UUID(v)
        except ValueError as e:
            raise ValueError(f"insight_id must be valid UUID string: {v}") from e
        return v


class Section(BaseModel):
    """A section within a report containing ordered insights.

    Sections provide logical grouping and ordering of insights within a report.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    section_id: str = Field(
        ...,
        description="Stable UUID for this section",
        min_length=1,
    )
    title: str = Field(
        ...,
        description="Human-readable section title",
        min_length=1,
    )
    order: int = Field(
        ...,
        description="Display order (lower numbers appear first)",
        ge=0,
    )
    insight_ids: List[str] = Field(
        default_factory=list,
        description="Ordered list of insight IDs in this section",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional human notes or prose for this section",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional section metadata (category tags, etc.)",
    )

    @field_validator("section_id")
    @classmethod
    def _validate_section_id(cls, v: str) -> str:
        """Validate section_id is a valid UUID string."""
        try:
            uuid.UUID(v)
        except ValueError as e:
            raise ValueError(f"section_id must be valid UUID string: {v}") from e
        return v


class Outline(BaseModel):
    """Machine-truth representation of a complete report.

    The outline contains all structural information about a report,
    including metadata, sections, and insights. This is the source
    of truth that drives report generation and evolution.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    report_id: str = Field(
        ...,
        description="Stable report identifier",
        min_length=1,
    )
    title: str = Field(
        ...,
        description="Human-readable report title",
        min_length=1,
    )
    created_at: str = Field(
        ...,
        description="ISO 8601 timestamp when report was created",
    )
    updated_at: str = Field(
        ...,
        description="ISO 8601 timestamp when report was last updated",
    )
    version: str = Field(
        "1.0",
        description="Schema version for forward compatibility",
    )
    outline_version: int = Field(
        1,
        description="Monotonic version counter for optimistic locking",
        ge=1,
    )
    sections: List[Section] = Field(
        default_factory=list,
        description="Ordered list of report sections",
    )
    insights: List[Insight] = Field(
        default_factory=list,
        description="All insights referenced by sections",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional report metadata (tags, owner, etc.)",
    )

    @field_validator("report_id")
    @classmethod
    def _validate_report_id(cls, v: str) -> str:
        """Validate report_id is a valid ReportId string."""
        try:
            ReportId(v)
        except ValueError as e:
            raise ValueError(f"report_id must be valid ReportId: {v}") from e
        return v

    def get_insight(self, insight_id: str) -> Insight:
        """Get insight by ID.

        Args:
            insight_id: UUID string of the insight

        Returns:
            The insight object

        Raises:
            ValueError: If insight not found
        """
        for insight in self.insights:
            if insight.insight_id == insight_id:
                return insight
        raise ValueError(f"Insight not found: {insight_id}")

    def get_section(self, section_id: str) -> Section:
        """Get section by ID.

        Args:
            section_id: UUID string of the section

        Returns:
            The section object

        Raises:
            ValueError: If section not found
        """
        for section in self.sections:
            if section.section_id == section_id:
                return section
        raise ValueError(f"Section not found: {section_id}")


class AuditEvent(BaseModel):
    """Immutable audit event for report operations.

    Audit events provide complete traceability of all changes to reports,
    enabling revert operations and compliance auditing.
    """

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(
        ...,
        description="Unique identifier for this audit event",
        min_length=1,
    )
    report_id: str = Field(
        ...,
        description="Report identifier this event relates to",
        min_length=1,
    )
    ts: str = Field(
        ...,
        description="ISO 8601 timestamp when action occurred",
    )
    actor: str = Field(
        ...,
        description="Who performed the action (cli, agent, human)",
        pattern="^(cli|agent|human)$",
    )
    action_type: str = Field(
        ...,
        description="Type of action performed",
        pattern=r"^(create|evolve|revert|rename|tag_update|render|manual_edit_detected|backup)$",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Optional correlation ID for request tracing",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific data and metadata",
    )

    @field_validator("action_id")
    @classmethod
    def _validate_action_id(cls, v: str) -> str:
        """Validate action_id is a valid UUID string."""
        try:
            uuid.UUID(v)
        except ValueError as e:
            raise ValueError(f"action_id must be valid UUID string: {v}") from e
        return v

    @field_validator("report_id")
    @classmethod
    def _validate_report_id(cls, v: str) -> str:
        """Validate report_id is a valid ReportId string."""
        try:
            ReportId(v)
        except ValueError as e:
            raise ValueError(f"report_id must be valid ReportId: {v}") from e
        return v


class IndexEntry(BaseModel):
    """Entry in the global reports index.

    Index entries provide fast lookup of reports by title or ID,
    and track basic metadata for listing operations.
    """

    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(
        ...,
        description="Report identifier",
        min_length=1,
    )
    current_title: str = Field(
        ...,
        description="Current human-readable title",
        min_length=1,
    )
    created_at: str = Field(
        ...,
        description="ISO 8601 timestamp when report was created",
    )
    updated_at: str = Field(
        ...,
        description="ISO 8601 timestamp when report was last updated",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="User-defined tags for organization",
    )
    status: str = Field(
        "active",
        description="Report status: active or archived",
        pattern="^(active|archived)$",
    )
    path: str = Field(
        ...,
        description="Relative path to report directory from reports root",
    )

    @field_validator("report_id")
    @classmethod
    def _validate_report_id(cls, v: str) -> str:
        """Validate report_id is a valid ReportId string."""
        try:
            ReportId(v)
        except ValueError as e:
            raise ValueError(f"report_id must be valid ReportId: {v}") from e
        return v


__all__ = [
    "AuditEvent",
    "IndexEntry",
    "Insight",
    "Outline",
    "ReportId",
    "Section",
]
