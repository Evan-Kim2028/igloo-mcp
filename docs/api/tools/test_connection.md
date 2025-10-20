# test_connection

Test Snowflake connection and verify credentials.

## Parameters

None - uses current profile configuration.

## Returns

```json
{
  "status": "success",
  "connected": true,
  "profile": "default",
  "warehouse": "COMPUTE_WH",
  "database": "ANALYTICS",
  "schema": "PUBLIC",
  "role": "ANALYST"
}
```

Note: For SSO/Okta troubleshooting (e.g., which authenticator a profile uses), prefer `health_check`, which surfaces the active profile’s authenticator details.

## Errors

```json
{
  "status": "failed",
  "connected": false,
  "profile": "default",
  "error": "Authentication failed: Invalid credentials"
}
```

## Examples

```python
# Test current connection
result = test_connection()
if result["connected"]:
    print(f"Connected to {result['warehouse']}")
else:
    print(f"Connection failed: {result['error']}")
```

## Use Cases

1. **Before running queries** - Verify connection is valid
2. **Troubleshooting** - Check which warehouse/database is active
3. **Profile validation** - Ensure credentials are correct

## Related

- [check_profile_config](check_profile_config.md) - Validate profile setup
- [health_check](health_check.md) - Comprehensive health status with authenticator details
