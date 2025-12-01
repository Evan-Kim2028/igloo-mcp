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
from typing import Annotated, Any

import anyio
from pydantic import Field, ValidationError

# NOTE: For typing, import from the fastmcp package; fallback handled at runtime.
try:  # Prefer the standalone fastmcp package when available
    from fastmcp import Context, FastMCP
    from fastmcp.exceptions import NotFoundError
    from fastmcp.utilities.logging import configure_logging, get_logger
except ImportError:  # Fall back to the implementation bundled with python-sdk
    from mcp.server.fastmcp import Context, FastMCP  # type: ignore[import-untyped,assignment]
    from mcp.server.fastmcp.exceptions import (  # type: ignore[import-untyped,assignment,attr-defined,no-redef]
        NotFoundError,
    )
    from mcp.server.fastmcp.utilities.logging import (  # type: ignore[import-untyped,assignment]
        configure_logging,
        get_logger,
    )

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
from .constants import MAX_QUERY_TIMEOUT_SECONDS, MIN_QUERY_TIMEOUT_SECONDS
from .context import create_service_context

# Lineage functionality removed - not part of igloo-mcp
from .living_reports.service import ReportService
from .mcp.exceptions import MCPExecutionError, MCPToolError, MCPValidationError
from .mcp.tools import (
    BuildCatalogTool,
    BuildDependencyGraphTool,
    ConnectionTestTool,
    CreateReportTool,
    EvolveReportBatchTool,
    EvolveReportTool,
    ExecuteQueryTool,
    GetCatalogSummaryTool,
    GetReportSchemaTool,
    GetReportTool,
    HealthCheckTool,
    RenderReportTool,
    SearchCatalogTool,
    SearchCitationsTool,
    SearchReportTool,
)
from .mcp.validation_helpers import format_pydantic_validation_error
from .mcp_health import (
    MCPHealthMonitor,
)
from .mcp_resources import MCPResourceManager
from .path_utils import resolve_artifact_root
from .profile_utils import (
    ProfileValidationError,
    get_profile_summary,
    validate_and_resolve_profile,
)
from .service_layer import CatalogService, DependencyService, QueryService
from .session_utils import (
    SessionContext,
    apply_session_context,
    ensure_session_lock,
    restore_session_context,
    snapshot_session,
)

logger = get_logger(__name__)

# Global health monitor and resource manager instances
_health_monitor: MCPHealthMonitor | None = None
_resource_manager: MCPResourceManager | None = None
_catalog_service: CatalogService | None = None

# Non-SQL tools that should not be subject to SQL validation
# These tools operate on file system, metadata, or other non-SQL resources
NON_SQL_TOOLS = {
    "create_report",
    "evolve_report",
    "render_report",
    "search_report",
    "get_report",
    "get_report_schema",
    "build_catalog",
    "build_dependency_graph",
    "get_catalog_summary",
    "search_catalog",
    "test_connection",
    "health_check",
}


