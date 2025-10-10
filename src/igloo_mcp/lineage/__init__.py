"""Simplified lineage package for building and querying Snowflake lineage graphs.

This module provides core lineage functionality with a focus on simplicity and
maintainability.
"""

# Backward compatibility - keep existing builder and loader
from .builder import LineageBuilder
from .exceptions import LineageException, LineageParseError, ObjectNotFoundException

# Core simplified lineage components
from .format import format_as_dot, format_as_mermaid, format_as_text
from .loader import CatalogLoader, CatalogObject
from .logging_config import get_logger, setup_logging
from .models import Edge, EdgeType, Graph, Node, NodeType
from .queries import LineageQueryService
from .traversal import traverse_dependencies

# Advanced lineage features (new in v2.0)
from .column_parser import ColumnLineageExtractor
from .history import LineageHistoryManager
from .impact import ChangeType, ImpactAnalyzer

# Backward compatibility alias
LineageGraph = Graph
LineageNode = Node
LineageEdge = Edge

# Setup default logging
setup_logging(level="INFO")

__all__ = [
    # Core models
    "Graph",
    "Node",
    "Edge",
    "NodeType",
    "EdgeType",
    # Traversal
    "traverse_dependencies",
    # Formatting
    "format_as_text",
    "format_as_mermaid",
    "format_as_dot",
    # Builders and loaders (kept for backward compatibility)
    "LineageBuilder",
    "CatalogLoader",
    "CatalogObject",
    "LineageQueryService",
    # Advanced lineage features
    "ColumnLineageExtractor",
    "LineageHistoryManager",
    "ImpactAnalyzer",
    "ChangeType",
    # Exceptions
    "LineageException",
    "LineageParseError",
    "ObjectNotFoundException",
    # Logging
    "setup_logging",
    "get_logger",
    # Backward compatibility aliases
    "LineageGraph",
    "LineageNode",
    "LineageEdge",
]
