# export_report - Bundle Living Reports for Backup or Transfer

The `export_report` tool packages a living report into a portable ZIP bundle. The bundle always includes `outline.json` and `manifest.json`, and can optionally include the report audit log and files stored under `report_files/`.

## Overview

Use `export_report` when you want a point-in-time artifact for backup, review, or later import into another environment. The export is non-destructive: it reads the current report state, writes a ZIP bundle, and records an `export` audit event on the source report.

## Parameters

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `report_selector` | string | Report ID or title to export |

### Optional Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `output_path` | string | Destination ZIP path. If an existing directory is provided, the bundle is written there as `<report_id>.zip`. | `null` |
| `include_audit` | boolean | Include `audit.jsonl` in the bundle | `true` |
| `include_assets` | boolean | Include files under `report_files/` | `true` |

## Bundle Layout

Typical bundle contents:

```text
report-export.zip
├── manifest.json
├── outline.json
├── audit.jsonl
└── report_files/
    └── growth.png
```

`manifest.json` captures bundle metadata including:

- `bundle_version`
- `exported_at`
- `report_id`
- `title`
- `outline_version`
- `include_audit`
- `include_assets`
- `audit_event_count`
- `asset_count`
- `outline_sha256`
- `files`

## Usage Examples

### Default Export

```python
result = await export_report(
    report_selector="Q1 Revenue Analysis"
)
```

### Export to Specific Path

```python
result = await export_report(
    report_selector="rpt_550e8400e29b11d4a716446655440000",
    output_path="./artifacts/reports/q1-revenue.zip"
)
```

### Minimal Bundle

```python
result = await export_report(
    report_selector="Q1 Revenue Analysis",
    include_audit=False,
    include_assets=False
)
```

## Response Format

### Success Response

```json
{
  "status": "success",
  "report_id": "rpt_550e8400e29b11d4a716446655440000",
  "title": "Q1 Revenue Analysis",
  "output": {
    "output_path": "/absolute/path/to/reports/exports/rpt_550e8400e29b11d4a716446655440000.zip"
  },
  "bundle": {
    "bundle_version": 1,
    "file_count": 4,
    "files": [
      "manifest.json",
      "outline.json",
      "audit.jsonl",
      "report_files/growth.png"
    ],
    "include_audit": true,
    "include_assets": true,
    "audit_event_count": 12,
    "asset_count": 1,
    "size_bytes": 4821,
    "outline_sha256": "..."
  },
  "warnings": [],
  "audit_action_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Notes

- The exported `audit.jsonl` reflects the report state before the export event itself is appended.
- Symlinked files inside `report_files/` are skipped and reported in `warnings`.
- If `output_path` is omitted, bundles are written under `<reports_root>/exports/`.

## Related Tools

- [`create_report`](create_report.md) - Create a new living report
- [`get_report`](get_report.md) - Inspect report structure and content
- [`render_report`](render_report.md) - Produce HTML, PDF, or Markdown output
