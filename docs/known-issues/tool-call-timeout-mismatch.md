## Known Issue: MCP tool-call timeout mismatch vs. query execution

Status: Mitigated (auto async fallback shipped in v0.2.3)

### Summary
In some sessions, `igloo_mcp.execute_query` returns a tool-level timeout:

```
tool call error: timed out awaiting tools/call after 120s
```

even though the underlying Snowflake query completes successfully and is recorded in the local history with `status: success` and cached rows.

### Impact
- The client reports a timeout while results exist in history/artifacts.
- Can trigger unnecessary re-runs or misdiagnosis as a Snowflake/warehouse issue.

### Environment
- macOS host running Codex CLI with MCP tools.
- Igloo MCP profile: `mystenlabs-keypair`
- Warehouse: `LOCAL_READ_WH`
- Role: `SECURITYADMIN`

### Artifacts and Logs
```
History file:  /Users/evandekim/Documents/ml-data-science/logs/igloo_mcp_query_history.jsonl
Artifacts dir: /Users/evandekim/.igloo_mcp/logs/artifacts
```

### Reproduction
1. Execute a query via MCP that runs between ~10–90s with `timeout_seconds` set to a value >= runtime (e.g., 120s).
2. In some sessions, the client call returns the 120s tools/call timeout above.
3. Inspect local history/artifacts and observe the query was recorded as `status: success` with cached rows.

Example successful entries observed in history (summarized):

- Fetch RequestProcessed events (two variants)
  - `status: success`, `duration_ms: ~66_000`, `rowcount: 2`
  - Rows cached under:
    - `~/.igloo_mcp/logs/artifacts/cache/ff8f58d4.../rows.jsonl`
    - `~/.igloo_mcp/logs/artifacts/cache/92587ffa.../rows.jsonl`

- Daily VWAP (two dates)
  - `status: success`, `duration_ms: ~4_000`, `rowcount: 2`
  - Rows cached under: `~/.igloo_mcp/logs/artifacts/cache/4b4e1a62.../rows.jsonl`

Counter-example (expected behavior):

- Tight-window withdraw fee test
  - `status: timeout` with `timeout_seconds: 400` (legitimate Snowflake timeout/cancel)
  - SQL artifact: `~/.igloo_mcp/logs/artifacts/queries/by_sha/b88e94dc3075ae9e30f0ea62cb94c1227d09e8c8765168869268d71edee65ef2.sql`

### Expected Behavior
If the underlying Snowflake query succeeds within the specified `timeout_seconds`, the MCP tool should return `success` to the client without a tools/call timeout.

### Actual Behavior
For some successful queries (<= ~66s), the client reports a tools/call timeout at ~120s while the history shows `status: success` and cached rows exist.

### Likely Cause
Mismatch between the client/harness tools/call RPC deadline (~120s) and the tool execution lifecycle. The Igloo MCP server completes the query and persists history/artifacts, but the client RPC times out before receiving the response.

### Workarounds
- Keep query runtime comfortably under the client RPC limit (e.g., <110s) or raise the client-side RPC timeout if configurable.
- Use `execute_query(..., response_mode="async")` together with `fetch_async_query_result` so the query continues running after the client returns; results are persisted under the same `execution_id`.
- On timeout, check history/artifacts for `sql_sha256` and cached rows; reuse cached results when present.
- For heavier queries, split into smaller steps or temporarily increase warehouse size.

### Proposed Fixes / Current Mitigation
- **v0.2.3+:** The default `response_mode="auto"` now dispatches every query asynchronously, waits up to `min(timeout_seconds, IGLOO_MCP_RPC_SOFT_TIMEOUT - 5s)`, and returns the full result if it finishes in time. Otherwise it yields `status: accepted` with `inline_wait_seconds` plus the `execution_id`, so callers can immediately poll [`fetch_async_query_result`](../api/tools/fetch_async_query_result.md) without hitting the MCP RPC limit.
- Align timeouts:
  - Ensure client RPC timeout > Snowflake `timeout_seconds` used by `execute_query`.
  - Expose/configure the client-side tools/call timeout where possible (`IGLOO_MCP_RPC_SOFT_TIMEOUT` controls when auto mode yields).
- Improve resilience:
  - If completion occurs after client timeout, surface a history pointer the client can poll.
  - Return partial/cached results eagerly when available.

### Notes
- The tight-window test’s `status: timeout` is a valid Snowflake timeout (400s). The mismatch issue concerns successful queries that still surfaced a client-level timeout message.
