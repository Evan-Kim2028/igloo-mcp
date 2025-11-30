# search_report

Search for living reports with intelligent fallback behavior.

**Features**:
- Exact report ID matching
- Fuzzy title search (case-insensitive)
- Tag-based filtering (AND logic)
- Status filtering (active/archived/deleted)
- **Selective fields**: Request only the fields you need

## Overview

The `search_report` tool enables agents to discover reports in the igloo-mcp instance. It supports:

- **Title search**: Exact or partial match (case-insensitive)
- **ID lookup**: Direct report ID resolution
- **Tag filtering**: Find reports with specific tags
- **Status filtering**: Filter by active/archived reports
- **Selective fields**: Request only the fields you need

## Parameters

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `report_id` | string | null | Exact report ID to search for |
| `title` | string | null | Search by title (exact or partial match, case-insensitive) |
| `tags` | array[string] | null | Filter by tags (reports must have ALL specified tags) |
| `status` | string | "active" | Filter by status: `active` or `archived` |
| `fields` | array[string] | null | Specific fields to return (defaults to all) |
| `limit` | integer | 20 | Maximum results to return (1-50) |

## Field Selection

The `fields` parameter allows you to request only specific fields, significantly reducing token usage.

### Valid Fields

| Field | Type | Description |
|-------|------|-------------|
| `report_id` | string | UUID of the report |
| `title` | string | Report title |
| `created_at` | string | Creation timestamp (ISO 8601) |
| `updated_at` | string | Last update timestamp (ISO 8601) |
| `tags` | array[string] | Report tags |
| `status` | string | Report status (active/archived) |
| `path` | string | Filesystem path to report |

### Default Behavior

- **Without `fields`**: Returns all fields (backward compatible)
- **With `fields`**: Returns only specified fields

### Token Savings

| Request Type | Tokens (All Fields) | Tokens (Minimal Fields) | Savings |
|-------------|---------------------|-------------------------|---------|
| Single report | ~150 tokens | ~50 tokens | 67% |
| 10 reports | ~1,200 tokens | ~400 tokens | 67% |
| 20 reports | ~2,400 tokens | ~800 tokens | 67% |

**Average Savings**: 30-50% when using selective fields

---

## Examples

### Example 1: Find Reports by Title (All Fields)

```json
{
  "title": "Q1 Analysis"
}
```

**Response**:
```json
{
  "status": "success",
  "reports": [
    {
      "report_id": "rpt_550e8400e29b11d4a716446655440000",
      "title": "Q1 Network Analysis",
      "created_at": "2025-01-15T10:30:00Z",
      "updated_at": "2025-01-20T14:45:00Z",
      "tags": ["q1", "network", "analysis"],
      "status": "active",
      "path": "/Users/user/.igloo_mcp/reports/rpt_550e8400e29b11d4a716446655440000/outline.json"
    },
    {
      "report_id": "rpt_660e9511f30c22e5b827557766551111",
      "title": "Q1 Sales Analysis",
      "created_at": "2025-01-10T09:15:00Z",
      "updated_at": "2025-01-18T11:30:00Z",
      "tags": ["q1", "sales"],
      "status": "active",
      "path": "/Users/user/.igloo_mcp/reports/rpt_660e9511f30c22e5b827557766551111/outline.json"
    }
  ],
  "total": 2,
  "limit": 20
}
```

---

### Example 2: Minimal Fields (Token Efficient)

```json
{
  "title": "Q1 Analysis",
  "fields": ["report_id", "title"]
}
```

**Response**:
```json
{
  "status": "success",
  "reports": [
    {
      "report_id": "rpt_550e8400e29b11d4a716446655440000",
      "title": "Q1 Network Analysis"
    },
    {
      "report_id": "rpt_660e9511f30c22e5b827557766551111",
      "title": "Q1 Sales Analysis"
    }
  ],
  "total": 2,
  "limit": 20
}
```

**Token Savings**: ~70% reduction (400 tokens → 120 tokens)

---

### Example 3: Search with Tags and Selective Fields

```json
{
  "tags": ["q1", "revenue"],
  "fields": ["report_id", "title", "tags", "updated_at"]
}
```

**Response**:
```json
{
  "status": "success",
  "reports": [
    {
      "report_id": "rpt_770fa622g41d33f6c938668877662222",
      "title": "Q1 Revenue Analysis",
      "tags": ["q1", "revenue", "finance"],
      "updated_at": "2025-01-25T16:20:00Z"
    }
  ],
  "total": 1,
  "limit": 20
}
```

---

### Example 4: Find by Exact Report ID

```json
{
  "report_id": "rpt_550e8400e29b11d4a716446655440000",
  "fields": ["report_id", "title", "status"]
}
```

**Response**:
```json
{
  "status": "success",
  "reports": [
    {
      "report_id": "rpt_550e8400e29b11d4a716446655440000",
      "title": "Q1 Network Analysis",
      "status": "active"
    }
  ],
  "total": 1,
  "limit": 20
}
```

---

### Example 5: List All Active Reports (IDs Only)

```json
{
  "status": "active",
  "fields": ["report_id"],
  "limit": 50
}
```

**Response**:
```json
{
  "status": "success",
  "reports": [
    {"report_id": "rpt_550e8400e29b11d4a716446655440000"},
    {"report_id": "rpt_660e9511f30c22e5b827557766551111"},
    {"report_id": "rpt_770fa622g41d33f6c938668877662222"}
  ],
  "total": 3,
  "limit": 50
}
```

