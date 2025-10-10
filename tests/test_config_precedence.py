from __future__ import annotations

import os
from unittest.mock import patch

from igloo_mcp.config import Config


def test_cli_override_precedence(monkeypatch):
    with patch.dict(os.environ, {"SNOWFLAKE_PROFILE": "env_profile"}, clear=True):
        cfg = Config.from_env()
        assert cfg.snowflake.profile == "env_profile"

        # Simulate loader applying CLI override on top of env
        from igloo_mcp.config import ConfigLoader

        loader = ConfigLoader()
        merged = loader.build(cli_overrides={"profile": "cli_profile"})
        assert merged.snowflake.profile == "cli_profile"
