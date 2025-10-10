# Catalog Building Examples

This document provides real examples of catalog building with igloo-mcp, showing actual output and usage patterns.

## Basic Catalog Building

### Single Database Catalog

```bash
# Build catalog for a specific database
{
  "tool": "build_catalog",
  "arguments": {
    "database": "PIPELINE_V2_GROOT_DB",
    "output_dir": "./catalog",
    "account": false,
    "format": "json"
  }
}
```

**Expected Output**:
```json
{
  "status": "success",
  "output_dir": "./catalog",
  "database": "PIPELINE_V2_GROOT_DB",
  "account_scope": false,
  "format": "json",
  "totals": {
    "databases": 1,
    "schemas": 8,
    "tables": 440,
    "views": 199,
    "materialized_views": 36,
    "dynamic_tables": 50,
    "tasks": 81,
    "functions": 10,
    "procedures": 36,
    "columns": 6995
  }
}
```

### Account-Wide Catalog

```bash
# Build catalog for entire account
{
  "tool": "build_catalog",
  "arguments": {
    "output_dir": "./account_catalog",
    "account": true,
    "format": "json"
  }
}
```

**Expected Output**:
```json
{
  "status": "success",
  "output_dir": "./account_catalog",
  "database": "current",
  "account_scope": true,
  "format": "json",
  "totals": {
    "databases": 13,
    "schemas": 8,
    "tables": 409,
    "views": 128,
    "materialized_views": 36,
    "dynamic_tables": 50,
    "tasks": 81,
    "functions": 10,
    "procedures": 36,
    "columns": 6995
  }
}
```

## Catalog Summary

### Get Catalog Statistics

```bash
# Get summary of built catalog
{
  "tool": "get_catalog_summary",
  "arguments": {
    "catalog_dir": "./catalog"
  }
}
```

**Expected Output**:
```json
{
  "status": "success",
  "catalog_dir": "./catalog",
  "summary": {
    "databases": 1,
    "schemas": 8,
    "tables": 440,
    "views": 199,
    "materialized_views": 36,
    "dynamic_tables": 50,
    "tasks": 81,
    "functions": 10,
    "procedures": 36,
    "columns": 6995
  }
}
```

## Real Catalog Data Examples

### Sample Function Data

The catalog includes only user-defined functions. Here's what you'll see:

```json
{
  "functions": [
    {
      "DATABASE_NAME": "PIPELINE_V2_GROOT_DB",
      "SCHEMA_NAME": "PIPELINE_V2_GROOT_SCHEMA",
      "FUNCTION_NAME": "BYTE_ARRAY_TO_HEX",
      "RETURN_TYPE": "VARCHAR(16777216)",
      "LANGUAGE": "PYTHON",
      "COMMENT": null,
      "CREATED": "2024-09-11T12:54:38.733000-07:00",
      "LAST_ALTERED": "2024-09-19T11:38:13.029000-07:00"
    },
    {
      "DATABASE_NAME": "PIPELINE_V2_GROOT_DB",
      "SCHEMA_NAME": "PIPELINE_V2_GROOT_SCHEMA",
      "FUNCTION_NAME": "CALC_TOKEN_AMOUNTS",
      "RETURN_TYPE": "VARIANT",
      "LANGUAGE": "JAVASCRIPT",
      "COMMENT": null,
      "CREATED": "2025-09-05T11:19:15.011000-07:00",
      "LAST_ALTERED": "2025-09-05T11:19:15.011000-07:00"
    }
  ]
}
```

### Sample Table Data

```json
{
  "tables": [
    {
      "name": "DEX_TRADES_STABLE",
      "database_name": "PIPELINE_V2_GROOT_DB",
      "schema_name": "PIPELINE_V2_GROOT_SCHEMA",
      "kind": "TABLE",
      "comment": "Stable table for DEX trades data",
      "cluster_by": null,
      "rows": 1250000,
      "bytes": 450000000,
      "owner": "SECURITYADMIN",
      "created_on": "2024-08-15T10:30:00.000000-07:00",
      "last_altered": "2024-10-05T14:22:15.000000-07:00"
    }
  ]
}
```

