import pytest

from igloo_mcp.mcp_server import read_sql_artifact_by_sha


def test_read_sql_artifact_by_sha_returns_sql(tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    sql_dir = artifact_root / "queries" / "by_sha"
    sql_dir.mkdir(parents=True, exist_ok=True)
    sha = "a" * 64
    sql_file = sql_dir / f"{sha}.sql"
    sql_file.write_text("SELECT 1", encoding="utf-8")

    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(artifact_root))

    assert read_sql_artifact_by_sha(sha) == "SELECT 1"


def test_read_sql_artifact_by_sha_missing(tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("IGLOO_MCP_ARTIFACT_ROOT", str(artifact_root))

    with pytest.raises(FileNotFoundError):
        read_sql_artifact_by_sha("b" * 64)


def test_read_sql_artifact_by_sha_rejects_invalid_input():
    with pytest.raises(ValueError):
        read_sql_artifact_by_sha("not-a-sha")
