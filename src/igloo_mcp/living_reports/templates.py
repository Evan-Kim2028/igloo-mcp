"""Report templates with pre-configured section structures.

Templates provide starting points for common report types,
giving LLM agents a clear structure to populate with content.

All templates enforce citation requirements by default.
"""

from __future__ import annotations

import uuid
from typing import Any

from .models import Section


def default() -> list[Section]:
    """Default template with standard report structure.

    Provides a clean, professional structure suitable for most analysis reports.
    All insights should include citations for data provenance.

    Sections:
    - Executive Summary: High-level overview and key takeaways
    - Analysis: Detailed findings and examination
    - Recommendations: Actionable next steps
    """
    return [
        Section(
            section_id=str(uuid.uuid4()),
            title="Executive Summary",
            order=0,
            insight_ids=[],
            notes="High-level overview and key takeaways",
            metadata={"category": "summary"},
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Analysis",
            order=1,
            insight_ids=[],
            notes="Detailed findings and examination",
            metadata={"category": "analysis"},
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Recommendations",
            order=2,
            insight_ids=[],
            notes="Actionable next steps and recommendations",
            metadata={"category": "recommendations"},
        ),
    ]


def deep_dive() -> list[Section]:
    """Single-topic deep dive template.

    For in-depth technical analysis of a specific topic or system.
    All insights should include citations for data provenance.

    Sections:
    - Overview: Introduction and background context
    - Methodology: Data sources and analysis approach
    - Findings: Detailed examination and key discoveries
    - Recommendations: Actionable next steps
    """
    return [
        Section(
            section_id=str(uuid.uuid4()),
            title="Overview",
            order=0,
            insight_ids=[],
            notes="Introduction and background context",
            metadata={"category": "overview"},
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Methodology",
            order=1,
            insight_ids=[],
            notes="Data sources and analysis approach",
            metadata={"category": "methodology"},
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Findings",
            order=2,
            insight_ids=[],
            notes="Detailed examination and key discoveries",
            metadata={"category": "findings"},
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Recommendations",
            order=3,
            insight_ids=[],
            notes="Actionable next steps and recommendations",
            metadata={"category": "recommendations"},
        ),
    ]


def analyst_v1() -> list[Section]:
    """Analyst report template for blockchain/protocol analysis.

    Specialized structure for on-chain data analysis.
    All insights should include citations for data provenance.

    Sections:
    - Executive Summary: High-level overview for stakeholders
    - Methodology: Data sources, time range, and analysis approach
    - Key Findings: Primary discoveries and insights
    - Detailed Analysis: In-depth examination of findings
    - Recommendations: Actionable next steps
    """
    return [
        Section(
            section_id=str(uuid.uuid4()),
            title="Executive Summary",
            order=0,
            insight_ids=[],
            notes="High-level overview for stakeholders",
            metadata={"category": "summary"},
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Methodology",
            order=1,
            insight_ids=[],
            notes="Data sources, time range, and analysis approach",
            metadata={"category": "methodology"},
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Key Findings",
            order=2,
            insight_ids=[],
            notes="Primary discoveries and insights",
            metadata={"category": "findings"},
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Detailed Analysis",
            order=3,
            insight_ids=[],
            notes="In-depth examination of findings",
            metadata={"category": "analysis"},
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Recommendations",
            order=4,
            insight_ids=[],
            notes="Actionable next steps and recommendations",
            metadata={"category": "recommendations"},
        ),
    ]


def empty() -> list[Section]:
    """Empty template - no pre-configured sections.

    For maximum flexibility when you want to build structure from scratch.
    """
    return []


# Template registry for lookup
TEMPLATES = {
    "default": default,
    "deep_dive": deep_dive,
    "analyst_v1": analyst_v1,
    "empty": empty,
}


def get_template(name: str) -> list[Section]:
    """Get template sections by name.

    Args:
        name: Template name (default, deep_dive, analyst_v1, empty)

    Returns:
        List of pre-configured sections

    Raises:
        ValueError: If template name not found
    """
    if name not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        raise ValueError(f"Unknown template: {name}. Available templates: {available}")
    return TEMPLATES[name]()


