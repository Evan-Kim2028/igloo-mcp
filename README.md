# Igloo MCP
**Lightweight Snowflake MCP server for AI-powered data workflows**

[![PyPI version](https://badge.fury.io/py/igloo-mcp.svg)](https://pypi.org/project/igloo-mcp/)
[![GitHub Release](https://img.shields.io/github/v/release/Evan-Kim2028/igloo-mcp)](https://github.com/Evan-Kim2028/igloo-mcp/releases)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

Connect your AI assistant (Cursor, Claude) to Snowflake with built-in safety, caching, and auditing. Query databases, build catalogs, and create living reports—all through natural language.

## Why Igloo MCP?

✅ **Query Safely** — Blocks DDL/DML by default, auto-cancels slow queries, logs every execution
✅ **Work Faster** — Minimizes token usage through progressive disclosure and smart caching
✅ **Stay Audited** — Complete query history with source attribution for compliance tracking

## Quick Start

```bash
# Install
uv pip install igloo-mcp

# Configure Snowflake (uses your existing Snowflake CLI profile)
snow connection add --name quickstart --account <account> --user <user> --authenticator externalbrowser --warehouse <warehouse>

# Add to ~/.cursor/mcp.json
{
  "mcpServers": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": ["--profile", "quickstart"]
    }
  }
}
```

Restart your MCP client and ask: *"Preview the customers table"*

**Full setup guide**: [docs/installation.md](./docs/installation.md)

## Core Capabilities

### 🔍 Query & Explore
- **`execute_query`** — Run safe SQL with guardrails, timeouts, and auto-insights
- **`build_catalog`** — Export Snowflake metadata for offline search
- **`search_catalog`** — Find tables/columns without querying Snowflake
- **`build_dependency_graph`** — Visualize table lineage and dependencies

### 📊 Living Reports
- **`create_report`** — Initialize auditable JSON-backed business reports
- **`evolve_report`** — Modify reports safely with LLM assistance and full audit trail
- **`evolve_report_batch`** — Perform multiple report operations atomically (add insights, attach charts)
- **`render_report`** — Export to HTML, PDF, or Markdown via Quarto
- **`get_report`** — Read reports efficiently with progressive disclosure (summary/sections/insights/full modes)
- **`search_report`** — Find reports by title or tags
- **`search_citations`** — Search citations across reports by source type, provider, or URL
- **`get_report_schema`** — Discover valid report structures at runtime

Attach charts to insights, cite multiple source types (query, API, URL, observation, document), and search citations across all reports.

### 🏥 Health & Diagnostics
- **`test_connection`** — Validate Snowflake authentication
- **`health_check`** — Monitor server, profile, and catalog status

**View all 15 tools**: [docs/api/TOOLS_INDEX.md](./docs/api/TOOLS_INDEX.md)

## When to Use Igloo MCP

| **Choose Igloo if you want:** | **Choose Snowflake Labs MCP if you need:** |
|---|---|
| ✅ AI assistant for dev/analytics workflows | ❌ Production Cortex AI integration |
| ✅ Simple SnowCLI-based setup | ❌ Enterprise service architecture |
| ✅ Query safety + automatic caching | ❌ Full Snowflake object management |
| ✅ Built-in auditing and compliance tracking | ❌ Container-based deployment |

## Resources

- 📖 [Getting Started Guide](./docs/getting-started.md)
- 🔧 [API Reference](./docs/api/README.md)
- 📊 [Living Reports User Guide](./docs/living-reports/user-guide.md)
- 💡 [Examples](./examples/README.md)
- 📝 [Changelog](./CHANGELOG.md)
- 💬 [Discussions](https://github.com/Evan-Kim2028/igloo-mcp/discussions)

---

**MIT Licensed** | Built for agentic efficiency