def _patch_sql_validation_middleware(server: FastMCP) -> None:
    """Patch upstream SQL validation middleware to only apply to execute_query tool.

    The upstream Snowflake MCP server's initialize_middleware adds CheckQueryType
    middleware that validates ALL tool calls as SQL. This function wraps that middleware
    to only apply SQL validation to the execute_query tool, allowing all other tools
    to bypass SQL validation.

    Args:
        server: FastMCP server instance
    """
    # Try multiple ways to access middleware stack
    middleware_stack = None

    # Method 1: Check _middleware attribute
    if hasattr(server, "_middleware"):
        middleware_stack = server._middleware
        logger.debug("Found middleware stack via _middleware attribute")
    # Method 2: Check middleware attribute (without underscore)
    elif hasattr(server, "middleware"):
        middleware_stack = server.middleware
        logger.debug("Found middleware stack via middleware attribute")
    # Method 3: Check if server has a _app attribute with middleware
    elif hasattr(server, "_app") and hasattr(server._app, "middleware"):
        middleware_stack = server._app.middleware
        logger.debug("Found middleware stack via _app.middleware")
    else:
        # Log all available attributes for debugging
        attrs = [attr for attr in dir(server) if not attr.startswith("__")]
        logger.debug(f"Server attributes: {attrs[:20]}...")  # First 20 to avoid spam
        logger.warning("Could not find middleware stack, SQL validation patch may not work")
        return

    if not middleware_stack:
        logger.debug("Middleware stack is empty or None")
        return

    # Find CheckQueryType middleware and wrap it
    patched = False
    for i, middleware in enumerate(middleware_stack):
        # Check if this is the CheckQueryType middleware by inspecting its type/name
        middleware_type_name = type(middleware).__name__ if hasattr(middleware, "__class__") else str(middleware)
        middleware_str = str(middleware)

        # Check for various SQL validation middleware patterns
        is_sql_validation = (
            "CheckQueryType" in middleware_type_name
            or "QueryType" in middleware_type_name
            or ("sql" in middleware_str.lower() and "validation" in middleware_str.lower())
            or "statement type" in middleware_str.lower()
        )

        if is_sql_validation:
            logger.info(
                f"Found SQL validation middleware: {middleware_type_name}, wrapping to only apply to execute_query"
            )

            # Create a wrapper that only applies to execute_query
            original_middleware = middleware

            async def conditional_sql_validation_middleware(
                *args: Any, _original=original_middleware, **kwargs: Any
            ) -> Any:
                """Middleware wrapper that only applies SQL validation to execute_query."""

                # FastMCP 2.13+ passes (context, call_next); legacy path passes
                # (call_next, name, arguments). Detect signature dynamically.
                message = None
                tool_name = None
                arguments: dict[str, Any] | None = None
                call_next = None

                # Prefer kwargs to avoid duplicate values when both are provided
                if kwargs:
                    call_next = kwargs.get("call_next")
                    tool_name = kwargs.get("name")
                    arguments = kwargs.get("arguments")

                # If first arg looks like a Context, extract the tool name from message
                if not tool_name and args and hasattr(args[0], "message"):
                    context = args[0]
                    message = getattr(context, "message", None)
                    tool_name = getattr(message, "name", None)
                    arguments = getattr(message, "arguments", {}) if message else {}
                    if call_next is None and len(args) >= 2:
                        call_next = args[1]
                elif tool_name is None and len(args) >= 3:
                    # Legacy signature (call_next, name, arguments)
                    call_next, tool_name, arguments = args[0], args[1], args[2]

                # If we still couldn't resolve, fall back to original middleware
                if tool_name is None or call_next is None:
                    return await _original(*args, **kwargs)

                if tool_name == "execute_query":
                    # Let the original middleware handle execute_query
                    try:
                        return await _original(*args, **kwargs)
                    except TypeError:
                        # Legacy signature fallback
                        return await _original(call_next, tool_name, arguments)

                logger.debug(
                    "Skipping SQL validation for non-SQL tool: %s",
                    tool_name or "<unknown>",
                )
                # Call next middleware in chain with the appropriate signature
                if message is not None:
                    # New-style middleware: call_next(context)
                    return await call_next(args[0])
                # Legacy middleware: call_next is the next handler, invoke with (name, arguments)
                # Note: In legacy FastMCP, call_next expects just the tool execution args
                return await call_next(tool_name, arguments)

            # Replace the middleware with our conditional wrapper
            middleware_stack[i] = conditional_sql_validation_middleware  # type: ignore[call-overload]
            logger.info("Patched SQL validation middleware to only apply to execute_query")
            patched = True
            break

    if not patched:
        logger.warning(
            "SQL validation middleware not found in middleware stack. "
            "Non-SQL tools may be incorrectly validated. "
            f"Middleware stack length: {len(middleware_stack) if middleware_stack else 0}"
        )


def read_sql_artifact_by_sha(sql_sha256: str) -> str:
    """Return the SQL text for the given SHA-256 hash."""

    if len(sql_sha256) != 64 or any(ch not in string.hexdigits for ch in sql_sha256):
        raise ValueError("sql_sha256 must be a 64-character hexadecimal digest")

    artifact_root = resolve_artifact_root().resolve()
    artifact_path = (artifact_root / "queries" / "by_sha" / f"{sql_sha256}.sql").resolve()
    if not artifact_path.is_relative_to(artifact_root):
        raise FileNotFoundError(f"SQL artifact for {sql_sha256} not found under {artifact_root}")
    if not artifact_path.exists() or not artifact_path.is_file():
        raise FileNotFoundError(f"SQL artifact for {sql_sha256} not found under {artifact_root}")
    return artifact_path.read_text(encoding="utf-8")


