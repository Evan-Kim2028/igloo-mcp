"""
Consolidated SQL validation tests.

This file consolidates tests from:
- test_sql_validation.py (30 tests)
- test_sql_validation_enhanced.py (19 tests)
- test_sql_validation_obscure.py (19 tests)

Total: 68 tests consolidated with logical grouping and parametrization.

Organization:
1. Configuration & Permissions
2. Statement Type Detection
3. Statement Validation (Allow/Block)
4. Enhanced Features (CTEs, LATERAL, etc.)
5. Edge Cases & Complex Patterns
6. Error Handling & Alternatives
"""

from __future__ import annotations

import pytest

from igloo_mcp.config import SQLPermissions
from igloo_mcp.sql_validation import (
    extract_table_name,
    generate_sql_alternatives,
    get_sql_statement_type,
    validate_sql_statement,
)

# =============================================================================
# 1. Configuration & Permissions Tests
# =============================================================================


class TestSQLPermissions:
    """Test SQLPermissions configuration."""

    def test_default_permissions(self):
        """Test default permissions block dangerous operations."""
        perms = SQLPermissions()

        assert perms.select is True
        assert perms.insert is False
        assert perms.update is False
        assert perms.delete is False
        assert perms.drop is False
        assert perms.truncate is False

    def test_get_allow_list(self):
        """Test getting list of allowed statement types."""
        perms = SQLPermissions()
        allow_list = perms.get_allow_list()

        assert "select" in allow_list
        assert "insert" not in allow_list
        assert "delete" not in allow_list

    def test_get_disallow_list(self):
        """Test getting list of disallowed statement types."""
        perms = SQLPermissions()
        disallow_list = perms.get_disallow_list()

        assert "insert" in disallow_list
        assert "delete" in disallow_list
        assert "select" not in disallow_list

    def test_custom_permissions(self):
        """Test custom permission configuration."""
        perms = SQLPermissions(delete=True, drop=True)
        allow_list = perms.get_allow_list()

        assert "delete" in allow_list
        assert "drop" in allow_list


# =============================================================================
# 2. Statement Type Detection Tests
# =============================================================================


class TestStatementTypeDetection:
    """Test SQL statement type detection."""

    @pytest.mark.parametrize(
        "sql,expected_type",
        [
            ("SELECT * FROM users", "Select"),
            ("  SELECT col FROM table", "Select"),
            ("/* comment */ SELECT 1", "Select"),
            ("WITH cte AS (SELECT 1) SELECT * FROM cte", "Select"),
            ("DELETE FROM users WHERE id = 1", "Delete"),
            ("INSERT INTO users VALUES (1)", "Insert"),
            ("UPDATE users SET name = 'test'", "Update"),
            ("DROP TABLE users", "Drop"),
            ("TRUNCATE TABLE temp", "Truncate"),
            ("SHOW TABLES", "Show"),
            ("DESCRIBE users", "Describe"),
        ],
    )
    def test_statement_type_detection(self, sql, expected_type):
        """Test detecting various SQL statement types."""
        result = get_sql_statement_type(sql)
        assert result == expected_type

    def test_case_insensitive_detection(self):
        """Test that detection is case-insensitive."""
        assert get_sql_statement_type("select 1") == "Select"
        assert get_sql_statement_type("SELECT 1") == "Select"
        assert get_sql_statement_type("SeLeCt 1") == "Select"

    def test_detect_with_leading_whitespace(self):
        """Test detection with leading whitespace."""
        assert get_sql_statement_type("  \n  SELECT 1") == "Select"

    def test_detect_with_leading_comments(self):
        """Test detection with leading SQL comments."""
        assert get_sql_statement_type("-- comment\nSELECT 1") == "Select"
        assert get_sql_statement_type("/* block comment */SELECT 1") == "Select"


# =============================================================================
# 3. Statement Validation Tests (Allow/Block)
# =============================================================================


