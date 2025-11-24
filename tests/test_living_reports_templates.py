"""Tests for report templates."""

import pytest

from igloo_mcp.living_reports.service import ReportService


def test_create_with_monthly_sales_template(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    report_id = service.create_report("Q1 Sales", template="monthly_sales")
    outline = service.get_report_outline(report_id)

    assert len(outline.sections) == 3
    assert outline.sections[0].title == "Revenue Overview"
    assert outline.sections[1].title == "Top Products"
    assert outline.sections[2].title == "Trends & Insights"
    assert outline.metadata["template"] == "monthly_sales"


def test_create_with_quarterly_review_template(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    report_id = service.create_report("Q4 Review", template="quarterly_review")
    outline = service.get_report_outline(report_id)

    assert len(outline.sections) == 4
    assert outline.sections[0].title == "Executive Summary"
    assert outline.sections[1].title == "Key Metrics"
    assert outline.sections[2].title == "Strategic Initiatives"
    assert outline.sections[3].title == "Next Quarter Goals"
    assert outline.metadata["template"] == "quarterly_review"


def test_create_with_deep_dive_template(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    report_id = service.create_report("User Behavior Deep Dive", template="deep_dive")
    outline = service.get_report_outline(report_id)

    assert len(outline.sections) == 3
    assert outline.sections[0].title == "Topic Overview"
    assert outline.sections[1].title == "Analysis"
    assert outline.sections[2].title == "Recommendations"
    assert outline.metadata["template"] == "deep_dive"


def test_create_with_invalid_template(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    with pytest.raises(ValueError, match="Invalid template"):
        service.create_report("Test", template="nonexistent_template")


def test_create_with_default_template(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    report_id = service.create_report("Empty Report", template="default")
    outline = service.get_report_outline(report_id)

    assert len(outline.sections) == 0
    assert outline.metadata["template"] == "default"


def test_template_sections_have_unique_ids(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    # Create two reports with the same template
    id1 = service.create_report("Report 1", template="monthly_sales")
    id2 = service.create_report("Report 2", template="monthly_sales")

    outline1 = service.get_report_outline(id1)
    outline2 = service.get_report_outline(id2)

    # Section IDs should be different between reports
    ids1 = {s.section_id for s in outline1.sections}
    ids2 = {s.section_id for s in outline2.sections}
    assert ids1.isdisjoint(ids2)


def test_template_sections_have_correct_order(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    report_id = service.create_report("Ordered Report", template="quarterly_review")
    outline = service.get_report_outline(report_id)

    # Check that sections are in correct order
    orders = [s.order for s in outline.sections]
    assert orders == [0, 1, 2, 3]


def test_template_sections_have_notes(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    report_id = service.create_report("Noted Report", template="deep_dive")
    outline = service.get_report_outline(report_id)

    # All sections should have notes
    for section in outline.sections:
        assert section.notes is not None
        assert len(section.notes) > 0


def test_template_preserves_custom_metadata(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    report_id = service.create_report(
        "Custom Report",
        template="monthly_sales",
        tags=["custom"],
        owner="test_user",
        custom_field="value",
    )
    outline = service.get_report_outline(report_id)

    assert outline.metadata["template"] == "monthly_sales"
    assert outline.metadata["tags"] == ["custom"]
    assert outline.metadata["owner"] == "test_user"
    assert outline.metadata["custom_field"] == "value"
    assert len(outline.sections) == 3  # Template sections still added


def test_create_with_analyst_v1_template(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    report_id = service.create_report("Q1 Network Analysis", template="analyst_v1")
    outline = service.get_report_outline(report_id)

    assert len(outline.sections) == 4
    assert outline.sections[0].title == "Network Activity"
    assert outline.sections[1].title == "DEX Trading"
    assert outline.sections[2].title == "Objects"
    assert outline.sections[3].title == "Events"
    assert outline.metadata["template"] == "analyst_v1"

    # Check that sections have metadata with category
    for section in outline.sections:
        assert "metadata" in section.model_fields
        assert section.metadata.get("category") is not None


def test_analyst_v1_sections_have_category_metadata(tmp_path):
    service = ReportService(reports_root=tmp_path / "reports")

    report_id = service.create_report("Network Report", template="analyst_v1")
    outline = service.get_report_outline(report_id)

    categories = {s.metadata.get("category") for s in outline.sections}
    assert "network_activity" in categories
    assert "dex_trading" in categories
    assert "objects" in categories
    assert "events" in categories
