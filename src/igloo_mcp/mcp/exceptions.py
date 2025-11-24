"""MCP-specific exception classes for consistent error handling.

These exceptions are used throughout the MCP tool implementations to provide
structured, machine-readable error responses that follow MCP protocol standards.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class MCPToolError(Exception):
    """Base exception class for all MCP tool errors.

    This is the base class for all MCP-specific exceptions. It provides
    a consistent structure for error responses that can be serialized
    and returned to MCP clients.

    Attributes:
        message: Human-readable error message
        error_code: Optional error code for programmatic handling
        hints: Optional list of actionable suggestions
        context: Optional additional context data
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: Optional[str] = None,
        hints: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize MCP tool error.

        Args:
            message: Human-readable error message
            error_code: Optional error code for programmatic handling
            hints: Optional list of actionable suggestions
            context: Optional additional context data
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.hints = hints or []
        self.context = context or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the error
        """
        result: Dict[str, Any] = {
            "message": self.message,
            "error_type": self.__class__.__name__,
        }
        if self.error_code:
            result["error_code"] = self.error_code
        if self.hints:
            result["hints"] = self.hints
        if self.context:
            result["context"] = self.context
        return result


class MCPValidationError(MCPToolError):
    """Raised when tool parameters fail validation.

    This exception is used when input parameters don't meet the tool's
    requirements (e.g., missing required fields, invalid types, out-of-range values).

    Attributes:
        validation_errors: List of specific validation error messages
    """

    def __init__(
        self,
        message: str,
        *,
        validation_errors: Optional[List[str]] = None,
        hints: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize validation error.

        Args:
            message: Human-readable error message
            validation_errors: List of specific validation error messages
            hints: Optional list of actionable suggestions
            context: Optional additional context data
        """
        super().__init__(
            message,
            error_code="VALIDATION_ERROR",
            hints=hints,
            context=context,
        )
        self.validation_errors = validation_errors or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the error
        """
        result = super().to_dict()
        if self.validation_errors:
            result["validation_errors"] = self.validation_errors
        return result


class MCPExecutionError(MCPToolError):
    """Raised when tool execution fails.

    This exception is used when a tool's execution fails due to runtime
    errors (e.g., database connection failures, query execution errors,
    file system errors).

    Attributes:
        operation: Name of the operation that failed
        original_error: Optional original exception that caused this error
    """

    def __init__(
        self,
        message: str,
        *,
        operation: Optional[str] = None,
        original_error: Optional[Exception] = None,
        hints: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize execution error.

        Args:
            message: Human-readable error message
            operation: Name of the operation that failed
            original_error: Optional original exception that caused this error
            hints: Optional list of actionable suggestions
            context: Optional additional context data
        """
        super().__init__(
            message,
            error_code="EXECUTION_ERROR",
            hints=hints,
            context=context,
        )
        self.operation = operation
        self.original_error = original_error

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the error
        """
        result = super().to_dict()
        if self.operation:
            result["operation"] = self.operation
        if self.original_error:
            result["original_error"] = str(self.original_error)
        return result


class MCPSelectorError(MCPToolError):
    """Raised when a selector (ID, name, etc.) cannot be resolved.

    This exception is used when a tool cannot find or uniquely identify
    a resource based on the provided selector (e.g., report ID, catalog path).

    Attributes:
        selector: The selector that failed to resolve
        error: Type of selector error ("not_found", "ambiguous", "invalid_format")
        candidates: Optional list of candidate matches (for ambiguous errors)
    """

    def __init__(
        self,
        message: str,
        *,
        selector: Optional[str] = None,
        error: Optional[str] = None,
        candidates: Optional[List[str]] = None,
        hints: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize selector error.

        Args:
            message: Human-readable error message
            selector: The selector that failed to resolve
            error: Type of selector error ("not_found", "ambiguous", "invalid_format")
            candidates: Optional list of candidate matches (for ambiguous errors)
            hints: Optional list of actionable suggestions
            context: Optional additional context data
        """
        super().__init__(
            message,
            error_code="SELECTOR_ERROR",
            hints=hints,
            context=context,
        )
        self.selector = selector
        self.error = error or "not_found"
        self.candidates = candidates or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the error
        """
        result = super().to_dict()
        if self.selector:
            result["selector"] = self.selector
        result["error"] = self.error
        if self.candidates:
            result["candidates"] = self.candidates
        return result
