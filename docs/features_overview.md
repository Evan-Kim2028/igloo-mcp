# igloo-mcp Features Overview

## 🚀 Core Features

### 1. SQL Execution & Query Management
**Description**: Direct SQL execution against Snowflake with structured output and error handling.

**Capabilities**:
- Execute arbitrary SQL queries with configurable output formats (JSON, CSV)
- Context-aware execution with warehouse/database/schema/role overrides
- Query result parsing and structured output
- Timeout and error handling with detailed diagnostics

**MCP Tools**: `execute_query`

**AI Assistant Usage**:
```
"Execute this query: SELECT * FROM CUSTOMERS LIMIT 10"
"Run the SQL query in query.sql file"
"Preview the CUSTOMERS table"
```

**Testing Coverage**: ✅ **WELL COVERED**
- Unit tests for SnowCLI wrapper (`test_snow_cli.py`)
- Query parsing and output formatting tests
- Error handling scenarios
- Mock-based testing for different output formats

---

### 2. Data Catalog Generation
**Description**: Comprehensive metadata extraction and cataloging of Snowflake databases.

**Capabilities**:
- Parallel metadata extraction from INFORMATION_SCHEMA and SHOW commands
- Support for tables, views, materialized views, functions, procedures, tasks, dynamic tables
- DDL extraction with concurrency control
- JSON/JSONL output formats with configurable structure
- **Unified storage**: Automatic organization in `~/.igloo_mcp/catalogs/{database}/` by default
- **Per-database catalogs**: Each database maintains its own catalog folder with metadata
- Incremental catalog updates with change tracking via `_catalog_metadata.json`
- Cross-database catalog generation
- Custom path support: Override unified storage with explicit `output_dir` parameter

**MCP Tools**: `build_catalog`, `get_catalog_summary`, `search_catalog`

**AI Assistant Usage**:
```
"Build a catalog for the ANALYTICS database"
"Create a comprehensive catalog with DDL for all databases"
"Show me the catalog summary"
```

**Testing Coverage**: ⚠️ **PARTIALLY COVERED**
- ✅ Basic catalog building functionality
- ✅ Service layer architecture (`test_services.py`)
- ❌ **MISSING**: Large-scale catalog testing
- ❌ **MISSING**: DDL extraction testing
- ❌ **MISSING**: Incremental update testing
- ❌ **MISSING**: Cross-database catalog testing

---

### 3. Dependency Graph Generation
**Description**: Create visual dependency graphs showing object relationships.

**Capabilities**:
- Object relationship mapping from metadata
- DOT format output for Graphviz rendering
- JSON output for programmatic consumption
- Circular dependency detection
- Hierarchical visualization support

**MCP Tools**: `build_dependency_graph`

**AI Assistant Usage**:
```
"Build a dependency graph for the ANALYTICS database"
"Create a dependency graph in DOT format"
"Show me object dependencies as a graph"
```

**Testing Coverage**: ⚠️ **PARTIALLY COVERED**
- ✅ Basic dependency graph construction
- ❌ **MISSING**: Complex relationship testing
- ❌ **MISSING**: Circular dependency detection testing
- ❌ **MISSING**: Large graph performance testing

---

### 5. Configuration Management & Profile Validation
**Description**: Robust configuration system with advanced profile validation and health monitoring.

**Core Capabilities**:
- YAML-based configuration files
- Environment variable overrides
- Multiple Snowflake profile support
- Default value cascading
- Configuration validation

**Profile Validation Features**:
- **Startup validation**: Profile issues detected before server becomes available
- **Clear error messages**: No more confusing timeout errors
- **MCP-compliant error responses**: Structured error format with specific error codes
- **Real-time diagnostics**: Health monitoring tools for ongoing validation
- **Actionable guidance**: Specific next steps for fixing configuration issues
- **Profile health caching**: Efficient validation with TTL-based caching

**MCP Server Usage**:
```bash
# Start MCP server with profile validation (v2.0+)
igloo_mcp  # Shows validation success/failure immediately
export SNOWFLAKE_PROFILE=my-profile  # Clear profile selection

# Profile selection via command line
igloo_mcp --profile my-profile
```

**MCP Tools**:
- `health_check`: Comprehensive server health status (includes profile validation and resource availability)

**Error Handling Improvements**:
**Benefits**:
- Immediate, specific error messages with context
- No generic timeout errors

**Example Enhanced Error Response**:
```json
{
  "error": {
    "code": -32004,
    "message": "Snowflake profile validation failed",
    "data": {
      "profile_name": "default",
      "available_profiles": ["dev", "prod"],
      "suggestion": "Set SNOWFLAKE_PROFILE environment variable"
    }
  }
}
```

