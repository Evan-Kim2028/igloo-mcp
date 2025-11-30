"""Tests for placeholder-based merging utilities."""

from __future__ import annotations

import pytest

from igloo_mcp.living_reports.merge_utils import (
    MERGE_MODE_APPEND,
    MERGE_MODE_MERGE,
    MERGE_MODE_PREPEND,
    MERGE_MODE_REPLACE,
    apply_content_merge,
    has_placeholders,
    merge_with_placeholders,
)


class TestHasPlaceholders:
    """Tests for has_placeholders detection."""

    def test_no_placeholders(self) -> None:
        """Content without placeholders returns False."""
        assert has_placeholders("Just some regular content") is False
        assert has_placeholders("# Header\nSome text") is False

    def test_existing_placeholder(self) -> None:
        """Detects '// ... existing ...' placeholder."""
        assert has_placeholders("// ... existing ...") is True
        assert has_placeholders("<!-- ... existing ... -->") is True
        assert has_placeholders("# ... existing ...") is True
        assert has_placeholders("// ... keep existing ...") is True

    def test_keep_above_placeholder(self) -> None:
        """Detects '// ... keep above ...' placeholder."""
        assert has_placeholders("// ... keep above ...") is True
        assert has_placeholders("<!-- ... keep above ... -->") is True

    def test_keep_below_placeholder(self) -> None:
        """Detects '// ... keep below ...' placeholder."""
        assert has_placeholders("// ... keep below ...") is True
        assert has_placeholders("<!-- ... keep below ... -->") is True

    def test_keep_section_placeholder(self) -> None:
        """Detects '// ... keep "Section Name" ...' placeholder."""
        assert has_placeholders('// ... keep "Introduction" ...') is True
        assert has_placeholders('<!-- ... keep "Analysis" ... -->') is True

    def test_empty_content(self) -> None:
        """Empty content returns False."""
        assert has_placeholders("") is False
        assert has_placeholders(None) is False  # type: ignore


class TestMergeWithPlaceholders:
    """Tests for merge_with_placeholders function."""

    def test_no_placeholders_returns_template(self) -> None:
        """Without placeholders, return template as-is (replace mode)."""
        existing = "Old content"
        template = "New content"
        result = merge_with_placeholders(existing, template)
        assert result == "New content"

    def test_empty_template_returns_existing(self) -> None:
        """Empty template returns existing content."""
        existing = "Keep this"
        result = merge_with_placeholders(existing, "")
        assert result == "Keep this"

    def test_empty_existing_removes_placeholders(self) -> None:
        """With no existing content, placeholders are removed."""
        template = "// ... existing ...\nNew stuff"
        result = merge_with_placeholders("", template)
        assert "existing" not in result.lower()
        assert "New stuff" in result

    def test_keep_existing_placeholder(self) -> None:
        """'// ... existing ...' replaces with all existing content."""
        existing = "All my existing content here"
        template = "// ... existing ..."
        result = merge_with_placeholders(existing, template)
        assert result == "All my existing content here"

    def test_keep_above_placeholder(self) -> None:
        """'// ... keep above ...' preserves content before placeholder."""
        existing = "# Header\nOld intro.\n\n# Body\nOld body."
        template = "// ... keep above ...\n# Body\nNew body content."
        result = merge_with_placeholders(existing, template)
        assert "# Header" in result
        assert "Old intro" in result
        assert "New body content" in result

    def test_keep_below_placeholder(self) -> None:
        """'// ... keep below ...' preserves content after placeholder."""
        existing = "# Header\nOld intro.\n\n# Footer\nOld footer."
        template = "# Header\nNew intro.\n// ... keep below ..."
        result = merge_with_placeholders(existing, template)
        assert "New intro" in result
        assert "Old intro" in result or "Old footer" in result

    def test_keep_section_placeholder(self) -> None:
        """'// ... keep "Section" ...' preserves named section."""
        existing = """# Introduction
This is the intro.

# Analysis
Old analysis here.

# Conclusion
Final thoughts."""

        template = """// ... keep "Introduction" ...

# Analysis
New analysis with updated data.

# Conclusion
Updated conclusion."""

        result = merge_with_placeholders(existing, template)
        assert "This is the intro" in result
        assert "New analysis with updated data" in result

    def test_section_not_found(self) -> None:
        """Missing section placeholder is removed gracefully."""
        existing = "# Intro\nSome content"
        template = '// ... keep "NonExistent" ...\n# New Section\nContent'
        result = merge_with_placeholders(existing, template)
        assert "NonExistent" not in result
        assert "# New Section" in result


class TestApplyContentMerge:
    """Tests for apply_content_merge function."""

    def test_replace_mode(self) -> None:
        """Replace mode returns new content entirely."""
        result = apply_content_merge("old", "new", MERGE_MODE_REPLACE)
        assert result == "new"

    def test_merge_mode_with_placeholders(self) -> None:
        """Merge mode applies placeholder-based merging."""
        result = apply_content_merge(
            "Existing content",
            "// ... existing ...\n\nAdditional content",
            MERGE_MODE_MERGE,
        )
        assert "Existing content" in result
        assert "Additional content" in result

    def test_merge_mode_without_placeholders(self) -> None:
        """Merge mode without placeholders returns new content."""
        result = apply_content_merge("old", "new", MERGE_MODE_MERGE)
        assert result == "new"

    def test_append_mode(self) -> None:
        """Append mode adds new content after existing."""
        result = apply_content_merge("First", "Second", MERGE_MODE_APPEND)
        assert result.startswith("First")
        assert result.endswith("Second")
        assert "First" in result and "Second" in result

    def test_prepend_mode(self) -> None:
        """Prepend mode adds new content before existing."""
        result = apply_content_merge("Second", "First", MERGE_MODE_PREPEND)
        assert result.startswith("First")
        assert result.endswith("Second")

    def test_append_with_empty_existing(self) -> None:
        """Append with no existing returns just new content."""
        result = apply_content_merge("", "New content", MERGE_MODE_APPEND)
        assert result == "New content"

    def test_prepend_with_empty_existing(self) -> None:
        """Prepend with no existing returns just new content."""
        result = apply_content_merge("", "New content", MERGE_MODE_PREPEND)
        assert result == "New content"

    def test_invalid_merge_mode_raises(self) -> None:
        """Invalid merge mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid merge_mode"):
            apply_content_merge("old", "new", "invalid_mode")


class TestMergeModeConstants:
    """Tests for merge mode constants."""

    def test_constant_values(self) -> None:
        """Constants have expected values."""
        assert MERGE_MODE_REPLACE == "replace"
        assert MERGE_MODE_MERGE == "merge"
        assert MERGE_MODE_APPEND == "append"
        assert MERGE_MODE_PREPEND == "prepend"
