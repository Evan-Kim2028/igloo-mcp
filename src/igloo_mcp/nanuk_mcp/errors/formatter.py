"""Unified error formatting utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..snow_cli import SnowCLIError


@dataclass
class ErrorContext:
    code: Optional[str] = None
    suggestion: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class UnifiedErrorFormatter:
    """Provides consistent error payloads for CLI and MCP surfaces."""

    def format_for_cli(
        self, error: Exception, *, details: ErrorContext | None = None
    ) -> str:
        base = getattr(error, "message", str(error))
        suggestion = details.suggestion if details else None
        parts = [f"[red]✗[/red] {base}"]
        if suggestion:
            parts.append(f"[dim]Suggestion: {suggestion}[/dim]")
        return "\n".join(parts)

    def format_for_mcp(
        self,
        error: Exception,
        *,
        details: ErrorContext | None = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "error": {
                "message": getattr(error, "message", str(error)),
                "type": error.__class__.__name__,
            }
        }
        if isinstance(error, SnowCLIError):
            payload["error"]["code"] = getattr(error, "code", "snowcli_error")
        if details:
            if details.code:
                payload["error"]["code"] = details.code
            if details.suggestion:
                payload["error"]["suggestion"] = details.suggestion
            if details.context:
                payload["error"]["context"] = details.context
        return payload
