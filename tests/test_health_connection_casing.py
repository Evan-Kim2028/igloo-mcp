"""Casing behavior test for HealthCheckTool connection info.

Ensures that DictCursor results with UPPERCASE keys are handled.
"""

from __future__ import annotations

from typing import Any

import pytest

from igloo_mcp.config import Config
from igloo_mcp.mcp.tools.health import HealthCheckTool


class _UpperDictCursor:
    def __init__(self) -> None:
        self._current: dict[str, Any] = {}

    def execute(self, query: str) -> None:
        # Emulate UPPERCASE column labels typically seen with DictCursor
        key = query.split("CURRENT_", 1)[-1].split("()")[0]
        label = key.split()[0]  # strip potential "as ..." suffix
        self._current = {label: label}

    def fetchone(self) -> dict[str, Any]:
        return self._current


class _Conn:
    def __init__(self, cursor: _UpperDictCursor) -> None:
        self.cursor = cursor

    def __enter__(self) -> tuple[None, _UpperDictCursor]:
        return None, self.cursor

    def __exit__(self, exc_type, exc, tb) -> bool:  # pragma: no cover - simple stub
        return False


class _Svc:
    def __init__(self) -> None:
        self._cursor = _UpperDictCursor()

    def get_query_tag_param(self) -> dict[str, Any]:
        return {}

    def get_connection(self, **kwargs: Any) -> _Conn:
        return _Conn(self._cursor)


@pytest.mark.asyncio
async def test_health_connection_handles_uppercase_keys() -> None:
    config = Config.from_env()
    tool = HealthCheckTool(config=config, snowflake_service=_Svc())

    result = await tool.execute(response_mode="full")

    conn = result["checks"]["connection"]
    # Values should not be None when uppercase keys are returned
    assert conn["connected"] is True
    assert conn["warehouse"] is not None
    assert conn["database"] is not None
    assert conn["schema"] is not None
    assert conn["role"] is not None
