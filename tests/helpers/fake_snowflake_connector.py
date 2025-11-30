"""Deterministic Snowflake service/cursor fakes for execute_query tests."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass
class FakeSessionDefaults:
    """Session defaults returned by snapshot_session in tests."""

    role: str = "TEST_ROLE"
    warehouse: str = "TEST_WH"
    database: str = "TEST_DB"
    schema: str = "PUBLIC"


@dataclass
class FakeQueryPlan:
    """Plan describing how the fake cursor should behave for a single query."""

    statement: str
    rows: list[dict[str, Any]] | None = None
    rowcount: int | None = None
    duration: float = 0.05
    sfqid: str = "FAKE_QID_123"
    error: Exception | None = None

    def clone(self) -> FakeQueryPlan:
        rows_copy = None
        if self.rows is not None:
            rows_copy = []
            for row in self.rows:
                if isinstance(row, dict):
                    rows_copy.append(dict(row))
                elif hasattr(row, "_asdict"):
                    rows_copy.append(row.__class__(**row._asdict()))
                else:
                    rows_copy.append(row)
        return FakeQueryPlan(
            statement=self.statement,
            rows=rows_copy,
            rowcount=self.rowcount,
            duration=self.duration,
            sfqid=self.sfqid,
            error=self.error,
        )


class FakeSnowflakeService:
    """Service that returns fixture-backed cursors following provided plans."""

    def __init__(
        self,
        plans: Iterable[FakeQueryPlan],
        *,
        session_defaults: FakeSessionDefaults | None = None,
        query_tag_param: dict[str, Any] | None = None,
    ) -> None:
        self._plans = [plan.clone() for plan in plans]
        if not self._plans:
            raise ValueError("FakeSnowflakeService requires at least one query plan.")
        self._plan_index = 0
        self.session_defaults = session_defaults or FakeSessionDefaults()
        self.cursors: list[FakeSnowflakeCursor] = []
        self._snowcli_session_lock = threading.Lock()
        self._query_tag_param = dict(query_tag_param or {})

    def get_query_tag_param(self) -> dict[str, Any]:
        return dict(self._query_tag_param)

    def add_query_plan(self, plan: FakeQueryPlan) -> None:
        """Add a new query plan to the service.

        Plans are consumed in order as queries are executed.
        Useful for system tests that dynamically add queries.
        """
        self._plans.append(plan.clone())

    def get_connection(self, **_: Any) -> FakeSnowflakeConnection:
        plan = self._consume_plan()
        cursor = FakeSnowflakeCursor(plan, self.session_defaults)
        self.cursors.append(cursor)
        return FakeSnowflakeConnection(cursor)

    def _consume_plan(self) -> FakeQueryPlan:
        if self._plan_index < len(self._plans):
            plan = self._plans[self._plan_index].clone()
            self._plan_index += 1
            return plan
        # Reuse the last plan when more connections are requested
        return self._plans[-1].clone()


class FakeSnowflakeConnection:
    """Context manager returning the prepared fake cursor."""

    def __init__(self, cursor: FakeSnowflakeCursor) -> None:
        self.cursor = cursor

    def __enter__(self) -> tuple[None, FakeSnowflakeCursor]:
        return None, self.cursor

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeSnowflakeCursor:
    """Cursor that emulates the subset of Snowflake behaviour execute_query needs."""

    def __init__(
        self,
        plan: FakeQueryPlan,
        session_defaults: FakeSessionDefaults,
    ) -> None:
        self.plan = plan
        self.session_defaults = session_defaults
        self.sfqid: str | None = None
        self.description: list[tuple[str]] | None = None
        self.rowcount: int = 0
        self._rows: list[dict[str, Any]] = []
        self._cancelled: bool = False
        self._main_executed: bool = False
        self._fetchone_map: dict[str, Any] = {}
        self._session_parameters: dict[str, str | None] = {
            "QUERY_TAG": None,
            "STATEMENT_TIMEOUT_IN_SECONDS": "0",
        }
        self.query_tags_seen: list[str | None] = []
        self.statement_timeouts_seen: list[str | None] = []

    # -- DB-API subset ---------------------------------------------------
    def execute(self, query: str) -> None:
        normalized = " ".join(query.strip().split())
        upper = normalized.upper()

        if upper.startswith("SHOW PARAMETERS LIKE 'QUERY_TAG'"):
            self.description = [("KEY",), ("VALUE",)]
            tag = self._session_parameters.get("QUERY_TAG") or ""
            self._rows = [{"KEY": "QUERY_TAG", "VALUE": tag}]
            return

        if upper.startswith("SHOW PARAMETERS LIKE 'STATEMENT_TIMEOUT_IN_SECONDS'"):
            self.description = [("KEY",), ("VALUE",)]
            timeout = self._session_parameters.get("STATEMENT_TIMEOUT_IN_SECONDS") or ""
            self._rows = [{"KEY": "STATEMENT_TIMEOUT_IN_SECONDS", "VALUE": timeout}]
            return

        if upper.startswith("ALTER SESSION SET QUERY_TAG"):
            value = self._extract_assignment_value(normalized)
            self._session_parameters["QUERY_TAG"] = value or None
            self._rows = []
            self.description = None
            return

        if upper.startswith("ALTER SESSION UNSET QUERY_TAG"):
            self._session_parameters["QUERY_TAG"] = None
            self._rows = []
            self.description = None
            return

        if upper.startswith("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS"):
            value = self._extract_assignment_value(normalized)
            self._session_parameters["STATEMENT_TIMEOUT_IN_SECONDS"] = value or "0"
            self._rows = []
            self.description = None
            return

        if upper.startswith("ALTER SESSION UNSET STATEMENT_TIMEOUT_IN_SECONDS"):
            self._session_parameters["STATEMENT_TIMEOUT_IN_SECONDS"] = "0"
            self._rows = []
            self.description = None
            return

        # Generic ALTER SESSION handler for any other session parameters
        if upper.startswith("ALTER SESSION"):
            self._rows = []
            self.description = None
            return

        # Handle snapshot_session query:
        # SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()
        if "CURRENT_ROLE()" in upper and "CURRENT_WAREHOUSE()" in upper:
            self._fetchone_map = {
                "ROLE": self.session_defaults.role,
                "WAREHOUSE": self.session_defaults.warehouse,
                "DATABASE": self.session_defaults.database,
                "SCHEMA": self.session_defaults.schema,
            }
            self.description = [("ROLE",), ("WAREHOUSE",), ("DATABASE",), ("SCHEMA",)]
            self._rows = [self._fetchone_map]
            return

        if upper.startswith("USE ROLE") or upper.startswith("USE WAREHOUSE"):
            self._rows = []
            self.description = None
            return

        if upper.startswith("USE DATABASE") or upper.startswith("USE SCHEMA"):
            self._rows = []
            self.description = None
            return

        # Main statement execution
        if not self._main_executed:
            self._execute_plan(normalized)
            return

        # Allow re-execution if it matches the plan (for cache hit scenarios or retries)
        expected = " ".join(self.plan.statement.strip().split()).upper()
        if expected and normalized.upper() == expected:
            # Reset and re-execute
            self._main_executed = False
            self._execute_plan(normalized)
            return

        raise RuntimeError(f"Unexpected extra execute call in fake cursor: {query}")

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def fetchone(self) -> dict[str, Any]:
        return dict(self._fetchone_map)

    def cancel(self) -> None:
        self._cancelled = True

    # -- Internal helpers ------------------------------------------------
    def _execute_plan(self, normalized_query: str) -> None:
        self._main_executed = True
        expected = " ".join(self.plan.statement.strip().split()).upper()
        if expected and normalized_query.upper() != expected:
            raise AssertionError(f"Expected query '{self.plan.statement}' but received '{normalized_query}'")

        if self.plan.error:
            raise self.plan.error

        deadline = time.time() + max(self.plan.duration, 0.0)
        while time.time() < deadline:
            if self._cancelled:
                self.description = None
                self._rows = []
                self.rowcount = 0
                self.sfqid = None
                return
            time.sleep(0.01)

        self.sfqid = self.plan.sfqid
        self.query_tags_seen.append(self._session_parameters.get("QUERY_TAG"))
        self.statement_timeouts_seen.append(self._session_parameters.get("STATEMENT_TIMEOUT_IN_SECONDS"))

        if self.plan.rows is not None:
            column_names = self._infer_column_names(self.plan.rows)
            self.description = [(name,) for name in column_names]
            self._rows = list(self.plan.rows)
            self.rowcount = self.plan.rowcount or len(self.plan.rows)
        else:
            self.description = None
            self._rows = []
            self.rowcount = int(self.plan.rowcount or 0)

    def _infer_column_names(self, rows: list[dict[str, Any]]) -> list[str]:
        if not rows:
            return []
        first = rows[0]
        if isinstance(first, dict):
            return list(first.keys())
        return [f"column_{idx}" for idx in range(len(first))]

    @staticmethod
    def _extract_assignment_value(normalized: str) -> str | None:
        if "=" not in normalized:
            return None
        _, value = normalized.split("=", 1)
        cleaned = value.strip().strip(";").strip()
        if cleaned.startswith("'") and cleaned.endswith("'"):
            cleaned = cleaned[1:-1]
        return cleaned or None
