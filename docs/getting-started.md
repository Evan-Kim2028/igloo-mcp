# Getting Started with igloo-mcp

> **Quick Start**: Set up your Snowflake profile → Install igloo-mcp → Start using with your AI assistant

## How It Works
- Your LLM calls MCP tools (execute_query, preview_table, build_catalog, etc.) exposed by igloo-mcp.
- igloo-mcp uses your Snowflake CLI profile for authentication and session context.
- Built-in guardrails block write and DDL SQL (INSERT/UPDATE/CREATE/ALTER/DELETE/DROP/TRUNCATE); timeouts and best‑effort cancellation keep runs responsive.
- Optional JSONL query history records success/timeout/error with minimal fields for auditing.
- Configure your editor (Cursor or Claude Code) to launch igloo-mcp with your Snowflake profile.

## Prerequisites

**Required**:
1. **Python 3.12+** with `uv` or pip package manager
   - Check: `python --version`
   - Install: https://www.python.org/downloads/

2. **Snowflake CLI** (Official package - bundled with igloo-mcp)
   - Expect: `snow --version` works after installing igloo-mcp
   - Docs: https://docs.snowflake.com/en/developer-guide/snowflake-cli/
   - Purpose: Manages Snowflake authentication profiles only

3. **Snowflake account** with appropriate permissions
   - Need: USAGE on warehouse/database/schema
   - Need: SELECT on INFORMATION_SCHEMA
   - Contact your Snowflake admin if unsure

4. **AI Assistant** that supports MCP (e.g., Claude Code, Cline, etc.)

## Step 1: Install igloo-mcp

### Installation Methods

**Option 1: PyPI Installation (Recommended for most users)**
```bash
uv pip install igloo-mcp
```

**Option 2: Development Installation (For contributors)**
```bash
# Clone and install the project
git clone https://github.com/Evan-Kim2028/igloo-mcp
cd igloo-mcp

# Install with uv (recommended)
uv sync
```

## Step 2: Set Up Your Snowflake Profile

**Critical**: igloo-mcp uses Snowflake CLI profiles for authentication.

### Snowflake Parameters

Before creating your profile, gather these Snowflake parameters:

| Parameter | Required | Description | How to Find | Example |
|-----------|----------|-------------|-------------|---------|
| **Account Identifier** | Yes | Your Snowflake account location | Snowflake URL (remove `.snowflakecomputing.com`) | `abc12345.us-east-1` |
| **Username** | Yes | Your Snowflake username | From your Snowflake admin or login | `alex.chen` |
| **Authentication** | Yes | SSO (Okta via browser), password, or key‑pair | See examples below | `externalbrowser` |
| **Warehouse** | Recommended | Compute cluster for queries | Snowflake UI → Admin → Warehouses | `COMPUTE_WH` |
| **Database** | Optional | Default database | Snowflake UI → Data → Databases | `MY_DB` |
| **Schema** | Optional | Default schema | Inside database view | `PUBLIC` |

**Finding Your Account Identifier**:
- Your Snowflake URL: `https://abc12345.us-east-1.snowflakecomputing.com`
- Your account identifier: `abc12345.us-east-1` (the part before `.snowflakecomputing.com`)
- Format: `<orgname>-<account>.<region>` or `<account>.<region>` (for older accounts)

**Finding Your Warehouse**:
- Trial accounts: Usually `COMPUTE_WH` (default warehouse)
- Enterprise: Check Snowflake UI → Admin → Warehouses
- Ask your Snowflake admin if unsure
- Common names: `COMPUTE_WH`, `WH_DEV`, `ANALYTICS_WH`

**Don't have this info?** Contact your Snowflake administrator or check your trial account welcome email.

### Create a Snowflake Profile

Recommended: SSO (Okta) via external browser

```bash
# Create a new profile (interactive)
snow connection add

# Example with SSO (Okta)
snow connection add \
  --connection-name my-profile \
  --account mycompany-prod.us-east-1 \
  --user alex.chen \
  --warehouse COMPUTE_WH \
  --database MY_DB \
  --schema PUBLIC \
  --authenticator externalbrowser

# If your org requires a direct Okta URL instead of externalbrowser
# --authenticator https://<your_okta_domain>.okta.com
```

Fallbacks:

```bash
# Password authentication (no SSO)
snow connection add \
  --connection-name my-profile \
  --account mycompany-prod.us-east-1 \
  --user alex.chen \
  --warehouse COMPUTE_WH \
  --database MY_DB \
  --schema PUBLIC \
  --password

# Key-pair authentication (advanced/headless)
snow connection add \
  --connection-name my-profile \
  --account mycompany-prod.us-east-1 \
  --user alex.chen \
  --warehouse COMPUTE_WH \
  --database MY_DB \
  --schema PUBLIC \
  --private-key-file ~/.snowflake/key.pem
```

### Verify Your Profile

```bash
# List all profiles
snow connection list

# Test your connection
snow sql -q "SELECT CURRENT_VERSION()" --connection my-profile
```

