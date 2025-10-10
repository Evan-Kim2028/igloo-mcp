from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

"""Helpers for canonical Snowflake identifier handling."""


@dataclass(frozen=True)
class QualifiedName:
    """Represents a fully qualified Snowflake object name."""

    database: Optional[str]
    schema: Optional[str]
    name: str

    def with_defaults(
        self, default_db: Optional[str], default_schema: Optional[str]
    ) -> "QualifiedName":
        db = self.database or default_db
        schema = self.schema or default_schema
        return QualifiedName(db, schema, self.name)

    def key(self) -> str:
        return format_fqn(self.database, self.schema, self.name)


def normalize(identifier: Optional[str]) -> Optional[str]:
    if identifier is None:
        return None
    identifier = identifier.strip()
    if not identifier:
        return None
    if identifier.startswith('"') and identifier.endswith('"'):
        return identifier[1:-1]
    return identifier.upper()


def format_fqn(database: Optional[str], schema: Optional[str], name: str) -> str:
    name = normalize(name) or name
    db = normalize(database)
    sch = normalize(schema)
    parts = [p for p in (db, sch, name) if p]
    return ".".join(parts)


def parse_table_name(table: str) -> QualifiedName:
    tokens = [token.strip() for token in table.split(".")]
    if len(tokens) == 3:
        return QualifiedName(tokens[0] or None, tokens[1] or None, tokens[2])
    if len(tokens) == 2:
        return QualifiedName(None, tokens[0] or None, tokens[1])
    return QualifiedName(None, None, tokens[0])
