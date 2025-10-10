"""Tests for error handling functionality."""

from unittest.mock import patch

import pytest

from igloo_mcp.error_handling import (
    ErrorAggregator,
    ErrorContext,
    SnowflakeConnectionError,
    SnowflakePermissionError,
    SnowflakeTimeoutError,
    categorize_snowflake_error,
    handle_snowflake_errors,
    safe_execute,
)
from igloo_mcp.snow_cli import SnowCLIError


def test_error_context_creation():
    """Test ErrorContext creation."""
    context = ErrorContext(operation="test_op")
    assert context.operation == "test_op"
    assert context.database is None
    assert context.schema is None
    assert context.object_name is None
    assert context.query is None

    full_context = ErrorContext(
        operation="query_execution",
        database="test_db",
        schema="test_schema",
        object_name="test_table",
        query="SELECT * FROM test_table",
    )
    assert full_context.operation == "query_execution"
    assert full_context.database == "test_db"
    assert full_context.schema == "test_schema"
    assert full_context.object_name == "test_table"
    assert full_context.query == "SELECT * FROM test_table"


def test_categorize_connection_error():
    """Test categorization of connection errors."""
    context = ErrorContext(operation="test")

    connection_errors = [
        "connection failed",
        "network timeout",
        "connection refused",
        "host unreachable",
    ]

    for error_msg in connection_errors:
        error = SnowCLIError(error_msg)
        categorized = categorize_snowflake_error(error, context)
        assert isinstance(categorized, SnowflakeConnectionError)
        assert "Connection failed for test" in str(categorized)


def test_categorize_permission_error():
    """Test categorization of permission errors."""
    context = ErrorContext(operation="test")

    permission_errors = [
        "permission denied",
        "insufficient privileges",
        "access denied",
        "unauthorized access",
        "forbidden operation",
    ]

    for error_msg in permission_errors:
        error = SnowCLIError(error_msg)
        categorized = categorize_snowflake_error(error, context)
        assert isinstance(categorized, SnowflakePermissionError)
        assert "Permission denied for test" in str(categorized)


def test_categorize_timeout_error():
    """Test categorization of timeout errors."""
    context = ErrorContext(operation="test")

    timeout_errors = ["operation timed out", "timeout occurred", "request timeout"]

    for error_msg in timeout_errors:
        error = SnowCLIError(error_msg)
        categorized = categorize_snowflake_error(error, context)
        assert isinstance(categorized, SnowflakeTimeoutError)
        assert "Timeout during test" in str(categorized)


def test_categorize_unknown_error():
    """Test categorization of unknown errors."""
    context = ErrorContext(operation="test")
    error = SnowCLIError("some unknown error")

    categorized = categorize_snowflake_error(error, context)
    assert isinstance(categorized, SnowCLIError)
    assert categorized is error  # Should return original error


def test_handle_snowflake_errors_decorator_success():
    """Test error handling decorator with successful execution."""

    @handle_snowflake_errors(operation="test_operation")
    def successful_function():
        return "success"

    result = successful_function()
    assert result == "success"


def test_handle_snowflake_errors_decorator_with_snowcli_error():
    """Test error handling decorator with SnowCLIError."""

    @handle_snowflake_errors(operation="test_operation")
    def failing_function():
        raise SnowCLIError("connection failed")

    with pytest.raises(SnowflakeConnectionError):
        failing_function()


def test_handle_snowflake_errors_decorator_no_reraise():
    """Test error handling decorator with reraise=False."""

    @handle_snowflake_errors(
        operation="test_operation", reraise=False, fallback_value="fallback"
    )
    def failing_function():
        raise SnowCLIError("connection failed")

    result = failing_function()
    assert result == "fallback"


def test_handle_snowflake_errors_decorator_unexpected_error():
    """Test error handling decorator with unexpected error."""

    @handle_snowflake_errors(operation="test_operation")
    def failing_function():
        raise ValueError("unexpected error")

    with pytest.raises(ValueError):
        failing_function()


