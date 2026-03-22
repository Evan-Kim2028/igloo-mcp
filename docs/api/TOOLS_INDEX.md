# MCP Tools Quick Reference

> **Quick Links**: [Complete API Reference](README.md) | [Error Catalog](ERROR_CATALOG.md) | [Error Handling](ERROR_HANDLING.md)

## Overview

Igloo MCP provides **16 focused tools** organized by workflow. Each workflow shows how tools work together to accomplish common tasks.

## Workflows

### 🔍 Data Discovery Workflow

Explore your Snowflake environment, query safely, and build offline catalogs for fast searches.

1. **[test_connection](tools/test_connection.md)** — Verify Snowflake authentication and profile setup
2. **[execute_query](tools/execute_query.md)** — Run safe SQL with guardrails, timeouts, and auto-insights
   - Use `response_mode` parameter for significant token reduction
   - Automatically blocks DDL/DML operations
3. **[build_catalog](tools/build_catalog.md)** — Export metadata (tables, views, columns) to offline catalog
4. **[search_catalog](tools/search_catalog.md)** — Find objects by name/column without querying Snowflake
5. **[build_dependency_graph](tools/build_dependency_graph.md)** — Visualize table lineage and dependencies

**Common pattern**: test_connection → execute_query (explore data) → build_catalog → search_catalog (fast offline lookups)

### 📊 Analytics & Reporting Workflow

Create auditable business reports that evolve with LLM assistance and full change history.

1. **[create_report](tools/create_report.md)** — Initialize new structured reports with optional templates
2. **[search_report](tools/search_report.md)** — Find existing reports by title or tags
   - Use `fields` parameter for selective retrieval
3. **[get_report](tools/get_report.md)** — Read reports with progressive disclosure
   - Modes: summary (metadata only), sections, insights, or full
4. **[get_report_schema](tools/get_report_schema.md)** — Discover valid report structures before evolving
5. **[evolve_report](tools/evolve_report.md)** — Modify reports safely with validation and audit logging
   - Use `response_detail="minimal"` for token efficiency
6. **[evolve_report_batch](tools/evolve_report_batch.md)** — Atomic multi-operation report evolution
7. **[render_report](tools/render_report.md)** — Export to HTML, PDF, Markdown, or DOCX via Quarto

**Common pattern**: search_report → get_report (summary mode) → get_report_schema → evolve_report (minimal response) → render_report

**Token Efficiency**: Minimize token usage using progressive disclosure and selective retrieval.

### 🏥 Monitoring Workflow

Check system health, validate configuration, and monitor catalog status.

1. **[health_check](tools/health_check.md)** — Comprehensive server, profile, and catalog health status
2. **[test_connection](tools/test_connection.md)** — Validate Snowflake connectivity
3. **[get_catalog_summary](tools/get_catalog_summary.md)** — Get catalog statistics and metadata health

**Common pattern**: health_check (overall status) → test_connection (if issues) → get_catalog_summary (catalog health)

## Quick Reference Table

| Tool | Workflow | Key Use | Documentation |
|------|----------|---------|---------------|
| `test_connection` | Discovery, Monitoring | Validate auth | [Details](tools/test_connection.md) |
| `execute_query` | Discovery | Safe SQL execution | [Details](tools/execute_query.md) |
| `build_catalog` | Discovery | Export metadata | [Details](tools/build_catalog.md) |
| `search_catalog` | Discovery | Offline object search | [Details](tools/search_catalog.md) |
| `build_dependency_graph` | Discovery | Lineage visualization | [Details](tools/build_dependency_graph.md) |
| `create_report` | Analytics | Initialize reports | [Details](tools/create_report.md) |
| `search_report` | Analytics | Find reports | [Details](tools/search_report.md) |
| `get_report` | Analytics | Read reports | [Details](tools/get_report.md) |
| `get_report_schema` | Analytics | Discover structures | [Details](tools/get_report_schema.md) |
| `evolve_report` | Analytics | Modify reports | [Details](tools/evolve_report.md) |
| `evolve_report_batch` | Analytics | Batch operations | [Details](tools/evolve_report_batch.md) |
| `render_report` | Analytics | Export formats | [Details](tools/render_report.md) |
| `validate_report` | Analytics | Quality checks | [Details](tools/validate_report.md) |
| `search_citations` | Analytics | Citation search | [Details](tools/search_citations.md) |
| `health_check` | Monitoring | System health | [Details](tools/health_check.md) |
| `get_catalog_summary` | Monitoring | Catalog stats | [Details](tools/get_catalog_summary.md) |

## See Also

- [Complete API Reference](README.md) - Full API documentation with examples
- [Error Catalog](ERROR_CATALOG.md) - Error reference and solutions
- [Error Handling](ERROR_HANDLING.md) - Error handling architecture
- [Catalog Examples](../examples/catalog-examples.md) - Real-world catalog examples
- [Getting Started Guide](../getting-started.md) - Quick start overview
- [Living Reports User Guide](../living-reports/user-guide.md) - Complete reporting workflows
