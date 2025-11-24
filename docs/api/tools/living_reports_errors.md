# Living Reports Error Catalog

This document catalogs all structured error responses from Living Reports MCP tools. Each tool returns machine-readable error responses that agents can handle programmatically.

## Common Error Response Structure

All errors are raised as MCP exceptions that FastMCP serializes to JSON-RPC error responses. The exception structure includes:

```json
{
  "message": "human_readable_message",
  "error_type": "MCPValidationError|MCPExecutionError|MCPSelectorError",
  "error_code": "VALIDATION_ERROR|EXECUTION_ERROR|SELECTOR_ERROR",
  "validation_errors": ["..."] (for MCPValidationError),
  "operation": "tool_name" (for MCPExecutionError),
  "selector": "..." (for MCPSelectorError),
  "hints": ["actionable", "suggestions"],
  "context": {
    "request_id": "uuid-here",
    "additional": "context"
  }
}
```

**Note:** All tools automatically generate a `request_id` if not provided, enabling error correlation and tracing across tool calls.

## Complete Error Response Examples

### MCPValidationError Examples

#### Invalid Template (create_report)
```json
{
  "code": -32602,
  "message": "Parameter validation failed for create_report",
  "data": {
    "message": "Invalid template 'invalid_template'. Must be one of: default, monthly_sales, quarterly_review, deep_dive, analyst_v1",
    "error_type": "MCPValidationError",
    "error_code": "VALIDATION_ERROR",
    "validation_errors": [
      "Invalid template: invalid_template"
    ],
    "hints": [
      "Use template='default' for empty report",
      "Use template='monthly_sales' for sales reports",
      "Use template='quarterly_review' for quarterly reviews",
      "Use template='deep_dive' for detailed analysis",
      "Use template='analyst_v1' for blockchain analysis with citation enforcement"
    ],
    "context": {
      "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "My Report"
    }
  }
}
```

#### Schema Validation Error (evolve_report)
```json
{
  "code": -32602,
  "message": "Parameter validation failed for evolve_report",
  "data": {
    "message": "Parameter validation failed for evolve_report",
    "error_type": "MCPValidationError",
    "error_code": "VALIDATION_ERROR",
    "validation_errors": [
      "proposed_changes.insights_to_add.0.importance: ensure this value is less than or equal to 10",
      "proposed_changes.insights_to_add.0.insight_id: value is not a valid uuid"
    ],
    "hints": [
      "Check parameter types and required fields for evolve_report",
      "Review evolve_report parameter schema for valid values",
      "Common issues: missing required fields, wrong data types, out-of-range values"
    ],
    "context": {
      "request_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901"
    }
  }
}
```

#### Invalid Format (render_report)
```json
{
  "code": -32602,
  "message": "Invalid format 'doc'. Must be one of: html, pdf, markdown, docx",
  "data": {
    "message": "Invalid format 'doc'. Must be one of: html, pdf, markdown, docx",
    "error_type": "MCPValidationError",
    "error_code": "VALIDATION_ERROR",
    "validation_errors": [
      "Invalid format: doc"
    ],
    "hints": [
      "Use format='html' for web output",
      "Use format='pdf' for document output",
      "Use format='markdown' for markdown output",
      "Use format='docx' for Word document output"
    ],
    "context": {
      "request_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
      "report_selector": "Q1 Report"
    }
  }
}
```

#### Invalid Status (search_report)
```json
{
  "code": -32602,
  "message": "Invalid status 'invalid'. Must be 'active' or 'archived'.",
  "data": {
    "message": "Invalid status 'invalid'. Must be 'active' or 'archived'.",
    "error_type": "MCPValidationError",
    "error_code": "VALIDATION_ERROR",
    "validation_errors": [
      "Invalid status: invalid"
    ],
    "hints": [
      "Use status='active' to search active reports only",
      "Use status='archived' to search archived reports only",
      "Status parameter is case-sensitive"
    ],
    "context": {
      "request_id": "d4e5f6a7-b8c9-0123-def0-234567890123"
    }
  }
}
```

### MCPSelectorError Examples

