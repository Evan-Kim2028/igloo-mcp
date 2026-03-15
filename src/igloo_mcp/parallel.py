"""Parallel Query Executor using Snowflake CLI.

Executes multiple queries in parallel by invoking the `snow` CLI.
Provides progress tracking, error handling, and result aggregation.
"""

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from .config import get_config
from .snow_cli import SnowCLI, SnowCLIError

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result container for individual query execution."""

    object_name: str
    query: str
    success: bool
    # Raw row dicts parsed from Snow CLI output (CSV/JSON)
    rows: list[dict[str, Any]] | None = None
    json_data: list[dict[str, Any]] | None = None
    error: str | None = None
    execution_time: float = 0.0
    row_count: int = 0


@dataclass(init=False)
class ParallelQueryConfig:
    """Configuration for parallel query execution."""

    max_concurrent_queries: int
    retry_attempts: int
    retry_delay: float
    timeout_seconds: int

    def __init__(
        self,
        max_concurrent_queries: int = 5,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
        timeout_seconds: int = 300,
        max_workers: int | None = None,
        retry_count: int | None = None,
    ):
        """Initialize ParallelQueryConfig.

        Args:
            max_concurrent_queries: Maximum number of concurrent queries
            retry_attempts: Number of retry attempts
            retry_delay: Delay between retries
            timeout_seconds: Timeout for individual queries
            max_workers: Alias for max_concurrent_queries
            retry_count: Alias for retry_attempts
        """
        # Use aliases if provided, otherwise use direct parameters
        self.max_concurrent_queries = max_workers if max_workers is not None else max_concurrent_queries
        self.retry_attempts = retry_count if retry_count is not None else retry_attempts
        self.retry_delay = retry_delay
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_global_config(cls) -> "ParallelQueryConfig":
        """Create config from global configuration."""
        config = get_config()
        return cls(
            max_concurrent_queries=config.max_concurrent_queries,
            retry_attempts=config.retry_attempts,
            retry_delay=config.retry_delay,
            timeout_seconds=config.timeout_seconds,
        )


class ParallelQueryExecutor:
    """Execute multiple Snowflake queries in parallel.

    Uses ThreadPoolExecutor with configurable concurrency, progress tracking,
    and result aggregation.
    """

    def __init__(self, config: ParallelQueryConfig | None = None):
        self.config = config or ParallelQueryConfig.from_global_config()
        self._last_wall_time: float = 0.0

    def _execute_single_query(
        self,
        query: str,
        object_name: str,
        cli: SnowCLI,
    ) -> QueryResult:
        """Execute a single query via Snowflake CLI with retries."""
        start_time = time.time()

        for attempt in range(self.config.retry_attempts + 1):
            try:
                out = cli.run_query(
                    query,
                    output_format="csv",
                    timeout=self.config.timeout_seconds,
                )

                rows = out.rows or []

                # Extract JSON data if available in a column called object_json
                json_data = None
                if rows and any("object_json" in r for r in rows):
                    json_data = []
                    for r in rows:
                        try:
                            js = r.get("object_json")
                            if js:
                                json_data.append(json.loads(js))
                        except (json.JSONDecodeError, TypeError):
                            continue

                execution_time = time.time() - start_time

                logger.info(
                    "%s: %d rows in %.2fs",
                    object_name,
                    len(rows),
                    execution_time,
                )
                return QueryResult(
                    object_name=object_name,
                    query=query,
                    success=True,
                    rows=rows,
                    json_data=json_data,
                    execution_time=execution_time,
                    row_count=len(rows),
                )

            except (SnowCLIError, OSError, TimeoutError) as e:
                execution_time = time.time() - start_time
                error_msg = f"Attempt {attempt + 1}: {e!s}"

                if attempt < self.config.retry_attempts:
                    logger.warning(
                        "%s failed (%s), retrying in %.1fs...",
                        object_name,
                        error_msg,
                        self.config.retry_delay,
                    )
                    time.sleep(self.config.retry_delay)
                else:
                    logger.error(
                        "%s failed after %d attempts: %s",
                        object_name,
                        attempt + 1,
                        error_msg,
                    )
                    return QueryResult(
                        object_name=object_name,
                        query=query,
                        success=False,
                        error=error_msg,
                        execution_time=execution_time,
                    )

        # Unreachable: loop always returns on success or final failure.
        # Satisfy type checker / defensive guard.
        return QueryResult(  # pragma: no cover
            object_name=object_name,
            query=query,
            success=False,
            error="Exhausted retries without producing a result.",
            execution_time=time.time() - start_time,
        )

    async def execute_queries_async(
        self,
        queries: dict[str, str],
    ) -> dict[str, QueryResult]:
        """Execute multiple queries in parallel using a thread pool.

        Args:
            queries: Dict mapping object names to SQL queries

        Returns:
            Dict mapping object names to QueryResult objects
        """
        cli = SnowCLI()
        logger.info("Executing %d queries in parallel...", len(queries))

        results: dict[str, QueryResult] = {}
        wall_start = time.monotonic()

        with ThreadPoolExecutor(
            max_workers=self.config.max_concurrent_queries,
        ) as executor:
            future_to_object = {
                executor.submit(
                    self._execute_single_query,
                    query,
                    object_name,
                    cli,
                ): object_name
                for object_name, query in queries.items()
            }

            try:
                for future in as_completed(
                    future_to_object,
                    timeout=self.config.timeout_seconds,
                ):
                    object_name = future_to_object[future]
                    try:
                        results[object_name] = future.result()
                    except Exception:
                        logger.exception("Unexpected error for %s", object_name)
                        results[object_name] = QueryResult(
                            object_name=object_name,
                            query=queries[object_name],
                            success=False,
                            error="Unexpected error during parallel execution",
                        )
            except TimeoutError:
                # Some futures didn't complete in time — record them as timed out
                for future, object_name in future_to_object.items():
                    if object_name not in results:
                        future.cancel()
                        results[object_name] = QueryResult(
                            object_name=object_name,
                            query=queries[object_name],
                            success=False,
                            error=f"Query timed out after {self.config.timeout_seconds}s",
                        )

        self._last_wall_time = time.monotonic() - wall_start
        return results

    def execute_single_query(
        self,
        query: str,
        object_name: str = "query",
    ) -> QueryResult:
        """Execute a single query.

        Args:
            query: SQL query string
            object_name: Name identifier for the query

        Returns:
            QueryResult with execution details
        """
        cli = SnowCLI()
        return self._execute_single_query(query, object_name, cli)

    def execute_queries(
        self,
        queries: dict[str, str],
    ) -> dict[str, QueryResult]:
        """Synchronous wrapper for execute_queries_async.

        Safe to call from non-async code. If an event loop is already running
        (e.g. inside an MCP handler), uses run_in_executor pattern instead.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            # Already inside an async context — run synchronously via the thread pool
            # directly instead of nesting asyncio.run() which would raise RuntimeError.
            return self._execute_queries_sync(queries)

        return asyncio.run(self.execute_queries_async(queries))

    def _execute_queries_sync(self, queries: dict[str, str]) -> dict[str, QueryResult]:
        """Pure synchronous parallel execution (no asyncio)."""
        cli = SnowCLI()
        results: dict[str, QueryResult] = {}
        wall_start = time.monotonic()

        with ThreadPoolExecutor(
            max_workers=self.config.max_concurrent_queries,
        ) as executor:
            future_to_object = {
                executor.submit(
                    self._execute_single_query,
                    query,
                    object_name,
                    cli,
                ): object_name
                for object_name, query in queries.items()
            }

            try:
                for future in as_completed(
                    future_to_object,
                    timeout=self.config.timeout_seconds,
                ):
                    object_name = future_to_object[future]
                    try:
                        results[object_name] = future.result()
                    except Exception:
                        logger.exception("Unexpected error for %s", object_name)
                        results[object_name] = QueryResult(
                            object_name=object_name,
                            query=queries[object_name],
                            success=False,
                            error="Unexpected error during parallel execution",
                        )
            except TimeoutError:
                for future, object_name in future_to_object.items():
                    if object_name not in results:
                        future.cancel()
                        results[object_name] = QueryResult(
                            object_name=object_name,
                            query=queries[object_name],
                            success=False,
                            error=f"Query timed out after {self.config.timeout_seconds}s",
                        )

        self._last_wall_time = time.monotonic() - wall_start
        return results

    def get_execution_summary(self, results: dict[str, QueryResult]) -> dict[str, Any]:
        """Generate a summary of query execution results."""
        total_queries = len(results)
        successful_queries = sum(1 for r in results.values() if r.success)
        failed_queries = total_queries - successful_queries

        total_rows = sum(r.row_count for r in results.values() if r.success)
        sequential_time = sum(r.execution_time for r in results.values())
        avg_execution_time = sequential_time / total_queries if total_queries > 0 else 0

        # Wall time is the actual elapsed time; sequential_time / wall_time = speedup factor
        wall_time = self._last_wall_time or sequential_time
        parallel_efficiency = sequential_time / wall_time if wall_time > 0 else 1.0

        return {
            "total_queries": total_queries,
            "successful_queries": successful_queries,
            "failed_queries": failed_queries,
            "success_rate": (successful_queries / total_queries * 100 if total_queries > 0 else 0),
            "total_rows_retrieved": total_rows,
            "total_execution_time": sequential_time,
            "wall_time": round(wall_time, 3),
            "avg_execution_time_per_query": avg_execution_time,
            "parallel_efficiency": round(parallel_efficiency, 2),
            "failed_objects": [name for name, result in results.items() if not result.success],
        }


