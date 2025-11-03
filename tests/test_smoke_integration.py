"""Smoke tests that verify integration without requiring Snowflake database.

These tests focus on the end-to-end behavior of our enhancements
using mocks and in-memory operations.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from igloo_mcp.config import Config
from igloo_mcp.logging.query_history import QueryHistory
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.sql_validation import validate_sql_statement
from tests.helpers.fake_snowflake_connector import FakeQueryPlan, FakeSnowflakeService


class TestSmokeIntegration:
    """Smoke tests for integrated functionality without database dependencies."""

    def test_complete_lateral_query_workflow(self):
        """Test complete workflow for LATERAL queries end-to-end."""

        # Step 1: SQL validation should allow LATERAL queries
        lateral_query = """SELECT fees.position_object_id, rewards.seq AS reward_index
            FROM tmp_cetus_lp_positions_calculated_enhanced_may20_2025 fees
            , LATERAL FLATTEN(input => fees.rewards_info) rewards
            WHERE fees.rewards_info IS NOT NULL AND rewards.seq < 10"""

        stmt_type, is_valid, error_msg = validate_sql_statement(
            lateral_query, ["Select"], []
        )

        assert is_valid is True, "LATERAL query validation failed in smoke test"
        assert error_msg is None, f"LATERAL query had error message: {error_msg}"
        assert stmt_type == "Select"

    def test_complete_post_query_insight_workflow(self):
        """Test complete workflow for post_query_insight feature."""

        with tempfile.TemporaryDirectory() as temp_dir:
            # Simulate git repository
            (Path(temp_dir) / ".git").mkdir()

            # Create QueryHistory in git repo (should be enabled by default)
            with patch("igloo_mcp.path_utils.find_repo_root") as mock_find:
                mock_find.return_value = Path(temp_dir)

                history = QueryHistory.from_env()
                assert (
                    history.enabled
                ), "Query history should be enabled in git repo smoke test"

                # Simulate recording query with post_query_insight
                payload = {
                    "ts": 1699999999,
                    "status": "success",
                    "profile": "simulate_test",
                    "statement_preview": "SELECT revenue_growth FROM quarterly_metrics",
                    "rowcount": 4,
                    "post_query_insight": {
                        "summary": (
                            "Q4 revenue grew 23% YoY exceeding forecast by 8 points"
                        ),
                        "key_metrics": [
                            "revenue:+23%",
                            "forecast_deviation:+8pp",
                            "market_share:+2.1%",
                        ],
                        "business_impact": (
                            "Strong performance driven by new product launches and "
                            "expanded enterprise contracts"
                        ),
                        "follow_up_needed": True,
                    },
                }

                history.record(payload)

                # Verify JSONL file was created and contains correct data
                history_file = history._path
                assert (
                    history_file.exists()
                ), "History file should be created in smoke test"

                lines = [
                    line
                    for line in history_file.read_text().splitlines()
                    if line.strip()
                ]
                assert lines, "History file should contain at least one entry"
                recorded = json.loads(lines[-1])

                # Verify post_query_insight was properly structured
                assert "post_query_insight" in recorded
                assert (
                    recorded["post_query_insight"]["summary"]
                    == payload["post_query_insight"]["summary"]
                )
                assert (
                    recorded["post_query_insight"]["key_metrics"]
                    == payload["post_query_insight"]["key_metrics"]
                )
                assert (
                    recorded["post_query_insight"]["business_impact"]
                    == payload["post_query_insight"]["business_impact"]
                )
                assert recorded["post_query_insight"]["follow_up_needed"] is True

    @pytest.mark.asyncio
    async def test_complete_query_execution_workflow_with_all_features(self):
        """Test complete query execution workflow with all enhancements."""

        config = Config.from_env()
        query_service = Mock()
        mock_rows = [{"id": i, "value": f"data_{i}"} for i in range(1500)]

        with tempfile.TemporaryDirectory() as temp_dir:
            history_file = Path(temp_dir) / "logs" / "doc.jsonl"
            artifact_root = Path(temp_dir) / "artifacts"
            cache_root = Path(temp_dir) / "cache"

            env_overrides = {
                "IGLOO_MCP_QUERY_HISTORY": str(history_file),
                "IGLOO_MCP_ARTIFACT_ROOT": str(artifact_root),
                "IGLOO_MCP_CACHE_ROOT": str(cache_root),
            }

            with patch.dict(os.environ, env_overrides, clear=False):
                complex_query = """WITH monthly_metrics AS (
                SELECT month, SUM(revenue) as total_revenue, COUNT(DISTINCT customer_id) as unique_customers
                FROM sales s
                , LATERAL FLATTEN(input => s.metadata) meta
                WHERE s.created_at >= '2023-01-01'
                GROUP BY month
            )
            SELECT
                m.month,
                m.total_revenue,
                m.unique_customers,
                prev.revenue
            FROM monthly_metrics m
            LEFT JOIN monthly_metrics prev ON m.month = DATEADD(month, 1, prev.month)
            ORDER BY m.month"""

                service = FakeSnowflakeService(
                    [
                        FakeQueryPlan(
                            statement=complex_query,
                            rows=mock_rows,
                            rowcount=1500,
                            duration=0.01,
                            sfqid="test_query_id_12345",
                        )
                    ]
                )

                tool = ExecuteQueryTool(
                    config=config,
                    snowflake_service=service,
                    query_service=query_service,
                    health_monitor=None,
                )

                result = await tool.execute(
                    statement=complex_query,
                    warehouse="ANALYTICS_WH",
                    timeout_seconds=120,
                    reason="Q4 2023 revenue analysis with customer cohort breakdown",
                    post_query_insight={
                        "summary": (
                            "Q4 showed record performance with 23% revenue growth "
                            "and improved customer acquisition"
                        ),
                        "key_metrics": [
                            "revenue:+23%",
                            "customers:+15%",
                            "avg_order_value:+8%",
                        ],
                        "business_impact": (
                            "Significant outperformance of Q4 targets, driven by "
                            "successful holiday campaign and new product launches"
                        ),
                    },
                )

                assert result["rowcount"] == 1500
                assert "query_id" in result
                assert "duration_ms" in result
                assert result["cache"]["hit"] is False
                assert result["audit_info"]["cache"]["hit"] is False

                manifest_path = Path(result["cache"]["manifest_path"])
                assert manifest_path.exists()
                assert (manifest_path.parent / "rows.jsonl").exists()

                assert history_file.exists()
                lines = history_file.read_text().strip().splitlines()
                assert len(lines) == 1
                recorded = json.loads(lines[0])
                assert recorded["status"] == "success"
                assert recorded["cache_key"]
                assert recorded["execution_id"] == result["audit_info"]["execution_id"]

                cached_result = await tool.execute(
                    statement=complex_query,
                    warehouse="ANALYTICS_WH",
                    timeout_seconds=120,
                    reason="Q4 2023 revenue analysis with customer cohort breakdown",
                )

                executed_cursors = [
                    cursor for cursor in service.cursors if cursor._main_executed
                ]
                assert len(executed_cursors) == 1
                assert service.cursors[-1]._main_executed is False
                assert cached_result["cache"]["hit"] is True
                assert cached_result["audit_info"]["cache"]["hit"] is True
                assert cached_result["rowcount"] == 1500

                lines = history_file.read_text().strip().splitlines()
                assert len(lines) == 2
                cache_entry = json.loads(lines[-1])
                assert cache_entry["status"] == "cache_hit"
                assert cache_entry["cache_key"] == recorded["cache_key"]

    def test_error_propagation_workflow(self):
        """Test error handling and propagation end-to-end."""

        # Test complete error workflow for SQL validation
        blocked_queries = [
            ("DELETE FROM users WHERE id = 1", "Delete"),
            ("DROP TABLE important_data", "Drop"),
            ("TRUNCATE TABLE logs", "Truncate"),
        ]

        for query, expected_type in blocked_queries:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                query, ["Select"], ["Delete", "Drop", "Truncate"]
            )

            assert is_valid is False, f"Blocked query should fail: {query}"
            assert (
                expected_type in stmt_type
            ), f"Should detect correct type: {stmt_type}"
            assert (
                "Safe alternatives:" in error_msg
            ), f"Should provide alternatives: {error_msg}"

    def test_repository_detection_workflow(self):
        """Test repository detection and logging workflow."""

        with tempfile.TemporaryDirectory() as temp_dir:
            # Test non-git directory (logging should still enable with workspace path)
            with (
                patch("igloo_mcp.path_utils.find_repo_root") as mock_find,
                patch("igloo_mcp.path_utils.Path.home", lambda: Path(temp_dir)),
            ):
                mock_find.return_value = Path(temp_dir)

                with patch.dict("os.environ", {}, clear=True):
                    history = QueryHistory.from_env()
                    assert (
                        history.enabled is True
                    ), "Should default to workspace history"
                    assert history.path is not None
                    expected = (
                        Path(temp_dir) / ".igloo_mcp" / "logs" / "doc.jsonl"
                    ).resolve()
                    assert history.path.resolve() == expected

            # Test git directory (logging should be enabled)
            (Path(temp_dir) / ".git").mkdir()

            with (
                patch("igloo_mcp.path_utils.find_repo_root") as mock_find,
                patch("igloo_mcp.path_utils.Path.home", lambda: Path(temp_dir)),
            ):
                mock_find.return_value = Path(temp_dir)

                with patch.dict(
                    "os.environ",
                    {"IGLOO_MCP_LOG_SCOPE": "repo"},
                    clear=True,
                ):
                    history = QueryHistory.from_env()
                    assert history.enabled is True, "Should be enabled in git repo"
                    assert history.path is not None
                    resolved = history.path.resolve()
                    assert resolved.is_relative_to(Path(temp_dir).resolve())
                    assert (
                        "logs" in resolved.as_posix()
                    ), "Should use repository-specific path"

    def test_complex_snowflake_patterns_validation(self):
        """Test validation of complex Snowflake-specific patterns."""

        snowflake_patterns = [
            # Complex LATERAL with VARIANT operations
            """SELECT
                event.user_id,
                event_data.event_name,
                event_data.properties:page_name::STRING as page_name,
                event_data.properties:session_id::STRING as session_id
            FROM (
                SELECT user_id, parse_json(event_data) as event_data
                FROM user_events
                WHERE event_date >= '2023-01-01'
            ) events
            , LATERAL FLATTEN(input => events.event_data) event
            WHERE event_data.event_name = 'page_view'""",
            # Window functions with CTE and LATERAL
            """WITH user_sessions AS (
                SELECT
                    user_id,
                    session_start,
                    LAG(session_end) OVER (PARTITION BY user_id ORDER BY session_start) as prev_session_end
                FROM user_activity
            ), session_gaps AS (
                SELECT
                    user_id,
                    session_start,
                    prev_session_end,
                    DATEDIFF(hours, prev_session_end, session_start) as gap_hours
                FROM user_sessions
                WHERE prev_session_end IS NOT NULL
            )
            SELECT user_id, AVG(gap_hours) as avg_gap_between_sessions
            FROM session_gaps
            WHERE gap_hours > 24
            GROUP BY user_id""",
        ]

        for pattern in snowflake_patterns:
            stmt_type, is_valid, error_msg = validate_sql_statement(
                pattern, ["Select"], []
            )

            assert (
                is_valid is True
            ), f"Complex Snowflake pattern should be valid: {pattern[:100]}..."
            assert (
                error_msg is None
            ), f"Complex pattern should not have error: {error_msg}"

    def test_parameter_schema_completeness(self):
        """Test that parameter schemas are complete and include all new features."""

        config = Config.from_env()
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=Mock(),
            query_service=Mock(),
            health_monitor=None,
        )

        schema = tool.get_parameter_schema()

        # Verify all expected parameters are present
        expected_params = [
            "statement",
            "warehouse",
            "database",
            "schema",
            "role",
            "timeout_seconds",
            "verbose_errors",
            "reason",
            "post_query_insight",
        ]

        for param in expected_params:
            assert (
                param in schema["properties"]
            ), f"Missing parameter in schema: {param}"

        # Verify post_query_insight schema details
        metric_schema = schema["properties"]["post_query_insight"]
        assert "anyOf" in metric_schema
        assert any(option.get("type") == "string" for option in metric_schema["anyOf"])
        assert any(option.get("type") == "object" for option in metric_schema["anyOf"])
        assert "insights" in metric_schema["description"].lower()
        assert len(metric_schema["examples"]) >= 2

        # Verify timeout validation
        timeout_schema = schema["properties"]["timeout_seconds"]
        assert timeout_schema["minimum"] == 1
        assert timeout_schema["maximum"] == 3600

    def test_joined_enhancements_integration(self):
        """Test that all enhancements work together seamlessly."""

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create simulated git repository
            (Path(temp_dir) / ".git").mkdir()
            history_file = Path(temp_dir) / "logs" / "doc.jsonl"
            history_file.parent.mkdir(exist_ok=True)

            # Create complex query that uses multiple enhancement features
            complex_lateral_query = """WITH event_patterns AS (
                SELECT
                    user_id,
                    event_type,
                    COUNT(*) as event_count,
                    LAG(event_type) OVER (PARTITION BY user_id ORDER BY created_at) as prev_event_type
                FROM user_events ue
                , LATERAL FLATTEN(input => ue.event_properties) props
                WHERE ue.created_at >= CURRENT_DATE() - 7
                AND props.key = 'page_name'
            )
            SELECT
                user_id,
                prev_event_type,
                event_type,
                event_count
            FROM event_patterns
            WHERE prev_event_type != event_type
            ORDER BY event_count DESC
            LIMIT 100"""

            # Test validation (should work)
            stmt_type, is_valid, error_msg = validate_sql_statement(
                complex_lateral_query, ["Select"], []
            )

            assert is_valid is True, "Complex integration query should validate"
            assert stmt_type == "Select"

            # Test history recording (should work)
            history = QueryHistory(history_file)

            integration_payload = {
                "ts": 1699999999,
                "status": "success",
                "profile": "integration_test",
                "statement_preview": complex_lateral_query[:200],
                "rowcount": 50,
                "reason": "User behavior pattern analysis for product recommendation improvements",
                "post_query_insight": {
                    "summary": (
                        "Users show distinct navigation patterns with 60% following "
                        "predictable paths"
                    ),
                    "key_metrics": [
                        "pattern_recognition:60%",
                        "unique_flows:25%",
                        "bounce_rate_reduction:15%",
                    ],
                    "business_impact": (
                        "Opportunity to implement intelligent navigation suggestions "
                        "and improve user journey flow"
                    ),
                },
            }

            history.record(integration_payload)

            # Verify integration recording worked
            assert history_file.exists(), "Integration history should be created"

            content = history_file.read_text()
            recorded = json.loads(content.strip())

            # All enhancement features should be present
            assert "timestamp" in recorded
            assert "reason" in recorded
            assert "post_query_insight" in recorded
            assert (
                recorded["post_query_insight"]["summary"]
                == integration_payload["post_query_insight"]["summary"]
            )
            assert recorded["statement_preview"] == complex_lateral_query[:200]
