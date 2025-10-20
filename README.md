# Igloo MCP - Snowflake MCP Server for Agentic Native Workflows


Igloo MCP is a standalone MCP server for Snowflake operations, designed for agentic native workflows with AI assistants. Built from the ground up with SnowCLI integration for maximum simplicity and performance.

## ✨ Features

- 🛡️ **SQL Safety:** Blocks destructive operations (DELETE, DROP, TRUNCATE) with safe alternatives
- 🧠 **Intelligent Errors:** Compact mode (default) and Verbose mode. Standard exception-based error handling
- ⏱️ **Agent-Controlled Timeouts:** Configure query timeouts per-request (1-3600s)
- ✅ **MCP Protocol Compliant:** Standard exception-based error handling

[📖 See Release Notes](./RELEASE_NOTES.md) for details.

[![PyPI version](https://badge.fury.io/py/igloo-mcp.svg)](https://pypi.org/project/igloo-mcp/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)


## Available MCP Tools

### Igloo MCP Tools
- `execute_query` - Execute SQL queries with safety checks
- `preview_table` - Preview table contents with LIMIT support
- `build_catalog` - Build comprehensive metadata catalog from Snowflake INFORMATION_SCHEMA
- `get_catalog_summary` - Get catalog overview with object counts and statistics
- `build_dependency_graph` - Build dependency graph for data lineage analysis
- `test_connection` - Test Snowflake connection and profile validation
- `health_check` - Get system health status and configuration details

See [MCP Documentation](docs/mcp/mcp_server_user_guide.md) for details.



---

## Installation

### For End Users (Recommended)

**Install from PyPI for stable releases**:
```bash
uv pip install igloo-mcp
```

## ⚡ 5-Minute Quickstart

Get igloo-mcp running with Cursor in under 5 minutes!

**Who this is for**: Users new to Snowflake and MCP who want to get started quickly.

### Prerequisites Check (30 seconds)

```bash
# Check Python version (need 3.12+)
python --version

# Check if Snowflake CLI is installed
snow --version

# If not installed, install it:
pip install snowflake-cli-labs
```

**What you'll need**:
- Snowflake account with username/password (or ask your admin)
- Cursor installed
- Your Snowflake account identifier (looks like: `mycompany-prod.us-east-1`)

### Step 1: Install igloo-mcp (1 minute)

```bash
# Install from PyPI
uv pip install igloo-mcp

# Verify installation
python -c "import igloo_mcp; print('igloo-mcp installed successfully')"
# Expected: igloo-mcp installed successfully
```

> **Note**: igloo-mcp automatically installs `snowflake-cli-labs` as a dependency

### Step 2: Create Snowflake Profile (2 minutes)

Recommended: use your organization's SSO (Okta) via external browser.

```bash
# Create a profile with SSO (Okta) via external browser
snow connection add \
  --connection-name "quickstart" \
  --account "<your-account>.<region>" \
  --user "<your-username>" \
  --authenticator externalbrowser \
  --warehouse "<your-warehouse>"

# A browser window opens to your Snowflake/Okta login
# Expected: "Connection 'quickstart' added successfully"
```

Notes:
- If your org requires an explicit Okta URL, use: `--authenticator https://<your_okta_domain>.okta.com`
- If your org doesn’t use SSO, see the password fallback below

**Finding your account identifier**:
- Your Snowflake URL: `https://abc12345.us-east-1.snowflakecomputing.com`
- Your account identifier: `abc12345.us-east-1` (remove `.snowflakecomputing.com`)

**Finding your warehouse**:
- Trial accounts: Usually `COMPUTE_WH` (default warehouse)
- Enterprise: Check Snowflake UI → Admin → Warehouses, or ask your admin
- Common names: `COMPUTE_WH`, `WH_DEV`, `ANALYTICS_WH`

**Don't have these?** Ask your Snowflake admin for:
- Account identifier
- Username & password
- Warehouse name

Fallback (no SSO): password authentication

```bash
snow connection add \
  --connection-name "quickstart" \
  --account "<your-account>.<region>" \
  --user "<your-username>" \
  --password \
  --warehouse "<your-warehouse>"

# Enter password when prompted
```

### Step 3: Configure Cursor MCP (1 minute)

Edit `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": [
        "--profile",
        "quickstart"
      ],
      "env": {
        "SNOWFLAKE_PROFILE": "quickstart"
      }
    }
  }
}
```

> **Note**: No `service_config.yml` needed! igloo-mcp uses Snowflake CLI profiles directly.

**Restart Cursor** after configuring.

### Step 4: Test Your Setup (30 seconds)

#### Verify Snowflake Connection
```bash
# Test your profile
snow sql -q "SELECT CURRENT_VERSION()" --connection quickstart
```

#### Verify MCP Server
```bash
# Start MCP server (should show help without errors)
igloo-mcp --profile quickstart --help
```

### Step 5: Test It! (30 seconds)

In Cursor, try these prompts:

```
"Test my Snowflake connection"
```

Expected: ✅ Connection successful message

```
"Show me my Snowflake databases"
```

Expected: List of your databases

```
"What tables are in my database?"
```

Expected: List of tables (if you have access)

## Success! 🎉

You've successfully:
- ✅ Installed igloo-mcp
- ✅ Configured Snowflake connection
- ✅ Connected Cursor to igloo-mcp
- ✅ Ran your first Snowflake queries via AI

**Time taken**: ~5 minutes

### What's Next?

#### Explore MCP Tools

Try these prompts in Cursor:

```
"Build a catalog for MY_DATABASE"
→ Explores all tables, columns, views, functions, procedures, and metadata
→ Only includes user-defined functions (excludes built-in Snowflake functions)

"Show me lineage for USERS table"
→ Visualizes data dependencies

"Preview the CUSTOMERS table with 10 rows"
→ Shows sample data from tables

"Execute: SELECT COUNT(*) FROM orders WHERE created_at > CURRENT_DATE - 7"
→ Runs custom SQL queries
```

#### Alternate: Key‑Pair (advanced)

Use RSA key‑pair auth when required by security policy or for headless automation:

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
  --connection-name "quickstart" \
  --account "mycompany-prod.us-east-1" \
  --user "your-username" \
  --private-key-file "~/.snowflake/key.pem" \
  --warehouse "COMPUTE_WH"
```

### Troubleshooting

#### "Profile not found"
**Fix**:
```bash
# List profiles
snow connection list

# Use exact name from list in your MCP config
```

#### "Connection failed"
**Fix**:
- Verify account format: `org-account.region` (not `https://...`)
- Check username/password are correct
- Ensure warehouse exists and you have access
- Try: `snow sql -q "SELECT 1" --connection quickstart`

#### "MCP tools not showing up"
**Fix**:
1. Verify igloo-mcp is installed: `which igloo-mcp`
2. Check MCP config JSON syntax is valid
3. **Restart Cursor completely**
4. Check Cursor logs for errors

#### "Permission denied"
**Fix**:
- Ensure you have `USAGE` on warehouse
- Check database/schema access: `SHOW GRANTS TO USER <your_username>`
- Contact your Snowflake admin for permissions

#### "SQL statement type 'Union' is not permitted"
**Fix**:
- Upgrade to the latest igloo-mcp; UNION/INTERSECT/EXCEPT now inherit SELECT permissions
- If you override SQL permissions, ensure `select` remains enabled in your configuration

#### Still stuck?

- 💬 [GitHub Discussions](https://github.com/Evan-Kim2028/igloo-mcp/discussions) - Community help
- 🐛 [GitHub Issues](https://github.com/Evan-Kim2028/igloo-mcp/issues) - Report bugs
- 📖 [Full Documentation](docs/getting-started.md) - Comprehensive guides
- 🔐 [Authentication Options](docs/authentication.md) - SSO/Okta, password, key‑pair

---

## Complete Setup Guide

### For Cursor Users

```bash
# 1. Set up your Snowflake profile
snow connection add --connection-name "my-profile" \
  --account "your-account.region" --user "your-username" \
  --authenticator externalbrowser --database "DB" --warehouse "WH"

# 2. Configure Cursor MCP
# Edit ~/.cursor/mcp.json:
{
  "mcpServers": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": [
        "--profile",
        "my-profile"
      ],
      "env": {
        "SNOWFLAKE_PROFILE": "my-profile"
      }
    }
  }
}

# 3. Restart Cursor and test
# Ask: "Test my Snowflake connection"
```

See [Getting Started Guide](docs/getting-started.md) for detailed setup instructions.

### MCP Server (MCP-Only Interface)

| Task | Command | Notes |
|------|---------|-------|
| Start MCP server | `igloo-mcp` | For AI assistant integration |
| Start with profile | `igloo-mcp --profile PROF` | Specify profile explicitly |
| Configure | `igloo-mcp --configure` | Interactive setup |

> 🐻‍❄️ **MCP-Only Architecture**
> Igloo MCP is MCP-only. All functionality is available through MCP tools.

**Profile Selection Options**:
- **Command flag**: `igloo-mcp --profile PROFILE_NAME` (explicit)
- **Environment variable**: `export SNOWFLAKE_PROFILE=PROFILE_NAME` (session)
- **Default profile**: Set with `snow connection set-default PROFILE_NAME` (implicit)

## Python API

```python
from igloo_mcp import QueryService, CatalogService

# Execute query
query_service = QueryService(profile="my-profile")
result = query_service.execute("SELECT * FROM users LIMIT 10")

# Build catalog
catalog_service = CatalogService(profile="my-profile")
catalog = catalog_service.build_catalog(database="MY_DB")
```

## Documentation

- [Getting Started Guide](docs/getting-started.md) - **Recommended for all users**
- [MCP Server User Guide](docs/mcp/mcp_server_user_guide.md) - Advanced MCP configuration
- [Architecture Overview](docs/architecture.md)
- [API Reference](docs/api/README.md) - All available MCP tools
- [Migration Guide (CLI to MCP)](docs/migration-guide.md)
- [Contributing Guide](CONTRIBUTING.md)

## Examples

### Query Execution via MCP

```python
# AI assistant sends query via MCP
{
  "tool": "execute_query",
  "arguments": {
    "statement": "SELECT COUNT(*) FROM users WHERE created_at > CURRENT_DATE - 30",
    "timeout_seconds": 60
  }
}
```

### Data Catalog Building

```python
# Build comprehensive metadata catalog
{
  "tool": "build_catalog",
  "arguments": {
    "database": "MY_DATABASE",
    "output_dir": "./catalog",
    "account": false,
    "format": "json"
  }
}
# Returns: databases, schemas, tables, views, functions, procedures, columns, etc.
# Note: Only includes user-defined functions (excludes built-in Snowflake functions)
```

### Data Lineage

```python
# Query lineage for impact analysis
{
  "tool": "query_lineage",
  "arguments": {
    "object_name": "MY_TABLE",
    "direction": "both",
    "depth": 3
  }
}
```
