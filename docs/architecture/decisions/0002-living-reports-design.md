# ADR-0002: Living Reports Design v0.3.0

**Status**: Accepted
**Date**: 2025-11-23
**Deciders**: Core team
**Technical Story**: Living Reports feature implementation

## Context

Need auditable business reports that:
- Evolve safely with LLM assistance
- Preserve full change history
- Work offline-first
- Never lose data
- Prevent LLM hallucinations

Options considered:
1. Database-backed reports
2. Markdown files with git history
3. JSON-backed with audit logs

## Decision

Implement three-layer architecture:
- **Layer 3 (Presentation)**: Quarto QMD rendered to HTML/PDF
- **Layer 2 (Machine Truth)**: outline.json with structured data
- **Layer 1 (Immutable Memory)**: audit.jsonl + backups

**Key Design Choices**:
- UUID-based storage (rename immunity)
- File-based locking (portalocker)
- Atomic writes (temp + fsync + rename)
- LLM produces only structured patches (no free-writing)

## Consequences

**Positive**:
- Complete audit trail (who, when, what, why)
- LLM-safe (validation before apply)
- Offline-first (no database dependency)
- Revertible (audit log replay)
- Cross-platform (tested on Mac/Linux/Windows)

**Negative**:
- Filesystem locking complexity
- No real-time multi-user collaboration
- Quarto dependency for rendering

**Neutral**:
- Reports stored in ~/.igloo_mcp/reports/ (unified storage)

## References

- [Technical Design](../living-reports/design-v030.md) - Full implementation details
- [User Guide](../../living-reports/user-guide.md) - User-facing documentation
