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
from typing import Any, Dict, List, Optional

from .config import get_config
from .snow_cli import SnowCLI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress verbose Snowflake connector logging
logging.getLogger("snowflake.connector").setLevel(logging.WARNING)
logging.getLogger("snowflake.connector.connection").setLevel(logging.WARNING)


@dataclass
class QueryResult:
    """Result container for individual query execution."""

    object_name: str
    query: str
    success: bool
    # Raw row dicts parsed from Snow CLI output (CSV/JSON)
    rows: Optional[List[Dict[str, Any]]] = None
    json_data: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    row_count: int = 0


@dataclass
class ParallelQueryConfig:
    """Configuration for parallel query execution."""

    max_concurrent_queries: int = 5
    connection_pool_size: int = 10
    retry_attempts: int = 3
    retry_delay: float = 1.0
    timeout_seconds: int = 300

    @classmethod
    def from_global_config(cls) -> "ParallelQueryConfig":
        """Create config from global configuration."""
        config = get_config()
        return cls(
            max_concurrent_queries=config.max_concurrent_queries,
            connection_pool_size=config.connection_pool_size,
            retry_attempts=config.retry_attempts,
            retry_delay=config.retry_delay,
            timeout_seconds=config.timeout_seconds,
        )


class SnowflakeConnectionPool:
    """Deprecated placeholder left for compatibility (no-op).

    With Snowflake CLI, we don't manage connections directly. This class is
    retained to minimize diff in the executor internals.
    """

    def __init__(self, config: Dict[str, Any], pool_size: int = 10):
        self.config = config
        self.pool_size = pool_size
        logger.info("Using Snowflake CLI; connection pool is a no-op.")

    def get_connection(self):  # pragma: no cover - compatibility shim
        return None

    def return_connection(self, conn):  # pragma: no cover - compatibility shim
        return None

    def close_all(self):  # pragma: no cover - compatibility shim
        return None


class ParallelQueryExecutor:
    """
    Execute multiple Snowflake queries in parallel.

    Optimized for JSON object retrieval with:
    - Connection pooling for efficient resource usage
    - Configurable concurrency limits
    - Progress tracking and error handling
    - Result aggregation and formatting
    """

    def __init__(self, config: Optional[ParallelQueryConfig] = None):
        self.config = config or ParallelQueryConfig.from_global_config()
        self.connection_pool: Optional[SnowflakeConnectionPool] = None

    def _create_context_overrides(self) -> Dict[str, Any]:
        cfg = get_config().snowflake
        return {
            "warehouse": cfg.warehouse,
            "database": cfg.database,
            "schema": cfg.schema,
            "role": cfg.role,
        }

    def _execute_single_query(
        self,
        query: str,
        object_name: str,
        cli: SnowCLI,
    ) -> QueryResult:
        """Execute a single query via Snowflake CLI and return results."""
        start_time = time.time()

        for attempt in range(self.config.retry_attempts):
            try:
                # Execute via Snow CLI; default to CSV for easy parsing
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

                result = QueryResult(
                    object_name=object_name,
                    query=query,
                    success=True,
                    rows=rows,
                    json_data=json_data,
                    execution_time=execution_time,
                    row_count=len(rows),
                )

                logger.info(
                    f"✅ {object_name}: {len(rows)} rows in {execution_time:.2f}s",
                )
                return result

            except Exception as e:
                execution_time = time.time() - start_time
                error_msg = f"Attempt {attempt + 1}: {e!s}"

                if attempt < self.config.retry_attempts - 1:
                    logger.warning(
                        f"⚠️  {object_name} failed ({error_msg}), retrying in {self.config.retry_delay}s...",
                    )
                    time.sleep(self.config.retry_delay)
                else:
                    logger.exception(
                        f"❌ {object_name} failed after {self.config.retry_attempts} attempts: {error_msg}",
                    )
                    return QueryResult(
                        object_name=object_name,
                        query=query,
                        success=False,
                        error=error_msg,
                        execution_time=execution_time,
                    )

            finally:
                pass

        # This should never be reached, but mypy requires it
        raise RuntimeError(
            f"Query execution failed for {object_name} after all retries"
        )

    async def execute_queries_async(
        self,
        queries: Dict[str, str],
    ) -> Dict[str, QueryResult]:
        """
        Execute multiple queries in parallel using asyncio.

        Args:
            queries: Dict mapping object names to SQL queries

        Returns:
            Dict mapping object names to QueryResult objects
        """
        cli = SnowCLI()
        logger.info("🔗 Using Snowflake CLI for parallel execution...")

        try:
            # Execute queries in parallel using ThreadPoolExecutor
            results: Dict[str, QueryResult] = {}
            logger.info(f"⚡ Executing {len(queries)} queries in parallel...")

            with ThreadPoolExecutor(
                max_workers=self.config.max_concurrent_queries,
            ) as executor:
                # Submit all queries
                future_to_object = {
                    executor.submit(
                        self._execute_single_query,
                        query,
                        object_name,
                        cli,
                    ): object_name
                    for object_name, query in queries.items()
                }

                # Process completed queries
                for future in as_completed(
                    future_to_object,
                    timeout=self.config.timeout_seconds,
                ):
                    object_name = future_to_object[future]
                    try:
                        result = future.result()
                        results[object_name] = result
                    except Exception as e:
                        logger.exception(f"Unexpected error for {object_name}: {e}")
                        results[object_name] = QueryResult(
                            object_name=object_name,
                            query=queries[object_name],
                            success=False,
                            error=f"Unexpected error: {e!s}",
                        )

            return results

        finally:
            pass

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
        queries: Dict[str, str],
    ) -> Dict[str, QueryResult]:
        """
        Synchronous wrapper for execute_queries_async.

        Args:
            queries: Dict mapping object names to SQL queries

        Returns:
            Dict mapping object names to QueryResult objects
        """
        return asyncio.run(self.execute_queries_async(queries))

    def get_execution_summary(self, results: Dict[str, QueryResult]) -> Dict[str, Any]:
        """Generate a summary of query execution results."""
        total_queries = len(results)
        successful_queries = sum(1 for r in results.values() if r.success)
        failed_queries = total_queries - successful_queries

        total_rows = sum(r.row_count for r in results.values() if r.success)
        total_execution_time = sum(r.execution_time for r in results.values())
        avg_execution_time = (
            total_execution_time / total_queries if total_queries > 0 else 0
        )

        # Calculate parallelization efficiency
        sequential_time = sum(r.execution_time for r in results.values())
        parallel_efficiency = (
            sequential_time / total_execution_time if total_execution_time > 0 else 1.0
        )

        return {
            "total_queries": total_queries,
            "successful_queries": successful_queries,
            "failed_queries": failed_queries,
            "success_rate": (
                successful_queries / total_queries * 100 if total_queries > 0 else 0
            ),
            "total_rows_retrieved": total_rows,
            "total_execution_time": total_execution_time,
            "avg_execution_time_per_query": avg_execution_time,
            "parallel_efficiency": parallel_efficiency,
            "failed_objects": [
                name for name, result in results.items() if not result.success
            ],
        }


