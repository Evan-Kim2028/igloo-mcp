"""Schema field name constants for living reports.

Provides centralized constants for field names in ProposedChanges and related schemas.
Using constants prevents typos and makes refactoring safer when field names change.
"""

from __future__ import annotations


class ProposedChangesFields:
    """Field names for ProposedChanges schema."""

    # Section operations
    SECTIONS_TO_ADD = "sections_to_add"
    SECTIONS_TO_MODIFY = "sections_to_modify"
    SECTIONS_TO_REMOVE = "sections_to_remove"

    # Insight operations
    INSIGHTS_TO_ADD = "insights_to_add"
    INSIGHTS_TO_MODIFY = "insights_to_modify"
    INSIGHTS_TO_REMOVE = "insights_to_remove"

    # Metadata
    METADATA_UPDATES = "metadata_updates"
    TITLE_CHANGE = "title_change"
    STATUS_CHANGE = "status_change"
    SCHEMA_VERSION = "schema_version"


class SectionChangeFields:
    """Field names for SectionChange schema."""

    SECTION_ID = "section_id"
    TITLE = "title"
    ORDER = "order"
    CONTENT = "content"
    CONTENT_FORMAT = "content_format"
    NOTES = "notes"

    # Insight linking
    INSIGHT_IDS = "insight_ids"
    INSIGHT_IDS_TO_ADD = "insight_ids_to_add"
    INSIGHT_IDS_TO_REMOVE = "insight_ids_to_remove"

    # Inline insights
    INSIGHTS = "insights"


class InsightChangeFields:
    """Field names for InsightChange schema."""

    INSIGHT_ID = "insight_id"
    IMPORTANCE = "importance"
    SUMMARY = "summary"
    STATUS = "status"

    # Query/citation fields
    SUPPORTING_QUERIES = "supporting_queries"
    CITATIONS = "citations"

    # Draft changes
    DRAFT_CHANGES = "draft_changes"


class ResponseFields:
    """Field names for tool response schemas."""

    # Common response fields
    STATUS = "status"
    MESSAGE = "message"
    REQUEST_ID = "request_id"
    REPORT_ID = "report_id"

    # Timing metrics
    TIMING = "timing"
    TOTAL_DURATION_MS = "total_duration_ms"
    APPLY_DURATION_MS = "apply_duration_ms"
    STORAGE_DURATION_MS = "storage_duration_ms"

    # Summary fields
    SUMMARY = "summary"
    CHANGES_APPLIED = "changes_applied"
    WARNINGS = "warnings"
    OUTLINE_VERSION = "outline_version"

    # Response symmetry for complete CRUD tracking
    SECTION_IDS_ADDED = "section_ids_added"
    SECTION_IDS_MODIFIED = "section_ids_modified"
    SECTION_IDS_REMOVED = "section_ids_removed"
    INSIGHT_IDS_ADDED = "insight_ids_added"
    INSIGHT_IDS_MODIFIED = "insight_ids_modified"
    INSIGHT_IDS_REMOVED = "insight_ids_removed"


class ConstraintsFields:
    """Field names for constraints parameter."""

    SKIP_CITATION_VALIDATION = "skip_citation_validation"
    DRY_RUN = "dry_run"
    MAX_SECTIONS = "max_sections"
    MAX_INSIGHTS = "max_insights"


class ResponseDetailLevels:
    """Valid response_detail levels for evolve_report and other tools."""

    MINIMAL = "minimal"
    STANDARD = "standard"
    FULL = "full"


class ReportModes:
    """Valid modes for get_report tool."""

    SUMMARY = "summary"
    SECTIONS = "sections"
    INSIGHTS = "insights"
    FULL = "full"


class ContentFormats:
    """Valid content format values."""

    MARKDOWN = "markdown"
    HTML = "html"
    PLAIN = "plain"


class InsightStatus:
    """Valid insight status values."""

    ACTIVE = "active"
    DRAFT = "draft"
    ARCHIVED = "archived"


class ReportStatus:
    """Valid report status values."""

    ACTIVE = "active"
    DRAFT = "draft"
    ARCHIVED = "archived"
    PUBLISHED = "published"


# Convenience exports for common usage patterns
__all__ = [
    "ProposedChangesFields",
    "SectionChangeFields",
    "InsightChangeFields",
    "ResponseFields",
    "ConstraintsFields",
    "ResponseDetailLevels",
    "ReportModes",
    "ContentFormats",
    "InsightStatus",
    "ReportStatus",
]
