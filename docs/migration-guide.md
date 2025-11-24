# Migration Guide

This guide helps you migrate between different versions of Igloo MCP and from the deprecated CLI interface.

## Table of Contents
- [Migrating to v0.2.4 (Required `reason` Parameter)](#migrating-to-v024-required-reason-parameter)
- [Migrating from CLI to MCP](#migrating-from-cli-to-mcp)

---

## Migrating to v0.2.4 (Required `reason` Parameter)

### Breaking Change
Starting in v0.2.4, the `reason` parameter is **required** for all `execute_query` calls.

### Before (v0.2.3 and earlier)
```python
execute_query(
    statement="SELECT * FROM users LIMIT 10"
)
```

### After (v0.2.4+)
```python
execute_query(
    statement="SELECT * FROM users LIMIT 10",
    reason="Sample user data for debugging"  # Required!
)
```

### Requirements
- **Minimum Length**: 5 characters
- **Purpose**: Auditability - stored in Snowflake QUERY_TAG and local history
- **Examples**:
  - ✅ "Debug null orders in Q3"
  - ✅ "Validate customer count for dashboard"
  - ✅ "Explore sales schema"
  - ❌ "test" (too short - must be at least 5 characters)
  - ❌ "" (empty string not allowed)

### Error Messages
If you forget to add `reason` or make it too short, you'll see a helpful error:

```
❌ Missing required parameter: 'reason'

The 'reason' parameter is required in v0.2.4+ for query auditability.

💡 Quick fix: Add a brief explanation (5+ characters)
   execute_query(
       statement='SELECT * FROM customers LIMIT 10',
       reason='Sample customer data for debugging'  # ← Add this
   )

📝 Examples of good reasons:
   • 'Debug null customer records in Q3'
   • 'Validate revenue totals for dashboard'
   • 'Explore product catalog schema'
```

### Migration Steps
1. Search your codebase for `execute_query` calls
2. Add `reason` parameter (5+ characters) to each call
3. Update any automation/scripts that call execute_query
4. Test with your MCP client to verify errors are clear

### Why This Change?
- **Improved Auditability**: Every query in history logs now has context
- **Better Team Collaboration**: Teammates can understand why queries were run
- **Snowflake Integration**: Reasons appear in Snowflake QUERY_TAG for full traceability
- **LLM Context**: AI agents can better understand and resume query workflows

---

## CLI as Administrative Interface

igloo-mcp includes both MCP tools (primary interface for development) and CLI commands (administrative interface for power users and system administrators). This section clarifies the intended usage of each interface.

### Primary vs Administrative Interfaces

**MCP Tools (Primary - Recommended for Development)**:
- Designed for AI assistant integration
- Structured tool-based interface
- Industry standard Model Context Protocol
- Primary interface for report evolution and data operations

**CLI Commands (Administrative - For Power Users)**:
- Direct command-line access for administrators
- Report creation and management operations
- System setup and configuration tasks
- Available but not the primary development workflow

### CLI Availability Status
- **Current**: CLI available for administrative operations
- **Future**: CLI remains available for admin tasks
- **Note**: CLI is not deprecated - it's repositioned as administrative interface

## Interface Selection Guide

### When to Use MCP Tools (Recommended)
- AI assistant integration
- Report evolution and analysis
- Data exploration and querying
- Development workflows

### When to Use CLI Commands (Administrative)
- Initial report creation setup
- Bulk administrative operations
- System configuration tasks
- Power-user direct access

### Getting Started with Both Interfaces
- [ ] Configure MCP server for primary development work
- [ ] Test MCP tools in your AI assistant
- [ ] Use CLI for administrative setup when needed
- [ ] Review administrative operations documentation

## Interface Mapping

| Administrative CLI | Primary MCP Tools | Usage Context |
|-------------------|-------------------|---------------|
| `igloo report create` | `evolve_report` (with new report) | Report initialization |
| `igloo report list` | N/A - use MCP for active work | Administrative listing |
| `igloo report show` | N/A - use MCP for analysis | Administrative inspection |
| N/A | `execute_query` | Data exploration and querying |
| N/A | `build_catalog` | Metadata operations |
| N/A | `search_catalog` | Data discovery |
| N/A | `evolve_report` | Report evolution and updates |
| `igloo-mcp` | MCP server startup | Server management |

## Migration Examples

### Before (CLI - Deprecated)
```bash
# Test connection
igloo-mcp --profile prod verify

# Build catalog
igloo-mcp --profile prod catalog -d MY_DATABASE -o ./output

# Query lineage
igloo-mcp --profile prod lineage MY_TABLE

# Execute query
igloo-mcp --profile prod query "SELECT * FROM users LIMIT 10"
```

### After (MCP)
```json
{
  "tool": "test_connection",
  "arguments": {
    "profile": "prod"
  }
}

{
  "tool": "build_catalog",
  "arguments": {
    "database": "MY_DATABASE",
    "output_dir": "./output"
  }
}

{
  "tool": "query_lineage",
  "arguments": {
    "object_name": "MY_TABLE"
  }
}

{
  "tool": "execute_query",
  "arguments": {
    "statement": "SELECT * FROM users LIMIT 10"
  }
}
```

## MCP Server Setup

### 1. Start MCP Server
```bash
# Set profile environment variable
export SNOWFLAKE_PROFILE=my-profile

# Start MCP server
igloo-mcp
```

### 2. Configure AI Assistant
Add to your AI assistant configuration:

```json
{
  "mcpServers": {
    "snowflake": {
      "command": "igloo-mcp",
      "args": ["--profile", "my-profile"]
    }
  }
}
```

### 3. Test MCP Integration
```bash
# Test connection via MCP
echo '{"tool": "test_connection", "arguments": {}}' | igloo-mcp

# Expected: JSON response with connection status
```

## Automation Migration

### Scripts Using CLI
**Before**:
```bash
#!/bin/bash
# Old script using CLI (deprecated)
igloo-mcp --profile prod catalog -d MY_DB
igloo-mcp --profile prod lineage MY_TABLE
```

**After**:
```bash
#!/bin/bash
# New script using MCP
export SNOWFLAKE_PROFILE=prod

# Start MCP server in background
igloo-mcp &
MCP_PID=$!

# Send MCP requests
echo '{"tool": "build_catalog", "arguments": {"database": "MY_DB"}}' | nc localhost 8080
echo '{"tool": "query_lineage", "arguments": {"object_name": "MY_TABLE"}}' | nc localhost 8080

# Cleanup
kill $MCP_PID
```

### CI/CD Pipeline Updates
**Before**:
```yaml
# GitHub Actions using CLI (deprecated)
- name: Build Catalog
  run: igloo-mcp --profile prod catalog -d MY_DB
```

**After**:
```yaml
# GitHub Actions using MCP
- name: Build Catalog
  run: |
    export SNOWFLAKE_PROFILE=prod
    echo '{"tool": "build_catalog", "arguments": {"database": "MY_DB"}}' | igloo-mcp
```

## Troubleshooting

### Common Migration Issues

#### MCP Server Won't Start
**Error**: `MCP server failed to start`
**Solution**:
- Check profile configuration: `snow connection list`
- Verify environment variables: `echo $SNOWFLAKE_PROFILE`
- Test basic connection: `igloo-mcp --profile my-profile verify`

#### Tool Not Found
**Error**: `Tool 'execute_query' not found`
**Solution**:
- Ensure MCP server is running
- Check tool name spelling
- Verify MCP protocol version

#### Authentication Issues
**Error**: `Authentication failed`
**Solution**:
- Use same profile as CLI
- Check key permissions
- Verify Snowflake credentials

### Getting Help

- 📖 [MCP Integration Guide](mcp-integration.md) - Complete MCP setup
- 🔧 [Configuration Guide](configuration.md) - Advanced settings
- 🐛 [Error Catalog](api/ERROR_CATALOG.md) - Common issues and solutions
- 💬 [GitHub Discussions](https://github.com/Evan-Kim2028/igloo-mcp/discussions) - Community help

## Legacy CLI Support

### If You Still Need CLI
The CLI has been completely removed in igloo-mcp v2.0.0 (package rebrand). For legacy CLI support, use the previous package:

```bash
# Install legacy snowcli-tools package (v1.x)
pip install "snowcli-tools>=1.9.0,<2.0.0"
```

### Legacy snowcli-tools Limitations
- Security fixes only
- No new features
- Limited support through December 2025
- Replaced by igloo-mcp (current version: 0.3.0+)

## Success Metrics

After migration, you should have:
- ✅ MCP server running successfully
- ✅ All CLI functionality available via MCP
- ✅ AI assistant integration working
- ✅ Automation scripts updated
- ✅ No CLI dependencies in new code

## Next Steps

1. **Complete Migration**: Follow this guide step by step
2. **Test Thoroughly**: Verify all functionality works via MCP
3. **Update Documentation**: Update internal docs to reference MCP
4. **Train Team**: Share MCP knowledge with your team
5. **Monitor**: Watch for new MCP features and improvements

---

*Need help with migration? Check the [Error Catalog](api/ERROR_CATALOG.md) or [GitHub Discussions](https://github.com/Evan-Kim2028/igloo-mcp/discussions).*
