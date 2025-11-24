# MCP Tools Quick Reference

> **Quick Links**: [Complete API Reference](README.md) | [Error Catalog](ERROR_CATALOG.md) | [Error Handling](ERROR_HANDLING.md)

## Core MCP Tools

| Tool | Purpose | Key Parameters | Documentation |
|------|---------|----------------|---------------|
| [execute_query](tools/execute_query.md) | Execute SQL queries with guardrails and timeouts | statement, timeout_seconds, reason | [Details](tools/execute_query.md) |
| [build_catalog](tools/build_catalog.md) | Build metadata catalog | database, format, output_dir | [Details](tools/build_catalog.md) |
| [get_catalog_summary](tools/get_catalog_summary.md) | Get catalog info | catalog_dir | [Details](tools/get_catalog_summary.md) |
| [search_catalog](tools/search_catalog.md) | Search locally built catalog artifacts | catalog_dir, name_contains, column_contains | [Details](tools/search_catalog.md) |
| [build_dependency_graph](tools/build_dependency_graph.md) | Build dependency graph | database, schema, format | [Details](tools/build_dependency_graph.md) |
| [test_connection](tools/test_connection.md) | Test connectivity | none | [Details](tools/test_connection.md) |
| [health_check](tools/health_check.md) | System/profile/catalog health | include_cortex, include_profile, include_catalog | [Details](tools/health_check.md) |
| [create_report](tools/create_report.md) | Create a new living report | title, template, tags, description | [Details](tools/create_report.md) |
| [evolve_report](tools/evolve_report.md) | Evolve a living report with LLM assistance | report_selector, instruction, constraints, dry_run | [Details](tools/evolve_report.md) |
| [render_report](tools/render_report.md) | Render reports to various formats | report_selector, format, persist_output | [Details](tools/render_report.md) |
| [search_report](tools/search_report.md) | Search for living reports | report_selector | [Details](tools/search_report.md) |

## By Category

### Query & Data Access
- execute_query

### Metadata & Discovery
- build_catalog
- get_catalog_summary
- search_catalog
- build_dependency_graph

### Health & Diagnostics
- test_connection
- health_check

### Living Reports
- create_report
- evolve_report
- render_report
- search_report

Living reports are stored in your igloo-mcp instance directory (default: `~/.igloo-mcp/reports/`) and are accessible across all projects.

## See Also

- [Complete API Reference](README.md) - Full API documentation with examples
- [Error Catalog](ERROR_CATALOG.md) - Error reference and solutions
- [Error Handling](ERROR_HANDLING.md) - Error handling architecture
- [Catalog Examples](../examples/catalog-examples.md) - Real-world catalog examples
- [Getting Started Guide](../getting-started.md) - Quick start overview
