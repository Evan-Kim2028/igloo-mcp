"""Search Citations MCP Tool - Search citations across all reports.

This tool enables powerful citation discovery and audit workflows by searching
across all reports to find insights backed by specific sources.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from igloo_mcp.config import Config
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.exceptions import MCPValidationError
from igloo_mcp.mcp.tools.base import MCPTool, ensure_request_id, tool_error_handler

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class SearchCitationsTool(MCPTool):
    """MCP tool for searching citations across all living reports."""

    def __init__(self, config: Config, report_service: ReportService):
        """Initialize search citations tool.

        Args:
            config: Application configuration
            report_service: Report service instance
        """
        self.config = config
        self.report_service = report_service

    @property
    def name(self) -> str:
        return "search_citations"

    @property
    def description(self) -> str:
        return (
            "Search citations across all living reports. Find insights backed by specific "
            "data sources including queries, APIs, URLs, observations, and documents. "
            "Supports filtering by source type, provider, URL patterns, and more. "
            "Enables citation auditing and discovery workflows."
        )

    @property
    def category(self) -> str:
        return "reports"

    @property
    def tags(self) -> list[str]:
        return ["reports", "citations", "search", "audit"]

    @property
    def usage_examples(self) -> list[Dict[str, Any]]:
        return [
            {
                "description": "Find all insights citing DeFiLlama API",
                "parameters": {
                    "source_type": "api",
                    "provider": "defillama",
                },
            },
            {
                "description": "Search for insights backed by specific URL",
                "parameters": {
                    "url_contains": "monad.xyz",
                },
            },
            {
                "description": "Group citations by provider to audit sources",
                "parameters": {
                    "group_by": "provider",
                    "limit": 100,
                },
            },
        ]

    @tool_error_handler("search_citations")
    async def execute(
        self,
        source_type: Optional[str] = None,
        provider: Optional[str] = None,
        url_contains: Optional[str] = None,
        description_contains: Optional[str] = None,
        execution_id: Optional[str] = None,
        limit: int = 50,
        group_by: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search citations across all reports.

        Args:
            source_type: Filter by source type (query, api, url, observation, document)
            provider: Filter by provider (snowflake, allium, defillama, etc.)
            url_contains: Substring search in URL field
            description_contains: Substring search in description field
            execution_id: Exact match on execution_id (for query sources)
            limit: Maximum results to return (default: 50, max: 200)
            group_by: Group results by field ("source" or "provider")
            request_id: Optional request correlation ID for tracing

        Returns:
            Dictionary with:
            - status: "success"
            - matches_found: Number of matching citations
            - citations: List of citation matches with insight context
            - grouped_results: Optional grouped results if group_by specified
            - request_id: Request correlation ID

        Raises:
            MCPValidationError: If parameters are invalid
        """
        start_time = time.time()
        request_id = ensure_request_id(request_id)

        # Validate source_type if provided
        valid_sources = {"query", "api", "url", "observation", "document"}
        if source_type and source_type not in valid_sources:
            raise MCPValidationError(
                f"Invalid source_type '{source_type}'",
                validation_errors=[f"Must be one of: {', '.join(sorted(valid_sources))}"],
                hints=[
                    "Use source_type='query' for Snowflake/Allium queries",
                    "Use source_type='api' for API calls (DeFiLlama, CoinGecko, etc.)",
                    "Use source_type='url' for web pages and articles",
                ],
                context={"request_id": request_id},
            )

        # Validate group_by if provided
        if group_by and group_by not in ("source", "provider"):
            raise MCPValidationError(
                f"Invalid group_by '{group_by}'",
                validation_errors=["Must be 'source' or 'provider'"],
                context={"request_id": request_id},
            )

        # Validate limit
        if limit < 1:
            limit = 1
        elif limit > 200:
            limit = 200

        logger.info(
            "search_citations_started",
            extra={
                "source_type": source_type,
                "provider": provider,
                "limit": limit,
                "group_by": group_by,
                "request_id": request_id,
            },
        )

        # Collect all citations from all reports
        all_citations: List[Dict[str, Any]] = []

        try:
            # Rebuild index to get latest reports
            if getattr(self.report_service, "index", None):
                self.report_service.index.rebuild_from_filesystem()

            # Get all active reports
            index = self.report_service.index
            all_entries = index.list_entries(status="active", sort_by="updated_at", reverse=True)

            for entry in all_entries:
                report_id = entry.report_id
                try:
                    outline = self.report_service.get_report_outline(report_id)

                    # Search citations in each insight
                    for insight in outline.insights:
                        if not insight.citations:
                            continue

                        for citation in insight.citations:
                            # Apply filters
                            if source_type and citation.source != source_type:
                                continue
                            if provider and citation.provider != provider:
                                continue
                            if url_contains and (not citation.url or url_contains.lower() not in citation.url.lower()):
                                continue
                            if description_contains and (
                                not citation.description
                                or description_contains.lower() not in citation.description.lower()
                            ):
                                continue
                            if execution_id and citation.execution_id != execution_id:
                                continue

                            # Match found - add to results
                            all_citations.append(
                                {
                                    "citation": citation.model_dump(),
                                    "insight": {
                                        "insight_id": insight.insight_id,
                                        "summary": insight.summary,
                                        "importance": insight.importance,
                                    },
                                    "report": {
                                        "report_id": report_id,
                                        "title": outline.title,
                                    },
                                }
                            )

                except Exception as e:
                    logger.warning(
                        "search_citations_report_error",
                        extra={
                            "report_id": report_id,
                            "error": str(e),
                            "request_id": request_id,
                        },
                    )
                    continue

        except Exception as e:
            logger.error(
                "search_citations_error",
                extra={
                    "error": str(e),
                    "request_id": request_id,
                },
            )
            raise

        # Apply limit
        total_matches = len(all_citations)
        limited_citations = all_citations[:limit]

        # Group results if requested
        grouped_results = None
        if group_by:
            grouped_results = self._group_citations(limited_citations, group_by)

        total_duration = (time.time() - start_time) * 1000

        logger.info(
            "search_citations_completed",
            extra={
                "matches_found": total_matches,
                "returned": len(limited_citations),
                "total_duration_ms": total_duration,
                "request_id": request_id,
            },
        )

        return {
            "status": "success",
            "matches_found": total_matches,
            "returned": len(limited_citations),
            "citations": limited_citations,
            "grouped_results": grouped_results,
            "request_id": request_id,
            "timing": {
                "total_duration_ms": round(total_duration, 2),
            },
        }

    def _group_citations(
        self,
        citations: List[Dict[str, Any]],
        group_by: str,
    ) -> Dict[str, Any]:
        """Group citations by specified field.

        Args:
            citations: List of citation results
            group_by: Field to group by ("source" or "provider")

        Returns:
            Dictionary with grouped results
        """
        grouped: Dict[str, List[Dict[str, Any]]] = {}

        for cit_result in citations:
            citation = cit_result["citation"]
            key = citation.get(group_by, "unknown")

            if key not in grouped:
                grouped[key] = []

            grouped[key].append(cit_result)

        # Add counts
        result = {
            "groups": grouped,
            "summary": {group_key: len(items) for group_key, items in grouped.items()},
        }

        return result

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "source_type": {
                    "type": "string",
                    "enum": ["query", "api", "url", "observation", "document"],
                    "description": "Filter by citation source type",
                },
                "provider": {
                    "type": "string",
                    "description": "Filter by provider (snowflake, allium, defillama, etc.)",
                },
                "url_contains": {
                    "type": "string",
                    "description": "Substring search in URL field (case-insensitive)",
                },
                "description_contains": {
                    "type": "string",
                    "description": "Substring search in description field (case-insensitive)",
                },
                "execution_id": {
                    "type": "string",
                    "description": "Exact match on execution_id (for query sources)",
                },
                "limit": {
                    "type": "integer",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 200,
                    "description": "Maximum number of results to return",
                },
                "group_by": {
                    "type": "string",
                    "enum": ["source", "provider"],
                    "description": "Group results by field",
                },
            },
        }


__all__ = ["SearchCitationsTool"]
