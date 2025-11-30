# Environment Variables Reference

Complete reference for all environment variables supported by igloo-mcp.

## Quick Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `SNOWFLAKE_PROFILE` | `"default"` | Snowflake connection profile name |
| `SNOWFLAKE_WAREHOUSE` | - | Override warehouse |
| `SNOWFLAKE_DATABASE` | - | Override database |
| `SNOWFLAKE_SCHEMA` | - | Override schema |
| `SNOWFLAKE_ROLE` | - | Override role |
| `IGLOO_MCP_CACHE_MODE` | `"enabled"` | Result caching mode |
| `IGLOO_MCP_MAX_QUERY_TIMEOUT_SECONDS` | `3600` | Maximum query timeout |
| `LOG_LEVEL` | `"INFO"` | Logging verbosity |

---

## Snowflake Connection

### `SNOWFLAKE_PROFILE`
- **Default**: `"default"`
- **Type**: String
- **Description**: Name of the Snowflake profile to use from `~/.snowflake/config.toml`

**Example**:
```bash
export SNOWFLAKE_PROFILE="production"
export SNOWFLAKE_PROFILE="dev"
```

**When to use**: Switch between different Snowflake accounts or environments

---

### `SNOWFLAKE_WAREHOUSE`
- **Default**: None (uses profile default)
- **Type**: String
- **Description**: Override the warehouse for all queries

**Example**:
```bash
export SNOWFLAKE_WAREHOUSE="COMPUTE_WH_XL"
export SNOWFLAKE_WAREHOUSE="XSMALL_WH"
```

**Use cases**:
- Cost optimization: Use smaller warehouse for metadata queries
- Performance: Use larger warehouse for heavy analytics
- Testing: Isolate development workloads

---

### `SNOWFLAKE_DATABASE`
- **Default**: None (uses profile default)
- **Type**: String
- **Description**: Override the default database

**Example**:
```bash
export SNOWFLAKE_DATABASE="ANALYTICS"
export SNOWFLAKE_DATABASE="PRODUCTION"
```

---

### `SNOWFLAKE_SCHEMA`
- **Default**: None (uses profile default)
- **Type**: String
- **Description**: Override the default schema

**Example**:
```bash
export SNOWFLAKE_SCHEMA="PUBLIC"
export SNOWFLAKE_SCHEMA="REPORTING"
```

---

### `SNOWFLAKE_ROLE`
- **Default**: None (uses profile default)
- **Type**: String
- **Description**: Override the Snowflake role

**Example**:
```bash
export SNOWFLAKE_ROLE="ANALYST_ROLE"
export SNOWFLAKE_ROLE="READONLY_ROLE"
```

---

## Query Execution

### `IGLOO_MCP_MIN_QUERY_TIMEOUT_SECONDS`
- **Default**: `1`
- **Type**: Integer
- **Description**: Minimum allowed query timeout in seconds

**Example**:
```bash
export IGLOO_MCP_MIN_QUERY_TIMEOUT_SECONDS=5
```

---

### `IGLOO_MCP_MAX_QUERY_TIMEOUT_SECONDS`
- **Default**: `3600` (1 hour)
- **Type**: Integer
- **Description**: Maximum allowed query timeout in seconds

**Example**:
```bash
export IGLOO_MCP_MAX_QUERY_TIMEOUT_SECONDS=7200  # 2 hours
```

**When to increase**: Long-running analytical queries or large data exports

---

### `IGLOO_MCP_MIN_REASON_LENGTH`
- **Default**: `5`
- **Type**: Integer
- **Description**: Minimum character length for the `reason` parameter

**Example**:
```bash
export IGLOO_MCP_MIN_REASON_LENGTH=10
```

---

### `IGLOO_MCP_MAX_REASON_LENGTH`
- **Default**: `200`
- **Type**: Integer
- **Description**: Maximum character length for the `reason` parameter

---

### `IGLOO_MCP_MAX_SQL_STATEMENT_LENGTH`
- **Default**: `1000000` (1MB)
- **Type**: Integer
- **Description**: Maximum SQL statement size in characters

**Example**:
```bash
export IGLOO_MCP_MAX_SQL_STATEMENT_LENGTH=2000000  # 2MB
```

---

## Result Caching

### `IGLOO_MCP_CACHE_MODE`
- **Default**: `"enabled"`
- **Type**: String (enum)
- **Options**: `enabled`, `disabled`, `read_only`, `force_refresh`
- **Description**: Controls query result caching behavior

**Modes**:
- `enabled`: Cache reads and writes (default)
- `disabled`: No caching, always execute queries
- `read_only`: Use cache but don't write new results
- `force_refresh`: Bypass cache reads, refresh all queries

**Example**:
```bash
export IGLOO_MCP_CACHE_MODE="disabled"     # Testing
export IGLOO_MCP_CACHE_MODE="read_only"    # Production (read-only)
export IGLOO_MCP_CACHE_MODE="force_refresh" # Force cache refresh
```

**Use cases**:
- `disabled`: Development/testing with changing data
- `read_only`: Production safety (prevent cache poisoning)
- `force_refresh`: Scheduled cache updates

---

