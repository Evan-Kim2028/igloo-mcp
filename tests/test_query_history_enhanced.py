"""Enhanced tests for query history with post_query_insight support."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from igloo_mcp.logging.query_history import QueryHistory


class TestQueryHistoryEnhancements:
    """Test enhanced query history features."""

    def test_post_query_insight_string_passthrough(self):
        """Test that string post_query_insight is recorded as provided."""
        with tempfile.TemporaryDirectory() as temp_dir:
            history_file = Path(temp_dir) / "test_history.jsonl"
            history = QueryHistory(history_file)

            # Test string post_query_insight
            payload = {
                "ts": 1699999999,
                "status": "success",
                "profile": "test",
                "statement_preview": "SELECT * FROM users",
                "rowcount": 100,
                "post_query_insight": "Query shows 15% increase in daily active users",
            }

            history.record(payload)

            # Read back and verify structure
            content = history_file.read_text()
            recorded = json.loads(content.strip())

            assert "timestamp" in recorded  # ISO timestamp should be added
            assert (
                recorded["post_query_insight"]
                == "Query shows 15% increase in daily active users"
            )

    def test_post_query_insight_dict_preservation(self):
        """Test that dict post_query_insight is preserved and structured."""
        with tempfile.TemporaryDirectory() as temp_dir:
            history_file = Path(temp_dir) / "test_history.jsonl"
            history = QueryHistory(history_file)

            # Test dict post_query_insight
            insight_dict = {
                "summary": "Revenue growth of 23% MoM",
                "key_metrics": ["revenue_up_23pct", "new_customers_450"],
                "business_impact": "Positive trend indicating market expansion",
                "follow_up_needed": True,
                "confidence": 0.92,
            }

            payload = {
                "ts": 1699999999,
                "status": "success",
                "profile": "test",
                "statement_preview": "SELECT revenue, customers FROM sales",
                "rowcount": 50,
                "post_query_insight": insight_dict,
            }

            history.record(payload)

            # Read back and verify structure
            content = history_file.read_text()
            recorded = json.loads(content.strip())

            assert recorded["post_query_insight"]["summary"] == insight_dict["summary"]
            assert (
                recorded["post_query_insight"]["key_metrics"]
                == insight_dict["key_metrics"]
            )
            assert (
                recorded["post_query_insight"]["business_impact"]
                == insight_dict["business_impact"]
            )
            assert (
                recorded["post_query_insight"]["follow_up_needed"]
                == insight_dict["follow_up_needed"]
            )
            assert (
                recorded["post_query_insight"]["confidence"]
                == insight_dict["confidence"]
            )

    def test_iso_timestamp_conversion(self):
        """Test that timestamps are converted to ISO format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            history_file = Path(temp_dir) / "test_history.jsonl"
            history = QueryHistory(history_file)

            # Test with numeric timestamp
            payload = {
                "ts": 1699999999.123456,
                "status": "success",
                "profile": "test",
                "statement_preview": "SELECT * FROM test",
                "rowcount": 10,
            }

            history.record(payload)

            # Read back and verify ISO format
            content = history_file.read_text()
            recorded = json.loads(content.strip())

            assert "timestamp" in recorded
            # Should be ISO format like "2023-11-15T03:33:19.123456"
            timestamp = recorded["timestamp"]
            assert "T" in timestamp and "-" in timestamp  # Basic ISO format check

    def test_multiple_entries_with_post_query_insight(self):
        """Test recording multiple entries with varying post_query_insight formats."""
        with tempfile.TemporaryDirectory() as temp_dir:
            history_file = Path(temp_dir) / "test_history.jsonl"
            history = QueryHistory(history_file)

            # Record multiple entries
            entries = [
                {
                    "ts": 1699999999,
                    "status": "success",
                    "profile": "test",
                    "statement_preview": "SELECT * FROM users",
                    "rowcount": 100,
                    "post_query_insight": "User growth trend positive",
                },
                {
                    "ts": 1700000000,
                    "status": "timeout",
                    "profile": "test",
                    "statement_preview": "SELECT * FROM large_table",
                    "timeout_seconds": 30,
                    "error": "Timeout exceeded",
                },
                {
                    "ts": 1700000001,
                    "status": "success",
                    "profile": "test",
                    "statement_preview": "SELECT COUNT(*) FROM orders",
                    "rowcount": 1,
                    "post_query_insight": {
                        "summary": "Total order count calculated",
                        "key_metrics": ["total_orders:12450"],
                        "business_impact": "Order volume indicators healthy",
                    },
                },
            ]

            for entry in entries:
                history.record(entry)

            # Verify all entries were recorded
            content = history_file.read_text().strip().split("\n")
            assert len(content) == 3

            # Verify each entry structure
            for i, line in enumerate(content):
                recorded = json.loads(line)
                assert recorded["statement_preview"] == entries[i]["statement_preview"]
                assert recorded["status"] == entries[i]["status"]
                assert "timestamp" in recorded

                if entries[i].get("post_query_insight"):
                    assert "post_query_insight" in recorded
                    if isinstance(entries[i]["post_query_insight"], str):
                        assert (
                            recorded["post_query_insight"]
                            == entries[i]["post_query_insight"]
                        )
                    else:
                        assert "summary" in recorded["post_query_insight"]

    def test_repository_specific_logging_enabled_by_default(self):
        """Test that repository-specific logging is enabled by default in git repos."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock git repository
            git_dir = Path(temp_dir) / ".git"
            git_dir.mkdir()

            # Patch find_repo_root to return our temp directory
            with patch("igloo_mcp.path_utils.find_repo_root") as mock_find:
                mock_find.return_value = Path(temp_dir)

                # Clear any existing environment variable
                with patch.dict("os.environ", {"IGLOO_MCP_QUERY_HISTORY": ""}):
                    # UNSET the env var (empty string should disable)
                    import os

                    if "IGLOO_MCP_QUERY_HISTORY" in os.environ:
                        del os.environ["IGLOO_MCP_QUERY_HISTORY"]

                    history = QueryHistory.from_env()

                    # Should be enabled since we're in a git repo
                    assert history.enabled is True
                    assert history._path is not None
                    assert "logs" in str(history._path)

    def test_repository_specific_logging_disabled_outside_git(self):
        """Test that logging is disabled outside git repositories when env var not set."""
        # Test the explicit scenario: create QueryHistory with None path
        history = QueryHistory(None)

        # Should be disabled since no path was provided
        assert history.enabled is False

    def test_disable_via_environment(self):
        """History can be explicitly disabled via environment variable."""
        with patch.dict("os.environ", {"IGLOO_MCP_QUERY_HISTORY": "disabled"}):
            history = QueryHistory.from_env()
            assert history.enabled is False
            assert history.disabled is True

    def test_error_handling_in_post_query_insight_processing(self):
        """Test graceful error handling when payload contains non-serializable data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            history_file = Path(temp_dir) / "test_history.jsonl"
            history = QueryHistory(history_file)

            # Test with non-serializable field
            payload = {
                "ts": 1699999999,
                "status": "success",
                "profile": "test",
                "statement_preview": "SELECT * FROM test",
                "rowcount": 10,
                "post_query_insight": object(),  # Non-serializable object
            }

            # Should not raise an exception
            history.record(payload)

            # Verify fallback behavior
            content = history_file.read_text()
            recorded = json.loads(content.strip())

            # Should handle the non-serializable object gracefully by writing error entry
            assert "error" in recorded

    def test_jsonl_format_maintained_with_enhancements(self):
        """Test that JSONL format is maintained with enhanced features."""
        with tempfile.TemporaryDirectory() as temp_dir:
            history_file = Path(temp_dir) / "test_history.jsonl"
            history = QueryHistory(history_file)

            # Record multiple entries
            for i in range(3):
                payload = {
                    "ts": 1699999999 + i,
                    "status": "success",
                    "profile": "test",
                    "statement_preview": f"SELECT * FROM table_{i}",
                    "rowcount": i * 10,
                    "post_query_insight": f"Entry {i} summary",
                }
                history.record(payload)

            # Verify JSONL format (one JSON object per line)
            content = history_file.read_text()
            lines = content.strip().split("\n")

            assert len(lines) == 3

            for line in lines:
                # Each line should be valid JSON
                json.loads(line)
                # Each line should end with newline (except last one in strip())

            # Verify file ends with newline (JSONL standard)
            assert content.endswith("\n")

    def test_history_fallback_when_primary_fails(self, monkeypatch: pytest.MonkeyPatch):
        with tempfile.TemporaryDirectory() as temp_dir:
            primary = Path(temp_dir) / "history" / "primary.jsonl"
            fallback = Path(temp_dir) / "secondary" / "fallback.jsonl"
            original_mkdir = Path.mkdir

            def fake_mkdir(self, *args, **kwargs):
                if self == primary.parent:
                    raise OSError("cannot create primary")
                return original_mkdir(self, *args, **kwargs)

            monkeypatch.setattr(Path, "mkdir", fake_mkdir, raising=False)
            history = QueryHistory(primary, fallbacks=[fallback])
            warnings = history.pop_warnings()
            assert history.enabled is True
            assert any("using fallback" in msg for msg in warnings)

    def test_history_disabled_when_all_paths_fail(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            primary = Path(temp_dir) / "history" / "primary.jsonl"
            fallback = Path(temp_dir) / "history" / "fallback.jsonl"
            original_mkdir = Path.mkdir

            def fake_mkdir(self, *args, **kwargs):
                if self in {primary.parent, fallback.parent}:
                    raise OSError("no permission")
                return original_mkdir(self, *args, **kwargs)

            monkeypatch.setattr(Path, "mkdir", fake_mkdir, raising=False)
            history = QueryHistory(primary, fallbacks=[fallback])
            assert history.enabled is False
            warnings = history.pop_warnings()
            assert any("disabled" in msg for msg in warnings)

    def test_from_env_resolution_failure(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "custom/path")
        monkeypatch.setattr(
            "igloo_mcp.logging.query_history.resolve_history_path",
            lambda raw=None: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        history = QueryHistory.from_env()
        assert history.enabled is True

    def test_record_handles_write_failure(self, monkeypatch: pytest.MonkeyPatch):
        with tempfile.TemporaryDirectory() as temp_dir:
            history_file = Path(temp_dir) / "test_history.jsonl"
            history = QueryHistory(history_file)
            original_open = Path.open

            def fake_open(self, *args, **kwargs):
                if self == history_file:
                    raise OSError("disk error")
                return original_open(self, *args, **kwargs)

            monkeypatch.setattr(Path, "open", fake_open, raising=False)
            history.record({"status": "ok"})
            warnings = history.pop_warnings()
            assert any(
                "Failed to append query history entry" in msg for msg in warnings
            )

    def test_from_env_handles_fallback_mkdir_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        target_parent = Path.home() / ".igloo_mcp"
        original_mkdir = Path.mkdir

        def fake_mkdir(self, *args, **kwargs):
            if self == target_parent:
                raise OSError("perm")
            return original_mkdir(self, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", fake_mkdir, raising=False)
        monkeypatch.delenv("IGLOO_MCP_QUERY_HISTORY", raising=False)
        history = QueryHistory.from_env()
        # Even with mkdir failure we should still get a history instance
        assert isinstance(history, QueryHistory)
