"""Graph traversal algorithms for lineage analysis.

Simple BFS-based traversal for upstream/downstream dependency discovery.
"""

from __future__ import annotations

from collections import deque
from typing import Iterable, Optional

from .models import Edge, EdgeType, Graph, Node


def traverse_dependencies(
    graph: Graph,
    start: str,
    *,
    direction: str = "downstream",
    edge_types: Optional[Iterable[EdgeType]] = None,
    depth: Optional[int] = None,
) -> Graph:
    """Traverse the lineage graph from a starting node.

    Args:
        graph: The lineage graph to traverse
        start: Starting node key
        direction: Traversal direction - "upstream", "downstream", or "both"
        edge_types: Optional filter for specific edge types
        depth: Maximum traversal depth (None for unlimited)

    Returns:
        A subgraph containing all reachable nodes and edges
    """
    if start not in graph.nodes:
        return Graph()

    # Determine which edge types to follow
    if edge_types:
        allowed = set(edge_types)
    else:
        # Include all edge types that exist in the graph
        all_edge_types: set[EdgeType] = set()
        for edges_dict in graph.out_edges.values():
            all_edge_types.update(edges_dict.keys())
        for edges_dict in graph.in_edges.values():
            all_edge_types.update(edges_dict.keys())
        # Default to all enum values if no edges exist yet
        allowed = (
            all_edge_types
            if all_edge_types
            else {EdgeType.DERIVES_FROM, EdgeType.PRODUCES, EdgeType.CONSUMES}
        )

    subgraph = Graph()
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    visited = {start}

    while queue:
        node_key, dist = queue.popleft()
        node = graph.nodes[node_key]

        # Add node to subgraph
        subgraph.add_node(Node(node.key, node.node_type, dict(node.attributes)))

        # Determine which edge maps to traverse
        iterator = []
        if direction in {"downstream", "both"}:
            iterator.append((graph.out_edges, True))
        if direction in {"upstream", "both"}:
            iterator.append((graph.in_edges, False))

        for edge_map, forward in iterator:
            for edge_type, neighbors in edge_map.get(node_key, {}).items():
                if edge_type not in allowed:
                    continue
                for neighbor in neighbors:
                    # Determine edge direction
                    src, dst = (node_key, neighbor) if forward else (neighbor, node_key)
                    evidence = graph.edge_metadata.get((src, dst, edge_type), {})

                    # Add neighbor node
                    neighbor_node = graph.nodes[neighbor]
                    subgraph.add_node(
                        Node(
                            neighbor_node.key,
                            neighbor_node.node_type,
                            dict(neighbor_node.attributes),
                        )
                    )

                    # Add edge
                    subgraph.add_edge(Edge(src, dst, edge_type, dict(evidence)))

                    # Queue neighbor if not visited and within depth limit
                    if neighbor not in visited and (depth is None or dist + 1 <= depth):
                        visited.add(neighbor)
                        queue.append((neighbor, dist + 1))

    return subgraph
