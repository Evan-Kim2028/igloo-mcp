"""Schema validation helpers for tests.

Provides factory functions that guarantee valid schema structures,
reducing test maintenance burden when schema evolves.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional


def create_valid_insight(
    summary: str,
    importance: int,
    *,
    insight_id: Optional[str] = None,
    supporting_queries: Optional[List[Dict[str, Any]]] = None,
    citations: Optional[List[Dict[str, Any]]] = None,
    status: str = "active",
    draft_changes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create insight with guaranteed valid schema.

    Args:
        summary: Insight summary text (required)
        importance: Importance score 0-10 (required)
        insight_id: Optional UUID string (auto-generates if None)
        supporting_queries: Optional list of query dicts
        citations: Optional list of citation dicts
        status: Insight status (default: "active")
        draft_changes: Optional draft changes dict

    Returns:
        Valid insight dict matching InsightChange schema

    Example:
        >>> insight = create_valid_insight("Revenue grew 25%", importance=9)
        >>> insight = create_valid_insight(
        ...     "Key finding",
        ...     importance=8,
        ...     citations=[{"execution_id": "qid-123"}]
        ... )
    """
    if not 0 <= importance <= 10:
        raise ValueError(f"importance must be 0-10, got {importance}")

    insight: Dict[str, Any] = {
        "summary": summary,
        "importance": importance,
    }

    # Only include optional fields if provided
    if insight_id is not None:
        # Validate UUID format
        try:
            uuid.UUID(insight_id)
        except ValueError as e:
            raise ValueError(f"insight_id must be valid UUID: {e}") from e
        insight["insight_id"] = insight_id

    if supporting_queries is not None:
        insight["supporting_queries"] = supporting_queries

    if citations is not None:
        insight["citations"] = citations

    if status != "active":
        insight["status"] = status

    if draft_changes is not None:
        insight["draft_changes"] = draft_changes

    return insight


