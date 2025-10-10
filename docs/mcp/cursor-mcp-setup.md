# Cursor MCP Setup Guide

This guide shows you how to set up igloo-mcp with Cursor for Snowflake data operations.

## Prerequisites

- Cursor installed
- Python 3.12+ with `uv` package manager
- Snowflake account with appropriate permissions
- igloo-mcp installed (see [Installation Guide](getting-started.md#step-1-install-igloo-mcp))

## Step 1: Create Snowflake Profile

First, create a Snowflake profile using the Snowflake CLI:

```bash
# Create a profile with password authentication
snow connection add \
  --connection-name "cursor-profile" \
  --account "<your-account>.<region>" \
  --user "<your-username>" \
  --password \
  --warehouse "<your-warehouse>"

# Enter password when prompted
```

**Finding your account identifier**:
- Your Snowflake URL: `https://abc12345.us-east-1.snowflakecomputing.com`
- Your account identifier: `abc12345.us-east-1` (remove `.snowflakecomputing.com`)

## Step 2: Configure Cursor MCP

Edit your Cursor MCP configuration file at `~/.cursor/mcp.json`:

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

**Important**: Replace `/path/to/igloo-mcp` with the actual path to your igloo-mcp installation directory.

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
| `preview_table` | Preview table contents | "Preview the users table with 5 rows" |
| `build_catalog` | Build database catalog | "Build a catalog for MY_DATABASE" |
| `get_catalog_summary` | Get catalog statistics | "Show me catalog summary for MY_DATABASE" |
| `build_dependency_graph` | Build dependency graph | "Build dependency graph for MY_DATABASE" |
| `health_check` | Check system health | "Check igloo-mcp health" |

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
      "env": {"SNOWFLAKE_PROFILE": "dev"}
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
      "env": {"SNOWFLAKE_PROFILE": "prod"}
    }
  }
}
```

### Key-Pair Authentication

For production environments, use key-pair authentication:

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
