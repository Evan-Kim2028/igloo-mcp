"""Living reports system - machine truth layer for auditable, LLM-assisted report generation.

This module provides the core infrastructure for living reports, which are version-controlled,
auditable documents that can be evolved by LLMs while maintaining human oversight and
traceability back to source data.

Key components:
- models.py: Pydantic models for report structure and validation
- storage.py: File system operations with locking and atomic writes
- index.py: Global report registry and title resolution
- service.py: High-level orchestration for CLI and MCP integration
"""

from .models import (
    AuditEvent,
    IndexEntry,
    Insight,
    Outline,
    ReportId,
    Section,
)

__all__ = [
    "AuditEvent",
    "IndexEntry",
    "Insight",
    "Outline",
    "ReportId",
    "Section",
]
