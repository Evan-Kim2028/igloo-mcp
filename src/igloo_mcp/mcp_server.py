"""FastMCP-powered MCP server providing Snowflake data operations.

This module boots a FastMCP server, reusing the upstream Snowflake MCP runtime
(`snowflake-labs-mcp`) for authentication, connection management, middleware,
transport wiring, and its suite of Cortex/object/query tools. On top of that
foundation we register the igloo-mcp catalog and dependency
workflows so agents can access both sets of capabilities via a single MCP
endpoint.
"""

from __future__ import annotations

import argparse
import os
import string
from contextlib import asynccontextmanager
from dataclasses import asdict
from functools import partial
from typing import Any, Dict, List, Optional

import anyio
from pydantic import Field
from typing_extensions import Annotated

# NOTE: For typing, import from the fastmcp package; fallback handled at runtime.
try:  # Prefer the standalone fastmcp package when available
    from fastmcp import Context, FastMCP
    from fastmcp.exceptions import NotFoundError
    from fastmcp.utilities.logging import configure_logging, get_logger
except ImportError:  # Fall back to the implementation bundled with python-sdk
    from mcp.server.fastmcp import Context, FastMCP  # type: ignore[import-untyped,assignment]
    from mcp.server.fastmcp.exceptions import NotFoundError  # type: ignore[import-untyped,assignment]
    from mcp.server.fastmcp.utilities.logging import configure_logging, get_logger  # type: ignore[import-untyped,assignment]

from mcp_server_snowflake.server import (  # type: ignore[import-untyped]
    SnowflakeService,
)
from mcp_server_snowflake.server import (
    create_lifespan as create_snowflake_lifespan,  # type: ignore[import-untyped]
)
from mcp_server_snowflake.utils import (  # type: ignore[import-untyped]
    get_login_params,
    warn_deprecated_params,
)

from .config import Config, ConfigError, apply_config_overrides, get_config, load_config
from .context import create_service_context
from .logging import QueryHistory, update_cache_manifest_insight

# Lineage functionality removed - not part of igloo-mcp
from .mcp.tools import (  # QueryLineageTool,  # Removed - lineage functionality not part of igloo-mcp
    BuildCatalogTool,
    BuildDependencyGraphTool,
    ConnectionTestTool,
    ExecuteQueryTool,
    GetCatalogSummaryTool,
    HealthCheckTool,
    PreviewTableTool,
    SearchCatalogTool,
)
from .mcp.utils import get_profile_recommendations
from .mcp_health import (
    MCPHealthMonitor,
)
from .mcp_resources import MCPResourceManager
from .path_utils import find_repo_root, resolve_artifact_root, resolve_history_path
from .profile_utils import (
    ProfileValidationError,
    get_profile_summary,
    validate_and_resolve_profile,
)
from .reporting.builder import build_report, lint_report
from .reporting.history_index import HistoryIndex
from .reporting.manifest import (
    DatasetRef,
    DatasetSource,
    ReportManifest,
    ReportOutput,
    TemplatesConfig,
    load_manifest,
)
from .service_layer import CatalogService, DependencyService, QueryService
from .session_utils import (
    SessionContext,
    apply_session_context,
    ensure_session_lock,
    restore_session_context,
    snapshot_session,
)
from .snow_cli import SnowCLI, SnowCLIError

_get_profile_recommendations = get_profile_recommendations

logger = get_logger(__name__)

# Global health monitor and resource manager instances
_health_monitor: Optional[MCPHealthMonitor] = None
_resource_manager: Optional[MCPResourceManager] = None
_catalog_service: Optional[CatalogService] = None


def read_sql_artifact_by_sha(sql_sha256: str) -> str:
    """Return the SQL text for the given SHA-256 hash."""

    if len(sql_sha256) != 64 or any(ch not in string.hexdigits for ch in sql_sha256):
        raise ValueError("sql_sha256 must be a 64-character hexadecimal digest")

    artifact_root = resolve_artifact_root().resolve()
    artifact_path = (
        artifact_root / "queries" / "by_sha" / f"{sql_sha256}.sql"
    ).resolve()
    if not artifact_path.is_relative_to(artifact_root):
        raise FileNotFoundError(
            f"SQL artifact for {sql_sha256} not found under {artifact_root}"
        )
    if not artifact_path.exists() or not artifact_path.is_file():
        raise FileNotFoundError(
            f"SQL artifact for {sql_sha256} not found under {artifact_root}"
        )
    return artifact_path.read_text(encoding="utf-8")


def _get_catalog_summary_sync(catalog_dir: str) -> Dict[str, Any]:
    service = _catalog_service
    if service is None:
        context = create_service_context(existing_config=get_config())
        service = CatalogService(context=context)
    return service.load_summary(catalog_dir)


def _execute_query_sync(
    snowflake_service: Any,
    statement: str,
    overrides: Dict[str, Optional[str]] | SessionContext,
) -> Dict[str, Any]:
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
                    "rows": rows,
                }
            finally:
                restore_session_context(cursor, original)


