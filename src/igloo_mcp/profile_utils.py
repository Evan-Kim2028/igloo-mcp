"""Snowflake profile validation and management utilities.

This module provides comprehensive profile validation with clear error messages,
performance caching, and integration with the existing error handling infrastructure.
"""

from __future__ import annotations

import functools
import logging
import os
import platform
import tomllib
from pathlib import Path
from typing import Any, NamedTuple

from .error_handling import ProfileConfigurationError

logger = logging.getLogger(__name__)


class ProfileValidationError(ProfileConfigurationError):
    """Error raised when Snowflake profile validation fails."""

    pass


class ProfileInfo(NamedTuple):
    """Structured profile information."""

    name: str
    exists: bool
    is_default: bool
    config_path: Path


class ProfileSummary(NamedTuple):
    """Complete profile configuration summary."""

    config_path: Path
    config_exists: bool
    available_profiles: list[str]
    default_profile: str | None
    current_profile: str | None
    profile_count: int
    current_profile_authenticator: str | None


@functools.lru_cache(maxsize=1)
def get_snowflake_config_path() -> Path:
    """Get the path to the Snowflake CLI configuration file.

    Cached for performance since this path doesn't change during execution.
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        config_dir = Path.home() / "Library" / "Application Support" / "snowflake"
    elif system == "Windows":
        config_dir = Path.home() / "AppData" / "Local" / "snowflake"
    else:  # Linux and others
        config_dir = Path.home() / ".config" / "snowflake"

    return config_dir / "config.toml"


@functools.lru_cache(maxsize=32)
def _load_snowflake_config(config_path: Path, mtime: float) -> dict[str, Any]:
    """Load and cache Snowflake config file.

    Args:
        config_path: Path to config file
        mtime: Modification time for cache invalidation

    Returns:
        Parsed TOML configuration

    Note: mtime parameter ensures cache invalidation when file changes
    """
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        logger.warning(f"Failed to load Snowflake config from {config_path}: {e}")
        return {}


def get_available_profiles() -> set[str]:
    """Get all available Snowflake profiles from the CLI configuration.

    Returns:
        Set of available profile names
    """
    config_path = get_snowflake_config_path()

    if not config_path.exists():
        logger.debug(f"Snowflake config file does not exist: {config_path}")
        return set()

    try:
        # Use mtime for cache invalidation
        mtime = config_path.stat().st_mtime
        config_data = _load_snowflake_config(config_path, mtime)
        connections = config_data.get("connections", {})
        profiles = set(connections.keys())
        logger.debug(f"Found {len(profiles)} profiles: {sorted(profiles)}")
        return profiles
    except Exception as e:
        logger.warning(f"Error reading profiles from {config_path}: {e}")
        return set()


def get_default_profile() -> str | None:
    """Get the default Snowflake profile from the CLI configuration.

    Returns:
        Default profile name or None if not configured
    """
    config_path = get_snowflake_config_path()

    if not config_path.exists():
        return None

    try:
        mtime = config_path.stat().st_mtime
        config_data = _load_snowflake_config(config_path, mtime)
        default = config_data.get("default_connection_name")
        logger.debug(f"Default profile: {default}")
        return default
    except Exception as e:
        logger.warning(f"Error reading default profile from {config_path}: {e}")
        return None


def validate_profile(profile_name: str | None) -> str:
    """Validate a Snowflake profile name and return the validated profile.

    Args:
        profile_name: The profile name to validate, or None to use default

    Returns:
        The validated profile name

    Raises:
        ProfileValidationError: If the profile is invalid or doesn't exist
    """
    logger.info(f"Validating Snowflake profile: {profile_name or '(default)'}")

    config_path = get_snowflake_config_path()
    available_profiles = get_available_profiles()

    if not available_profiles:
        error_msg = (
            f"No Snowflake profiles found in {config_path}.\n\n"
            "Quick fix:\n"
            "  snow connection add \\\n"
            '    --connection-name "quickstart" \\\n'
            '    --account "<your-account>.<region>" \\\n'
            '    --user "<your-username>" \\\n'
            "    --password \\\n"
            '    --warehouse "<your-warehouse>"\n\n'
            "Don't know your account identifier? See: docs/getting-started.md#finding-your-account-identifier"
        )
        raise ProfileValidationError(
            error_msg,
            profile_name=profile_name,
            available_profiles=[],
            config_path=str(config_path),
        )

    # If no profile specified, try to use the default
    if not profile_name:
        default_profile = get_default_profile()
        if default_profile and default_profile in available_profiles:
            logger.info(f"Using default profile: {default_profile}")
            return default_profile

        available_list = sorted(available_profiles)
        error_msg = (
            "No Snowflake profile specified and no valid default found.\n\n"
            f"Available profiles: {', '.join(available_list)}\n\n"
            "Quick fix (choose one):\n"
            f'  1. Set environment variable: export SNOWFLAKE_PROFILE="{available_list[0]}"\n'
            f'  2. Pass profile flag: igloo-mcp --profile "{available_list[0]}"\n'
            f'  3. Set default: snow connection set-default "{available_list[0]}"\n\n'
            f"Config location: {config_path}"
        )
        raise ProfileValidationError(
            error_msg,
            profile_name=profile_name,
            available_profiles=available_list,
            config_path=str(config_path),
        )

    # Validate the specified profile exists
    if profile_name not in available_profiles:
        available_list = sorted(available_profiles)
        error_msg = (
            f"Snowflake profile '{profile_name}' not found.\n\n"
            f"Available profiles ({len(available_list)}): {', '.join(available_list)}\n\n"
            "Quick fix:\n"
            "  1. Use existing profile: igloo-mcp --profile "
            f"\"{available_list[0] if available_list else 'PROFILE_NAME'}\"\n"
            '  2. Create new profile: snow connection add --connection-name "'
            + profile_name
            + '" ...\n'
            "  3. List all profiles: snow connection list\n\n"
            f"Config location: {config_path}"
        )
        raise ProfileValidationError(
            error_msg,
            profile_name=profile_name,
            available_profiles=available_list,
            config_path=str(config_path),
        )

    logger.info(f"Profile validation successful: {profile_name}")
    return profile_name


def get_profile_info(profile_name: str | None) -> ProfileInfo:
    """Get detailed information about a specific profile.

    Args:
        profile_name: Profile name to get info for

    Returns:
        ProfileInfo with details about the profile
    """
    config_path = get_snowflake_config_path()
    available_profiles = get_available_profiles()
    default_profile = get_default_profile()

    if not profile_name:
        profile_name = default_profile or "default"

    return ProfileInfo(
        name=profile_name,
        exists=profile_name in available_profiles,
        is_default=profile_name == default_profile,
        config_path=config_path,
    )


def get_profile_summary() -> ProfileSummary:
    """Get a comprehensive summary of Snowflake profile configuration.

    Returns:
        ProfileSummary with complete configuration details
    """
    config_path = get_snowflake_config_path()
    available_profiles = get_available_profiles()
    default_profile = get_default_profile()
    env_profile = os.environ.get("SNOWFLAKE_PROFILE")
    resolved_profile = None

    # Determine authenticator for the current profile if possible
    current_auth = None
    try:
        # Use mtime for cache invalidation
        if config_path.exists():
            mtime = config_path.stat().st_mtime
            config_data = _load_snowflake_config(config_path, mtime)
            connections = config_data.get("connections", {})
            if isinstance(connections, dict):
                if env_profile and env_profile in connections:
                    resolved_profile = env_profile
                elif default_profile and default_profile in connections:
                    resolved_profile = default_profile
                elif connections:
                    resolved_profile = next(iter(connections))

                if resolved_profile:
                    entry = connections.get(resolved_profile, {}) or {}
                    current_auth = entry.get("authenticator")
    except Exception:
        # Non-fatal: leave authenticator as None if parsing fails
        current_auth = None

    return ProfileSummary(
        config_path=config_path,
        config_exists=config_path.exists(),
        available_profiles=sorted(available_profiles),
        default_profile=default_profile,
        current_profile=resolved_profile,
        profile_count=len(available_profiles),
        current_profile_authenticator=current_auth,
    )


def validate_and_resolve_profile() -> str:
    """Validate and resolve the active Snowflake profile using precedence rules.

    This function implements the standard precedence:
    1. SNOWFLAKE_PROFILE environment variable
    2. Default profile from config
    3. Raise error if none available

    Returns:
        Validated and resolved profile name

    Raises:
        ProfileValidationError: If no valid profile can be resolved
    """
    # Check environment first (highest precedence)
    env_profile = os.environ.get("SNOWFLAKE_PROFILE")
    if env_profile:
        return validate_profile(env_profile.strip())

    # Fall back to default profile
    return validate_profile(None)
