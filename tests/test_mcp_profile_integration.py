"""Integration tests for MCP server profile validation.

Tests the complete profile validation flow during MCP server startup,
including error handling and user experience.
"""

# pylint: disable=redefined-outer-name,unused-variable

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import igloo_mcp.profile_utils as profile_utils


class TestMCPServerProfileIntegration:
    """Test MCP server integration with profile validation."""

    def test_server_startup_with_valid_profile(self, mock_config_with_profiles):
        """Test successful server startup with valid profile."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            with patch.dict(os.environ, {"SNOWFLAKE_PROFILE": "dev"}):
                from igloo_mcp.mcp_server import main

                # Mock the FastMCP server to avoid actual startup
                with patch("igloo_mcp.mcp_server.FastMCP") as mock_fastmcp:
                    with patch("igloo_mcp.mcp_server.parse_arguments") as mock_args:
                        with patch("igloo_mcp.mcp_server.configure_logging"):
                            # Configure mocks
                            mock_args.return_value = Mock(
                                log_level="INFO",
                                snowcli_config=None,
                                profile=None,
                                name="test-server",
                                instructions="test",
                                transport="stdio",
                            )
                            mock_server = Mock()
                            mock_fastmcp.return_value = mock_server

                            # Should not raise SystemExit
                            try:
                                main()
                                # If we get here, validation passed
                                assert True
                            except SystemExit:
                                pytest.fail(
                                    "Server startup should not fail with valid profile"
                                )

    def test_server_startup_fails_with_invalid_profile(self, mock_config_with_profiles):
        """Test server startup fails gracefully with invalid profile."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            with patch.dict(os.environ, {"SNOWFLAKE_PROFILE": "nonexistent"}):
                from igloo_mcp.mcp_server import main

                with patch("igloo_mcp.mcp_server.parse_arguments") as mock_args:
                    with patch("igloo_mcp.mcp_server.configure_logging"):
                        mock_args.return_value = Mock(
                            log_level="INFO",
                            snowcli_config=None,
                            profile=None,
                            name="test-server",
                            instructions="test",
                            transport="stdio",
                        )

                        # Should raise SystemExit with code 1
                        with pytest.raises(SystemExit) as exc_info:
                            main()

                        assert exc_info.value.code == 1

    def test_server_startup_fails_with_no_profiles(self, mock_empty_config):
        """Test server startup fails when no profiles exist."""
        with mock_empty_config():
            with patch.dict(os.environ, {}, clear=True):
                from igloo_mcp.mcp_server import main

                with patch("igloo_mcp.mcp_server.parse_arguments") as mock_args:
                    with patch("igloo_mcp.mcp_server.configure_logging"):
                        mock_args.return_value = Mock(
                            log_level="INFO",
                            snowcli_config=None,
                            profile=None,
                            name="test-server",
                            instructions="test",
                            transport="stdio",
                        )

                        with pytest.raises(SystemExit) as exc_info:
                            main()

                        assert exc_info.value.code == 1

    def test_profile_override_from_command_line(self, mock_config_with_profiles):
        """Test that command line profile override works."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            from igloo_mcp.mcp_server import main

            with patch("igloo_mcp.mcp_server.FastMCP") as mock_fastmcp:
                with patch("igloo_mcp.mcp_server.parse_arguments") as mock_args:
                    with patch("igloo_mcp.mcp_server.configure_logging"):
                        # Configure mocks - override profile via CLI
                        mock_args.return_value = Mock(
                            log_level="INFO",
                            snowcli_config=None,
                            profile="prod",  # Override to prod
                            warehouse=None,
                            database=None,
                            schema=None,
                            role=None,
                            name="test-server",
                            instructions="test",
                            transport="stdio",
                        )
                        mock_server = Mock()
                        mock_fastmcp.return_value = mock_server

                        # Should succeed and use prod profile
                        main()

                        # Verify profile was set correctly
                        assert os.environ.get("SNOWFLAKE_PROFILE") == "prod"


class TestMCPToolProfileCheck:
    """Test the MCP profile check tool."""

    def test_profile_check_tool_success(self, mock_config_with_profiles):
        """Test profile check tool with valid configuration."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            with patch.dict(os.environ, {"SNOWFLAKE_PROFILE": "dev"}):
                from igloo_mcp.mcp.utils import get_profile_recommendations

                # Test the recommendation function
                from igloo_mcp.profile_utils import get_profile_summary

                summary = get_profile_summary()
                assert summary.default_profile == "dev"
                assert summary.profile_count == 2
                recommendations = get_profile_recommendations("dev")

                assert isinstance(recommendations, list)
                assert len(recommendations) > 0

    def test_profile_check_tool_with_issues(self, mock_config_with_profiles):
        """Test profile check tool identifies configuration issues."""
        with mock_config_with_profiles(["dev", "prod"], default=None):  # No default
            with patch.dict(os.environ, {}, clear=True):  # No env var
                from igloo_mcp.mcp.utils import get_profile_recommendations
                from igloo_mcp.profile_utils import get_profile_summary

                summary = get_profile_summary()
                assert summary.default_profile is None
                assert summary.profile_count == 2
                recommendations = get_profile_recommendations(None)

                assert isinstance(recommendations, list)
                assert len(recommendations) > 0
                # Should suggest setting SNOWFLAKE_PROFILE
                assert any("SNOWFLAKE_PROFILE" in rec for rec in recommendations)


