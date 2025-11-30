"""Factory helper for creating test Outline objects with sensible defaults."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from igloo_mcp.living_reports.models import Outline


def create_test_outline(**kwargs: Any) -> Outline:
    """Create an Outline with sensible test defaults.

    Automatically adds required fields like created_at and updated_at
    if not provided, preventing Pydantic validation errors in tests.

    Args:
        **kwargs: Outline fields to override defaults

    Returns:
        Outline instance with test defaults applied

    Example:
        >>> outline = create_test_outline(
        ...     report_id="test-123",
        ...     title="Test Report",
        ...     sections=[]
        ... )
    """
    # Outline expects ISO format strings, not datetime objects
    now = datetime.now(UTC).isoformat()

    defaults = {
        "created_at": now,
        "updated_at": now,
    }

    # Merge defaults with provided kwargs (kwargs take precedence)
    merged = {**defaults, **kwargs}

    return Outline(**merged)
