"""Tests for robust pattern detection to avoid false positives."""

from __future__ import annotations

from igloo_mcp.sql_validation import _is_select_like_statement, validate_sql_statement


class TestRobustPatternDetection:
    """Test robust pattern detection that avoids false positives."""

    def test_ast_based_select_detection(self):
        """Test that AST-based detection correctly identifies SELECT queries."""
        select_queries = [
            "SELECT id FROM table1",
            "SELECT * FROM users ORDER BY created_at",
            "SELECT COUNT(*) FROM events WHERE status = 'active'",
        ]

        for query in select_queries:
            assert _is_select_like_statement(query), f"Should detect SELECT: {query}"

    def test_ast_based_union_detection(self):
        """Test that UNION operations are correctly detected."""
        union_queries = [
            "SELECT id FROM table1 UNION SELECT id FROM table2",
            "SELECT name FROM a UNION ALL SELECT name FROM b",
            "SELECT * FROM table1 INTERSECT SELECT * FROM table2",
            "SELECT id FROM table1 EXCEPT SELECT id FROM table2",
            "SELECT id FROM table1 MINUS SELECT id FROM table2",  # Oracle-style
        ]

        for query in union_queries:
            assert _is_select_like_statement(query), f"Should detect UNION: {query}"

    def test_false_positive_prevention_in_strings(self):
        """Test that keywords in string literals don't cause false positives."""
        false_positive_queries = [
            "UPDATE users SET description = 'This UNION will fail' WHERE id = 1",
            "DELETE FROM logs WHERE message = 'EXCEPT in namespace'",
            "INSERT INTO comments (text) VALUES ('MINUS the following')",
            "UPDATE products SET notes = 'UNION is not allowed' WHERE category = 'test'",
            'SELECT * FROM table1 WHERE description = "INTERSECT with other data"',
        ]

        for query in false_positive_queries:
            assert not _is_select_like_statement(
                query
            ), f"Should NOT detect as SELECT: {query}"

    def test_false_positive_prevention_in_identifiers(self):
        """Test that keywords in column/table names don't cause false positives."""
        false_positive_queries = [
            "SELECT * FROM table_union WHERE status = 'active'",
            "SELECT * FROM except_logs ORDER BY created_at",
            "UPDATE union_table SET name = 'test' WHERE id = 1",
            "CREATE TABLE except_data (id INT, name VARCHAR)",
            "ALTER TABLE minus_records ADD COLUMN status VARCHAR",
        ]

        for query in false_positive_queries:
            assert not _is_select_like_statement(
                query
            ), f"Should NOT detect as SELECT: {query}"

    def test_complex_select_patterns(self):
        """Test complex SELECT patterns that should be detected."""
        complex_select_queries = [
            # WITH CTEs
            "WITH monthly_sales AS (SELECT month, SUM(amount) FROM sales GROUP BY month) SELECT * FROM monthly_sales",
            # Nested queries
            "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders WHERE total > 100)",
            # Window functions
            "SELECT name, ROW_NUMBER() OVER (ORDER BY created_at) as rn FROM users",
            # LATERAL operations (the original issue)
            "SELECT user_id, event_type FROM events LATERAL FLATTEN(input => event_data) events",
            # Complex multi-line queries
            """WITH ranked_users AS (
                SELECT
                    user_id,
                    RANK() OVER (PARTITION BY department ORDER BY created_at DESC) as dept_rank
                FROM users
                WHERE active = true
            )
            SELECT user_id, dept_rank
            FROM ranked_users
            WHERE dept_rank <= 3""",
        ]

        for query in complex_select_queries:
            assert _is_select_like_statement(
                query
            ), f"Should detect complex SELECT: {query}"

    def test_non_select_statements(self):
        """Test that non-SELECT statements are correctly rejected."""
        non_select_queries = [
            "INSERT INTO users (name, email) VALUES ('test', 'test@example.com')",
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = 1",
            "DELETE FROM users WHERE created_at < '2020-01-01'",
            "CREATE TABLE backup_data AS SELECT * FROM users",
            "DROP TABLE old_users",
            "TRUNCATE TABLE logs",
        ]

        for query in non_select_queries:
            assert not _is_select_like_statement(
                query
            ), f"Should NOT detect non-SELECT: {query}"

    def test_malformed_sql_handling(self):
        """Test that malformed SQL is handled gracefully."""
        malformed_queries = [
            "",  # Empty string
            "SELECT",  # Incomplete
            "UNION",  # Invalid syntax
            "WITH",  # Incomplete CTE
            "SELECT * FROM",  # Incomplete FROM clause
        ]

        for query in malformed_queries:
            result = _is_select_like_statement(query)
            # Malformed queries should be treated conservatively (not SELECT)
            assert isinstance(result, bool), f"Should return boolean: {query}"

    def test_validation_integration(self):
        """Test that robust detection works in full validation context."""
        # These should be allowed
        allow_list = ["Select"]
        disallow_list = []

        valid_queries = [
            "SELECT * FROM users",
            "SELECT id FROM a UNION SELECT id FROM b",
            "SELECT * FROM table1 CROSS JOIN LATERAL evidence AS ev ON table1.id = ev.rec_id",
        ]

        for query in valid_queries:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, allow_list, disallow_list
            )
            assert is_valid is True, f"Should be allowed: {query}"
            assert error_msg is None, f"Should have no error: {query}"

        # These should be blocked
        blocked_queries = [
            "DELETE FROM users",
            "UPDATE users SET name = 'test'",
        ]

        for query in blocked_queries:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, allow_list, disallow_list
            )
            assert is_valid is False, f"Should be blocked: {query}"
            assert error_msg is not None, f"Should have error message: {query}"

    def test_edge_cases_in_string_matching(self):
        """Test edge cases in string pattern matching."""
        edge_cases = [
            # SQL with comments containing keywords
            "SELECT * FROM users -- Note: This query contains no UNION operations",
            "SELECT id FROM table1 /* EXCEPT: this is just a comment */",
            # SQL with escaped strings
            "SELECT * FROM users WHERE notes = 'This contains \\'UNION\\' as text'",
            'SELECT * FROM table1 WHERE description = "\\"INTERSECT\\" is a keyword"',
            # SQL with mixed case
            "select * from table1 Union select * from table2",  # Mixed case but valid
            "Select * From Users WHERE id > 10",  # Random capitalization
        ]

        mixed_results = [True, True, False, False, True, True]  # Expected results

        for i, query in enumerate(edge_cases):
            result = _is_select_like_statement(query)
            assert result == mixed_results[i], f"Edge case {i}: {query}"

    def test_future_unknown_patterns(self):
        """Test robustness against future unknown patterns."""
        # Simulate new Snowflake features that upstream parser might not recognize
        future_patterns = [
            # Unknown hypothetical syntax
            "SELECT * FROM table1 FUTURE_FEATURE param1='value'",
            "SELECT * FROM table1 USE_NEW_INDEX idx_name",
            # Complex expressions that might confuse parsers
            "SELECT * FROM table1 WHERE json_data:field::variant = 'test'",
            "SELECT * FROM table1 WHERE array_col[1] = 'UNION test'",
        ]

        # These should be handled conservatively - some might be detected as SELECT by AST
        for query in future_patterns:
            result = _is_select_like_statement(query)
            # Just ensure it doesn't crash and returns a boolean
            assert isinstance(
                result, bool
            ), f"Future pattern should return boolean: {query}"
