"""Comprehensive tests for profile validation utilities.

Tests cover modern Python 3.12+ features, error handling patterns,
performance optimizations, and integration scenarios.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import igloo_mcp.profile_utils as profile_utils
from igloo_mcp.profile_utils import (
    ProfileSummary,
    ProfileValidationError,
    get_available_profiles,
    get_default_profile,
    get_profile_info,
    get_profile_summary,
    get_snowflake_config_path,
    validate_and_resolve_profile,
    validate_profile,
)


class TestProfileValidation:
    """Test profile validation functionality."""

    def test_profile_validation_with_valid_profile(self, mock_config_with_profiles):
        """Test validation succeeds with valid profile."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            result = validate_profile("dev")
            assert result == "dev"

    def test_profile_validation_with_invalid_profile(self, mock_config_with_profiles):
        """Test validation fails with invalid profile."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            with pytest.raises(ProfileValidationError) as exc_info:
                validate_profile("nonexistent")

            error = exc_info.value
            assert "nonexistent" in str(error)
            assert error.profile_name == "nonexistent"
            assert "dev" in error.available_profiles
            assert "prod" in error.available_profiles

    def test_profile_validation_with_no_profiles(self, mock_empty_config):
        """Test validation fails when no profiles exist."""
        with mock_empty_config():
            with pytest.raises(ProfileValidationError) as exc_info:
                validate_profile("any")

            error = exc_info.value
            assert "No Snowflake profiles found" in str(error)
            assert error.available_profiles == []

    def test_profile_validation_uses_default_when_none_specified(
        self, mock_config_with_profiles
    ):
        """Test validation uses default profile when none specified."""
        with mock_config_with_profiles(["dev", "prod"], default="prod"):
            result = validate_profile(None)
            assert result == "prod"

    def test_profile_validation_fails_when_no_default_and_none_specified(
        self, mock_config_with_profiles
    ):
        """Test validation fails when no profile specified and no default."""
        with mock_config_with_profiles(["dev", "prod"], default=None):
            with pytest.raises(ProfileValidationError) as exc_info:
                validate_profile(None)

            error = exc_info.value
            assert "No Snowflake profile specified" in str(error)
            assert "SNOWFLAKE_PROFILE" in str(error)


class TestProfileResolution:
    """Test profile resolution with environment precedence."""

    def test_resolve_profile_uses_environment_variable(self, mock_config_with_profiles):
        """Test that SNOWFLAKE_PROFILE env var takes precedence."""
        with mock_config_with_profiles(["dev", "prod"], default="prod"):
            with patch.dict(os.environ, {"SNOWFLAKE_PROFILE": "dev"}):
                result = validate_and_resolve_profile()
                assert result == "dev"

    def test_resolve_profile_falls_back_to_default(self, mock_config_with_profiles):
        """Test fallback to default profile when no env var."""
        with mock_config_with_profiles(["dev", "prod"], default="prod"):
            with patch.dict(os.environ, {}, clear=True):
                result = validate_and_resolve_profile()
                assert result == "prod"

    def test_resolve_profile_strips_whitespace_from_env(
        self, mock_config_with_profiles
    ):
        """Test that whitespace is stripped from environment variable."""
        with mock_config_with_profiles(["dev", "prod"], default="prod"):
            with patch.dict(os.environ, {"SNOWFLAKE_PROFILE": "  dev  "}):
                result = validate_and_resolve_profile()
                assert result == "dev"


class TestProfileInfo:
    """Test profile information structures."""

    def test_profile_info_for_existing_profile(self, mock_config_with_profiles):
        """Test ProfileInfo for existing profile."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            info = get_profile_info("prod")

            assert info.name == "prod"
            assert info.exists is True
            assert info.is_default is False
            assert isinstance(info.config_path, Path)

    def test_profile_info_for_default_profile(self, mock_config_with_profiles):
        """Test ProfileInfo identifies default profile correctly."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            info = get_profile_info("dev")

            assert info.name == "dev"
            assert info.exists is True
            assert info.is_default is True

    def test_profile_info_for_nonexistent_profile(self, mock_config_with_profiles):
        """Test ProfileInfo for nonexistent profile."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            info = get_profile_info("missing")

            assert info.name == "missing"
            assert info.exists is False
            assert info.is_default is False

    def test_profile_info_with_none_uses_default(self, mock_config_with_profiles):
        """Test ProfileInfo with None uses default profile."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            info = get_profile_info(None)

            assert info.name == "dev"
            assert info.exists is True
            assert info.is_default is True


class TestProfileSummary:
    """Test profile summary functionality."""

    def test_profile_summary_complete_config(self, mock_config_with_profiles):
        """Test profile summary with complete configuration."""
        with mock_config_with_profiles(["dev", "staging", "prod"], default="dev"):
            with patch.dict(os.environ, {"SNOWFLAKE_PROFILE": "staging"}):
                summary = get_profile_summary()

                assert isinstance(summary, ProfileSummary)
                assert summary.config_exists is True
                assert summary.available_profiles == [
                    "dev",
                    "prod",
                    "staging",
                ]  # sorted
                assert summary.profile_count == 3
                assert summary.default_profile == "dev"
                assert summary.current_profile == "staging"

    def test_profile_summary_no_config(self, mock_no_config):
        """Test profile summary when no config exists."""
        with mock_no_config():
            summary = get_profile_summary()

            assert summary.config_exists is False
            assert summary.available_profiles == []
            assert summary.profile_count == 0
            assert summary.default_profile is None


class TestConfigPathDetection:
    """Test configuration path detection across platforms."""

    @patch("platform.system")
    def test_config_path_macos(self, mock_system):
        """Test config path detection on macOS."""
        mock_system.return_value = "Darwin"
        # Clear the cache first
        get_snowflake_config_path.cache_clear()

        path = get_snowflake_config_path()
        expected = (
            Path.home()
            / "Library"
            / "Application Support"
            / "snowflake"
            / "config.toml"
        )
        assert path == expected

    @patch("platform.system")
    def test_config_path_windows(self, mock_system):
        """Test config path detection on Windows."""
        mock_system.return_value = "Windows"
        get_snowflake_config_path.cache_clear()

        path = get_snowflake_config_path()
        expected = Path.home() / "AppData" / "Local" / "snowflake" / "config.toml"
        assert path == expected

    @patch("platform.system")
    def test_config_path_linux(self, mock_system):
        """Test config path detection on Linux."""
        mock_system.return_value = "Linux"
        get_snowflake_config_path.cache_clear()

        path = get_snowflake_config_path()
        expected = Path.home() / ".config" / "snowflake" / "config.toml"
        assert path == expected


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_validation_error_contains_context(self, mock_config_with_profiles):
        """Test that validation errors contain helpful context."""
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            with pytest.raises(ProfileValidationError) as exc_info:
                validate_profile("invalid")

            error = exc_info.value
            assert error.profile_name == "invalid"
            assert "dev" in error.available_profiles
            assert "prod" in error.available_profiles
            assert error.config_path is not None

    def test_graceful_handling_of_corrupted_config(self, mock_corrupted_config):
        """Test graceful handling when config file is corrupted."""
        with mock_corrupted_config():
            profiles = get_available_profiles()
            assert profiles == set()

            default = get_default_profile()
            assert default is None

    def test_graceful_handling_of_permission_errors(self, mock_permission_error):
        """Test graceful handling of permission errors."""
        with mock_permission_error():
            profiles = get_available_profiles()
            assert profiles == set()


class TestPerformanceOptimizations:
    """Test performance optimizations and caching."""

    def test_config_path_is_cached(self):
        """Test that config path lookup is cached."""
        get_snowflake_config_path.cache_clear()

        path1 = get_snowflake_config_path()
        path2 = get_snowflake_config_path()

        assert path1 is path2  # Same object due to caching

    def test_config_loading_is_cached_by_mtime(self, tmp_path):
        """Test that config loading respects mtime for cache invalidation."""
        from igloo_mcp.profile_utils import _load_snowflake_config

        # Create a test config file
        config_file = tmp_path / "config.toml"
        config_file.write_text("[connections]\ndev = {}\n")

        # Load config - should be cached
        mtime1 = config_file.stat().st_mtime
        config1 = _load_snowflake_config(config_file, mtime1)
        config2 = _load_snowflake_config(config_file, mtime1)

        # Should return cached result
        assert config1 is config2

        # Modify file and reload - should invalidate cache
        config_file.write_text("[connections]\ndev = {}\nprod = {}\n")
        mtime2 = config_file.stat().st_mtime
        config3 = _load_snowflake_config(config_file, mtime2)

        # Should be different object due to mtime change
        assert config1 is not config3


# Fixtures
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


@pytest.fixture
def mock_no_config():
    """Mock scenario where no config file exists."""

    def _mock():
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = False

        return patch.object(
            profile_utils,
            "get_snowflake_config_path",
            return_value=mock_path,
        )

    return _mock


@pytest.fixture
def mock_corrupted_config():
    """Mock corrupted configuration file."""

    def _mock():
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.stat.return_value = Mock(st_mtime=123.0)

        return patch.multiple(
            profile_utils,
            get_snowflake_config_path=Mock(return_value=mock_path),
            _load_snowflake_config=Mock(side_effect=Exception("Corrupted file")),
        )

    return _mock


@pytest.fixture
def mock_permission_error():
    """Mock permission error when accessing config."""

    def _mock():
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.stat.return_value = Mock(st_mtime=123.0)

        return patch.multiple(
            profile_utils,
            get_snowflake_config_path=Mock(return_value=mock_path),
            _load_snowflake_config=Mock(side_effect=PermissionError("Access denied")),
        )

    return _mock