#### Report Not Found
```json
{
  "code": -32602,
  "message": "Could not resolve report selector: Non-existent Report",
  "data": {
    "message": "Could not resolve report selector: Non-existent Report",
    "error_type": "MCPSelectorError",
    "error_code": "SELECTOR_ERROR",
    "selector": "Non-existent Report",
    "error": "not_found",
    "candidates": [],
    "hints": [
      "Verify report_selector matches an existing report: Non-existent Report",
      "Check report ID or title spelling (case-insensitive)",
      "Use search_report to find available reports"
    ],
    "context": {
      "request_id": "e5f6a7b8-c9d0-1234-ef01-345678901234"
    }
  }
}
```

#### Ambiguous Selector
```json
{
  "code": -32602,
  "message": "Ambiguous selector 'Sales' matches multiple reports",
  "data": {
    "message": "Ambiguous selector 'Sales' matches multiple reports",
    "error_type": "MCPSelectorError",
    "error_code": "SELECTOR_ERROR",
    "selector": "Sales",
    "error": "ambiguous",
    "candidates": [
      {
        "title": "Q1 Sales Report",
        "id": "rpt_550e8400e29b11d4a716446655440000"
      },
      {
        "title": "Sales Analysis 2024",
        "id": "rpt_660f9511f39c22e5b827557766551111"
      }
    ],
    "hints": [
      "Use a more specific selector or one of: rpt_550e8400e29b11d4a716446655440000, rpt_660f9511f39c22e5b827557766551111",
      "Provide full ID instead of partial match"
    ],
    "context": {
      "request_id": "f6a7b8c9-d0e1-2345-f012-456789012345"
    }
  }
}
```

### MCPExecutionError Examples

#### Quarto Missing (render_report)
```json
{
  "code": -32603,
  "message": "Tool execution failed: Quarto not found: Quarto binary not available",
  "data": {
    "message": "Quarto not found: Quarto binary not available",
    "error_type": "MCPExecutionError",
    "error_code": "EXECUTION_ERROR",
    "operation": "render_report",
    "original_error": "QuartoNotFoundError: Quarto not found. Install Quarto from https://quarto.org/docs/get-started/",
    "hints": [
      "Install Quarto from https://quarto.org/docs/get-started/",
      "Or set IGLOO_QUARTO_BIN environment variable to the path of quarto executable",
      "For dry_run=True, Quarto is not required (only generates QMD file)"
    ],
    "context": {
      "request_id": "a7b8c9d0-e1f2-3456-0123-567890123456",
      "report_id": "rpt_550e8400e29b11d4a716446655440000",
      "format": "html"
    }
  }
}
```

#### Report Validation Failed (render_report)
```json
{
  "code": -32602,
  "message": "Report validation failed: Missing required insights in section 'Executive Summary'",
  "data": {
    "message": "Report validation failed: Missing required insights in section 'Executive Summary'",
    "error_type": "MCPValidationError",
    "error_code": "VALIDATION_ERROR",
    "validation_errors": [
      "Missing required insights in section 'Executive Summary'",
      "Section 'Financials' has no insights"
    ],
    "hints": [
      "Fix reported validation errors using evolve_report",
      "Check that all referenced insights and sections exist",
      "Verify report outline structure is valid"
    ],
    "context": {
      "request_id": "b8c9d0e1-f2a3-4567-1234-678901234567",
      "report_id": "rpt_550e8400e29b11d4a716446655440000"
    }
  }
}
```

#### Rendering Failed (render_report)
```json
{
  "code": -32603,
  "message": "Rendering failed: Quarto rendering process exited with code 1",
  "data": {
    "message": "Rendering failed: Quarto rendering process exited with code 1",
    "error_type": "MCPExecutionError",
    "error_code": "EXECUTION_ERROR",
    "operation": "render_report",
    "original_error": "Quarto rendering failed: Template syntax error at line 45",
    "hints": [
      "Check Quarto logs for detailed error information",
      "Verify report content is valid",
      "Check file system permissions and disk space",
      "Try dry_run=True to generate QMD file without rendering"
    ],
    "context": {
      "request_id": "c9d0e1f2-a3b4-5678-2345-789012345678",
      "report_id": "rpt_550e8400e29b11d4a716446655440000",
      "format": "pdf"
    }
  }
}
```

