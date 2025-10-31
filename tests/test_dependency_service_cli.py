"""Direct tests for dependency.dependency_service."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from igloo_mcp.dependency.dependency_service import DependencyService


def test_build_dependency_graph_success(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    class StubCLI:
        def __init__(self, profile):
            captured["profile"] = profile

    monkeypatch.setattr("igloo_mcp.dependency.dependency_service.SnowCLI", StubCLI)

    service = DependencyService(context={"profile": "DEV"})
    result = service.build_dependency_graph(
        database="DB", schema="SCHEMA", account_scope=False, format="json"
    )
    assert captured["profile"] == "DEV"
    assert result["status"] == "success"
    assert result["database"] == "DB"
    assert result["schema"] == "SCHEMA"
    assert result["graph_file"].endswith("dependencies.json")


def test_build_dependency_graph_failure(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "igloo_mcp.dependency.dependency_service.SnowCLI",
        lambda profile=None: SimpleNamespace(),  # noqa: ARG005
    )

    class ExplodingFormat:
        def __format__(self, spec: str) -> str:  # noqa: D401
            raise RuntimeError("boom")

    service = DependencyService()
    result = service.build_dependency_graph(format=ExplodingFormat())
    assert result["status"] == "error"
    assert result["error"] == "boom"