# _query_lineage_sync function removed - lineage functionality not part of igloo-mcp


def register_igloo_mcp(
    server: FastMCP,
    snowflake_service: SnowflakeService,
    *,
    enable_cli_bridge: bool = False,
) -> None:
    """Register igloo-mcp MCP endpoints on top of the official service.

    Simplified in v1.8.0 Phase 2.3 - now delegates to extracted tool classes
    instead of containing inline implementations. This reduces mcp_server.py
    from 1,089 LOC to ~300 LOC while improving testability and maintainability.
    """

    if getattr(server, "_igloo_mcp_registered", False):  # pragma: no cover - safety
        return
    setattr(server, "_igloo_mcp_registered", True)

    config = get_config()
    context = create_service_context(existing_config=config)
    query_service = QueryService(context=context)
    catalog_service = CatalogService(context=context)
    dependency_service = DependencyService(context=context)
    global _health_monitor, _resource_manager, _catalog_service
    _health_monitor = context.health_monitor
    _resource_manager = context.resource_manager
    _catalog_service = catalog_service
    snow_cli: SnowCLI | None = SnowCLI() if enable_cli_bridge else None

    # Instantiate all extracted tool classes
    execute_query_inst = ExecuteQueryTool(
        config, snowflake_service, query_service, _health_monitor
    )
    preview_table_inst = PreviewTableTool(config, snowflake_service, query_service)
    # query_lineage_inst = QueryLineageTool(config)  # Removed - lineage functionality not part of igloo-mcp
    build_catalog_inst = BuildCatalogTool(config, catalog_service)
    build_dependency_graph_inst = BuildDependencyGraphTool(dependency_service)
    test_connection_inst = ConnectionTestTool(config, snowflake_service)
    health_check_inst = HealthCheckTool(config, snowflake_service, _health_monitor)
    get_catalog_summary_inst = GetCatalogSummaryTool(catalog_service)
    search_catalog_inst = SearchCatalogTool()

    @server.tool(
        name="execute_query", description="Execute a SQL query against Snowflake"
    )
    async def execute_query_tool(
        statement: Annotated[str, Field(description="SQL statement to execute")],
        warehouse: Annotated[
            Optional[str], Field(description="Warehouse override", default=None)
        ] = None,
        database: Annotated[
            Optional[str], Field(description="Database override", default=None)
        ] = None,
        schema: Annotated[
            Optional[str], Field(description="Schema override", default=None)
        ] = None,
        role: Annotated[
            Optional[str], Field(description="Role override", default=None)
        ] = None,
        reason: Annotated[
            Optional[str],
            Field(
                description=(
                    "Short reason for executing this query. Stored in Snowflake QUERY_TAG "
                    "and local history; avoid sensitive info."
                ),
                default=None,
            ),
        ] = None,
        timeout_seconds: Annotated[
            Optional[int],
            Field(
                description=(
                    "Query timeout in seconds (default: 30s from config). "
                    "Integer between 1 and 3600."
                ),
                ge=1,
                le=3600,
                default=None,
            ),
        ] = None,
        verbose_errors: Annotated[
            bool,
            Field(
                description="Include detailed optimization hints in error messages (default: false for compact errors)",
                default=False,
            ),
        ] = False,
        post_query_insight: Annotated[
            Optional[Dict[str, Any] | str],
            Field(
                description=(
                    "Optional insights or key findings from query results. Metadata-only; no extra compute. "
                    "Can be a summary string or structured JSON with key metrics and business impact."
                ),
                default=None,
            ),
        ] = None,
        response_mode: Annotated[
            Optional[str],
            Field(
                description=(
                    "Execution response mode: 'auto' (default) runs synchronously until nearing the client timeout, "
                    "'async' enqueues the query and requires polling via fetch_async_query_result, "
                    "and 'sync' forces inline execution."
                ),
                default=None,
            ),
        ] = None,
        ctx: Context | None = None,
    ) -> Dict[str, Any]:
        """Execute a SQL query against Snowflake - delegates to ExecuteQueryTool."""
        try:
            return await execute_query_inst.execute(
                statement=statement,
                warehouse=warehouse,
                database=database,
                schema=schema,
                role=role,
                reason=reason,
                timeout_seconds=timeout_seconds,
                verbose_errors=verbose_errors,
                post_query_insight=post_query_insight,
                response_mode=response_mode,
                ctx=ctx,
            )
        except ValueError as e:
            # Enhanced structured error for validation issues
            error_msg = str(e)
            if "timeout_seconds must be an integer" in error_msg:
                raise ValueError(
                    {
                        "code": "PARAM_TYPE",
                        "message": "Invalid parameter type: timeout_seconds must be an integer",
                        "data": {
                            "path": ".timeout_seconds",
                            "expected": "integer",
                            "received_type": "string",
                            "hint": "Use 480 (number) without quotes instead of '480'",
                            "examples": [30, 60, 300, 480],
                        },
                    }
                ) from e
            elif "timeout_seconds must be between" in error_msg:
                raise ValueError(
                    {
                        "code": "PARAM_RANGE",
                        "message": "Invalid parameter value: timeout_seconds out of range",
                        "data": {
                            "path": ".timeout_seconds",
                            "min": 1,
                            "max": 3600,
                            "received_sample": timeout_seconds,
                            "hint": "Use a timeout between 1 and 3600 seconds",
                        },
                    }
                ) from e
            elif "SQL statement type" in error_msg:
                # Pass through enhanced SQL validation errors
                raise ValueError(error_msg) from e
            else:
                # Generic parameter error
                raise ValueError(
                    {
                        "code": "PARAM_VALIDATION",
                        "message": "Parameter validation failed",
                        "data": {
                            "error": error_msg,
                            "hint": "Check parameter values and types",
                        },
                    }
                ) from e
        except TimeoutError as e:
            # Structured timeout error
            raise RuntimeError(
                {
                    "code": "QUERY_TIMEOUT",
                    "message": f"Query timeout after {timeout_seconds or 30}s",
                    "data": {
                        "timeout_seconds": timeout_seconds or 30,
                        "suggestions": [
                            "Increase timeout: timeout_seconds=480",
                            "Add WHERE/LIMIT clause to reduce data volume",
                            "Use larger warehouse for complex queries",
                            "Use verbose_errors=True for detailed hints",
                        ],
                    },
                }
            ) from e
        except Exception as e:
            # Structured execution error
            error_msg = str(e)
            if verbose_errors:
                # Include detailed error when requested
                raise RuntimeError(error_msg) from e
            else:
                # Compact, actionable error
                raise RuntimeError(
                    {
                        "code": "QUERY_EXECUTION_FAILED",
                        "message": f"Query execution failed: {error_msg[:150]}",
                        "data": {
                            "hint": "Use verbose_errors=true for detailed information",
                            "suggestions": [
                                "Check SQL syntax and table names",
                                "Verify database/schema context",
                                "Check permissions for the objects referenced",
                            ],
                        },
                    }
                ) from e

    @server.tool(
        name="fetch_async_query_result",
        description="Check status or retrieve results for an async execute_query call",
    )
    async def fetch_async_query_result_tool(
        execution_id: Annotated[
            str,
            Field(
                description="Execution ID returned when execute_query runs in async mode",
            ),
        ],
        include_rows: Annotated[
            bool,
            Field(
                description="Include cached rows when the job has finished",
                default=True,
            ),
        ] = True,
    ) -> Dict[str, Any]:
        return await execute_query_inst.fetch_async_result(
            execution_id=execution_id,
            include_rows=include_rows,
        )

    @server.tool(name="preview_table", description="Preview table contents")
    async def preview_table_tool(
        table_name: Annotated[str, Field(description="Fully qualified table name")],
        limit: Annotated[int, Field(description="Row limit", ge=1, default=100)] = 100,
        warehouse: Annotated[
            Optional[str], Field(description="Warehouse override", default=None)
        ] = None,
        database: Annotated[
            Optional[str], Field(description="Database override", default=None)
        ] = None,
        schema: Annotated[
            Optional[str], Field(description="Schema override", default=None)
        ] = None,
        role: Annotated[
            Optional[str], Field(description="Role override", default=None)
        ] = None,
    ) -> Dict[str, Any]:
        """Preview table contents - delegates to PreviewTableTool."""
        return await preview_table_inst.execute(
            table_name=table_name,
            limit=limit,
            warehouse=warehouse,
            database=database,
            schema=schema,
            role=role,
        )

    @server.tool(name="build_catalog", description="Build Snowflake catalog metadata")
    async def build_catalog_tool(
        output_dir: Annotated[
            str,
            Field(description="Catalog output directory", default="./data_catalogue"),
        ] = "./data_catalogue",
        database: Annotated[
            Optional[str],
            Field(description="Specific database to introspect", default=None),
        ] = None,
        account: Annotated[
            bool, Field(description="Include entire account", default=False)
        ] = False,
        format: Annotated[
            str, Field(description="Output format (json/jsonl)", default="json")
        ] = "json",
        include_ddl: Annotated[
            bool, Field(description="Include object DDL", default=True)
        ] = True,
    ) -> Dict[str, Any]:
        """Build catalog metadata - delegates to BuildCatalogTool."""
        return await build_catalog_inst.execute(
            output_dir=output_dir,
            database=database,
            account=account,
            format=format,
            include_ddl=include_ddl,
        )

    # query_lineage tool removed - lineage functionality not part of igloo-mcp

    @server.tool(
        name="build_dependency_graph", description="Build object dependency graph"
    )
    async def build_dependency_graph_tool(
        database: Annotated[
            Optional[str], Field(description="Specific database", default=None)
        ] = None,
        schema: Annotated[
            Optional[str], Field(description="Specific schema", default=None)
        ] = None,
        account: Annotated[
            bool, Field(description="Include account-level metadata", default=False)
        ] = False,
        format: Annotated[
            str, Field(description="Output format (json/dot)", default="json")
        ] = "json",
    ) -> Dict[str, Any]:
        """Build dependency graph - delegates to BuildDependencyGraphTool."""
        return await build_dependency_graph_inst.execute(
            database=database,
            schema=schema,
            account_scope=account,
            format=format,
        )

    @server.tool(name="test_connection", description="Validate Snowflake connectivity")
    async def test_connection_tool() -> Dict[str, Any]:
        """Test Snowflake connection - delegates to TestConnectionTool."""
        return await test_connection_inst.execute()

    @server.tool(name="health_check", description="Get comprehensive health status")
    async def health_check_tool() -> Dict[str, Any]:
        """Get health status - delegates to HealthCheckTool."""
        return await health_check_inst.execute()

    @server.tool(name="get_catalog_summary", description="Read catalog summary JSON")
    async def get_catalog_summary_tool(
        catalog_dir: Annotated[
            str,
            Field(description="Catalog directory", default="./data_catalogue"),
        ] = "./data_catalogue",
    ) -> Dict[str, Any]:
        """Get catalog summary - delegates to GetCatalogSummaryTool."""
        return await get_catalog_summary_inst.execute(catalog_dir=catalog_dir)

    @server.tool(
        name="search_catalog", description="Search locally built catalog artifacts"
    )
    async def search_catalog_tool(
        catalog_dir: Annotated[
            str,
            Field(
                description="Directory containing catalog artifacts (catalog.json or catalog.jsonl).",
                default="./data_catalogue",
            ),
        ] = "./data_catalogue",
        object_types: Annotated[
            Optional[List[str]],
            Field(description="Optional list of object types to include", default=None),
        ] = None,
        database: Annotated[
            Optional[str],
            Field(description="Filter results to a specific database", default=None),
        ] = None,
        schema: Annotated[
            Optional[str],
            Field(description="Filter results to a specific schema", default=None),
        ] = None,
        name_contains: Annotated[
            Optional[str],
            Field(
                description="Substring search on object name (case-insensitive)",
                default=None,
            ),
        ] = None,
        column_contains: Annotated[
            Optional[str],
            Field(
                description="Substring search on column name (case-insensitive)",
                default=None,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description="Maximum number of results to return",
                ge=1,
                le=500,
                default=20,
            ),
        ] = 20,
    ) -> Dict[str, Any]:
        return await search_catalog_inst.execute(
            catalog_dir=catalog_dir,
            object_types=object_types,
            database=database,
            schema=schema,
            name_contains=name_contains,
            column_contains=column_contains,
            limit=limit,
        )

    @server.tool(
        name="report_scaffold",
        description=(
            "Scaffold a starter report manifest from recent execute_query history so agents "
            "can edit it and later build reports with report_build."
        ),
    )
    async def report_scaffold_tool(
        manifest_path: Annotated[
            Optional[str],
            Field(
                description=(
                    "Optional target path for a manifest YAML (e.g. 'reports/my_report.yaml'). "
                    "Used to derive report id and default output naming when write_manifest is true. "
                    "Relative paths are resolved against the repository root."
                ),
                default=None,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description=(
                    "Number of recent execute_query history entries to turn into datasets in the manifest."
                ),
                ge=1,
                le=20,
                default=3,
            ),
        ] = 3,
        write_manifest: Annotated[
            bool,
            Field(
                description=(
                    "If true, also write the scaffolded manifest YAML to disk (using manifest_path or 'report.yaml' "
                    "in the repo root) and return written_path. When false, only return the manifest JSON payload."
                ),
                default=False,
            ),
        ] = False,
    ) -> Dict[str, Any]:
        """Scaffold a ReportManifest from recent history entries.

        This tool is intended for AI/native workflows: it returns the manifest as
        structured JSON so agents can edit and commit it, and optionally writes a
        YAML file when requested.
        """

        from pathlib import Path

        history_path = resolve_history_path()
        index = HistoryIndex(history_path)
        records = index.records
        records_sorted = sorted(records, key=lambda r: r.get("ts") or 0.0)
        recent = records_sorted[-limit:] if limit and records_sorted else []

        datasets: List[DatasetRef] = []
        for idx, record in enumerate(recent, start=1):
            exec_id = record.get("execution_id")
            sha = record.get("sql_sha256")
            artifacts = record.get("artifacts") or {}
            cache_manifest = artifacts.get("cache_manifest") or record.get(
                "cache_manifest"
            )
            source = DatasetSource(
                execution_id=str(exec_id) if exec_id else None,
                sql_sha256=str(sha) if sha else None,
                cache_manifest=str(cache_manifest) if cache_manifest else None,
            )
            description = None
            if record.get("reason"):
                description = str(record["reason"])
            datasets.append(
                DatasetRef(
                    name=f"dataset_{idx}",
                    description=description,
                    source=source,
                )
            )

        if manifest_path is not None:
            manifest_raw = Path(manifest_path)
            report_id = manifest_raw.stem or "report"
        else:
            report_id = "report"

        manifest = ReportManifest(
            id=report_id,
            title=f"Report {report_id}",
            templates=TemplatesConfig(main="templates/report.md"),
            datasets=datasets,
            outputs=[
                ReportOutput(
                    name="default",
                    format="markdown",
                    path=f"reports/{report_id}.md",
                )
            ],
        )

        written_path: Optional[str] = None
        if write_manifest:
            raw_path = manifest_path or "report.yaml"
            path = Path(raw_path).expanduser()
            if not path.is_absolute():
                repo_root = find_repo_root()
                path = (repo_root / path).resolve()

            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                import yaml  # type: ignore[import-untyped]

                with path.open("w", encoding="utf-8") as fh:
                    yaml.safe_dump(manifest.model_dump(), fh, sort_keys=False)
                written_path = str(path)
            except Exception as exc:  # pragma: no cover - unlikely I/O error
                raise RuntimeError(
                    f"Failed to write scaffolded manifest: {exc}"
                ) from exc

        return {
            "manifest": manifest.model_dump(),
            "report_id": manifest.id,
            "dataset_count": len(manifest.datasets),
            "history_path": str(history_path),
            "written_path": written_path,
        }

    @server.tool(
        name="report_build",
        description=(
            "Validate a report manifest and build a narrative or JSON payload from cached execute_query results. "
            "Use validate_only=true to lint without rendering, or default settings to render the report body."
        ),
    )
    async def report_build_tool(
        manifest_path: Annotated[
            str,
            Field(
                description=(
                    "Path to the report manifest YAML to use (relative to repo root or absolute), "
                    "for example 'reports/my_report.yaml'."
                ),
                default="report.yaml",
            ),
        ] = "report.yaml",
        output_name: Annotated[
            Optional[str],
            Field(
                description=(
                    "Logical output name from manifest.outputs to build (default: the first output), "
                    "for example 'default' or 'html_export'."
                ),
                default=None,
            ),
        ] = None,
        format: Annotated[
            Optional[str],
            Field(
                description=(
                    "Optional override for output format: 'markdown', 'html', or 'json'. "
                    "Defaults to the manifest output format; 'json' is recommended for agent consumption."
                ),
                default=None,
            ),
        ] = None,
        persist_output: Annotated[
            bool,
            Field(
                description=(
                    "If true, write the rendered body to disk using either output_path "
                    "or the path defined on the selected manifest.outputs entry."
                ),
                default=False,
            ),
        ] = False,
        output_path: Annotated[
            Optional[str],
            Field(
                description=(
                    "Explicit output path for the rendered report when persist_output is true "
                    "(relative to repo root or absolute)."
                ),
                default=None,
            ),
        ] = None,
        validate_only: Annotated[
            bool,
            Field(
                description=(
                    "If true, only run validation and return ok/issues without rendering the report body."
                ),
                default=False,
            ),
        ] = False,
        fail_on_issues: Annotated[
            bool,
            Field(
                description=(
                    "If true and validation finds issues, skip rendering and return ok=false with issues, "
                    "so agents can treat any lint problems as hard failures."
                ),
                default=False,
            ),
        ] = False,
        include_body: Annotated[
            bool,
            Field(
                description=(
                    "If false, omit the rendered body from the response while still returning format, provenance, "
                    "and any validation issues (useful when agents only need metadata)."
                ),
                default=True,
            ),
        ] = True,
    ) -> Dict[str, Any]:
        import json
        from pathlib import Path

        raw_path = Path(manifest_path).expanduser()
        if raw_path.is_absolute():
            manifest_abs = raw_path.resolve()
        else:
            repo_root = find_repo_root()
            manifest_abs = (repo_root / raw_path).resolve()
        issues = lint_report(manifest_abs)
        ok = not issues

        response: Dict[str, Any] = {
            "manifest_path": str(manifest_abs),
            "ok": ok,
            "issues": [asdict(issue) for issue in issues],
        }

        if validate_only:
            return response

        if fail_on_issues and not ok:
            return response

        result = build_report(manifest_abs, output_name=output_name, refresh=False)
        result_format = result.get("format", "markdown")
        body = result.get("body", "")
        provenance = result.get("provenance", {})

        effective_format = format or result_format
        if effective_format == "html" and result_format == "markdown":
            body = f"<html><body><pre>\n{body}\n</pre></body></html>\n"

        selected_output_name: Optional[str] = output_name
        written_path: Optional[str] = None

        if persist_output:
            if output_path is not None:
                out_path = Path(output_path).expanduser()
                if not out_path.is_absolute():
                    repo_root = find_repo_root()
                    out_path = (repo_root / out_path).resolve()
            else:
                manifest_obj = load_manifest(manifest_abs)
                selected = None
                if output_name is not None:
                    for candidate in manifest_obj.outputs:
                        if candidate.name == output_name:
                            selected = candidate
                            break
                if selected is None:
                    if not manifest_obj.outputs:
                        raise ValueError(
                            "Report manifest defines no outputs and output_path was not provided",
                        )
                    selected = manifest_obj.outputs[0]
                selected_output_name = selected.name
                out_path = Path(selected.path).expanduser()
                if not out_path.is_absolute():
                    repo_root = find_repo_root()
                    out_path = (repo_root / out_path).resolve()

            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(body, encoding="utf-8")
            written_path = str(out_path)

        response.update(
            {
                "output_name": selected_output_name,
                "format": effective_format,
                "provenance": provenance,
            }
        )

        if include_body:
            response["body"] = body

        if effective_format == "json" and result_format == "json" and include_body:
            try:
                response["body_json"] = json.loads(body)
            except Exception:
                pass

        if written_path is not None:
            response["output_path"] = written_path

        return response

    @server.tool(
        name="record_query_insight",
        description="Attach a post-hoc insight to a prior execute_query run",
    )
    async def record_query_insight_tool(
        execution_id: Annotated[
            str,
            Field(
                description="Execution ID from execute_query.audit_info.execution_id"
            ),
        ],
        post_query_insight: Annotated[
            Dict[str, Any] | str,
            Field(description="LLM-provided post-query insight"),
        ],
        cache_manifest_override: Annotated[
            Optional[str],
            Field(
                description="Optional path to manifest if audit_info missing",
                default=None,
            ),
        ] = None,
        source: Annotated[
            Optional[str],
            Field(
                description="Optional source identifier (e.g., 'human', 'agent:claude')",
                default=None,
            ),
        ] = None,
    ) -> Dict[str, Any]:
        """Record a post-hoc insight for a prior query execution."""
        history = QueryHistory.from_env()
        result = history.record_insight(
            execution_id=execution_id,
            post_query_insight=post_query_insight,
            source=source,
        )

        # Try to update manifest if path provided
        updated_manifest: Optional[str] = None
        if cache_manifest_override:
            from pathlib import Path

            manifest_path = Path(cache_manifest_override)
            if update_cache_manifest_insight(manifest_path, post_query_insight):
                updated_manifest = str(manifest_path.resolve())

        return {
            "execution_id": result["execution_id"],
            "deduped": result["deduped"],
            "updated_manifest": updated_manifest,
        }

    @server.tool(
        name="describe_logging_paths",
        description="Get resolved paths for history, artifacts, and cache with writability checks",
    )
    async def describe_logging_paths_tool() -> Dict[str, Any]:
        """Describe logging paths and writability."""
        from pathlib import Path

        history = QueryHistory.from_env()
        history_path = str(history.path) if history.path else None

        artifact_root_raw = os.environ.get("IGLOO_MCP_ARTIFACT_ROOT")
        from .path_utils import resolve_artifact_root

        try:
            artifact_root = resolve_artifact_root(raw=artifact_root_raw)
            artifact_root_str = str(artifact_root)
        except Exception:
            artifact_root_str = None

        cache_root_str = None
        if artifact_root_str:
            from .path_utils import DEFAULT_CACHE_SUBDIR

            cache_root = Path(artifact_root_str) / DEFAULT_CACHE_SUBDIR
            cache_root_str = str(cache_root.resolve())

        # Check writability
        writable: Dict[str, bool] = {}
        if history_path:
            try:
                path = Path(history_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                test_file = path.parent / ".writable_test"
                test_file.write_text("test")
                test_file.unlink()
                writable["history"] = True
            except Exception:
                writable["history"] = False
        else:
            writable["history"] = False

        if artifact_root_str:
            try:
                path = Path(artifact_root_str)
                path.mkdir(parents=True, exist_ok=True)
                test_file = path / ".writable_test"
                test_file.write_text("test")
                test_file.unlink()
                writable["artifacts"] = True
            except Exception:
                writable["artifacts"] = False
        else:
            writable["artifacts"] = False

        if cache_root_str:
            try:
                path = Path(cache_root_str)
                path.mkdir(parents=True, exist_ok=True)
                test_file = path / ".writable_test"
                test_file.write_text("test")
                test_file.unlink()
                writable["cache"] = True
            except Exception:
                writable["cache"] = False
        else:
            writable["cache"] = False

        return {
            "history_path": history_path,
            "artifact_root": artifact_root_str,
            "cache_root": cache_root_str,
            "writable": writable,
        }

    @server.resource(
        "igloo://queries/by-sha/{sql_sha256}.sql",
        name="sql_artifact_by_sha",
        description="Full SQL text for a recorded query execution identified by its SHA-256 hash.",
        mime_type="text/sql; charset=utf-8",
    )
    async def sql_artifact_by_sha(sql_sha256: str) -> str:
        try:
            return read_sql_artifact_by_sha(sql_sha256)
        except FileNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - unlikely I/O error
            raise NotFoundError(
                f"SQL artifact for {sql_sha256} is unreadable: {exc}"
            ) from exc

    if enable_cli_bridge and snow_cli is not None:

        @server.tool(
            name="run_cli_query",
            description="Execute a query via the Snowflake CLI bridge",
        )
        async def run_cli_query_tool(
            statement: Annotated[
                str, Field(description="SQL query to execute using snow CLI")
            ],
            warehouse: Annotated[
                Optional[str], Field(description="Warehouse override", default=None)
            ] = None,
            database: Annotated[
                Optional[str], Field(description="Database override", default=None)
            ] = None,
            schema: Annotated[
                Optional[str], Field(description="Schema override", default=None)
            ] = None,
            role: Annotated[
                Optional[str], Field(description="Role override", default=None)
            ] = None,
        ) -> Dict[str, Any]:
            overrides: Dict[str, Optional[str]] = {
                "warehouse": warehouse,
                "database": database,
                "schema": schema,
                "role": role,
            }
            ctx_overrides: Dict[str, Optional[str]] = {
                k: v for k, v in overrides.items() if v is not None
            }
            try:
                result = await anyio.to_thread.run_sync(
                    partial(
                        snow_cli.run_query,
                        statement,
                        output_format="json",
                        ctx_overrides=ctx_overrides,
                    )
                )
            except SnowCLIError as exc:
                raise RuntimeError(f"Snow CLI query failed: {exc}") from exc

            rows = result.rows or []
            return {
                "statement": statement,
                "rows": rows,
                "stdout": result.raw_stdout,
                "stderr": result.raw_stderr,
            }


def _apply_config_overrides(args: argparse.Namespace) -> Config:
    overrides = {
        key: value
        for key in ("profile", "warehouse", "database", "schema", "role")
        if (value := getattr(args, key, None))
    }

    try:
        cfg = load_config(
            config_path=args.snowcli_config,
            cli_overrides=overrides or None,
        )
    except ConfigError as exc:
        raise SystemExit(f"Failed to load configuration: {exc}") from exc

    if cfg.snowflake.profile:
        os.environ.setdefault("SNOWFLAKE_PROFILE", cfg.snowflake.profile)
        os.environ["SNOWFLAKE_PROFILE"] = cfg.snowflake.profile

    return cfg


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Snowflake MCP server with igloo-mcp extensions",
    )

    login_params = get_login_params()
    for value in login_params.values():
        if len(value) < 2:
            # Malformed entry; ignore to avoid argparse blow-ups
            continue

        help_text = value[-1]
        if len(value) >= 3:
            flags = value[:-2]
            default_value = value[-2]
        else:
            flags = value[:-1]
            default_value = None

        # Guard against implementations that only provide flags + help text
        if default_value == help_text:
            default_value = None

        parser.add_argument(
            *flags,
            required=False,
            default=default_value,
            help=help_text,
        )

    parser.add_argument(
        "--service-config-file",
        required=False,
        help="Path to Snowflake MCP service configuration YAML (optional for advanced users)",
    )
    parser.add_argument(
        "--transport",
        required=False,
        choices=["stdio", "http", "sse", "streamable-http"],
        default=os.environ.get("SNOWCLI_MCP_TRANSPORT", "stdio"),
        help="Transport to use for FastMCP (default: stdio)",
    )
    parser.add_argument(
        "--endpoint",
        required=False,
        default=os.environ.get("SNOWCLI_MCP_ENDPOINT", "/mcp"),
        help="Endpoint path when running HTTP-based transports",
    )
    parser.add_argument(
        "--mount-path",
        required=False,
        default=None,
        help="Optional mount path override for SSE transport",
    )
    parser.add_argument(
        "--snowcli-config",
        required=False,
        help="Optional path to igloo-mcp YAML config (defaults to env)",
    )
    parser.add_argument(
        "--profile",
        required=False,
        help="Override Snowflake CLI profile for igloo-mcp operations",
    )
    parser.add_argument(
        "--enable-cli-bridge",
        action="store_true",
        help="Expose the legacy Snowflake CLI bridge tool (disabled by default)",
    )
    parser.add_argument(
        "--log-level",
        required=False,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=os.environ.get("SNOWCLI_MCP_LOG_LEVEL", "INFO"),
        help="Log level for FastMCP runtime",
    )
    parser.add_argument(
        "--name",
        required=False,
        default="igloo-mcp MCP Server",
        help="Display name for the FastMCP server",
    )
    parser.add_argument(
        "--instructions",
        required=False,
        default="Igloo MCP server combining Snowflake official tools with catalog/lineage helpers.",
        help="Instructions string surfaced to MCP clients",
    )

    args = parser.parse_args(argv)

    # Mirror CLI behaviour for env overrides
    if not getattr(args, "service_config_file", None):
        args.service_config_file = os.environ.get("SERVICE_CONFIG_FILE")

    return args


