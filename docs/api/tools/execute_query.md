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
| `reason` | string | ❌ No | - | Short reason for running the query. Stored in Snowflake `QUERY_TAG` and local history; avoid sensitive information. |
| `timeout_seconds` | integer | ❌ No | 120 | Query timeout in seconds (1-3600) |
| `verbose_errors` | boolean | ❌ No | false | Include detailed optimization hints |
| `warehouse` | string | ❌ No | profile | Warehouse override (Snowflake identifier) |
| `database` | string | ❌ No | profile | Database override (Snowflake identifier) |
| `schema` | string | ❌ No | profile | Schema override (Snowflake identifier) |
| `role` | string | ❌ No | profile | Role override (Snowflake identifier) |
| `post_query_insight` | string \| object | ❌ No | - | Optional summary/JSON describing the results; stored alongside history and cache artifacts. |
| `response_mode` | string | ❌ No | auto | `auto` runs synchronously until nearing the 120s tools/call limit, `async` returns immediately with an `execution_id` to poll via `fetch_async_query_result`, and `sync` forces inline execution. |

> Identifiers accept standard Snowflake names such as `ANALYTICS_WH` or double-quoted values like `"Analytics-WH"` / `"Sales Analytics"`.

## Discovery Metadata

- **Category:** `query`
- **Tags:** `sql`, `execute`, `analytics`, `warehouse`
- **Usage Examples:**
  1. Preview recent sales rows with an analytics warehouse override.
  2. Run a regional revenue aggregation with an explicit analyst role and 30s timeout.
  3. Enqueue a long-running aggregation with `response_mode="async"` and fetch the cached rows later.

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
- When `response_mode="auto"` needs to hand execution back before the MCP RPC limit, the response switches to the async form shown below and includes `inline_wait_seconds` to document how long the tool waited before yielding control.

## Async Execution & Polling

Set `response_mode="async"` (or let the default `auto` mode run past the inline wait budget) to enqueue long-running queries without tripping the MCP `tools/call` deadline. The tool immediately returns an `execution_id` along with the recommended poll tool:

```json
{
  "status": "accepted",
  "execution_id": "f0af3d...",
  "poll_tool": "fetch_async_query_result",
  "inline_wait_seconds": 90,
  "message": "Query accepted for asynchronous execution..."
}
```

Use [`fetch_async_query_result`](fetch_async_query_result.md) with the execution ID to check status or retrieve cached rows once the warehouse finishes. Results still land in history/caches with the same `execution_id`, so you can reuse existing manifest paths if the client timed out earlier.

### RPC Timeout Alignment

- `response_mode="auto"` now launches every query on the async executor, waits up to `min(timeout_seconds, IGLOO_MCP_RPC_SOFT_TIMEOUT - 5s)`, and returns the full result if the warehouse finishes inside that window.
- When the inline wait budget expires, the tool yields the async handle shown above (`status: accepted`) so the MCP client can return before the ~120s `tools/call` deadline. The background job keeps running, writes history/artifacts, and is immediately retrievable via `fetch_async_query_result`.
- Set `IGLOO_MCP_RPC_SOFT_TIMEOUT` if your client’s RPC budget differs from the default 110s. Lowering it (for example to 60s) makes `auto` mode fall back to async sooner; raising it gives the inline wait more time.

## Post-Query Insights & Key Metrics

`execute_query` now emits lightweight diagnostics for every successful response without running additional SQL:

- `key_metrics` captures the observed rowcount, number of columns, and per-column stats such as non-null ratios, numeric min/max/avg, categorical top values, and time spans (based solely on the returned rows).
- `insights` distills those metrics into short bullets (for example, "Returned 2,145 rows across 8 columns" or "event_ts covers 2025-10-01 → 2025-10-07 (144h)").

These fields travel with tool responses, query history JSONL, and cache manifests so downstream agents can reason about the dataset without re-running any queries. When result sets are truncated, the metadata reflects the sampled subset.

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
    reason="Dashboard refresh — monthly rollup",
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

### Async Mode (Long-Running Query)

```python
response = execute_query(
    statement="CALL analytics.run_heavy_rollup()",
    timeout_seconds=480,
    response_mode="async",
    reason="Overnight dashboard refresh"
)
print(response["message"])  # contains execution_id

poll = fetch_async_query_result(execution_id=response["execution_id"])
if poll["status"] == "success":
    print(poll["result"]["rowcount"], "rows ready")
else:
    print("Status:", poll["status"])
```

## Performance Tips

1. **Add WHERE clauses** - Filter data at the source
2. **Use LIMIT for testing** - Sample data before full queries
3. **Increase timeout for complex queries** - Use 300-600s for aggregations
4. **Scale warehouse** - Use larger warehouse for heavy queries
5. **Leverage result cache** - Repeated SQL with the same session context reuses stored CSV/JSON instead of rerunning Snowflake; set `IGLOO_MCP_CACHE_MODE=disabled` to force live execution.
6. **Enable verbose errors** - Get optimization hints when queries fail

## Related Tools

- [preview_table](preview_table.md) - Quick table preview without SQL
- [test_connection](test_connection.md) - Verify connection before queries

## See Also

- [SQL Permissions Configuration](../configuration.md#sql-permissions)
- [Error Catalog](../errors.md)
