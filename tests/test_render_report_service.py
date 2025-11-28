"""Service-level tests for render_report behaviors."""

from __future__ import annotations

from pathlib import Path

from igloo_mcp.living_reports.service import ReportService


def test_render_service_dry_run_includes_qmd_path(tmp_path):
    """Dry run should return the QMD path and preview for convenience."""
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Render Dry Run Test")

    result = service.render_report(
        report_id=report_id, dry_run=True, include_preview=True
    )

    assert result["status"] == "success"
    qmd_path = result["output"].get("qmd_path")
    assert qmd_path
    assert Path(qmd_path).exists()
    # Preview should be generated from the QMD path
    assert "preview" in result
