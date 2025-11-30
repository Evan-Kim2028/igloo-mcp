"""Comprehensive error handling strategy for igloo-mcp."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, TypeVar

from .snow_cli import SnowCLIError

T = TypeVar("T")

logger = logging.getLogger(__name__)


@dataclass
class ErrorContext:
    """Context information for error handling."""

    operation: str
    database: str | None = None
    schema: str | None = None
    object_name: str | None = None
    query: str | None = None
    request_id: str | None = None
    timing: dict[str, float] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)

    def add_timing(self, key: str, duration_ms: float) -> None:
        """Add timing information."""
        self.timing[key] = duration_ms

    def get_total_duration_ms(self) -> float | None:
        """Get total duration if available."""
        return self.timing.get("total_duration_ms")

    def sanitize_parameters(self) -> dict[str, Any]:
        """Return sanitized parameters (remove sensitive data, truncate long values)."""
        sanitized = {}
        for key, value in self.parameters.items():
            # Skip sensitive fields
            if any(sensitive in key.lower() for sensitive in ["password", "secret", "token", "key", "credential"]):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, str) and len(value) > 200:
                sanitized[key] = value[:200] + "..."
            else:
                sanitized[key] = value
        return sanitized


class SnowflakeConnectionError(Exception):
    """Raised when Snowflake connection issues occur."""

    pass


class SnowflakePermissionError(Exception):
    """Raised when insufficient permissions are detected."""

    pass


class SnowflakeTimeoutError(Exception):
    """Raised when operations timeout."""

    pass


class SnowflakeError(Exception):
    """Base class for all Snowflake-related errors."""

    pass


class ProfileConfigurationError(SnowflakeError):
    """Raised when there are profile configuration issues."""

    def __init__(
        self,
        message: str,
        *,
        profile_name: str | None = None,
        available_profiles: list[str] | None = None,
        config_path: str | None = None,
    ):
        super().__init__(message)
        self.profile_name = profile_name
        self.available_profiles = available_profiles or []
        self.config_path = config_path

    def __str__(self) -> str:
        base_msg = super().__str__()
        context_parts = []

        if self.profile_name:
            context_parts.append(f"Profile: {self.profile_name}")
        if self.config_path:
            context_parts.append(f"Config: {self.config_path}")
        if self.available_profiles:
            context_parts.append(f"Available: {', '.join(self.available_profiles)}")

        if context_parts:
            return f"{base_msg} ({'; '.join(context_parts)})"
        return base_msg


def categorize_snowflake_error(error: SnowCLIError, context: ErrorContext) -> Exception:
    """Categorize a SnowCLIError into more specific error types."""
    error_msg = str(error).lower()

    # Timeout errors (check first since timeout can be in connection errors)
    if any(keyword in error_msg for keyword in ["timed out", "timeout occurred", "request timeout"]):
        return SnowflakeTimeoutError(f"Timeout during {context.operation}: {error}")

    # Connection-related errors
    if any(keyword in error_msg for keyword in ["connection", "network", "timeout", "unreachable", "refused"]):
        return SnowflakeConnectionError(f"Connection failed for {context.operation}: {error}")

    # Permission-related errors
    if any(
        keyword in error_msg
        for keyword in [
            "permission",
            "privilege",
            "access denied",
            "unauthorized",
            "forbidden",
        ]
    ):
        return SnowflakePermissionError(f"Permission denied for {context.operation}: {error}")

    # Return original error if not categorized
    return error


def handle_snowflake_errors(
    operation: str,
    database: str | None = None,
    schema: str | None = None,
    object_name: str | None = None,
    fallback_value: Any = None,
    reraise: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T | Any]]:
    """Decorator to handle Snowflake errors with context and proper categorization."""

    def decorator(func: Callable[..., T]) -> Callable[..., T | Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T | Any:
            context = ErrorContext(
                operation=operation,
                database=database,
                schema=schema,
                object_name=object_name,
            )

            try:
                return func(*args, **kwargs)
            except SnowCLIError as e:
                categorized_error = categorize_snowflake_error(e, context)

                # Log the error with context
                logger.error(
                    f"Snowflake operation failed: {context.operation}",
                    extra={
                        "database": context.database,
                        "schema": context.schema,
                        "object_name": context.object_name,
                        "error_type": type(categorized_error).__name__,
                        "original_error": str(e),
                    },
                )

                if reraise:
                    raise categorized_error from e
                else:
                    logger.warning(f"Returning fallback value for {context.operation}")
                    return fallback_value
            except Exception as e:
                logger.error(
                    f"Unexpected error in {context.operation}: {e}",
                    extra={"operation": context.operation},
                )
                if reraise:
                    raise
                else:
                    return fallback_value

        return wrapper

    return decorator


def safe_execute(
    func: Callable[..., T],
    *args: Any,
    context: ErrorContext | None = None,
    fallback_value: Any = None,
    **kwargs: Any,
) -> T | Any:
    """Execute a function safely with proper error handling."""
    try:
        return func(*args, **kwargs)
    except SnowCLIError as e:
        ctx = context or ErrorContext(operation="unknown")
        categorized_error = categorize_snowflake_error(e, ctx)

        logger.warning(
            f"Safe execution failed for {ctx.operation}: {categorized_error}",
            extra={"context": ctx},
        )
        return fallback_value
    except Exception as e:
        ctx = context or ErrorContext(operation="unknown")
        logger.warning(
            f"Unexpected error in safe execution for {ctx.operation}: {e}",
            extra={"context": ctx},
        )
        return fallback_value


def format_error_response(
    status: str,
    error_type: str,
    message: str,
    context: ErrorContext | None = None,
    hints: list[str] | None = None,
    additional_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Format a standardized error response.

    Args:
        status: Error status (e.g., "error", "validation_failed", "selector_error")
        error_type: Specific error category (e.g., "unexpected", "schema_validation")
        message: Human-readable error message
        context: Optional error context with request_id, timing, parameters
        hints: Optional list of actionable suggestions
        additional_data: Optional additional error-specific data

    Returns:
        Standardized error response dictionary
    """
    response: dict[str, Any] = {
        "status": status,
        "error_type": error_type,
        "message": message,
    }

    if context:
        if context.request_id:
            response["request_id"] = context.request_id

        if context.timing:
            response["timing"] = context.timing

        if context.parameters:
            response["context"] = {
                "operation": context.operation,
                "parameters": context.sanitize_parameters(),
            }
            # Add database/schema context if available
            if context.database:
                response["context"]["database"] = context.database
            if context.schema:
                response["context"]["schema"] = context.schema
            if context.object_name:
                response["context"]["object_name"] = context.object_name
        else:
            response["context"] = {
                "operation": context.operation,
            }

    if hints:
        response["hints"] = hints

    if additional_data:
        response.update(additional_data)

    return response


class ErrorAggregator:
    """Aggregates errors during batch operations."""

    def __init__(self) -> None:
        self.errors: dict[str, Exception] = {}
        self.warnings: dict[str, str] = {}

    def add_error(self, key: str, error: Exception) -> None:
        """Add an error for a specific key."""
        self.errors[key] = error
        logger.error(f"Error for {key}: {error}")

    def add_warning(self, key: str, message: str) -> None:
        """Add a warning for a specific key."""
        self.warnings[key] = message
        logger.warning(f"Warning for {key}: {message}")

    def has_errors(self) -> bool:
        """Check if any errors were recorded."""
        return len(self.errors) > 0

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all errors and warnings."""
        return {
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": {k: str(v) for k, v in self.errors.items()},
            "warnings": self.warnings,
        }
