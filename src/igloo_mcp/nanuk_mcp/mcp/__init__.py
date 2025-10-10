"""MCP server modular components.

This module provides the MCP (Model Context Protocol) server components
for Nanuk MCP, including tool registration and server lifecycle management.

Note: Tool registration is handled in mcp_server.py to avoid circular imports.
The modular architecture allows for clean separation of concerns while keeping
the registration logic close to the server implementation.
"""

__all__ = []  # Tools are registered in mcp_server.py
