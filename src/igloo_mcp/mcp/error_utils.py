"""Error handling utilities for MCP tools.

This module provides standardized error handling, formatting, and context
management for all MCP tool implementations.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

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
    request_id: Optional[str] = None,
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
    context: Optional[Dict[str, Any]] = None,
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
    validation_errors: Optional[List[str]] = None,
    hints: Optional[List[str]] = None,
    field: Optional[str] = None,
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
    original_error: Optional[Exception] = None,
    hints: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> MCPExecutionError:
    """Create a standardized execution error.

    Args:
        message: Human-readable error message
        operation: Name of the operation that failed
        original_error: Optional original exception
        hints: Optional actionable suggestions
        context: Optional additional context

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
    )


def wrap_selector_error(
    message: str,
    selector: str,
    error_type: str = "not_found",
    candidates: Optional[List[str]] = None,
    hints: Optional[List[str]] = None,
) -> MCPSelectorError:
    """Create a standardized selector error.

    Args:
        message: Human-readable error message
        selector: The selector that failed to resolve
        error_type: Type of error ("not_found", "ambiguous", "invalid_format")
        candidates: Optional list of candidate matches
        hints: Optional actionable suggestions

    Returns:
        MCPSelectorError instance
    """
    if hints is None:
        if error_type == "not_found":
            hints = [
                f"Verify selector exists: {selector}",
                "Check spelling and case sensitivity",
                "List available resources to see valid selectors",
            ]
        elif error_type == "ambiguous":
            hints = [
                f"Use a more specific selector or one of: {', '.join(candidates or [])}",
                "Provide full ID instead of partial match",
            ]
        else:
            hints = [
                "Check selector format",
                "Verify selector matches expected pattern",
            ]

    return MCPSelectorError(
        message,
        selector=selector,
        error=error_type,
        candidates=candidates or [],
        hints=hints,
    )


def format_error_response(
    error: MCPToolError,
    request_id: Optional[str] = None,
    include_traceback: bool = False,
) -> Dict[str, Any]:
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

        response["traceback"] = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )

    return response


def format_success_response(
    data: Dict[str, Any],
    request_id: Optional[str] = None,
    operation: Optional[str] = None,
) -> Dict[str, Any]:
    """Format a successful tool execution as a standardized response.

    Args:
        data: Tool-specific result data
        request_id: Optional request correlation ID
        operation: Optional operation name

    Returns:
        Standardized success response dictionary
    """
    response: Dict[str, Any] = {
        "status": "success",
        **data,
    }

    if request_id:
        response["request_id"] = request_id

    if operation:
        response["operation"] = operation

    response["timestamp"] = time.time()

    return response
