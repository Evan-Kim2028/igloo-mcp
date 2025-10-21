"""Tests for enhanced MCP tool parameter schemas and metadata."""

from __future__ import annotations

import re
from typing import Any
from unittest.mock import Mock

import pytest
from jsonschema import Draft202012Validator

from igloo_mcp.catalog import CatalogService
from igloo_mcp.config import Config, SnowflakeConfig
from igloo_mcp.mcp.tools.build_catalog import BuildCatalogTool
from igloo_mcp.mcp.tools.build_dependency_graph import BuildDependencyGraphTool
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.mcp.tools.get_catalog_summary import GetCatalogSummaryTool
from igloo_mcp.mcp.tools.health import HealthCheckTool
from igloo_mcp.mcp.tools.preview_table import PreviewTableTool
from igloo_mcp.mcp.tools.schema_utils import IDENTIFIER_PATTERN, QUALIFIED_NAME_PATTERN
from igloo_mcp.mcp.tools.test_connection import ConnectionTestTool


@pytest.fixture()
def base_config() -> Config:
    """Provide a minimal config for tool instantiation."""
    return Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))


def _validate_schema(schema: dict[str, Any]) -> None:
    """Ensure schema conforms to JSON Schema draft 2020-12."""
    Draft202012Validator.check_schema(schema)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False


def test_execute_query_schema(base_config: Config) -> None:
    tool = ExecuteQueryTool(
        config=base_config,
        snowflake_service=Mock(),
        query_service=Mock(),
        health_monitor=None,
    )

    schema = tool.get_parameter_schema()
    _validate_schema(schema)

    assert schema["required"] == ["statement"]
    props = schema["properties"]

    statement = props["statement"]
    assert statement["minLength"] == 1
    assert "examples" in statement

    for override in ("warehouse", "database", "schema", "role"):
        override_schema = props[override]
        assert override_schema["pattern"] == IDENTIFIER_PATTERN
        assert re.fullmatch(IDENTIFIER_PATTERN, '"Analytics-WH"')

    timeout = props["timeout_seconds"]
    assert timeout["minimum"] == 1
    assert timeout["maximum"] == 3600
    assert timeout["default"] == 30

    verbose = props["verbose_errors"]
    assert verbose["type"] == "boolean"
    assert verbose["default"] is False

    # Discovery metadata
    assert tool.category == "query"
    assert {"sql", "execute"}.issubset(set(tool.tags))
    assert isinstance(tool.usage_examples, list)
    assert tool.usage_examples
    for example in tool.usage_examples:
        assert {"description", "parameters"} <= set(example.keys())


def test_build_catalog_schema(base_config: Config) -> None:
    tool = BuildCatalogTool(
        config=base_config,
        catalog_service=Mock(spec=CatalogService),
    )

    schema = tool.get_parameter_schema()
    _validate_schema(schema)

    props = schema["properties"]

    assert props["output_dir"]["default"] == "./data_catalogue"
    assert props["output_dir"]["type"] == "string"

    db = props["database"]
    assert db["pattern"] == IDENTIFIER_PATTERN

    account = props["account"]
    assert account["type"] == "boolean"
    assert account["default"] is False

    fmt = props["format"]
    assert fmt["enum"] == ["json", "jsonl"]
    assert fmt["default"] == "json"

    assert "allOf" in schema
    assert any(
        "account" in cond.get("if", {}).get("properties", {})
        for cond in schema["allOf"]
    )

    # Discovery metadata
    assert tool.category == "metadata"
    assert {"catalog", "metadata"}.issubset(set(tool.tags))
    assert isinstance(tool.usage_examples, list)
    assert tool.usage_examples
    for example in tool.usage_examples:
        assert {"description", "parameters"} <= set(example.keys())