def create_combined_lifespan(args: argparse.Namespace):
    # Create a temporary config file if none is provided
    if not getattr(args, "service_config_file", None):
        import tempfile

        import yaml  # type: ignore[import-untyped]

        # Create minimal config with just the profile
        config_data = {"snowflake": {"profile": args.profile or "mystenlabs-keypair"}}

        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix=".yml", prefix="igloo_mcp_")
        try:
            with os.fdopen(temp_fd, "w") as f:
                yaml.dump(config_data, f)
            args.service_config_file = temp_path
        except Exception:
            os.close(temp_fd)
            raise

    snowflake_lifespan = create_snowflake_lifespan(args)

    @asynccontextmanager
    async def lifespan(server: FastMCP):
        global _health_monitor, _resource_manager

        # Initialize health monitor at server startup
        _health_monitor = MCPHealthMonitor(server_start_time=anyio.current_time())

        # Initialize resource manager with health monitor
        _resource_manager = MCPResourceManager(health_monitor=_health_monitor)

        # Perform early profile validation
        try:
            config = get_config()
            if config.snowflake.profile:
                profile_health = await anyio.to_thread.run_sync(
                    _health_monitor.get_profile_health,
                    config.snowflake.profile,
                    True,  # force_refresh
                )
                if not profile_health.is_valid:
                    logger.warning(
                        f"Profile validation issue detected: {profile_health.validation_error}"
                    )
                    _health_monitor.record_error(
                        f"Profile validation failed: {profile_health.validation_error}"
                    )
                else:
                    logger.info(
                        f"✓ Profile health check passed for: {profile_health.profile_name}"
                    )
        except Exception as e:
            logger.warning(f"Early profile validation failed: {e}")
            _health_monitor.record_error(f"Early profile validation failed: {e}")

        async with snowflake_lifespan(server) as snowflake_service:
            # Test Snowflake connection during startup
            try:
                connection_health = await anyio.to_thread.run_sync(
                    _health_monitor.check_connection_health, snowflake_service
                )
                if connection_health.value == "healthy":
                    logger.info("✓ Snowflake connection health check passed")
                else:
                    logger.warning(
                        f"Snowflake connection health check failed: {connection_health}"
                    )
            except Exception as e:
                logger.warning(f"Connection health check failed: {e}")
                _health_monitor.record_error(f"Connection health check failed: {e}")

            register_igloo_mcp(
                server,
                snowflake_service,
                enable_cli_bridge=args.enable_cli_bridge,
            )
            yield snowflake_service

    return lifespan


