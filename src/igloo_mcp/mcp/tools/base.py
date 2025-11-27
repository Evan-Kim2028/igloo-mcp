"""Base class for MCP tools using command pattern.

Part of v1.8.0 Phase 2.2 - MCP server simplification.
"""

from __future__ import annotations

import functools
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, TypeVar

from pydantic import BaseModel, ValidationError

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    try:
        from mcp.server.fastmcp.utilities.logging import get_logger
    except ImportError:
        # Fallback to standard logging if FastMCP logging unavailable
        def get_logger(name: str) -> logging.Logger:
            return logging.getLogger(name)


from igloo_mcp.mcp.exceptions import (
    MCPExecutionError,
    MCPToolError,
    MCPValidationError,
)

T = TypeVar("T")


def ensure_request_id(request_id: Optional[str] = None) -> str:
    """Ensure a request_id exists, generating one if not provided.

    Args:
        request_id: Optional request correlation ID

    Returns:
        Request ID (provided or newly generated)
    """
    return request_id if request_id else str(uuid.uuid4())


class MCPToolSchema(BaseModel):
    """Base schema for MCP tool parameters."""

    pass


class MCPTool(ABC):
    """Base class for MCP tools implementing command pattern.

    Benefits:
    - Each tool is self-contained and testable
    - Clear separation of concerns
    - Easy to add new tools
    - Consistent interface across all tools
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for MCP registration.

        Returns:
            The unique name of the tool (e.g., "execute_query")
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for AI agents.

        Returns:
            Human-readable description of what the tool does
        """
        pass

    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Execute the tool's main logic.

        Args:
            *args: Positional arguments (tool-specific)
            **kwargs: Tool-specific parameters

        Returns:
            Tool execution result as a dictionary

        Raises:
            ValueError: For validation errors
            RuntimeError: For execution errors
        """
        pass

    @abstractmethod
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters.

        Returns:
            JSON schema dictionary compatible with MCP specification
        """
        pass

    @property
    def category(self) -> str:
        """High-level tool category used for discovery metadata.

        Returns:
            Category string (e.g., "query", "metadata", "diagnostics")
        """
        return "uncategorized"

    @property
    def tags(self) -> list[str]:
        """Searchable metadata tags for MCP tool discovery."""
        return []

    @property
    def usage_examples(self) -> list[Dict[str, Any]]:
        """Example invocations (parameter sets) with brief context."""
        return []

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and coerce parameters before execution.

        Override this method for custom validation logic.

        Args:
            params: Raw parameters dictionary

        Returns:
            Validated parameters dictionary

        Raises:
            MCPValidationError: If parameters are invalid
        """
        return params


def tool_error_handler(
    tool_name: str,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for consistent error handling in MCP tools.

    This decorator provides standardized error handling for all MCP tool
    execute methods. It:
    - Catches and wraps exceptions in appropriate MCP exception types
    - Logs errors with context
    - Preserves MCP exception types (re-raises as-is)
    - Converts ValidationError to MCPValidationError
    - Converts other exceptions to MCPExecutionError

    Args:
        tool_name: Name of the tool (for logging and error context)

    Returns:
        Decorator function

    Example:
        ```python
        @tool_error_handler("my_tool")
        async def execute(self, param: str) -> Dict[str, Any]:
            # Tool implementation
            pass
        ```
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            logger = get_logger(f"igloo_mcp.mcp.tools.{tool_name}")

            try:
                return await func(*args, **kwargs)
            except (MCPValidationError, MCPExecutionError, MCPToolError) as mcp_error:
                # Add request_id to MCP exceptions if available in kwargs
                request_id = kwargs.get("request_id")
                if request_id and hasattr(mcp_error, "context"):
                    if mcp_error.context is None:
                        mcp_error.context = {}
                    mcp_error.context["request_id"] = request_id
                # Re-raise MCP exceptions as-is - they're already properly formatted
                raise
            except TypeError:
                # Bubble TypeError so tests and callers get the original signature issue
                raise
            except ValidationError as e:
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

                # Extract request_id from kwargs if available
                request_id = kwargs.get("request_id")
                error_context = {"request_id": request_id} if request_id else {}

                raise MCPValidationError(
                    f"Parameter validation failed for {tool_name}",
                    validation_errors=validation_errors,
                    hints=[
                        f"Check parameter types and required fields for {tool_name}",
                        f"Review {tool_name} parameter schema for valid values",
                        "Common issues: missing required fields, wrong data types, out-of-range values",
                    ],
                    context=error_context,
                ) from e
            except Exception as e:
                # Convert unexpected exceptions to MCPExecutionError
                error_msg = str(e)
                request_id = kwargs.get("request_id")
                error_context = {"request_id": request_id} if request_id else {}

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
                ) from e

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            # Handle synchronous functions (though most tools are async)
            logger = get_logger(f"igloo_mcp.mcp.tools.{tool_name}")

            try:
                return func(*args, **kwargs)
            except (MCPValidationError, MCPExecutionError, MCPToolError) as mcp_error:
                # Add request_id to MCP exceptions if available in kwargs
                request_id = kwargs.get("request_id")
                if request_id and hasattr(mcp_error, "context"):
                    if mcp_error.context is None:
                        mcp_error.context = {}
                    mcp_error.context["request_id"] = request_id
                # Re-raise MCP exceptions as-is
                raise
            except ValidationError as e:
                # Convert Pydantic validation errors to MCPValidationError
                errors = e.errors()
                validation_errors = []
                for err in errors:
                    field_path = ".".join(str(loc) for loc in err.get("loc", []))
                    error_msg = err.get("msg", "Validation error")
                    validation_errors.append(f"{field_path}: {error_msg}")

                request_id = kwargs.get("request_id")
                error_context = {"request_id": request_id} if request_id else {}

                logger.warning(
                    f"Validation error in {tool_name}",
                    extra={
                        "tool": tool_name,
                        "validation_errors": validation_errors,
                        "request_id": request_id,
                    },
                )

                raise MCPValidationError(
                    f"Parameter validation failed for {tool_name}",
                    validation_errors=validation_errors,
                    hints=[
                        f"Check parameter types and required fields for {tool_name}",
                        f"Review {tool_name} parameter schema for valid values",
                        "Common issues: missing required fields, wrong data types, out-of-range values",
                    ],
                    context=error_context,
                ) from e
            except Exception as e:
                # Convert unexpected exceptions to MCPExecutionError
                error_msg = str(e)
                request_id = kwargs.get("request_id")
                error_context = {"request_id": request_id} if request_id else {}

                logger.error(
                    f"Unexpected error in {tool_name}",
                    extra={
                        "tool": tool_name,
                        "error_type": type(e).__name__,
                        "error_message": error_msg[:500],
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
                ) from e

        # Return appropriate wrapper based on whether function is async
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
