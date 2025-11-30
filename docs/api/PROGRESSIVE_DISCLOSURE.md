# Progressive Disclosure

Control response verbosity across all tools using the standardized `response_mode` parameter.

## Overview

All tools support `response_mode` for token efficiency:

| Value | Description | Token Range | Use Case |
|-------|-------------|-------------|----------|
| `minimal` | IDs, counts, status only | Smallest | Quick checks, validation |
| `standard` | Structure + key details (default) | Moderate | Most operations |
| `full` | Complete data and details | Largest | Analysis, reporting |

**Token Savings**: Significant reduction using `minimal` vs `full`

## Standard Values

### `minimal`

Returns only essential data:
- **execute_query**: Row count + schema (no data)
- **health_check**: Component status only
- **get_catalog_summary**: Object counts only
- **get_report**: Metadata (title, ID, counts)
- **evolve_report**: Operation counts only

### `standard` (default)

Balanced response for typical workflows:
- **execute_query**: Sample rows + metrics
- **health_check**: Status + remediation guidance
- **get_catalog_summary**: Counts + database breakdown
- **get_report**: Full outline with IDs
- **evolve_report**: Counts + IDs of changed items

### `full`

Complete data:
- **execute_query**: All query results
- **health_check**: Status + remediation + diagnostics
- **get_catalog_summary**: All statistics + distributions
- **get_report**: All content + audit trail
- **evolve_report**: Complete change details

## Tool-Specific Modes

### execute_query

| Mode | Description | Savings |
|------|-------------|---------|
| `schema_only` | Column schema only, no rows | Maximum |
| `summary` | 5 sample rows + metrics | High |
| `sample` | 10 sample rows | Moderate |
| `full` | All query results | baseline |

### get_report

Legacy mode values mapped to standard:
- `summary` → `minimal`
- `sections` / `insights` → `standard`
- `full` → `full`

## Usage Examples

### Quick Checks (Default Behavior - v0.3.5+)

```python
# Check system health (defaults to minimal)
health_check()

# Verify catalog exists (defaults to minimal)
get_catalog_summary()

# Check report exists (defaults to minimal)
get_report("Q1 Revenue")

# Execute query (defaults to summary - 5 sample rows)
execute_query(
    "SELECT * FROM customers",
    reason="Quick validation"
)
```

### Explicit Mode Control

```python
# Get full report structure
get_report("Q1 Revenue", response_mode="standard")

# Get all query results (no sampling)
execute_query(
    "SELECT * FROM table",
    reason="Full export",
    response_mode="full"
)
```

### Complete Data

```python
# Get all results (explicit)
execute_query(
    "SELECT * FROM table",
    reason="Export",
    response_mode="full"
)

# Get full report content with audit trail
get_report("Q1 Revenue", response_mode="full")
```

## Backward Compatibility

Legacy parameter names are supported with deprecation warnings:

| Tool | Legacy Parameter | Status |
|------|-----------------|---------|
| `execute_query` | `result_mode` | Deprecated |
| `health_check` | `detail_level` | Deprecated |
| `get_catalog_summary` | `mode` | Deprecated |
| `evolve_report` | `response_detail` | Deprecated |
| `evolve_report_batch` | `response_detail` | Deprecated |
| `get_report` | `mode` | Deprecated |

**Migration**: Replace legacy parameters with `response_mode`:

```python
# Old (deprecated, shows warning)
health_check(detail_level="minimal")

# New (recommended)
health_check(response_mode="minimal")
```

## Best Practices

1. **Start minimal, drill down**: Check existence first, then fetch details if needed
2. **Use standard for most operations**: The default is optimized for typical workflows
3. **Reserve full for exports**: Only request complete data when necessary
4. **Combine with filters**: Use `min_importance`, `section_ids`, etc. with `response_mode`

## See Also

- [Tool Index](./TOOLS_INDEX.md) - Complete tool reference
- [execute_query](./tools/execute_query.md) - Query execution with result modes
- [get_report](./tools/get_report.md) - Report retrieval with progressive disclosure
- [Error Handling](./ERROR_HANDLING.md) - Error handling patterns
