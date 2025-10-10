from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .audit import LineageAudit, ObjectAuditEntry
from .constants import Timeouts
from .identifiers import normalize
from .loader import CatalogLoader, CatalogObject, ObjectType
from .models import Edge as LineageEdge
from .models import EdgeType
from .models import Graph as LineageGraph
from .models import Node as LineageNode
from .models import NodeType
from .sql_parser import LineageParseResult, SqlLineageExtractor, extract_select_clause
from .utils import TimeoutError, timeout


@dataclass
class LineageBuildResult:
    graph: LineageGraph
    audit: LineageAudit


class LineageBuilder:
    def __init__(self, catalog_dir: Path | str) -> None:
        self.catalog_dir = Path(catalog_dir)
        self.loader = CatalogLoader(self.catalog_dir)
        self.parser = SqlLineageExtractor()

    @staticmethod
    def _node_key(obj: CatalogObject) -> str:
        base_key = obj.fqn()
        if obj.object_type == ObjectType.TASK:
            return f"{base_key}::task"
        return base_key

    def build(
        self, timeout_seconds: int = Timeouts.DEFAULT_BUILD
    ) -> LineageBuildResult:
        graph = LineageGraph()
        audit = LineageAudit()
        unknown_refs: Counter[str] = Counter()

        try:
            with timeout(
                timeout_seconds, f"Lineage build timed out after {timeout_seconds}s"
            ):
                objects = self.loader.load()
                catalog_keys = {
                    obj.fqn(): obj
                    for obj in objects
                    if obj.object_type != ObjectType.TASK
                }

                for obj in objects:
                    key = self._node_key(obj)
                    if obj.object_type == ObjectType.TASK:
                        graph.add_node(
                            LineageNode(
                                key=key,
                                node_type=NodeType.TASK,
                                attributes={
                                    "object_type": obj.object_type.value,
                                    "database": normalize(obj.database) or "",
                                    "schema": normalize(obj.schema) or "",
                                    "name": normalize(obj.name) or obj.name,
                                    "fqn": obj.fqn(),
                                    "in_catalog": "true",
                                },
                            )
                        )
                    else:
                        graph.add_node(
                            LineageNode(
                                key=key,
                                node_type=NodeType.DATASET,
                                attributes={
                                    "object_type": obj.object_type.value,
                                    "database": normalize(obj.database) or "",
                                    "schema": normalize(obj.schema) or "",
                                    "name": normalize(obj.name) or obj.name,
                                    "fqn": obj.fqn(),
                                    "in_catalog": "true",
                                },
                            )
                        )

                for obj in objects:
                    key = self._node_key(obj)
                    entry = ObjectAuditEntry(
                        key=key, object_type=obj.object_type, status="parsed"
                    )
                    if obj.object_type == ObjectType.TABLE:
                        entry.status = "base"
                        audit.entries.append(entry)
                        continue
                    if obj.object_type == ObjectType.TASK:
                        result = self._handle_task(obj, graph, catalog_keys)
                    else:
                        result = self._handle_dataset(
                            obj, graph, catalog_keys, unknown_refs
                        )
                    if result is None:
                        entry.status = "missing_sql"
                    else:
                        entry.upstreams = len(result.upstreams)
                        entry.produces = len(result.produces)
                        if any(issue.level == "error" for issue in result.issues):
                            entry.status = "parse_error"
                        entry.issues = [issue.message for issue in result.issues]
                    audit.entries.append(entry)

                audit.unknown_references = dict(
                    sorted(unknown_refs.items(), key=lambda x: x[0])
                )

        except TimeoutError:
            # Return partial results on timeout
            import logging

            logging.warning(f"Lineage build timed out after {timeout_seconds} seconds")
            audit.unknown_references = dict(
                sorted(unknown_refs.items(), key=lambda x: x[0])
            )

        return LineageBuildResult(graph=graph, audit=audit)

    def _handle_dataset(
        self,
        obj: CatalogObject,
        graph: LineageGraph,
        catalog_keys: Dict[str, CatalogObject],
        unknown_refs: Counter[str],
    ) -> Optional[LineageParseResult]:
        sql = obj.sql_for_lineage()
        if not sql and obj.object_type in {
            ObjectType.VIEW,
            ObjectType.MATERIALIZED_VIEW,
            ObjectType.DYNAMIC_TABLE,
        }:
            return None
        if obj.object_type in {
            ObjectType.VIEW,
            ObjectType.MATERIALIZED_VIEW,
            ObjectType.DYNAMIC_TABLE,
        }:
            select_sql = extract_select_clause(sql) if sql else None
            parse_target = select_sql or sql
            if not parse_target:
                return None
            result = self.parser.extract_select_sources(
                parse_target,
                default_database=obj.database,
                default_schema=obj.schema,
            )
            for upstream in result.upstreams:
                self._ensure_dataset_node(graph, upstream, upstream in catalog_keys)
                graph.add_edge(
                    LineageEdge(
                        src=obj.fqn(),
                        dst=upstream,
                        edge_type=EdgeType.DERIVES_FROM,
                        evidence={
                            "source": obj.object_type.value,
                            "source_file": str(obj.source_file.name),
                        },
                    )
                )
                if upstream not in catalog_keys:
                    unknown_refs[upstream] += 1
            return result
        return LineageParseResult()

    def _handle_task(
        self,
        obj: CatalogObject,
        graph: LineageGraph,
        catalog_keys: Dict[str, CatalogObject],
    ) -> Optional[LineageParseResult]:
        sql = obj.sql_for_lineage()
        if not sql:
            return None
        result = self.parser.extract(
            sql,
            object_type=ObjectType.TASK,
            default_database=obj.database,
            default_schema=obj.schema,
        )
        task_key = self._node_key(obj)
        for dataset in result.upstreams:
            self._ensure_dataset_node(graph, dataset, dataset in catalog_keys)
            graph.add_edge(
                LineageEdge(
                    src=task_key,
                    dst=dataset,
                    edge_type=EdgeType.CONSUMES,
                    evidence={
                        "source": "task",
                        "source_file": str(obj.source_file.name),
                    },
                )
            )
        for produced in result.produces:
            self._ensure_dataset_node(graph, produced, produced in catalog_keys)
            graph.add_edge(
                LineageEdge(
                    src=task_key,
                    dst=produced,
                    edge_type=EdgeType.PRODUCES,
                    evidence={
                        "source": "task",
                        "source_file": str(obj.source_file.name),
                    },
                )
            )
        return result

    def _ensure_dataset_node(
        self,
        graph: LineageGraph,
        key: str,
        in_catalog: bool,
    ) -> None:
        graph.set_node_type(key, NodeType.DATASET)
        attributes = graph.nodes.get(key, LineageNode(key, NodeType.DATASET)).attributes
        attrs = dict(attributes)
        if in_catalog:
            attrs["in_catalog"] = "true"
        else:
            attrs.setdefault("in_catalog", "false")
        graph.add_node(LineageNode(key, NodeType.DATASET, attrs))
