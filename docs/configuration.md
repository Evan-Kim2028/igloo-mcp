 # Configuration Guide

 ## Overview

 Igloo MCP can be configured through multiple methods, with the following precedence:
 1. MCP server arguments (highest priority)
 2. Environment variables
 3. Configuration files
 4. Default values (lowest priority)

 ## Configuration Methods

 ### 1. Environment Variables

 Set these in your shell profile or before running commands:

 ```bash
 # Snowflake connection settings
 export SNOWFLAKE_PROFILE=my-profile
 export SNOWFLAKE_WAREHOUSE=my-warehouse
 export SNOWFLAKE_DATABASE=my-database
 export SNOWFLAKE_SCHEMA=my-schema
 export SNOWFLAKE_ROLE=my-role

# Output directories
export SNOWCLI_CATALOG_DIR=./data_catalogue
export SNOWCLI_LINEAGE_DIR=./lineage_data
export SNOWCLI_DEPENDENCY_DIR=./dependencies

# Query history & cache (all optional - defaults provided)
export IGLOO_MCP_QUERY_HISTORY=~/workspace/logs/doc.jsonl   # Optional: JSONL history path (default: ~/.igloo_mcp/logs/doc.jsonl for global scope, or <repo>/logs/doc.jsonl for repo scope)
export IGLOO_MCP_ARTIFACT_ROOT=~/workspace/logs/artifacts   # Optional: SQL + result artifact root (default: ~/.igloo_mcp/logs/artifacts for global, or <repo>/logs/artifacts for repo)
export IGLOO_MCP_CACHE_ROOT=~/workspace/logs/cache          # Optional: Override cache directory (default: <artifact_root>/cache)
export IGLOO_MCP_CACHE_MODE=enabled                        # Optional: enabled|refresh|read_only|disabled (default: enabled)
export IGLOO_MCP_CACHE_MAX_ROWS=5000                       # Optional: Max rows to store per result (default: 5000)
export IGLOO_MCP_LOG_SCOPE=global                          # Optional: Log scope: global|repo (default: global)
export IGLOO_MCP_NAMESPACED_LOGS=false                     # Optional: When true, use logs/igloo_mcp/... namespace (default: false)

# Living Reports (optional - defaults provided)
export IGLOO_MCP_REPORTS_ROOT=~/.igloo-mcp/reports  # Optional: Root directory for living reports (default: ~/.igloo_mcp/reports for global scope, or <repo>/reports for repo scope)

# Catalog Storage (optional - defaults provided)
export IGLOO_MCP_CATALOG_ROOT=~/.igloo-mcp/catalogs  # Optional: Root directory for catalog storage (default: ~/.igloo_mcp/catalogs for global scope, or <repo>/catalogs for repo scope)

 # MCP server settings
 export MCP_SERVER_HOST=localhost
 export MCP_SERVER_PORT=3000
 ```

 ### 2. Configuration File

 Create `~/.igloo-mcp/config.yml`:

 ```yaml
 # Snowflake connection configuration
 snowflake:
   profile: "my-profile"          # Default profile name
   warehouse: "COMPUTE_WH"        # Default warehouse
   database: "MY_DB"              # Default database
   schema: "PUBLIC"               # Default schema
   role: "MY_ROLE"                # Default role

 # Catalog settings
 catalog:
   output_dir: "./data_catalogue" # Where to save catalog files
   format: "jsonl"                # Output format: json, jsonl, csv
   max_parallel: 4                # Parallel processing limit

 # Lineage settings
 lineage:
   cache_dir: "./lineage_cache"   # Cache directory for lineage data
   max_depth: 5                   # Maximum lineage depth
   include_views: true            # Include views in lineage
   include_external: false        # Include external tables

# Dependency graph settings
 dependencies:
   output_dir: "./dependencies"   # Output directory
   format: "dot"                  # Graph format: dot, json, mermaid
   include_system: false          # Include system objects

 # MCP server settings
 mcp:
   host: "localhost"              # Server bind address
   port: 3000                     # Server port
   log_level: "INFO"              # Logging level
   timeout: 30                    # Request timeout in seconds
 ```

