# preview_table

Quick preview of table contents without writing SQL.

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `table_name` | string | ✅ Yes | - | Table to preview (`DATABASE.SCHEMA.TABLE` or simple name) |
| `limit` | integer | ❌ No | 100 | Maximum rows to return (minimum 1) |
| `warehouse` | string | ❌ No | profile | Warehouse override (Snowflake identifier) |
| `database` | string | ❌ No | profile | Database override (Snowflake identifier) |
| `schema` | string | ❌ No | profile | Schema override (Snowflake identifier) |

> Identifiers may be unquoted (e.g., `ANALYTICS.FINANCE.TRANSACTIONS`) or quoted (`"Sales Analytics"."Reporting"."Orders"`). Up to three segments are supported.

## Discovery Metadata

- **Category:** `query`
- **Tags:** `preview`, `table`, `metadata`, `sampling`
- **Usage Examples:**
  1. Preview `ANALYTICS.FINANCE.TRANSACTIONS` with a 20 row limit and analytics warehouse override.
  2. Sample `PIPELINE_V2_GROOT_DB.PIPELINE_V2_GROOT_SCHEMA.DEX_TRADES_STABLE` with the default session context.

## Returns

```json
{
  "statement": "SELECT * FROM customers LIMIT 100",
  "rowcount": 100,
  "rows": [...]
}
```

## Examples

```python
# Simple preview
preview_table(table_name="customers", limit=10)

# With overrides
preview_table(
    table_name="analytics.prod.sales",
    limit=500,
    warehouse="LARGE_WH"
)
```

## Related

- [execute_query](execute_query.md) - For complex queries
