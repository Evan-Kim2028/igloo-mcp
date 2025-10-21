# Igloo MCP MCP API Documentation

## Overview

Igloo MCP provides 11 MCP tools for Snowflake data operations, built on top of the official `snowflake-labs-mcp` service.

## Quick Links

- [Tool Reference](#available-tools)
- [Getting Started](#getting-started)
- [Error Handling](#error-handling)
- [Configuration](#configuration)

## Available Tools

### Core Query Tools

1. **[execute_query](tools/execute_query.md)** - Execute SQL queries with validation and timeouts
2. **[preview_table](tools/preview_table.md)** - Quick table preview with row limits

### Metadata & Discovery Tools

3. **[build_catalog](tools/build_catalog.md)** - Build comprehensive metadata catalog
4. **[get_catalog_summary](tools/get_catalog_summary.md)** - Get catalog summary information
5. **[query_lineage](tools/query_lineage.md)** - Query object dependencies and lineage
6. **[build_dependency_graph](tools/build_dependency_graph.md)** - Build dependency graph

### System & Health Tools

7. **[test_connection](tools/test_connection.md)** - Test Snowflake connectivity
8. **[health_check](tools/health_check.md)** - Comprehensive health status
9. **[check_profile_config](tools/check_profile_config.md)** - Validate profile configuration

### Resource Management Tools

10. **[get_resource_status](tools/get_resource_status.md)** - Check MCP resource availability
11. **[check_resource_dependencies](tools/check_resource_dependencies.md)** - Check resource dependencies

## Getting Started

### Prerequisites

- Snowflake account with valid credentials
- Snowflake CLI configured with connection profile
- igloo-mcp installed

### Basic Usage

```python
# 1. Test connection
tool: test_connection
result: {"status": "connected", "profile": "default"}

# 2. Execute a query
tool: execute_query
params:
  statement: "SELECT * FROM customers LIMIT 10"
result: {"rowcount": 10, "rows": [...]}

# 3. Build catalog for metadata
tool: build_catalog
params:
  database: "MY_DATABASE"
result: {"output_dir": "./data_catalogue", "totals": {...}}
```

## Error Handling

All tools follow consistent error patterns:

- **ValueError**: Invalid parameters or configuration
- **RuntimeError**: Execution failures (connection, timeout, etc.)

Enable verbose errors for detailed diagnostics:

```python
tool: execute_query
params:
  statement: "SELECT * FROM large_table"
  timeout_seconds: 300
  verbose_errors: true  # Get detailed optimization hints
```

## Configuration

Tools use Snowflake CLI profiles for configuration:

```bash
# List available profiles
snow connection list

# Set default profile
export SNOWFLAKE_PROFILE=my_profile

# Override per-tool
tool: execute_query
params:
  warehouse: "LARGE_WH"
  database: "ANALYTICS"
```

## Common Patterns

### Pattern 1: Data Discovery

```python
# 1. Check connection
test_connection()

# 2. Build catalog
build_catalog(database="PROD")

# 3. Get summary
get_catalog_summary()

# 4. Query specific tables
execute_query(statement="SELECT * FROM important_table LIMIT 100")
```

### Pattern 2: Dependency Analysis

```python
# 1. Build dependency graph
build_dependency_graph(database="PROD")

# 2. Query lineage for specific object
query_lineage(
    object_name="MY_TABLE",
    direction="both",
    depth=3
)
```

### Pattern 3: Health Monitoring

```python
# 1. Check overall health
health_check()

# 2. Verify profile configuration
check_profile_config()

# 3. Check resource availability
get_resource_status()
```

## Performance Tips

1. **Use appropriate timeouts** - Default is 30s, increase for large queries
2. **Enable lightweight history (optional)** - Set `IGLOO_MCP_QUERY_HISTORY=/path/to/query_history.jsonl` to write one JSON object per executed query (status, preview, query_id when available, duration)
2. **Batch operations** - Catalog builds are optimized for batch processing
3. **Enable caching** - Repeated queries use Snowflake result cache
4. **Profile your queries** - Use verbose_errors for optimization hints

## Support

- Documentation: `/docs/api/tools/`
- Examples: `/examples/`
- Issues: GitHub repository

---

**Version:** v2.0.0
**Last Updated:** December 2024
