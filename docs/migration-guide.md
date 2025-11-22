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

## Migrating from CLI to MCP

This section helps you migrate from the deprecated CLI interface to the modern MCP (Model Context Protocol) interface.

### Why Migrate?

### Benefits of MCP
- **AI-First Design**: Built for AI assistant integration
- **Modern Protocol**: Industry standard for tool integration
- **Better Error Handling**: Structured error responses
- **Future-Proof**: Aligns with emerging AI tool standards
- **Reduced Maintenance**: Single interface to maintain

### CLI Deprecation Timeline
- **v1.9.0**: Deprecation warnings added
- **v2.0.0**: CLI completely removed - MCP-only architecture (Current)

## Migration Checklist

- [ ] Review current CLI usage
- [ ] Install MCP dependencies (included by default)
- [ ] Configure MCP server
- [ ] Test MCP tools
- [ ] Update scripts/automation
- [ ] Remove CLI from workflow

## Command Mapping

| CLI Command | MCP Equivalent | Notes |
|-------------|----------------|-------|
| `nanuk verify` | `test_connection` tool | Connection testing |
| `nanuk catalog -d DB` | `build_catalog` tool | Database cataloging |
| `nanuk lineage TABLE` | `query_lineage` tool | Lineage analysis |
| `nanuk depgraph -d DB` | `build_dependency_graph` tool | Dependency mapping |
| `nanuk query "SQL"` | `execute_query` tool | SQL execution |
| `nanuk-mcp` | MCP server startup | Server management |

## Migration Examples

### Before (CLI)
```bash
# Test connection
nanuk --profile prod verify

# Build catalog
nanuk --profile prod catalog -d MY_DATABASE -o ./output

# Query lineage
nanuk --profile prod lineage MY_TABLE

# Execute query
nanuk --profile prod query "SELECT * FROM users LIMIT 10"
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
nanuk-mcp
```

### 2. Configure AI Assistant
Add to your AI assistant configuration:

```json
{
  "mcpServers": {
    "snowflake": {
      "command": "nanuk-mcp",
      "args": ["--profile", "my-profile"]
    }
  }
}
```

### 3. Test MCP Integration
```bash
# Test connection via MCP
echo '{"tool": "test_connection", "arguments": {}}' | nanuk-mcp

# Expected: JSON response with connection status
```

## Automation Migration

### Scripts Using CLI
**Before**:
```bash
#!/bin/bash
# Old script using CLI
nanuk --profile prod catalog -d MY_DB
nanuk --profile prod lineage MY_TABLE
```

**After**:
```bash
#!/bin/bash
# New script using MCP
export SNOWFLAKE_PROFILE=prod

# Start MCP server in background
nanuk-mcp &
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
# GitHub Actions using CLI
- name: Build Catalog
  run: nanuk --profile prod catalog -d MY_DB
```

**After**:
```yaml
# GitHub Actions using MCP
- name: Build Catalog
  run: |
    export SNOWFLAKE_PROFILE=prod
    echo '{"tool": "build_catalog", "arguments": {"database": "MY_DB"}}' | nanuk-mcp
```

## Troubleshooting

### Common Migration Issues

#### MCP Server Won't Start
**Error**: `MCP server failed to start`
**Solution**:
- Check profile configuration: `snow connection list`
- Verify environment variables: `echo $SNOWFLAKE_PROFILE`
- Test basic connection: `nanuk --profile my-profile verify`

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
- 🐛 [Error Catalog](api/errors.md) - Common issues and solutions
- 💬 [GitHub Discussions](https://github.com/Evan-Kim2028/nanuk-mcp/discussions) - Community help

## Legacy CLI Support

### If You Still Need CLI
The CLI has been completely removed in v2.0.0. For legacy CLI support, use the previous package:

```bash
# Install legacy snowcli-tools package (v1.x)
pip install "snowcli-tools>=1.9.0,<2.0.0"
```

### Legacy snowcli-tools Limitations
- Security fixes only
- No new features
- Limited support through December 2025
- Replaced by nanuk-mcp v2.0.0+

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

*Need help with migration? Check the [Error Catalog](api/errors.md) or [GitHub Discussions](https://github.com/Evan-Kim2028/nanuk-mcp/discussions).*
