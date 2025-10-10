"""Query service for service layer."""

from typing import Any, Dict, Optional

from ..snow_cli import SnowCLI, QueryOutput


class QueryService:
    """Service for executing Snowflake queries."""
    
    def __init__(self, context: Optional[Any] = None):
        """Initialize query service.
        
        Args:
            context: Service context with profile information
        """
        self.context = context
        if hasattr(context, 'config') and hasattr(context.config, 'snowflake'):
            self.profile = context.config.snowflake.profile
        else:
            self.profile = None
        self.cli = SnowCLI(self.profile)
    
    def execute(
        self,
        query: str,
        output_format: Optional[str] = None,
        timeout: Optional[int] = None,
        session: Optional[Dict[str, Any]] = None,
        **kwargs
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
        return self.cli.run_query(
            query,
            output_format=output_format,
            timeout=timeout,
            ctx_overrides=session
        )

    def session_from_mapping(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
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
