# MCP Integration Guide

Nanuk MCP provides MCP (Model Context Protocol) integration for AI assistants, enabling natural language interaction with your Snowflake data.

## Quick Start

1. **Install Nanuk MCP**:
   ```bash
   pip install igloo-mcp-mcp
   ```

2. **Start the MCP server**:
   ```bash
   SNOWFLAKE_PROFILE=my-profile igloo-mcp-mcp
   ```

3. **Configure your AI assistant** using the examples below.

## AI Assistant Configuration

### Claude Code

**Configuration file**: `~/.config/claude-code/mcp.json`

```json
{
  "mcpServers": {
    "igloo-mcp-mcp": {
      "command": "igloo-mcp-mcp",
      "args": ["--profile", "my-profile"],
      "env": {}
    }
  }
}
```

**Alternative with environment variable**:
```json
{
  "mcpServers": {
    "igloo-mcp-mcp": {
      "command": "igloo-mcp-mcp",
      "env": {
        "SNOWFLAKE_PROFILE": "my-profile"
      }
    }
  }
}
```

**Usage**: Ask Claude Code questions like:
- "What tables are in my database?"
- "Show me the schema for the ORDERS table"
- "What's the lineage for CUSTOMER_ORDERS?"
- "Generate a data quality report for MY_TABLE"

### VS Code with MCP Extension

**Configuration file**: `~/.vscode/mcp.json`

```json
{
  "mcpServers": {
    "igloo-mcp-mcp": {
      "command": "igloo-mcp-mcp",
      "args": ["--profile", "my-profile"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

**Installation**:
1. Install the MCP extension for VS Code
2. Add the configuration above
3. Restart VS Code
4. Use the MCP panel to interact with Snowflake

### Cursor IDE

**Configuration file**: `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "igloo-mcp-mcp": {
      "command": "igloo-mcp-mcp",
      "args": ["--profile", "my-profile"]
    }
  }
}
```

**Usage**: Use Cursor's AI features to:
- Query your Snowflake data
- Analyze table schemas
- Generate SQL queries
- Explore data lineage

### Generic MCP Client

**Configuration template**:
```json
{
  "mcpServers": {
    "igloo-mcp-mcp": {
      "command": "igloo-mcp-mcp",
      "args": ["--profile", "your-profile-name"]
    }
  }
}
```

**Or with environment variable**:
```json
{
  "mcpServers": {
    "igloo-mcp-mcp": {
      "command": "igloo-mcp-mcp",
      "env": {
        "SNOWFLAKE_PROFILE": "your-profile-name"
      }
    }
  }
}
```

## Available MCP Tools

Nanuk MCP provides these MCP tools for AI assistants:

| Tool | Purpose | Example Use |
|------|---------|-------------|
| `execute_query` | Run SQL queries | "Show me the top 10 customers by revenue" |
| `preview_table` | Preview table data | "What does the ORDERS table look like?" |
| `build_catalog` | Build data catalog | "Catalog all tables in my database" |
| `query_lineage` | Analyze data lineage | "What tables depend on CUSTOMERS?" |
| `build_dependency_graph` | Create dependency graphs | "Show me the data flow diagram" |
| `get_catalog_summary` | Get catalog statistics | "How many tables do I have?" |
| `test_connection` | Test Snowflake connection | "Is my Snowflake connection working?" |
| `health_check` | Check system health | "Is everything running properly?" |

## Troubleshooting

### Server Won't Start
```bash
# Check if profile exists
snow connection list

# Test profile manually with Snowflake CLI
snow sql -q "SELECT CURRENT_USER()" --connection my-profile

# Check permissions
ls -la ~/.snowflake/config.toml
```

### AI Assistant Can't Connect
1. **Verify MCP server is running**:
   ```bash
   SNOWFLAKE_PROFILE=my-profile igloo-mcp-mcp
   # Should show "FastMCP 2.0 Server Starting..."
   ```

2. **Check configuration file**:
   - Ensure correct path to `igloo-mcp`
   - Verify profile name matches
   - Check file permissions

3. **Test with simple query**:
   ```bash
   echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | SNOWFLAKE_PROFILE=my-profile igloo-mcp-mcp
   ```

### Common Errors

**"Profile not found"**:
- Check profile exists: `snow connection list`
- Verify profile name spelling
- Ensure profile is properly configured

**"Permission denied"**:
- Check key file permissions: `chmod 400 rsa_key.p8`
- Verify Snowflake user has required permissions

**"JWT token invalid"**:
- Re-upload public key to Snowflake
- Ensure no line breaks in public key
- Verify key format is correct

## Advanced Configuration

### Multiple Profiles
```json
{
  "mcpServers": {
    "igloo-mcp-mcp-prod": {
      "command": "igloo-mcp-mcp",
      "args": ["--profile", "prod-profile"]
    },
    "igloo-mcp-mcp-dev": {
      "command": "igloo-mcp-mcp",
      "args": ["--profile", "dev-profile"]
    }
  }
}
```

### Custom Catalog Directory
```json
{
  "mcpServers": {
    "igloo-mcp-mcp": {
      "command": "igloo-mcp-mcp",
      "args": ["--profile", "my-profile"],
      "env": {
        "SNOWCLI_CATALOG_DIR": "/path/to/custom/catalog"
      }
    }
  }
}
```

## For More Details

- [MCP Server User Guide](mcp/mcp_server_user_guide.md) - Complete setup guide
- [MCP Server Technical Guide](mcp/mcp_server_technical_guide.md) - Architecture details
- [MCP Architecture](mcp/mcp_architecture.md) - Design patterns