class TestErrorLogging:
    """Test error logging and user experience."""

    @patch("igloo_mcp.mcp_server.logger")
    def test_validation_error_logging(self, mock_logger, mock_config_with_profiles):
        """Test that validation errors are logged with helpful information."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            with patch.dict(os.environ, {"SNOWFLAKE_PROFILE": "invalid"}):
                from igloo_mcp.mcp_server import main

                with patch("igloo_mcp.mcp_server.parse_arguments") as mock_args:
                    with patch("igloo_mcp.mcp_server.configure_logging"):
                        mock_args.return_value = Mock(
                            log_level="INFO",
                            snowcli_config=None,
                            profile=None,
                            name="test-server",
                            instructions="test",
                            transport="stdio",
                        )

                        with pytest.raises(SystemExit):
                            main()

                        # Verify helpful error messages were logged
                        logged_calls = [
                            call.args[0] for call in mock_logger.error.call_args_list
                        ]
                        assert any(
                            "profile validation failed" in call.lower()
                            for call in logged_calls
                        )
                        assert any(
                            "available profiles" in call.lower()
                            for call in logged_calls
                        )

    @patch("igloo_mcp.mcp_server.logger")
    def test_no_profiles_error_logging(self, mock_logger, mock_empty_config):
        """Test logging when no profiles are configured."""
        with mock_empty_config():
            from igloo_mcp.mcp_server import main

            with patch("igloo_mcp.mcp_server.parse_arguments") as mock_args:
                with patch("igloo_mcp.mcp_server.configure_logging"):
                    mock_args.return_value = Mock(
                        log_level="INFO",
                        snowcli_config=None,
                        profile=None,
                        name="test-server",
                        instructions="test",
                        transport="stdio",
                    )

                    with pytest.raises(SystemExit):
                        main()

                    # Verify helpful error messages for no profiles scenario
                    logged_calls = [
                        call.args[0] for call in mock_logger.error.call_args_list
                    ]
                    assert any(
                        "no snowflake profiles found" in call.lower()
                        for call in logged_calls
                    )
                    assert any(
                        "snow connection add" in call.lower() for call in logged_calls
                    )


# Fixtures (reuse from test_profile_utils.py)
@pytest.fixture
def mock_config_with_profiles():
    """Mock configuration with specified profiles."""

    def _mock(profiles: list[str], default: str | None = None):
        config_data: dict[str, dict[str, dict] | str] = {
            "connections": {profile: {} for profile in profiles}
        }
        if default:
            config_data["default_connection_name"] = default

        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.stat.return_value = Mock(st_mtime=123.0)

        return patch.multiple(
            profile_utils,
            get_snowflake_config_path=Mock(return_value=mock_path),
            _load_snowflake_config=Mock(return_value=config_data),
        )

    return _mock


@pytest.fixture
def mock_empty_config():
    """Mock empty configuration (no profiles)."""

    def _mock():
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.stat.return_value = Mock(st_mtime=123.0)

        return patch.multiple(
            profile_utils,
            get_snowflake_config_path=Mock(return_value=mock_path),
            _load_snowflake_config=Mock(return_value={"connections": {}}),
        )

    return _mock
