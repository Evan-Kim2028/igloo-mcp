# Error Catalog

Complete reference for igloo-mcp errors and solutions.

## MCP Exception Types

All MCP tools use standardized exception types for consistent error handling:

- **MCPValidationError**: Parameter validation failures (invalid types, missing required fields, out-of-range values)
- **MCPExecutionError**: Runtime execution failures (connection errors, query failures, timeouts)
- **MCPSelectorError**: Resource selector resolution failures (not found, ambiguous, invalid format)
- **MCPToolError**: Base class for all MCP tool errors

All exceptions include:
- `message`: Human-readable error message
- `error_code`: Programmatic error code
- `hints`: List of actionable suggestions
- `context`: Additional context data

## MCPValidationError Errors

### 1. Profile Validation Failed

**Exception Type:** `MCPValidationError`

**Message:**
```
Snowflake profile validation failed: Profile 'invalid_name' not found
```

**Error Structure:**
```json
{
  "message": "Snowflake profile validation failed: Profile 'invalid_name' not found",
  "error_type": "MCPValidationError",
  "error_code": "VALIDATION_ERROR",
  "validation_errors": [
    "Profile: invalid_name",
    "Available: default, prod, dev"
  ],
  "hints": [
    "Check configuration with 'snow connection list'",
    "Verify profile settings",
    "Run 'snow connection add' to create a new profile"
  ]
}
```

**Cause:** Specified profile doesn't exist in Snowflake CLI configuration

**Solutions:**
1. Set valid profile: `export SNOWFLAKE_PROFILE=default`
2. List profiles: `snow connection list`
3. Create profile: `snow connection add`

**Related Tools:** execute_query, test_connection, health_check

---

### 2. SQL Statement Not Permitted

**Exception Type:** `MCPValidationError`

**Message:**
```
SQL statement type 'Delete' is not permitted.
```

**Error Structure:**
```json
{
  "message": "SQL statement type 'Delete' is not permitted.",
  "error_type": "MCPValidationError",
  "error_code": "VALIDATION_ERROR",
  "validation_errors": [
    "Statement type: Delete"
  ],
  "hints": [
    "Set IGLOO_MCP_SQL_PERMISSIONS='write' to enable write operations",
    "Use SELECT statements for read-only queries"
  ]
}
```

**Cause:** Attempting a blocked SQL operation. By default igloo-mcp denies write + DDL statements (`INSERT`, `UPDATE`, `CREATE`, `ALTER`) and destructive commands (`DELETE`, `DROP`, `TRUNCATE`). Statements the Snowflake parser cannot classify fall back to `Command` and are also rejected.

**Solutions:**
1. Use suggested safe alternative (soft delete, view creation)
2. Verify necessity of the blocked statement; request a human to run it if required
3. If you override SQL permissions, explicitly enable the needed verb and leave `select` enabled

**Related Tools:** execute_query

---

### 3. Invalid Database Name

**Message:**
```
Invalid database name: contains illegal characters
```

**Cause:** Database name contains SQL injection characters or invalid syntax

**Solutions:**
1. Use valid identifier: `MYDB` not `my;db`
2. Quote if needed: `"MY-DB"`
3. Check database exists: `SHOW DATABASES`

**Related Tools:** build_catalog, execute_query

---

## MCPExecutionError Errors

### 4. Query Timeout

**Exception Type:** `MCPExecutionError`

**Message:**
```
Query timeout after 30s
```

**Error Structure:**
```json
{
  "message": "Query timeout after 30s",
  "error_type": "MCPExecutionError",
  "error_code": "EXECUTION_ERROR",
  "operation": "query",
  "hints": [
    "Increase timeout: timeout_seconds=480",
    "Add WHERE/LIMIT clause to reduce data volume",
    "Use larger warehouse for complex queries"
  ],
  "context": {
    "timeout_seconds": 30,
    "warehouse": "COMPUTE_WH",
    "database": "ANALYTICS"
  }
}
```

