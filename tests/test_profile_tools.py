"""Tests for profile management MCP tools (list_profiles, switch_profile, profile_setup_guide)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from igloo_mcp import profile_utils
from igloo_mcp.config import Config, SnowflakeConfig, set_config


@pytest.fixture
def mock_config_with_profiles():
    """Mock configuration with specified profiles and connection details."""

    def _mock(profiles: list[str], default: str | None = None, details: dict | None = None):
        connections = {}
        for p in profiles:
            entry = {"account": f"{p}-account.us-east-1", "warehouse": f"{p.upper()}_WH", "user": "test_user"}
            if details and p in details:
                entry.update(details[p])
            connections[p] = entry

        config_data: dict = {"connections": connections}
        if default:
            config_data["default_connection_name"] = default

        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.stat.return_value = Mock(st_mtime=123.0)
        mock_path.__str__ = Mock(return_value="/mock/.config/snowflake/config.toml")

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
        mock_path.__str__ = Mock(return_value="/mock/.config/snowflake/config.toml")

        return patch.multiple(
            profile_utils,
            get_snowflake_config_path=Mock(return_value=mock_path),
            _load_snowflake_config=Mock(return_value={"connections": {}}),
        )

    return _mock


@pytest.fixture
def mock_no_config():
    """Mock missing configuration file."""

    def _mock():
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = False
        mock_path.__str__ = Mock(return_value="/mock/.config/snowflake/config.toml")

        return patch.multiple(
            profile_utils,
            get_snowflake_config_path=Mock(return_value=mock_path),
            _load_snowflake_config=Mock(return_value={}),
        )

    return _mock


class TestListProfilesTool:
    """Tests for the ListProfilesTool."""

    @pytest.mark.anyio
    async def test_list_profiles_with_details(self, mock_config_with_profiles):
        """Test listing profiles with connection details."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            config = Config(snowflake=SnowflakeConfig(profile="dev"))
            set_config(config)

            from igloo_mcp.mcp.tools.list_profiles import ListProfilesTool

            tool = ListProfilesTool(config)
            result = await tool.execute(include_details=True)

            assert result["active_profile"] == "dev"
            assert result["default_profile"] == "dev"
            assert result["profile_count"] == 2
            assert len(result["profiles"]) == 2

            # Check dev profile
            dev = next(p for p in result["profiles"] if p["name"] == "dev")
            assert dev["is_active"] is True
            assert dev["is_default"] is True
            assert "details" in dev
            assert dev["details"]["account"] == "dev-account.us-east-1"

            # Check prod profile
            prod = next(p for p in result["profiles"] if p["name"] == "prod")
            assert prod["is_active"] is False
            assert prod["is_default"] is False

    @pytest.mark.anyio
    async def test_list_profiles_without_details(self, mock_config_with_profiles):
        """Test listing profiles without connection details."""
        with mock_config_with_profiles(["dev", "staging"], default="dev"):
            config = Config(snowflake=SnowflakeConfig(profile="dev"))
            set_config(config)

            from igloo_mcp.mcp.tools.list_profiles import ListProfilesTool

            tool = ListProfilesTool(config)
            result = await tool.execute(include_details=False)

            assert result["profile_count"] == 2
            for profile in result["profiles"]:
                assert "details" not in profile

    @pytest.mark.anyio
    async def test_list_profiles_empty(self, mock_empty_config):
        """Test listing when no profiles exist."""
        with mock_empty_config():
            config = Config(snowflake=SnowflakeConfig(profile="default"))
            set_config(config)

            from igloo_mcp.mcp.tools.list_profiles import ListProfilesTool

            tool = ListProfilesTool(config)
            result = await tool.execute()

            assert result["profile_count"] == 0
            assert result["profiles"] == []

    def test_tool_metadata(self):
        """Test tool name, description, and schema."""
        config = Config(snowflake=SnowflakeConfig(profile="dev"))
        from igloo_mcp.mcp.tools.list_profiles import ListProfilesTool

        tool = ListProfilesTool(config)
        assert tool.name == "list_profiles"
        assert "profile" in tool.description.lower()
        assert tool.category == "profile"

        schema = tool.get_parameter_schema()
        assert "include_details" in schema["properties"]


