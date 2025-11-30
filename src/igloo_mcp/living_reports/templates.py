"""Report templates with pre-configured section structures.

Templates provide starting points for common report types,
giving LLM agents a clear structure to populate with content.
"""

import uuid

from .models import Section


def monthly_sales() -> list[Section]:
    """Monthly sales report template.

    Sections:
    - Revenue Overview: High-level revenue metrics and trends
    - Top Products: Best-performing products or categories
    - Trends & Insights: Patterns and noteworthy observations
    """
    return [
        Section(
            section_id=str(uuid.uuid4()),
            title="Revenue Overview",
            order=0,
            insight_ids=[],
            notes="High-level revenue metrics and trends for the month",
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Top Products",
            order=1,
            insight_ids=[],
            notes="Best-performing products or categories",
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Trends & Insights",
            order=2,
            insight_ids=[],
            notes="Key patterns and noteworthy observations",
        ),
    ]


def quarterly_review() -> list[Section]:
    """Quarterly business review template.

    Sections:
    - Executive Summary: High-level overview for stakeholders
    - Key Metrics: Critical KPIs and performance indicators
    - Strategic Initiatives: Progress on major projects
    - Next Quarter Goals: Forward-looking objectives
    """
    return [
        Section(
            section_id=str(uuid.uuid4()),
            title="Executive Summary",
            order=0,
            insight_ids=[],
            notes="High-level overview for executive stakeholders",
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Key Metrics",
            order=1,
            insight_ids=[],
            notes="Critical KPIs and performance indicators",
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Strategic Initiatives",
            order=2,
            insight_ids=[],
            notes="Progress on major strategic projects",
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Next Quarter Goals",
            order=3,
            insight_ids=[],
            notes="Forward-looking objectives and priorities",
        ),
    ]


def deep_dive() -> list[Section]:
    """Single-topic deep dive template.

    Sections:
    - Topic Overview: Introduction and context
    - Analysis: Detailed examination and findings
    - Recommendations: Actionable next steps
    """
    return [
        Section(
            section_id=str(uuid.uuid4()),
            title="Topic Overview",
            order=0,
            insight_ids=[],
            notes="Introduction and background context",
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Analysis",
            order=1,
            insight_ids=[],
            notes="Detailed examination and key findings",
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Recommendations",
            order=2,
            insight_ids=[],
            notes="Actionable recommendations and next steps",
        ),
    ]


def analyst_v1() -> list[Section]:
    """Analyst report template with standard blockchain analysis sections.

    Sections:
    - Network Activity: Network-level metrics and activity patterns
    - DEX Trading: Decentralized exchange trading analysis
    - Objects: On-chain objects and contract analysis
    - Events: Significant events and transactions
    """
    return [
        Section(
            section_id=str(uuid.uuid4()),
            title="Network Activity",
            order=0,
            insight_ids=[],
            notes="Network-level metrics and activity patterns",
            metadata={"category": "network_activity"},
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="DEX Trading",
            order=1,
            insight_ids=[],
            notes="Decentralized exchange trading analysis",
            metadata={"category": "dex_trading"},
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Objects",
            order=2,
            insight_ids=[],
            notes="On-chain objects and contract analysis",
            metadata={"category": "objects"},
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Events",
            order=3,
            insight_ids=[],
            notes="Significant events and transactions",
            metadata={"category": "events"},
        ),
    ]


def default() -> list[Section]:
    """Default template - empty report.

    Returns empty section list for maximum flexibility.
    """
    return []


# Template registry for lookup
TEMPLATES = {
    "default": default,
    "monthly_sales": monthly_sales,
    "quarterly_review": quarterly_review,
    "deep_dive": deep_dive,
    "analyst_v1": analyst_v1,
}


def get_template(name: str) -> list[Section]:
    """Get template sections by name.

    Args:
        name: Template name (default, monthly_sales, quarterly_review, deep_dive)

    Returns:
        List of pre-configured sections

    Raises:
        ValueError: If template name not found
    """
    if name not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        raise ValueError(f"Unknown template: {name}. Available templates: {available}")
    return TEMPLATES[name]()
