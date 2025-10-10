"""Utility functions and fixes for advanced lineage features."""

from __future__ import annotations

import re
import signal
import sqlite3
import threading
from contextlib import contextmanager
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, Callable, Generator, Optional, Set, TypeVar, Union, cast

import networkx as nx

T = TypeVar("T")


@lru_cache(maxsize=1000)
def validate_object_name(name: str) -> bool:
    """Validate Snowflake object name format with caching."""
    if not name:
        return False

    # Handle quoted identifiers (can contain spaces and other chars)
    if name.startswith('"') and name.endswith('"'):
        return len(name) > 2  # Must have content between quotes

    # Split on dots for qualified names
    parts = name.split(".")

    for part in parts:
        # Remove quotes if present
        clean_part = part.strip('"')

        # Allow quoted identifiers with spaces
        if part.startswith('"') and part.endswith('"'):
            if len(clean_part) == 0:
                return False
            continue

        # Basic validation for unquoted identifiers
        pattern = r"^[A-Za-z_][A-Za-z0-9_$]*$"
        if not re.match(pattern, clean_part):
            return False

    return True


def validate_path(
    path: Path,
    must_exist: bool = False,
    create_if_missing: bool = False,
    allow_absolute_only: bool = True,
) -> bool:
    """Validate file system path with path traversal protection."""
    try:
        path = Path(path)

        # Path traversal protection
        resolved_path = path.resolve()

        # Check for path traversal attempts
        path_str = str(path)
        if ".." in path_str or path_str.startswith("/"):
            if allow_absolute_only and not path.is_absolute():
                return False

        # Ensure resolved path doesn't escape intended boundaries
        dangerous_patterns = ["../", "..\\", "%2e%2e", "..%2f", "..%5c"]
        for pattern in dangerous_patterns:
            if pattern in path_str.lower():
                return False

        # Validate against null bytes and control characters
        if "\x00" in path_str or any(
            ord(c) < 32 for c in path_str if c not in ["\t", "\n", "\r"]
        ):
            return False

        if must_exist and not resolved_path.exists():
            if create_if_missing and path.suffix == "":  # It's a directory
                resolved_path.mkdir(parents=True, exist_ok=True)
                return True
            return False

        # Check write permissions for parent directory
        parent = resolved_path.parent
        if not parent.exists() and create_if_missing:
            parent.mkdir(parents=True, exist_ok=True)

        if parent.exists():
            # Test write permission
            test_file = parent / ".write_test"
            try:
                test_file.touch()
                test_file.unlink()
                return True
            except (OSError, PermissionError):
                return False

        return True

    except (OSError, ValueError, RuntimeError):
        return False


def safe_file_write(path: Path, content: str | bytes, mode: str = "w") -> bool:
    """Safely write to file with atomic operations and path validation."""
    try:
        path = Path(path)

        # Validate path for security
        if not validate_path(path, must_exist=False, create_if_missing=True):
            return False

        temp_path = path.with_suffix(path.suffix + ".tmp")

        # Validate content size to prevent excessive memory usage
        if isinstance(content, str):
            if len(content) > 100 * 1024 * 1024:  # 100MB limit
                return False
        elif isinstance(content, bytes):
            if len(content) > 100 * 1024 * 1024:  # 100MB limit
                return False

        # Write to temporary file
        if isinstance(content, bytes):
            temp_path.write_bytes(content)
        else:
            temp_path.write_text(content, encoding="utf-8")

        # Atomic rename
        temp_path.replace(path)
        return True

    except (OSError, IOError, UnicodeError):
        # Clean up temp file if it exists
        try:
            if "temp_path" in locals() and temp_path.exists():
                temp_path.unlink()
        except (OSError, IOError, PermissionError):
            # Best effort cleanup - failures here don't affect the main operation
            pass
        return False


@contextmanager
def safe_db_connection(db_path: Path) -> Generator:
    """Context manager for safe SQLite connections."""

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        yield conn
    finally:
        if conn:
            try:
                conn.close()
            except (OSError, sqlite3.Error):
                # Database connection cleanup failed - not critical
                pass


def networkx_descendants_at_distance(
    graph: nx.DiGraph, source: str, distance: int
) -> Set[str]:
    """Get all descendants at a specific distance or less from source node."""
    if source not in graph:
        return set()

    descendants = set()
    current_level = {source}

    for d in range(1, distance + 1):
        next_level = set()
        for node in current_level:
            for successor in graph.successors(node):
                next_level.add(successor)
                descendants.add(successor)
        current_level = next_level

        if not current_level:  # No more descendants at this level
            break

    return descendants


def safe_sql_parse(sql: str, dialect: str = "snowflake") -> Optional[Any]:
    """Safely parse SQL with better error handling."""
    import sqlglot
    from sqlglot.errors import ErrorLevel, ParseError

    if not sql or not sql.strip():
        return None

    try:
        # Handle multi-statement SQL
        statements = sqlglot.parse(sql, read=dialect, error_level=ErrorLevel.RAISE)

        # Filter out None results and validate statements
        valid_statements = []
        for stmt in statements:
            if stmt is not None:
                # Additional validation - check if statement has meaningful content
                if hasattr(stmt, "sql") and stmt.sql().strip():
                    valid_statements.append(stmt)

        if not valid_statements:
            return None

        # Return first statement for single-statement expectation
        # Or return all for multi-statement handling
        return valid_statements[0] if len(valid_statements) == 1 else valid_statements

    except ParseError as e:
        # Log the parse error but don't raise
        import logging

        logging.warning(f"SQL parse error: {e}")
        return None
    except (AttributeError, TypeError, ValueError) as e:
        # Handle malformed expressions or unsupported SQL features
        import logging

        logging.error(f"Error processing SQL structure: {e}")
        return None
    except ImportError as e:
        # Missing sqlglot or dependencies
        import logging

        logging.error(f"SQL parsing dependency error: {e}")
        return None


