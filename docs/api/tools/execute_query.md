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
| `reason` | string | ✅ Yes | - | Short reason for running the query (min length 5). Stored in Snowflake `QUERY_TAG` and local history; avoid sensitive information. |
| `timeout_seconds` | integer | ❌ No | 120 | Query timeout in seconds (1-3600) |
| `verbose_errors` | boolean | ❌ No | false | Include detailed optimization hints |
| `result_mode` | string | ❌ No | "full" | Control response verbosity: `full`, `summary`, `schema_only`, or `sample`. Reduces token usage by 60-90%. |
| `warehouse` | string | ❌ No | profile | Warehouse override (Snowflake identifier) |
| `database` | string | ❌ No | profile | Database override (Snowflake identifier) |
| `schema` | string | ❌ No | profile | Schema override (Snowflake identifier) |
| `role` | string | ❌ No | profile | Role override (Snowflake identifier) |
| `post_query_insight` | string \| object | ❌ No | - | Optional summary/JSON describing the results; stored alongside history and cache artifacts. |

> Identifiers accept standard Snowflake names such as `ANALYTICS_WH` or double-quoted values like `"Analytics-WH"` / `"Sales Analytics"`.

## Discovery Metadata

- **Category:** `query`
- **Tags:** `sql`, `execute`, `analytics`, `warehouse`
- **Usage Examples:**
  1. Preview recent sales rows with an analytics warehouse override.
  2. Run a regional revenue aggregation with an explicit analyst role and 30s timeout.
  3. Run a long-running aggregation with explicit timeout and warehouse override.

## Returns

```json
{
  "statement": "SELECT * FROM customers LIMIT 10",
  "rowcount": 10,
  "rows": [
    {"customer_id": 1, "name": "Alice", "email": "alice@example.com"},
    {"customer_id": 2, "name": "Bob", "email": "bob@example.com"}
  ],
  "columns": ["customer_id", "name", "email"],
  "objects": [
    {"database": "SALES", "schema": "PUBLIC", "name": "CUSTOMERS", "type": null}
  ],
  "source_databases": ["SALES"],
  "tables": ["SALES.PUBLIC.CUSTOMERS"],
  "session_context": {
    "warehouse": "ANALYTICS_WH",
    "database": "SALES",
    "schema": "PUBLIC",
    "role": "ANALYST"
  },
  "cache": {
    "hit": false,
    "cache_key": "f2f5d2…",
    "manifest_path": "logs/artifacts/cache/f2f5d2…/manifest.json",
    "result_csv_path": "logs/artifacts/cache/f2f5d2…/rows.csv",
    "created_at": "2025-01-15T12:34:56.123456+00:00"
  },
  "audit_info": {
    "execution_id": "11111111111111111111111111111111",
    "history_path": "logs/doc.jsonl",
    "cache": {
      "mode": "enabled",
      "hit": false,
      "key": "f2f5d2…",
      "manifest": "logs/artifacts/cache/f2f5d2…/manifest.json"
    },
    "columns": ["customer_id", "name", "email"],
    "session_context": {
      "warehouse": "ANALYTICS_WH",
      "database": "SALES",
      "schema": "PUBLIC",
      "role": "ANALYST"
    }
  },
  "key_metrics": {
    "total_rows": 10,
    "sampled_rows": 10,
    "num_columns": 3,
    "columns": [
      {
        "name": "customer_id",
        "kind": "numeric",
        "non_null_ratio": 1.0,
        "min": 1,
        "max": 10,
        "avg": 5.5
      },
      {
        "name": "name",
        "kind": "categorical",
        "non_null_ratio": 1.0,
        "top_values": [
          {"value": "Alice", "count": 1, "ratio": 0.1}
        ],
        "distinct_values": 10
      }
    ],
    "truncated_output": false
  },
  "insights": [
    "Returned 10 rows across 3 columns.",
    "customer_id spans 1 → 10 (avg 5.5)."
  ]
}
```

- Result caching is on by default; subsequent runs with the same SQL, profile, and resolved session context return `cache.hit = true` along with the manifest path and CSV/JSON artifacts for auditability.
- `key_metrics` and `insights` are automatically derived from the returned rows (no extra SQL) so downstream tools get quick summaries of the seen data. Metrics include non-null ratios, numeric ranges, categorical top values, and time spans based on the sampled result set.
- `source_databases`/`tables` enumerate every referenced object extracted from the compiled SQL so history logs and cache hits retain accurate cross-database attribution even when the active session database differs.

## Post-Query Insights & Key Metrics

`execute_query` now emits lightweight diagnostics for every successful response without running additional SQL:

