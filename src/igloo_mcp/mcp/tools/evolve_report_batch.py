"""Evolve Report Batch MCP Tool - Atomic Multi-Operation Report Evolution.

This tool allows agents to perform multiple report evolution operations
in a single atomic transaction, reducing round-trips and ensuring consistency.

EXAMPLE USAGE:
    evolve_report_batch(
        report_selector="Q1 Revenue Report",
        instruction="Add comprehensive revenue analysis with multiple sections",
        operations=[
            {
                "type": "add_insight",
                "insight_id": "uuid-1",
                "summary": "Enterprise revenue grew 45% YoY",
                "importance": 9,
                "citations": [{"execution_id": "exec-123"}]
            },
            {
                "type": "add_insight",
                "insight_id": "uuid-2",
                "summary": "SMB segment showed 12% improvement",
                "importance": 7,
                "citations": [{"execution_id": "exec-124"}]
            },
            {
                "type": "add_section",
                "title": "Revenue Analysis",
                "order": 1,
                "insight_ids": ["uuid-1", "uuid-2"]
            },
            {
                "type": "update_section",
                "section_id": "existing-section-uuid",
                "content": "// ... keep above ...\\n\\nNew analysis paragraph.",
                "content_merge_mode": "merge"
            }
        ]
    )

SUPPORTED OPERATIONS:
- add_insight: Add a new insight
- modify_insight: Modify an existing insight
- remove_insight: Remove an insight
- add_section: Add a new section
- modify_section: Modify an existing section
- remove_section: Remove a section
- update_title: Update report title
- update_metadata: Update report metadata

All operations are validated before any are applied, ensuring atomicity.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

from igloo_mcp.config import Config
from igloo_mcp.living_reports.changes_schema import ProposedChanges
from igloo_mcp.living_reports.selector import ReportSelector, SelectorResolutionError
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.exceptions import (
    MCPSelectorError,
    MCPValidationError,
)
from igloo_mcp.mcp.tools.base import MCPTool, ensure_request_id, tool_error_handler

logger = get_logger(__name__)

# Operation type constants
OP_ADD_INSIGHT = "add_insight"
OP_MODIFY_INSIGHT = "modify_insight"
OP_REMOVE_INSIGHT = "remove_insight"
OP_ADD_SECTION = "add_section"
OP_MODIFY_SECTION = "modify_section"
OP_REMOVE_SECTION = "remove_section"
OP_UPDATE_TITLE = "update_title"
OP_UPDATE_METADATA = "update_metadata"

VALID_OPERATIONS = {
    OP_ADD_INSIGHT,
    OP_MODIFY_INSIGHT,
    OP_REMOVE_INSIGHT,
    OP_ADD_SECTION,
    OP_MODIFY_SECTION,
    OP_REMOVE_SECTION,
    OP_UPDATE_TITLE,
    OP_UPDATE_METADATA,
}


class EvolveReportBatchTool(MCPTool):
    """MCP tool for batch evolution of living reports.

    Allows multiple operations to be performed atomically, reducing
    round-trips and ensuring transactional consistency.
    """

    def __init__(self, config: Config, report_service: ReportService):
        """Initialize batch evolve report tool.

        Args:
            config: Application configuration
            report_service: Report service instance
        """
        self.config = config
        self.report_service = report_service

    @property
    def name(self) -> str:
        return "evolve_report_batch"

    @property
    def description(self) -> str:
        return (
            "Perform multiple report evolution operations atomically. "
            "Supports adding/modifying/removing insights and sections in a single call. "
            "All operations are validated before any are applied, ensuring consistency."
        )

    @property
    def category(self) -> str:
        return "reports"

    @property
    def tags(self) -> list[str]:
        return ["reports", "evolution", "batch", "atomic"]

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "report_selector": {
                    "type": "string",
                    "description": "Report ID or title to evolve",
                },
                "instruction": {
                    "type": "string",
                    "description": "Natural language description of the batch operation for audit trail",
                },
                "operations": {
                    "type": "array",
                    "description": "List of operations to perform atomically",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": list(VALID_OPERATIONS),
                                "description": "Operation type",
                            },
                        },
                        "required": ["type"],
                    },
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Validate without applying changes",
                    "default": False,
                },
                "response_detail": {
                    "type": "string",
                    "enum": ["minimal", "standard", "full"],
                    "default": "standard",
                    "description": "Response verbosity level",
                },
            },
            "required": ["report_selector", "instruction", "operations"],
        }

    @property
    def usage_examples(self) -> list[Dict[str, Any]]:
        return [
            {
                "description": "Add multiple insights and a section atomically",
                "parameters": {
                    "report_selector": "Q1 Revenue Report",
                    "instruction": "Add revenue analysis section with insights",
                    "operations": [
                        {
                            "type": "add_insight",
                            "summary": "Enterprise grew 45% YoY",
                            "importance": 9,
                            "citations": [{"execution_id": "exec-1"}],
                        },
                        {
                            "type": "add_section",
                            "title": "Revenue Analysis",
                            "order": 1,
                        },
                    ],
                },
            },
        ]

    @tool_error_handler("evolve_report_batch")
    async def execute(
        self,
        report_selector: str,
        instruction: str,
        operations: List[Dict[str, Any]],
        dry_run: bool = False,
        response_detail: str = "standard",
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute batch report evolution.

        Args:
            report_selector: Report ID or title to evolve
            instruction: Natural language description for audit trail
            operations: List of operations to perform
            dry_run: If True, validate without applying
            response_detail: Response verbosity level
            request_id: Optional request correlation ID

        Returns:
            Structured response with operation results
        """
        start_time = time.time()
        request_id = ensure_request_id(request_id)

        # Validate response_detail
        valid_levels = ("minimal", "standard", "full")
        if response_detail not in valid_levels:
            raise MCPValidationError(
                f"Invalid response_detail '{response_detail}'",
                validation_errors=[f"Must be one of: {', '.join(valid_levels)}"],
            )

        # Validate operations list
        if not operations:
            raise MCPValidationError(
                "No operations provided",
                validation_errors=["operations list cannot be empty"],
                hints=["Provide at least one operation to perform"],
            )

        # Validate each operation has a valid type
        operation_errors = []
        for i, op in enumerate(operations):
            if "type" not in op:
                operation_errors.append(f"Operation {i}: missing 'type' field")
            elif op["type"] not in VALID_OPERATIONS:
                operation_errors.append(
                    f"Operation {i}: invalid type '{op['type']}'. Must be one of: {', '.join(sorted(VALID_OPERATIONS))}"
                )

        if operation_errors:
            raise MCPValidationError(
                "Invalid operations",
                validation_errors=operation_errors,
            )

        logger.info(
            "evolve_report_batch_started",
            extra={
                "report_selector": report_selector,
                "instruction": instruction[:100] if instruction else None,
                "operation_count": len(operations),
                "dry_run": dry_run,
                "request_id": request_id,
            },
        )

        # Resolve report selector
        try:
            if getattr(self.report_service, "index", None):
                self.report_service.index.rebuild_from_filesystem()

            if hasattr(self.report_service, "resolve_report_selector"):
                report_id = self.report_service.resolve_report_selector(report_selector)
            elif getattr(self.report_service, "index", None):
                selector = ReportSelector(self.report_service.index)
                report_id = selector.resolve(report_selector, strict=False)
            else:
                report_id = report_selector
        except SelectorResolutionError as e:
            raise MCPSelectorError(
                f"Could not resolve report selector: {report_selector}",
                selector=report_selector,
                error="not_found",
            ) from e

        # Load current outline
        try:
            current_outline = self.report_service.get_report_outline(report_id)
        except ValueError as e:
            raise MCPSelectorError(
                str(e),
                selector=report_id,
                error="not_found",
            ) from e

        # Convert operations to ProposedChanges format
        proposed_changes = self._operations_to_proposed_changes(operations)

        # Create and validate ProposedChanges
        try:
            changes_obj = ProposedChanges(**proposed_changes)
        except Exception as e:
            raise MCPValidationError(
                f"Failed to parse operations: {e}",
                validation_errors=[str(e)],
            ) from e

        # Semantic validation
        semantic_errors = changes_obj.validate_against_outline(current_outline)
        if semantic_errors:
            error_strings = [err.to_string() for err in semantic_errors]
            return {
                "status": "validation_failed",
                "report_id": report_id,
                "validation_errors": error_strings,
                "operation_count": len(operations),
                "request_id": request_id,
            }

        # Dry run check
        if dry_run:
            return {
                "status": "dry_run_success",
                "report_id": report_id,
                "validation_passed": True,
                "operation_count": len(operations),
                "operations_summary": self._summarize_operations(operations),
                "request_id": request_id,
            }

        # Import and use the evolve report tool to apply changes
        from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool

        evolve_tool = EvolveReportTool(self.config, self.report_service)

        result = await evolve_tool.execute(
            report_selector=report_id,
            instruction=f"[BATCH] {instruction}",
            proposed_changes=proposed_changes,
            dry_run=False,
            response_detail=response_detail,
            request_id=request_id,
        )

        total_duration = (time.time() - start_time) * 1000

        # Enhance result with batch-specific info
        result["batch_info"] = {
            "operation_count": len(operations),
            "operations_summary": self._summarize_operations(operations),
            "total_duration_ms": round(total_duration, 2),
        }

        logger.info(
            "evolve_report_batch_completed",
            extra={
                "report_id": report_id,
                "operation_count": len(operations),
                "status": result.get("status"),
                "total_duration_ms": total_duration,
                "request_id": request_id,
            },
        )

        return result

    def _operations_to_proposed_changes(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert operations list to ProposedChanges format.

        Args:
            operations: List of operation dictionaries

        Returns:
            ProposedChanges-compatible dictionary
        """
        changes: Dict[str, Any] = {
            "insights_to_add": [],
            "insights_to_modify": [],
            "insights_to_remove": [],
            "sections_to_add": [],
            "sections_to_modify": [],
            "sections_to_remove": [],
            "title_change": None,
            "metadata_updates": {},
        }

        for op in operations:
            op_type = op.get("type")
            op_data = {k: v for k, v in op.items() if k != "type"}

            if op_type == OP_ADD_INSIGHT:
                # Auto-generate insight_id if not provided
                if "insight_id" not in op_data:
                    op_data["insight_id"] = str(uuid.uuid4())
                changes["insights_to_add"].append(op_data)

            elif op_type == OP_MODIFY_INSIGHT:
                changes["insights_to_modify"].append(op_data)

            elif op_type == OP_REMOVE_INSIGHT:
                insight_id = op_data.get("insight_id")
                if insight_id:
                    changes["insights_to_remove"].append(insight_id)

            elif op_type == OP_ADD_SECTION:
                # Auto-generate section_id if not provided
                if "section_id" not in op_data:
                    op_data["section_id"] = str(uuid.uuid4())
                changes["sections_to_add"].append(op_data)

            elif op_type == OP_MODIFY_SECTION:
                changes["sections_to_modify"].append(op_data)

            elif op_type == OP_REMOVE_SECTION:
                section_id = op_data.get("section_id")
                if section_id:
                    changes["sections_to_remove"].append(section_id)

            elif op_type == OP_UPDATE_TITLE:
                changes["title_change"] = op_data.get("title")

            elif op_type == OP_UPDATE_METADATA:
                changes["metadata_updates"].update(op_data.get("metadata", {}))

        return changes

    def _summarize_operations(self, operations: List[Dict[str, Any]]) -> Dict[str, int]:
        """Create a summary count of operations by type.

        Args:
            operations: List of operations

        Returns:
            Dictionary mapping operation type to count
        """
        summary: Dict[str, int] = {}
        for op in operations:
            op_type = op.get("type", "unknown")
            summary[op_type] = summary.get(op_type, 0) + 1
        return summary


__all__ = ["EvolveReportBatchTool"]
