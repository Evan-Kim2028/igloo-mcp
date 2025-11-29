"""Validation helpers for MCP tool parameter validation.

This module provides standardized validation error formatting for common
parameter validation scenarios, extracted from mcp_server.py.
"""

from __future__ import annotations

from typing import Any, List, Optional, TypeVar

from pydantic import ValidationError

from igloo_mcp.mcp.exceptions import MCPValidationError

T = TypeVar("T")


def format_pydantic_validation_error(
    error: ValidationError,
    tool_name: str = "tool",
) -> MCPValidationError:
    """Format a Pydantic ValidationError as MCPValidationError with helpful messages.

    This function provides enhanced error messages for common validation
    scenarios, particularly for the execute_query tool's 'reason' parameter.

    Args:
        error: Pydantic ValidationError instance
        tool_name: Name of the tool (for context in error messages)

    Returns:
        MCPValidationError with formatted validation errors and hints
    """
    errors = error.errors()
    validation_errors: List[str] = []
    hints: List[str] = []

    for err in errors:
        field = err["loc"][0] if err["loc"] else None
        error_type = err["type"]

        # Handle 'reason' parameter validation (common in execute_query)
        if field == "reason":
            if error_type == "missing":
                validation_errors.append("Missing required parameter: 'reason'")
                hints.extend(
                    [
                        "The 'reason' parameter is required for query auditability",
                        "Add a brief explanation (5+ characters) describing why you're running the query",
                        "Examples: 'Debug null customer records', 'Validate revenue totals', 'Explore schema'",
                    ]
                )
            elif error_type == "string_too_short":
                provided = err.get("input", "")
                validation_errors.append(f"Parameter 'reason' is too short: '{provided}' ({len(str(provided))} chars)")
                hints.extend(
                    [
                        f"Minimum length: 5 characters (you provided {len(str(provided))})",
                        "Be more descriptive - explain the query's purpose",
                        "Examples: 'Debug sales spike on 2025-01-15', 'Count active users for monthly report'",
                    ]
                )
            else:
                validation_errors.append(f"Field 'reason': {err.get('msg', 'Validation error')}")

        # Handle timeout_seconds validation
        elif field == "timeout_seconds":
            if "must be an integer" in str(err.get("msg", "")):
                validation_errors.append("Invalid parameter type: timeout_seconds must be an integer")
                hints.extend(
                    [
                        "Use a number without quotes: timeout_seconds=480",
                        "Examples: 30, 60, 300, 480",
                    ]
                )
            elif "must be between" in str(err.get("msg", "")):
                validation_errors.append("Invalid parameter value: timeout_seconds out of range")
                hints.extend(
                    [
                        "Use a timeout between 1 and 3600 seconds",
                        f"Received: {err.get('input', 'unknown')}",
                    ]
                )
            else:
                validation_errors.append(f"Field 'timeout_seconds': {err.get('msg', 'Validation error')}")

        # Generic field validation
        else:
            field_path = ".".join(str(loc) for loc in err.get("loc", []))
            validation_errors.append(f"{field_path}: {err.get('msg', 'Validation error')}")

    # Default hints if none provided
    if not hints:
        hints = [
            "Check parameter types and required fields",
            f"Review {tool_name} parameter schema",
        ]

    return MCPValidationError(
        f"Parameter validation failed for {tool_name}",
        validation_errors=validation_errors,
        hints=hints,
    )


def format_sql_permission_error(
    error_message: str,
) -> MCPValidationError:
    """Format SQL permission error with configuration guidance.

    Args:
        error_message: Original error message

    Returns:
        MCPValidationError with enhanced guidance
    """
    hints = [
        "Set environment variable: IGLOO_MCP_SQL_PERMISSIONS='write'",
        "Or configure in your MCP client settings",
        "Warning: Enabling writes removes safety guardrails",
        "Use with caution in production environments",
    ]

    return MCPValidationError(
        f"{error_message}\n\n"
        "Safety Guardrails: This operation is blocked by default.\n\n"
        "To enable write operations:\n"
        "  1. Set environment variable: IGLOO_MCP_SQL_PERMISSIONS='write'\n"
        "  2. Or configure in your MCP client settings\n\n"
        "Warning: Enabling writes removes safety guardrails.\n"
        "Use with caution in production environments.",
        validation_errors=[error_message],
        hints=hints,
    )


