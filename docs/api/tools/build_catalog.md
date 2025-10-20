# build_catalog

Build comprehensive metadata catalog for Snowflake databases.

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `output_dir` | string | ❌ No | ./data_catalogue | Directory for generated catalog artifacts |
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

```json
{
  "output_dir": "./data_catalogue",
  "totals": {
    "databases": 3,
    "schemas": 15,
    "tables": 142,
    "views": 38
  }
}
```

## Examples

```python
# Build catalog for specific database
build_catalog(
    database="ANALYTICS",
    format="jsonl"
)

# Build entire account catalog
build_catalog(
    account=True,
    output_dir="./full_catalog"
)
```

## Performance

- **Small database (< 50 tables):** 5-10 seconds
- **Medium database (50-500 tables):** 10-30 seconds
- **Large database (500+ tables):** 30-120 seconds

## Related

- [get_catalog_summary](get_catalog_summary.md) - Read catalog info