> **Note**: Build catalog outputs always include DDL; no additional flag is required.

 ### 3. MCP Server Arguments

 Override settings when starting the MCP server:

 ```bash
 # Start MCP server with specific profile
 igloo-mcp --profile prod-profile

 # Set environment variables for MCP session
 export SNOWFLAKE_WAREHOUSE=LARGE_WH
 export SNOWFLAKE_DATABASE=PROD_DB
 igloo-mcp
 ```

 ### 4. Python API Configuration

 Configure directly in Python code:

 ```python
 from igloo_mcp import CatalogService, QueryService
from igloo_mcp.config import Config, SnowflakeConfig

 # Create custom configuration
 config = Config(
     snowflake=SnowflakeConfig(
         profile="prod-profile",
         warehouse="LARGE_WH",
         database="PROD_DB"
     )
 )

 # Use with services
 catalog_service = CatalogService(config=config)
 query_service = QueryService(config=config)
 ```

 ## Profile Management

 ### Snowflake CLI Profiles

 Igloo MCP uses Snowflake CLI profiles for authentication. Configure them with:

 ```bash
 # List existing profiles
 snow connection list

 # Add a new profile
 snow connection add --connection-name my-profile \
   --account myaccount.us-east-1 \
   --user myuser \
   --authenticator externalbrowser

 # Test a profile via MCP
 # In your AI assistant, ask: "Test my Snowflake connection"
 # Or use the Python API:
 # python -c "from igloo_mcp import QueryService; QueryService(profile='my-profile')"
 ```

 ### Profile Locations

 - **macOS/Linux**: `~/.snowflake/config.toml`
 - **Windows**: `%USERPROFILE%\.snowflake\config.toml`

## Output Directory Structure

Igloo MCP creates the following directory structure:

```
project-root/
├── data_catalogue/           # Catalog outputs
│   ├── databases.json        # Database metadata
│   ├── schemas.jsonl         # Schema metadata
│   ├── tables.jsonl          # Table metadata
│   └── views.jsonl           # View metadata
├── lineage_cache/            # Cached lineage data
├── dependencies/             # Dependency graphs
│   └── dependency_graph.dot  # GraphViz format
└── logs/                     # Query history + artifacts (ignored by git)
    ├── doc.jsonl             # JSONL history (success/timeout/error/cache_hit)
    ├── artifacts/
    │   ├── queries/by_sha/   # Full SQL text stored once per SHA-256
    │   └── cache/<key>/      # Result manifests + CSV/JSON rows
    └── catalog/              # (optional) cached catalog exports
```

## Advanced Configuration

All environment variables below are **optional**. Igloo MCP provides sensible defaults for all paths and settings.

- **History enable/disable**: `IGLOO_MCP_QUERY_HISTORY` is optional. If unset, defaults to `~/.igloo_mcp/logs/doc.jsonl` (global scope) or `<repo>/logs/doc.jsonl` (repo scope). Set to a custom path or to `disabled`/`off`/`false`/`0` to skip history writes entirely.
- **Log scope**: `IGLOO_MCP_LOG_SCOPE=global|repo` is optional (default: `global`). Chooses between the global logs directory (`~/.igloo_mcp/logs/...`) and repo-local logs (`<repo>/logs/...`).
- **Namespacing**: `IGLOO_MCP_NAMESPACED_LOGS` is optional (default: `false`). Set to `true` to insert an `igloo_mcp` namespace (e.g., `logs/igloo_mcp/doc.jsonl`) for easier sharing without collisions.
- **Artifact root**: `IGLOO_MCP_ARTIFACT_ROOT` is optional. If unset, defaults to `~/.igloo_mcp/logs/artifacts` (global) or `<repo>/logs/artifacts` (repo scope). Controls where SQL text and cache folders live.
- **Reports root**: `IGLOO_MCP_REPORTS_ROOT` is optional. If unset, defaults to `~/.igloo_mcp/reports` (global) or `<repo>/reports` (repo scope). Can also be derived from instance-specific history/artifact paths.
- **Result cache**: `IGLOO_MCP_CACHE_MODE=enabled|refresh|read_only|disabled` toggles caching. Set `refresh` to bypass the cache while still writing new results; `disabled` skips both lookup and storage. Limit the stored payload size with `IGLOO_MCP_CACHE_MAX_ROWS` (default 5 000 rows per execution).
- **Cache directory override**: use `IGLOO_MCP_CACHE_ROOT` to relocate the cache away from the artifact root (e.g., onto a faster disk).

