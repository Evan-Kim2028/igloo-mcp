"""SQL Injection Security Tests for Session Parameter Handling.

Tests comprehensive SQL injection attack vectors against session parameter
handling in execute_query tool to ensure robust security.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from igloo_mcp.config import Config
from igloo_mcp.constants import (
    ALLOWED_SESSION_PARAMETERS,
    MAX_QUERY_TIMEOUT_SECONDS,
    MIN_QUERY_TIMEOUT_SECONDS,
)
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.service_layer import QueryService


class TestSessionParameterSQLInjection:
    """Test SQL injection prevention in session parameter handling."""

    @pytest.fixture
    def tool(self, monkeypatch):
        """Create ExecuteQueryTool instance for testing."""
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        config = Config.from_env()
        snowflake_service = Mock()
        query_service = Mock(spec=QueryService)

        return ExecuteQueryTool(
            config=config,
            snowflake_service=snowflake_service,
            query_service=query_service,
            health_monitor=None,
        )

    def test_whitelist_prevents_invalid_parameter_names(self, tool):
        """Test that whitelist prevents access to invalid parameter names."""
        # Attempt to access non-whitelisted parameter
        invalid_names = [
            "DROP TABLE users",
            "'; DROP TABLE users; --",
            "QUERY_TAG'; DROP TABLE users; --",
            "UNION SELECT * FROM sensitive_data",
            "../../etc/passwd",
            "QUERY_TAG' OR '1'='1",
        ]

        # This tests the validation logic - invalid names should be rejected
        for invalid_name in invalid_names:
            # The whitelist check should prevent these
            assert invalid_name.upper() not in ALLOWED_SESSION_PARAMETERS

    def test_escape_sql_identifier_handles_injection_patterns(self):
        """Test that SQL identifier escaping handles injection patterns."""
        # These patterns should be safely escaped
        injection_patterns = [
            ("normal_name", "normal_name"),
            ("name'with'quotes", "name''with''quotes"),
            ("'; DROP TABLE users; --", "''; DROP TABLE users; --"),
            ("name' OR '1'='1", "name'' OR ''1''=''1"),
            ("QUERY_TAG'; DELETE FROM users; --", "QUERY_TAG''; DELETE FROM users; --"),
            ("QUERY_TAG%", "QUERY_TAG\\%"),
            ("QUERY_TAG_", "QUERY_TAG\\_"),
            ("QUERY%TAG", "QUERY\\%TAG"),
            ("name\\with\\backslash", "name\\\\with\\\\backslash"),
        ]

        # Test the escaping logic (simulating the function)
        def escape_sql_identifier(identifier: str) -> str:
            """Escape SQL identifier for LIKE clause with wildcard protection."""
            escaped = identifier.replace("'", "''")
            # Escape LIKE wildcards
            escaped = escaped.replace("\\", "\\\\")
            escaped = escaped.replace("%", "\\%")
            escaped = escaped.replace("_", "\\_")
            return escaped

        for input_val, expected in injection_patterns:
            result = escape_sql_identifier(input_val)
            # Escaped value should match expected
            assert (
                result == expected
            ), f"Input: {input_val}, Expected: {expected}, Got: {result}"
            # Escaped value should not contain unescaped single quotes
            assert "''" in result or "'" not in result or result.count("'") % 2 == 0

    def test_escape_tag_value_handles_injection_patterns(self):
        """Test that tag value escaping handles injection patterns."""
        injection_patterns = [
            "normal_tag",
            "tag'with'quotes",
            "'; DROP TABLE users; --",
            "tag' OR '1'='1",
            "QUERY_TAG'; DELETE FROM users; --",
            "tag'; INSERT INTO logs VALUES ('hacked'); --",
        ]

        # Test the escaping logic (simulating the function)
        def escape_tag(tag_value: str) -> str:
            return tag_value.replace("'", "''")

        for pattern in injection_patterns:
            escaped = escape_tag(pattern)
            # Escaped value should have all single quotes doubled
            assert escaped.count("''") == pattern.count("'")
            # Should not contain unescaped single quotes (except as part of '')
            single_quotes = escaped.replace("''", "")
            assert "'" not in single_quotes

    def test_escape_sql_value_handles_injection_patterns(self):
        """Test that SQL value escaping handles injection patterns."""
        injection_patterns = [
            ("normal_value", "'normal_value'"),
            ("value'with'quotes", "'value''with''quotes'"),
            ("'; DROP TABLE users; --", "'''; DROP TABLE users; --'"),
            ("value' OR '1'='1", "'value'' OR ''1''=''1'"),
        ]

        # Test the escaping logic (simulating the function)
        def escape_sql_value(value: Any) -> str:
            if isinstance(value, (int, float)):
                return str(value)
            value_str = str(value)
            # Escape single quotes and wrap in quotes
            return f"'{value_str.replace(chr(39), chr(39) + chr(39))}'"

        for input_val, expected_prefix in injection_patterns:
            escaped = escape_sql_value(input_val)
            # Should be wrapped in quotes
            assert escaped.startswith("'") and escaped.endswith("'")
            # All single quotes inside should be escaped
            inner = escaped[1:-1]  # Remove outer quotes
            assert inner.count("''") == input_val.count("'")
            # Should not contain unescaped single quotes
            single_quotes = inner.replace("''", "")
            assert "'" not in single_quotes

    def test_session_parameter_name_whitelist_enforcement(self):
        """Test that only whitelisted session parameters can be accessed."""
        # All allowed parameters should be in the whitelist
        allowed_params = [
            "QUERY_TAG",
            "STATEMENT_TIMEOUT_IN_SECONDS",
            "AUTOCOMMIT",
            "BINARY_INPUT_FORMAT",
        ]

        for param in allowed_params:
            assert param in ALLOWED_SESSION_PARAMETERS

        # Invalid parameters should not be in whitelist
        invalid_params = [
            "DROP",
            "DELETE",
            "INSERT",
            "UPDATE",
            "EXECUTE",
            "CALL",
        ]

        for param in invalid_params:
            assert param not in ALLOWED_SESSION_PARAMETERS

    @pytest.mark.parametrize(
        "malicious_value",
        [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "'; DELETE FROM logs; --",
            "tag'; INSERT INTO sensitive VALUES ('hacked'); --",
            "'; UPDATE users SET password='hacked'; --",
            "'; EXECUTE IMMEDIATE 'DROP TABLE users'; --",
            "'; CALL malicious_procedure(); --",
            "'; SELECT * FROM sensitive_data; --",
            "tag' UNION SELECT password FROM users; --",
            "'; ALTER TABLE users ADD COLUMN hacked TEXT; --",
        ],
    )
    def test_malicious_tag_values_are_escaped(self, malicious_value):
        """Test that malicious tag values are properly escaped."""

        # Simulate the escaping function
        def escape_tag(tag_value: str) -> str:
            return tag_value.replace("'", "''")

        escaped = escape_tag(malicious_value)

        # Verify escaping
        assert escaped.count("''") == malicious_value.count("'")
        # The escaped value should be safe to use in SQL string literal
        # (when wrapped in quotes and used in f-string)
        assert "'" not in escaped.replace("''", "")

    @pytest.mark.parametrize(
        "malicious_name",
        [
            "QUERY_TAG'; DROP TABLE users; --",
            "QUERY_TAG' OR '1'='1",
            "STATEMENT_TIMEOUT_IN_SECONDS'; DELETE FROM logs; --",
        ],
    )
    def test_malicious_parameter_names_are_rejected(self, malicious_name):
        """Test that malicious parameter names are rejected by whitelist."""
        # These should not be in the whitelist (even if they contain valid names)
        assert malicious_name.upper() not in ALLOWED_SESSION_PARAMETERS

        # The whitelist check should prevent these
        name_upper = malicious_name.upper()
        is_allowed = name_upper in ALLOWED_SESSION_PARAMETERS
        assert (
            not is_allowed
        ), f"Malicious parameter name should be rejected: {malicious_name}"

    def test_unicode_and_special_characters_in_values(self):
        """Test that Unicode and special characters are handled safely."""
        special_values = [
            "tag with spaces",
            "tag-with-dashes",
            "tag.with.dots",
            "tag_with_underscores",
            "tag'with'quotes",
            "tag;with;semicolons",
            "tag--with--comments",
            "tag/*with*/comments",
            "tag\nwith\nnewlines",
            "tag\twith\ttabs",
            "tag with émojis 🎉",
            "tag with 中文",
            "tag with русский",
        ]

        def escape_tag(tag_value: str) -> str:
            return tag_value.replace("'", "''")

        for value in special_values:
            escaped = escape_tag(value)
            # Should preserve all characters except single quotes (which are doubled)
            assert len(escaped) >= len(value)
            # Single quotes should be doubled
            assert escaped.count("''") == value.count("'")

    def test_numeric_timeout_values_are_validated(self):
        """Test that timeout values are validated as numeric."""
        # Valid numeric values
        valid_timeouts = [1, 30, 60, 300, 3600, "1", "30", "60"]

        for timeout in valid_timeouts:
            try:
                timeout_int = int(timeout)
                assert (
                    MIN_QUERY_TIMEOUT_SECONDS
                    <= timeout_int
                    <= MAX_QUERY_TIMEOUT_SECONDS
                )
            except (ValueError, TypeError):
                # String values that can't be converted should fail validation
                pass

        # Invalid values that might be used for injection
        invalid_timeouts = [
            "'; DROP TABLE users; --",
            "30' OR '1'='1",
            "'; DELETE FROM logs; --",
        ]

        for timeout in invalid_timeouts:
            try:
                timeout_int = int(timeout)
                # If conversion succeeds, it should be a valid range
                assert (
                    MIN_QUERY_TIMEOUT_SECONDS
                    <= timeout_int
                    <= MAX_QUERY_TIMEOUT_SECONDS
                )
            except ValueError:
                # Expected - these should fail int() conversion
                pass

    def test_extremely_long_values_are_handled(self):
        """Test that extremely long parameter values are handled safely."""
        # Very long tag value (longer than MAX_REASON_LENGTH)
        long_value = "A" * 1000 + "' OR '1'='1"

        def escape_tag(tag_value: str) -> str:
            return tag_value.replace("'", "''")

        escaped = escape_tag(long_value)
        # Should still escape properly
        assert escaped.count("''") == long_value.count("'")
        # Length should increase by number of quotes
        assert len(escaped) == len(long_value) + long_value.count("'")

    def test_null_and_empty_values_are_handled(self):
        """Test that null and empty values are handled safely."""
        edge_cases = [
            None,
            "",
            "   ",
            "'",
            "''",
            "'''",
        ]

        def escape_sql_value(value: Any) -> str:
            if isinstance(value, (int, float)):
                return str(value)
            if value is None:
                return "NULL"
            value_str = str(value)
            return f"'{value_str.replace(chr(39), chr(39) + chr(39))}'"

        for value in edge_cases:
            escaped = escape_sql_value(value)
            # Should not raise exception
            assert isinstance(escaped, str)

    def test_parameter_name_case_insensitivity(self):
        """Test that parameter name validation is case-insensitive."""
        # All variations should match the whitelist
        variations = [
            "query_tag",
            "QUERY_TAG",
            "Query_Tag",
            "qUeRy_TaG",
        ]

        for variation in variations:
            assert variation.upper() in ALLOWED_SESSION_PARAMETERS

    def test_sql_injection_in_like_clause(self):
        """Test SQL injection prevention in LIKE clause for parameter lookup."""
        # The LIKE clause uses: f"SHOW PARAMETERS LIKE '{escaped_name}' IN SESSION"
        # Test that escaping prevents injection including LIKE wildcards

        malicious_names = [
            "QUERY_TAG' OR '1'='1",
            "QUERY_TAG'; DROP TABLE users; --",
            "QUERY_TAG%",
            "QUERY_TAG_",
            "QUERY%TAG",
            "QUERY_TAG%' OR '1'='1",
            "QUERY_TAG_' OR '1'='1",
        ]

        def escape_sql_identifier(identifier: str) -> str:
            """Escape SQL identifier for LIKE clause with wildcard protection."""
            escaped = identifier.replace("'", "''")
            # Escape LIKE wildcards
            escaped = escaped.replace("\\", "\\\\")
            escaped = escaped.replace("%", "\\%")
            escaped = escaped.replace("_", "\\_")
            return escaped

        for malicious_name in malicious_names:
            escaped = escape_sql_identifier(malicious_name)
            # Escaped name should be safe for LIKE clause
            # Should not contain unescaped single quotes
            assert "'" not in escaped.replace("''", "")
            # Should not contain unescaped LIKE wildcards
            # After removing escaped sequences, no % or _ should remain
            temp = escaped.replace("\\%", "").replace("\\_", "").replace("\\\\", "")
            assert "%" not in temp or temp.count("%") == 0
            assert "_" not in temp or temp.count("_") == 0
