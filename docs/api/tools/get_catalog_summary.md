# Tool: get_catalog_summary

## Purpose

Retrieves summary information about a built catalog, including statistics and metadata about the cataloged objects.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `catalog_dir` | string | No | Directory containing catalog data (default: "./data_catalogue") |

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
  "last_updated": "2025-01-15T10:30:00Z",
  "status": {
    "health": "healthy",
    "warnings": [],
    "errors": []
  }
}
```

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
- [query_lineage](query_lineage.md) - Analyze object lineage
- [build_dependency_graph](build_dependency_graph.md) - Build dependency graphs
- [preview_table](preview_table.md) - Preview table structure

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