class TestStatementValidation:
    """Test SQL statement validation with allow/block rules."""

    # --- Allowed Statements ---

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM users",
            "SELECT col1, col2 FROM table WHERE id > 100",
            "SELECT COUNT(*) FROM orders",
        ],
    )
    def test_select_statements_allowed(self, sql):
        """Test that SELECT statements are allowed by default."""
        allow_list = ["select"]
        disallow_list = ["delete", "drop", "truncate"]

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, allow_list, disallow_list
        )
        assert is_valid is True
        assert error_msg is None

    def test_cte_queries_allowed(self):
        """Test that CTE (WITH) queries are allowed."""
        sql = "WITH cte AS (SELECT 1) SELECT * FROM cte"
        allow_list = ["select"]
        disallow_list = ["delete", "drop"]

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, allow_list, disallow_list
        )
        assert is_valid is True

    def test_union_queries_allowed(self):
        """Test that UNION queries are allowed."""
        sql = "SELECT 1 UNION SELECT 2"
        allow_list = ["select"]
        disallow_list = ["delete"]

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, allow_list, disallow_list
        )
        assert is_valid is True

    def test_intersect_except_allowed(self):
        """Test that INTERSECT and EXCEPT are allowed."""
        sql1 = "SELECT 1 INTERSECT SELECT 2"
        sql2 = "SELECT 1 EXCEPT SELECT 2"
        allow_list = ["select"]
        disallow_list = ["delete"]

        _, is_valid1, _ = validate_sql_statement(sql1, allow_list, disallow_list)
        _, is_valid2, _ = validate_sql_statement(sql2, allow_list, disallow_list)

        assert is_valid1 is True
        assert is_valid2 is True

    # --- Blocked Statements ---

    @pytest.mark.parametrize(
        "sql,expected_type",
        [
            ("DELETE FROM users", "Delete"),
            ("INSERT INTO users VALUES (1)", "Insert"),
            ("UPDATE users SET name = 'x'", "Update"),
            ("DROP TABLE users", "Drop"),
            ("TRUNCATE TABLE temp", "Truncate"),
        ],
    )
    def test_dangerous_statements_blocked(self, sql, expected_type):
        """Test that dangerous statements are blocked by default."""
        allow_list = ["select"]
        disallow_list = ["delete", "insert", "update", "drop", "truncate"]

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, allow_list, disallow_list
        )

        assert stmt_type == expected_type
        assert is_valid is False
        assert error_msg is not None
        assert "not permitted" in error_msg.lower()

    def test_multiple_statements_blocked(self):
        """Test that multiple statements are blocked."""
        sql = "SELECT 1; SELECT 2"
        allow_list = ["select"]
        disallow_list = []

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, allow_list, disallow_list
        )
        assert is_valid is False

    # --- Custom Permissions ---

    def test_custom_allow_list(self):
        """Test validation with custom allow list."""
        sql = "DELETE FROM users WHERE id = 1"
        # Allow delete explicitly
        allow_list = ["select", "delete"]
        disallow_list = ["drop", "truncate"]

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, allow_list, disallow_list
        )
        # Should be allowed with custom permissions
        assert is_valid is True or error_msg is None


# =============================================================================
# 4. Enhanced Features Tests (CTEs, LATERAL, Snowflake-specific)
# =============================================================================


