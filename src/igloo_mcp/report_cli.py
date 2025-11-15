from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import yaml  # type: ignore[import-untyped]

from .path_utils import find_repo_root, resolve_history_path
from .reporting.builder import LintIssue, build_report, lint_report
from .reporting.history_index import HistoryIndex
from .reporting.manifest import (
    DatasetRef,
    DatasetSource,
    ReportManifest,
    ReportOutput,
    TemplatesConfig,
)


def _resolve_manifest_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    repo_root = find_repo_root()
    return (repo_root / path).resolve()


def _command_build(args: argparse.Namespace) -> int:
    manifest_path = _resolve_manifest_path(args.manifest)

    try:
        result = build_report(
            manifest_path,
            output_name=args.output_name,
            refresh=args.refresh,
        )
    except Exception as exc:  # pragma: no cover - error surface
        print(f"report build failed: {exc}", file=sys.stderr)
        return 1

    body = result.get("body", "")
    fmt = result.get("format", "markdown")

    # Optional format override (html simply wraps markdown)
    effective_format = args.format or fmt
    if effective_format == "html" and fmt == "markdown":
        body = f"<html><body><pre>\n{body}\n</pre></body></html>\n"

    # Determine output path: explicit flag wins; otherwise use manifest outputs
    output_path: Path
    if args.output:
        output_path = _resolve_manifest_path(args.output)
    else:
        # Re-load manifest cheaply to get output metadata
        from .reporting.manifest import load_manifest

        manifest = load_manifest(manifest_path)
        selected = None
        if args.output_name is not None:
            for candidate in manifest.outputs:
                if candidate.name == args.output_name:
                    selected = candidate
                    break
        if selected is None:
            if not manifest.outputs:
                print(
                    "report build: manifest defines no outputs and --output was not provided",
                    file=sys.stderr,
                )
                return 1
            selected = manifest.outputs[0]
        output_path = _resolve_manifest_path(selected.path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(body, encoding="utf-8")
    print(f"Wrote report to {output_path} ({effective_format})")
    return 0


def _command_lint(args: argparse.Namespace) -> int:
    manifest_path = _resolve_manifest_path(args.manifest)
    issues: List[LintIssue] = lint_report(manifest_path)
    if not issues:
        print("Manifest lint passed: no issues found")
        return 0
    for issue in issues:
        prefix = issue.code
        if issue.dataset_name:
            prefix += f"[{issue.dataset_name}]"
        print(f"{prefix}: {issue.message}", file=sys.stderr)
        if issue.detail:
            print(f"  detail: {issue.detail}", file=sys.stderr)
    return 1


def _command_scaffold(args: argparse.Namespace) -> int:
    manifest_path = _resolve_manifest_path(args.manifest)
    repo_root = find_repo_root()

    try:
        history_path = resolve_history_path()
    except Exception as exc:  # pragma: no cover - rare
        print(f"Failed to resolve history path: {exc}", file=sys.stderr)
        return 1

    index = HistoryIndex(history_path)
    records = index.records
    # Use the latest few entries to seed datasets
    records_sorted = sorted(records, key=lambda r: r.get("ts") or 0.0)
    recent = records_sorted[-args.limit :] if args.limit and records_sorted else []

    datasets: List[DatasetRef] = []
    for idx, record in enumerate(recent, start=1):
        exec_id = record.get("execution_id")
        sha = record.get("sql_sha256")
        artifacts = record.get("artifacts") or {}
        cache_manifest = artifacts.get("cache_manifest") or record.get("cache_manifest")
        source = DatasetSource(
            execution_id=str(exec_id) if exec_id else None,
            sql_sha256=str(sha) if sha else None,
            cache_manifest=str(cache_manifest) if cache_manifest else None,
        )
        description = None
        if record.get("reason"):
            description = str(record["reason"])
        datasets.append(
            DatasetRef(
                name=f"dataset_{idx}",
                description=description,
                source=source,
            )
        )

    report_id = manifest_path.stem or "report"
    manifest = ReportManifest(
        id=report_id,
        title=f"Report {report_id}",
        templates=TemplatesConfig(main="templates/report.md"),
        datasets=datasets,
        outputs=[
            ReportOutput(
                name="default",
                format="markdown",
                path=f"reports/{report_id}.md",
            )
        ],
    )

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(manifest.model_dump(), fh, sort_keys=False)

    rel_path = manifest_path
    try:
        rel_path = manifest_path.relative_to(repo_root)
    except Exception:
        pass
    print(f"Scaffolded manifest at {rel_path}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manifest-driven reporting utilities for igloo-mcp",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser(
        "build",
        help="Render a report manifest into an output file",
    )
    build_parser.add_argument(
        "--manifest",
        default="report.yaml",
        help="Path to report manifest (default: report.yaml)",
    )
    build_parser.add_argument(
        "--output",
        default=None,
        help="Explicit output path (overrides manifest.outputs)",
    )
    build_parser.add_argument(
        "--output-name",
        default=None,
        help="Named output from manifest.outputs to build",
    )
    build_parser.add_argument(
        "--format",
        choices=["markdown", "html", "json"],
        default=None,
        help="Override output format (html wraps markdown)",
    )
    build_parser.add_argument(
        "--refresh",
        action="store_true",
        help="Reserved flag; currently ignored (no re-execution)",
    )
    build_parser.set_defaults(func=_command_build)

    lint_parser = subparsers.add_parser(
        "lint",
        help="Validate a manifest and dataset bindings",
    )
    lint_parser.add_argument(
        "--manifest",
        default="report.yaml",
        help="Path to report manifest (default: report.yaml)",
    )
    lint_parser.set_defaults(func=_command_lint)

    scaffold_parser = subparsers.add_parser(
        "scaffold",
        help="Create a skeleton manifest from recent history entries",
    )
    scaffold_parser.add_argument(
        "--manifest",
        default="report.yaml",
        help="Path where the scaffolded manifest should be written",
    )
    scaffold_parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Number of recent history entries to scaffold into datasets",
    )
    scaffold_parser.set_defaults(func=_command_scaffold)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1
    return int(func(args))


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
