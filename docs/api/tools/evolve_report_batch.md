# evolve_report_batch

Perform multiple report evolution operations atomically in a single transaction.

## Description

The `evolve_report_batch` tool enables atomic multi-operation report evolution, reducing round-trips and ensuring transactional consistency. All operations are validated before any are applied, providing all-or-nothing semantics.

**Benefits**:
- **Reduce API Round-trips**: Perform multiple operations in one call instead of multiple sequential calls
- **Ensure Consistency**: All operations succeed or fail together (transactional semantics)
- **Improve Ergonomics**: Natural batching for multi-insight/multi-section reports
- **Performance**: Single validation pass, single storage operation

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `report_selector` | string | ✅ Yes | - | Report ID or title to evolve |
| `instruction` | string | ✅ Yes | - | Natural language description for audit trail (min 5 chars) |
| `operations` | array | ✅ Yes | - | List of operations to perform atomically |
| `constraints` | object | ❌ No | null | Optional constraints (e.g., `skip_citation_validation: true`) |
| `dry_run` | boolean | ❌ No | false | Validate without applying changes |
| `response_detail` | string | ❌ No | "standard" | Response verbosity: `minimal`, `standard`, or `full` |

### Operation Types

Each operation is an object with a `type` field and type-specific parameters:

#### Insight Operations

**`add_insight`**: Add new insight
- `insight_id` (optional): UUID for the insight (auto-generated if omitted)
- `summary` (required): Brief insight summary
- `importance` (required): 1-10 importance score
- `citations` (optional): Array of citation objects with `execution_id`, `sql_sha256`, or `cache_manifest`
- `supporting_queries` (optional): Alias for citations (backward compatibility)

**`modify_insight`**: Modify existing insight
- `insight_id` (required): UUID of insight to modify
- `summary` (optional): Updated summary
- `importance` (optional): Updated importance score
- Other fields: Only provided fields are updated (partial update)

**`remove_insight`**: Remove insight
- `insight_id` (required): UUID of insight to remove

#### Section Operations

**`add_section`**: Add new section
- `section_id` (optional): UUID for the section (auto-generated if omitted)
- `title` (required): Section title
- `order` (optional): Section order/position
- `content` (optional): Section prose content (markdown)
- `notes` (optional): Section notes
- `insight_ids` (optional): Array of insight UUIDs to link

**`modify_section`**: Modify existing section
- `section_id` (required): UUID of section to modify
- `title` (optional): Updated title
- `content` (optional): Updated content
- `insight_ids_to_add` (optional): Array of insight UUIDs to add
- `insight_ids_to_remove` (optional): Array of insight UUIDs to remove
- Other fields: Only provided fields are updated (partial update)

**`remove_section`**: Remove section
- `section_id` (required): UUID of section to remove

#### Metadata Operations

**`update_title`**: Update report title
- `title` (required): New report title

**`update_metadata`**: Update report metadata
- `metadata` (required): Object with metadata key-value pairs to merge

## Returns

### Success Response (`status="success"`)

```json
{
  "status": "success",
  "report_id": "rpt_550e8400e29b11d4a716446655440000",
  "outline_version": 3,
  "summary": {
    "sections_added": 1,
    "insights_added": 2,
    "sections_modified": 0,
    "insights_modified": 0,
    "sections_removed": 0,
    "insights_removed": 0,
    "insight_ids_added": ["uuid-1", "uuid-2"],
    "section_ids_added": ["uuid-3"],
    "insight_ids_modified": [],
    "section_ids_modified": [],
    "insight_ids_removed": [],
    "section_ids_removed": []
  },
  "batch_info": {
    "operation_count": 3,
    "operations_summary": {
      "add_insight": 2,
      "add_section": 1
    },
    "total_duration_ms": 45.2
  },
  "warnings": []
}
```

### Validation Failed Response (`status="validation_failed"`)

```json
{
  "status": "validation_failed",
  "report_id": "rpt_...",
  "validation_errors": [
    "Insight insight-uuid not found. Available: uuid-1, uuid-2",
    "Section title 'Revenue' already exists"
  ],
  "operation_count": 5,
  "request_id": "req_..."
}
```

### Dry Run Response (`status="dry_run_success"`)

```json
{
  "status": "dry_run_success",
  "report_id": "rpt_...",
  "validation_passed": true,
  "operation_count": 3,
  "operations_summary": {
    "add_insight": 2,
    "add_section": 1
  },
  "request_id": "req_..."
}
```

## Examples

### Add Multiple Insights and Section

```python
result = evolve_report_batch(
    report_selector="Q1 Sales Analysis",
    instruction="Add comprehensive revenue analysis",
    operations=[
        {
            "type": "add_insight",
            "summary": "Enterprise revenue grew 45% YoY",
            "importance": 9,
            "citations": [{"execution_id": "exec-123"}]
        },
        {
            "type": "add_insight",
            "summary": "SMB segment showed 12% improvement",
            "importance": 7,
            "citations": [{"execution_id": "exec-124"}]
        },
        {
            "type": "add_section",
            "title": "Revenue Analysis",
            "order": 1,
            "content": "Comprehensive revenue breakdown by segment.",
            "insight_ids": ["<uuid-from-first-insight>", "<uuid-from-second-insight>"]
        }
    ]
)

print(f"Added {result['summary']['insights_added']} insights")
print(f"Added {result['summary']['sections_added']} sections")
```

### Update Existing Report Atomically

