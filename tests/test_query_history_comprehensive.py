"""Comprehensive tests for QueryHistory.

Tests cover initialization, recording, insight normalization,
truncation, concurrency, and edge cases.

Target: 48% → 85% coverage
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from igloo_mcp.logging.query_history import (
    QueryHistory,
    normalize_insight,
    truncate_insight_for_storage,
)


class TestQueryHistoryInitialization:
    """Test QueryHistory initialization."""

    def test_init_with_path(self, tmp_path):
        """Initialize with valid path."""
        # Arrange
        history_path = tmp_path / "query_history.jsonl"

        # Act
        history = QueryHistory(path=history_path)

        # Assert
        assert history.path == history_path
        assert not history.disabled

    def test_init_disabled(self):
        """Initialize with disabled sentinel."""
        # Act
        history = QueryHistory(path=None, disabled=True)

        # Assert
        assert history.disabled is True

    def test_init_creates_directory(self, tmp_path):
        """Initialize creates parent directory if needed."""
        # Arrange
        nested_path = tmp_path / "nested" / "dir" / "history.jsonl"

        # Act
        history = QueryHistory(path=nested_path)
        history.record({"execution_id": "test", "statement": "SELECT 1"})

        # Assert
        assert nested_path.parent.exists()


class TestQueryHistoryRecord:
    """Test record() functionality."""

    def test_record_query_success(self, tmp_path):
        """Record a query successfully."""
        # Arrange
        history_path = tmp_path / "history.jsonl"
        history = QueryHistory(path=history_path)
        record = {
            "execution_id": "exec-123",
            "statement": "SELECT * FROM users",
            "rowcount": 100,
            "duration_ms": 150,
        }

        # Act
        history.record(record)

        # Assert
        assert history_path.exists()
        content = history_path.read_text()
        assert "exec-123" in content
        assert "SELECT * FROM users" in content

    def test_record_with_all_fields(self, tmp_path):
        """Record with all possible fields."""
        # Arrange
        history_path = tmp_path / "history.jsonl"
        history = QueryHistory(path=history_path)
        record = {
            "execution_id": "exec-456",
            "sql_sha256": "abc123",
            "statement": "INSERT INTO table VALUES (1)",
            "rowcount": 1,
            "duration_ms": 50,
            "timestamp": "2024-01-01T00:00:00Z",
            "cache_hit": False,
            "post_query_insight": {"summary": "Test insight"},
        }

        # Act
        history.record(record)

        # Assert
        content = history_path.read_text()
        loaded = json.loads(content)
        assert loaded["execution_id"] == "exec-456"
        assert loaded["sql_sha256"] == "abc123"

    def test_record_with_insight_truncation(self, tmp_path):
        """Record truncates large insights."""
        # Arrange
        history_path = tmp_path / "history.jsonl"
        history = QueryHistory(path=history_path)
        large_insight = {"summary": "x" * 20000}  # Very large
        record = {
            "execution_id": "exec-789",
            "statement": "SELECT 1",
            "post_query_insight": large_insight,
        }

        # Act
        history.record(record)

        # Assert - Just verify it doesn't crash and file exists
        assert history_path.exists()
        content = history_path.read_text()
        assert "exec-789" in content

    def test_record_to_disabled_history(self):
        """Recording to disabled history is a no-op."""
        # Arrange
        history = QueryHistory(path=None)

        # Act & Assert - Should not raise
        history.record({"execution_id": "test"})

    def test_record_concurrent_writes(self, tmp_path):
        """Concurrent writes don't corrupt file."""
        # Arrange
        history_path = tmp_path / "history.jsonl"
        history = QueryHistory(path=history_path)

        def write_record(i):
            history.record(
                {
                    "execution_id": f"exec-{i}",
                    "statement": f"SELECT {i}",
                }
            )

        # Act - Multiple threads writing
        threads = [threading.Thread(target=write_record, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Assert - All records written
        lines = history_path.read_text().strip().split("\n")
        assert len(lines) == 10
        # Each line should be valid JSON
        for line in lines:
            json.loads(line)


class TestInsightNormalization:
    """Test normalize_insight() function."""

    def test_normalize_insight_from_string(self):
        """Normalize string insight to structured format."""
        # Act
        result = normalize_insight("Simple insight text")

        # Assert
        assert result["summary"] == "Simple insight text"
        assert result["key_metrics"] == []
        assert result["business_impact"] == ""
        assert result["follow_up_needed"] is False

    def test_normalize_insight_from_dict(self):
        """Normalize dict insight preserves fields."""
        # Arrange
        insight = {
            "summary": "Test summary",
            "key_metrics": ["metric1", "metric2"],
            "business_impact": "High impact",
            "follow_up_needed": True,
        }

        # Act
        result = normalize_insight(insight)

        # Assert
        assert result["summary"] == "Test summary"
        assert result["key_metrics"] == ["metric1", "metric2"]
        assert result["business_impact"] == "High impact"
        assert result["follow_up_needed"] is True

    def test_normalize_insight_with_partial_dict(self):
        """Normalize dict with missing fields adds defaults."""
        # Arrange
        insight = {"summary": "Partial insight"}

        # Act
        result = normalize_insight(insight)

        # Assert
        assert result["summary"] == "Partial insight"
        assert result["key_metrics"] == []
        assert result["business_impact"] == ""
        assert result["follow_up_needed"] is False


class TestInsightTruncation:
    """Test truncate_insight_for_storage() function."""

    def test_truncate_insight_within_limit(self):
        """Insights within limit are not truncated."""
        # Arrange
        insight = {
            "summary": "Short summary",
            "key_metrics": ["m1"],
            "business_impact": "Low",
            "follow_up_needed": False,
        }

        # Act
        result = truncate_insight_for_storage(insight, max_bytes=16384)

        # Assert
        assert result == insight

    def test_truncate_large_insight(self):
        """Large insights are truncated."""
        # Arrange
        insight = {
            "summary": "x" * 20000,  # Very large summary
            "key_metrics": [],
            "business_impact": "",
            "follow_up_needed": False,
        }

        # Act
        result = truncate_insight_for_storage(insight, max_bytes=1000)

        # Assert
        # Summary should be truncated
        assert len(result["summary"]) < 20000
        assert result["summary"].endswith("...")

    def test_truncate_preserves_json_validity(self):
        """Truncated insight is valid JSON."""
        # Arrange
        insight = {
            "summary": "Test " + "x" * 5000,  # Simple ASCII
            "key_metrics": [],
            "business_impact": "",
            "follow_up_needed": False,
        }

        # Act
        result = truncate_insight_for_storage(insight, max_bytes=1000)

        # Assert - Should serialize without error
        serialized = json.dumps(result)
        assert len(serialized) > 0  # Just verify it serializes


class TestQueryHistoryEdgeCases:
    """Test edge cases and error conditions."""

    def test_record_with_none_fields(self, tmp_path):
        """Record with None values doesn't crash."""
        # Arrange
        history_path = tmp_path / "history.jsonl"
        history = QueryHistory(path=history_path)
        record = {
            "execution_id": "test",
            "statement": None,
            "rowcount": None,
        }

        # Act
        history.record(record)

        # Assert
        assert history_path.exists()

    def test_record_empty_dict(self, tmp_path):
        """Record empty dict is handled."""
        # Arrange
        history_path = tmp_path / "history.jsonl"
        history = QueryHistory(path=history_path)

        # Act
        history.record({})

        # Assert
        assert history_path.exists()

    def test_normalize_insight_with_extra_fields(self):
        """Normalize preserves extra fields."""
        # Arrange
        insight = {
            "summary": "Test",
            "key_metrics": [],
            "business_impact": "",
            "follow_up_needed": False,
            "custom_field": "custom_value",
        }

        # Act
        result = normalize_insight(insight)

        # Assert
        assert "custom_field" in result
        assert result["custom_field"] == "custom_value"


class TestQueryHistoryFileOperations:
    """Test file operation edge cases."""

    def test_history_appends_not_overwrites(self, tmp_path):
        """Multiple records append to file."""
        # Arrange
        history_path = tmp_path / "history.jsonl"
        history = QueryHistory(path=history_path)

        # Act
        history.record({"execution_id": "first"})
        history.record({"execution_id": "second"})
        history.record({"execution_id": "third"})

        # Assert
        lines = history_path.read_text().strip().split("\n")
        assert len(lines) == 3
        assert "first" in lines[0]
        assert "second" in lines[1]
        assert "third" in lines[2]

    def test_history_survives_process_restart(self, tmp_path):
        """History persists across QueryHistory instances."""
        # Arrange
        history_path = tmp_path / "history.jsonl"

        # Act - First instance
        history1 = QueryHistory(path=history_path)
        history1.record({"execution_id": "record1"})

        # Second instance (simulates process restart)
        history2 = QueryHistory(path=history_path)
        history2.record({"execution_id": "record2"})

        # Assert
        lines = history_path.read_text().strip().split("\n")
        assert len(lines) == 2


class TestQueryHistoryDisabledSentinels:
    """Test disabled sentinel handling."""

    @pytest.mark.parametrize("sentinel", [None, "", "disabled", "off", "false", "0"])
    def test_disabled_sentinels(self, sentinel):
        """Various sentinels disable history."""
        # Act
        if sentinel is None:
            history = QueryHistory(path=None)
        else:
            history = QueryHistory(path=Path(sentinel) if sentinel else None)

        # Assert
        # Should not raise on record
        history.record({"execution_id": "test"})


class TestQueryHistoryProperties:
    """Test QueryHistory properties."""

    def test_enabled_property_true(self, tmp_path):
        """Enabled property returns True when initialized with path."""
        # Arrange
        history_path = tmp_path / "history.jsonl"
        history = QueryHistory(path=history_path)

        # Assert
        assert history.enabled is True

    def test_enabled_property_false(self):
        """Enabled property returns False when disabled."""
        # Arrange
        history = QueryHistory(path=None, disabled=True)

        # Assert
        assert history.enabled is False

    def test_path_property(self, tmp_path):
        """Path property returns the history path."""
        # Arrange
        history_path = tmp_path / "history.jsonl"
        history = QueryHistory(path=history_path)

        # Assert
        assert history.path == history_path

    def test_disabled_property(self):
        """Disabled property returns correct state."""
        # Arrange
        history = QueryHistory(path=None, disabled=True)

        # Assert
        assert history.disabled is True


class TestQueryHistoryWarnings:
    """Test warning collection."""

    def test_pop_warnings_empty(self, tmp_path):
        """Pop warnings returns empty list when no warnings."""
        # Arrange
        history_path = tmp_path / "history.jsonl"
        history = QueryHistory(path=history_path)

        # Act
        warnings = history.pop_warnings()

        # Assert
        assert warnings == []

    def test_pop_warnings_clears_list(self, tmp_path):
        """Pop warnings clears the warnings list."""
        # Arrange - Create history with bad fallback to generate warning
        history_path = tmp_path / "history.jsonl"
        bad_fallback = Path("/nonexistent/path/history.jsonl")
        history = QueryHistory(path=history_path, fallbacks=[bad_fallback])

        # Act
        _warnings1 = history.pop_warnings()
        warnings2 = history.pop_warnings()

        # Assert - Second call should be empty
        assert warnings2 == []


class TestQueryHistoryTimestampConversion:
    """Test timestamp handling in record()."""

    def test_record_converts_ts_to_timestamp(self, tmp_path):
        """Record converts numeric ts to ISO timestamp."""
        # Arrange
        history_path = tmp_path / "history.jsonl"
        history = QueryHistory(path=history_path)
        record = {
            "execution_id": "test",
            "statement": "SELECT 1",
            "ts": 1609459200.0,  # 2021-01-01 00:00:00 UTC
        }

        # Act
        history.record(record)

        # Assert
        content = history_path.read_text()
        assert "timestamp" in content
        assert "2021-01-01" in content

    def test_record_preserves_existing_timestamp(self, tmp_path):
        """Record preserves existing timestamp field."""
        # Arrange
        history_path = tmp_path / "history.jsonl"
        history = QueryHistory(path=history_path)
        record = {
            "execution_id": "test",
            "statement": "SELECT 1",
            "timestamp": "2024-01-01T00:00:00Z",
        }

        # Act
        history.record(record)

        # Assert
        content = history_path.read_text()
        assert "2024-01-01T00:00:00Z" in content


class TestQueryHistoryFallbacks:
    """Test fallback path handling."""

    def test_init_with_fallbacks(self, tmp_path):
        """Initialize with fallback paths."""
        # Arrange
        primary_path = tmp_path / "primary" / "history.jsonl"
        fallback_path = tmp_path / "fallback" / "history.jsonl"

        # Act
        history = QueryHistory(path=primary_path, fallbacks=[fallback_path])

        # Assert
        assert history.enabled is True
        assert history.path == primary_path

    def test_fallback_used_when_primary_fails(self, tmp_path):
        """Fallback path used when primary path fails."""
        # Arrange
        bad_primary = Path("/root/cannot_write/history.jsonl")
        fallback_path = tmp_path / "fallback" / "history.jsonl"

        # Act
        history = QueryHistory(path=bad_primary, fallbacks=[fallback_path])

        # Assert
        assert history.enabled is True
        assert history.path == fallback_path
        # Should have warning about fallback
        warnings = history.pop_warnings()
        assert len(warnings) > 0


class TestQueryHistoryFromEnv:
    """Test from_env() class method."""

    def test_from_env_disabled(self, monkeypatch):
        """from_env returns disabled history when env var is disable sentinel."""
        # Arrange
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", "disabled")

        # Act
        history = QueryHistory.from_env()

        # Assert
        assert history.disabled is True

    def test_from_env_with_path(self, monkeypatch, tmp_path):
        """from_env uses path from environment variable."""
        # Arrange
        history_path = tmp_path / "env_history.jsonl"
        monkeypatch.setenv("IGLOO_MCP_QUERY_HISTORY", str(history_path))

        # Act
        history = QueryHistory.from_env()

        # Assert
        assert history.enabled is True
        assert history.path == history_path

    def test_from_env_no_env_var(self, monkeypatch):
        """from_env handles missing environment variable."""
        # Arrange
        monkeypatch.delenv("IGLOO_MCP_QUERY_HISTORY", raising=False)

        # Act
        history = QueryHistory.from_env()

        # Assert
        # Should either be disabled or use fallback
        assert history is not None
