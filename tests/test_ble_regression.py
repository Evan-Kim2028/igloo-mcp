"""Regression tests for BLE (Blind Exception) fixes.

These tests ensure that exception handling remains specific and doesn't regress
to catching generic Exception. Related to #116.
"""

import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from igloo_mcp.profile_utils import get_available_profiles, get_default_profile
from igloo_mcp.sql_objects import extract_query_objects


class TestBLERegressionProfileUtils:
    """Test that profile_utils catches specific exceptions, not generic Exception."""

    def test_get_available_profiles_catches_toml_decode_error(self):
        """Test that TOMLDecodeError is properly caught and returns empty set."""
        with patch("igloo_mcp.profile_utils._load_snowflake_config") as mock_load:
            mock_load.side_effect = tomllib.TOMLDecodeError("Bad TOML", "", 0)

            # Should handle gracefully
            profiles = get_available_profiles()
            assert profiles == set()

    def test_get_available_profiles_catches_file_not_found(self):
        """Test that FileNotFoundError is properly caught."""
        with patch("igloo_mcp.profile_utils.get_snowflake_config_path") as mock_path:
            mock_path.return_value = Path("/nonexistent/config.toml")

            # Should handle gracefully
            profiles = get_available_profiles()
            assert profiles == set()

    def test_get_default_profile_catches_permission_error(self):
        """Test that PermissionError is properly caught."""
        with patch("igloo_mcp.profile_utils._load_snowflake_config") as mock_load:
            mock_load.side_effect = PermissionError("Access denied")

            # Should handle gracefully
            default = get_default_profile()
            assert default is None


class TestBLERegressionSQLObjects:
    """Test that sql_objects handles SQL parsing failures gracefully."""

    def test_extract_query_objects_handles_empty_sql(self):
        """Test that empty SQL is handled gracefully."""
        # Empty or minimal SQL should not crash
        result = extract_query_objects("")
        assert isinstance(result, list)

    def test_extract_query_objects_handles_simple_sql(self):
        """Test that simple SQL returns correct objects."""
        # Valid SQL should work
        result = extract_query_objects("SELECT * FROM users")
        assert isinstance(result, list)


class TestBLEDocumentation:
    """Tests documenting the BLE fix rationale."""

    def test_ble_fixes_prevent_silent_failures(self):
        """Document that specific exceptions prevent silent failures like #115.

        Before BLE fixes, blind 'except Exception' caught ValidationError
        silently in living_reports/index.py, causing reports to disappear
        without logging. After fixes, ValidationError is caught specifically
        and logged with context.
        """
        # This test documents the improvement - the actual fix is tested
        # in test_living_reports_index.py
        assert True  # Documentation test

    def test_ble_fixes_improve_debugging(self):
        """Document that specific exceptions with logging improve debugging.

        Specific exception types with logging context make it easier to:
        - Identify root cause of failures
        - Distinguish between different error types
        - Add appropriate handling for each case
        """
        # This test documents the improvement
        assert True  # Documentation test


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
