"""Tests for obscure SQL pattern validation.

Tests complex and edge case SQL patterns that might cause validation issues.
"""

from __future__ import annotations


from igloo_mcp.sql_validation import validate_sql_statement


class TestNestedCTEs:
    """Test validation of deeply nested CTEs."""

    def test_deeply_nested_ctes_5_levels(self):
        """Test 5-level nested CTE structure."""
        sql = """
        WITH level1 AS (
            SELECT 1 as id, 'level1' as name
        ),
        level2 AS (
            SELECT l1.id, l1.name, 'level2' as level
            FROM level1 l1
        ),
        level3 AS (
            SELECT l2.id, l2.name, l2.level, 'level3' as next_level
            FROM level2 l2
        ),
        level4 AS (
            SELECT l3.id, l3.name, l3.level, l3.next_level, 'level4' as final_level
            FROM level3 l3
        ),
        level5 AS (
            SELECT l4.id, l4.name, l4.level, l4.next_level, l4.final_level, 'level5' as deepest
            FROM level4 l4
        )
        SELECT * FROM level5
        """

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None

    def test_deeply_nested_ctes_10_levels(self):
        """Test 10-level nested CTE structure."""
        # Build a 10-level CTE chain
        cte_parts = []
        for i in range(1, 11):
            if i == 1:
                cte_parts.append(f"level{i} AS (SELECT {i} as level)")
            else:
                prev = f"level{i-1}"
                cte_parts.append(
                    f"level{i} AS (SELECT l.level + 1 as level FROM {prev} l)"
                )

        sql = f"WITH {', '.join(cte_parts)} SELECT * FROM level10"

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None

    def test_nested_ctes_with_complex_joins(self):
        """Test nested CTEs with complex joins and aggregations."""
        sql = """
        WITH sales_summary AS (
            SELECT customer_id, SUM(amount) as total_sales
            FROM sales
            GROUP BY customer_id
        ),
        customer_ranks AS (
            SELECT customer_id, total_sales,
                   RANK() OVER (ORDER BY total_sales DESC) as sales_rank
            FROM sales_summary
        ),
        top_customers AS (
            SELECT cr.customer_id, cr.total_sales, cr.sales_rank,
                   c.customer_name, c.region
            FROM customer_ranks cr
            JOIN customers c ON cr.customer_id = c.customer_id
            WHERE cr.sales_rank <= 10
        ),
        regional_summary AS (
            SELECT region, COUNT(*) as customer_count,
                   SUM(total_sales) as regional_sales
            FROM top_customers
            GROUP BY region
        )
        SELECT * FROM regional_summary
        ORDER BY regional_sales DESC
        """

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None


class TestComplexLateralFlatten:
    """Test validation of complex LATERAL FLATTEN scenarios."""

    def test_lateral_flatten_with_nested_arrays(self):
        """Test LATERAL FLATTEN on nested array structures."""
        sql = """
        SELECT parent.id,
               flat.value,
               flat.index,
               flat.path
        FROM (
            SELECT 1 as id, ARRAY_CONSTRUCT(1, 2, ARRAY_CONSTRUCT(3, 4)) as nested_array
        ) parent,
        LATERAL FLATTEN(parent.nested_array) flat
        """

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None

    def test_multiple_lateral_flatten_operations(self):
        """Test multiple LATERAL FLATTEN operations in one query."""
        sql = """
        SELECT p.id,
               users.value as user_name,
               orders.value as order_id,
               products.value as product_name
        FROM parent_data p,
        LATERAL FLATTEN(p.user_array) users,
        LATERAL FLATTEN(p.order_array) orders,
        LATERAL FLATTEN(p.product_array) products
        WHERE users.index = orders.index
          AND orders.index = products.index
        """

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None

    def test_lateral_flatten_with_path_references(self):
        """Test LATERAL FLATTEN with complex path references."""
        sql = """
        SELECT flat.value,
               flat.path,
               flat.index,
               flat.key
        FROM (
            SELECT OBJECT_CONSTRUCT(
                'users', ARRAY_CONSTRUCT(
                    OBJECT_CONSTRUCT('name', 'Alice', 'age', 30),
                    OBJECT_CONSTRUCT('name', 'Bob', 'age', 25)
                ),
                'metadata', OBJECT_CONSTRUCT('version', '1.0')
            ) as data
        ) parent,
        LATERAL FLATTEN(parent.data:users) flat
        """

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None


