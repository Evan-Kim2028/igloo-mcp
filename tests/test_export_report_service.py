"""Service-level tests for report export bundles."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from igloo_mcp.living_reports.service import ReportService


def test_export_report_includes_outline_audit_and_assets(tmp_path):
    """Export should bundle the report outline, audit log, and report_files assets."""
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Export Bundle Test")
    storage = service.global_storage.get_report_storage(report_id)

    asset_path = storage.report_dir / "report_files" / "growth.png"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(b"fake-chart")

    result = service.export_report(report_id=report_id, actor="human")
    bundle_path = Path(result["output"]["output_path"])

    assert result["status"] == "success"
    assert bundle_path.exists()
    assert result["bundle"]["asset_count"] == 1
    assert result["bundle"]["include_audit"] is True
    assert result["bundle"]["include_assets"] is True

    with zipfile.ZipFile(bundle_path) as bundle:
        names = set(bundle.namelist())
        assert "manifest.json" in names
        assert "outline.json" in names
        assert "audit.jsonl" in names
        assert "report_files/growth.png" in names

        manifest = json.loads(bundle.read("manifest.json"))
        outline = json.loads(bundle.read("outline.json"))
        audit_lines = bundle.read("audit.jsonl").decode("utf-8").strip().splitlines()

        assert manifest["report_id"] == report_id
        assert manifest["title"] == "Export Bundle Test"
        assert manifest["asset_count"] == 1
        assert manifest["include_audit"] is True
        assert outline["title"] == "Export Bundle Test"
        assert bundle.read("report_files/growth.png") == b"fake-chart"

        # The bundle should capture the report state before the export event is appended.
        assert len(audit_lines) == 1
        assert json.loads(audit_lines[0])["action_type"] == "create"

    events = storage.load_audit_events()
    assert events[-1].action_type == "export"
    assert events[-1].actor == "human"
    assert events[-1].action_id == result["audit_action_id"]


def test_export_report_can_skip_audit_and_assets_and_write_into_directory(tmp_path):
    """Export should support minimal bundles and directory-style output paths."""
    service = ReportService(reports_root=tmp_path / "reports")
    report_id = service.create_report("Minimal Export Test")
    storage = service.global_storage.get_report_storage(report_id)

    asset_path = storage.report_dir / "report_files" / "skip-me.png"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(b"ignore-me")

    output_dir = tmp_path / "bundle-output"
    output_dir.mkdir()

    result = service.export_report(
        report_id=report_id,
        output_path=output_dir,
        include_audit=False,
        include_assets=False,
    )
    bundle_path = Path(result["output"]["output_path"])

    assert bundle_path == (output_dir / f"{report_id}.zip").resolve()
    assert result["bundle"]["file_count"] == 2
    assert result["bundle"]["audit_event_count"] == 0
    assert result["bundle"]["asset_count"] == 0

    with zipfile.ZipFile(bundle_path) as bundle:
        names = set(bundle.namelist())
        assert names == {"manifest.json", "outline.json"}

        manifest = json.loads(bundle.read("manifest.json"))
        assert manifest["include_audit"] is False
        assert manifest["include_assets"] is False
        assert manifest["asset_count"] == 0
        assert manifest["audit_event_count"] == 0
