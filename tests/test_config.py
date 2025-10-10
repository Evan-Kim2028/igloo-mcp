"""Tests for configuration management."""

import os
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import yaml  # type: ignore[import-untyped]

from igloo_mcp.config import Config, SnowflakeConfig, get_config, set_config


class TestConfig:
    """Test configuration functionality."""

    def test_config_from_env_defaults(self):
        """Test loading config from environment with defaults."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config.from_env()

            assert config.snowflake.profile == "default"
            assert config.snowflake.warehouse is None
            assert config.snowflake.database is None
            assert config.snowflake.schema is None
            assert config.max_concurrent_queries == 5
            assert config.connection_pool_size == 10

    def test_config_from_env_custom_values(self):
        """Test loading config from environment with custom values."""
        env_vars = {
            "SNOWFLAKE_PROFILE": "my-dev",
            "SNOWFLAKE_WAREHOUSE": "custom_wh",
            "SNOWFLAKE_DATABASE": "custom_db",
            "SNOWFLAKE_SCHEMA": "custom_schema",
            "SNOWFLAKE_ROLE": "custom_role",
            "MAX_CONCURRENT_QUERIES": "10",
            "CONNECTION_POOL_SIZE": "20",
            "RETRY_ATTEMPTS": "5",
            "RETRY_DELAY": "2.0",
            "TIMEOUT_SECONDS": "600",
            "LOG_LEVEL": "DEBUG",
        }

        with patch.dict(os.environ, env_vars):
            config = Config.from_env()

            assert config.snowflake.profile == "my-dev"
            assert config.snowflake.warehouse == "custom_wh"
            assert config.snowflake.database == "custom_db"
            assert config.snowflake.schema == "custom_schema"
            assert config.snowflake.role == "custom_role"
            assert config.max_concurrent_queries == 10
            assert config.connection_pool_size == 20
            assert config.retry_attempts == 5
            assert config.retry_delay == 2.0
            assert config.timeout_seconds == 600
            assert config.log_level == "DEBUG"

    def test_config_from_yaml(self):
        """Test loading config from YAML file."""
        config_data = {
            "snowflake": {
                "profile": "yaml_profile",
                "warehouse": "yaml_wh",
                "database": "yaml_db",
                "schema": "yaml_schema",
                "role": "yaml_role",
            },
            "max_concurrent_queries": 15,
            "connection_pool_size": 25,
            "retry_attempts": 7,
            "retry_delay": 3.0,
            "timeout_seconds": 700,
            "log_level": "WARNING",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            with patch.dict(os.environ, {}, clear=True):
                config = Config.from_yaml(config_path)

            assert config.snowflake.profile == "yaml_profile"
            assert config.snowflake.warehouse == "yaml_wh"
            assert config.snowflake.database == "yaml_db"
            assert config.snowflake.schema == "yaml_schema"
            assert config.snowflake.role == "yaml_role"
            assert config.max_concurrent_queries == 15
            assert config.connection_pool_size == 25
            assert config.retry_attempts == 7
            assert config.retry_delay == 3.0
            assert config.timeout_seconds == 700
            assert config.log_level == "WARNING"
        finally:
            Path(config_path).unlink()

    def test_config_save_to_yaml(self):
        """Test saving config to YAML file."""
        config = Config.from_env()
        config = replace(
            config,
            snowflake=replace(config.snowflake, profile="test_profile"),
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_path = f.name

        try:
            config.save_to_yaml(config_path)

            # Verify the file was created and contains expected data
            with open(config_path, "r") as f:
                saved_data = yaml.safe_load(f)

            assert saved_data["snowflake"]["profile"] == "test_profile"
            assert "max_concurrent_queries" in saved_data
            assert "connection_pool_size" in saved_data
        finally:
            Path(config_path).unlink()

    def test_get_set_config(self):
        """Test global config getter and setter."""
        original_config = get_config()

        # Set a custom config
        custom_config = replace(get_config(), max_concurrent_queries=99)
        set_config(custom_config)

        # Verify it's set
        current_config = get_config()
        assert current_config.max_concurrent_queries == 99

        # Reset to original
        set_config(original_config)


class TestSnowflakeConfig:
    """Test SnowflakeConfig functionality."""

    def test_fields(self):
        cfg = SnowflakeConfig(
            profile="test_profile",
            warehouse="test_wh",
            database="test_db",
            schema="test_schema",
            role="test_role",
        )

        assert cfg.profile == "test_profile"
        assert cfg.warehouse == "test_wh"
        assert cfg.database == "test_db"
        assert cfg.schema == "test_schema"
        assert cfg.role == "test_role"
