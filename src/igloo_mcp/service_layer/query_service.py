"""Query service for service layer."""

import logging
import os
from typing import Any

from igloo_mcp.snow_cli import QueryOutput, SnowCLI
from igloo_mcp.snow_rest import SnowRestClient

logger = logging.getLogger(__name__)


class QueryService:
    """Service for executing Snowflake queries."""

    def __init__(self, context: Any | None = None, *, driver: str | None = None):
        """Initialize query service.

        Args:
            context: Service context with profile information
        """
        self.context = context
        driver_name = (driver or os.environ.get("IGLOO_MCP_SNOW_DRIVER") or "cli").lower()
        if context is not None and hasattr(context, "config") and hasattr(context.config, "snowflake"):
            self.profile = context.config.snowflake.profile
        else:
            self.profile = None
        self.driver = driver_name
        self.cli: SnowCLI | None = None
        self.rest_client: SnowRestClient | None = None
        if driver_name == "rest":
            default_ctx = {}
            if context is not None and hasattr(context, "config") and hasattr(context.config, "snowflake"):
                default_ctx = context.config.snowflake.session_defaults()
            try:
                self.rest_client = SnowRestClient.from_env(default_context=default_ctx)
            except (AttributeError, KeyError, TypeError, ValueError):
                # Fall back to CLI driver if REST client setup fails for any reason
                logger.warning(
                    "SnowREST initialization failed; falling back to SnowCLI driver",
                    exc_info=True,
                )
                self.cli = SnowCLI(self.profile)
                self.driver = "cli"
        else:
            self.cli = SnowCLI(self.profile)

    def execute(
        self,
        query: str,
        output_format: str | None = None,
        timeout: int | None = None,
        session: dict[str, Any] | None = None,
        **kwargs,
    ) -> QueryOutput:
        """Execute a query.

        Args:
            query: SQL query to execute
            output_format: Output format ('table', 'json', 'csv')
            timeout: Query timeout in seconds
            session: Session context overrides
            **kwargs: Additional parameters

        Returns:
            Query execution result
        """
        if self.driver == "rest" and self.rest_client is not None:
            result = self.rest_client.run_query(
                query,
                ctx_overrides=session,
                timeout=timeout,
            )
            return result

        if not self.cli:
            raise RuntimeError("Snowflake CLI driver unavailable")

        return self.cli.run_query(query, output_format=output_format, timeout=timeout, ctx_overrides=session)

    def session_from_mapping(self, mapping: dict[str, Any]) -> dict[str, Any]:
        """Create session context from mapping."""
        return {
            "warehouse": mapping.get("warehouse"),
            "database": mapping.get("database"),
            "schema": mapping.get("schema"),
            "role": mapping.get("role"),
        }

    def execute_with_service(self, query: str, service: Any = None, **kwargs) -> QueryOutput:
        """Execute query with service."""
        return self.execute(query, **kwargs)