## Step 3: Configure Cursor MCP

Add igloo-mcp to Cursor's MCP configuration.

### Cursor Configuration

Edit your Cursor MCP settings (`~/.cursor/mcp.json`):

**For development installation** (recommended):
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
        "my-profile"
      ],
      "env": {
        "SNOWFLAKE_PROFILE": "my-profile"
      }
    }
  }
}
```

> **Note**: No `service_config.yml` needed! igloo-mcp uses Snowflake CLI profiles directly for authentication.

**Profile selection options**:
- `--profile` flag (recommended): `"args": ["--profile", "my-profile"]`
- Environment variable: `"env": {"SNOWFLAKE_PROFILE": "my-profile"}`
- Default profile: Omit args/env if you set a default with `snow connection set-default`

### Claude Code (alternative)

Add this to your Claude Code MCP settings:

```json
{
  "mcp": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": ["--profile", "my-profile"],
      "env": { "SNOWFLAKE_PROFILE": "my-profile" }
    }
  }
}
```

Then ask Claude to test the connection or list databases.

## Step 4: Test Your Setup

### Verify Snowflake Connection
```bash
# Test your profile
snow sql -q "SELECT CURRENT_VERSION()" --connection my-profile
```

### Verify MCP Server
```bash
# Start MCP server (should show help without errors)
igloo-mcp --profile my-profile --help
```

## Step 5: Start Using MCP Tools

Once configured, interact with igloo-mcp through Cursor:

### Example Prompts

```
"Test my Snowflake connection"
→ Uses: test_connection tool

"Build a catalog for MY_DATABASE"
→ Uses: build_catalog tool

"Build a dependency graph for USERS-related objects"
→ Uses: build_dependency_graph tool

"Execute this query: SELECT * FROM CUSTOMERS LIMIT 10"
→ Uses: execute_query tool
```

## Available MCP Tools

| Tool Name | Description | Key Parameters |
|-----------|-------------|----------------|
| `execute_query` | Execute SQL with safety checks, timeouts, cancellation | statement, timeout_seconds, verbose_errors, reason, warehouse, database, schema, role |
| `preview_table` | Preview table rows without writing SQL | table_name, limit, warehouse, database, schema, role |
| `build_catalog` | Build comprehensive catalog from INFORMATION_SCHEMA | output_dir, database, account, format |
| `get_catalog_summary` | Get catalog statistics and metadata | catalog_dir |
| `build_dependency_graph` | Generate object dependency graph (JSON/DOT) | database, schema, account, format |
| `test_connection` | Test Snowflake connection | — |
| `health_check` | Check MCP server health | — |

**Catalog Building Details**:
- Queries Snowflake `INFORMATION_SCHEMA` for comprehensive metadata
- Includes: databases, schemas, tables, views, materialized views, dynamic tables, tasks, functions, procedures, columns
- **Functions**: Only user-defined functions (excludes built-in Snowflake functions like operators `!=`, `%`, `*`, etc.)
- **Performance**: Optimized queries with proper filtering and ordering
- **Output**: Structured JSON with detailed metadata for each object type

## Advanced Configuration

### Multiple Profiles

Switch between environments by changing the `SNOWFLAKE_PROFILE`:

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

### Environment Variables

```bash
# Set default Snowflake profile
export SNOWFLAKE_PROFILE=my-profile

# Set default catalog directory
export SNOWCLI_CATALOG_DIR=./my_catalog

# Set default lineage directory
export SNOWCLI_LINEAGE_DIR=./my_lineage
```

## Troubleshooting

### MCP Server Won't Start

**Issue**: MCP server fails to start
**Solution**:
1. Verify Snowflake profile: `snow connection list`
2. Test connection: `snow sql -q "SELECT 1" --connection my-profile`
3. Check MCP configuration in your AI assistant settings
4. Review logs in your AI assistant

### Authentication Errors

**Issue**: "Authentication failed"
**Solution**:
1. Verify profile credentials are correct
2. Check private key file permissions (should be 600)
3. Ensure profile name matches `SNOWFLAKE_PROFILE` env var

### Tool Not Found

**Issue**: Cursor can't find MCP tools
**Solution**:
1. Restart Cursor completely
2. Verify MCP server is configured correctly
3. Check command path in MCP configuration
4. Ensure igloo-mcp is installed and accessible

## Next Steps

- 🎯 [Cursor MCP Setup Guide](cursor-mcp-setup.md) - **Recommended for Cursor users**
- 📖 [MCP Tools Reference](mcp/tools-reference.md) - Detailed tool documentation
- 🔧 [Configuration Guide](configuration.md) - Advanced settings
- 🐛 [Troubleshooting Guide](troubleshooting.md) - Common issues
- 📊 [Usage Examples](examples/) - Real-world examples

## Migrating from CLI?

If you were using the old CLI interface from snowcli-tools, see the [Migration Guide](migration-guide.md) for step-by-step instructions.

---

*Questions? Check our [GitHub Discussions](https://github.com/Evan-Kim2028/igloo-mcp/discussions)*
