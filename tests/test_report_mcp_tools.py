from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from igloo_mcp import mcp_server


class CapturingServer:
    """Minimal FastMCP-like server that records registered tools."""

    def __init__(self) -> None:
        self.tools: Dict[str, Any] = {}

    def tool(self, *, name: str, description: str):  # noqa: D401, ARG002
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator

    def resource(self, uri: str, **_: Any):  # noqa: D401, ARG002
        def decorator(func):
            return func

        return decorator


class StubService:
    """SnowflakeService stub sufficient for register_igloo_mcp()."""

    def get_query_tag_param(self) -> None:
        return None

    def get_connection(self, **_: Any):  # type: ignore[override]
        class _ConnCtx:
            def __enter__(self):
                return None, None

            def __exit__(self, exc_type, exc, tb):  # noqa: D401, ARG002
                return False

        return _ConnCtx()


@pytest.mark.asyncio
async def test_report_build_tool_json_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Prepare a minimal cache manifest + rows payload
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    rows_path = cache_dir / "rows.jsonl"
    rows = [{"id": 1, "value": "a"}, {"id": 2, "value": "b"}]
    with rows_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row))
            fh.write("\n")

    manifest_json_path = cache_dir / "manifest.json"
    manifest_json_path.write_text(
        json.dumps(
            {
                "version": 1,
                "cache_key": "demo-key",
                "created_at": "2025-01-01T00:00:00Z",
                "profile": "test-profile",
                "context": {},
                "rowcount": len(rows),
                "duration_ms": 10,
                "statement_sha256": "deadbeef",
                "result_json": rows_path.name,
                "result_csv": None,
                "columns": ["id", "value"],
                "truncated": False,
                "key_metrics": {"total_rows": len(rows)},
                "insights": ["example insight"],
            }
        ),
        encoding="utf-8",
    )

    # History file is required by HistoryIndex but can be empty
    history_path = tmp_path / "history.jsonl"
    history_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "igloo_mcp.reporting.builder.resolve_history_path",
        lambda: history_path,
        raising=True,
    )

    # Manifest referencing the cache manifest directly
    report_manifest_path = tmp_path / "report.yaml"
    report_manifest_path.write_text(
        f"""
id: "demo-report"
templates:
  main: "templates/report.md"
datasets:
  - name: "cached_dataset"
    source:
      cache_manifest: "{manifest_json_path}"
outputs:
  - name: "default"
    format: "json"
    path: "reports/demo.json"
""".lstrip(),
        encoding="utf-8",
    )

    server = CapturingServer()
    service = StubService()
    # Registration will attach all tools, including the reporting helpers
    mcp_server.register_igloo_mcp(server, service)

    tool = server.tools["report_build"]
    result = await tool(str(report_manifest_path), "default", "json", False, None)

    assert result["format"] == "json"
    assert result["manifest_path"] == str(report_manifest_path.resolve())

    body = result["body"]
    payload = json.loads(body)
    assert "datasets" in payload
    assert "cached_dataset" in payload["datasets"]
    ds = payload["datasets"]["cached_dataset"]
    assert ds["columns"] == ["id", "value"]
    assert ds["key_metrics"]["total_rows"] == len(rows)
    assert len(ds["rows"]) == len(rows)


@pytest.mark.asyncio
async def test_report_lint_tool_flags_missing_cache(tmp_path: Path) -> None:
    # History file can be empty; dataset references a missing cache manifest
    history_path = tmp_path / "history.jsonl"
    history_path.write_text("", encoding="utf-8")

    # Small manifest with an unresolvable dataset
    report_manifest_path = tmp_path / "report.yaml"
    report_manifest_path.write_text(
        """
id: "lint-demo"
templates:
  main: "templates/report.md"
datasets:
  - name: "missing"
    source:
      cache_manifest: "nonexistent/manifest.json"
outputs:
  - name: "default"
    format: "json"
    path: "reports/demo.json"
""".lstrip(),
        encoding="utf-8",
    )

    server = CapturingServer()
    service = StubService()
    mcp_server.register_igloo_mcp(server, service)

    tool = server.tools["report_lint"]
    result = await tool(str(report_manifest_path))

    assert result["manifest_path"] == str(report_manifest_path.resolve())
    assert result["ok"] is False
    assert result["issues"]