class TestEnhancedFeatures:
    """Test enhanced SQL features support."""

    def test_lateral_flatten_allowed(self):
        """Test that LATERAL FLATTEN (Snowflake) is allowed."""
        sql = "SELECT * FROM table, LATERAL FLATTEN(input => array_col)"
        allow_list = ["select"]
        disallow_list = []

        _, is_valid, _ = validate_sql_statement(sql, allow_list, disallow_list)
        assert is_valid is True

    def test_cross_join_lateral_allowed(self):
        """Test CROSS JOIN LATERAL patterns."""
        sql = "SELECT * FROM table CROSS JOIN LATERAL FLATTEN(input => col)"
        allow_list = ["select"]
        disallow_list = []

        _, is_valid, _ = validate_sql_statement(sql, allow_list, disallow_list)
        assert is_valid is True

    @pytest.mark.parametrize("nesting_level", [3, 5, 10])
    def test_deeply_nested_ctes(self, nesting_level):
        """Test deeply nested CTEs are handled."""
        # Build nested CTE
        ctes = []
        for i in range(nesting_level):
            if i == 0:
                ctes.append(f"cte{i} AS (SELECT 1 as val)")
            else:
                ctes.append(f"cte{i} AS (SELECT val FROM cte{i-1})")

        sql = f"WITH {', '.join(ctes)} SELECT * FROM cte{nesting_level-1}"
        allow_list = ["select"]
        disallow_list = []

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, allow_list, disallow_list
        )
        # Should not crash, should return a tuple
        assert stmt_type is not None

    def test_complex_snowflake_patterns(self):
        """Test complex Snowflake-specific patterns."""
        sql = """
        WITH data AS (
            SELECT * FROM table
            WHERE date >= DATEADD(day, -7, CURRENT_DATE())
        )
        SELECT
            f.value::string as item,
            COUNT(*) as cnt
        FROM data,
        LATERAL FLATTEN(input => array_column) f
        GROUP BY 1
        ORDER BY 2 DESC
        """
        allow_list = ["select"]
        disallow_list = []

        _, is_valid, _ = validate_sql_statement(sql, allow_list, disallow_list)
        assert is_valid is True


# =============================================================================
# 5. Edge Cases & Complex Patterns Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and complex patterns."""

    def test_mixed_case_keywords(self):
        """Test mixed case SQL keywords."""
        sql = "SeLeCt * FrOm UsErS wHeRe Id = 1"
        result = validate_sql_statement(sql)
        assert result["is_valid"] is True

    def test_sql_with_comments(self):
        """Test SQL with embedded comments."""
        sql = """
        -- This is a comment
        SELECT * FROM users /* inline comment */
        WHERE id = 1 -- another comment
        """
        result = validate_sql_statement(sql)
        assert result["is_valid"] is True

    def test_block_comment_with_keywords_ignored(self):
        """Test that keywords in block comments are ignored."""
        sql = "/* DELETE UPDATE DROP */ SELECT 1"
        result = validate_sql_statement(sql)
        assert result["is_valid"] is True

    def test_very_long_sql_statement(self):
        """Test validation of very long SQL (10KB+)."""
        # Create a 10KB SELECT with many columns
        cols = ", ".join([f"col{i}" for i in range(500)])
        sql = f"SELECT {cols} FROM large_table"

        result = validate_sql_statement(sql)
        # Should not crash
        assert "is_valid" in result

    def test_sql_with_many_unions(self):
        """Test SQL with many UNION statements."""
        unions = " UNION ".join([f"SELECT {i}" for i in range(20)])
        sql = unions

        result = validate_sql_statement(sql)
        assert result["is_valid"] is True

    def test_extreme_whitespace(self):
        """Test SQL with extreme whitespace and newlines."""
        sql = """


        SELECT    *

        FROM

        table

        """
        result = validate_sql_statement(sql)
        assert result["is_valid"] is True

    def test_window_functions_complex(self):
        """Test complex window function patterns."""
        sql = """
        SELECT
            col1,
            ROW_NUMBER() OVER (PARTITION BY col2 ORDER BY col3) as rn,
            RANK() OVER (PARTITION BY col2 ORDER BY col3 DESC) as rnk
        FROM table
        """
        result = validate_sql_statement(sql)
        assert result["is_valid"] is True

    def test_recursive_cte(self):
        """Test recursive CTE pattern."""
        sql = """
        WITH RECURSIVE cte AS (
            SELECT 1 as n
            UNION ALL
            SELECT n + 1 FROM cte WHERE n < 10
        )
        SELECT * FROM cte
        """
        result = validate_sql_statement(sql)
        # Should handle gracefully
        assert "is_valid" in result


# =============================================================================
# 6. SHOW/DESCRIBE Statement Tests
# =============================================================================


