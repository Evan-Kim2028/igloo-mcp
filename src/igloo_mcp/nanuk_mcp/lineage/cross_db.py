"""Cross-database lineage helpers."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable, Sequence

from .builder import LineageBuilder, LineageBuildResult
from .graph import LineageGraph
from .audit import LineageAudit


class CrossDatabaseLineageBuilder:
    """Build lineage across multiple catalog exports by merging results."""

    def __init__(self, catalog_paths: Sequence[Path | str]) -> None:
        if not catalog_paths:
            raise ValueError("At least one catalog path is required for cross database lineage")
        self.catalog_paths = [Path(path) for path in catalog_paths]

    def build(self) -> LineageBuildResult:
        combined_graph = LineageGraph()
        combined_audit = LineageAudit()
        unknown_refs: Counter[str] = Counter()

        for catalog_path in self.catalog_paths:
            builder = LineageBuilder(catalog_path)
            result = builder.build()

            for node in result.graph.nodes.values():
                combined_graph.add_node(node)
            for edge in result.graph.edges:
                combined_graph.add_edge(edge)

            combined_audit.entries.extend(result.audit.entries)
            for ref, count in result.audit.unknown_references.items():
                unknown_refs[ref] += count

        combined_audit.unknown_references = dict(unknown_refs)
        return LineageBuildResult(graph=combined_graph, audit=combined_audit)


__all__ = ["CrossDatabaseLineageBuilder"]
