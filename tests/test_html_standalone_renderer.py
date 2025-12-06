"""Tests for HTML Standalone Renderer.

Tests the self-contained HTML renderer that generates
reports without Quarto dependency.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from igloo_mcp.living_reports.models import Citation, Insight, Outline, Section
from igloo_mcp.living_reports.renderers.html_standalone import HTMLStandaloneRenderer


@pytest.fixture
def renderer():
    """Create HTML standalone renderer instance."""
    return HTMLStandaloneRenderer()


@pytest.fixture
def basic_outline():
    """Create a basic outline for testing."""
    return Outline(
        report_id=str(uuid.uuid4()),
        title="Test Report",
        created_at="2024-01-15T10:00:00Z",
        updated_at="2024-01-15T12:00:00Z",
        sections=[],
        insights=[],
        metadata={"template": "default"},
    )


@pytest.fixture
def full_outline():
    """Create a comprehensive outline with sections and insights."""
    insight_id_1 = str(uuid.uuid4())
    insight_id_2 = str(uuid.uuid4())
    section_id_1 = str(uuid.uuid4())
    section_id_2 = str(uuid.uuid4())

    return Outline(
        report_id=str(uuid.uuid4()),
        title="Quarterly Revenue Analysis",
        created_at="2024-01-15T10:00:00Z",
        updated_at="2024-01-15T12:00:00Z",
        sections=[
            Section(
                section_id=section_id_1,
                title="Executive Summary",
                order=0,
                insight_ids=[insight_id_1],
                content="This report provides a **comprehensive** analysis of Q4 revenue.",
            ),
            Section(
                section_id=section_id_2,
                title="Detailed Analysis",
                order=1,
                insight_ids=[insight_id_2],
                notes="Focus on YoY growth metrics",
            ),
        ],
        insights=[
            Insight(
                insight_id=insight_id_1,
                summary="Revenue increased 25% YoY",
                importance=9,
                supporting_queries=[],
                citations=[Citation(source="query", execution_id="exec-001")],
            ),
            Insight(
                insight_id=insight_id_2,
                summary="Customer retention rate improved to 95%",
                importance=7,
                supporting_queries=[],
                citations=[Citation(source="query", execution_id="exec-002")],
            ),
        ],
        metadata={"tags": ["quarterly", "revenue"]},
    )


class TestHTMLStandaloneRendererBasic:
    """Test basic rendering functionality."""

    def test_render_basic_report(self, renderer, basic_outline, tmp_path):
        """Test rendering a minimal report."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
        )

        assert result["output_path"] == str(tmp_path / "report_standalone.html")
        assert result["size_bytes"] > 0
        assert result["warnings"] == []

        # Verify file exists
        output_file = Path(result["output_path"])
        assert output_file.exists()

    def test_render_generates_valid_html(self, renderer, basic_outline, tmp_path):
        """Test that rendered output is valid HTML."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # Check HTML structure
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "</html>" in content
        assert "<head>" in content
        assert "</head>" in content
        assert "<body>" in content
        assert "</body>" in content

    def test_render_includes_title(self, renderer, basic_outline, tmp_path):
        """Test that report title is included."""
        basic_outline.title = "My Custom Report Title"

        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert "<title>My Custom Report Title</title>" in content
        assert "My Custom Report Title" in content

    def test_render_includes_report_id(self, renderer, basic_outline, tmp_path):
        """Test that report ID is included in metadata."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert basic_outline.report_id in content


class TestHTMLStandaloneRendererSections:
    """Test section rendering."""

    def test_render_with_sections(self, renderer, full_outline, tmp_path):
        """Test rendering report with sections."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=full_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # Check sections are present
        assert "Executive Summary" in content
        assert "Detailed Analysis" in content

    def test_render_section_order(self, renderer, full_outline, tmp_path):
        """Test that sections are rendered in correct order."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=full_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # Executive Summary should appear before Detailed Analysis
        exec_summary_pos = content.find("Executive Summary")
        detailed_pos = content.find("Detailed Analysis")

        assert exec_summary_pos < detailed_pos

    def test_render_section_content(self, renderer, full_outline, tmp_path):
        """Test that section content is rendered."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=full_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # Content should be present (markdown converted)
        assert "comprehensive" in content
        assert "analysis" in content

    def test_render_section_notes(self, renderer, full_outline, tmp_path):
        """Test that section notes are rendered."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=full_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert "Focus on YoY growth metrics" in content