#### Creation Failed (create_report)
```json
{
  "code": -32603,
  "message": "Failed to create report: Permission denied: /path/to/reports",
  "data": {
    "message": "Failed to create report: Permission denied: /path/to/reports",
    "error_type": "MCPExecutionError",
    "error_code": "EXECUTION_ERROR",
    "operation": "create_report",
    "original_error": "PermissionError: [Errno 13] Permission denied: '/path/to/reports'",
    "hints": [
      "Check file system permissions",
      "Verify reports directory is writable",
      "Check disk space availability"
    ],
    "context": {
      "request_id": "d0e1f2a3-b4c5-6789-3456-890123456789",
      "title": "My Report",
      "template": "default"
    }
  }
}
```

#### Index Corruption (search_report)
```json
{
  "code": -32603,
  "message": "Report index is corrupted: Invalid JSON at line 42",
  "data": {
    "message": "Report index is corrupted: Invalid JSON at line 42",
    "error_type": "MCPExecutionError",
    "error_code": "EXECUTION_ERROR",
    "operation": "search_report",
    "original_error": "JSONDecodeError: Expecting ',' delimiter: line 42 column 5",
    "hints": [
      "Try rebuilding the report index",
      "Check file system permissions for index file",
      "Verify index file is not corrupted or locked"
    ],
    "context": {
      "request_id": "e1f2a3b4-c5d6-7890-4567-901234567890"
    }
  }
}
```

#### Apply Failed (evolve_report)
```json
{
  "code": -32603,
  "message": "Failed to apply changes to report: Section ID conflict detected",
  "data": {
    "message": "Failed to apply changes to report: Section ID conflict detected",
    "error_type": "MCPExecutionError",
    "error_code": "EXECUTION_ERROR",
    "operation": "evolve_report",
    "original_error": "ValueError: Section ID 'section_123' already exists",
    "hints": [
      "Check logs for detailed error information",
      "Verify report file is not locked",
      "Check file system permissions"
    ],
    "context": {
      "request_id": "f2a3b4c5-d6e7-8901-5678-012345678901",
      "report_id": "rpt_550e8400e29b11d4a716446655440000"
    }
  }
}
```

#### Storage Failed (evolve_report)
```json
{
  "code": -32603,
  "message": "Failed to save report changes: No space left on device",
  "data": {
    "message": "Failed to save report changes: No space left on device",
    "error_type": "MCPExecutionError",
    "error_code": "EXECUTION_ERROR",
    "operation": "evolve_report",
    "original_error": "OSError: [Errno 28] No space left on device",
    "hints": [
      "Check file system permissions and disk space",
      "Free up disk space and retry",
      "Check disk quota limits"
    ],
    "context": {
      "request_id": "a3b4c5d6-e7f8-9012-6789-123456789012",
      "report_id": "rpt_550e8400e29b11d4a716446655440000"
    }
  }
}
```

#### Semantic Validation Failed (evolve_report)
```json
{
  "code": -32602,
  "message": "Semantic validation failed for proposed changes",
  "data": {
    "message": "Semantic validation failed for proposed changes",
    "error_type": "MCPValidationError",
    "error_code": "VALIDATION_ERROR",
    "validation_errors": [
      "Cannot add - insight_id already exists: abc-123-def-456",
      "Section ID not found: xyz-789-abc-012",
      "Cannot modify - insight_id does not exist: non-existent-id"
    ],
    "hints": [
      "Check that all referenced insight and section IDs exist in the current outline"
    ],
    "context": {
      "request_id": "b4c5d6e7-f8a9-0123-7890-234567890123",
      "structured_errors": [
        {
          "field": "insights_to_add.0.insight_id",
          "value": "abc-123-def-456",
          "error": "duplicate_id",
          "available_ids": []
        },
        {
          "field": "sections_to_modify.0.section_id",
          "value": "xyz-789-abc-012",
          "error": "not_found",
          "available_ids": ["section-001", "section-002"]
        }
      ]
    }
  }
}
```

## evolve_report Tool Errors

All errors are raised as MCP exceptions with structured error information and timing data.

### MCPSelectorError - Selector Resolution Failed

Raised when the report selector could not be resolved.

**Exception Type:** `MCPSelectorError`

**Fields:**
- `message`: Human-readable error message
- `error_code`: "SELECTOR_ERROR"
- `selector`: Original selector string
- `error`: Error type ("not_found", "ambiguous", "invalid_format")
- `candidates`: List of candidate IDs (for ambiguous errors)
- `hints`: Actionable suggestions
- `context`: Additional context including `request_id`

