from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import Config
from ..lineage import LineageQueryService
from ..lineage.identifiers import parse_table_name
from ..profile_utils import ProfileSummary


def json_compatible(payload: Any) -> Any:
    """Convert non-JSON-serialisable objects to strings recursively."""

    return json.loads(json.dumps(payload, default=str))


def query_lineage_sync(
    object_name: str,
    direction: str,
    depth: int,
    fmt: str,
    catalog_dir: str,
    cache_dir: str,
    config: Config,
) -> Dict[str, Any]:
    service = LineageQueryService(
        catalog_dir=Path(catalog_dir),
        cache_root=Path(cache_dir),
    )

    default_db = config.snowflake.database
    default_schema = config.snowflake.schema

    qualified = parse_table_name(object_name).with_defaults(default_db, default_schema)
    base_key = qualified.key()
    candidates = [base_key]
    if not base_key.endswith("::task"):
        candidates.append(f"{base_key}::task")

    lineage_result = None
    resolved_key: Optional[str] = None
    for candidate in candidates:
        try:
            result = service.object_subgraph(
                candidate, direction=direction, depth=depth
            )
        except KeyError:
            continue
        lineage_result = result
        resolved_key = candidate
        break

    if lineage_result is None or resolved_key is None:
        raise ValueError(
            f"Object '{object_name}' not found in lineage graph. "
            f"Run build_catalog first or verify the object name. "
            f"Catalog directory: {catalog_dir}"
        )

    nodes = len(lineage_result.graph.nodes)
    edges = len(lineage_result.graph.edge_metadata)

    payload: Dict[str, Any] = {
        "object": resolved_key,
        "direction": direction,
        "depth": depth,
        "node_count": nodes,
        "edge_count": edges,
    }

    if fmt == "json":
        graph = getattr(lineage_result.graph, "to_dict", None)
        payload["graph"] = (
            graph() if callable(graph) else json_compatible(lineage_result.graph)
        )
    else:
        summary = [
            f"- {node.attributes.get('name', key)} ({node.node_type.value})"
            for key, node in lineage_result.graph.nodes.items()
        ]
        payload["summary"] = "\n".join(summary)
    return payload


def get_profile_recommendations(
    summary: ProfileSummary, current_profile: str | None
) -> list[str]:
    """Generate actionable recommendations for profile configuration."""
    recommendations = []

    if not summary.config_exists:
        recommendations.append(
            "Snowflake CLI configuration file not found. Run 'snow connection add' to create a profile."
        )
        return recommendations

    if summary.profile_count == 0:
        recommendations.append(
            "No profiles configured. Run 'snow connection add <profile_name>' to create your first profile."
        )
        return recommendations

    if not current_profile and not summary.default_profile:
        recommendations.append(
            f"Set SNOWFLAKE_PROFILE environment variable to one of: {', '.join(summary.available_profiles)}"
        )
        recommendations.append(
            "Or set a default profile by running 'snow connection set-default <profile_name>'"
        )

    if current_profile and current_profile not in summary.available_profiles:
        recommendations.append(
            f"Current profile '{current_profile}' not found. "
            f"Available profiles: {', '.join(summary.available_profiles)}"
        )

    if summary.profile_count == 1 and not summary.default_profile:
        profile_name = summary.available_profiles[0]
        recommendations.append(
            f"Consider setting '{profile_name}' as default: 'snow connection set-default {profile_name}'"
        )

    if not recommendations:
        recommendations.append("Profile configuration looks good!")

    return recommendations
