"""Structured logging helpers for Nanuk MCP."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict


def _ensure_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


@dataclass(slots=True)
class StructuredLogger:
    name: str
    logger: logging.Logger = field(init=False)

    def __post_init__(self) -> None:
        self.logger = _ensure_logger(self.name)

    def log_tool_execution(
        self,
        tool: str,
        duration: float,
        success: bool,
        **context: Any,
    ) -> None:
        payload: Dict[str, Any] = {
            "event": "tool_execution",
            "tool": tool,
            "duration_ms": round(duration * 1000, 2),
            "success": success,
        }
        if context:
            payload.update(context)
        self.logger.info(json.dumps(payload))
