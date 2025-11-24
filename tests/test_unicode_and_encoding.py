"""Tests for Unicode and encoding handling across the system.

Tests SQL with Unicode, query results with international characters,
column names with special characters, cache keys with Unicode, and file I/O.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from igloo_mcp.cache.query_result_cache import QueryResultCache
from igloo_mcp.config import Config
from igloo_mcp.logging.query_history import QueryHistory
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.sql_validation import validate_sql_statement
from tests.helpers.fake_snowflake_connector import (
    FakeQueryPlan,
    FakeSnowflakeService,
)


class TestUnicodeInSQL:
    """Test Unicode characters in SQL statements."""

    def test_unicode_in_select_statements(self):
        """Test that Unicode characters in SELECT statements are accepted."""
        # Test various Unicode scripts
        unicode_queries = [
            "SELECT 'Hello 世界' as greeting",  # Chinese
            "SELECT 'مرحبا بالعالم' as arabic",  # Arabic
            "SELECT 'Здравствуй мир' as russian",  # Cyrillic
            "SELECT 'こんにちは世界' as japanese",  # Japanese
            "SELECT '🌟⭐✨' as emoji",  # Emoji
            "SELECT 'café' as french",  # Latin with diacritics
            "SELECT 'naïve' as accented",  # More accents
        ]

        for query in unicode_queries:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, ["select"], []
            )
            assert is_valid, f"Unicode query failed: {query}"
            assert stmt_type == "Select"
            assert error_msg is None

    def test_unicode_in_column_aliases(self):
        """Test Unicode in column aliases (quoted strings)."""
        unicode_aliases = [
            "SELECT col as '世界' FROM table1",  # Chinese column alias
            "SELECT col as '🌟star🌟' FROM table1",  # Emoji column alias
            "SELECT 'مرحبا' as greeting FROM table1",  # Arabic in string literal
        ]

        for query in unicode_aliases:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, ["select"], []
            )
            assert is_valid, f"Unicode alias query failed: {query}"

    def test_unicode_in_table_names_simple(self):
        """Test Unicode in simple table contexts."""
        # Test Unicode in contexts where it's more likely to be accepted
        unicode_contexts = [
            "SELECT * FROM my_table WHERE name = '表1'",  # Chinese in string
            "SELECT * FROM my_table WHERE description = 'таблица'",  # Cyrillic in string
        ]

        for query in unicode_contexts:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, ["select"], []
            )
            assert is_valid, f"Unicode context query failed: {query}"

    def test_unicode_in_comments(self):
        """Test Unicode in SQL comments."""
        query = """
        -- This is a comment with Unicode: 世界 🌟
        SELECT 'Hello 世界' -- More Unicode: مرحبا
        """
        stmt_type, is_valid, error_msg = validate_sql_statement(query, ["select"], [])
        assert is_valid, "Unicode in comments failed"

    def test_unicode_in_multiline_queries(self):
        """Test Unicode in multiline queries."""
        multiline_query = """
        SELECT
            'Hello 世界 🌟' as greeting,
            'مرحبا بالعالم ⭐' as arabic
        FROM my_table
        WHERE status = 'active'
        """
        stmt_type, is_valid, error_msg = validate_sql_statement(
            multiline_query, ["select"], []
        )
        assert is_valid, "Multiline Unicode query failed"


class TestUnicodeInQueryResults:
    """Test Unicode handling in query results."""

    @pytest.mark.asyncio
    async def test_unicode_in_result_data(self):
        """Test that Unicode data in results is handled correctly."""
        unicode_data = [
            {"greeting": "Hello 世界", "emoji": "🌟⭐✨"},
            {"greeting": "مرحبا بالعالم", "emoji": "🌙🌟🌞"},
            {"greeting": "Здравствуй мир", "emoji": "❄️🌸🍁"},
        ]

        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT greeting, emoji FROM unicode_test",
                    rows=unicode_data,
                    duration=0.01,
                )
            ]
        )

        tool = ExecuteQueryTool(
            config=Config.from_env(),
            snowflake_service=service,
            query_service=Mock(),
            health_monitor=None,
        )

        result = await tool.execute(
            statement="SELECT greeting, emoji FROM unicode_test"
        )

        assert result["rowcount"] == 3
        assert len(result["rows"]) == 3

        # Check that Unicode is preserved
        for i, row in enumerate(result["rows"]):
            assert row["greeting"] == unicode_data[i]["greeting"]
            assert row["emoji"] == unicode_data[i]["emoji"]

    @pytest.mark.asyncio
    async def test_unicode_column_names_in_results(self):
        """Test Unicode in column names in results."""
        unicode_columns = [
            {"世界": "Chinese", "🌟": "star", "café": "coffee"},
            {"世界": "中国", "🌟": "星星", "café": "咖啡"},
        ]

        service = FakeSnowflakeService(
            [
                FakeQueryPlan(
                    statement="SELECT `世界`, `🌟`, `café` FROM unicode_cols",
                    rows=unicode_columns,
                    duration=0.01,
                )
            ]
        )

        from dataclasses import replace

        from igloo_mcp.config import SQLPermissions

        config = Config.from_env()
        config = replace(
            config,
            sql_permissions=SQLPermissions(
                select=True,
                show=True,
                describe=True,
                use=True,
                unknown=True,  # Allow unknown statement types
            ),
        )

        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=service,
            query_service=Mock(),
            health_monitor=None,
        )

        result = await tool.execute(
            statement="SELECT `世界`, `🌟`, `café` FROM unicode_cols"
        )

        assert result["rowcount"] == 2
        assert len(result["rows"]) == 2

        # Check that Unicode data is preserved in results
        # The exact column format may vary, but Unicode should be preserved
        for row in result["rows"]:
            assert isinstance(row, dict)
            # Check that the data contains Unicode characters
            all_values = str(row)
            assert any(char in all_values for char in ["世界", "🌟", "café"])


class TestUnicodeInCacheAndHistory:
    """Test Unicode handling in cache keys and history."""

    def test_unicode_in_cache_keys(self):
        """Test that Unicode in SQL doesn't break cache key computation."""
        import hashlib

        unicode_sqls = [
            "SELECT 'Hello 世界'",
            "SELECT '🌟⭐✨' as emoji",
        ]

        cache = QueryResultCache(mode="enabled", root=Path("/tmp/test_cache"))

        for sql in unicode_sqls:
            # Test SHA256 computation with Unicode SQL
            sql_sha256 = hashlib.sha256(sql.encode("utf-8")).hexdigest()

            # Test cache key generation with Unicode context
            key = cache.compute_cache_key(
                sql_sha256=sql_sha256,
                profile="test_profile",
                effective_context={
                    "warehouse": "TEST_WH",
                    "database": "TEST_DB_世界",  # Unicode in context
                    "schema": "TEST_SCHEMA",
                    "role": "TEST_ROLE_🌟",  # Emoji in context
                },
            )
            assert isinstance(key, str)
            assert len(key) == 64  # SHA256 hex length

    def test_unicode_in_history_files(self):
        """Test Unicode in query history JSONL files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = Path(temp_dir) / "history.jsonl"
            history = QueryHistory(history_path)

            # Record query with Unicode
            unicode_payload = {
                "ts": 1234567890,
                "status": "success",
                "profile": "test",
                "statement_preview": "SELECT 'Hello 世界 🌟'",
                "rowcount": 1,
                "reason": "Testing Unicode: مرحبا بالعالم",
            }

            history.record(unicode_payload)

            # Verify file was written and can be read back
            assert history_path.exists()

            with open(history_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                assert len(lines) == 1

                recorded = json.loads(lines[0])
                assert recorded["statement_preview"] == "SELECT 'Hello 世界 🌟'"
                assert recorded["reason"] == "Testing Unicode: مرحبا بالعالم"

    def test_unicode_in_json_files(self):
        """Test Unicode in JSON file I/O (used by cache manifests)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "unicode_manifest.json"

            unicode_data = {
                "message": "Hello 世界 🌟",
                "greeting": "مرحبا",
                "insights": ["Unicode test: こんにちは世界"],
            }

            # Write manifest with Unicode
            with open(test_file, "w", encoding="utf-8") as f:
                json.dump(unicode_data, f, ensure_ascii=False)

            # Verify it can be read back
            with open(test_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                assert loaded == unicode_data
                assert loaded["message"] == "Hello 世界 🌟"


class TestUnicodeEdgeCases:
    """Test edge cases with Unicode handling."""

    def test_zero_width_characters(self):
        """Test handling of zero-width Unicode characters."""
        # These can cause issues in string processing
        zw_chars = (
            "\u200b\u200c\u200d\ufeff"  # Zero-width space, non-joiner, joiner, BOM
        )
        query = f"SELECT '{zw_chars}test{zw_chars}' as zw_test"

        stmt_type, is_valid, error_msg = validate_sql_statement(query, ["select"], [])
        assert is_valid, "Zero-width characters should not break validation"

    def test_combining_characters(self):
        """Test combining Unicode characters."""
        # Characters with combining marks
        combining = "e\u0301"  # é as e + combining acute
        query = f"SELECT '{combining}' as combined"

        stmt_type, is_valid, error_msg = validate_sql_statement(query, ["select"], [])
        assert is_valid, "Combining characters should be handled"

    def test_unicode_normalization(self):
        """Test different Unicode normalization forms."""
        # Same character represented differently
        nfc = "café"  # Composed
        nfd = "café"  # Decomposed (if available)

        query_nfc = f"SELECT '{nfc}' as nfc"
        query_nfd = f"SELECT '{nfd}' as nfd"

        for query in [query_nfc, query_nfd]:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, ["select"], []
            )
            assert is_valid, f"Unicode normalization form failed: {query}"

    def test_high_unicode_codepoints(self):
        """Test very high Unicode codepoints."""
        # Emoji and symbols from higher planes
        high_unicode = "🧑‍💻🎯🚀"  # Person technologist, bullseye, rocket
        query = f"SELECT '{high_unicode}' as high_unicode"

        stmt_type, is_valid, error_msg = validate_sql_statement(query, ["select"], [])
        assert is_valid, "High Unicode codepoints should be handled"

    def test_mixed_scripts(self):
        """Test mixing different writing scripts."""
        mixed = "Hello 世界 مرحبا Здравствуй こんにちは 🌟"
        query = f"SELECT '{mixed}' as mixed_scripts"

        stmt_type, is_valid, error_msg = validate_sql_statement(query, ["select"], [])
        assert is_valid, "Mixed scripts should be handled"

    def test_unicode_in_simple_identifiers(self):
        """Test Unicode in simple identifier contexts."""
        # Test Unicode in contexts where identifiers are more likely to work
        simple_cases = [
            "SELECT café_price FROM my_table",  # Unicode in unquoted identifier
            "SELECT col FROM table_ñ",  # Unicode in unquoted identifier
        ]

        for query in simple_cases:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, ["select"], []
            )
            # These may or may not be valid depending on parser, but shouldn't crash
            assert stmt_type is not None


