# get_report

Read living reports with progressive disclosure for token-efficient inspection.

## Overview

The `get_report` tool enables agents to read report structure and content efficiently without loading entire reports. This is critical for:

- **Multi-turn workflows**: Get section_ids/insight_ids before calling `evolve_report`
- **Token efficiency**: Load only what you need (60-80% reduction vs. full reports)
- **Progressive disclosure**: Start with summary, drill down as needed
- **Content inspection**: Understand report structure before modifications

## Parameters

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `report_selector` | string | Report ID (e.g., `rpt_550e8400...`) or title (e.g., "Q1 Analysis") |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | string | "summary" | Retrieval mode: `summary`, `sections`, `insights`, or `full` |
| `section_ids` | array[string] | null | Filter to specific section IDs |
| `section_titles` | array[string] | null | Filter sections by title (case-insensitive substring match) |
| `insight_ids` | array[string] | null | Filter to specific insight IDs |
| `min_importance` | integer | null | Filter insights with importance >= this value (1-10) |
| `limit` | integer | 50 | Maximum items to return (1-100) |
| `offset` | integer | 0 | Skip first N items (pagination) |
| `include_content` | boolean | false | Include section prose content |
| `include_audit` | boolean | false | Include recent audit events |

## Retrieval Modes

### `summary` Mode - Lightweight Overview

Returns high-level report metadata and section overview. **Most token-efficient** (~100-200 tokens).

**Use when**: You need basic report info or section structure without details.

**Example**:
```json
{
  "report_selector": "Q1 Network Analysis",
  "mode": "summary"
}
```

**Response**:
```json
{
  "status": "success",
  "report_id": "rpt_550e8400...",
  "title": "Q1 Network Analysis",
  "template": "default",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-20T14:45:00Z",
  "outline_version": 5,
  "summary": {
    "total_sections": 3,
    "total_insights": 12,
    "tags": ["q1", "network", "analysis"],
    "status": "active"
  },
  "sections_overview": [
    {
      "section_id": "sec_a1b2...",
      "title": "Network Activity",
      "insight_count": 5,
      "order": 1
    },
    {
      "section_id": "sec_c3d4...",
      "title": "Performance Metrics",
      "insight_count": 4,
      "order": 2
    },
    {
      "section_id": "sec_e5f6...",
      "title": "Recommendations",
      "insight_count": 3,
      "order": 3
    }
  ]
}
```

**Token Savings**: ~75% reduction vs. full report

---

### `sections` Mode - Section Details

Returns detailed section information with optional prose content. Supports filtering by section IDs or titles.

**Use when**: You need section structure and insight IDs for a specific part of the report.

**Example 1: Get specific sections by ID**:
```json
{
  "report_selector": "Q1 Network Analysis",
  "mode": "sections",
  "section_ids": ["sec_a1b2..."],
  "include_content": true
}
```

**Example 2: Filter by title**:
```json
{
  "report_selector": "Q1 Network Analysis",
  "mode": "sections",
  "section_titles": ["Network Activity", "Performance"],
  "include_content": false
}
```

**Response**:
```json
{
  "status": "success",
  "report_id": "rpt_550e8400...",
  "sections": [
    {
      "section_id": "sec_a1b2...",
      "title": "Network Activity",
      "order": 1,
      "insight_ids": ["ins_123...", "ins_456...", "ins_789..."],
      "insight_count": 3,
      "notes": "Analysis of network throughput and latency",
      "content": "# Network Activity Overview\n\nThis section analyzes...",
      "content_format": "markdown"
    }
  ],
  "total_matched": 1,
  "returned": 1,
  "limit": 50,
  "offset": 0
}
```

**Token Savings**: ~50-70% reduction vs. full report (depending on filtering)

---

### `insights` Mode - Insight Details

Returns detailed insight information. Supports filtering by importance, section, or specific IDs.

**Use when**: You need to analyze insights, especially high-importance findings.

**Example 1: Get high-importance insights**:
```json
{
  "report_selector": "Q1 Network Analysis",
  "mode": "insights",
  "min_importance": 8
}
```

**Example 2: Get insights from specific section**:
```json
{
  "report_selector": "Q1 Network Analysis",
  "mode": "insights",
  "section_ids": ["sec_a1b2..."],
  "min_importance": 5
}
```