def _get_catalog_summary_sync(catalog_dir: str) -> dict[str, Any]:
    service = _catalog_service
    if service is None:
        context = create_service_context(existing_config=get_config())
        service = CatalogService(context=context)
    return service.load_summary(catalog_dir)


def _execute_query_sync(
    snowflake_service: Any,
    statement: str,
    overrides: dict[str, str | None] | SessionContext,
) -> dict[str, Any]:
    lock = ensure_session_lock(snowflake_service)
    with (
        lock,
        snowflake_service.get_connection(  # type: ignore[attr-defined]
            use_dict_cursor=True,
            session_parameters=snowflake_service.get_query_tag_param(),  # type: ignore[attr-defined]
        ) as (_, cursor),
    ):
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
    server._igloo_mcp_registered = True  # type: ignore[attr-defined]

    config = get_config()
    context = create_service_context(existing_config=config)
    query_service = QueryService(context=context)
    catalog_service = CatalogService(context=context)
    dependency_service = DependencyService(context=context)
    global _health_monitor, _resource_manager, _catalog_service
    _health_monitor = context.health_monitor
    _resource_manager = context.resource_manager
    _catalog_service = catalog_service
    # snow_cli bridge removed - no longer needed

    # Instantiate all extracted tool classes
    execute_query_inst = ExecuteQueryTool(config, snowflake_service, query_service, _health_monitor)
    build_catalog_inst = BuildCatalogTool(config, catalog_service)
    build_dependency_graph_inst = BuildDependencyGraphTool(dependency_service)
    test_connection_inst = ConnectionTestTool(config, snowflake_service)
    health_check_inst = HealthCheckTool(config, snowflake_service, _health_monitor)
    get_catalog_summary_inst = GetCatalogSummaryTool(catalog_service)
    search_catalog_inst = SearchCatalogTool()

    # Initialize living reports system
    report_service = ReportService()
    create_report_inst = CreateReportTool(config, report_service)
    evolve_report_inst = EvolveReportTool(config, report_service)
    evolve_report_batch_inst = EvolveReportBatchTool(config, report_service)
    render_report_inst = RenderReportTool(config, report_service)
    search_report_inst = SearchReportTool(config, report_service)
    get_report_inst = GetReportTool(config, report_service)
    get_report_schema_inst = GetReportSchemaTool(config)
    search_citations_inst = SearchCitationsTool(config, report_service)

    @server.tool(name="execute_query", description="Execute a SQL query against Snowflake")
    async def execute_query_tool(
        statement: Annotated[str, Field(description="SQL statement to execute")],
        reason: Annotated[
            str,
            Field(
                description=(
                    "Short reason for executing this query. Stored in Snowflake QUERY_TAG "
                    "and local history; avoid sensitive info."
                ),
                min_length=5,
            ),
        ],
        warehouse: Annotated[str | None, Field(description="Warehouse override", default=None)] = None,
        database: Annotated[str | None, Field(description="Database override", default=None)] = None,
        schema: Annotated[str | None, Field(description="Schema override", default=None)] = None,
        role: Annotated[str | None, Field(description="Role override", default=None)] = None,
        timeout_seconds: Annotated[
            int | str | None,
            Field(
                description=(
                    "Query timeout in seconds (default: 30s from config). "
                    "Accepts either an integer or a numeric string. "
                    f"Must resolve to a value between {MIN_QUERY_TIMEOUT_SECONDS} and "
                    f"{MAX_QUERY_TIMEOUT_SECONDS}. Maximum timeout is configurable via "
                    "IGLOO_MCP_MAX_QUERY_TIMEOUT_SECONDS environment variable."
                ),
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
            dict[str, Any] | str | None,
            Field(
                description=(
                    "Optional insights or key findings from query results. Metadata-only; no extra compute. "
                    "Can be a summary string or structured JSON with key metrics and business impact."
                ),
                default=None,
            ),
        ] = None,
        result_mode: Annotated[
            str | None,
            Field(
                description=(
                    "Control response verbosity to reduce token usage. Options: "
                    "'full' (default) - return all rows; "
                    "'summary' - return key_metrics + 5 sample rows only; "
                    "'schema_only' - return column names/types only, no rows; "
                    "'sample' - return first 10 rows only."
                ),
                default=None,
            ),
        ] = None,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Execute a SQL query against Snowflake - delegates to ExecuteQueryTool."""
        # Coerce timeout_seconds from string to int if needed
        timeout_int: int | None = None
        if timeout_seconds is not None:
            if isinstance(timeout_seconds, str):
                try:
                    timeout_int = int(timeout_seconds)
                except ValueError:
                    raise MCPValidationError(
                        f"timeout_seconds must be a valid integer, got: {timeout_seconds}"
                    ) from None
            else:
                timeout_int = timeout_seconds

        try:
            return await execute_query_inst.execute(
                statement=statement,
                warehouse=warehouse,
                database=database,
                schema=schema,
                role=role,
                reason=reason,
                timeout_seconds=timeout_int,
                verbose_errors=verbose_errors,
                post_query_insight=post_query_insight,
                result_mode=result_mode,
                ctx=ctx,
            )
        except (MCPValidationError, MCPExecutionError, MCPToolError):
            # Re-raise MCP tool errors as-is - FastMCP will handle formatting
            raise
        except ValidationError as e:
            # Convert Pydantic validation errors to MCPValidationError with enhanced messages
            raise format_pydantic_validation_error(e, tool_name="execute_query") from e
        except Exception:
            # All other exceptions should be handled by the tool's @tool_error_handler decorator
            # This catch-all is a safety net for unexpected errors
            raise

    @server.tool(name="evolve_report", description="Evolve a living report with LLM assistance")
    async def evolve_report_tool(
        report_selector: Annotated[str, Field(description="Report ID or title to evolve")],
        instruction: Annotated[
            str,
            Field(description="Natural language evolution instruction for audit trail"),
        ],
        proposed_changes: Annotated[
            dict[str, Any],
            Field(description="Structured changes generated by LLM based on instruction and current outline"),
        ],
        constraints: Annotated[
            dict[str, Any] | None,
            Field(description="Optional evolution constraints", default=None),
        ] = None,
        dry_run: Annotated[bool, Field(description="Validate without applying changes", default=False)] = False,
        status_change: Annotated[
            str | None,
            Field(
                description="Optional status change for the report",
                default=None,
                pattern="^(active|archived|deleted)$",
            ),
        ] = None,
        response_detail: Annotated[
            str,
            Field(
                description="Response verbosity level for token efficiency",
                default="standard",
                pattern="^(minimal|standard|full)$",
            ),
        ] = "standard",
    ) -> dict[str, Any]:
        """Evolve report - delegates to EvolveReportTool."""
        return await evolve_report_inst.execute(
            report_selector=report_selector,
            instruction=instruction,
            proposed_changes=proposed_changes,
            constraints=constraints,
            dry_run=dry_run,
            status_change=status_change,
            response_detail=response_detail,
        )

    @server.tool(
        name="evolve_report_batch",
        description="Perform multiple report evolution operations atomically",
    )
    async def evolve_report_batch_tool(
        report_selector: Annotated[str, Field(description="Report ID or title to evolve")],
        instruction: Annotated[
            str,
            Field(description="Natural language description of batch operation for audit trail"),
        ],
        operations: Annotated[
            list[dict[str, Any]],
            Field(
                description=(
                    "List of operations to perform atomically. Each operation has a 'type' field "
                    "(add_insight, modify_insight, remove_insight, add_section, modify_section, "
                    "remove_section, update_title, update_metadata, attach_chart) and type-specific fields."
                )
            ),
        ],
        dry_run: Annotated[
            bool,
            Field(description="Validate without applying changes", default=False),
        ] = False,
        response_detail: Annotated[
            str,
            Field(
                description="Response verbosity level",
                default="standard",
                pattern="^(minimal|standard|full)$",
            ),
        ] = "standard",
    ) -> dict[str, Any]:
        """Batch evolve report - delegates to EvolveReportBatchTool."""
        return await evolve_report_batch_inst.execute(
            report_selector=report_selector,
            instruction=instruction,
            operations=operations,
            dry_run=dry_run,
            response_detail=response_detail,
        )

    @server.tool(
        name="render_report",
        description="Render a living report to human-readable formats (HTML, PDF, etc.) using Quarto",
    )
    async def render_report_tool(
        report_selector: Annotated[str, Field(description="Report ID or title to render")],
        format: Annotated[
            str,
            Field(
                description="Output format. Use 'html_standalone' for self-contained HTML without Quarto.",
                default="html",
                pattern="^(html|pdf|markdown|docx|html_standalone)$",
            ),
        ] = "html",
        regenerate_outline_view: Annotated[
            bool,
            Field(description="Whether to regenerate QMD from outline", default=True),
        ] = True,
        include_preview: Annotated[
            bool,
            Field(description="Include truncated preview in response", default=False),
        ] = False,
        preview_max_chars: Annotated[
            int,
            Field(
                description="Maximum characters for preview truncation (default 2000)",
                default=2000,
                ge=100,
                le=10000,
            ),
        ] = 2000,
        dry_run: Annotated[
            bool,
            Field(
                description="If True, only generate QMD file without running Quarto",
                default=False,
            ),
        ] = False,
        options: Annotated[
            dict[str, Any] | None,
            Field(description="Additional Quarto options", default=None),
        ] = None,
    ) -> dict[str, Any]:
        """Render report - delegates to RenderReportTool."""
        return await render_report_inst.execute(
            report_selector=report_selector,
            format=format,
            regenerate_outline_view=regenerate_outline_view,
            include_preview=include_preview,
            preview_max_chars=preview_max_chars,
            dry_run=dry_run,
            options=options,
        )

    @server.tool(
        name="create_report",
        description="Create a new living report with optional template and tags",
    )
    async def create_report_tool(
        title: Annotated[str, Field(description="Human-readable title for the report")],
        template: Annotated[
            str,
            Field(
                description=(
                    "Report template to use. Defaults to 'default' if not specified. "
                    "Available templates: default (empty report), monthly_sales, "
                    "quarterly_review, deep_dive, analyst_v1 (blockchain analysis with "
                    "citation enforcement)."
                ),
                default="default",
                pattern="^(default|monthly_sales|quarterly_review|deep_dive|analyst_v1)$",
            ),
        ] = "default",
        tags: Annotated[
            list[str] | None,
            Field(
                description="Optional tags for categorization and filtering",
                default=None,
            ),
        ] = None,
        description: Annotated[
            str | None,
            Field(
                description="Optional description of the report (stored in metadata)",
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Create report - delegates to CreateReportTool.

        Note: This is a non-SQL tool that operates on file system, not Snowflake.
        It should not be subject to SQL validation from upstream middleware.
        """
        # The middleware patch should prevent SQL validation on non-SQL tools.
        # If SQL validation errors still occur, they indicate a middleware patching issue
        # that should be fixed there, not worked around here with redundant retries.
        return await create_report_inst.execute(
            title=title,
            template=template,
            tags=tags,
            description=description,
        )

    @server.tool(
        name="search_report",
        description="Search for living reports with intelligent fallback behavior",
    )
    async def search_report_tool(
        title: Annotated[
            str | None,
            Field(
                description="Search for reports by title (exact or partial match, case-insensitive)",
                default=None,
            ),
        ] = None,
        tags: Annotated[
            list[str] | None,
            Field(
                description="Filter reports by tags (reports must have all specified tags)",
                default=None,
            ),
        ] = None,
        report_id: Annotated[
            str | None,
            Field(description="Exact report ID to search for", default=None),
        ] = None,
        status: Annotated[
            str | None,
            Field(
                description="Filter by report status",
                default="active",
                pattern="^(active|archived|deleted)$",
            ),
        ] = "active",
        limit: Annotated[
            int,
            Field(
                description="Maximum number of results to return",
                default=20,
                ge=1,
                le=50,
            ),
        ] = 20,
        fields: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Optional list of fields to return (default: all fields). "
                    "Valid fields: report_id, title, created_at, updated_at, "
                    "tags, status, path"
                ),
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Search report - delegates to SearchReportTool."""
        return await search_report_inst.execute(
            title=title,
            tags=tags,
            report_id=report_id,
            status=status,
            limit=limit,
            fields=fields,
        )

    @server.tool(
        name="get_report",
        description="Get the structure and content of a living report with selective retrieval",
    )
    async def get_report_tool(
        report_selector: Annotated[str, Field(description="Report ID or title to retrieve")],
        mode: Annotated[
            str,
            Field(
                description="Retrieval mode for token efficiency",
                default="summary",
                pattern="^(summary|sections|insights|full)$",
            ),
        ] = "summary",
        section_ids: Annotated[
            list[str] | None,
            Field(
                description="Filter to specific section IDs (mode='sections' or mode='insights')",
                default=None,
            ),
        ] = None,
        section_titles: Annotated[
            list[str] | None,
            Field(
                description="Filter to sections matching titles (fuzzy, case-insensitive)",
                default=None,
            ),
        ] = None,
        insight_ids: Annotated[
            list[str] | None,
            Field(
                description="Filter to specific insight IDs (mode='insights')",
                default=None,
            ),
        ] = None,
        min_importance: Annotated[
            int | None,
            Field(
                description="Filter insights with importance >= this value (mode='insights')",
                default=None,
                ge=0,
                le=10,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description="Maximum items to return (default 50, max 100)",
                default=50,
                ge=1,
                le=100,
            ),
        ] = 50,
        offset: Annotated[
            int,
            Field(
                description="Skip first N items (pagination, default 0)",
                default=0,
                ge=0,
            ),
        ] = 0,
        include_content: Annotated[
            bool,
            Field(
                description="Include section prose content (mode='sections' or mode='full')",
                default=False,
            ),
        ] = False,
        include_audit: Annotated[
            bool,
            Field(
                description="Include recent audit events (mode='summary' or mode='full')",
                default=False,
            ),
        ] = False,
    ) -> dict[str, Any]:
        """Get report - delegates to GetReportTool."""
        return await get_report_inst.execute(
            report_selector=report_selector,
            mode=mode,
            section_ids=section_ids,
            section_titles=section_titles,
            insight_ids=insight_ids,
            min_importance=min_importance,
            limit=limit,
            offset=offset,
            include_content=include_content,
            include_audit=include_audit,
        )

    @server.tool(
        name="get_report_schema",
        description="Get JSON schema for Living Reports operations - self-documentinging API",
    )
    async def get_report_schema_tool(
        schema_type: Annotated[
            str,
            Field(
                description="What schema to return",
                default="proposed_changes",
                pattern="^(proposed_changes|insight|section|outline|all)$",
            ),
        ] = "proposed_changes",
        format: Annotated[
            str,
            Field(
                description="Output format for schema",
                default="json_schema",
                pattern="^(json_schema|examples|compact)$",
            ),
        ] = "json_schema",
    ) -> dict[str, Any]:
        """Get report schema - delegates to GetReportSchemaTool."""
        return await get_report_schema_inst.execute(
            schema_type=schema_type,
            format=format,
        )

    @server.tool(
        name="search_citations",
        description="Search citations across all living reports by source type, provider, URL, etc.",
    )
    async def search_citations_tool(
        source_type: Annotated[
            str | None,
            Field(
                description="Filter by source type (query, api, url, observation, document)",
                default=None,
                pattern="^(query|api|url|observation|document)$",
            ),
        ] = None,
        provider: Annotated[
            str | None,
            Field(description="Filter by provider (snowflake, allium, defillama, etc.)", default=None),
        ] = None,
        url_contains: Annotated[
            str | None,
            Field(description="Substring search in URL field (case-insensitive)", default=None),
        ] = None,
        description_contains: Annotated[
            str | None,
            Field(description="Substring search in description field (case-insensitive)", default=None),
        ] = None,
        execution_id: Annotated[
            str | None,
            Field(description="Exact match on execution_id (for query sources)", default=None),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Maximum results to return (default: 50, max: 200)", default=50, ge=1, le=200),
        ] = 50,
        group_by: Annotated[
            str | None,
            Field(
                description="Group results by field (source or provider)", default=None, pattern="^(source|provider)$"
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Search citations across all reports - delegates to SearchCitationsTool."""
        return await search_citations_inst.execute(
            source_type=source_type,
            provider=provider,
            url_contains=url_contains,
            description_contains=description_contains,
            execution_id=execution_id,
            limit=limit,
            group_by=group_by,
        )

    @server.tool(name="build_catalog", description="Build Snowflake catalog metadata")
    async def build_catalog_tool(
        output_dir: Annotated[
            str,
            Field(description="Catalog output directory", default="./data_catalogue"),
        ] = "./data_catalogue",
        database: Annotated[
            str | None,
            Field(description="Specific database to introspect", default=None),
        ] = None,
        account: Annotated[bool, Field(description="Include entire account", default=False)] = False,
        format: Annotated[str, Field(description="Output format (json/jsonl)", default="json")] = "json",
        include_ddl: Annotated[bool, Field(description="Include object DDL", default=True)] = True,
        request_id: Annotated[
            str | None,
            Field(
                description="Optional request correlation ID for tracing",
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Build catalog metadata - delegates to BuildCatalogTool."""
        return await build_catalog_inst.execute(
            output_dir=output_dir,
            database=database,
            account=account,
            format=format,
            include_ddl=include_ddl,
            request_id=request_id,
        )

    @server.tool(name="build_dependency_graph", description="Build object dependency graph")
    async def build_dependency_graph_tool(
        database: Annotated[str | None, Field(description="Specific database", default=None)] = None,
        schema: Annotated[str | None, Field(description="Specific schema", default=None)] = None,
        account: Annotated[bool, Field(description="Include account-level metadata", default=False)] = False,
        format: Annotated[str, Field(description="Output format (json/dot)", default="json")] = "json",
    ) -> dict[str, Any]:
        """Build dependency graph - delegates to BuildDependencyGraphTool."""
        return await build_dependency_graph_inst.execute(
            database=database,
            schema=schema,
            account=account,
            format=format,
        )

    @server.tool(name="test_connection", description="Validate Snowflake connectivity")
    async def test_connection_tool(
        request_id: Annotated[
            str | None,
            Field(
                description="Optional request correlation ID for tracing",
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Test Snowflake connection - delegates to TestConnectionTool."""
        return await test_connection_inst.execute(request_id=request_id)

    @server.tool(name="health_check", description="Get comprehensive health status")
    async def health_check_tool(
        request_id: Annotated[
            str | None,
            Field(
                description="Optional request correlation ID for tracing",
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Get health status - delegates to HealthCheckTool."""
        return await health_check_inst.execute(request_id=request_id)

    @server.tool(name="get_catalog_summary", description="Read catalog summary JSON")
    async def get_catalog_summary_tool(
        catalog_dir: Annotated[
            str,
            Field(description="Catalog directory", default="./data_catalogue"),
        ] = "./data_catalogue",
        request_id: Annotated[
            str | None,
            Field(
                description="Optional request correlation ID for tracing",
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Get catalog summary - delegates to GetCatalogSummaryTool."""
        return await get_catalog_summary_inst.execute(catalog_dir=catalog_dir, request_id=request_id)

    @server.tool(name="search_catalog", description="Search locally built catalog artifacts")
    async def search_catalog_tool(
        catalog_dir: Annotated[
            str,
            Field(
                description="Directory containing catalog artifacts (catalog.json or catalog.jsonl).",
                default="./data_catalogue",
            ),
        ] = "./data_catalogue",
        object_types: Annotated[
            list[str] | None,
            Field(description="Optional list of object types to include", default=None),
        ] = None,
        database: Annotated[
            str | None,
            Field(description="Filter results to a specific database", default=None),
        ] = None,
        schema: Annotated[
            str | None,
            Field(description="Filter results to a specific schema", default=None),
        ] = None,
        name_contains: Annotated[
            str | None,
            Field(
                description="Substring search on object name (case-insensitive)",
                default=None,
            ),
        ] = None,
        column_contains: Annotated[
            str | None,
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
        request_id: Annotated[
            str | None,
            Field(
                description="Optional request correlation ID for tracing",
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        return await search_catalog_inst.execute(
            catalog_dir=catalog_dir,
            object_types=object_types,
            database=database,
            schema=schema,
            name_contains=name_contains,
            column_contains=column_contains,
            limit=limit,
            request_id=request_id,
        )

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
            raise NotFoundError(f"SQL artifact for {sql_sha256} is unreadable: {exc}") from exc


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
                    logger.warning(f"Profile validation issue detected: {profile_health.validation_error}")
                    _health_monitor.record_error(f"Profile validation failed: {profile_health.validation_error}")
                else:
                    logger.info(f"✓ Profile health check passed for: {profile_health.profile_name}")
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
                    logger.warning(f"Snowflake connection health check failed: {connection_health}")
            except Exception as e:
                logger.warning(f"Connection health check failed: {e}")
                _health_monitor.record_error(f"Connection health check failed: {e}")

            # Patch upstream middleware to only apply SQL validation to execute_query
            # The upstream server's initialize_middleware adds CheckQueryType middleware
            # that validates ALL tool calls. We need to ensure it only validates execute_query.
            _patch_sql_validation_middleware(server)

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
            logger.error("1. Set SNOWFLAKE_PROFILE environment variable to one of the available profiles")
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
                host="0.0.0.0",  # noqa: S104 - MCP server needs to bind to all interfaces
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
