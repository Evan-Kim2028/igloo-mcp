# Error Catalog

Complete reference for igloo-mcp errors and solutions.

## ValueError Errors

### 1. Profile Validation Failed

**Message:**
```
Profile validation failed: Profile 'invalid_name' not found
Available profiles: default, prod, dev
```

**Cause:** Specified profile doesn't exist in Snowflake CLI configuration

**Solutions:**
1. Set valid profile: `export SNOWFLAKE_PROFILE=default`
2. List profiles: `snow connection list`
3. Create profile: `snow connection add`

**Related Tools:** execute_query, test_connection, check_profile_config

---

### 2. SQL Statement Not Permitted

**Message:**
```
SQL statement type 'Delete' is not permitted.

Safe alternatives:
  soft_delete: UPDATE users SET deleted_at = CURRENT_TIMESTAMP() WHERE <condition>
  create_view: CREATE VIEW active_users AS SELECT * FROM users WHERE NOT (<condition>)
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

## RuntimeError Errors

### 4. Query Timeout

**Compact Message (~80 tokens):**
```
Query timeout (30s). Try: timeout_seconds=480, add WHERE/LIMIT clause,
or scale warehouse. Use verbose_errors=True for detailed hints. Query ID may be
unavailable on timeout.
```

**Verbose Message (~250 tokens):**
```
Query timeout after 30s.

Quick fixes:
1. Increase timeout: execute_query(..., timeout_seconds=480, reason="Allow longer-running query")
2. Add filter: Add WHERE clause to reduce data volume
3. Sample data: Add LIMIT clause for testing (e.g., LIMIT 1000)
4. Scale warehouse: Use larger warehouse for complex queries

Current settings:
  - Timeout: 30s
  - Warehouse: COMPUTE_WH
  - Database: ANALYTICS

Notes:
  - Query ID may be unavailable when a timeout triggers early cancellation.
  - History is written to `logs/doc.jsonl` by default (override with `IGLOO_MCP_QUERY_HISTORY`)

Query preview: SELECT * FROM huge_table WHERE date >= '2024-01-01'...
```

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

**Related Tools:** execute_query, preview_table

---

### 5. Connection Failed

**Message:**
```
Snowflake connection test failed. Verify credentials, network connectivity,
and warehouse availability.
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

**Message:**
```
Catalog build failed: Permission denied on database 'RESTRICTED_DB'
```

**Cause:** Insufficient permissions to read database metadata

**Solutions:**
1. Request permissions: `GRANT USAGE ON DATABASE x TO ROLE y`
2. Switch role: Use role with required permissions
3. Build specific database: Target accessible databases only

**Related Tools:** build_catalog

---

### 7. Lineage Graph Not Found

**Message:**
```
Lineage graph not found at ./lineage/lineage_graph.pkl.
Run 'build_catalog' first to generate lineage data.
```

**Cause:** Trying to query lineage before building catalog

**Solutions:**
1. Build catalog first:
   ```python
   build_catalog(database="ANALYTICS")
   ```
2. Then query lineage:
   ```python
   query_lineage(object_name="MY_TABLE")
   ```

**Related Tools:** query_lineage, build_catalog

---

### 8. Object Not Found in Lineage

**Message:**
```
Object 'MISSING_TABLE' not found in lineage graph.
Ensure the object exists and catalog is up-to-date.
```

**Cause:** Object doesn't exist or catalog is stale

**Solutions:**
1. Verify object exists: `SHOW TABLES LIKE 'MISSING_TABLE'`
2. Rebuild catalog if stale: `build_catalog(database="DB")`
3. Check object name spelling

**Related Tools:** query_lineage

---

### 9. Resource Manager Not Available

**Message:**
```
Resource manager not available. Server may not be fully initialized.
```

**Cause:** MCP server component not fully initialized

**Solutions:**
1. Wait for server startup to complete
2. Check server logs for initialization errors
3. Restart MCP server

**Related Tools:** get_resource_status, check_resource_dependencies

---

## Warning Messages

### 10. Profile Validation Issue

**Message:**
```
Warning: Profile validation issue detected: Missing warehouse parameter
```

**Cause:** Profile configuration incomplete

**Solutions:**
1. Check profile: `check_profile_config()`
2. Update profile: `snow connection add --connection-name default`
3. Override in tool call: Use `warehouse="COMPUTE_WH"`

---

## Error Response Format

All errors follow this structure:

```json
{
  "error": "RuntimeError",
  "message": "Query timeout (30s). Try: timeout_seconds=480...",
  "context": {
    "tool": "execute_query",
    "statement": "SELECT * FROM large_table",
    "timeout": 120
  }
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
health_check()  # Overall system status
check_profile_config()  # Profile diagnostics
test_connection()  # Connection test
```

**Review Configuration:**
```python
check_profile_config()  # Returns:
{
  "config_path": "~/.snowflake/config.toml",
  "config_exists": true,
  "available_profiles": ["default", "prod"],
  "validation": {"valid": true},
  "recommendations": [...]
}
```

---

**Last Updated:** December 2024
**Version:** v2.0.0
