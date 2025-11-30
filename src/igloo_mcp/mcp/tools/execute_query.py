"""Execute Query MCP Tool - Execute SQL queries against Snowflake.

Part of v1.8.0 Phase 2.2 - extracted from mcp_server.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anyio

try:  # pragma: no cover - imported for typing/runtime compatibility only
    from fastmcp import Context
    from fastmcp.utilities.logging import get_logger
except ImportError:  # pragma: no cover
    try:
        from mcp.server.fastmcp import Context  # type: ignore[import-untyped,assignment]
        from mcp.server.fastmcp.utilities.logging import (
            get_logger,  # type: ignore[import-untyped]
        )
    except ImportError:  # pragma: no cover
        Context = Any  # type: ignore[misc,assignment]
        import logging

        def get_logger(name: str) -> logging.Logger:
            return logging.getLogger(name)


import contextlib

from igloo_mcp.cache import QueryResultCache
from igloo_mcp.config import Config
from igloo_mcp.constants import (
    ALLOWED_SESSION_PARAMETERS,
    MAX_QUERY_TIMEOUT_SECONDS,
    MAX_REASON_LENGTH,
    MAX_SQL_STATEMENT_LENGTH,
    MIN_QUERY_TIMEOUT_SECONDS,
    RESULT_KEEP_FIRST_ROWS,
    RESULT_KEEP_LAST_ROWS,
    RESULT_SIZE_LIMIT_MB,
    RESULT_TRUNCATION_THRESHOLD,
    STATEMENT_PREVIEW_LENGTH,
)
from igloo_mcp.logging import (
    Insight,
    QueryHistory,
    normalize_insight,
    truncate_insight_for_storage,
)
from igloo_mcp.mcp.error_utils import wrap_execution_error, wrap_timeout_error
from igloo_mcp.mcp.exceptions import MCPValidationError
from igloo_mcp.mcp.utils import json_compatible
from igloo_mcp.mcp.validation_helpers import validate_response_mode
from igloo_mcp.mcp_health import MCPHealthMonitor
from igloo_mcp.path_utils import (
    DEFAULT_ARTIFACT_ROOT,
    find_repo_root,
    resolve_artifact_root,
)
from igloo_mcp.post_query_insights import build_default_insights
from igloo_mcp.service_layer import QueryService
from igloo_mcp.session_utils import (
    apply_session_context,
    ensure_session_lock,
    restore_session_context,
    snapshot_session,
)
from igloo_mcp.sql_objects import extract_query_objects
from igloo_mcp.sql_validation import validate_sql_statement

from .base import MCPTool, tool_error_handler
from .schema_utils import (
    boolean_schema,
    integer_schema,
    snowflake_identifier_schema,
    string_schema,
)

logger = get_logger(__name__)


def _write_sql_artifact(artifact_root: Path, sql_sha256: str, sql: str) -> Path | None:
    """Write SQL statement to artifact storage with SHA-256 naming.

    Persists SQL text to disk for audit trails and query history correlation.
    Creates parent directories if needed. Uses SHA-256 hash for deduplication
    so identical queries share the same artifact file.

    Args:
        artifact_root: Base directory for SQL artifacts
        sql_sha256: SHA-256 hash of SQL statement (used as filename)
        sql: SQL statement text to persist

    Returns:
        Path to written artifact file, or None if write failed

    Example:
        >>> path = _write_sql_artifact(
        ...     Path("logs/artifacts"),
        ...     "a1b2c3d4...",
        ...     "SELECT * FROM table"
        ... )
        >>> assert path.name == "a1b2c3d4....sql"
    """
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


def _relative_sql_path(repo_root: Path, artifact_path: Path | None) -> str | None:
    """Compute relative path from repo root to SQL artifact.

    Used for portable artifact references in history logs and reports.
    Returns None if artifact_path is None or path computation fails.

    Args:
        repo_root: Repository root directory
        artifact_path: Absolute path to artifact file

    Returns:
        Relative path string (e.g., "logs/artifacts/a1b2c3....sql")
        or absolute path if not under repo_root, or None if input is None

    Example:
        >>> rel = _relative_sql_path(
        ...     Path("/repo"),
        ...     Path("/repo/logs/foo.sql")
        ... )
        >>> assert rel == "logs/foo.sql"
    """
    if artifact_path is None:
        return None
    try:
        return artifact_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return artifact_path.resolve().as_posix()


# Result mode constants
RESULT_MODE_FULL = "full"
RESULT_MODE_SUMMARY = "summary"
RESULT_MODE_SCHEMA_ONLY = "schema_only"
RESULT_MODE_SAMPLE = "sample"
RESULT_MODE_SAMPLE_SIZE = 10  # Default sample size for 'sample' mode
RESULT_MODE_SUMMARY_SAMPLE_SIZE = 5  # Sample size for 'summary' mode


def _build_hint(rowcount: int, sample_size: int) -> str | None:
    """Build helpful hint for result mode based on actual vs sample size.

    Args:
        rowcount: Total number of rows in result
        sample_size: Number of rows being returned

    Returns:
        Hint string or None if no rows
    """
    if rowcount == 0:
        return None
    if rowcount <= sample_size:
        return f"All {rowcount} rows returned"
    return f"Showing first {sample_size} of {rowcount} rows. Use result_mode='full' to retrieve all rows"


def _apply_result_mode(result: dict[str, Any], mode: str) -> dict[str, Any]:
    """Apply result_mode filtering to reduce response size for token efficiency.

    This function modifies the query result based on the requested mode to reduce
    token usage in LLM contexts. It preserves all metadata (columns, key_metrics,
    insights) while controlling the number of rows returned.

    Args:
        result: Full query result dict containing rows, columns, rowcount, etc.
        mode: Result mode to apply. Options:
              - 'full': No filtering, return all rows (pass-through)
              - 'summary': Return key_metrics + 5 sample rows (~90% reduction)
              - 'schema_only': Return schema/metrics only, no rows (~95% reduction)
              - 'sample': Return first 10 rows in result order (~60-80% reduction)

    Returns:
        Modified result dict. For non-'full' modes, includes:
            - result_mode: The mode that was applied
            - result_mode_info: Dict with filtering metadata including
              total_rows, rows_returned, sample_size, and hint

    Notes:
        - **Mutates input dict**: Modifies result in-place for efficiency.
          If you need the original dict, pass a copy: _apply_result_mode(dict(result), mode)
        - Always preserves: columns, key_metrics, insights, session_context
        - Only modifies: rows array (truncated based on mode), adds result_mode metadata
        - Sampling uses result order, not database order. Use ORDER BY for deterministic sampling.
        - Safe to call multiple times (idempotent for same mode)
    """
    if mode == RESULT_MODE_FULL:
        return result

    # Get original rows for filtering
    rows = result.get("rows", [])
    rowcount = result.get("rowcount", len(rows))
    columns = result.get("columns", [])

    # Add result_mode to response so caller knows what they got
    result["result_mode"] = mode

    if mode == RESULT_MODE_SCHEMA_ONLY:
        # Return only schema info, no rows
        result["rows"] = []
        result["result_mode_info"] = {
            "mode": "schema_only",
            "total_rows": rowcount,
            "rows_returned": 0,
            "hint": "Use result_mode='full' to retrieve all rows",
        }
        return result

    if mode == RESULT_MODE_SAMPLE:
        # Return first N rows only (in result order - use ORDER BY for deterministic sampling)
        sample_rows = rows[:RESULT_MODE_SAMPLE_SIZE]
        result["rows"] = sample_rows

        result["result_mode_info"] = {
            "mode": "sample",
            "total_rows": rowcount,
            "rows_returned": len(sample_rows),
            "sample_size": RESULT_MODE_SAMPLE_SIZE,
            "hint": _build_hint(rowcount, RESULT_MODE_SAMPLE_SIZE),
        }
        return result

    if mode == RESULT_MODE_SUMMARY:
        # Return key_metrics + small sample only
        sample_rows = rows[:RESULT_MODE_SUMMARY_SAMPLE_SIZE]
        result["rows"] = sample_rows

        result["result_mode_info"] = {
            "mode": "summary",
            "total_rows": rowcount,
            "rows_returned": len(sample_rows),
            "sample_size": RESULT_MODE_SUMMARY_SAMPLE_SIZE,
            "columns_count": len(columns),
            "hint": _build_hint(rowcount, RESULT_MODE_SUMMARY_SAMPLE_SIZE),
        }
        # Ensure key_metrics is present (already computed by _ensure_default_insights)
        return result

    return result


class ExecuteQueryTool(MCPTool):
    """MCP tool for executing SQL queries against Snowflake."""

    def __init__(
        self,
        config: Config,
        snowflake_service: Any,
        query_service: QueryService,
        health_monitor: MCPHealthMonitor | None = None,
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
        # Avoid global cache bleed-through when no explicit cache settings are provided
        if not os.environ.get("IGLOO_MCP_CACHE_MODE") and not os.environ.get("IGLOO_MCP_CACHE_ROOT"):
            self._cache_enabled = False
            self._cache_mode = "disabled"

    @property
    def name(self) -> str:
        return "execute_query"

    def _init_artifact_root(self) -> tuple[Path | None, list[str]]:
        warnings: list[str] = []
        raw = os.environ.get("IGLOO_MCP_ARTIFACT_ROOT")
        try:
            primary = resolve_artifact_root(raw=raw)
        except Exception as exc:
            primary = None
            warnings.append(f"Failed to resolve artifact root from environment: {exc}")

        fallback = (Path.home() / ".igloo_mcp" / DEFAULT_ARTIFACT_ROOT).resolve()
        candidates: list[Path] = []
        if primary is not None:
            candidates.append(primary)
        if fallback not in candidates:
            candidates.append(fallback)

        for index, candidate in enumerate(candidates):
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                if index > 0:
                    warnings.append(f"Artifact root unavailable; using fallback: {candidate}")
                return candidate, warnings
            except Exception as exc:
                warnings.append(f"Failed to initialise artifact root {candidate}: {exc}")

        warnings.append("Artifact root unavailable; SQL artifacts and cache will be disabled.")
        return None, warnings

    def _persist_sql_artifact(self, sql_sha256: str, statement: str) -> Path | None:
        if self._artifact_root is None:
            self._transient_audit_warnings.append("SQL artifact root is unavailable; statement text was not persisted.")
            return None
        artifact_path = _write_sql_artifact(self._artifact_root, sql_sha256, statement)
        if artifact_path is None:
            self._transient_audit_warnings.append("Failed to persist SQL text for audit history.")
        return artifact_path

    def _resolve_cache_context(self, overrides: dict[str, str | None]) -> tuple[dict[str, str | None], bool]:
        """Return effective session context for caching and a flag indicating success.

        When caching is enabled we snapshot the Snowflake session to capture the
        defaults (warehouse/database/schema/role) and then merge in any explicit
        overrides provided by the caller. If the snapshot fails we record a warning
        and signal the caller to skip cache usage for this execution.
        """
        snapshot_values: dict[str, str | None] = {}
        success = False

        try:
            lock = ensure_session_lock(self.snowflake_service)
            with (
                lock,
                self.snowflake_service.get_connection(
                    use_dict_cursor=True,
                ) as (_, cursor),
            ):
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

        effective: dict[str, str | None] = {}
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

    async def _ensure_profile_health(self) -> None:
        if not self.health_monitor:
            return

        profile_health = await anyio.to_thread.run_sync(
            self.health_monitor.get_profile_health,
            self.config.snowflake.profile,
            False,
        )
        if profile_health.is_valid:
            return

        error_msg = profile_health.validation_error or "Profile validation failed"
        available = ", ".join(profile_health.available_profiles) if profile_health.available_profiles else "none"
        self.health_monitor.record_error(f"Profile validation failed: {error_msg}")
        raise MCPValidationError(
            f"Snowflake profile validation failed: {error_msg}",
            validation_errors=[
                f"Profile: {self.config.snowflake.profile}",
                f"Available: {available}",
            ],
            hints=[
                "Check configuration with 'snow connection list'",
                "Verify profile settings",
                "Run 'snow connection add' to create a new profile",
            ],
        )

    def _enforce_sql_permissions(self, statement: str) -> None:
        allow_list = self.config.sql_permissions.get_allow_list()
        disallow_list = self.config.sql_permissions.get_disallow_list()

        stmt_type, is_valid, error_msg = validate_sql_statement(statement, allow_list, disallow_list)

        if not is_valid and error_msg:
            if self.health_monitor:
                self.health_monitor.record_error(
                    f"SQL statement blocked: {stmt_type} - {statement[:STATEMENT_PREVIEW_LENGTH]}"
                )
            raise MCPValidationError(
                error_msg,
                validation_errors=[f"Statement type: {stmt_type}"],
                hints=[
                    "Set IGLOO_MCP_SQL_PERMISSIONS='write' to enable write operations",
                    "Use SELECT statements for read-only queries",
                ],
            )

    def _ensure_default_insights(self, result: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        key_metrics = result.get("key_metrics")
        insights = result.get("insights")
        rows = result.get("rows")

        if (key_metrics is None or insights is None) and rows:
            computed_metrics, computed_insights = build_default_insights(
                rows,
                columns=result.get("columns"),
                total_rows=result.get("rowcount"),
                truncated=bool(result.get("truncated")),
            )
            if key_metrics is None and computed_metrics:
                result["key_metrics"] = computed_metrics
                key_metrics = computed_metrics
            if insights is None and computed_insights:
                result["insights"] = computed_insights
                insights = computed_insights

        return key_metrics, insights or []

    @staticmethod
    def _iso_timestamp(epoch: float) -> str:
        return datetime.fromtimestamp(epoch, tz=UTC).isoformat()

    def _build_audit_info(
        self,
        *,
        execution_id: str,
        sql_sha256: str | None,
        history_artifacts: dict[str, str],
        cache_key: str | None,
        cache_hit_metadata: dict[str, Any] | None = None,
        session_context: dict[str, str | None] | None = None,
        columns: list[str] | None = None,
        include_full: bool = False,
    ) -> dict[str, Any]:
        """Build audit info with optional full details.
        
        Args:
            include_full: If True, include all details. If False, only essentials.
        """
        # Essential fields (always included)
        info: dict[str, Any] = {
            "execution_id": execution_id,
        }
        
        if sql_sha256:
            info["sql_sha256"] = sql_sha256
        
        # Cache hit status (always minimal)
        info["cache_hit"] = cache_hit_metadata is not None
        
        # Full details only when requested
        if include_full:
            info.update({
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
            })
            
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
        return (
            "Execute SQL queries against Snowflake with safety guardrails. "
            "Use for data exploration, validation, and analysis—always capture execution_id for citations. "
            "Start with response_mode='schema_only' for structure discovery, 'summary' for validation, "
            "'full' only for final data export."
        )

    @property
    def category(self) -> str:
        return "query"

    @property
    def tags(self) -> list[str]:
        return ["sql", "execute", "analytics", "warehouse"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
        return [
            {
                "description": "Preview recent sales rows",
                "parameters": {
                    "statement": ("SELECT * FROM ANALYTICS.SALES.FACT_ORDERS ORDER BY ORDER_TS DESC LIMIT 20"),
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
            {
                "description": "Run long analytics query with extended timeout",
                "parameters": {
                    "statement": (
                        "WITH params AS (SELECT DATEADD('day', -30, CURRENT_DATE) AS start_dt) "
                        "SELECT * FROM ANALYTICS.LONG_RUNNING_METRICS WHERE event_ts >= (SELECT start_dt FROM params)"
                    ),
                    "warehouse": "ANALYTICS_WH",
                    "timeout_seconds": 480,
                    "response_mode": "sync",
                },
            },
        ]

    def _extract_source_info(self, objects: list[dict[str, Any]]) -> dict[str, Any]:
        """Extract structured source info from referenced objects."""
        source_databases = set()
        tables = []
        for obj in objects:
            db = obj.get("database")
            schema = obj.get("schema")
            name = obj.get("name")

            if db:
                source_databases.add(db)

            # Construct fully qualified name
            parts = []
            if db:
                parts.append(db)
            if schema:
                parts.append(schema)
            if name:
                parts.append(name)
            # Only append if we have any parts
            if parts:
                tables.append(".".join(parts))

        return {
            "source_databases": sorted(source_databases),
            "tables": sorted(tables),
        }

    def _enrich_payload_with_objects(self, payload: dict[str, Any], referenced_objects: list[dict[str, Any]]) -> None:
        """Enrich payload with objects and extracted source info."""
        if referenced_objects:
            payload["objects"] = referenced_objects
            source_info = self._extract_source_info(referenced_objects)
            payload.update(source_info)

    async def _execute_impl(
        self,
        statement: str,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
        role: str | None = None,
        timeout_seconds: int | None = None,
        verbose_errors: bool = False,
        reason: str | None = None,
        normalized_insight: Insight | None = None,
        result_mode: str = "full",
        ctx: Context | None = None,
        *,
        execution_id_override: str | None = None,
        sql_sha_override: str | None = None,
        validate_profile: bool = True,
        validate_statement: bool = True,
    ) -> dict[str, Any]:
        """Internal execute_query implementation shared by sync + async flows."""

        if validate_profile:
            await self._ensure_profile_health()

        if validate_statement:
            # Validate SQL statement length
            if len(statement) > MAX_SQL_STATEMENT_LENGTH:
                raise MCPValidationError(
                    f"SQL statement exceeds maximum length of {MAX_SQL_STATEMENT_LENGTH} characters",
                    validation_errors=[f"Statement length: {len(statement)} characters"],
                    hints=[
                        "Break the query into smaller parts",
                        "Use CTEs or views to simplify complex queries",
                    ],
                )
            self._enforce_sql_permissions(statement)

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
            effective_context, cache_context_ready = self._resolve_cache_context(overrides_input)
        else:
            effective_context = {
                "warehouse": overrides_input.get("warehouse"),
                "database": overrides_input.get("database"),
                "schema": overrides_input.get("schema"),
                "role": overrides_input.get("role"),
            }

        # Generate execution metadata
        execution_id = execution_id_override or uuid.uuid4().hex
        requested_ts = time.time()
        sql_sha256 = sql_sha256 or hashlib.sha256(statement.encode("utf-8")).hexdigest()
        referenced_objects = extract_query_objects(statement)
        history_artifacts: dict[str, str] = {}
        artifact_path = self._persist_sql_artifact(sql_sha256, statement)
        if artifact_path is not None:
            sql_rel = _relative_sql_path(self._repo_root, artifact_path)
            if sql_rel:
                history_artifacts["sql_path"] = sql_rel

        timeout = int(timeout_seconds or getattr(self.config, "timeout_seconds", 120))  # type: ignore[arg-type]

        cache_key: str | None = None
        cache_hit_metadata: dict[str, Any] | None = None
        cache_rows: list[dict[str, Any]] | None = None
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
                self._transient_audit_warnings.append("Query cache lookup failed; continuing with live execution.")

            if cache_hit:
                cache_rows = cache_hit.rows
                cache_hit_metadata = dict(cache_hit.metadata)
                cache_hit_metadata["manifest_path"] = cache_hit.manifest_path
                cache_hit_metadata["result_json_path"] = cache_hit.result_json_path
                if cache_hit.result_csv_path:
                    cache_hit_metadata["result_csv_path"] = cache_hit.result_csv_path
                manifest_rel = _relative_sql_path(self._repo_root, cache_hit.manifest_path)
                if manifest_rel:
                    history_artifacts["cache_manifest"] = manifest_rel
                rows_rel = _relative_sql_path(self._repo_root, cache_hit.result_json_path)
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
                result["cache"]["result_csv_path"] = str(cache_hit_metadata["result_csv_path"])
            if cache_hit_metadata.get("truncated"):
                result["truncated"] = cache_hit_metadata.get("truncated")
            session_context = effective_context.copy()
            if cache_hit_metadata.get("context"):
                context_data: dict[str, Any] = cache_hit_metadata["context"]
                session_context.update(
                    {k: context_data.get(k) for k in ["warehouse", "database", "schema", "role"] if context_data.get(k)}
                )
            result["session_context"] = session_context
            if cache_hit_metadata.get("columns"):
                result["columns"] = cache_hit_metadata["columns"]
            if cache_hit_metadata.get("objects"):
                result["objects"] = cache_hit_metadata["objects"]

            # Retrieve stored insight from cache manifest
            stored_insight_raw = cache_hit_metadata.get("post_query_insight")
            if stored_insight_raw:
                # Normalize stored insight if needed (may be stored as dict or already normalized)
                stored_insight = (
                    normalize_insight(stored_insight_raw)
                    if isinstance(stored_insight_raw, (str, dict))
                    else stored_insight_raw
                )
                result["post_query_insight"] = stored_insight

            cached_metrics = cache_hit_metadata.get("key_metrics")
            if cached_metrics:
                result["key_metrics"] = cached_metrics
            cached_insights = cache_hit_metadata.get("insights")
            if cached_insights:
                result["insights"] = cached_insights
            cached_objects = cache_hit_metadata.get("objects")
            if cached_objects:
                result["objects"] = cached_objects

            key_metrics, derived_insights = self._ensure_default_insights(result)

            payload: dict[str, Any] = {
                "ts": requested_ts,
                "timestamp": self._iso_timestamp(requested_ts),
                "execution_id": execution_id,
                "status": "cache_hit",
                "profile": self.config.snowflake.profile,
                "statement_preview": statement[:STATEMENT_PREVIEW_LENGTH],
                "rowcount": rowcount,
                "timeout_seconds": timeout,
                "overrides": overrides,
                "cache_key": cache_key,
                "cache_created_at": cache_hit_metadata.get("created_at"),
                "cache_manifest": str(cache_hit_metadata.get("manifest_path")),
                "columns": cache_hit_metadata.get("columns"),
            }
            full_session = effective_context.copy()
            full_session.update(
                {
                    k: session_context.get(k)
                    for k in ["warehouse", "database", "schema", "role"]
                    if session_context.get(k)
                }
            )
            payload["session_context"] = full_session
            # Always include sql_sha256 in history payload (computed at line 499)
            payload["sql_sha256"] = sql_sha256
            if history_artifacts:
                payload["artifacts"] = dict(history_artifacts)
            if reason:
                payload["reason"] = reason
            # Include truncated insight in history (for storage)
            if stored_insight_raw:
                stored_insight_for_storage = (
                    normalize_insight(stored_insight_raw)
                    if isinstance(stored_insight_raw, (str, dict))
                    else stored_insight_raw
                )
                payload["post_query_insight"] = truncate_insight_for_storage(stored_insight_for_storage)
            if key_metrics:
                payload["key_metrics"] = key_metrics
            if derived_insights:
                payload["insights"] = derived_insights
            self._enrich_payload_with_objects(payload, referenced_objects)
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
            # Apply result_mode filtering before returning
            return _apply_result_mode(result, result_mode)

        # Execute query with session context management

        try:
            result = await anyio.to_thread.run_sync(  # type: ignore[arg-type]
                self._execute_query_sync,
                statement,
                overrides,
                timeout,
                reason,
            )

            key_metrics, derived_insights = self._ensure_default_insights(result)

            if self.health_monitor and hasattr(self.health_monitor, "record_query_success"):
                self.health_monitor.record_query_success(statement[:STATEMENT_PREVIEW_LENGTH])  # type: ignore[attr-defined]

            # Persist success history (lightweight JSONL)
            session_context = result.get("session_context") or effective_context
            manifest_path: Path | None = None
            if self._cache_enabled and cache_key and cache_context_ready:
                try:
                    # Store truncated insight in cache manifest
                    cache_insight = None
                    if normalized_insight:
                        cache_insight = truncate_insight_for_storage(normalized_insight)

                    cache_metadata = {
                        "profile": self.config.snowflake.profile,
                        "context": session_context,
                        "rowcount": result.get("rowcount"),
                        "duration_ms": result.get("duration_ms"),
                        "statement_sha256": sql_sha256,
                        "truncated": result.get("truncated"),
                        "post_query_insight": cache_insight,
                        "reason": reason,
                        "columns": result.get("columns"),
                        "key_metrics": key_metrics,
                        "insights": derived_insights,
                        "objects": referenced_objects,
                    }
                    manifest_path = self.cache.store(
                        cache_key,
                        rows=result.get("rows") or [],
                        metadata=cache_metadata,
                    )
                except Exception:
                    logger.debug("Failed to persist query cache", exc_info=True)
                    self._transient_audit_warnings.append("Failed to persist query cache entry.")

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
                    "statement_preview": statement[:STATEMENT_PREVIEW_LENGTH],
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
                # Include truncated insight in history (for storage)
                if normalized_insight:
                    payload["post_query_insight"] = truncate_insight_for_storage(normalized_insight)
                if cache_key:
                    payload["cache_key"] = cache_key
                if manifest_path is not None:
                    payload["cache_manifest"] = str(manifest_path)
                if result.get("columns"):
                    payload["columns"] = result.get("columns")
                if key_metrics:
                    payload["key_metrics"] = key_metrics
                if derived_insights:
                    payload["insights"] = derived_insights
                self._enrich_payload_with_objects(payload, referenced_objects)
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
            if referenced_objects:
                result["objects"] = referenced_objects

            # Include full (untruncated) insight in response
            if normalized_insight:
                result["post_query_insight"] = normalized_insight

            result["audit_info"] = self._build_audit_info(
                execution_id=execution_id,
                sql_sha256=sql_sha256,
                history_artifacts=history_artifacts,
                cache_key=cache_key,
                cache_hit_metadata=None,
                session_context=session_context,
                columns=result.get("columns"),
            )

            # Apply result_mode filtering before returning
            return _apply_result_mode(result, result_mode)

        except TimeoutError as e:
            # Persist timeout history
            try:
                completed_ts = time.time()
                payload = {
                    "ts": completed_ts,
                    "timestamp": self._iso_timestamp(completed_ts),
                    "execution_id": execution_id,
                    "status": "timeout",
                    "profile": self.config.snowflake.profile,
                    "statement_preview": statement[:STATEMENT_PREVIEW_LENGTH],
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
                # Include truncated insight in history (for storage)
                if normalized_insight:
                    payload["post_query_insight"] = truncate_insight_for_storage(normalized_insight)
                if cache_key:
                    payload["cache_key"] = cache_key
                self._enrich_payload_with_objects(payload, referenced_objects)
                self.history.record(payload)
            except Exception:
                pass

            # Use standardized timeout error wrapper
            context = {
                "timeout_seconds": timeout,
                "warehouse": overrides.get("warehouse"),
                "database": overrides.get("database"),
                "schema": overrides.get("schema"),
                "role": overrides.get("role"),
            }
            timeout_error = wrap_timeout_error(
                timeout_seconds=timeout,
                operation="query",
                verbose=verbose_errors,
                context=context,
            )
            if self.health_monitor:
                self.health_monitor.record_error(str(timeout_error))
            self._collect_audit_warnings()
            raise timeout_error
        except Exception as e:
            error_message = str(e)

            if self.health_monitor:
                self.health_monitor.record_error(f"Query execution failed: {error_message[:200]}")

            # Persist failure history
            try:
                completed_ts = time.time()
                payload = {
                    "ts": completed_ts,
                    "timestamp": self._iso_timestamp(completed_ts),
                    "execution_id": execution_id,
                    "status": "error",
                    "profile": self.config.snowflake.profile,
                    "statement_preview": statement[:STATEMENT_PREVIEW_LENGTH],
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
                # Include truncated insight in history (for storage)
                if normalized_insight:
                    payload["post_query_insight"] = truncate_insight_for_storage(normalized_insight)
                if cache_key:
                    payload["cache_key"] = cache_key
                self._enrich_payload_with_objects(payload, referenced_objects)
                self.history.record(payload)
            except Exception:
                pass

            # Use standardized execution error wrapper
            context = {
                "timeout_seconds": timeout,
                "warehouse": overrides.get("warehouse"),
                "database": overrides.get("database"),
                "schema": overrides.get("schema"),
                "role": overrides.get("role"),
                "statement_preview": statement[:STATEMENT_PREVIEW_LENGTH],
            }
            hints = [
                "Check SQL syntax and table names",
                "Verify database/schema context",
                "Check permissions for the objects referenced",
            ]
            if verbose_errors:
                query_preview = statement[:STATEMENT_PREVIEW_LENGTH]
                if len(statement) > STATEMENT_PREVIEW_LENGTH:
                    query_preview += "..."
                hints.extend(
                    [
                        f"Query: {query_preview}",
                        f"Timeout: {timeout}s",
                    ]
                )
            else:
                hints.append("Use verbose_errors=true for detailed information")

            execution_error = wrap_execution_error(
                message=f"Query execution failed: {error_message[:150] if not verbose_errors else error_message}",
                operation="execute_query",
                original_error=e,
                hints=hints,
                context=context,
            )
            self._collect_audit_warnings()
            raise execution_error

    @tool_error_handler("execute_query")
    async def execute(
        self,
        statement: str,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
        role: str | None = None,
        timeout_seconds: int | None = None,
        verbose_errors: bool = False,
        reason: str | None = None,
        post_query_insight: dict[str, Any] | str | None = None,
        result_mode: str | None = None,
        response_mode: str | None = None,
        ctx: Context | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute SQL query against Snowflake with validation and token optimization.

        This is the main entry point for SQL query execution. It provides:
        - SQL permission validation (blocks DDL/DML by default)
        - Configurable timeouts with server-side cancellation
        - Session parameter overrides (warehouse, database, schema, role)
        - Result caching with SHA-256 indexing
        - Token-efficient response modes
        - Auto-generated insights and key metrics

        Args:
            statement: SQL statement to execute (max 1MB)
            warehouse: Optional warehouse override (default: from profile)
            database: Optional database override (default: from profile)
            schema: Optional schema override (default: from profile)
            role: Optional role override (default: from profile)
            timeout_seconds: Query timeout in seconds (1-3600, default: 120)
            verbose_errors: Include all error hints (default: False for compact errors)
            reason: Required. Short description for audit trail (min 5 chars).
                   Stored in Snowflake QUERY_TAG and local history.
            post_query_insight: Optional summary or structured JSON describing results.
                              Stored in history and cache artifacts.
            response_mode: Control response verbosity for token efficiency (STANDARD, default: "summary")
                        - "summary": Return key_metrics + 5 sample rows (default)
                        - "full": Return all rows (no filtering)
                        - "schema_only": Return column schema only, no rows
                        - "sample": Return first 10 rows only
            result_mode: DEPRECATED in v0.3.5 - use response_mode instead
            ctx: Optional MCP context for request correlation
            **kwargs: Additional arguments (for backward compatibility)

        Returns:
            Dict containing query results and metadata. When response_mode is not "full",
            includes additional fields:
                - result_mode: Mode used ("summary", "schema_only", or "sample")
                - result_mode_info: Filtering metadata with total_rows, rows_returned,
                                   sample_size, and hint for retrieving response_mode='full'

        Raises:
            TypeError: If timeout_seconds is not an integer
            MCPValidationError: If parameters fail validation
            MCPExecutionError: If query execution fails
            MCPPermissionError: If SQL contains blocked operations
        """

        if "metric_insight" in kwargs:
            raise TypeError("execute_query no longer accepts 'metric_insight'; use 'post_query_insight' instead")

        normalized_insight: Insight | None = None
        if post_query_insight is not None:
            normalized_insight = normalize_insight(post_query_insight)

        # Validate response_mode parameter with backward compatibility
        effective_result_mode = validate_response_mode(
            response_mode,
            legacy_param_name="result_mode",
            legacy_param_value=result_mode,
            valid_modes=("full", "summary", "schema_only", "sample"),
            default="full",
        )

        coerced_timeout: int | None = None
        if timeout_seconds is not None:
            if isinstance(timeout_seconds, bool):
                raise TypeError("timeout_seconds must be an integer value in seconds.")

            try:
                numeric = float(timeout_seconds)
            except (TypeError, ValueError):
                raise TypeError("timeout_seconds must be an integer value in seconds.") from None

            if not numeric.is_integer():
                raise TypeError("timeout_seconds must be an integer value in seconds.")

            coerced_timeout = int(numeric)
            if not MIN_QUERY_TIMEOUT_SECONDS <= coerced_timeout <= MAX_QUERY_TIMEOUT_SECONDS:
                raise MCPValidationError(
                    f"timeout_seconds must be between {MIN_QUERY_TIMEOUT_SECONDS} "
                    f"and {MAX_QUERY_TIMEOUT_SECONDS} seconds",
                    validation_errors=[f"Invalid timeout: {coerced_timeout}"],
                    hints=[
                        f"Use a timeout between {MIN_QUERY_TIMEOUT_SECONDS} and {MAX_QUERY_TIMEOUT_SECONDS} seconds",
                    ],
                )

        # Validate SQL statement length
        if len(statement) > MAX_SQL_STATEMENT_LENGTH:
            raise MCPValidationError(
                f"SQL statement exceeds maximum length of {MAX_SQL_STATEMENT_LENGTH} characters",
                validation_errors=[f"Statement length: {len(statement)} characters"],
                hints=[
                    "Break the query into smaller parts",
                    "Use CTEs or views to simplify complex queries",
                ],
            )

        # Always validate profile + SQL up front so async paths fail fast.
        await self._ensure_profile_health()
        self._enforce_sql_permissions(statement)

        mode = (response_mode or "auto").lower()
        if mode not in {"auto", "sync"}:
            raise MCPValidationError(
                "Invalid response_mode",
                validation_errors=[f"response_mode must be one of: auto, sync (got: {mode})"],
                hints=["Use response_mode='auto' or response_mode='sync'"],
            )

        # Both auto and sync modes use synchronous execution
        return await self._execute_impl(
            statement=statement,
            warehouse=warehouse,
            database=database,
            schema=schema,
            role=role,
            timeout_seconds=coerced_timeout,
            verbose_errors=verbose_errors,
            reason=reason,
            normalized_insight=normalized_insight,
            result_mode=effective_result_mode,
            ctx=ctx,
        )

    def _execute_query_sync(
        self,
        statement: str,
        overrides: dict[str, Any],
        timeout: int,
        reason: str | None = None,
    ) -> dict[str, Any]:
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
                reason_clean = " ".join(reason.split())[:MAX_REASON_LENGTH]
                existing = params.get("QUERY_TAG")

                # Try merging into existing JSON tag if present
                merged = None
                if isinstance(existing, str):
                    try:
                        obj = json.loads(existing)
                        if isinstance(obj, dict):
                            obj.update({"tool": "execute_query", "reason": reason_clean})
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

        with (
            lock,
            self.snowflake_service.get_connection(
                use_dict_cursor=True,
            ) as (_, cursor),
        ):
            original = snapshot_session(cursor)

            result_box: dict[str, Any] = {
                "rows": None,
                "rowcount": None,
                "error": None,
                "session": None,
                "columns": None,
            }
            query_id_box: dict[str, str | None] = {"id": None}
            done = threading.Event()

            def _validate_session_parameter_name(name: str) -> bool:
                """Validate that session parameter name is in the whitelist."""
                return name.upper() in ALLOWED_SESSION_PARAMETERS

            def _escape_sql_identifier(identifier: str) -> str:
                r"""Escape SQL identifier for use in LIKE clause.

                Escapes:
                - Single quotes (' -> '')
                - LIKE wildcards (% -> \%, _ -> \_)

                Args:
                    identifier: SQL identifier to escape

                Returns:
                    Escaped identifier safe for LIKE clause
                """
                # Escape single quotes first
                escaped = identifier.replace("'", "''")
                # Escape LIKE wildcards (must escape backslash first if present)
                escaped = escaped.replace("\\", "\\\\")
                escaped = escaped.replace("%", "\\%")
                escaped = escaped.replace("_", "\\_")
                return escaped

            def _escape_tag(tag_value: str) -> str:
                """Escape tag value for use in SQL string literal."""
                return tag_value.replace("'", "''")

            def _escape_sql_value(value: Any) -> str:
                """Escape SQL value for use in SQL statement."""
                if isinstance(value, (int, float)):
                    return str(value)
                value_str = str(value)
                # Escape single quotes and wrap in quotes
                return f"'{value_str.replace(chr(39), chr(39) + chr(39))}'"

            def _get_session_parameter(name: str) -> str | None:
                """Get session parameter value with SQL injection protection."""
                try:
                    # Validate parameter name
                    if not _validate_session_parameter_name(name):
                        logger.warning(f"Attempted to access invalid session parameter: {name}")
                        return None
                    # Escape the name for LIKE clause
                    escaped_name = _escape_sql_identifier(name)
                    cursor.execute(f"SHOW PARAMETERS LIKE '{escaped_name}' IN SESSION")
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
                    logger.debug(f"Failed to get session parameter {name}", exc_info=True)
                    return None

            def _set_session_parameter(name: str, value: Any) -> None:
                """Set session parameter with SQL injection protection."""
                try:
                    # Validate parameter name against whitelist
                    if not _validate_session_parameter_name(name):
                        logger.warning(f"Attempted to set invalid session parameter: {name}")
                        return

                    name_upper = name.upper()
                    if name_upper == "QUERY_TAG":
                        if value:
                            escaped = _escape_tag(str(value))
                            cursor.execute(f"ALTER SESSION SET QUERY_TAG = '{escaped}'")
                        else:
                            cursor.execute("ALTER SESSION UNSET QUERY_TAG")
                    elif name_upper == "STATEMENT_TIMEOUT_IN_SECONDS":
                        # Validate value is numeric
                        try:
                            timeout_value = int(value)
                            cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {timeout_value}")
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid timeout value for STATEMENT_TIMEOUT_IN_SECONDS: {value}")
                    else:
                        # For other parameters, escape both name and value
                        escaped_value = _escape_sql_value(value)
                        cursor.execute(f"ALTER SESSION SET {name_upper} = {escaped_value}")
                except Exception:
                    # Session parameter adjustments are best-effort; ignore failures.
                    logger.debug(f"Failed to set session parameter {name}", exc_info=True)
                    pass

            def _restore_session_parameters(
                previous: dict[str, str | None],
            ) -> None:
                """Restore session parameters with SQL injection protection."""
                try:
                    prev_tag = previous.get("QUERY_TAG")
                    if "QUERY_TAG" in params:
                        if prev_tag:
                            escaped = _escape_tag(prev_tag)
                            cursor.execute(f"ALTER SESSION SET QUERY_TAG = '{escaped}'")
                        else:
                            cursor.execute("ALTER SESSION UNSET QUERY_TAG")
                except Exception:
                    logger.debug(
                        "Failed to restore QUERY_TAG session parameter",
                        exc_info=True,
                    )
                    pass

                try:
                    prev_timeout = previous.get("STATEMENT_TIMEOUT_IN_SECONDS")
                    if "STATEMENT_TIMEOUT_IN_SECONDS" in params:
                        if prev_timeout and prev_timeout.isdigit():
                            cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {int(prev_timeout)}")
                        else:
                            cursor.execute("ALTER SESSION UNSET STATEMENT_TIMEOUT_IN_SECONDS")
                except Exception:
                    pass

            def run_query() -> None:
                try:
                    # Apply session overrides (warehouse/database/schema/role)
                    if overrides:
                        apply_session_context(cursor, overrides)
                    previous_parameters: dict[str, str | None] = {}
                    if "QUERY_TAG" in params:
                        previous_parameters["QUERY_TAG"] = _get_session_parameter("QUERY_TAG")
                        _set_session_parameter("QUERY_TAG", params["QUERY_TAG"])
                    if "STATEMENT_TIMEOUT_IN_SECONDS" in params:
                        previous_parameters["STATEMENT_TIMEOUT_IN_SECONDS"] = _get_session_parameter(
                            "STATEMENT_TIMEOUT_IN_SECONDS"
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
                    has_result_set = getattr(cursor, "description", None) is not None
                    if has_result_set:
                        raw_rows = cursor.fetchall()
                        description = getattr(cursor, "description", None) or []
                        column_names = []
                        for idx, col in enumerate(description):
                            name = None
                            if isinstance(col, (list, tuple)) and col:
                                name = col[0]
                            else:
                                name = getattr(col, "name", None) or getattr(col, "column_name", None)
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
                                    key = column_names[idx] if idx < len(column_names) else f"column_{idx}"
                                    record[key] = value
                            else:
                                # Fallback for scalar rows or mismatched metadata
                                record = {"value": raw}

                            processed_rows.append(json_compatible(record))

                        result_box["rows"] = processed_rows
                        result_box["rowcount"] = len(processed_rows)
                        result_box["columns"] = column_names

                        # Smart truncation for large outputs to prevent context window overflow
                        if len(processed_rows) > RESULT_TRUNCATION_THRESHOLD:
                            import json

                            # Sample data size estimation
                            sample_size = len(json.dumps(processed_rows[:100]))
                            estimated_total_size = sample_size * (len(processed_rows) / 100)

                            # If estimated output is too large, truncate with metadata
                            size_limit_bytes = RESULT_SIZE_LIMIT_MB * 1024 * 1024
                            if estimated_total_size > size_limit_bytes:
                                original_count = len(processed_rows)
                                truncated_rows = processed_rows[:RESULT_KEEP_FIRST_ROWS]
                                last_rows = processed_rows[-RESULT_KEEP_LAST_ROWS:]

                                result_box["rows"] = [
                                    *truncated_rows,
                                    {"__truncated__": True, "__message__": "Large result set truncated"},
                                    *last_rows,
                                ]
                                result_box["truncated"] = True
                                result_box["original_rowcount"] = original_count
                                result_box["returned_rowcount"] = len(result_box["rows"])
                                result_box["truncation_info"] = {
                                    "original_size_mb": round(estimated_total_size / (1024 * 1024), 2),
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
                    with contextlib.suppress(Exception):
                        _restore_session_parameters(previous_parameters)
                    with contextlib.suppress(Exception):
                        restore_session_context(cursor, original)
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
                # Signal timeout to caller (will be caught and wrapped above)
                raise TimeoutError(f"Query execution exceeded timeout ({timeout}s) and was cancelled")

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

    def get_parameter_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Execute Snowflake Query",
            "type": "object",
            "additionalProperties": False,
            "required": ["statement", "reason"],
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
                            "REQUIRED: Short reason for executing this query. "
                            "Stored in Snowflake QUERY_TAG, history, and cache metadata "
                            "to explain why the data was requested. Avoid sensitive information. "
                            "Examples: 'Validate revenue spike', 'Dashboard refresh', 'Investigate missing data'"
                        ),
                        title="Reason (REQUIRED)",
                        examples=[
                            "Validate yesterday's revenue spike",
                            "Power BI dashboard refresh",
                            "Investigate nulls in customer_email",
                            "Check Q3 2025 Hyperliquid coverage",
                            "Explore Base DEX BTC trading volume",
                        ],
                    ),
                    "minLength": 5,
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
                "timeout_seconds": {
                    "title": "Timeout Seconds",
                    "description": (
                        "Query timeout in seconds (falls back to config default). Accepts "
                        "either an integer or a numeric string so CLI clients that serialize "
                        "arguments as strings continue to work."
                    ),
                    "default": 30,
                    "anyOf": [
                        integer_schema(
                            "Numeric timeout value",
                            minimum=MIN_QUERY_TIMEOUT_SECONDS,
                            maximum=MAX_QUERY_TIMEOUT_SECONDS,
                            examples=[30, 60, 300],
                        ),
                        {
                            "type": "string",
                            "pattern": r"^[0-9]+$",
                            "description": "Numeric string timeout (e.g., '120').",
                            "examples": ["30", "60", "300"],
                        },
                    ],
                },
                "verbose_errors": boolean_schema(
                    "Include detailed optimization hints in error messages.",
                    default=False,
                    examples=[True],
                ),
                "post_query_insight": {
                    "title": "Post Query Insight",
                    "description": (
                        "Optional insights or key findings from the query results. Metadata-only; no extra compute. "
                        "Logged alongside the history and caches so agents can recall what was discovered without "
                        "re-running the statement. Provide either a plain summary string or structured JSON with "
                        "richer context."
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
                "response_mode": {
                    "title": "Response Mode",
                    "type": "string",
                    "enum": ["auto", "sync"],
                    "default": "auto",
                    "description": (
                        "Controls how the tool responds: 'auto' and 'sync' both use synchronous execution. "
                        "This parameter is maintained for backward compatibility."
                    ),
                    "examples": ["auto", "sync"],
                },
            },
        }