class TestSwitchProfileTool:
    """Tests for the SwitchProfileTool."""

    @pytest.mark.anyio
    async def test_switch_to_valid_profile(self, mock_config_with_profiles):
        """Test switching to a valid profile."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            config = Config(snowflake=SnowflakeConfig(profile="dev"))
            set_config(config)

            from igloo_mcp.mcp.tools.switch_profile import SwitchProfileTool

            mock_service = Mock()
            tool = SwitchProfileTool(config, mock_service)
            result = await tool.execute(profile_name="prod", validate_connection=False)

            assert result["status"] == "switched"
            assert result["previous_profile"] == "dev"
            assert result["active_profile"] == "prod"
            assert os.environ.get("SNOWFLAKE_PROFILE") == "prod"

    @pytest.mark.anyio
    async def test_switch_to_same_profile(self, mock_config_with_profiles):
        """Test switching to the already-active profile."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            config = Config(snowflake=SnowflakeConfig(profile="dev"))
            set_config(config)

            from igloo_mcp.mcp.tools.switch_profile import SwitchProfileTool

            tool = SwitchProfileTool(config, Mock())
            result = await tool.execute(profile_name="dev", validate_connection=False)

            assert result["status"] == "no_change"

    @pytest.mark.anyio
    async def test_switch_to_nonexistent_profile(self, mock_config_with_profiles):
        """Test switching to a profile that doesn't exist."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            config = Config(snowflake=SnowflakeConfig(profile="dev"))
            set_config(config)

            from igloo_mcp.mcp.tools.switch_profile import SwitchProfileTool

            tool = SwitchProfileTool(config, Mock())
            result = await tool.execute(profile_name="nonexistent", validate_connection=False)

            assert result["status"] == "error"
            assert "not found" in result["error"]
            assert "dev" in result["available_profiles"]
            assert "prod" in result["available_profiles"]

    def test_tool_metadata(self):
        """Test tool name, description, and schema."""
        config = Config(snowflake=SnowflakeConfig(profile="dev"))
        from igloo_mcp.mcp.tools.switch_profile import SwitchProfileTool

        tool = SwitchProfileTool(config, Mock())
        assert tool.name == "switch_profile"
        assert "switch" in tool.description.lower()
        assert tool.category == "profile"

        schema = tool.get_parameter_schema()
        assert "profile_name" in schema["required"]


class TestProfileSetupGuideTool:
    """Tests for the ProfileSetupGuideTool."""

    @pytest.mark.anyio
    async def test_guide_no_config(self, mock_no_config):
        """Test guide when no config file exists."""
        with mock_no_config():
            config = Config(snowflake=SnowflakeConfig(profile="default"))

            from igloo_mcp.mcp.tools.profile_setup_guide import ProfileSetupGuideTool

            tool = ProfileSetupGuideTool(config)
            result = await tool.execute()

            assert result["current_state"]["status"] == "no_config"
            assert result["current_state"]["needs_setup"] is True
            assert "steps" in result["guide"]

    @pytest.mark.anyio
    async def test_guide_no_profiles(self, mock_empty_config):
        """Test guide when config exists but no profiles defined."""
        with mock_empty_config():
            config = Config(snowflake=SnowflakeConfig(profile="default"))

            from igloo_mcp.mcp.tools.profile_setup_guide import ProfileSetupGuideTool

            tool = ProfileSetupGuideTool(config)
            result = await tool.execute()

            assert result["current_state"]["status"] == "no_profiles"

    @pytest.mark.anyio
    async def test_guide_configured(self, mock_config_with_profiles):
        """Test guide when profiles are properly configured."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            config = Config(snowflake=SnowflakeConfig(profile="dev"))

            from igloo_mcp.mcp.tools.profile_setup_guide import ProfileSetupGuideTool

            tool = ProfileSetupGuideTool(config)
            result = await tool.execute()

            assert result["current_state"]["status"] == "configured"
            assert result["current_state"]["needs_setup"] is False

    @pytest.mark.anyio
    async def test_guide_sso_topic(self, mock_config_with_profiles):
        """Test SSO-specific guide."""
        with mock_config_with_profiles(["dev"], default="dev"):
            config = Config(snowflake=SnowflakeConfig(profile="dev"))

            from igloo_mcp.mcp.tools.profile_setup_guide import ProfileSetupGuideTool

            tool = ProfileSetupGuideTool(config)
            result = await tool.execute(topic="sso")

            assert "SSO" in result["guide"]["title"]
            assert "steps" in result["guide"]

    @pytest.mark.anyio
    async def test_guide_keypair_topic(self, mock_config_with_profiles):
        """Test keypair-specific guide."""
        with mock_config_with_profiles(["dev"], default="dev"):
            config = Config(snowflake=SnowflakeConfig(profile="dev"))

            from igloo_mcp.mcp.tools.profile_setup_guide import ProfileSetupGuideTool

            tool = ProfileSetupGuideTool(config)
            result = await tool.execute(topic="keypair")

            assert "Key-Pair" in result["guide"]["title"]

    @pytest.mark.anyio
    async def test_guide_troubleshooting(self, mock_config_with_profiles):
        """Test troubleshooting guide."""
        with mock_config_with_profiles(["dev"], default="dev"):
            config = Config(snowflake=SnowflakeConfig(profile="dev"))

            from igloo_mcp.mcp.tools.profile_setup_guide import ProfileSetupGuideTool

            tool = ProfileSetupGuideTool(config)
            result = await tool.execute(topic="troubleshooting")

            assert "common_issues" in result["guide"]
            assert len(result["guide"]["common_issues"]) > 0

    def test_tool_metadata(self):
        """Test tool name, description, and schema."""
        config = Config(snowflake=SnowflakeConfig(profile="dev"))

        from igloo_mcp.mcp.tools.profile_setup_guide import ProfileSetupGuideTool

        tool = ProfileSetupGuideTool(config)
        assert tool.name == "profile_setup_guide"
        assert tool.category == "profile"

        schema = tool.get_parameter_schema()
        assert "topic" in schema["properties"]
        assert "enum" in schema["properties"]["topic"]


