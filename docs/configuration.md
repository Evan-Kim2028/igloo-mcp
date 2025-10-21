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
 └── logs/                     # Application logs
 ```

 ## Advanced Configuration

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

 ## Related Documentation

 - [Getting Started Guide](getting-started.md) - Basic setup
 - [Authentication Guide](authentication.md) - Profile setup
 - [MCP Integration](mcp-integration.md) - AI assistant setup
 - [API Reference](api-reference.md) - Tool documentation
