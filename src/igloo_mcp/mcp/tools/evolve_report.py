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
                "summary": "30-day retention improved 15% QoQ",
                "importance": 8,
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

import datetime
import time
import uuid
from typing import Any

from pydantic import ValidationError

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

from igloo_mcp.config import Config
from igloo_mcp.living_reports.changes_schema import (
    CURRENT_CHANGES_SCHEMA_VERSION,
    ProposedChanges,
)
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
from igloo_mcp.mcp.validation_helpers import validate_response_mode

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
            "Add insights, sections, or content to an existing report—your primary tool for 'taking notes'. "
            "Use AFTER execute_query to record findings with proper citations (execution_id). "
            "Use response_mode='minimal' during iterative work, 'full' only for final review. "
            "Think: 'I found something interesting in my data, let me record it.'"
        )

    @property
    def category(self) -> str:
        return "reports"

    @property
    def tags(self) -> list[str]:
        return ["reports", "evolution", "llm", "structured-edits"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
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
        proposed_changes: dict[str, Any] | None = None,
        constraints: dict[str, Any] | None = None,
        dry_run: bool = False,
        status_change: str | None = None,
        response_mode: str | None = None,
        response_detail: str | None = None,  # DEPRECATED in v0.3.5
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute report evolution with structured error handling.

        Args:
            report_selector: Report ID or title to evolve
            instruction: Natural language instruction describing desired evolution
            proposed_changes: Structured changes to apply
            constraints: Optional constraints on evolution
            dry_run: If True, validate without applying changes
            status_change: Optional status change for the report
            response_mode: Response verbosity level (STANDARD: 'minimal', 'standard', 'full')
            response_detail: DEPRECATED - use response_mode instead
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

        # Validate response_mode parameter with backward compatibility
        mode = validate_response_mode(
            response_mode,
            legacy_param_name="response_detail",
            legacy_param_value=response_detail,
            valid_modes=("minimal", "standard", "full"),
            default="standard",
        )

        # Use mode for the rest of the function
        response_detail = mode

        proposed_changes = proposed_changes or {}

        # Handle status_change parameter: merge into proposed_changes if not already present
        # If both are provided with different values, raise validation error
        if status_change:
            if "status_change" in proposed_changes:
                if proposed_changes["status_change"] != status_change:
                    raise MCPValidationError(
                        "Conflicting status_change values provided",
                        validation_errors=[
                            f"status_change parameter: {status_change}",
                            f"proposed_changes.status_change: {proposed_changes['status_change']}",
                        ],
                        hints=[
                            "Provide status_change either as a top-level parameter OR in proposed_changes, not both",
                            "If using proposed_changes.status_change, omit the status_change parameter",
                        ],
                        context={"request_id": request_id},
                    )
            else:
                proposed_changes = {**proposed_changes, "status_change": status_change}

        if not proposed_changes:
            proposed_changes = self._generate_proposed_changes(
                self.report_service.get_report_outline(self.report_service.resolve_report_selector(report_selector)),
                instruction,
                constraints or {},
            )

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

            # Note: Index refresh moved to post-operation only to avoid double filesystem scan.
            # The post-operation refresh (line ~547) ensures consistency after changes.
            selector_start = time.time()

            # Step 1: Resolve selector with explicit error handling
            try:
                if hasattr(self.report_service, "resolve_report_selector"):
                    try:
                        report_id = self.report_service.resolve_report_selector(report_selector)
                    except Exception:
                        report_id = report_selector
                elif getattr(self.report_service, "index", None):
                    selector = ReportSelector(self.report_service.index)
                    report_id = selector.resolve(report_selector, strict=False)
                else:
                    report_id = report_selector
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
                error_msg = str(e)
                # If it's a "not found" error, raise selector error instead of execution error
                if "not found" in error_msg.lower():
                    logger.warning(
                        "evolve_report_report_not_found",
                        extra={
                            "report_id": report_id,
                            "request_id": request_id,
                            "outline_duration_ms": outline_duration,
                        },
                    )
                    raise MCPSelectorError(
                        error_msg,
                        selector=report_id,
                        error="not_found",
                        candidates=[],
                    ) from e
                logger.error(
                    "evolve_report_outline_load_failed",
                    extra={
                        "report_id": report_id,
                        "error": error_msg,
                        "request_id": request_id,
                        "outline_duration_ms": outline_duration,
                    },
                )
                raise MCPExecutionError(
                    f"Failed to load report outline: {error_msg}",
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
                return {
                    "status": "validation_failed",
                    "report_id": report_id,
                    "validation_issues": error_details["errors"],
                    "validation_errors": error_details["errors"],
                    "proposed_changes": proposed_changes,
                    "request_id": request_id,
                    "error_type": "schema_validation",
                }

            # Semantic validation
            # Legacy validation hook
            validation_issues = self._validate_changes(current_outline, proposed_changes, constraints or {})
            if validation_issues:
                return {
                    "status": "validation_failed",
                    "report_id": report_id,
                    "validation_issues": validation_issues,
                    "validation_errors": validation_issues,
                    "proposed_changes": proposed_changes,
                    "request_id": request_id,
                    "error_type": "semantic_validation",
                }

            semantic_errors = changes_obj.validate_against_outline(current_outline)
            if semantic_errors:
                validation_duration = (time.time() - validation_start) * 1000

                # Format structured errors for logging and response
                error_strings = [err.to_string() for err in semantic_errors]
                structured_errors = [
                    {
                        "field": err.field,
                        "value": err.value,
                        "error": err.error,
                        "available_ids": err.available_ids,
                    }
                    for err in semantic_errors
                ]
                compatibility_errors = list(error_strings)
                if any("already exists" in msg for msg in error_strings):
                    compatibility_errors.append("Cannot add - insight_id already exists")

                logger.warning(
                    "evolve_report_semantic_validation_failed",
                    extra={
                        "report_id": report_id,
                        "semantic_errors": error_strings,
                        "semantic_errors_structured": structured_errors,
                        "request_id": request_id,
                        "validation_duration_ms": validation_duration,
                    },
                )
                return {
                    "status": "validation_failed",
                    "report_id": report_id,
                    "validation_issues": compatibility_errors,
                    "validation_errors": compatibility_errors,
                    "proposed_changes": proposed_changes,
                    "request_id": request_id,
                    "error_type": "semantic_validation",
                }

            # Apply changes to compute future state (used for warnings and persistence)
            changes_payload = changes_obj.model_dump()
            apply_start = time.time()
            try:
                new_outline, apply_stats = self._apply_changes(current_outline, changes_payload)

                # Persist status change on outline metadata for compatibility
                if changes_obj.status_change:
                    new_outline.metadata["status"] = changes_obj.status_change

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
                    f"Failed to apply changes to report: {e!s}",
                    operation="evolve_report",
                    hints=["Check logs for detailed error information"],
                ) from e
            apply_duration = (time.time() - apply_start) * 1000

            # Calculate warnings from the post-change outline
            warnings = self._calculate_outline_warnings(new_outline)
            formatting_feedback = self._calculate_formatting_feedback(changes_obj, new_outline)
            warnings = warnings + formatting_feedback["warnings"]

            # Step 4: Dry run check
            if dry_run or (constraints and constraints.get("dry_run")):
                validation_duration = (time.time() - validation_start) * 1000
                total_duration = (time.time() - start_time) * 1000

                # Calculate preview
                preview = self._calculate_preview(changes_obj, current_outline)
                if changes_obj.status_change:
                    preview["status_change"] = changes_obj.status_change

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
                    "formatting_feedback": formatting_feedback,
                    "validation_passed": True,
                    "request_id": request_id,
                }

            # Step 6: Save with atomic write
            storage_start = time.time()
            try:
                self.report_service.update_report_outline(report_id, new_outline, actor="agent", request_id=request_id)

                if changes_obj.status_change:
                    self.report_service.update_report_status(
                        report_id,
                        changes_obj.status_change,
                        actor="agent",
                        request_id=request_id,
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
                    f"Failed to save report changes: {e!s}",
                    operation="evolve_report",
                    hints=["Check file system permissions and disk space"],
                ) from e

            # Auto-refresh index after successful changes to ensure consistency
            if getattr(self.report_service, "index", None):
                self.report_service.index.rebuild_from_filesystem()

            storage_duration = (time.time() - storage_start) * 1000
            total_duration = (time.time() - start_time) * 1000

            # Calculate summary
            # Note: UUIDs are auto-generated by model_validator if not provided, so all IDs should be present
            summary = {
                "sections_added": len(changes_obj.sections_to_add),
                "insights_added": len(apply_stats.get("insight_ids_added", [])),
                "sections_modified": len(changes_obj.sections_to_modify),
                "insights_modified": len(changes_obj.insights_to_modify),
                "sections_removed": len(changes_obj.sections_to_remove),
                "insights_removed": len(changes_obj.insights_to_remove),
                "insight_ids_added": apply_stats.get("insight_ids_added", []),
                "section_ids_added": apply_stats.get("section_ids_added", []),
                "insight_ids_modified": [c.insight_id for c in changes_obj.insights_to_modify if c.insight_id],
                "section_ids_modified": [c.section_id for c in changes_obj.sections_to_modify if c.section_id],
                "insight_ids_removed": list(changes_obj.insights_to_remove),
                "section_ids_removed": list(changes_obj.sections_to_remove),
            }
            if changes_obj.status_change:
                summary["status_change"] = changes_obj.status_change

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

            # Build response based on response_detail level
            if response_detail == "minimal":
                # Minimal response: just status, IDs, version, and counts
                minimal_summary: dict[str, Any] = {
                    "sections_added": summary["sections_added"],
                    "insights_added": summary["insights_added"],
                    "sections_modified": summary["sections_modified"],
                    "insights_modified": summary["insights_modified"],
                    "sections_removed": summary["sections_removed"],
                    "insights_removed": summary["insights_removed"],
                }
                if changes_obj.status_change:
                    minimal_summary["status_change"] = changes_obj.status_change

                response = {
                    "status": "success",
                    "report_id": report_id,
                    "outline_version": int(new_outline.outline_version),
                    "summary": minimal_summary,
                    "duration_ms": round(total_duration, 2),
                }
            elif response_detail == "standard":
                # Standard response: add IDs and warnings but no full echo
                response = {
                    "status": "success",
                    "report_id": report_id,
                    "outline_version": int(new_outline.outline_version),
                    "summary": summary,
                    "warnings": warnings,
                    "duration_ms": round(total_duration, 2),
                    # Response symmetry: flatten ID tracking fields to top level
                    "section_ids_added": summary["section_ids_added"],
                    "insight_ids_added": summary["insight_ids_added"],
                    "section_ids_modified": summary["section_ids_modified"],
                    "insight_ids_modified": summary["insight_ids_modified"],
                    "section_ids_removed": summary["section_ids_removed"],
                    "insight_ids_removed": summary["insight_ids_removed"],
                }
            else:  # response_detail == "full"
                # Full response: complete details including changes_applied
                changes_applied = changes_obj.model_dump(exclude_none=True)
                # Drop empty citations lists for backward compatibility
                for collection_key in ("insights_to_add", "insights_to_modify"):
                    for insight_change in changes_applied.get(collection_key, []):
                        if insight_change.get("citations") in ([], None):
                            insight_change.pop("citations", None)
                changes_applied.setdefault("title_change", None)

                response = {
                    "status": "success",
                    "report_id": report_id,
                    "changes_applied": changes_applied,
                    "outline_version": int(new_outline.outline_version),
                    "summary": summary,
                    "warnings": warnings,
                    "timing": {
                        "apply_duration_ms": round(apply_duration, 2),
                        "storage_duration_ms": round(storage_duration, 2),
                        "total_duration_ms": round(total_duration, 2),
                    },
                    # Response symmetry: flatten ID tracking fields to top level
                    "section_ids_added": summary["section_ids_added"],
                    "insight_ids_added": summary["insight_ids_added"],
                    "section_ids_modified": summary["section_ids_modified"],
                    "insight_ids_modified": summary["insight_ids_modified"],
                    "section_ids_removed": summary["section_ids_removed"],
                    "insight_ids_removed": summary["insight_ids_removed"],
                }

            # Add request_id to all response levels
            response["request_id"] = request_id
            response["formatting_feedback"] = formatting_feedback

            return response

        except Exception:
            # Re-raise to let @tool_error_handler decorator handle it
            raise
        # Note: The @tool_error_handler decorator will catch all unhandled exceptions
        # and format them appropriately, so we don't need a catch-all here

    def _validate_changes(
        self,
        current_outline: Outline,
        changes: dict[str, Any],
        constraints: dict[str, Any],
    ) -> list[str]:
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
            modify_data = dict(modify_data)
            if modify_data.get("template_data") and not modify_data.get("template"):
                sid = modify_data.get("section_id")
                raise ValueError(
                    f"Section modification requires template when template_data is provided (section_id={sid})"
                )
            section_id = modify_data.get("section_id")
            if section_id not in existing_section_ids:
                issues.append(f"Section ID not found: {section_id}")

        for section_id in changes.get("sections_to_remove", []):
            if section_id not in existing_section_ids:
                issues.append(f"Section ID not found for removal: {section_id}")

        # Citation enforcement for ALL reports (universal requirement)
        # Template should only control formatting, not data quality requirements
        citation_validation_enabled = not (constraints or {}).get("skip_citation_validation", False)

        if citation_validation_enabled:
            # Validate insights_to_add
            for insight_data in changes.get("insights_to_add", []):
                insight_id = insight_data.get("insight_id", "unknown")
                supporting_queries = insight_data.get("citations") or insight_data.get("supporting_queries", [])

                if not supporting_queries or len(supporting_queries) == 0:
                    issues.append(
                        f"All insights require citations for reproducibility. Insight '{insight_id}' "
                        "missing supporting_queries[0] with execution_id. "
                        "Use execute_query() first to get an execution_id, then include it in citations. "
                        "To disable validation (not recommended): "
                        "set skip_citation_validation=True in constraints"
                    )
                elif not supporting_queries[0].get("execution_id"):
                    issues.append(
                        f"All insights require citations. Insight '{insight_id}' "
                        "missing execution_id in citations[0]. "
                        "Use execute_query() first to get an execution_id, then include it in citations"
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
                        supporting_queries = modify_data.get("citations") or modify_data.get("supporting_queries", [])
                        if not supporting_queries or len(supporting_queries) == 0:
                            issues.append(
                                f"All insights require citations. Insight '{insight_id}' "
                                "missing supporting_queries[0] with execution_id. "
                                "Use execute_query() first to get an execution_id, "
                                "then include it in citations. "
                                "To disable validation (not recommended): "
                                "set skip_citation_validation=True in constraints"
                            )
                        elif not supporting_queries[0].get("execution_id"):
                            issues.append(
                                f"All insights require citations. Insight '{insight_id}' "
                                "missing execution_id in citations[0]. "
                                "Use execute_query() first to get an execution_id, "
                                "then include it in citations"
                            )
                    # If not modifying supporting_queries, check current value
                    elif not current_insight.supporting_queries and not current_insight.citations:
                        issues.append(
                            f"All insights require citations. Insight '{insight_id}' "
                            "missing supporting_queries[0] with execution_id. "
                            "Use execute_query() first to get an execution_id, "
                            "then include it in citations. "
                            "To disable validation (not recommended): set skip_citation_validation=True in constraints"
                        )
                    elif (
                        current_insight.supporting_queries and not current_insight.supporting_queries[0].execution_id
                    ) or (current_insight.citations and not current_insight.citations[0].execution_id):
                        issues.append(
                            f"All insights require citations. Insight '{insight_id}' "
                            "missing execution_id in citations[0]. "
                            "Use execute_query() first to get an execution_id, "
                            "then include it in citations"
                        )

        return issues

    def _generate_proposed_changes(
        self, current_outline: Outline, instruction: str, constraints: dict[str, Any]
    ) -> dict[str, Any]:
        """Fallback generator for proposed_changes when none are provided.

        This stub returns an empty change set to keep backwards compatibility
        with callers that rely on the tool to supply a minimal structure.
        """
        return {
            "schema_version": CURRENT_CHANGES_SCHEMA_VERSION,
            "type": "noop",
            "description": instruction or "No-op changes generated",
            "insights_to_add": [],
            "sections_to_add": [],
            "insights_to_modify": [],
            "sections_to_modify": [],
            "insights_to_remove": [],
            "sections_to_remove": [],
        }

    def _apply_changes(self, current_outline: Outline, changes: dict[str, Any]) -> tuple[Outline, dict[str, Any]]:
        """Apply validated changes to create new outline.

        Args:
            current_outline: Current outline
            changes: Validated changes to apply

        Returns:
            New outline with changes applied
        """
        now_iso = datetime.datetime.now(datetime.UTC).isoformat()
        # Create a deep copy of the outline
        new_outline_data = current_outline.model_dump(by_alias=True)
        new_outline = Outline(**new_outline_data)
        apply_stats: dict[str, Any] = {
            "insight_ids_added": [],
            "section_ids_added": [],
        }

        def _ensure_supporting_queries(payload: dict[str, Any]) -> None:
            if payload.get("citations") is None:
                payload["citations"] = []
            if "supporting_queries" not in payload or payload["supporting_queries"] is None:
                payload["supporting_queries"] = []
            # Keep citations aligned for backward compatibility
            if "citations" in payload and payload["citations"] is not None:
                if not payload.get("supporting_queries"):
                    # Convert citations to supporting_queries (for backward compat)
                    # Only extract fields that DatasetSource accepts
                    converted_queries = []
                    for cit in payload["citations"]:
                        if isinstance(cit, dict):
                            # Extract only DatasetSource fields from Citation dict
                            ds_data = {}
                            for field in ["execution_id", "sql_sha256", "cache_manifest"]:
                                if field in cit:
                                    ds_data[field] = cit[field]
                            if ds_data:  # Only add if at least one field is present
                                converted_queries.append(ds_data)
                        else:
                            # Already a DatasetSource object
                            converted_queries.append(cit)
                    payload["supporting_queries"] = converted_queries
            elif payload.get("supporting_queries"):
                payload["citations"] = payload["supporting_queries"]

        def _create_inline_insights(raw_insights: list[dict[str, Any]], section_context: str) -> list[str]:
            inline_ids: list[str] = []
            for idx, raw_insight in enumerate(raw_insights):
                if not isinstance(raw_insight, dict):
                    raise ValueError(f"Section {section_context}: insights[{idx}] must be a dictionary")
                insight_payload = dict(raw_insight)
                if "insight_id" not in insight_payload or insight_payload["insight_id"] is None:
                    insight_payload["insight_id"] = str(uuid.uuid4())
                if insight_payload.get("summary") is None or insight_payload.get("importance") is None:
                    raise ValueError(f"Section {section_context}: insights[{idx}] must have summary and importance")
                if "status" not in insight_payload or insight_payload["status"] is None:
                    insight_payload["status"] = "active"
                insight_payload.setdefault("created_at", now_iso)
                insight_payload.setdefault("updated_at", now_iso)
                _ensure_supporting_queries(insight_payload)
                try:
                    insight = Insight(**insight_payload)
                except Exception as exc:
                    raise ValueError(
                        f"Section {section_context}: Failed to create insight at index {idx}: {exc}"
                    ) from exc
                new_outline.insights.append(insight)
                inline_ids.append(insight.insight_id)
                apply_stats["insight_ids_added"].append(insight.insight_id)
            return inline_ids

        # Apply insight additions
        for insight_data in changes.get("insights_to_add", []):
            # Ensure status defaults to "active" if not provided
            if "status" not in insight_data or insight_data["status"] is None:
                insight_data["status"] = "active"
            insight_data.setdefault("created_at", now_iso)
            insight_data.setdefault("updated_at", now_iso)
            _ensure_supporting_queries(insight_data)
            insight = Insight(**insight_data)
            new_outline.insights.append(insight)
            apply_stats["insight_ids_added"].append(insight.insight_id)

        # Apply insight modifications
        for modify_data in changes.get("insights_to_modify", []):
            insight_id = modify_data["insight_id"]
            for _i, insight in enumerate(new_outline.insights):
                if insight.insight_id == insight_id:
                    modified = False
                    if not insight.created_at:
                        insight.created_at = now_iso
                    for key, value in modify_data.items():
                        # Skip None values to support partial updates
                        # Only update fields that are explicitly provided (not None)
                        if key != "insight_id" and hasattr(insight, key) and value is not None:
                            if key == "citations" and not modify_data.get("supporting_queries"):
                                # Keep supporting_queries in sync when only citations are provided
                                insight.supporting_queries = value
                            setattr(insight, key, value)
                            modified = True
                    if modified:
                        insight.updated_at = now_iso
                    break

        # Apply insight removals
        insights_to_remove = set(changes.get("insights_to_remove", []))
        new_outline.insights = [i for i in new_outline.insights if i.insight_id not in insights_to_remove]

        if insights_to_remove:
            # Ensure removed insights are also dropped from section references
            for section in new_outline.sections:
                section.insight_ids = [iid for iid in section.insight_ids if iid not in insights_to_remove]

        # Apply section additions
        for section_data in changes.get("sections_to_add", []):
            section_id = section_data.get("section_id")

            # Filter out fields that don't belong in Section model
            section_fields = {
                "section_id",
                "title",
                "order",
                "notes",
                "insight_ids",
                "content",
                "content_format",
            }
            filtered_data = {k: v for k, v in section_data.items() if k in section_fields}
            if section_data.get("template_data") and not section_data.get("template"):
                raise ValueError(f"Section {section_id or '<auto>'}: template_data provided without template name")
            template_name = section_data.get("template")
            if template_name:
                filtered_data["content"] = self._render_section_template(
                    template_name=template_name,
                    template_data=section_data.get("template_data") or {},
                    section_title=section_data.get("title") or "Untitled Section",
                )
                filtered_data.setdefault("content_format", "markdown")
            format_options = section_data.get("format_options")
            if format_options is not None and not isinstance(format_options, dict):
                sid = section_id or "<auto>"
                raise ValueError(
                    f"Section {sid}: format_options must be a dictionary, got {type(format_options).__name__}"
                )
            if filtered_data.get("content") and format_options:
                filtered_data["content"] = self._apply_format_options(
                    filtered_data["content"],
                    format_options,
                    filtered_data.get("title") or "Untitled Section",
                )

            filtered_data.setdefault("created_at", now_iso)
            filtered_data.setdefault("updated_at", now_iso)

            # Handle inline insights (atomic add-and-link)
            if "insights" in section_data and section_data["insights"] is not None:
                if not isinstance(section_data["insights"], list):
                    raise wrap_validation_error(
                        f"Section {section_id}: insights must be a list",
                        validation_errors=[f"Got {type(section_data['insights']).__name__} instead of list"],
                        field="insights",
                    )
                inline_ids = _create_inline_insights(section_data["insights"], section_id or "<auto>")
                filtered_data["insight_ids"] = inline_ids

            # Handle insight_ids_to_add for new sections (preferred field name)
            # Also support direct insight_ids for backward compatibility
            elif "insight_ids_to_add" in section_data and section_data["insight_ids_to_add"] is not None:
                # Validate that insight_ids_to_add is a list
                if not isinstance(section_data["insight_ids_to_add"], list):
                    raise wrap_validation_error(
                        f"Section {section_id}: insight_ids_to_add must be a list",
                        validation_errors=[f"Got {type(section_data['insight_ids_to_add']).__name__} instead of list"],
                        field="insight_ids_to_add",
                    )
                filtered_data["insight_ids"] = section_data["insight_ids_to_add"]
            elif "insight_ids" in section_data and section_data["insight_ids"] is not None:
                # Direct insight_ids provided
                if not isinstance(section_data["insight_ids"], list):
                    raise wrap_validation_error(
                        f"Section {section_id}: insight_ids must be a list",
                        validation_errors=[f"Got {type(section_data['insight_ids']).__name__} instead of list"],
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
                    if iid not in existing_insight_ids and iid not in insights_being_added
                ]
                if invalid_insights:
                    raise ValueError(
                        f"Section {section_id} references non-existent insights: {invalid_insights}. "
                        f"Insights must exist in outline or be added in the same operation."
                    )

            try:
                section = Section(**filtered_data)
                new_outline.sections.append(section)
                if section.section_id:
                    apply_stats["section_ids_added"].append(section.section_id)
            except Exception as e:
                raise ValueError(f"Failed to create section {section_id}: {e!s}. Section data: {filtered_data}") from e

        # Apply section modifications
        for modify_data in changes.get("sections_to_modify", []):
            modify_data = dict(modify_data)
            if modify_data.get("template_data") and not modify_data.get("template"):
                sid = modify_data.get("section_id")
                raise ValueError(
                    f"Section modification requires template when template_data is provided (section_id={sid})"
                )
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
                    updated = False

                    if modify_data.get("template"):
                        section_title = modify_data.get("title") or section.title or "Untitled Section"
                        modify_data["content"] = self._render_section_template(
                            template_name=modify_data["template"],
                            template_data=modify_data.get("template_data") or {},
                            section_title=section_title,
                        )
                        modify_data.setdefault("content_format", "markdown")

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
                    format_options = modify_data.get("format_options")
                    if format_options is not None and not isinstance(format_options, dict):
                        raise ValueError(
                            f"Section {section_id}: format_options must be a dictionary, "
                            f"got {type(format_options).__name__}"
                        )

                    # Modify title
                    if "title" in modify_data and modify_data["title"] is not None:
                        try:
                            if not isinstance(modify_data["title"], str):
                                raise ValueError(f"title must be a string, got {type(modify_data['title']).__name__}")
                            if not modify_data["title"].strip():
                                raise ValueError("title cannot be empty")
                            section.title = modify_data["title"]
                            operations_performed.append("title")
                            updated = True
                        except Exception as e:
                            errors.append(f"Failed to update title: {e!s}")

                    # Modify notes
                    if "notes" in modify_data and modify_data["notes"] is not None:
                        try:
                            if not isinstance(modify_data["notes"], str):
                                raise ValueError(f"notes must be a string, got {type(modify_data['notes']).__name__}")
                            section.notes = modify_data["notes"]
                            operations_performed.append("notes")
                            updated = True
                        except Exception as e:
                            errors.append(f"Failed to update notes: {e!s}")

                    # Modify content
                    if "content" in modify_data and modify_data["content"] is not None:
                        try:
                            if not isinstance(modify_data["content"], str):
                                raise ValueError(
                                    f"content must be a string, got {type(modify_data['content']).__name__}"
                                )
                            # Apply content merge mode if specified
                            merge_mode = modify_data.get("content_merge_mode", "replace")
                            if merge_mode != "replace":
                                from igloo_mcp.living_reports.merge_utils import apply_content_merge

                                section.content = apply_content_merge(
                                    existing=section.content,
                                    new_content=modify_data["content"],
                                    merge_mode=merge_mode,
                                )
                            else:
                                section.content = modify_data["content"]
                            if section.content and section.content.strip():
                                section.notes = None
                            elif not section.content or not section.content.strip():
                                section.content = None
                            operations_performed.append("content")
                            updated = True
                        except Exception as e:
                            errors.append(f"Failed to update content: {e!s}")

                    # Modify content_format
                    if "content_format" in modify_data and modify_data["content_format"] is not None:
                        try:
                            if modify_data["content_format"] not in (
                                "markdown",
                                "html",
                                "plain",
                            ):
                                raise ValueError("content_format must be one of markdown, html, plain")
                            section.content_format = modify_data["content_format"]
                            operations_performed.append("content_format")
                            updated = True
                        except Exception as e:
                            errors.append(f"Failed to update content_format: {e!s}")

                    # Modify order
                    if "order" in modify_data and modify_data["order"] is not None:
                        try:
                            if not isinstance(modify_data["order"], int):
                                raise ValueError(f"order must be an integer, got {type(modify_data['order']).__name__}")
                            if modify_data["order"] < 0:
                                raise ValueError(f"order must be non-negative, got {modify_data['order']}")
                            section.order = modify_data["order"]
                            operations_performed.append("order")
                            updated = True
                        except Exception as e:
                            errors.append(f"Failed to update order: {e!s}")

                    # Add insight_ids
                    if "insight_ids_to_add" in modify_data and modify_data["insight_ids_to_add"] is not None:
                        try:
                            if not isinstance(modify_data["insight_ids_to_add"], list):
                                raise ValueError(
                                    f"insight_ids_to_add must be a list, got "
                                    f"{type(modify_data['insight_ids_to_add']).__name__}"
                                )

                            insight_ids_to_add = modify_data["insight_ids_to_add"]
                            if not insight_ids_to_add:  # Empty list is valid
                                operations_performed.append("insight_ids_to_add (empty)")
                            else:
                                # Validate all insight IDs exist
                                invalid_insights = [
                                    iid for iid in insight_ids_to_add if iid not in all_valid_insight_ids
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
                                if added_count > 0 or skipped_count > 0:
                                    updated = True
                        except Exception as e:
                            errors.append(f"Failed to add insight_ids: {e!s}")

                    # Inline insights for modifications
                    if "insights" in modify_data and modify_data["insights"] is not None:
                        try:
                            if not isinstance(modify_data["insights"], list):
                                raise ValueError(
                                    f"insights must be a list, got {type(modify_data['insights']).__name__}"
                                )
                            inline_ids = _create_inline_insights(modify_data["insights"], section_id)
                            for inline_id in inline_ids:
                                if inline_id not in section.insight_ids:
                                    section.insight_ids.append(inline_id)
                            operations_performed.append(f"inline_insights_added ({len(inline_ids)})")
                            if inline_ids:
                                updated = True
                        except Exception as e:
                            errors.append(f"Failed to create inline insights: {e!s}")

                    # Remove insight_ids
                    if "insight_ids_to_remove" in modify_data and modify_data["insight_ids_to_remove"] is not None:
                        try:
                            if not isinstance(modify_data["insight_ids_to_remove"], list):
                                raise ValueError(
                                    f"insight_ids_to_remove must be a list, got "
                                    f"{type(modify_data['insight_ids_to_remove']).__name__}"
                                )

                            insight_ids_to_remove = modify_data["insight_ids_to_remove"]
                            if not insight_ids_to_remove:  # Empty list is valid
                                operations_performed.append("insight_ids_to_remove (empty)")
                            else:
                                # Remove insights (skip if not present silently)
                                removed_count = 0
                                missing_count = 0
                                for insight_id in insight_ids_to_remove:
                                    if insight_id in section.insight_ids:
                                        section.insight_ids.remove(insight_id)
                                        removed_count += 1
                                    else:
                                        missing_count += 1

                                operations_performed.append(
                                    f"insight_ids_to_remove ({removed_count} removed, {missing_count} missing)"
                                )
                                if removed_count > 0 or missing_count > 0:
                                    updated = True
                        except Exception as e:
                            errors.append(f"Failed to remove insight_ids: {e!s}")

                    if format_options:
                        section.content = self._apply_format_options(
                            section.content or "",
                            format_options,
                            section.title or "Untitled Section",
                        )
                        if section.content and section.content.strip():
                            section.notes = None
                        operations_performed.append("format_options")
                        updated = True

                    # Report errors if any occurred
                    if errors:
                        error_details = " | ".join(errors)
                        raise ValueError(
                            f"Failed to modify section {section_id}: {error_details}. "
                            f"Operations attempted: {operations_performed}. "
                            f"Modification data: {modify_data}"
                        )

                    if updated:
                        section.updated_at = now_iso

                    break

            if not section_found:
                raise ValueError(
                    f"Section not found for modification: {section_id}. "
                    f"Available section IDs: {[s.section_id for s in new_outline.sections]}"
                )

        # Apply section removals
        sections_to_remove = set(changes.get("sections_to_remove", []))
        new_outline.sections = [s for s in new_outline.sections if s.section_id not in sections_to_remove]

        # Apply title change
        if changes.get("title_change"):
            logger.info(
                "Applied title change",
                extra={
                    "old_title": current_outline.title,
                    "new_title": changes["title_change"],
                },
            )
            new_outline.title = changes["title_change"]

        # Apply metadata updates
        if changes.get("metadata_updates"):
            logger.info(
                "Applied metadata updates",
                extra={"updated_keys": list(changes["metadata_updates"].keys())},
            )
            # Merge metadata updates (shallow merge)
            new_outline.metadata.update(changes["metadata_updates"])

        return new_outline, apply_stats

    def _format_validation_errors(self, errors: list[Any]) -> dict[str, Any]:
        """Format Pydantic validation errors with hints and examples.

        Args:
            errors: List of Pydantic ValidationError error dicts

        Returns:
            Dict with errors, hints, examples, and schema help
        """
        formatted_errors: list[dict[str, Any]] = []
        hints: list[str] = []
        examples: dict[str, Any] = {}

        # Track which operation types had errors for targeted schema help
        operations_with_errors = set()

        for error in errors:
            error_type = error.get("type", "unknown")
            loc = error.get("loc", ())
            msg = error.get("msg", "")
            input_value = error.get("input")

            field_path = ".".join(str(x) for x in loc)

            formatted_errors.append(
                {
                    "field": field_path,
                    "type": error_type,
                    "message": msg,
                    "input_value": input_value,
                }
            )

            # Track operation type
            if loc and len(loc) > 0:
                operation = str(loc[0])
                operations_with_errors.add(operation)

            # Add hints based on error type
            if error_type == "value_error.missing" or "missing" in error_type.lower():
                hints.append(f"Missing required field: {field_path}")
            elif "uuid" in error_type.lower() or "uuid" in msg.lower():
                hints.append("insight_id and section_id must be valid UUID strings")
                examples["insight_id"] = str(uuid.uuid4())
                examples["section_id"] = str(uuid.uuid4())
            elif "int" in error_type.lower() and "importance" in str(loc):
                hints.append("importance must be an integer between 0 and 10")
                examples["importance"] = 8
            elif "list" in error_type.lower():
                hints.append(f"{field_path} must be a list/array")
                if "supporting_queries" in field_path:
                    hints.append("supporting_queries defaults to [] if omitted")

        # Add operation-specific schema examples
        schema_examples = self._get_schema_examples_for_operations(operations_with_errors)

        return {
            "errors": formatted_errors,
            "hints": hints if hints else None,
            "examples": examples if examples else None,
            "schema_examples": schema_examples if schema_examples else None,
            "documentation": "https://github.com/Evan-Kim2028/igloo-mcp/blob/main/docs/living-reports/user-guide.md",
        }

    def _get_schema_examples_for_operations(self, operations: set[str]) -> dict[str, Any]:
        """Get schema examples for specific operations that had errors.

        Args:
            operations: Set of operation types that had validation errors

        Returns:
            Dict with schema examples for each operation type
        """
        examples: dict[str, Any] = {}

        if "insights_to_add" in operations:
            examples["insights_to_add"] = [
                {
                    "section_id": "550e8400-e29b-41d4-a716-446655440012",
                    "insight": {
                        "summary": "Revenue grew 25% YoY to $2.4M",
                        "importance": 9,
                        "supporting_queries": [],  # Optional, defaults to []
                    },
                }
            ]

        if "sections_to_add" in operations:
            examples["sections_to_add"] = [
                {
                    "title": "Executive Summary",
                    "order": 1,
                    "notes": "Optional section notes",
                    "content": "Optional markdown content",
                    "content_format": "markdown",  # Optional, defaults to "markdown"
                }
            ]

        if "sections_to_modify" in operations:
            examples["sections_to_modify"] = [
                {
                    "section_id": "550e8400-e29b-41d4-a716-446655440012",
                    "title": "New Title",  # Optional
                    "order": 2,  # Optional
                    "insight_ids_to_add": [
                        "insight-uuid-1",
                        "insight-uuid-2",
                    ],  # Optional
                    "content": "Updated content",  # Optional
                }
            ]

        if "status_change" in operations:
            examples["status_change"] = "archived"  # or "active" or "deleted"

        return examples

    def _calculate_outline_warnings(self, outline: Outline) -> list[str]:
        """Calculate warnings based on the post-change outline state."""
        warnings: list[str] = []
        referenced_insights = {insight_id for section in outline.sections for insight_id in section.insight_ids}
        all_insight_ids = {insight.insight_id for insight in outline.insights}

        orphaned = sorted(all_insight_ids - referenced_insights)
        if orphaned:
            warnings.append(f"Orphaned insights (not referenced in any section): {orphaned}")

        for section in outline.sections:
            if not section.insight_ids:
                warnings.append(f"Section '{section.title}' ({section.section_id}) has no insights")

        return warnings

    def _render_section_template(self, template_name: str, template_data: dict[str, Any], section_title: str) -> str:
        """Render structured markdown templates for sections."""
        if not isinstance(template_name, str):
            raise ValueError("template must be a string")
        normalized_name = template_name.strip().lower()
        data = template_data or {}

        if normalized_name in {"findings", "findings_list"}:
            findings = data.get("findings", [])
            if not findings:
                raise ValueError("findings_list template requires 'findings' array")
            heading = data.get("heading") or f"Key Findings - {section_title}"
            lines = [f"## {heading.strip()}", ""]
            for idx, finding in enumerate(findings, 1):
                title = finding.get("title") or f"Finding {idx}"
                summary = finding.get("description") or finding.get("summary") or ""
                metric = finding.get("metric") or {}
                lines.append(f"### {idx}. {title.strip()}")
                if metric:
                    lines.append("")
                    lines.append("| Metric | Value | Trend |")
                    lines.append("| --- | --- | --- |")
                    lines.append(
                        f"| {metric.get('name', 'Value')} | {metric.get('value', '-')} | {metric.get('trend', '-')} |"
                    )
                if summary:
                    lines.append("")
                    lines.append(summary.strip())
                if finding.get("actions"):
                    lines.append("")
                    lines.append("**Next Steps**")
                    for action in finding["actions"]:
                        lines.append(f"- {action}")
                lines.append("")
            return "\n".join(lines).strip()

        if normalized_name in {"metrics", "metrics_snapshot"}:
            metrics = data.get("metrics", [])
            if not metrics:
                raise ValueError("metrics_snapshot template requires 'metrics' array")
            heading = data.get("heading") or f"{section_title} Metrics"
            lines = [f"## {heading.strip()}", "", "| Metric | Value | Target | Delta |", "| --- | --- | --- | --- |"]
            for metric in metrics:
                lines.append(
                    "| {name} | {value} | {target} | {delta} |".format(
                        name=metric.get("name", "Metric"),
                        value=metric.get("value", "-"),
                        target=metric.get("target", "-"),
                        delta=metric.get("delta", "-"),
                    )
                )
            if data.get("callouts"):
                lines.append("")
                lines.append("### Callouts")
                for callout in data["callouts"]:
                    title = callout.get("title", "Callout")
                    detail = callout.get("detail") or callout.get("description") or ""
                    lines.append(f"- **{title}** — {detail}")
            return "\n".join(lines).strip()

        if normalized_name in {"bullet", "bullet_list", "summary_bullets"}:
            items = data.get("items") or data.get("bullets")
            if not items:
                raise ValueError("bullet_list template requires 'items' array")
            heading = data.get("heading") or section_title or "Summary"
            lines = [f"## {heading.strip()}", ""]
            for item in items:
                lines.append(f"- {item}")
            return "\n".join(lines).strip()

        if normalized_name in {"executive_summary", "exec_summary"}:
            # Executive summary with headline, key takeaways, and optional recommendation
            headline = data.get("headline") or data.get("title") or section_title
            key_points = data.get("key_points") or data.get("takeaways") or []
            recommendation = data.get("recommendation") or data.get("action")
            conclusion = data.get("conclusion") or data.get("summary")

            lines = [f"## {headline.strip()}", ""]

            if data.get("context"):
                lines.append(data["context"].strip())
                lines.append("")

            if key_points:
                lines.append("### Key Takeaways")
                lines.append("")
                for idx, point in enumerate(key_points, 1):
                    if isinstance(point, dict):
                        title = point.get("title", f"Point {idx}")
                        detail = point.get("detail", "")
                        lines.append(f"{idx}. **{title}** — {detail}")
                    else:
                        lines.append(f"{idx}. {point}")
                lines.append("")

            if recommendation:
                lines.append("### Recommendation")
                lines.append("")
                lines.append(f"> {recommendation.strip()}")
                lines.append("")

            if conclusion:
                lines.append(conclusion.strip())
                lines.append("")

            return "\n".join(lines).strip()

        if normalized_name in {"action_items", "next_steps", "actions"}:
            # Action items with owners, due dates, and priority
            actions = data.get("actions") or data.get("items") or []
            if not actions:
                raise ValueError("action_items template requires 'actions' array")

            heading = data.get("heading") or "Action Items"
            lines = [f"## {heading.strip()}", ""]

            has_table_data = any(
                isinstance(a, dict) and (a.get("owner") or a.get("due") or a.get("priority")) for a in actions
            )

            if has_table_data:
                lines.append("| # | Action | Owner | Due | Priority |")
                lines.append("| --- | --- | --- | --- | --- |")
                for idx, action in enumerate(actions, 1):
                    if isinstance(action, dict):
                        desc = action.get("description") or action.get("action") or action.get("title") or ""
                        owner = action.get("owner") or "TBD"
                        due = action.get("due") or action.get("due_date") or "-"
                        priority = action.get("priority") or "Medium"
                        lines.append(f"| {idx} | {desc} | {owner} | {due} | {priority} |")
                    else:
                        lines.append(f"| {idx} | {action} | TBD | - | Medium |")
            else:
                for idx, action in enumerate(actions, 1):
                    if isinstance(action, dict):
                        desc = action.get("description") or action.get("action") or action.get("title") or ""
                        lines.append(f"{idx}. {desc}")
                    else:
                        lines.append(f"{idx}. {action}")

            lines.append("")
            return "\n".join(lines).strip()

        raise ValueError(f"Unknown section template: {template_name}")

    def _apply_format_options(self, content: str, format_options: dict[str, Any], section_title: str) -> str:
        """Apply simple markdown formatting helpers requested by the agent."""
        if not content:
            return content

        updated = content.strip()
        auto_heading = format_options.get("auto_heading")
        if auto_heading:
            heading_text = auto_heading if isinstance(auto_heading, str) else section_title or "Overview"
            first_line = updated.splitlines()[0].strip() if updated.splitlines() else ""
            if not first_line.startswith("#"):
                updated = f"## {heading_text.strip()}\n\n{updated}"

        if format_options.get("ensure_blank_lines", True):
            normalized_lines: list[str] = []
            lines = updated.splitlines()
            for idx, line in enumerate(lines):
                normalized_lines.append(line.rstrip())
                if line.strip().startswith("#") and idx + 1 < len(lines) and lines[idx + 1].strip():
                    normalized_lines.append("")
            updated = "\n".join(normalized_lines).strip()

        return updated

    def _analyze_section_formatting(self, section: Section) -> list[str]:
        """Heuristic checks to flag unreadable markdown sections."""
        warnings: list[str] = []
        title = section.title or section.section_id or "Untitled Section"
        content = (section.content or "").strip()
        if not content:
            warnings.append(f"Section '{title}' is missing markdown content.")
            return warnings

        lines = [line for line in content.splitlines() if line.strip()]
        has_heading = any(line.lstrip().startswith("#") for line in lines)
        if len(content) > 240 and not has_heading:
            warnings.append(f"Section '{title}' has >200 characters but no headings. Add ## subheads for scanability.")

        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if any(len(p) > 600 for p in paragraphs):
            warnings.append(
                f"Section '{title}' contains very long paragraphs. Break them into shorter blocks or bullets."
            )

        bullet_lines = [line for line in lines if line.lstrip().startswith(("-", "*", "+", "1.", "1)"))]
        if len(paragraphs) >= 4 and len(content) > 600 and not bullet_lines:
            warnings.append(
                f"Section '{title}' has multiple paragraphs but no bullet lists. Consider using '-' or numbered lists."
            )

        return warnings

    def _calculate_formatting_feedback(self, changes: ProposedChanges, outline: Outline) -> dict[str, Any]:
        """Focus formatting guidance on sections touched by this request."""
        touched_section_ids = {
            *(section.section_id for section in changes.sections_to_add if section.section_id),
            *(section.section_id for section in changes.sections_to_modify if section.section_id),
        }
        touched_section_ids -= set(changes.sections_to_remove)

        section_feedback: list[dict[str, Any]] = []
        formatting_warnings: list[str] = []

        for section in outline.sections:
            if section.section_id in touched_section_ids:
                section_warnings = self._analyze_section_formatting(section)
                if section_warnings:
                    formatting_warnings.extend(section_warnings)
                    section_feedback.append(
                        {
                            "section_id": section.section_id,
                            "title": section.title,
                            "warnings": section_warnings,
                        }
                    )

        score_penalty = 12 * len(formatting_warnings)
        score = max(0, 100 - score_penalty) if touched_section_ids else 100

        return {
            "score": score,
            "warnings": formatting_warnings,
            "section_feedback": section_feedback,
        }

    def _calculate_preview(self, changes: ProposedChanges, outline: Outline) -> dict[str, Any]:
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
            "status_change": changes.status_change,
        }

    def get_parameter_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Evolve Report Parameters",
            "type": "object",
            "additionalProperties": False,
            "required": ["report_selector", "instruction"],
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
                    "description": "Natural language instruction describing desired "
                    "report evolution (for audit/generation)",
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
                "status_change": {
                    "type": "string",
                    "description": "Optional status change for the report",
                    "enum": ["active", "archived", "deleted"],
                },
                "request_id": {
                    "type": "string",
                    "description": "Optional request correlation ID for tracing (auto-generated if not provided)",
                },
            },
        }


__all__ = ["EvolveReportTool"]
