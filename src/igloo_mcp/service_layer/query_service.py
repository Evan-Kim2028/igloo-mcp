"""Query service for service layer."""

from typing import Any, Dict, Optional

from ..snow_cli import SnowCLI, QueryOutput


class QueryService:
    """Service for executing Snowflake queries."""
    
    def __init__(self, context: Optional[Dict[str, Any]] = None):
        """Initialize query service.
        
        Args:
            context: Session context with profile information
        """
        self.context = context or {}
        self.profile = self.context.get("profile")
        self.cli = SnowCLI(self.profile)
    
    def execute(
        self,
        query: str,
        output_format: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> QueryOutput:
        """Execute a query.
        
        Args:
            query: SQL query to execute
            output_format: Output format ('table', 'json', 'csv')
            timeout: Query timeout in seconds
            
        Returns:
            Query execution result
        """
        return self.cli.run_query(
            query,
            output_format=output_format,
            timeout=timeout
        )

    def session_from_mapping(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Create session context from mapping."""
        return {
            "warehouse": mapping.get("warehouse"),
            "database": mapping.get("database"),
            "schema": mapping.get("schema"),
            "role": mapping.get("role"),
        }

    def execute_with_service(self, query: str, **kwargs) -> QueryOutput:
        """Execute query with service."""
        return self.execute(query, **kwargs)
