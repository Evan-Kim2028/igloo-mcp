# Igloo MCP MCP API Documentation

## Overview

Igloo MCP provides a focused set of MCP tools for Snowflake data operations, built on top of the official `snowflake-labs-mcp` service.

## Quick Links

- [Tool Reference](#available-tools)
- [Getting Started](#getting-started)
- [Error Handling](#error-handling)
- [Configuration](#configuration)

## Available Tools

### Core Query Tools

1. **[execute_query](tools/execute_query.md)** - Execute SQL queries with validation and timeouts

### Metadata & Discovery Tools

2. **[build_catalog](tools/build_catalog.md)** - Build comprehensive metadata catalog
3. **[get_catalog_summary](tools/get_catalog_summary.md)** - Get catalog summary information
4. **[search_catalog](tools/search_catalog.md)** - Search locally built catalog artifacts
5. **[build_dependency_graph](tools/build_dependency_graph.md)** - Build dependency graph

### Health & Diagnostics Tools

6. **[test_connection](tools/test_connection.md)** - Test Snowflake connectivity
7. **[health_check](tools/health_check.md)** - Comprehensive health status

### Living Reports Tools

8. **[create_report](tools/create_report.md)** *(MCP-only)* - Create a new living report with optional template and tags
9. **[evolve_report](tools/evolve_report.md)** *(MCP-only)* - Evolve a living report with LLM assistance and audit logging
10. **render_report** *(MCP-only)* - Render reports to various formats (see [create_report](tools/create_report.md) for details)
11. **search_report** *(MCP-only)* - Search for living reports with intelligent fallback behavior (see [create_report](tools/create_report.md) for details)

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
execute_query(
    statement="SELECT * FROM important_table LIMIT 100",
    reason="Inspect sample rows from important_table",
)
```

### Pattern 2: Dependency Analysis

```python
# 1. Build dependency graph
build_dependency_graph(database="PROD")

# 2. Search catalog for related objects
search_catalog(
    catalog_dir="./data_catalogue",  # Default resolves to unified storage
    name_contains="MY_TABLE"
)
```

### Pattern 3: Health Monitoring

```python
# 1. Check overall health (includes profile and catalog status)
health_check(
    include_profile=True,
    include_catalog=True,
    include_cortex=False
)

# 2. Test connection separately if needed
test_connection()
```

## Performance Tips

1. **Use appropriate timeouts** - Default is 30s, increase for large queries
2. **Inspect lightweight history** - Records land in `logs/doc.jsonl` (falling back to `~/.igloo_mcp/logs/doc.jsonl`); override via `IGLOO_MCP_QUERY_HISTORY` / `IGLOO_MCP_ARTIFACT_ROOT`
3. **Leverage local result cache** - Default-on CSV/JSON cache keyed by SQL + context; control with `IGLOO_MCP_CACHE_MODE` / `IGLOO_MCP_CACHE_ROOT`
4. **Search the catalog snapshot** - Run `search_catalog` after `build_catalog` to locate tables/views/columns instantly
5. **Batch operations** - Catalog builds are optimized for batch processing
6. **Profile your queries** - Use `verbose_errors` for optimization hints

## Support

- Documentation: `/docs/api/tools/`
- Examples: `/examples/`
- Issues: GitHub repository

## See Also

- [Getting Started Guide](../getting-started.md) - Quick start overview
- [MCP Integration Guide](../mcp-integration.md) - MCP client setup
- [Error Catalog](ERROR_CATALOG.md) - Error reference
- [Error Handling](ERROR_HANDLING.md) - Error handling architecture
- [Tools Index](TOOLS_INDEX.md) - Quick tool reference

---

**Version:** 0.3.0
**Last Updated:** November 2025
