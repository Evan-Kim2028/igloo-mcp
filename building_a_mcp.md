# Building `igloo-mcp` for Agentic Snowflake Workflows

## Introduction
This is a build log of my first steps building an MCP server for Snowflake. It captures what I tried, what exists today, what worked, what did not, and where I am going next. If you are exploring or building your own MCP, I hope these notes and code references save you time. For install and a quickstart, see the [igloo-mcp README](https://github.com/Evan-Kim2028/igloo-mcp).

### Table of contents
- [Why I started building an MCP](#why-i-started-building-an-mcp)
- [How igloo-mcp differs from Snowflake Labs MCP](#how-igloo-mcp-differs-from-snowflake-labs-mcp)
- [How igloo-mcp works](#how-igloo-mcp-works)
- [What exists today](#what-exists-today)
- [Known limitations (early days)](#known-limitations-early-days)
- [Learnings](#learnings)
- [What's next](#whats-next)


## Why I started building an MCP
As a data scientist, there are always more questions than answers. I built `igloo-mcp` to optimize how agents run sequences of queries on my Snowflake database to answer the never ending stream of questions. The major benefit of agentic querying is that agents can quickly build the context needed to derive nontrivial insights with minimal instructions.

It's magical when everything works smoothly. I can rapidly debug and improve data pipelines, develop metrics faster, and also ask low priority but potentially interesting questions about datasets that I never had time to answer before. I also wanted a way to codify behaviors I found effective. MCPs are a natural choice to standardize tools that make agents' outputs more reliable and trustworthy.

Finally, I wanted to build the MCP from scratch to experiment with managing agents to design a repo from the ground up. When I use agents on the Snowflake database, I almost always use `igloo-mcp` to run tens of queries at a time. In contrast, building a repository lets me test multi agent workflows on code.

## How `igloo-mcp` differs from Snowflake Labs MCP

- **Stacking on top instead of rebuilding**: `igloo-mcp` boots the [Snowflake Labs MCP](https://github.com/Snowflake-Labs/mcp) runtime and layers catalog/dependency workflows on top, which keeps the upstream Cortex/object/query tools available while adding the metadata utilities I rely on.
- **Zero config profiles vs YAML service maps**: `igloo-mcp` reuses the SnowCLI profile that already exists on my machine, while Snowflake Labs MCP expects a `configuration.yaml` that lists Cortex services, tool groups, and SQL permissions before the server can start.
- **Safety first execution path**: `igloo-mcp` runs queries through the CLI to inherit profile RBAC, validate statements against allow/deny lists, check profile health, and optionally return verbose error diagnostics. Snowflake Labs MCP executes through the connector and surfaces failures through a generic `SnowflakeException`, leaving destructive statements enabled unless you turn them off in YAML.

## How `igloo-mcp` works

I evaluated Snowflake Labs MCP to understand its strengths and how to make an MCP that better fits my agentic workflows. `igloo-mcp` reflects those choices.


## What exists today
Currently, functionality includes:

**Tools**
- `execute_query` — Executes SQL via SnowCLI; supports warehouse/database/schema/role overrides, allow/deny validation, timeouts, and optional verbose errors
- `preview_table` — Returns a limited preview of a table
- `build_catalog` — Builds metadata from INFORMATION_SCHEMA (account or database scope) with JSON/JSONL output; includes DDL
- `get_catalog_summary` — Reads and returns catalog summary from a directory
- `build_dependency_graph` — Produces object dependency graph (JSON or DOT)
- `test_connection` — Verifies Snowflake connectivity using the configured profile
- `health_check` — Reports server and profile health

**Defaults**
- DELETE, DROP, and TRUNCATE are blocked by default; can be changed in configuration

**Execution**
- Error handling:
  - Compact by default keeps agent loops readable and reduces noise
  - Verbose on demand includes a SQL snippet, timeout, and context for faster debugging
  - Profile health checks fail fast when a profile is missing or misconfigured
  - Allow/deny validation blocks risky or unsupported statements before anything runs
  - Messages are formatted so MCP clients surface actionable feedback instead of long stack traces
- Session overrides: per request overrides for warehouse, database, schema, and role

**Configuration**
- Uses your existing SnowCLI profile; no separate YAML is required

Although `igloo-mcp` has 7 tools, the two I use most are `build_catalog` and `execute_query`. The other five are roadmap items that may be automated.

## Known limitations (early days)
- Query timeout now cancels the running statement server-side and breaks out immediately on the MCP side. In some timeout scenarios, a Snowflake `query_id` may be unavailable. Enable a lightweight JSONL history trail with `IGLOO_MCP_QUERY_HISTORY=/path/to/query_history.jsonl` to aid auditing.
- Requires SnowCLI to be installed and configured since query execution goes through the CLI.
- Metadata features are evolving and may change shape as I test with larger accounts.

## Learnings
I pushed the boundaries to see where agent capabilities currently end. The biggest lesson was that agents cannot be trivially parallelized on large codebases. It requires thoughtful planning, and there are not yet great solutions to monitor multiple agents working on different things. However, there are promising products like Claude Subagents and Zed CLI CRDTs (Conflict free Replicated Data Types).

Another limitation is the human ability to keep up with multiple agents' work. That said, it feels like more parallel autonomous agents are getting closer, and I am looking forward to seeing more of this soon.

A large refactor cut the codebase from more than 20k LOC to less than 5k LOC; repo wide renaming required multiple assistive passes.

## What's next
I will keep iterating on `igloo-mcp` to continue learning how to build strong MCP tools and what does and does not work in practice for different workflows. For instance, I am doing heavy quantitative research and I am exploring a cache for the `execute_query` tool and a better way to persist SQL history locally for specific tasks.

The other angle is that I find it useful to hand pick issues by defining the problem and desired result, then have the LLM write a more in depth issue and eventually fix it and open a PR. As a result, I spend more time as a product manager and power user of my own work while delegating more boilerplate aspects of development to different agents in the background.
