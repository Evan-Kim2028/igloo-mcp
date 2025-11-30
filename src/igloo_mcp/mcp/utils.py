"""Utility functions for MCP tools."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID


def get_profile_recommendations(profile: str | None = None) -> list[str]:
    """Get profile recommendations for troubleshooting.

    Args:
        profile: Profile name to get recommendations for

    Returns:
        List of recommendation strings
    """
    recommendations = []

    if not profile:
        recommendations.append("No profile specified. Use --profile flag or set SNOWFLAKE_PROFILE env var")
        recommendations.append("Run 'snow connection list' to see available profiles")
        recommendations.append("Create a profile with 'snow connection add'")
    else:
        recommendations.append(f"Profile '{profile}' specified")
        recommendations.append("Verify profile exists with 'snow connection list'")
        recommendations.append("Test profile with 'snow sql -q \"SELECT 1\" --connection {profile}'")

    return recommendations


def json_compatible(obj: Any) -> Any:
    """Convert an arbitrary object to a JSON-serializable structure."""

    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    if isinstance(obj, Decimal):
        # Preserve integers as ints to avoid float precision loss.
        if obj == obj.to_integral_value():
            return int(obj)
        return float(obj)

    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()

    if isinstance(obj, timedelta):
        return obj.total_seconds()

    if isinstance(obj, UUID):
        return str(obj)

    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            return obj.hex()

    if isinstance(obj, dict):
        return {k: json_compatible(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set, frozenset)):
        return [json_compatible(item) for item in obj]

    if hasattr(obj, "_asdict"):
        return json_compatible(obj._asdict())  # type: ignore[attr-defined]

    if hasattr(obj, "__dict__"):
        return json_compatible(obj.__dict__)

    return str(obj)
