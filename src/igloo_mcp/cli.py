from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from .config import get_config
from .living_reports.service import ReportService
from .mcp.tools.create_report import VALID_TEMPLATES as REPORT_TEMPLATES
from .query_optimizer import optimize_execution


def _command_query_optimize(args: argparse.Namespace) -> int:
    try:
        report = optimize_execution(
            execution_id=args.execution_id,
            history_path=args.history,
        )
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"optimization failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    findings = report.get("findings") or []
    print(
        "Execution: {exec_id}\nStatus: {status}\nDuration: {duration} ms\nRowcount: {rowcount}".format(
            exec_id=report.get("execution_id"),
            status=report.get("status"),
            duration=report.get("duration_ms"),
            rowcount=report.get("rowcount"),
        )
    )
    if report.get("objects"):
        objs = ", ".join(
            filter(
                None,
                [
                    obj.get("name") if isinstance(obj, dict) else None
                    for obj in report["objects"]
                ],
            )
        )
        if objs:
            print(f"Objects: {objs}")
    print("Findings:")
    for finding in findings:
        msg = finding.get("message")
        level = finding.get("level", "info").upper()
        detail = finding.get("detail")
        print(f" - [{level}] {msg}")
        if detail:
            print(f"   {detail}")
    return 0


# Report command handlers


