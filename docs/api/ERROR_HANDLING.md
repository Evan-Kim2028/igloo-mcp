# MCP Tool Error Handling

This document describes the error handling architecture for igloo-mcp MCP tools.

## Overview

All MCP tools use a consistent exception-based error handling pattern:
1. Tools raise MCP-specific exceptions (`MCPValidationError`, `MCPExecutionError`, `MCPSelectorError`)
2. The `@tool_error_handler` decorator ensures all exceptions are properly formatted
3. FastMCP serializes exceptions to JSON-RPC error responses
4. All errors include `request_id` for correlation and timing information

## Exception Types

### MCPValidationError
Raised when tool parameters fail validation (invalid types, missing required fields, out-of-range values).

**Key Features:**
- Includes `validation_errors` list with specific field-level errors
- Provides actionable `hints` with parameter-specific guidance
- Includes `context` with `request_id` and operation details

### MCPExecutionError
Raised when tool execution fails (database errors, file I/O errors, runtime failures).

**Key Features:**
- Includes `operation` name for identification
- Preserves `original_error` for debugging
- Provides `hints` for troubleshooting
- Includes `context` with `request_id` and operation details

### MCPSelectorError
Raised when a selector (ID, name, etc.) cannot be resolved.

**Key Features:**
- Includes `selector` that failed
- Specifies `error` type ("not_found", "ambiguous", "invalid_format")
- Provides `candidates` list for ambiguous errors
- Includes `context` with `request_id`

## Error Handler Decorator

The `@tool_error_handler` decorator in `src/igloo_mcp/mcp/tools/base.py`:

1. **Preserves MCP exceptions**: Re-raises MCP exceptions as-is (they're already properly formatted)
2. **Converts ValidationError**: Converts Pydantic `ValidationError` to `MCPValidationError` with detailed field paths
3. **Converts other exceptions**: Wraps unexpected exceptions in `MCPExecutionError` with context
4. **Adds request_id**: Automatically includes `request_id` from kwargs in error context
5. **Logs errors**: Logs all errors with context for debugging

## FastMCP Serialization

FastMCP automatically serializes exceptions raised from tool handlers to JSON-RPC error responses. The serialization process:

1. **Exception Detection**: FastMCP catches exceptions raised from tool handlers
2. **to_dict() Call**: If the exception has a `to_dict()` method, FastMCP calls it
3. **JSON-RPC Format**: The result is formatted as a JSON-RPC error response
4. **Error Code Mapping**: FastMCP maps exception types to appropriate JSON-RPC error codes

**Note**: All MCP exception classes (`MCPToolError`, `MCPValidationError`, `MCPExecutionError`, `MCPSelectorError`) implement `to_dict()` methods that return structured error dictionaries.

## Request ID Generation

All tools automatically generate a `request_id` if not provided:

```python
from igloo_mcp.mcp.tools.base import ensure_request_id

request_id = ensure_request_id(request_id)  # Generates UUID if None
```

The `request_id` is:
- Included in all error responses via `context`
- Logged with all operations
- Included in successful responses for correlation

## Timing Information

Tools capture timing information for performance monitoring:

```python
start_time = time.time()
# ... operation ...
duration_ms = (time.time() - start_time) * 1000
```

Timing is included in:
- Successful responses: `timing` field with operation-specific durations
- Error responses: Available in logs via `request_id` correlation

## Error Response Format

### Success Response
```json
{
  "status": "success",
  "request_id": "uuid-here",
  "timing": {
    "operation_duration_ms": 123.45,
    "total_duration_ms": 150.67
  },
  "data": {...}
}
```

### Error Response (via FastMCP)
```json
{
  "code": -32603,
  "message": "Tool execution failed: ...",
  "data": {
    "message": "Human-readable error message",
    "error_type": "MCPValidationError",
    "error_code": "VALIDATION_ERROR",
    "validation_errors": ["field: error message"],
    "hints": ["actionable", "suggestions"],
    "context": {
      "request_id": "uuid-here",
      "operation": "tool_name"
    }
  }
}
```

## Best Practices

1. **Always use @tool_error_handler**: Ensures consistent error formatting
2. **Raise specific exceptions**: Use `MCPValidationError`, `MCPExecutionError`, or `MCPSelectorError`
3. **Include request_id**: Use `ensure_request_id()` helper
4. **Provide actionable hints**: Include specific parameter names and examples
5. **Capture timing**: Include timing information in responses
6. **Log with context**: Include `request_id` in all log statements

## Error Aggregation

The `ErrorAggregator` class in `src/igloo_mcp/error_handling.py` provides functionality for aggregating errors during batch operations. Currently, it's available but not actively used in MCP tools.

**Current Status:** Available for future batch operation implementations

**Usage Example:**
```python
from igloo_mcp.error_handling import ErrorAggregator

aggregator = ErrorAggregator()

# Process multiple items
for item in items:
    try:
        process_item(item)
    except Exception as e:
        aggregator.add_error(item.id, e)

if aggregator.has_errors():
    summary = aggregator.get_summary()
    # Handle aggregated errors
```

**Potential Use Cases:**
- Batch report operations (create/evolve multiple reports)
- Bulk catalog operations
- Parallel query execution with error collection

**Note:** For single-operation tools, exceptions are raised immediately. ErrorAggregator would be useful for future batch operation tools.

## Testing Error Handling

Error handling is tested in:
- `tests/test_*_tool.py` - Individual tool error scenarios
- `tests/test_mcp_error_handling.py` - Request ID, error context, exception serialization
- `tests/test_error_handling.py` - Error handler decorator and ErrorAggregator behavior
- `tests/test_evolve_report_mcp.py` - Evolve report error scenarios
- `tests/test_render_report_tool.py` - Render report error scenarios
- `tests/test_create_report_tool.py` - Create report error scenarios

## Migration Notes

If migrating from dict-based error responses to exception-based:

1. **Remove status dicts**: Don't return `{"status": "error", ...}` - raise exceptions instead
2. **Use MCP exceptions**: Import and raise `MCPValidationError`, `MCPExecutionError`, `MCPSelectorError`
3. **Add request_id**: Use `ensure_request_id()` helper
4. **Update tests**: Test exception raising instead of dict responses