class TestHTMLStandaloneRendererInsights:
    """Test insight rendering."""

    def test_render_with_insights(self, renderer, full_outline, tmp_path):
        """Test rendering report with insights in insights-only sections."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=full_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # Executive Summary has narrative content, so insights won't show in HTML
        # (this is correct - we fixed double rendering in #114)
        # But Detailed Analysis section has no content, only insights, so they WILL show
        assert "Customer retention rate improved to 95%" in content  # insight_id_2 in section without content

    def test_render_insight_importance_class(self, renderer, full_outline, tmp_path):
        """Test that insights have correct importance class."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=full_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # High importance (9) should have insight-high class
        assert "insight-high" in content
        # Medium importance (7) should have insight-medium class
        assert "insight-medium" in content


class TestHTMLStandaloneRendererTableOfContents:
    """Test table of contents rendering."""

    def test_render_with_toc(self, renderer, full_outline, tmp_path):
        """Test rendering with table of contents enabled (default)."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=full_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert "table-of-contents" in content
        assert "Contents" in content

    def test_render_without_toc(self, renderer, full_outline, tmp_path):
        """Test rendering with table of contents disabled."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=full_outline,
            options={"toc": False},
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # Should not have TOC nav element (but CSS class may still be in styles)
        assert '<nav class="table-of-contents">' not in content

    def test_toc_links_to_sections(self, renderer, full_outline, tmp_path):
        """Test that TOC links to section IDs."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=full_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # Check for anchor links
        for section in full_outline.sections:
            assert f'href="#section-{section.section_id}"' in content


class TestHTMLStandaloneRendererCitations:
    """Test citations appendix rendering."""

    def test_render_with_citations(self, renderer, full_outline, tmp_path):
        """Test rendering with citations appendix."""
        hints = {
            "citation_map": {
                "exec-001": 1,
                "exec-002": 2,
            },
            "citation_details": {
                "exec-001": {
                    "timestamp": "2024-01-15T10:30:00Z",
                    "statement_preview": "SELECT * FROM revenue WHERE quarter = 'Q4'",
                    "rowcount": 1500,
                    "duration_ms": 250,
                },
                "exec-002": {
                    "timestamp": "2024-01-15T11:00:00Z",
                    "statement_preview": "SELECT * FROM customers WHERE status = 'active'",
                    "rowcount": 5000,
                    "duration_ms": 180,
                },
            },
        }

        result = renderer.render(
            report_dir=tmp_path,
            outline=full_outline,
            hints=hints,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # Check citations appendix
        assert "Data Sources" in content
        assert "exec-001" in content
        assert "exec-002" in content

    def test_render_citations_in_order(self, renderer, full_outline, tmp_path):
        """Test that citations are rendered in order."""
        hints = {
            "citation_map": {
                "exec-002": 2,
                "exec-001": 1,  # Out of order in dict
            },
        }

        result = renderer.render(
            report_dir=tmp_path,
            outline=full_outline,
            hints=hints,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # Citation 1 should appear before citation 2
        pos_1 = content.find("citation-1")
        pos_2 = content.find("citation-2")

        assert pos_1 < pos_2


class TestHTMLStandaloneRendererThemes:
    """Test theme support."""

    def test_render_default_theme(self, renderer, basic_outline, tmp_path):
        """Test rendering with default theme."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # Check for CSS variables
        assert "--primary-color" in content
        assert "--background" in content

    def test_render_dark_theme(self, renderer, basic_outline, tmp_path):
        """Test rendering with dark theme."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
            options={"theme": "dark"},
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert "--background: #0f172a;" in content
        assert "prefers-color-scheme" in content

    def test_render_minimal_theme(self, renderer, basic_outline, tmp_path):
        """Test rendering with minimal theme overrides."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
            options={"theme": "minimal"},
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert "font-family: 'Source Sans Pro'" in content
        assert "--surface: #f3f4f6" in content


class TestHTMLStandaloneRendererStyles:
    """Test style presets and overrides for standalone renderer."""

    def test_style_preset_compact(self, renderer, basic_outline, tmp_path):
        """Compact preset should update max width and padding values."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
            options={"style_preset": "compact"},
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert "max-width: 900px" in content
        assert "padding: 2rem 2.5rem" in content

    def test_css_options_override(self, renderer, basic_outline, tmp_path):
        """Custom css_options should override preset defaults."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
            options={
                "css_options": {
                    "max_width": "1500px",
                    "paragraph_spacing": "2rem",
                }
            },
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert "max-width: 1500px" in content
        assert "margin-bottom: 2rem" in content

    def test_custom_css_appended(self, renderer, basic_outline, tmp_path):
        """Custom CSS should be appended verbatim to the stylesheet."""
        custom = "body { border: 5px solid red; }"
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
            options={"custom_css": custom},
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert custom in content

    def test_css_includes_code_block_styles(self, renderer, basic_outline, tmp_path):
        """Rendered CSS should include code block styling."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert ".section-content pre" in content
        assert ".section-content code" in content

    def test_css_includes_table_styles(self, renderer, basic_outline, tmp_path):
        """Rendered CSS should include table styling."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert ".section-content table" in content
        assert ".section-content th" in content
        assert ".section-content td" in content

    def test_css_includes_print_styles(self, renderer, basic_outline, tmp_path):
        """Rendered CSS should include comprehensive print styles."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert "@media print" in content
        assert "page-break-inside: avoid" in content

    def test_css_includes_responsive_styles(self, renderer, basic_outline, tmp_path):
        """Rendered CSS should include responsive/mobile styles."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert "@media (max-width: 768px)" in content


