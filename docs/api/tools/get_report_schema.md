# get_report_schema - API Schema Introspection

**New in v0.3.2** ✨

Self-documenting schema introspection for Living Reports structures. Discover valid payload structures at runtime before constructing `evolve_report` calls.

## Overview

The `get_report_schema` tool enables agents to:

- **Discover valid structures**: Get JSON schemas for report models before creating payloads
- **Generate compliant payloads**: See copy-paste-ready examples for common operations
- **Understand data models**: Learn the Living Reports data structure at runtime
- **Avoid validation errors**: Reference correct field names, types, and requirements

This is the **single source of truth** for report structures - auto-generated from Pydantic models to ensure accuracy.

## Parameters

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `schema_type` | string | "proposed_changes" | Schema to return: `proposed_changes`, `insight`, `section`, `outline`, or `all` |
| `format` | string | "json_schema" | Output format: `json_schema`, `examples`, or `compact` |

## Schema Types

### `proposed_changes` (Most Common)

Complete schema for `evolve_report` payloads. Includes all operation types:
- `insights_to_add`, `insights_to_modify`, `insights_to_remove`
- `sections_to_add`, `sections_to_modify`, `sections_to_remove`
- `status_change`

**Use when**: You need to construct `evolve_report` payloads.

### `insight`

Schema for individual insight objects.

**Use when**: You need to understand insight structure for creating or modifying insights.

### `section`

Schema for individual section objects.

**Use when**: You need to understand section structure for creating or modifying sections.

### `outline`

Schema for complete report outline (read-only, returned by `get_report`).

**Use when**: You need to understand the overall report structure.

### `all`

All schemas at once.

**Use when**: You want comprehensive API documentation or are building tooling.

---

## Output Formats

### `json_schema` Format - Full JSON Schema Draft 7

Returns complete JSON Schema specification with types, descriptions, constraints.

**Use when**: You need programmatic schema validation or IDE autocomplete support.

**Example**:
```json
{
  "schema_type": "proposed_changes",
  "format": "json_schema"
}
```

**Response** (abbreviated):
```json
{
  "status": "success",
  "schema_type": "proposed_changes",
  "schema_version": "1.0.0",
  "json_schema": {
    "$defs": {...},
    "properties": {
      "insights_to_add": {
        "anyOf": [
          {
            "items": {
              "$ref": "#/$defs/InsightChange"
            },
            "type": "array"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "description": "Insights to add to the report",
        "title": "Insights To Add"
      },
      "sections_to_add": {...},
      ...
    },
    "title": "ProposedChanges",
    "type": "object"
  }
}
```

---

### `examples` Format - Copy-Paste Ready Payloads

Returns practical examples for common operations. **Most useful for agents**.

**Use when**: You want to see working examples to copy and adapt.

**Example**:
```json
{
  "schema_type": "proposed_changes",
  "format": "examples"
}
```

**Response**:
```json
{
  "status": "success",
  "schema_type": "proposed_changes",
  "schema_version": "1.0.0",
  "examples": {
    "add_insight": {
      "description": "Add a new insight to the report",
      "payload": {
        "insights_to_add": [
          {
            "insight_id": "ins_550e8400e29b11d4a716446655440000",
            "summary": "Revenue increased 25% YoY",
            "importance": 8,
            "supporting_queries": [
              {
                "execution_id": "exec_123...",
                "sql_sha256": "abc123...",
                "cache_manifest": "path/to/cache.json"
              }
            ]
          }
        ]
      }
    },
    "modify_section": {
      "description": "Modify an existing section",
      "payload": {
        "sections_to_modify": [
          {
            "section_id": "sec_a1b2c3d4...",
            "title": "Updated Section Title",
            "insight_ids_to_add": ["ins_new123..."],
            "insight_ids_to_remove": ["ins_old456..."]
          }
        ]
      }
    },
    "atomic_section_with_insights": {
      "description": "Add section with inline insights (atomic operation)",
      "payload": {
        "sections_to_add": [
          {
            "section_id": "sec_new123...",
            "title": "Revenue Analysis",
            "order": 1,
            "insights": [
              {
                "summary": "Q1 revenue grew 30%",
                "importance": 9,
                "supporting_queries": []
              }
            ]
          }
        ]
      }
    },
    "remove_items": {
      "description": "Remove insights and sections",
      "payload": {
        "insights_to_remove": ["ins_old123...", "ins_old456..."],
        "sections_to_remove": ["sec_old789..."]
      }
    },
    "change_status": {
      "description": "Change report status",
      "payload": {
        "status_change": {
          "new_status": "archived",
          "reason": "End of quarter archival"
        }
      }
    },
    "minimal_insight_add": {
      "description": "Add insight with minimal fields (supporting_queries optional)",
      "payload": {
        "insights_to_add": [
          {
            "summary": "Key finding text",
            "importance": 7
          }
        ]
      }
    },
    "partial_update": {
      "description": "Modify only specific fields (partial update)",
      "payload": {
        "insights_to_modify": [
          {
            "insight_id": "ins_existing...",
            "importance": 9
          }
        ]
      }
    }
  }
}
```

