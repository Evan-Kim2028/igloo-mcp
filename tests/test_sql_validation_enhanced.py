"""Enhanced tests for SQL validation with LATERAL support and improved error messages."""

from __future__ import annotations

import types

from igloo_mcp import sql_validation as sv
from igloo_mcp.sql_validation import validate_sql_statement


class TestEnhancedSQLValidation:
    """Test enhanced SQL validation with LATERAL pattern support."""

    def test_lateral_flatten_queries_allowed(self):
        """Test that LATERAL FLATTEN queries are allowed when SELECT is permitted."""
        lateral_queries = [
            """SELECT fees.position_object_id, rewards.seq AS reward_index
            FROM tmp_cetus_lp_positions_calculated_enhanced_may20_2025 fees
            , LATERAL FLATTEN(input => fees.rewards_info) rewards
            WHERE fees.rewards_info IS NOT NULL
            LIMIT 5""",
            """SELECT
                fees.position_object_id,
                rewards.seq AS reward_index
            FROM tmp_cetus_lp_positions_calculated_enhanced_may20_2025 fees
            , LATERAL FLATTEN(input => fees.rewards_info) rewards
            WHERE fees.rewards_info IS NOT NULL
            AND rewards.seq < 10""",
        ]

        allow_list = ["Select"]
        disallow_list = []

        for query in lateral_queries:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, allow_list, disallow_list
            )

            assert is_valid is True, f"LATERAL query should be allowed: {query}"
            assert (
                stmt_type == "Select"
            ), f"LATERAL query should be recognized as SELECT: {stmt_type}"
            assert (
                error_msg is None
            ), f"LATERAL query should not have error message: {error_msg}"

    def test_cross_join_lateral_queries_allowed(self):
        """Test that CROSS JOIN LATERAL queries are allowed when SELECT is permitted."""
        cross_join_queries = [
            """SELECT t1.id, t2.value
            FROM table1 t1
            CROSS JOIN LATERAL (
                SELECT value FROM table2 WHERE table2.parent_id = t1.id
            ) t2""",
            """SELECT customers.cust_id, orders.order_id
            FROM customers
            CROSS JOIN LATERAL (
                SELECT order_id FROM orders WHERE orders.cust_id = customers.cust_id
                ORDER BY order_date DESC LIMIT 1
            ) orders""",
        ]

        allow_list = ["Select"]
        disallow_list = []

        for query in cross_join_queries:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, allow_list, disallow_list
            )

            assert (
                is_valid is True
            ), f"CROSS JOIN LATERAL query should be allowed: {query}"
            assert (
                stmt_type == "Select"
            ), f"CROSS JOIN LATERAL query should be recognized as SELECT: {stmt_type}"
            assert (
                error_msg is None
            ), f"CROSS JOIN LATERAL query should not have error message: {error_msg}"

    def test_case_sensitivity_fix(self):
        """Test that case sensitivity is properly handled in validation."""
        query = "SELECT * FROM test_table"

        # Test with mixed case allow list (should work after our fix)
        mixed_case_list = ["Select", "Insert"]
        stmt_type, is_valid, error_msg = validate_sql_statement(
            query, mixed_case_list, []
        )

        assert (
            is_valid is True
        ), "Mixed case allow list should work with case normalization"
        assert stmt_type == "Select"
        assert error_msg is None

    def test_enhanced_error_messages_for_unknown_type(self):
        """Test enhanced error messages for 'Unknown' type queries."""
        unknown_query = "SOME_WEIRD_SQL_COMMAND table1"

        allow_list = ["Select"]
        disallow_list = []

        stmt_type, is_valid, error_msg = validate_sql_statement(
            unknown_query, allow_list, disallow_list
        )

        assert is_valid is False
        # Note: The query might be detected as 'Alias' or other type, so check for general patterns
        assert (
            "is not permitted" in error_msg
        ), f"Error should indicate not permitted: {error_msg}"

        # Test LATERAL-specific suggestions (this should actually be allowed by our fix)
        lateral_query = (
            "SELECT * FROM table1, LATERAL FLATTEN(input => variant_col) col"
        )
        stmt_type, is_valid, error_msg = validate_sql_statement(
            lateral_query, allow_list, disallow_list
        )

        # This should now be allowed due to our LATERAL fix
        assert is_valid is True, "LATERAL query should be allowed after our fix"

    def test_structured_error_information(self):
        """Test that structured error information is properly formatted."""
        delete_query = "DELETE FROM table1 WHERE id = 1"

        allow_list = ["Select"]
        disallow_list = []

        stmt_type, is_valid, error_msg = validate_sql_statement(
            delete_query, allow_list, disallow_list
        )

        assert is_valid is False
        assert stmt_type == "Delete"
        assert "Safe alternatives:" in error_msg
        assert "soft_delete:" in error_msg
        assert "create_view:" in error_msg

    def test_with_cte_queries_allowed(self):
        """Test that WITH (CTE) queries are properly handled."""
        cte_queries = [
            """WITH monthly_revenue AS (
                SELECT month, SUM(amount) as total
                FROM sales
                GROUP BY month
            )
            SELECT month, total FROM monthly_revenue""",
            """WITH RECURSIVE hierarchy AS (
                SELECT id, parent_id, name, 1 as level
                FROM categories
                WHERE parent_id IS NULL
                UNION ALL
                SELECT c.id, c.parent_id, c.name, h.level + 1
                FROM categories c
                JOIN hierarchy h ON c.parent_id = h.id
            )
            SELECT * FROM hierarchy""",
        ]

        allow_list = ["Select"]
        disallow_list = []

        for query in cte_queries:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, allow_list, disallow_list
            )

            assert is_valid is True, f"CTE query should be allowed: {query}"
            assert (
                error_msg is None
            ), f"CTE query should not have error message: {error_msg}"

    def test_union_intersect_except_operations(self):
        """Test that set operations (UNION, INTERSECT, EXCEPT) work correctly."""
        set_operations = [
            "SELECT id FROM table1 UNION SELECT id FROM table2",
            "SELECT id FROM table1 UNION ALL SELECT id FROM table2",
            "SELECT id FROM table1 INTERSECT SELECT id FROM table2",
            "SELECT id FROM table1 EXCEPT SELECT id FROM table2",
            "SELECT id FROM table1 MINUS SELECT id FROM table2",  # Oracle-style
        ]

        allow_list = ["Select"]
        disallow_list = []

        for query in set_operations:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, allow_list, disallow_list
            )

            assert is_valid is True, f"Set operation should be allowed: {query}"
            assert (
                error_msg is None
            ), f"Set operation should not have error message: {error_msg}"

    def test_multiple_statements_blocked(self):
        """Ensure multiple statements in a single payload are rejected."""
        multi_statement_query = "SELECT 1; DROP TABLE sensitive_data"
        allow_list = ["Select"]
        disallow_list = ["Drop"]

        stmt_type, is_valid, error_msg = validate_sql_statement(
            multi_statement_query, allow_list, disallow_list
        )

        assert is_valid is False
        assert stmt_type == "MultipleStatements"
        assert "Multiple SQL statements" in error_msg

    def test_fallback_handles_unknown_select_like_queries(self, monkeypatch):
        """Parser misclassifications should still allow SELECT-like statements."""

        monkeypatch.setattr(sv, "HAS_SQLGLOT", True)
        monkeypatch.setattr(
            sv,
            "validate_sql_type",
            lambda statement, allow, disallow: ("Unknown", False),
        )

        class _StubExpression:
            key = "select"

            def walk(self):
                return []

        stub_sqlglot = types.SimpleNamespace(
            parse=lambda sql, dialect=None: [_StubExpression()]
        )
        monkeypatch.setattr(sv, "sqlglot", stub_sqlglot)
        monkeypatch.setattr(
            sv, "_is_select_like_statement", lambda statement, parsed=None: True
        )

        stmt_type, is_valid, error_msg = sv.validate_sql_statement(
            "SELECT 42", ["select"], []
        )

        assert stmt_type == "Select"
        assert is_valid is True
        assert error_msg is None

    def test_validation_without_sqlglot_keeps_alternatives(self, monkeypatch):
        """When sqlglot is unavailable we still surface safe alternatives."""

        monkeypatch.setattr(sv, "HAS_SQLGLOT", False)
        monkeypatch.setattr(
            sv,
            "validate_sql_type",
            lambda statement, allow, disallow: ("Delete", False),
        )

        stmt_type, is_valid, error_msg = sv.validate_sql_statement(
            "DELETE FROM important", ["select"], ["delete"]
        )

        assert stmt_type == "Delete"
        assert is_valid is False
        assert error_msg is not None
        assert "Safe alternatives" in error_msg

    def test_block_comment_with_keywords_ignored(self):
        """Ensure block comments containing keywords do not trigger false positives."""
        query = (
            "SELECT id FROM users /* UNION SELECT password FROM admins */ "
            "WHERE active = 1"
        )
        allow_list = ["Select"]
        disallow_list: list[str] = []

        stmt_type, is_valid, error_msg = validate_sql_statement(
            query, allow_list, disallow_list
        )

        assert is_valid is True
        assert stmt_type == "Select"
        assert error_msg is None

    def test_blocked_operations_still_blocked(self):
        """Test that dangerous operations are still properly blocked."""
        blocked_queries = [
            "DELETE FROM table1",
            "DROP TABLE table1",
            "TRUNCATE TABLE table1",
            "UPDATE table1 SET col = 'value'",
            "INSERT INTO table1 VALUES (1, 'test')",
        ]

        allow_list = ["Select"]
        disallow_list = ["Delete", "Drop", "Truncate", "Update", "Insert"]

        for query in blocked_queries:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, allow_list, disallow_list
            )

            assert is_valid is False, f"Blocked operation should be rejected: {query}"
            assert error_msg is not None, "Blocked operation should have error message"
            assert (
                "Safe alternatives:" in error_msg or "SQL statement type" in error_msg
            )

    def test_complex_snowflake_patterns(self):
        """Test complex Snowflake-specific SQL patterns."""
        # Use a simpler, valid LATERAL pattern that should work
        snowflake_patterns = [
            """SELECT user_id, event_data.event_name
            FROM user_events ue
            , LATERAL FLATTEN(input => ue.event_properties) event_data
            WHERE event_data.key = 'page_name'""",
        ]

        allow_list = ["Select"]
        disallow_list = []

        for query in snowflake_patterns:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, allow_list, disallow_list
            )

            assert is_valid is True, f"Snowflake pattern should be allowed: {query}"
            assert (
                error_msg is None
            ), f"Snowflake pattern should not have error message: {error_msg}"

    def test_show_statements_allowed_when_permitted(self):
        """SHOW statements should be recognized and allowed when 'show' is enabled."""
        allow_list = ["Select", "Show"]
        disallow_list: list[str] = []

        queries = [
            "SHOW TABLES;",
            "SHOW TERSE TABLES;",
            "SHOW DATABASES;",
            "SHOW SCHEMAS;",
            "SHOW VIEWS;",
            "SHOW FUNCTIONS;",
            "SHOW TABLES LIKE 'MVR_PACKAGES' IN ACCOUNT;",
            "SHOW TABLES LIKE 'MVR_PACKAGES' IN DATABASE;",
        ]

        for query in queries:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, allow_list, disallow_list
            )

            assert is_valid is True, f"SHOW should be allowed: {query} -> {stmt_type}"
            assert stmt_type == "Show", f"Expected 'Show' type, got: {stmt_type}"
            assert error_msg is None

    def test_show_statements_blocked_when_disabled(self):
        """When 'show' is disabled, SHOW statements should be blocked with type Show."""
        allow_list = ["Select"]
        disallow_list = ["Show"]

        queries = [
            "SHOW TABLES;",
            "SHOW DATABASES;",
        ]

        for query in queries:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, allow_list, disallow_list
            )

            assert is_valid is False
            assert stmt_type == "Show"
            assert error_msg is not None and "not permitted" in error_msg

    def test_show_statements_disallow_overrides_allow(self):
        """Explicit disallow entries should override allow list membership for SHOW."""
        allow_list = ["Select", "Show"]
        disallow_list = ["Show"]

        stmt_type, is_valid, error_msg = validate_sql_statement(
            "SHOW ROLES;", allow_list, disallow_list
        )

        assert is_valid is False
        assert stmt_type == "Show"
        assert error_msg is not None and "not permitted" in error_msg
