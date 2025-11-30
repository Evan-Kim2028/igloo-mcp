"""Base class for MCP tools using command pattern.

Part of v1.8.0 Phase 2.2 - MCP server simplification.
"""

from __future__ import annotations

import functools
import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import (
    Any,
    ParamSpec,
    TypeVar,
    cast,
    overload,
)

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


from igloo_mcp.mcp.error_utils import (
    handle_generic_exception_decorator,
    handle_mcp_exception_decorator,
    handle_validation_error_decorator,
)
from igloo_mcp.mcp.exceptions import (
    MCPExecutionError,
    MCPToolError,
    MCPValidationError,
)

T = TypeVar("T")
P = ParamSpec("P")


def ensure_request_id(request_id: str | None = None) -> str:
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
    async def execute(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
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
    def get_parameter_schema(self) -> dict[str, Any]:
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
    def usage_examples(self) -> list[dict[str, Any]]:
        """Example invocations (parameter sets) with brief context."""
        return []

    def validate_parameters(self, params: dict[str, Any]) -> dict[str, Any]:
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
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
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

    @overload
    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]: ...

    @overload
    def decorator(func: Callable[P, T]) -> Callable[P, T]: ...

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_logger(f"igloo_mcp.mcp.tools.{tool_name}")
            request_id = kwargs.get("request_id")

            try:
                return await cast(Callable[P, Awaitable[T]], func)(*args, **kwargs)
            except (MCPValidationError, MCPExecutionError, MCPToolError) as mcp_error:
                handle_mcp_exception_decorator(mcp_error, request_id, kwargs)
            except TypeError:
                # Bubble TypeError so tests and callers get the original signature issue
                raise
            except ValidationError as e:
                handle_validation_error_decorator(e, request_id, tool_name, logger, kwargs)
            except Exception as e:
                handle_generic_exception_decorator(e, request_id, tool_name, logger, kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Handle synchronous functions (though most tools are async)
            logger = get_logger(f"igloo_mcp.mcp.tools.{tool_name}")
            request_id = kwargs.get("request_id")

            try:
                return func(*args, **kwargs)
            except (MCPValidationError, MCPExecutionError, MCPToolError) as mcp_error:
                handle_mcp_exception_decorator(mcp_error, request_id, kwargs)
            except ValidationError as e:
                handle_validation_error_decorator(e, request_id, tool_name, logger, kwargs)
            except Exception as e:
                handle_generic_exception_decorator(e, request_id, tool_name, logger, kwargs)

        # Return appropriate wrapper based on whether function is async
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
