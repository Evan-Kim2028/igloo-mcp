from types import SimpleNamespace

import pytest

from igloo_mcp.config import SnowflakeConfig
from igloo_mcp.service_layer.query_service import QueryService, SnowRestClient
from igloo_mcp.snow_cli import QueryOutput


class DummyRestClient:
    def __init__(self) -> None:
        self.calls = []

    def run_query(self, query: str, *, ctx_overrides=None, timeout=None) -> QueryOutput:
        self.calls.append(query)
        return QueryOutput("{}", "", 0, rows=[{"VALUE": 1}], columns=["VALUE"])


def test_query_service_rest_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyRestClient()

    def fake_from_env(**_: object) -> DummyRestClient:
        return dummy

    monkeypatch.setenv("IGLOO_MCP_SNOW_DRIVER", "rest")
    monkeypatch.setattr(SnowRestClient, "from_env", staticmethod(fake_from_env))

    context = SimpleNamespace(
        config=SimpleNamespace(snowflake=SnowflakeConfig(profile="test"))
    )
    service = QueryService(context=context)
    result = service.execute("SELECT 1")

    assert dummy.calls == ["SELECT 1"]
    assert result.rows == [{"VALUE": 1}]