class TestEncodingRobustness:
    """Test encoding robustness across the system."""

    def test_mixed_byte_sequences(self):
        """Test handling of mixed byte sequences (if they occur)."""
        # This tests that we don't crash on unexpected byte sequences
        # In real usage, these shouldn't occur, but we want to be robust
        try:
            # Test with some edge case strings that might cause encoding issues
            edge_strings = [
                "Normal string",
                "String with null\x00byte",
                "String with high byte\xff",
            ]

            for test_str in edge_strings:
                query = f"SELECT '{test_str}' as test"
                stmt_type, is_valid, error_msg = validate_sql_statement(
                    query, ["select"], []
                )
                # Should either validate successfully or fail gracefully
                assert isinstance(is_valid, bool)
                assert isinstance(error_msg, (str, type(None)))

        except Exception as e:
            # If there are encoding issues, they should be caught and handled
            pytest.fail(f"Encoding robustness test failed: {e}")

    def test_file_encoding_preservation(self):
        """Test that file I/O preserves encoding."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "unicode_test.json"

            unicode_content = {
                "chinese": "世界",
                "emoji": "🌟⭐✨",
                "mixed": "Hello 世界 🌟 مرحبا",
            }

            # Write with UTF-8
            with open(test_file, "w", encoding="utf-8") as f:
                json.dump(unicode_content, f, ensure_ascii=False)

            # Read back
            with open(test_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            # Verify preservation
            assert loaded == unicode_content
            assert loaded["chinese"] == "世界"
            assert loaded["emoji"] == "🌟⭐✨"