Each execution writes an `audit_info` block and history record that link together the execution ID, session context, and cached manifest path so you can trace queries long after they run.

### Custom SQL Permissions

 Ensure your Snowflake role has these permissions:

 ```sql
 -- Required for catalog operations
 GRANT USAGE ON WAREHOUSE <warehouse> TO ROLE <role>;
 GRANT USAGE ON DATABASE <database> TO ROLE <role>;
 GRANT USAGE ON SCHEMA <database>.<schema> TO ROLE <role>;
 GRANT SELECT ON ALL TABLES IN SCHEMA <database>.<schema> TO ROLE <role>;
 GRANT SELECT ON ALL VIEWS IN SCHEMA <database>.<schema> TO ROLE <role>;

 -- Required for INFORMATION_SCHEMA access
 GRANT SELECT ON ALL TABLES IN SCHEMA INFORMATION_SCHEMA TO ROLE <role>;
 GRANT SELECT ON ALL VIEWS IN SCHEMA INFORMATION_SCHEMA TO ROLE <role>;

 -- Optional: For ACCOUNT_USAGE access (better metadata)
 GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE <role>;
 ```

 ### Proxy Configuration

 For corporate environments with proxies:

 ```bash
 export HTTP_PROXY=http://proxy.company.com:8080
 export HTTPS_PROXY=http://proxy.company.com:8080
 export NO_PROXY=.company.com,localhost,127.0.0.1
 ```

 ### Timeouts and Retries

 Configure connection behavior:

 ```yaml
 # In config.yml
 snowflake:
   connection_timeout: 30      # Connection timeout in seconds
   retry_count: 3              # Number of retries
   retry_delay: 1              # Delay between retries
 ```

 ## Troubleshooting

 ### Configuration Not Found

 ```bash
 # Check if config file exists
 ls -la ~/.igloo-mcp/config.yml

 # Validate YAML syntax
 python -c "import yaml; yaml.safe_load(open('~/.igloo-mcp/config.yml'))"
 ```

 ### Profile Issues

 ```bash
 # Test Snowflake CLI directly
 snow sql -q "SELECT CURRENT_USER()" --connection my-profile

 # Check profile configuration
 snow connection list
 cat ~/.snowflake/config.toml
 ```

 ### Permission Errors

 Common permission issues:
 - Missing `USAGE` on warehouse/database/schema
 - No `SELECT` on INFORMATION_SCHEMA
 - Role not granted to user

 Check with:
 ```sql
 SHOW GRANTS TO ROLE <your_role>;
 SHOW GRANTS TO USER <your_user>;
 ```

### Unified Storage Structure

By default, all igloo-mcp data is stored in a unified directory structure:

```
~/.igloo-mcp/                    # Global storage (default)
├── logs/
│   └── query_history.jsonl     # Query execution history
├── artifacts/                   # Query artifacts and cache
│   ├── cache/                   # Cached query results
│   └── sql/                     # SQL statement archives
├── catalogs/                    # Catalog storage (per-database)
│   ├── account/                 # Account-wide catalogs
│   │   ├── catalog.json
│   │   └── catalog_summary.json
│   ├── ANALYTICS/               # Per-database catalogs
│   │   ├── catalog.json
│   │   ├── catalog_summary.json
│   │   └── _catalog_metadata.json  # Incremental update metadata
│   ├── PRODUCT/
│   │   ├── catalog.json
│   │   ├── catalog_summary.json
│   │   └── _catalog_metadata.json
│   └── current/                 # Current database (when database not specified)
│       ├── catalog.json
│       ├── catalog_summary.json
│       └── _catalog_metadata.json
└── reports/                     # Living reports
    ├── index.jsonl              # Report index
    └── by_id/                   # Individual report storage
        └── {report-id}/
            ├── outline.json
            ├── audit.jsonl
            └── backups/
```

For separate MCP server instances (e.g., production vs experimental):