# =============================================================================
# Section Content Templates
# =============================================================================
# These templates format section content with structured markdown.
# Use via evolve_report with template="findings" and template_data={...}
#
# SINGLE SOURCE OF TRUTH: evolve_report.py delegates to these functions.

# Template metadata for discovery via get_report_schema
SECTION_CONTENT_TEMPLATES: dict[str, dict[str, Any]] = {
    "findings": {
        "description": "Key findings with optional metrics and action items",
        "aliases": ["findings_list"],
        "required_fields": ["findings"],
        "optional_fields": ["heading"],
        "example": {
            "heading": "Key Findings",
            "findings": [
                {
                    "title": "Revenue Growth",
                    "description": "Strong YoY performance",
                    "metric": {"name": "YoY Growth", "value": "+45%", "trend": "↑"},
                    "actions": ["Expand to new markets"],
                }
            ],
        },
    },
    "metrics": {
        "description": "Metrics snapshot table with optional callouts",
        "aliases": ["metrics_snapshot"],
        "required_fields": ["metrics"],
        "optional_fields": ["heading", "callouts"],
        "example": {
            "heading": "Q4 Metrics",
            "metrics": [
                {"name": "Revenue", "value": "$2.4M", "target": "$2.0M", "delta": "+20%"},
                {"name": "Users", "value": "50K", "target": "45K", "delta": "+11%"},
            ],
            "callouts": [{"title": "Record Quarter", "detail": "Highest revenue ever"}],
        },
    },
    "bullet_list": {
        "description": "Simple bullet point list",
        "aliases": ["bullet", "summary_bullets"],
        "required_fields": ["items"],
        "optional_fields": ["heading"],
        "example": {
            "heading": "Summary",
            "items": ["First key point", "Second key point", "Third key point"],
        },
    },
    "executive_summary": {
        "description": "Executive summary with key takeaways and recommendation",
        "aliases": ["exec_summary"],
        "required_fields": [],
        "optional_fields": ["headline", "context", "key_points", "recommendation", "conclusion"],
        "example": {
            "headline": "Q4 Performance Review",
            "context": "This quarter marked significant growth...",
            "key_points": [
                {"title": "Revenue", "detail": "Up 25% YoY"},
                "Customer satisfaction at all-time high",
            ],
            "recommendation": "Increase investment in growth initiatives",
            "conclusion": "Strong foundation for continued expansion",
        },
    },
    "action_items": {
        "description": "Action items with owners, due dates, and priority",
        "aliases": ["next_steps", "actions"],
        "required_fields": ["actions"],
        "optional_fields": ["heading"],
        "example": {
            "heading": "Next Steps",
            "actions": [
                {
                    "description": "Complete security audit",
                    "owner": "Security Team",
                    "due": "2024-01-15",
                    "priority": "High",
                },
                {"description": "Update documentation", "owner": "TBD"},
            ],
        },
    },
    "methodology": {
        "description": "Methodology section with data sources and approach",
        "aliases": [],
        "required_fields": [],
        "optional_fields": ["heading", "data_sources", "time_period", "approach"],
        "example": {
            "heading": "Methodology",
            "data_sources": ["Snowflake analytics warehouse", "On-chain transaction data"],
            "time_period": "Q4 2024 (Oct 1 - Dec 31)",
            "approach": "Aggregated daily metrics with 7-day moving averages",
        },
    },
}


