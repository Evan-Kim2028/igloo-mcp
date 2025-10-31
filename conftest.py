"""Pytest configuration ensuring offline tests run by default."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--snowflake",
        action="store_true",
        default=False,
        help="run tests that require live Snowflake connectivity",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "offline: test relies only on local fixtures and should run in CI by default",
    )
    config.addinivalue_line(
        "markers",
        "requires_snowflake: test depends on a live Snowflake account "
        "and is skipped unless --snowflake is passed",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    run_live = config.getoption("--snowflake")
    for item in items:
        if "requires_snowflake" in item.keywords:
            if not run_live:
                item.add_marker(
                    pytest.mark.skip(
                        reason="requires --snowflake to run against live Snowflake"
                    )
                )
            continue
        item.add_marker(pytest.mark.offline)
