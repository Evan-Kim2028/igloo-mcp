# create_report - Create New Living Reports

The `create_report` tool allows agents to create new living reports through the MCP interface, providing a seamless MCP-only workflow for report creation and evolution.

## Overview

Living reports are structured, auditable business reports that evolve safely over time. The `create_report` tool creates the initial report structure with optional templates and tags, ready for evolution via `evolve_report` and rendering via `render_report`.

## Parameters

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `title` | string | Human-readable title for the report |

### Optional Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `template` | string | Report template to use. Defaults to `default` if not specified. Available templates: `default` (empty report), `monthly_sales`, `quarterly_review`, `deep_dive`, `analyst_v1` (blockchain analysis with citation enforcement). | `default` |
| `tags` | array of strings | Optional tags for categorization and filtering | `[]` |
| `description` | string | Optional description of the report (stored in metadata) | `null` |

## Templates

Available templates provide pre-configured section structures:

- **`default`**: Empty report with no predefined sections (default if not specified)
- **`monthly_sales`**: Sections for sales metrics, trends, and analysis
- **`quarterly_review`**: Executive summary, financials, operations, and outlook
- **`deep_dive`**: Detailed analysis structure with multiple investigation sections
- **`analyst_v1`**: Standardized blockchain analysis reports with citation enforcement

## Usage Examples

### Basic Report Creation

```python
# Create a simple report with default template
result = await create_report(
    title="Q1 Revenue Analysis"
)
# Returns: {"status": "success", "report_id": "rpt_...", "title": "Q1 Revenue Analysis", ...}
```

### Report with Template and Tags

```python
# Create report with template and tags
result = await create_report(
    title="Monthly Sales Report",
    template="monthly_sales",
    tags=["sales", "monthly", "revenue"]
)
```

### Report with Description

```python
# Create report with full metadata
result = await create_report(
    title="Customer Churn Analysis",
    template="deep_dive",
    tags=["analytics", "churn"],
    description="Comprehensive analysis of customer retention patterns"
)
```

## Response Format

### Success Response

```json
{
  "status": "success",
  "report_id": "rpt_550e8400e29b11d4a716446655440000",
  "title": "Q1 Revenue Analysis",
  "template": "default",
  "tags": ["q1", "revenue"],
  "section_ids_added": [],
  "insight_ids_added": [],
  "timing": {
    "outline_duration_ms": 2.34,
    "create_duration_ms": 5.67
  },
  "message": "Created report 'Q1 Revenue Analysis' with ID: rpt_550e8400e29b11d4a716446655440000"
}
```

### Response Fields

- **`section_ids_added`**: Array of section IDs created from template (empty for default template)
- **`insight_ids_added`**: Array of insight IDs created from template (empty for default template)
- **`timing`**: Performance metrics
  - `outline_duration_ms`: Time to fetch/create outline
  - `create_duration_ms`: Total creation time

### Error Responses

**Invalid Template**:
```json
{
  "status": "validation_failed",
  "error_type": "invalid_template",
  "message": "Invalid template: nonexistent_template",
  "title": "My Report"
}
```

**Unexpected Error**:
```json
{
  "status": "error",
  "error_type": "unexpected",
  "message": "Error details here",
  "title": "My Report"
}
```

## Integration with Other Tools

After creating a report, you can:

1. **Evolve the report** using `evolve_report` to add insights and sections
2. **Render the report** using `render_report` to generate HTML/PDF/Markdown output

Example workflow:

```python
# 1. Create report
create_result = await create_report(
    title="Q1 Business Performance",
    template="quarterly_review",
    tags=["q1", "business"]
)
report_id = create_result["report_id"]

# 2. Evolve report (add insights)
await evolve_report(
    report_selector=report_id,
    instruction="Add revenue insights",
    proposed_changes={
        "insights_to_add": [{
            "insight_id": "uuid-123",
            "summary": "Revenue grew 25% YoY",
            "importance": 9,
            "supporting_queries": []
        }]
    }
)

# 3. Render report
await render_report(
    report_selector=report_id,
    format="html"
)
```

## Storage Location

Reports are stored in your igloo-mcp instance directory:
- Default: `~/.igloo-mcp/reports/`
- Configurable via: `IGLOO_MCP_REPORTS_ROOT` environment variable
- Follows: `IGLOO_MCP_LOG_SCOPE` setting (global or repo)

## Automatic Index Synchronization

Reports created via `create_report` are immediately available to other MCP tools. The `evolve_report` tool automatically refreshes the index before operations, ensuring seamless synchronization between CLI and MCP workflows.

## Best Practices

- **Use descriptive titles** for easy identification and selection
- **Apply appropriate templates** to get started with structured sections
- **Tag reports consistently** for organization and filtering
- **Add descriptions** for context and documentation
- **Start with templates** then evolve with specific insights

## Related Tools

- [`evolve_report`](evolve_report.md) - Modify and evolve existing reports
- [`render_report`](render_report.md) - Generate human-readable output formats
