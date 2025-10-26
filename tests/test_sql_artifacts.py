import pytest

from igloo_mcp.mcp_server import read_sql_artifact_by_sha


def test_read_sql_artifact_by_sha_returns_sql(tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    sql_dir = artifact_root / "queries" / "by_sha"
    sql_dir.mkdir(parents=True, exist_ok=True)
    sql_file = sql_dir / "abc123.sql"
    sql_file.write_text("SELECT 1", encoding="utf-8")

    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(artifact_root))

    assert read_sql_artifact_by_sha("abc123") == "SELECT 1"


def test_read_sql_artifact_by_sha_missing(tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(artifact_root))

    with pytest.raises(FileNotFoundError):
        read_sql_artifact_by_sha("missing")
