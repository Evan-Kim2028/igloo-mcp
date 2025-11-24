"""Render Report MCP Tool - Convert living reports to human-readable artifacts.

This tool allows rendering living reports into high-quality outputs (HTML, PDF, etc.)
using Quarto as an optional dependency.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from igloo_mcp.config import Config
from igloo_mcp.living_reports.selector import ReportSelector, SelectorResolutionError
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.exceptions import (
    MCPExecutionError,
    MCPSelectorError,
    MCPValidationError,
)
from igloo_mcp.mcp.tools.base import MCPTool, ensure_request_id, tool_error_handler

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class RenderReportTool(MCPTool):
    """MCP tool for rendering living reports to human-readable formats."""

    def __init__(self, config: Config, report_service: ReportService):
        """Initialize render report tool.

        Args:
            config: Application configuration
            report_service: Report service instance
        """
        self.config = config
        self.report_service = report_service

    @property
    def name(self) -> str:
        return "render_report"

    @property
    def description(self) -> str:
        return (
            "Render a living report to human-readable formats (HTML, PDF, markdown, docx) using Quarto. "
            "Use this tool to generate final output from a report outline. Converts structured report data "
            "into formatted documents suitable for sharing or presentation."
        )

    @property
    def category(self) -> str:
        return "reports"

    @property
    def tags(self) -> list[str]:
        return ["reports", "rendering", "quarto", "html", "pdf", "export"]

    @property
    def usage_examples(self) -> list[Dict[str, Any]]:
        return [
            {
                "description": "Render quarterly sales report to HTML",
                "parameters": {
                    "report_selector": "Q1 Sales Report",
                    "format": "html",
                    "include_preview": True,
                },
            },
            {
                "description": "Generate PDF report with table of contents",
                "parameters": {
                    "report_selector": "rpt_550e8400e29b11d4a716446655440000",
                    "format": "pdf",
                    "options": {"toc": True, "theme": "default"},
                },
            },
            {
                "description": "Dry run - generate QMD only without rendering",
                "parameters": {
                    "report_selector": "rpt_550e8400e29b11d4a716446655440000",
                    "dry_run": True,
                },
            },
        ]

    @tool_error_handler("render_report")
    async def execute(
        self,
        report_selector: str,
        format: str = "html",
        regenerate_outline_view: bool = True,
        include_preview: bool = False,
        dry_run: bool = False,
        options: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute report rendering.

        Args:
            report_selector: Report ID or title to render
            format: Output format ('html', 'pdf', 'markdown', etc.)
            regenerate_outline_view: Whether to regenerate QMD from outline (currently ignored)
            include_preview: Whether to include truncated preview in response
            dry_run: If True, only generate QMD file without running Quarto
            options: Additional Quarto rendering options (toc, theme, etc.)
            request_id: Optional request correlation ID for tracing (auto-generated if not provided)

        Returns:
            Rendering result with status, paths, preview (if requested), warnings, and audit info

        Raises:
            MCPValidationError: If parameters are invalid
            MCPSelectorError: If report not found
            MCPExecutionError: If rendering fails
        """
        start_time = time.time()
        request_id = ensure_request_id(request_id)

        logger.info(
            "render_report_started",
            extra={
                "report_selector": report_selector,
                "format": format,
                "dry_run": dry_run,
                "request_id": request_id,
            },
        )

        # Validate format parameter
        if format not in ("html", "pdf", "markdown", "docx"):
            raise MCPValidationError(
                f"Invalid format '{format}'. Must be one of: html, pdf, markdown, docx",
                validation_errors=[f"Invalid format: {format}"],
                hints=[
                    "Use format='html' for web output",
                    "Use format='pdf' for document output",
                    "Use format='markdown' for markdown output",
                    "Use format='docx' for Word document output",
                ],
                context={"request_id": request_id, "report_selector": report_selector},
            )

        # Resolve selector first to provide better error messages
        selector_start = time.time()
        try:
            # Auto-refresh index before operations to sync with CLI-created reports
            self.report_service.index.rebuild_from_filesystem()
            selector = ReportSelector(self.report_service.index)
            resolved_report_id = selector.resolve(report_selector, strict=False)
        except SelectorResolutionError as e:
            selector_duration = (time.time() - selector_start) * 1000
            error_dict = e.to_dict()
            logger.warning(
                "render_report_selector_error",
                extra={
                    "report_selector": report_selector,
                    "error_type": error_dict.get("error"),
                    "request_id": request_id,
                    "selector_duration_ms": selector_duration,
                },
            )
            raise MCPSelectorError(
                error_dict.get(
                    "message", f"Could not resolve report selector: {report_selector}"
                ),
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

        # Note: regenerate_outline_view is currently ignored as rendering always regenerates QMD
        render_start = time.time()
        result = self.report_service.render_report(
            report_id=resolved_report_id,
            format=format,
            options=options,
            include_preview=include_preview,
            dry_run=dry_run,
        )
        render_duration = (time.time() - render_start) * 1000
        total_duration = (time.time() - start_time) * 1000

        # Check result status and convert to exceptions if needed
        status = result.get("status", "success")
        if status == "quarto_missing":
            raise MCPExecutionError(
                f"Quarto not found: {result.get('error', 'Quarto binary not available')}",
                operation="render_report",
                hints=[
                    "Install Quarto from https://quarto.org/docs/get-started/",
                    "Or set IGLOO_QUARTO_BIN environment variable to the path of quarto executable",
                    "For dry_run=True, Quarto is not required (only generates QMD file)",
                ],
                context={
                    "request_id": request_id,
                    "report_id": resolved_report_id,
                    "format": format,
                },
            )
        elif status == "validation_failed":
            validation_errors = result.get("validation_errors", [])
            raise MCPValidationError(
                f"Report validation failed: {', '.join(validation_errors)}",
                validation_errors=validation_errors,
                hints=[
                    "Fix reported validation errors using evolve_report",
                    "Check that all referenced insights and sections exist",
                    "Verify report outline structure is valid",
                ],
                context={
                    "request_id": request_id,
                    "report_id": resolved_report_id,
                },
            )
        elif status == "render_failed":
            error_msg = result.get("error", "Unknown rendering error")
            raise MCPExecutionError(
                f"Rendering failed: {error_msg}",
                operation="render_report",
                hints=[
                    "Check Quarto logs for detailed error information",
                    "Verify report content is valid",
                    "Check file system permissions and disk space",
                    "Try dry_run=True to generate QMD file without rendering",
                ],
                context={
                    "request_id": request_id,
                    "report_id": resolved_report_id,
                    "format": format,
                },
            )

        # Success - add timing and request_id to result
        result["request_id"] = request_id
        result["timing"] = {
            "selector_duration_ms": round((time.time() - selector_start) * 1000, 2),
            "render_duration_ms": round(render_duration, 2),
            "total_duration_ms": round(total_duration, 2),
        }

        logger.info(
            "render_report_completed",
            extra={
                "report_id": resolved_report_id,
                "format": format,
                "status": status,
                "request_id": request_id,
                "render_duration_ms": render_duration,
                "total_duration_ms": total_duration,
            },
        )

        return result

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Render Report Parameters",
            "type": "object",
            "additionalProperties": False,
            "required": ["report_selector"],
            "properties": {
                "report_selector": {
                    "type": "string",
                    "description": "Report ID (e.g., 'rpt_550e8400e29b11d4a716446655440000') or title to render",
                    "examples": [
                        "Q1 Revenue Report",
                        "rpt_550e8400e29b11d4a716446655440000",
                    ],
                },
                "format": {
                    "type": "string",
                    "description": "Output format for rendering",
                    "enum": ["html", "pdf", "markdown", "docx"],
                    "default": "html",
                    "examples": ["html", "pdf", "markdown"],
                },
                "regenerate_outline_view": {
                    "type": "boolean",
                    "description": "Whether to regenerate QMD from outline (currently always true)",
                    "default": True,
                },
                "include_preview": {
                    "type": "boolean",
                    "description": "Include truncated preview of rendered content in response",
                    "default": False,
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If True, only generate QMD file without running Quarto",
                    "default": False,
                },
                "options": {
                    "type": "object",
                    "description": "Additional Quarto rendering options",
                    "properties": {
                        "toc": {
                            "type": "boolean",
                            "description": "Include table of contents",
                            "default": False,
                        },
                        "code_folding": {
                            "type": "boolean",
                            "description": "Enable code folding in HTML output",
                            "default": False,
                        },
                        "theme": {
                            "type": "string",
                            "description": "HTML theme (e.g., 'default', 'cerulean', 'cosmo')",
                            "examples": ["default", "cerulean", "cosmo"],
                        },
                    },
                    "additionalProperties": True,
                },
                "request_id": {
                    "type": "string",
                    "description": "Optional request correlation ID for tracing (auto-generated if not provided)",
                },
            },
        }


__all__ = ["RenderReportTool"]
