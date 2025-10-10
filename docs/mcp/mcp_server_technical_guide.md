# MCP Server Technical Guide

## Architecture Overview

The MCP server is the primary interface for Nanuk MCP (v2.0+). It exposes Snowflake operations as structured tools that AI assistants can call through the MCP protocol.

### Core Architecture
- MCP server built on FastMCP framework
- Service layer provides business logic
- All dependencies included by default (no separate installation needed)
- Import errors handled gracefully with helpful messages

### Key Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MCP Client    │    │   MCP Server     │    │  Service Layer  │
│ (VS Code, etc.) │◄──►│ (mcp_server.py)  │◄──►│ (Business Logic)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ Snowflake Labs   │
                       │  MCP + Snow CLI  │
                       └──────────────────┘
```

### Core Files

- **`src/nanuk_mcp/mcp_server.py`** - Main MCP server implementation
- **`src/nanuk_mcp/mcp/tools/`** - MCP tool implementations
- **`src/nanuk_mcp/service_layer/`** - Business logic services
- **`tests/test_mcp_server.py`** - Comprehensive test suite
- **`.mcp.json.example`** - Example MCP client configuration

## Adding New MCP Tools

**Important**: New service layer features should be exposed as MCP tools. The MCP server tool registry must be updated when adding new functionality.

### When to Update the MCP Server

Update the MCP server when:
1. **New service methods are added** - Expose as new MCP tools
2. **Existing service methods are modified** - Update corresponding MCP tool schemas
3. **New parameters are added** - Add to MCP tool input schemas
4. **Authentication or configuration changes** - Update MCP server initialization

### Feature Iteration Process

```mermaid
graph LR
    A[Add Service Method] --> B[Create MCP Tool]
    B --> C[Update Tests]
    C --> D[Update Documentation]
    D --> E[Release]
```

### Example: Adding a New MCP Tool

1. **Add Service Method** (e.g., in `service_layer/query.py`):
   ```python
   def analyze_query_performance(self, query: str) -> dict:
       """Analyze query performance and suggest optimizations."""
       # Implementation
       return {"analysis": "...", "suggestions": [...]}
   ```

2. **Create MCP Tool** - Add to `mcp/tools/` directory:
   ```python
   types.Tool(
       name="analyze_performance",
       description="Analyze query performance and suggest optimizations",
       inputSchema={
           "type": "object",
           "properties": {
               "query": {"type": "string", "description": "Query to analyze"},
               "database": {"type": "string", "description": "Database context"}
           },
           "required": ["query"]
       }
   )
   ```

3. **Implement Tool Handler**:
   ```python
   @self.server.call_tool()
   async def handle_call_tool(name: str, arguments: Dict[str, Any]):
       if name == "analyze_performance":
           result = self._analyze_performance(**arguments)
           return [types.TextContent(type="text", text=result)]
   ```

4. **Add Implementation Method**:
   ```python
   def _analyze_performance(self, query: str, database: Optional[str] = None) -> str:
       """Analyze query performance."""
       # Implementation that calls the service layer
       return analyze_query_performance(query, database)
   ```

5. **Add Tests** - Create unit and integration tests for the new tool

6. **Update Documentation** - Update both user and technical docs

## Development Workflow

### Adding New MCP Tools

1. **Define the Tool Schema**:
   ```python
   types.Tool(
       name="tool_name",
       description="Human-readable description",
       inputSchema={
           "type": "object",
           "properties": {
               "param1": {"type": "string", "description": "Parameter description"},
               "param2": {"type": "integer", "description": "Optional parameter"}
           },
           "required": ["param1"]
       }
   )
   ```

2. **Add Tool Handler**:
   ```python
   elif name == "tool_name":
       result = self._tool_name(**arguments)
       return [types.TextContent(type="text", text=result)]
   ```

3. **Implement Tool Method**:
   ```python
   def _tool_name(self, param1: str, param2: Optional[int] = None) -> str:
       """Tool implementation."""
       try:
           # Call existing functionality or implement new logic
           result = call_existing_function(param1, param2)
           return json.dumps(result, indent=2)
       except Exception as e:
           raise Exception(f"Tool execution failed: {e}")
   ```

### Error Handling

The MCP server uses structured error handling:

```python
# In tool handlers
try:
    result = self._some_operation(**arguments)
    return [types.TextContent(type="text", text=result)]
