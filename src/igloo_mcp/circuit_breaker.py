"""Circuit breaker pattern implementation for Snowflake operations.

This module provides a circuit breaker to prevent cascade failures when
Snowflake is unavailable or experiencing issues.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    expected_exception: type[Exception] = Exception


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""


class CircuitBreaker:
    """Circuit breaker implementation with exponential backoff."""

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = CircuitState.CLOSED
        self._lock = threading.RLock()  # Reentrant lock for thread safety

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a function through the circuit breaker."""
        with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerError(f"Circuit breaker is open. Last failure: {self.last_failure_time}")

            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.config.expected_exception as e:
                self._on_failure()
                raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt a reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.config.recovery_timeout

    def _on_success(self) -> None:
        """Handle successful execution."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self) -> None:
        """Handle failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN

    def allow_request(self) -> bool:
        """Check whether a request can proceed under current breaker state.

        Returns True when the breaker is closed, or when an open breaker
        has reached recovery timeout and transitions to half-open.
        """
        with self._lock:
            if self.state != CircuitState.OPEN:
                return True
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                return True
            return False

    def record_success(self) -> None:
        """Record a successful protected operation."""
        with self._lock:
            self._on_success()

    def record_failure(self) -> None:
        """Record a failed protected operation."""
        with self._lock:
            self._on_failure()

    @property
    def is_open(self) -> bool:
        """Whether the circuit is currently open."""
        with self._lock:
            return self.state == CircuitState.OPEN

    def time_until_retry_seconds(self) -> float:
        """Return remaining time before the next half-open attempt is allowed."""
        with self._lock:
            if self.state != CircuitState.OPEN or self.last_failure_time is None:
                return 0.0
            elapsed = time.time() - self.last_failure_time
            return max(0.0, self.config.recovery_timeout - elapsed)

    def get_status(self) -> dict[str, Any]:
        """Return a thread-safe status snapshot for diagnostics."""
        with self._lock:
            status: dict[str, Any] = {
                "state": self.state.value,
                "failure_count": self.failure_count,
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout_seconds": self.config.recovery_timeout,
                "is_open": self.state == CircuitState.OPEN,
            }
            if self.last_failure_time is not None:
                status["last_failure_time"] = self.last_failure_time
                if self.state == CircuitState.OPEN:
                    elapsed = time.time() - self.last_failure_time
                    status["time_until_retry_seconds"] = max(0.0, self.config.recovery_timeout - elapsed)
            return status


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: type = Exception,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to apply circuit breaker pattern to a function."""
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception,
    )
    breaker = CircuitBreaker(config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator
