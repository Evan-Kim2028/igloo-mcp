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