**Token Savings**: ~85% reduction vs. full fields

---

## Search Behavior

### Title Matching

Title search is **case-insensitive** and supports **partial matches**:

- Search: `"Q1"` → Matches: "Q1 Analysis", "q1 sales", "2025 Q1 Report"
- Search: `"revenue"` → Matches: "Revenue Analysis", "Q1 Revenue", "revenue metrics"
- Search: `"Q1 Analysis"` → Exact match or partial substring

### Tag Filtering

Reports must have **ALL** specified tags (AND logic, not OR):

```json
{"tags": ["q1", "revenue"]}
```
- ✅ Matches: Report with tags `["q1", "revenue", "finance"]`
- ❌ No match: Report with tags `["q1", "sales"]` (missing "revenue")

### Status Filtering

- `"active"` (default): Returns only active reports
- `"archived"`: Returns only archived reports
- Omit or set to `null`: Returns reports of any status

---

## Common Workflows

### Workflow 1: Quick Report Discovery

```python
# Minimal fields for fastest discovery
results = search_report(
    title="Q1",
    fields=["report_id", "title"]
)

# Extract report_id for subsequent operations
report_id = results["reports"][0]["report_id"]

# Use in get_report
details = get_report(report_selector=report_id, mode="summary")
```

**Token Savings**: ~70% vs. searching with all fields

---

### Workflow 2: Tag-Based Report Management

```python
# Find all Q1 reports with metadata
q1_reports = search_report(
    tags=["q1"],
    fields=["report_id", "title", "updated_at", "status"]
)

# Process reports by recency
for report in sorted(q1_reports["reports"], key=lambda r: r["updated_at"], reverse=True):
    print(f"{report['title']} - Last updated: {report['updated_at']}")
```

---

### Workflow 3: Multi-Step Analysis Pipeline

```python
# Step 1: Find reports efficiently (minimal fields)
reports = search_report(
    tags=["quarterly", "analysis"],
    fields=["report_id", "title"],
    limit=10
)

# Step 2: For each report, get detailed structure
for report in reports["reports"]:
    summary = get_report(
        report_selector=report["report_id"],
        mode="summary"
    )
    # Analyze summary...
```

**Token Savings**: ~60% vs. full field retrieval + full report reads

---

## Response Fields

### Standard Response

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "success" or "error" |
| `reports` | array[object] | Matching reports (fields based on `fields` parameter) |
| `total` | integer | Total number of matching reports |
| `limit` | integer | Maximum results returned |
| `request_id` | string | Request correlation ID |

### Report Object Fields

Depends on `fields` parameter. If omitted, includes all fields:

- `report_id`: UUID string
- `title`: Report title
- `created_at`: ISO 8601 timestamp
- `updated_at`: ISO 8601 timestamp
- `tags`: Array of tag strings
- `status`: "active" or "archived"
- `path`: Absolute filesystem path

---

## Error Handling

### No Results Found

```json
{
  "status": "success",
  "reports": [],
  "total": 0,
  "limit": 20
}
```

Note: Empty results are **not an error** - returns successful response with empty array.

### Invalid Field Name

```json
{
  "status": "error",
  "error": "validation_error",
  "message": "Invalid field 'invalid_field' in fields parameter",
  "hints": [
    "Valid fields: report_id, title, created_at, updated_at, tags, status, path"
  ]
}
```

---

## Best Practices

### 1. Use Minimal Fields for Discovery

Always request only the fields you need:

```python
# ✅ Good: Minimal fields
search_report(title="Q1", fields=["report_id", "title"])

# ❌ Avoid: All fields when you only need ID
search_report(title="Q1")  # Returns 7 fields per report
```

### 2. Chain with get_report for Details

```python
# Efficient two-step workflow
# Step 1: Find report (minimal)
result = search_report(title="Q1 Sales", fields=["report_id"])
report_id = result["reports"][0]["report_id"]

# Step 2: Get details (selective mode)
details = get_report(report_selector=report_id, mode="summary")
```

### 3. Use Tags for Categorization

Organize reports with consistent tagging:

```python
# Tag reports consistently
create_report(title="Q1 Analysis", tags=["q1", "2025", "network"])

# Find easily later
q1_reports = search_report(tags=["q1", "2025"])
```

### 4. Filter by Status for Active Work

```python
# Focus on active reports only (default)
active = search_report(status="active", fields=["report_id", "title"])

# Review archived reports
archived = search_report(status="archived", fields=["report_id", "title", "updated_at"])
```

---

## Token Efficiency Comparison

| Search Pattern | Without `fields` | With `fields` | Savings |
|---------------|-----------------|---------------|---------|
| Find 1 report | 150 tokens | 50 tokens | 67% |
| Find 5 reports | 650 tokens | 220 tokens | 66% |
| Find 20 reports | 2,400 tokens | 800 tokens | 67% |
| List all IDs (50 reports) | 6,000 tokens | 500 tokens | 92% |

**Recommendation**: Always use `fields` parameter when you know what you need.

---

## See Also

- [get_report](./get_report.md) - Read report details after finding them
- [get_report_schema](./get_report_schema.md) - Discover valid report structures
- [create_report](./create_report.md) - Create new reports with tags
- [evolve_report](./evolve_report.md) - Modify reports
- [Living Reports User Guide](../../living-reports/user-guide.md) - Complete workflow documentation

---

**Version**: Complete API documentation available
