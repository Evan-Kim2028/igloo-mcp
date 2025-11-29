# search_catalog

Query the catalog artifacts produced by `build_catalog` and retrieve matching
objects (tables, views, functions, etc.) along with basic metadata and columns.

## Description

Use this tool after running `build_catalog` to explore the locally cached
snapshot without reconnecting to Snowflake. It supports substring filtering on
object names or column names and returns at most `limit` matches.

**Unified Storage**: When `catalog_dir` is the default, the tool resolves to unified storage location (`~/.igloo_mcp/catalogs/{database}/`). Set `search_all_databases=true` to search across all database catalogs in unified storage.

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `catalog_dir` | string | ❌ No | `./data_catalogue` | Directory containing `catalog.json` or `catalog.jsonl`. Default resolves to unified storage at `~/.igloo_mcp/catalogs/{database}/` when used with `build_catalog` default. |
| `search_all_databases` | boolean | ❌ No | `false` | If `true` and `catalog_dir` is default, search across all database catalogs in unified storage. |
| `object_types` | array[string] | ❌ No | — | Optional list of object types (`table`, `view`, `function`, …). |
| `database` | string | ❌ No | — | Filter results to a specific database. |
| `schema` | string | ❌ No | — | Filter results to a specific schema. |
| `name_contains` | string | ❌ No | — | Case-insensitive substring match on object name. |
| `column_contains` | string | ❌ No | — | Case-insensitive substring match on column name. |
| `limit` | integer | ❌ No | 20 | Maximum number of results to return (1-500). |
| `request_id` | string | ❌ No | auto-generated | Request correlation ID for distributed tracing (UUID4). Auto-generated if not provided. |

## Example

```json
{
  "status": "success",
  "request_id": "650e8400-e29b-41d4-a716-446655440001",
  "catalog_dir": "./artifacts/catalog",
  "total_matches": 3,
  "limit": 20,
  "results": [
    {
      "object_type": "table",
      "database": "ANALYTICS",
      "schema": "REPORTING",
      "name": "SALES_FACT",
      "columns": [
        {"name": "ID", "data_type": "NUMBER"},
        {"name": "REGION", "data_type": "VARCHAR"}
      ]
    }
  ],
  "timing": {
    "search_duration_ms": 12.34,
    "total_duration_ms": 15.67
  },
  "warnings": []
}
```

### Response Fields

- **`request_id`**: UUID4 correlation ID for distributed tracing
- **`timing`**: Performance metrics in milliseconds
  - `search_duration_ms`: Time spent searching catalog data
  - `total_duration_ms`: Total execution time
- **`warnings`**: Array of non-fatal issues (e.g., missing catalog files, empty if none)

## Notes

- If the catalog directory does not contain a build artifact, the tool returns
  an error instructing the user to run `build_catalog`.
- Column metadata is surfaced when available so downstream tools can inspect
  schemas without rerunning catalog queries.
