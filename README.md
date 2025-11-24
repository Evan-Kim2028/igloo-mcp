
# Igloo MCP - Lightweight MCP Server for Agentic Snowflake Workflows

Igloo MCP is a standalone, SnowCLI-powered MCP server designed for seamless Snowflake interactions in AI agentic workflows. Unlike general-purpose tools, it's optimized for developers using LLMs (e.g., in Cursor or Claude) to explore data, build catalogs, and analyze lineage – with built-in safety, auditing, and speed boosts for iterative dev.

[![PyPI version](https://badge.fury.io/py/igloo-mcp.svg)](https://pypi.org/project/igloo-mcp/)
[![GitHub Release](https://img.shields.io/github/v/release/Evan-Kim2028/igloo-mcp)](https://github.com/Evan-Kim2028/igloo-mcp/releases)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

## Key Features

- 🛡️ **Built-in Guardrails**: Defaults block writes/DDL (e.g., no INSERT/CREATE); safe alternatives suggested. Enhanced in v0.2.3 for stricter validation.
- ⏱️ **Timeouts & Cancellation**: Per-query limits (default 30s) with server-side cancel; captures query IDs for tracing.
- 📝 **Always-On History**: Auto-logs executions (success/error/timeout) to JSONL + SHA-hashed SQL artifacts. Fallback to `~/.igloo_mcp/logs/` if no workspace.
- 📦 **Smart Caching**: Cache results (up to 5k rows as CSV/JSONL) by SQL + context; modes for refresh/read-only. Instant for AI replays.
- 📊 **Auto Insights**: Every query returns `key_metrics` (null ratios, ranges, top values) + insights – fuels LLM reasoning without follow-up SQL.
- 🧠 **Error Handling**: Compact errors; verbose mode for hints. v0.2.3 adds better REST init fallbacks and v0.2.5 ensures health-check feedback routes through the new `get_comprehensive_health` monitor.
- 📡 **Source Attribution**: v0.2.5+ includes structured `source_databases`/`tables` fields in both query responses and history logs so compliance reviews no longer rely on session defaults.
- 🧩 **MCP-Compliant Tools**: Clean set for agentic use – no extras. Consolidated in v0.2.3 for reporting workflows.
- 📂 **Unified Storage**: All data (query history, artifacts, reports) stored together per instance for easy access across projects
- ⚡ **Simple Backend**: SnowCLI integration for max performance; CLI/REST modes. Python 3.12+, MIT-licensed.

Full API in [docs/api/README.md](./docs/api/README.md).

## Why Igloo MCP? (vs. Official Snowflake Labs MCP)

The official [Snowflake Labs MCP](https://github.com/Snowflake-Labs/mcp) is a powerful, enterprise-grade server for full Snowflake AI integration – great for production apps using Cortex (RAG, semantic agents) and object ops. But for **agentic development** (e.g., LLM-driven data exploration in dev tools), Igloo offers a lighter, more dev-focused alternative:

- **Simpler Setup**: SnowCLI-based – no YAML service configs. Just install, pick a profile, and go. Official requires detailed service listings and permission tuning.
- **Dev Workflow Boosts**: Always-on query history (JSONL audits), result caching (instant replays, no re-hits on Snowflake), and auto-insights (row summaries for LLM reasoning – no extra SQL). Official emphasizes Cortex but lacks these for rapid iteration.
- **Agent-Safe Defaults**: Blocks risky SQL (DDL/DML) out-of-box, with timeouts/cancellation. Official is flexible but needs config for guards.
- **Lightweight Focus**: 6 core MCP tools for querying, cataloging, and lineage – perfect for AI prototypes. Skip Cortex bloat if you don't need RAG/agents.
- **Performance Edge**: Optimized for local/dev (CLI mode default; REST fallback added in v0.2.3). Official is container-heavy for prod.
- **Transparent Attribution**: v0.2.5+ logs `source_databases` + fully-qualified `tables` for every query result/history entry so cross-database access is always auditable.

In essence: Use official for production Snowflake AI ecosystems. Choose Igloo for agile agentic coding – faster auditing, caching, and safety to make your LLMs more productive with data.

## MCP Tools

Igloo exposes 11 focused tools for Snowflake ops. Use via any MCP client (e.g., Cursor: add to `.mcp.json`).

| Tool | Purpose | Key Use |
|------|---------|---------|
| `execute_query` | Run safe SQL with guards/timeouts | Agent-generated queries; returns rows + insights |
| `build_catalog` | Export metadata (tables/views/etc.) to JSONL | Offline catalog for search/lineage |
| `get_catalog_summary` | Stats on built catalogs (counts, health) | Quick schema overviews |
| `search_catalog` | Offline search by name/column/schema | Find objects without Snowflake hits |
| `build_dependency_graph` | Lineage as JSON/DOT (visualizable) | Pipeline analysis |
| `test_connection` | Validate profile/auth | Setup checks |
| `health_check` | System/profile/catalog status | Monitoring |
| `create_report` | Create a new living report | Initialize structured business reports |
| `evolve_report` | LLM-agnostic report evolution | Safely evolve audited reports |
| `render_report` | Quarto-based report rendering | Export reports to HTML/PDF/Markdown |
| `search_report` | Search for living reports | Find reports by title or ID |

Detailed schemas in [docs/api/TOOLS_INDEX.md](./docs/api/TOOLS_INDEX.md).

## Living Reports (Beta)

Living Reports are JSON-backed, auditable business reports that evolve safely with LLM assistance. Key features:

- **Structured**: JSON schema with sections, insights, and supporting queries
- **Auditable**: Full history of changes with actor tracking
- **LLM-Evolvable**: Use `evolve_report` tool to safely modify reports
- **MCP-First**: Primary interface through AI assistants and MCP tools

**MCP Usage:**
```python
# Evolve report via MCP
result = await evolve_report(
    report_selector="Q1 Sales Analysis",
    instruction="Prioritize revenue drivers over user acquisition",
    constraints={"max_importance_delta": 2}
)
```

**For Administrators:**
```bash
# Create a report (administrative setup)
igloo report create "Q1 Sales Analysis" --description "Quarterly sales metrics"

# List reports (administrative operations)
igloo report list
```

See [docs/living-reports/user-guide.md](./docs/living-reports/user-guide.md) for details.

## Installation & Quickstart

### Install (1 min)
```bash
uv pip install igloo-mcp  # Or pip install igloo-mcp
igloo --version  # Verify (v0.3.0+)
```

### Connect Snowflake Profile (2 min)
Use SnowCLI (bundled):
```bash
snow connection add --name quickstart --account <your-account> --user <username> --authenticator externalbrowser --warehouse <warehouse>
# Browser login (SSO/Okta preferred)
```

### Launch & Test in Cursor/Claude (1 min)
## Usage Notes: Required `reason` Parameter (v0.2.4+ / still mandatory in v0.3.0)

- **Every `execute_query` needs `reason`** (5+ chars): Explains query purpose for audits.
- Examples:
  ```python
  execute_query(statement="SELECT * FROM sales LIMIT 10", reason="Preview recent orders")
  execute_query(statement="SELECT COUNT(*) FROM users WHERE date >= '2025-01-01'", reason="Validate user growth Q1")
  ```
- **Why?** Improves Snowflake QUERY_TAG, history searchability, and team collaboration.
- Backward compatible with existing logs.
Copy [docs/config/mcp-client-config.example.json](./docs/config/mcp-client-config.example.json) to `~/.cursor/mcp.json` (or client-specific path):
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
Restart client; test: Ask "Preview the customers table" – should return safe rows + insights.

Full client guides: [docs/installation.md](./docs/installation.md).

## Advanced: History & Caching

- **Query History**: Logs to `logs/doc.jsonl` (ts, status, SQL hash, metrics). Export bundles via `scripts/export_report_bundle.py`.
- **Caching**: Enabled by default; configurable modes (env: `IGLOO_MCP_CACHE_MODE`). Persists insights for hits.

**Optional Configuration**: All history/artifact/report paths have sensible defaults. Only set these environment variables if you need custom paths or to disable features:
- `IGLOO_MCP_QUERY_HISTORY` - Optional. Defaults to `~/.igloo_mcp/logs/doc.jsonl` (global) or `<repo>/logs/doc.jsonl` (repo scope). Set to `disabled` to turn off history.
- `IGLOO_MCP_ARTIFACT_ROOT` - Optional. Defaults to `~/.igloo_mcp/logs/artifacts` (global) or `<repo>/logs/artifacts` (repo scope).
- `IGLOO_MCP_REPORTS_ROOT` - Optional. Defaults to `~/.igloo_mcp/reports` (global) or `<repo>/reports` (repo scope).

See [Configuration Guide](./docs/configuration.md) for details.


## Resources
- [Full Docs](./docs/getting-started.md)
- [API Reference](./docs/api/README.md)
- [Examples](./examples/README.md) (e.g., catalog building, dep graphs)
- [CHANGELOG](./CHANGELOG.md) for full release notes (0.2.3, 0.2.4, 0.2.5, 0.3.0, etc.)
- Questions? Open an issue or discuss in [CONTRIBUTING.md](./CONTRIBUTING.md).

Built for agentic efficiency – let's make Snowflake AI-native!
