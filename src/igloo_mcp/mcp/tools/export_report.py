"""Export Report MCP Tool - Package living reports into portable ZIP bundles."""

from __future__ import annotations

import time
from typing import Any

from igloo_mcp.config import Config
from igloo_mcp.living_reports.selector import ReportSelector, SelectorResolutionError
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.compat import get_logger
from igloo_mcp.mcp.exceptions import MCPExecutionError, MCPSelectorError, MCPValidationError
from igloo_mcp.mcp.tools.base import MCPTool, ensure_request_id, tool_error_handler
from igloo_mcp.mcp.validation_helpers import validate_text_field

logger = get_logger(__name__)


class ExportReportTool(MCPTool):
    """MCP tool for exporting living reports as portable ZIP bundles."""

    def __init__(self, config: Config, report_service: ReportService):
        self.config = config
        self.report_service = report_service

    @property
    def name(self) -> str:
        return "export_report"

    @property
    def description(self) -> str:
        return "Export a living report as a ZIP bundle with outline, audit log, and optional assets."

    @property
    def category(self) -> str:
        return "reports"

    @property
    def tags(self) -> list[str]:
        return ["reports", "export", "backup", "bundle"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
        return [
            {
                "description": "Export a report with its audit log and bundled assets",
                "parameters": {
                    "report_selector": "Q1 Revenue Analysis",
                },
            },
            {
                "description": "Export to a specific ZIP path",
                "parameters": {
                    "report_selector": "rpt_550e8400e29b11d4a716446655440000",
                    "output_path": "./artifacts/reports/q1-revenue.zip",
                },
            },
            {
                "description": "Create a minimal bundle without audit history or assets",
                "parameters": {
                    "report_selector": "Q1 Revenue Analysis",
                    "include_audit": False,
                    "include_assets": False,
                },
            },
        ]

    @tool_error_handler("export_report")
    async def execute(
        self,
        report_selector: str,
        output_path: str | None = None,
        include_audit: bool = True,
        include_assets: bool = True,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Export a living report as a portable ZIP bundle."""
        start_time = time.time()
        request_id = ensure_request_id(request_id)

        validate_text_field(
            value=report_selector,
            field_name="report_selector",
            min_length=1,
            max_length=255,
            allow_empty=False,
        )
        if output_path is not None:
            validate_text_field(
                value=output_path,
                field_name="output_path",
                min_length=1,
                max_length=4096,
                allow_empty=False,
            )

        logger.info(
            "export_report_started",
            extra={
                "report_selector": report_selector,
                "output_path": output_path,
                "include_audit": include_audit,
                "include_assets": include_assets,
                "request_id": request_id,
            },
        )

        selector_start = time.time()
        try:
            self.report_service.index.rebuild_from_filesystem()
            selector = ReportSelector(self.report_service.index)
            resolved_report_id = selector.resolve(report_selector, strict=False)
        except SelectorResolutionError as e:
            selector_duration = (time.time() - selector_start) * 1000
            error_dict = e.to_dict()
            logger.warning(
                "export_report_selector_error",
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

        export_start = time.time()
        try:
            result = self.report_service.export_report(
                report_id=resolved_report_id,
                output_path=output_path,
                include_audit=include_audit,
                include_assets=include_assets,
                actor="agent",
            )
        except ValueError as e:
            raise MCPValidationError(
                f"Report export failed: {e!s}",
                validation_errors=[str(e)],
                hints=[
                    "Verify the report exists and can be resolved by ID or title",
                    "Use search_report to list available reports",
                ],
                context={"request_id": request_id, "report_selector": report_selector},
            ) from e
        except OSError as e:
            raise MCPExecutionError(
                f"Failed to write export bundle: {e!s}",
                operation="export_report",
                original_error=e,
                hints=[
                    "Check that the destination directory exists or can be created",
                    "Verify file system permissions for the output path",
                    "Check available disk space",
                ],
                context={"request_id": request_id, "report_id": resolved_report_id},
            ) from e
        except Exception as e:
            raise MCPExecutionError(
                f"Failed to export report: {e!s}",
                operation="export_report",
                original_error=e,
                hints=[
                    "Verify the report files are readable",
                    "Check that the report storage directory is intact",
                ],
                context={"request_id": request_id, "report_id": resolved_report_id},
            ) from e

        result["request_id"] = request_id
        result["timing"] = {
            "selector_duration_ms": round((time.time() - selector_start) * 1000, 2),
            "export_duration_ms": round((time.time() - export_start) * 1000, 2),
            "total_duration_ms": round((time.time() - start_time) * 1000, 2),
        }
        return result

    def get_parameter_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Export Report Parameters",
            "type": "object",
            "additionalProperties": False,
            "required": ["report_selector"],
            "properties": {
                "report_selector": {
                    "type": "string",
                    "description": "Report ID or title to export as a portable ZIP bundle.",
                    "examples": [
                        "Q1 Revenue Analysis",
                        "rpt_550e8400e29b11d4a716446655440000",
                    ],
                },
                "output_path": {
                    "type": "string",
                    "description": (
                        "Optional destination ZIP path. If an existing directory is provided, "
                        "the bundle is written there as <report_id>.zip."
                    ),
                    "examples": [
                        "./artifacts/reports/q1-revenue.zip",
                        "./exports",
                    ],
                },
                "include_audit": {
                    "type": "boolean",
                    "description": "Include the report's audit.jsonl history in the bundle.",
                    "default": True,
                },
                "include_assets": {
                    "type": "boolean",
                    "description": "Include files under report_files/ in the bundle.",
                    "default": True,
                },
                "request_id": {
                    "type": "string",
                    "description": "Optional request correlation ID for tracing and logs.",
                    "examples": ["req_export_123"],
                },
            },
        }
