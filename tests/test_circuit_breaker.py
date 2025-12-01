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
    config = CircuitBreakerConfig(failure_threshold=2, expected_exception=CircuitBreakerTestException)
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
    config = CircuitBreakerConfig(failure_threshold=2, expected_exception=CircuitBreakerTestException)
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
    config = CircuitBreakerConfig(failure_threshold=1, expected_exception=CircuitBreakerTestException)
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

    @circuit_breaker(failure_threshold=2, expected_exception=CircuitBreakerTestException)
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
    config = CircuitBreakerConfig(failure_threshold=2, expected_exception=CircuitBreakerTestException)
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

        def failing_func():
            raise CircuitBreakerTestException("fail")

        breaker.call(failing_func)

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

        def failing_func():
            raise CircuitBreakerTestException("fail")

        breaker.call(failing_func)

    # Wait for recovery timeout
    time.sleep(0.2)

    # Failure in half-open should return to open
    with pytest.raises(CircuitBreakerTestException):

        def failing_func_again():
            raise CircuitBreakerTestException("fail again")

        breaker.call(failing_func_again)

    assert breaker.state == CircuitState.OPEN


@pytest.mark.slow
class TestCircuitBreakerConcurrentAccess:
    """Test concurrent access scenarios for circuit breaker."""

    def test_concurrent_access_thread_safety(self):
        """Test circuit breaker handles concurrent access safely."""
        import concurrent.futures

        config = CircuitBreakerConfig(
            failure_threshold=50,  # Higher threshold to allow some successes
            recovery_timeout=1.0,
            expected_exception=CircuitBreakerTestException,
        )
        breaker = CircuitBreaker(config)

        results = []
        errors = []

        def worker(worker_id: int):
            """Worker function that makes calls to the circuit breaker."""
            try:
                for i in range(10):
                    if i < 7:  # First 7 calls fail to trigger open circuit
                        try:

                            def failing_func(_i=i, _wid=worker_id):
                                raise CircuitBreakerTestException(f"fail_{_wid}_{_i}")

                            breaker.call(failing_func)
                            results.append(f"unexpected_success_{worker_id}_{i}")
                        except CircuitBreakerError:
                            results.append(f"circuit_open_{worker_id}_{i}")
                        except CircuitBreakerTestException:
                            results.append(f"expected_failure_{worker_id}_{i}")
                    else:
                        # Last 3 calls should succeed and reset failure count
                        try:
                            result = breaker.call(lambda _wid=worker_id, _i=i: f"success_{_wid}_{_i}")
                            results.append(result)
                        except CircuitBreakerError:
                            results.append(f"circuit_open_{worker_id}_{i}")
                        except CircuitBreakerTestException:
                            results.append(f"unexpected_exception_{worker_id}_{i}")
            except (CircuitBreakerError, CircuitBreakerTestException, RuntimeError) as e:
                errors.append(f"worker_{worker_id}_error: {e}")

        # Run 10 workers concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            concurrent.futures.wait(futures)

        # Check that no unexpected errors occurred
        assert len(errors) == 0, f"Worker errors: {errors}"

        # With successes resetting failure count, circuit should not open under intermittent failures
        circuit_open_results = [r for r in results if r.startswith("circuit_open")]
        assert len(circuit_open_results) == 0, "Circuit should not open when successes reset failure count"

        # Check that some calls succeeded
        success_results = [r for r in results if r.startswith("success")]
        assert len(success_results) > 0, "Some calls should have succeeded"

    def test_concurrent_state_transitions(self):
        """Test concurrent state transitions don't cause race conditions."""
        import concurrent.futures

        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=0.1,  # Very short recovery time
            expected_exception=CircuitBreakerTestException,
        )
        breaker = CircuitBreaker(config)

        results = []

        def state_checker():
            """Continuously check state transitions."""
            last_state = None
            transitions = 0
            for _ in range(50):  # Check state multiple times
                current_state = breaker.state
                if last_state != current_state:
                    transitions += 1
                    results.append(f"transition_{last_state}_to_{current_state}")
                last_state = current_state
                time.sleep(0.01)  # Small delay
            results.append(f"total_transitions_{transitions}")

        def failure_injector():
            """Continuously inject failures."""
            for i in range(20):
                try:

                    def failing_func(_i=i):
                        raise CircuitBreakerTestException(f"fail_{_i}")

                    breaker.call(failing_func)
                except CircuitBreakerError:
                    pass  # Expected when circuit is open
                time.sleep(0.005)

        # Run state checker and failure injector concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            checker_future = executor.submit(state_checker)
            injector_future = executor.submit(failure_injector)

            concurrent.futures.wait([checker_future, injector_future])

        # Check that state transitions occurred (circuit should have opened and possibly recovered)
        transition_results = [r for r in results if r.startswith("transition")]
        assert len(transition_results) > 0, "State transitions should have occurred"

    def test_high_load_concurrent_calls(self):
        """Test circuit breaker under high concurrent load."""
        import concurrent.futures

        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=2.0,
            expected_exception=CircuitBreakerTestException,
        )
        breaker = CircuitBreaker(config)

        def make_call(call_id: int):
            """Make a single call that may succeed or fail."""
            try:
                # All calls succeed (we want to test concurrent access, not failure scenarios)
                return breaker.call(lambda: f"success_{call_id}")
            except CircuitBreakerError:
                return f"circuit_open_{call_id}"
            except CircuitBreakerTestException:
                return f"unexpected_failure_{call_id}"

        # Make 100 concurrent calls
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_call, i) for i in range(100)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Analyze results
        circuit_open_results = [r for r in results if r.startswith("circuit_open")]
        expected_failures = [r for r in results if r.startswith("expected_failure")]
        successes = [r for r in results if r.startswith("success")]

        # Circuit should remain closed when all calls succeed
        assert len(circuit_open_results) == 0, "Circuit should not open when all calls succeed"

        # Should have no expected failures
        assert len(expected_failures) == 0, "Should have no failures"

        # Should have all successes
        assert len(successes) == 100, "Should have all successful calls"


