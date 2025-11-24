# Cursor MCP Setup Guide

This guide shows you how to set up igloo-mcp with Cursor for Snowflake data operations.

## Prerequisites

- Cursor installed
- Python 3.12+ with `uv` package manager
- Snowflake account with appropriate permissions
- igloo-mcp installed (see [Installation Guide](getting-started.md#step-1-install-igloo-mcp))

## Step 1: Create Snowflake Profile

First, create a Snowflake profile using the Snowflake CLI. Recommended: SSO (Okta) via external browser.

```bash
# Create a profile with SSO (Okta) via external browser
snow connection add \
  --connection-name "cursor-profile" \
  --account "<your-account>.<region>" \
  --user "<your-username>" \
  --authenticator externalbrowser \
  --warehouse "<your-warehouse>"

# A browser window opens to your Snowflake/Okta login
```

Notes:
- If your org requires an explicit Okta URL, use: `--authenticator https://<your_okta_domain>.okta.com`
- If your org doesn’t use SSO, you can use `--password` instead

**Finding your account identifier**:
- Your Snowflake URL: `https://abc12345.us-east-1.snowflakecomputing.com`
- Your account identifier: `abc12345.us-east-1` (remove `.snowflakecomputing.com`)

## Step 2: Configure Cursor MCP

Edit your Cursor MCP configuration file at `~/.cursor/mcp.json`:

**Minimal Configuration** (uses defaults):
```json
{
  "mcpServers": {
    "igloo-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/igloo-mcp",
        "run",
        "igloo-mcp",
        "--profile",
        "cursor-profile"
      ],
      "env": {
        "SNOWFLAKE_PROFILE": "cursor-profile"
      }
    }
  }
}
```

**Full Configuration** (with custom paths - all optional):
```json
{
  "mcpServers": {
    "igloo-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/igloo-mcp",
        "run",
        "igloo-mcp",
        "--profile",
        "cursor-profile"
      ],
      "env": {
        "SNOWFLAKE_PROFILE": "cursor-profile",
        "IGLOO_MCP_QUERY_HISTORY": "~/.igloo-mcp/logs/query_history.jsonl",
        "IGLOO_MCP_ARTIFACT_ROOT": "~/.igloo-mcp/artifacts",
        "IGLOO_MCP_REPORTS_ROOT": "~/.igloo-mcp/reports"
      }
    }
  }
}
```

**Important**:
- Replace `/path/to/igloo-mcp` with the actual path to your igloo-mcp installation directory
- **All environment variables except `SNOWFLAKE_PROFILE` are optional** - igloo-mcp provides sensible defaults
- If you omit the history/artifact/report paths, they default to `~/.igloo-mcp/logs/...` (global scope) or `<repo>/logs/...` (repo scope)
- Each MCP server instance maintains separate storage to avoid conflicts. Reports, query history, and artifacts are all stored together in the instance-specific directory

## Step 3: Restart Cursor

After configuring MCP, restart Cursor completely to load the new configuration.

## Step 4: Test the Connection

In Cursor, try these prompts to test your setup:

```
"Test my Snowflake connection"
```

Expected response: Connection status and profile information

```
"Show me my Snowflake databases"
```

Expected response: List of databases you have access to

```
"Execute: SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES"
```

Expected response: Query results with row count

## Available MCP Tools

Once connected, you can use these MCP tools through Cursor:

| Tool | Description | Example Prompt |
|------|-------------|----------------|
| `test_connection` | Test Snowflake connection | "Test my Snowflake connection" |
| `execute_query` | Execute SQL queries | "Execute: SELECT * FROM my_table LIMIT 10" |
| `build_catalog` | Build database catalog | "Build a catalog for MY_DATABASE" |
| `get_catalog_summary` | Get catalog statistics | "Show me catalog summary for MY_DATABASE" |
| `search_catalog` | Search catalog snapshots | "Find tables with a column named user_id" |
| `build_dependency_graph` | Build dependency graph | "Build dependency graph for MY_DATABASE" |
| `health_check` | Check system health | "Check igloo-mcp health" |
| `evolve_report` | Evolve living reports | "Evolve the Q1 sales report with new insights" |
| `render_report` | Render reports | "Render the Q1 sales report as HTML" |

## Troubleshooting

### "MCP tools not showing up"

**Solution**:
1. Verify igloo-mcp is installed: `which igloo-mcp`
2. Check MCP config JSON syntax is valid
3. **Restart Cursor completely**
4. Check Cursor logs for errors
5. Ensure the path to igloo-mcp is correct

### "Connection failed"

**Solution**:
- Verify account format: `org-account.region` (not `https://...`)
- Check username/password are correct
- Ensure warehouse exists and you have access
- Test profile: `snow sql -q "SELECT 1" --connection cursor-profile`

### "Permission denied"

**Solution**:
- Ensure you have `USAGE` on warehouse
- Check database/schema access: `SHOW GRANTS TO USER <your_username>`
- Contact your Snowflake admin for permissions

## Advanced Configuration

### Multiple Profiles

You can configure multiple Snowflake profiles for different environments:

```json
{
  "mcpServers": {
    "igloo-dev": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/igloo-mcp",
        "run",
        "igloo-mcp",
        "--profile",
        "dev"
      ],
      "env": {
        "SNOWFLAKE_PROFILE": "dev",
        "IGLOO_MCP_QUERY_HISTORY": "~/.igloo-mcp-dev/logs/query_history.jsonl",
        "IGLOO_MCP_ARTIFACT_ROOT": "~/.igloo-mcp-dev/artifacts",
        "IGLOO_MCP_REPORTS_ROOT": "~/.igloo-mcp-dev/reports"
      }
    },
    "igloo-prod": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/igloo-mcp",
        "run",
        "igloo-mcp",
        "--profile",
        "prod"
      ],
      "env": {
        "SNOWFLAKE_PROFILE": "prod",
        "IGLOO_MCP_QUERY_HISTORY": "~/.igloo-mcp-prod/logs/query_history.jsonl",
        "IGLOO_MCP_ARTIFACT_ROOT": "~/.igloo-mcp-prod/artifacts",
        "IGLOO_MCP_REPORTS_ROOT": "~/.igloo-mcp-prod/reports"
      }
    }
  }
}
```

**Note**: The history/artifact/report paths shown above are **optional**. They're included here to demonstrate instance isolation (separate storage per profile). If omitted, igloo-mcp uses defaults: `~/.igloo-mcp/logs/...` for global scope or `<repo>/logs/...` for repo scope.

### Key-Pair Authentication (advanced)

Use RSA key‑pair auth when required by policy or for headless automation:

1. **Generate keys**:
```bash
mkdir -p ~/.snowflake
openssl genrsa -out ~/.snowflake/key.pem 2048
openssl rsa -in ~/.snowflake/key.pem -pubout -out ~/.snowflake/key.pub
chmod 400 ~/.snowflake/key.pem
```

2. **Upload public key to Snowflake**:
```bash
# Format key for Snowflake
cat ~/.snowflake/key.pub | grep -v "BEGIN\|END" | tr -d '\n'

# In Snowflake, run:
ALTER USER <your_username> SET RSA_PUBLIC_KEY='<paste_key_here>';
```

3. **Update your profile**:
```bash
snow connection add \
  --connection-name "cursor-profile" \
  --account "mycompany-prod.us-east-1" \
  --user "your-username" \
  --private-key-file "~/.snowflake/key.pem" \
  --warehouse "COMPUTE_WH"
```

## Next Steps

- 📖 [Getting Started Guide](getting-started.md) - Complete setup instructions
- 🔧 [MCP Tools Reference](mcp/tools-reference.md) - Detailed tool documentation
- 🐛 [Troubleshooting Guide](troubleshooting.md) - Common issues and solutions

---

**Need help?** Check our [GitHub Discussions](https://github.com/Evan-Kim2028/igloo-mcp/discussions) for community support.
