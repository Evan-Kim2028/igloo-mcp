"""Session management helpers for Snowflake connections."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Protocol

_LOCK_ATTR = "_snowcli_session_lock"


class SnowflakeServiceProtocol(Protocol):
    pass


class CursorProtocol(Protocol):
    def execute(self, query: str) -> None: ...

    def fetchone(self) -> dict[str, Any] | tuple | None: ...


@dataclass(frozen=True)
class SessionContext:
    warehouse: str | None = None
    database: str | None = None
    schema: str | None = None
    role: str | None = None

    def to_mapping(self) -> dict[str, str | None]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class SessionSnapshot(SessionContext):
    pass


def ensure_session_lock(service: SnowflakeServiceProtocol) -> threading.Lock:
    """Get or create a session lock with defensive error handling.

    Args:
        service: The Snowflake service object

    Returns:
        A threading.Lock for session synchronization

    Raises:
        ValueError: If the service is None or invalid
    """
    if service is None:
        raise ValueError("Snowflake service is None - cannot create session lock")

    # Defensive check to ensure we have a valid service object
    if not hasattr(service, "__dict__"):
        raise ValueError("Invalid Snowflake service object - missing attributes")

    try:
        lock = getattr(service, _LOCK_ATTR, None)
        if lock is None:
            lock = threading.Lock()
            setattr(service, _LOCK_ATTR, lock)
        return lock
    except AttributeError as e:
        raise ValueError(f"Failed to access Snowflake service attributes: {e}") from e
    except (TypeError, RuntimeError, ConnectionError) as e:
        raise ValueError(f"Unexpected error creating session lock: {e}") from e


def validate_session_lock(service: SnowflakeServiceProtocol) -> bool:
    """Validate that a session lock exists and is functional.

    Args:
        service: The Snowflake service object

    Returns:
        True if the session lock is valid, False otherwise
    """
    if service is None:
        return False

    try:
        lock = getattr(service, _LOCK_ATTR, None)
        # Use duck typing instead of isinstance since threading.Lock is a factory function
        # Check that the lock has the required Lock protocol methods
        return lock is not None and isinstance(lock, type(threading.Lock()))
    except (AttributeError, TypeError):
        return False


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
    overrides: SessionContext | Mapping[str, str | None],
) -> None:
    context = (
        overrides.to_mapping() if isinstance(overrides, SessionContext) else {k: v for k, v in overrides.items() if v}
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
    session: SessionSnapshot | Mapping[str, str | None],
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
