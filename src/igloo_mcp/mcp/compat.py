"""FastMCP import compatibility shim.

Centralises the try/except dance so every tool doesn't need its own
triple-fallback import block.
"""

from __future__ import annotations

import logging
from typing import Any

try:  # Prefer the standalone fastmcp package when available
    from fastmcp import Context as Context
    from fastmcp.utilities.logging import get_logger as get_logger
except ImportError:
    try:
        from mcp.server.fastmcp import Context as Context  # type: ignore[import-untyped,assignment,no-redef]
        from mcp.server.fastmcp.utilities.logging import (
            get_logger as get_logger,  # type: ignore[import-untyped,no-redef]
        )
    except ImportError:
        Context = Any  # type: ignore[misc,assignment]

        def get_logger(name: str) -> logging.Logger:  # type: ignore[misc]
            return logging.getLogger(name)
