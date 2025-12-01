"""Tests for MCP utility helpers."""

from __future__ import annotations

from collections import namedtuple
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest

from igloo_mcp.mcp.utils import get_profile_recommendations, json_compatible


def test_get_profile_recommendations_without_profile():
    tips = get_profile_recommendations()
    assert any("No profile specified" in tip for tip in tips)
    assert any("snow connection list" in tip for tip in tips)


def test_get_profile_recommendations_with_profile():
    tips = get_profile_recommendations("DEV")
    assert "Profile 'DEV' specified" in tips[0]
    assert any("Verify profile exists" in tip for tip in tips)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (True, True),
        (1, 1),
        (3.14, 3.14),
        ("text", "text"),
        (Decimal(5), 5),
        (Decimal("2.5"), 2.5),
        (datetime(2024, 1, 2, 3, 4, 5), "2024-01-02T03:04:05"),
        (date(2024, 1, 2), "2024-01-02"),
        (time(3, 4, 5), "03:04:05"),
        (timedelta(seconds=90), 90.0),
        (
            UUID("12345678-1234-5678-1234-567812345678"),
            "12345678-1234-5678-1234-567812345678",
        ),
        (b"bytes", "bytes"),
    ],
)
def test_json_compatible_basic_types(value, expected):
    assert json_compatible(value) == expected


def test_json_compatible_bytes_hex():
    assert json_compatible(b"\xff") == "ff"


def test_json_compatible_iterables_and_dicts():
    data = {
        "items": {1, 2},
        "tuple": (Decimal(1), Decimal("2.5")),
        "list": [datetime(2024, 1, 1, 1, 1), Decimal(3)],
    }
    result = json_compatible(data)
    assert result["items"] == [1, 2]
    assert result["tuple"] == [1, 2.5]
    assert result["list"][0].startswith("2024-01-01T01:01")
    assert result["list"][1] == 3


def test_json_compatible_namedtuple_and_namespace():
    Row = namedtuple("Row", ["col"])
    ns = SimpleNamespace(a=Decimal(4))
    result = json_compatible({"row": Row(col=datetime(2024, 1, 2)), "ns": ns})
    assert result["row"][0].startswith("2024-01-02T")
    assert result["ns"]["a"] == 4


def test_json_compatible_fallback():
    class Custom:
        __slots__ = ()

        def __str__(self) -> str:
            return "custom-value"

    assert json_compatible(Custom()) == "custom-value"