**Response**:
```json
{
  "status": "success",
  "report_id": "rpt_550e8400...",
  "insights": [
    {
      "insight_id": "ins_123...",
      "summary": "Network throughput increased 45% QoQ",
      "importance": 9,
      "status": "active",
      "section_id": "sec_a1b2...",
      "has_citations": true,
      "citation_count": 2
    },
    {
      "insight_id": "ins_456...",
      "summary": "Peak latency reduced by 30ms",
      "importance": 8,
      "status": "active",
      "section_id": "sec_a1b2...",
      "has_citations": true,
      "citation_count": 1
    }
  ],
  "total_matched": 2,
  "returned": 2,
  "limit": 50,
  "offset": 0,
  "filtered_by": {
    "min_importance": 8
  }
}
```

**Token Savings**: ~60-75% reduction vs. full report (depending on filtering)

---

### `full` Mode - Complete Report

Returns complete report structure with all sections and insights. Most comprehensive but also most token-intensive.

**Use when**: You need the entire report structure or are generating a comprehensive analysis.

**Example**:
```json
{
  "report_selector": "Q1 Network Analysis",
  "mode": "full",
  "include_content": true,
  "limit": 100
}
```

**Response**: Complete report outline with all sections, insights, and metadata (structure similar to combining sections + insights modes).

**Token Cost**: ~1000-3000 tokens (full report)

---

## Pagination

All modes support pagination via `limit` and `offset` parameters:

```json
{
  "report_selector": "Large Report",
  "mode": "insights",
  "limit": 20,
  "offset": 0  // First page
}
```

```json
{
  "report_selector": "Large Report",
  "mode": "insights",
  "limit": 20,
  "offset": 20  // Second page
}
```

---

## Mode Selection Guide

Choose the right mode based on your needs to optimize token usage:

### Quick Comparison

| Mode | Rows Returned | Token Cost | Use Case |
|------|---------------|------------|----------|
| `summary` | Metadata only | ~50 tokens | List reports, check status |
| `insights` | Key findings | ~200 tokens | Review conclusions without reading |
| `sections` | Structure + content | ~500+ tokens | Read report prose |
| `full` | Everything | ~1000+ tokens | Complete audit trail, exports |

### When to Use Each Mode

**`summary` mode** - Minimal metadata
```python
# Use when: Browsing reports, checking existence
get_report(report_selector="Q1 Revenue", mode="summary")

# Returns:
# - report_id, title, created_at, updated_at
# - tags, status, path
# - Section count, insight count
# - NO prose content, NO insights, NO citations
```

**`insights` mode** - Key findings only
```python
# Use when: Quick review of conclusions
get_report(report_selector="Q1 Revenue", mode="insights")

# Returns:
# - All insights with summaries and importance
# - Supporting query IDs
# - Citations
# - NO section prose content
```

**`sections` mode** - Structure and prose
```python
# Use when: Reading the report narrative
get_report(report_selector="Q1 Revenue", mode="sections")

# Returns:
# - All section titles, order, prose content
# - Section-to-insight mappings
# - NO detailed insight metadata
# - NO full citation details
```

**`full` mode** - Complete data
```python
# Use when: Exporting, auditing, or modifying
get_report(report_selector="Q1 Revenue", mode="full")

# Returns:
# - EVERYTHING: metadata, sections, insights, citations
# - Audit trail information
# - Ready for render_report or evolve_report
```

### Recommended Workflow

```
1. Start with summary → See available reports
   ↓
2. Use insights → Review key findings
   ↓
3. Drill into sections → Read specific content
   ↓
4. Use full → Export or modify
```

### Token Efficiency Tips

**Bad** (wastes tokens):
```python
# Getting full mode just to check if report exists
result = get_report("Q1 Revenue", mode="full")  # 1000+ tokens
if result["status"] == "success":
    print("Report exists")
```

**Good** (token efficient):
```python
# Use summary mode for existence checks
result = get_report("Q1 Revenue", mode="summary")  # 50 tokens
if result["status"] == "success":
    print("Report exists")
```

### Progressive Disclosure Pattern

