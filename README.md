# Igloo MCP - Snowflake MCP Server for Agentic Native Workflows

Igloo MCP is a standalone MCP server for Snowflake operations, designed for agentic native workflows with AI assistants. Built from the ground up with SnowCLI integration for maximum simplicity and performance.

## ✨ Features

- 🛡️ **SQL Guardrails**: Blocks write + DDL operations (INSERT, UPDATE, CREATE, ALTER, DELETE, DROP, TRUNCATE) with safe alternatives
- ⏱️ **Timeouts + Cancellation**: Per‑request timeouts with best‑effort server‑side cancel; captures query ID when available
- 📝 **Lightweight Query History (default)**: Auto-write compact JSONL audit events (success, timeout, error) to `logs/doc.jsonl` with SHA-indexed SQL artifacts
- 🧠 **Smart Errors**: Compact by default; turn on verbose mode for actionable optimization hints
- 🧩 **MCP‑Only Tooling**: Clean set of MCP tools for query, preview, catalog, dependency graph, health, and connection tests
- ✅ **MCP Protocol Compliant**: Standard exception‑based error handling and robust health checks

[📖 See Release Notes](./RELEASE_NOTES.md) for details.

[![PyPI version](https://badge.fury.io/py/igloo-mcp.svg)](https://pypi.org/project/igloo-mcp/)
[![GitHub Release](https://img.shields.io/github/v/release/Evan-Kim2028/igloo-mcp)](https://github.com/Evan-Kim2028/igloo-mcp/releases)
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

## Tool Overview

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `execute_query` | Run SQL with validation, timeouts, cancellation | `statement`, `timeout_seconds`, `verbose_errors`, `reason`, `warehouse`, `database`, `schema`, `role` |
| `preview_table` | Quick table preview without writing SQL | `table_name`, `limit`, `warehouse`, `database`, `schema` |
| `build_catalog` | Export comprehensive Snowflake metadata | `output_dir`, `database`, `account`, `format` |
| `get_catalog_summary` | Read catalog statistics and health | `catalog_dir` |
| `build_dependency_graph` | Build dependency relationships (JSON/DOT) | `database`, `schema`, `account`, `format` |
| `test_connection` | Validate Snowflake connectivity | — |
| `health_check` | Comprehensive system, profile, and resource health | `include_cortex`, `include_profile`, `include_catalog` |

---

## Query Log History (doc.jsonl + SQL artifacts)

Every execution writes a compact JSONL record to the repo-local `logs/doc.jsonl` (created on demand). Each record references the full SQL stored once by SHA-256 under `logs/artifacts/queries/by_sha/`.

### Configure Paths

| Purpose | Default | Override |
|---------|---------|----------|
| History file | `<repo>/logs/doc.jsonl` | `IGLOO_MCP_QUERY_HISTORY=/custom/doc.jsonl` |
| Artifact root | `<repo>/logs/artifacts/` | `IGLOO_MCP_ARTIFACT_ROOT=/custom/artifacts` |

Set either env var to change locations. Use an empty string (`export IGLOO_MCP_QUERY_HISTORY=""`) to disable history entirely.
When disabled, neither JSONL records nor SQL artifacts are written to disk.

### Logged Fields (per line)

- `ts` — Unix timestamp (seconds)
- `status` — `success` | `timeout` | `error`
- `profile` — Snowflake profile used
- `statement_preview` — First 200 characters of the SQL
- `timeout_seconds` — Effective timeout applied
- `sql_sha256` — SHA-256 digest of the full SQL text
- `artifacts` — `{ "sql_path": "logs/artifacts/queries/by_sha/<sha>.sql" }`
- `rowcount`, `duration_ms`, `query_id` — When available (success only)
- `overrides` — Session overrides `{ warehouse, database, schema, role }`
- `reason` — Optional short reason (also stored in Snowflake `QUERY_TAG`)
- `error` — Error message (timeout/error only)

### Examples

Success:
```json
{
  "ts": 1737412345,
  "status": "success",
  "profile": "quickstart",
  "statement_preview": "SELECT * FROM customers LIMIT 10",
  "rowcount": 10,
  "timeout_seconds": 30,
  "query_id": "01a1b2c3d4",
  "duration_ms": 142,
  "sql_sha256": "4f7c1e2f...",
  "artifacts": {"sql_path": "logs/artifacts/queries/by_sha/4f7c1e2f....sql"}
}
```

Timeout (server-side cancel attempted):
```json
{
  "ts": 1737412399,
  "status": "timeout",
  "profile": "quickstart",
  "statement_preview": "SELECT * FROM huge_table WHERE date >= '2024-01-01'",
  "timeout_seconds": 30,
  "sql_sha256": "f1c3a8c0...",
  "artifacts": {"sql_path": "logs/artifacts/queries/by_sha/f1c3a8c0....sql"},
  "error": "Query execution exceeded timeout and was cancelled"
}
```

Notes:
- Query ID may be unavailable if a timeout triggers early cancellation.
- History writes are best-effort; logging never raises to the caller.
- Full SQL is stored once by hash; use the MCP resource `igloo://queries/by-sha/{sql_sha256}.sql` or the exporter (below) to read it.
- Use `reason` for human context only; avoid sensitive data.

### Bundle SQL for Audits

Export a self-contained bundle (full SQL + minimal provenance) straight from `doc.jsonl`:

```bash
uv run python scripts/export_report_bundle.py \
  --doc logs/doc.jsonl \
  --artifact-root logs/artifacts \
  --query-id 01a1b2c3d4 \
  --output notes/reports/flashcrash_bundle.json
```

Or select by `reason` substring and keep only the latest run per SQL hash:

```bash
uv run python scripts/export_report_bundle.py \
  --reason-contains "flashcrash" \
  --latest-per-sql \
  --output notes/reports/flashcrash_latest.json
```

Each bundle entry includes:
- `sql_sha256`, `mcp_uri`, and the full `sql_text`
- Any `query_id`, `reason`, `rowcount`, `duration_ms`, and overrides
- Generator metadata with the selection criteria used

## Installation

### For End Users (Recommended)

**Install from PyPI for stable releases**:
```bash
uv pip install igloo-mcp
```

## ⚡ 5-Minute Quickstart

Get igloo-mcp running with Cursor in under 5 minutes!

**Who this is for**: Users new to Snowflake and MCP who want to get started quickly.

### How It Works
- Your LLM calls MCP tools (execute_query, preview_table, build_catalog, etc.) exposed by igloo-mcp.
- igloo-mcp uses your Snowflake CLI profile for authentication and session context.
- Built-in guardrails block destructive SQL; timeouts and best‑effort cancellation keep runs responsive.
- Optional JSONL query history records success/timeout/error with minimal fields for auditing.
- Configure your editor (Cursor or Claude Code) to launch igloo-mcp with your Snowflake profile.

### Prerequisites Check (30 seconds)

```bash
# Check Python version (need 3.12+)
python --version
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

> **Note**: igloo-mcp bundles the Snowflake CLI, so `snow --version` should succeed after installation. If it does not, check that your environment PATH includes the uv-managed scripts directory or that you’re using the same virtual environment.

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

#### Claude Code (alternative)

Add this to your Claude Code MCP settings:

```json
{
  "mcp": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": ["--profile", "quickstart"],
      "env": { "SNOWFLAKE_PROFILE": "quickstart" }
    }
  }
}
```

Then ask Claude to test the connection or list databases.

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

"Build a dependency graph for USERS in MY_DB"
→ Visualizes object dependencies (upstream/downstream) via build_dependency_graph

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

### Table Preview

```python
# Quickly sample rows from a table
{
  "tool": "preview_table",
  "arguments": {
    "table_name": "PUBLIC.CUSTOMERS",
    "limit": 5
  }
}
```
