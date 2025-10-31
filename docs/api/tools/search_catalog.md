# search_catalog

Query the catalog artifacts produced by `build_catalog` and retrieve matching
objects (tables, views, functions, etc.) along with basic metadata and columns.

## Description

Use this tool after running `build_catalog` to explore the locally cached
snapshot without reconnecting to Snowflake. It supports substring filtering on
object names or column names and returns at most `limit` matches.

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `catalog_dir` | string | ❌ No | `./data_catalogue` | Directory containing `catalog.json` or `catalog.jsonl`. |
| `object_types` | array[string] | ❌ No | — | Optional list of object types (`table`, `view`, `function`, …). |
| `database` | string | ❌ No | — | Filter results to a specific database. |
| `schema` | string | ❌ No | — | Filter results to a specific schema. |
| `name_contains` | string | ❌ No | — | Case-insensitive substring match on object name. |
| `column_contains` | string | ❌ No | — | Case-insensitive substring match on column name. |
| `limit` | integer | ❌ No | 20 | Maximum number of results to return (1-500). |

## Example

```json
{
  "status": "success",
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
  ]
}
```

## Notes

- If the catalog directory does not contain a build artifact, the tool returns
  an error instructing the user to run `build_catalog`.
- Column metadata is surfaced when available so downstream tools can inspect
  schemas without rerunning catalog queries.