### `IGLOO_MCP_CACHE_TTL_HOURS`
- **Default**: `24`
- **Type**: Integer
- **Description**: Cache entry time-to-live in hours

**Example**:
```bash
export IGLOO_MCP_CACHE_TTL_HOURS=12   # Refresh twice daily
export IGLOO_MCP_CACHE_TTL_HOURS=168  # Weekly refresh
```

---

## Catalog Building

### `IGLOO_MCP_CATALOG_CONCURRENCY`
- **Default**: `16`
- **Type**: Integer
- **Description**: Number of parallel DDL fetch operations during catalog build

**Example**:
```bash
export IGLOO_MCP_CATALOG_CONCURRENCY=32  # Faster builds
export IGLOO_MCP_CATALOG_CONCURRENCY=8   # Lower warehouse load
```

**Tuning guide**:
- Increase for faster builds (requires more warehouse resources)
- Decrease to reduce warehouse load or avoid rate limits

---

### `IGLOO_MCP_MAX_DDL_CONCURRENCY`
- **Default**: `8`
- **Type**: Integer
- **Description**: Maximum concurrent DDL requests to Snowflake

**Example**:
```bash
export IGLOO_MCP_MAX_DDL_CONCURRENCY=16
```

---

## Result Size Limits

### `IGLOO_MCP_RESULT_SIZE_LIMIT_MB`
- **Default**: `1`
- **Type**: Integer
- **Description**: Maximum result set size in megabytes before truncation warning

---

### `IGLOO_MCP_RESULT_KEEP_FIRST_ROWS`
- **Default**: `500`
- **Type**: Integer
- **Description**: Number of first rows to keep when truncating large results

---

### `IGLOO_MCP_RESULT_KEEP_LAST_ROWS`
- **Default**: `50`
- **Type**: Integer
- **Description**: Number of last rows to keep when truncating large results

---

### `IGLOO_MCP_RESULT_TRUNCATION_THRESHOLD`
- **Default**: `1000`
- **Type**: Integer
- **Description**: Row count threshold before truncation kicks in

---

## Logging & Debugging

### `LOG_LEVEL`
- **Default**: `"INFO"`
- **Type**: String (enum)
- **Options**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Description**: Logging verbosity level

**Example**:
```bash
export LOG_LEVEL="DEBUG"    # Verbose logging for troubleshooting
export LOG_LEVEL="WARNING"  # Production (errors and warnings only)
```

**Recommended settings**:
- Development: `DEBUG` or `INFO`
- Production: `WARNING` or `ERROR`
- Troubleshooting: `DEBUG`

---

## Configuration Precedence

Environment variables override values in this order (highest to lowest):

1. **Tool parameter** - Direct parameter in tool call
2. **Environment variable** - OS environment variable
3. **Config file** - `~/.igloo_mcp/config.yaml`
4. **Profile default** - Snowflake profile settings
5. **Hard-coded default** - Built-in default values

**Example**:
```bash
# Config file has warehouse="SMALL_WH"
# But this overrides it:
export SNOWFLAKE_WAREHOUSE="LARGE_WH"

# And this overrides both:
execute_query(statement="...", warehouse="XL_WH")
```

---

## Common Configuration Patterns

### Development Environment
```bash
export SNOWFLAKE_PROFILE="dev"
export SNOWFLAKE_WAREHOUSE="DEV_WH"
export IGLOO_MCP_CACHE_MODE="disabled"
export LOG_LEVEL="DEBUG"
```

### Production Environment
```bash
export SNOWFLAKE_PROFILE="production"
export SNOWFLAKE_WAREHOUSE="COMPUTE_WH"
export IGLOO_MCP_CACHE_MODE="enabled"
export IGLOO_MCP_CACHE_TTL_HOURS=12
export LOG_LEVEL="WARNING"
```

### High-Performance Analytics
```bash
export SNOWFLAKE_WAREHOUSE="COMPUTE_WH_XL"
export IGLOO_MCP_MAX_QUERY_TIMEOUT_SECONDS=7200
export IGLOO_MCP_CATALOG_CONCURRENCY=32
export IGLOO_MCP_CACHE_MODE="enabled"
```

### Cost-Optimized Development
```bash
export SNOWFLAKE_WAREHOUSE="XSMALL_WH"
export IGLOO_MCP_CACHE_MODE="enabled"
export IGLOO_MCP_CACHE_TTL_HOURS=168  # Weekly refresh
export IGLOO_MCP_CATALOG_CONCURRENCY=8
```

---

## Validation & Error Handling

All environment variables are validated on startup:

- **Type checking**: Integers must be numeric, enums must match valid options
- **Range checking**: Timeouts must be within min/max bounds
- **Clear errors**: Invalid values show expected format and valid options

**Example error**:
```
ConfigError: Invalid value for IGLOO_MCP_CACHE_MODE: 'invalid'
Valid options: enabled, disabled, read_only, force_refresh
```

---

## See Also

- [Configuration Guide](../getting-started.md#configuration)
- [Query Execution](../api/tools/execute_query.md)
- [Catalog Building](../api/tools/build_catalog.md)
- [Caching Architecture](../architecture/caching.md)
