"""Example: Build a lineage cache and export focused lineage views for the sample dataset.

Usage:
  # 1) Set up the sample dataset first
  uv run python examples/sample_data/setup_sample_data.py

  # 2) Build a catalog for the sample data using MCP tools
  # Use your MCP client to ask: "Build a catalog for DEFI_SAMPLE_DB"

  # 3) Run this example to rebuild the lineage cache and emit JSON/HTML outputs
  uv run python examples/run_depgraph.py \
    --catalog-dir ./sample_data_catalog \
    --object DEFI_SAMPLE_DB.PROCESSED.DEX_TRADES_STABLE \
    --direction both \
    --depth 2

  # Try other sample objects:
  # --object DEFI_SAMPLE_DB.ANALYTICS.FILTERED_DEX_TRADES_VIEW
  # --object DEFI_SAMPLE_DB.ANALYTICS.BTC_DEX_TRADES_USD_DT
  # --object DEFI_SAMPLE_DB.PROCESSED.COIN_INFO
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from igloo_mcp.lineage import LineageQueryService
from igloo_mcp.lineage.queries import LineageQueryResult


def build_cache(service: LineageQueryService) -> None:
    """Ensure the lineage cache is populated from the catalog."""
    console_prefix = "[lineage-example]"
    print(f"{console_prefix} Building lineage cache at {service.cache_dir}...")
    service.build(force=True)
    print(f"{console_prefix} Cache ready: {service.graph_path}")


def export_outputs(
    result: LineageQueryResult,
    output_dir: Path,
    object_key: str,
    direction: str,
) -> None:
    """Write JSON and HTML representations of the lineage subgraph."""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{direction}_{object_key.replace('.', '_')}.json"
    json_payload = LineageQueryService.to_json(result.graph)
    json_path.write_text(json.dumps(json_payload, indent=2))
    print(f"[lineage-example] JSON saved to {json_path}")

    html_path = output_dir / f"{direction}_{object_key.replace('.', '_')}.html"
    LineageQueryService.to_html(
        result.graph,
        html_path,
        title=f"{direction.title()} lineage for {object_key}",
        root_key=object_key,
    )
    print(f"[lineage-example] HTML saved to {html_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lineage query example")
    parser.add_argument(
        "--catalog-dir",
        type=Path,
        default=Path("./sample_data_catalog"),
        help="Path to a catalog directory containing JSON/JSONL exports (default: sample data catalog)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("./sample_lineage"),
        help="Directory to store lineage cache artifacts",
    )
    parser.add_argument(
        "--object",
        default="DEFI_SAMPLE_DB.PROCESSED.DEX_TRADES_STABLE",
        help="Fully qualified object name (default: main fact table from sample data)",
    )
    parser.add_argument(
        "--direction",
        choices=["upstream", "downstream", "both"],
        default="both",
        help="Traversal direction for the lineage query",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        help="Traversal depth (0 = only the object itself, default: 2 for sample data)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./sample_lineage_outputs"),
        help="Directory to place JSON/HTML lineage artifacts",
    )
    args = parser.parse_args()

    if not args.catalog_dir.exists():
        print(
            f"[lineage-example] Catalog directory {args.catalog_dir} not found. Run the following commands first:",
        )
        print("  uv run python examples/sample_data/setup_sample_data.py")
        print(f"  # Use MCP client to build catalog for DEFI_SAMPLE_DB to {args.catalog_dir}")
        sys.exit(1)

    service = LineageQueryService(args.catalog_dir, args.cache_dir)
    build_cache(service)

    try:
        result = service.object_subgraph(
            args.object,
            direction=args.direction,
            depth=args.depth,
        )
    except KeyError as exc:
        print(f"[lineage-example] {exc}")
        sys.exit(1)

    export_outputs(result, args.output_dir, args.object, args.direction)


if __name__ == "__main__":
    main()
