# render_report - Report Rendering

Render living reports to various output formats (HTML, PDF, Markdown, DOCX) using Quarto.

**Enhanced in v0.3.2** with `preview_max_chars` parameter for configurable preview truncation.

## Overview

The `render_report` tool transforms Living Reports from JSON structure into human-readable documents. It supports:

- **Multiple formats**: HTML, PDF, Markdown, DOCX
- **Quarto rendering**: Professional document generation with templates
- **Optional preview** ✨ v0.3.2: Configurable preview truncation (100-10,000 chars)
- **Dry-run mode**: Generate QMD without rendering
- **Automatic cleanup**: Manages temporary files

## Parameters

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `report_selector` | string | Report ID or title to render |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | string | "html" | Output format: `html`, `pdf`, `markdown`, or `docx` |
| `include_preview` | boolean | false | Return truncated preview of rendered content |
| `preview_max_chars` | integer | 2000 | **✨ v0.3.2** - Preview truncation size (100-10,000) |
| `dry_run` | boolean | false | Generate QMD file without rendering |
| `regenerate_outline_view` | boolean | true | Regenerate QMD from current outline |
| `options` | object | null | Additional Quarto rendering options |

## Output Formats

### HTML (Default)

Professional web-ready reports with:
- Responsive layout
- Table of contents
- Syntax highlighting
- Interactive elements

**Use when**: Sharing reports via web or email.

**Example**:
```json
{
  "report_selector": "Q1 Analysis",
  "format": "html"
}
```

---

### PDF

Print-ready documents with:
- Professional formatting
- Page numbering
- Headers/footers
- Table of contents

**Use when**: Archiving or formal distribution.

**Example**:
```json
{
  "report_selector": "Q1 Analysis",
  "format": "pdf"
}
```

**Note**: Requires Quarto PDF dependencies (TinyTeX or LaTeX).

---

### Markdown

Plain markdown output for:
- Version control
- Documentation systems
- Further processing

**Use when**: You need editable source or integration with docs systems.

**Example**:
```json
{
  "report_selector": "Q1 Analysis",
  "format": "markdown"
}
```

---

### DOCX

Microsoft Word format for:
- Collaborative editing
- Corporate workflows
- Template-based reports

**Use when**: Reports need manual editing or Word-based workflows.

**Example**:
```json
{
  "report_selector": "Q1 Analysis",
  "format": "docx"
}
```

---

## Preview Feature (v0.3.2)

### preview_max_chars Parameter

Control the size of preview text returned in the response.

**Options**:
- Range: 100 to 10,000 characters
- Default: 2000 characters
- Only applies when `include_preview=true`

### Token Efficiency

| Preview Size | Approximate Tokens | Use Case |
|--------------|-------------------|----------|
| 100 chars | ~30 tokens | Quick validation |
| 500 chars | ~150 tokens | Executive summary |
| 2000 chars (default) | ~600 tokens | Standard preview |
| 5000 chars | ~1500 tokens | Detailed review |
| 10000 chars | ~3000 tokens | Full content check |

### Example: Compact Preview ✨ v0.3.2

```json
{
  "report_selector": "Q1 Analysis",
  "format": "html",
  "include_preview": true,
  "preview_max_chars": 500
}
```

**Response**:
```json
{
  "status": "success",
  "report_id": "rpt_550e8400...",
  "output_path": "/Users/user/.igloo_mcp/reports/rpt_550e8400.../render/report.html",
  "format": "html",
  "preview": "# Q1 Network Analysis\n\n## Executive Summary\n\nThis report analyzes network performance metrics for Q1 2025...",
  "preview_truncated": true,
  "preview_length": 500,
  "full_content_available_at": "/Users/user/.igloo_mcp/reports/rpt_550e8400.../render/report.html"
}
```

**Token Savings**: 75% reduction (500 chars vs 2000 chars default)

---

### Example: Standard Preview

