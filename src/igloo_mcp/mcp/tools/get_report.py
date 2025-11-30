"""Get Report MCP Tool - Read living reports with selective retrieval.

This tool allows agents to read report structure and content efficiently,
with multiple modes for progressive disclosure and token efficiency.
"""

from __future__ import annotations

import time
from typing import Any

from igloo_mcp.config import Config
from igloo_mcp.living_reports.selector import ReportSelector, SelectorResolutionError
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.exceptions import (
    MCPExecutionError,
    MCPSelectorError,
)
from igloo_mcp.mcp.tools.base import MCPTool, ensure_request_id, tool_error_handler
from igloo_mcp.mcp.validation_helpers import validate_response_mode

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class GetReportTool(MCPTool):
    """MCP tool for reading living reports with selective retrieval."""

    def __init__(self, config: Config, report_service: ReportService):
        """Initialize get report tool.

        Args:
            config: Application configuration
            report_service: Report service instance
        """
        self.config = config
        self.report_service = report_service

    @property
    def name(self) -> str:
        return "get_report"

    @property
    def description(self) -> str:
        return (
            "Read a report's structure or content with progressive disclosure. "
            "Use BEFORE evolve_report to understand current state and obtain IDs for modifications. "
            "Start with response_mode='minimal' (IDs only), drill down with 'standard' or 'full' only when needed."
        )

    @property
    def category(self) -> str:
        return "reports"

    @property
    def tags(self) -> list[str]:
        return ["reports", "read", "retrieval", "inspection"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
        return [
            {
                "description": "Get lightweight summary of report structure",
                "parameters": {
                    "report_selector": "Q1 Network Analysis",
                    "mode": "summary",
                },
            },
            {
                "description": "Get details for specific section",
                "parameters": {
                    "report_selector": "Q1 Network Analysis",
                    "mode": "sections",
                    "section_titles": ["Network Activity"],
                    "include_content": True,
                },
            },
            {
                "description": "Get high-importance insights only",
                "parameters": {
                    "report_selector": "Q1 Network Analysis",
                    "mode": "insights",
                    "min_importance": 8,
                },
            },
            {
                "description": "Get full report structure",
                "parameters": {
                    "report_selector": "rpt_550e8400e29b11d4a716446655440000",
                    "mode": "full",
                },
            },
        ]

    @tool_error_handler("get_report")
    async def execute(
        self,
        report_selector: str,
        response_mode: str | None = None,
        mode: str | None = None,  # DEPRECATED in v0.3.5
        section_ids: list[str] | None = None,
        section_titles: list[str] | None = None,
        insight_ids: list[str] | None = None,
        min_importance: int | None = None,
        limit: int = 50,
        offset: int = 0,
        include_content: bool = False,
        include_audit: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute report retrieval with selective filtering.

        Args:
            report_selector: Report ID or title to retrieve
            response_mode: Retrieval mode (STANDARD: 'minimal', 'standard', 'full')
                - 'minimal': Lightweight overview (metadata only)
                - 'standard': Section/insight structure (default)
                - 'full': Complete report with all details
            mode: DEPRECATED - use response_mode instead
                Legacy values: 'summary' → 'minimal', 'sections'/'insights' → 'standard', 'full' → 'full'
            section_ids: Filter to specific section IDs
            section_titles: Filter to sections matching titles (fuzzy)
            insight_ids: Filter to specific insight IDs
            min_importance: Filter insights with importance >= this value
            limit: Maximum items to return (default 50)
            offset: Skip first N items (default 0)
            include_content: Include section prose content
            include_audit: Include recent audit events
            request_id: Optional request correlation ID

        Returns:
            Report data formatted according to response_mode

        Raises:
            MCPValidationError: If parameters are invalid
            MCPSelectorError: If report not found
            MCPExecutionError: If retrieval fails
        """
        start_time = time.time()
        request_id = ensure_request_id(request_id)

        # Validate response_mode with backward compatibility
        # Map legacy values to standard values for response structure
        effective_mode = validate_response_mode(
            response_mode,
            legacy_param_name="mode",
            legacy_param_value=mode,
            valid_modes=("minimal", "standard", "full", "summary", "sections", "insights"),
            default="minimal",
        )

        # Keep track of original mode for routing decisions
        original_mode = effective_mode

        # Map legacy values to standard values for response structure
        mode_mapping = {
            "summary": "minimal",
            "sections": "standard",
            "insights": "standard",
            "full": "full",
            "minimal": "minimal",
            "standard": "standard",
        }
        mode = mode_mapping.get(effective_mode, effective_mode)

        # Validate limit and offset
        if limit < 1:
            limit = 1
        elif limit > 100:
            limit = 100
        if offset < 0:
            offset = 0

        logger.info(
            "get_report_started",
            extra={
                "report_selector": report_selector,
                "mode": mode,
                "request_id": request_id,
            },
        )

        # Resolve selector
        selector_start = time.time()
        try:
            self.report_service.index.rebuild_from_filesystem()
            selector = ReportSelector(self.report_service.index)
            report_id = selector.resolve(report_selector, strict=False)
        except SelectorResolutionError as e:
            selector_duration = (time.time() - selector_start) * 1000
            error_dict = e.to_dict()
            logger.warning(
                "get_report_selector_error",
                extra={
                    "report_selector": report_selector,
                    "error_type": error_dict.get("error"),
                    "request_id": request_id,
                    "selector_duration_ms": selector_duration,
                },
            )
            raise MCPSelectorError(
                error_dict.get("message", f"Could not resolve report selector: {report_selector}"),
                selector=report_selector,
                error=error_dict.get("error", "not_found"),
                candidates=error_dict.get("candidates", []),
                hints=[
                    f"Verify report_selector matches an existing report: {report_selector}",
                    "Check report ID or title spelling (case-insensitive)",
                    "Use search_report to find available reports",
                ],
                context={"request_id": request_id},
            ) from e

        # Load outline
        retrieval_start = time.time()
        try:
            outline = self.report_service.get_report_outline(report_id)
        except ValueError as e:
            retrieval_duration = (time.time() - retrieval_start) * 1000
            raise MCPExecutionError(
                f"Failed to load report: {e!s}",
                operation="get_report",
                hints=["Verify the report exists and is accessible"],
                context={"request_id": request_id, "report_id": report_id},
            ) from e

        # Build response based on mode
        if mode == "minimal":
            response = self._build_summary_response(outline, include_audit, report_id)
        elif mode == "standard":
            # For standard mode, decide based on original mode (for backward compat) first, then filters
            if original_mode == "insights":
                # Legacy 'insights' mode - always use insights response
                response = self._build_insights_response(
                    outline,
                    insight_ids,
                    min_importance,
                    section_ids,  # Can filter insights by section
                    limit,
                    offset,
                )
            elif original_mode == "sections":
                # Legacy 'sections' mode - always use sections response
                response = self._build_sections_response(
                    outline,
                    section_ids,
                    section_titles,
                    include_content,
                    limit,
                    offset,
                )
            elif insight_ids or min_importance is not None:
                # New response_mode with insight filters
                response = self._build_insights_response(
                    outline,
                    insight_ids,
                    min_importance,
                    section_ids,
                    limit,
                    offset,
                )
            elif section_ids or section_titles:
                # New response_mode with section filters
                response = self._build_sections_response(
                    outline,
                    section_ids,
                    section_titles,
                    include_content,
                    limit,
                    offset,
                )
            else:
                # Default to sections view if no specific mode or filters
                response = self._build_sections_response(
                    outline,
                    section_ids,
                    section_titles,
                    include_content,
                    limit,
                    offset,
                )
        elif mode == "full":
            response = self._build_full_response(outline, include_content, include_audit, limit, offset)

        retrieval_duration = (time.time() - retrieval_start) * 1000
        total_duration = (time.time() - start_time) * 1000

        # Add common fields
        response["request_id"] = request_id

        # Condense timing based on mode
        if mode == "minimal":
            response["duration_ms"] = round(total_duration, 2)
        else:
            response["timing"] = {
                "selector_duration_ms": round((time.time() - selector_start) * 1000, 2),
                "retrieval_duration_ms": round(retrieval_duration, 2),
                "total_duration_ms": round(total_duration, 2),
            }

        logger.info(
            "get_report_completed",
            extra={
                "report_id": report_id,
                "mode": mode,
                "request_id": request_id,
                "retrieval_duration_ms": retrieval_duration,
                "total_duration_ms": total_duration,
            },
        )

        return response

    def _build_summary_response(self, outline: Any, include_audit: bool, report_id: str) -> dict[str, Any]:
        """Build summary mode response (lightweight overview)."""
        return {
            "status": "success",
            "report_id": outline.report_id,
            "title": outline.title,
            "template": outline.metadata.get("template", "default"),
            "created_at": outline.created_at,
            "updated_at": outline.updated_at,
            "outline_version": outline.outline_version,
            "summary": {
                "total_sections": len(outline.sections),
                "total_insights": len(outline.insights),
                "tags": outline.metadata.get("tags", []),
                "status": outline.metadata.get("status", "active"),
            },
            "sections_overview": [
                {
                    "section_id": s.section_id,
                    "title": s.title,
                    "insight_count": len(s.insight_ids),
                    "order": s.order,
                }
                for s in sorted(outline.sections, key=lambda x: x.order)
            ],
        }

    def _build_sections_response(
        self,
        outline: Any,
        section_ids: list[str] | None,
        section_titles: list[str] | None,
        include_content: bool,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        """Build sections mode response."""
        # Filter sections
        sections = outline.sections

        if section_ids:
            section_id_set = set(section_ids)
            sections = [s for s in sections if s.section_id in section_id_set]

        if section_titles:
            # Fuzzy match on titles (case-insensitive substring)
            title_lowers = [t.lower() for t in section_titles]
            sections = [s for s in sections if any(title in s.title.lower() for title in title_lowers)]

        # Apply pagination
        total_matched = len(sections)
        sections = sections[offset : offset + limit]

        # Build section data
        sections_data = []
        for section in sorted(sections, key=lambda x: x.order):
            section_dict = {
                "section_id": section.section_id,
                "title": section.title,
                "order": section.order,
                "insight_ids": section.insight_ids,
                "insight_count": len(section.insight_ids),
            }
            if section.notes:
                section_dict["notes"] = section.notes
            if include_content and section.content:
                section_dict["content"] = section.content
                section_dict["content_format"] = section.content_format
            sections_data.append(section_dict)

        return {
            "status": "success",
            "report_id": outline.report_id,
            "sections": sections_data,
            "total_matched": total_matched,
            "returned": len(sections_data),
            "limit": limit,
            "offset": offset,
        }

    def _build_insights_response(
        self,
        outline: Any,
        insight_ids: list[str] | None,
        min_importance: int | None,
        section_ids: list[str] | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        """Build insights mode response."""
        # Build section ownership map
        section_map = {}
        for section in outline.sections:
            for insight_id in section.insight_ids:
                section_map[insight_id] = section.section_id

        # Filter insights
        insights = outline.insights

        if insight_ids:
            insight_id_set = set(insight_ids)
            insights = [i for i in insights if i.insight_id in insight_id_set]

        if min_importance is not None:
            insights = [i for i in insights if i.importance >= min_importance]

        if section_ids:
            section_id_set = set(section_ids)
            insights = [i for i in insights if section_map.get(i.insight_id) in section_id_set]

        # Apply pagination
        total_matched = len(insights)
        insights = insights[offset : offset + limit]

        # Build insight data
        insights_data = []
        for insight in sorted(insights, key=lambda x: x.importance, reverse=True):
            insight_dict = {
                "insight_id": insight.insight_id,
                "summary": insight.summary,
                "importance": insight.importance,
                "status": insight.status,
                "section_id": section_map.get(insight.insight_id),
                "has_citations": bool(insight.supporting_queries or insight.citations),
                "citation_count": len(insight.supporting_queries or insight.citations or []),
            }
            insights_data.append(insight_dict)

        filters_applied: dict[str, Any] = {}
        if min_importance is not None:
            filters_applied["min_importance"] = min_importance
        if section_ids:
            filters_applied["section_ids"] = section_ids

        return {
            "status": "success",
            "report_id": outline.report_id,
            "insights": insights_data,
            "total_matched": total_matched,
            "returned": len(insights_data),
            "limit": limit,
            "offset": offset,
            "filtered_by": filters_applied if filters_applied else None,
        }

    def _build_full_response(
        self,
        outline: Any,
        include_content: bool,
        include_audit: bool,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        """Build full mode response (complete report)."""
        # Paginate sections and insights
        sections = sorted(outline.sections, key=lambda x: x.order)
        insights = sorted(outline.insights, key=lambda x: x.importance, reverse=True)

        total_sections = len(sections)
        total_insights = len(insights)

        sections = sections[offset : offset + limit]
        insights = insights[offset : offset + limit]

        # Build section data
        sections_data = []
        for section in sections:
            section_dict = {
                "section_id": section.section_id,
                "title": section.title,
                "order": section.order,
                "insight_ids": section.insight_ids,
            }
            if section.notes:
                section_dict["notes"] = section.notes
            if include_content and section.content:
                section_dict["content"] = section.content
                section_dict["content_format"] = section.content_format
            sections_data.append(section_dict)

        # Build insight data
        insights_data = []
        for insight in insights:
            insight_dict = {
                "insight_id": insight.insight_id,
                "summary": insight.summary,
                "importance": insight.importance,
                "status": insight.status,
            }
            if insight.supporting_queries:
                insight_dict["supporting_queries"] = [
                    {
                        "execution_id": sq.execution_id,
                        "sql_sha256": sq.sql_sha256,
                    }
                    for sq in (insight.supporting_queries or [])
                    if sq.execution_id or sq.sql_sha256
                ]
            insights_data.append(insight_dict)

        return {
            "status": "success",
            "report_id": outline.report_id,
            "title": outline.title,
            "created_at": outline.created_at,
            "updated_at": outline.updated_at,
            "outline_version": outline.outline_version,
            "outline": outline.model_dump(),  # Add full outline object
            "metadata": outline.metadata,
            "sections": sections_data,
            "insights": insights_data,
            "total_sections": total_sections,
            "total_insights": total_insights,
            "returned_sections": len(sections_data),
            "returned_insights": len(insights_data),
            "limit": limit,
            "offset": offset,
        }

    def get_parameter_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Get Report Parameters",
            "type": "object",
            "additionalProperties": False,
            "required": ["report_selector"],
            "properties": {
                "report_selector": {
                    "type": "string",
                    "description": "Report ID or title to retrieve",
                    "examples": [
                        "Q1 Network Analysis",
                        "rpt_550e8400e29b11d4a716446655440000",
                    ],
                },
                "mode": {
                    "type": "string",
                    "description": "Retrieval mode for token efficiency",
                    "enum": ["summary", "sections", "insights", "full"],
                    "default": "summary",
                    "examples": ["summary", "sections", "insights"],
                },
                "section_ids": {
                    "type": "array",
                    "description": "Filter to specific section IDs (mode='sections' or mode='insights')",
                    "items": {"type": "string"},
                    "examples": [["550e8400-e29b-41d4-a716-446655440012"]],
                },
                "section_titles": {
                    "type": "array",
                    "description": "Filter to sections matching titles (fuzzy, case-insensitive)",
                    "items": {"type": "string"},
                    "examples": [["Network Activity", "Executive Summary"]],
                },
                "insight_ids": {
                    "type": "array",
                    "description": "Filter to specific insight IDs (mode='insights')",
                    "items": {"type": "string"},
                },
                "min_importance": {
                    "type": "integer",
                    "description": "Filter insights with importance >= this value (mode='insights')",
                    "minimum": 0,
                    "maximum": 10,
                    "examples": [8, 9],
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum items to return (default 50, max 100)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 50,
                },
                "offset": {
                    "type": "integer",
                    "description": "Skip first N items (pagination, default 0)",
                    "minimum": 0,
                    "default": 0,
                },
                "include_content": {
                    "type": "boolean",
                    "description": "Include section prose content (mode='sections' or mode='full')",
                    "default": False,
                },
                "include_audit": {
                    "type": "boolean",
                    "description": "Include recent audit events (mode='summary' or mode='full')",
                    "default": False,
                },
                "request_id": {
                    "type": "string",
                    "description": "Optional request correlation ID for tracing",
                },
            },
        }


__all__ = ["GetReportTool"]