def main(argv: list[str] | None = None) -> None:
    """Main entry point for MCP server.

    Args:
        argv: Optional command line arguments. If None, uses sys.argv[1:].
               When called from CLI, should pass empty list to avoid argument conflicts.
    """
    args = parse_arguments(argv)

    warn_deprecated_params()
    configure_logging(level=args.log_level)
    _apply_config_overrides(args)

    # Validate Snowflake profile configuration before starting server
    try:
        # Use the enhanced validation function
        resolved_profile = validate_and_resolve_profile()

        logger.info(f"✓ Snowflake profile validation successful: {resolved_profile}")

        # Set the validated profile in environment for snowflake-labs-mcp
        os.environ["SNOWFLAKE_PROFILE"] = resolved_profile
        os.environ["SNOWFLAKE_DEFAULT_CONNECTION_NAME"] = resolved_profile

        # Update config with validated profile
        apply_config_overrides(snowflake={"profile": resolved_profile})

        # Log profile summary for debugging
        summary = get_profile_summary()
        logger.debug(f"Profile summary: {summary}")

    except ProfileValidationError as e:
        logger.error("❌ Snowflake profile validation failed")
        logger.error(f"Error: {e}")

        # Provide helpful next steps
        if e.available_profiles:
            logger.error(f"Available profiles: {', '.join(e.available_profiles)}")
            logger.error("To fix this issue:")
            logger.error(
                "1. Set SNOWFLAKE_PROFILE environment variable to one of the available profiles"
            )
            logger.error("2. Or pass --profile <profile_name> when starting the server")
            logger.error("3. Or run 'snow connection add' to create a new profile")
        else:
            logger.error("No Snowflake profiles found.")
            logger.error("Please run 'snow connection add' to create a profile first.")

        if e.config_path:
            logger.error(f"Expected config file at: {e.config_path}")

        # Exit with clear error code
        raise SystemExit(1) from e
    except Exception as e:
        logger.error(f"❌ Unexpected error during profile validation: {e}")
        raise SystemExit(1) from e

    server = FastMCP(
        args.name,
        instructions=args.instructions,
        lifespan=create_combined_lifespan(args),
    )

    try:
        logger.info("Starting FastMCP server using transport=%s", args.transport)
        if args.transport in {"http", "sse", "streamable-http"}:
            endpoint = os.environ.get("SNOWFLAKE_MCP_ENDPOINT", args.endpoint)
            server.run(
                transport=args.transport,
                host="0.0.0.0",
                port=9000,
                path=endpoint,
            )
        else:
            server.run(transport=args.transport)
    except Exception as exc:  # pragma: no cover - run loop issues bubble up
        logger.error("MCP server terminated with error: %s", exc)
        raise


if __name__ == "__main__":
    main()
