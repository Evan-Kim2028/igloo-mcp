"""Evolve Report MCP Tool - LLM-Agnostic Report Evolution Framework

This tool provides a framework for LLMs to evolve living reports. The LLM is responsible
for analyzing the current report outline and generating structured changes.

TYPICAL LLM WORKFLOW:
1. LLM calls evolve_report with instruction="Add revenue insights" and dry_run=True
2. Tool returns current outline structure and validation that changes are feasible
3. LLM analyzes outline and generates ProposedChanges object
4. LLM calls evolve_report again with proposed_changes and dry_run=False
5. Tool validates, applies changes, and returns success

EXAMPLE FLOW:
Step 1 - LLM discovers report structure:
    evolve_report(
        report_selector="Q1 Revenue Report",
        instruction="Add insights about top revenue drivers",
        proposed_changes={},  # Empty to trigger structure discovery
        dry_run=True
    )

Step 2 - LLM generates and applies changes:
    evolve_report(
        report_selector="Q1 Revenue Report",
        instruction="Add insights about top revenue drivers",
        proposed_changes={
            "insights_to_add": [{
                "insight_id": "insight_uuid_123",
                "summary": "Enterprise segment drove 45% YoY growth",
                "importance": 9,
                "supporting_queries": [...]
            }],
            "sections_to_modify": [{
                "section_id": "revenue_overview",
                "insight_ids_to_add": ["insight_uuid_123"]
            }]
        },
        dry_run=False
    )

This design keeps the tool LLM-agnostic - works with any MCP client (Claude, GPT, local models).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

from igloo_mcp.config import Config
from igloo_mcp.living_reports.changes_schema import ProposedChanges
from igloo_mcp.living_reports.models import Insight, Outline, Section
from igloo_mcp.living_reports.selector import ReportSelector, SelectorResolutionError
from igloo_mcp.living_reports.service import ReportService
from igloo_mcp.mcp.error_utils import wrap_validation_error
from igloo_mcp.mcp.exceptions import (
    MCPExecutionError,
    MCPSelectorError,
    MCPValidationError,
)
from igloo_mcp.mcp.tools.base import MCPTool, ensure_request_id, tool_error_handler

logger = get_logger(__name__)


class EvolveReportTool(MCPTool):
    """MCP tool for evolving living reports through LLM assistance.

    This tool allows agents to evolve reports by either:
    1. Providing an instruction and letting the tool generate changes (fallback)
    2. Providing explicit structured proposed_changes (preferred for agents)
    """

    def __init__(self, config: Config, report_service: ReportService):
        """Initialize evolve report tool.

        Args:
            config: Application configuration
            report_service: Report service instance
        """
        self.config = config
        self.report_service = report_service

    @property
    def name(self) -> str:
        return "evolve_report"

    @property
    def description(self) -> str:
        return (
            "Evolve a living report with LLM assistance. "
            "Use this tool to add insights, modify sections, or restructure an existing report. "
            "Requires structured changes describing what to add, modify, or remove from the report outline."
        )

    @property
    def category(self) -> str:
        return "reports"

    @property
    def tags(self) -> list[str]:
        return ["reports", "evolution", "llm", "structured-edits"]

    @property
    def usage_examples(self) -> list[Dict[str, Any]]:
        return [
            {
                "description": "Add revenue insights with explicit changes",
                "parameters": {
                    "report_selector": "Q1 Revenue Report",
                    "instruction": "Add insights about top revenue drivers",
                    "proposed_changes": {
                        "insights_to_add": [
                            {
                                "insight_id": str(uuid.uuid4()),
                                "summary": "30-day retention improved 15% QoQ",
                                "importance": 8,
                                "supporting_queries": [],
                            }
                        ]
                    },
                },
            },
            {
                "description": "Batch operation: Add multiple insights and link to sections",
                "parameters": {
                    "report_selector": "Q1 Revenue Report",
                    "instruction": "Add comprehensive revenue analysis",
                    "proposed_changes": {
                        "insights_to_add": [
                            {
                                "insight_id": str(uuid.uuid4()),
                                "summary": "Enterprise segment drove 45% YoY growth",
                                "importance": 9,
                                "supporting_queries": [],
                            },
                            {
                                "insight_id": str(uuid.uuid4()),
                                "summary": "SMB retention improved 12%",
                                "importance": 7,
                                "supporting_queries": [],
                            },
                        ],
                        "sections_to_modify": [
                            {
                                "section_id": "revenue_overview",
                                "insight_ids_to_add": [
                                    "<insight_id_1>",
                                    "<insight_id_2>",
                                ],
                            }
                        ],
                    },
                },
            },
            {
                "description": "Dry run to preview changes before applying",
                "parameters": {
                    "report_selector": "rpt_550e8400e29b11d4a716446655440000",
                    "instruction": "Prioritize customer retention metrics over acquisition",
                    "proposed_changes": {
                        "insights_to_add": [
                            {
                                "insight_id": str(uuid.uuid4()),
                                "summary": "Test",
                                "importance": 5,
                            }
                        ]
                    },
                    "dry_run": True,
                },
            },
        ]

    @tool_error_handler("evolve_report")
    async def execute(
        self,
        report_selector: str,
        instruction: str,
        proposed_changes: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute report evolution with structured error handling.

        Args:
            report_selector: Report ID or title to evolve
            instruction: Natural language instruction describing desired evolution
            proposed_changes: Structured changes to apply
            constraints: Optional constraints on evolution
            dry_run: If True, validate without applying changes
            request_id: Optional request correlation ID for tracing

        Returns:
            Structured response with one of these statuses:
            - "success": Changes applied successfully
            - "dry_run_success": Validation passed (dry run)
            - "validation_failed": Schema/semantic validation errors
            - "selector_error": Could not resolve report selector
            - "error": Unexpected error
        """
        start_time = time.time()
        request_id = ensure_request_id(request_id)

        changes_count = (
            len(proposed_changes.get("insights_to_add", []))
            + len(proposed_changes.get("sections_to_add", []))
            + len(proposed_changes.get("insights_to_modify", []))
            + len(proposed_changes.get("sections_to_modify", []))
        )

        try:
            logger.info(
                "evolve_report_started",
                extra={
                    "report_selector": report_selector,
                    "instruction": instruction[:100] if instruction else None,
                    "dry_run": dry_run,
                    "changes_count": changes_count,
                    "request_id": request_id,
                },
            )

            # Auto-refresh index before operations to sync with CLI-created reports
            selector_start = time.time()
            self.report_service.index.rebuild_from_filesystem()

            # Step 1: Resolve selector with explicit error handling
            selector = ReportSelector(self.report_service.index)
            try:
                report_id = selector.resolve(report_selector, strict=False)
            except SelectorResolutionError as e:
                selector_duration = (time.time() - selector_start) * 1000
                error_dict = e.to_dict()
                logger.warning(
                    "evolve_report_selector_error",
                    extra={
                        "report_selector": report_selector,
                        "error_type": error_dict.get("error"),
                        "request_id": request_id,
                        "selector_duration_ms": selector_duration,
                    },
                )
                raise MCPSelectorError(
                    error_dict.get(
                        "message",
                        f"Could not resolve report selector: {report_selector}",
                    ),
                    selector=report_selector,
                    error=error_dict.get("error", "not_found"),
                    candidates=error_dict.get("candidates", []),
                ) from e

            # Step 2: Load current outline
            outline_start = time.time()
            try:
                current_outline = self.report_service.get_report_outline(report_id)
            except ValueError as e:
                outline_duration = (time.time() - outline_start) * 1000
                logger.error(
                    "evolve_report_outline_load_failed",
                    extra={
                        "report_id": report_id,
                        "error": str(e),
                        "request_id": request_id,
                        "outline_duration_ms": outline_duration,
                    },
                )
                raise MCPExecutionError(
                    f"Failed to load report outline: {str(e)}",
                    operation="evolve_report",
                    hints=["Verify the report exists and is accessible"],
                ) from e

            # Step 3: Parse and validate proposed changes
            validation_start = time.time()
            try:
                changes_obj = ProposedChanges(**proposed_changes)
            except ValidationError as e:
                validation_duration = (time.time() - validation_start) * 1000
                error_details = self._format_validation_errors(e.errors())
                logger.warning(
                    "evolve_report_schema_validation_failed",
                    extra={
                        "report_id": report_id,
                        "validation_errors": error_details,
                        "request_id": request_id,
                        "validation_duration_ms": validation_duration,
                    },
                )
                raise MCPValidationError(
                    "Schema validation failed for proposed changes",
                    validation_errors=error_details["errors"],
                    hints=error_details["hints"],
                ) from e

            # Semantic validation
            semantic_errors = changes_obj.validate_against_outline(current_outline)
            if semantic_errors:
                validation_duration = (time.time() - validation_start) * 1000

                # Format structured errors for logging and response
                error_strings = [err.to_string() for err in semantic_errors]
                error_details = [
                    {
                        "field": err.field,
                        "value": err.value,
                        "error": err.error,
                        "available_ids": err.available_ids,
                    }
                    for err in semantic_errors
                ]

                logger.warning(
                    "evolve_report_semantic_validation_failed",
                    extra={
                        "report_id": report_id,
                        "semantic_errors": error_strings,
                        "semantic_errors_structured": error_details,
                        "request_id": request_id,
                        "validation_duration_ms": validation_duration,
                    },
                )
                raise MCPValidationError(
                    "Semantic validation failed for proposed changes",
                    validation_errors=error_strings,  # Backward compatible string format
                    hints=[
                        "Check that all referenced insight and section IDs exist in the current outline"
                    ],
                    context={
                        "structured_errors": error_details
                    },  # Include structured format in context
                )

            # Calculate warnings (non-blocking)
            warnings = self._calculate_warnings(current_outline, changes_obj)

            # Step 4: Dry run check
            if dry_run or (constraints and constraints.get("dry_run")):
                validation_duration = (time.time() - validation_start) * 1000
                total_duration = (time.time() - start_time) * 1000

                # Calculate preview
                preview = self._calculate_preview(changes_obj, current_outline)

                logger.info(
                    "evolve_report_dry_run_success",
                    extra={
                        "report_id": report_id,
                        "validation_passed": True,
                        "preview": preview,
                        "request_id": request_id,
                        "validation_duration_ms": validation_duration,
                        "total_duration_ms": total_duration,
                    },
                )

                return {
                    "status": "dry_run_success",
                    "report_id": report_id,
                    "current_outline": {
                        "sections": [s.model_dump() for s in current_outline.sections],
                        "insights": [i.model_dump() for i in current_outline.insights],
                        "outline_version": current_outline.outline_version,
                    },
                    "proposed_changes": changes_obj.model_dump(),
                    "preview": preview,
                    "warnings": warnings,
                    "validation_passed": True,
                    "request_id": request_id,
                }

            # Step 5: Apply changes
            apply_start = time.time()
            try:
                new_outline = self._apply_changes(
                    current_outline, changes_obj.model_dump()
                )
            except Exception as e:
                apply_duration = (time.time() - apply_start) * 1000
                logger.error(
                    "evolve_report_apply_failed",
                    extra={
                        "report_id": report_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "request_id": request_id,
                        "apply_duration_ms": apply_duration,
                    },
                    exc_info=True,
                )
                raise MCPExecutionError(
                    f"Failed to apply changes to report: {str(e)}",
                    operation="evolve_report",
                    hints=["Check logs for detailed error information"],
                ) from e

            # Step 6: Save with atomic write
            storage_start = time.time()
            try:
                self.report_service.update_report_outline(
                    report_id, new_outline, actor="agent", request_id=request_id
                )
            except Exception as e:
                storage_duration = (time.time() - storage_start) * 1000
                logger.error(
                    "evolve_report_storage_failed",
                    extra={
                        "report_id": report_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "request_id": request_id,
                        "storage_duration_ms": storage_duration,
                    },
                    exc_info=True,
                )
                raise MCPExecutionError(
                    f"Failed to save report changes: {str(e)}",
                    operation="evolve_report",
                    hints=["Check file system permissions and disk space"],
                ) from e

            # Auto-refresh index after successful changes to ensure consistency
            self.report_service.index.rebuild_from_filesystem()

            apply_duration = (time.time() - apply_start) * 1000
            storage_duration = (time.time() - storage_start) * 1000
            total_duration = (time.time() - start_time) * 1000

            # Calculate summary
            # Note: UUIDs are auto-generated by model_validator if not provided, so all IDs should be present
            summary = {
                "sections_added": len(changes_obj.sections_to_add),
                "insights_added": len(changes_obj.insights_to_add),
                "sections_modified": len(changes_obj.sections_to_modify),
                "insights_modified": len(changes_obj.insights_to_modify),
                "sections_removed": len(changes_obj.sections_to_remove),
                "insights_removed": len(changes_obj.insights_to_remove),
                "insight_ids_added": [
                    c.insight_id for c in changes_obj.insights_to_add if c.insight_id
                ],
                "section_ids_added": [
                    c.section_id for c in changes_obj.sections_to_add if c.section_id
                ],
                "insight_ids_modified": [
                    c.insight_id for c in changes_obj.insights_to_modify if c.insight_id
                ],
                "section_ids_modified": [
                    c.section_id for c in changes_obj.sections_to_modify if c.section_id
                ],
            }

            logger.info(
                "evolve_report_completed",
                extra={
                    "report_id": report_id,
                    "outline_version": new_outline.outline_version,
                    "summary": summary,
                    "warnings": warnings,
                    "request_id": request_id,
                    "apply_duration_ms": apply_duration,
                    "storage_duration_ms": storage_duration,
                    "total_duration_ms": total_duration,
                },
            )

            return {
                "status": "success",
                "report_id": report_id,
                "changes_applied": changes_obj.model_dump(),
                "outline_version": int(
                    new_outline.outline_version
                ),  # Ensure integer type
                "summary": summary,
                "warnings": warnings,
                "request_id": request_id,
                "timing": {
                    "apply_duration_ms": round(apply_duration, 2),
                    "storage_duration_ms": round(storage_duration, 2),
                    "total_duration_ms": round(total_duration, 2),
                },
            }

        except Exception:
            # Re-raise to let @tool_error_handler decorator handle it
            raise
        # Note: The @tool_error_handler decorator will catch all unhandled exceptions
        # and format them appropriately, so we don't need a catch-all here

    def _validate_changes(
        self, current_outline: Outline, changes: Dict[str, Any]
    ) -> List[str]:
        """Validate proposed changes against safety constraints.

        Args:
            current_outline: Current outline
            changes: Proposed changes

        Returns:
            List of validation error messages
        """
        issues = []

        # Check for invalid insight IDs
        existing_insight_ids = {i.insight_id for i in current_outline.insights}

        for insight_data in changes.get("insights_to_add", []):
            insight_id = insight_data.get("insight_id")
            if insight_id in existing_insight_ids:
                issues.append(f"Insight ID already exists: {insight_id}")

        for modify_data in changes.get("insights_to_modify", []):
            insight_id = modify_data.get("insight_id")
            if insight_id not in existing_insight_ids:
                issues.append(f"Insight ID not found: {insight_id}")

        for insight_id in changes.get("insights_to_remove", []):
            if insight_id not in existing_insight_ids:
                issues.append(f"Insight ID not found for removal: {insight_id}")

        # Check for invalid section IDs
        existing_section_ids = {s.section_id for s in current_outline.sections}

        for section_data in changes.get("sections_to_add", []):
            section_id = section_data.get("section_id")
            if section_id in existing_section_ids:
                issues.append(f"Section ID already exists: {section_id}")

        for modify_data in changes.get("sections_to_modify", []):
            section_id = modify_data.get("section_id")
            if section_id not in existing_section_ids:
                issues.append(f"Section ID not found: {section_id}")

        for section_id in changes.get("sections_to_remove", []):
            if section_id not in existing_section_ids:
                issues.append(f"Section ID not found for removal: {section_id}")

        # Citation enforcement for analyst reports
        if current_outline.metadata.get("template") == "analyst_v1":
            # Validate insights_to_add
            for insight_data in changes.get("insights_to_add", []):
                insight_id = insight_data.get("insight_id", "unknown")
                supporting_queries = insight_data.get("supporting_queries", [])

                if not supporting_queries or len(supporting_queries) == 0:
                    issues.append(
                        f"Analyst reports require citations. Insight '{insight_id}' missing supporting_queries[0] with execution_id. "
                        "Use execute_query() first to get an execution_id, then include it in supporting_queries"
                    )
                elif not supporting_queries[0].get("execution_id"):
                    issues.append(
                        f"Analyst reports require citations. Insight '{insight_id}' missing execution_id in supporting_queries[0]. "
                        "Use execute_query() first to get an execution_id, then include it in supporting_queries"
                    )

            # Validate insights_to_modify
            for modify_data in changes.get("insights_to_modify", []):
                insight_id = modify_data.get("insight_id")
                if insight_id not in existing_insight_ids:
                    continue  # Already handled above

                # Get current insight to check if supporting_queries is being modified
                current_insight = None
                for insight in current_outline.insights:
                    if insight.insight_id == insight_id:
                        current_insight = insight
                        break

                if current_insight:
                    # Check if supporting_queries is being modified
                    if "supporting_queries" in modify_data:
                        supporting_queries = modify_data.get("supporting_queries", [])
                        if not supporting_queries or len(supporting_queries) == 0:
                            issues.append(
                                f"Analyst reports require citations. Insight '{insight_id}' missing supporting_queries[0] with execution_id. "
                                "Use execute_query() first to get an execution_id, then include it in supporting_queries"
                            )
                        elif not supporting_queries[0].get("execution_id"):
                            issues.append(
                                f"Analyst reports require citations. Insight '{insight_id}' missing execution_id in supporting_queries[0]. "
                                "Use execute_query() first to get an execution_id, then include it in supporting_queries"
                            )
                    # If not modifying supporting_queries, check current value
                    elif (
                        not current_insight.supporting_queries
                        or len(current_insight.supporting_queries) == 0
                    ):
                        issues.append(
                            f"Analyst reports require citations. Insight '{insight_id}' missing supporting_queries[0] with execution_id. "
                            "Use execute_query() first to get an execution_id, then include it in supporting_queries"
                        )
                    elif not current_insight.supporting_queries[0].execution_id:
                        issues.append(
                            f"Analyst reports require citations. Insight '{insight_id}' missing execution_id in supporting_queries[0]. "
                            "Use execute_query() first to get an execution_id, then include it in supporting_queries"
                        )

        return issues

    def _apply_changes(
        self, current_outline: Outline, changes: Dict[str, Any]
    ) -> Outline:
        """Apply validated changes to create new outline.

        Args:
            current_outline: Current outline
            changes: Validated changes to apply

        Returns:
            New outline with changes applied
        """
        # Create a deep copy of the outline
        new_outline_data = current_outline.model_dump(by_alias=True)
        new_outline = Outline(**new_outline_data)

        # Apply insight additions
        for insight_data in changes.get("insights_to_add", []):
            # Ensure status defaults to "active" if not provided
            if "status" not in insight_data or insight_data["status"] is None:
                insight_data["status"] = "active"
            insight = Insight(**insight_data)
            new_outline.insights.append(insight)

        # Apply insight modifications
        for modify_data in changes.get("insights_to_modify", []):
            insight_id = modify_data["insight_id"]
            for i, insight in enumerate(new_outline.insights):
                if insight.insight_id == insight_id:
                    for key, value in modify_data.items():
                        # Skip None values to support partial updates
                        # Only update fields that are explicitly provided (not None)
                        if (
                            key != "insight_id"
                            and hasattr(insight, key)
                            and value is not None
                        ):
                            setattr(insight, key, value)
                    break

        # Apply insight removals
        insights_to_remove = set(changes.get("insights_to_remove", []))
        new_outline.insights = [
            i for i in new_outline.insights if i.insight_id not in insights_to_remove
        ]

        if insights_to_remove:
            # Ensure removed insights are also dropped from section references
            for section in new_outline.sections:
                section.insight_ids = [
                    iid for iid in section.insight_ids if iid not in insights_to_remove
                ]

        # Apply section additions
        for section_data in changes.get("sections_to_add", []):
            section_id = section_data.get("section_id")

            # Filter out fields that don't belong in Section model
            section_fields = {"section_id", "title", "order", "notes", "insight_ids"}
            filtered_data = {
                k: v for k, v in section_data.items() if k in section_fields
            }

            # Handle inline insights (atomic add-and-link)
            if "insights" in section_data and section_data["insights"] is not None:
                if not isinstance(section_data["insights"], list):
                    raise wrap_validation_error(
                        f"Section {section_id}: insights must be a list",
                        validation_errors=[
                            f"Got {type(section_data['insights']).__name__} instead of list"
                        ],
                        field="insights",
                    )

                # Process inline insights: create Insight objects and collect IDs
                inline_insight_ids = []
                for idx, insight_dict in enumerate(section_data["insights"]):
                    if not isinstance(insight_dict, dict):
                        raise ValueError(
                            f"Section {section_id}: insights[{idx}] must be a dictionary"
                        )

                    # Ensure status defaults to "active" if not provided
                    if "status" not in insight_dict or insight_dict["status"] is None:
                        insight_dict["status"] = "active"

                    # Auto-generate UUID if not provided
                    if (
                        "insight_id" not in insight_dict
                        or insight_dict["insight_id"] is None
                    ):
                        insight_dict["insight_id"] = str(uuid.uuid4())

                    # Validate required fields
                    if (
                        insight_dict.get("summary") is None
                        or insight_dict.get("importance") is None
                    ):
                        raise ValueError(
                            f"Section {section_id}: insights[{idx}] must have summary and importance"
                        )

                    # Create Insight object
                    try:
                        insight = Insight(**insight_dict)
                        new_outline.insights.append(insight)
                        inline_insight_ids.append(insight.insight_id)
                    except Exception as e:
                        raise ValueError(
                            f"Section {section_id}: Failed to create insight at index {idx}: {str(e)}"
                        ) from e

                # Set insight_ids to the inline insights
                filtered_data["insight_ids"] = inline_insight_ids

            # Handle insight_ids_to_add for new sections (preferred field name)
            # Also support direct insight_ids for backward compatibility
            elif (
                "insight_ids_to_add" in section_data
                and section_data["insight_ids_to_add"] is not None
            ):
                # Validate that insight_ids_to_add is a list
                if not isinstance(section_data["insight_ids_to_add"], list):
                    raise wrap_validation_error(
                        f"Section {section_id}: insight_ids_to_add must be a list",
                        validation_errors=[
                            f"Got {type(section_data['insight_ids_to_add']).__name__} instead of list"
                        ],
                        field="insight_ids_to_add",
                    )
                filtered_data["insight_ids"] = section_data["insight_ids_to_add"]
            elif (
                "insight_ids" in section_data
                and section_data["insight_ids"] is not None
            ):
                # Direct insight_ids provided
                if not isinstance(section_data["insight_ids"], list):
                    raise wrap_validation_error(
                        f"Section {section_id}: insight_ids must be a list",
                        validation_errors=[
                            f"Got {type(section_data['insight_ids']).__name__} instead of list"
                        ],
                        field="insight_ids",
                    )
                filtered_data["insight_ids"] = section_data["insight_ids"]
            else:
                # Default to empty list if neither provided
                filtered_data["insight_ids"] = []

            # Validate insight_ids reference existing insights or insights being added
            insight_ids_to_check = filtered_data.get("insight_ids", [])
            if insight_ids_to_check:
                existing_insight_ids = {i.insight_id for i in new_outline.insights}
                insights_being_added = {
                    change.get("insight_id")
                    for change in changes.get("insights_to_add", [])
                    if change.get("insight_id")
                }
                invalid_insights = [
                    iid
                    for iid in insight_ids_to_check
                    if iid not in existing_insight_ids
                    and iid not in insights_being_added
                ]
                if invalid_insights:
                    raise ValueError(
                        f"Section {section_id} references non-existent insights: {invalid_insights}. "
                        f"Insights must exist in outline or be added in the same operation."
                    )

            try:
                section = Section(**filtered_data)
                new_outline.sections.append(section)
            except Exception as e:
                raise ValueError(
                    f"Failed to create section {section_id}: {str(e)}. "
                    f"Section data: {filtered_data}"
                ) from e

        # Apply section modifications
        for modify_data in changes.get("sections_to_modify", []):
            section_id = modify_data.get("section_id")
            if not section_id:
                raise wrap_validation_error(
                    "Section modification missing required field: section_id",
                    field="section_id",
                )

            section_found = False
            for i, section in enumerate(new_outline.sections):
                if section.section_id == section_id:
                    section_found = True

                    # Get all existing and new insight IDs for validation
                    existing_insight_ids = {i.insight_id for i in new_outline.insights}
                    insights_being_added = {
                        change.get("insight_id")
                        for change in changes.get("insights_to_add", [])
                        if change.get("insight_id")
                    }
                    all_valid_insight_ids = existing_insight_ids | insights_being_added

                    # Track operations for detailed error reporting
                    operations_performed = []
                    errors = []

                    # Modify title
                    if "title" in modify_data and modify_data["title"] is not None:
                        try:
                            if not isinstance(modify_data["title"], str):
                                raise ValueError(
                                    f"title must be a string, got {type(modify_data['title']).__name__}"
                                )
                            if not modify_data["title"].strip():
                                raise ValueError("title cannot be empty")
                            section.title = modify_data["title"]
                            operations_performed.append("title")
                        except Exception as e:
                            errors.append(f"Failed to update title: {str(e)}")

                    # Modify notes
                    if "notes" in modify_data and modify_data["notes"] is not None:
                        try:
                            if not isinstance(modify_data["notes"], str):
                                raise ValueError(
                                    f"notes must be a string, got {type(modify_data['notes']).__name__}"
                                )
                            section.notes = modify_data["notes"]
                            operations_performed.append("notes")
                        except Exception as e:
                            errors.append(f"Failed to update notes: {str(e)}")

                    # Modify order
                    if "order" in modify_data and modify_data["order"] is not None:
                        try:
                            if not isinstance(modify_data["order"], int):
                                raise ValueError(
                                    f"order must be an integer, got {type(modify_data['order']).__name__}"
                                )
                            if modify_data["order"] < 0:
                                raise ValueError(
                                    f"order must be non-negative, got {modify_data['order']}"
                                )
                            section.order = modify_data["order"]
                            operations_performed.append("order")
                        except Exception as e:
                            errors.append(f"Failed to update order: {str(e)}")

                    # Add insight_ids
                    if (
                        "insight_ids_to_add" in modify_data
                        and modify_data["insight_ids_to_add"] is not None
                    ):
                        try:
                            if not isinstance(modify_data["insight_ids_to_add"], list):
                                raise ValueError(
                                    f"insight_ids_to_add must be a list, got {type(modify_data['insight_ids_to_add']).__name__}"
                                )

                            insight_ids_to_add = modify_data["insight_ids_to_add"]
                            if not insight_ids_to_add:  # Empty list is valid
                                operations_performed.append(
                                    "insight_ids_to_add (empty)"
                                )
                            else:
                                # Validate all insight IDs exist
                                invalid_insights = [
                                    iid
                                    for iid in insight_ids_to_add
                                    if iid not in all_valid_insight_ids
                                ]
                                if invalid_insights:
                                    raise ValueError(
                                        f"Invalid insight IDs: {invalid_insights}. "
                                        f"Insights must exist in outline or be added in the same operation."
                                    )

                                # Add insights (skip duplicates silently)
                                added_count = 0
                                skipped_count = 0
                                for insight_id in insight_ids_to_add:
                                    if insight_id not in section.insight_ids:
                                        section.insight_ids.append(insight_id)
                                        added_count += 1
                                    else:
                                        skipped_count += 1

                                operations_performed.append(
                                    f"insight_ids_to_add ({added_count} added, {skipped_count} already present)"
                                )
                        except Exception as e:
                            errors.append(f"Failed to add insight_ids: {str(e)}")

                    # Remove insight_ids
                    if (
                        "insight_ids_to_remove" in modify_data
                        and modify_data["insight_ids_to_remove"] is not None
                    ):
                        try:
                            if not isinstance(
                                modify_data["insight_ids_to_remove"], list
                            ):
                                raise ValueError(
                                    f"insight_ids_to_remove must be a list, got {type(modify_data['insight_ids_to_remove']).__name__}"
                                )

                            insight_ids_to_remove = modify_data["insight_ids_to_remove"]
                            if not insight_ids_to_remove:  # Empty list is valid
                                operations_performed.append(
                                    "insight_ids_to_remove (empty)"
                                )
                            else:
                                # Remove insights (skip if not present silently)
                                removed_count = 0
                                skipped_count = 0
                                for insight_id in insight_ids_to_remove:
                                    if insight_id in section.insight_ids:
                                        section.insight_ids.remove(insight_id)
                                        removed_count += 1
                                    else:
                                        skipped_count += 1

                                operations_performed.append(
                                    f"insight_ids_to_remove ({removed_count} removed, {skipped_count} not present)"
                                )
                        except Exception as e:
                            errors.append(f"Failed to remove insight_ids: {str(e)}")

                    # Report errors if any occurred
                    if errors:
                        error_details = "; ".join(errors)
                        raise ValueError(
                            f"Failed to modify section {section_id}: {error_details}. "
                            f"Operations attempted: {operations_performed}. "
                            f"Modification data: {modify_data}"
                        )

                    break

            if not section_found:
                raise ValueError(
                    f"Section not found for modification: {section_id}. "
                    f"Available section IDs: {[s.section_id for s in new_outline.sections]}"
                )

        # Apply section removals
        sections_to_remove = set(changes.get("sections_to_remove", []))
        new_outline.sections = [
            s for s in new_outline.sections if s.section_id not in sections_to_remove
        ]

        return new_outline

    def _format_validation_errors(self, errors: List[Any]) -> Dict[str, Any]:
        """Format Pydantic validation errors with hints and examples.

        Args:
            errors: List of Pydantic ValidationError error dicts

        Returns:
            Dict with errors, hints, and examples
        """
        formatted_errors = []
        hints = []
        examples = {}

        for error in errors:
            error_type = error.get("type", "unknown")
            loc = error.get("loc", ())
            msg = error.get("msg", "")

            formatted_errors.append(
                {
                    "field": ".".join(str(x) for x in loc),
                    "type": error_type,
                    "message": msg,
                }
            )

            # Add hints based on error type
            if error_type == "value_error.missing":
                hints.append(f"Missing required field: {'.'.join(str(x) for x in loc)}")
            elif "uuid" in error_type.lower() or "uuid" in msg.lower():
                hints.append("insight_id and section_id must be valid UUID strings")
                examples["insight_id"] = str(uuid.uuid4())
                examples["section_id"] = str(uuid.uuid4())
            elif "int" in error_type.lower() and "importance" in str(loc):
                hints.append("importance must be an integer between 0 and 10")
                examples["importance"] = 8

        return {
            "errors": formatted_errors,
            "hints": hints if hints else None,
            "examples": examples if examples else None,
        }

    def _calculate_warnings(
        self, outline: Outline, changes: ProposedChanges
    ) -> List[str]:
        """Calculate non-blocking warnings for proposed changes.

        Args:
            outline: Current outline
            changes: Proposed changes

        Returns:
            List of warning messages
        """
        warnings = []

        # Track insights that will exist after changes
        future_insight_ids = {i.insight_id for i in outline.insights}
        future_insight_ids.update({c.insight_id for c in changes.insights_to_add})
        future_insight_ids.difference_update(set(changes.insights_to_remove))

        # Track sections that will exist after changes
        future_section_ids = {s.section_id for s in outline.sections}
        future_section_ids.update({c.section_id for c in changes.sections_to_add})
        future_section_ids.difference_update(set(changes.sections_to_remove))

        # Check for orphaned insights (not referenced in any section)
        referenced_insights = set()
        for section in outline.sections:
            if section.section_id in future_section_ids:
                referenced_insights.update(section.insight_ids)

        # Add insights from new sections
        for change in changes.sections_to_add:
            if change.insight_ids_to_add:
                referenced_insights.update(change.insight_ids_to_add)

        # Add insights from modified sections
        for change in changes.sections_to_modify:
            # Get current section
            for section in outline.sections:
                if section.section_id == change.section_id:
                    referenced_insights.update(section.insight_ids)
                    if change.insight_ids_to_add:
                        referenced_insights.update(change.insight_ids_to_add)
                    if change.insight_ids_to_remove:
                        referenced_insights.difference_update(
                            change.insight_ids_to_remove
                        )
                    break

        orphaned = future_insight_ids - referenced_insights
        if orphaned:
            warnings.append(
                f"Orphaned insights (not referenced in any section): {sorted(orphaned)}"
            )

        # Check for sections with no insights
        for section in outline.sections:
            if section.section_id in future_section_ids:
                if not section.insight_ids:
                    warnings.append(
                        f"Section '{section.title}' ({section.section_id}) has no insights"
                    )

        # Check new sections
        for change in changes.sections_to_add:
            if not change.insight_ids_to_add:
                warnings.append(
                    f"New section '{change.title}' ({change.section_id}) has no insights"
                )

        return warnings

    def _calculate_preview(
        self, changes: ProposedChanges, outline: Outline
    ) -> Dict[str, Any]:
        """Calculate preview of changes that would be applied.

        Args:
            changes: Proposed changes
            outline: Current outline

        Returns:
            Preview dict with counts and estimated version
        """
        return {
            "sections_to_add": len(changes.sections_to_add),
            "insights_to_add": len(changes.insights_to_add),
            "sections_to_modify": len(changes.sections_to_modify),
            "insights_to_modify": len(changes.insights_to_modify),
            "sections_to_remove": len(changes.sections_to_remove),
            "insights_to_remove": len(changes.insights_to_remove),
            "estimated_outline_version": outline.outline_version + 1,
        }

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Evolve Report Parameters",
            "type": "object",
            "additionalProperties": False,
            "required": ["report_selector", "instruction", "proposed_changes"],
            "properties": {
                "report_selector": {
                    "type": "string",
                    "description": "Report ID (e.g., 'rpt_550e8400e29b11d4a716446655440000') or title to evolve",
                    "examples": [
                        "Q1 Revenue Report",
                        "rpt_550e8400e29b11d4a716446655440000",
                    ],
                },
                "instruction": {
                    "type": "string",
                    "description": "Natural language instruction describing desired report evolution (for audit/generation)",
                    "examples": [
                        "Add insights about customer retention trends",
                        "Prioritize revenue metrics over user acquisition",
                        "Add a new section for competitive analysis",
                    ],
                },
                "proposed_changes": {
                    "type": "object",
                    "description": "Structured changes to apply (REQUIRED - LLM must generate based on instruction)",
                    "properties": {
                        "insights_to_add": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                        "sections_to_add": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                        "insights_to_modify": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                        "sections_to_modify": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                        "insights_to_remove": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "sections_to_remove": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "constraints": {
                    "type": "object",
                    "description": "Optional constraints on the evolution (only used if generating changes)",
                    "properties": {
                        "max_importance_delta": {
                            "type": "integer",
                            "description": "Maximum change in insight importance scores",
                            "minimum": 0,
                            "maximum": 10,
                        },
                        "sections": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Limit changes to these section titles",
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Validate changes without applying them",
                            "default": False,
                        },
                    },
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Validate changes without applying them (shortcut for constraints.dry_run)",
                    "default": False,
                },
                "request_id": {
                    "type": "string",
                    "description": "Optional request correlation ID for tracing (auto-generated if not provided)",
                },
            },
        }


__all__ = ["EvolveReportTool"]