---

### `compact` Format - Quick Reference

Returns minimal schema overview with field names and types only. Most token-efficient.

**Use when**: You need a quick lookup or already know the structure.

**Example**:
```json
{
  "schema_type": "all",
  "format": "compact"
}
```

**Response**:
```json
{
  "status": "success",
  "schema_type": "all",
  "schema_version": "1.0.0",
  "compact_schemas": {
    "proposed_changes": {
      "insights_to_add": "array[InsightChange] | null",
      "insights_to_modify": "array[InsightChange] | null",
      "insights_to_remove": "array[string] | null",
      "sections_to_add": "array[SectionChange] | null",
      "sections_to_modify": "array[SectionChange] | null",
      "sections_to_remove": "array[string] | null",
      "status_change": "StatusChange | null"
    },
    "insight": {
      "insight_id": "string",
      "summary": "string",
      "importance": "int (1-10)",
      "status": "string",
      "supporting_queries": "array[QueryReference]",
      "citations": "array[QueryReference]"
    },
    "section": {
      "section_id": "string",
      "title": "string",
      "order": "int",
      "notes": "string | null",
      "content": "string | null",
      "content_format": "string (default: markdown)",
      "insight_ids": "array[string]"
    },
    "outline": {
      "report_id": "string",
      "title": "string",
      "created_at": "string (ISO 8601)",
      "updated_at": "string (ISO 8601)",
      "outline_version": "int",
      "metadata": "object",
      "sections": "array[Section]",
      "insights": "array[Insight]"
    }
  }
}
```

---

## Common Workflows

### Workflow 1: Build evolve_report Payload

```python
# Step 1: Get examples to understand structure
schema = get_report_schema(
    schema_type="proposed_changes",
    format="examples"
)

# Step 2: Copy relevant example
add_insight_example = schema["examples"]["add_insight"]

# Step 3: Adapt to your needs
proposed_changes = {
    "insights_to_add": [
        {
            "summary": "Revenue grew 40% in Q1 2025",
            "importance": 9,
            "supporting_queries": [
                {
                    "execution_id": "exec_abc123...",
                    "sql_sha256": "sha256_def456..."
                }
            ]
        }
    ]
}

# Step 4: Use in evolve_report
result = evolve_report(
    report_selector="Q1 Analysis",
    instruction="Add Q1 revenue insight",
    proposed_changes=proposed_changes
)
```

### Workflow 2: Validate Before Submission

```python
# Get schema for validation
schema = get_report_schema(
    schema_type="proposed_changes",
    format="json_schema"
)

# Use json_schema to validate your payload before submission
# (pseudo-code - actual validation depends on your library)
from jsonschema import validate

validate(instance=my_proposed_changes, schema=schema["json_schema"])

# If validation passes, submit
result = evolve_report(
    report_selector="My Report",
    proposed_changes=my_proposed_changes
)
```

### Workflow 3: Discover Data Model

```python
# Get all schemas for comprehensive understanding
all_schemas = get_report_schema(
    schema_type="all",
    format="compact"
)

# Quick reference for all models
print(all_schemas["compact_schemas"])
```

---

## Use Cases

### 1. First-Time Users

**Problem**: "I don't know what fields `evolve_report` expects."