# Convenience functions for common use cases


def query_multiple_objects(
    object_queries: dict[str, str],
    max_concurrent: int | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, QueryResult]:
    """Convenience function to query multiple objects in parallel.

    Args:
        object_queries: Dict mapping object names to SQL queries
        max_concurrent: Maximum number of concurrent queries (optional)
        timeout_seconds: Timeout in seconds for individual queries (optional)

    Returns:
        Dict mapping object names to QueryResult objects
    """
    config = ParallelQueryConfig.from_global_config()

    if max_concurrent is not None:
        config.max_concurrent_queries = max_concurrent
    if timeout_seconds is not None:
        config.timeout_seconds = timeout_seconds

    executor = ParallelQueryExecutor(config)
    results = executor.execute_queries(object_queries)

    summary = executor.get_execution_summary(results)
    logger.info(
        "Query summary: %d/%d succeeded (%.1f%%), %d rows, %.2fs wall, %.2fx speedup",
        summary["successful_queries"],
        summary["total_queries"],
        summary["success_rate"],
        summary["total_rows_retrieved"],
        summary["wall_time"],
        summary["parallel_efficiency"],
    )
    if summary["failed_objects"]:
        logger.warning("Failed objects: %s", ", ".join(summary["failed_objects"]))

    return results


def create_object_queries(
    object_names: list[str],
    base_query_template: str = "SELECT * FROM object_parquet2 WHERE type = '{object}' LIMIT 100",
) -> dict[str, str]:
    """Create queries for multiple objects using a template.

    Args:
        object_names: List of object names to query
        base_query_template: SQL template with {object} placeholder.
            Values are single-quote escaped to prevent SQL injection.

    Returns:
        Dict mapping object names to SQL queries

    Warning:
        Both ``object_names`` and ``base_query_template`` must come from
        trusted sources.  The template is interpolated via ``str.format()``
        and is not safe against arbitrary user input.
    """
    return {obj: base_query_template.format(object=obj.replace("'", "''")) for obj in object_names}


# Example usage and testing
if __name__ == "__main__":
    objects_to_query = [
        "0x1::coin::CoinInfo",
        "0x1::account::Account",
        "0x1::table::Table",
        "0x2::sui::SUI",
        "0x3::staking_pool::StakingPool",
    ]

    queries = create_object_queries(objects_to_query)

    print("Starting parallel query execution...")
    results = query_multiple_objects(queries, max_concurrent=3)

    for obj_name, result in results.items():
        if result.success:
            print(f"\n{obj_name}:")
            print(f"   Rows: {result.row_count}")
            print(
                f"   JSON objects: {len(result.json_data) if result.json_data else 0}",
            )
        else:
            print(f"\n{obj_name}: {result.error}")
