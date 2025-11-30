"""Create Report MCP Tool - Create new living reports via MCP.

This tool allows agents to create new living reports through the MCP interface,
providing a seamless MCP-only workflow for report creation and evolution.
"""

from __future__ import annotations

import time
from typing import Any

from igloo_mcp.config import Config
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.exceptions import MCPExecutionError, MCPValidationError
from igloo_mcp.mcp.tools.base import MCPTool, ensure_request_id, tool_error_handler
from igloo_mcp.mcp.validation_helpers import validate_text_field

VALID_TEMPLATES = (
    "default",
    "monthly_sales",
    "quarterly_review",
    "deep_dive",
    "analyst_v1",
)

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class CreateReportTool(MCPTool):
    """MCP tool for creating new living reports."""

    def __init__(self, config: Config, report_service: ReportService):
        """Initialize create report tool.

        Args:
            config: Application configuration
            report_service: Report service instance
        """
        self.config = config
        self.report_service = report_service

    @property
    def name(self) -> str:
        return "create_report"

    @property
    def description(self) -> str:
        return (
            "Initialize a new living report for accumulating insights over time. "
            "Use AFTER running queries and gathering initial findings—the report is your 'notebook' for consolidating discoveries. "
            "Start with template='default' for flexibility, or 'analyst_v1' when citations are mandatory."
        )

    @property
    def category(self) -> str:
        return "reports"

    @property
    def tags(self) -> list[str]:
        return ["reports", "creation", "templates"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
        return [
            {
                "description": "Create a simple report with default template",
                "parameters": {
                    "title": "Q1 Revenue Analysis",
                },
            },
            {
                "description": "Create report with template and tags",
                "parameters": {
                    "title": "Monthly Sales Report",
                    "template": "monthly_sales",
                    "tags": ["sales", "monthly", "revenue"],
                },
            },
            {
                "description": "Create deep dive report with description",
                "parameters": {
                    "title": "Customer Churn Analysis",
                    "template": "deep_dive",
                    "tags": ["analytics", "churn"],
                    "description": "Comprehensive analysis of customer retention patterns",
                },
            },
            {
                "description": "Create analyst report with citation enforcement",
                "parameters": {
                    "title": "Q1 Network Analysis",
                    "template": "analyst_v1",
                    "tags": ["network", "analysis", "q1"],
                },
            },
        ]

    @tool_error_handler("create_report")
    async def execute(
        self,
        title: str,
        template: str = "default",
        tags: list[str] | None = None,
        description: str | None = None,
        initial_sections: list[dict[str, Any]] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute report creation.

        Args:
            title: Human-readable title for the report (required)
            template: Template name (default, monthly_sales, quarterly_review, deep_dive, analyst_v1)
            tags: Optional list of tags for categorization
            description: Optional description (stored in metadata)
            initial_sections: Optional list of sections (with optional inline insights) to create atomically
            request_id: Optional request correlation ID for tracing (auto-generated if not provided)

        Returns:
            Creation result with status, report_id, and confirmation message

        Raises:
            MCPValidationError: If parameters are invalid
            MCPExecutionError: If report creation fails
        """
        start_time = time.time()
        request_id = ensure_request_id(request_id)

        # Validate title
        validate_text_field(
            value=title,
            field_name="title",
            min_length=3,
            max_length=200,
            pattern=r"^[a-zA-Z0-9\s\-_]+$",
        )

        # Validate description if provided
        if description:
            validate_text_field(
                value=description,
                field_name="description",
                min_length=5,
                max_length=500,
                allow_empty=True,
            )

        logger.info(
            "create_report_started",
            extra={
                "title": title,
                "template": template,
                "request_id": request_id,
            },
        )

        # Validate template
        if template not in VALID_TEMPLATES:
            raise MCPValidationError(
                f"Invalid template '{template}'. Must be one of: {', '.join(VALID_TEMPLATES)}",
                validation_errors=[f"Invalid template: {template}"],
                hints=[
                    "Use template='default' for empty report",
                    "Use template='monthly_sales' for sales reports",
                    "Use template='quarterly_review' for quarterly reviews",
                    "Use template='deep_dive' for detailed analysis",
                    "Use template='analyst_v1' for blockchain analysis with citation enforcement",
                ],
                context={"request_id": request_id, "title": title},
            )

        # Prepare metadata
        metadata: dict[str, Any] = {}
        if tags:
            metadata["tags"] = tags
        if description:
            metadata["description"] = description

        # Create report via service layer (MCP calls CLI service layer)
        # Set actor to "agent" for MCP-created reports
        create_start = time.time()
        try:
            report_id = self.report_service.create_report(
                title=title,
                template=template,
                actor="agent",
                initial_sections=initial_sections,
                **metadata,
            )

            # Get outline to retrieve created section/insight IDs
            outline_start = time.time()
            outline = self.report_service.get_report_outline(report_id)
            section_ids_added = [s.section_id for s in outline.sections]
            insight_ids_added = [i.insight_id for i in outline.insights]
            outline_duration = (time.time() - outline_start) * 1000

        except ValueError as e:
            # Template validation errors from service
            create_duration = (time.time() - create_start) * 1000
            raise MCPValidationError(
                f"Report creation failed: {e!s}",
                validation_errors=[str(e)],
                hints=[
                    f"Check template name is valid: {template}",
                    "Verify title is not empty",
                ],
                context={
                    "request_id": request_id,
                    "title": title,
                    "template": template,
                },
            ) from e
        except Exception as e:
            create_duration = (time.time() - create_start) * 1000
            raise MCPExecutionError(
                f"Failed to create report: {e!s}",
                operation="create_report",
                original_error=e,
                hints=[
                    "Check file system permissions",
                    "Verify reports directory is writable",
                    "Check disk space availability",
                ],
                context={
                    "request_id": request_id,
                    "title": title,
                    "template": template,
                },
            ) from e

        create_duration = (time.time() - create_start) * 1000
        total_duration = (time.time() - start_time) * 1000

        logger.info(
            "create_report_completed",
            extra={
                "report_id": report_id,
                "title": title,
                "template": template,
                "request_id": request_id,
                "create_duration_ms": create_duration,
                "outline_duration_ms": outline_duration,
                "total_duration_ms": total_duration,
                "section_ids_added": section_ids_added,
                "insight_ids_added": insight_ids_added,
            },
        )

        return {
            "status": "success",
            "report_id": report_id,
            "section_ids_added": section_ids_added,
            "insight_ids_added": insight_ids_added,
            "title": title,
            "template": template,
            "tags": tags or [],
            "message": f"Created report '{title}' with ID: {report_id}",
            "request_id": request_id,
            "timing": {
                "create_duration_ms": round(create_duration, 2),
                "outline_duration_ms": round(outline_duration, 2),
                "total_duration_ms": round(total_duration, 2),
            },
        }

    def get_parameter_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Create Report Parameters",
            "type": "object",
            "additionalProperties": False,
            "required": ["title"],
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Human-readable title for the report",
                    "examples": [
                        "Q1 Revenue Analysis",
                        "Monthly Sales Report",
                        "Customer Churn Analysis",
                    ],
                },
                "template": {
                    "type": "string",
                    "description": (
                        "Report template to use. Defaults to 'default' if not specified. "
                        "Available templates: default (empty report), monthly_sales, quarterly_review, "
                        "deep_dive, analyst_v1 (blockchain analysis with citation enforcement)."
                    ),
                    "enum": [
                        "default",
                        "monthly_sales",
                        "quarterly_review",
                        "deep_dive",
                        "analyst_v1",
                    ],
                    "default": "default",
                    "examples": ["default", "monthly_sales", "deep_dive", "analyst_v1"],
                },
                "tags": {
                    "type": "array",
                    "description": "Optional tags for categorization and filtering",
                    "items": {"type": "string"},
                    "default": [],
                    "examples": [["sales", "monthly"], ["analytics", "churn"]],
                },
                "description": {
                    "type": "string",
                    "description": "Optional description of the report (stored in metadata)",
                    "examples": [
                        "Comprehensive analysis of customer retention patterns",
                        "Monthly sales performance review",
                    ],
                },
                "initial_sections": {
                    "type": "array",
                    "description": "Optional sections to seed the report (supports inline insights via 'insights')",
                    "items": {
                        "type": "object",
                        "properties": {
                            "section_id": {"type": "string"},
                            "title": {"type": "string"},
                            "order": {"type": "integer", "minimum": 0},
                            "notes": {"type": "string"},
                            "content": {"type": "string"},
                            "content_format": {
                                "type": "string",
                                "enum": ["markdown", "html", "plain"],
                                "default": "markdown",
                            },
                            "insight_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "insights": {
                                "type": "array",
                                "items": {"type": "object"},
                                "description": "Inline insights to create and link to this section",
                            },
                        },
                        "additionalProperties": True,
                    },
                },
                "request_id": {
                    "type": "string",
                    "description": "Optional request correlation ID for tracing (auto-generated if not provided)",
                },
            },
        }


__all__ = ["CreateReportTool"]
