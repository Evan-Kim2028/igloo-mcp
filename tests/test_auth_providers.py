from __future__ import annotations

import argparse

import pytest

from igloo_mcp.auth.providers import (
    AUTH_MODE_AUTO,
    AUTH_MODE_KEYPAIR,
    AUTH_MODE_SNOWFLAKE_LABS,
    AuthProviderSpec,
    _build_keypair_connection_params,
    attach_provider_runtime_metadata,
    get_auth_provider_spec,
    get_service_provider_spec,
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


def test_get_auth_provider_spec_returns_capability_matrix():
    keypair = get_auth_provider_spec(AUTH_MODE_KEYPAIR)
    assert keypair.mode == AUTH_MODE_KEYPAIR
    assert keypair.capabilities.supports_profile_validation is False
    assert keypair.capabilities.supports_retry_handling is True
    assert keypair.reliability.retry_attempts >= 1

    labs = get_auth_provider_spec(AUTH_MODE_SNOWFLAKE_LABS)
    assert labs.mode == AUTH_MODE_SNOWFLAKE_LABS
    assert labs.capabilities.supports_profile_validation is True
    assert labs.capabilities.supports_sql_validation_middleware_patch is True


def test_attach_provider_runtime_metadata_sets_service_fields():
    class StubService:
        pass

    service = StubService()
    spec = attach_provider_runtime_metadata(service, mode=AUTH_MODE_KEYPAIR)
    assert isinstance(spec, AuthProviderSpec)
    assert service.auth_mode == AUTH_MODE_KEYPAIR
    assert service.provider_spec == spec
    assert service.provider_capabilities == spec.capabilities
    assert service.provider_reliability == spec.reliability


def test_get_service_provider_spec_uses_existing_provider_spec():
    class StubService:
        pass

    service = StubService()
    attached = attach_provider_runtime_metadata(service, mode=AUTH_MODE_SNOWFLAKE_LABS)
    resolved = get_service_provider_spec(service)
    assert resolved is attached
