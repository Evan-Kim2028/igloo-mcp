"""Formatting utilities for lineage graphs.

Export lineage graphs to various formats: text, Mermaid, DOT.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Graph


def format_as_text(graph: Graph, *, show_attributes: bool = False) -> str:
    """Format graph as human-readable text.

    Args:
        graph: The lineage graph to format
        show_attributes: Whether to include node attributes

    Returns:
        Text representation of the graph
    """
    lines = []
    lines.append(f"Lineage Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges\n")

    # Group edges by source
    edges_by_src: dict[str, list] = {}
    for edge in graph.edges:
        edges_by_src.setdefault(edge.src, []).append(edge)

    # Format each node and its outgoing edges
    for node_key in sorted(graph.nodes.keys()):
        node = graph.nodes[node_key]
        lines.append(f"\n{node_key} ({node.node_type.value})")

        if show_attributes and node.attributes:
            for attr_key, attr_value in sorted(node.attributes.items()):
                lines.append(f"  - {attr_key}: {attr_value}")

        # Show outgoing edges
        if node_key in edges_by_src:
            for edge in sorted(edges_by_src[node_key], key=lambda e: e.dst):
                lines.append(f"  → {edge.dst} ({edge.edge_type.value})")

    return "\n".join(lines)


def format_as_mermaid(graph: Graph) -> str:
    """Format graph as Mermaid diagram syntax.

    Args:
        graph: The lineage graph to format

    Returns:
        Mermaid diagram code
    """
    lines = ["graph TD"]

    # Add nodes with labels
    for node in graph.nodes.values():
        node_id = _safe_id(node.key)
        label = node.key.split(".")[-1]  # Use just the object name
        if node.node_type.value == "task":
            lines.append(f'  {node_id}["{label} (task)"]')
        else:
            lines.append(f'  {node_id}["{label}"]')

    # Add edges
    for edge in graph.edges:
        src_id = _safe_id(edge.src)
        dst_id = _safe_id(edge.dst)
        if edge.edge_type.value == "derives_from":
            lines.append(f"  {dst_id} -->|derives| {src_id}")
        elif edge.edge_type.value == "produces":
            lines.append(f"  {src_id} -->|produces| {dst_id}")
        elif edge.edge_type.value == "consumes":
            lines.append(f"  {src_id} -->|consumes| {dst_id}")

    return "\n".join(lines)


def format_as_dot(graph: Graph) -> str:
    """Format graph as GraphViz DOT format.

    Args:
        graph: The lineage graph to format

    Returns:
        DOT format graph
    """
    lines = ["digraph lineage {"]
    lines.append("  rankdir=LR;")
    lines.append("  node [shape=box, style=rounded];")

    # Add nodes
    for node in graph.nodes.values():
        node_id = _safe_id(node.key)
        label = node.key
        if node.node_type.value == "task":
            lines.append(f'  {node_id} [label="{label}", shape=ellipse];')
        else:
            lines.append(f'  {node_id} [label="{label}"];')

    # Add edges
    for edge in graph.edges:
        src_id = _safe_id(edge.src)
        dst_id = _safe_id(edge.dst)
        label = edge.edge_type.value
        if edge.edge_type.value == "derives_from":
            lines.append(f'  {dst_id} -> {src_id} [label="{label}"];')
        else:
            lines.append(f'  {src_id} -> {dst_id} [label="{label}"];')

    lines.append("}")
    return "\n".join(lines)


def _safe_id(name: str) -> str:
    """Convert a name to a safe identifier for graph formats.

    Args:
        name: The name to convert

    Returns:
        Safe identifier string
    """
    return name.replace(".", "_").replace("-", "_").replace(" ", "_")
