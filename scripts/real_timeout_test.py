from __future__ import annotations

import argparse
import os

import anyio

from igloo_mcp.config import apply_config_overrides, get_config
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.mcp_server import create_combined_lifespan, parse_arguments
from igloo_mcp.service_layer.query_service import QueryService


async def run_real_timeout_test(profile: str, statement: str, timeout_seconds: int) -> None:
    # Ensure config uses the requested profile
    apply_config_overrides(snowflake={"profile": profile})
    cfg = get_config()

    # Ensure upstream Snowflake MCP selects the right connection
    os.environ["SNOWFLAKE_PROFILE"] = profile
    os.environ["SNOWFLAKE_DEFAULT_CONNECTION_NAME"] = profile

    # Prepare server + lifespan to obtain a real snowflake_service
    args = parse_arguments(
        [
            "--profile",
            profile,
            "--transport",
            "stdio",
        ]
    )
    lifespan = create_combined_lifespan(args)

    # FastMCP server object is only needed to satisfy the lifespan signature
    try:
        from fastmcp import FastMCP
    except ImportError:
        from mcp.server.fastmcp import FastMCP  # type: ignore

    server = FastMCP("timeout-test", lifespan=lifespan)

    async with lifespan(server) as snowflake_service:
        tool = ExecuteQueryTool(cfg, snowflake_service, QueryService(context=None))
        try:
            res = await tool.execute(
                statement=statement,
                timeout_seconds=timeout_seconds,
                verbose_errors=False,
            )
            print("Success within timeout")
            print("  rowcount:", res.get("rowcount"))
            print("  query_id:", res.get("query_id"))
            print("  duration_ms:", res.get("duration_ms"))
        except RuntimeError as e:
            print("Caught RuntimeError:")
            print(str(e))


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-world timeout test for igloo-mcp execute_query")
    parser.add_argument(
        "--profile",
        default=os.getenv("SNOWFLAKE_PROFILE"),
        help="Snowflake profile name",
    )
    parser.add_argument(
        "--statement",
        default=os.getenv("IGLOO_MCP_LONG_QUERY", "SELECT SYSTEM$WAIT(25)"),
        help="SQL to run that takes ~25s; fallback uses GENERATOR if WAIT is unavailable",
    )
    parser.add_argument("--timeout-seconds", type=float, default=1.0)
    args = parser.parse_args()

    if not args.profile:
        raise SystemExit("Set --profile or SNOWFLAKE_PROFILE to run this test.")

    # If SYSTEM$WAIT isn't available, suggest a heavy GENERATOR query
    stmt = args.statement
    if stmt.strip().upper() == "GENERATOR_FALLBACK":
        stmt = "SELECT COUNT(*) FROM TABLE(GENERATOR(ROWCOUNT => 1000000000))"

    anyio.run(run_real_timeout_test, args.profile, stmt, args.timeout_seconds)


if __name__ == "__main__":
    main()
