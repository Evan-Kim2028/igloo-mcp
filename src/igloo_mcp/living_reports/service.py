"""High-level service layer for living reports operations.

This module provides the main orchestration logic for living reports,
coordinating between storage, index, and external integrations.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import uuid
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..path_utils import resolve_history_path
from .history_index import HistoryIndex, ResolvedDataset
from .index import ReportIndex
from .models import AuditEvent, IndexEntry, Outline, ReportId
from .quarto_renderer import QuartoNotFoundError, QuartoRenderer, RenderResult
from .storage import GlobalStorage, ReportStorage


class ReportService:
    """High-level service for living reports operations."""

    def __init__(self, reports_root: Optional[Path] = None) -> None:
        """Initialize report service.

        Args:
            reports_root: Root directory for reports (defaults to global/repo based on IGLOO_MCP_LOG_SCOPE)
        """
        if reports_root is None:
            from ..path_utils import resolve_reports_root

            reports_root = resolve_reports_root()

        self.reports_root = reports_root
        self.global_storage = GlobalStorage(reports_root)
        self.index = ReportIndex(reports_root / "index.jsonl")

        # Initialize HistoryIndex lazily
        self._history_index: Optional[HistoryIndex] = None

    @property
    def history_index(self) -> HistoryIndex:
        """Get the history index for resolving query references."""
        if self._history_index is None:
            history_path = resolve_history_path()
            self._history_index = HistoryIndex(history_path)
        return self._history_index

    def create_report(
        self, title: str, template: str = "default", actor: str = "cli", **metadata: Any
    ) -> str:
        """Create a new report.

        Args:
            title: Human-readable title for the report
            template: Template name (default, monthly_sales, quarterly_review, deep_dive)
            actor: Who is creating the report (cli, agent, human) - defaults to "cli" for backward compatibility
            **metadata: Additional metadata (tags, owner, etc.)

        Returns:
            Report ID of the created report

        Raises:
            ValueError: If template name is invalid
        """
        # Import templates.py module directly (avoiding conflict with templates/ directory)
        import importlib.util
        import sys

        # Set up parent package context for relative imports
        parent_module = sys.modules.get("igloo_mcp.living_reports")
        if parent_module is None:
            from igloo_mcp import living_reports as parent_module
        templates_file = Path(__file__).parent / "templates.py"
        spec = importlib.util.spec_from_file_location(
            "igloo_mcp.living_reports.templates",
            templates_file,
            submodule_search_locations=[str(Path(__file__).parent)],
        )
        templates_mod = importlib.util.module_from_spec(spec)
        templates_mod.__package__ = "igloo_mcp.living_reports"
        templates_mod.__name__ = "igloo_mcp.living_reports.templates"
        # Set up models import
        templates_mod.models = parent_module.models
        spec.loader.exec_module(templates_mod)
        get_template = templates_mod.get_template

        # Normalize actor to a valid value
        if actor not in {"cli", "agent", "human"}:
            actor = "cli"

        report_id = ReportId.new()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Get template sections
        try:
            sections = get_template(template)
        except ValueError as e:
            raise ValueError(f"Invalid template: {e}") from e

        # Create initial outline with template sections
        outline = Outline(
            report_id=str(report_id),
            title=title,
            created_at=now,
            updated_at=now,
            version="1.0",
            sections=sections,
            insights=[],
            metadata={**metadata, "template": template},
        )

        # Create storage and save
        storage = self.global_storage.get_report_storage(str(report_id))
        with storage.lock():
            storage._save_outline_atomic(outline)  # No backup for initial creation

            # Create audit event
            audit_event = AuditEvent(
                action_id=str(uuid.uuid4()),
                report_id=str(report_id),
                ts=now,
                actor=actor,
                action_type="create",
                payload={"initial_title": title},
            )
            storage.append_audit_event(audit_event)

        # Add to index
        index_entry = IndexEntry(
            report_id=str(report_id),
            current_title=title,
            created_at=now,
            updated_at=now,
            tags=metadata.get("tags", []),
            status="active",
            path=f"by_id/{report_id}",
        )
        self.index.add_entry(index_entry)

        return str(report_id)

    def get_report_outline(self, report_id: str) -> Outline:
        """Get the current outline for a report.

        Args:
            report_id: Report identifier

        Returns:
            Current outline

        Raises:
            ValueError: If report not found
        """
        storage = self.global_storage.get_report_storage(report_id)
        try:
            return storage.load_outline()
        except FileNotFoundError as e:
            raise ValueError(f"Report not found: {report_id}") from e

    def update_report_outline(
        self,
        report_id: str,
        outline: Outline,
        actor: str = "cli",
        expected_version: Optional[int] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Update a report's outline with optional version check.

        Args:
            report_id: Report identifier
            outline: New outline
            actor: Who is making the change (cli, agent, human)
            expected_version: Expected outline_version for optimistic locking
            request_id: Optional request correlation ID for tracing

        Raises:
            ValueError: If version mismatch (concurrent modification detected)
        """
        storage = self.global_storage.get_report_storage(report_id)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Normalize actor to a valid value for AuditEvent
        if actor not in {"cli", "agent", "human"}:
            actor = "agent"

        with storage.lock():
            # Load current outline for comparison
            old_outline = storage.load_outline()

            # Version check for optimistic locking
            if expected_version is not None:
                if old_outline.outline_version != expected_version:
                    raise ValueError(
                        f"Version mismatch: expected {expected_version}, "
                        f"got {old_outline.outline_version}. "
                        f"Report was modified concurrently."
                    )

            # Increment version
            outline.outline_version = old_outline.outline_version + 1
            outline.updated_at = now

            # Save new outline (without additional audit events)
            backup_filename = storage._save_outline_atomic(outline)

            # Calculate change summary for audit payload
            sections_added = len(outline.sections) - len(old_outline.sections)
            insights_added = len(outline.insights) - len(old_outline.insights)

            # Track IDs of added/modified items
            old_section_ids = {s.section_id for s in old_outline.sections}
            new_section_ids = {s.section_id for s in outline.sections}
            section_ids_added = list(new_section_ids - old_section_ids)
            section_ids_modified = list(new_section_ids & old_section_ids)

            old_insight_ids = {i.insight_id for i in old_outline.insights}
            new_insight_ids = {i.insight_id for i in outline.insights}
            insight_ids_added = list(new_insight_ids - old_insight_ids)
            insight_ids_modified = list(new_insight_ids & old_insight_ids)
            insight_ids_removed = list(old_insight_ids - new_insight_ids)

            # Create audit event
            audit_event = AuditEvent(
                action_id=str(uuid.uuid4()),
                report_id=report_id,
                ts=now,
                actor=actor,
                action_type="evolve",
                request_id=request_id,
                payload={
                    "old_title": old_outline.title,
                    "new_title": outline.title,
                    "sections_changed": len(outline.sections)
                    != len(old_outline.sections),
                    "insights_changed": len(outline.insights)
                    != len(old_outline.insights),
                    "sections_added": sections_added,
                    "insights_added": insights_added,
                    "section_ids_added": section_ids_added,
                    "section_ids_modified": section_ids_modified,
                    "insight_ids_added": insight_ids_added,
                    "insight_ids_modified": insight_ids_modified,
                    "insight_ids_removed": insight_ids_removed,
                    "backup_filename": backup_filename,
                    "outline_version": outline.outline_version,
                },
            )
            storage.append_audit_event(audit_event)

        # Update index
        index_entry = IndexEntry(
            report_id=report_id,
            current_title=outline.title,
            created_at=outline.created_at,
            updated_at=now,
            tags=outline.metadata.get("tags", []),
            status="active",
            path=f"by_id/{report_id}",
        )
        self.index.add_entry(index_entry)

    def resolve_report_selector(self, selector: str) -> str:
        """Resolve a report selector (ID or title) to a report ID.

        Args:
            selector: Report ID or title

        Returns:
            Resolved report ID

        Raises:
            ValueError: If selector cannot be resolved
        """
        # First try as direct ID
        try:
            ReportId(selector)
            if self.index.get_entry(selector):
                return selector
        except ValueError:
            pass

        # Try as title
        resolved = self.index.resolve_title(selector)
        if resolved:
            return resolved

        raise ValueError(f"Report not found: {selector}")

    def list_reports(
        self,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List reports with optional filtering.

        Args:
            status: Filter by status
            tags: Filter by tags

        Returns:
            List of report summaries
        """
        entries = self.index.list_entries(status=status, tags=tags)

        reports = []
        for entry in entries:
            reports.append(
                {
                    "id": entry.report_id,
                    "title": entry.current_title,
                    "created_at": entry.created_at,
                    "updated_at": entry.updated_at,
                    "tags": entry.tags,
                    "status": entry.status,
                }
            )

        return reports

    def revert_report(
        self, report_id: str, action_id: str, actor: str = "cli"
    ) -> Dict[str, Any]:
        """Revert a report to a previous state.

        Args:
            report_id: Report identifier
            action_id: Action ID to revert to
            actor: Who is performing the revert

        Returns:
            Dictionary with revert details

        Raises:
            ValueError: If action_id not found or backup missing
        """
        storage = self.global_storage.get_report_storage(report_id)

        with storage.lock():
            # Load audit events
            events = storage.load_audit_events()

            # Find the target action
            target_event = None
            for event in events:
                if event.action_id == action_id:
                    target_event = event
                    break

            if not target_event:
                raise ValueError(
                    f"Action not found: {action_id}. "
                    f"Use 'igloo report history {report_id}' to see available actions."
                )

            # Get backup filename from event payload
            backup_filename = target_event.payload.get("backup_filename")
            if not backup_filename:
                raise ValueError(
                    f"No backup associated with action: {action_id}. "
                    f"Only 'evolve' and 'update' actions can be reverted."
                )

            backup_path = storage.backups_dir / backup_filename
            if not backup_path.exists():
                raise ValueError(
                    f"Backup file missing: {backup_filename}. "
                    f"It may have been deleted or filesystem corruption occurred."
                )

            # Load backup to verify it's valid
            try:
                backup_data = json.loads(backup_path.read_text(encoding="utf-8"))
                backup_outline = Outline(**backup_data)
            except Exception as e:
                raise ValueError(f"Backup file is corrupted: {e}") from e

            # Create backup of current state before reverting
            current_backup_filename = storage._create_backup()

            # Restore backup atomically
            import shutil

            shutil.copy2(backup_path, storage.outline_path)

            # Log revert audit event
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            revert_audit_event = AuditEvent(
                action_id=str(uuid.uuid4()),
                report_id=report_id,
                ts=now,
                actor=actor,
                action_type="revert",
                payload={
                    "reverted_from_action_id": action_id,
                    "reverted_from_action_type": target_event.action_type,
                    "reverted_from_timestamp": target_event.ts,
                    "backup_restored": backup_filename,
                    "current_state_backup": current_backup_filename,
                },
            )
            storage.append_audit_event(revert_audit_event)

            # Update index
            outline = storage.load_outline()
            index_entry = IndexEntry(
                report_id=report_id,
                current_title=outline.title,
                created_at=outline.created_at,
                updated_at=now,
                tags=outline.metadata.get("tags", []),
                status=outline.metadata.get("status", "active"),
                path=f"by_id/{report_id}",
            )
            self.index.add_entry(index_entry)

        return {
            "success": True,
            "reverted_to_action_id": action_id,
            "reverted_to_timestamp": target_event.ts,
            "backup_filename": backup_filename,
        }

    def validate_report(self, report_id: str) -> List[str]:
        """Validate a report's consistency.

        Args:
            report_id: Report identifier

        Returns:
            List of validation errors
        """
        errors = []

        try:
            outline = self.get_report_outline(report_id)
        except ValueError as e:
            errors.append(str(e))
            return errors

        # Validate section references
        insight_ids = {insight.insight_id for insight in outline.insights}
        for section in outline.sections:
            for insight_id in section.insight_ids:
                if insight_id not in insight_ids:
                    errors.append(
                        f"Section '{section.title}' references unknown insight: {insight_id}"
                    )

        # Validate insight references
        section_insight_ids = set()
        for section in outline.sections:
            section_insight_ids.update(section.insight_ids)

        for insight in outline.insights:
            if insight.insight_id not in section_insight_ids:
                errors.append(
                    f"Insight '{insight.summary}' not referenced by any section"
                )

        return errors

    def resolve_insight_datasets(self, report_id: str) -> Dict[str, ResolvedDataset]:
        """Resolve all insight datasets for a report.

        Args:
            report_id: Report identifier

        Returns:
            Dictionary mapping insight IDs to resolved datasets
        """
        outline = self.get_report_outline(report_id)
        resolved_datasets = {}

        for section in outline.sections:
            for insight_id in section.insight_ids:
                insight = outline.get_insight(insight_id)
                for i, dataset_source in enumerate(insight.supporting_queries):
                    try:
                        # Resolve dataset directly with name and source
                        resolved = self.history_index.resolve_dataset(
                            dataset_name=f"{insight_id}_{i}",
                            source=dataset_source,
                        )
                        resolved_datasets[insight_id] = resolved
                    except Exception:
                        # Skip unresolvable datasets for now
                        continue

        return resolved_datasets

    def archive_report(self, report_id: str, actor: str = "cli") -> None:
        """Archive a report (set status to archived).

        Args:
            report_id: Report identifier
            actor: Who is archiving the report
        """
        storage = self.global_storage.get_report_storage(report_id)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        with storage.lock():
            outline = storage.load_outline()
            outline.metadata["status"] = "archived"
            outline.updated_at = now
            backup_filename = storage._save_outline_atomic(outline)

            # Log audit event
            audit_event = AuditEvent(
                action_id=str(uuid.uuid4()),
                report_id=report_id,
                ts=now,
                actor=actor,
                action_type="archive",
                payload={"backup_filename": backup_filename},
            )
            storage.append_audit_event(audit_event)

            # Update index
            index_entry = IndexEntry(
                report_id=report_id,
                current_title=outline.title,
                created_at=outline.created_at,
                updated_at=now,
                tags=outline.metadata.get("tags", []),
                status="archived",
                path=f"by_id/{report_id}",
            )
            self.index.add_entry(index_entry)

    def delete_report(self, report_id: str, actor: str = "cli") -> str:
        """Soft delete - move report to .trash directory.

        Args:
            report_id: Report identifier
            actor: Who is deleting the report

        Returns:
            Path to trash location

        Raises:
            ValueError: If report not found
        """
        storage = self.global_storage.get_report_storage(report_id)

        if not storage.report_dir.exists():
            raise ValueError(f"Report not found: {report_id}")

        # Create trash directory
        trash_dir = self.reports_root / ".trash"
        trash_dir.mkdir(exist_ok=True)

        # Generate trash location with timestamp
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        timestamp_clean = now.replace(":", "").replace("-", "").split(".")[0]
        trash_location = trash_dir / f"{report_id}_{timestamp_clean}"

        # Move report directory to trash
        import shutil

        shutil.move(str(storage.report_dir), str(trash_location))

        # Remove from index
        self.index.remove_entry(report_id)

        # Log delete event in trash location
        trash_storage = ReportStorage(trash_location)
        delete_audit_event = AuditEvent(
            action_id=str(uuid.uuid4()),
            report_id=report_id,
            ts=now,
            actor=actor,
            action_type="delete",
            payload={
                "trash_location": str(trash_location),
                "deleted_at": now,
            },
        )
        trash_storage.append_audit_event(delete_audit_event)

        return str(trash_location)

    def tag_report(
        self,
        report_id: str,
        tags_to_add: Optional[List[str]] = None,
        tags_to_remove: Optional[List[str]] = None,
        actor: str = "cli",
    ) -> None:
        """Add or remove tags from report.

        Args:
            report_id: Report identifier
            tags_to_add: Tags to add (None or empty list to add nothing)
            tags_to_remove: Tags to remove (None or empty list to remove nothing)
            actor: Who is modifying tags
        """
        storage = self.global_storage.get_report_storage(report_id)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        with storage.lock():
            outline = storage.load_outline()
            current_tags = set(outline.metadata.get("tags", []))

            if tags_to_add:
                current_tags.update(tags_to_add)
            if tags_to_remove:
                current_tags.difference_update(tags_to_remove)

            outline.metadata["tags"] = sorted(list(current_tags))
            outline.updated_at = now
            backup_filename = storage._save_outline_atomic(outline)

            # Log audit event
            audit_event = AuditEvent(
                action_id=str(uuid.uuid4()),
                report_id=report_id,
                ts=now,
                actor=actor,
                action_type="tag_update",
                payload={
                    "tags_added": list(tags_to_add) if tags_to_add else [],
                    "tags_removed": list(tags_to_remove) if tags_to_remove else [],
                    "final_tags": outline.metadata["tags"],
                    "backup_filename": backup_filename,
                },
            )
            storage.append_audit_event(audit_event)

            # Update index
            index_entry = IndexEntry(
                report_id=report_id,
                current_title=outline.title,
                created_at=outline.created_at,
                updated_at=now,
                tags=outline.metadata["tags"],
                status=outline.metadata.get("status", "active"),
                path=f"by_id/{report_id}",
            )
            self.index.add_entry(index_entry)

    def fork_report(self, source_id: str, new_title: str, actor: str = "cli") -> str:
        """Fork an existing report to new ID.

        Creates a complete copy of the source report with a new ID,
        preserving all sections, insights, and metadata (except fork tracking).

        Args:
            source_id: Source report ID
            new_title: Title for forked report
            actor: Who is forking the report

        Returns:
            New report ID

        Raises:
            ValueError: If source report not found
        """
        # Verify source exists
        source_storage = self.global_storage.get_report_storage(source_id)
        if not source_storage.report_dir.exists():
            raise ValueError(f"Source report not found: {source_id}")

        # Generate new ID
        new_id = ReportId.new()
        new_storage = self.global_storage.get_report_storage(str(new_id))

        # Copy entire directory structure
        import shutil

        shutil.copytree(source_storage.report_dir, new_storage.report_dir)

        # Load and update outline
        with new_storage.lock():
            outline = new_storage.load_outline()
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # Update IDs and metadata
            outline.report_id = str(new_id)
            outline.title = new_title
            outline.created_at = now
            outline.updated_at = now
            outline.outline_version = 1  # Reset version
            outline.metadata["forked_from"] = source_id
            outline.metadata["forked_at"] = now

            # Save updated outline
            new_storage._save_outline_atomic(outline)

            # Log fork audit event
            fork_audit_event = AuditEvent(
                action_id=str(uuid.uuid4()),
                report_id=str(new_id),
                ts=now,
                actor=actor,
                action_type="fork",
                payload={
                    "source_report_id": source_id,
                    "new_title": new_title,
                },
            )
            new_storage.append_audit_event(fork_audit_event)

        # Register in index
        index_entry = IndexEntry(
            report_id=str(new_id),
            current_title=new_title,
            created_at=now,
            updated_at=now,
            tags=outline.metadata.get("tags", []),
            status="active",
            path=f"by_id/{new_id}",
        )
        self.index.add_entry(index_entry)

        return str(new_id)

    def synthesize_reports(
        self, source_ids: List[str], title: str, actor: str = "cli"
    ) -> str:
        """Create new report combining insights from multiple sources.

        Copies all sections and insights from source reports into a new report.
        Agents can then refine and reorganize the synthesized content.

        Args:
            source_ids: List of source report IDs
            title: Title for synthesized report
            actor: Who is creating the synthesis

        Returns:
            New report ID

        Raises:
            ValueError: If any source report not found
        """
        if not source_ids:
            raise ValueError("At least one source report is required")

        # Verify all sources exist
        for source_id in source_ids:
            storage = self.global_storage.get_report_storage(source_id)
            if not storage.report_dir.exists():
                raise ValueError(f"Source report not found: {source_id}")

        # Create new report (empty)
        new_id = self.create_report(title, tags=["synthesized"], actor=actor)

        # Load all source outlines
        all_sections = []
        all_insights = []
        all_tags = set()

        for source_id in source_ids:
            source_outline = self.get_report_outline(source_id)

            # Copy sections (with updated order to avoid conflicts)
            for i, section in enumerate(source_outline.sections):
                section.order = len(all_sections) + i
                all_sections.append(section)

            # Copy insights
            all_insights.extend(source_outline.insights)

            # Merge tags
            all_tags.update(source_outline.metadata.get("tags", []))

        # Update new report with combined content
        new_outline = self.get_report_outline(new_id)
        new_outline.sections = all_sections
        new_outline.insights = all_insights
        new_outline.metadata["tags"] = sorted(list(all_tags))
        new_outline.metadata["synthesized_from"] = source_ids
        new_outline.metadata["synthesis_note"] = (
            f"Synthesized from {len(source_ids)} source reports. "
            "Sections and insights copied; agent can refine organization."
        )

        self.update_report_outline(new_id, new_outline, actor=actor)

        return new_id

    def _build_citation_map(self, outline: Outline) -> Dict[str, int]:
        """Build stable mapping of execution_id to citation number.

        Scans all insights in the outline and creates a mapping from execution_id
        to citation number (1-indexed, ordered by first appearance).

        Args:
            outline: Report outline to scan

        Returns:
            Dictionary mapping execution_id to citation number
        """
        citation_map: Dict[str, int] = {}
        citation_number = 1

        # Iterate through sections in order, then insights within each section
        for section in sorted(outline.sections, key=lambda s: s.order):
            for insight_id in section.insight_ids:
                try:
                    insight = outline.get_insight(insight_id)
                    # Only use first supporting query for citation
                    if (
                        insight.supporting_queries
                        and len(insight.supporting_queries) > 0
                    ):
                        exec_id = insight.supporting_queries[0].execution_id
                        if exec_id and exec_id not in citation_map:
                            citation_map[exec_id] = citation_number
                            citation_number += 1
                except ValueError:
                    # Skip if insight not found
                    continue

        return citation_map

    def render_report(
        self,
        report_id: str,
        format: str = "html",
        options: Optional[Dict[str, Any]] = None,
        open_browser: bool = False,
        include_preview: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Render a living report to the specified format using Quarto.

        Args:
            report_id: Report identifier
            format: Output format ('html', 'pdf', 'markdown', etc.)
            options: Additional Quarto rendering options (toc, theme, etc.)
            open_browser: Whether to open the rendered output in browser (HTML only)
            include_preview: Whether to include a truncated preview in response
            dry_run: If True, only generate QMD file without running Quarto

        Returns:
            Dictionary with render result containing:
            - status: 'success', 'quarto_missing', 'validation_failed', or 'render_failed'
            - report_id: Resolved report ID
            - output: Dict with format, output_path, assets_dir (if applicable)
            - preview: Truncated content string (if include_preview=True)
            - warnings: List of warning messages
            - audit_action_id: ID of the audit event logged

        Raises:
            ValueError: If report not found or invalid
        """
        options = options or {}

        try:
            # Resolve report ID
            resolved_id = self.resolve_report_selector(report_id)
        except ValueError as e:
            return {
                "status": "validation_failed",
                "report_id": report_id,
                "validation_errors": [str(e)],
            }

        # Validate report
        validation_errors = self.validate_report(resolved_id)
        if validation_errors:
            return {
                "status": "validation_failed",
                "report_id": resolved_id,
                "validation_errors": validation_errors,
            }

        # Detect Quarto (unless dry run)
        renderer = None
        if not dry_run:
            try:
                renderer = QuartoRenderer.detect()
            except QuartoNotFoundError as e:
                return {
                    "status": "quarto_missing",
                    "report_id": resolved_id,
                    "error": str(e),
                }

        # Load report data
        try:
            outline = self.get_report_outline(resolved_id)
            storage = self.global_storage.get_report_storage(resolved_id)
            report_dir = storage.report_dir

            # Load dataset sources if they exist
            datasets = {}
            dataset_sources_path = report_dir / "dataset_sources.json"
            if dataset_sources_path.exists():
                with open(dataset_sources_path, "r", encoding="utf-8") as f:
                    datasets = json.load(f)

            # Resolve query history for traceability
            query_provenance = {}
            try:
                from .models import DatasetSource

                for insight in outline.insights:
                    for query in insight.supporting_queries:
                        if query.execution_id:
                            try:
                                # Convert to DatasetSource for resolution
                                source = DatasetSource(
                                    execution_id=query.execution_id,
                                    sql_sha256=query.sql_sha256,
                                )
                                history_record = (
                                    self.history_index._resolve_history_record(source)
                                )
                                if history_record:
                                    query_provenance[query.execution_id] = {
                                        "execution_id": query.execution_id,
                                        "timestamp": history_record.get("timestamp")
                                        or history_record.get("ts"),
                                        "duration_ms": history_record.get(
                                            "duration_ms"
                                        ),
                                        "rowcount": history_record.get("rowcount"),
                                        "status": history_record.get("status"),
                                        "statement_preview": history_record.get(
                                            "statement_preview"
                                        ),
                                        "sql_sha256": history_record.get("sql_sha256")
                                        or query.sql_sha256,
                                    }
                            except Exception:
                                # Gracefully handle resolution failures
                                pass
            except Exception:
                # Don't fail rendering if provenance resolution fails
                pass

            # Build citation map for analyst reports
            citation_map = {}
            citation_details = {}
            if outline.metadata.get("template") == "analyst_v1":
                citation_map = self._build_citation_map(outline)
                # Build citation_details dict with provenance info for appendix
                for exec_id, citation_num in citation_map.items():
                    if exec_id in query_provenance:
                        citation_details[exec_id] = query_provenance[exec_id]
                    else:
                        # Fallback if provenance not found
                        citation_details[exec_id] = {
                            "execution_id": exec_id,
                            "timestamp": None,
                        }

        except Exception as e:
            return {
                "status": "render_failed",
                "report_id": resolved_id,
                "error": f"Failed to load report data: {e}",
            }

        # Render the report or generate QMD only (dry run)
        if dry_run:
            # Dry run: generate QMD file only
            try:
                # Prepare render hints with query provenance and citations
                render_hints = outline.metadata.get("render_hints", {})
                if not isinstance(render_hints, dict):
                    render_hints = {}
                render_hints["query_provenance"] = query_provenance
                render_hints["citation_map"] = citation_map
                render_hints["citation_details"] = citation_details

                renderer = (
                    renderer or QuartoRenderer()
                )  # Create instance for QMD generation
                renderer._generate_qmd_file(
                    report_dir, format, options or {}, outline, datasets, render_hints
                )
                result = RenderResult(
                    output_paths=[],
                    stdout="Dry run: QMD file generated successfully",
                    stderr="",
                    warnings=["Dry run mode - Quarto render was skipped"],
                )
            except Exception as e:
                return {
                    "status": "render_failed",
                    "report_id": resolved_id,
                    "error": f"QMD generation failed: {e}",
                }
        else:
            # Normal render
            try:
                # Prepare render hints with query provenance and citations
                render_hints = outline.metadata.get("render_hints", {})
                if not isinstance(render_hints, dict):
                    render_hints = {}
                render_hints["query_provenance"] = query_provenance
                render_hints["citation_map"] = citation_map
                render_hints["citation_details"] = citation_details

                result = renderer.render(
                    report_dir=report_dir,
                    format=format,
                    options=options,
                    outline=outline,
                    datasets=datasets,
                    hints=render_hints,
                )
            except Exception as e:
                return {
                    "status": "render_failed",
                    "report_id": resolved_id,
                    "error": f"Rendering failed: {e}",
                }

        # Create audit event
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        outline_sha256 = hashlib.sha256(
            json.dumps(outline.model_dump(), sort_keys=True).encode()
        ).hexdigest()

        audit_event = AuditEvent(
            action_id=str(uuid.uuid4()),
            report_id=resolved_id,
            ts=now,
            actor="agent",
            action_type="render",
            payload={
                "format": format,
                "output_files": result.output_paths,
                "quarto_version": renderer.version,
                "outline_sha256": outline_sha256,
                "options": options,
            },
        )

        # Save audit event
        storage = self.global_storage.get_report_storage(resolved_id)
        with storage.lock():
            storage.append_audit_event(audit_event)

        # Prepare response
        response = {
            "status": "success",
            "report_id": resolved_id,
            "output": {
                "format": format,
                "output_path": result.output_paths[0] if result.output_paths else None,
                "assets_dir": (
                    str(report_dir / "_files")
                    if format == "html" and (report_dir / "_files").exists()
                    else None
                ),
            },
            "warnings": result.warnings,
            "audit_action_id": audit_event.action_id,
        }

        # Generate preview if requested
        if include_preview and result.output_paths:
            try:
                preview = self._generate_preview(result.output_paths[0])
                if preview:
                    response["preview"] = preview
            except Exception:
                # Don't fail the render if preview generation fails
                pass

        # Open in browser if requested and it's HTML
        if open_browser and format == "html" and result.output_paths:
            try:
                webbrowser.open(f"file://{result.output_paths[0]}")
            except Exception:
                # Don't fail if browser opening fails
                pass

        return response

    def _generate_preview(
        self, output_path: str, max_chars: int = 2000
    ) -> Optional[str]:
        """Generate a truncated preview of the rendered output.

        Args:
            output_path: Path to the rendered output file
            max_chars: Maximum characters to include in preview

        Returns:
            Truncated preview string or None if generation fails
        """
        try:
            path = Path(output_path)
            if not path.exists():
                return None

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Truncate and add indicator if needed
            if len(content) > max_chars:
                content = content[:max_chars] + "...\n\n[Content truncated]"

            return content

        except Exception:
            return None


__all__ = ["ReportService"]