**Testing Coverage**: ✅ **EXCELLENT COVERAGE**
- Configuration loading and validation (`test_config.py`)
- Environment variable handling
- YAML serialization/deserialization
- Profile management
- Health monitoring tests (`test_mcp_health.py`)
- Profile validation tests
- MCP error response testing

---

### 6. MCP Server Integration
**Description**: Model Context Protocol server for AI assistant integration with advanced health monitoring and reliability.

**Core Capabilities**:
- JSON-RPC 2.0 protocol implementation
- Tool-based interface for AI assistants
- Async operation support
- VS Code, Cursor, Claude Code compatibility
- Secure authentication through existing Snowflake CLI profiles

**Reliability Features**:
- **Proactive validation**: Profile validation during server startup lifecycle
- **Circuit breaker pattern**: Fault-tolerant Snowflake operations
- **Health monitoring**: Real-time component health tracking
- **Structured error responses**: MCP-compliant error codes and context
- **Resource management**: Dependency tracking and availability monitoring
- **Graceful degradation**: Partial functionality when components fail

**MCP Server Administration**:
```bash
# Startup with validation
igloo_mcp  # Shows immediate validation feedback

# Expected successful startup:
# ✓ Snowflake profile validation successful: dev
# ✓ Profile health check passed for: dev
# ✓ Snowflake connection health check passed
# Starting FastMCP server using transport=stdio
```

**MCP Tools**:
- **Core tools**: All existing tools (execute_query, build_catalog, etc.)
- **Diagnostic tools**: health_check, test_connection

**Reliability Infrastructure**:
- **MCPHealthMonitor**: Comprehensive health status tracking
- **MCPResourceManager**: Resource dependency management
- **Error categorization**: Connection, Permission, Timeout, Configuration errors
- **Performance optimization**: Caching with TTL for health checks

**Testing Coverage**: ✅ **EXCELLENT COVERAGE**
- MCP server functionality (`test_mcp_server.py`)
- Tool registration and execution
- Error handling and response formatting
- Mock-based testing for external dependencies
- Health monitoring system tests
- Circuit breaker pattern tests
- Resource management tests
- Profile validation integration tests

---

## 🛡️ Infrastructure Features

### 7. Circuit Breaker Pattern
**Description**: Prevent cascade failures with intelligent failure handling.

**Capabilities**:
- Configurable failure thresholds
- Exponential backoff
- State management (closed, open, half-open)
- Decorator support for easy application

**Testing Coverage**: ✅ **EXCELLENT COVERAGE**
- Comprehensive circuit breaker tests (`test_circuit_breaker.py`)
- All states and transitions tested
- Recovery scenarios covered
- Error categorization testing

---

### 8. Health Monitoring
**Description**: System health monitoring and diagnostics.

**Capabilities**:
- Connection health checks
- Circuit breaker status reporting
- System metrics collection
- Health endpoint for monitoring

**Testing Coverage**: ✅ **WELL COVERED**
- Health status reporting (`test_services.py`)
- Circuit breaker integration
- Error state handling

---

### 9. Comprehensive Error Handling
**Description**: Structured error handling with categorization and context.

**Capabilities**:
- Error categorization (Connection, Permission, Timeout)
- Context-aware error reporting
- Error aggregation for batch operations
- Safe execution patterns with fallbacks

**Testing Coverage**: ✅ **EXCELLENT COVERAGE**
- Error handling strategies (`test_error_handling.py`)
- Error categorization testing
- Context preservation
- Fallback mechanism testing

---

## 📊 Testing Coverage Summary

### Overall Test Statistics
- **Total Tests**: 1264+ passing tests
- **Test Files**: 91 test files
- **Coverage**: 80% minimum threshold enforced in CI
- **Test Frameworks**: pytest, pytest-asyncio, hypothesis (property-based), pytest-xdist (parallel)

### Coverage by Category

| Feature Category | Coverage Level | Notes |
|------------------|----------------|-------|
| **Configuration** | ✅ Excellent | Comprehensive validation testing |
| **MCP Server** | ✅ Excellent | Tool registration, error handling |
| **Query Execution** | ✅ Excellent | Timeout, retry, result modes |
| **Living Reports** | ✅ Excellent | Full CRUD + rendering |
| **Infrastructure** | ✅ Excellent | Circuit breaker, error handling |
| **Health Monitoring** | ✅ Excellent | Profile validation, diagnostics |
| **Data Catalog** | ✅ Good | Core functionality covered |
| **Dependency Graphs** | ⚠️ Partial | Basic graph construction |

## See Also

- [Getting Started Guide](getting-started.md) - Quick start overview
- [API Reference](api/README.md) - Complete tool documentation
- [Architecture Overview](architecture/system-overview.md) - System architecture details
- [Configuration Guide](configuration.md) - Configuration options