```json
{
  "report_selector": "Q1 Analysis",
  "format": "html",
  "include_preview": true
}
```

Uses default `preview_max_chars=2000`.

---

### Example: No Preview (Most Efficient)

```json
{
  "report_selector": "Q1 Analysis",
  "format": "pdf",
  "include_preview": false
}
```

**Response**:
```json
{
  "status": "success",
  "report_id": "rpt_550e8400...",
  "output_path": "/Users/user/.igloo_mcp/reports/rpt_550e8400.../render/report.pdf",
  "format": "pdf"
}
```

**Token Savings**: Maximum efficiency - no preview content in response.

---

## Dry Run Mode

Generate QMD (Quarto Markdown) file without rendering.

**Use when**: You want to inspect or manually edit the QMD before rendering.

**Example**:
```json
{
  "report_selector": "Q1 Analysis",
  "dry_run": true
}
```

**Response**:
```json
{
  "status": "success",
  "report_id": "rpt_550e8400...",
  "output_path": "/Users/user/.igloo_mcp/reports/rpt_550e8400.../render/report.qmd",
  "format": "qmd",
  "dry_run": true,
  "message": "QMD file generated. Run without dry_run to render."
}
```

---

## Common Workflows

### Workflow 1: Quick Validation with Preview

```python
# Render with compact preview for quick check
result = render_report(
    report_selector="Q1 Analysis",
    format="html",
    include_preview=true,
    preview_max_chars=500  # Token-efficient
)

# Check preview
if "error" not in result["preview"]:
    print("✓ Report rendered successfully")
    print(f"Preview: {result['preview'][:200]}...")
```

**Token Savings**: ~75% vs. default preview

---

### Workflow 2: Multi-Format Export

```python
# Generate multiple formats for different audiences
formats = ["html", "pdf", "markdown"]

for fmt in formats:
    result = render_report(
        report_selector="Q1 Analysis",
        format=fmt,
        include_preview=false  # No preview needed
    )
    print(f"{fmt.upper()}: {result['output_path']}")
```

---

### Workflow 3: Evolve → Verify → Render

```python
# Complete workflow
# 1. Evolve report
evolve_report(
    report_selector="Q1 Analysis",
    instruction="Add revenue insights",
    proposed_changes={...},
    response_detail="minimal"
)

# 2. Verify changes
updated = get_report(
    report_selector="Q1 Analysis",
    mode="summary"
)

# 3. Render with preview
rendered = render_report(
    report_selector="Q1 Analysis",
    format="html",
    include_preview=true,
    preview_max_chars=1000
)
```

---

### Workflow 4: Dry Run → Manual Edit → Render

```python
# Step 1: Generate QMD
dry_result = render_report(
    report_selector="Q1 Analysis",
    dry_run=true
)

# Step 2: Manually edit QMD file (outside MCP)
# Edit: /path/to/report.qmd

# Step 3: Render edited QMD
final_result = render_report(
    report_selector="Q1 Analysis",
    format="pdf",
    regenerate_outline_view=false  # Use existing QMD
)
```

---

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "success" or "error" |
| `report_id` | string | UUID of the rendered report |
| `output_path` | string | Absolute path to rendered file (or QMD for dry_run) |
| `format` | string | Output format used |
| `preview` | string | **Optional** - Truncated preview (if `include_preview=true`) |
| `preview_truncated` | boolean | **Optional** - Whether preview was truncated |
| `preview_length` | integer | **Optional** - Actual preview length in characters |
| `full_content_available_at` | string | **Optional** - Path to full rendered file |
| `dry_run` | boolean | **Optional** - True if dry-run mode |
| `request_id` | string | Request correlation ID |

---

## Error Handling

### Report Not Found

```json
{
  "status": "error",
  "error": "selector_error",
  "message": "Could not resolve report selector: 'Unknown Report'",
  "hints": [
    "Verify report_selector matches an existing report",
    "Use search_report to find available reports"
  ]
}
```

### Quarto Not Installed

