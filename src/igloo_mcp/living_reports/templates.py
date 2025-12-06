"""Report templates with pre-configured section structures.

Templates provide starting points for common report types,
giving LLM agents a clear structure to populate with content.

All templates enforce citation requirements by default.
"""

import uuid

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

SECTION_CONTENT_TEMPLATES: dict[str, dict[str, str | list[str]]] = {
    "findings": {
        "format": """## {heading}

| Finding | Metric | Impact |
|---------|--------|--------|
{findings_rows}

### Details

{findings_details}
""",
        "fields": ["findings"],
        "description": "Key findings table with details section",
    },
    "metrics": {
        "format": """## {heading}

| Metric | Value | Change |
|--------|-------|--------|
{metrics_rows}
""",
        "fields": ["metrics"],
        "description": "Metrics summary table",
    },
    "methodology": {
        "format": """## {heading}

**Data Sources:**
{data_sources}

**Time Period:** {time_period}

**Analysis Approach:**
{approach}
""",
        "fields": ["data_sources", "time_period", "approach"],
        "description": "Methodology section with sources and approach",
    },
    "executive_summary": {
        "format": """## {heading}

{summary}

### Key Highlights

{highlights}

### Recommendations

{recommendations}
""",
        "fields": ["summary", "highlights", "recommendations"],
        "description": "Executive summary with highlights and recommendations",
    },
}


def format_section_content(template_name: str, data: dict[str, str | list]) -> str:
    """Format section content using a predefined template.

    This function renders structured markdown content from template + data.
    Use for consistent formatting of common section types.

    Args:
        template_name: Template name (findings, metrics, methodology, executive_summary)
        data: Template data dictionary with required fields

    Returns:
        Formatted markdown string

    Raises:
        ValueError: If template name not found or required fields missing

    Example:
        >>> content = format_section_content("findings", {
        ...     "heading": "Key Findings",
        ...     "findings": [
        ...         {"title": "Revenue Growth", "metric": "+45%", "impact": "High"},
        ...         {"title": "User Retention", "metric": "92%", "impact": "Medium"},
        ...     ],
        ... })
    """
    if template_name not in SECTION_CONTENT_TEMPLATES:
        available = ", ".join(SECTION_CONTENT_TEMPLATES.keys())
        raise ValueError(f"Unknown section template: {template_name}. Available: {available}")

    template_info = SECTION_CONTENT_TEMPLATES[template_name]
    template_format = str(template_info["format"])

    # Set default heading
    data = dict(data)  # Copy to avoid mutation
    data.setdefault("heading", template_name.replace("_", " ").title())

    # Format based on template type
    if template_name == "findings":
        findings = data.get("findings", [])
        if not isinstance(findings, list):
            raise ValueError("findings template requires 'findings' list")

        rows = []
        details = []
        for idx, finding in enumerate(findings, 1):
            if isinstance(finding, dict):
                title = finding.get("title", f"Finding {idx}")
                metric = finding.get("metric", "N/A")
                impact = finding.get("impact", "N/A")
                description = finding.get("description", "")
                rows.append(f"| {title} | {metric} | {impact} |")
                if description:
                    details.append(f"**{title}:** {description}")
            else:
                rows.append(f"| Finding {idx} | N/A | N/A |")

        data["findings_rows"] = "\n".join(rows) if rows else "| No findings | - | - |"
        data["findings_details"] = "\n\n".join(details) if details else "_No details available._"

    elif template_name == "metrics":
        metrics = data.get("metrics", [])
        if not isinstance(metrics, list):
            raise ValueError("metrics template requires 'metrics' list")

        rows = []
        for metric in metrics:
            if isinstance(metric, dict):
                name = metric.get("name", "Unknown")
                value = metric.get("value", "N/A")
                change = metric.get("change", "-")
                rows.append(f"| {name} | {value} | {change} |")

        data["metrics_rows"] = "\n".join(rows) if rows else "| No metrics | - | - |"

    elif template_name == "methodology":
        # Format data_sources as bullet list if it's a list
        sources = data.get("data_sources", "Not specified")
        if isinstance(sources, list):
            data["data_sources"] = "\n".join(f"- {s}" for s in sources)
        data.setdefault("time_period", "Not specified")
        data.setdefault("approach", "Not specified")

    elif template_name == "executive_summary":
        # Format highlights as bullet list if it's a list
        highlights = data.get("highlights", "")
        if isinstance(highlights, list):
            data["highlights"] = "\n".join(f"- {h}" for h in highlights)
        recommendations = data.get("recommendations", "")
        if isinstance(recommendations, list):
            data["recommendations"] = "\n".join(f"- {r}" for r in recommendations)
        data.setdefault("summary", "")

    # Format the template with data
    try:
        return template_format.format(**data)
    except KeyError as e:
        raise ValueError(f"Missing required field for {template_name} template: {e}") from e


def list_section_content_templates() -> dict[str, str]:
    """List available section content templates with descriptions.

    Returns:
        Dictionary mapping template name to description
    """
    return {name: str(info.get("description", "No description")) for name, info in SECTION_CONTENT_TEMPLATES.items()}
