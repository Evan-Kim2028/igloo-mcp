# Tool: get_catalog_summary

## Purpose

Retrieves summary information about a built catalog, including statistics and metadata about the cataloged objects.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `catalog_dir` | string | ❌ No | ./data_catalogue | Directory containing catalog artifacts. Default resolves to unified storage at `~/.igloo_mcp/catalogs/{database}/` when used with `build_catalog` default. |
| `response_mode` | string | ❌ No | `standard` | Response verbosity: `minimal`, `standard`, or `full`. |
| `mode` | string | ❌ No | — | **DEPRECATED** alias for `response_mode`. |
| `request_id` | string | ❌ No | auto-generated | Request correlation ID for distributed tracing (UUID4). Auto-generated if not provided. |

> **Unified Storage**: When `catalog_dir` is the default (`./data_catalogue`), the tool attempts to resolve to unified storage location for the active context. Provide an explicit catalog path to target a specific database directory.

## Discovery Metadata

- **Category:** `metadata`
- **Tags:** `catalog`, `summary`, `metadata`
- **Usage Examples:**
  1. Retrieve summary from unified storage (default resolves to `~/.igloo_mcp/catalogs/{database}/`).
  2. Return minimal counts only: `get_catalog_summary(response_mode="minimal")`.
  3. Load summary from custom directory: `get_catalog_summary(catalog_dir="./artifacts/catalog")`.

## Returns

Returns a dictionary containing:
- `catalog_info`: Basic catalog information
- `statistics`: Summary statistics
- `objects`: Object counts by type
- `last_updated`: When catalog was last built
- `status`: Catalog status and health

## Examples

### Basic Catalog Summary
```json
{
  "tool": "get_catalog_summary",
  "arguments": {}
}
```

**Expected Output**:
```json
{
  "request_id": "750e8400-e29b-41d4-a716-446655440002",
  "catalog_info": {
    "database": "MY_DATABASE",
    "total_objects": 150,
    "last_updated": "2025-01-15T10:30:00Z"
  },
  "statistics": {
    "tables": 45,
    "views": 30,
    "functions": 15,
    "procedures": 8,
    "schemas": 12,
    "databases": 1
  },
  "objects": {
    "by_type": {
      "table": 45,
      "view": 30,
      "function": 15,
      "procedure": 8
    },
    "by_schema": {
      "PUBLIC": 25,
      "ANALYTICS": 35,
      "STAGING": 20
    }
  },
  "timing": {
    "total_duration_ms": 5.23
  },
  "last_updated": "2025-01-15T10:30:00Z",
  "status": {
    "health": "healthy",
    "warnings": [],
    "errors": []
  }
}
```

### Response Fields

- **`request_id`**: UUID4 correlation ID for distributed tracing
- **`timing`**: Performance metrics with `total_duration_ms` only (simple operation)

### Custom Catalog Directory
```json
{
  "tool": "get_catalog_summary",
  "arguments": {
    "catalog_dir": "./my_catalog"
  }
}
```

## Common Use Cases

### Catalog Health Check
Verify catalog status and identify any issues before running analysis.

### Object Inventory
Get a quick overview of what objects are available in your database.

### Pre-Analysis Validation
Check if catalog is up-to-date before running lineage or dependency analysis.

### Documentation Generation
Use summary data to generate documentation about your data architecture.

## Troubleshooting

### Catalog Not Found
**Error**: `Catalog not found in directory`
**Solution**:
- Verify catalog directory path
- Run `build_catalog` tool first
- Check directory permissions

### Corrupted Catalog
**Error**: `Catalog appears to be corrupted`
**Solution**:
- Rebuild catalog using `build_catalog` tool
- Check for incomplete catalog builds
- Verify disk space

### Outdated Catalog
**Warning**: `Catalog is older than 7 days`
**Solution**:
- Rebuild catalog to get latest changes
- Check if objects have been modified
- Consider automated catalog updates

## Related Tools

- [build_catalog](build_catalog.md) - Build or rebuild catalog
- [build_dependency_graph](build_dependency_graph.md) - Build dependency graphs

## Status Indicators

### Health Status
- `healthy`: Catalog is in good condition
- `warning`: Minor issues detected
- `error`: Critical issues found
- `stale`: Catalog is outdated

### Common Warnings
- `Catalog is older than 7 days`
- `Some objects may be missing`
- `Incomplete lineage data`

### Common Errors
- `Catalog file corrupted`
- `Missing required metadata`
- `Permission denied`

## Notes

- Catalog must be built before getting summary
- Summary is generated from catalog metadata
- Status indicators help identify catalog health
- Object counts include all cataloged object types
- Last updated timestamp shows when catalog was built
