"""Regression tests for parallel query timeout handling."""

from __future__ import annotations

import threading
import time

import pytest

from igloo_mcp.parallel import ParallelQueryConfig, ParallelQueryExecutor, QueryResult


def _install_slow_executor(executor: ParallelQueryExecutor, release: threading.Event) -> None:
    def slow_execute(self, query: str, object_name: str, cli) -> QueryResult:
        release.wait(0.4)
        return QueryResult(
            object_name=object_name,
            query=query,
            success=True,
            rows=[],
            execution_time=0.4,
        )

    executor._execute_single_query = slow_execute.__get__(executor, ParallelQueryExecutor)  # type: ignore[method-assign]


def test_execute_queries_timeout_returns_without_waiting_for_workers() -> None:
    executor = ParallelQueryExecutor(
        ParallelQueryConfig(max_concurrent_queries=1, timeout_seconds=0.05),
    )
    release = threading.Event()
    _install_slow_executor(executor, release)

    started = time.monotonic()
    results = executor.execute_queries({"slow": "SELECT 1"})
    elapsed = time.monotonic() - started
    release.set()

    assert elapsed < 0.25
    assert results["slow"].success is False
    assert "timed out" in (results["slow"].error or "")


@pytest.mark.asyncio
async def test_execute_queries_async_timeout_returns_without_waiting_for_workers() -> None:
    executor = ParallelQueryExecutor(
        ParallelQueryConfig(max_concurrent_queries=1, timeout_seconds=0.05),
    )
    release = threading.Event()
    _install_slow_executor(executor, release)

    started = time.monotonic()
    results = await executor.execute_queries_async({"slow": "SELECT 1"})
    elapsed = time.monotonic() - started
    release.set()

    assert elapsed < 0.25
    assert results["slow"].success is False
    assert "timed out" in (results["slow"].error or "")
