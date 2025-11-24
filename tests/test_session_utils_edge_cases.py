"""Edge case tests for session_utils functionality.

Tests edge cases like Unicode handling, concurrent modifications,
malformed data, and boundary conditions.
"""

from __future__ import annotations

import threading
from unittest.mock import Mock

import pytest

from igloo_mcp.session_utils import (
    SessionContext,
    SessionSnapshot,
    apply_session_context,
    quote_identifier,
    restore_session_context,
    snapshot_session,
)


class TestQuoteIdentifierEdgeCases:
    """Test quote_identifier function with edge cases."""

    def test_quote_identifier_empty_string(self):
        """Test quoting empty string."""
        assert quote_identifier("") == '""'

    def test_quote_identifier_with_quotes(self):
        """Test quoting strings containing quotes."""
        assert quote_identifier('table"name') == '"table""name"'
        assert quote_identifier('"quoted"') == '"""quoted"""'

    def test_quote_identifier_with_special_characters(self):
        """Test quoting strings with special characters."""
        assert quote_identifier("table-name") == '"table-name"'
        assert quote_identifier("table.name") == '"table.name"'
        assert quote_identifier("table name") == '"table name"'

    def test_quote_identifier_with_unicode(self):
        """Test quoting strings with Unicode characters."""
        assert quote_identifier("tâble_ñame") == '"tâble_ñame"'
        assert quote_identifier("表_名前") == '"表_名前"'
        assert quote_identifier("table_🌟_name") == '"table_🌟_name"'

    def test_quote_identifier_sql_injection_patterns(self):
        """Test quoting strings that might be used for SQL injection."""
        assert (
            quote_identifier("table; DROP TABLE users; --")
            == '"table; DROP TABLE users; --"'
        )
        assert quote_identifier("table' OR '1'='1") == "\"table' OR '1'='1\""

    def test_quote_identifier_long_strings(self):
        """Test quoting very long strings."""
        long_name = "a" * 1000
        expected = '"' + long_name + '"'
        assert quote_identifier(long_name) == expected


class TestSnapshotSessionEdgeCases:
    """Test snapshot_session function with edge cases."""

    def test_snapshot_session_with_none_result(self):
        """Test snapshot_session when cursor.fetchone() returns None."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None

        snapshot = snapshot_session(mock_cursor)

        assert snapshot.role is None
        assert snapshot.warehouse is None
        assert snapshot.database is None
        assert snapshot.schema is None

    def test_snapshot_session_with_tuple_result(self):
        """Test snapshot_session when cursor.fetchone() returns tuple."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ("ROLE1", "WH1", "DB1", "SCHEMA1")

        snapshot = snapshot_session(mock_cursor)

        assert snapshot.role == "ROLE1"
        assert snapshot.warehouse == "WH1"
        assert snapshot.database == "DB1"
        assert snapshot.schema == "SCHEMA1"

    def test_snapshot_session_with_short_tuple(self):
        """Test snapshot_session with tuple shorter than expected."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ("ROLE1", "WH1")

        snapshot = snapshot_session(mock_cursor)

        assert snapshot.role == "ROLE1"
        assert snapshot.warehouse == "WH1"
        assert snapshot.database is None
        assert snapshot.schema is None

    def test_snapshot_session_with_empty_tuple(self):
        """Test snapshot_session with empty tuple."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ()

        snapshot = snapshot_session(mock_cursor)

        assert snapshot.role is None
        assert snapshot.warehouse is None
        assert snapshot.database is None
        assert snapshot.schema is None

    def test_snapshot_session_with_unicode_values(self):
        """Test snapshot_session with Unicode in session values."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {
            "ROLE": "角色_🌟",
            "WAREHOUSE": "仓库_ñame",
            "DATABASE": "数据库_名前",
            "SCHEMA": "模式_name",
        }

        snapshot = snapshot_session(mock_cursor)

        assert snapshot.role == "角色_🌟"
        assert snapshot.warehouse == "仓库_ñame"
        assert snapshot.database == "数据库_名前"
        assert snapshot.schema == "模式_name"

    def test_snapshot_session_with_none_values_in_dict(self):
        """Test snapshot_session with None values in dict result."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {
            "ROLE": "ROLE1",
            "WAREHOUSE": None,
            "DATABASE": "DB1",
            "SCHEMA": None,
        }

        snapshot = snapshot_session(mock_cursor)

        assert snapshot.role == "ROLE1"
        assert snapshot.warehouse is None
        assert snapshot.database == "DB1"
        assert snapshot.schema is None


