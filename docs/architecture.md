# Igloo MCP Architecture (v2.0.0)

> **Overview**: Igloo MCP uses a layered service architecture that provides AI assistant integration through MCP (Model Context Protocol) and a Python API for programmatic access.

## Architectural Principles

### 1. Layered Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                  Client Applications                        │
│              (AI Assistants, Python API)                    │
├─────────────────────────────────────────────────────────────┤
│                  Presentation Layer                         │
│                    (MCP Server)                             │
├─────────────────────────────────────────────────────────────┤
│                   Service Layer                             │
│           (CatalogService, QueryService, etc.)             │
├─────────────────────────────────────────────────────────────┤
│                Infrastructure Layer                         │
│        (Snowflake Labs MCP, Snow CLI, Configuration)       │
├─────────────────────────────────────────────────────────────┤
│                  Snowflake Platform                         │
└─────────────────────────────────────────────────────────────┘
```

### 2. Separation of Concerns
- **Business Logic**: Isolated in service layer
- **Infrastructure**: Handled by Snowflake Labs MCP
- **Configuration**: Centralized and immutable
- **Error Handling**: Consistent across all layers

### 3. Dependency Injection
- Services receive dependencies through constructor injection
- Configuration is provided at service initialization
- No global state or singletons in business logic

## Core Components

### Service Layer (`src/igloo_mcp/service_layer/`)

The service layer provides the core business logic for Igloo MCP operations:

```python
# Service interfaces are clean and focused
class CatalogService:
    def __init__(self, *, config: Config | None = None)
    def build_catalog(self, database: str = None, schema: str = None) -> dict
    def load_summary(self, catalog_dir: str) -> dict

class QueryService:
    def __init__(self, *, config: Config | None = None)
    def execute_with_service(self, service, statement: str, **context) -> dict
    def session_from_mapping(self, overrides: dict) -> SessionContext

class DependencyService:
    def __init__(self, *, config: Config | None = None)
    def build_dependency_graph(self, **filters) -> dict
```

**Design Patterns**:
- **Dependency Injection**: All services receive configuration through constructor
- **Strategy Pattern**: Different execution strategies for sync/async operations
- **Factory Pattern**: Session context creation from various inputs

### MCP Integration (`src/igloo_mcp/mcp_server.py`)

The MCP server provides AI assistant integration through a layered approach:

```python
# Layered MCP Architecture
┌─────────────────────────────────────┐
│     Igloo MCP MCP Layer         │
│  • catalog, lineage, dependencies   │
│  • Enhanced query tools             │
│  • Custom diagnostics               │
├─────────────────────────────────────┤
│    Snowflake Labs MCP Layer         │
│  • Authentication & security        │
│  • Core Snowflake operations        │
│  • Connection management            │
└─────────────────────────────────────┘
```

**Key Features**:
- **Health Monitoring**: Comprehensive health checks and diagnostics
- **Error Handling**: Structured error responses with context
- **Resource Management**: Efficient resource lifecycle management
- **Profile Validation**: Enhanced Snowflake profile validation

### Configuration Management (`src/igloo_mcp/config.py`)

Centralized configuration with override precedence:

```python
# Configuration Hierarchy (highest to lowest precedence)
1. CLI Arguments        (--warehouse COMPUTE_WH)
2. Environment Variables (SNOWFLAKE_WAREHOUSE=COMPUTE_WH)
3. Configuration File   (config.yml: warehouse: COMPUTE_WH)
4. Profile Defaults     (Snow CLI profile settings)
5. System Defaults      (Built-in fallbacks)
```

**Features**:
- **Immutable**: Configuration objects cannot be modified after creation
- **Thread-safe**: Safe for concurrent access
- **Validated**: All values are validated at load time
- **Extensible**: Easy to add new configuration options

### MCP Server Interface (`src/igloo_mcp/mcp_server.py`)

MCP server provides AI assistant integration:

```bash
# Start MCP server (MCP-only interface in v2.0+)
igloo-mcp                    # Use default or env profile
igloo-mcp --profile <name>   # Specify profile explicitly

# All operations via MCP tools:
# - execute_query           # SQL execution
# - build_catalog           # Data discovery operations
# - query_lineage           # Lineage analysis
# - build_dependency_graph  # Dependency mapping
# - test_connection         # Connection testing
# - health_check            # Server health status
```

## Data Flow

### 1. MCP Request Processing (Primary Interface in v2.0+)
```mermaid
graph TD
    A[MCP Client Request] --> B[Authentication Check]
    B --> C[Profile Validation]
    C --> D[Service Layer Call]
    D --> E[Snowflake Operation]
    E --> F[Response Formatting]
    F --> G[MCP Response]