**Verbose Mode:** When `verbose_errors=True`, additional hints include:
- Filter by clustering keys
- Catalog-guided filtering
- Detailed query preview

**Cause:** Query exceeded timeout limit (default 30s)

**Solutions by Scenario:**

**Large Table Scan:**
```python
execute_query(
    statement="SELECT * FROM sales WHERE date >= '2024-01-01'",  # Add filter
    timeout_seconds=300,
    reason="Analyze sales since 2024-01-01",
)
```

**Complex Aggregation:**
```python
execute_query(
    statement="SELECT customer_id, SUM(revenue) FROM orders GROUP BY 1",
    warehouse="LARGE_WH",  # Scale up
    timeout_seconds=600,
    reason="Compute customer revenue aggregates",
)
```

**Testing/Development:**
```python
execute_query(
    statement="SELECT * FROM huge_table LIMIT 1000",  # Sample
    timeout_seconds=60,
    reason="Sample rows from huge_table for testing",
)
```

**Related Tools:** execute_query

---

### 5. Connection Failed

**Exception Type:** `MCPExecutionError`

**Message:**
```
Tool execution failed: Snowflake connection test failed
```

**Error Structure:**
```json
{
  "message": "Tool execution failed: Snowflake connection test failed",
  "error_type": "MCPExecutionError",
  "error_code": "EXECUTION_ERROR",
  "operation": "test_connection",
  "hints": [
    "Check test_connection logs for details",
    "Verify input parameters are correct",
    "Check system resources and connectivity"
  ]
}
```

**Cause:** Cannot establish connection to Snowflake

**Solutions:**
1. Check credentials: `snow connection test --connection default`
2. Verify network: Check firewall, VPN, proxy settings
3. Check warehouse: Ensure warehouse is running and accessible
4. Verify role permissions: `USE ROLE <your_role>`

**Related Tools:** test_connection, execute_query, health_check

---

### 6. Catalog Build Failed

**Exception Type:** `MCPExecutionError`

**Message:**
```
Tool execution failed: Permission denied on database 'RESTRICTED_DB'
```

**Error Structure:**
```json
{
  "message": "Tool execution failed: Permission denied on database 'RESTRICTED_DB'",
  "error_type": "MCPExecutionError",
  "error_code": "EXECUTION_ERROR",
  "operation": "build_catalog",
  "hints": [
    "Check build_catalog logs for details",
    "Verify input parameters are correct",
    "Check system resources and connectivity"
  ]
}
```

**Cause:** Insufficient permissions to read database metadata

**Solutions:**
1. Request permissions: `GRANT USAGE ON DATABASE x TO ROLE y`
2. Switch role: Use role with required permissions
3. Build specific database: Target accessible databases only

**Related Tools:** build_catalog

---

### 7. Catalog Directory Not Found

**Exception Type:** `MCPSelectorError`

**Message:**
```
Catalog directory not found: ./data_catalogue
```

**Error Structure:**
```json
{
  "message": "Catalog directory not found: ./data_catalogue",
  "error_type": "MCPSelectorError",
  "error_code": "SELECTOR_ERROR",
  "selector": "./data_catalogue",
  "error": "not_found",
  "hints": [
    "Verify catalog_dir exists: ./data_catalogue",
    "Run build_catalog first to create catalog artifacts"
  ]
}
```

**Cause:** Trying to search catalog before building it

**Solutions:**
1. Build catalog first:
   ```python
   build_catalog(database="ANALYTICS")
   ```
2. Then search catalog:
   ```python
   search_catalog(database="ANALYTICS")
   ```

**Related Tools:** search_catalog, get_catalog_summary, build_catalog

---

### 8. Report Not Found

**Exception Type:** `MCPSelectorError`

**Message:**
```
Could not resolve report selector: Sales Report
```

