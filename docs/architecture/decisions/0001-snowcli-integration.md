# ADR-0001: SnowCLI Integration

**Status**: Accepted
**Date**: 2025-11
**Deciders**: Core team
**Technical Story**: Foundation architecture decision

## Context

Need to integrate with Snowflake for MCP tools. Options:
1. Use Snowflake Python Connector directly
2. Use SnowCLI profiles and bundled connector
3. Build custom authentication layer

Requirements:
- Support multiple auth methods (SSO, key-pair, OAuth)
- No credential storage in MCP
- Simple user setup
- Leverage existing Snowflake tooling

## Decision

Use SnowCLI profiles and bundled Snowflake Labs MCP connector.

**Rationale**:
- Users already have `snow` CLI configured
- No credential duplication
- Auto-updates with SnowCLI
- Proven auth flows
- Minimal setup friction

## Consequences

**Positive**:
- Simple setup: "Just use your snow profile"
- No credential management burden
- All SnowCLI auth methods work
- Consistent with Snowflake ecosystem

**Negative**:
- Dependency on SnowCLI package
- Users must install SnowCLI (bundled)
- Tied to SnowCLI profile format

**Neutral**:
- Profile selection via --profile flag or SNOWFLAKE_PROFILE env var

## References

- [Installation Guide](../../installation.md)
- [Authentication Guide](../../authentication.md)
