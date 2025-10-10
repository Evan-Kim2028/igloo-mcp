"""Utility functions for MCP tools."""

from typing import Any, Dict, List, Optional


def get_profile_recommendations(profile: Optional[str] = None) -> List[str]:
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
    """Convert object to JSON-compatible format.
    
    Args:
        obj: Object to convert
        
    Returns:
        JSON-compatible object
    """
    if isinstance(obj, dict):
        return {k: json_compatible(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [json_compatible(item) for item in obj]
    elif isinstance(obj, tuple):
        return list(json_compatible(item) for item in obj)
    elif hasattr(obj, '__dict__'):
        return json_compatible(obj.__dict__)
    else:
        return obj