**Efficient multi-step workflow**:
```python
# Step 1: List all reports (summary mode)
reports = search_report(tags=["quarterly"], fields=["report_id", "title"])

# Step 2: Get insights for relevant report (insights mode)
insights = get_report("Q1 Revenue", mode="insights")
print(f"Found {len(insights['insights'])} key findings")

# Step 3: Read specific sections if needed (sections mode)
content = get_report(
    "Q1 Revenue",
    mode="sections",
    section_titles=["Executive Summary"]  # Filter to specific section
)

# Step 4: Full mode only when modifying or exporting
full_report = get_report("Q1 Revenue", mode="full")
render_report(full_report["report_id"], format="pdf")
```

**Token savings**: 50 + 200 + 300 + 1000 = **1,550 tokens** (progressive)
vs. 4 × 1000 = **4,000 tokens** (always using full mode)
**Savings: 61%** ✨

---

## Common Workflows

### Workflow 1: Progressive Disclosure

Start lightweight, drill down as needed:

```python
# Step 1: Get overview (100 tokens)
summary = get_report(
    report_selector="Q1 Analysis",
    mode="summary"
)

# Step 2: Get specific section details (200 tokens)
section = get_report(
    report_selector="Q1 Analysis",
    mode="sections",
    section_titles=["Revenue Analysis"]
)

# Step 3: Get high-priority insights (300 tokens)
insights = get_report(
    report_selector="Q1 Analysis",
    mode="insights",
    section_ids=["sec_revenue..."],
    min_importance=7
)

# Total: ~600 tokens vs. 2000+ for full report (70% savings)
```

### Workflow 2: Prepare for Evolution

Get IDs before modifying:

```python
# Step 1: Get section structure
sections = get_report(
    report_selector="Q1 Analysis",
    mode="sections"
)
# Extract: section_id = "sec_a1b2..."

# Step 2: Evolve with correct IDs
evolve_report(
    report_selector="Q1 Analysis",
    instruction="Add insight to revenue section",
    proposed_changes={
        "sections_to_modify": [{
            "section_id": "sec_a1b2...",  # From get_report
            "insight_ids_to_add": ["new_insight_id"]
        }]
    }
)
```

### Workflow 3: Content Inspection

Review prose content before rendering:

```python
# Get sections with prose content
sections = get_report(
    report_selector="Executive Summary",
    mode="sections",
    include_content=True
)

# Inspect content
for section in sections["sections"]:
    print(f"Section: {section['title']}")
    print(f"Content: {section.get('content', 'No content')}")
```

---

## Token Efficiency Comparison

| Operation | Tokens (Previously) | Tokens (With get_report) | Savings |

---

## Error Handling

### Report Not Found

```json
{
  "status": "error",
  "error": "selector_error",
  "message": "Could not resolve report selector: 'Unknown Report'",
  "selector": "Unknown Report",
  "hints": [
    "Verify report_selector matches an existing report",
    "Check report ID or title spelling (case-insensitive)",
    "Use search_report to find available reports"
  ]
}
```

### Invalid Mode

```json
{
  "status": "error",
  "error": "validation_error",
  "message": "Invalid mode 'invalid'. Must be one of: summary, sections, insights, full",
  "hints": [
    "Use mode='summary' for lightweight overview",
    "Use mode='sections' for section details",
    "Use mode='insights' for insight details",
    "Use mode='full' for complete report"
  ]
}
```

---

## Best Practices

### 1. Start with Summary Mode
Always begin with `mode="summary"` to understand report structure before requesting details.

### 2. Use Filters to Reduce Tokens
- Filter by `section_ids` or `section_titles` when you know what you need
- Use `min_importance` to focus on key insights
- Set `limit` to reasonable values (10-50 items)

### 3. Progressive Disclosure Pattern
```
summary → sections (filtered) → insights (filtered) → full (only if needed)
```

### 4. Cache Section/Insight IDs
Extract and reuse IDs from initial queries instead of re-fetching full structure.

### 5. Avoid Full Mode Unless Necessary
Reserve `mode="full"` for final reviews or comprehensive analysis. Use filtered modes for most operations.

---

## See Also

- [get_report_schema](./get_report_schema.md) - Discover valid report structures at runtime
- [evolve_report](./evolve_report.md) - Modify reports with structured changes
- [search_report](./search_report.md) - Find reports by title or tags
- [render_report](./render_report.md) - Generate HTML/PDF outputs
- [Living Reports User Guide](../../living-reports/user-guide.md) - Complete workflow documentation

---

**Version**: Complete API documentation available
