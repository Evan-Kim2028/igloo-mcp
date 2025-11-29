"""Tests for the query result cache."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from igloo_mcp.cache.query_result_cache import CacheHit, QueryResultCache
from igloo_mcp.path_utils import DEFAULT_ARTIFACT_ROOT, DEFAULT_CACHE_SUBDIR


def _write_manifest(directory: Path, data: dict[str, object]) -> Path:
    path = directory / "manifest.json"
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_store_and_lookup_round_trip(tmp_path: Path) -> None:
    cache = QueryResultCache(mode="enabled", root=tmp_path, max_rows=10)

    rows = [{"id": 1, "value": "alpha"}, {"id": 2, "value": "beta"}]
    metadata = {
        "profile": "TEST",
        "context": {"warehouse": "WH"},
        "rowcount": 2,
        "duration_ms": 100,
        "statement_sha256": "abc",
    }

    key = cache.compute_cache_key(
        sql_sha256="deadbeef",
        profile="TEST",
        effective_context={"warehouse": "WH", "role": None},
    )
    manifest_path = cache.store(key, rows=rows, metadata=metadata)
    assert manifest_path is not None

    hit = cache.lookup(key)
    assert isinstance(hit, CacheHit)
    assert hit.cache_key == key
    assert hit.rows == rows
    assert hit.metadata["cache_hit"] is True
    assert hit.metadata["rowcount"] == 2
    assert hit.result_json_path.exists()
    assert hit.result_csv_path is not None
    assert hit.manifest_path == manifest_path
    assert cache.pop_warnings() == []


def test_store_skips_when_rows_exceed_limit(tmp_path: Path) -> None:
    cache = QueryResultCache(mode="enabled", root=tmp_path, max_rows=1)

    key = "key"
    result = cache.store(
        key,
        rows=[{"id": 1}, {"id": 2}],
        metadata={"profile": "TEST", "context": {}},
    )
    assert result is None
    warnings = cache.pop_warnings()
    assert any("exceeds limit" in message for message in warnings)


def test_lookup_handles_manifest_mismatch(tmp_path: Path) -> None:
    cache = QueryResultCache(mode="enabled", root=tmp_path)
    key = "correct"
    key_dir = tmp_path / key
    _write_manifest(
        key_dir,
        {
            "cache_key": "different",
            "result_json": "rows.jsonl",
        },
    )
    key_dir.joinpath("rows.jsonl").write_text("{}", encoding="utf-8")

    assert cache.lookup(key) is None
    warnings = cache.pop_warnings()
    assert any("manifest mismatch" in message for message in warnings)


def test_lookup_handles_missing_rows_file(tmp_path: Path) -> None:
    cache = QueryResultCache(mode="enabled", root=tmp_path)
    key = "missing"
    key_dir = tmp_path / key
    _write_manifest(
        key_dir,
        {
            "cache_key": key,
            "result_json": "rows.jsonl",
        },
    )

    assert cache.lookup(key) is None
    warnings = cache.pop_warnings()
    assert any("rows file missing" in message for message in warnings)


def test_from_env_with_invalid_mode_and_max_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "unknown-mode")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MAX_ROWS", "not-a-number")

    cache = QueryResultCache.from_env(artifact_root=Path.cwd())
    assert cache.enabled
    assert cache.max_rows == QueryResultCache.DEFAULT_MAX_ROWS
    # Ensure warnings about invalid mode/max rows were captured
    warnings = cache.pop_warnings()
    assert isinstance(warnings, list)


def test_store_disabled_and_read_only(tmp_path: Path) -> None:
    disabled = QueryResultCache(mode="disabled", root=tmp_path)
    assert disabled.store("key", rows=[{}], metadata={}) is None

    read_only = QueryResultCache(mode="read_only", root=tmp_path)
    assert read_only.store("key", rows=[{}], metadata={}) is None


def test_store_directory_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = QueryResultCache(mode="enabled", root=tmp_path)
    key = cache.compute_cache_key(
        sql_sha256="abc",
        profile="TEST",
        effective_context={"warehouse": "WH"},
    )
    original_mkdir = Path.mkdir

    def fake_mkdir(self, *args, **kwargs):
        if self == tmp_path / key:
            raise OSError("cannot create directory")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fake_mkdir, raising=False)

    assert cache.store(key, rows=[{"ID": 1}], metadata={}) is None
    warnings = cache.pop_warnings()
    assert any("Failed to create cache directory" in msg for msg in warnings)


def test_store_rows_write_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = QueryResultCache(mode="enabled", root=tmp_path)
    key = cache.compute_cache_key(
        sql_sha256="def",
        profile="TEST",
        effective_context={},
    )
    original_open = Path.open

    def fake_open(self, mode="r", *args, **kwargs):
        if self.name == "rows.jsonl" and "w" in mode:
            raise OSError("rows write failure")
        return original_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_open, raising=False)

    assert cache.store(key, rows=[{"ID": 1}], metadata={}) is None
    warnings = cache.pop_warnings()
    assert any("Failed to persist cached rows" in msg for msg in warnings)


def test_store_csv_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = QueryResultCache(mode="enabled", root=tmp_path)
    key = cache.compute_cache_key(
        sql_sha256="ghi",
        profile="TEST",
        effective_context={},
    )
    original_open = Path.open

    def fake_open(self, mode="r", *args, **kwargs):
        if self.name == "rows.csv" and "w" in mode:
            raise OSError("csv write failure")
        return original_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_open, raising=False)

    manifest = cache.store(key, rows=[{"ID": 1}], metadata={})
    assert manifest is not None
    warnings = cache.pop_warnings()
    assert any("Failed to persist cached CSV" in msg for msg in warnings)


def test_lookup_refresh_mode_and_no_root(tmp_path: Path) -> None:
    refresh_cache = QueryResultCache(mode="refresh", root=tmp_path)
    assert refresh_cache.lookup("any") is None

    cache = QueryResultCache(mode="enabled", root=tmp_path)
    cache._root = None  # simulate root loss
    assert cache.store("key", rows=[{"ID": 1}], metadata={}) is None


def test_compute_cache_key_is_deterministic(tmp_path: Path) -> None:
    cache = QueryResultCache(mode="enabled", root=tmp_path)
    key1 = cache.compute_cache_key(
        sql_sha256="abc",
        profile="TEST",
        effective_context={"warehouse": "WH", "role": None},
    )
    key2 = cache.compute_cache_key(
        sql_sha256="abc",
        profile="TEST",
        effective_context={"role": None, "warehouse": "WH"},
    )
    assert key1 == key2


def test_lookup_corrupted_manifest(tmp_path: Path) -> None:
    cache = QueryResultCache(mode="enabled", root=tmp_path)
    key_dir = tmp_path / "key"
    key_dir.mkdir()
    (key_dir / "manifest.json").write_text("not-json", encoding="utf-8")
    assert cache.lookup("key") is None
    warnings = cache.pop_warnings()
    assert any("Failed to read cache manifest" in msg for msg in warnings)


def test_lookup_with_missing_manifest_fields(tmp_path: Path) -> None:
    cache = QueryResultCache(mode="enabled", root=tmp_path)
    key_dir = tmp_path / "key2"
    key_dir.mkdir()
    (key_dir / "manifest.json").write_text(json.dumps({"cache_key": "key2"}), encoding="utf-8")
    assert cache.lookup("key2") is None


def test_from_env_disable_via_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGLOO_MCP_CACHE_ROOT", "off")
    cache = QueryResultCache.from_env(artifact_root=None)
    assert cache.enabled is False


def test_from_env_handles_resolution_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGLOO_MCP_CACHE_ROOT", "relative/path")
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "enabled")
    monkeypatch.setattr(
        "igloo_mcp.cache.query_result_cache.resolve_cache_root",
        lambda raw=None, artifact_root=None: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    cache = QueryResultCache.from_env(artifact_root=None)
    expected = Path.home() / ".igloo_mcp" / DEFAULT_ARTIFACT_ROOT / DEFAULT_CACHE_SUBDIR
    assert cache.root == expected


def test_cache_uses_fallback_root_when_primary_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    primary = tmp_path / "primary"
    fallback = tmp_path / "fallback"
    original_mkdir = Path.mkdir

    def fake_mkdir(self, *args, **kwargs):
        if self == primary:
            raise OSError("primary unavailable")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fake_mkdir, raising=False)

    cache = QueryResultCache(mode="enabled", root=primary, fallbacks=[fallback])
    assert cache.root == fallback
    warnings = cache.pop_warnings()
    assert any("using fallback" in msg for msg in warnings)


def test_cache_disables_when_all_roots_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    primary = tmp_path / "primary"
    fallback = tmp_path / "fallback"
    original_mkdir = Path.mkdir

    def fake_mkdir(self, *args, **kwargs):
        if self in {primary, fallback}:
            raise OSError("unavailable")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fake_mkdir, raising=False)

    cache = QueryResultCache(mode="enabled", root=primary, fallbacks=[fallback])
    assert cache.enabled is False
    warnings = cache.pop_warnings()
    assert any("disabled" in msg for msg in warnings)


def test_from_env_blank_mode_uses_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGLOO_MCP_CACHE_MODE", "   ")
    monkeypatch.setenv("IGLOO_MCP_CACHE_ROOT", str(tmp_path))
    cache = QueryResultCache.from_env(artifact_root=None)
    assert cache.mode == QueryResultCache.DEFAULT_MODE


def test_from_env_fallback_mkdir_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fallback = Path.home() / ".igloo_mcp" / DEFAULT_ARTIFACT_ROOT / DEFAULT_CACHE_SUBDIR
    original_mkdir = Path.mkdir

    def fake_mkdir(self, *args, **kwargs):
        if self == fallback:
            raise OSError("fallback mkdir failure")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fake_mkdir, raising=False)
    monkeypatch.setenv("IGLOO_MCP_CACHE_ROOT", str(tmp_path))

    cache = QueryResultCache.from_env(artifact_root=None)
    assert cache.root == Path(tmp_path)


def test_lookup_skips_blank_lines(tmp_path: Path) -> None:
    cache = QueryResultCache(mode="enabled", root=tmp_path)
    key = "k1"
    key_dir = tmp_path / key
    key_dir.mkdir()
    (key_dir / "manifest.json").write_text(
        json.dumps(
            {
                "cache_key": key,
                "result_json": "rows.jsonl",
            }
        ),
        encoding="utf-8",
    )
    rows_path = key_dir / "rows.jsonl"
    rows_path.write_text('{"id": 1}\n\n{"id": 2}\n', encoding="utf-8")
    hit = cache.lookup(key)
    assert hit is not None
    assert len(hit.rows) == 2


def test_store_manifest_write_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = QueryResultCache(mode="enabled", root=tmp_path)
    key = cache.compute_cache_key(
        sql_sha256="xyz",
        profile="TEST",
        effective_context={},
    )
    original_write_text = Path.write_text

    def fake_write_text(self, *args, **kwargs):
        if self.name == "manifest.json":
            raise OSError("manifest failure")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fake_write_text, raising=False)

    result = cache.store(
        key,
        rows=[{"ID": 1}],
        metadata={"profile": "TEST", "context": {}},
    )
    assert result is None
    warnings = cache.pop_warnings()
    assert any("Failed to write cache manifest" in msg for msg in warnings)
