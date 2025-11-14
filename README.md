# Igloo MCP - Snowflake MCP Server for Agentic Native Workflows

Igloo MCP is a standalone MCP server for Snowflake operations, designed for agentic native workflows with AI assistants. Built from the ground up with SnowCLI integration for maximum simplicity and performance.

## ✨ Features

- 🛡️ **SQL Guardrails**: Blocks write + DDL operations (INSERT, UPDATE, CREATE, ALTER, DELETE, DROP, TRUNCATE) with safe alternatives
- ⏱️ **Timeouts + Cancellation**: Per‑request timeouts with best‑effort server‑side cancel; captures query ID when available
- 📝 **Always-On Query History**: Automatically capture JSONL audit events (success, timeout, error) with SHA-indexed SQL artifacts, even outside a git repo
- 📦 **Result Cache**: Default-on CSV/JSON cache per SQL + session context for instant replays without rerunning Snowflake
- 📊 **Auto Insights**: Every successful query returns lightweight `key_metrics` + `insights` derived from the seen rows—no extra SQL required
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
- `search_catalog` - Search locally built catalog artifacts for tables, views, and columns
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
| `search_catalog` | Search locally built catalog artifacts | `catalog_dir`, `object_types`, `database`, `schema`, `name_contains`, `column_contains`, `limit` |
| `build_dependency_graph` | Build dependency relationships (JSON/DOT) | `database`, `schema`, `account`, `format` |
| `test_connection` | Validate Snowflake connectivity | — |
| `health_check` | Comprehensive system, profile, and resource health | `include_cortex`, `include_profile`, `include_catalog` |
| `fetch_async_query_result` | Poll asynchronous `execute_query` jobs and retrieve cached results | `execution_id`, `include_rows` |

---

## Query Log History (doc.jsonl + SQL artifacts)

Every execution writes a compact JSONL record to `logs/doc.jsonl` (created on demand). If the workspace path is unavailable, Igloo falls back to `~/.igloo_mcp/logs/doc.jsonl` so history is always captured. Each record references the full SQL stored once by SHA-256 under `logs/artifacts/queries/by_sha/`.

### Configure Paths

| Purpose | Default | Override |
|---------|---------|----------|
| History file | `<repo>/logs/doc.jsonl` | `IGLOO_MCP_QUERY_HISTORY=/custom/doc.jsonl` |
| Artifact root | `<repo>/logs/artifacts/` | `IGLOO_MCP_ARTIFACT_ROOT=/custom/artifacts` |
| Cache root | `<artifact_root>/cache/` | `IGLOO_MCP_CACHE_ROOT=/custom/cache` |

Set these env vars to change locations. Use `IGLOO_MCP_QUERY_HISTORY=disabled` (or `off`/`false`/`0`) to disable history entirely. When disabled, neither JSONL records nor SQL artifacts are written to disk.

### Logged Fields (per line)

- `ts` — Unix timestamp (seconds)
- `execution_id` — Stable UUID per request (ties history, cache, audit info together)
- `status` — `success` | `timeout` | `error`
- `profile` — Snowflake profile used
- `statement_preview` — First 200 characters of the SQL
- `timeout_seconds` — Effective timeout applied
- `sql_sha256` — SHA-256 digest of the full SQL text
- `artifacts` — `{ "sql_path": "logs/artifacts/queries/by_sha/<sha>.sql" }`
- `rowcount`, `duration_ms`, `query_id` — When available (success only)
- `overrides` — Session overrides `{ warehouse, database, schema, role }`
- `reason` — Optional short reason (also stored in Snowflake `QUERY_TAG`)
- `post_query_insight` — Optional structured insight summarising what the query discovered
- `key_metrics`, `insights` — Automatically generated summaries of the returned rows (non-null ratios, numeric ranges, categorical top values, etc.)
- `cache_key`, `cache_manifest` — Present on cache hits/saves for traceability
- `session_context` — Effective warehouse/database/schema/role used for execution
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
- Cached executions log the `cache_key` and manifest path so you can open the saved CSV/JSON without rerunning Snowflake.
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

## Result Caching (rows.jsonl + CSV)

- Successful executions (up to `IGLOO_MCP_CACHE_MAX_ROWS`, default 5 000 rows) are cached under `<artifact_root>/cache/<cache_key>/` with both `rows.jsonl` and a human-friendly `rows.csv` plus a manifest.
- Subsequent calls with the same SQL, profile, and session overrides return the cached payload instantly; Snowflake is bypassed and history records a `cache_hit`.
- Configure behaviour via:
  - `IGLOO_MCP_CACHE_MODE=enabled|refresh|read_only|disabled`
  - `IGLOO_MCP_CACHE_ROOT=/custom/cache`
  - `IGLOO_MCP_CACHE_MAX_ROWS=2000`
- History entries include `cache_key`/`cache_manifest`, and tool responses expose `result.cache` + `audit_info.cache` so you always know when cached data was served.
- Cache manifests now persist the generated `key_metrics` + `insights`, so cache hits return the same summaries without recomputation.

### Fixture-Based Regression Testing

- A deterministic cache/history scenario lives under `tests/fixtures/cache_scenarios/baseline/` (history JSONL, manifest, rows CSV/JSONL, SQL text).
- Regenerate locally via `python -m tests.helpers.cache_fixture_builder` (see helper for details) and validate with `python -m pytest tests/test_cache_golden_fixtures.py`.
- CI consumers and log-processing scripts can rely on these fixtures to ensure compatibility with fields such as `execution_id`, `cache_key`, `post_query_insight`, and artifact paths.

