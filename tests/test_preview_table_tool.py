"""Tests for PreviewTableTool execution."""

from __future__ import annotations

import pytest

from igloo_mcp.config import Config
from igloo_mcp.mcp.tools.preview_table import PreviewTableTool
from igloo_mcp.snow_cli import QueryOutput


class StubQueryService:
    def __init__(self) -> None:
        self.last_session = None
        self.calls: list[tuple[str, dict[str, object] | None, str | None]] = []

    def session_from_mapping(self, mapping):
        self.last_session = {k: v for k, v in mapping.items() if v}
        return self.last_session

    def execute_with_service(
        self,
        query: str,
        *,
        service=None,  # noqa: ANN001
        session=None,
        output_format=None,
    ) -> QueryOutput:
        self.calls.append((query, session, output_format))
        return QueryOutput(
            raw_stdout="",
            raw_stderr="",
            returncode=0,
            rows=[{"ID": 1, "NAME": "Alice"}],
            columns=["ID", "NAME"],
        )


class StubSnowflakeService:
    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return "<StubSnowflakeService>"


@pytest.mark.asyncio
async def test_preview_table_success():
    config = Config.from_env()
    service = StubSnowflakeService()
    query_service = StubQueryService()

    tool = PreviewTableTool(config, service, query_service)

    result = await tool.execute(
        table_name="PUBLIC.CUSTOMERS",
        limit=5,
        warehouse="ANALYTICS_WH",
        database="ANALYTICS",
    )

    assert result["status"] == "success"
    preview = result["preview"]
    assert preview["columns"] == ["ID", "NAME"]
    assert preview["rows"] == [{"ID": 1, "NAME": "Alice"}]
    assert preview["limit"] == 5

    assert query_service.last_session == {
        "warehouse": "ANALYTICS_WH",
        "database": "ANALYTICS",
    }
    query, session, fmt = query_service.calls[-1]
    assert query == "SELECT * FROM PUBLIC.CUSTOMERS LIMIT 5"
    assert session == query_service.last_session
    assert fmt == "json"


@pytest.mark.asyncio
async def test_preview_table_invalid_input():
    config = Config.from_env()
    tool = PreviewTableTool(config, StubSnowflakeService(), StubQueryService())

    with pytest.raises(ValueError):
        await tool.execute(table_name="", limit=10)

    with pytest.raises(ValueError):
        await tool.execute(table_name="PUBLIC.CUSTOMERS", limit=0)


@pytest.mark.asyncio
async def test_preview_table_runtime_error():
    config = Config.from_env()
    service = StubSnowflakeService()
    query_service = StubQueryService()

    def execute_failure(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    tool = PreviewTableTool(config, service, query_service)
    query_service.execute_with_service = execute_failure  # type: ignore[assignment]

    with pytest.raises(RuntimeError) as exc_info:
        await tool.execute(table_name="PUBLIC.CUSTOMERS", limit=1)

    assert "Failed to preview table 'PUBLIC.CUSTOMERS'" in str(exc_info.value)