def render_section_template(
    template_name: str,
    template_data: dict[str, Any],
    section_title: str = "Untitled Section",
) -> str:
    """Render structured markdown content from a section template.

    This is the SINGLE SOURCE OF TRUTH for section content templates.
    evolve_report.py delegates to this function.

    Args:
        template_name: Template name (findings, metrics, bullet_list, executive_summary, action_items, methodology)
        template_data: Data to populate the template
        section_title: Fallback title if not provided in template_data

    Returns:
        Formatted markdown string

    Raises:
        ValueError: If template name not found or required fields missing

    Example:
        >>> content = render_section_template("findings", {
        ...     "heading": "Key Findings",
        ...     "findings": [
        ...         {"title": "Revenue Growth", "metric": {"name": "YoY", "value": "+45%", "trend": "↑"}},
        ...     ],
        ... }, "Analysis")
    """
    if not isinstance(template_name, str):
        raise ValueError("template must be a string")

    normalized_name = template_name.strip().lower()
    data = template_data or {}

    # Resolve aliases
    resolved_name = _resolve_template_alias(normalized_name)
    if resolved_name is None:
        available = ", ".join(SECTION_CONTENT_TEMPLATES.keys())
        raise ValueError(f"Unknown section template: {template_name}. Available: {available}")

    # Dispatch to specific renderer
    if resolved_name == "findings":
        return _render_findings(data, section_title)
    elif resolved_name == "metrics":
        return _render_metrics(data, section_title)
    elif resolved_name == "bullet_list":
        return _render_bullet_list(data, section_title)
    elif resolved_name == "executive_summary":
        return _render_executive_summary(data, section_title)
    elif resolved_name == "action_items":
        return _render_action_items(data, section_title)
    elif resolved_name == "methodology":
        return _render_methodology(data, section_title)
    else:
        raise ValueError(f"Unknown section template: {template_name}")


def _resolve_template_alias(name: str) -> str | None:
    """Resolve template alias to canonical name."""
    # Check direct match
    if name in SECTION_CONTENT_TEMPLATES:
        return name
    # Check aliases
    for canonical, info in SECTION_CONTENT_TEMPLATES.items():
        if name in info.get("aliases", []):
            return canonical
    return None


def _render_findings(data: dict[str, Any], section_title: str) -> str:
    """Render findings template."""
    findings = data.get("findings", [])
    if not findings:
        raise ValueError("findings template requires 'findings' array")

    heading = data.get("heading") or f"Key Findings - {section_title}"
    lines = [f"## {heading.strip()}", ""]

    for idx, finding in enumerate(findings, 1):
        title = finding.get("title") or f"Finding {idx}"
        summary = finding.get("description") or finding.get("summary") or ""
        metric = finding.get("metric") or {}

        lines.append(f"### {idx}. {title.strip()}")
        if metric:
            lines.append("")
            lines.append("| Metric | Value | Trend |")
            lines.append("| --- | --- | --- |")
            lines.append(f"| {metric.get('name', 'Value')} | {metric.get('value', '-')} | {metric.get('trend', '-')} |")
        if summary:
            lines.append("")
            lines.append(summary.strip())
        if finding.get("actions"):
            lines.append("")
            lines.append("**Next Steps**")
            for action in finding["actions"]:
                lines.append(f"- {action}")
        lines.append("")

    return "\n".join(lines).strip()


def _render_metrics(data: dict[str, Any], section_title: str) -> str:
    """Render metrics snapshot template."""
    metrics = data.get("metrics", [])
    if not metrics:
        raise ValueError("metrics template requires 'metrics' array")

    heading = data.get("heading") or f"{section_title} Metrics"
    lines = [f"## {heading.strip()}", "", "| Metric | Value | Target | Delta |", "| --- | --- | --- | --- |"]

    for metric in metrics:
        lines.append(
            "| {name} | {value} | {target} | {delta} |".format(
                name=metric.get("name", "Metric"),
                value=metric.get("value", "-"),
                target=metric.get("target", "-"),
                delta=metric.get("delta", "-"),
            )
        )

    if data.get("callouts"):
        lines.append("")
        lines.append("### Callouts")
        for callout in data["callouts"]:
            title = callout.get("title", "Callout")
            detail = callout.get("detail") or callout.get("description") or ""
            lines.append(f"- **{title}** — {detail}")

    return "\n".join(lines).strip()


def _render_bullet_list(data: dict[str, Any], section_title: str) -> str:
    """Render bullet list template."""
    items = data.get("items") or data.get("bullets")
    if not items:
        raise ValueError("bullet_list template requires 'items' array")

    heading = data.get("heading") or section_title or "Summary"
    lines = [f"## {heading.strip()}", ""]
    for item in items:
        lines.append(f"- {item}")

    return "\n".join(lines).strip()


