# MCP Server User Guide

## What is the MCP Server?

The MCP (Model Context Protocol) server is the primary interface for Igloo MCP. It enables AI assistants to interact with your Snowflake database, acting as a bridge between natural language requests and structured database operations.

### Key Benefits

- **Natural Language Queries**: Ask questions in plain English, get SQL results
- **Intelligent Context**: AI understands your schema, relationships, and data lineage
- **Secure Integration**: Uses existing Snowflake CLI authentication
- **Tool-based Safety**: Structured tools prevent arbitrary code execution
- **Multi-Client Support**: Works with VS Code, Cursor, Claude Code, and other MCP clients

### How It Works

The MCP server exposes Snowflake functionality as "tools" that AI assistants can call. When you ask an AI assistant a question about your data, it:

1. Interprets your natural language request
2. Selects the appropriate MCP tool(s)
3. Executes the tool with proper parameters
4. Returns formatted, understandable results

For example, asking "What tables are in my database?" triggers the AI to use the `execute_query` tool with an appropriate SQL query.

## Quick Start

### Prerequisites

1. **Install Igloo MCP**: All MCP functionality is included by default:
   ```bash
   # Standard installation (includes MCP server)
   pip install igloo-mcp
   ```

   Or with uv:
   ```bash
   uv pip install igloo-mcp
   ```

2. **Configure Snowflake Connection**: Set up a Snowflake CLI connection profile
   ```bash
   uv run snow connection add \
     --connection-name my-profile \
     --account your-account \
     --user your-username \
     --private-key /path/to/your/rsa_key.p8 \
     --warehouse your-warehouse \
     --database your-database \
     --schema your-schema \
     --default
   ```

2. **Set Environment Variable** (optional):
   ```bash
   export SNOWFLAKE_PROFILE=my-profile
   ```

### Starting the MCP Server

**For AI Assistant Integration** (Recommended):

The MCP server starts automatically when your AI assistant connects. Simply configure your AI assistant's MCP settings (see Configuration section below) and the server will start on-demand.

**For Manual Testing** (Advanced):

```bash
igloo-mcp
```

This starts the server in stdio mode, which is useful for debugging but not needed for normal AI assistant usage. Press `Ctrl+C` to stop the server.

## Available Tools

The MCP server exposes the following tools to AI assistants:

### Core Data Tools
- **`execute_query`** - Execute SQL queries against Snowflake
  - Parameters: `query`, `warehouse`, `database`, `schema`, `role`
  - Returns: Query results as JSON

- **`preview_table`** - Preview table contents
  - Parameters: `table_name`, `limit`, `warehouse`, `database`, `schema`, `role`
  - Returns: Table preview data

### Catalog and Metadata Tools
- **`build_catalog`** - Generate comprehensive data catalogs
  - Parameters: `output_dir`, `database`, `account`, `format`, `include_ddl`
  - Returns: Catalog metadata summary

- **`get_catalog_summary`** - Retrieve existing catalog summaries
  - Parameters: `catalog_dir`
  - Returns: Catalog statistics and metadata

### Analysis Tools
- **`query_lineage`** - Analyze data lineage and dependencies
  - Parameters: `object_name`, `direction`, `depth`, `format`, `catalog_dir`, `cache_dir`
  - Returns: Lineage graph in text/JSON/HTML format

- **`build_dependency_graph`** - Create object dependency graphs
  - Parameters: `database`, `schema`, `account`, `format`
  - Returns: Dependency graph in JSON or DOT format

### Utility Tools
- **`test_connection`** - Test Snowflake connection
  - Parameters: None
  - Returns: Connection status

## Configuration

### VS Code / Cursor Configuration

Create or update your MCP configuration file (usually `~/.vscode/mcp.json`):

```json
{
  "mcpServers": {
    "igloo-tools": {
      "command": "uv",
      "args": ["run", "igloo-mcp"],
      "cwd": "/path/to/your/igloo-mcp"
    }
  }
}
```

### Claude Code Configuration

Add to your Claude Code MCP settings:

```json
{
  "mcp": {
    "igloo-tools": {
      "command": "uv",
      "args": ["run", "igloo-mcp"],
      "cwd": "/path/to/your/igloo-mcp"
    }
  }
}
```

### Environment Variables

The MCP server respects the following environment variables:

- `SNOWFLAKE_PROFILE` - Snowflake connection profile to use
- `SNOWFLAKE_WAREHOUSE` - Default warehouse
- `SNOWFLAKE_DATABASE` - Default database
- `SNOWFLAKE_SCHEMA` - Default schema
- `SNOWFLAKE_ROLE` - Default role

## Real-World Usage Examples

Once configured, you can interact with your Snowflake data naturally through your AI assistant.

### Example Conversations

