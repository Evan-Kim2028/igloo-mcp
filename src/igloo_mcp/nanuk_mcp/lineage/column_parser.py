"""Column-level lineage extraction utilities.

This module restores the lightweight column lineage functionality that existed
prior to the v1.9.0 simplification. The focus is on safe SQL parsing and
producing actionable metadata for downstream tooling without reintroducing the
previous thousand-line implementation.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from sqlglot import expressions as exp

from .base import BaseExtractor
from .constants import Limits, Thresholds
from .types import FQN
from .utils import cached_sql_parse, validate_object_name, validate_sql_injection


@dataclass(frozen=True)
class QualifiedColumn:
    """Minimal representation of a column with optional table scope."""

    table: Optional[str]
    column: str

    def fqn(self) -> str:
        if self.table:
            return f"{self.table}.{self.column}"
        return self.column


@dataclass(frozen=True)
class ColumnLineageTransformation:
    """Representation of how a target column is produced."""

    target_column: str
    source_columns: Tuple[str, ...]
    transformation: Optional[str] = None
    confidence: float = Thresholds.HIGH_CONFIDENCE


@dataclass
class ColumnLineageResult:
    """Result payload returned by ``ColumnLineageExtractor``."""

    target_table: Optional[str]
    source_tables: Set[FQN] = field(default_factory=set)
    column_map: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    transformations: List[ColumnLineageTransformation] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)

    def add_issue(self, message: str) -> None:
        """Append an issue message while keeping the API ergonomic."""
        self.issues.append(message)


class ColumnLineageExtractor(BaseExtractor):
    """Best-effort column lineage extractor built on top of sqlglot."""

    def __init__(self, *, dialect: str = "snowflake") -> None:
        super().__init__("column_lineage")
        self.dialect = dialect

    def extract(self, source: str) -> ColumnLineageResult:  # pragma: no cover - API shim
        """Compatibility shim for ``BaseExtractor``."""
        return self.extract_column_lineage(source)

    def validate(self, source: str) -> bool:  # pragma: no cover - API shim
        return bool(source and isinstance(source, str))

    def extract_column_lineage(
        self,
        sql: str,
        target_table: Optional[str] = None,
        *,
        default_database: Optional[str] = None,
        default_schema: Optional[str] = None,
    ) -> ColumnLineageResult:
        """Parse SQL and return a ``ColumnLineageResult``.

        The implementation intentionally focuses on the scenarios covered in the
        regression tests:
        * Detects multi-statement SQL and records an issue
        * Validates optional target table names
        * Produces a conservative mapping between target columns and
          source columns, defaulting to direct mappings where possible
        * Captures basic transformation metadata for downstream analyzers
        """

        result = ColumnLineageResult(target_table=None)

        if not sql or not isinstance(sql, str):
            result.add_issue("Empty SQL statement supplied for column lineage analysis")
            return result

        segments = [segment.strip() for segment in sql.split(";") if segment.strip()]
        if not segments:
            result.add_issue("SQL did not contain any executable statement")
            return result

        if len(segments) > 1:
            result.add_issue("Multi-statement SQL detected; only first statement analyzed")

        primary_sql = segments[0]
        if not validate_sql_injection(primary_sql):
            result.add_issue("Potential SQL injection detected in analyzed statement; aborting")
            return result

        # Validate the optional target table name before doing any heavy work
        if target_table:
            if not validate_object_name(target_table):
                result.add_issue(
                    f"Invalid target table name: '{target_table}'. "
                    "Only alphanumeric, underscore, and dollar characters are allowed."
                )
            else:
                result.target_table = target_table

        parsed = cached_sql_parse(primary_sql, dialect=self.dialect)
        statement: Optional[exp.Expression]

        if parsed is None:
            result.add_issue("Failed to parse SQL for column lineage")
            return result

        if isinstance(parsed, list):
            statements = [stmt for stmt in parsed if isinstance(stmt, exp.Expression)]
            statement = statements[0] if statements else None
        else:
            statement = parsed

        if statement is None:
            result.add_issue("SQL parser did not return a valid statement")
            return result

        source_tables = self._collect_source_tables(statement, default_database, default_schema)
        result.source_tables.update(source_tables)

        column_pairs = self._collect_column_mappings(statement)
        for target, sources in column_pairs.items():
            if len(result.column_map) >= Limits.MAX_SQL_CACHE_SIZE:
                result.add_issue(
                    "Column lineage truncated due to safety limits (MAX_SQL_CACHE_SIZE exceeded)"
                )
                break
            result.column_map[target].update(sources)
            result.transformations.append(
                ColumnLineageTransformation(
                    target_column=target,
                    source_columns=tuple(sorted(sources)),
                    transformation=self._infer_transformation(statement, target),
                )
            )

        return result

    def _collect_source_tables(
        self,
        statement: exp.Expression,
        default_database: Optional[str],
        default_schema: Optional[str],
    ) -> Set[FQN]:
        tables: Set[FQN] = set()
        for table in statement.find_all(exp.Table):
            name = table.sql(dialect=self.dialect)
            if name:
                tables.add(name)
            elif table.this:
                tables.add(str(table.this))

        if not tables and default_schema and default_database:
            tables.add(f"{default_database}.{default_schema}")
        return tables

    def _collect_column_mappings(self, statement: exp.Expression) -> Dict[str, Set[str]]:
        """Return a mapping of target column -> set of source column references."""
        mappings: Dict[str, Set[str]] = defaultdict(set)
        for column in statement.find_all(exp.Column):
            target_name = column.alias_or_name
            source_ref = column.sql(dialect=self.dialect)
            if not target_name or not source_ref:
                continue
            mappings[target_name].add(source_ref)
        return mappings

    def _infer_transformation(
        self, statement: exp.Expression, target_column: str
    ) -> Optional[str]:
        """Return a best-effort textual transformation for a target column."""
        select = next(statement.find_all(exp.Select), None)
        if not select:
            return None

        for projection in select.expressions:
            alias = projection.alias_or_name
            if alias == target_column:
                return projection.sql(dialect=self.dialect)
        return None
