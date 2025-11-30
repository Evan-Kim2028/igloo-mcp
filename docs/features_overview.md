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

### 3. Data Lineage Analysis
**Description**: Build and analyze data lineage graphs to understand data flow and dependencies.

**Capabilities**:
- SQL parsing with SQLGlot for dependency extraction
- Bidirectional lineage traversal (upstream/downstream)
- Multiple output formats (text, JSON, HTML, DOT)
- Cross-database lineage resolution
- Lineage caching for performance
- Interactive HTML visualizations

**MCP Tools**: `query_lineage`

**AI Assistant Usage**:
```
"Show me lineage for ANALYTICS.CUSTOMERS going both upstream and downstream"
"Trace data lineage with depth 3"
"Generate an HTML visualization of lineage for MY_TABLE"
```

**Testing Coverage**: ✅ **WELL COVERED**
- Comprehensive lineage tests (`test_lineage.py`, `test_advanced_lineage.py`)
- SQL parsing and dependency extraction
- Graph traversal algorithms
- Multiple output format testing
- Edge case handling

---

### 4. Dependency Graph Generation
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
igloo-mcp  # Shows validation success/failure immediately
export SNOWFLAKE_PROFILE=my-profile  # Clear profile selection

# Profile selection via command line
igloo-mcp --profile my-profile
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
igloo-mcp  # Shows immediate validation feedback

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

## 🔧 Advanced Features

### 7. Column-Level Lineage (Advanced)
**Description**: Track data flow at individual column granularity.

**Capabilities**:
- SQL parsing for column-level dependencies
- Transformation type detection (DIRECT, FUNCTION, AGGREGATE, etc.)
- Confidence scoring for transformations
- Source-to-target column mapping

**Testing Coverage**: ✅ **WELL COVERED**
- Advanced lineage tests cover column parsing
- SQL transformation detection
- Complex query analysis

---

### 8. Cross-Database Lineage (Advanced)
**Description**: Unified lineage analysis across multiple databases.

**Capabilities**:
- Multi-database catalog merging
- Cross-database reference resolution
- Database hub detection
- Boundary analysis

**Testing Coverage**: ⚠️ **PARTIALLY COVERED**
- ✅ Basic cross-database functionality
- ❌ **MISSING**: Multi-database integration testing
- ❌ **MISSING**: Large-scale cross-database scenarios

---

### 9. Impact Analysis (Advanced)
**Description**: Analyze potential impact of changes before implementation.

**Capabilities**:
- Blast radius calculation
- Change impact severity scoring
- Single point of failure detection
- Propagation time analysis

**Testing Coverage**: ✅ **WELL COVERED**
- Impact analysis algorithms tested
- Circular dependency detection
- Missing node handling

---

### 10. Time-Travel Lineage (Advanced)
**Description**: Track lineage evolution over time with snapshots.

**Capabilities**:
- Lineage snapshot capture
- Historical comparison
- Evolution tracking
- Pattern detection

**Testing Coverage**: ✅ **WELL COVERED**
- Snapshot comparison functionality
- Time-travel scenarios tested

---

### 11. External Source Integration (Advanced)
**Description**: Map external data sources including cloud storage.

**Capabilities**:
- S3, Azure Blob, GCS integration
- Stage configuration tracking
- Security analysis
- Access pattern monitoring

**Testing Coverage**: ⚠️ **PARTIALLY COVERED**
- ✅ Basic external source mapping
- ❌ **MISSING**: Full credential handling tests (1 failing test)
- ❌ **MISSING**: Integration with actual cloud storage

---

## 🛡️ Infrastructure Features

### 12. Circuit Breaker Pattern
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

### 13. Health Monitoring
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

### 14. Comprehensive Error Handling
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
- **Total Tests**: 80+ passing tests
- **Test Files**: 7 primary test files
- **Coverage Estimate**: Good coverage of core features

### Coverage by Category

| Feature Category | Coverage Level | Test Quality | Missing Areas |
|------------------|----------------|--------------|---------------|
| **Core CLI** | ✅ Excellent | High | Minor edge cases |
| **Configuration** | ✅ Excellent | High | None significant |
| **MCP Server** | ✅ Excellent | High | Integration scenarios |
| **Basic Lineage** | ✅ Excellent | High | Large graph performance |
| **Infrastructure** | ✅ Excellent | High | None significant |
| **Data Catalog** | ⚠️ Partial | Medium | Large-scale, DDL, incremental |
| **Dependency Graphs** | ⚠️ Partial | Medium | Complex relationships |
| **Advanced Lineage** | ✅ Good | Medium-High | Multi-database scenarios |
| **External Sources** | ⚠️ Partial | Medium | Cloud integration |

