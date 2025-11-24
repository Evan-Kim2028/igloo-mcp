"""Tests for parallel Snowflake CLI execution helpers."""

from __future__ import annotations

from typing import Dict, List

import pytest

from igloo_mcp.parallel import (
    ParallelQueryConfig,
    ParallelQueryExecutor,
    QueryResult,
    query_multiple_objects,
)
from igloo_mcp.snow_cli import QueryOutput


class StubCLI:
    def __init__(self, responses: List[QueryOutput | Exception]):
        self._responses = responses
        self.calls: List[str] = []

    def run_query(self, query: str, *args, **kwargs) -> QueryOutput:
        self.calls.append(query)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _patch_snow_cli(monkeypatch: pytest.MonkeyPatch, cli: StubCLI) -> None:
    monkeypatch.setattr("igloo_mcp.parallel.SnowCLI", lambda: cli)


def test_execute_single_query_success(monkeypatch: pytest.MonkeyPatch):
    cli = StubCLI(
        [
            QueryOutput(
                raw_stdout="",
                raw_stderr="",
                returncode=0,
                rows=[{"col1": "1"}, {"col1": "2"}],
                columns=["col1"],
            )
        ]
    )
    _patch_snow_cli(monkeypatch, cli)

    executor = ParallelQueryExecutor(
        ParallelQueryConfig(
            max_concurrent_queries=1, retry_attempts=1, timeout_seconds=60
        )
    )
    result = executor.execute_single_query("SELECT 1", object_name="test")
    assert result.success is True
    assert result.row_count == 2
    assert result.rows[0]["col1"] == "1"


def test_execute_single_query_retries(monkeypatch: pytest.MonkeyPatch):
    cli = StubCLI(
        [
            RuntimeError("first failure"),
            QueryOutput(
                raw_stdout="",
                raw_stderr="",
                returncode=0,
                rows=[],
                columns=[],
            ),
        ]
    )
    _patch_snow_cli(monkeypatch, cli)

    config = ParallelQueryConfig(
        max_concurrent_queries=1,
        retry_attempts=2,
        retry_delay=0,
        timeout_seconds=10,
    )
    executor = ParallelQueryExecutor(config)
    result = executor.execute_single_query("SELECT 1", object_name="retry")
    assert result.success is True
    assert result.row_count == 0
    assert len(cli.calls) == 2


def test_execute_single_query_exhausts_retries(monkeypatch: pytest.MonkeyPatch):
    cli = StubCLI(
        [
            RuntimeError("fail 1"),
            RuntimeError("fail 2"),
        ]
    )
    _patch_snow_cli(monkeypatch, cli)

    config = ParallelQueryConfig(
        max_concurrent_queries=1,
        retry_attempts=2,
        retry_delay=0,
        timeout_seconds=5,
    )
    executor = ParallelQueryExecutor(config)
    result = executor.execute_single_query("SELECT 1", object_name="fail")
    assert result.success is False
    assert "fail 2" in result.error


@pytest.mark.asyncio
async def test_execute_queries_async(monkeypatch: pytest.MonkeyPatch):
    cli = StubCLI(
        [
            QueryOutput("", "", 0, rows=[{"col": "a"}], columns=["col"]),
            QueryOutput("", "", 0, rows=[{"col": "b"}], columns=["col"]),
        ]
    )
    _patch_snow_cli(monkeypatch, cli)

    executor = ParallelQueryExecutor(
        ParallelQueryConfig(
            max_concurrent_queries=2, retry_attempts=1, timeout_seconds=30
        )
    )
    queries: Dict[str, str] = {"q1": "SELECT 'a'", "q2": "SELECT 'b'"}
    results = await executor.execute_queries_async(queries)
    assert results["q1"].success and results["q2"].success
    assert len(cli.calls) == 2


def test_query_multiple_objects(monkeypatch: pytest.MonkeyPatch):
    results = {
        "obj": QueryResult(
            object_name="obj",
            query="SELECT 1",
            success=True,
            rows=[{"col": "1"}],
            execution_time=0.1,
            row_count=1,
        )
    }

    def fake_execute(self, queries):  # noqa: D401
        return results

    monkeypatch.setattr(
        ParallelQueryExecutor,
        "execute_queries",
        fake_execute,
        raising=False,
    )

    summary = query_multiple_objects({"obj": "SELECT 1"}, max_concurrent=1)
    assert summary["obj"].success is True


