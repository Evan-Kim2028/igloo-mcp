"""Session management helpers for Snowflake connections."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from typing import Any, Dict, Mapping, Optional, Protocol, Union

_LOCK_ATTR = "_snowcli_session_lock"


class SnowflakeServiceProtocol(Protocol):
    pass


class CursorProtocol(Protocol):
    def execute(self, query: str) -> None: ...

    def fetchone(self) -> Union[Dict[str, Any], tuple, None]: ...


@dataclass(frozen=True)
class SessionContext:
    warehouse: Optional[str] = None
    database: Optional[str] = None
    schema: Optional[str] = None
    role: Optional[str] = None

    def to_mapping(self) -> Dict[str, Optional[str]]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class SessionSnapshot(SessionContext):
    pass


def ensure_session_lock(service: SnowflakeServiceProtocol) -> threading.Lock:
    lock = getattr(service, _LOCK_ATTR, None)
    if lock is None:
        lock = threading.Lock()
        setattr(service, _LOCK_ATTR, lock)
    return lock


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def snapshot_session(cursor: CursorProtocol) -> SessionSnapshot:
    cursor.execute(
        "SELECT CURRENT_ROLE() AS ROLE, CURRENT_WAREHOUSE() AS WAREHOUSE, "
        "CURRENT_DATABASE() AS DATABASE, CURRENT_SCHEMA() AS SCHEMA"
    )
    row = cursor.fetchone()
    if isinstance(row, dict):
        return SessionSnapshot(
            role=row.get("ROLE"),
            warehouse=row.get("WAREHOUSE"),
            database=row.get("DATABASE"),
            schema=row.get("SCHEMA"),
        )
    if not row:  # pragma: no cover - defensive guard for empty fetch
        return SessionSnapshot()
    return SessionSnapshot(
        role=row[0] if len(row) > 0 else None,
        warehouse=row[1] if len(row) > 1 else None,
        database=row[2] if len(row) > 2 else None,
        schema=row[3] if len(row) > 3 else None,
    )


def apply_session_context(
    cursor: CursorProtocol,
    overrides: SessionContext | Mapping[str, Optional[str]],
) -> None:
    context = (
        overrides.to_mapping()
        if isinstance(overrides, SessionContext)
        else {k: v for k, v in overrides.items() if v}
    )
    if role := context.get("role"):
        cursor.execute(f"USE ROLE {quote_identifier(role)}")
    if warehouse := context.get("warehouse"):
        cursor.execute(f"USE WAREHOUSE {quote_identifier(warehouse)}")
    if database := context.get("database"):
        cursor.execute(f"USE DATABASE {quote_identifier(database)}")
    if schema := context.get("schema"):
        cursor.execute(f"USE SCHEMA {quote_identifier(schema)}")


def restore_session_context(
    cursor: CursorProtocol,
    session: SessionSnapshot | Mapping[str, Optional[str]],
) -> None:
    if isinstance(session, SessionSnapshot):
        target = session
    else:
        target = SessionSnapshot(
            role=session.get("role"),
            warehouse=session.get("warehouse"),
            database=session.get("database"),
            schema=session.get("schema"),
        )

    if target.role:
        cursor.execute(f"USE ROLE {quote_identifier(target.role)}")
    if target.warehouse:
        cursor.execute(f"USE WAREHOUSE {quote_identifier(target.warehouse)}")
    if target.database:
        cursor.execute(f"USE DATABASE {quote_identifier(target.database)}")
    if target.schema:
        cursor.execute(f"USE SCHEMA {quote_identifier(target.schema)}")