```json
{
  "status": "error",
  "error": "execution_error",
  "message": "Quarto not found. Install from https://quarto.org",
  "hints": [
    "Install Quarto: https://quarto.org/docs/get-started/",
    "Verify Quarto is in PATH: quarto --version"
  ]
}
```

### PDF Rendering Requires Dependencies

```json
{
  "status": "error",
  "error": "execution_error",
  "message": "PDF rendering failed. TinyTeX or LaTeX required.",
  "hints": [
    "Install TinyTeX: quarto install tinytex",
    "Or install full LaTeX distribution"
  ]
}
```

### Invalid Preview Size

```json
{
  "status": "error",
  "error": "validation_error",
  "message": "preview_max_chars must be between 100 and 10000",
  "hints": [
    "Use preview_max_chars >= 100 for compact previews",
    "Use preview_max_chars <= 10000 for detailed previews"
  ]
}
```

---

## Best Practices

### 1. Use Appropriate Preview Sizes

```python
# ✅ Good: Match preview size to use case
render_report(..., preview_max_chars=500)   # Quick check
render_report(..., preview_max_chars=2000)  # Standard review
render_report(..., preview_max_chars=5000)  # Detailed analysis

# ❌ Avoid: Always using maximum or default
render_report(..., preview_max_chars=10000)  # Only when necessary
```

### 2. Skip Preview for Batch Operations

```python
# Batch rendering - no preview needed
for report in report_ids:
    render_report(
        report_selector=report,
        format="pdf",
        include_preview=false  # Token efficient
    )
```

### 3. Use HTML for Interactive Review

```python
# HTML is fastest and most feature-rich
render_report(
    report_selector="Q1 Analysis",
    format="html",
    include_preview=true,
    preview_max_chars=1000
)
```

### 4. Cache Rendered Outputs

Rendered files are saved to disk - reuse them instead of re-rendering:

```python
# First render
result = render_report(report_selector="Q1", format="html")
html_path = result["output_path"]

# Reuse file instead of re-rendering
# (unless report has been updated)
```

---

## Advanced Options

### Custom Quarto Options

Pass additional Quarto rendering options:

```json
{
  "report_selector": "Q1 Analysis",
  "format": "html",
  "options": {
    "toc": true,
    "toc-depth": 3,
    "number-sections": true,
    "theme": "cosmo"
  }
}
```

### Skip QMD Regeneration

Use existing QMD file (for manual edits):

```json
{
  "report_selector": "Q1 Analysis",
  "format": "pdf",
  "regenerate_outline_view": false
}
```

---

## Output Locations

Rendered files are saved in the report's render directory:

```
~/.igloo_mcp/reports/
└── rpt_550e8400e29b11d4a716446655440000/
    ├── outline.json
    ├── audit_log.jsonl
    └── render/
        ├── report.qmd      # Generated Quarto source
        ├── report.html     # HTML output
        ├── report.pdf      # PDF output
        └── report.md       # Markdown output
```

---

## Token Efficiency Comparison

| Configuration | Response Tokens | Use Case |
|--------------|----------------|----------|
| No preview | ~50 tokens | Batch operations |
| Preview (500 chars) | ~200 tokens | Quick validation |
| Preview (2000 chars, default) | ~650 tokens | Standard review |
| Preview (5000 chars) | ~1600 tokens | Detailed review |

**Recommendation**: Use `include_preview=false` for batch operations, compact previews (500-1000 chars) for interactive workflows.

---

## See Also

- [evolve_report](./evolve_report.md) - Modify reports before rendering
- [get_report](./get_report.md) - Inspect report structure
- [create_report](./create_report.md) - Initialize new reports
- [Living Reports User Guide](../../living-reports/user-guide.md) - Complete workflow documentation

---

**Version**: Enhanced in v0.3.2 with `preview_max_chars` parameter
**Category**: Living Reports
**Token Efficiency**: Configure preview size for 50-95% reduction