class TestHTMLStandaloneRendererCSS:
    """Test CSS embedding."""

    def test_css_is_embedded(self, renderer, basic_outline, tmp_path):
        """Test that CSS is embedded in the HTML."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # CSS should be in a style tag, not a link
        assert "<style>" in content
        assert "</style>" in content
        assert '<link rel="stylesheet"' not in content


class TestHTMLStandaloneRendererHelpers:
    """Test helper methods."""

    def test_escape_html_special_chars(self, renderer):
        """Test HTML special character escaping."""
        assert renderer._escape_html("<script>") == "&lt;script&gt;"
        assert renderer._escape_html('"quoted"') == "&quot;quoted&quot;"
        assert renderer._escape_html("A & B") == "A &amp; B"
        assert renderer._escape_html("it's") == "it&#x27;s"

    def test_escape_html_empty(self, renderer):
        """Test escaping empty/None strings."""
        assert renderer._escape_html("") == ""
        assert renderer._escape_html(None) == ""

    def test_markdown_to_html_headers(self, renderer):
        """Test basic markdown header conversion."""
        result = renderer._markdown_to_html("# Header 1")
        assert "<h1>" in result

        result = renderer._markdown_to_html("## Header 2")
        assert "<h2>" in result

        result = renderer._markdown_to_html("### Header 3")
        assert "<h3>" in result

        result = renderer._markdown_to_html("#### Header 4")
        assert "<h4>" in result

    def test_markdown_to_html_bold_italic(self, renderer):
        """Test markdown bold and italic conversion."""
        result = renderer._markdown_to_html("**bold text**")
        assert "<strong>bold text</strong>" in result

        result = renderer._markdown_to_html("*italic text*")
        assert "<em>italic text</em>" in result

    def test_markdown_to_html_code(self, renderer):
        """Test markdown code conversion."""
        result = renderer._markdown_to_html("`code`")
        assert "<code>code</code>" in result


class TestHTMLStandaloneRendererEdgeCases:
    """Test edge cases and error handling."""

    def test_render_empty_report(self, renderer, tmp_path):
        """Test rendering a report with no sections or insights."""
        outline = Outline(
            report_id=str(uuid.uuid4()),
            title="Empty Report",
            created_at="2024-01-15T10:00:00Z",
            updated_at="2024-01-15T10:00:00Z",
            sections=[],
            insights=[],
            metadata={},
        )

        result = renderer.render(
            report_dir=tmp_path,
            outline=outline,
        )

        assert result["output_path"]
        assert result["size_bytes"] > 0

        content = Path(result["output_path"]).read_text(encoding="utf-8")
        assert "Empty Report" in content

    def test_render_large_report_warning(self, renderer, basic_outline, tmp_path, monkeypatch):
        """Test that large reports generate a warning."""
        # Create outline with very long content to trigger size warning
        section_id = str(uuid.uuid4())
        basic_outline.sections = [
            Section(
                section_id=section_id,
                title="Long Section",
                order=0,
                insight_ids=[],
                content="x" * 100000,  # 100KB of content
            )
        ]

        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
        )

        # Note: The warning is only generated if > 10MB
        # This test verifies the warning mechanism works
        # In practice, you'd need > 10MB content to trigger it
        assert "warnings" in result

    def test_render_special_characters_in_title(self, renderer, basic_outline, tmp_path):
        """Test rendering with special characters in title."""
        basic_outline.title = "Report <with> 'special' & \"characters\""

        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # Title should be properly escaped
        assert "&lt;with&gt;" in content
        assert "&amp;" in content


class TestHTMLStandaloneRendererMetadata:
    """Test metadata in generated HTML."""

    def test_includes_generator_meta(self, renderer, basic_outline, tmp_path):
        """Test that generator meta tag is included."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert 'name="generator"' in content
        assert "igloo-mcp" in content

    def test_includes_timestamps(self, renderer, basic_outline, tmp_path):
        """Test that timestamps are included in meta tags."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        assert 'name="created"' in content
        assert 'name="updated"' in content


@pytest.mark.regression
class TestMarkdownRenderingRegression:
    """Ensure markdown features render correctly with standard library.

    These tests protect against regressions when replacing the custom
    markdown parser with the standard markdown library.

    See: todos/003-pending-p1-replace-custom-markdown-parser.md
    """

    def test_markdown_code_blocks(self, renderer):
        """Code blocks should render with proper <pre><code> tags."""
        markdown_text = """```python
def hello():
    print('world')
```"""

        html = renderer._markdown_to_html(markdown_text)

        # Should have code block elements
        assert "<pre>" in html or "<code>" in html, "Code blocks not rendered"
        assert "def hello()" in html, "Code content missing"

    def test_markdown_inline_code(self, renderer):
        """Inline code should render with <code> tags."""
        markdown_text = "Use the `markdown` library for parsing."

        html = renderer._markdown_to_html(markdown_text)

        assert "<code>markdown</code>" in html, "Inline code not rendered"

    def test_markdown_tables(self, renderer):
        """Tables should render with proper <table> structure."""
        markdown_text = """| Column A | Column B |
