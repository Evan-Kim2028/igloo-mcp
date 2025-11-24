"""Report selector resolution with deterministic behavior and structured errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .index import ReportIndex


@dataclass
class SelectorResolutionError(ValueError):
    """Structured error for selector resolution failures."""

    selector: str
    error_type: str  # "not_found", "ambiguous", "invalid_format"
    candidates: Optional[List[str]] = None
    message: Optional[str] = None
    candidate_details: Optional[List[Dict[str, str]]] = (
        None  # List of {title, id} dicts
    )

    def to_dict(self):
        result = {
            "error": self.error_type,
            "selector": self.selector,
            "message": self.message or self._default_message(),
        }

        # Include candidate details if available
        if self.candidate_details:
            result["candidates"] = self.candidate_details
            result["hint"] = "Did you mean one of these?"
        elif self.candidates:
            result["candidates"] = self.candidates

        return result

    def _default_message(self):
        if self.error_type == "not_found":
            return f"Report not found: {self.selector}"
        elif self.error_type == "ambiguous":
            return f"Ambiguous selector '{self.selector}' matches multiple reports"
        elif self.error_type == "invalid_format":
            return f"Invalid selector format: {self.selector}"
        return "Unknown selector error"


class ReportSelector:
    """Deterministic report selector resolution.

    Resolves in order:
    1. Exact UUID match
    2. Exact title match (case-insensitive)
    3. Partial title match (single result only)
    4. Tag-based match (if prefixed with 'tag:')
    """

    def __init__(self, index: ReportIndex):
        self.index = index

    def resolve(self, selector: str, strict: bool = False) -> str:
        """Resolve selector to report ID.

        Args:
            selector: Report ID, title, or 'tag:tagname'
            strict: If True, only allow exact ID/title matches

        Returns:
            Resolved report ID

        Raises:
            SelectorResolutionError: With structured error information
        """
        # 1. Try exact UUID match
        try:
            from .models import ReportId

            ReportId(selector)
            entry = self.index.get_entry(selector)
            if entry:
                return selector
        except ValueError:
            pass

        # 2. Try exact title match
        exact_id = self.index.resolve_title(selector, allow_partial=False)
        if exact_id:
            return exact_id

        if strict:
            raise SelectorResolutionError(
                selector=selector,
                error_type="not_found",
                message=f"Exact match required but not found: {selector}",
            )

        # 3. Try partial title match
        partial_id = self.index.resolve_title(selector, allow_partial=True)
        if partial_id:
            return partial_id

        # 4. Check for tag-based selector
        if selector.startswith("tag:"):
            tag = selector[4:]
            entries = self.index.list_entries(tags=[tag])
            if not entries:
                raise SelectorResolutionError(
                    selector=selector,
                    error_type="not_found",
                    message=f"No reports found with tag: {tag}",
                )
            if len(entries) > 1:
                candidate_details = [
                    {"title": e.current_title, "id": e.report_id} for e in entries
                ]
                raise SelectorResolutionError(
                    selector=selector,
                    error_type="ambiguous",
                    candidates=[e.report_id for e in entries],
                    candidate_details=candidate_details,
                    message=f"Multiple reports with tag '{tag}'",
                )
            return entries[0].report_id

        # Not found - try to find candidates for helpful error message
        candidates = []
        candidate_details = []
        selector_lower = selector.lower()

        # Look for partial matches in titles
        for entry in self.index.list_entries():
            if selector_lower in entry.current_title.lower():
                candidate_details.append(
                    {
                        "title": entry.current_title,
                        "id": entry.report_id,
                    }
                )
                candidates.append(entry.report_id)

        # Limit to top 5 candidates
        candidate_details = candidate_details[:5]
        candidates = candidates[:5]

        raise SelectorResolutionError(
            selector=selector,
            error_type="not_found",
            candidates=candidates if candidates else None,
            candidate_details=candidate_details if candidate_details else None,
            message=f"Report not found: {selector}"
            + (". Did you mean one of these?" if candidate_details else ""),
        )