```
~/.igloo-mcp/                    # Production instance
~/.igloo-mcp-experimental/       # Experimental instance
```

Each instance maintains its own isolated storage to prevent conflicts.

#### Configuring Storage Scope

Use `IGLOO_MCP_LOG_SCOPE` to control storage location:

- `global` (default): Store in `~/.igloo-mcp/` regardless of working directory
- `repo`: Store in current repository's directory structure

Example for repository-scoped storage:
```bash
export IGLOO_MCP_LOG_SCOPE=repo
# Storage will be in: <repo-root>/logs/, <repo-root>/artifacts/, <repo-root>/catalogs/, <repo-root>/reports/
```

#### Catalog Storage

Catalogs are automatically saved to **unified storage** by default for centralized management and incremental updates.

##### Default Unified Storage Behavior

When you run `build_catalog` without specifying `output_dir`, catalogs are automatically saved to:

- **Per-database**: `~/.igloo_mcp/catalogs/{database_name}/`
  - Example: `~/.igloo_mcp/catalogs/ANALYTICS/`
- **Account-wide**: `~/.igloo_mcp/catalogs/account/` (when `account=true`)
- **Current database**: `~/.igloo_mcp/catalogs/current/` (when database is not specified)

Each database folder contains:
- `catalog.json` or `catalog.jsonl` - Full catalog metadata with all objects
- `catalog_summary.json` - Summary statistics and totals
- `_catalog_metadata.json` - Metadata for incremental updates (per-database only)

##### Benefits of Unified Storage

1. **Centralized Management**: All catalogs organized in one location by database
2. **Incremental Updates**: Metadata files track `last_build` timestamps for efficient refreshes
3. **Per-Database Tracking**: Each database maintains independent metadata for change detection
4. **Consistent Structure**: Standardized organization makes it easy to find and manage catalogs

##### Customizing Catalog Storage

**Option 1: Override Catalog Root Directory**

Set `IGLOO_MCP_CATALOG_ROOT` to change where unified storage saves catalogs:

```bash
# Use custom root directory for all catalogs
export IGLOO_MCP_CATALOG_ROOT=/shared/catalogs

# Now build_catalog saves to /shared/catalogs/{database}/
build_catalog(database="ANALYTICS")
```

**Option 2: Use Custom Output Directory**

Explicitly specify `output_dir` to bypass unified storage entirely:

```python
# Uses unified storage (default) - saves to ~/.igloo_mcp/catalogs/ANALYTICS/
build_catalog(database="ANALYTICS")

# Uses custom directory - saves to ./my_custom_catalog/
build_catalog(
    database="ANALYTICS",
    output_dir="./my_custom_catalog"
)

# Use absolute path
build_catalog(
    database="ANALYTICS",
    output_dir="/project/catalogs/analytics"
)
```

**Option 3: Repository-Scoped Storage**

Set `IGLOO_MCP_LOG_SCOPE=repo` to use repository-local storage:

```bash
export IGLOO_MCP_LOG_SCOPE=repo
# Catalogs save to <repo-root>/catalogs/{database}/
```

##### Metadata Files for Incremental Updates

The `_catalog_metadata.json` file contains:
- `last_build`: Timestamp of last catalog build
- `last_full_refresh`: Timestamp of last full refresh
- `database`: Database name
- `total_objects`: Total count of cataloged objects
- Per-object-type counts (tables, views, functions, etc.)

This metadata enables incremental catalog updates that only process changed objects, significantly faster than full rebuilds.

##### Finding Your Catalogs

```bash
# List all databases with catalogs
ls ~/.igloo_mcp/catalogs/

# View catalog for specific database
ls ~/.igloo_mcp/catalogs/ANALYTICS/

# Check metadata for incremental updates
cat ~/.igloo_mcp/catalogs/ANALYTICS/_catalog_metadata.json
```

## See Also

- [Getting Started Guide](getting-started.md) - Quick start overview
- [Installation Guide](installation.md) - Installation and profile setup
- [Authentication Guide](authentication.md) - Authentication options
- [MCP Integration Guide](mcp-integration.md) - MCP client configuration
- [API Reference](api-reference.md) - Complete tool documentation
