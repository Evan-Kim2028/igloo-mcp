#!/usr/bin/env python3
"""Schema compatibility validation script.

Detects breaking changes in living reports schemas by comparing field names
against known constants. Run in CI to catch schema changes before they break tests.

Usage:
    python scripts/validate_schema_compatibility.py

Exit codes:
    0: All schemas compatible
    1: Breaking changes detected
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from igloo_mcp.living_reports.schema_constants import (
    InsightChangeFields,
    ProposedChangesFields,
    SectionChangeFields,
)


def extract_pydantic_fields(model_class) -> set[str]:
    """Extract field names from a Pydantic model.

    Args:
        model_class: Pydantic model class

    Returns:
        Set of field names
    """
    if hasattr(model_class, "model_fields"):
        return set(model_class.model_fields.keys())
    elif hasattr(model_class, "__fields__"):
        # Pydantic v1 compatibility
        return set(model_class.__fields__.keys())
    return set()


def validate_schema_fields(schema_class, constants_class, schema_name: str) -> list[str]:
    """Validate that schema fields match constants.

    Args:
        schema_class: Pydantic schema class
        constants_class: Constants class with field names
        schema_name: Human-readable schema name

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Get actual schema fields
    actual_fields = extract_pydantic_fields(schema_class)

    # Get expected fields from constants
    expected_fields = {
        value for key, value in vars(constants_class).items() if not key.startswith("_") and isinstance(value, str)
    }

    # Check for missing fields (in constants but not in schema)
    missing = expected_fields - actual_fields
    if missing:
        errors.append(f"{schema_name}: Fields in constants but missing from schema: {missing}")

    # Check for unexpected fields (in schema but not in constants)
    unexpected = actual_fields - expected_fields
    if unexpected:
        errors.append(f"{schema_name}: Fields in schema but missing from constants: {unexpected}")

    return errors


def main() -> int:
    """Run schema compatibility validation.

    Returns:
        Exit code (0 = success, 1 = errors found)
    """
    print("🔍 Validating schema compatibility...")
    print()

    all_errors = []

    # Import schema classes
    try:
        from igloo_mcp.living_reports.changes_schema import (
            InsightChange,
            ProposedChanges,
            SectionChange,
        )
    except ImportError as e:
        print(f"❌ Failed to import schema classes: {e}")
        return 1

    # Validate each schema
    schemas_to_validate = [
        (ProposedChanges, ProposedChangesFields, "ProposedChanges"),
        (SectionChange, SectionChangeFields, "SectionChange"),
        (InsightChange, InsightChangeFields, "InsightChange"),
    ]

    for schema_class, constants_class, name in schemas_to_validate:
        print(f"Checking {name}...")
        errors = validate_schema_fields(schema_class, constants_class, name)
        if errors:
            all_errors.extend(errors)
            for error in errors:
                print(f"  ⚠️  {error}")
        else:
            print(f"  ✅ {name} schema is compatible")

    print()

    if all_errors:
        print("❌ Schema compatibility validation FAILED")
        print()
        print("Breaking changes detected! Update schema_constants.py to match:")
        for error in all_errors:
            print(f"  - {error}")
        print()
        print("This prevents tests from breaking when schema fields change.")
        return 1

    print("✅ All schemas are compatible with constants")
    print()
    print("Schema validation passed. No breaking changes detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
