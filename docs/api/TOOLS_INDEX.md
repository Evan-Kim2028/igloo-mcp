# MCP Tools Quick Reference

> **Quick Links**: [Complete API Reference](README.md) | [Error Catalog](ERROR_CATALOG.md) | [Error Handling](ERROR_HANDLING.md)

## Core MCP Tools

Igloo MCP provides **14 focused tools** for Snowflake operations and Living Reports management.

| Tool | Purpose | Key Parameters | Documentation |
|------|---------|----------------|---------------|
| [execute_query](tools/execute_query.md) | Execute SQL queries with guardrails and timeouts | statement, timeout_seconds, reason, result_mode | [Details](tools/execute_query.md) |
| [build_catalog](tools/build_catalog.md) | Build metadata catalog | database, format, output_dir | [Details](tools/build_catalog.md) |
| [get_catalog_summary](tools/get_catalog_summary.md) | Get catalog info | catalog_dir | [Details](tools/get_catalog_summary.md) |
| [search_catalog](tools/search_catalog.md) | Search locally built catalog artifacts | catalog_dir, name_contains, column_contains | [Details](tools/search_catalog.md) |
| [build_dependency_graph](tools/build_dependency_graph.md) | Build dependency graph | database, schema, format | [Details](tools/build_dependency_graph.md) |
| [test_connection](tools/test_connection.md) | Test connectivity | none | [Details](tools/test_connection.md) |
| [health_check](tools/health_check.md) | System/profile/catalog health | include_cortex, include_profile, include_catalog | [Details](tools/health_check.md) |
| [create_report](tools/create_report.md) | Create a new living report | title, template, tags, description | [Details](tools/create_report.md) |
| [evolve_report](tools/evolve_report.md) | Evolve a living report with LLM assistance | report_selector, instruction, constraints, dry_run, response_detail | [Details](tools/evolve_report.md) |
| [evolve_report_batch](tools/evolve_report_batch.md) | Atomic multi-operation report evolution | report_selector, instruction, operations | [Details](tools/evolve_report_batch.md) |
| [render_report](tools/render_report.md) | Render reports to various formats | report_selector, format, persist_output, preview_max_chars | [Details](tools/render_report.md) |
| [search_report](tools/search_report.md) | Search for living reports | report_selector, fields | [Details](tools/search_report.md) |
| [get_report](tools/get_report.md) | Read reports with progressive disclosure | report_selector, mode, section_ids, filters | [Details](tools/get_report.md) |
| [get_report_schema](tools/get_report_schema.md) | Get report structure schemas | schema_type, format | [Details](tools/get_report_schema.md) |

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
- [create_report](tools/create_report.md) - Initialize new structured reports
- [evolve_report](tools/evolve_report.md) - Modify reports with structured changes
- [evolve_report_batch](tools/evolve_report_batch.md) - Atomic multi-operation evolution
- [render_report](tools/render_report.md) - Generate HTML/PDF/Markdown outputs
- [search_report](tools/search_report.md) - Find reports by title/tags
- [get_report](tools/get_report.md) - Read reports with progressive disclosure
- [get_report_schema](tools/get_report_schema.md) - API schema introspection

**Token Efficiency**: Achieve significant token reduction in multi-turn workflows using progressive disclosure (`get_report` modes), selective field retrieval (`search_report` fields), and configurable response verbosity (`evolve_report` response_detail).

Living reports are stored in your igloo-mcp instance directory (default: `~/.igloo-mcp/reports/`) and are accessible across all projects.

## See Also

- [Complete API Reference](README.md) - Full API documentation with examples
- [Error Catalog](ERROR_CATALOG.md) - Error reference and solutions
- [Error Handling](ERROR_HANDLING.md) - Error handling architecture
- [Catalog Examples](../examples/catalog-examples.md) - Real-world catalog examples
- [Getting Started Guide](../getting-started.md) - Quick start overview
