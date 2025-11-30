# Contributing to Igloo MCP

Thank you for your interest in contributing to Igloo MCP!

## Documentation Structure

### User Documentation (`docs/`)
User-facing guides for installing and using Igloo MCP.

**Do NOT put** implementation details, design decisions, or internal architecture here.

### Architecture Documentation (`docs/architecture/`)
Developer and contributor documentation:
- **ADRs** (`decisions/`) - Architecture decisions with context
- **Technical Designs** - Deep dives into subsystems
- **Implementation Guides** - How components work internally

### When to Write an ADR

Create an ADR for decisions that:
- Affect system structure or core behavior
- Are expensive to change later
- Impact multiple components
- Need justification for future maintainers

Examples: Database choice, protocol selection, data format, security model.

**Process**:
1. Copy `docs/architecture/decisions/template.md`
2. Fill in Context, Decision, Consequences
3. Submit PR for review
4. Number sequentially when merged (ask maintainer)
5. Update `docs/architecture/decisions/README.md`

See [Architecture Documentation Guide](docs/architecture/README.md) for full details.

## Development Setup

// ... existing code ...