def test_handle_snowflake_errors_decorator_unexpected_error_no_reraise():
    """Test error handling decorator with unexpected error and reraise=False."""

    @handle_snowflake_errors(
        operation="test_operation", reraise=False, fallback_value="fallback"
    )
    def failing_function():
        raise ValueError("unexpected error")

    result = failing_function()
    assert result == "fallback"


def test_safe_execute_success():
    """Test safe_execute with successful function."""

    def success_func():
        return "success"

    result = safe_execute(success_func)
    assert result == "success"


def test_safe_execute_with_snowcli_error():
    """Test safe_execute with SnowCLIError."""

    def failing_func():
        raise SnowCLIError("test error")

    result = safe_execute(failing_func, fallback_value="fallback")
    assert result == "fallback"


def test_safe_execute_with_context():
    """Test safe_execute with error context."""
    context = ErrorContext(operation="test_operation", database="test_db")

    def failing_func():
        raise SnowCLIError("test error")

    result = safe_execute(failing_func, context=context, fallback_value="fallback")
    assert result == "fallback"


def test_safe_execute_with_unexpected_error():
    """Test safe_execute with unexpected error."""

    def failing_func():
        raise ValueError("unexpected")

    result = safe_execute(failing_func, fallback_value="fallback")
    assert result == "fallback"


def test_error_aggregator_creation():
    """Test ErrorAggregator creation."""
    aggregator = ErrorAggregator()
    assert len(aggregator.errors) == 0
    assert len(aggregator.warnings) == 0
    assert not aggregator.has_errors()


def test_error_aggregator_add_error():
    """Test adding errors to ErrorAggregator."""
    aggregator = ErrorAggregator()
    error = ValueError("test error")

    aggregator.add_error("key1", error)

    assert aggregator.has_errors()
    assert len(aggregator.errors) == 1
    assert aggregator.errors["key1"] == error


def test_error_aggregator_add_warning():
    """Test adding warnings to ErrorAggregator."""
    aggregator = ErrorAggregator()

    aggregator.add_warning("key1", "test warning")

    assert not aggregator.has_errors()  # Warnings don't count as errors
    assert len(aggregator.warnings) == 1
    assert aggregator.warnings["key1"] == "test warning"


def test_error_aggregator_summary():
    """Test ErrorAggregator summary generation."""
    aggregator = ErrorAggregator()

    error1 = ValueError("error1")
    error2 = RuntimeError("error2")

    aggregator.add_error("key1", error1)
    aggregator.add_error("key2", error2)
    aggregator.add_warning("warn1", "warning1")
    aggregator.add_warning("warn2", "warning2")

    summary = aggregator.get_summary()

    assert summary["error_count"] == 2
    assert summary["warning_count"] == 2
    assert summary["errors"]["key1"] == "error1"
    assert summary["errors"]["key2"] == "error2"
    assert summary["warnings"]["warn1"] == "warning1"
    assert summary["warnings"]["warn2"] == "warning2"


@patch("igloo_mcp.error_handling.logger")
def test_error_handling_logging(mock_logger):
    """Test that error handling properly logs errors."""

    @handle_snowflake_errors(operation="test_operation", database="test_db")
    def failing_function():
        raise SnowCLIError("connection failed")

    with pytest.raises(SnowflakeConnectionError):
        failing_function()

    # Verify logging was called
    mock_logger.error.assert_called_once()
    args, kwargs = mock_logger.error.call_args
    assert "Snowflake operation failed: test_operation" in args[0]
    assert kwargs["extra"]["database"] == "test_db"


def test_handle_snowflake_errors_with_context_parameters():
    """Test error handling decorator with context parameters."""

    @handle_snowflake_errors(
        operation="test_op",
        database="test_db",
        schema="test_schema",
        object_name="test_obj",
    )
    def failing_function():
        raise SnowCLIError("permission denied")

    with pytest.raises(SnowflakePermissionError) as exc_info:
        failing_function()

    assert "Permission denied for test_op" in str(exc_info.value)
