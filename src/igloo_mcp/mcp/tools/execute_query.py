"""Execute Query MCP Tool - Execute SQL queries against Snowflake.

Part of v1.8.0 Phase 2.2 - extracted from mcp_server.py.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import anyio

from igloo_mcp.cache import QueryResultCache
from igloo_mcp.config import Config
from igloo_mcp.logging import QueryHistory
from igloo_mcp.mcp.utils import json_compatible
from igloo_mcp.mcp_health import MCPHealthMonitor
from igloo_mcp.path_utils import (
    DEFAULT_ARTIFACT_ROOT,
    find_repo_root,
    resolve_artifact_root,
)
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

logger = logging.getLogger(__name__)


def _write_sql_artifact(
    artifact_root: Path, sql_sha256: str, sql: str
) -> Optional[Path]:
    """Persist SQL text under the by-sha directory if missing."""

    try:
        queries_dir = artifact_root / "queries" / "by_sha"
        queries_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = (queries_dir / f"{sql_sha256}.sql").resolve()
        if not artifact_path.exists():
            artifact_path.write_text(sql, encoding="utf-8")
        return artifact_path
    except Exception:
        logger.debug("Failed to persist SQL artifact", exc_info=True)
        return None


def _relative_sql_path(repo_root: Path, artifact_path: Optional[Path]) -> Optional[str]:
    if artifact_path is None:
        return None
    try:
        return artifact_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return artifact_path.resolve().as_posix()


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
        self._history_enabled = self.history.enabled
        self._repo_root = find_repo_root()
        self._artifact_root, artifact_warnings = self._init_artifact_root()
        self._static_audit_warnings: list[str] = list(artifact_warnings)
        self._transient_audit_warnings: list[str] = []
        self.cache = QueryResultCache.from_env(artifact_root=self._artifact_root)
        self._cache_enabled = self.cache.enabled
        self._cache_mode = self.cache.mode
        self._static_audit_warnings.extend(self.cache.pop_warnings())

    @property
    def name(self) -> str:
        return "execute_query"

    def _init_artifact_root(self) -> tuple[Optional[Path], list[str]]:
        warnings: list[str] = []
        raw = os.environ.get("IGLOO_MCP_ARTIFACT_ROOT")
        try:
            primary = resolve_artifact_root(raw=raw)
        except Exception as exc:
            primary = None
            warnings.append(f"Failed to resolve artifact root from environment: {exc}")

        fallback = (Path.home() / ".igloo_mcp" / DEFAULT_ARTIFACT_ROOT).resolve()
        candidates = []
        if primary is not None:
            candidates.append(primary)
        if fallback not in candidates:
            candidates.append(fallback)

        for index, candidate in enumerate(candidates):
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                if index > 0:
                    warnings.append(
                        f"Artifact root unavailable; using fallback: {candidate}"
                    )
                return candidate, warnings
            except Exception as exc:
                warnings.append(
                    f"Failed to initialise artifact root {candidate}: {exc}"
                )

        warnings.append(
            "Artifact root unavailable; SQL artifacts and cache will be disabled."
        )
        return None, warnings

    def _persist_sql_artifact(self, sql_sha256: str, statement: str) -> Optional[Path]:
        if self._artifact_root is None:
            self._transient_audit_warnings.append(
                "SQL artifact root is unavailable; statement text was not persisted."
            )
            return None
        artifact_path = _write_sql_artifact(self._artifact_root, sql_sha256, statement)
        if artifact_path is None:
            self._transient_audit_warnings.append(
                "Failed to persist SQL text for audit history."
            )
        return artifact_path

    def _resolve_cache_context(
        self, overrides: Dict[str, Optional[str]]
    ) -> tuple[Dict[str, Optional[str]], bool]:
        """Return effective session context for caching and a flag indicating success.

        When caching is enabled we snapshot the Snowflake session to capture the
        defaults (warehouse/database/schema/role) and then merge in any explicit
        overrides provided by the caller. If the snapshot fails we record a warning
        and signal the caller to skip cache usage for this execution.
        """
        snapshot_values: Dict[str, Optional[str]] = {}
        success = False

        try:
            lock = ensure_session_lock(self.snowflake_service)
            with lock:
                with self.snowflake_service.get_connection(
                    use_dict_cursor=True,
                ) as (_, cursor):
                    snapshot = snapshot_session(cursor)
            snapshot_values = {
                "warehouse": snapshot.warehouse,
                "database": snapshot.database,
                "schema": snapshot.schema,
                "role": snapshot.role,
            }
            success = True
        except Exception:
            self._transient_audit_warnings.append(
                "Failed to snapshot session defaults; skipping cache for this execution."
            )

        effective: Dict[str, Optional[str]] = {}
        for key in ("warehouse", "database", "schema", "role"):
            override_value = overrides.get(key)
            if override_value is not None:
                effective[key] = override_value
            else:
                effective[key] = snapshot_values.get(key)

        return effective, success

    def _collect_audit_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self._static_audit_warnings:
            warnings.extend(self._static_audit_warnings)
            self._static_audit_warnings = []
        if self._transient_audit_warnings:
            warnings.extend(self._transient_audit_warnings)
            self._transient_audit_warnings = []
        warnings.extend(self.history.pop_warnings())
        warnings.extend(self.cache.pop_warnings())
        return warnings

    @staticmethod
    def _iso_timestamp(epoch: float) -> str:
        return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()

    def _build_audit_info(
        self,
        *,
        execution_id: str,
        sql_sha256: Optional[str],
        history_artifacts: Dict[str, str],
        cache_key: Optional[str],
        cache_hit_metadata: Optional[Dict[str, Any]] = None,
        session_context: Optional[Dict[str, Optional[str]]] = None,
        columns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "execution_id": execution_id,
            "history_enabled": self.history.enabled and not self.history.disabled,
            "history_path": str(self.history.path) if self.history.path else None,
            "artifact_root": str(self._artifact_root) if self._artifact_root else None,
            "cache": {
                "mode": self._cache_mode,
                "root": str(self.cache.root) if self.cache.root else None,
                "key": cache_key,
                "hit": cache_hit_metadata is not None,
            },
            "artifacts": dict(history_artifacts),
        }
        if sql_sha256:
            info["sql_sha256"] = sql_sha256
        if session_context:
            info["session_context"] = dict(session_context)
        if columns:
            info["columns"] = list(columns)
        if cache_hit_metadata:
            manifest_path = cache_hit_metadata.get("manifest_path")
            if manifest_path:
                info["cache"]["manifest"] = str(manifest_path)
            if cache_hit_metadata.get("created_at"):
                info["cache"]["created_at"] = cache_hit_metadata["created_at"]
        warnings = self._collect_audit_warnings()
        if warnings:
            info["warnings"] = warnings
        return info

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
        metric_insight: Optional[Dict[str, Any] | str] = None,
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
            reason: Short reason for executing this query
            metric_insight: Optional dict or string with key findings and metrics from query results

        Returns:
            Query results with rows, rowcount, and execution metadata

        Raises:
            ValueError: If profile validation fails or SQL is blocked
            RuntimeError: If query execution fails
        """
        if timeout_seconds is not None:
            if isinstance(timeout_seconds, str):
                try:
                    timeout_seconds = int(timeout_seconds)
                except (TypeError, ValueError):
                    raise TypeError(
                        "timeout_seconds must be an integer value in seconds."
                    ) from None
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
        overrides_input = {
            "warehouse": warehouse,
            "database": database,
            "schema": schema,
            "role": role,
        }
        overrides = {k: v for k, v in overrides_input.items() if v is not None}
        cache_context_ready = False
        if self._cache_enabled:
            effective_context, cache_context_ready = self._resolve_cache_context(
                overrides_input
            )
        else:
            effective_context = {
                "warehouse": overrides_input.get("warehouse"),
                "database": overrides_input.get("database"),
                "schema": overrides_input.get("schema"),
                "role": overrides_input.get("role"),
            }

        execution_id = uuid.uuid4().hex
        requested_ts = time.time()
        sql_sha256 = hashlib.sha256(statement.encode("utf-8")).hexdigest()
        history_artifacts: Dict[str, str] = {}
        artifact_path = self._persist_sql_artifact(sql_sha256, statement)
        if artifact_path is not None:
            sql_rel = _relative_sql_path(self._repo_root, artifact_path)
            if sql_rel:
                history_artifacts["sql_path"] = sql_rel

        timeout = timeout_seconds or getattr(self.config, "timeout_seconds", 120)

        cache_key: Optional[str] = None
        cache_hit_metadata: Optional[Dict[str, Any]] = None
        cache_rows: Optional[list[Dict[str, Any]]] = None
        if self._cache_enabled and cache_context_ready:
            try:
                cache_key = self.cache.compute_cache_key(
                    sql_sha256=sql_sha256,
                    profile=self.config.snowflake.profile,
                    effective_context=effective_context,
                )
                cache_hit = self.cache.lookup(cache_key)
            except Exception:
                cache_hit = None
                logger.debug("Query cache lookup failed", exc_info=True)
                self._transient_audit_warnings.append(
                    "Query cache lookup failed; continuing with live execution."
                )

            if cache_hit:
                cache_rows = cache_hit.rows
                cache_hit_metadata = dict(cache_hit.metadata)
                cache_hit_metadata["manifest_path"] = cache_hit.manifest_path
                cache_hit_metadata["result_json_path"] = cache_hit.result_json_path
                if cache_hit.result_csv_path:
                    cache_hit_metadata["result_csv_path"] = cache_hit.result_csv_path
                manifest_rel = _relative_sql_path(
                    self._repo_root, cache_hit.manifest_path
                )
                if manifest_rel:
                    history_artifacts["cache_manifest"] = manifest_rel
                rows_rel = _relative_sql_path(
                    self._repo_root, cache_hit.result_json_path
                )
                if rows_rel:
                    history_artifacts["cache_rows"] = rows_rel

        if cache_rows is not None and cache_hit_metadata is not None:
            rowcount = cache_hit_metadata.get("rowcount")
            if rowcount is None:
                rowcount = len(cache_rows)
            result = {
                "statement": statement,
                "rowcount": rowcount,
                "rows": cache_rows,
                "query_id": None,
                "duration_ms": cache_hit_metadata.get("duration_ms", 0),
                "cache": {
                    "hit": True,
                    "cache_key": cache_key,
                    "created_at": cache_hit_metadata.get("created_at"),
                    "manifest_path": str(cache_hit_metadata.get("manifest_path")),
                },
            }
            if cache_hit_metadata.get("result_csv_path"):
                result["cache"]["result_csv_path"] = str(
                    cache_hit_metadata["result_csv_path"]
                )
            if cache_hit_metadata.get("truncated"):
                result["truncated"] = cache_hit_metadata.get("truncated")
            if cache_hit_metadata.get("context"):
                result.setdefault("session_context", cache_hit_metadata["context"])
            else:
                result.setdefault("session_context", effective_context)
            if cache_hit_metadata.get("columns"):
                result["columns"] = cache_hit_metadata["columns"]

            payload: Dict[str, Any] = {
                "ts": requested_ts,
                "timestamp": self._iso_timestamp(requested_ts),
                "execution_id": execution_id,
                "status": "cache_hit",
                "profile": self.config.snowflake.profile,
                "statement_preview": statement[:200],
                "rowcount": rowcount,
                "timeout_seconds": timeout,
                "overrides": overrides,
                "cache_key": cache_key,
                "cache_created_at": cache_hit_metadata.get("created_at"),
                "cache_manifest": str(cache_hit_metadata.get("manifest_path")),
                "columns": cache_hit_metadata.get("columns"),
            }
            payload["session_context"] = effective_context
            if sql_sha256:
                payload["sql_sha256"] = sql_sha256
            if history_artifacts:
                payload["artifacts"] = dict(history_artifacts)
            if reason:
                payload["reason"] = reason
            if metric_insight:
                payload["metric_insight"] = metric_insight
            try:
                self.history.record(payload)
            except Exception:
                logger.debug("Failed to record cache hit in history", exc_info=True)

            result["audit_info"] = self._build_audit_info(
                execution_id=execution_id,
                sql_sha256=sql_sha256,
                history_artifacts=history_artifacts,
                cache_key=cache_key,
                cache_hit_metadata=cache_hit_metadata,
                session_context=effective_context,
                columns=cache_hit_metadata.get("columns"),
            )
            return result

        # Execute query with session context management

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
            session_context = result.get("session_context") or effective_context
            manifest_path: Optional[Path] = None
            if self._cache_enabled and cache_key and cache_context_ready:
                try:
                    cache_metadata = {
                        "profile": self.config.snowflake.profile,
                        "context": session_context,
                        "rowcount": result.get("rowcount"),
                        "duration_ms": result.get("duration_ms"),
                        "statement_sha256": sql_sha256,
                        "truncated": result.get("truncated"),
                        "metric_insight": metric_insight,
                        "reason": reason,
                        "columns": result.get("columns"),
                    }
                    manifest_path = self.cache.store(
                        cache_key,
                        rows=result.get("rows") or [],
                        metadata=cache_metadata,
                    )
                except Exception:
                    logger.debug("Failed to persist query cache", exc_info=True)
                    self._transient_audit_warnings.append(
                        "Failed to persist query cache entry."
                    )

            if manifest_path is not None:
                manifest_rel = _relative_sql_path(self._repo_root, manifest_path)
                if manifest_rel:
                    history_artifacts["cache_manifest"] = manifest_rel
                rows_file = manifest_path.parent / "rows.jsonl"
                rows_rel = _relative_sql_path(self._repo_root, rows_file)
                if rows_rel:
                    history_artifacts.setdefault("cache_rows", rows_rel)

            try:
                completed_ts = time.time()
                payload = {
                    "ts": completed_ts,
                    "timestamp": self._iso_timestamp(completed_ts),
                    "execution_id": execution_id,
                    "status": "success",
                    "profile": self.config.snowflake.profile,
                    "statement_preview": statement[:200],
                    "rowcount": result.get("rowcount", 0),
                    "timeout_seconds": timeout,
                    "overrides": overrides,
                    "query_id": result.get("query_id"),
                    "duration_ms": result.get("duration_ms"),
                    "session_context": session_context,
                }
                if sql_sha256 is not None:
                    payload["sql_sha256"] = sql_sha256
                if history_artifacts:
                    payload["artifacts"] = dict(history_artifacts)
                if reason:
                    payload["reason"] = reason
                if metric_insight:
                    payload["metric_insight"] = metric_insight
                if cache_key:
                    payload["cache_key"] = cache_key
                if manifest_path is not None:
                    payload["cache_manifest"] = str(manifest_path)
                if result.get("columns"):
                    payload["columns"] = result.get("columns")
                self.history.record(payload)
            except Exception:
                pass

            result.setdefault(
                "cache",
                {
                    "hit": False,
                    "cache_key": cache_key,
                },
            )
            if manifest_path is not None:
                result["cache"]["manifest_path"] = str(manifest_path)
            if session_context:
                result.setdefault("session_context", session_context)

            result["audit_info"] = self._build_audit_info(
                execution_id=execution_id,
                sql_sha256=sql_sha256,
                history_artifacts=history_artifacts,
                cache_key=cache_key,
                cache_hit_metadata=None,
                session_context=session_context,
                columns=result.get("columns"),
            )

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
                completed_ts = time.time()
                payload = {
                    "ts": completed_ts,
                    "timestamp": self._iso_timestamp(completed_ts),
                    "execution_id": execution_id,
                    "status": "timeout",
                    "profile": self.config.snowflake.profile,
                    "statement_preview": statement[:200],
                    "timeout_seconds": timeout,
                    "overrides": overrides,
                    "error": str(e),
                }
                if sql_sha256 is not None:
                    payload["sql_sha256"] = sql_sha256
                if history_artifacts:
                    payload["artifacts"] = dict(history_artifacts)
                if reason:
                    payload["reason"] = reason
                if metric_insight:
                    payload["metric_insight"] = metric_insight
                if cache_key:
                    payload["cache_key"] = cache_key
                self.history.record(payload)
            except Exception:
                pass

            if verbose_errors:
                preview = statement[:200] + ("..." if len(statement) > 200 else "")
                self._collect_audit_warnings()
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
                self._collect_audit_warnings()
                raise RuntimeError(compact)
        except Exception as e:
            error_message = str(e)

            if self.health_monitor:
                self.health_monitor.record_error(
                    f"Query execution failed: {error_message[:200]}"
                )

            # Persist failure history
            try:
                completed_ts = time.time()
                payload = {
                    "ts": completed_ts,
                    "timestamp": self._iso_timestamp(completed_ts),
                    "execution_id": execution_id,
                    "status": "error",
                    "profile": self.config.snowflake.profile,
                    "statement_preview": statement[:200],
                    "timeout_seconds": timeout,
                    "overrides": overrides,
                    "error": error_message,
                }
                if sql_sha256 is not None:
                    payload["sql_sha256"] = sql_sha256
                if history_artifacts:
                    payload["artifacts"] = dict(history_artifacts)
                if reason:
                    payload["reason"] = reason
                if metric_insight:
                    payload["metric_insight"] = metric_insight
                if cache_key:
                    payload["cache_key"] = cache_key
                self.history.record(payload)
            except Exception:
                pass

            if verbose_errors:
                # Return detailed error with optimization hints
                self._collect_audit_warnings()
                raise RuntimeError(
                    f"Query execution failed: {error_message}\n\n"
                    f"Query: {statement[:200]}{'...' if len(statement) > 200 else ''}\n"
                    f"Timeout: {timeout}s\n"
                    f"Context: {overrides}"
                )
            else:
                # Return compact error
                self._collect_audit_warnings()
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
                    "session": None,
                    "columns": None,
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
                            result_box["columns"] = column_names

                            # Smart truncation for large outputs to prevent context window overflow
                            if len(processed_rows) > 1000:
                                import json

                                # Sample data size estimation
                                sample_size = len(json.dumps(processed_rows[:100]))
                                estimated_total_size = sample_size * (
                                    len(processed_rows) / 100
                                )

                                # If estimated output is too large (>1MB), truncate with metadata
                                if estimated_total_size > 1024 * 1024:
                                    original_count = len(processed_rows)
                                    truncated_rows = processed_rows[
                                        :500
                                    ]  # Keep first 500 rows
                                    last_10_rows = processed_rows[
                                        -10:
                                    ]  # Keep last 10 rows

                                    result_box["rows"] = (
                                        truncated_rows
                                        + [
                                            {
                                                "__truncated__": True,
                                                "__message__": "Large result set truncated",
                                            }
                                        ]
                                        + last_10_rows
                                    )
                                    result_box["truncated"] = True
                                    result_box["original_rowcount"] = original_count
                                    result_box["returned_rowcount"] = len(
                                        result_box["rows"]
                                    )
                                    result_box["truncation_info"] = {
                                        "original_size_mb": round(
                                            estimated_total_size / (1024 * 1024), 2
                                        ),
                                        "truncated_for_context_window": True,
                                        "export_suggestions": [
                                            "Consider using LIMIT clause in your query",
                                            "Export to CSV/Parquet: use warehouse with more memory",
                                            "Add WHERE clause to filter data early",
                                        ],
                                    }
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
                            session_snapshot = snapshot_session(cursor)
                            result_box["session"] = session_snapshot.to_mapping()
                        except Exception:
                            result_box["session"] = None
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
                    "session_context": result_box.get("session"),
                    "columns": result_box.get("columns"),
                    "truncated": result_box.get("truncated"),
                    "original_rowcount": result_box.get("original_rowcount"),
                    "returned_rowcount": result_box.get("returned_rowcount"),
                    "truncation_info": result_box.get("truncation_info"),
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
                            "QUERY_TAG, history, and cache metadata to explain why the data was requested. "
                            "Avoid sensitive information."
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
                "metric_insight": {
                    "title": "Metric Insight",
                    "description": (
                        "Optional insights or key findings from the query results. Logged alongside the history and "
                        "caches so agents can recall what was discovered without re-running the statement. Provide "
                        "either a plain summary string or structured JSON with richer context."
                    ),
                    "anyOf": [
                        string_schema(
                            "Summary insight describing noteworthy metrics or anomalies detected in the query results.",
                            examples=[
                                "Query shows 15% increase in daily active users compared to last week",
                                "Inventory levels holding steady while demand increases",
                            ],
                        ),
                        {
                            "type": "object",
                            "description": (
                                "Structured insight payload with optional fields for key metrics, business impact, and "
                                "follow-up needs."
                            ),
                            "properties": {
                                "summary": {
                                    "type": "string",
                                    "description": "Primary summary of the query findings.",
                                },
                                "key_metrics": {
                                    "type": "array",
                                    "description": "List of metric identifiers or human-readable highlights.",
                                    "items": {
                                        "type": "string",
                                    },
                                },
                                "business_impact": {
                                    "type": "string",
                                    "description": "Short explanation of business impact or recommendations.",
                                },
                                "follow_up_needed": {
                                    "type": "boolean",
                                    "description": "Flag indicating if additional investigation or action is required.",
                                },
                            },
                            "required": ["summary"],
                            "additionalProperties": True,
                            "examples": [
                                {
                                    "summary": "Revenue growth of 23% MoM",
                                    "key_metrics": [
                                        "revenue_up_23pct",
                                        "new_customers_450",
                                    ],
                                    "business_impact": "Positive trend indicating market expansion",
                                    "follow_up_needed": False,
                                }
                            ],
                        },
                    ],
                    "examples": [
                        "Query shows 15% increase in daily active users compared to last week",
                        {
                            "summary": "Revenue growth of 23% MoM",
                            "key_metrics": ["revenue_up_23pct", "new_customers_450"],
                            "business_impact": "Positive trend indicating market expansion",
                            "follow_up_needed": True,
                        },
                    ],
                },
            },
        }