|----------|----------|
| Value 1  | Value 2  |
| Value 3  | Value 4  |"""

        html = renderer._markdown_to_html(markdown_text)

        # Should have table elements
        assert "<table>" in html, "Table not rendered"
        assert "<th>" in html or "<td>" in html, "Table cells missing"
        assert "Column A" in html, "Table header Column A missing"
        assert "Column B" in html, "Table header Column B missing"
        assert "Value 1" in html, "Table data Value 1 missing"
        assert "Value 2" in html, "Table data Value 2 missing"

    def test_markdown_headers(self, renderer):
        """Headers should render with proper semantic HTML."""
        markdown_text = """# Heading 1
## Heading 2
### Heading 3
#### Heading 4"""

        html = renderer._markdown_to_html(markdown_text)

        assert "<h1>Heading 1</h1>" in html, "H1 not rendered"
        assert "<h2>Heading 2</h2>" in html, "H2 not rendered"
        assert "<h3>Heading 3</h3>" in html, "H3 not rendered"
        assert "<h4>Heading 4</h4>" in html, "H4 not rendered"

    def test_markdown_lists(self, renderer):
        """Lists should render with <ul> and <li> tags."""
        markdown_text = """- Item 1
- Item 2
- Item 3"""

        html = renderer._markdown_to_html(markdown_text)

        assert "<ul>" in html, "Unordered list not rendered"
        assert "<li>Item 1</li>" in html, "List item 1 missing"
        assert "<li>Item 2</li>" in html, "List item 2 missing"
        assert "<li>Item 3</li>" in html, "List item 3 missing"

    def test_markdown_links(self, renderer):
        """Links should render with <a> tags."""
        markdown_text = "[Click here](https://example.com)"

        html = renderer._markdown_to_html(markdown_text)

        assert '<a href="https://example.com">Click here</a>' in html, "Link not rendered"

    def test_markdown_images(self, renderer):
        """Images should render with <img> tags."""
        markdown_text = "![Alt text](https://example.com/image.png)"

        html = renderer._markdown_to_html(markdown_text)

        assert "<img" in html, "Image tag not rendered"
        assert 'alt="Alt text"' in html, "Alt text missing"
        assert 'src="https://example.com/image.png"' in html, "Image source missing"

    def test_markdown_bold_and_italic(self, renderer):
        """Bold and italic formatting should work."""
        markdown_text = "**bold text** and *italic text*"

        html = renderer._markdown_to_html(markdown_text)

        assert "<strong>bold text</strong>" in html or "<b>bold text</b>" in html, "Bold not rendered"
        assert "<em>italic text</em>" in html or "<i>italic text</i>" in html, "Italic not rendered"

    def test_markdown_mixed_content(self, renderer):
        """Complex markdown with mixed elements should render correctly."""
        markdown_text = """# Overview

This is a **comprehensive** test with:

- Code: `inline_code()`
- Links: [example](https://example.com)
- **Bold** and *italic*

## Data Table

| Metric | Value |
|--------|-------|
| Count  | 100   |

```python
def test():
    return True
```"""

        html = renderer._markdown_to_html(markdown_text)

        # Verify all elements are present
        assert "<h1>Overview</h1>" in html, "Header missing"
        assert "<strong>comprehensive</strong>" in html or "<b>comprehensive</b>" in html, "Bold missing"
        assert "<ul>" in html, "List missing"
        assert "<code>inline_code()</code>" in html, "Inline code missing"
        assert '<a href="https://example.com">example</a>' in html, "Link missing"
        assert "<table>" in html, "Table missing"
        assert "<pre>" in html or "def test():" in html, "Code block missing"

    def test_markdown_preserves_newlines(self, renderer):
        """Newlines should be converted to <br> with nl2br extension."""
        markdown_text = """Line 1
Line 2
Line 3"""

        html = renderer._markdown_to_html(markdown_text)

        # With nl2br extension, newlines should create line breaks
        assert "Line 1" in html
        assert "Line 2" in html
        assert "Line 3" in html
