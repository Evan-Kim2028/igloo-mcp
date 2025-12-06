"""Render Report MCP Tool - Convert living reports to human-readable artifacts.

This tool allows rendering living reports into high-quality outputs (HTML, PDF, etc.)
using Quarto as an optional dependency.
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
            "Export a report to shareable formats (HTML, PDF, Markdown)—the 'finals week study guide'. "
            "Use AFTER report is complete and reviewed. "
            "Use dry_run=True to preview, include_preview=True for inline content sampling."
        )

    @property
    def category(self) -> str:
        return "reports"

    @property
    def tags(self) -> list[str]:
        return ["reports", "rendering", "quarto", "html", "pdf", "export"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
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
        preview_max_chars: int = 2000,
        dry_run: bool = False,
        options: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute report rendering.

        Args:
            report_selector: Report ID or title to render
            format: Output format ('html', 'pdf', 'markdown', etc.)
            regenerate_outline_view: Whether to regenerate QMD from outline (currently ignored)
            include_preview: Whether to include truncated preview in response
            preview_max_chars: Maximum characters for preview truncation (default 2000)
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
        valid_formats = ("html", "pdf", "markdown", "docx", "html_standalone")
        if format not in valid_formats:
            raise MCPValidationError(
                f"Invalid format '{format}'. Must be one of: {', '.join(valid_formats)}",
                validation_errors=[f"Invalid format: {format}"],
                hints=[
                    "Use format='html' for Quarto HTML output",
                    "Use format='html_standalone' for single self-contained HTML (no Quarto required)",
                    "Use format='pdf' for PDF document output",
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

        # Note: regenerate_outline_view is currently ignored as rendering always regenerates QMD
        render_start = time.time()

        # Handle html_standalone separately - doesn't require Quarto
        if format == "html_standalone":
            result = self._render_standalone_html(
                report_id=resolved_report_id,
                options=options or {},
                include_preview=include_preview,
                preview_max_chars=preview_max_chars,
            )
        elif format == "markdown":
            result = self._render_markdown(
                report_id=resolved_report_id,
                options=options or {},
                include_preview=include_preview,
                preview_max_chars=preview_max_chars,
            )
        else:
            result = self.report_service.render_report(
                report_id=resolved_report_id,
                format=format,
                options=options,
                include_preview=include_preview,
                preview_max_chars=preview_max_chars,
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
        if status == "validation_failed":
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
        if status == "render_failed":
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

    def get_parameter_schema(self) -> dict[str, Any]:
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
                    "enum": ["html", "pdf", "markdown", "docx", "html_standalone"],
                    "default": "html",
                    "examples": ["html", "pdf", "markdown", "html_standalone"],
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
                    "description": "Rendering options (format-specific)",
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
                        "style_preset": {
                            "type": "string",
                            "description": "Standalone HTML style preset (compact, professional, wide, print).",
                            "enum": ["compact", "default", "professional", "wide", "print"],
                            "default": "professional",
                        },
                        "css_options": {
                            "type": "object",
                            "description": "Fine-grained CSS overrides for html_standalone rendering.",
                            "properties": {
                                "max_width": {"type": "string", "description": "Body max-width (e.g., '1400px')."},
                                "body_padding": {"type": "string", "description": "Body padding (CSS shorthand)."},
                                "line_height": {"type": "number", "description": "Body line-height."},
                                "paragraph_spacing": {"type": "string", "description": "Spacing between paragraphs."},
                                "list_indent": {"type": "string", "description": "Indent for lists."},
                                "table_cell_padding": {"type": "string", "description": "Padding for table cells."},
                                "font_family": {"type": "string", "description": "Body font stack."},
                                "heading_color": {"type": "string", "description": "Color for section headings."},
                            },
                            "additionalProperties": False,
                        },
                        "custom_css": {
                            "type": "string",
                            "description": "Raw CSS appended to the standalone HTML stylesheet.",
                        },
                        "include_frontmatter": {
                            "type": "boolean",
                            "description": "Include YAML frontmatter for static site generators (markdown format).",
                            "default": True,
                        },
                        "include_toc": {
                            "type": "boolean",
                            "description": "Include table of contents in markdown output.",
                            "default": True,
                        },
                        "image_mode": {
                            "type": "string",
                            "description": "How to handle images in markdown: 'relative' (copy to images/), 'base64' (embed), 'absolute' (keep paths).",
                            "enum": ["relative", "base64", "absolute"],
                            "default": "relative",
                        },
                        "platform": {
                            "type": "string",
                            "description": "Target platform for markdown output.",
                            "enum": ["github", "gitlab", "generic"],
                            "default": "generic",
                        },
                        "output_filename": {
                            "type": "string",
                            "description": "Output filename for markdown (default: 'report.md').",
                            "default": "report.md",
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

    def _render_standalone_html(
        self,
        report_id: str,
        options: dict[str, Any],
        include_preview: bool = False,
        preview_max_chars: int = 2000,
    ) -> dict[str, Any]:
        """Render report to standalone HTML without Quarto.

        Args:
            report_id: Report ID to render
            options: Rendering options (theme, toc, etc.)
            include_preview: Include truncated preview in response
            preview_max_chars: Maximum characters for preview

        Returns:
            Rendering result dictionary
        """
        from igloo_mcp.living_reports.renderers import HTMLStandaloneRenderer

        try:
            # Load outline and prepare data
            outline = self.report_service.get_report_outline(report_id)
            outline = self.report_service._prepare_outline_for_render(outline)
            storage = self.report_service.global_storage.get_report_storage(report_id)
            report_dir = storage.report_dir

            # Build hints (citation_map, query_provenance)
            hints: dict[str, Any] = {}
            try:
                citation_map = self.report_service._build_citation_map(outline)
                hints["citation_map"] = citation_map

                # Build citation_details from query provenance using batch lookup
                query_provenance: dict[str, Any] = {}

                # Collect all execution_ids first for batch lookup
                execution_ids_to_resolve: list[str] = []
                for insight in outline.insights:
                    references = insight.citations or insight.supporting_queries
                    for query in references:
                        if query.execution_id:
                            execution_ids_to_resolve.append(query.execution_id)

                # Batch lookup - single operation instead of N individual lookups
                history_records = self.report_service.history_index.get_records_batch(execution_ids_to_resolve)

                # Build provenance from batch results
                for exec_id, history_record in history_records.items():
                    query_provenance[exec_id] = {
                        "execution_id": exec_id,
                        "timestamp": history_record.get("timestamp") or history_record.get("ts"),
                        "duration_ms": history_record.get("duration_ms"),
                        "rowcount": history_record.get("rowcount"),
                        "status": history_record.get("status"),
                        "statement_preview": history_record.get("statement_preview"),
                    }

                hints["query_provenance"] = query_provenance
                hints["citation_details"] = query_provenance
            except Exception:
                pass

            # Render using standalone renderer
            renderer = HTMLStandaloneRenderer()
            render_result = renderer.render(
                report_dir=report_dir,
                outline=outline,
                datasets={},
                hints=hints,
                options=options,
            )

            # Build response
            result: dict[str, Any] = {
                "status": "success",
                "report_id": report_id,
                "output": {
                    "format": "html_standalone",
                    "output_path": render_result["output_path"],
                    "size_bytes": render_result["size_bytes"],
                },
                "warnings": render_result.get("warnings", []),
            }

            # Include preview if requested
            if include_preview:
                try:
                    from pathlib import Path

                    output_path = Path(render_result["output_path"])
                    if output_path.exists():
                        content = output_path.read_text(encoding="utf-8")
                        if len(content) > preview_max_chars:
                            content = content[:preview_max_chars] + "\n\n[Content truncated]"
                        result["preview"] = content
                        result["output"]["preview"] = content
                except Exception:
                    pass

            return result

        except Exception as e:
            return {
                "status": "render_failed",
                "report_id": report_id,
                "error": str(e),
            }

    def _render_markdown(
        self,
        report_id: str,
        options: dict[str, Any],
        include_preview: bool = False,
        preview_max_chars: int = 2000,
    ) -> dict[str, Any]:
        """Render report to Markdown format for GitHub/GitLab publishing.

        Args:
            report_id: Report ID to render
            options: Rendering options:
                - include_frontmatter: bool (default: True)
                - include_toc: bool (default: True)
                - image_mode: 'relative' | 'base64' | 'absolute' (default: 'relative')
                - platform: 'github' | 'gitlab' | 'generic' (default: 'generic')
                - output_filename: str (default: 'report.md')
            include_preview: Include truncated preview in response
            preview_max_chars: Maximum characters for preview

        Returns:
            Rendering result dictionary
        """
        from igloo_mcp.living_reports.renderers import MarkdownRenderer

        try:
            # Load outline and prepare data
            outline = self.report_service.get_report_outline(report_id)
            outline = self.report_service._prepare_outline_for_render(outline)
            storage = self.report_service.global_storage.get_report_storage(report_id)
            report_dir = storage.report_dir

            # Build hints (citation_map, query_provenance)
            hints: dict[str, Any] = {}
            try:
                citation_map = self.report_service._build_citation_map(outline)
                hints["citation_map"] = citation_map

                # Build citation_details from query provenance using batch lookup
                query_provenance: dict[str, Any] = {}

                # Collect all execution_ids first for batch lookup
                execution_ids_to_resolve: list[str] = []
                for insight in outline.insights:
                    references = insight.citations or insight.supporting_queries
                    for query in references:
                        if query.execution_id:
                            execution_ids_to_resolve.append(query.execution_id)

                # Batch lookup - single operation instead of N individual lookups
                history_records = self.report_service.history_index.get_records_batch(execution_ids_to_resolve)

                # Build provenance from batch results
                for exec_id, history_record in history_records.items():
                    query_provenance[exec_id] = {
                        "execution_id": exec_id,
                        "timestamp": history_record.get("timestamp") or history_record.get("ts"),
                        "duration_ms": history_record.get("duration_ms"),
                        "rowcount": history_record.get("rowcount"),
                        "status": history_record.get("status"),
                        "statement_preview": history_record.get("statement_preview"),
                    }

                hints["query_provenance"] = query_provenance
                hints["citation_details"] = query_provenance
            except Exception:
                pass

            # Render using markdown renderer
            renderer = MarkdownRenderer()
            render_result = renderer.render(
                report_dir=report_dir,
                outline=outline,
                datasets={},
                hints=hints,
                options=options,
            )

            # Build response
            result: dict[str, Any] = {
                "status": "success",
                "report_id": report_id,
                "output": {
                    "format": "markdown",
                    "output_path": render_result["output_path"],
                    "size_bytes": render_result["size_bytes"],
                    "images_copied": render_result.get("images_copied", 0),
                },
                "warnings": render_result.get("warnings", []),
            }

            # Include preview if requested
            if include_preview:
                try:
                    from pathlib import Path

                    output_path = Path(render_result["output_path"])
                    if output_path.exists():
                        content = output_path.read_text(encoding="utf-8")
                        if len(content) > preview_max_chars:
                            content = content[:preview_max_chars] + "\n\n[Content truncated]"
                        result["preview"] = content
                        result["output"]["preview"] = content
                except Exception:
                    pass

            return result

        except Exception as e:
            return {
                "status": "render_failed",
                "report_id": report_id,
                "error": str(e),
            }


__all__ = ["RenderReportTool"]
