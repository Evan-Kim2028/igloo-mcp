#!/usr/bin/env python3
"""Check coverage for critical modules.

Critical modules (tools, services, validation) must have >= 90% coverage.
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_coverage_xml(coverage_file: Path) -> dict[str, float]:
    """Parse coverage.xml and extract per-file coverage."""
    tree = ET.parse(coverage_file)  # noqa: S314 - Parsing trusted local coverage.xml from pytest-cov
    root = tree.getroot()

    coverage_by_file = {}
    for package in root.findall(".//package"):
        for cls in package.findall("classes/class"):
            filename = cls.get("filename", "")
            lines = cls.find("lines")
            if lines is not None:
                total = len(list(lines.findall("line")))
                covered = len([line_elem for line_elem in lines.findall("line") if line_elem.get("hits", "0") != "0"])
                coverage_pct = (covered / total * 100) if total > 0 else 100.0
                coverage_by_file[filename] = coverage_pct

    return coverage_by_file


def check_critical_modules(
    coverage_by_file: dict[str, float], critical_modules: list[str], min_coverage: float
) -> list[str]:
    """Check if critical modules meet minimum coverage."""
    violations = []

    for file_path, coverage in coverage_by_file.items():
        for critical_module in critical_modules:
            if critical_module in file_path and coverage < min_coverage:
                violations.append(f"{file_path}: {coverage:.1f}% (required: {min_coverage}%)")
                break

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Check critical module coverage")
    parser.add_argument("--coverage-file", type=Path, required=True, help="Path to coverage.xml")
    parser.add_argument("--min-coverage", type=float, required=True, help="Minimum coverage percentage")
    parser.add_argument("--critical-modules", nargs="+", required=True, help="Critical module patterns")

    args = parser.parse_args()

    if not args.coverage_file.exists():
        print(f"❌ Coverage file not found: {args.coverage_file}")
        return 1

    coverage_by_file = parse_coverage_xml(args.coverage_file)
    violations = check_critical_modules(coverage_by_file, args.critical_modules, args.min_coverage)

    if violations:
        print(f"❌ Critical modules below {args.min_coverage}% coverage:")
        for v in violations:
            print(f"   {v}")
        return 1

    print(f"✅ All critical modules meet {args.min_coverage}% coverage requirement")
    return 0


if __name__ == "__main__":
    sys.exit(main())
