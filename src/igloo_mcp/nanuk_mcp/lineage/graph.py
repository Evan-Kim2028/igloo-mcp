"""Backward compatibility module for graph.py.

This module re-exports the new simplified models for backward compatibility.
Direct imports from .graph will continue to work.
"""

from __future__ import annotations

from .models import Edge as LineageEdge
from .models import EdgeType
from .models import Graph as LineageGraph
from .models import Node as LineageNode
from .models import NodeType
from .traversal import traverse_dependencies

# Re-export for backward compatibility
__all__ = [
    "LineageNode",
    "LineageEdge",
    "LineageGraph",
    "NodeType",
    "EdgeType",
    "traverse_dependencies",
]
