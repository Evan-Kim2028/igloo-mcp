"""Comprehensive error handling strategy for igloo-mcp."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from .snow_cli import SnowCLIError

T = TypeVar("T")

logger = logging.getLogger(__name__)


@dataclass
class ErrorContext:
    """Context information for error handling."""

    operation: str
    database: Optional[str] = None
    schema: Optional[str] = None
    object_name: Optional[str] = None
    query: Optional[str] = None


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
    if any(
        keyword in error_msg
        for keyword in ["timed out", "timeout occurred", "request timeout"]
    ):
        return SnowflakeTimeoutError(f"Timeout during {context.operation}: {error}")

    # Connection-related errors
    if any(
        keyword in error_msg
        for keyword in ["connection", "network", "timeout", "unreachable", "refused"]
    ):
        return SnowflakeConnectionError(
            f"Connection failed for {context.operation}: {error}"
        )

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
        return SnowflakePermissionError(
            f"Permission denied for {context.operation}: {error}"
        )

    # Return original error if not categorized
    return error


def handle_snowflake_errors(
    operation: str,
    database: Optional[str] = None,
    schema: Optional[str] = None,
    object_name: Optional[str] = None,
    fallback_value: Any = None,
    reraise: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., Union[T, Any]]]:
    """Decorator to handle Snowflake errors with context and proper categorization."""

    def decorator(func: Callable[..., T]) -> Callable[..., Union[T, Any]]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Union[T, Any]:
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
    context: Optional[ErrorContext] = None,
    fallback_value: Any = None,
    **kwargs: Any,
) -> Union[T, Any]:
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


class ErrorAggregator:
    """Aggregates errors during batch operations."""

    def __init__(self) -> None:
        self.errors: Dict[str, Exception] = {}
        self.warnings: Dict[str, str] = {}

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

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all errors and warnings."""
        return {
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": {k: str(v) for k, v in self.errors.items()},
            "warnings": self.warnings,
        }