@pytest.mark.slow
class TestCircuitBreakerTimingEdgeCases:
    """Test timing-related edge cases in circuit breaker."""

    def test_recovery_timeout_boundary(self):
        """Test behavior at exact recovery timeout boundary."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,  # 100ms
            expected_exception=CircuitBreakerTestException,
        )
        breaker = CircuitBreaker(config)

        # Trigger circuit to open
        for _ in range(2):
            with pytest.raises(CircuitBreakerTestException):

                def failing_func():
                    raise CircuitBreakerTestException("fail")

                breaker.call(failing_func)

        assert breaker.state == CircuitState.OPEN

        # Wait exactly at the recovery timeout
        time.sleep(0.1)

        # Next call should attempt recovery (half-open)
        result = breaker.call(lambda: "recovered")
        assert result == "recovered"
        assert breaker.state == CircuitState.CLOSED

    def test_recovery_timeout_slightly_before(self):
        """Test behavior slightly before recovery timeout."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.2,  # 200ms
            expected_exception=CircuitBreakerTestException,
        )
        breaker = CircuitBreaker(config)

        # Trigger circuit to open
        for _ in range(2):
            with pytest.raises(CircuitBreakerTestException):

                def failing_func():
                    raise CircuitBreakerTestException("fail")

                breaker.call(failing_func)

        assert breaker.state == CircuitState.OPEN

        # Wait just before recovery timeout
        time.sleep(0.15)  # 150ms, recovery at 200ms

        # Should still be open
        with pytest.raises(CircuitBreakerError):
            breaker.call(lambda: "should_fail")

        assert breaker.state == CircuitState.OPEN

    def test_recovery_timeout_slightly_after(self):
        """Test behavior slightly after recovery timeout."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,  # 100ms
            expected_exception=CircuitBreakerTestException,
        )
        breaker = CircuitBreaker(config)

        # Trigger circuit to open
        for _ in range(2):
            with pytest.raises(CircuitBreakerTestException):

                def failing_func():
                    raise CircuitBreakerTestException("fail")

                breaker.call(failing_func)

        assert breaker.state == CircuitState.OPEN

        # Wait slightly past recovery timeout
        time.sleep(0.12)  # 120ms, recovery at 100ms

        # Next call should attempt recovery
        result = breaker.call(lambda: "recovered")
        assert result == "recovered"
        assert breaker.state == CircuitState.CLOSED

    def test_rapid_succession_failures(self):
        """Test rapid succession of failures."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=0.05,  # Very short
            expected_exception=CircuitBreakerTestException,
        )
        breaker = CircuitBreaker(config)

        # Rapid failures - first few should raise the original exception
        for i in range(3):
            with pytest.raises(CircuitBreakerTestException):

                def failing_func(_i=i):
                    raise CircuitBreakerTestException(f"fail_{_i}")

                breaker.call(failing_func)

        # Circuit should now be open, subsequent calls should raise CircuitBreakerError
        for i in range(2):
            with pytest.raises(CircuitBreakerError):

                def failing_func(_i=i):
                    raise CircuitBreakerTestException(f"fail_{_i + 3}")

                breaker.call(failing_func)

        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count >= 3

    def test_timing_precision_under_load(self):
        """Test timing precision when system is under load."""
        import concurrent.futures

        config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=0.2,
            expected_exception=CircuitBreakerTestException,
        )
        breaker = CircuitBreaker(config)

        def timing_worker():
            """Worker that tests timing behavior."""
            results = []

            # Trigger failures
            for _ in range(5):
                try:

                    def failing_func():
                        raise CircuitBreakerTestException("fail")

                    breaker.call(failing_func)
                    results.append("unexpected_success")
                except CircuitBreakerError:
                    results.append("circuit_open")
                except CircuitBreakerTestException:
                    results.append("expected_failure")

            # Wait for recovery
            time.sleep(0.25)  # Slightly longer than recovery timeout

            # Try recovery
            try:
                _ = breaker.call(lambda: "recovered")
                results.append("recovery_success")
            except CircuitBreakerError:
                results.append("recovery_failed_circuit_open")
            except CircuitBreakerTestException:
                results.append("recovery_failed_exception")

            return results

        # Run multiple timing workers concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(timing_worker) for _ in range(3)]
            all_results = []
            for future in concurrent.futures.as_completed(futures):
                all_results.extend(future.result())

        # Analyze results
        circuit_open_results = [r for r in all_results if r == "circuit_open"]
        expected_failures = [r for r in all_results if r == "expected_failure"]
        recovery_successes = [r for r in all_results if r == "recovery_success"]

        # Should have some circuit open results
        assert len(circuit_open_results) > 0, "Should have circuit open results under concurrent timing load"

        # Should have some expected failures
        assert len(expected_failures) > 0, "Should have expected failures"

        # Should have some recovery successes
        assert len(recovery_successes) > 0, "Should have recovery successes"

    def test_state_transition_timing_race(self):
        """Test potential race conditions in state transitions."""
        import threading

        config = CircuitBreakerConfig(
            failure_threshold=1,  # Open on first failure
            recovery_timeout=0.05,
            expected_exception=CircuitBreakerTestException,
        )
        breaker = CircuitBreaker(config)

        results = []
        errors = []

        def rapid_caller():
            """Make rapid calls to potentially trigger race conditions."""
            for i in range(20):
                try:

                    def failing_func(_i=i):
                        raise CircuitBreakerTestException(f"fail_{_i}")

                    breaker.call(failing_func)
                    results.append(f"unexpected_success_{i}")
                except CircuitBreakerError:
                    results.append(f"circuit_open_{i}")
                except CircuitBreakerTestException:
                    results.append(f"expected_failure_{i}")
                except RuntimeError as e:
                    errors.append(f"error_{i}: {e}")

        # Run rapid calls in separate thread
        thread = threading.Thread(target=rapid_caller)
        thread.start()
        thread.join()

        # Check results
        assert len(errors) == 0, f"Should not have errors: {errors}"

        # Circuit should have opened due to rapid failures
        assert breaker.state == CircuitState.OPEN, "Circuit should be open after rapid failures"

        # Should have some expected failures and circuit open results
        expected_failures = [r for r in results if r.startswith("expected_failure")]
        circuit_open_results = [r for r in results if r.startswith("circuit_open")]

        assert len(expected_failures) > 0, "Should have expected failures"
        assert len(circuit_open_results) > 0, "Should have circuit open results under rapid calling"
