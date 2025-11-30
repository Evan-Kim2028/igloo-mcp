# Igloo MCP API Documentation

## Overview

Igloo MCP provides a focused set of MCP tools for Snowflake data operations, built on SnowCLI.

## Quick Links

- [Core Concepts](#core-concepts)
- [Tool Reference](#available-tools)
- [Getting Started](#getting-started)
- [Configuration](#configuration)

## Core Concepts

- **[Progressive Disclosure](./PROGRESSIVE_DISCLOSURE.md)** - Control response verbosity for token efficiency
- **[Error Handling](./ERROR_HANDLING.md)** - Error handling patterns and recovery strategies
- **[Error Catalog](./ERROR_CATALOG.md)** - Complete error reference
- **[Tools Index](./TOOLS_INDEX.md)** - Quick tool reference

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

8. **[create_report](tools/create_report.md)** *(MCP-only)* - Create new living reports with optional templates
9. **[evolve_report](tools/evolve_report.md)** *(MCP-only)* - Evolve reports with LLM assistance and audit logging
10. **[evolve_report_batch](tools/evolve_report_batch.md)** *(MCP-only)* - Atomic multi-operation report evolution
11. **[render_report](tools/render_report.md)** *(MCP-only)* - Render reports to various formats
12. **[search_report](tools/search_report.md)** *(MCP-only)* - Search for living reports with intelligent fallback
13. **[get_report](tools/get_report.md)** *(MCP-only)* - Read reports with progressive disclosure
14. **[get_report_schema](tools/get_report_schema.md)** *(MCP-only)* - API schema introspection

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
  reason: "Preview customer data"
result: {"rowcount": 10, "rows": [...]}

# 3. Build catalog for metadata
tool: build_catalog
params:
  database: "MY_DATABASE"
result: {"output_dir": "./data_catalogue", "totals": {...}}
```

## Error Handling

All tools use consistent error patterns:

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
    catalog_dir="./data_catalogue",
    name_contains="MY_TABLE"
)
```

### Pattern 3: Health Monitoring

```python
# 1. Check overall health
health_check()

# 2. Test connection if needed
test_connection()
```

## Performance Tips

1. **Use appropriate timeouts** - Default is 30s, increase for large queries
2. **Inspect lightweight history** - Records land in `logs/doc.jsonl` (falling back to `~/.igloo_mcp/logs/doc.jsonl`)
3. **Leverage local result cache** - Default-on CSV/JSON cache keyed by SQL + context
4. **Search the catalog snapshot** - Run `search_catalog` after `build_catalog` to locate tables/views/columns instantly
5. **Batch operations** - Catalog builds optimize for batch processing
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
- [Progressive Disclosure](./PROGRESSIVE_DISCLOSURE.md) - Control response verbosity for token efficiency

---

**Version:** 0.3.5
**Last Updated:** November 2025