**Solution**:
```python
examples = get_report_schema(
    schema_type="proposed_changes",
    format="examples"
)
# Browse examples to find the operation you need
```

### 2. Debugging Validation Errors

**Problem**: "My `evolve_report` call keeps failing with validation errors."

**Solution**:
```python
# Get schema to verify field names and types
schema = get_report_schema(
    schema_type="proposed_changes",
    format="json_schema"
)
# Compare your payload against schema
```

### 3. Building Tooling

**Problem**: "I'm building a UI/CLI for report management."

**Solution**:
```python
# Get full schemas for programmatic validation
schemas = get_report_schema(
    schema_type="all",
    format="json_schema"
)
# Use schemas for form generation, validation, etc.
```

### 4. Learning by Example

**Problem**: "I want to see how to do atomic section + insight creation."

**Solution**:
```python
examples = get_report_schema(
    schema_type="proposed_changes",
    format="examples"
)
# Check examples["atomic_section_with_insights"]
```

---

## Key Features

### ✅ Auto-Generated from Pydantic Models

Schemas are **always accurate** - generated directly from source code models. No manual documentation drift.

### ✅ Comprehensive Coverage

Includes all operation types:
- Adding insights/sections
- Modifying insights/sections (partial updates supported)
- Removing insights/sections
- Changing report status
- Atomic operations (section + insights together)

### ✅ Multiple Formats

Choose the format that suits your needs:
- `json_schema`: Programmatic validation
- `examples`: Learning and copy-paste
- `compact`: Quick lookup

### ✅ Versioned

Schema version tracked (`schema_version` field) for compatibility checking.

---

## Response Fields

All responses include:

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "success" or "error" |
| `schema_type` | string | Requested schema type |
| `schema_version` | string | Current schema version (e.g., "1.0.0") |
| `json_schema` / `examples` / `compact_schemas` | object | Schema data in requested format |
| `request_id` | string | Request correlation ID |
| `timing` | object | Performance metrics |

---

## Error Handling

### Invalid Schema Type

```json
{
  "status": "error",
  "error": "validation_error",
  "message": "Invalid schema_type 'invalid'. Must be one of: proposed_changes, insight, section, outline, all",
  "hints": [
    "Use 'proposed_changes' for evolve_report schema (most common)",
    "Use 'insight', 'section', or 'outline' for individual models",
    "Use 'all' to get all schemas at once"
  ]
}
```

### Invalid Format

```json
{
  "status": "error",
  "error": "validation_error",
  "message": "Invalid format 'invalid'. Must be one of: json_schema, examples, compact",
  "hints": [
    "Use 'json_schema' for full JSON Schema draft 7",
    "Use 'examples' for copy-paste-ready payload examples",
    "Use 'compact' for minimal quick reference"
  ]
}
```

---

## Best Practices

### 1. Start with Examples Format

New to Living Reports? Start with `format="examples"` to see working payloads.

### 2. Use Compact for Quick Lookup

Already familiar with the structure? Use `format="compact"` for fast reference.

### 3. Cache Schemas

Schemas don't change frequently - cache the response to avoid repeated calls.

### 4. Validate Before Evolving

Use `json_schema` format with a JSON Schema validator to catch errors before calling `evolve_report`.

### 5. Reference Examples in Errors

When debugging validation errors, compare your payload against the examples format.

---

## Token Efficiency

| Format | Typical Token Count | Use Case |
|--------|-------------------|----------|
| `compact` | ~100-200 tokens | Quick reference |
| `examples` | ~500-800 tokens | Learning, copy-paste |
| `json_schema` | ~1000-2000 tokens | Programmatic validation |

**Recommendation**: Use `examples` format for most agent workflows - good balance of detail and token efficiency.

---

## See Also

- [evolve_report](./evolve_report.md) - Use schemas to construct valid payloads
- [get_report](./get_report.md) - Get current report structure before evolving
- [Living Reports User Guide](../../living-reports/user-guide.md) - Complete workflow documentation
- [create_report](./create_report.md) - Initialize new reports

---

**Version**: Added in v0.3.2
**Category**: Living Reports
**Single Source of Truth**: Auto-generated from Pydantic models