class TestProfileUtilsNew:
    """Tests for new profile_utils functions."""

    def test_get_profile_details(self, mock_config_with_profiles):
        """Test getting details for a specific profile."""
        with mock_config_with_profiles(
            ["dev"],
            default="dev",
            details={"dev": {"authenticator": "externalbrowser"}},
        ):
            from igloo_mcp.profile_utils import get_profile_details

            details = get_profile_details("dev")
            assert details["account"] == "dev-account.us-east-1"
            assert details["warehouse"] == "DEV_WH"
            assert details["user"] == "test_user"
            assert details["authenticator"] == "externalbrowser"

    def test_get_profile_details_not_found(self, mock_config_with_profiles):
        """Test getting details for a nonexistent profile."""
        with mock_config_with_profiles(["dev"], default="dev"):
            from igloo_mcp.profile_utils import get_profile_details

            details = get_profile_details("nonexistent")
            assert details == {}

    def test_get_all_profile_details(self, mock_config_with_profiles):
        """Test getting details for all profiles."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            from igloo_mcp.profile_utils import get_all_profile_details

            all_details = get_all_profile_details()
            assert "dev" in all_details
            assert "prod" in all_details
            assert all_details["dev"]["account"] == "dev-account.us-east-1"
            assert all_details["prod"]["account"] == "prod-account.us-east-1"

    def test_get_config_file_mtime(self, mock_config_with_profiles):
        """Test getting config file mtime."""
        with mock_config_with_profiles(["dev"], default="dev"):
            from igloo_mcp.profile_utils import get_config_file_mtime

            mtime = get_config_file_mtime()
            assert mtime == 123.0

    def test_get_config_file_mtime_no_file(self, mock_no_config):
        """Test getting config file mtime when file doesn't exist."""
        with mock_no_config():
            from igloo_mcp.profile_utils import get_config_file_mtime

            mtime = get_config_file_mtime()
            assert mtime is None


class TestConfigChangeDetection:
    """Tests for config file change detection in health monitor."""

    def test_has_config_changed_detects_change(self):
        """Test that mtime change is detected."""
        from igloo_mcp.mcp_health import MCPHealthMonitor

        monitor = MCPHealthMonitor()
        monitor._last_config_mtime = 100.0

        with patch("igloo_mcp.mcp_health.get_config_file_mtime", return_value=200.0):
            assert monitor.has_config_changed() is True
            # After detection, mtime is updated
            assert monitor._last_config_mtime == 200.0

    def test_has_config_changed_no_change(self):
        """Test that same mtime is not flagged as change."""
        from igloo_mcp.mcp_health import MCPHealthMonitor

        monitor = MCPHealthMonitor()
        monitor._last_config_mtime = 100.0

        with patch("igloo_mcp.mcp_health.get_config_file_mtime", return_value=100.0):
            assert monitor.has_config_changed() is False


class TestGracefulStartupFallback:
    """Tests for graceful startup fallback."""

    def test_attempt_profile_fallback_finds_valid(self, mock_config_with_profiles):
        """Test fallback finds a valid profile."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            from igloo_mcp.mcp_server import _attempt_profile_fallback

            result = _attempt_profile_fallback(["dev", "prod"])
            assert result == "dev"

    def test_attempt_profile_fallback_no_profiles(self):
        """Test fallback with no available profiles."""
        from igloo_mcp.mcp_server import _attempt_profile_fallback

        with patch("igloo_mcp.mcp_server.get_available_profiles", return_value=set()):
            result = _attempt_profile_fallback([])
            assert result is None

    def test_attempt_profile_fallback_none_input(self):
        """Test fallback with None input."""
        from igloo_mcp.mcp_server import _attempt_profile_fallback

        with patch("igloo_mcp.mcp_server.get_available_profiles", return_value=set()):
            result = _attempt_profile_fallback(None)
            assert result is None
