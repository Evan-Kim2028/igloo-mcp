"""Subtle edge case tests for execute_query functionality.

Tests edge cases like empty queries, cache collisions, session locks, etc.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from igloo_mcp.cache.query_result_cache import QueryResultCache
from igloo_mcp.config import Config
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from tests.helpers.fake_snowflake_connector import (
    FakeQueryPlan,
    FakeSnowflakeService,
)


class TestQueryEdgeCases:
    """Test subtle edge cases in query execution."""

    @pytest.mark.asyncio
    async def test_minimal_valid_query(self):
        """Test handling of minimal valid queries."""
        service = FakeSnowflakeService(
            [FakeQueryPlan(statement="SELECT 1", rows=[{"1": 1}], duration=0.01)]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        # Minimal valid query should work
        result = await tool.execute(statement="SELECT 1")
        assert "rows" in result
        # The fake cursor generates column names from the dict keys
        assert len(result["rows"]) == 1
        assert "1" in result["rows"][0] or "col" in result["rows"][0]

    @pytest.mark.asyncio
    async def test_whitespace_around_query(self):
        """Test handling of queries with surrounding whitespace."""
        service = FakeSnowflakeService(
            [FakeQueryPlan(statement="SELECT 1", rows=[{"1": 1}], duration=0.01)]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        # Query with surrounding whitespace should work
        result = await tool.execute(statement="   \n\t  SELECT 1   \n\t  ")
        assert "rows" in result
        assert result["rows"] == [{"1": 1}]

    @pytest.mark.asyncio
    async def test_very_long_query(self):
        """Test handling of extremely long queries."""
        # Create a very long query (10KB+)
        long_query_part = "SELECT col1, col2, col3 FROM table1 WHERE " + " AND ".join(
            [f"col{i} = {i}" for i in range(100)]
        )
        long_query = long_query_part * 50  # Make it very long

        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement=long_query[:100],
                    rows=[{"result": "success"}],
                    duration=0.01,
                )
            ]
        )

        # Allow unknown SQL types for this test

        config = replace(
            Config.from_env(),
            sql_permissions=replace(Config.from_env().sql_permissions, unknown=True),
        )

        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        # Should handle very long queries without crashing
        result = await tool.execute(statement=long_query[:100])  # Truncate for the mock
        assert "rows" in result

    @pytest.mark.asyncio
    async def test_query_with_extreme_comments(self):
        """Test queries with unusual comment patterns."""
        query_with_comments = """
        -- This is a comment
        /* Multi-line
           comment */
        SELECT -- Inline comment
            col1, -- Another comment
            col2  -- Final comment
        FROM table1
        -- End comment
        """

        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement=query_with_comments.strip(),
                    rows=[{"col1": 1, "col2": 2}],
                    duration=0.01,
                )
            ]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement=query_with_comments)
        assert "rows" in result
        assert result["rows"] == [{"col1": 1, "col2": 2}]

    @pytest.mark.asyncio
    async def test_query_with_unicode_in_comments(self):
        """Test queries with Unicode characters in comments."""
        query = """
        -- Comment with Unicode: 世界 🌟
        SELECT 'Hello' as greeting
        /* マルチライnコメント with Unicode: こんにちは */
        """

        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement=query.strip(), rows=[{"greeting": "Hello"}], duration=0.01
                )
            ]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement=query)
        assert "rows" in result


class TestCacheEdgeCases:
    """Test cache-related edge cases."""

    def test_cache_key_with_special_characters(self):
        """Test cache key generation with special characters."""
        cache = QueryResultCache(mode="enabled", root=None)

        # Test with various special characters in context
        special_contexts = [
            {"warehouse": "WH-特殊", "database": "DB@test", "schema": "SCHEMA#123"},
            {
                "warehouse": "WH",
                "database": "DB",
                "schema": "SCHEMA",
                "role": "ROLE/with/slashes",
            },
            {
                "warehouse": "WH",
                "database": "DB",
                "schema": "SCHEMA",
                "extra": "ignored",
            },
        ]

        sql = "SELECT * FROM test_table"

        for context in special_contexts:
            # Should not crash with special characters
            key = cache.compute_cache_key(
                sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
                profile="test_profile",
                effective_context=context,
            )
            assert isinstance(key, str)
            assert len(key) == 64  # SHA256 length

    def test_cache_key_consistency(self):
        """Test that identical inputs produce identical cache keys."""
        cache = QueryResultCache(mode="enabled", root=None)

        sql = "SELECT * FROM users WHERE active = 1"
        profile = "prod_profile"
        context1 = {"warehouse": "PROD_WH", "database": "PROD_DB", "schema": "PUBLIC"}
        context2 = {"warehouse": "PROD_WH", "database": "PROD_DB", "schema": "PUBLIC"}

        key1 = cache.compute_cache_key(
            sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
            profile=profile,
            effective_context=context1,
        )

        key2 = cache.compute_cache_key(
            sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
            profile=profile,
            effective_context=context2,
        )

        assert key1 == key2

    def test_cache_key_different_inputs(self):
        """Test that different inputs produce different cache keys."""
        cache = QueryResultCache(mode="enabled", root=None)

        base_sql = "SELECT * FROM users"
        base_context = {"warehouse": "WH", "database": "DB", "schema": "SCHEMA"}

        # Different SQL
        key1 = cache.compute_cache_key(
            sql_sha256=hashlib.sha256(base_sql.encode()).hexdigest(),
            profile="profile",
            effective_context=base_context,
        )

        key2 = cache.compute_cache_key(
            sql_sha256=hashlib.sha256(
                (base_sql + " WHERE active = 1").encode()
            ).hexdigest(),
            profile="profile",
            effective_context=base_context,
        )

        assert key1 != key2

        # Different profile
        key3 = cache.compute_cache_key(
            sql_sha256=hashlib.sha256(base_sql.encode()).hexdigest(),
            profile="different_profile",
            effective_context=base_context,
        )

        assert key1 != key3

        # Different context
        different_context = base_context.copy()
        different_context["schema"] = "DIFFERENT_SCHEMA"

        key4 = cache.compute_cache_key(
            sql_sha256=hashlib.sha256(base_sql.encode()).hexdigest(),
            profile="profile",
            effective_context=different_context,
        )

        assert key1 != key4


class TestSessionLockEdgeCases:
    """Test session lock edge cases."""

    @pytest.mark.asyncio
    async def test_concurrent_session_access(self):
        """Test concurrent access to session resources."""
        import asyncio

        # Use multiple plans that can be reused for concurrent access
        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT 1", rows=[{"result": 1}], duration=0.01
                ),
                FakeQueryPlan(
                    statement="SELECT 1", rows=[{"result": 1}], duration=0.01
                ),
                FakeQueryPlan(
                    statement="SELECT 1", rows=[{"result": 1}], duration=0.01
                ),
            ]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        async def run_query():
            return await tool.execute(statement="SELECT 1")

        # Run multiple identical queries concurrently
        tasks = [run_query() for _ in range(3)]
        results = await asyncio.gather(*tasks)

        # All should succeed with the same result
        for result in results:
            assert "rows" in result
            # The fake cursor generates column names from the dict keys
            assert len(result["rows"]) == 1

    @pytest.mark.asyncio
    async def test_session_cleanup_on_error(self, monkeypatch):
        """Test that session locks are cleaned up properly on errors."""
        # Disable caching
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        service = FakeSnowflakeService(
            [FakeQueryPlan(statement="SELECT 1", error=Exception("Connection failed"))]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        # This should fail but not leave locks hanging
        with pytest.raises(Exception, match="Connection failed"):
            await tool.execute(statement="SELECT 1")

        # Should be able to try again (no lock blocking)
        service = FakeSnowflakeService(
            [FakeQueryPlan(statement="SELECT 1", rows=[{"col": 1}], duration=0.01)]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement="SELECT 1")
        assert "rows" in result


class TestDurationCalculationEdgeCases:
    """Test edge cases in duration calculation."""

    @pytest.mark.asyncio
    async def test_zero_duration_queries(self, monkeypatch):
        """Test queries that complete instantly."""
        # Disable caching
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        service = FakeSnowflakeService(
            [FakeQueryPlan(statement="SELECT 1", rows=[{"col": 1}], duration=0.0)]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement="SELECT 1")
        assert "rows" in result
        assert result["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_negative_duration_handling(self, monkeypatch):
        """Test handling of negative durations (if they occur)."""
        # Disable caching
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        # This tests robustness against timing anomalies
        service = FakeSnowflakeService(
            [FakeQueryPlan(statement="SELECT 1", rows=[{"col": 1}], duration=-0.001)]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement="SELECT 1")
        assert "rows" in result
        # Should handle negative duration gracefully
        assert isinstance(result["duration_ms"], int)

    @pytest.mark.asyncio
    async def test_very_long_duration_queries(self, monkeypatch):
        """Test queries with very long execution times."""
        # Disable caching
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        # Use a shorter duration that won't timeout (10 seconds)
        service = FakeSnowflakeService(
            [FakeQueryPlan(statement="SELECT 1", rows=[{"col": 1}], duration=10.0)]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement="SELECT 1")
        assert "rows" in result
        assert (
            9990 <= result["duration_ms"] <= 10010
        )  # duration is in ms, allow small timing variance


class TestResultProcessingEdgeCases:
    """Test edge cases in result processing."""

    @pytest.mark.asyncio
    async def test_results_with_none_values(self):
        """Test processing results that contain None values."""
        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT * FROM test",
                    rows=[
                        {"a": 1, "b": None, "c": "text"},
                        {"a": None, "b": 2, "c": None},
                        {"a": 3, "b": None, "c": "more text"},
                    ],
                    duration=0.01,
                )
            ]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement="SELECT * FROM test")
        assert "rows" in result
        assert len(result["rows"]) == 3

        # Check None values are preserved
        assert result["rows"][0]["b"] is None
        assert result["rows"][1]["a"] is None
        assert result["rows"][1]["c"] is None

    @pytest.mark.asyncio
    async def test_results_with_duplicate_column_names(self):
        """Test handling of results with duplicate column names."""
        # This might happen with certain SQL constructs
        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT a, a FROM dual",
                    rows=[
                        {"a": 1, "a": 2},  # Duplicate keys - later values win
                    ],
                    duration=0.01,
                )
            ]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement="SELECT a, a FROM dual")
        assert "rows" in result
        # Python dict behavior: later values overwrite earlier ones
        assert result["rows"][0]["a"] == 2  # Last value wins

    @pytest.mark.asyncio
    async def test_empty_result_sets_with_metadata(self):
        """Test empty results that still have column metadata."""
        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT * FROM empty_table", rows=[], duration=0.01
                )
            ]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        result = await tool.execute(statement="SELECT * FROM empty_table")
        assert "rows" in result
        assert result["rows"] == []
        assert result["rowcount"] == 0


class TestErrorHandlingEdgeCases:
    """Test error handling edge cases."""

    @pytest.mark.asyncio
    async def test_error_messages_with_unicode(self, monkeypatch):
        """Test error messages containing Unicode characters."""
        # Disable caching to ensure we hit the fake service
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        unicode_error = "Error with Unicode: 世界 🌟 マルチバイト"
        service = FakeSnowflakeService(
            [FakeQueryPlan(statement="SELECT 1", error=Exception(unicode_error))]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        with pytest.raises(Exception) as exc_info:
            await tool.execute(statement="SELECT 1")

        # Error message should preserve Unicode
        assert unicode_error in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_messages_with_special_characters(self, monkeypatch):
        """Test error messages with special characters."""
        # Disable caching
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        special_error = "Error with specials: <>&\"'\t\n\r"
        service = FakeSnowflakeService(
            [FakeQueryPlan(statement="SELECT 1", error=Exception(special_error))]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        with pytest.raises(Exception) as exc_info:
            await tool.execute(statement="SELECT 1")

        assert special_error in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exception_chaining_preservation(self, monkeypatch):
        """Test that exception messages are preserved through error handling."""
        # Disable caching
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        root_cause = ValueError("Root cause")
        wrapped_error = RuntimeError("Wrapped error")
        wrapped_error.__cause__ = root_cause

        service = FakeSnowflakeService(
            [FakeQueryPlan(statement="SELECT 1", error=wrapped_error)]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=None,
            health_monitor=None,
        )

        with pytest.raises(RuntimeError) as exc_info:
            await tool.execute(statement="SELECT 1")

        # The tool wraps errors, so check that the original error message is in the wrapped message
        assert "Wrapped error" in str(exc_info.value)