### Inspect Local Logs Quickly

1. **View latest history line** – `tail -n 1 logs/doc.jsonl`
2. **Open full SQL text** – `cat $(jq -r '.artifacts.sql_path' <<< "$(tail -n 1 logs/doc.jsonl)")`
3. **Check cache manifest** – `jq '.' logs/artifacts/cache/<cache_key>/manifest.json`
4. **Disable logging/caching** (when debugging) – set `IGLOO_MCP_QUERY_HISTORY=disabled` and/or `IGLOO_MCP_CACHE_MODE=disabled` for that session.

### Search Built Catalogs

1. Run `build_catalog` once (for example `build_catalog --output_dir ./artifacts/catalog --database ANALYTICS`).
2. Query the local snapshot via `search_catalog`:
   ```bash
   search_catalog --catalog_dir ./artifacts/catalog --object_types table --name_contains customers
   ```
3. Filter by columns (`--column_contains revenue`) or schemas (`--schema REPORTING`) to rapidly find the objects you need without hitting Snowflake.

## Installation

### For End Users (Recommended)

**Install from PyPI for stable releases**:
```bash
uv pip install igloo-mcp
```

### Editor Setup (Cursor, Codex, Claude Code)

Quick wiring for common MCP clients. See the full guide in docs/installation.md.

• Cursor (`~/.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": ["--profile", "my-profile"],
      "env": {"SNOWFLAKE_PROFILE": "my-profile"}
    }
  }
}
```

• Claude Code (settings snippet)
```json
{
  "mcp": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": ["--profile", "my-profile"],
      "env": {"SNOWFLAKE_PROFILE": "my-profile"}
    }
  }
}
```

• Codex / Other MCP Clients (generic block; consult client docs for config path)
```json
{
  "mcpServers": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": ["--profile", "my-profile"],
      "env": {"SNOWFLAKE_PROFILE": "my-profile"}
    }
  }
}
```

After editing, restart your client and run a quick smoke test: `igloo-mcp --profile my-profile --help`.

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
#### Codex / Other MCP Clients (alternative)

Most MCP clients support the same server block; place it in your client’s MCP config file:
```json
{
  "mcpServers": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": ["--profile", "quickstart"],
      "env": {"SNOWFLAKE_PROFILE": "quickstart"}
    }
  }
}
```
Consult your client’s documentation for the specific config path and restart the client after changes.

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

## Global MCP Configuration (All Projects)

Cursor, Codex, and most MCP clients support a *global* configuration that applies to every workspace on your machine. Use this when you want igloo-mcp available everywhere without copying blocks into each repo.

1. **Edit the global config:**
   - Cursor: `~/.cursor/mcp.json`
   - Codex CLI: `~/.factory/mcp.json`
   - Claude Code: `~/Library/Application Support/Claude/mcp.json`
2. **Register igloo-mcp once:**
   ```json
   {
     "mcpServers": {
       "igloo-mcp": {
         "command": "igloo-mcp",
         "args": ["--profile", "quickstart"],
         "env": {
           "SNOWFLAKE_PROFILE": "quickstart",
           "IGLOO_MCP_QUERY_HISTORY": "~/.igloo_mcp/logs/doc.jsonl",
           "IGLOO_MCP_ARTIFACT_ROOT": "~/.igloo_mcp/logs/artifacts"
         }
       }
     }
   }
   ```
   The `env` block keeps history/artifacts in a stable global directory so every project reuses the same cache + audit trail.
3. **Switch profiles per workspace:** override `SNOWFLAKE_PROFILE` or pass `--profile` when launching igloo-mcp (Cursor adds per-project overrides via `.cursor/mcp.json`). You can also define multiple servers:
   ```json
   "igloo-mcp-prd": { "command": "igloo-mcp", "args": ["--profile", "prod"], "env": {"SNOWFLAKE_PROFILE": "prod"} }
   ```
4. **Manage secrets centrally:** export `SNOWFLAKE_PRIVATE_KEY_PATH`, `IGLOO_MCP_CACHE_MODE`, etc., in your shell RC so every project inherits the same behaviour. The MCP config should only reference non-sensitive identifiers.

Troubleshooting tips:
- If a project needs a different artifact root, set `IGLOO_MCP_ARTIFACT_ROOT` in that repo’s `.env` or launch script—it overrides the global default.
- Use `igloo-mcp --profile <name> --health-check` to validate the profile once; all editors re-use the cached session metadata.
- When sharing machines, prefer per-user global configs under your home directory so other accounts keep separate Snowflake profiles and audit logs.

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

## Testing

- **Offline (default):** `python -m pytest` – runs the offline suite backed by stored Snowflake CLI fixtures and fake connectors. This is the command we run in CI.
- **Live Snowflake checks (optional):** `python -m pytest --snowflake -m requires_snowflake` after setting up credentials. Without `--snowflake`, tests marked `requires_snowflake` are skipped automatically.

Fixtures that capture sanitized Snowflake CLI output live under `tests/fixtures/snowflake_cli/`. Update them as the schema evolves, then rerun the offline suite to ensure coverage stays green.
