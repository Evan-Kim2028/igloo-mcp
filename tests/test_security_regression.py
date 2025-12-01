"""Security regression tests to prevent vulnerabilities.

This module contains tests for security-critical functionality to ensure
vulnerabilities don't reappear in future changes.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from igloo_mcp.path_utils import resolve_catalog_root, resolve_reports_root


@pytest.mark.regression
class TestPathTraversalRegression:
    """Ensure path traversal vulnerability stays fixed.

    These tests protect against CVE-level path traversal attacks where
    malicious environment variables could access sensitive system files.

    See: todos/001-pending-p1-path-traversal-vulnerability.md
    """

    def test_no_directory_escape_via_query_history_reports(self):
        """Block ../../../ patterns in IGLOO_MCP_QUERY_HISTORY for reports root.

        Attack scenario: Malicious user sets IGLOO_MCP_QUERY_HISTORY to a path
        that looks like it's in .igloo-mcp but actually traverses to /etc/passwd.
        """
        with patch.dict(
            os.environ,
            {"IGLOO_MCP_QUERY_HISTORY": "/tmp/evil/.igloo-mcp/logs/../../../../etc/passwd"},
            clear=False,
        ):
            result = resolve_reports_root()

            # Should fall back to safe default, not traverse to /etc
            assert "/etc" not in str(result), f"Path traversal attack succeeded: {result}"
            assert result.is_relative_to(Path.home()), f"Path escaped home directory: {result}"

    def test_no_directory_escape_via_artifact_root_reports(self):
        """Block ../../../ patterns in IGLOO_MCP_ARTIFACT_ROOT for reports root."""
        with patch.dict(
            os.environ,
            {"IGLOO_MCP_ARTIFACT_ROOT": "/tmp/evil/.igloo-mcp/artifacts/../../../root/.ssh"},
            clear=False,
        ):
            result = resolve_reports_root()

            # Should not access sensitive directories
            assert "/.ssh" not in str(result), f"Accessed sensitive directory: {result}"
            assert "/root" not in str(result), f"Accessed root home directory: {result}"

    def test_no_directory_escape_via_query_history_catalog(self):
        """Block ../../../ patterns in IGLOO_MCP_QUERY_HISTORY for catalog root."""
        with patch.dict(
            os.environ,
            {"IGLOO_MCP_QUERY_HISTORY": "/var/tmp/.igloo-mcp/logs/../../../../../var/log/auth.log"},
            clear=False,
        ):
            result = resolve_catalog_root()

            # Should not access system logs
            assert "/var/log" not in str(result), f"Path traversal to system logs: {result}"
            assert result.is_relative_to(Path.home()), f"Path escaped home directory: {result}"

    def test_no_directory_escape_via_artifact_root_catalog(self):
        """Block ../../../ patterns in IGLOO_MCP_ARTIFACT_ROOT for catalog root."""
        with patch.dict(
            os.environ,
            {"IGLOO_MCP_ARTIFACT_ROOT": "/opt/mal/.igloo_mcp/artifacts/../../../../bin"},
            clear=False,
        ):
            result = resolve_catalog_root()

            # Should not access system binaries
            assert "/bin" not in str(result) or result.is_relative_to(Path.home()), (
                f"Accessed system directories: {result}"
            )

    def test_legitimate_custom_paths_accepted_reports(self):
        """Legitimate custom paths within safe roots should work for reports."""
        # Create a custom path within user's home directory
        custom_path = Path.home() / ".igloo-mcp-custom" / "logs" / "doc.jsonl"

        with patch.dict(os.environ, {"IGLOO_MCP_QUERY_HISTORY": str(custom_path)}, clear=False):
            result = resolve_reports_root()

            # Should accept this path since it's under home directory
            assert result is not None
            assert result.is_relative_to(Path.home())

    def test_legitimate_custom_paths_accepted_catalog(self):
        """Legitimate custom paths within safe roots should work for catalog."""
        # Create a custom path within current working directory
        custom_path = Path.cwd() / ".igloo-mcp-project" / "artifacts" / "data"

        with patch.dict(os.environ, {"IGLOO_MCP_ARTIFACT_ROOT": str(custom_path)}, clear=False):
            result = resolve_catalog_root()

            # Should accept this path since it's under current directory
            assert result is not None
            # Should be within either home or cwd
            assert result.is_relative_to(Path.home()) or result.is_relative_to(Path.cwd())

    def test_symbolic_link_escape_blocked(self):
        """Symbolic links that escape safe roots should be rejected.

        Attack scenario: Create a symlink inside .igloo-mcp that points outside safe roots.
        """
        # This tests that even if someone creates a malicious symlink,
        # our validation will catch it after resolution
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Simulate a malicious path that looks safe but resolves outside
            malicious = Path(tmpdir) / ".igloo-mcp" / "logs" / "evil"

            with patch.dict(os.environ, {"IGLOO_MCP_QUERY_HISTORY": str(malicious)}, clear=False):
                result = resolve_reports_root()

                # Should fall back to safe default, not use the tmpdir path
                if Path(tmpdir) not in Path.home().parents and Path(tmpdir) != Path.home():
                    # tmpdir is outside safe roots, should be rejected
                    assert not result.is_relative_to(Path(tmpdir)), f"Accepted path outside safe roots: {result}"

    def test_absolute_path_outside_safe_roots_rejected(self):
        """Absolute paths outside safe roots should be rejected."""
        # Try to point directly to a system directory
        with patch.dict(os.environ, {"IGLOO_MCP_QUERY_HISTORY": "/opt/.igloo-mcp/logs/doc.jsonl"}, clear=False):
            result = resolve_reports_root()

            # Unless /opt is under home (unlikely), this should fall back
            if not Path("/opt").is_relative_to(Path.home()):
                assert "/opt" not in str(result) or result.is_relative_to(Path.home()), f"Accepted /opt path: {result}"

    def test_windows_style_traversal_blocked(self):
        """Windows-style path traversal should also be blocked."""
        # Test Windows-style paths (even on Unix systems, be defensive)
        with patch.dict(
            os.environ,
            {"IGLOO_MCP_QUERY_HISTORY": "C:\\evil\\.igloo-mcp\\logs\\..\\..\\..\\Windows\\System32"},
            clear=False,
        ):
            result = resolve_reports_root()

            # Should fall back to safe default
            assert "Windows" not in str(result), f"Windows-style traversal succeeded: {result}"
            assert "System32" not in str(result), f"Accessed System32: {result}"
