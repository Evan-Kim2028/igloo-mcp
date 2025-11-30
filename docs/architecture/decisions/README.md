# Architecture Decision Records (ADRs)

This directory contains records of significant architectural decisions made in the Igloo MCP project.

## Active ADRs

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-snowcli-integration.md) | SnowCLI Integration | Accepted | 2025-11 |
| [0002](0002-living-reports-design.md) | Living Reports Design v0.3.0 | Accepted | 2025-11 |

## What is an ADR?

An ADR captures a single significant decision regarding the software architecture, including:
- **Context**: The issue motivating this decision
- **Decision**: The choice made
- **Consequences**: Results of the decision (positive and negative)

## When to write an ADR

Create an ADR for decisions that:
- Affect the system's structure or core behavior
- Are expensive to change later
- Impact multiple components
- Need justification for future maintainers

Examples: Choice of database, communication protocol, data format, security model.

## Using the template

1. Copy [template.md](template.md) to `XXXX-your-decision.md`
2. Fill in the sections (don't assign number yet)
3. Submit PR for review
4. Assign number sequentially when merged
5. Update this index
