# Igloo MCP

[![PyPI version](https://badge.fury.io/py/igloo-mcp.svg)](https://pypi.org/project/igloo-mcp/)
[![GitHub Release](https://img.shields.io/github/v/release/Evan-Kim2028/igloo-mcp)](https://github.com/Evan-Kim2028/igloo-mcp/releases)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

A lightweight Snowflake MCP server that connects your AI assistant to Snowflake with built-in safety, caching, and auditing. Query databases, build catalogs, and create living reports—all through natural language.

## Why Igloo MCP?

### 🔒 Query Safely
Block dangerous DDL/DML by default, auto-cancel slow queries, and log every execution. Use `execute_query` with configurable guardrails and `test_connection` to validate authentication before running queries.

### ⚡ Work Faster
Minimize token usage through progressive disclosure and smart result caching. Tools like `get_report` support multiple retrieval modes (summary/sections/insights/full), and `search_catalog` lets you find tables without hitting Snowflake.

### 📋 Stay Audited
Maintain complete query history with source attribution for compliance tracking. Every `execute_query` call logs to history, and Living Reports track all modifications with full audit trails via `evolve_report`.

### 📊 Build Living Reports
Create auditable, evolving business reports with `create_report`, modify them safely with `evolve_report`, attach charts to insights, and export to HTML/PDF/Markdown via `render_report`.

## Quick Start

### Prerequisites

```bash
# Install igloo-mcp
uv pip install igloo-mcp

# Configure Snowflake connection (uses Snowflake CLI)
snow connection add --name quickstart --account <account> --user <user> --authenticator externalbrowser --warehouse <warehouse>
```

### Cursor Setup

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": ["--profile", "quickstart"]
    }
  }
}
```

Restart Cursor and ask: *"Preview the customers table"*

### Claude Code Setup

Run from terminal:

```bash
claude mcp add igloo-mcp --scope user -- igloo-mcp --profile quickstart
```

Or add to `~/.claude.json` manually:

```json
{
  "mcpServers": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": ["--profile", "quickstart"]
    }
  }
}
```

Restart Claude Code and ask: *"Show me the schema for my database"*

**Full setup guide**: [docs/installation.md](./docs/installation.md)

## Core Tools

### 🔍 Query & Explore
| Tool | Description |
|------|-------------|
| `execute_query` | Run SQL with guardrails, timeouts, and auto-insights |
| `build_catalog` | Export Snowflake metadata for offline search |
| `search_catalog` | Find tables/columns without querying Snowflake |
| `build_dependency_graph` | Visualize table lineage and dependencies |

### 📊 Living Reports
| Tool | Description |
|------|-------------|
| `create_report` | Initialize auditable JSON-backed reports |
| `evolve_report` | Modify reports with LLM assistance and audit trail |
| `evolve_report_batch` | Perform multiple operations atomically |
| `render_report` | Export to HTML, PDF, or Markdown via Quarto |
| `get_report` | Read reports with progressive disclosure modes |
| `search_report` | Find reports by title or tags |
| `search_citations` | Search citations by source type or provider |
| `get_report_schema` | Discover valid structures and section templates at runtime |

### 🏥 Health & Diagnostics
| Tool | Description |
|------|-------------|
| `test_connection` | Validate Snowflake authentication |
| `health_check` | Monitor server, profile, and catalog status |

**View all 15 tools**: [docs/api/TOOLS_INDEX.md](./docs/api/TOOLS_INDEX.md)

## When to Use Igloo MCP

| Choose Igloo MCP | Choose Snowflake Labs MCP |
|------------------|---------------------------|
| AI assistant for dev/analytics workflows | Production Cortex AI integration |
| Simple SnowCLI-based setup | Enterprise service architecture |
| Query safety + automatic caching | Full Snowflake object management |
| Built-in auditing and compliance | Container-based deployment |

## Resources

- 📖 [Getting Started Guide](./docs/getting-started.md)
- 🔧 [API Reference](./docs/api/README.md)
- 📊 [Living Reports User Guide](./docs/living-reports/user-guide.md)
- 💡 [Examples](./examples/README.md)
- 📝 [Changelog](./CHANGELOG.md)
- 💬 [Discussions](https://github.com/Evan-Kim2028/igloo-mcp/discussions)

---

**MIT Licensed** | Built for agentic efficiency
