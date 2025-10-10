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
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from typing import Any, Dict, Optional

import anyio
from pydantic import Field
from typing_extensions import Annotated

# NOTE: For typing, import from the fastmcp package; fallback handled at runtime.
try:  # Prefer the standalone fastmcp package when available
    from fastmcp import Context, FastMCP
    from fastmcp.utilities.logging import configure_logging, get_logger
except ImportError:  # Fall back to the implementation bundled with python-sdk
    from mcp.server.fastmcp import Context, FastMCP  # type: ignore[import-untyped,assignment]
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
# Lineage functionality removed - not part of igloo-mcp
from .mcp.tools import (
    BuildCatalogTool,
    BuildDependencyGraphTool,
    ConnectionTestTool,
    ExecuteQueryTool,
    GetCatalogSummaryTool,
    HealthCheckTool,
    PreviewTableTool,
    # QueryLineageTool,  # Removed - lineage functionality not part of igloo-mcp
)
from .mcp.utils import get_profile_recommendations, json_compatible
from .mcp_health import (
    MCPHealthMonitor,
)
from .mcp_resources import MCPResourceManager
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
from .snow_cli import SnowCLI, SnowCLIError

_get_profile_recommendations = get_profile_recommendations

logger = get_logger(__name__)

# Global health monitor and resource manager instances
_health_monitor: Optional[MCPHealthMonitor] = None
_resource_manager: Optional[MCPResourceManager] = None
_catalog_service: Optional[CatalogService] = None


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
    execute_query_inst = ExecuteQueryTool(config, snowflake_service, query_service, _health_monitor)
    preview_table_inst = PreviewTableTool(config, snowflake_service, query_service)
    # query_lineage_inst = QueryLineageTool(config)  # Removed - lineage functionality not part of igloo-mcp
    build_catalog_inst = BuildCatalogTool(config, catalog_service)
    build_dependency_graph_inst = BuildDependencyGraphTool(dependency_service)
    test_connection_inst = ConnectionTestTool(config, snowflake_service)
    health_check_inst = HealthCheckTool(config, snowflake_service, _health_monitor)
    get_catalog_summary_inst = GetCatalogSummaryTool(catalog_service)

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
        timeout_seconds: Annotated[
            Optional[int],
            Field(
                description="Query timeout in seconds (default: 120s from config)",
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
        ctx: Context | None = None,
    ) -> Dict[str, Any]:
        """Execute a SQL query against Snowflake - delegates to ExecuteQueryTool."""
        return await execute_query_inst.execute(
            statement=statement,
            warehouse=warehouse,
            database=database,
            schema=schema,
            role=role,
            timeout_seconds=timeout_seconds,
            verbose_errors=verbose_errors,
            ctx=ctx,
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
            account=account,
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
        import yaml
        
        # Create minimal config with just the profile
        config_data = {
            "snowflake": {
                "profile": args.profile or "mystenlabs-keypair"
            }
        }
        
        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.yml', prefix='igloo_mcp_')
        try:
            with os.fdopen(temp_fd, 'w') as f:
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
