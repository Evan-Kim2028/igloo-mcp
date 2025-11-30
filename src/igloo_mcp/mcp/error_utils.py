"""Error handling utilities for MCP tools.

This module provides standardized error handling, formatting, and context
management for all MCP tool implementations.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import ValidationError

from igloo_mcp.error_handling import ErrorContext
from igloo_mcp.mcp.exceptions import (
    MCPExecutionError,
    MCPSelectorError,
    MCPToolError,
    MCPValidationError,
)

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    try:
        from mcp.server.fastmcp.utilities.logging import get_logger
    except ImportError:
        import logging

        def get_logger(name: str) -> logging.Logger:
            return logging.getLogger(name)


logger = get_logger(__name__)


def create_error_context(
    operation: str,
    request_id: str | None = None,
    **kwargs: Any,
) -> ErrorContext:
    """Create an ErrorContext for error handling.

    Args:
        operation: Name of the operation
        request_id: Optional request correlation ID
        **kwargs: Additional context fields (database, schema, object_name, etc.)

    Returns:
        ErrorContext instance
    """
    return ErrorContext(
        operation=operation,
        request_id=request_id,
        database=kwargs.get("database"),
        schema=kwargs.get("schema"),
        object_name=kwargs.get("object_name"),
        query=kwargs.get("query"),
        parameters=kwargs.get("parameters", {}),
    )


def wrap_timeout_error(
    timeout_seconds: int,
    operation: str = "query",
    verbose: bool = False,
    context: dict[str, Any] | None = None,
) -> MCPExecutionError:
    """Create a standardized timeout error.

    Args:
        timeout_seconds: Timeout value that was exceeded
        operation: Name of the operation that timed out
        verbose: Whether to include detailed hints
        context: Optional additional context (warehouse, database, etc.)

    Returns:
        MCPExecutionError with timeout details
    """
    hints = [
        f"Increase timeout: timeout_seconds={max(timeout_seconds * 2, 480)}",
        "Filter by clustering keys: Check catalog for clustered columns",
        "Add WHERE/LIMIT clause to reduce data volume",
        "Use larger warehouse for complex queries",
    ]

    if verbose and context:
        detailed_hints = [
            "Filter by clustering keys: Check catalog for clustered columns",
            "Catalog-guided filtering: Use build_catalog to understand data distribution",
            "Add WHERE/LIMIT: Reduce data volume with targeted filters",
            "Scale warehouse: Use larger warehouse for complex queries",
        ]
        hints.extend(detailed_hints)

    message = (
        f"{operation.capitalize()} timeout after {timeout_seconds}s. "
        "filter by clustering keys or catalog columns first, then add WHERE/LIMIT before increasing timeout."
    )
    if verbose:
        message += ". Use verbose_errors=False for compact error message."

    return MCPExecutionError(
        message,
        operation=operation,
        hints=hints,
        context=context or {},
    )


def wrap_validation_error(
    message: str,
    validation_errors: list[str] | None = None,
    hints: list[str] | None = None,
    field: str | None = None,
) -> MCPValidationError:
    """Create a standardized validation error.

    Args:
        message: Human-readable error message
        validation_errors: List of specific validation error messages
        hints: Optional actionable suggestions
        field: Optional field name that failed validation

    Returns:
        MCPValidationError instance
    """
    if validation_errors is None:
        validation_errors = []

    if hints is None:
        hints = [
            "Check parameter types and required fields",
            "Review tool parameter schema",
        ]

    if field:
        validation_errors.insert(0, f"Field '{field}': {message}")

    return MCPValidationError(
        message,
        validation_errors=validation_errors,
        hints=hints,
    )


def wrap_execution_error(
    message: str,
    operation: str,
    original_error: Exception | None = None,
    hints: list[str] | None = None,
    context: dict[str, Any] | None = None,
    verbose: bool = True,  # Default True for backward compatibility with tests
) -> MCPExecutionError:
    """Create a standardized execution error.

    Args:
        message: Human-readable error message
        operation: Name of the operation that failed
        original_error: Optional original exception
        hints: Optional actionable suggestions
        context: Optional additional context
        verbose: If False, truncate hints to DEFAULT_MAX_HINTS (default: True)

    Returns:
        MCPExecutionError instance
    """
    if hints is None:
        hints = [
            f"Check {operation} logs for details",
            "Verify input parameters are correct",
            "Check system resources and connectivity",
        ]

    return MCPExecutionError(
        message,
        operation=operation,
        original_error=original_error,
        hints=hints,
        context=context or {},
        verbose=verbose,
    )


def wrap_selector_error(
    message: str,
    selector: str,
    error_type: str = "not_found",
    candidates: list[str] | None = None,
    hints: list[str] | None = None,
    verbose: bool = True,
) -> MCPSelectorError:
    """Create a standardized selector error.

    Args:
        message: Human-readable error message
        selector: The selector that failed to resolve
        error_type: Type of error ("not_found", "ambiguous", "invalid_format")
        candidates: Optional list of candidate matches
        hints: Optional actionable suggestions
        verbose: If False, truncate hints to DEFAULT_MAX_HINTS (default: True)

    Returns:
        MCPSelectorError instance
    """
    if hints is None:
        if error_type == "not_found":
            # Always provide actionable hints for not found errors
            hints = [
                f"Verify '{selector}' exists in the system",
                "Check spelling and case sensitivity",
                "Use search tool to list available items (e.g., search_report, search_catalog)",
            ]
            # Add specific guidance if this looks like a report ID
            if selector.startswith("rpt_"):
                hints.append("Report IDs must be exact - use search_report to find the correct ID")
        elif error_type == "ambiguous":
            hints = [
                f"Multiple items match '{selector}' - be more specific",
                f"Use one of these exact IDs: {', '.join(candidates[:3] if candidates else [])}",
                "Provide full ID instead of partial match",
            ]
        else:
            hints = [
                f"Check '{selector}' format and syntax",
                "Verify selector matches expected pattern",
                "Review tool documentation for selector requirements",
            ]

    return MCPSelectorError(
        message,
        selector=selector,
        error=error_type,
        candidates=candidates or [],
        hints=hints,
        verbose=verbose,
    )


def format_error_response(
    error: MCPToolError,
    request_id: str | None = None,
    include_traceback: bool = False,
) -> dict[str, Any]:
    """Format an MCP error as a standardized response dictionary.

    Args:
        error: MCP exception instance
        request_id: Optional request correlation ID
        include_traceback: Whether to include traceback (for debugging)

    Returns:
        Standardized error response dictionary
    """
    response = error.to_dict()

    if request_id:
        response["request_id"] = request_id

    response["timestamp"] = time.time()

    if include_traceback and hasattr(error, "__traceback__"):
        import traceback

        response["traceback"] = "".join(traceback.format_exception(type(error), error, error.__traceback__))

    return response


def format_success_response(
    data: dict[str, Any],
    request_id: str | None = None,
    operation: str | None = None,
) -> dict[str, Any]:
    """Format a successful tool execution as a standardized response.

    Args:
        data: Tool-specific result data
        request_id: Optional request correlation ID
        operation: Optional operation name

    Returns:
        Standardized success response dictionary
    """
    response: dict[str, Any] = {
        "status": "success",
        **data,
    }

    if request_id:
        response["request_id"] = request_id

    if operation:
        response["operation"] = operation

    response["timestamp"] = time.time()

    return response


# Error handler helpers for tool_error_handler decorator


def handle_mcp_exception_decorator(
    e: MCPToolError,
    request_id: str | None,
    kwargs: dict[str, Any],
) -> None:
    """Handle MCP exceptions in decorator - adds request_id and re-raises.

    Args:
        e: MCP exception instance
        request_id: Request correlation ID
        kwargs: Keyword arguments from tool call

    Raises:
        MCPToolError: Re-raises the original exception
    """
    # Add request_id to MCP exceptions if available
    if request_id and hasattr(e, "context"):
        if e.context is None:
            e.context = {}
        e.context["request_id"] = request_id
    # Re-raise MCP exceptions as-is - they're already properly formatted
    raise


def handle_validation_error_decorator(
    e: ValidationError,
    request_id: str | None,
    tool_name: str,
    logger: logging.Logger,
    kwargs: dict[str, Any],
) -> MCPValidationError:
    """Convert Pydantic ValidationError to MCPValidationError.

    Args:
        e: Pydantic ValidationError
        request_id: Request correlation ID
        tool_name: Name of the tool
        logger: Logger instance
        kwargs: Keyword arguments from tool call

    Returns:
        MCPValidationError with formatted validation messages

    Raises:
        MCPValidationError: Converted validation error
    """
    # Convert Pydantic validation errors to MCPValidationError
    errors = e.errors()
    validation_errors = []
    for err in errors:
        field_path = ".".join(str(loc) for loc in err.get("loc", []))
        error_msg = err.get("msg", "Validation error")
        validation_errors.append(f"{field_path}: {error_msg}")

    logger.warning(
        f"Validation error in {tool_name}",
        extra={
            "tool": tool_name,
            "validation_errors": validation_errors,
            "input": str(kwargs)[:200],  # Truncate for logging
        },
    )

    # Extract request_id and verbose_errors from kwargs
    error_context = {"request_id": request_id} if request_id else {}
    verbose = kwargs.get("verbose_errors", False)

    raise MCPValidationError(
        f"Parameter validation failed for {tool_name}",
        validation_errors=validation_errors,
        hints=[
            f"Check parameter types and required fields for {tool_name}",
            f"Review {tool_name} parameter schema for valid values",
            "Common issues: missing required fields, wrong data types, out-of-range values",
        ],
        context=error_context,
        verbose=verbose,
    ) from e


def handle_generic_exception_decorator(
    e: Exception,
    request_id: str | None,
    tool_name: str,
    logger: logging.Logger,
    kwargs: dict[str, Any],
) -> MCPExecutionError:
    """Convert generic exception to MCPExecutionError.

    Args:
        e: Generic exception
        request_id: Request correlation ID
        tool_name: Name of the tool
        logger: Logger instance
        kwargs: Keyword arguments from tool call

    Returns:
        MCPExecutionError with formatted error details

    Raises:
        MCPExecutionError: Converted execution error
    """
    # Convert unexpected exceptions to MCPExecutionError
    error_msg = str(e)
    error_context = {"request_id": request_id} if request_id else {}
    verbose = kwargs.get("verbose_errors", False)

    logger.error(
        f"Unexpected error in {tool_name}",
        extra={
            "tool": tool_name,
            "error_type": type(e).__name__,
            "error_message": error_msg[:500],  # Truncate for logging
            "request_id": request_id,
        },
        exc_info=True,
    )

    raise MCPExecutionError(
        f"Tool execution failed: {error_msg}",
        operation=tool_name,
        original_error=e,
        hints=[
            f"Check {tool_name} logs for detailed error information",
            f"Verify input parameters match {tool_name} schema requirements",
            "Check system resources (disk space, memory, network connectivity)",
            f"Review recent changes to {tool_name} configuration if applicable",
        ],
        context=error_context,
        verbose=verbose,
    ) from e