# Convenience functions for common use cases


def query_multiple_objects(
    object_queries: Dict[str, str],
    max_concurrent: Optional[int] = None,
    timeout_seconds: Optional[int] = None,
) -> Dict[str, QueryResult]:
    """
    Convenience function to query multiple objects in parallel.

    Args:
        object_queries: Dict mapping object names to SQL queries
        max_concurrent: Maximum number of concurrent queries (optional)
        timeout_seconds: Timeout in seconds for individual queries (optional)

    Returns:
        Dict mapping object names to QueryResult objects
    """
    config = ParallelQueryConfig.from_global_config()

    # Override defaults if provided
    if max_concurrent is not None:
        config.max_concurrent_queries = max_concurrent
    if timeout_seconds is not None:
        config.timeout_seconds = timeout_seconds

    executor = ParallelQueryExecutor(config)

    results = executor.execute_queries(object_queries)

    # Print summary
    summary = executor.get_execution_summary(results)
    print("\n📊 Query Summary:")
    print(
        f"   ✅ Successful: {summary['successful_queries']}/{summary['total_queries']}",
    )
    print(f"   📈 Success Rate: {summary['success_rate']:.1f}%")
    print(f"   📋 Total Rows: {summary['total_rows_retrieved']:,}")
    print(f"   ⏱️  Total Time: {summary['total_execution_time']:.2f}s")
    print(f"   🚀 Parallel Efficiency: {summary['parallel_efficiency']:.2f}x")

    if summary["failed_objects"]:
        print(f"   ❌ Failed Objects: {', '.join(summary['failed_objects'])}")

    return results


def create_object_queries(
    object_names: List[str],
    base_query_template: str = "SELECT * FROM object_parquet2 WHERE type = '{object}' LIMIT 100",
) -> Dict[str, str]:
    """
    Create queries for multiple objects using a template.

    Args:
        object_names: List of object names to query
        base_query_template: SQL template with {object} placeholder

    Returns:
        Dict mapping object names to SQL queries
    """
    return {obj: base_query_template.format(object=obj) for obj in object_names}


# Example usage and testing
if __name__ == "__main__":
    # Example: Query multiple object types in parallel
    objects_to_query = [
        "0x1::coin::CoinInfo",
        "0x1::account::Account",
        "0x1::table::Table",
        "0x2::sui::SUI",
        "0x3::staking_pool::StakingPool",
    ]

    # Create queries using template
    queries = create_object_queries(objects_to_query)

    # Execute queries in parallel
    print("🚀 Starting parallel query execution...")
    results = query_multiple_objects(queries, max_concurrent=3)

    # Process results
    for obj_name, result in results.items():
        if result.success:
            print(f"\n✅ {obj_name}:")
            print(f"   Rows: {result.row_count}")
            print(
                f"   JSON objects: {len(result.json_data) if result.json_data else 0}",
            )
        else:
            print(f"\n❌ {obj_name}: {result.error}")
