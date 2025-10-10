from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, cast

import sqlglot
from sqlglot import exp

from .identifiers import QualifiedName, normalize
from .loader import ObjectType


@dataclass
class ParseIssue:
    message: str
    level: str = "warning"


@dataclass
class LineageParseResult:
    upstreams: Set[str] = field(default_factory=set)
    produces: Set[str] = field(default_factory=set)
    issues: List[ParseIssue] = field(default_factory=list)


class SqlLineageExtractor:
    def __init__(self) -> None:
        self._dialect = "snowflake"

    def extract(
        self,
        sql_text: str,
        *,
        object_type: ObjectType,
        default_database: Optional[str],
        default_schema: Optional[str],
        target_name: Optional[str] = None,
    ) -> LineageParseResult:
        result = LineageParseResult()
        statements = self._parse(sql_text, result)
        if not statements:
            return result

        for statement in statements:
            self._handle_statement(
                statement,
                result,
                object_type=object_type,
                default_database=default_database,
                default_schema=default_schema,
                target_name=target_name,
            )
        return result

    def extract_select_sources(
        self,
        sql_text: str,
        *,
        default_database: Optional[str],
        default_schema: Optional[str],
    ) -> LineageParseResult:
        result = LineageParseResult()
        statements = self._parse(sql_text, result)
        if not statements:
            return result
        for statement in statements:
            self._collect_tables(statement, result, default_database, default_schema)
        return result

    def _parse(self, sql_text: str, result: LineageParseResult) -> List[exp.Expression]:
        try:
            parsed = sqlglot.parse(sql_text, read=self._dialect)
        except sqlglot.errors.ParseError as exc:
            result.issues.append(
                ParseIssue(message=f"sqlglot parse error: {exc}", level="error")
            )
            return []
        non_null = [stmt for stmt in parsed if stmt is not None]
        return cast(List[exp.Expression], non_null)

    def _handle_statement(
        self,
        statement: exp.Expression,
        result: LineageParseResult,
        *,
        object_type: ObjectType,
        default_database: Optional[str],
        default_schema: Optional[str],
        target_name: Optional[str],
    ) -> None:
        if isinstance(statement, exp.Create):
            target = _qualified_from_table(
                statement.this, default_database, default_schema
            )
            if target_name:
                result.produces.add(target_name)
            elif target:
                result.produces.add(target.key())
            expr = statement.args.get("expression")
            if expr:
                self._collect_tables(expr, result, default_database, default_schema)
            return
        if isinstance(statement, exp.Insert):
            target = _qualified_from_table(
                statement.this, default_database, default_schema
            )
            if target:
                result.produces.add(target.key())
            expression = statement.args.get("expression")
            if expression:
                self._collect_tables(
                    expression, result, default_database, default_schema
                )
            return
        if isinstance(statement, exp.Merge):
            target = _qualified_from_table(
                statement.this, default_database, default_schema
            )
            if target:
                result.produces.add(target.key())
            self._collect_tables(
                statement.args.get("using"), result, default_database, default_schema
            )
            return
        if isinstance(statement, exp.Update):
            target = _qualified_from_table(
                statement.this, default_database, default_schema
            )
            if target:
                result.produces.add(target.key())
            self._collect_tables(statement, result, default_database, default_schema)
            return
        if object_type in {
            ObjectType.VIEW,
            ObjectType.MATERIALIZED_VIEW,
            ObjectType.DYNAMIC_TABLE,
        }:
            self._collect_tables(statement, result, default_database, default_schema)
        elif object_type == ObjectType.TASK:
            self._collect_tables(statement, result, default_database, default_schema)

    def _collect_tables(
        self,
        expression: Optional[exp.Expression],
        result: LineageParseResult,
        default_database: Optional[str],
        default_schema: Optional[str],
    ) -> None:
        if expression is None:
            return
        cte_names = set()
        for cte in expression.find_all(exp.CTE):
            alias_expr = getattr(cte, "alias", None)
            alias = alias_expr if isinstance(alias_expr, exp.Expression) else None
            alias_name = _alias_name(alias)
            normalized = normalize(alias_name) if alias_name else None
            if normalized:
                cte_names.add(normalized)
        for table in expression.find_all(exp.Table):
            if (
                getattr(table, "is_function", False)
                or getattr(table, "is_temp", False)
                or getattr(table, "is_pseudo", False)
            ):
                continue
            name = normalize(table.name)
            if name and name in cte_names:
                continue
            qualified = _qualified_from_table(table, default_database, default_schema)
            if not qualified:
                continue
            result.upstreams.add(qualified.key())


def extract_select_clause(ddl: str) -> Optional[str]:
    pattern = re.compile(r"(?is)\bAS\b\s*(SELECT|WITH|TABLE|CALL)\b")
    matches = list(pattern.finditer(ddl))
    if not matches:
        return None
    last = matches[-1]
    start = last.start(1)
    return ddl[start:].strip()


def _alias_name(alias: Optional[exp.Expression]) -> Optional[str]:
    if alias is None:
        return None
    if isinstance(alias, exp.TableAlias):
        if alias.this:
            return alias.this.name
    if hasattr(alias, "name"):
        return alias.name
    return None


def _qualified_from_table(
    table: Optional[exp.Expression],
    default_database: Optional[str],
    default_schema: Optional[str],
) -> Optional[QualifiedName]:
    if isinstance(table, exp.Schema):
        table = table.this
    if not isinstance(table, exp.Table):
        return None
    catalog = table.catalog
    schema = table.db
    name = table.this
    if name is None:
        return None
    name_str = name.name
    catalog_name = catalog.name if isinstance(catalog, exp.Identifier) else None
    schema_name = schema.name if isinstance(schema, exp.Identifier) else None
    qn = QualifiedName(
        normalize(catalog_name),
        normalize(schema_name),
        normalize(name_str) or name_str,
    ).with_defaults(normalize(default_database), normalize(default_schema))
    return qn
