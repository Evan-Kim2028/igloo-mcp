"""Tests for service layer functionality."""

from unittest.mock import Mock, patch

import pytest

from igloo_mcp.circuit_breaker import CircuitBreakerError
from igloo_mcp.services import (
    HealthStatus,
    RobustSnowflakeService,
    execute_query_safe,
)
from igloo_mcp.snow_cli import QueryOutput, SnowCLIError


def test_health_status_creation():
    """Test HealthStatus dataclass creation."""
    status = HealthStatus(healthy=True, snowflake_connection=True)
    assert status.healthy is True
    assert status.snowflake_connection is True
    assert status.last_error is None
    assert status.circuit_breaker_state is None

    status_with_error = HealthStatus(
        healthy=False,
        snowflake_connection=False,
        last_error="Connection failed",
        circuit_breaker_state="open",
    )
    assert status_with_error.healthy is False
    assert status_with_error.last_error == "Connection failed"
    assert status_with_error.circuit_breaker_state == "open"


@patch("igloo_mcp.services.SnowCLI")
def test_robust_snowflake_service_init(mock_cli_class):
    """Test RobustSnowflakeService initialization."""
    mock_cli = Mock()
    mock_cli_class.return_value = mock_cli

    service = RobustSnowflakeService(profile="test_profile")
    assert service.cli == mock_cli
    assert service._last_error is None
    mock_cli_class.assert_called_once_with("test_profile")


@patch("igloo_mcp.services.SnowCLI")
def test_execute_query_success(mock_cli_class):
    """Test successful query execution."""
    mock_cli = Mock()
    mock_cli_class.return_value = mock_cli

    mock_result = QueryOutput("output", "", 0)
    mock_cli.run_query.return_value = mock_result

    service = RobustSnowflakeService()
    result = service.execute_query("SELECT 1")

    assert result == mock_result
    assert service._last_error is None
    mock_cli.run_query.assert_called_once_with(
        "SELECT 1", output_format=None, ctx_overrides=None, timeout=None
    )


@patch("igloo_mcp.services.SnowCLI")
def test_execute_query_failure(mock_cli_class):
    """Test query execution failure."""
    mock_cli = Mock()
    mock_cli_class.return_value = mock_cli

    mock_cli.run_query.side_effect = SnowCLIError("Query failed")

    service = RobustSnowflakeService()

    with pytest.raises(SnowCLIError):
        service.execute_query("SELECT 1")

    assert service._last_error == "Query failed"


@patch("igloo_mcp.services.SnowCLI")
def test_test_connection_success(mock_cli_class):
    """Test successful connection test."""
    mock_cli = Mock()
    mock_cli_class.return_value = mock_cli
    mock_cli.test_connection.return_value = True

    service = RobustSnowflakeService()
    result = service.test_connection()

    assert result is True
    assert service._last_error is None


@patch("igloo_mcp.services.SnowCLI")
def test_test_connection_failure(mock_cli_class):
    """Test connection test failure."""
    mock_cli = Mock()
    mock_cli_class.return_value = mock_cli
    mock_cli.test_connection.side_effect = SnowCLIError("Connection failed")

    service = RobustSnowflakeService()

    with pytest.raises(SnowCLIError):
        service.test_connection()

    assert service._last_error == "Connection failed"


@patch("igloo_mcp.services.SnowCLI")
def test_get_health_status_healthy(mock_cli_class):
    """Test health status when system is healthy."""
    mock_cli = Mock()
    mock_cli_class.return_value = mock_cli
    mock_cli.test_connection.return_value = True

    service = RobustSnowflakeService()
    status = service.get_health_status()

    assert status.healthy is True
    assert status.snowflake_connection is True
    assert status.last_error is None


@patch("igloo_mcp.services.SnowCLI")
def test_get_health_status_unhealthy(mock_cli_class):
    """Test health status when system is unhealthy."""
    mock_cli = Mock()
    mock_cli_class.return_value = mock_cli
    mock_cli.test_connection.side_effect = SnowCLIError("Connection failed")

    service = RobustSnowflakeService()
    # Set up the error state
    try:
        service.test_connection()
    except SnowCLIError:
        pass

    status = service.get_health_status()

    assert status.healthy is False
    assert status.snowflake_connection is False
    assert "Connection failed" in status.last_error


@patch("igloo_mcp.services.SnowCLI")
def test_get_health_status_circuit_breaker_open(mock_cli_class):
    """Test health status when circuit breaker is open."""
    mock_cli = Mock()
    mock_cli_class.return_value = mock_cli

    service = RobustSnowflakeService()

    # Mock circuit breaker to be open
    with patch.object(
        service, "test_connection", side_effect=CircuitBreakerError("Circuit open")
    ):
        status = service.get_health_status()

    assert status.healthy is False
    assert status.snowflake_connection is False
    assert "Circuit open" in status.last_error
    assert status.circuit_breaker_state == "open"


def test_execute_query_safe_success():
    """Test safe query execution with success."""
    mock_service = Mock()
    mock_result = QueryOutput("output", "", 0, rows=[{"col1": "value1"}])
    mock_service.execute_query.return_value = mock_result

    result = execute_query_safe(mock_service, "SELECT 1")

    assert result == [{"col1": "value1"}]
    mock_service.execute_query.assert_called_once_with("SELECT 1")


def test_execute_query_safe_snowcli_error():
    """Test safe query execution with SnowCLIError."""
    mock_service = Mock()
    mock_service.execute_query.side_effect = SnowCLIError("Query failed")

    result = execute_query_safe(mock_service, "SELECT 1")

    assert result == []


def test_execute_query_safe_circuit_breaker_error():
    """Test safe query execution with CircuitBreakerError."""
    mock_service = Mock()
    mock_service.execute_query.side_effect = CircuitBreakerError("Circuit open")

    result = execute_query_safe(mock_service, "SELECT 1")

    assert result == []


def test_execute_query_safe_no_rows():
    """Test safe query execution with no rows."""
    mock_service = Mock()
    mock_result = QueryOutput("output", "", 0, rows=None)
    mock_service.execute_query.return_value = mock_result

    result = execute_query_safe(mock_service, "SELECT 1")

    assert result == []


def test_execute_query_safe_with_kwargs():
    """Test safe query execution with additional kwargs."""
    mock_service = Mock()
    mock_result = QueryOutput("output", "", 0, rows=[{"col1": "value1"}])
    mock_service.execute_query.return_value = mock_result

    result = execute_query_safe(
        mock_service, "SELECT 1", output_format="json", timeout=30
    )

    assert result == [{"col1": "value1"}]
    mock_service.execute_query.assert_called_once_with(
        "SELECT 1", output_format="json", timeout=30
    )