```python
result = evolve_report_batch(
    report_selector="rpt_550e8400e29b11d4a716446655440000",
    instruction="Reprioritize insights and update section",
    operations=[
        {
            "type": "modify_insight",
            "insight_id": "existing-insight-1",
            "importance": 10  # Increase priority
        },
        {
            "type": "modify_insight",
            "insight_id": "existing-insight-2",
            "importance": 5  # Decrease priority
        },
        {
            "type": "modify_section",
            "section_id": "existing-section-1",
            "content": "Updated analysis based on Q2 data."
        }
    ]
)
```

### Dry Run Validation

```python
result = evolve_report_batch(
    report_selector="Q1 Sales Analysis",
    instruction="Preview batch changes",
    operations=[
        {
            "type": "add_insight",
            "summary": "Test insight",
            "importance": 5
        },
        {
            "type": "add_section",
            "title": "Test Section",
            "order": 1
        }
    ],
    dry_run=True
)

if result["validation_passed"]:
    print("Operations are valid - ready to apply")
else:
    print(f"Validation errors: {result['validation_errors']}")
```

### With Constraints (Skip Citation Validation)

```python
result = evolve_report_batch(
    report_selector="Q1 Sales Analysis",
    instruction="Add draft insights without citations",
    operations=[
        {
            "type": "add_insight",
            "summary": "Draft insight pending data validation",
            "importance": 5
            # No citations - would normally fail validation
        }
    ],
    constraints={"skip_citation_validation": True}
)
```

### Minimal Response Mode

```python
result = evolve_report_batch(
    report_selector="Q1 Sales Analysis",
    instruction="Add multiple insights",
    operations=[...],
    response_detail="minimal"  # ~200 tokens vs ~400 for standard
)

# Returns: status, report_id, summary counts only
print(f"Status: {result['status']}")
print(f"Insights added: {result['summary']['insights_added']}")
```

## Comparison with evolve_report

### Use `evolve_report_batch` when:
- Adding multiple insights and sections together
- Ensuring atomic consistency across operations
- Reducing API round-trips for batch operations
- Building reports programmatically with many operations

### Use `evolve_report` when:
- Making single-operation changes
- Using LLM-generated `proposed_changes` format (more flexible schema)
- Need fine-grained control over change structure
- Working with inline insights in sections

**Key Difference**: `evolve_report_batch` uses an operation-based API (list of operations), while `evolve_report` uses a change-based API (`ProposedChanges` object with separate arrays for adds/modifies/removes).

## Response Detail Modes

Control response verbosity for token efficiency:

| Mode | Token Count | Includes |
|------|-------------|----------|
| `minimal` | ~200 tokens | Status, report_id, version, counts |
| `standard` | ~400 tokens | + IDs of created/modified items, warnings |
| `full` | ~1000+ tokens | + Complete changes_applied echo, timing details |

## Errors

### Validation Errors

**Invalid operation type**:
```
Operation 2: invalid type 'add_insights'. Must be one of: add_insight, modify_insight, remove_insight, add_section, modify_section, remove_section, update_title, update_metadata
```

**Missing required field**:
```
Operation 0: missing 'type' field
```

### Selector Errors

**Report not found**:
```json
{
  "status": "error",
  "error": "selector_error",
  "message": "Could not resolve report selector: Unknown Report",
  "selector": "Unknown Report",
  "candidates": ["Q1 Sales Analysis", "Q2 Revenue Report"]
}
```

### Semantic Validation Errors

**Insight not found**:
```
Insight insight-uuid not found. Available: uuid-1, uuid-2, uuid-3
```

**Duplicate section title**:
```
Section with title 'Revenue Analysis' already exists
```

See [Living Reports Errors](living_reports_errors.md) for comprehensive error handling.

## Best Practices

### 1. Auto-generated IDs
Let the tool generate UUIDs automatically:
```python
operations=[
    {
        "type": "add_insight",
        # insight_id omitted - auto-generated
        "summary": "Revenue grew 45%",
        "importance": 9
    }
]
```

### 2. Use Dry Run First
Validate complex operations before applying:
```python
# Step 1: Validate
result = evolve_report_batch(..., dry_run=True)
if not result["validation_passed"]:
    print(f"Errors: {result['validation_errors']}")
    return

# Step 2: Apply
result = evolve_report_batch(..., dry_run=False)
```

### 3. Batch Related Changes
Group logically related operations:
```python
# Good: Add insights + link to section atomically
operations=[
    {"type": "add_insight", ...},
    {"type": "add_insight", ...},
    {"type": "add_section", "insight_ids": [...]}
]

# Avoid: Separate calls for each operation
```

### 4. Use Minimal Response for Large Batches
Reduce token usage for operations with many items:
```python
result = evolve_report_batch(
    operations=[...100 operations...],
    response_detail="minimal"  # 80% token reduction
)
```

## Performance

- **Validation**: All operations validated in single pass (~10-20ms)
- **Application**: Single atomic write to storage (~20-50ms)
- **Total**: Typical batch of 10 operations: ~30-70ms

Compare to sequential `evolve_report` calls:
- **10 operations**: 10 × (30-70ms) = 300-700ms (10x slower)

## See Also

- [evolve_report](evolve_report.md) - Single-operation evolution with `proposed_changes` format
- [get_report](get_report.md) - Read reports progressively to discover section/insight IDs
- [create_report](create_report.md) - Initialize new reports
- [render_report](render_report.md) - Export reports to HTML/PDF/Markdown
- [Living Reports User Guide](../../living-reports/user-guide.md) - Complete workflow documentation
