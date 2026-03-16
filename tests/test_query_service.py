"""Regression tests for QueryService driver selection and delegation."""

from __future__ import annotations

from types import SimpleNamespace

from igloo_mcp.service_layer.query_service import QueryService
from igloo_mcp.snow_cli import QueryOutput


def test_query_service_rest_driver_uses_context_and_helpers(monkeypatch) -> None:
    expected = QueryOutput(raw_stdout="", raw_stderr="", returncode=0, rows=[{"ok": 1}])
    captured: dict[str, object] = {}

    class DummyRestClient:
        def run_query(self, query: str, *, ctx_overrides=None, timeout=None):
            captured["query"] = query
            captured["ctx_overrides"] = ctx_overrides
            captured["timeout"] = timeout
            return expected

    def fake_from_env(*, default_context):
        captured["default_context"] = default_context
        return DummyRestClient()

    monkeypatch.setattr("igloo_mcp.service_layer.query_service.SnowRestClient.from_env", fake_from_env)
    monkeypatch.setattr("igloo_mcp.service_layer.query_service.SnowCLI", lambda profile: None)

    context = SimpleNamespace(
        config=SimpleNamespace(
            snowflake=SimpleNamespace(
                profile="DEV",
                session_defaults=lambda: {
                    "warehouse": "WH",
                    "database": "DB",
                    "schema": "PUBLIC",
                    "role": "ANALYST",
                },
            )
        )
    )

    service = QueryService(context=context, driver="rest")
    session = service.session_from_mapping(
        {
            "warehouse": "ALT_WH",
            "database": "ALT_DB",
            "schema": "ALT_SCHEMA",
            "role": "ALT_ROLE",
            "ignored": "value",
        }
    )

    result = service.execute_with_service("SELECT 1", service="ignored", session=session, timeout=12)

    assert service.profile == "DEV"
    assert service.driver == "rest"
    assert result is expected
    assert captured["default_context"] == {
        "warehouse": "WH",
        "database": "DB",
        "schema": "PUBLIC",
        "role": "ANALYST",
    }
    assert captured["query"] == "SELECT 1"
    assert captured["ctx_overrides"] == {
        "warehouse": "ALT_WH",
        "database": "ALT_DB",
        "schema": "ALT_SCHEMA",
        "role": "ALT_ROLE",
    }
    assert captured["timeout"] == 12


def test_query_service_rest_initialization_falls_back_to_cli(monkeypatch) -> None:
    expected = QueryOutput(raw_stdout="", raw_stderr="", returncode=0, rows=[{"ok": 2}])
    captured: dict[str, object] = {}

    class DummyCLI:
        def __init__(self, profile):
            captured["profile"] = profile

        def run_query(self, query: str, *, output_format=None, timeout=None, ctx_overrides=None):
            captured["query"] = query
            captured["output_format"] = output_format
            captured["timeout"] = timeout
            captured["ctx_overrides"] = ctx_overrides
            return expected

    def fail_from_env(*, default_context):
        raise ValueError("missing credentials")

    monkeypatch.setattr("igloo_mcp.service_layer.query_service.SnowRestClient.from_env", fail_from_env)
    monkeypatch.setattr("igloo_mcp.service_layer.query_service.SnowCLI", DummyCLI)

    service = QueryService(context=None, driver="rest")
    result = service.execute(
        "SELECT 2",
        output_format="json",
        timeout=30,
        session={"warehouse": "WH"},
    )

    assert service.driver == "cli"
    assert result is expected
    assert captured == {
        "profile": None,
        "query": "SELECT 2",
        "output_format": "json",
        "timeout": 30,
        "ctx_overrides": {"warehouse": "WH"},
    }
