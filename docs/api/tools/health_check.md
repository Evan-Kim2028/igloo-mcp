# health_check

Get comprehensive health status for the MCP server and Snowflake connection.

## Parameters

None - returns full system status.

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
    "uptime_seconds": 120,
    "timestamp": 1702345678.9
  }
}
```

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
