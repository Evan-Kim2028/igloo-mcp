#!/usr/bin/env python3
"""Enforce regression test requirements for bug fix commits.

Bug fix commits (fix:, bug:, fixes #, closes #) must have corresponding
regression tests tagged with @pytest.mark.regression(issue_id="...")
"""

import re
import subprocess
import sys
from pathlib import Path


def get_commit_message() -> str:
    """Get the latest commit message."""
    result = subprocess.run(
        ["git", "log", "-1", "--pretty=%B"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def is_bug_fix_commit(commit_msg: str) -> bool:
    """Check if commit is a bug fix."""
    bug_keywords = ["fix:", "bug:", "regression:", "hotfix:", "fixes #", "closes #"]
    return any(kw in commit_msg.lower() for kw in bug_keywords)


def find_regression_tests() -> list[Path]:
    """Find all regression test files."""
    tests_dir = Path("tests")
    if not tests_dir.exists():
        return []
    return list(tests_dir.rglob("test_regression_*.py"))


def main() -> int:
    """Check if bug fixes have regression tests."""
    commit_msg = get_commit_message()

    if not commit_msg:
        print("⚠️  Could not get commit message, skipping check")
        return 0

    if not is_bug_fix_commit(commit_msg):
        print("✅ Not a bug fix commit, skipping regression test check")
        return 0

    # Extract issue number from commit message
    issue_match = re.search(r"#(\d+)", commit_msg)
    if not issue_match:
        print("⚠️  Bug fix commit should reference issue number (e.g., 'fixes #123')")
        print("   Skipping regression test requirement")
        return 0

    issue_num = issue_match.group(1)

    # Check if regression test exists
    regression_tests = find_regression_tests()
    has_test = any(
        f"issue_{issue_num}" in test_file.name or f"issue{issue_num}" in test_file.name
        for test_file in regression_tests
    )

    if not has_test:
        print(f"❌ Bug fix commit for issue #{issue_num} requires regression test")
        print(f"   Create: tests/test_regression_issue_{issue_num}_<description>.py")
        print(f'   Use: @pytest.mark.regression(issue_id="{issue_num}")')
        print("\n   Example:")
        print("   ```python")
        print("   import pytest")
        print("   ")
        print(f'   @pytest.mark.regression(issue_id="{issue_num}")')
        print(f"   def test_regression_issue_{issue_num}_<description>():")
        print(f'       """Regression test for Issue #{issue_num}."""')
        print("       # Test that reproduces and verifies fix")
        print("       assert True")
        print("   ```")
        return 1

    print(f"✅ Regression test found for issue #{issue_num}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
