"""Execute Query MCP Tool - Execute SQL queries against Snowflake.

Part of v1.8.0 Phase 2.2 - extracted from mcp_server.py.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, Optional

import anyio

from igloo_mcp.config import Config
from igloo_mcp.logging import QueryHistory
from igloo_mcp.mcp.utils import json_compatible
from igloo_mcp.mcp_health import MCPHealthMonitor
from igloo_mcp.service_layer import QueryService
from igloo_mcp.session_utils import (
    apply_session_context,
    ensure_session_lock,
    restore_session_context,
    snapshot_session,
)
from igloo_mcp.sql_validation import validate_sql_statement

from .base import MCPTool
from .schema_utils import (
    boolean_schema,
    integer_schema,
    snowflake_identifier_schema,
    string_schema,
)


class ExecuteQueryTool(MCPTool):
    """MCP tool for executing SQL queries against Snowflake."""

    def __init__(
        self,
        config: Config,
        snowflake_service: Any,
        query_service: QueryService,
        health_monitor: Optional[MCPHealthMonitor] = None,
    ):
        """Initialize execute query tool.

        Args:
            config: Application configuration
            snowflake_service: Snowflake service instance from mcp-server-snowflake
            query_service: Query service for execution
            health_monitor: Optional health monitoring instance
        """
        self.config = config
        self.snowflake_service = snowflake_service
        self.query_service = query_service
        self.health_monitor = health_monitor
        # Optional JSONL query history (enabled via IGLOO_MCP_QUERY_HISTORY)
        self.history = QueryHistory.from_env()

    @property
    def name(self) -> str:
        return "execute_query"

    @property
    def description(self) -> str:
        return "Execute a SQL query against Snowflake"

    @property
    def category(self) -> str:
        return "query"

    @property
    def tags(self) -> list[str]:
        return ["sql", "execute", "analytics", "warehouse"]

    @property
    def usage_examples(self) -> list[Dict[str, Any]]:
        return [
            {
                "description": "Preview recent sales rows",
                "parameters": {
                    "statement": (
                        "SELECT * FROM ANALYTICS.SALES.FACT_ORDERS ORDER BY ORDER_TS DESC LIMIT 20"
                    ),
                    "warehouse": "ANALYTICS_WH",
                },
            },
            {
                "description": "Run aggregate by region with explicit role",
                "parameters": {
                    "statement": (
                        "SELECT REGION, SUM(REVENUE) AS total_revenue "
                        "FROM SALES.METRICS.REVENUE_BY_REGION "
                        "GROUP BY REGION"
                    ),
                    "warehouse": "REPORTING_WH",
                    "role": "ANALYST",
                    "timeout_seconds": 120,
                },
            },
        ]

    async def execute(
        self,
        statement: str,
        warehouse: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        role: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        verbose_errors: bool = False,
        reason: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute SQL query against Snowflake.

        Args:
            statement: SQL statement to execute
            warehouse: Optional warehouse override
            database: Optional database override
            schema: Optional schema override
            role: Optional role override
            timeout_seconds: Query timeout in seconds (default: 30s)
            verbose_errors: Include detailed optimization hints in errors

        Returns:
            Query results with rows, rowcount, and execution metadata

        Raises:
            ValueError: If profile validation fails or SQL is blocked
            RuntimeError: If query execution fails
        """
        if timeout_seconds is not None:
            if isinstance(timeout_seconds, bool) or not isinstance(
                timeout_seconds, int
            ):
                raise TypeError("timeout_seconds must be an integer value in seconds.")
            if not 1 <= timeout_seconds <= 3600:
                raise ValueError("timeout_seconds must be between 1 and 3600 seconds.")

        # Validate profile health before executing query
        if self.health_monitor:
            profile_health = await anyio.to_thread.run_sync(
                self.health_monitor.get_profile_health,
                self.config.snowflake.profile,
                False,  # use cache
            )
            if not profile_health.is_valid:
                error_msg = (
                    profile_health.validation_error or "Profile validation failed"
                )
                available = (
                    ", ".join(profile_health.available_profiles)
                    if profile_health.available_profiles
                    else "none"
                )
                self.health_monitor.record_error(
                    f"Profile validation failed: {error_msg}"
                )
                raise ValueError(
                    f"Snowflake profile validation failed: {error_msg}. "
                    f"Profile: {self.config.snowflake.profile}, "
                    f"Available profiles: {available}. "
                    f"Check configuration with 'snow connection list' or verify profile settings."
                )

        # Validate SQL statement against permissions
        allow_list = self.config.sql_permissions.get_allow_list()
        disallow_list = self.config.sql_permissions.get_disallow_list()

        stmt_type, is_valid, error_msg = validate_sql_statement(
            statement, allow_list, disallow_list
        )

        if not is_valid and error_msg:
            if self.health_monitor:
                self.health_monitor.record_error(
                    f"SQL statement blocked: {stmt_type} - {statement[:100]}"
                )
            raise ValueError(error_msg)

        # Prepare session context overrides
        overrides = {
            "warehouse": warehouse,
            "database": database,
            "schema": schema,
            "role": role,
        }
        # Filter out None values
        overrides = {k: v for k, v in overrides.items() if v is not None}

        # Execute query with session context management
        timeout = timeout_seconds or getattr(self.config, "timeout_seconds", 120)

        try:
            result = await anyio.to_thread.run_sync(
                self._execute_query_sync,
                statement,
                overrides,
                timeout,
                reason,
            )

            if self.health_monitor and hasattr(
                self.health_monitor, "record_query_success"
            ):
                self.health_monitor.record_query_success(statement[:100])  # type: ignore[attr-defined]

            # Persist success history (lightweight JSONL)
            try:
                self.history.record(
                    {
                        "ts": time.time(),
                        "status": "success",
                        "profile": self.config.snowflake.profile,
                        "statement_preview": statement[:200],
                        "rowcount": result.get("rowcount", 0),
                        "timeout_seconds": timeout,
                        "overrides": overrides,
                        "query_id": result.get("query_id"),
                        "duration_ms": result.get("duration_ms"),
                        **({"reason": reason} if reason else {}),
                    }
                )
            except Exception:
                pass

            return result

        except TimeoutError as e:
            # Build tailored timeout messages (compact vs verbose)
            compact = (
                f"Query timeout ({timeout}s). Try: timeout_seconds=480, add WHERE/LIMIT clause, "
                f"or scale warehouse. Use verbose_errors=True for detailed hints. "
                f"Query ID may be unavailable on timeout."
            )
            if self.health_monitor:
                self.health_monitor.record_error(compact)

            # Persist timeout history
            try:
                self.history.record(
                    {
                        "ts": time.time(),
                        "status": "timeout",
                        "profile": self.config.snowflake.profile,
                        "statement_preview": statement[:200],
                        "timeout_seconds": timeout,
                        "overrides": overrides,
                        "error": str(e),
                        **({"reason": reason} if reason else {}),
                    }
                )
            except Exception:
                pass

            if verbose_errors:
                preview = statement[:200] + ("..." if len(statement) > 200 else "")
                raise RuntimeError(
                    "Query timeout after {}s.\n\n".format(timeout)
                    + "Quick fixes:\n"
                    + "1. Increase timeout: execute_query(..., timeout_seconds=480)\n"
                    + "2. Add filter: Add WHERE clause to reduce data volume\n"
                    + "3. Sample data: Add LIMIT clause for testing (e.g., LIMIT 1000)\n"
                    + "4. Scale warehouse: Use larger warehouse for complex queries\n\n"
                    + "Current settings:\n"
                    + f"  - Timeout: {timeout}s\n"
                    + (
                        f"  - Warehouse: {overrides.get('warehouse')}\n"
                        if overrides.get("warehouse")
                        else ""
                    )
                    + (
                        f"  - Database: {overrides.get('database')}\n"
                        if overrides.get("database")
                        else ""
                    )
                    + (
                        f"  - Schema: {overrides.get('schema')}\n"
                        if overrides.get("schema")
                        else ""
                    )
                    + (
                        f"  - Role: {overrides.get('role')}\n"
                        if overrides.get("role")
                        else ""
                    )
                    + "\nNotes:\n  - Query ID may be unavailable when a timeout triggers early cancellation.\n"
                    + "\nQuery preview: "
                    + preview
                )
            else:
                raise RuntimeError(compact)
        except Exception as e:
            error_message = str(e)

            if self.health_monitor:
                self.health_monitor.record_error(
                    f"Query execution failed: {error_message[:200]}"
                )

            # Persist failure history
            try:
                self.history.record(
                    {
                        "ts": time.time(),
                        "status": "error",
                        "profile": self.config.snowflake.profile,
                        "statement_preview": statement[:200],
                        "timeout_seconds": timeout,
                        "overrides": overrides,
                        "error": error_message,
                        **({"reason": reason} if reason else {}),
                    }
                )
            except Exception:
                pass

            if verbose_errors:
                # Return detailed error with optimization hints
                raise RuntimeError(
                    f"Query execution failed: {error_message}\n\n"
                    f"Query: {statement[:200]}{'...' if len(statement) > 200 else ''}\n"
                    f"Timeout: {timeout}s\n"
                    f"Context: {overrides}"
                )
            else:
                # Return compact error
                raise RuntimeError(
                    f"Query execution failed: {error_message[:150]}. Use verbose_errors=true for details."
                )

    def _execute_query_sync(
        self,
        statement: str,
        overrides: Dict[str, Any],
        timeout: int,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute query synchronously using Snowflake service with robust timeout/cancel.

        This path uses the official MCP Snowflake service to obtain a connector
        cursor so we can cancel server-side statements on timeout and capture
        the Snowflake query ID when available.
        """
        params = {}
        # Include igloo query tag from the upstream service if available
        try:
            params = dict(self.snowflake_service.get_query_tag_param())
        except Exception:
            params = {}

        # If a reason is provided, append it to the Snowflake QUERY_TAG for auditability.
        # We make a best-effort to preserve any existing tag from the upstream service.
        if reason:
            try:
                # Truncate and sanitize reason to avoid overly long tags
                reason_clean = " ".join(reason.split())[:240]
                existing = params.get("QUERY_TAG")

                # Try merging into existing JSON tag if present
                merged = None
                if isinstance(existing, str):
                    try:
                        obj = json.loads(existing)
                        if isinstance(obj, dict):
                            obj.update(
                                {"tool": "execute_query", "reason": reason_clean}
                            )
                            merged = json.dumps(obj, ensure_ascii=False)
                    except Exception:
                        merged = None

                # Fallback to concatenated string tag
                if not merged:
                    base = existing if isinstance(existing, str) else ""
                    sep = " | " if base else ""
                    merged = f"{base}{sep}tool:execute_query; reason:{reason_clean}"

                params["QUERY_TAG"] = merged
            except Exception:
                # Never fail query execution on tag manipulation
                pass

        if timeout:
            # Enforce server-side statement timeout as an additional safeguard
            params["STATEMENT_TIMEOUT_IN_SECONDS"] = int(timeout)

        lock = ensure_session_lock(self.snowflake_service)
        started = time.time()

        with lock:
            with self.snowflake_service.get_connection(
                use_dict_cursor=True,
            ) as (_, cursor):
                original = snapshot_session(cursor)

                result_box: Dict[str, Any] = {
                    "rows": None,
                    "rowcount": None,
                    "error": None,
                }
                query_id_box: Dict[str, Optional[str]] = {"id": None}
                done = threading.Event()

                def _escape_tag(tag_value: str) -> str:
                    return tag_value.replace("'", "''")

                def _get_session_parameter(name: str) -> Optional[str]:
                    try:
                        cursor.execute(f"SHOW PARAMETERS LIKE '{name}' IN SESSION")
                        rows = cursor.fetchall() or []
                        if not rows:
                            return None
                        for row in rows:
                            level = (row.get("level") or row.get("LEVEL") or "").upper()
                            if level not in {"", "SESSION", "USER"}:
                                continue
                            value = row.get("value") or row.get("VALUE")
                            if value in (None, ""):
                                return None
                            return str(value)
                        # Fallback to first row if level filtering failed
                        first = rows[0]
                        value = first.get("value") or first.get("VALUE")
                        if value in (None, ""):
                            return None
                        return str(value)
                    except Exception:
                        return None

                def _set_session_parameter(name: str, value: Any) -> None:
                    try:
                        if name == "QUERY_TAG":
                            if value:
                                escaped = _escape_tag(str(value))
                                cursor.execute(
                                    f"ALTER SESSION SET QUERY_TAG = '{escaped}'"
                                )
                            else:
                                cursor.execute("ALTER SESSION UNSET QUERY_TAG")
                        elif name == "STATEMENT_TIMEOUT_IN_SECONDS":
                            cursor.execute(
                                f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {int(value)}"
                            )
                        else:
                            cursor.execute(f"ALTER SESSION SET {name} = {value}")
                    except Exception:
                        # Session parameter adjustments are best-effort; ignore failures.
                        pass

                def _restore_session_parameters(
                    previous: Dict[str, Optional[str]],
                ) -> None:
                    try:
                        prev_tag = previous.get("QUERY_TAG")
                        if "QUERY_TAG" in params:
                            if prev_tag:
                                escaped = _escape_tag(prev_tag)
                                cursor.execute(
                                    f"ALTER SESSION SET QUERY_TAG = '{escaped}'"
                                )
                            else:
                                cursor.execute("ALTER SESSION UNSET QUERY_TAG")
                    except Exception:
                        pass

                    try:
                        prev_timeout = previous.get("STATEMENT_TIMEOUT_IN_SECONDS")
                        if "STATEMENT_TIMEOUT_IN_SECONDS" in params:
                            if prev_timeout and prev_timeout.isdigit():
                                cursor.execute(
                                    "ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {}".format(
                                        int(prev_timeout)
                                    )
                                )
                            else:
                                cursor.execute(
                                    "ALTER SESSION UNSET STATEMENT_TIMEOUT_IN_SECONDS"
                                )
                    except Exception:
                        pass

                def run_query() -> None:
                    try:
                        # Apply session overrides (warehouse/database/schema/role)
                        if overrides:
                            apply_session_context(cursor, overrides)
                        previous_parameters: Dict[str, Optional[str]] = {}
                        if "QUERY_TAG" in params:
                            previous_parameters["QUERY_TAG"] = _get_session_parameter(
                                "QUERY_TAG"
                            )
                            _set_session_parameter("QUERY_TAG", params["QUERY_TAG"])
                        if "STATEMENT_TIMEOUT_IN_SECONDS" in params:
                            previous_parameters["STATEMENT_TIMEOUT_IN_SECONDS"] = (
                                _get_session_parameter("STATEMENT_TIMEOUT_IN_SECONDS")
                            )
                            _set_session_parameter(
                                "STATEMENT_TIMEOUT_IN_SECONDS",
                                params["STATEMENT_TIMEOUT_IN_SECONDS"],
                            )
                        cursor.execute(statement)
                        # Capture Snowflake query id when available
                        try:
                            qid = getattr(cursor, "sfqid", None)
                        except Exception:
                            qid = None
                        query_id_box["id"] = qid
                        # Only fetch rows if a result set is present
                        has_result_set = (
                            getattr(cursor, "description", None) is not None
                        )
                        if has_result_set:
                            raw_rows = cursor.fetchall()
                            description = getattr(cursor, "description", None) or []
                            column_names = []
                            for idx, col in enumerate(description):
                                name = None
                                if isinstance(col, (list, tuple)) and col:
                                    name = col[0]
                                else:
                                    name = getattr(col, "name", None) or getattr(
                                        col, "column_name", None
                                    )
                                if not name:
                                    name = f"column_{idx}"
                                column_names.append(str(name))

                            processed_rows = []
                            for raw in raw_rows:
                                if isinstance(raw, dict):
                                    record = raw
                                elif hasattr(raw, "_asdict"):
                                    record = raw._asdict()  # type: ignore[assignment]
                                elif isinstance(raw, (list, tuple)):
                                    record = {}
                                    for idx, value in enumerate(raw):
                                        key = (
                                            column_names[idx]
                                            if idx < len(column_names)
                                            else f"column_{idx}"
                                        )
                                        record[key] = value
                                else:
                                    # Fallback for scalar rows or mismatched metadata
                                    record = {"value": raw}

                                processed_rows.append(json_compatible(record))

                            result_box["rows"] = processed_rows
                            result_box["rowcount"] = len(processed_rows)
                        else:
                            # DML/DDL: no result set, use rowcount from cursor if available
                            rc = getattr(cursor, "rowcount", 0)
                            try:
                                # Normalize negative/None to 0
                                rc = int(rc) if rc and int(rc) >= 0 else 0
                            except Exception:
                                rc = 0
                            result_box["rows"] = []
                            result_box["rowcount"] = rc
                    except Exception as exc:  # capture to re-raise on main thread
                        result_box["error"] = exc
                    finally:
                        try:
                            _restore_session_parameters(previous_parameters)
                        except Exception:
                            pass
                        try:
                            restore_session_context(cursor, original)
                        except Exception:
                            pass
                        done.set()

                worker = threading.Thread(target=run_query, daemon=True)
                worker.start()

                finished = done.wait(timeout)
                if not finished:
                    # Local timeout: cancel the running statement server-side
                    try:
                        cursor.cancel()
                    except Exception:
                        # Best-effort. If cancel fails, we still time out.
                        pass

                    # Give a short grace period for cancellation to propagate
                    done.wait(5)
                    # Signal timeout to caller
                    raise TimeoutError(
                        "Query execution exceeded timeout and was cancelled"
                    )

                # Worker finished: process result
                if result_box["error"] is not None:
                    raise result_box["error"]  # type: ignore[misc]

                rows = result_box["rows"] or []
                rowcount = result_box.get("rowcount")
                if rowcount is None:
                    rowcount = len(rows)
                duration_ms = int((time.time() - started) * 1000)
                return {
                    "statement": statement,
                    "rowcount": rowcount,
                    "rows": rows,
                    "query_id": query_id_box.get("id"),
                    "duration_ms": duration_ms,
                }

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Execute Snowflake Query",
            "type": "object",
            "additionalProperties": False,
            "required": ["statement"],
            "properties": {
                "statement": {
                    **string_schema(
                        "SQL statement to execute. Must be permitted by the SQL allow list.",
                        title="SQL Statement",
                        examples=[
                            "SELECT CURRENT_ACCOUNT(), CURRENT_REGION()",
                            (
                                "SELECT REGION, SUM(REVENUE) AS total "
                                "FROM SALES.METRICS.REVENUE_BY_REGION "
                                "GROUP BY REGION"
                            ),
                        ],
                    ),
                    "minLength": 1,
                },
                "reason": {
                    **string_schema(
                        (
                            "Short reason for executing this query. Stored in Snowflake "
                            "QUERY_TAG and local history. Avoid sensitive information."
                        ),
                        title="Reason",
                        examples=[
                            "Validate yesterday's revenue spike",
                            "Power BI dashboard refresh",
                            "Investigate nulls in customer_email",
                        ],
                    ),
                },
                "warehouse": snowflake_identifier_schema(
                    "Warehouse override. Defaults to the active profile warehouse.",
                    title="Warehouse",
                    examples=["ANALYTICS_WH", "REPORTING_WH"],
                ),
                "database": snowflake_identifier_schema(
                    "Database override. Defaults to the current database.",
                    title="Database",
                    examples=["SALES", "PIPELINE_V2_GROOT_DB"],
                ),
                "schema": snowflake_identifier_schema(
                    "Schema override. Defaults to the current schema.",
                    title="Schema",
                    examples=["PUBLIC", "PIPELINE_V2_GROOT_SCHEMA"],
                ),
                "role": snowflake_identifier_schema(
                    "Role override. Defaults to the current role.",
                    title="Role",
                    examples=["ANALYST", "SECURITYADMIN"],
                ),
                "timeout_seconds": integer_schema(
                    "Query timeout in seconds (falls back to config default).",
                    minimum=1,
                    maximum=3600,
                    default=30,
                    examples=[30, 60, 300],
                ),
                "verbose_errors": boolean_schema(
                    "Include detailed optimization hints in error messages.",
                    default=False,
                    examples=[True],
                ),
            },
        }
