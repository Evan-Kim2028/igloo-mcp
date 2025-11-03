from __future__ import annotations

from pathlib import Path

import pytest

from igloo_mcp import path_utils


def _clear_logging_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "IGLOO_MCP_QUERY_HISTORY",
        "IGLOO_MCP_ARTIFACT_ROOT",
        "IGLOO_MCP_CACHE_ROOT",
        "IGLOO_MCP_LOG_SCOPE",
        "IGLOO_MCP_NAMESPACED_LOGS",
    ):
        monkeypatch.delenv(key, raising=False)


def _set_fake_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    monkeypatch.setattr(path_utils.Path, "home", lambda: home)


def test_resolve_history_path_defaults_to_global_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_logging_env(monkeypatch)
    _set_fake_home(monkeypatch, tmp_path)

    history_path = path_utils.resolve_history_path()
    expected = tmp_path / ".igloo_mcp" / "logs" / "doc.jsonl"
    assert history_path == expected


def test_resolve_history_path_repo_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_logging_env(monkeypatch)
    _set_fake_home(monkeypatch, tmp_path)
    repo_root = tmp_path / "repo"
    monkeypatch.setenv("IGLOO_MCP_LOG_SCOPE", "repo")
    monkeypatch.setattr(path_utils, "find_repo_root", lambda start=None: repo_root)

    history_path = path_utils.resolve_history_path()
    expected = repo_root / "logs" / "doc.jsonl"
    assert history_path == expected


def test_resolve_history_path_namespaced_global(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_logging_env(monkeypatch)
    _set_fake_home(monkeypatch, tmp_path)
    monkeypatch.setenv("IGLOO_MCP_NAMESPACED_LOGS", "true")

    history_path = path_utils.resolve_history_path()
    expected = tmp_path / ".igloo_mcp" / "logs" / "igloo_mcp" / "doc.jsonl"
    assert history_path == expected


def test_resolve_history_path_explicit_env_overrides_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_logging_env(monkeypatch)
    _set_fake_home(monkeypatch, tmp_path)
    repo_root = tmp_path / "repo"
    monkeypatch.setenv("IGLOO_MCP_LOG_SCOPE", "repo")
    monkeypatch.setattr(path_utils, "find_repo_root", lambda start=None: repo_root)
    explicit_path = tmp_path / "custom" / "history.jsonl"
    monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(explicit_path))

    history_path = path_utils.resolve_history_path()
    assert history_path == explicit_path.resolve()


def test_resolve_artifact_and_cache_paths_namespaced_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_logging_env(monkeypatch)
    _set_fake_home(monkeypatch, tmp_path)
    repo_root = tmp_path / "repo"
    monkeypatch.setenv("IGLOO_MCP_LOG_SCOPE", "repo")
    monkeypatch.setenv("IGLOO_MCP_NAMESPACED_LOGS", "true")
    monkeypatch.setattr(path_utils, "find_repo_root", lambda start=None: repo_root)

    artifact_path = path_utils.resolve_artifact_root()
    expected_artifact = repo_root / "logs" / "igloo_mcp" / "artifacts"
    assert artifact_path == expected_artifact

    cache_path = path_utils.resolve_cache_root()
    assert cache_path == expected_artifact / "cache"


def test_resolve_cache_root_explicit_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_logging_env(monkeypatch)
    explicit_cache = tmp_path / "cache-dir"
    monkeypatch.setenv("IGLOO_MCP_CACHE_ROOT", str(explicit_cache))

    cache_path = path_utils.resolve_cache_root()
    assert cache_path == explicit_cache.resolve()
