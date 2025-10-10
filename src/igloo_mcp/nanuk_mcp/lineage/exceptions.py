"""Custom exceptions for the lineage module."""

from __future__ import annotations

from typing import Any, Dict, Optional


class LineageException(Exception):
    """Base exception for all lineage-related errors."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.details = details or {}
        self.cause = cause


class LineageParseError(LineageException):
    """Raised when SQL or DDL parsing fails."""

    def __init__(self, sql: str, error: str, cause: Optional[Exception] = None):
        super().__init__(
            f"Failed to parse SQL: {error}",
            details={"sql": sql[:500], "error": error},
            cause=cause,
        )
        self.sql = sql
        self.error = error


class ObjectNotFoundException(LineageException):
    """Raised when a referenced object is not found."""

    def __init__(self, object_name: str, object_type: Optional[str] = None):
        message = f"Object not found: {object_name}"
        if object_type:
            message = f"{object_type} not found: {object_name}"
        super().__init__(
            message,
            details={"object_name": object_name, "object_type": object_type},
        )
        self.object_name = object_name
        self.object_type = object_type


class InvalidConfigurationError(LineageException):
    """Raised when configuration is invalid or missing."""

    def __init__(self, config_key: str, reason: str):
        super().__init__(
            f"Invalid configuration for '{config_key}': {reason}",
            details={"config_key": config_key, "reason": reason},
        )
        self.config_key = config_key
        self.reason = reason


class SecurityViolationError(LineageException):
    """Raised when a security violation is detected."""

    def __init__(self, violation_type: str, details: str):
        super().__init__(
            f"Security violation detected: {violation_type}",
            details={"violation_type": violation_type, "details": details},
        )
        self.violation_type = violation_type


class CircularDependencyError(LineageException):
    """Raised when a circular dependency is detected in lineage."""

    def __init__(self, path: list, cycle_point: str):
        super().__init__(
            f"Circular dependency detected at: {cycle_point}",
            details={"path": path, "cycle_point": cycle_point},
        )
        self.path = path
        self.cycle_point = cycle_point


class StorageError(LineageException):
    """Raised when storage operations fail."""

    def __init__(self, operation: str, path: str, cause: Optional[Exception] = None):
        super().__init__(
            f"Storage operation '{operation}' failed for path: {path}",
            details={"operation": operation, "path": path},
            cause=cause,
        )
        self.operation = operation
        self.path = path


class ValidationError(LineageException):
    """Raised when validation fails."""

    def __init__(self, field: str, value: Any, reason: str):
        super().__init__(
            f"Validation failed for '{field}': {reason}",
            details={"field": field, "value": str(value)[:100], "reason": reason},
        )
        self.field = field
        self.value = value
        self.reason = reason


class TimeoutError(LineageException):
    """Raised when an operation times out."""

    def __init__(self, operation: str, timeout_seconds: int):
        super().__init__(
            f"Operation '{operation}' timed out after {timeout_seconds} seconds",
            details={"operation": operation, "timeout_seconds": timeout_seconds},
        )
        self.operation = operation
        self.timeout_seconds = timeout_seconds


class ResourceExhaustedError(LineageException):
    """Raised when a resource limit is exceeded."""

    def __init__(self, resource: str, limit: int, actual: int):
        super().__init__(
            f"Resource '{resource}' exhausted: limit={limit}, actual={actual}",
            details={"resource": resource, "limit": limit, "actual": actual},
        )
        self.resource = resource
        self.limit = limit
        self.actual = actual


class UnsupportedOperationError(LineageException):
    """Raised when an unsupported operation is attempted."""

    def __init__(self, operation: str, reason: str):
        super().__init__(
            f"Unsupported operation '{operation}': {reason}",
            details={"operation": operation, "reason": reason},
        )
        self.operation = operation
        self.reason = reason