- `key_metrics` captures the observed rowcount, number of columns, and per-column stats such as non-null ratios, numeric min/max/avg, categorical top values, and time spans (based solely on the returned rows).
- `insights` distills those metrics into short bullets (for example, "Returned 2,145 rows across 8 columns" or "event_ts covers 2025-10-01 → 2025-10-07 (144h)").

These fields travel with tool responses, query history JSONL, and cache manifests so downstream agents can reason about the dataset without re-running any queries. When result sets are truncated, the metadata reflects the sampled subset.

## Result Modes (Token Efficiency)

The `result_mode` parameter controls response verbosity to reduce token usage in LLM contexts.

### Modes

| Mode | Rows Returned | Use Case | Token Reduction |
|------|---------------|----------|-----------------|
| `full` | All rows | Complete data retrieval (default) | 0% (baseline) |
| `summary` | 5 sample rows + key_metrics | Quick analysis with metrics | ~90% |
| `schema_only` | 0 rows (schema + metrics only) | Schema discovery | ~95% |
| `sample` | 10 sample rows | Quick preview/validation | ~60-80% |

**Important:** Sampling returns rows in **result order** (as returned by Snowflake), not database order. For deterministic, repeatable samples across runs, add an `ORDER BY` clause to your query:

```python
# ✅ Deterministic sampling - same 10 rows every time
result = execute_query(
    statement="SELECT * FROM users ORDER BY user_id LIMIT 1000",
    result_mode="sample",  # Returns first 10 rows in sorted order
    reason="Preview user data"
)

# ⚠️ Non-deterministic - may return different rows each run
result = execute_query(
    statement="SELECT * FROM users",  # No ORDER BY
    result_mode="sample",  # Returns first 10 rows in arbitrary order
    reason="Preview user data"
)
```

### Response Format

All non-full modes add `result_mode` and `result_mode_info` to the response:

```json
{
  "result_mode": "summary",
  "result_mode_info": {
    "mode": "summary",
    "total_rows": 10000,
    "rows_returned": 5,
    "sample_size": 5,
    "columns_count": 8,
    "hint": "Use result_mode='full' to retrieve all rows"
  },
  "rows": [...5 sample rows...],
  "key_metrics": {...},
  "insights": [...]
}
```

### Examples

**Schema Discovery**:
```python
result = execute_query(
    statement="SELECT * FROM large_table",
    result_mode="schema_only",
    reason="Discover table schema"
)
# Returns columns, types, key_metrics but no rows
```

**Quick Preview**:
```python
result = execute_query(
    statement="SELECT * FROM orders WHERE date >= '2024-01-01'",
    result_mode="sample",
    reason="Preview recent orders"
)
# Returns first 10 rows
```

**Metrics-Focused Analysis**:
```python
result = execute_query(
    statement="SELECT customer_id, total_spend FROM customer_summary",
    result_mode="summary",
    reason="Analyze customer spending patterns"
)
# Returns key_metrics + 5 sample rows (90% token reduction)
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
Query timeout (30s). Try: timeout_seconds=480, add WHERE/LIMIT clause,
or scale warehouse. Use verbose_errors=True for detailed hints.
```

**Query timeout (verbose)**
```
Query timeout after 30s.

Quick fixes:
1. Increase timeout: execute_query(..., timeout_seconds=480)
2. Add filter: Add WHERE clause to reduce data volume
3. Sample data: Add LIMIT clause for testing (e.g., LIMIT 1000)
4. Scale warehouse: Consider using a larger warehouse

Current settings:
  - Timeout: 30s
  - Warehouse: COMPUTE_WH
  - Database: ANALYTICS

Query preview: SELECT * FROM huge_table WHERE...
```

**Solution:** Increase timeout, add filters, or scale warehouse

## Examples

### Basic Query

```python
result = execute_query(
    statement="SELECT COUNT(*) as count FROM orders WHERE date >= '2024-01-01'",
    reason="Monthly order count for reporting"
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
    reason="Dashboard refresh — monthly rollup",
    verbose_errors=True
)
```

### Handling Errors

```python
try:
    result = execute_query(
        statement="SELECT * FROM non_existent_table",
        reason="Testing error handling"
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
5. **Leverage result cache** - Repeated SQL with the same session context reuses stored CSV/JSON instead of rerunning Snowflake; set `IGLOO_MCP_CACHE_MODE=disabled` to force live execution.
6. **Enable verbose errors** - Get optimization hints when queries fail

## Related Tools

- [test_connection](test_connection.md) - Verify connection before queries

## See Also

- [SQL Permissions Configuration](../configuration.md#sql-permissions)
- [Error Catalog](../errors.md)