### High-Priority Testing Gaps

#### 1. **Catalog Testing** (Priority: HIGH)
```python
# MISSING: Large catalog testing
def test_large_catalog_performance():
    """Test catalog building with 1000+ objects"""

# MISSING: DDL extraction testing
def test_ddl_extraction_concurrent():
    """Test concurrent DDL fetching"""

# MISSING: Incremental updates
def test_incremental_catalog_updates():
    """Test incremental catalog building"""
```

#### 2. **Integration Testing** (Priority: HIGH)
```python
# MISSING: End-to-end MCP workflows
def test_mcp_end_to_end_workflow():
    """Test complete AI assistant workflow"""

# MISSING: Cross-database scenarios
def test_cross_database_lineage_integration():
    """Test lineage across multiple databases"""
```

#### 3. **Performance Testing** (Priority: MEDIUM)
```python
# MISSING: Large dataset handling
def test_large_graph_performance():
    """Test lineage with 10,000+ objects"""

# MISSING: Memory usage testing
def test_memory_usage_large_catalogs():
    """Monitor memory usage during catalog building"""
```

#### 4. **External Integration Testing** (Priority: MEDIUM)
```python
# MISSING: Cloud storage integration
def test_s3_integration():
    """Test S3 bucket mapping and access"""

# MISSING: Credential security
def test_credential_security():
    """Test credential handling security"""
```

### Recommended Testing Improvements

#### 1. **Add Property-Based Testing**
```python
from hypothesis import given, strategies as st

@given(st.text(), st.integers(min_value=1, max_value=100))
def test_catalog_building_properties(database_name, object_count):
    """Property-based testing for catalog building"""
```

#### 2. **Add Load Testing**
```python
def test_concurrent_mcp_requests():
    """Test MCP server under concurrent load"""

def test_large_lineage_graph_traversal():
    """Test lineage traversal with large graphs"""
```

#### 3. **Add Integration Scenarios**
```python
def test_full_data_pipeline_analysis():
    """Test complete data pipeline analysis workflow"""

def test_impact_analysis_real_world():
    """Test impact analysis with realistic scenarios"""
```

#### 4. **Add Error Recovery Testing**
```python
def test_circuit_breaker_recovery_scenarios():
    """Test various circuit breaker recovery patterns"""

def test_partial_failure_handling():
    """Test handling of partial failures in batch operations"""
```

## 🎯 Testing Strategy Recommendations

### Short Term (Next Sprint)
1. **Fix failing external source test** - Address credential handling issue
2. **Add catalog performance tests** - Test with 1000+ objects
3. **Add MCP integration tests** - End-to-end workflows
4. **Add error recovery tests** - Circuit breaker scenarios

### Medium Term (Next Month)
1. **Property-based testing** - Add hypothesis-based tests
2. **Load testing** - Concurrent operations and large datasets
3. **Security testing** - Credential handling and injection prevention
4. **Memory profiling** - Monitor resource usage

### Long Term (Next Quarter)
1. **Automated performance benchmarks** - Regression detection
2. **Chaos engineering** - Fault injection testing
3. **Integration test suite** - Real Snowflake environments
4. **Documentation testing** - Verify all examples work

## 🎉 Conclusion

igloo-mcp provides a comprehensive suite of features for Snowflake data management, with particularly strong coverage in:
- Core CLI functionality
- Circuit breaker and reliability patterns
- Error handling and monitoring
- Basic lineage analysis
- MCP server integration

The testing coverage is solid for core features (~80 passing tests), with room for improvement in:
- Large-scale catalog operations
- Complex dependency scenarios
- External system integrations
- Performance and load testing

The codebase demonstrates excellent software engineering practices with the recent addition of circuit breakers, proper error handling, and comprehensive service layer architecture.

## See Also

- [Getting Started Guide](getting-started.md) - Quick start overview
- [API Reference](api/README.md) - Complete tool documentation
- [Architecture Overview](architecture.md) - System architecture details
- [Configuration Guide](configuration.md) - Configuration options
