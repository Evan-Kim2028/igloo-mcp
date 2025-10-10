"""Impact analysis utilities for lineage graphs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import networkx as nx

from .constants import Limits
from .graph import LineageGraph
from .types import SeverityLevel


class ChangeType(str, Enum):
    """Types of changes that can be analyzed for impact."""

    DROP = "drop"
    ALTER_SCHEMA = "alter_schema"
    ALTER_DATA_TYPE = "alter_data_type"
    RENAME = "rename"
    ADD_COLUMN = "add_column"
    DROP_COLUMN = "drop_column"
    MODIFY_LOGIC = "modify_logic"
    PERMISSION_CHANGE = "permission_change"
    REFRESH_SCHEDULE = "refresh_schedule"


@dataclass
class ImpactedObject:
    """Represents an object affected by a change."""

    key: str
    distance: int
    severity: SeverityLevel
    path: List[str] = field(default_factory=list)


@dataclass
class ImpactResult:
    """Aggregate impact analysis outcome."""

    source: str
    change_type: ChangeType
    impacted_objects: List[ImpactedObject]
    metadata: Dict[str, float] = field(default_factory=dict)

    @property
    def total_impacted(self) -> int:
        return len(self.impacted_objects)


class ImpactAnalyzer:
    """Perform blast-radius style analysis on a lineage graph."""

    def __init__(self, graph: LineageGraph) -> None:
        self.graph = graph
        self.nx_graph = self._build_networkx_graph(graph)

    def analyze_impact(
        self,
        node_key: str,
        change_type: ChangeType,
        *,
        max_depth: int = Limits.MAX_IMPACT_DEPTH,
    ) -> ImpactResult:
        if node_key not in self.nx_graph:
            raise ValueError(f"Lineage node '{node_key}' not found; cannot analyze impact")

        reverse_graph = self.nx_graph.reverse(copy=True)
        lengths = nx.single_source_shortest_path_length(reverse_graph, node_key, cutoff=max_depth)
        paths = nx.single_source_shortest_path(reverse_graph, node_key, cutoff=max_depth)

        impacted: List[ImpactedObject] = []
        for target, distance in sorted(lengths.items(), key=lambda item: item[1]):
            if target == node_key:
                continue
            path = list(paths.get(target, []))
            impacted.append(
                ImpactedObject(
                    key=target,
                    distance=distance,
                    severity=self._severity_for_distance(distance),
                    path=path,
                )
            )

        metadata = {
            "max_distance": float(max(lengths.values())) if lengths else 0.0,
            "average_distance": (
                float(sum(lengths.values())) / len(lengths) if lengths else 0.0
            ),
        }

        return ImpactResult(
            source=node_key,
            change_type=change_type,
            impacted_objects=impacted,
            metadata=metadata,
        )

    def identify_circular_dependencies(self) -> List[List[str]]:
        """Return simple cycles present in the lineage graph."""
        cycles = list(nx.simple_cycles(self.nx_graph))
        return [cycle for cycle in cycles if cycle]

    def _build_networkx_graph(self, graph: LineageGraph) -> nx.DiGraph:
        nx_graph = nx.DiGraph()
        for key, node in graph.nodes.items():
            if hasattr(node, "attributes"):
                attrs = dict(getattr(node, "attributes", {}))
            elif isinstance(node, dict):
                attrs = dict(node)
            else:
                attrs = {}
            nx_graph.add_node(key, **attrs)
        for edge in graph.edges:
            nx_graph.add_edge(edge.src, edge.dst, edge_type=edge.edge_type.value)
        return nx_graph

    def _severity_for_distance(self, distance: int) -> SeverityLevel:
        if distance <= 1:
            return "critical"
        if distance == 2:
            return "high"
        if distance <= 4:
            return "medium"
        return "low"


__all__ = ["ChangeType", "ImpactAnalyzer", "ImpactResult", "ImpactedObject"]