### Sample Column Data

```json
{
  "columns": [
    {
      "database_name": "PIPELINE_V2_GROOT_DB",
      "schema_name": "PIPELINE_V2_GROOT_SCHEMA",
      "table_name": "DEX_TRADES_STABLE",
      "column_name": "TRADE_ID",
      "data_type": "VARCHAR(16777216)",
      "is_nullable": "NO",
      "column_default": null,
      "comment": "Unique identifier for the trade"
    },
    {
      "database_name": "PIPELINE_V2_GROOT_DB",
      "schema_name": "PIPELINE_V2_GROOT_SCHEMA",
      "table_name": "DEX_TRADES_STABLE",
      "column_name": "AMOUNT",
      "data_type": "NUMBER(38,18)",
      "is_nullable": "YES",
      "column_default": null,
      "comment": "Trade amount in base token"
    }
  ]
}
```

## Key Points About Catalog Output

### Function Filtering

- **Before Fix**: 1,043 functions (included built-in operators like `!=`, `%`, `*`, `+`, `-`)
- **After Fix**: 10 functions (only user-defined functions)
- **Why**: `INFORMATION_SCHEMA.FUNCTIONS` automatically excludes built-in Snowflake functions

### Comprehensive Coverage

The catalog includes all Snowflake object types:
- **Databases**: All accessible databases
- **Schemas**: All schemas within databases
- **Tables**: Regular tables with metadata
- **Views**: Standard views
- **Materialized Views**: Materialized views for performance
- **Dynamic Tables**: Snowflake's streaming tables
- **Tasks**: Scheduled tasks and workflows
- **Functions**: User-defined functions only
- **Procedures**: Stored procedures
- **Columns**: Detailed column metadata with types, nullability, defaults

### Performance Considerations

- **Query Optimization**: Uses efficient SHOW commands and INFORMATION_SCHEMA queries
- **Filtering**: Proper WHERE clauses to limit scope
- **Ordering**: Results ordered by database, schema, object name
- **JSON Output**: Structured format for easy parsing

## Usage Patterns

### Development Workflow

```bash
# 1. Build catalog for development database
"Build a catalog for DEV_DATABASE"

# 2. Get summary to understand scope
"Get catalog summary for the DEV_DATABASE catalog"

# 3. Explore specific objects
"Show me all functions in DEV_DATABASE"
"List all tables in the PUBLIC schema"
```

### Production Monitoring

```bash
# 1. Build account-wide catalog
"Build a catalog for the entire account"

# 2. Monitor object counts
"Get catalog summary to see total object counts"

# 3. Track changes over time
"Compare this catalog with last month's catalog"
```

### Data Discovery

```bash
# 1. Build comprehensive catalog
"Build a catalog for PROD_DATABASE"

# 2. Explore data structure
"Show me all tables with more than 1 million rows"
"List all functions created in the last 30 days"

# 3. Understand relationships
"Show me all tables that reference the USERS table"
```

## Troubleshooting

### Common Issues

**Issue**: Catalog shows 0 functions
**Solution**: This is expected if you have no user-defined functions. Built-in functions are intentionally excluded.

**Issue**: Catalog takes a long time to build
**Solution**: Use database-specific catalogs instead of account-wide catalogs for large environments.

**Issue**: Missing objects in catalog
**Solution**: Check your Snowflake permissions. You need USAGE on databases/schemas and SELECT on INFORMATION_SCHEMA.

### Performance Tips

1. **Use Database Scope**: Build catalogs for specific databases when possible
2. **Filter Results**: Use the `database` parameter to limit scope
3. **Monitor Size**: Large catalogs may take time to build and process
4. **Cache Results**: Save catalog output for reuse in analysis

---

**Note**: These examples are based on real Snowflake metadata queries. The actual output will vary based on your Snowflake environment, permissions, and object counts.
