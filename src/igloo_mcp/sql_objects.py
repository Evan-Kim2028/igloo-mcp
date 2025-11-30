"""Helpers for extracting referenced Snowflake objects from SQL text."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import sqlglot
from sqlglot import exp


@dataclass(frozen=True)
class QueryObject:
    """Represents a table/view reference detected in a SQL statement."""

    database: str | None
    schema: str | None
    name: str
    catalog: str | None = None
    type: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "catalog": self.catalog,
            "database": self.database,
            "schema": self.schema,
            "name": self.name,
            "type": self.type,
        }


def _iter_tables(expression: exp.Expression | None) -> Iterable[exp.Table]:
    if expression is None:
        return
    for table in expression.find_all(exp.Table):
        # Skip derived tables like (select ... ) alias
        if isinstance(table.this, exp.Subquery):
            continue
        yield table


def extract_query_objects(sql: str) -> list[dict[str, str | None]]:
    """Parse SQL and return referenced Snowflake objects.

    Falls back to an empty list if parsing fails.
    """

    objects: list[dict[str, str | None]] = []
    seen: set[tuple[str | None, str | None, str]] = set()
    try:
        parsed = sqlglot.parse(sql, read="snowflake")
    except Exception:
        return objects

    for expression in parsed:
        for table in _iter_tables(expression):
            name = table.name
            if not name:
                continue
            schema = table.args.get("db")
            if isinstance(schema, exp.Identifier):
                schema = schema.name
            elif isinstance(schema, exp.Expression):
                schema = schema.sql(dialect="snowflake")
            catalog = table.args.get("catalog")
            if isinstance(catalog, exp.Identifier):
                catalog = catalog.name
            elif isinstance(catalog, exp.Expression):
                catalog = catalog.sql(dialect="snowflake")
            database = catalog or None
            schema_name = schema or None
            entry_key = (database, schema_name, name.lower())
            if entry_key in seen:
                continue
            seen.add(entry_key)
            obj = QueryObject(
                database=database,
                schema=schema_name,
                name=name,
                catalog=catalog or None,
                type=None,
            )
            objects.append(obj.as_dict())

    return objects
