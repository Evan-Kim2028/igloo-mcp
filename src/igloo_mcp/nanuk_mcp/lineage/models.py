"""Core data models for lineage graphs.

Simplified lineage models containing only essential Node, Edge, and Graph structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, cast


class NodeType(str, Enum):
    """Type of node in the lineage graph."""

    DATASET = "dataset"
    TASK = "task"


class EdgeType(str, Enum):
    """Type of edge in the lineage graph."""

    DERIVES_FROM = "derives_from"
    PRODUCES = "produces"
    CONSUMES = "consumes"


@dataclass
class Node:
    """A node in the lineage graph representing a data object or task."""

    key: str
    node_type: NodeType
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class Edge:
    """An edge in the lineage graph representing a dependency relationship."""

    src: str
    dst: str
    edge_type: EdgeType
    evidence: Dict[str, str] = field(default_factory=dict)

    @property
    def source(self) -> str:
        """Compatibility property for source."""
        return self.src

    @property
    def target(self) -> str:
        """Compatibility property for target."""
        return self.dst


class Graph:
    """A directed graph representing lineage relationships."""

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.out_edges: Dict[str, Dict[EdgeType, set[str]]] = {}
        self.in_edges: Dict[str, Dict[EdgeType, set[str]]] = {}
        self.edge_metadata: Dict[tuple[str, str, EdgeType], Dict[str, str]] = {}

    def set_node_type(self, key: str, node_type: NodeType) -> None:
        """Set the type of a node (for backward compatibility with builder.py)."""
        if key in self.nodes:
            self.nodes[key].node_type = node_type
        else:
            self.add_node(Node(key, node_type))

    def add_node(self, node: Node) -> None:
        """Add a node to the graph."""
        if node.key not in self.nodes:
            self.nodes[node.key] = node
            self.out_edges[node.key] = {}
            self.in_edges[node.key] = {}
        else:
            # Update existing node attributes
            existing = self.nodes[node.key]
            existing.attributes.update(node.attributes)

    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the graph."""
        # Ensure both nodes exist
        if edge.src not in self.nodes:
            self.add_node(Node(edge.src, NodeType.DATASET))
        if edge.dst not in self.nodes:
            self.add_node(Node(edge.dst, NodeType.DATASET))

        # Add edge to adjacency structures
        self.out_edges.setdefault(edge.src, {}).setdefault(edge.edge_type, set()).add(
            edge.dst
        )
        self.in_edges.setdefault(edge.dst, {}).setdefault(edge.edge_type, set()).add(
            edge.src
        )
        self.edge_metadata[(edge.src, edge.dst, edge.edge_type)] = edge.evidence

    @property
    def edges(self) -> List[Edge]:
        """Get all edges in the graph."""
        edges = []
        for src, edge_types in self.out_edges.items():
            for edge_type, dsts in edge_types.items():
                for dst in dsts:
                    evidence = self.edge_metadata.get((src, dst, edge_type), {})
                    edges.append(Edge(src, dst, edge_type, evidence))
        return edges

    def to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        """Convert graph to dictionary format."""
        return {
            "nodes": [
                {
                    "key": node.key,
                    "type": (
                        node.node_type.value
                        if isinstance(node.node_type, NodeType)
                        else node.node_type
                    ),
                    "attributes": cast(Dict[str, Any], dict(node.attributes)),
                }
                for node in self.nodes.values()
            ],
            "edges": [
                {
                    "src": src,
                    "dst": dst,
                    "type": (
                        edge_type.value
                        if isinstance(edge_type, EdgeType)
                        else edge_type
                    ),
                    "evidence": cast(Dict[str, Any], dict(evidence)),
                }
                for (src, dst, edge_type), evidence in self.edge_metadata.items()
            ],
        }

    def traverse(
        self,
        start: str,
        *,
        direction: str = "downstream",
        edge_types: Any = None,
        depth: Any = None,
    ) -> "Graph":
        """Traverse the graph (delegates to traversal.py for backward compatibility)."""
        from .traversal import traverse_dependencies

        return traverse_dependencies(
            self, start, direction=direction, edge_types=edge_types, depth=depth
        )

    @classmethod
    def from_dict(cls, payload: Dict[str, List[Dict[str, Any]]]) -> "Graph":
        """Create graph from dictionary format."""
        graph = cls()
        for node in payload.get("nodes", []):
            node_type = node["type"]
            if not isinstance(node_type, NodeType):
                try:
                    node_type = NodeType(node_type)
                except (ValueError, KeyError):
                    pass
            graph.add_node(
                Node(
                    key=node["key"],
                    node_type=node_type,
                    attributes=node.get("attributes", {}),
                )
            )
        for edge in payload.get("edges", []):
            edge_type = edge["type"]
            if not isinstance(edge_type, EdgeType):
                try:
                    edge_type = EdgeType(edge_type)
                except (ValueError, KeyError):
                    pass
            graph.add_edge(
                Edge(
                    src=edge["src"],
                    dst=edge["dst"],
                    edge_type=edge_type,
                    evidence=edge.get("evidence", {}),
                )
            )
        return graph
