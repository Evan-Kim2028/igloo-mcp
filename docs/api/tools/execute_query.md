# execute_query

Execute SQL queries against Snowflake with validation, timeout control, and error verbosity options.

## Description

The `execute_query` tool allows you to run SQL queries against Snowflake with:
- SQL permission validation
- Configurable timeouts
- Session parameter overrides
- Verbose or compact error messages
- Profile health validation

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `statement` | string | ✅ Yes | - | SQL statement to execute (min length 1) |
| `timeout_seconds` | integer | ❌ No | 120 | Query timeout in seconds (1-3600) |
| `verbose_errors` | boolean | ❌ No | false | Include detailed optimization hints |
| `warehouse` | string | ❌ No | profile | Warehouse override (Snowflake identifier) |
| `database` | string | ❌ No | profile | Database override (Snowflake identifier) |
| `schema` | string | ❌ No | profile | Schema override (Snowflake identifier) |
| `role` | string | ❌ No | profile | Role override (Snowflake identifier) |

> Identifiers accept standard Snowflake names such as `ANALYTICS_WH` or double-quoted values like `"Analytics-WH"` / `"Sales Analytics"`.

## Discovery Metadata

- **Category:** `query`
- **Tags:** `sql`, `execute`, `analytics`, `warehouse`
- **Usage Examples:**
  1. Preview recent sales rows with an analytics warehouse override.
  2. Run a regional revenue aggregation with an explicit analyst role and 120s timeout.

## Returns

```json
{
  "statement": "SELECT * FROM customers LIMIT 10",
  "rowcount": 10,
  "rows": [
    {"customer_id": 1, "name": "Alice", "email": "alice@example.com"},
    {"customer_id": 2, "name": "Bob", "email": "bob@example.com"}
  ]
}
```

## Errors

### ValueError

**Profile validation failed**
```
Profile validation failed: Profile 'invalid' not found
Available profiles: default, prod, dev
```
**Solution:** Set valid SNOWFLAKE_PROFILE or use --profile flag

**SQL statement blocked**
```
SQL statement type 'Delete' is not permitted.
Safe alternatives:
  soft_delete: UPDATE users SET deleted_at = CURRENT_TIMESTAMP()
```
**Solution:** Use safe alternatives or enable permission in config

### RuntimeError

**Query timeout (compact)**
```
Query timeout (120s). Try: timeout_seconds=480, add WHERE/LIMIT clause,
or scale warehouse. Use verbose_errors=True for detailed hints.
```

**Query timeout (verbose)**
```
Query timeout after 120s.

Quick fixes:
1. Increase timeout: execute_query(..., timeout_seconds=480)
2. Add filter: Add WHERE clause to reduce data volume
3. Sample data: Add LIMIT clause for testing (e.g., LIMIT 1000)
4. Scale warehouse: Consider using a larger warehouse

Current settings:
  - Timeout: 120s
  - Warehouse: COMPUTE_WH
  - Database: ANALYTICS

Query preview: SELECT * FROM huge_table WHERE...
```

**Solution:** Increase timeout, add filters, or scale warehouse

## Examples

### Basic Query

```python
result = execute_query(
    statement="SELECT COUNT(*) as count FROM orders WHERE date >= '2024-01-01'"
)
print(f"Row count: {result['rowcount']}")
print(f"Result: {result['rows'][0]['count']}")
```

### With Overrides

```python
result = execute_query(
    statement="SELECT * FROM large_table LIMIT 1000",
    timeout_seconds=300,
    warehouse="LARGE_WH",
    verbose_errors=True
)
```

### Handling Errors

```python
try:
    result = execute_query(
        statement="SELECT * FROM non_existent_table"
    )
except ValueError as e:
    print(f"Validation error: {e}")
except RuntimeError as e:
    print(f"Execution error: {e}")
```

## Performance Tips

1. **Add WHERE clauses** - Filter data at the source
2. **Use LIMIT for testing** - Sample data before full queries
3. **Increase timeout for complex queries** - Use 300-600s for aggregations
4. **Scale warehouse** - Use larger warehouse for heavy queries
5. **Enable verbose errors** - Get optimization hints when queries fail

## Related Tools

- [preview_table](preview_table.md) - Quick table preview without SQL
- [test_connection](test_connection.md) - Verify connection before queries

## See Also

- [SQL Permissions Configuration](../configuration.md#sql-permissions)
- [Error Catalog](../errors.md)