class TestVeryLongSQLStatements:
    """Test validation of extremely long SQL statements."""

    def test_10kb_sql_statement(self):
        """Test validation of a 10KB+ SQL statement."""
        # Create a very long SQL with extensive column references and complex expressions
        columns = []
        for i in range(500):  # Much more columns
            columns.append(f"col_{i}")
            # Add computed expressions to make it longer
            columns.append(
                f"CASE WHEN col_{i} > 0 THEN col_{i} * 2 ELSE col_{i} END as computed_{i}"
            )

        column_list = ", ".join(columns)

        # Create a very long WHERE clause with many conditions
        where_conditions = []
        for i in range(200):  # More conditions
            where_conditions.append(f"col_{i} IS NOT NULL")
            where_conditions.append(f"LENGTH(col_{i}) > 0")
            where_conditions.append(f"col_{i} != ''")

        where_clause = " AND ".join(where_conditions)

        # Add complex subqueries and JOINs to make it even longer
        subquery_parts = []
        for i in range(20):
            subquery_parts.append(
                f"""
            LEFT JOIN (
                SELECT id, SUM(amount) as total_{i}
                FROM related_table_{i}
                GROUP BY id
                HAVING COUNT(*) > 1
            ) rt_{i} ON main_table.id = rt_{i}.id
            """
            )

        joins = "".join(subquery_parts)

        sql = f"""
        SELECT {column_list}
        FROM very_wide_table main_table
        {joins}
        WHERE {where_clause}
        GROUP BY col_0, col_1, col_2
        HAVING COUNT(*) > 1
        ORDER BY col_0 DESC, col_1 ASC, col_2 DESC
        LIMIT 1000
        """

        # Ensure it's over 10KB
        assert len(sql) > 10 * 1024, f"SQL length is {len(sql)}, need > {10 * 1024}"

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None

    def test_sql_with_many_union_statements(self):
        """Test SQL with many UNION statements (10+ SELECT statements)."""
        # Create 15 SELECT statements with UNION
        union_parts = []
        for i in range(15):
            union_parts.append(f"SELECT {i} as value, 'table_{i}' as source")

        sql = "\nUNION ALL\n".join(union_parts)

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() in ["select", "union"]
        assert is_valid is True
        assert error_msg is None

    def test_sql_with_extreme_whitespace_and_comments(self):
        """Test SQL with unusual whitespace patterns and comments."""
        sql = """
        -- This is a comment
        /* Multi-line
           comment with
           lots of content */
        SELECT


            col1    ,
                col2
                    ,
                        col3 -- Inline comment
        FROM
            -- Another comment
            table1
                -- More comments
        WHERE /* condition */ col1 = 1
        -- Final comment
        """

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None


class TestCaseSensitivityEdgeCases:
    """Test case sensitivity edge cases in SQL validation."""

    def test_mixed_case_keywords(self):
        """Test SQL with mixed case keywords."""
        sql = """
        sElEcT CoL1, col2, COL3
        FrOm TaBlE1
        WhErE CoL1 = 'VaLuE'
        OrDeR By col2 DeSc
        """

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None

    def test_mixed_case_function_names(self):
        """Test SQL with mixed case function names."""
        sql = """
        SELECT CoUnT(*), MaX(col1), MiN(col2), SuM(col3)
        FROM table1
        GROUP BY CoL1
        """

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None

    def test_mixed_case_table_and_column_names(self):
        """Test SQL with mixed case identifiers (quoted)."""
        sql = """
        SELECT "CoL1", "col2", "COL3"
        FROM "TaBlE1"
        WHERE "CoL1" = 'VaLuE'
        """

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None


class TestComplexSQLConstructs:
    """Test validation of complex SQL constructs."""

    def test_recursive_cte(self):
        """Test recursive CTE validation."""
        sql = """
        WITH RECURSIVE fibonacci(n, a, b) AS (
            SELECT 1, 0, 1
            UNION ALL
            SELECT n+1, b, a+b FROM fibonacci WHERE n < 10
        )
        SELECT n, b FROM fibonacci
        """

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None

    def test_window_functions_complex(self):
        """Test complex window function validation."""
        sql = """
        SELECT employee_id, department, salary,
               RANK() OVER (PARTITION BY department ORDER BY salary DESC) as dept_rank,
               DENSE_RANK() OVER (ORDER BY salary DESC) as overall_rank,
               PERCENT_RANK() OVER (PARTITION BY department ORDER BY salary DESC) as dept_percentile,
               NTILE(4) OVER (PARTITION BY department ORDER BY salary DESC) as quartile
        FROM employees
        """

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None

    def test_pivot_unpivot_operations(self):
        """Test PIVOT and UNPIVOT operations."""
        sql = """
        SELECT *
        FROM (
            SELECT region, quarter, sales
            FROM sales_data
        ) source_table
        PIVOT (
            SUM(sales)
            FOR quarter IN ('Q1', 'Q2', 'Q3', 'Q4')
        ) pivot_table
        """

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None

    def test_complex_subquery_patterns(self):
        """Test complex subquery patterns."""
        sql = """
        SELECT *
        FROM (
            SELECT t1.id,
                   (SELECT COUNT(*) FROM table2 t2 WHERE t2.parent_id = t1.id) as child_count,
                   EXISTS(SELECT 1 FROM table3 t3 WHERE t3.ref_id = t1.id) as has_reference
            FROM table1 t1
            WHERE t1.id IN (
                SELECT DISTINCT parent_id
                FROM table2
                WHERE status = 'active'
            )
        ) filtered_data
        WHERE child_count > 0
        """

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None


class TestMalformedSQLEdgeCases:
    """Test validation of malformed SQL that might cause parsing issues."""

    def test_sql_with_unusual_characters(self):
        """Test SQL with unusual Unicode characters."""
        sql = """
        SELECT '🚀 Rocket', '🌟 Star', '🔥 Fire', '❄️ Snow' as symbols,
               'Здравствуй', 'こんにちは', '안녕하세요' as greetings
        FROM dual
        """

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None

    def test_sql_with_zero_width_characters(self):
        """Test SQL with zero-width Unicode characters that might cause issues."""
        sql = "SELECT 'normal' || '\u200b' || 'text' as sneaky_column FROM dual"

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None

    def test_sql_with_extreme_nesting(self):
        """Test SQL with extreme parentheses nesting."""
        # Create deeply nested expression
        nested_expr = "col1"
        for i in range(10):
            nested_expr = f"({nested_expr} + {i})"

        sql = f"SELECT {nested_expr} FROM table1"

        stmt_type, is_valid, error_msg = validate_sql_statement(
            sql, ["select"], ["insert", "update", "delete"]
        )

        assert stmt_type.lower() == "select"
        assert is_valid is True
        assert error_msg is None
