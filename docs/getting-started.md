# Getting Started with igloo-mcp

> **Quick Start**: Set up your Snowflake profile → Install igloo-mcp → Start using with your AI assistant

## How It Works

Your LLM calls MCP tools (execute_query, build_catalog, evolve_report, etc.) through igloo-mcp, which uses your Snowflake CLI profile for authentication. Built-in guardrails block risky SQL operations, while timeouts and cancellation keep runs responsive. Every query logs to JSONL for auditing.

## Prerequisites

**Required**:
1. **Python 3.12+** with `uv` or pip
2. **Snowflake CLI** (bundled with igloo-mcp)
3. **Snowflake account** with appropriate permissions (USAGE on warehouse/database/schema, SELECT on INFORMATION_SCHEMA)
4. **AI Assistant** that supports MCP (Cursor, Claude Code, etc.)

## Installation & Setup

For complete installation instructions, see the **[Installation Guide](installation.md)**.

**Quick install**:
```bash
uv pip install igloo-mcp
```

**Quick Snowflake profile** (SSO recommended):
```bash
snow connection add --connection-name my-profile --account <account>.<region> --user <username> --warehouse COMPUTE_WH --authenticator externalbrowser
```

**Quick MCP config** (Cursor example - see [Installation Guide](installation.md) for other clients):
```json
{
  "mcpServers": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": ["--profile", "my-profile"]
    }
  }
}
```

> **Note**: For detailed setup including all authentication methods, multiple profiles, and troubleshooting, see [Installation Guide](installation.md).

## Your First Queries

Once configured, interact with igloo-mcp through your AI assistant:

### Example Prompts

```
"Test my Snowflake connection"
→ Uses: test_connection

"Show me the first 10 rows from CUSTOMERS table"
→ Uses: execute_query with auto-insights

"Build a catalog for MY_DATABASE"
→ Uses: build_catalog

"Find all tables with 'user' in the name"
→ Uses: search_catalog

"Create a dependency graph for the ANALYTICS schema"
→ Uses: build_dependency_graph
```

## Available MCP Tools

Igloo MCP provides **14 focused tools** organized by workflow. See [API Tools Index](api/TOOLS_INDEX.md) for complete workflow documentation.

### 🔍 Data Discovery
- `test_connection`, `execute_query`, `build_catalog`, `search_catalog`, `build_dependency_graph`

### 📊 Living Reports
- `create_report`, `search_report`, `get_report`, `get_report_schema`, `evolve_report`, `evolve_report_batch`, `render_report`

### 🏥 Health & Diagnostics
- `health_check`, `get_catalog_summary`

**View complete workflows**: [API Tools Index](api/TOOLS_INDEX.md)

---

## Token-Efficient Report Workflows

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

# Total: ~1,000 tokens (vs. 3,500+ tokens previously)
# Savings: 71%
```

**Key Features**:
- **Progressive disclosure**: `get_report` with 4 modes (summary/sections/insights/full)
- **Schema discovery**: `get_report_schema` for runtime API introspection
- **Field filtering**: `search_report` with selective field retrieval
- **Response control**: `evolve_report` with configurable verbosity
- **Preview sizing**: `render_report` with adjustable preview truncation

See [Living Reports User Guide](living-reports/user-guide.md) for complete workflows.

## Advanced Configuration

For configuration options including multiple profiles, environment variables, and custom storage paths, see the [Configuration Guide](configuration.md).

## Troubleshooting

### MCP Server Won't Start

**Solution**:
1. Verify Snowflake profile: `snow connection list`
2. Test connection: `snow sql -q "SELECT 1" --connection my-profile`
3. Check MCP configuration in your AI assistant settings
4. See [Installation Guide](installation.md#troubleshooting) for detailed troubleshooting

### Authentication Errors

**Solution**: See [Authentication Guide](authentication.md) for all auth methods and troubleshooting.

### Tool Not Found

**Solution**: Restart your MCP client completely after configuration changes.

## Next Steps

- 🎯 [Installation Guide](installation.md) - **Complete setup documentation**
- 🔧 [API Reference](api/README.md) - All MCP tools documentation
- 📊 [Living Reports User Guide](living-reports/user-guide.md) - Report workflows
- 💡 [Examples](examples/catalog-examples.md) - Real-world usage examples

## See Also

- [Installation Guide](installation.md) - Detailed installation and profile setup
- [MCP Integration Guide](mcp-integration.md) - General MCP client configuration
- [Authentication Guide](authentication.md) - Authentication options and troubleshooting
- [Features Overview](features_overview.md) - Complete feature list

## Administrative CLI Tools

igloo-mcp includes administrative CLI tools for power users and system administrators. The primary interface for development work is through MCP tools in your AI assistant. See the [Administrative Operations](docs/index.md#administrative-operations) section for CLI usage details.

---

*Questions? Check our [GitHub Discussions](https://github.com/Evan-Kim2028/igloo-mcp/discussions)*
