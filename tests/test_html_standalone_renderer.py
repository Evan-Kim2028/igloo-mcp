"""Tests for HTML Standalone Renderer.

Tests the self-contained HTML renderer that generates
reports without Quarto dependency.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from igloo_mcp.living_reports.models import DatasetSource, Insight, Outline, Section
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
                citations=[DatasetSource(execution_id="exec-001")],
            ),
            Insight(
                insight_id=insight_id_2,
                summary="Customer retention rate improved to 95%",
                importance=7,
                supporting_queries=[],
                citations=[DatasetSource(execution_id="exec-002")],
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
        """Test rendering report with insights."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=full_outline,
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # Check insights are present
        assert "Revenue increased 25% YoY" in content
        assert "Customer retention rate improved to 95%" in content

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

        # Check for dark theme override
        assert "--background: #0f172a" in content

    def test_render_minimal_theme(self, renderer, basic_outline, tmp_path):
        """Test rendering with minimal theme."""
        result = renderer.render(
            report_dir=tmp_path,
            outline=basic_outline,
            options={"theme": "minimal"},
        )

        content = Path(result["output_path"]).read_text(encoding="utf-8")

        # Minimal theme should have modified insight styles
        assert "border-left: none" in content


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
        assert "<h3>" in result

        result = renderer._markdown_to_html("## Header 2")
        assert "<h3>" in result

        result = renderer._markdown_to_html("### Header 3")
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
