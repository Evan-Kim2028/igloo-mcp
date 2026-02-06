# health_check

Get comprehensive health status for the MCP server and Snowflake connection.

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `response_mode` | string | ❌ No | `"minimal"` | Response verbosity: `minimal`, `standard`, or `full`. |
| `detail_level` | string | ❌ No | - | **DEPRECATED** alias for `response_mode`. |
| `include_cortex` | boolean | ❌ No | true | Check Cortex AI availability |
| `include_profile` | boolean | ❌ No | true | Validate profile configuration |
| `include_catalog` | boolean | ❌ No | false | Check catalog resource status |
| `request_id` | string | ❌ No | auto-generated | Request correlation ID for distributed tracing (UUID4). Auto-generated if not provided. |

## Discovery Metadata

- **Category:** `diagnostics`
- **Tags:** `health`, `profile`, `cortex`, `catalog`, `diagnostics`
- **Usage Examples:**
  1. `include_cortex=true`, `include_catalog=true` to perform the full suite of checks.
  2. `include_cortex=false`, `include_catalog=false` for a fast profile-only validation.

## Returns

```json
{
  "request_id": "850e8400-e29b-41d4-a716-446655440003",
  "overall_status": "healthy",
  "connection": {
    "status": "connected",
    "connected": true,
    "profile": "quickstart",
    "warehouse": "COMPUTE_WH",
    "database": "ANALYTICS",
    "schema": "PUBLIC",
    "role": "ANALYST"
  },
  "profile": {
    "status": "valid",
    "profile": "quickstart",
    "config": {
      "config_path": "/Users/user/.config/snowflake/config.toml",
      "config_exists": true,
      "available_profiles": ["quickstart", "prod"],
      "default_profile": "quickstart",
      "current_profile": "quickstart",
      "profile_count": 2
    },
    "authentication": {
      "authenticator": "externalbrowser",
      "is_externalbrowser": true,
      "is_okta_url": false
    }
  },
  "catalog": {
    "status": "ready"
  },
  "system": {
    "status": "healthy",
    "healthy": true,
    "error_count": 0,
    "warning_count": 0,
    "metrics": {
      "uptime_seconds": 120
    },
    "recent_errors": []
  },
  "timing": {
    "total_duration_ms": 125.45
  }
}
```

### Response Fields

- **`request_id`**: UUID4 correlation ID for distributed tracing
- **`timing`**: Performance metrics with `total_duration_ms` only

- `system` now reflects the consolidated `get_comprehensive_health` response with `healthy`, `error_count`, `metrics.uptime_seconds`, and recent errors populated. Older monitors that only expose `get_health_status()` are still supported.
- If configured, `query_circuit_breaker` shows `execute_query` circuit state (`closed`, `open`, `half_open`, or `disabled`) and retry timing metadata.

### Storage Paths Diagnostics (Full Mode Only)

When `response_mode="full"`, the response includes a `diagnostics.storage_paths` object showing where igloo-mcp stores data:

```json
{
  "diagnostics": {
    "storage_paths": {
      "scope": "global",
      "base_directory": "/Users/username/.igloo_mcp",
      "query_history": "/Users/username/.igloo_mcp/logs/doc.jsonl",
      "artifacts": "/Users/username/.igloo_mcp/logs/artifacts",
      "cache": "/Users/username/.igloo_mcp/logs/artifacts/cache",
      "reports": "/Users/username/.igloo_mcp/reports",
      "catalogs": "/Users/username/.igloo_mcp/catalogs",
      "namespaced": false
    }
  }
}
```

When available, full diagnostics also include `diagnostics.query_circuit_breaker` mirroring the current `execute_query` circuit breaker status.

**Storage Scope Modes:**
- `global`: All data stored in `~/.igloo_mcp/` (default, persistent across projects)
- `repo`: Data stored in current repository under `./logs/` (project-specific)

**Path Configuration:**
- Set scope via `IGLOO_MCP_LOG_SCOPE` environment variable
- Enable namespacing via `IGLOO_MCP_NAMESPACED_LOGS=true`
- Override individual paths via `IGLOO_MCP_QUERY_HISTORY`, `IGLOO_MCP_REPORTS_ROOT`, etc.

**Related Documentation:**
- [Environment Variables Reference](../../configuration/ENVIRONMENT_VARIABLES.md)
- [Living Reports Storage](../../living-reports/user-guide.md#storage)

## Examples

```python
health = health_check()
print(f"Status: {health['status']}")
print(f"Version: {health['version']}")

if health['snowflake_connection']:
    print("Snowflake: Connected ✓")
else:
    print("Snowflake: Disconnected ✗")
```

## Related

- [test_connection](test_connection.md) - Test Snowflake only
