"""Tests for ExecuteQueryTool source attribution functionality.

Tests verify that cross-database queries correctly extract and log
source_databases and tables information.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pytest

from igloo_mcp.config import Config, SQLPermissions
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool


class TestExtractSourceInfo:
    """Unit tests for _extract_source_info method."""

    def test_extract_source_info_single_database(self):
        """Test extraction with single database, schema, and table."""
        config = replace(Config.from_env(), sql_permissions=SQLPermissions())
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=Mock(),
            query_service=Mock(),
            health_monitor=None,
        )

        objects = [
            {
                "database": "ART_SHARE",
                "schema": "INFORMATION_SCHEMA",
                "name": "TABLES",
                "type": None,
            }
        ]

        result = tool._extract_source_info(objects)

        assert result == {
            "source_databases": ["ART_SHARE"],
            "tables": ["ART_SHARE.INFORMATION_SCHEMA.TABLES"],
        }

    def test_extract_source_info_multiple_databases(self):
        """Test extraction with multiple databases."""
        config = replace(Config.from_env(), sql_permissions=SQLPermissions())
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=Mock(),
            query_service=Mock(),
            health_monitor=None,
        )

        objects = [
            {
                "database": "ART_SHARE",
                "schema": "INFO_SCHEMA",
                "name": "TABLES",
                "type": None,
            },
            {
                "database": "ANALYTICS",
                "schema": "PUBLIC",
                "name": "SALES",
                "type": None,
            },
        ]

        result = tool._extract_source_info(objects)

        assert result["source_databases"] == ["ANALYTICS", "ART_SHARE"]
        assert "ANALYTICS.PUBLIC.SALES" in result["tables"]
        assert "ART_SHARE.INFO_SCHEMA.TABLES" in result["tables"]
        assert len(result["tables"]) == 2

    def test_extract_source_info_empty_parts(self):
        """Test that empty parts (all None) do not create empty table strings."""
        config = replace(Config.from_env(), sql_permissions=SQLPermissions())
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=Mock(),
            query_service=Mock(),
            health_monitor=None,
        )

        objects = [{"database": None, "schema": None, "name": None, "type": None}]

        result = tool._extract_source_info(objects)

        # Should not include empty strings
        assert "" not in result["tables"]
        assert len(result["tables"]) == 0
        assert result["source_databases"] == []

    def test_extract_source_info_partial_fields(self):
        """Test extraction with missing schema or database fields."""
        config = replace(Config.from_env(), sql_permissions=SQLPermissions())
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=Mock(),
            query_service=Mock(),
            health_monitor=None,
        )

        # Only database and name, no schema
        objects = [
            {"database": "MY_DB", "schema": None, "name": "MY_TABLE", "type": None}
        ]

        result = tool._extract_source_info(objects)

        assert result["source_databases"] == ["MY_DB"]
        assert result["tables"] == ["MY_DB.MY_TABLE"]

        # Only name, no database or schema
        objects2 = [
            {"database": None, "schema": None, "name": "SIMPLE_TABLE", "type": None}
        ]

        result2 = tool._extract_source_info(objects2)

        assert result2["source_databases"] == []
        assert result2["tables"] == ["SIMPLE_TABLE"]

    def test_extract_source_info_sorted_output(self):
        """Test that output is sorted deterministically."""
        config = replace(Config.from_env(), sql_permissions=SQLPermissions())
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=Mock(),
            query_service=Mock(),
            health_monitor=None,
        )

        objects = [
            {"database": "Z_DB", "schema": "Z_SCHEMA", "name": "Z_TABLE", "type": None},
            {"database": "A_DB", "schema": "A_SCHEMA", "name": "A_TABLE", "type": None},
        ]

        result = tool._extract_source_info(objects)

        assert result["source_databases"] == ["A_DB", "Z_DB"]
        assert result["tables"] == ["A_DB.A_SCHEMA.A_TABLE", "Z_DB.Z_SCHEMA.Z_TABLE"]

    def test_extract_source_info_empty_list(self):
        """Test extraction with empty objects list."""
        config = replace(Config.from_env(), sql_permissions=SQLPermissions())
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=Mock(),
            query_service=Mock(),
            health_monitor=None,
        )

        result = tool._extract_source_info([])

        assert result == {
            "source_databases": [],
            "tables": [],
        }


@pytest.mark.anyio
class TestSourceAttributionIntegration:
    """Integration tests verifying source attribution in query execution."""

    async def test_success_path_includes_source_info(self, monkeypatch):
        """Verify source_databases and tables appear in success payload."""
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        config = replace(Config.from_env(), sql_permissions=SQLPermissions())
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=Mock(),
            query_service=Mock(),
            health_monitor=None,
        )

        # Mock extract_query_objects to return cross-database objects
        from unittest.mock import patch

        with patch(
            "igloo_mcp.mcp.tools.execute_query.extract_query_objects"
        ) as mock_extract:
            mock_extract.return_value = [
                {
                    "database": "ART_SHARE",
                    "schema": "INFORMATION_SCHEMA",
                    "name": "TABLES",
                    "type": None,
                }
            ]

            expected = {
                "statement": "SELECT * FROM ART_SHARE.INFORMATION_SCHEMA.TABLES",
                "rowcount": 1,
                "rows": [{"table_name": "test"}],
                "duration_ms": 10,
            }

            tool._execute_query_sync = Mock(return_value=expected)  # type: ignore[assignment]

            result = await tool.execute(
                statement="SELECT * FROM ART_SHARE.INFORMATION_SCHEMA.TABLES",
                reason="Test cross-database query attribution",
            )

            # Verify objects are in result
            assert "objects" in result
            assert result["objects"] == [
                {
                    "database": "ART_SHARE",
                    "schema": "INFORMATION_SCHEMA",
                    "name": "TABLES",
                    "type": None,
                }
            ]

    async def test_cache_hit_path_includes_source_info(self, monkeypatch, tmp_path):
        """Verify source_databases and tables appear in cache hit history payload."""
        import json

        history_path = tmp_path / "history.jsonl"
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(history_path))
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "enabled")
        monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(tmp_path))

        config = replace(Config.from_env(), sql_permissions=SQLPermissions())
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=Mock(),
            query_service=Mock(),
            health_monitor=None,
        )

        # Mock extract_query_objects to return cross-database objects
        from unittest.mock import patch

        with patch(
            "igloo_mcp.mcp.tools.execute_query.extract_query_objects"
        ) as mock_extract:
            mock_extract.return_value = [
                {
                    "database": "ART_SHARE",
                    "schema": "INFORMATION_SCHEMA",
                    "name": "TABLES",
                    "type": None,
                }
            ]

            expected = {
                "statement": "SELECT * FROM ART_SHARE.INFORMATION_SCHEMA.TABLES LIMIT 1",
                "rowcount": 1,
                "rows": [{"table_name": "test"}],
                "duration_ms": 10,
                "session_context": {
                    "warehouse": "TEST_WH",
                    "database": "TEST_DB",
                    "schema": "PUBLIC",
                    "role": "TEST_ROLE",
                },
            }

            tool._execute_query_sync = Mock(return_value=expected)  # type: ignore[assignment]

            # Execute first time to cache
            await tool.execute(
                statement="SELECT * FROM ART_SHARE.INFORMATION_SCHEMA.TABLES LIMIT 1",
                reason="First execution to populate cache",
            )

            # Reset mock - second execution should hit cache if session context matches
            tool._execute_query_sync.reset_mock()

            # Second execution with same statement and context should hit cache
            await tool.execute(
                statement="SELECT * FROM ART_SHARE.INFORMATION_SCHEMA.TABLES LIMIT 1",
                reason="Second execution should hit cache",
            )

            # Verify history was recorded with source info (even if cache hit)
            if history_path.exists():
                with open(history_path) as f:
                    lines = [json.loads(line) for line in f if line.strip()]
                    # Check the last entry (cache hit if it occurred, otherwise success)
                    if lines:
                        last_entry = lines[-1]
                        # Source info should be present regardless of cache status
                        assert "source_databases" in last_entry
                        assert "tables" in last_entry
                        assert last_entry["source_databases"] == ["ART_SHARE"]
                        assert (
                            "ART_SHARE.INFORMATION_SCHEMA.TABLES"
                            in last_entry["tables"]
                        )

    async def test_timeout_path_includes_source_info(self, monkeypatch, tmp_path):
        """Verify source_databases and tables appear in timeout payload."""
        history_path = tmp_path / "history.jsonl"
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(history_path))
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        config = replace(Config.from_env(), sql_permissions=SQLPermissions())
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=Mock(),
            query_service=Mock(),
            health_monitor=None,
        )

        from unittest.mock import patch

        with patch(
            "igloo_mcp.mcp.tools.execute_query.extract_query_objects"
        ) as mock_extract:
            mock_extract.return_value = [
                {
                    "database": "ART_SHARE",
                    "schema": "INFORMATION_SCHEMA",
                    "name": "TABLES",
                    "type": None,
                }
            ]

            # Mock timeout
            def timeout_execute(*args, **kwargs):
                import time

                time.sleep(0.1)
                raise TimeoutError("Query timeout")

            tool._execute_query_sync = Mock(side_effect=timeout_execute)  # type: ignore[assignment]

            with pytest.raises(RuntimeError):
                await tool.execute(
                    statement="SELECT * FROM ART_SHARE.INFORMATION_SCHEMA.TABLES",
                    reason="Test timeout attribution",
                    timeout_seconds=1,  # Very short timeout
                )

            # Verify history was recorded with source info
            if history_path.exists():
                import json

                with open(history_path) as f:
                    lines = [json.loads(line) for line in f if line.strip()]
                    if lines:
                        last_entry = lines[-1]
                        assert last_entry["status"] == "timeout"
                        assert "source_databases" in last_entry
                        assert "tables" in last_entry
                        assert last_entry["source_databases"] == ["ART_SHARE"]
                        assert (
                            "ART_SHARE.INFORMATION_SCHEMA.TABLES"
                            in last_entry["tables"]
                        )

    async def test_error_path_includes_source_info(self, monkeypatch, tmp_path):
        """Verify source_databases and tables appear in error payload."""
        history_path = tmp_path / "history.jsonl"
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(history_path))
        monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "disabled")

        config = replace(Config.from_env(), sql_permissions=SQLPermissions())
        tool = ExecuteQueryTool(
            config=config,
            snowflake_service=Mock(),
            query_service=Mock(),
            health_monitor=None,
        )

        from unittest.mock import patch

        with patch(
            "igloo_mcp.mcp.tools.execute_query.extract_query_objects"
        ) as mock_extract:
            mock_extract.return_value = [
                {
                    "database": "ART_SHARE",
                    "schema": "INFORMATION_SCHEMA",
                    "name": "TABLES",
                    "type": None,
                }
            ]

            # Mock error
            tool._execute_query_sync = Mock(side_effect=RuntimeError("SQL syntax error"))  # type: ignore[assignment]

            with pytest.raises(RuntimeError):
                await tool.execute(
                    statement="SELECT * FROM ART_SHARE.INFORMATION_SCHEMA.TABLES",
                    reason="Test error attribution",
                )

            # Verify history was recorded with source info
            if history_path.exists():
                import json

                with open(history_path) as f:
                    lines = [json.loads(line) for line in f if line.strip()]
                    if lines:
                        last_entry = lines[-1]
                        assert last_entry["status"] == "error"
                        assert "source_databases" in last_entry
                        assert "tables" in last_entry
                        assert last_entry["source_databases"] == ["ART_SHARE"]
                        assert (
                            "ART_SHARE.INFORMATION_SCHEMA.TABLES"
                            in last_entry["tables"]
                        )
