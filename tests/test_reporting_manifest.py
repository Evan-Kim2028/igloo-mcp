from __future__ import annotations

from pathlib import Path

from igloo_mcp.reporting.manifest import (
    DatasetRef,
    DatasetSource,
    ReportManifest,
    TemplatesConfig,
    load_manifest,
    manifest_json_schema,
)


def test_load_manifest_minimal(tmp_path: Path) -> None:
    manifest_path = tmp_path / "report.yaml"
    manifest_path.write_text(
        """
id: "demo-report"
title: "Demo Report"
templates:
  main: "templates/report.md"
datasets:
  - name: "sales"
    source:
      execution_id: "exec-123"
outputs:
  - name: "default"
    format: "markdown"
    path: "reports/demo.md"
""".lstrip(),
        encoding="utf-8",
    )

    manifest = load_manifest(manifest_path)

    assert isinstance(manifest, ReportManifest)
    assert manifest.id == "demo-report"
    assert manifest.templates.main == "templates/report.md"
    assert len(manifest.datasets) == 1
    assert manifest.datasets[0].name == "sales"
    assert manifest.datasets[0].source.execution_id == "exec-123"
    assert len(manifest.outputs) == 1
    assert manifest.outputs[0].format == "markdown"


def test_manifest_json_schema_contains_key_fields() -> None:
    schema = manifest_json_schema()
    assert isinstance(schema, dict)
    properties = schema.get("properties") or {}
    assert "id" in properties
    assert "templates" in properties
    assert "datasets" in properties
    assert "outputs" in properties


def test_dataset_source_requires_identifier() -> None:
    # At least one identifier must be present
    try:
        DatasetSource()  # type: ignore[call-arg]
    except Exception:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("DatasetSource should require an identifier")

    src = DatasetSource(execution_id="abc")
    ref = DatasetRef(name="demo", source=src)
    manifest = ReportManifest(
        id="demo", templates=TemplatesConfig(main="tmpl.md"), datasets=[ref], outputs=[]
    )
    assert manifest.datasets[0].source.execution_id == "abc"