def _render_executive_summary(data: dict[str, Any], section_title: str) -> str:
    """Render executive summary template."""
    headline = data.get("headline") or data.get("title") or section_title
    key_points = data.get("key_points") or data.get("takeaways") or []
    recommendation = data.get("recommendation") or data.get("action")
    conclusion = data.get("conclusion") or data.get("summary")

    lines = [f"## {headline.strip()}", ""]

    if data.get("context"):
        lines.append(data["context"].strip())
        lines.append("")

    if key_points:
        lines.append("### Key Takeaways")
        lines.append("")
        for idx, point in enumerate(key_points, 1):
            if isinstance(point, dict):
                title = point.get("title", f"Point {idx}")
                detail = point.get("detail", "")
                lines.append(f"{idx}. **{title}** — {detail}")
            else:
                lines.append(f"{idx}. {point}")
        lines.append("")

    if recommendation:
        lines.append("### Recommendation")
        lines.append("")
        lines.append(f"> {recommendation.strip()}")
        lines.append("")

    if conclusion:
        lines.append(conclusion.strip())
        lines.append("")

    return "\n".join(lines).strip()


def _render_action_items(data: dict[str, Any], section_title: str) -> str:
    """Render action items template."""
    actions = data.get("actions") or data.get("items") or []
    if not actions:
        raise ValueError("action_items template requires 'actions' array")

    heading = data.get("heading") or "Action Items"
    lines = [f"## {heading.strip()}", ""]

    has_table_data = any(isinstance(a, dict) and (a.get("owner") or a.get("due") or a.get("priority")) for a in actions)

    if has_table_data:
        lines.append("| # | Action | Owner | Due | Priority |")
        lines.append("| --- | --- | --- | --- | --- |")
        for idx, action in enumerate(actions, 1):
            if isinstance(action, dict):
                desc = action.get("description") or action.get("action") or action.get("title") or ""
                owner = action.get("owner") or "TBD"
                due = action.get("due") or action.get("due_date") or "-"
                priority = action.get("priority") or "Medium"
                lines.append(f"| {idx} | {desc} | {owner} | {due} | {priority} |")
            else:
                lines.append(f"| {idx} | {action} | TBD | - | Medium |")
    else:
        for idx, action in enumerate(actions, 1):
            if isinstance(action, dict):
                desc = action.get("description") or action.get("action") or action.get("title") or ""
                lines.append(f"{idx}. {desc}")
            else:
                lines.append(f"{idx}. {action}")

    lines.append("")
    return "\n".join(lines).strip()


def _render_methodology(data: dict[str, Any], section_title: str) -> str:
    """Render methodology template."""
    heading = data.get("heading") or section_title or "Methodology"
    lines = [f"## {heading.strip()}", ""]

    # Data sources
    sources = data.get("data_sources", [])
    if sources:
        lines.append("**Data Sources:**")
        if isinstance(sources, list):
            for source in sources:
                lines.append(f"- {source}")
        else:
            lines.append(str(sources))
        lines.append("")

    # Time period
    time_period = data.get("time_period")
    if time_period:
        lines.append(f"**Time Period:** {time_period}")
        lines.append("")

    # Approach
    approach = data.get("approach")
    if approach:
        lines.append("**Analysis Approach:**")
        lines.append(approach.strip())
        lines.append("")

    return "\n".join(lines).strip()


def list_section_content_templates() -> dict[str, dict[str, Any]]:
    """List available section content templates with full metadata.

    Returns:
        Dictionary with template info including description, aliases, fields, and example.

    Example:
        >>> templates = list_section_content_templates()
        >>> print(templates["findings"]["description"])
        'Key findings with optional metrics and action items'
    """
    return SECTION_CONTENT_TEMPLATES.copy()


def get_section_template_names() -> list[str]:
    """Get list of all valid template names including aliases.

    Returns:
        List of all template names that can be used.
    """
    names = list(SECTION_CONTENT_TEMPLATES.keys())
    for info in SECTION_CONTENT_TEMPLATES.values():
        names.extend(info.get("aliases", []))
    return sorted(set(names))


# Legacy alias for backward compatibility
def format_section_content(template_name: str, data: dict[str, Any]) -> str:
    """Format section content using a predefined template.

    DEPRECATED: Use render_section_template() instead.
    This function is kept for backward compatibility.
    """
    return render_section_template(template_name, data, "Untitled Section")