def _command_report_create(args: argparse.Namespace) -> int:
    """Create a new living report."""
    try:
        service = ReportService()
        report_id = service.create_report(
            args.title, template=args.template, tags=args.tags
        )
        print(f"Created report '{args.title}' with ID: {report_id}")
        if args.template != "default":
            print(f"Using template: {args.template}")
        return 0
    except ValueError as e:
        print(f"Failed to create report: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def _command_report_evolve(args: argparse.Namespace) -> int:
    """Evolve a report with LLM assistance."""
    try:
        from .mcp.tools.evolve_report import EvolveReportTool

        config = get_config()
        service = ReportService()

        # For now, call the tool directly (would normally go through MCP)
        tool = EvolveReportTool(config, service)

        # CLI interface currently supports discovery mode and explicit changes.
        # If proposed_changes is not provided, default to empty dict which
        # triggers structure discovery in dry-run mode.
        proposed_changes = getattr(args, "proposed_changes", None) or {}

        import asyncio

        result = asyncio.run(
            tool.execute(
                report_selector=args.selector,
                instruction=args.instruction,
                proposed_changes=proposed_changes,
                dry_run=args.dry_run,
            )
        )

        if result["status"] == "validation_failed":
            print("Validation failed:", file=sys.stderr)
            for issue in result["validation_issues"]:
                print(f"  - {issue}", file=sys.stderr)
            return 1
        elif result["status"] == "dry_run_success":
            print("Dry run successful - changes would be applied")
            return 0
        elif result["status"] == "success":
            print(f"Report evolved successfully: {result['report_id']}")
            return 0
        else:
            print(f"Unexpected result: {result}", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"Failed to evolve report: {e}", file=sys.stderr)
        return 1


def _command_report_render(args: argparse.Namespace) -> int:
    """Render report to final format."""
    try:
        service = ReportService()

        result = service.render_report(
            report_id=args.selector,
            format=args.format,
            options=args.options,
            open_browser=args.open,
            dry_run=args.dry_run,
        )

        if result["status"] == "success":
            output_path = result.get("output", {}).get("output_path")
            if output_path:
                print(f"✓ Report rendered successfully: {output_path}")
            else:
                print("✓ QMD file generated successfully (dry run)")

            if result.get("warnings"):
                print("⚠️  Warnings:")
                for warning in result["warnings"]:
                    print(f"   - {warning}")

        elif result["status"] == "quarto_missing":
            print(
                "❌ Quarto not found. Install from https://quarto.org/docs/get-started/",
                file=sys.stderr,
            )
            print("   Or set IGLOO_QUARTO_BIN environment variable.", file=sys.stderr)
            return 1

        elif result["status"] == "validation_failed":
            print("❌ Report validation failed:", file=sys.stderr)
            for error in result.get("validation_errors", []):
                print(f"   - {error}", file=sys.stderr)
            return 1

        elif result["status"] == "render_failed":
            print(
                f"❌ Rendering failed: {result.get('error', 'Unknown error')}",
                file=sys.stderr,
            )
            return 1

        return 0

    except Exception as e:
        print(f"Failed to render report: {e}", file=sys.stderr)
        return 1


def _command_report_revert(args: argparse.Namespace) -> int:
    """Revert report to previous state."""
    try:
        service = ReportService()
        report_id = service.resolve_report_selector(args.selector)

        service.revert_report(report_id, args.action_id)
        print(f"Reverted report {report_id} to action {args.action_id}")
        return 0

    except Exception as e:
        print(f"Failed to revert report: {e}", file=sys.stderr)
        return 1


def _command_report_list(args: argparse.Namespace) -> int:
    """List reports."""
    try:
        service = ReportService()
        reports = service.list_reports(status=args.status, tags=args.tags)

        if not reports:
            print("No reports found")
            return 0

        print(
            f"{'ID':<36} {'Title':<30} {'Created':<20} {'Updated':<20} {'Status':<8} {'Tags'}"
        )
        print("-" * 120)

        for report in reports:
            tags_str = ", ".join(report.get("tags", []))
            print(
                f"{report['id']:<36} {report['title']:<30} {report['created_at']:<20} {report['updated_at']:<20} {report['status']:<8} {tags_str}"
            )

        return 0

    except Exception as e:
        print(f"Failed to list reports: {e}", file=sys.stderr)
        return 1


def _command_report_archive(args: argparse.Namespace) -> int:
    """Archive a report."""
    try:
        service = ReportService()
        report_id = service.resolve_report_selector(args.selector)
        service.archive_report(report_id, actor="cli")
        print(f"✓ Archived report: {report_id}")
        return 0
    except Exception as e:
        print(f"❌ Failed to archive report: {e}", file=sys.stderr)
        return 1


def _command_report_delete(args: argparse.Namespace) -> int:
    """Delete a report (move to .trash)."""
    try:
        service = ReportService()
        report_id = service.resolve_report_selector(args.selector)

        if not args.force:
            # Confirmation prompt
            print(f"⚠️  This will move report {report_id} to .trash/")
            response = input("Continue? (y/N): ")
            if response.lower() != "y":
                print("Cancelled.")
                return 0

        trash_location = service.delete_report(report_id, actor="cli")
        print(f"✓ Deleted report: {report_id}")
        print(f"  Location: {trash_location}")
        print("  (Can be manually restored from .trash/ directory)")
        return 0
    except Exception as e:
        print(f"❌ Failed to delete report: {e}", file=sys.stderr)
        return 1


def _command_report_tag(args: argparse.Namespace) -> int:
    """Modify report tags."""
    try:
        service = ReportService()
        report_id = service.resolve_report_selector(args.selector)

        service.tag_report(
            report_id,
            tags_to_add=args.add,
            tags_to_remove=args.remove,
            actor="cli",
        )

        # Show current tags
        outline = service.get_report_outline(report_id)
        tags = outline.metadata.get("tags", [])
        print(f"✓ Updated tags for report: {report_id}")
        print(f"  Current tags: {', '.join(tags) if tags else '(none)'}")
        return 0
    except Exception as e:
        print(f"❌ Failed to update tags: {e}", file=sys.stderr)
        return 1


def _command_report_fork(args: argparse.Namespace) -> int:
    """Fork an existing report."""
    try:
        service = ReportService()
        source_id = service.resolve_report_selector(args.source_selector)

        new_id = service.fork_report(source_id, args.new_title, actor="cli")

        print("✓ Forked report successfully")
        print(f"  Source: {source_id}")
        print(f"  New report: {new_id}")
        print(f"  Title: {args.new_title}")
        return 0
    except Exception as e:
        print(f"❌ Failed to fork report: {e}", file=sys.stderr)
        return 1


def _command_report_synthesize(args: argparse.Namespace) -> int:
    """Synthesize multiple reports into one."""
    try:
        service = ReportService()

        # Resolve all source selectors
        source_ids = []
        for selector in args.source_selectors:
            report_id = service.resolve_report_selector(selector)
            source_ids.append(report_id)

        new_id = service.synthesize_reports(source_ids, args.title, actor="cli")

        print("✓ Synthesized report successfully")
        print(f"  Sources: {', '.join(source_ids)}")
        print(f"  New report: {new_id}")
        print(f"  Title: {args.title}")
        return 0
    except Exception as e:
        print(f"❌ Failed to synthesize reports: {e}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="igloo administrative CLI utilities for power users and system administrators"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    query_parser = subparsers.add_parser("query", help="Query tooling")
    query_sub = query_parser.add_subparsers(dest="query_command", required=True)

    optimize_parser = query_sub.add_parser(
        "optimize", help="Analyze a recorded query execution"
    )
    optimize_parser.add_argument(
        "--execution-id",
        dest="execution_id",
        default=None,
        help="Execution ID from execute_query (defaults to latest)",
    )
    optimize_parser.add_argument(
        "--history",
        default=None,
        help="Optional override for query history path",
    )
    optimize_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    optimize_parser.set_defaults(func=_command_query_optimize)

    # Report subcommand
    report_parser = subparsers.add_parser(
        "report",
        help="Administrative living reports management (MCP tools are primary for development)",
    )
    report_sub = report_parser.add_subparsers(dest="report_command", required=True)

    # report create
    create_parser = report_sub.add_parser("create", help="Create a new living report")
    create_parser.add_argument("title", help="Report title")
    create_parser.add_argument(
        "--template",
        choices=list(REPORT_TEMPLATES),
        default="default",
        help="Report template to use",
    )
    create_parser.add_argument(
        "--tags",
        nargs="*",
        default=[],
        help="Optional tags for the report",
    )
    create_parser.set_defaults(func=_command_report_create)

    # report evolve
    evolve_parser = report_sub.add_parser(
        "evolve", help="Evolve a report with LLM assistance"
    )
    evolve_parser.add_argument("selector", help="Report ID or title")
    evolve_parser.add_argument("instruction", help="Evolution instruction")
    evolve_parser.add_argument(
        "--proposed-changes",
        type=json.loads,
        default=None,
        help="Structured proposed changes as JSON string. "
        "Omit (or use with --dry-run) to discover the current outline structure.",
    )
    evolve_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate changes without applying them",
    )
    evolve_parser.set_defaults(func=_command_report_evolve)

    # report render
    render_parser = report_sub.add_parser(
        "render", help="Render report to final format"
    )
    render_parser.add_argument("selector", help="Report ID or title")
    render_parser.add_argument(
        "--format",
        choices=["markdown", "html", "pdf"],
        default="html",
        help="Output format",
    )
    render_parser.add_argument(
        "--open",
        action="store_true",
        help="Open rendered output in browser (HTML only)",
    )
    render_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate QMD file only, skip Quarto rendering",
    )
    render_parser.add_argument(
        "--options",
        type=json.loads,
        default=None,
        help='Additional Quarto options as JSON string (e.g., \'{"toc": true, "theme": "default"}\')',
    )
    render_parser.set_defaults(func=_command_report_render)

    # report revert
    revert_parser = report_sub.add_parser(
        "revert", help="Revert report to previous state"
    )
    revert_parser.add_argument("selector", help="Report ID or title")
    revert_parser.add_argument("action_id", help="Action ID to revert to")
    revert_parser.set_defaults(func=_command_report_revert)

    # report list
    list_parser = report_sub.add_parser("list", help="List reports")
    list_parser.add_argument(
        "--status",
        choices=["active", "archived"],
        help="Filter by status",
    )
    list_parser.add_argument(
        "--tags",
        nargs="*",
        help="Filter by tags",
    )
    list_parser.set_defaults(func=_command_report_list)

    # report archive
    archive_parser = report_sub.add_parser("archive", help="Archive a report")
    archive_parser.add_argument("selector", help="Report ID or title")
    archive_parser.set_defaults(func=_command_report_archive)

    # report delete
    delete_parser = report_sub.add_parser(
        "delete", help="Delete a report (move to .trash)"
    )
    delete_parser.add_argument("selector", help="Report ID or title")
    delete_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt",
    )
    delete_parser.set_defaults(func=_command_report_delete)

    # report tag
    tag_parser = report_sub.add_parser("tag", help="Modify report tags")
    tag_parser.add_argument("selector", help="Report ID or title")
    tag_parser.add_argument(
        "--add",
        nargs="*",
        default=[],
        help="Tags to add",
    )
    tag_parser.add_argument(
        "--remove",
        nargs="*",
        default=[],
        help="Tags to remove",
    )
    tag_parser.set_defaults(func=_command_report_tag)

    # report fork
    fork_parser = report_sub.add_parser("fork", help="Fork an existing report")
    fork_parser.add_argument("source_selector", help="Source report ID or title")
    fork_parser.add_argument("new_title", help="Title for forked report")
    fork_parser.set_defaults(func=_command_report_fork)

    # report synthesize
    synthesize_parser = report_sub.add_parser(
        "synthesize", help="Synthesize multiple reports into one"
    )
    synthesize_parser.add_argument(
        "source_selectors",
        nargs="+",
        help="Source report IDs or titles",
    )
    synthesize_parser.add_argument(
        "--title",
        required=True,
        help="Title for synthesized report",
    )
    synthesize_parser.set_defaults(func=_command_report_synthesize)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "func", None)
    if not handler:
        parser.print_help()
        return 2
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