def clean_old_snapshots(storage_path: Path, keep_count: int = 100, keep_days: int = 90):
    """Clean up old snapshot files to prevent unbounded growth."""
    from datetime import datetime, timedelta

    storage_path = Path(storage_path)
    if not storage_path.exists():
        return

    cutoff_date = datetime.now() - timedelta(days=keep_days)
    graph_files = list(storage_path.glob("graph_*.json"))

    # Sort by modification time
    graph_files.sort(key=lambda f: f.stat().st_mtime)

    # Keep minimum number of files
    if len(graph_files) <= keep_count:
        return

    # Remove old files - always remove oldest files beyond keep_count
    files_to_remove = graph_files[:-keep_count]
    cutoff_date = datetime.now() - timedelta(days=keep_days)

    for graph_file in files_to_remove:
        try:
            # Always remove if we have too many files, or if it's too old
            mtime = datetime.fromtimestamp(graph_file.stat().st_mtime)
            if len(graph_files) > keep_count or mtime < cutoff_date:
                graph_file.unlink()
        except (OSError, IOError):
            pass


@lru_cache(maxsize=1000)
def validate_sql_injection(value: str) -> bool:
    """Enhanced SQL injection prevention check with caching."""
    if not isinstance(value, str) or not value.strip():
        return False

    # Comprehensive dangerous patterns with better coverage
    dangerous_patterns = [
        # SQL statement injection
        r";\s*(DROP|DELETE|TRUNCATE|ALTER|CREATE|INSERT|UPDATE|EXEC|EXECUTE)\s+",
        # Comment-based bypasses
        r"--[^\n]*",
        r"/\*.*?\*/",
        r"#.*$",
        # Union-based injection
        r"\b(UNION\s+(ALL\s+)?SELECT|UNION\s+ALL)",
        # Boolean-based injection
        r"\b(OR|AND)\s+(\d+\s*[=<>!]\s*\d+|'[^']*'\s*[=<>!]\s*'[^']*')",
        # Time-based injection
        r"\b(WAITFOR|SLEEP|BENCHMARK|pg_sleep)\s*\(",
        # Stacked queries
        r";\s*[A-Za-z]",
        # Information gathering
        r"\b(information_schema|sys\.tables|mysql\.user)",
        # Special characters that often indicate injection
        r"['\"`;].*['\"`;]",
        # Hex encoding attempts
        r"0x[0-9a-fA-F]+",
        # Script tags (for XSS prevention as well)
        r"<\s*script[^>]*>",
    ]

    value_normalized = re.sub(r"\s+", " ", value.strip().upper())

    for pattern in dangerous_patterns:
        if re.search(
            pattern, value_normalized, re.IGNORECASE | re.MULTILINE | re.DOTALL
        ):
            return False

    return True


def get_cache_key(*args) -> str:
    """Generate a cache key from arguments."""
    import hashlib

    key_parts = []
    for arg in args:
        if arg is None:
            key_parts.append("None")
        elif isinstance(arg, (list, tuple)):
            key_parts.append(str(sorted(arg)))
        elif isinstance(arg, dict):
            key_parts.append(str(sorted(arg.items())))
        else:
            key_parts.append(str(arg))

    combined = "|".join(key_parts)
    return hashlib.md5(combined.encode()).hexdigest()


# LRUCache class removed - replaced with functools.lru_cache decorators


@lru_cache(maxsize=500)
def cached_sql_parse(sql: str, dialect: str = "snowflake") -> Optional[Any]:
    """Parse SQL with caching using functools.lru_cache."""
    return safe_sql_parse(sql, dialect)


class TimeoutError(Exception):
    """Raised when an operation times out."""

    pass


@contextmanager
def timeout(seconds: int, error_message: str = "Operation timed out"):
    """Context manager for setting a timeout on operations.

    Args:
        seconds: Timeout in seconds
        error_message: Custom error message for timeout

    Example:
        with timeout(30):
            expensive_operation()
    """

    def timeout_handler(signum, frame):
        raise TimeoutError(error_message)

    # Check if running on a system that supports SIGALRM
    if hasattr(signal, "SIGALRM"):
        # Set the signal handler and alarm
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)

        try:
            yield
        finally:
            # Cancel the alarm and restore the previous handler
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # For Windows/non-Unix systems, just yield without timeout
        # (More complex threading solution would be needed for cross-platform)
        yield


def with_timeout(
    seconds: int = 30, default: Optional[T] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to add timeout to functions.

    Args:
        seconds: Timeout in seconds
        default: Default value to return on timeout

    Example:
        @with_timeout(30)
        def expensive_function():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # For non-Unix systems or when SIGALRM is not available
            if not hasattr(signal, "SIGALRM"):
                result: list[Union[T, BaseException]] = [
                    TimeoutError("Operation timed out")
                ]

                def target() -> None:
                    try:
                        result[0] = func(*args, **kwargs)
                    except Exception as e:
                        result[0] = e

                thread = threading.Thread(target=target)
                thread.daemon = True
                thread.start()
                thread.join(timeout=seconds)

                if thread.is_alive():
                    if default is not None:
                        return default
                    raise TimeoutError("Operation timed out")

                if isinstance(result[0], BaseException):
                    if isinstance(result[0], TimeoutError):
                        if default is not None:
                            return default
                        raise TimeoutError("Operation timed out")
                    raise result[0]
                return cast(T, result[0])
            else:
                # Use signal-based timeout for Unix systems
                try:
                    with timeout(seconds):
                        return func(*args, **kwargs)
                except TimeoutError:
                    if default is not None:
                        return default
                    raise

        return wrapper

    return decorator
