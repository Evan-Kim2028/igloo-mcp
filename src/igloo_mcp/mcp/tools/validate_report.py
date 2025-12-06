"""Validate Report MCP Tool - Quality checks for living reports.

This tool performs comprehensive quality validation on living reports,
checking for common issues like missing citations, empty sections,
orphaned insights, and stale content.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from igloo_mcp.config import Config
from igloo_mcp.living_reports.models import Outline
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


# Check result constants
CHECK_PASS = "pass"
CHECK_WARNING = "warning"
CHECK_ERROR = "error"
CHECK_FIXED = "fixed"

# Available check types
AVAILABLE_CHECKS = {
    "citations",
    "empty_sections",
    "orphaned_insights",
    "duplicate_orders",
    "chart_references",
    "insight_importance",
    "section_titles",
    "stale_content",
}


class CheckResult:
    """Result of a single validation check."""

    def __init__(
        self,
        status: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
        fix_available: bool = False,
        fix_action: str | None = None,
    ):
        self.status = status
        self.message = message
        self.details = details or []
        self.fix_available = fix_available
        self.fix_action = fix_action

    def to_dict(self) -> dict[str, Any]:
        result = {
            "status": self.status,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        if self.fix_available:
            result["fix_available"] = True
            if self.fix_action:
                result["fix_action"] = self.fix_action
        return result


class ValidateReportTool(MCPTool):
    """MCP tool for validating living reports quality before publishing."""

    def __init__(self, config: Config, report_service: ReportService):
        """Initialize validate report tool.

        Args:
            config: Application configuration
            report_service: Report service instance
        """
        self.config = config
        self.report_service = report_service

    @property
    def name(self) -> str:
        return "validate_report"

    @property
    def description(self) -> str:
        return (
            "Validate Living Report quality before publishing. "
            "Checks for missing citations, empty sections, orphaned insights, "
            "and other common issues. Use fix_mode=True to auto-fix where possible."
        )

    @property
    def category(self) -> str:
        return "reports"

    @property
    def tags(self) -> list[str]:
        return ["reports", "validation", "quality", "checks"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
        return [
            {
                "description": "Validate all checks on a report",
                "parameters": {
                    "report_selector": "Q1 Revenue Report",
                },
            },
            {
                "description": "Check only citations and empty sections",
                "parameters": {
                    "report_selector": "Q1 Revenue Report",
                    "checks": ["citations", "empty_sections"],
                },
            },
            {
                "description": "Validate with stale content check",
                "parameters": {
                    "report_selector": "Q1 Revenue Report",
                    "checks": ["stale_content"],
                    "stale_threshold_days": 30,
                },
            },
            {
                "description": "Auto-fix fixable issues",
                "parameters": {
                    "report_selector": "Q1 Revenue Report",
                    "fix_mode": True,
                },
            },
        ]

    def get_parameter_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Validate Report Parameters",
            "type": "object",
            "additionalProperties": False,
            "required": ["report_selector"],
            "properties": {
                "report_selector": {
                    "type": "string",
                    "description": "Report ID or title to validate",
                },
                "checks": {
                    "type": "array",
                    "description": (
                        f"Checks to run. Use ['all'] for all checks. Available: {', '.join(sorted(AVAILABLE_CHECKS))}"
                    ),
                    "items": {"type": "string"},
                    "default": ["all"],
                },
                "stale_threshold_days": {
                    "type": "integer",
                    "description": "Threshold in days for stale content check",
                    "minimum": 1,
                    "default": 30,
                },
                "fix_mode": {
                    "type": "boolean",
                    "description": "Auto-fix issues where possible",
                    "default": False,
                },
                "request_id": {
                    "type": "string",
                    "description": "Optional request correlation ID for tracing",
                },
            },
        }

    @tool_error_handler("validate_report")
    async def execute(
        self,
        report_selector: str,
        checks: list[str] | None = None,
        stale_threshold_days: int = 30,
        fix_mode: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute report validation.

        Args:
            report_selector: Report ID or title to validate
            checks: List of checks to run (default: all)
            stale_threshold_days: Threshold for stale content (default: 30 days)
            fix_mode: Auto-fix issues where possible
            request_id: Optional request correlation ID

        Returns:
            Validation results with status, checks, and recommendations

        Raises:
            MCPSelectorError: If report not found
            MCPValidationError: If parameters are invalid
            MCPExecutionError: If validation fails
        """
        start_time = time.time()
        request_id = ensure_request_id(request_id)

        # Validate checks parameter
        checks = checks or ["all"]
        if "all" in checks:
            checks_to_run = list(AVAILABLE_CHECKS)
        else:
            invalid_checks = set(checks) - AVAILABLE_CHECKS
            if invalid_checks:
                raise MCPValidationError(
                    f"Invalid checks: {', '.join(invalid_checks)}",
                    validation_errors=[f"Invalid check: {c}" for c in invalid_checks],
                    hints=[f"Available checks: {', '.join(sorted(AVAILABLE_CHECKS))}"],
                )
            checks_to_run = list(checks)

        logger.info(
            "validate_report_started",
            extra={
                "report_selector": report_selector,
                "checks": checks_to_run,
                "fix_mode": fix_mode,
                "request_id": request_id,
            },
        )

        # Resolve selector
        try:
            self.report_service.index.rebuild_from_filesystem()
            selector = ReportSelector(self.report_service.index)
            report_id = selector.resolve(report_selector, strict=False)
        except SelectorResolutionError as e:
            error_dict = e.to_dict()
            raise MCPSelectorError(
                error_dict.get("message", f"Could not resolve report selector: {report_selector}"),
                selector=report_selector,
                error=error_dict.get("error", "not_found"),
                hints=["Use search_report to find available reports"],
            ) from e

        # Load outline
        try:
            outline = self.report_service.get_report_outline(report_id)
        except ValueError as e:
            raise MCPExecutionError(
                f"Failed to load report: {e!s}",
                operation="validate_report",
            ) from e

        # Get report directory for chart reference checks
        storage = self.report_service.global_storage.get_report_storage(report_id)
        report_dir = storage.report_dir

        # Run checks
        check_results: dict[str, dict[str, Any]] = {}
        fixes_applied = []

        for check_name in checks_to_run:
            result, fixed = self._run_check(check_name, outline, report_dir, stale_threshold_days, fix_mode)
            check_results[check_name] = result.to_dict()
            if fixed:
                fixes_applied.append(check_name)

        # If fixes were applied, save the outline
        if fix_mode and fixes_applied:
            self.report_service.update_report_outline(report_id, outline, actor="agent", request_id=request_id)

        # Calculate summary
        passed = sum(1 for r in check_results.values() if r["status"] == CHECK_PASS)
        warnings = sum(1 for r in check_results.values() if r["status"] == CHECK_WARNING)
        errors = sum(1 for r in check_results.values() if r["status"] == CHECK_ERROR)
        fixed_count = sum(1 for r in check_results.values() if r["status"] == CHECK_FIXED)

        # Determine overall status
        if errors > 0:
            overall_status = "errors"
        elif warnings > 0:
            overall_status = "warnings"
        else:
            overall_status = "valid"

        # Generate recommendations
        recommendations = self._generate_recommendations(check_results)

        total_duration = (time.time() - start_time) * 1000

        logger.info(
            "validate_report_completed",
            extra={
                "report_id": report_id,
                "overall_status": overall_status,
                "passed": passed,
                "warnings": warnings,
                "errors": errors,
                "fixed": fixed_count,
                "duration_ms": total_duration,
                "request_id": request_id,
            },
        )

        return {
            "status": overall_status,
            "report_id": report_id,
            "title": outline.title,
            "summary": {
                "total_checks": len(check_results),
                "passed": passed,
                "warnings": warnings,
                "errors": errors,
                "fixed": fixed_count,
            },
            "checks": check_results,
            "recommendations": recommendations,
            "fixes_applied": fixes_applied if fixes_applied else None,
            "request_id": request_id,
            "duration_ms": round(total_duration, 2),
        }

    def _run_check(
        self,
        check_name: str,
        outline: Outline,
        report_dir: Path,
        stale_threshold_days: int,
        fix_mode: bool,
    ) -> tuple[CheckResult, bool]:
        """Run a single check and optionally fix issues.

        Returns:
            Tuple of (CheckResult, was_fixed)
        """
        if check_name == "citations":
            return self._check_citations(outline, fix_mode)
        elif check_name == "empty_sections":
            return self._check_empty_sections(outline, fix_mode)
        elif check_name == "orphaned_insights":
            return self._check_orphaned_insights(outline, fix_mode)
        elif check_name == "duplicate_orders":
            return self._check_duplicate_orders(outline, fix_mode)
        elif check_name == "chart_references":
            return self._check_chart_references(outline, report_dir, fix_mode)
        elif check_name == "insight_importance":
            return self._check_insight_importance(outline, fix_mode)
        elif check_name == "section_titles":
            return self._check_section_titles(outline, fix_mode)
        elif check_name == "stale_content":
            return self._check_stale_content(outline, stale_threshold_days, fix_mode)
        else:
            return CheckResult(CHECK_PASS, f"Unknown check: {check_name}"), False

    def _check_citations(self, outline: Outline, fix_mode: bool) -> tuple[CheckResult, bool]:
        """Check that all insights have valid citations."""
        missing_citations = []

        for insight in outline.insights:
            has_citations = bool(insight.citations) or bool(insight.supporting_queries)
            if not has_citations:
                missing_citations.append(
                    {
                        "insight_id": insight.insight_id,
                        "summary": insight.summary[:100] + "..." if len(insight.summary) > 100 else insight.summary,
                        "issue": "No citations or supporting queries",
                    }
                )

        if not missing_citations:
            return CheckResult(CHECK_PASS, "All insights have citations"), False

        return CheckResult(
            CHECK_ERROR,
            f"{len(missing_citations)} insights missing citations",
            details=missing_citations,
            fix_available=False,
        ), False

    def _check_empty_sections(self, outline: Outline, fix_mode: bool) -> tuple[CheckResult, bool]:
        """Check for sections with no content or insights."""
        empty_sections = []

        for section in outline.sections:
            has_content = bool(section.content or section.notes)
            has_insights = bool(section.insight_ids)

            if not has_content and not has_insights:
                empty_sections.append(
                    {
                        "section_id": section.section_id,
                        "title": section.title,
                        "has_content": has_content,
                        "has_insights": has_insights,
                    }
                )

        if not empty_sections:
            return CheckResult(CHECK_PASS, "All sections have content"), False

        if fix_mode:
            # Remove empty sections
            section_ids_to_remove = {s["section_id"] for s in empty_sections}
            outline.sections = [s for s in outline.sections if s.section_id not in section_ids_to_remove]
            return CheckResult(
                CHECK_FIXED,
                f"Removed {len(empty_sections)} empty sections",
                details=empty_sections,
            ), True

        return CheckResult(
            CHECK_WARNING,
            f"{len(empty_sections)} sections have no content",
            details=empty_sections,
            fix_available=True,
            fix_action="Remove empty sections",
        ), False

    def _check_orphaned_insights(self, outline: Outline, fix_mode: bool) -> tuple[CheckResult, bool]:
        """Check for insights not linked to any section."""
        # Build set of all referenced insight IDs
        referenced_ids = set()
        for section in outline.sections:
            referenced_ids.update(section.insight_ids)

        # Find orphaned insights
        orphaned = []
        for insight in outline.insights:
            if insight.insight_id not in referenced_ids:
                orphaned.append(
                    {
                        "insight_id": insight.insight_id,
                        "summary": insight.summary[:100] + "..." if len(insight.summary) > 100 else insight.summary,
                        "importance": insight.importance,
                    }
                )

        if not orphaned:
            return CheckResult(CHECK_PASS, "All insights linked to sections"), False

        if fix_mode and outline.sections:
            # Link orphaned insights to first section
            first_section = min(outline.sections, key=lambda s: s.order)
            for item in orphaned:
                first_section.insight_ids.append(item["insight_id"])
            return CheckResult(
                CHECK_FIXED,
                f"Linked {len(orphaned)} orphaned insights to '{first_section.title}'",
                details=orphaned,
            ), True

        return CheckResult(
            CHECK_WARNING,
            f"{len(orphaned)} insights not linked to any section",
            details=orphaned,
            fix_available=bool(outline.sections),
            fix_action="Link to first section",
        ), False

    def _check_duplicate_orders(self, outline: Outline, fix_mode: bool) -> tuple[CheckResult, bool]:
        """Check for sections with duplicate order values."""
        order_map: dict[int, list[str]] = {}
        for section in outline.sections:
            order = section.order
            if order not in order_map:
                order_map[order] = []
            order_map[order].append(section.title)

        duplicates = [{"order": order, "sections": titles} for order, titles in order_map.items() if len(titles) > 1]

        if not duplicates:
            return CheckResult(CHECK_PASS, "All sections have unique order values"), False

        if fix_mode:
            # Re-assign unique order values
            for idx, section in enumerate(sorted(outline.sections, key=lambda s: (s.order, s.title))):
                section.order = idx
            return CheckResult(
                CHECK_FIXED,
                f"Re-assigned unique order values to {len(outline.sections)} sections",
            ), True

        return CheckResult(
            CHECK_WARNING,
            f"{len(duplicates)} order values shared by multiple sections",
            details=duplicates,
            fix_available=True,
            fix_action="Auto-assign unique orders",
        ), False

    def _check_chart_references(self, outline: Outline, report_dir: Path, fix_mode: bool) -> tuple[CheckResult, bool]:
        """Check that chart file references are valid."""
        charts_metadata = outline.metadata.get("charts", {})
        issues = []

        for chart_id, chart_data in charts_metadata.items():
            chart_path_str = chart_data.get("path", "")
            if not chart_path_str:
                issues.append(
                    {
                        "chart_id": chart_id,
                        "issue": "No path specified",
                        "path": None,
                    }
                )
                continue

            chart_path = Path(chart_path_str)

            # Check if absolute path (external)
            if chart_path.is_absolute():
                if not chart_path.exists():
                    issues.append(
                        {
                            "chart_id": chart_id,
                            "issue": "Chart file not found",
                            "path": str(chart_path),
                        }
                    )
                else:
                    issues.append(
                        {
                            "chart_id": chart_id,
                            "issue": "Chart stored outside report directory",
                            "path": str(chart_path),
                            "fix_available": True,
                        }
                    )
            else:
                # Relative path - resolve against report dir
                full_path = report_dir / chart_path
                if not full_path.exists():
                    issues.append(
                        {
                            "chart_id": chart_id,
                            "issue": "Chart file not found",
                            "path": str(chart_path),
                        }
                    )

        if not issues:
            return CheckResult(CHECK_PASS, "All chart references valid"), False

        return CheckResult(
            CHECK_WARNING,
            f"{len(issues)} chart reference issues",
            details=issues,
            fix_available=any(i.get("fix_available") for i in issues),
            fix_action="Copy external charts to report_files/",
        ), False

    def _check_insight_importance(self, outline: Outline, fix_mode: bool) -> tuple[CheckResult, bool]:
        """Check that all insights have valid importance values (1-10)."""
        invalid = []

        for insight in outline.insights:
            if insight.importance < 1 or insight.importance > 10:
                invalid.append(
                    {
                        "insight_id": insight.insight_id,
                        "summary": insight.summary[:50] + "...",
                        "importance": insight.importance,
                        "issue": "Importance must be 1-10",
                    }
                )

        if not invalid:
            return CheckResult(CHECK_PASS, "All insights have valid importance values"), False

        if fix_mode:
            # Clamp importance values to valid range
            for insight in outline.insights:
                if insight.importance < 1:
                    insight.importance = 1
                elif insight.importance > 10:
                    insight.importance = 10
            return CheckResult(
                CHECK_FIXED,
                f"Clamped {len(invalid)} importance values to 1-10 range",
                details=invalid,
            ), True

        return CheckResult(
            CHECK_WARNING,
            f"{len(invalid)} insights have invalid importance values",
            details=invalid,
            fix_available=True,
            fix_action="Clamp to valid range",
        ), False

    def _check_section_titles(self, outline: Outline, fix_mode: bool) -> tuple[CheckResult, bool]:
        """Check that all sections have non-empty titles."""
        empty_titles = []

        for section in outline.sections:
            if not section.title or not section.title.strip():
                empty_titles.append(
                    {
                        "section_id": section.section_id,
                        "order": section.order,
                    }
                )

        if not empty_titles:
            return CheckResult(CHECK_PASS, "All sections have non-empty titles"), False

        return CheckResult(
            CHECK_ERROR,
            f"{len(empty_titles)} sections have empty titles",
            details=empty_titles,
            fix_available=False,
        ), False

    def _check_stale_content(self, outline: Outline, threshold_days: int, fix_mode: bool) -> tuple[CheckResult, bool]:
        """Check for stale content not updated in threshold_days."""
        now = datetime.now(UTC)
        threshold = timedelta(days=threshold_days)
        stale_items = []

        for section in outline.sections:
            if self._is_stale(section.updated_at, now, threshold):
                days_old = self._days_since(section.updated_at, now)
                stale_items.append(
                    {
                        "type": "section",
                        "id": section.section_id,
                        "title": section.title,
                        "last_updated": section.updated_at,
                        "days_since_update": days_old,
                    }
                )

        for insight in outline.insights:
            if self._is_stale(insight.updated_at, now, threshold):
                days_old = self._days_since(insight.updated_at, now)
                stale_items.append(
                    {
                        "type": "insight",
                        "id": insight.insight_id,
                        "summary": insight.summary[:50] + "...",
                        "last_updated": insight.updated_at,
                        "days_since_update": days_old,
                    }
                )

        if not stale_items:
            return CheckResult(CHECK_PASS, f"No content older than {threshold_days} days"), False

        stale_sections = sum(1 for i in stale_items if i["type"] == "section")
        stale_insights = sum(1 for i in stale_items if i["type"] == "insight")

        return CheckResult(
            CHECK_WARNING,
            f"{stale_sections} sections and {stale_insights} insights not updated in {threshold_days}+ days",
            details=stale_items,
            fix_available=False,
        ), False

    def _is_stale(self, updated_at: str | None, now: datetime, threshold: timedelta) -> bool:
        """Check if content is stale based on updated_at timestamp."""
        if not updated_at:
            return True
        try:
            updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            return (now - updated) > threshold
        except (ValueError, TypeError):
            return True

    def _days_since(self, updated_at: str | None, now: datetime) -> int | None:
        """Calculate days since last update."""
        if not updated_at:
            return None
        try:
            updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            return (now - updated).days
        except (ValueError, TypeError):
            return None

    def _generate_recommendations(self, check_results: dict[str, dict[str, Any]]) -> list[str]:
        """Generate recommendations based on check results."""
        recommendations = []

        for check_name, result in check_results.items():
            if result["status"] in (CHECK_WARNING, CHECK_ERROR):
                if check_name == "citations":
                    recommendations.append("Add citations to insights for reproducibility and traceability")
                elif check_name == "empty_sections":
                    recommendations.append("Populate or remove empty sections to improve report clarity")
                elif check_name == "orphaned_insights":
                    recommendations.append("Link orphaned insights to relevant sections or remove if obsolete")
                elif check_name == "duplicate_orders":
                    recommendations.append("Fix duplicate order values to ensure consistent section ordering")
                elif check_name == "chart_references":
                    recommendations.append("Fix chart references - ensure files exist and are in report_files/")
                elif check_name == "stale_content":
                    recommendations.append("Review and update stale content before publishing")
                elif check_name == "section_titles":
                    recommendations.append("All sections must have descriptive titles")

        return recommendations


__all__ = ["ValidateReportTool"]
