"""Tests for extracting authenticator information from Snowflake profiles."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import igloo_mcp.profile_utils as profile_utils
from igloo_mcp.profile_utils import get_profile_summary


def test_summary_includes_externalbrowser_authenticator():
    """Profile summary should include authenticator when set to externalbrowser."""
    config_data = {
        "connections": {
            "dev": {
                "account": "acme-dev.us-east-1",
                "user": "alice",
                "authenticator": "externalbrowser",
            },
        },
        "default_connection_name": "dev",
    }

    mock_path = Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.stat.return_value = Mock(st_mtime=123.0)

    with patch.multiple(
        profile_utils,
        get_snowflake_config_path=Mock(return_value=mock_path),
        _load_snowflake_config=Mock(return_value=config_data),
    ):
        summary = get_profile_summary()
        assert summary.current_profile_authenticator == "externalbrowser"


def test_summary_includes_okta_url_authenticator():
    """Profile summary should include explicit Okta URL authenticator when provided."""
    config_data = {
        "connections": {
            "prod": {
                "account": "acme-prod.us-west-2",
                "user": "bob",
                "authenticator": "https://acme.okta.com",
            },
        },
        "default_connection_name": "prod",
    }

    mock_path = Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.stat.return_value = Mock(st_mtime=456.0)

    with patch.multiple(
        profile_utils,
        get_snowflake_config_path=Mock(return_value=mock_path),
        _load_snowflake_config=Mock(return_value=config_data),
    ):
        summary = get_profile_summary()
        assert summary.current_profile_authenticator == "https://acme.okta.com"
