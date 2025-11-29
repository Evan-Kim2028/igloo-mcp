"""Tests for report selector resolution."""

import pytest

from igloo_mcp.living_reports.selector import ReportSelector, SelectorResolutionError
from igloo_mcp.living_reports.service import ReportService


@pytest.fixture
def report_service(tmp_path):
    return ReportService(reports_root=tmp_path / "reports")


@pytest.fixture
def selector(report_service):
    return ReportSelector(report_service.index)


def test_resolve_by_exact_id(report_service, selector):
    """Test resolution by exact UUID match."""
    _ = report_service.create_report("Test Report")

    resolved = selector.resolve(report_id)
    assert resolved == report_id


def test_resolve_by_exact_title(report_service, selector):
    """Test resolution by exact title match."""
    title = "My Exact Report Title"
    _ = report_service.create_report(title)

    resolved = selector.resolve(title)
    assert resolved == report_id


def test_resolve_by_partial_title(report_service, selector):
    """Test resolution by partial title match."""
    _ = report_service.create_report("Sales Report Q1")

    # Partial match should work
    resolved = selector.resolve("Sales Report")
    assert resolved == report_id

    # Case insensitive
    resolved = selector.resolve("sales report")
    assert resolved == report_id


def test_resolve_by_tag(report_service, selector):
    """Test resolution by tag-based selector."""
    _ = report_service.create_report("Test Report", tags=["q1", "sales"])

    resolved = selector.resolve("tag:sales")
    assert resolved == report_id


def test_ambiguous_selector_error(report_service, selector):
    """Test error when selector matches multiple reports."""
    report_service.create_report("Report 1", tags=["shared"])
    report_service.create_report("Report 2", tags=["shared"])

    with pytest.raises(SelectorResolutionError) as exc_info:
        selector.resolve("tag:shared")

    assert exc_info.value.error_type == "ambiguous"
    assert len(exc_info.value.candidates) == 2


def test_not_found_error(selector):
    """Test error when selector doesn't match anything."""
    with pytest.raises(SelectorResolutionError) as exc_info:
        selector.resolve("NonExistent Report")

    assert exc_info.value.error_type == "not_found"
    assert exc_info.value.selector == "NonExistent Report"


def test_strict_mode(report_service, selector):
    """Test strict mode only allows exact matches."""
    _ = report_service.create_report("Sales Report Q1")

    # Partial match should fail in strict mode
    with pytest.raises(SelectorResolutionError) as exc_info:
        selector.resolve("Sales Report", strict=True)

    assert exc_info.value.error_type == "not_found"


def test_selector_error_to_dict():
    """Test SelectorResolutionError.to_dict() method."""
    error = SelectorResolutionError(
        selector="bad selector",
        error_type="not_found",
        candidates=None,
        message="Custom message",
    )

    result = error.to_dict()
    assert result["error"] == "not_found"
    assert result["selector"] == "bad selector"
    assert result["message"] == "Custom message"


def test_selector_error_default_message():
    """Test default error messages."""
    not_found = SelectorResolutionError("missing", "not_found")
    assert "Report not found" in not_found.to_dict()["message"]

    ambiguous = SelectorResolutionError("ambiguous", "ambiguous", ["id1", "id2"])
    assert "Ambiguous selector" in ambiguous.to_dict()["message"]
