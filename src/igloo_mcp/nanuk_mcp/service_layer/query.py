from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional

from ..config import Config, get_config
from ..context import ServiceContext, create_service_context
from ..session_utils import (
    SessionContext,
    apply_session_context,
    ensure_session_lock,
    restore_session_context,
    snapshot_session,
)
from ..snow_cli import QueryOutput, SnowCLI

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    from typing import Any as SnowflakeService  # type: ignore[misc]


class QueryService:
    """Shared query execution utilities for CLI and MCP surfaces."""

    def __init__(
        self,
        *,
        context: ServiceContext | None = None,
        config: Config | None = None,
        snow_cli: SnowCLI | None = None,
    ) -> None:
        if context is not None:
            self._context = context
        else:
            cfg = config or get_config()
            self._context = create_service_context(existing_config=cfg)
        self._snow_cli = snow_cli

    @property
    def config(self) -> Config:
        return self._context.config

    @property
    def context(self) -> ServiceContext:
        return self._context

    def execute_cli(
        self,
        statement: str,
        *,
        session: SessionContext | None = None,
        output_format: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> QueryOutput:
        overrides = session.to_mapping() if session else {}
        cli = self._snow_cli or SnowCLI(profile=self.config.snowflake.profile)
        self._snow_cli = cli
        return cli.run_query(
            statement,
            output_format=output_format,
            ctx_overrides=overrides or None,
            timeout=timeout or self.config.timeout_seconds,
        )

    def preview_cli(
        self,
        table_name: str,
        *,
        limit: int = 100,
        session: SessionContext | None = None,
    ) -> QueryOutput:
        statement = f"SELECT * FROM {table_name} LIMIT {limit}"
        return self.execute_cli(
            statement,
            session=session,
            output_format="csv",
        )

    def execute_with_service(
        self,
        snowflake_service: "SnowflakeService",
        statement: str,
        *,
        session: SessionContext | None = None,
    ) -> Dict[str, Any]:
        overrides = session.to_mapping() if session else {}
        lock = ensure_session_lock(snowflake_service)
        with lock:
            with snowflake_service.get_connection(  # type: ignore[attr-defined]
                use_dict_cursor=True,
                session_parameters=snowflake_service.get_query_tag_param(),  # type: ignore[attr-defined]
            ) as (_, cursor):
                original = snapshot_session(cursor)
                try:
                    if overrides:
                        apply_session_context(cursor, overrides)
                    cursor.execute(statement)
                    rows = cursor.fetchall()
                    return {
                        "statement": statement,
                        "rowcount": cursor.rowcount,
                        "rows": self._json_compatible(rows),
                    }
                finally:
                    restore_session_context(cursor, original)

    def test_connection(self, snowflake_service: "SnowflakeService") -> bool:
        try:
            with snowflake_service.get_connection(  # type: ignore[attr-defined]
                use_dict_cursor=True
            ) as (_, cursor):
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
                if isinstance(row, dict):
                    return any(str(value).strip() == "1" for value in row.values())
                if isinstance(row, (list, tuple)):
                    return any(str(value).strip() == "1" for value in row)
                return bool(row)
        except Exception:
            return False

    @staticmethod
    def session_from_mapping(overrides: Mapping[str, Optional[str]]) -> SessionContext:
        return SessionContext(
            warehouse=overrides.get("warehouse"),
            database=overrides.get("database"),
            schema=overrides.get("schema"),
            role=overrides.get("role"),
        )

    def _json_compatible(self, payload: Any) -> Any:
        return json.loads(json.dumps(payload, default=str))