```

### 2. Configuration Resolution
```mermaid
graph TD
    A[Application Start] --> B[Load CLI Args]
    B --> C[Load Environment]
    C --> D[Load Config File]
    D --> E[Load Profile Defaults]
    E --> F[Apply Overrides]
    F --> G[Validate & Freeze]
```

## Error Handling Strategy

### Error Categories
```python
# Hierarchical error classification
SnowCLIError
├── ProfileValidationError    # Profile/auth issues
├── ConfigurationError        # Config problems
├── ConnectionError          # Network/connectivity
├── PermissionError          # Access denied
└── OperationError           # Business logic failures
```

### Error Response Pattern
```python
# Consistent error response structure
{
    "success": false,
    "error": "Human-readable error message",
    "error_type": "ProfileValidationError",
    "context": {
        "profile": "my-profile",
        "operation": "catalog_build",
        "timestamp": "2024-01-01T12:00:00Z"
    },
    "recommendations": [
        "Check profile exists: snow connection list",
        "Verify credentials are valid"
    ]
}
```

## Security Considerations

### 1. Authentication
- **No Credential Storage**: Relies entirely on Snow CLI profiles
- **External Authentication**: Supports key-pair, OAuth, SSO
- **Profile Isolation**: Each operation uses specified profile only

### 2. Data Access
- **Principle of Least Privilege**: Only requests necessary permissions
- **Profile-scoped**: All operations scoped to profile's access
- **No Data Persistence**: No local data caching by default

### 3. MCP Security
- **Local Communication**: MCP server runs locally only
- **No Network Exposure**: Default stdio transport
- **Profile Validation**: Validates profile before any operations

## Performance Characteristics

### 1. Service Layer
- **Stateless**: Services can be created/destroyed efficiently
- **Connection Pooling**: Leverages Snowflake Labs MCP connection management
- **Lazy Loading**: Services initialized only when needed

### 2. MCP Server
- **Event-driven**: Responds to requests without polling
- **Resource Efficient**: Minimal memory footprint
- **Connection Reuse**: Efficient connection management

### 3. Configuration
- **Load Once**: Configuration loaded once at startup
- **Immutable**: No runtime configuration changes
- **Fast Access**: O(1) configuration value lookup

## Extension Points

### 1. New Services
```python
# Add new service to service layer
class AnalyticsService:
    def __init__(self, *, config: Config | None = None):
        self._config = config or get_config()

    def generate_insights(self) -> dict:
        # Business logic here
        pass
```

### 2. New MCP Tools
```python
# Add new MCP tool
@server.tool(name="analytics_insights")
async def analytics_insights_tool() -> Dict[str, Any]:
    analytics_service = AnalyticsService(config=config)
    return await anyio.to_thread.run_sync(
        analytics_service.generate_insights
    )
```

### 3. Python API Extensions
```python
# Add new service for Python API
class AnalyticsService:
    """Analytics and insights service."""
    def __init__(self, *, config: Config | None = None):
        self._config = config or get_config()

    def generate_insights(self) -> dict:
        """Generate data insights."""
        # Implementation
        return insights_data
```

## Testing Strategy

### 1. Unit Tests
- **Service Layer**: Mock external dependencies
- **Configuration**: Test all override scenarios
- **Error Handling**: Verify error propagation

### 2. Integration Tests
- **MCP Server**: Test with real Snowflake connections
- **MCP Tools**: End-to-end tool testing
- **Profile Validation**: Test with various profile types

### 3. Contract Tests
- **Service Interfaces**: Verify API contracts
- **MCP Protocol**: Ensure MCP compliance
- **Configuration Schema**: Validate config structure

## Migration Guide (1.4.x → 1.9.0)

### Breaking Changes (v2.0)
- **CLI Removed**: Legacy CLI commands removed in v2.0 - MCP-only architecture
- **MCP-Only**: All functionality via MCP tools and Python API
- **Profile Selection**: Via --profile flag when starting MCP server or SNOWFLAKE_PROFILE env var

### Migration Steps (v1.x to v2.0)
1. **Remove CLI usage**: Replace with MCP tool calls or Python API
2. **Update Integration**: Configure AI assistants with igloo-mcp
3. **Update Profiles**: Ensure Snowflake CLI profiles are valid
4. **Test MCP tools**: Verify all operations work via MCP
5. **See Migration Guide**: [CLI to MCP Migration](cli-to-mcp-migration.md)

### Compatibility
- **Python API**: Fully backward compatible
- **Configuration**: Existing configs supported
- **Profiles**: All existing Snow CLI profiles supported
- **CLI**: Removed in v2.0 - see migration guide

---

*Architecture Version: 1.9.0 | Last Updated: 2025-09-28*
