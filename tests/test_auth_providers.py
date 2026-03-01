from __future__ import annotations

import argparse

import pytest

from igloo_mcp.auth.providers import (
    AUTH_MODE_AUTO,
    AUTH_MODE_KEYPAIR,
    AUTH_MODE_SNOWFLAKE_LABS,
    _build_keypair_connection_params,
    resolve_effective_auth_mode,
)


def _args(**overrides):
    base = {
        "auth_mode": AUTH_MODE_SNOWFLAKE_LABS,
        "account": None,
        "user": None,
        "private_key_file": None,
        "private_key": None,
        "private_key_file_pwd": None,
        "authenticator": None,
        "host": None,
        "role": None,
        "warehouse": None,
        "database": None,
        "schema": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_resolve_effective_auth_mode_defaults_to_snowflake_labs():
    args = _args(auth_mode=AUTH_MODE_SNOWFLAKE_LABS)
    assert resolve_effective_auth_mode(args, env={}) == AUTH_MODE_SNOWFLAKE_LABS


def test_resolve_effective_auth_mode_auto_without_keypair_uses_snowflake_labs():
    args = _args(auth_mode=AUTH_MODE_AUTO)
    assert resolve_effective_auth_mode(args, env={}) == AUTH_MODE_SNOWFLAKE_LABS


def test_resolve_effective_auth_mode_auto_with_keypair_uses_keypair(tmp_path):
    key_path = tmp_path / "private_key.p8"
    key_path.write_text("-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n", encoding="utf-8")
    args = _args(
        auth_mode=AUTH_MODE_AUTO,
        account="MY_ACCOUNT",
        user="MY_USER",
        private_key_file=str(key_path),
    )
    assert resolve_effective_auth_mode(args, env={}) == AUTH_MODE_KEYPAIR


def test_resolve_effective_auth_mode_invalid_raises():
    args = _args(auth_mode="unsupported-mode")
    with pytest.raises(ValueError, match="Unsupported auth_mode"):
        resolve_effective_auth_mode(args, env={})


def test_build_keypair_connection_params_requires_account_user_and_key():
    args = _args(auth_mode=AUTH_MODE_KEYPAIR)
    with pytest.raises(ValueError, match="SNOWFLAKE_ACCOUNT"):
        _build_keypair_connection_params(args)


def test_build_keypair_connection_params_uses_file_and_defaults_authenticator(tmp_path):
    key_path = tmp_path / "private_key.p8"
    key_path.write_text("-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n", encoding="utf-8")
    args = _args(
        auth_mode=AUTH_MODE_KEYPAIR,
        account="MY_ACCOUNT",
        user="MY_USER",
        private_key_file=str(key_path),
        warehouse="WH",
        database="DB",
        schema="SCHEMA",
        role="ROLE",
    )

    params = _build_keypair_connection_params(args)
    assert params["account"] == "MY_ACCOUNT"
    assert params["user"] == "MY_USER"
    assert params["private_key_file"] == str(key_path)
    assert params["authenticator"] == "SNOWFLAKE_JWT"
    assert params["warehouse"] == "WH"
    assert params["database"] == "DB"
    assert params["schema"] == "SCHEMA"
    assert params["role"] == "ROLE"
