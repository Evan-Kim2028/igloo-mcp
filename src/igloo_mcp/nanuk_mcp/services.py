"""Service layer for Snowflake operations with circuit breaker protection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from .circuit_breaker import CircuitBreakerError, circuit_breaker
from .snow_cli import QueryOutput, SnowCLI, SnowCLIError

logger = logging.getLogger(__name__)


class SnowflakeService(Protocol):
    """Protocol for Snowflake service operations."""

    def execute_query(
        self,
        query: str,
        *,
        output_format: Optional[str] = None,
        ctx_overrides: Optional[Dict[str, Optional[str]]] = None,
        timeout: Optional[int] = None,
    ) -> QueryOutput:
        """Execute a query and return results."""
        ...

    def test_connection(self) -> bool:
        """Test if the connection is working."""
        ...


@dataclass
class HealthStatus:
    """Health status information."""

    healthy: bool
    snowflake_connection: bool
    last_error: Optional[str] = None
    circuit_breaker_state: Optional[str] = None


class RobustSnowflakeService:
    """Snowflake service with circuit breaker protection and health monitoring."""

    def __init__(self, profile: Optional[str] = None):
        self.cli = SnowCLI(profile)
        self._last_error: Optional[str] = None

    @circuit_breaker(
        failure_threshold=5, recovery_timeout=60.0, expected_exception=SnowCLIError
    )
    def execute_query(
        self,
        query: str,
        *,
        output_format: Optional[str] = None,
        ctx_overrides: Optional[Dict[str, Optional[str]]] = None,
        timeout: Optional[int] = None,
    ) -> QueryOutput:
        """Execute a query with circuit breaker protection."""
        try:
            result = self.cli.run_query(
                query,
                output_format=output_format,
                ctx_overrides=ctx_overrides,
                timeout=timeout,
            )
            self._last_error = None
            return result
        except SnowCLIError as e:
            self._last_error = str(e)
            logger.error(f"Snowflake query failed: {e}")
            raise

    @circuit_breaker(
        failure_threshold=3, recovery_timeout=30.0, expected_exception=SnowCLIError
    )
    def test_connection(self) -> bool:
        """Test connection with circuit breaker protection."""
        try:
            result = self.cli.test_connection()
            self._last_error = None
            return result
        except SnowCLIError as e:
            self._last_error = str(e)
            logger.error(f"Connection test failed: {e}")
            raise

    def get_health_status(self) -> HealthStatus:
        """Get current health status."""
        try:
            connection_ok = self.test_connection()
            return HealthStatus(
                healthy=connection_ok,
                snowflake_connection=connection_ok,
                last_error=self._last_error,
            )
        except CircuitBreakerError as e:
            return HealthStatus(
                healthy=False,
                snowflake_connection=False,
                last_error=str(e),
                circuit_breaker_state="open",
            )
        except Exception as e:
            return HealthStatus(
                healthy=False, snowflake_connection=False, last_error=str(e)
            )


def execute_query_safe(
    service: SnowflakeService, query: str, **kwargs: Any
) -> List[Dict[str, Any]]:
    """Execute a query safely, returning empty list on failure."""
    try:
        result = service.execute_query(query, **kwargs)
        return result.rows or []
    except (SnowCLIError, CircuitBreakerError) as e:
        logger.warning(f"Query failed safely: {e}")
        return []
