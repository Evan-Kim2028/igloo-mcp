# Getting Started with igloo-mcp

> **Quick Start**: Set up your Snowflake profile → Install igloo-mcp → Start using with your AI assistant

## How It Works
- Your LLM calls MCP tools (execute_query, build_catalog, search_catalog, evolve_report, etc.) exposed by igloo-mcp.
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

See the [Installation Guide](installation.md) for complete installation instructions.

**Quick install**:
```bash
uv pip install igloo-mcp
```

## Step 2: Set Up Your Snowflake Profile

See the [Installation Guide](installation.md#2-create-a-snowflake-profile) for detailed profile setup instructions.

**Quick setup** (SSO recommended):
```bash
snow connection add \
  --connection-name my-profile \
  --account <account>.<region> \
  --user <username> \
  --warehouse COMPUTE_WH \
  --authenticator externalbrowser
```

Verify your profile:
```bash
snow connection list
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

Igloo MCP provides **13 focused tools** for Snowflake operations and Living Reports management.

| Tool Name | Description | Key Parameters |
|-----------|-------------|----------------|
| `execute_query` | Execute SQL with safety checks, timeouts, cancellation | statement, timeout_seconds, verbose_errors, reason, warehouse, database, schema, role |
| `build_catalog` | Build comprehensive catalog from INFORMATION_SCHEMA | output_dir, database, account, format |
| `get_catalog_summary` | Get catalog statistics and metadata | catalog_dir |
| `search_catalog` | Search locally cached catalog artifacts | catalog_dir, object_types, database, schema, name_contains, column_contains, limit |
| `build_dependency_graph` | Generate object dependency graph (JSON/DOT) | database, schema, account, format |
| `test_connection` | Test Snowflake connection | — |
| `health_check` | Check MCP server health | — |
| `create_report` | Create a new living report | title, template, tags, description |
| `evolve_report` | Evolve living reports with LLM assistance | report_selector, instruction, constraints, dry_run, response_detail ✨ |
| `render_report` | Render reports to various formats | report_selector, format, persist_output, preview_max_chars ✨ |
| `search_report` | Search for living reports | report_selector, fields ✨ |
| `get_report` **✨ v0.3.2** | Read reports with progressive disclosure | report_selector, mode, section_ids, filters |
| `get_report_schema` **✨ v0.3.2** | API schema introspection | schema_type, format |

**Note**: ✨ indicates new or enhanced features in v0.3.2.

**Catalog Storage**: `build_catalog` uses unified storage by default, saving catalogs to `~/.igloo_mcp/catalogs/{database}/`. See [Configuration Guide](configuration.md) for details on customizing catalog storage.

**Catalog Building Details**:
- Queries Snowflake `INFORMATION_SCHEMA` for comprehensive metadata
- Includes: databases, schemas, tables, views, materialized views, dynamic tables, tasks, functions, procedures, columns
- **Functions**: Only user-defined functions (excludes built-in Snowflake functions like operators `!=`, `%`, `*`, etc.)
- **Performance**: Optimized queries with proper filtering and ordering
- **Output**: Structured JSON with detailed metadata for each object type

---

## Token-Efficient Report Workflows (v0.3.2+) ✨

Achieve **70% token reduction** in multi-turn Living Reports workflows with progressive disclosure:

```python
# Efficient workflow example

# 1. Find reports (minimal fields)
reports = search_report(
    title="Q1 Sales",
    fields=["report_id", "title"]
)  # ~100 tokens

# 2. Inspect with summary mode
summary = get_report(
    report_selector=reports["reports"][0]["report_id"],
    mode="summary"
)  # ~150 tokens

# 3. Discover valid schemas
schema = get_report_schema(
    schema_type="proposed_changes",
    format="examples"
)  # ~600 tokens

# 4. Evolve with minimal response
result = evolve_report(
    report_selector=reports["reports"][0]["report_id"],
    instruction="Add revenue insight",
    proposed_changes={...},  # Based on schema
    response_detail="minimal"  # Token-efficient
)  # ~150 tokens

# Total: ~1,000 tokens (vs. 3,500+ tokens pre-v0.3.2)
# Savings: 71%
```

**Key v0.3.2 Features**:
- **Progressive disclosure**: `get_report` with 4 modes (summary/sections/insights/full)
- **Schema discovery**: `get_report_schema` for runtime API introspection
- **Field filtering**: `search_report` with selective field retrieval
- **Response control**: `evolve_report` with configurable verbosity
- **Preview sizing**: `render_report` with adjustable preview truncation

See [Living Reports User Guide](living-reports/user-guide.md) for complete workflows.

## Advanced Configuration

For advanced configuration options including multiple profiles, environment variables, and custom settings, see the [Configuration Guide](configuration.md).

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

- 🎯 [Cursor MCP Setup Guide](mcp/cursor-mcp-setup.md) - **Recommended for Cursor users**
- 📖 [API Reference](api-reference.md) - Complete MCP tools documentation
- 🔧 [Configuration Guide](configuration.md) - Advanced settings
- 📊 [Usage Examples](examples/catalog-examples.md) - Real-world examples

## See Also

- [Installation Guide](installation.md) - Detailed installation and profile setup
- [MCP Integration Guide](mcp-integration.md) - General MCP client configuration
- [Authentication Guide](authentication.md) - Authentication options and troubleshooting
- [Architecture Overview](architecture.md) - System architecture and design
- [Features Overview](features_overview.md) - Complete feature list

## Administrative CLI Tools

igloo-mcp includes administrative CLI tools for power users and system administrators. The primary interface for development work is through MCP tools in your AI assistant. See the [Administrative Operations](docs/index.md#administrative-operations) section for CLI usage details.

---

*Questions? Check our [GitHub Discussions](https://github.com/Evan-Kim2028/igloo-mcp/discussions)*