def create_valid_section(
    title: str,
    order: int,
    *,
    section_id: Optional[str] = None,
    content: Optional[str] = None,
    content_format: str = "markdown",
    notes: Optional[str] = None,
    insight_ids: Optional[List[str]] = None,
    insights: Optional[List[Dict[str, Any]]] = None,
    insight_ids_to_add: Optional[List[str]] = None,
    insight_ids_to_remove: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create section with guaranteed valid schema.

    Args:
        title: Section title (required)
        order: Section order/position (required, >= 0)
        section_id: Optional UUID string (auto-generates if None)
        content: Optional markdown/HTML content
        content_format: Content format (default: "markdown")
        notes: Optional private notes
        insight_ids: Optional list of linked insight IDs
        insights: Optional inline insights (creates section + insights together)
        insight_ids_to_add: For sections_to_modify - IDs to link
        insight_ids_to_remove: For sections_to_modify - IDs to unlink

    Returns:
        Valid section dict matching SectionChange schema

    Example:
        >>> section = create_valid_section("Revenue Analysis", order=1)
        >>> section = create_valid_section(
        ...     "Findings",
        ...     order=2,
        ...     insights=[create_valid_insight("Finding", 8)]
        ... )
    """
    if order < 0:
        raise ValueError(f"order must be >= 0, got {order}")

    if content_format not in ("markdown", "html", "plain"):
        raise ValueError(f"content_format must be markdown/html/plain, got {content_format}")

    section: Dict[str, Any] = {
        "title": title,
        "order": order,
    }

    # Only include optional fields if provided
    if section_id is not None:
        # Validate UUID format
        try:
            uuid.UUID(section_id)
        except ValueError as e:
            raise ValueError(f"section_id must be valid UUID: {e}") from e
        section["section_id"] = section_id

    if content is not None:
        section["content"] = content

    if content_format != "markdown":
        section["content_format"] = content_format

    if notes is not None:
        section["notes"] = notes

    if insight_ids is not None:
        section["insight_ids"] = insight_ids

    if insights is not None:
        section["insights"] = insights

    if insight_ids_to_add is not None:
        section["insight_ids_to_add"] = insight_ids_to_add

    if insight_ids_to_remove is not None:
        section["insight_ids_to_remove"] = insight_ids_to_remove

    return section


def create_mock_citation(
    execution_id: str = "mock-execution-id",
    *,
    query_text: Optional[str] = None,
    row_count: Optional[int] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Create mock citation for test insights.

    Args:
        execution_id: Query execution ID (default: "mock-execution-id")
        query_text: Optional SQL query text
        row_count: Optional result row count
        timestamp: Optional ISO timestamp

    Returns:
        Valid citation dict

    Example:
        >>> citation = create_mock_citation("qid-123")
        >>> citation = create_mock_citation(
        ...     "qid-456",
        ...     query_text="SELECT * FROM sales",
        ...     row_count=100
        ... )
    """
    citation: Dict[str, Any] = {"execution_id": execution_id}

    if query_text is not None:
        citation["query_text"] = query_text

    if row_count is not None:
        citation["row_count"] = row_count

    if timestamp is not None:
        citation["timestamp"] = timestamp

    return citation


def create_insight_with_citation(
    summary: str,
    importance: int,
    execution_id: str = "mock-qid-123",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Create insight with mock citation (for tests requiring citations).

    Convenience wrapper around create_valid_insight that adds a mock citation.

    Args:
        summary: Insight summary text
        importance: Importance score 0-10
        execution_id: Mock execution ID for citation
        **kwargs: Additional insight fields

    Returns:
        Valid insight dict with citation

    Example:
        >>> insight = create_insight_with_citation("Revenue up 25%", 9)
        >>> # Automatically includes citation with execution_id
    """
    citation = create_mock_citation(execution_id)
    return create_valid_insight(
        summary,
        importance,
        citations=[citation],
        **kwargs,
    )


def create_section_with_insights(
    title: str,
    order: int,
    insights: List[tuple[str, int]],
    **kwargs: Any,
) -> Dict[str, Any]:
    """Create section with inline insights (avoids section_id validation).

    Args:
        title: Section title
        order: Section order
        insights: List of (summary, importance) tuples
        **kwargs: Additional section fields

    Returns:
        Valid section dict with inline insights

    Example:
        >>> section = create_section_with_insights(
        ...     "Findings",
        ...     order=1,
        ...     insights=[
        ...         ("Revenue grew 25%", 9),
        ...         ("Costs decreased 10%", 8),
        ...     ]
        ... )
    """
    insight_dicts = [create_valid_insight(summary, importance) for summary, importance in insights]

    return create_valid_section(
        title,
        order,
        insights=insight_dicts,
        **kwargs,
    )


def validate_uuid_format(value: str, field_name: str = "ID") -> str:
    """Validate that a string is a valid UUID.

    Args:
        value: String to validate
        field_name: Field name for error message

    Returns:
        The validated UUID string

    Raises:
        ValueError: If value is not a valid UUID

    Example:
        >>> validate_uuid_format("123e4567-e89b-12d3-a456-426614174000")
        '123e4567-e89b-12d3-a456-426614174000'
        >>> validate_uuid_format("not-a-uuid")  # Raises ValueError
    """
    try:
        uuid.UUID(value)
        return value
    except ValueError as e:
        raise ValueError(f"{field_name} must be valid UUID: {value}") from e


def validate_importance(value: int) -> int:
    """Validate importance score is in valid range.

    Args:
        value: Importance score to validate

    Returns:
        The validated importance score

    Raises:
        ValueError: If value not in 0-10 range

    Example:
        >>> validate_importance(5)
        5
        >>> validate_importance(15)  # Raises ValueError
    """
    if not 0 <= value <= 10:
        raise ValueError(f"importance must be 0-10, got {value}")
    return value
