"""Search Report MCP Tool - Search for living reports with intelligent fallback.

This tool allows agents to search for reports by title, tags, report ID, or status.
When no reports match the search criteria, it automatically returns the most
recent report or the top 5 most recently modified reports to help users discover
available reports.
"""

from __future__ import annotations

import time
from typing import Any

from igloo_mcp.config import Config
from igloo_mcp.living_reports.index import IndexCorruptionError
from igloo_mcp.living_reports.models import IndexEntry
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.exceptions import MCPExecutionError, MCPValidationError
from igloo_mcp.mcp.tools.base import MCPTool, ensure_request_id, tool_error_handler

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class SearchReportTool(MCPTool):
    """MCP tool for searching living reports with fallback behavior."""

    def __init__(self, config: Config, report_service: ReportService):
        """Initialize search report tool.

        Args:
            config: Application configuration
            report_service: Report service instance
        """
        self.config = config
        self.report_service = report_service

    @property
    def name(self) -> str:
        return "search_report"

    @property
    def description(self) -> str:
        return (
            "Find existing reports by title or tags. "
            "Use BEFORE create_report to avoid duplicates, or to locate a report for evolution. "
            "Use fields=['report_id', 'title'] for minimal token usage."
        )

    @property
    def category(self) -> str:
        return "reports"

    @property
    def tags(self) -> list[str]:
        return ["reports", "search", "discovery", "fallback"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
        return [
            {
                "description": "Search for reports with 'revenue' in the title",
                "parameters": {
                    "title": "revenue",
                },
            },
            {
                "description": "Find reports with specific tags",
                "parameters": {
                    "tags": ["monthly", "sales"],
                },
            },
            {
                "description": "Search by exact report ID",
                "parameters": {
                    "report_id": "c9bd8a8a-2a60-4e6e-bf8d-42f71b053438",
                },
            },
            {
                "description": "Get most recent reports (fallback when no matches)",
                "parameters": {},
            },
        ]

    @tool_error_handler("search_report")
    async def execute(
        self,
        title: str | None = None,
        tags: list[str] | None = None,
        report_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
        fields: list[str] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute report search with fallback behavior.

        Args:
            title: Optional title search (exact or partial match, case-insensitive)
            tags: Optional list of tags to filter by (reports must have all tags)
            report_id: Optional exact report ID to search for
            status: Optional status filter ("active" or "archived"), default: "active"
            limit: Maximum number of results to return (1-50), default: 20
            fields: Optional list of fields to return (default: all fields)
            request_id: Optional request correlation ID for tracing (auto-generated if not provided)

        Returns:
            Structured response with search results or fallback results

        Raises:
            MCPValidationError: If status is invalid
            MCPExecutionError: If search fails or index is corrupted
        """
        start_time = time.time()
        request_id = ensure_request_id(request_id)

        # Validate limit
        if limit < 1:
            limit = 1
        elif limit > 50:
            limit = 50

        # Default status to "active" if not specified
        if status is None:
            status = "active"

        # Validate status
        if status not in ("active", "archived", "deleted"):
            raise MCPValidationError(
                f"Invalid status '{status}'. Must be 'active', 'archived', or 'deleted'.",
                validation_errors=[f"Invalid status: {status}"],
                hints=[
                    "Use status='active' to search active reports only",
                    "Use status='archived' to search archived reports only",
                    "Use status='deleted' to search deleted reports",
                    "Status parameter is case-sensitive",
                ],
                context={"request_id": request_id},
            )

        search_criteria = {
            "title": title,
            "tags": tags,
            "report_id": report_id,
            "status": status,
            "limit": limit,
        }

        logger.info(
            "search_report_started",
            extra={
                "search_criteria": search_criteria,
                "request_id": request_id,
            },
        )

        try:
            # Rebuild index from filesystem to sync with CLI-created reports
            index_start = time.time()
            self.report_service.index.rebuild_from_filesystem()
            index_duration = (time.time() - index_start) * 1000

            index = self.report_service.index
            results: list[IndexEntry] = []

            # If report_id is provided, do exact lookup first
            if report_id:
                entry = index.get_entry(report_id)
                # Apply status filter if specified
                results = ([] if status and entry.status != status else [entry]) if entry else []
            # If title is provided, search all entries for title matches
            elif title:
                title_lower = title.lower()
                all_entries = index.list_entries(
                    status=status if status else None,
                    tags=tags if tags else None,
                    sort_by="updated_at",
                    reverse=True,
                )
                # Filter by title substring match
                results = [entry for entry in all_entries if title_lower in entry.current_title.lower()]
            # Otherwise, use list_entries with filters
            else:
                results = index.list_entries(
                    status=status if status else None,
                    tags=tags if tags else None,
                    sort_by="updated_at",
                    reverse=True,
                )

            # Apply limit
            if len(results) > limit:
                results = results[:limit]

            # If no results found, use fallback: return top 5 most recent reports
            fallback = False
            if not results:
                fallback = True
                # Get top 5 most recent reports (all statuses)
                all_reports = index.list_entries(
                    status=None,  # Include all statuses
                    tags=None,
                    sort_by="updated_at",
                    reverse=True,
                )
                results = all_reports[:5]

            # Convert IndexEntry objects to dicts with optional field filtering
            reports_data = []
            all_fields = [
                "report_id",
                "title",
                "created_at",
                "updated_at",
                "tags",
                "status",
                "path",
            ]

            # Determine which fields to include
            if fields:
                # Validate requested fields
                invalid_fields = [f for f in fields if f not in all_fields]
                if invalid_fields:
                    raise MCPValidationError(
                        f"Invalid fields: {', '.join(invalid_fields)}",
                        validation_errors=[f"Unknown field: {f}" for f in invalid_fields],
                        hints=[
                            f"Valid fields are: {', '.join(all_fields)}",
                            "Use fields=['report_id', 'title'] for minimal responses",
                        ],
                        context={"request_id": request_id},
                    )
                selected_fields = fields
            else:
                selected_fields = all_fields

            # Build report data with selected fields
            field_map = {
                "report_id": lambda e: e.report_id,
                "title": lambda e: e.current_title,
                "created_at": lambda e: e.created_at,
                "updated_at": lambda e: e.updated_at,
                "tags": lambda e: e.tags,
                "status": lambda e: e.status,
                "path": lambda e: e.path,
            }

            for entry in results:
                report_dict = {}
                for field in selected_fields:
                    report_dict[field] = field_map[field](entry)
                reports_data.append(report_dict)

            total_duration = (time.time() - start_time) * 1000

            logger.info(
                "search_report_completed",
                extra={
                    "matches_found": len(results),
                    "fallback": fallback,
                    "request_id": request_id,
                    "index_duration_ms": index_duration,
                    "total_duration_ms": total_duration,
                },
            )

            return {
                "status": "fallback" if fallback else "success",
                "matches_found": len(results),
                "fallback": fallback,
                "reports": reports_data,
                "search_criteria": search_criteria,
                "message": (
                    f"No reports matched your search criteria. Showing {len(results)} most recently modified reports."
                    if fallback
                    else f"Found {len(results)} matching report(s)."
                ),
                "request_id": request_id,
                "timing": {
                    "index_duration_ms": round(index_duration, 2),
                    "total_duration_ms": round(total_duration, 2),
                },
            }

        except IndexCorruptionError as e:
            total_duration = (time.time() - start_time) * 1000
            raise MCPExecutionError(
                f"Report index is corrupted: {e!s}",
                operation="search_report",
                original_error=e,
                hints=[
                    "Try rebuilding the report index",
                    "Check file system permissions for index file",
                    "Verify index file is not corrupted or locked",
                ],
                context={"request_id": request_id},
            ) from e

    def get_parameter_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Search Report Parameters",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Search for reports by title (exact or partial match, case-insensitive)",
                    "examples": ["revenue", "Q1 Analysis", "Monthly Sales"],
                },
                "tags": {
                    "type": "array",
                    "description": "Filter reports by tags (reports must have all specified tags)",
                    "items": {"type": "string"},
                    "examples": [["monthly", "sales"], ["analytics", "churn"]],
                },
                "report_id": {
                    "type": "string",
                    "description": "Exact report ID to search for",
                    "examples": ["c9bd8a8a-2a60-4e6e-bf8d-42f71b053438"],
                },
                "status": {
                    "type": "string",
                    "description": "Filter by report status",
                    "enum": ["active", "archived", "deleted"],
                    "default": "active",
                    "examples": ["active", "archived", "deleted"],
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 20,
                    "examples": [5, 10, 20],
                },
            },
        }


__all__ = ["SearchReportTool"]