**Example:**
```json
{
  "message": "Ambiguous selector 'Sales' matches multiple reports",
  "error_type": "MCPSelectorError",
  "error_code": "SELECTOR_ERROR",
  "selector": "Sales",
  "error": "ambiguous",
  "candidates": ["rpt_abc123", "rpt_def456"],
  "hints": [
    "Use a more specific selector or one of: rpt_abc123, rpt_def456",
    "Provide full ID instead of partial match"
  ],
  "context": {
    "request_id": "uuid-here"
  }
}
```

**Recovery:** Use exact report ID or a more specific selector. Use `search_report` to find available reports.

### MCPValidationError - Schema Validation Failed

Raised when proposed changes fail schema validation (Pydantic validation).

**Exception Type:** `MCPValidationError`

**Fields:**
- `message`: Human-readable error message
- `error_code`: "VALIDATION_ERROR"
- `validation_errors`: List of specific validation error messages with field paths
- `hints`: Field-specific suggestions and examples
- `context`: Additional context including `request_id` and structured error details

**Recovery:** Fix data types, required fields, and ensure UUIDs are valid format.

### MCPValidationError - Semantic Validation Failed

Raised when proposed changes fail semantic validation (e.g., referenced IDs don't exist).

**Exception Type:** `MCPValidationError`

**Fields:**
- `message`: Human-readable error message
- `error_code`: "VALIDATION_ERROR"
- `validation_errors`: List of semantic validation error messages
- `hints`: Suggestions for fixing semantic issues
- `context`: Additional context including `request_id` and structured error details

**Example:**
```json
{
  "message": "Semantic validation failed for proposed changes",
  "error_type": "MCPValidationError",
  "error_code": "VALIDATION_ERROR",
  "validation_errors": [
    "Cannot add - insight_id already exists: abc-123",
    "Section ID not found: xyz-789"
  ],
  "hints": [
    "Check that all referenced insight and section IDs exist in the current outline"
  ],
  "context": {
    "request_id": "uuid-here",
    "structured_errors": [...]
  }
}
```

**Recovery:** Ensure all referenced insight and section IDs exist in the current outline. Use `dry_run=True` to preview changes.

### MCPExecutionError - Apply Failed

Raised when changes cannot be applied to the report.

**Exception Type:** `MCPExecutionError`

**Fields:**
- `message`: Human-readable error message
- `error_code`: "EXECUTION_ERROR"
- `operation`: "evolve_report"
- `original_error`: Original exception message
- `hints`: Troubleshooting suggestions
- `context`: Additional context including `request_id` and `report_id`

**Recovery:** Check logs for detailed error information, verify report file is not locked, check file system permissions.

### MCPExecutionError - Storage Failed

Raised when report changes cannot be saved.

**Exception Type:** `MCPExecutionError`

**Fields:**
- `message`: Human-readable error message
- `error_code`: "EXECUTION_ERROR"
- `operation`: "evolve_report"
- `original_error`: Original exception message
- `hints`: File system troubleshooting suggestions
- `context`: Additional context including `request_id` and `report_id`

**Recovery:** Check file system permissions and disk space.

## create_report Tool Errors

All errors are raised as MCP exceptions with structured error information.

### MCPValidationError - Invalid Template

Raised when an invalid template name is provided.

**Exception Type:** `MCPValidationError`

**Fields:**
- `message`: Human-readable error message
- `error_code`: "VALIDATION_ERROR"
- `validation_errors`: List of validation error messages
- `hints`: Actionable suggestions
- `context`: Additional context including `request_id` and `title`

**Example:**
```json
{
  "message": "Invalid template 'invalid_template'. Must be one of: default, monthly_sales, quarterly_review, deep_dive, analyst_v1",
  "error_type": "MCPValidationError",
  "error_code": "VALIDATION_ERROR",
  "validation_errors": ["Invalid template: invalid_template"],
  "hints": [
    "Use template='default' for empty report",
    "Use template='monthly_sales' for sales reports",
    "Use template='analyst_v1' for blockchain analysis with citation enforcement"
  ],
  "context": {
    "request_id": "uuid-here",
    "title": "My Report"
  }
}
```

**Recovery:** Use a valid template name from the available options.

### MCPExecutionError - Creation Failed

Raised when report creation fails due to file system or other runtime errors.

**Exception Type:** `MCPExecutionError`

**Fields:**
- `message`: Human-readable error message
- `error_code`: "EXECUTION_ERROR"
- `operation`: "create_report"
- `original_error`: Original exception message
- `hints`: Actionable suggestions
- `context`: Additional context including `request_id`, `title`, `template`

**Recovery:** Check file system permissions, disk space, and reports directory writability.

## render_report Tool Errors

All errors are raised as MCP exceptions. The tool converts service-level status dicts to exceptions.

### MCPSelectorError - Report Not Found

Raised when the report selector cannot be resolved.

**Exception Type:** `MCPSelectorError`

**Fields:**
- `message`: Human-readable error message
- `error_code`: "SELECTOR_ERROR"
- `selector`: Original selector string
- `error`: Error type ("not_found", "ambiguous", "invalid_format")
- `candidates`: List of candidate IDs (for ambiguous errors)
- `hints`: Actionable suggestions
- `context`: Additional context including `request_id`

**Example:**
```json
{
  "message": "Could not resolve report selector: Invalid Report",
  "error_type": "MCPSelectorError",
  "error_code": "SELECTOR_ERROR",
  "selector": "Invalid Report",
  "error": "not_found",
  "candidates": [],
  "hints": [
    "Verify report_selector matches an existing report: Invalid Report",
    "Check report ID or title spelling (case-insensitive)",
    "Use search_report to find available reports"
  ],
  "context": {
    "request_id": "uuid-here"
  }
}
```

**Recovery:** Verify report exists using `search_report` or check selector spelling.

### MCPValidationError - Invalid Format

Raised when an invalid output format is specified.

**Exception Type:** `MCPValidationError`

**Fields:**
- `message`: Human-readable error message
- `error_code`: "VALIDATION_ERROR"
- `validation_errors`: List of validation error messages
- `hints`: Format-specific suggestions
- `context`: Additional context including `request_id` and `report_selector`

**Recovery:** Use one of the supported formats: `html`, `pdf`, `markdown`, `docx`.

### MCPValidationError - Report Validation Failed

Raised when the report has consistency issues preventing rendering.

**Exception Type:** `MCPValidationError`

**Fields:**
- `message`: Human-readable error message
- `error_code`: "VALIDATION_ERROR"
- `validation_errors`: List of validation issues
- `hints`: Suggestions for fixing validation errors
- `context`: Additional context including `request_id` and `report_id`

**Recovery:** Fix reported validation errors using `evolve_report` to correct the report structure.

### MCPExecutionError - Quarto Missing

Raised when Quarto is not installed or not found in PATH.

**Exception Type:** `MCPExecutionError`

**Fields:**
- `message`: Error message with installation instructions
- `error_code`: "EXECUTION_ERROR"
- `operation`: "render_report"
- `hints`: Installation and configuration suggestions
- `context`: Additional context including `request_id`, `report_id`, `format`

**Recovery:** Install Quarto from https://quarto.org or set `IGLOO_QUARTO_BIN` environment variable. For `dry_run=True`, Quarto is not required.

### MCPExecutionError - Rendering Failed

Raised when Quarto rendering fails (e.g., template error, file I/O).

**Exception Type:** `MCPExecutionError`

**Fields:**
- `message`: Error message describing the failure
- `error_code`: "EXECUTION_ERROR"
- `operation`: "render_report"
- `original_error`: Original exception message
- `hints`: Troubleshooting suggestions
- `context`: Additional context including `request_id`, `report_id`, `format`

**Recovery:** Check Quarto logs, verify report content is valid, check file system permissions and disk space. Try `dry_run=True` to generate QMD file without rendering.

## search_report Tool Errors

All errors are raised as MCP exceptions.

### MCPValidationError - Invalid Status

Raised when an invalid status filter is provided.

**Exception Type:** `MCPValidationError`

**Fields:**
- `message`: Human-readable error message
- `error_code`: "VALIDATION_ERROR"
- `validation_errors`: List of validation error messages
- `hints`: Status-specific suggestions
- `context`: Additional context including `request_id`

**Example:**
```json
{
  "message": "Invalid status 'invalid'. Must be 'active' or 'archived'.",
  "error_type": "MCPValidationError",
  "error_code": "VALIDATION_ERROR",
  "validation_errors": ["Invalid status: invalid"],
  "hints": [
    "Use status='active' to search active reports only",
    "Use status='archived' to search archived reports only",
    "Status parameter is case-sensitive"
  ],
  "context": {
    "request_id": "uuid-here"
  }
}
```

**Recovery:** Use `status='active'` or `status='archived'`.

### MCPExecutionError - Index Corruption

Raised when the report index is corrupted or unreadable.

**Exception Type:** `MCPExecutionError`

**Fields:**
- `message`: Error message describing the corruption
- `error_code`: "EXECUTION_ERROR"
- `operation`: "search_report"
- `original_error`: Original exception message
- `hints`: Recovery suggestions
- `context`: Additional context including `request_id`

**Recovery:** Try rebuilding the report index, check file system permissions, verify index file is not corrupted or locked.

## CLI Command Errors

CLI commands return exit codes and print error messages to stderr:

- **Exit Code 1**: Validation or execution errors
- **Exit Code 2**: CLI parsing errors

Error messages are prefixed with:
- `❌` for errors
- `⚠️` for warnings

## Error Recovery Strategies

### Selector Errors (MCPSelectorError)

#### not_found
**Symptoms:** Report selector cannot be found in index

**Recovery Steps:**
1. Use `search_report` with empty parameters to list all available reports
2. Check spelling and case sensitivity (titles are case-insensitive)
3. Verify report was created successfully (check `create_report` response)
4. If report was created via CLI, wait a moment and retry (index auto-refreshes)
5. Check if report was archived (use `status='archived'` in search)

**Retry Logic:**
```python
# Retry with search to find correct selector
results = await search_report(title="partial_title")
if results["matches_found"] > 0:
    report_id = results["reports"][0]["report_id"]
    # Use exact report_id for subsequent operations
```

#### ambiguous
**Symptoms:** Multiple reports match the selector

**Recovery Steps:**
1. Review `candidates` list in error response
2. Use exact report ID from candidates list
3. Provide more specific selector (longer title substring)
4. Use `search_report` with tags to narrow down results

**Retry Logic:**
```python
# Use exact ID from candidates
if error.error == "ambiguous" and error.candidates:
    report_id = error.candidates[0]  # Use first candidate
    # Retry operation with exact ID
```

#### invalid_format
**Symptoms:** Selector format is not recognized

**Recovery Steps:**
1. Use report ID (UUID format: `rpt_550e8400e29b11d4a716446655440000`)
2. Use full or partial title (case-insensitive)
3. Use tag format: `tag:tagname`
4. Verify selector is a string, not an object

### Validation Errors (MCPValidationError)

#### schema_validation
**Symptoms:** Parameter types or structure invalid

**Recovery Steps:**
1. Review `validation_errors` list for specific field issues
2. Check parameter types match schema (strings, integers, arrays, objects)
3. Ensure required fields are provided
4. Verify UUIDs are valid format (if applicable)
5. Check enum values match allowed options

**Common Patterns:**
- **Missing required field**: Add the required parameter
- **Wrong type**: Convert to correct type (e.g., string to int)
- **Invalid UUID**: Generate valid UUID or use auto-generation
- **Out of range**: Adjust value to valid range

**Retry Logic:**
```python
# Fix validation errors and retry
if isinstance(error, MCPValidationError):
    # Parse validation_errors to fix parameters
    for validation_error in error.validation_errors:
        # Extract field name and fix
        # Retry with corrected parameters
```

#### semantic_validation
**Symptoms:** Referenced IDs don't exist or conflict

**Recovery Steps:**
1. Use `evolve_report` with `dry_run=True` to preview current outline
2. Verify all referenced insight/section IDs exist in current outline
3. Check for duplicate IDs in `insights_to_add`
4. Ensure IDs being modified/removed actually exist
5. For analyst_v1 templates, ensure all insights have `supporting_queries` with `execution_id`

**Retry Logic:**
```python
# Get current outline first
dry_run_result = await evolve_report(
    report_selector=report_id,
    instruction="Preview",
    proposed_changes={},
    dry_run=True
)
current_outline = dry_run_result["current_outline"]
# Verify IDs exist before retrying
```

#### template_validation
**Symptoms:** Invalid template name provided

**Recovery Steps:**
1. Use one of: `default`, `monthly_sales`, `quarterly_review`, `deep_dive`, `analyst_v1`
2. Check spelling (case-sensitive)
3. Use `default` if unsure

#### format_validation
**Symptoms:** Invalid output format specified

**Recovery Steps:**
1. Use one of: `html`, `pdf`, `markdown`, `docx`
2. Check spelling (case-sensitive)
3. Use `html` for web output, `pdf` for documents

#### status_validation
**Symptoms:** Invalid status filter value

**Recovery Steps:**
1. Use `active` or `archived` (case-sensitive)
2. Omit status parameter to search all reports
3. Default is `active` if not specified

### Execution Errors (MCPExecutionError)

#### quarto_missing
**Symptoms:** Quarto binary not found

**Recovery Steps:**
1. Install Quarto: https://quarto.org/docs/get-started/
2. Verify installation: `quarto --version`
3. Set `IGLOO_QUARTO_BIN` environment variable if Quarto not in PATH
4. For `dry_run=True`, Quarto is not required (only generates QMD)

**Retry Logic:**
```python
# Check if dry_run is an option
if error.operation == "render_report" and "quarto" in error.message.lower():
    # Use dry_run to generate QMD without Quarto
    result = await render_report(
        report_selector=report_id,
        format="html",
        dry_run=True
    )
```

#### render_failed
**Symptoms:** Quarto rendering process failed

**Recovery Steps:**
1. Check Quarto logs in report directory
2. Validate report structure using `evolve_report` with `dry_run=True`
3. Verify file permissions on report directory
4. Check disk space availability
5. Try `dry_run=True` first to validate QMD generation
6. Review report content for template syntax errors

**Troubleshooting Workflow:**
```python
# Step 1: Validate report structure
dry_run = await evolve_report(..., dry_run=True)
if dry_run["validation_passed"]:
    # Step 2: Try dry_run rendering
    qmd_result = await render_report(..., dry_run=True)
    # Step 3: If QMD generation succeeds, try full render
    if qmd_result["status"] == "success":
        render_result = await render_report(..., dry_run=False)
```

#### creation_failed
**Symptoms:** Report creation failed

**Recovery Steps:**
1. Check file system permissions on reports directory
2. Verify disk space availability
3. Check if reports directory exists and is writable
4. Review error logs for specific file system errors
5. Try creating with simpler template (`default`)

**Retry Logic:**
```python
# Retry with default template if template-specific creation fails
try:
    result = await create_report(title="Report", template="complex_template")
except MCPExecutionError as e:
    if "creation" in e.operation:
        # Retry with default template
        result = await create_report(title="Report", template="default")
```

#### index_corruption
**Symptoms:** Report index is corrupted or unreadable

**Recovery Steps:**
1. Check file permissions on index file
2. Verify index file is not locked by another process
3. Backup current index file
4. Delete corrupted index file (will be rebuilt automatically)
5. Manually rebuild index if needed

**Recovery Workflow:**
```python
# Index will auto-rebuild on next search_report call
# If persistent, check file system:
# 1. Verify index file exists: ~/.igloo-mcp/reports/index.jsonl
# 2. Check file permissions
# 3. Remove corrupted file (backup first)
# 4. Next search_report will rebuild index
```

#### apply_failed
**Symptoms:** Changes cannot be applied to report

**Recovery Steps:**
1. Check logs for detailed error information (use `request_id` from error)
2. Verify report file is not locked by another process
3. Check file system permissions
4. Try `dry_run=True` first to validate changes
5. Retry with smaller change set if batch operation fails

**Retry Logic:**
```python
# Break large changes into smaller batches
if error.operation == "evolve_report" and "apply" in error.message.lower():
    # Retry with smaller change set
    # Apply changes incrementally
```

#### storage_failed
**Symptoms:** Report changes cannot be saved

**Recovery Steps:**
1. Check file system permissions on report directory
2. Verify disk space availability
3. Check if report file is locked
4. Review error logs for specific I/O errors
5. Retry operation (may be transient)

**Retry Logic:**
```python
import time
max_retries = 3
for attempt in range(max_retries):
    try:
        result = await evolve_report(...)
        break
    except MCPExecutionError as e:
        if "storage" in e.message.lower() and attempt < max_retries - 1:
            time.sleep(1)  # Wait before retry
            continue
        raise
```

### Concurrent Modification

#### version_mismatch
**Symptoms:** Report was modified by another process

**Recovery Steps:**
1. Use `search_report` to get fresh report data
2. Use `evolve_report` with `dry_run=True` to get current outline
3. Regenerate proposed changes based on current outline
4. Retry evolution with updated changes

**Retry Workflow:**
```python
# Get fresh outline
dry_run_result = await evolve_report(
    report_selector=report_id,
    instruction="Get current state",
    proposed_changes={},
    dry_run=True
)
current_outline = dry_run_result["current_outline"]
# Regenerate changes based on current outline
# Retry with updated changes
```

### Transient Errors

**Common Transient Errors:**
- Network timeouts
- Temporary file locks
- Database connection issues
- Resource exhaustion

**Retry Strategy:**
```python
import time
from igloo_mcp.mcp.exceptions import MCPExecutionError

async def retry_with_backoff(tool_call, max_retries=3, base_delay=1):
    """Retry tool call with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return await tool_call()
        except MCPExecutionError as e:
            # Check if error is transient
            transient_keywords = ["timeout", "lock", "connection", "temporary"]
            is_transient = any(kw in e.message.lower() for kw in transient_keywords)

            if is_transient and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            raise
    return None
```

### Error Pattern Recognition

**Common Error Patterns:**

1. **Selector Resolution Failures**
   - Pattern: Multiple tools fail with selector errors
   - Solution: Use `search_report` to verify report exists before operations

2. **Validation Cascades**
   - Pattern: Fixing one validation error reveals another
   - Solution: Use `dry_run=True` to validate all changes before applying

3. **Permission Denied**
   - Pattern: Multiple operations fail with permission errors
   - Solution: Check file system permissions on reports directory

4. **Resource Exhaustion**
   - Pattern: Operations fail after successful operations
   - Solution: Check disk space, file handles, memory

### Troubleshooting Workflows

#### Workflow 1: Report Not Found
```
1. search_report() → List all reports
2. Verify report exists in results
3. Use exact report_id from search results
4. Retry original operation
```

#### Workflow 2: Validation Errors
```
1. evolve_report(..., dry_run=True) → Get current outline
2. Review validation_errors in error response
3. Fix parameters based on current outline
4. Retry with corrected parameters
```

#### Workflow 3: Rendering Failures
```
1. render_report(..., dry_run=True) → Validate QMD generation
2. Check Quarto installation if dry_run succeeds
3. Review Quarto logs if dry_run fails
4. Fix report structure if needed
5. Retry rendering
```

#### Workflow 4: File System Issues
```
1. Check file permissions: ls -la ~/.igloo-mcp/reports/
2. Check disk space: df -h
3. Verify directory exists and is writable
4. Check for file locks
5. Retry operation
```

## Error Classification

Errors are classified by severity and exception type:

- **Fatal (MCPExecutionError)**: Cannot proceed without fixing underlying issue
  - `quarto_missing`: Must install Quarto or use dry_run
  - `render_failed`: Must fix report structure or Quarto configuration
  - `index_corruption`: Must rebuild index
  - `storage_failed`: Must fix file system issues

- **Recoverable (MCPValidationError, MCPSelectorError)**: Can retry with corrected inputs
  - `validation_failed`: Fix parameter values and retry
  - `selector_error`: Use correct selector and retry
  - `invalid_template`: Use valid template name
  - `invalid_format`: Use supported format

- **Transient**: May succeed on retry
  - Network errors, temporary file locks, concurrent modifications

## Request ID and Timing

All tools automatically generate a `request_id` if not provided, enabling:
- **Error correlation**: Track errors across tool calls
- **Request tracing**: Follow complete request lifecycle
- **Performance monitoring**: Timing information included in responses

Timing information is included in successful responses:
```json
{
  "status": "success",
  "request_id": "uuid-here",
  "timing": {
    "operation_duration_ms": 123.45,
    "total_duration_ms": 150.67
  }
}
```

## Testing Error Handling

Error scenarios are tested in:
- `tests/test_selector_resolution.py` - Selector resolution errors
- `tests/test_changes_schema.py` - Schema validation errors
- `tests/test_evolve_report_mcp.py` - MCP tool error handling
- `tests/test_render_report_tool.py` - Render tool error handling
- `tests/test_create_report_tool.py` - Create tool error handling
- `tests/test_search_report_tool.py` - Search tool error handling
- `tests/test_living_reports_integration.py` - End-to-end error scenarios

## Version Compatibility

Error response formats are backward compatible. New error types may be added but existing formats are preserved.