def format_parameter_type_error(
    field: str,
    expected_type: str,
    received_type: str,
    examples: Optional[List[Any]] = None,
) -> MCPValidationError:
    """Format parameter type error with helpful examples.

    Args:
        field: Field name
        expected_type: Expected type name
        received_type: Actual type received
        examples: Optional list of example values

    Returns:
        MCPValidationError with type guidance
    """
    validation_errors = [
        f"Field '{field}': Expected {expected_type}, got {received_type}",
    ]

    hints = [
        f"Use {expected_type} for '{field}' parameter",
    ]

    if examples:
        hints.append(f"Examples: {', '.join(str(ex) for ex in examples)}")

    return MCPValidationError(
        f"Invalid parameter type for '{field}'",
        validation_errors=validation_errors,
        hints=hints,
    )


# New validation helper functions for v0.3.4


def validate_required_string(
    value: Any,
    field_name: str,
    min_length: int = 1,
    max_length: Optional[int] = None,
) -> str:
    """Validate required string parameter.

    Args:
        value: Value to validate
        field_name: Name of the field
        min_length: Minimum string length (default: 1)
        max_length: Optional maximum string length

    Returns:
        Validated string value

    Raises:
        MCPValidationError: If validation fails
    """
    if value is None:
        raise MCPValidationError(
            f"{field_name} is required",
            validation_errors=[f"{field_name} cannot be None"],
            hints=[f"Provide a valid {field_name}"],
        )

    if not isinstance(value, str):
        raise MCPValidationError(
            f"{field_name} must be a string",
            validation_errors=[f"Expected string, got {type(value).__name__}"],
            hints=[f"Provide {field_name} as a string"],
        )

    value = value.strip()
    if len(value) < min_length:
        raise MCPValidationError(
            f"{field_name} cannot be empty",
            validation_errors=[f"{field_name} must be at least {min_length} characters"],
            hints=[f"Provide a non-empty {field_name}"],
        )

    if max_length and len(value) > max_length:
        raise MCPValidationError(
            f"{field_name} exceeds maximum length",
            validation_errors=[f"{field_name} must be at most {max_length} characters"],
            hints=[f"Reduce {field_name} length to {max_length} or less"],
        )

    return value


def validate_numeric_range(
    value: Any,
    field_name: str,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    allow_none: bool = False,
) -> Optional[float]:
    """Validate numeric parameter within range.

    Args:
        value: Value to validate
        field_name: Name of the field
        min_value: Optional minimum value
        max_value: Optional maximum value
        allow_none: Whether None is acceptable (default: False)

    Returns:
        Validated numeric value or None if allow_none=True

    Raises:
        MCPValidationError: If validation fails
    """
    if value is None:
        if allow_none:
            return None
        raise MCPValidationError(
            f"{field_name} is required",
            validation_errors=[f"{field_name} cannot be None"],
            hints=[f"Provide a valid {field_name}"],
        )

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        raise MCPValidationError(
            f"{field_name} must be a number",
            validation_errors=[f"Cannot convert {value!r} to number"],
            hints=[f"Provide {field_name} as a number (e.g., 480.0)"],
        )

    if min_value is not None and numeric_value < min_value:
        raise MCPValidationError(
            f"{field_name} below minimum",
            validation_errors=[f"{field_name}={numeric_value} is below minimum {min_value}"],
            hints=[f"Increase {field_name} to at least {min_value}"],
        )

    if max_value is not None and numeric_value > max_value:
        raise MCPValidationError(
            f"{field_name} exceeds maximum",
            validation_errors=[f"{field_name}={numeric_value} exceeds maximum {max_value}"],
            hints=[f"Reduce {field_name} to at most {max_value}"],
        )

    return numeric_value


def validate_enum_value(
    value: Any,
    field_name: str,
    allowed_values: List[str],
    allow_none: bool = False,
) -> Optional[str]:
    """Validate string is one of allowed values.

    Args:
        value: Value to validate
        field_name: Name of the field
        allowed_values: List of allowed string values
        allow_none: Whether None is acceptable (default: False)

    Returns:
        Validated value or None if allow_none=True

    Raises:
        MCPValidationError: If validation fails
    """
    if value is None:
        if allow_none:
            return None
        raise MCPValidationError(
            f"{field_name} is required",
            validation_errors=[f"{field_name} cannot be None"],
            hints=[f"Choose one of: {', '.join(allowed_values)}"],
        )

    if value not in allowed_values:
        raise MCPValidationError(
            f"Invalid {field_name}",
            validation_errors=[f"{value!r} is not a valid {field_name}"],
            hints=[f"Choose one of: {', '.join(allowed_values)}"],
        )

    return value