**Error Structure:**
```json
{
  "message": "Could not resolve report selector: Sales Report",
  "error_type": "MCPSelectorError",
  "error_code": "SELECTOR_ERROR",
  "selector": "Sales Report",
  "error": "not_found",
  "hints": [
    "Verify selector exists: Sales Report",
    "Check spelling and case sensitivity",
    "List available resources to see valid selectors"
  ]
}
```

**Cause:** Report selector cannot be resolved (not found, ambiguous, or invalid format)

**Solutions:**
1. Verify report exists: Use `search_report` to list available reports
2. Use exact report ID instead of title
3. Check spelling and case sensitivity

**Related Tools:** evolve_report, render_report, search_report

---

### 9. Resource Manager Not Available

**Exception Type:** `MCPExecutionError`

**Message:**
```
Tool execution failed: Resource manager not available
```

**Cause:** MCP server component not fully initialized

**Solutions:**
1. Wait for server startup to complete
2. Check server logs for initialization errors
3. Restart MCP server

**Related Tools:** health_check

---

## Warning Messages

### 10. Profile Validation Issue

**Message:**
```
Warning: Profile validation issue detected: Missing warehouse parameter
```

**Cause:** Profile configuration incomplete

**Solutions:**
1. Check profile: `health_check(include_profile=True)`
2. Update profile: `snow connection add --connection-name default`
3. Override in tool call: Use `warehouse="COMPUTE_WH"`

---

## Error Response Format

All MCP tool errors follow a standardized structure:

### MCPValidationError
```json
{
  "message": "Parameter validation failed for execute_query",
  "error_type": "MCPValidationError",
  "error_code": "VALIDATION_ERROR",
  "validation_errors": [
    "Field 'reason': Missing required parameter",
    "Field 'timeout_seconds': Expected integer, got string"
  ],
  "hints": [
    "Check parameter types and required fields",
    "Review execute_query parameter schema"
  ]
}
```

### MCPExecutionError
```json
{
  "message": "Query timeout after 30s",
  "error_type": "MCPExecutionError",
  "error_code": "EXECUTION_ERROR",
  "operation": "execute_query",
  "hints": [
    "Increase timeout: timeout_seconds=480",
    "Add WHERE/LIMIT clause to reduce data volume"
  ],
  "context": {
    "timeout_seconds": 30,
    "warehouse": "COMPUTE_WH"
  }
}
```

### MCPSelectorError
```json
{
  "message": "Catalog directory not found: ./data_catalogue",
  "error_type": "MCPSelectorError",
  "error_code": "SELECTOR_ERROR",
  "selector": "./data_catalogue",
  "error": "not_found",
  "hints": [
    "Verify catalog_dir exists: ./data_catalogue",
    "Run build_catalog first to create catalog artifacts"
  ]
}
```

## Getting Help

**Enable Verbose Errors:**
```python
execute_query(
    statement="...",
    verbose_errors=True,  # Get detailed diagnostics
    reason="Investigate query failure with verbose diagnostics",
)
```

**Check System Health:**
```python
health_check(include_profile=True, include_catalog=True)  # Overall system status
test_connection()  # Connection test
```

**Review Configuration:**
```python
health_check(include_profile=True)  # Returns:
{
  "system": {"healthy": true},
  "profile": {
    "config_path": "~/.snowflake/config.toml",
    "config_exists": true,
    "available_profiles": ["default", "prod"],
    "validation": {"valid": true},
    "recommendations": [...]
}
```

---

## Error Handling Decorator

All MCP tools use the `@tool_error_handler` decorator which automatically:
- Converts `ValidationError` to `MCPValidationError`
- Converts unexpected exceptions to `MCPExecutionError`
- Logs errors with context
- Preserves MCP exception types (re-raises as-is)

Tools can raise MCP exceptions directly for fine-grained control, or rely on the decorator for automatic conversion.

**Last Updated:** January 2025
**Version:** 0.3.0+