#### Getting Started
```
You: "Test my Snowflake connection"
AI: [Executes test_connection tool]
AI: "Connection successful! You're connected to account XYZ with warehouse COMPUTE_WH."

You: "What databases do I have access to?"
AI: [Executes query to list databases]
AI: "You have access to 5 databases: DEFI_SAMPLE_DB, PIPELINE_V2_GROOT_DB, ANALYTICS_DB, STAGING, and TEST_DB."
```

#### Data Discovery
```
You: "I need to understand the structure of our DEX trading data"
AI: [Builds catalog for DeFi-related objects]
AI: "I found the main DEX_TRADES_STABLE table with 224M+ records. Key tables are:
     - DEX_TRADES_STABLE (main fact table with all trades)
     - COIN_INFO (cryptocurrency metadata)
     - BTC_DEX_TRADES_USD_DT (BTC-focused analytics)
     Would you like me to show you the schema for any of these?"

You: "Yes, show me DEX_TRADES_STABLE and how it connects to other tables"
AI: [Queries lineage for DEX_TRADES_STABLE table]
AI: "The DEX_TRADES_STABLE table has 23 columns tracking trades across 6 protocols:
     [Shows schema]

     It connects to:
     - Downstream: FILTERED_DEX_TRADES_VIEW, BTC_DEX_TRADES_USD_DT
     - Upstream: OBJECT_PARQUET2, raw DEX events"
```

### Common Use Cases

#### 1. Data Exploration & Discovery
- **Schema Understanding**: "Show me all tables related to customer orders with their column definitions"
- **Data Sampling**: "Preview 50 rows from the TRANSACTIONS table, focusing on recent data"
- **Data Profiling**: "What's the date range and row count for the DEX_TRADES_STABLE table?"
- **Relationship Discovery**: "How are the DEX_TRADES_STABLE and COIN_INFO tables connected?"

#### 2. Catalog & Documentation
- **Full Catalog Build**: "Create a complete data catalog for the ANALYTICS database"
- **Targeted Documentation**: "Document all views and tables in the REPORTING schema"
- **Dependency Mapping**: "Generate a dependency graph showing how our KPI views are built"
- **Impact Analysis**: "What will be affected if I modify the USER_DIMENSION table?"

#### 3. Lineage & Impact Analysis
- **Source Tracing**: "Where does the data in REVENUE_SUMMARY ultimately come from?"
- **Impact Assessment**: "Show me everything downstream from RAW_EVENTS table"
- **Data Flow Visualization**: "Trace how customer data flows from source to dashboard"
- **Dependency Depth**: "Show 3 levels of dependencies for MONTHLY_METRICS view"

#### 4. Query Development & Execution
- **Ad-hoc Analysis**: "Count unique customers who made purchases last month"
- **Complex Queries**: "Join DEX_TRADES_STABLE with COIN_INFO and calculate average trade size by protocol"
- **Data Validation**: "Check for null values in critical columns of TRANSACTIONS table"
- **Performance Testing**: "Run this query and tell me how many rows it returns: [SQL]"

#### 5. Troubleshooting & Debugging
- **Missing Data**: "Why might the DAILY_SUMMARY table be missing data for yesterday?"
- **Schema Changes**: "Compare the current schema of DEX_TRADES_STABLE with what's documented"
- **Permission Issues**: "What tables can I access in the FINANCE database?"
- **Query Optimization**: "This query is slow, can you help me understand its dependencies?"

## Troubleshooting

### Connection Issues
1. Verify your Snowflake CLI connection works:
   ```bash
   # Test Snowflake connection directly
   snow sql -q "SELECT CURRENT_USER()" --connection my-profile
   
   # Or test via Python API
   python -c "from igloo_mcp import QueryService; QueryService(profile='my-profile')"
   ```

2. Check that your profile is configured correctly:
   ```bash
   uv run snow connection list
   ```

3. Ensure required environment variables are set or use CLI flags

### MCP Client Issues
1. **VS Code/Cursor**: Restart the editor after configuration changes
2. **Claude Code**: Reload your MCP settings
3. **Permission Errors**: Ensure the MCP server has access to your Snowflake credentials

### Performance Issues
- Use specific database/schema parameters to limit scan scope
- Set appropriate concurrency limits for large catalogs
- Use incremental catalog builds when possible

### Common Error Messages
- `"Object not found in lineage graph"` - Run `build_catalog` first
- `"Connection failed"` - Check your Snowflake CLI configuration
- `"Permission denied"` - Ensure your role has necessary privileges

## Security Considerations

- The MCP server uses the same authentication as your Snowflake CLI
- No credentials are stored in the MCP server configuration
- All database access is controlled by your Snowflake role permissions
- The server only exposes tools you've explicitly configured

## Support

For issues with the MCP server:
1. Check the troubleshooting section above
2. Verify your Snowflake CLI connection works independently
3. Review the MCP client logs for detailed error messages
4. Check that you're using compatible versions of all components

The MCP server exposes Igloo MCP functionality through structured tools, so most issues can be diagnosed by checking the service layer or testing with the Python API directly.
