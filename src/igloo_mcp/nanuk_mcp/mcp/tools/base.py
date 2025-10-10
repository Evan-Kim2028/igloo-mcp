"""Base class for MCP tools using command pattern.

Part of v1.8.0 Phase 2.2 - MCP server simplification.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from pydantic import BaseModel


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

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and coerce parameters before execution.

        Override this method for custom validation logic.

        Args:
            params: Raw parameters dictionary

        Returns:
            Validated parameters dictionary

        Raises:
            ValueError: If parameters are invalid
        """
        return params
