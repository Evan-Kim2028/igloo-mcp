# health_check

Get comprehensive health status for the MCP server and Snowflake connection.

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `include_cortex` | boolean | ❌ No | true | Check Cortex AI availability |
| `include_profile` | boolean | ❌ No | true | Validate profile configuration |
| `include_catalog` | boolean | ❌ No | false | Check catalog resource status |

## Discovery Metadata

- **Category:** `diagnostics`
- **Tags:** `health`, `profile`, `cortex`, `catalog`, `diagnostics`
- **Usage Examples:**
  1. `include_cortex=true`, `include_catalog=true` to perform the full suite of checks.
  2. `include_cortex=false`, `include_catalog=false` for a fast profile-only validation.

## Returns

```json
{
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
  }
}
```

- `system` now reflects the consolidated `get_comprehensive_health` response (v0.2.5) with `healthy`, `error_count`, `metrics.uptime_seconds`, and recent errors populated. Older monitors that only expose `get_health_status()` are still supported.

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
- [get_resource_status](get_resource_status.md) - Resource availability