def test_execute_single_query_parses_json(monkeypatch: pytest.MonkeyPatch):
    cli = StubCLI(
        [
            QueryOutput(
                raw_stdout="",
                raw_stderr="",
                returncode=0,
                rows=[
                    {"object_json": '{"foo": 1}'},
                    {"object_json": 5},
                ],
                columns=["object_json"],
            )
        ]
    )
    _patch_snow_cli(monkeypatch, cli)
    executor = ParallelQueryExecutor(
        ParallelQueryConfig(
            max_concurrent_queries=1, retry_attempts=1, timeout_seconds=30
        )
    )
    result = executor.execute_single_query(
        "SELECT object_json", object_name="json_test"
    )
    assert result.success is True
    assert result.json_data == [{"foo": 1}]


def test_execute_single_query_zero_retries(monkeypatch: pytest.MonkeyPatch):
    executor = ParallelQueryExecutor(
        ParallelQueryConfig(
            max_concurrent_queries=1, retry_attempts=0, timeout_seconds=1
        )
    )
    cli = StubCLI([])
    _patch_snow_cli(monkeypatch, cli)

    with pytest.raises(RuntimeError):
        executor._execute_single_query("SELECT 1", "no_retries", cli)


@pytest.mark.asyncio
async def test_execute_queries_async_handles_future_exception(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_snow_cli(monkeypatch, StubCLI([]))

    async_executor = ParallelQueryExecutor(
        ParallelQueryConfig(
            max_concurrent_queries=1, retry_attempts=1, timeout_seconds=5
        )
    )

    def boom(self, query, object_name, cli):  # noqa: D401
        raise RuntimeError("boom")

    monkeypatch.setattr(
        ParallelQueryExecutor,
        "_execute_single_query",
        boom,
        raising=False,
    )

    results = await async_executor.execute_queries_async({"obj": "SELECT 1"})
    assert results["obj"].success is False
    assert "Unexpected error" in results["obj"].error


class TestConcurrentFailureScenarios:
    """Test concurrent failure scenarios in parallel execution."""

    def test_concurrent_partial_failures(self, monkeypatch: pytest.MonkeyPatch):
        """Test handling when some queries in a batch fail."""
        # Create responses: first 2 succeed, next 2 fail, last 2 succeed
        responses = [
            QueryOutput(
                raw_stdout="",
                raw_stderr="",
                returncode=0,
                rows=[{"col": "success1"}],
                columns=["col"],
            ),
            QueryOutput(
                raw_stdout="",
                raw_stderr="",
                returncode=0,
                rows=[{"col": "success2"}],
                columns=["col"],
            ),
            Exception("Query failed"),  # Failure 1
            Exception("Query timeout"),  # Failure 2
            QueryOutput(
                raw_stdout="",
                raw_stderr="",
                returncode=0,
                rows=[{"col": "success3"}],
                columns=["col"],
            ),
            QueryOutput(
                raw_stdout="",
                raw_stderr="",
                returncode=0,
                rows=[{"col": "success4"}],
                columns=["col"],
            ),
        ]

        cli = StubCLI(responses)
        _patch_snow_cli(monkeypatch, cli)

        config = ParallelQueryConfig(
            max_concurrent_queries=3,
            retry_attempts=0,  # No retries to keep test simple
        )
        executor = ParallelQueryExecutor(config)

        queries = {
            "query1": "SELECT 1",
            "query2": "SELECT 2",
            "query3": "SELECT 3",  # Will fail
            "query4": "SELECT 4",  # Will fail
            "query5": "SELECT 5",
            "query6": "SELECT 6",
        }

        results = executor.execute_queries(queries)

        # Check that successful queries worked
        assert results["query1"].success is True
        assert results["query1"].rows == [{"col": "success1"}]

        assert results["query2"].success is True
        assert results["query2"].rows == [{"col": "success2"}]

        assert results["query5"].success is True
        assert results["query5"].rows == [{"col": "success3"}]

        assert results["query6"].success is True
        assert results["query6"].rows == [{"col": "success4"}]

        # Check that failed queries are marked as failures
        assert results["query3"].success is False
        assert "Query failed" in results["query3"].error

        assert results["query4"].success is False
        assert "Query timeout" in results["query4"].error

    def test_concurrent_timeout_propagation(self, monkeypatch: pytest.MonkeyPatch):
        """Test timeout propagation in concurrent execution."""
        import time

        class SlowThenFastCLI(StubCLI):
            def __init__(self):
                super().__init__([])
                self.call_count = 0

            def run_query(self, query: str, *args, **kwargs) -> QueryOutput:
                self.calls.append(query)
                self.call_count += 1

                # First query is slow, others are fast
                if self.call_count == 1:
                    time.sleep(0.1)  # Slow first query

                return QueryOutput(
                    raw_stdout="",
                    raw_stderr="",
                    returncode=0,
                    rows=[{"result": f"query_{self.call_count}"}],
                    columns=["result"],
                )

        cli = SlowThenFastCLI()
        _patch_snow_cli(monkeypatch, cli)

        config = ParallelQueryConfig(
            max_concurrent_queries=3,
            retry_attempts=0,
        )
        executor = ParallelQueryExecutor(config)

        queries = {f"q{i}": f"SELECT {i}" for i in range(10)}

        start_time = time.time()
        results = executor.execute_queries(queries)
        end_time = time.time()

        # All queries should succeed
        for i in range(10):
            assert results[f"q{i}"].success is True
            assert results[f"q{i}"].rows == [{"result": f"query_{i+1}"}]

        # Should complete in reasonable time (not sequentially)
        # With 3 workers, should be faster than sequential execution
        execution_time = end_time - start_time
        assert execution_time < 1.0, f"Execution took too long: {execution_time}s"

    def test_concurrent_error_aggregation(self, monkeypatch: pytest.MonkeyPatch):
        """Test that errors from multiple concurrent queries are properly aggregated."""
        # Create multiple different types of failures
        responses = [
            Exception("Connection timeout"),
            Exception("Syntax error"),
            Exception("Permission denied"),
            QueryOutput(
                raw_stdout="",
                raw_stderr="",
                returncode=0,
                rows=[{"ok": True}],
                columns=["ok"],
            ),
            Exception("Table not found"),
        ]

        cli = StubCLI(responses)
        _patch_snow_cli(monkeypatch, cli)

        config = ParallelQueryConfig(max_concurrent_queries=5, retry_attempts=0)
        executor = ParallelQueryExecutor(config)

        queries = {
            "timeout_query": "SELECT 1",
            "syntax_query": "SELECT 2",
            "permission_query": "SELECT 3",
            "success_query": "SELECT 4",
            "not_found_query": "SELECT 5",
        }

        results = executor.execute_queries(queries)

        # Check successes
        assert results["success_query"].success is True

        # Check failures have appropriate error messages
        assert results["timeout_query"].success is False
        assert "Connection timeout" in results["timeout_query"].error

        assert results["syntax_query"].success is False
        assert "Syntax error" in results["syntax_query"].error

        assert results["permission_query"].success is False
        assert "Permission denied" in results["permission_query"].error

        assert results["not_found_query"].success is False
        assert "Table not found" in results["not_found_query"].error

    def test_concurrent_retry_logic(self, monkeypatch: pytest.MonkeyPatch):
        """Test retry logic works correctly under concurrent load."""
        call_count = 0

        class FlakyCLI(StubCLI):
            def __init__(self):
                super().__init__([])
                self.call_counts = {}

            def run_query(self, query: str, *args, **kwargs) -> QueryOutput:
                self.calls.append(query)
                query_key = query.split()[-1]  # Get the number from "SELECT {number}"

                if query_key not in self.call_counts:
                    self.call_counts[query_key] = 0
                self.call_counts[query_key] += 1

                # Fail first 2 attempts for each query, succeed on 3rd
                if self.call_counts[query_key] <= 2:
                    raise Exception(
                        f"Attempt {self.call_counts[query_key]} failed for {query_key}"
                    )

                return QueryOutput(
                    raw_stdout="",
                    raw_stderr="",
                    returncode=0,
                    rows=[{"result": f"success_{query_key}"}],
                    columns=["result"],
                )

        cli = FlakyCLI()
        _patch_snow_cli(monkeypatch, cli)

        config = ParallelQueryConfig(
            max_concurrent_queries=3,
            retry_attempts=3,  # Allow retries
        )
        executor = ParallelQueryExecutor(config)

        queries = {f"q{i}": f"SELECT {i}" for i in range(5)}

        results = executor.execute_queries(queries)

        # All queries should eventually succeed
        for i in range(5):
            assert results[f"q{i}"].success is True
            assert results[f"q{i}"].rows == [{"result": f"success_{i}"}]

        # Check that retries were actually attempted
        # Each query should have been called 3 times (2 failures + 1 success)
        assert len(cli.calls) == 15  # 5 queries * 3 attempts each

    @pytest.mark.asyncio
    async def test_async_concurrent_mixed_results(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test async execution with mixed success/failure results."""
        responses = [
            QueryOutput(
                raw_stdout="",
                raw_stderr="",
                returncode=0,
                rows=[{"status": "ok"}],
                columns=["status"],
            ),
            Exception("Async failure 1"),
            QueryOutput(
                raw_stdout="",
                raw_stderr="",
                returncode=0,
                rows=[{"status": "ok"}],
                columns=["status"],
            ),
            Exception("Async failure 2"),
            QueryOutput(
                raw_stdout="",
                raw_stderr="",
                returncode=0,
                rows=[{"status": "ok"}],
                columns=["status"],
            ),
        ]

        cli = StubCLI(responses)
        _patch_snow_cli(monkeypatch, cli)

        config = ParallelQueryConfig(max_concurrent_queries=3, retry_attempts=0)
        async_executor = ParallelQueryExecutor(config)

        queries = {
            "async_success_1": "SELECT 1",
            "async_fail_1": "SELECT 2",
            "async_success_2": "SELECT 3",
            "async_fail_2": "SELECT 4",
            "async_success_3": "SELECT 5",
        }

        results = await async_executor.execute_queries_async(queries)

        # Check mixed results
        assert results["async_success_1"].success is True
        assert results["async_success_1"].rows == [{"status": "ok"}]

        assert results["async_fail_1"].success is False
        assert "Async failure 1" in results["async_fail_1"].error

        assert results["async_success_2"].success is True
        assert results["async_success_3"].success is True

        assert results["async_fail_2"].success is False
        assert "Async failure 2" in results["async_fail_2"].error


class TestTimeoutPropagation:
    """Test timeout propagation in parallel execution."""

    def test_timeout_during_parallel_execution(self, monkeypatch: pytest.MonkeyPatch):
        """Test behavior when queries timeout during parallel execution."""
        import time

        class TimingOutCLI(StubCLI):
            def __init__(self, timeout_query: str):
                super().__init__([])
                self.timeout_query = timeout_query

            def run_query(self, query: str, *args, **kwargs) -> QueryOutput:
                self.calls.append(query)

                if query == self.timeout_query:
                    # Simulate a timeout by sleeping
                    time.sleep(0.5)
                    raise Exception("Query timed out")

                return QueryOutput(
                    raw_stdout="",
                    raw_stderr="",
                    returncode=0,
                    rows=[{"result": "success"}],
                    columns=["result"],
                )

        timeout_query = "SELECT slow_query"
        cli = TimingOutCLI(timeout_query)
        _patch_snow_cli(monkeypatch, cli)

        config = ParallelQueryConfig(max_concurrent_queries=3, retry_attempts=0)
        executor = ParallelQueryExecutor(config)

        queries = {
            "fast1": "SELECT 1",
            "timeout": timeout_query,
            "fast2": "SELECT 2",
        }

        start_time = time.time()
        results = executor.execute_queries(queries)
        end_time = time.time()

        # Fast queries should succeed
        assert results["fast1"].success is True
        assert results["fast2"].success is True

        # Timeout query should fail
        assert results["timeout"].success is False
        assert "Query timed out" in results["timeout"].error

        # Should complete reasonably quickly (parallel execution)
        execution_time = end_time - start_time
        assert execution_time < 1.0, f"Execution took too long: {execution_time}s"

    def test_partial_success_with_timeouts(self, monkeypatch: pytest.MonkeyPatch):
        """Test partial success when some queries timeout."""
        import time

        class SelectiveTimeoutCLI(StubCLI):
            def __init__(self, timeout_indices: List[int]):
                super().__init__([])
                self.timeout_indices = set(timeout_indices)
                self.call_index = 0

            def run_query(self, query: str, *args, **kwargs) -> QueryOutput:
                self.calls.append(query)
                self.call_index += 1

                if self.call_index in self.timeout_indices:
                    time.sleep(0.3)  # Timeout delay
                    raise Exception("Timeout occurred")

                return QueryOutput(
                    raw_stdout="",
                    raw_stderr="",
                    returncode=0,
                    rows=[{"query_id": self.call_index}],
                    columns=["query_id"],
                )

        # Timeout queries 2 and 4 out of 6
        cli = SelectiveTimeoutCLI([2, 4])
        _patch_snow_cli(monkeypatch, cli)

        config = ParallelQueryConfig(max_concurrent_queries=3, retry_attempts=0)
        executor = ParallelQueryExecutor(config)

        queries = {f"q{i}": f"SELECT {i}" for i in range(1, 7)}

        results = executor.execute_queries(queries)

        # Queries 1, 3, 5, 6 should succeed
        success_queries = ["q1", "q3", "q5", "q6"]
        for q in success_queries:
            assert results[q].success is True, f"Query {q} should have succeeded"

        # Queries 2 and 4 should fail with timeout
        timeout_queries = ["q2", "q4"]
        for q in timeout_queries:
            assert results[q].success is False, f"Query {q} should have failed"
            assert "Timeout occurred" in results[q].error

    def test_concurrent_timeout_stress(self, monkeypatch: pytest.MonkeyPatch):
        """Test system behavior under concurrent timeout stress."""
        import concurrent.futures
        import time

        class StressTimeoutCLI(StubCLI):
            def __init__(self):
                super().__init__([])
                self.call_count = 0

            def run_query(self, query: str, *args, **kwargs) -> QueryOutput:
                self.calls.append(query)
                self.call_count += 1

                # Every 3rd query times out
                if self.call_count % 3 == 0:
                    time.sleep(0.1)  # Brief timeout simulation
                    raise Exception("Stress timeout")

                return QueryOutput(
                    raw_stdout="",
                    raw_stderr="",
                    returncode=0,
                    rows=[{"call": self.call_count}],
                    columns=["call"],
                )

        cli = StressTimeoutCLI()
        _patch_snow_cli(monkeypatch, cli)

        config = ParallelQueryConfig(max_concurrent_queries=5, retry_attempts=0)
        executor = ParallelQueryExecutor(config)

        # Run multiple batches concurrently
        def run_batch(batch_id: int):
            queries = {
                f"batch{batch_id}_q{i}": f"SELECT {batch_id}_{i}" for i in range(9)
            }
            return executor.execute_queries(queries)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as thread_executor:
            futures = [thread_executor.submit(run_batch, i) for i in range(3)]
            batch_results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        # Analyze results across all batches
        total_success = 0
        total_timeout = 0

        for batch_result in batch_results:
            for query_result in batch_result.values():
                if query_result.success:
                    total_success += 1
                else:
                    if "Stress timeout" in query_result.error:
                        total_timeout += 1

        # Should have both successes and timeouts
        assert total_success > 0, "Should have successful queries"
        assert total_timeout > 0, "Should have timeout failures"

        # Should be roughly 2/3 success rate (every 3rd query times out)
        expected_success_rate = 2.0 / 3.0
        actual_success_rate = total_success / (total_success + total_timeout)
        assert (
            abs(actual_success_rate - expected_success_rate) < 0.2
        ), f"Success rate {actual_success_rate} too far from expected {expected_success_rate}"
