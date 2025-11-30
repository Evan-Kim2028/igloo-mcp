# Architecture Documentation

Developer and contributor documentation for Igloo MCP internals.

**Audience**: Contributors, maintainers, architects
**For users**: See [docs/](../)

## Quick Links
- [System Overview](system-overview.md) - High-level architecture
- [Architecture Decisions](decisions/) - ADRs tracking key design choices

## Architecture Decision Records (ADRs)

- [ADR-0001: SnowCLI Integration](decisions/0001-snowcli-integration.md)
- [ADR-0002: Living Reports Design v0.3.0](decisions/0002-living-reports-design.md)

## Subsystem Documentation

### Living Reports
- [Design v0.3.0](living-reports/design-v030.md) - Technical implementation

### MCP Server
- [Protocol Architecture](mcp/protocol-architecture.md) - MCP protocol details
- [Server Implementation](mcp/server-implementation.md) - Implementation guide

## Contributing

When making significant architectural changes:
1. Create an ADR using the [template](decisions/template.md)
2. Number sequentially (0003, 0004, etc.)
3. Submit for review via PR
4. Update this index

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for full guidelines.
