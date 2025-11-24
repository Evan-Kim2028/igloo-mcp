# build_catalog

Build comprehensive metadata catalog for Snowflake databases.

## Unified Storage (Default Behavior)

By default, `build_catalog` saves catalogs to **unified storage** for centralized management and incremental updates:

- **Per-database catalogs**: `~/.igloo_mcp/catalogs/{database_name}/`
- **Account-wide catalogs**: `~/.igloo_mcp/catalogs/account/`
- **Current database**: `~/.igloo_mcp/catalogs/current/` (when database not specified)

Each database folder contains:
- `catalog.json` or `catalog.jsonl` - Full catalog metadata
- `catalog_summary.json` - Summary statistics
- `_catalog_metadata.json` - Metadata for incremental updates (per-database only)

### Benefits of Unified Storage

1. **Centralized Management**: All catalogs in one location, organized by database
2. **Incremental Updates**: Metadata files enable fast incremental catalog refreshes
3. **Per-Database Tracking**: Each database maintains its own metadata for change detection
4. **Consistent Structure**: Standardized organization across all catalogs

### Using Custom Paths

To use a custom directory instead of unified storage, explicitly specify `output_dir`:

```python
# Uses unified storage (default)
build_catalog(database="ANALYTICS")

# Uses custom directory
build_catalog(
    database="ANALYTICS",
    output_dir="./my_custom_catalog"
)
```

You can also configure the catalog root directory using the `IGLOO_MCP_CATALOG_ROOT` environment variable (see [Configuration Guide](../../configuration.md)).

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `output_dir` | string | ❌ No | ./data_catalogue | Directory for catalog artifacts. Default resolves to unified storage at `~/.igloo_mcp/catalogs/{database}/`. Specify a custom path to override. |
| `database` | string | ❌ No | current | Specific database to catalog (Snowflake identifier) |
| `account` | boolean | ❌ No | false | Include entire account (ACCOUNT_USAGE) |
| `format` | string | ❌ No | json | Output format (`json` or `jsonl`) |

> If `account` is `true`, omit `database`. Identifiers support both unquoted names (e.g., `ANALYTICS`) and quoted names (e.g., `"Sales Analytics"`).

## Discovery Metadata

- **Category:** `metadata`
- **Tags:** `catalog`, `metadata`, `introspection`, `documentation`
- **Usage Examples:**
  1. Build an account-wide catalog to share with governance teams (`account=true`, `format=jsonl`).
  2. Export a single database catalog into `./artifacts/catalog` for developer docs.

## Returns

When using unified storage (default), the `output_dir` in the response shows the resolved path:

```json
{
  "status": "success",
  "output_dir": "/Users/username/.igloo_mcp/catalogs/ANALYTICS",
  "database": "ANALYTICS",
  "account_scope": false,
  "format": "json",
  "totals": {
    "databases": 1,
    "schemas": 15,
    "tables": 142,
    "views": 38,
    "materialized_views": 2,
    "dynamic_tables": 0,
    "tasks": 5,
    "functions": 12,
    "procedures": 8,
    "columns": 2847
  }
}
```

> **Note**: The `output_dir` in the response reflects the actual directory where files were saved, which may differ from the input parameter when using unified storage.

## Error Handling

This tool uses standardized MCP exception types:

- **MCPValidationError**: Invalid parameters (e.g., invalid format, unsafe path)
- **MCPExecutionError**: Catalog build failures (e.g., permission denied, connection errors)

All errors include actionable hints and context. See [ERROR_CATALOG.md](../ERROR_CATALOG.md) for complete error reference.

## Examples

### Using Unified Storage (Default)

```python
# Build catalog for specific database (saves to ~/.igloo_mcp/catalogs/ANALYTICS/)
build_catalog(
    database="ANALYTICS",
    format="jsonl"
)

# Build entire account catalog (saves to ~/.igloo_mcp/catalogs/account/)
build_catalog(account=True)

# Build current database catalog (saves to ~/.igloo_mcp/catalogs/current/)
build_catalog()
```

### Using Custom Paths

```python
# Use custom directory instead of unified storage
build_catalog(
    database="ANALYTICS",
    output_dir="./my_custom_catalog"
)

# Export to project-specific location
build_catalog(
    database="PRODUCT",
    output_dir="./docs/catalogs/product"
)

# Use absolute path
build_catalog(
    database="ANALYTICS",
    output_dir="/shared/catalogs/analytics"
)
```

## Performance

- **Small database (< 50 tables):** 5-10 seconds
- **Medium database (50-500 tables):** 10-30 seconds
- **Large database (500+ tables):** 30-120 seconds

## Related

- [get_catalog_summary](get_catalog_summary.md) - Read catalog info
