"""Unified dependency module for Snowflake object dependency analysis.

This module consolidates dependency functionality that was previously spread across:
- dependency.py (core implementation, 221 LOC)
- service_layer/dependency.py (wrapper service, 61 LOC)

Total: 282 LOC consolidated into 250 LOC service.py
Reduction: ~32 LOC (11%)

Part of v1.8.0 refactoring Phase 1.2
"""

from __future__ import annotations

from .models import (
    DependencyCounts,
    DependencyEdge,
    DependencyGraph,
    DependencyNode,
    DependencyScope,
)
from .service import DependencyService, build_dependency_graph, to_dot

__all__ = [
    "DependencyService",
    "build_dependency_graph",
    "to_dot",
    "DependencyGraph",
    "DependencyNode",
    "DependencyEdge",
    "DependencyCounts",
    "DependencyScope",
]