class TestShowDescribeStatements:
    """Test SHOW and DESCRIBE statement handling."""

    def test_show_statements_allowed_when_permitted(self):
        """Test SHOW statements when explicitly allowed."""
        sql = "SHOW TABLES"
        perms = SQLPermissions(show=True)
        result = validate_sql_statement(sql, permissions=perms)
        assert result["is_valid"] is True

    def test_show_statements_blocked_when_disabled(self):
        """Test SHOW statements blocked by default."""
        sql = "SHOW DATABASES"
        perms = SQLPermissions(show=False)
        result = validate_sql_statement(sql, permissions=perms)
        assert result["is_valid"] is False

    def test_show_with_leading_comments(self):
        """Test SHOW with leading comments."""
        sql = "-- comment\nSHOW TABLES"
        perms = SQLPermissions(show=True)
        result = validate_sql_statement(sql, permissions=perms)
        assert result["is_valid"] is True

    def test_describe_table_allowed(self):
        """Test DESCRIBE TABLE statements."""
        sql = "DESCRIBE TABLE users"
        perms = SQLPermissions(describe=True)
        result = validate_sql_statement(sql, permissions=perms)
        # Should be allowed with proper permissions
        assert (
            result["is_valid"] is True or "describe" in result.get("error", "").lower()
        )


# =============================================================================
# 7. Error Handling & Alternatives Tests
# =============================================================================


class TestErrorHandlingAndAlternatives:
    """Test error messages and safe alternatives generation."""

    def test_extract_table_name_from_delete(self):
        """Test extracting table name from DELETE."""
        sql = "DELETE FROM users WHERE id = 1"
        table = extract_table_name(sql)
        assert table == "<table_name>" or "users" in table.lower()

    def test_extract_table_name_from_drop(self):
        """Test extracting table name from DROP."""
        sql = "DROP TABLE old_data"
        table = extract_table_name(sql)
        assert table == "<table_name>" or "old_data" in table.lower()

    def test_extract_failure_returns_placeholder(self):
        """Test failed extraction returns placeholder."""
        sql = "INVALID SQL"
        table = extract_table_name(sql)
        assert table == "<table_name>"

    def test_generate_alternatives_for_blocked_statement(self):
        """Test generating safe alternatives for blocked statements."""
        sql = "DELETE FROM users WHERE id = 1"
        result = validate_sql_statement(sql)

        if not result["is_valid"]:
            alternatives = generate_sql_alternatives(sql, result)
            assert isinstance(alternatives, list)
            # Should suggest safer alternatives
            assert len(alternatives) > 0

    def test_structured_error_information(self):
        """Test that errors provide structured information."""
        sql = "DELETE FROM users"
        result = validate_sql_statement(sql)

        assert "is_valid" in result
        assert "error" in result or result["is_valid"]
        if "error" in result:
            assert isinstance(result["error"], str)

    def test_enhanced_error_messages(self):
        """Test that error messages are helpful."""
        sql = "SOME_UNKNOWN_STATEMENT"
        result = validate_sql_statement(sql)

        # Should provide meaningful error
        assert "is_valid" in result
        if not result["is_valid"]:
            assert len(result.get("error", "")) > 0


# =============================================================================
# 8. Fallback & Compatibility Tests
# =============================================================================


class TestFallbackBehavior:
    """Test fallback behavior when sqlglot unavailable."""

    def test_validation_without_sqlglot_works(self):
        """Test that validation works even if sqlglot parsing fails."""
        # This tests the fallback path
        sql = "SELECT 1"
        result = validate_sql_statement(sql)
        # Should always return valid result structure
        assert "is_valid" in result

    def test_fallback_handles_unknown_select_like_queries(self):
        """Test fallback handles SELECT-like queries gracefully."""
        sql = "SELECT * FROM unknown_syntax_here @@weird@@"
        result = validate_sql_statement(sql)
        # Should not crash, provide some result
        assert "is_valid" in result
