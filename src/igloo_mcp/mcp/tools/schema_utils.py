"""Utility helpers for building JSON Schemas used by MCP tools."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

SEGMENT_PATTERN = r'(?:[A-Za-z_][A-Za-z0-9_$]*|"(?:""|[^"])+")'
IDENTIFIER_PATTERN = rf"^{SEGMENT_PATTERN}$"
QUALIFIED_NAME_PATTERN = rf"^{SEGMENT_PATTERN}(?:\.{SEGMENT_PATTERN}){{0,2}}$"


def string_schema(
    description: str,
    *,
    title: str | None = None,
    examples: Iterable[str] | None = None,
    pattern: str | None = None,
    default: str | None = None,
) -> dict[str, Any]:
    """Create a basic string schema with optional pattern and examples."""
    schema: dict[str, Any] = {
        "type": "string",
        "description": description,
    }
    if title:
        schema["title"] = title
    if pattern:
        schema["pattern"] = pattern
    if examples:
        schema["examples"] = list(examples)
    if default is not None:
        schema["default"] = default
    return schema


def snowflake_identifier_schema(
    description: str,
    *,
    title: str | None = None,
    examples: Iterable[str] | None = None,
    default: str | None = None,
) -> dict[str, Any]:
    """Schema for Snowflake identifiers (warehouse, database, schema, role)."""
    return string_schema(
        description,
        title=title,
        examples=examples,
        default=default,
        pattern=IDENTIFIER_PATTERN,
    )


def fully_qualified_object_schema(
    description: str,
    *,
    title: str | None = None,
    examples: Iterable[str] | None = None,
    default: str | None = None,
) -> dict[str, Any]:
    """Schema for fully qualified names (DATABASE.SCHEMA.OBJECT)."""
    return string_schema(
        description,
        title=title,
        examples=examples,
        default=default,
        pattern=QUALIFIED_NAME_PATTERN,
    )


def integer_schema(
    description: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
    default: int | None = None,
    examples: Iterable[int] | None = None,
) -> dict[str, Any]:
    """Schema for integer parameters."""
    schema: dict[str, Any] = {
        "type": "integer",
        "description": description,
    }
    if minimum is not None:
        schema["minimum"] = minimum
    if maximum is not None:
        schema["maximum"] = maximum
    if default is not None:
        schema["default"] = default
    if examples is not None:
        schema["examples"] = list(examples)
    return schema


def boolean_schema(
    description: str,
    *,
    default: bool | None = None,
    examples: Iterable[bool] | None = None,
) -> dict[str, Any]:
    """Schema for boolean flags."""
    schema: dict[str, Any] = {
        "type": "boolean",
        "description": description,
    }
    if default is not None:
        schema["default"] = default
    if examples is not None:
        schema["examples"] = list(examples)
    return schema


def enum_schema(
    description: str,
    *,
    values: Iterable[str],
    default: str | None = None,
    examples: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Schema for enumerated string values."""
    schema = string_schema(
        description,
        examples=examples,
        default=default,
    )
    schema["enum"] = list(values)
    return schema
