"""Query service for service layer."""

import os
from typing import Any, Dict, Optional

from ..snow_cli import QueryOutput, SnowCLI
from ..snow_rest import SnowRestClient


class QueryService:
    """Service for executing Snowflake queries."""

    def __init__(self, context: Optional[Any] = None, *, driver: Optional[str] = None):
        """Initialize query service.

        Args:
            context: Service context with profile information
        """
        self.context = context
        driver_name = (
            driver or os.environ.get("IGLOO_MCP_SNOW_DRIVER") or "cli"
        ).lower()
        if hasattr(context, "config") and hasattr(context.config, "snowflake"):
            self.profile = context.config.snowflake.profile
        else:
            self.profile = None
        self.driver = driver_name
        self.cli: Optional[SnowCLI] = None
        self.rest_client: Optional[SnowRestClient] = None
        if driver_name == "rest":
            default_ctx = {}
            if hasattr(context, "config") and hasattr(context.config, "snowflake"):
                default_ctx = context.config.snowflake.session_defaults()
            try:
                self.rest_client = SnowRestClient.from_env(default_context=default_ctx)
            except Exception:
                # Fall back to CLI driver if REST client setup fails for any reason
                self.cli = SnowCLI(self.profile)
                self.driver = "cli"
        else:
            self.cli = SnowCLI(self.profile)

    def execute(
        self,
        query: str,
        output_format: Optional[str] = None,
        timeout: Optional[int] = None,
        session: Optional[Dict[str, Any]] = None,
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

        return self.cli.run_query(
            query, output_format=output_format, timeout=timeout, ctx_overrides=session
        )

    def session_from_mapping(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Create session context from mapping."""
        return {
            "warehouse": mapping.get("warehouse"),
            "database": mapping.get("database"),
            "schema": mapping.get("schema"),
            "role": mapping.get("role"),
        }

    def execute_with_service(
        self, query: str, service: Any = None, **kwargs
    ) -> QueryOutput:
        """Execute query with service."""
        return self.execute(query, **kwargs)
