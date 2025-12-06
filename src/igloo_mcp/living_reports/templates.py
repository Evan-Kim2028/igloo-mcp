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