except Exception as e:
    raise Exception(f"Operation failed: {e}")
```

### Authentication and Configuration

The MCP server inherits authentication from the igloo-mcp configuration:

```python
def __init__(self):
    self.server = Server("igloo-tools")
    self.snow_cli = SnowCLI()  # Uses configured profile
    self.config = get_config()  # Uses existing configuration
```

### Testing Strategy

#### Unit Tests
- Test individual tool methods
- Mock external dependencies (SnowCLI, file system)
- Test error conditions and edge cases

#### Integration Tests
- Test tool orchestration
- Test with real file system operations
- Test authentication flows

#### Mock Strategy
```python
@patch('nanuk_mcp.mcp_server.SnowCLI')
@patch('nanuk_mcp.mcp_server.get_config')
def test_tool_functionality(self, mock_get_config, mock_snow_cli_class):
    # Setup mocks
    # Test tool behavior
```

## Configuration Management

### Environment Variables
The MCP server respects all igloo-mcp environment variables:
- `SNOWFLAKE_PROFILE`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_SCHEMA`
- `SNOWFLAKE_ROLE`

### Configuration Files
- MCP client configuration is separate from igloo-mcp config
- The server uses existing igloo-mcp configuration for Snowflake access
- No additional configuration files are required

## Deployment and Distribution

### Version Management
- MCP server version should match the main package version
- Update version in `pyproject.toml`
- Maintain backward compatibility when possible

### Dependencies
- MCP SDK: `mcp>=1.0.0`
- All other dependencies are inherited from igloo-mcp
- Add new dependencies to `pyproject.toml` in the main dependencies list

### Testing Requirements
- All MCP tools must have corresponding tests
- Tests should cover success and failure scenarios
- Integration tests should verify end-to-end functionality
- Mock-based tests for components requiring external services

## Monitoring and Debugging

### Logging
The MCP server uses the same logging configuration as igloo-mcp. Enable debug logging:

```bash
export NANUK_MCP_DEBUG=1
```

### Error Reporting
- Use structured error messages
- Include context information in error responses
- Log errors for debugging while providing user-friendly messages

### Performance Considerations
- Tool execution should be reasonably fast
- Use async operations where appropriate
- Cache expensive operations when possible
- Monitor memory usage for long-running operations

## Security Considerations

### Authentication
- MCP server uses existing Snowflake authentication
- No additional credentials are required
- Access control is managed through Snowflake roles

### Input Validation
- Validate all tool parameters
- Sanitize inputs where necessary
- Use parameterized queries to prevent injection

### Resource Limits
- Implement timeouts for long-running operations
- Limit resource usage for memory-intensive operations
- Validate input sizes and complexity

## Future Enhancements

### Potential New Tools
- Batch query execution
- Schema comparison and drift detection
- Performance benchmarking
- Data quality analysis
- Automated documentation generation

### Architecture Improvements
- Connection pooling for better performance
- Caching layer for frequently accessed data
- Plugin architecture for extensible tools
- Real-time collaboration features

## Maintenance Checklist

When updating the MCP server:

- [ ] Update tool schemas for any modified service methods
- [ ] Add tests for new or modified tools
- [ ] Update documentation (both user and technical)
- [ ] Verify all existing tests still pass
- [ ] Test with at least one MCP client (VS Code/Cursor)
- [ ] Update version numbers if needed
- [ ] Check for security implications of changes
- [ ] Update examples and configuration samples

### Additional Checks

When making changes, also verify:

- [ ] Does the change affect core service layer? (Review impact)
- [ ] Update installation documentation if needed
- [ ] Test production install (`pip install igloo-mcp`)
- [ ] Verify graceful error handling for missing dependencies
- [ ] Update CI to test installation modes

This ensures the MCP server stays synchronized with the service layer and provides a consistent experience.