def test_preview_table_schema(base_config: Config) -> None:
    tool = PreviewTableTool(
        config=base_config,
        snowflake_service=Mock(),
        query_service=Mock(),
    )

    schema = tool.get_parameter_schema()
    _validate_schema(schema)
    assert schema["required"] == ["table_name"]

    props = schema["properties"]

    table_name = props["table_name"]
    assert table_name["pattern"] == QUALIFIED_NAME_PATTERN
    assert "examples" in table_name
    assert re.fullmatch(
        QUALIFIED_NAME_PATTERN,
        '"Sales Analytics"."Reporting"."Orders"',
    )

    limit = props["limit"]
    assert limit["minimum"] == 1
    assert limit["default"] == 100

    for override in ("warehouse", "database", "schema"):
        override_schema = props[override]
        assert override_schema["pattern"] == IDENTIFIER_PATTERN

    assert tool.category == "query"
    assert {"preview", "table"}.issubset(set(tool.tags))
    assert isinstance(tool.usage_examples, list)
    assert tool.usage_examples
    for example in tool.usage_examples:
        assert {"description", "parameters"} <= set(example.keys())


def test_build_dependency_graph_schema() -> None:
    tool = BuildDependencyGraphTool(dependency_service=Mock())

    schema = tool.get_parameter_schema()
    _validate_schema(schema)

    props = schema["properties"]

    for name in ("database", "schema"):
        identifier = props[name]
        assert identifier["pattern"] == IDENTIFIER_PATTERN
        assert re.fullmatch(IDENTIFIER_PATTERN, '"Sales Analytics"')

    account_scope = props["account_scope"]
    assert account_scope["type"] == "boolean"
    assert account_scope["default"] is True

    fmt = props["format"]
    assert fmt["enum"] == ["json", "dot"]
    assert fmt["default"] == "json"

    assert tool.category == "metadata"
    assert {"dependencies", "lineage"}.issubset(set(tool.tags))
    assert tool.usage_examples
    for example in tool.usage_examples:
        assert {"description", "parameters"} <= set(example.keys())


@pytest.mark.anyio
async def test_build_dependency_graph_execute_passes_scope() -> None:
    service = Mock()
    service.build_dependency_graph.return_value = {"status": "success"}

    tool = BuildDependencyGraphTool(dependency_service=service)

    result = await tool.execute(
        database="ANALYTICS",
        schema="REPORTING",
        account_scope=False,
        format="dot",
    )

    service.build_dependency_graph.assert_called_once_with(
        database="ANALYTICS",
        schema="REPORTING",
        account_scope=False,
        format="dot",
        output_dir="./dependencies",
    )
    assert result == {"status": "success"}


def test_get_catalog_summary_schema() -> None:
    tool = GetCatalogSummaryTool(catalog_service=Mock())

    schema = tool.get_parameter_schema()
    _validate_schema(schema)

    props = schema["properties"]
    catalog_dir = props["catalog_dir"]
    assert catalog_dir["type"] == "string"
    assert catalog_dir["default"] == "./data_catalogue"

    assert tool.category == "metadata"
    assert {"catalog", "summary"}.issubset(set(tool.tags))
    assert tool.usage_examples


def test_test_connection_schema(base_config: Config) -> None:
    tool = ConnectionTestTool(config=base_config, snowflake_service=Mock())

    schema = tool.get_parameter_schema()
    _validate_schema(schema)
    assert schema["properties"] == {}

    assert tool.category == "diagnostics"
    assert {"connection", "health"}.issubset(set(tool.tags))
    assert tool.usage_examples


def test_health_check_schema(base_config: Config) -> None:
    tool = HealthCheckTool(
        config=base_config,
        snowflake_service=Mock(),
        health_monitor=Mock(),
        resource_manager=Mock(),
    )

    schema = tool.get_parameter_schema()
    _validate_schema(schema)

    props = schema["properties"]
    for flag in ("include_cortex", "include_profile", "include_catalog"):
        flag_schema = props[flag]
        assert flag_schema["type"] == "boolean"

    assert props["include_cortex"]["default"] is True
    assert props["include_profile"]["default"] is True
    assert props["include_catalog"]["default"] is False

    assert tool.category == "diagnostics"
    assert {"health", "profile"}.issubset(set(tool.tags))
    assert tool.usage_examples
