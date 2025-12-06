"""Service-level tests for render_report behaviors."""

from __future__ import annotations

import uuid
from pathlib import Path

from igloo_mcp.living_reports.models import Citation, Insight, Section
from igloo_mcp.living_reports.service import ReportService


def test_render_service_dry_run_includes_qmd_path(tmp_path):
    """Dry run should return the QMD path and preview for convenience."""
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Render Dry Run Test")

    result = service.render_report(report_id=report_id, dry_run=True, include_preview=True)

    assert result["status"] == "success"
    qmd_path = result["output"].get("qmd_path")
    assert qmd_path
    assert Path(qmd_path).exists()
    # Preview should be generated from the QMD path
    assert "preview" in result


def _seed_outline_with_sections(service: ReportService, report_id: str) -> tuple[Section, Section, Insight]:
    outline = service.get_report_outline(report_id)
    insight_id = str(uuid.uuid4())
    sections = [
        Section(
            section_id=str(uuid.uuid4()),
            title="Section Beta",
            order=2,
            insight_ids=[insight_id],
            notes="Second section notes",
        ),
        Section(
            section_id=str(uuid.uuid4()),
            title="Section Alpha",
            order=0,
            insight_ids=[insight_id],
            notes="First section notes",
        ),
    ]

    insight = Insight(
        insight_id=insight_id,
        summary="Ordering insight",
        importance=7,
        citations=[Citation(source="query", provider="snowflake", execution_id="exec-ordering")],
    )

    outline.sections = sections
    outline.insights = [insight]
    service.update_report_outline(report_id, outline)
    return sections[0], sections[1], insight


def test_render_service_sorts_sections_and_generates_toc(tmp_path):
    """QMD output should include table of contents with order-aware sections."""
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Ordering Test")
    beta, alpha, _insight = _seed_outline_with_sections(service, report_id)

    result = service.render_report(report_id=report_id, dry_run=True)
    qmd_path = Path(result["output"]["qmd_path"])
    content = qmd_path.read_text(encoding="utf-8")

    assert "## Table of Contents" in content
    assert content.index(f"- [{alpha.title}](#section-{alpha.section_id})") < content.index(
        f"- [{beta.title}](#section-{beta.section_id})"
    )
    assert content.index(f"## {alpha.title}") < content.index(f"## {beta.title}")
    assert f"#section-{alpha.section_id}" in content


def test_render_service_embeds_chart_references(tmp_path):
    """Referenced charts should be kept in the generated QMD for Quarto renders."""
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Chart Test")
    _beta, _alpha, _insight = _seed_outline_with_sections(service, report_id)

    storage = service.global_storage.get_report_storage(report_id)
    chart_path = storage.report_dir / "report_files" / "growth.png"
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_bytes(b"fake-chart-bytes")

    outline = service.get_report_outline(report_id)
    outline.metadata.setdefault("charts", {})["growth"] = {
        "path": str(chart_path),
        "description": "Growth Chart",
    }
    outline.insights[0].metadata["chart_id"] = "growth"
    service.update_report_outline(report_id, outline)

    result = service.render_report(report_id=report_id, dry_run=True)
    qmd_path = Path(result["output"]["qmd_path"])
    content = qmd_path.read_text(encoding="utf-8")

    assert f"![Growth Chart]({chart_path})" in content