class TestApplySessionContextEdgeCases:
    """Test apply_session_context function with edge cases."""

    def test_apply_session_context_empty_context(self):
        """Test apply_session_context with empty context."""
        mock_cursor = Mock()

        # Empty SessionContext
        context = SessionContext()
        apply_session_context(mock_cursor, context)

        # Should not execute any queries
        assert mock_cursor.execute.call_count == 0

    def test_apply_session_context_none_values(self):
        """Test apply_session_context with None values."""
        mock_cursor = Mock()

        context = SessionContext(
            role="ROLE1", warehouse=None, database="DB1", schema=None
        )
        apply_session_context(mock_cursor, context)

        # Should execute only for non-None values
        assert mock_cursor.execute.call_count == 2
        calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        assert 'USE ROLE "ROLE1"' in calls
        assert 'USE DATABASE "DB1"' in calls

    def test_apply_session_context_with_mapping(self):
        """Test apply_session_context with dict mapping."""
        mock_cursor = Mock()

        context = {
            "role": "ROLE1",
            "warehouse": "WH1",
            "database": None,  # Should be ignored
            "schema": "SCHEMA1",
        }
        apply_session_context(mock_cursor, context)

        assert mock_cursor.execute.call_count == 3
        calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        assert 'USE ROLE "ROLE1"' in calls
        assert 'USE WAREHOUSE "WH1"' in calls
        assert 'USE SCHEMA "SCHEMA1"' in calls

    def test_apply_session_context_with_special_characters(self):
        """Test apply_session_context with special characters in identifiers."""
        mock_cursor = Mock()

        context = SessionContext(
            role='role"name',
            warehouse="warehouse-name",
            database="database.name",
            schema="schema name",
        )
        apply_session_context(mock_cursor, context)

        assert mock_cursor.execute.call_count == 4
        calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        assert 'USE ROLE "role""name"' in calls  # Quotes doubled
        assert 'USE WAREHOUSE "warehouse-name"' in calls
        assert 'USE DATABASE "database.name"' in calls
        assert 'USE SCHEMA "schema name"' in calls

    def test_apply_session_context_with_unicode(self):
        """Test apply_session_context with Unicode in identifiers."""
        mock_cursor = Mock()

        context = SessionContext(
            role="角色_🌟",
            warehouse="仓库_ñame",
            database="数据库_名前",
            schema="模式_name",
        )
        apply_session_context(mock_cursor, context)

        assert mock_cursor.execute.call_count == 4
        calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        assert 'USE ROLE "角色_🌟"' in calls
        assert 'USE WAREHOUSE "仓库_ñame"' in calls
        assert 'USE DATABASE "数据库_名前"' in calls
        assert 'USE SCHEMA "模式_name"' in calls


class TestRestoreSessionContextEdgeCases:
    """Test restore_session_context function with edge cases."""

    def test_restore_session_context_with_none_values(self):
        """Test restore_session_context with None values."""
        mock_cursor = Mock()

        session = SessionSnapshot(
            role="ROLE1", warehouse=None, database="DB1", schema=None
        )
        restore_session_context(mock_cursor, session)

        # Should execute only for non-None values
        assert mock_cursor.execute.call_count == 2
        calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        assert 'USE ROLE "ROLE1"' in calls
        assert 'USE DATABASE "DB1"' in calls

    def test_restore_session_context_with_mapping(self):
        """Test restore_session_context with dict mapping."""
        mock_cursor = Mock()

        session = {
            "role": "ROLE1",
            "warehouse": "WH1",
            "database": None,  # Should be ignored
            "schema": "SCHEMA1",
        }
        restore_session_context(mock_cursor, session)

        assert mock_cursor.execute.call_count == 3
        calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        assert 'USE ROLE "ROLE1"' in calls
        assert 'USE WAREHOUSE "WH1"' in calls
        assert 'USE SCHEMA "SCHEMA1"' in calls

    def test_restore_session_context_with_unicode(self):
        """Test restore_session_context with Unicode in session values."""
        mock_cursor = Mock()

        session = SessionSnapshot(
            role="角色_🌟",
            warehouse="仓库_ñame",
            database="数据库_名前",
            schema="模式_name",
        )
        restore_session_context(mock_cursor, session)

        assert mock_cursor.execute.call_count == 4
        calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        assert 'USE ROLE "角色_🌟"' in calls
        assert 'USE WAREHOUSE "仓库_ñame"' in calls
        assert 'USE DATABASE "数据库_名前"' in calls
        assert 'USE SCHEMA "模式_name"' in calls

    def test_restore_session_context_empty_session(self):
        """Test restore_session_context with empty session."""
        mock_cursor = Mock()

        session = SessionSnapshot()
        restore_session_context(mock_cursor, session)

        # Should not execute any queries
        assert mock_cursor.execute.call_count == 0


class TestSessionContextEdgeCases:
    """Test SessionContext and SessionSnapshot with edge cases."""

    def test_session_context_to_mapping_with_nones(self):
        """Test to_mapping excludes None values."""
        context = SessionContext(
            role="ROLE1", warehouse=None, database="DB1", schema=None
        )

        mapping = context.to_mapping()

        expected = {"role": "ROLE1", "database": "DB1"}
        assert mapping == expected

    def test_session_context_to_mapping_all_nones(self):
        """Test to_mapping with all None values."""
        context = SessionContext()
        mapping = context.to_mapping()
        assert mapping == {}

    def test_session_context_to_mapping_with_unicode(self):
        """Test to_mapping preserves Unicode values."""
        context = SessionContext(
            role="角色_🌟",
            warehouse="仓库_ñame",
            database="数据库_名前",
            schema="模式_name",
        )

        mapping = context.to_mapping()

        expected = {
            "role": "角色_🌟",
            "warehouse": "仓库_ñame",
            "database": "数据库_名前",
            "schema": "模式_name",
        }
        assert mapping == expected

    def test_session_context_frozen_behavior(self):
        """Test that SessionContext is frozen and cannot be modified."""
        context = SessionContext(role="ROLE1")

        # Should be able to access attributes
        assert context.role == "ROLE1"

        # Should not be able to modify
        with pytest.raises(AttributeError):
            context.role = "ROLE2"

    def test_concurrent_session_context_usage(self):
        """Test concurrent access to session context objects."""
        context = SessionContext(
            role="ROLE1", warehouse="WH1", database="DB1", schema="SCHEMA1"
        )

        results = []

        def access_context():
            # Test concurrent access to to_mapping
            mapping = context.to_mapping()
            results.append(mapping)

        threads = []
        for _ in range(10):
            thread = threading.Thread(target=access_context)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All threads should produce the same result
        expected = {
            "role": "ROLE1",
            "warehouse": "WH1",
            "database": "DB1",
            "schema": "SCHEMA1",
        }
        assert all(result == expected for result in results)
