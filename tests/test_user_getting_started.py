"""Tests for user getting started process and documentation accuracy.

These tests verify that the getting started documentation accurately reflects
the actual behavior and that new users can successfully complete the setup process.
"""

# pylint: disable=redefined-outer-name

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from igloo_mcp.mcp_server import main


class TestGettingStartedProcess:
    """Test the complete user getting started process."""

    def test_installation_and_basic_setup(self):
        """Test that igloo-mcp can be imported and basic functionality works."""
        # Test that core modules can be imported
        from igloo_mcp.config import Config

        # Test that basic config creation works
        config = Config.from_env()
        assert config is not None
        assert hasattr(config, "snowflake")

    def test_snowflake_cli_profile_setup(self, mock_config_with_profiles):
        """Test that Snowflake CLI profile setup works as documented."""
        from igloo_mcp.profile_utils import validate_and_resolve_profile

        with mock_config_with_profiles(["dev", "prod"], default="dev"), patch.dict(os.environ, {}, clear=True):
            # Test profile validation as documented in getting started
            profile = validate_and_resolve_profile()
            assert profile == "dev"

    def test_mcp_server_startup_with_valid_profile(self, mock_config_with_profiles):
        """Test that MCP server can start with a valid profile."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            with patch.dict(os.environ, {"SNOWFLAKE_PROFILE": "dev"}):
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
                                assert True  # If we get here, startup succeeded
                            except SystemExit:
                                pytest.fail("MCP server should start with valid profile")

    def test_mcp_server_startup_fails_without_profile(self, mock_empty_config):
        """Test that MCP server fails gracefully without profiles."""
        with mock_empty_config(), patch.dict(os.environ, {}, clear=True):
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

    def test_snowflake_cli_wrapper_functionality(self):
        """Test that SnowCLI wrapper works as expected."""
        from igloo_mcp.snow_cli import SnowCLI

        with patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow"):
            cli = SnowCLI(profile="test")
            assert cli.profile == "test"

    def test_config_precedence_as_documented(self, mock_config_with_profiles):
        """Test that configuration precedence works as documented."""
        from igloo_mcp.profile_utils import validate_and_resolve_profile

        with mock_config_with_profiles(["dev", "prod"], default="prod"):
            # Test environment variable precedence
            with patch.dict(os.environ, {"SNOWFLAKE_PROFILE": "dev"}):
                profile = validate_and_resolve_profile()
                assert profile == "dev"

            # Test fallback to default
            with patch.dict(os.environ, {}, clear=True):
                profile = validate_and_resolve_profile()
                assert profile == "prod"


class TestDocumentationAccuracy:
    """Test that documentation examples actually work."""

    def test_readme_examples_work(self, mock_config_with_profiles):
        """Test that examples in README actually work."""
        from igloo_mcp.profile_utils import validate_and_resolve_profile

        with mock_config_with_profiles(["quickstart"], default="quickstart"):
            # Test the basic profile setup example
            with patch.dict(os.environ, {"SNOWFLAKE_PROFILE": "quickstart"}):
                profile = validate_and_resolve_profile()
                assert profile == "quickstart"

    def test_mcp_json_configuration_format(self):
        """Test that MCP JSON configuration format is valid."""
        # Test the documented MCP configuration format
        mcp_config = {
            "mcpServers": {
                "igloo-mcp": {
                    "command": "igloo-mcp",
                    "args": ["--profile", "quickstart"],
                    "env": {"SNOWFLAKE_PROFILE": "quickstart"},
                }
            }
        }

        # Verify the structure is correct
        assert "mcpServers" in mcp_config
        assert "igloo-mcp" in mcp_config["mcpServers"]
        assert mcp_config["mcpServers"]["igloo-mcp"]["command"] == "igloo-mcp"
        assert "--profile" in mcp_config["mcpServers"]["igloo-mcp"]["args"]
        assert "SNOWFLAKE_PROFILE" in mcp_config["mcpServers"]["igloo-mcp"]["env"]

    def test_error_messages_are_helpful(self, mock_config_with_profiles):
        """Test that error messages provide helpful guidance."""
        from igloo_mcp.profile_utils import validate_and_resolve_profile

        with mock_config_with_profiles(["dev", "prod"], default="dev"), patch.dict(os.environ, {}, clear=True):
            # This should work with default profile
            profile = validate_and_resolve_profile()
            assert profile == "dev"

            # Test error case with invalid profile
            with patch.dict(os.environ, {"SNOWFLAKE_PROFILE": "invalid"}):
                with pytest.raises(Exception) as exc_info:
                    validate_and_resolve_profile()

                error_msg = str(exc_info.value)
                # Should mention available profiles or setup instructions
                assert any(keyword in error_msg.lower() for keyword in ["profile", "snowflake", "connection", "setup"])


class TestNewUserExperience:
    """Test the experience of a completely new user."""

    def test_new_user_without_snowflake_cli(self, mock_empty_config):
        """Test experience when user hasn't set up Snowflake CLI."""
        from igloo_mcp.profile_utils import validate_and_resolve_profile

        with mock_empty_config(), patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception) as exc_info:
                validate_and_resolve_profile()

            error_msg = str(exc_info.value)
            # Should provide guidance on setting up Snowflake CLI
            assert any(keyword in error_msg.lower() for keyword in ["snowflake", "profile", "connection", "add"])

    def test_new_user_with_invalid_profile(self, mock_config_with_profiles):
        """Test experience when user specifies invalid profile."""
        from igloo_mcp.profile_utils import validate_and_resolve_profile

        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            with patch.dict(os.environ, {"SNOWFLAKE_PROFILE": "invalid"}):
                with pytest.raises(Exception) as exc_info:
                    validate_and_resolve_profile()

                error_msg = str(exc_info.value)
                # Should list available profiles
                assert "dev" in error_msg or "prod" in error_msg

    def test_new_user_without_default_profile(self, mock_config_with_profiles):
        """Test experience when no default profile is set."""
        from igloo_mcp.profile_utils import validate_and_resolve_profile

        with mock_config_with_profiles(["dev", "prod"], default=None), patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception) as exc_info:
                validate_and_resolve_profile()

            error_msg = str(exc_info.value)
            # Should suggest setting SNOWFLAKE_PROFILE
            assert "SNOWFLAKE_PROFILE" in error_msg


# Fixtures (reuse from test_config.py)
@pytest.fixture
def mock_config_with_profiles():
    """Mock configuration with specified profiles."""

    def _mock(profiles: list[str], default: str | None = None):
        config_data: dict[str, dict[str, dict] | str] = {"connections": {profile: {} for profile in profiles}}
        if default:
            config_data["default_connection_name"] = default

        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.stat.return_value = Mock(st_mtime=123.0)

        return patch.multiple(
            "igloo_mcp.profile_utils",
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
            "igloo_mcp.profile_utils",
            get_snowflake_config_path=Mock(return_value=mock_path),
            _load_snowflake_config=Mock(return_value={"connections": {}}),
        )

    return _mock
