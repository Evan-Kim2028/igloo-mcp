# Igloo MCP Architecture

> **High-level overview** for contributors. For detailed architecture docs, see [docs/architecture/](docs/architecture/).

## System Overview

Igloo MCP is a lightweight MCP server for Snowflake, built on SnowCLI with layered architecture:

```
┌─────────────────────────────────────┐
│   AI Assistants (Cursor, Claude)   │
├─────────────────────────────────────┤
│   MCP Server (igloo-mcp)            │
│   • Query execution                 │
│   • Catalog building                │
│   • Living Reports                  │
├─────────────────────────────────────┤
│   SnowCLI + Snowflake Labs MCP      │
│   • Authentication                  │
│   • Connection management           │
├─────────────────────────────────────┤
│   Snowflake                         │
└─────────────────────────────────────┘
```

## Key Design Decisions

See [Architecture Decision Records](docs/architecture/decisions/) for detailed rationale:

- **[ADR-0001](docs/architecture/decisions/0001-snowcli-integration.md)**: Use SnowCLI profiles (no custom auth)
- **[ADR-0002](docs/architecture/decisions/0002-living-reports-design.md)**: Three-layer reports architecture

## For Contributors

- **System Details**: [docs/architecture/system-overview.md](docs/architecture/system-overview.md)
- **Living Reports**: [docs/architecture/living-reports/](docs/architecture/living-reports/)
- **MCP Server**: [docs/architecture/mcp/](docs/architecture/mcp/)
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)

## For Users

See [docs/](docs/) for user-facing documentation.
