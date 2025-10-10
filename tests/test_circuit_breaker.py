"""Tests for circuit breaker functionality."""

import time

import pytest

from igloo_mcp.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    circuit_breaker,
)


class CircuitBreakerTestException(Exception):
    """Test exception for circuit breaker tests."""


def test_circuit_breaker_config():
    """Test circuit breaker configuration."""
    config = CircuitBreakerConfig()
    assert config.failure_threshold == 5
    assert config.recovery_timeout == 60.0
    assert config.expected_exception is Exception

    custom_config = CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=30.0,
        expected_exception=CircuitBreakerTestException,
    )
    assert custom_config.failure_threshold == 3
    assert custom_config.recovery_timeout == 30.0
    assert custom_config.expected_exception == CircuitBreakerTestException


def test_circuit_breaker_closed_state():
    """Test circuit breaker in closed state."""
    config = CircuitBreakerConfig(
        failure_threshold=2, expected_exception=CircuitBreakerTestException
    )
    breaker = CircuitBreaker(config)

    # Should start in closed state
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0

    # Successful calls should work
    def success_func():
        return "success"

    result = breaker.call(success_func)
    assert result == "success"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


def test_circuit_breaker_failure_counting():
    """Test that circuit breaker counts failures correctly."""
    config = CircuitBreakerConfig(
        failure_threshold=2, expected_exception=CircuitBreakerTestException
    )
    breaker = CircuitBreaker(config)

    def failing_func():
        raise CircuitBreakerTestException("Test failure")

    # First failure
    with pytest.raises(CircuitBreakerTestException):
        breaker.call(failing_func)
    assert breaker.failure_count == 1
    assert breaker.state == CircuitState.CLOSED

    # Second failure should open the circuit
    with pytest.raises(CircuitBreakerTestException):
        breaker.call(failing_func)
    assert breaker.failure_count == 2
    assert breaker.state == CircuitState.OPEN


def test_circuit_breaker_open_state():
    """Test circuit breaker in open state."""
    config = CircuitBreakerConfig(
        failure_threshold=1, expected_exception=CircuitBreakerTestException
    )
    breaker = CircuitBreaker(config)

    def failing_func():
        raise CircuitBreakerTestException("Test failure")

    # Trigger failure to open circuit
    with pytest.raises(CircuitBreakerTestException):
        breaker.call(failing_func)
    assert breaker.state == CircuitState.OPEN

    # Subsequent calls should raise CircuitBreakerError
    def any_func():
        return "should not execute"

    with pytest.raises(CircuitBreakerError):
        breaker.call(any_func)


def test_circuit_breaker_recovery():
    """Test circuit breaker recovery after timeout."""
    config = CircuitBreakerConfig(
        failure_threshold=1,
        recovery_timeout=0.1,  # 100ms
        expected_exception=CircuitBreakerTestException,
    )
    breaker = CircuitBreaker(config)

    def failing_func():
        raise CircuitBreakerTestException("Test failure")

    def success_func():
        return "success"

    # Open the circuit
    with pytest.raises(CircuitBreakerTestException):
        breaker.call(failing_func)
    assert breaker.state == CircuitState.OPEN

    # Wait for recovery timeout
    time.sleep(0.2)

    # Next call should transition to half-open and succeed
    result = breaker.call(success_func)
    assert result == "success"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


def test_circuit_breaker_decorator():
    """Test circuit breaker decorator functionality."""
    call_count = 0

    @circuit_breaker(
        failure_threshold=2, expected_exception=CircuitBreakerTestException
    )
    def decorated_func(should_fail=False):
        nonlocal call_count
        call_count += 1
        if should_fail:
            raise CircuitBreakerTestException("Decorated failure")
        return f"success_{call_count}"

    # Successful calls
    assert decorated_func() == "success_1"
    assert decorated_func() == "success_2"

    # Failures
    with pytest.raises(CircuitBreakerTestException):
        decorated_func(should_fail=True)

    with pytest.raises(CircuitBreakerTestException):
        decorated_func(should_fail=True)

    # Circuit should be open now
    with pytest.raises(CircuitBreakerError):
        decorated_func()


def test_circuit_breaker_ignores_unexpected_exceptions():
    """Test that circuit breaker ignores unexpected exception types."""
    config = CircuitBreakerConfig(
        failure_threshold=2, expected_exception=CircuitBreakerTestException
    )
    breaker = CircuitBreaker(config)

    def func_with_unexpected_error():
        raise ValueError("Unexpected error")

    # Unexpected exceptions should pass through without affecting circuit state
    with pytest.raises(ValueError):
        breaker.call(func_with_unexpected_error)

    assert breaker.failure_count == 0
    assert breaker.state == CircuitState.CLOSED


def test_circuit_breaker_half_open_success():
    """Test successful recovery from half-open state."""
    config = CircuitBreakerConfig(
        failure_threshold=1,
        recovery_timeout=0.1,
        expected_exception=CircuitBreakerTestException,
    )
    breaker = CircuitBreaker(config)

    # Open the circuit
    with pytest.raises(CircuitBreakerTestException):
        breaker.call(lambda: (_ for _ in ()).throw(CircuitBreakerTestException("fail")))

    # Wait and verify half-open transition
    time.sleep(0.2)

    # Success should reset to closed
    result = breaker.call(lambda: "recovered")
    assert result == "recovered"
    assert breaker.state == CircuitState.CLOSED


def test_circuit_breaker_half_open_failure():
    """Test failure in half-open state returns to open."""
    config = CircuitBreakerConfig(
        failure_threshold=1,
        recovery_timeout=0.1,
        expected_exception=CircuitBreakerTestException,
    )
    breaker = CircuitBreaker(config)

    # Open the circuit
    with pytest.raises(CircuitBreakerTestException):
        breaker.call(lambda: (_ for _ in ()).throw(CircuitBreakerTestException("fail")))

    # Wait for recovery timeout
    time.sleep(0.2)

    # Failure in half-open should return to open
    with pytest.raises(CircuitBreakerTestException):
        breaker.call(
            lambda: (_ for _ in ()).throw(CircuitBreakerTestException("fail again"))
        )

    assert breaker.state == CircuitState.OPEN
