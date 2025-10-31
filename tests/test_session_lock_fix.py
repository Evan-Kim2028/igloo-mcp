"""Tests for session lock error fixes and defensive session handling."""

from __future__ import annotations

import threading
from unittest.mock import Mock

import pytest

from igloo_mcp.session_utils import ensure_session_lock, validate_session_lock


class TestSessionLockFixes:
    """Test session lock error handling and defensive measures."""

    def test_ensure_session_lock_with_none_service(self):
        """Test that ensure_session_lock raises ValueError for None service."""
        with pytest.raises(ValueError) as exc_info:
            ensure_session_lock(None)

        assert "Snowflake service is None" in str(exc_info.value)
        assert "cannot create session lock" in str(exc_info.value)

    def test_ensure_session_lock_with_invalid_service(self):
        """Test that ensure_session_lock raises ValueError for invalid service."""
        invalid_service = object()  # No __dict__ attribute

        with pytest.raises(ValueError) as exc_info:
            ensure_session_lock(invalid_service)

        assert "Invalid Snowflake service object" in str(exc_info.value)
        assert "missing attributes" in str(exc_info.value)

    def test_ensure_session_lock_with_broken_service(self):
        """Test that ensure_session_lock handles broken service gracefully."""

        class BrokenService:
            def __getattr__(self, name):
                if name == "_snowcli_session_lock":
                    raise AttributeError("Test error")
                raise AttributeError(f"Attribute {name} not found")

            def __setattr__(self, name, value):
                raise AttributeError(f"Cannot set attribute {name}")

        broken_service = BrokenService()

        with pytest.raises(ValueError) as exc_info:
            ensure_session_lock(broken_service)

        assert "Failed to access Snowflake service attributes" in str(exc_info.value)

    def test_ensure_session_lock_creates_new_lock(self):
        """Test that ensure_session_lock creates a new lock when none exists."""

        class Service:
            pass

        service = Service()

        lock = ensure_session_lock(service)

        assert isinstance(lock, threading.Lock)
        assert hasattr(service, "_snowcli_session_lock")
        assert service._snowcli_session_lock is lock

    def test_ensure_session_lock_reuses_existing_lock(self):
        """Test that ensure_session_lock reuses existing lock."""

        class Service:
            pass

        service = Service()
        existing_lock = threading.Lock()
        service._snowcli_session_lock = existing_lock

        lock = ensure_session_lock(service)

        assert lock is existing_lock
        assert service._snowcli_session_lock is existing_lock

    def test_validate_session_lock_with_none_service(self):
        """Test that validate_session_lock returns False for None service."""
        assert validate_session_lock(None) is False

    def test_validate_session_lock_with_valid_service_and_lock(self):
        """Test that validate_session_lock returns True for valid service and lock."""
        service = Mock()
        service._snowcli_session_lock = threading.Lock()

        assert validate_session_lock(service) is True

    def test_validate_session_lock_with_no_lock(self):
        """Test that validate_session_lock returns False when no lock exists."""

        class Service:
            pass

        service = Service()
        # Don't set _snowcli_session_lock

        assert validate_session_lock(service) is False

    def test_validate_session_lock_with_invalid_lock_type(self):
        """Test that validate_session_lock returns False with wrong lock type."""

        class Service:
            pass

        service = Service()
        service._snowcli_session_lock = "not_a_lock"  # Wrong type

        assert validate_session_lock(service) is False

    def test_validate_session_lock_with_broken_service(self):
        """Test that validate_session_lock handles broken service gracefully."""

        class BrokenService:
            def __getattr__(self, name):
                raise AttributeError("Service broken")

        broken_service = BrokenService()

        assert validate_session_lock(broken_service) is False

    def test_session_lock_thread_safety(self):
        """Test that session locks work correctly across multiple threads."""

        class Service:
            pass

        service = Service()

        # Create lock and use it across multiple threads
        def use_lock():
            lock = ensure_session_lock(service)
            with lock:
                # Simulate some work
                import time

                time.sleep(0.01)
                return True

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(use_lock) for _ in range(10)]
            results = [f.result() for f in futures]

        # All threads should succeed without deadlocks
        assert all(results) is True
        assert validate_session_lock(service) is True

    def test_session_lock_error_recovery(self):
        """Test that session lock creation can recover from temporary issues."""

        class Service:
            pass

        service = Service()

        # First attempt should succeed
        lock1 = ensure_session_lock(service)
        assert isinstance(lock1, threading.Lock)

        # Second attempt should return same lock
        lock2 = ensure_session_lock(service)
        assert lock1 is lock2
