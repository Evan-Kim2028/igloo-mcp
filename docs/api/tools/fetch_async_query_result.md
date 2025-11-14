# fetch_async_query_result

Poll the status of an asynchronous `execute_query` call and retrieve cached results once the warehouse finishes. This is used both when you explicitly request `response_mode="async"` and when the default `auto` mode yields early to avoid the MCP RPC timeout (those responses include `inline_wait_seconds` plus the same `execution_id`).

## Description

When `execute_query` runs with `response_mode="async"`, it returns immediately with an `execution_id`. Use `fetch_async_query_result` to check whether the job is still running or to fetch the cached rows/metadata after completion. Results include the same payload that synchronous executions return (rows, columns, cache manifest pointers, `audit_info`, etc.).

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `execution_id` | string | ✅ Yes | — | Execution ID returned from `execute_query` when a query is enqueued asynchronously. |
| `include_rows` | boolean | ❌ No | true | Include cached rows when the job has completed. Set to false to retrieve metadata without transferring row data. |

## Returns

```json
{
  "execution_id": "f0af3d...",
  "status": "success",
  "sql_sha256": "4f7c1e2f...",
  "result": {
    "statement": "SELECT ...",
    "rowcount": 2048,
    "rows": [...],
    "cache": {
      "hit": false,
      "manifest_path": "logs/artifacts/cache/.../manifest.json"
    },
    "audit_info": {
      "execution_id": "f0af3d...",
      "history_path": "~/.igloo_mcp/logs/doc.jsonl"
    }
  }
}
```

- `status` can be `pending`, `running`, `success`, or `error`.
- When `include_rows=false`, the `rows` array is omitted while metadata remains.
- `execute_query` will often return `status: accepted` automatically for long queries; the `execution_id` surfaced there is the same value you pass here after the inline wait expires.

## Example

```python
response = execute_query(
    statement="CALL analytics.run_heavy_rollup()",
    timeout_seconds=480,
    response_mode="async"
)

poll = fetch_async_query_result(execution_id=response["execution_id"])
if poll["status"] == "success":
    print("Rows ready:", poll["result"]["rowcount"])
elif poll["status"] == "error":
    raise RuntimeError(poll["error"])
else:
    print("Still running…")
```

## Related Tools

- [execute_query](execute_query.md) — Submit synchronous or asynchronous Snowflake queries.
