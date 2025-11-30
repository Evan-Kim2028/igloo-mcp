#!/usr/bin/env python3
"""Convert relative imports to absolute imports.

This script converts relative imports like:
    from ..path_utils import resolve_catalog_path

To absolute imports like:
    from igloo_mcp.path_utils import resolve_catalog_path
"""

import re
from pathlib import Path


def fix_file(filepath: Path) -> tuple[int, list[str]]:
    """Fix relative imports in a single file.

    Returns:
        Tuple of (number_of_changes, list_of_changes)
    """
    content = filepath.read_text()
    original_content = content
    changes = []

    # Get the package path from the file location
    # e.g., src/igloo_mcp/catalog/catalog_service.py -> igloo_mcp.catalog
    parts = filepath.parts
    src_idx = parts.index('src')
    package_parts = parts[src_idx + 1:-1]  # Exclude 'src' and filename
    # Note: current_package not needed, we build absolute paths directly

    # Pattern 1: from .. import X or from ..module import X
    # Count dots to determine how many levels up
    lines = content.split("\n")
    new_lines = []

    for line in lines:
        # Match: from .. import X  or  from ..X import Y
        match = re.match(r"^(\s*)from (\.\.+)([a-zA-Z_][a-zA-Z0-9_]*)?(\.\w+)* import (.+)$", line)

        if match:
            indent = match.group(1)
            dots = match.group(2)
            first_module = match.group(3) or ""
            rest_path = match.group(4) or ""
            imports = match.group(5)

            # Calculate how many levels up
            levels_up = len(dots) - 1  # .. is 1 level up, ... is 2, etc.

            # Build the absolute import path
            if levels_up == 1:
                # from .. -> from igloo_mcp
                # from ..module -> from igloo_mcp.module
                if package_parts:
                    # We're in a subpackage, go up one level
                    parent_package = '.'.join(package_parts[:-1]) if len(package_parts) > 1 else 'igloo_mcp'
                    absolute_path = f"{parent_package}.{first_module}{rest_path}" if first_module else parent_package
                else:
                    # We're in the root package
                    absolute_path = f"igloo_mcp.{first_module}{rest_path}" if first_module else "igloo_mcp"
            elif levels_up == 2:
                # from ... -> go up 2 levels
                parent_package = '.'.join(package_parts[:-2]) if len(package_parts) > 2 else 'igloo_mcp'
                absolute_path = f"{parent_package}.{first_module}{rest_path}" if first_module else parent_package
            else:
                # More than 2 levels up - just use igloo_mcp
                absolute_path = f"igloo_mcp.{first_module}{rest_path}" if first_module else "igloo_mcp"

            new_line = f"{indent}from {absolute_path} import {imports}"
            new_lines.append(new_line)
            changes.append(f"{filepath.name}: {line.strip()} → {new_line.strip()}")
        else:
            new_lines.append(line)

    new_content = "\n".join(new_lines)

    if new_content != original_content:
        filepath.write_text(new_content)
        return len(changes), changes

    return 0, []


def main() -> int:
    """Run the import fixer on all Python files."""
    src_dir = Path("src/igloo_mcp")

    total_changes = 0
    all_changes = []
    files_changed = set()

    for py_file in src_dir.rglob("*.py"):
        num_changes, changes = fix_file(py_file)
        if num_changes > 0:
            total_changes += num_changes
            all_changes.extend(changes)
            files_changed.add(str(py_file))
            print(f"✅ Fixed {num_changes} imports in {py_file}")

    if all_changes:
        print("\n📊 Summary:")
        print(f"   Total files changed: {len(files_changed)}")
        print(f"   Total imports fixed: {total_changes}")
        print("\n📝 Changes:")
        for change in all_changes[:10]:  # Show first 10
            print(f"   {change}")
        if len(all_changes) > 10:
            print(f"   ... and {len(all_changes) - 10} more")
        return 0
    else:
        print("✅ No relative imports found!")
        return 0


if __name__ == "__main__":
    exit(main())
