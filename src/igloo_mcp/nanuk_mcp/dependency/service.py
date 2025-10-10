"""Unified dependency service for Snowflake object dependencies.

This module consolidates functionality from:
- dependency.py (core implementation, 221 LOC)
- service_layer/dependency.py (wrapper service, 61 LOC)

Total consolidated: ~282 LOC → ~250 LOC (reduction of ~32 LOC)

Features:
- Dependency graph extraction via ACCOUNT_USAGE.OBJECT_DEPENDENCIES
- Fallback to INFORMATION_SCHEMA for view→table dependencies
- DOT format export for visualization
- Context-aware service layer

Part of v1.8.0 refactoring Phase 1.2
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast

from ..config import Config, get_config
from ..context import ServiceContext, create_service_context
from ..snow_cli import SnowCLI, SnowCLIError
from .models import (
    DependencyCounts,
    DependencyEdge,
    DependencyGraph,
    DependencyNode,
    DependencyScope,
)

# =============================================================================
# Core Dependency Functions
# =============================================================================


@dataclass
class _DependencyEdgeInternal:
    """Internal representation of dependency edge."""

    source: str  # fully qualified name
    target: str  # fully qualified name
    source_type: Optional[str] = None
    target_type: Optional[str] = None
    relationship: Optional[str] = None


def _fq(db: Optional[str], schema: Optional[str], name: str) -> str:
    """Build fully qualified name from parts."""
    parts = [p for p in [db, schema, name] if p]
    return ".".join(parts)


def _query_account_usage(
    cli: SnowCLI, database: Optional[str], schema: Optional[str]
) -> List[_DependencyEdgeInternal]:
    """Query ACCOUNT_USAGE.OBJECT_DEPENDENCIES for dependencies."""
    filters: List[str] = []
    if database:
        filters.append("lower(REFERENCING_DATABASE) = lower($db)")
    if schema:
        filters.append("lower(REFERENCING_SCHEMA) = lower($schema)")
    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    sql = f"""
    SELECT
      REFERENCING_DATABASE,
      REFERENCING_SCHEMA,
      REFERENCING_OBJECT_NAME,
      REFERENCING_OBJECT_DOMAIN,
      REFERENCED_DATABASE,
      REFERENCED_SCHEMA,
      REFERENCED_OBJECT_NAME,
      REFERENCED_OBJECT_DOMAIN,
      RELATIONSHIP,
      DEPENDENCY_TYPE
    FROM SNOWFLAKE.ACCOUNT_USAGE.OBJECT_DEPENDENCIES
    {where}
    """

    binds: Dict[str, str] = {}
    if database:
        binds["db"] = database
    if schema:
        binds["schema"] = schema

    # Inline bind variables (snow CLI doesn't support them directly)
    for k, v in binds.items():
        sql = sql.replace(f"${k}", f"'{v}'")

    out = cli.run_query(sql, output_format="csv")
    edges: List[_DependencyEdgeInternal] = []
    if not out.rows:
        return edges

    for row in out.rows:
        src = _fq(
            row.get("REFERENCING_DATABASE"),
            row.get("REFERENCING_SCHEMA"),
            row.get("REFERENCING_OBJECT_NAME") or "",
        )
        tgt = _fq(
            row.get("REFERENCED_DATABASE"),
            row.get("REFERENCED_SCHEMA"),
            row.get("REFERENCED_OBJECT_NAME") or "",
        )
        rel = row.get("RELATIONSHIP") or row.get("DEPENDENCY_TYPE")
        edges.append(
            _DependencyEdgeInternal(
                source=src,
                target=tgt,
                source_type=row.get("REFERENCING_OBJECT_DOMAIN"),
                target_type=row.get("REFERENCED_OBJECT_DOMAIN"),
                relationship=rel,
            )
        )
    return edges


def _query_information_schema(
    cli: SnowCLI, database: Optional[str], schema: Optional[str]
) -> List[_DependencyEdgeInternal]:
    """Fallback using VIEW_TABLE_USAGE (only view→table dependencies)."""
    filters: List[str] = []
    if database:
        filters.append("lower(vtu.view_catalog) = lower($db)")
    if schema:
        filters.append("lower(vtu.view_schema) = lower($schema)")
    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    sql = f"""
    SELECT
      vtu.view_catalog,
      vtu.view_schema,
      vtu.view_name,
      vtu.table_catalog,
      vtu.table_schema,
      vtu.table_name
    FROM information_schema.view_table_usage vtu
    {where}
    """

    binds: Dict[str, str] = {}
    if database:
        binds["db"] = database
    if schema:
        binds["schema"] = schema
    for k, v in binds.items():
        sql = sql.replace(f"${k}", f"'{v}'")

    out = cli.run_query(sql, output_format="csv")
    edges: List[_DependencyEdgeInternal] = []
    if not out.rows:
        return edges

    for row in out.rows:
        src = _fq(
            row.get("VIEW_CATALOG"), row.get("VIEW_SCHEMA"), row.get("VIEW_NAME") or ""
        )
        tgt = _fq(
            row.get("TABLE_CATALOG"),
            row.get("TABLE_SCHEMA"),
            row.get("TABLE_NAME") or "",
        )
        edges.append(
            _DependencyEdgeInternal(
                source=src,
                target=tgt,
                source_type="VIEW",
                target_type="TABLE",
                relationship="uses",
            )
        )
    return edges


def build_dependency_graph(
    database: Optional[str] = None,
    schema: Optional[str] = None,
    account_scope: bool = True,
) -> Dict[str, object]:
    """Build a dependency graph and return a dict with nodes and edges.

    Args:
        database: Specific database to analyze
        schema: Specific schema to analyze
        account_scope: Use ACCOUNT_USAGE (broader coverage) vs INFORMATION_SCHEMA

    Returns:
        Dictionary with 'nodes', 'edges', 'counts', and 'scope'
    """
    cli = SnowCLI()
    try:
        edges = _query_account_usage(cli, database, schema) if account_scope else []
    except SnowCLIError:
        edges = []

    if not edges:
        # Fallback to information_schema
        edges = _query_information_schema(cli, database, schema)

    nodes: Dict[str, Dict[str, Optional[str]]] = {}
    out_edges: List[Dict[str, Optional[str]]] = []
    for e in edges:
        if e.source and e.source not in nodes:
            nodes[e.source] = {"id": e.source, "type": e.source_type}
        if e.target and e.target not in nodes:
            nodes[e.target] = {"id": e.target, "type": e.target_type}
        out_edges.append(
            {
                "source": e.source,
                "target": e.target,
                "relationship": e.relationship,
            }
        )

    return {
        "nodes": list(nodes.values()),
        "edges": out_edges,
        "counts": {"nodes": len(nodes), "edges": len(out_edges)},
        "scope": {
            "database": database,
            "schema": schema,
            "account_scope": account_scope,
        },
    }


def to_dot(graph: Dict[str, Any]) -> str:
    """Convert dependency graph to DOT format for Graphviz.

    Args:
        graph: Dependency graph dictionary

    Returns:
        DOT format string
    """
    nodes: List[Dict[str, Any]] = graph.get("nodes", [])
    edges: List[Dict[str, Any]] = graph.get("edges", [])
    lines = ["digraph dependencies {"]
    for n in nodes:
        nid = n.get("id", "")  # type: ignore
        ntype = n.get("type", "")  # type: ignore
        label = nid.replace('"', "'")
        lines.append(f'  "{label}" [shape=box label="{label}\n({ntype})"];')
    for e in edges:
        s = (e.get("source") or "").replace('"', "'")  # type: ignore
        t = (e.get("target") or "").replace('"', "'")  # type: ignore
        rel = e.get("relationship") or ""  # type: ignore
        attr = f' [label="{rel}"]' if rel else ""
        lines.append(f'  "{s}" -> "{t}"{attr};')
    lines.append("}")
    return "\n".join(lines)


# =============================================================================
# Service Layer Wrapper
# =============================================================================


class DependencyService:
    """Service layer wrapper for dependency operations with context management."""

    def __init__(
        self, *, context: ServiceContext | None = None, config: Config | None = None
    ) -> None:
        """Initialize dependency service with context or config."""
        if context is not None:
            self._context = context
        else:
            cfg = config or get_config()
            self._context = create_service_context(existing_config=cfg)

    @property
    def config(self) -> Config:
        """Get configuration."""
        return self._context.config

    @property
    def context(self) -> ServiceContext:
        """Get service context."""
        return self._context

    def build(
        self,
        *,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        account_scope: bool = True,
    ) -> DependencyGraph:
        """Build dependency graph and return structured result.

        Args:
            database: Specific database to analyze
            schema: Specific schema to analyze
            account_scope: Use ACCOUNT_USAGE (broader) vs INFORMATION_SCHEMA

        Returns:
            DependencyGraph with nodes, edges, counts, and scope
        """
        payload = build_dependency_graph(
            database=database,
            schema=schema,
            account_scope=account_scope,
        )
        raw_nodes = cast(List[Dict[str, Any]], payload.get("nodes", []))
        raw_edges = cast(List[Dict[str, Any]], payload.get("edges", []))
        raw_counts = cast(
            Dict[str, Any], payload.get("counts", {"nodes": 0, "edges": 0})
        )
        raw_scope = cast(Dict[str, Any], payload.get("scope", {}))
        return DependencyGraph(
            nodes=[DependencyNode(**node) for node in raw_nodes],
            edges=[DependencyEdge(**edge) for edge in raw_edges],
            counts=DependencyCounts(**raw_counts),
            scope=DependencyScope(**raw_scope),
        )

    def to_dot(self, graph: DependencyGraph) -> str:
        """Convert dependency graph to DOT format.

        Args:
            graph: DependencyGraph instance

        Returns:
            DOT format string for Graphviz
        """
        return to_dot(graph.model_dump(by_alias=True))
