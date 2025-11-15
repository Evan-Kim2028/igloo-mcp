from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="igloo CLI utilities")
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
