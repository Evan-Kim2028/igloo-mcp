"""Tests for MarkdownRenderer - GitHub/GitLab publishing.

Tests the markdown rendering functionality including frontmatter,
TOC generation, insight blockquotes, and image handling.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from igloo_mcp.living_reports.models import DatasetSource, Insight, Outline, Section
from igloo_mcp.living_reports.renderers.markdown import MarkdownRenderer


def make_report_id() -> str:
    """Generate a valid report ID (plain UUID)."""
    return str(uuid.uuid4())


def make_section_id() -> str:
    """Generate a valid section ID."""
    return str(uuid.uuid4())


def make_insight_id() -> str:
    """Generate a valid insight ID."""
    return str(uuid.uuid4())


@pytest.fixture
def renderer():
    """Create MarkdownRenderer instance."""
    return MarkdownRenderer()


@pytest.fixture
def sample_outline():
    """Create a sample outline for testing."""
    section1_id = make_section_id()
    section2_id = make_section_id()
    insight1_id = make_insight_id()
    insight2_id = make_insight_id()

    return Outline(
        report_id=make_report_id(),
        title="Test Report for Markdown",
        created_at="2024-01-15T10:00:00Z",
        updated_at="2024-01-20T15:30:00Z",
        outline_version=3,
        metadata={
            "tags": ["test", "markdown", "rendering"],
            "status": "active",
        },
        sections=[
            Section(
                section_id=section1_id,
                title="Executive Summary",
                order=0,
                insight_ids=[insight1_id],
                content="This is the executive summary with **bold** and *italic* text.",
            ),
            Section(
                section_id=section2_id,
                title="Detailed Analysis",
                order=1,
                insight_ids=[insight2_id],
                notes="Analysis notes here",
            ),
        ],
        insights=[
            Insight(
                insight_id=insight1_id,
                summary="Revenue increased by 25% year-over-year",
                importance=9,
                status="active",
                supporting_queries=[DatasetSource(execution_id="exec_123")],
            ),
            Insight(
                insight_id=insight2_id,
                summary="Customer retention improved to 95%",
                importance=7,
                status="active",
                supporting_queries=[DatasetSource(execution_id="exec_456")],
            ),
        ],
    )


@pytest.fixture
def outline_with_charts(sample_outline, tmp_path):
    """Create outline with chart metadata and actual chart files."""
    # Create chart files
    chart1_path = tmp_path / "charts" / "revenue_chart.png"
    chart1_path.parent.mkdir(parents=True, exist_ok=True)
    chart1_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake png data")

    chart2_path = tmp_path / "charts" / "retention_chart.svg"
    chart2_path.write_text("<svg></svg>")

    # Add chart metadata to outline
    sample_outline.metadata["charts"] = {
        "chart_revenue": {
            "path": str(chart1_path),
            "description": "Revenue Growth Chart",
        },
        "chart_retention": {
            "path": str(chart2_path),
            "description": "Customer Retention Chart",
        },
    }

    # Link charts to insights
    sample_outline.insights[0].metadata = {"chart_id": "chart_revenue"}
    sample_outline.insights[1].metadata = {"chart_id": "chart_retention"}

    return sample_outline


class TestMarkdownRendererBasic:
    """Test basic rendering functionality."""

    def test_render_creates_file(self, renderer, sample_outline, tmp_path):
        """Render should create a markdown file."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
        )

        assert "output_path" in result
        output_path = Path(result["output_path"])
        assert output_path.exists()
        assert output_path.suffix == ".md"

    def test_render_returns_size(self, renderer, sample_outline, tmp_path):
        """Render should return file size."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
        )

        assert "size_bytes" in result
        assert result["size_bytes"] > 0

    def test_render_custom_filename(self, renderer, sample_outline, tmp_path):
        """Render should support custom output filename."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
            options={"output_filename": "README.md"},
        )

        output_path = Path(result["output_path"])
        assert output_path.name == "README.md"


class TestMarkdownFrontmatter:
    """Test YAML frontmatter generation."""

    def test_frontmatter_included_by_default(self, renderer, sample_outline, tmp_path):
        """Frontmatter should be included by default."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
        )

        content = Path(result["output_path"]).read_text()
        assert content.startswith("---\n")
        assert "title:" in content
        assert "Test Report for Markdown" in content

    def test_frontmatter_can_be_disabled(self, renderer, sample_outline, tmp_path):
        """Frontmatter can be disabled via options."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
            options={"include_frontmatter": False},
        )

        content = Path(result["output_path"]).read_text()
        assert not content.startswith("---\n")

    def test_frontmatter_includes_tags(self, renderer, sample_outline, tmp_path):
        """Frontmatter should include tags from metadata."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
        )

        content = Path(result["output_path"]).read_text()
        assert "tags:" in content
        assert "test" in content
        assert "markdown" in content

    def test_frontmatter_github_platform(self, renderer, sample_outline, tmp_path):
        """GitHub platform should add layout field."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
            options={"platform": "github"},
        )

        content = Path(result["output_path"]).read_text()
        assert "layout:" in content


class TestMarkdownTableOfContents:
    """Test table of contents generation."""

    def test_toc_included_by_default(self, renderer, sample_outline, tmp_path):
        """TOC should be included by default."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
        )

        content = Path(result["output_path"]).read_text()
        assert "## Table of Contents" in content
        assert "Executive Summary" in content
        assert "Detailed Analysis" in content

    def test_toc_can_be_disabled(self, renderer, sample_outline, tmp_path):
        """TOC can be disabled via options."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
            options={"include_toc": False},
        )

        content = Path(result["output_path"]).read_text()
        assert "## Table of Contents" not in content

    def test_toc_links_use_anchors(self, renderer, sample_outline, tmp_path):
        """TOC links should use proper anchor format."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
        )

        content = Path(result["output_path"]).read_text()
        assert "(#executive-summary)" in content
        assert "(#detailed-analysis)" in content

    def test_toc_includes_data_sources_link(self, renderer, sample_outline, tmp_path):
        """TOC should include Data Sources link when citations exist."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
            hints={"citation_map": {"exec_123": 1}},
        )

        content = Path(result["output_path"]).read_text()
        assert "(#data-sources)" in content


class TestMarkdownSections:
    """Test section rendering."""

    def test_sections_rendered_in_order(self, renderer, sample_outline, tmp_path):
        """Sections should be rendered in order."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
        )

        content = Path(result["output_path"]).read_text()
        exec_pos = content.find("## Executive Summary")
        detail_pos = content.find("## Detailed Analysis")
        assert exec_pos < detail_pos

    def test_section_content_rendered(self, renderer, sample_outline, tmp_path):
        """Section content should be rendered."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
        )

        content = Path(result["output_path"]).read_text()
        assert "executive summary with **bold**" in content

    def test_section_separators(self, renderer, sample_outline, tmp_path):
        """Sections should have separators."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
        )

        content = Path(result["output_path"]).read_text()
        # Should have horizontal rules between sections
        assert "---" in content


class TestMarkdownInsights:
    """Test insight rendering as blockquotes."""

    def test_insights_rendered_as_blockquotes(self, renderer, tmp_path):
        """Insights should be rendered as blockquotes (when no prose content)."""
        # Create outline with section without prose content
        section_id = make_section_id()
        insight_id = make_insight_id()

        outline = Outline(
            report_id=make_report_id(),
            title="Insight Test",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            outline_version=1,
            metadata={},
            sections=[
                Section(
                    section_id=section_id,
                    title="Insights Section",
                    order=0,
                    insight_ids=[insight_id],
                    # No content - insights should render
                ),
            ],
            insights=[
                Insight(
                    insight_id=insight_id,
                    summary="Test insight summary",
                    importance=8,
                    status="active",
                    supporting_queries=[],
                ),
            ],
        )

        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=outline,
        )

        content = Path(result["output_path"]).read_text()
        assert "> **Insight:**" in content
        assert "Test insight summary" in content

    def test_insight_importance_shown(self, renderer, tmp_path):
        """Insight importance should be displayed."""
        section_id = make_section_id()
        insight_id = make_insight_id()

        outline = Outline(
            report_id=make_report_id(),
            title="Importance Test",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            outline_version=1,
            metadata={},
            sections=[
                Section(
                    section_id=section_id,
                    title="Section",
                    order=0,
                    insight_ids=[insight_id],
                ),
            ],
            insights=[
                Insight(
                    insight_id=insight_id,
                    summary="High importance insight",
                    importance=9,
                    status="active",
                    supporting_queries=[],
                ),
            ],
        )

        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=outline,
        )

        content = Path(result["output_path"]).read_text()
        assert "9/10" in content
        assert "★" in content  # Stars for importance


class TestMarkdownCitations:
    """Test citation rendering."""

    def test_citations_appendix_rendered(self, renderer, sample_outline, tmp_path):
        """Citations appendix should be rendered when citation_map provided."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        citation_map = {
            "exec_123": 1,
            "exec_456": 2,
        }
        citation_details = {
            "exec_123": {
                "timestamp": "2024-01-15T10:00:00Z",
                "statement_preview": "SELECT * FROM revenue...",
                "rowcount": 150,
            },
        }

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
            hints={
                "citation_map": citation_map,
                "citation_details": citation_details,
            },
        )

        content = Path(result["output_path"]).read_text()
        assert "## Data Sources" in content
        assert "exec_123" in content
        assert "[1]" in content

    def test_insight_citation_references(self, renderer, tmp_path):
        """Insights should reference citations inline."""
        section_id = make_section_id()
        insight_id = make_insight_id()

        outline = Outline(
            report_id=make_report_id(),
            title="Citation Ref Test",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            outline_version=1,
            metadata={},
            sections=[
                Section(
                    section_id=section_id,
                    title="Section",
                    order=0,
                    insight_ids=[insight_id],
                ),
            ],
            insights=[
                Insight(
                    insight_id=insight_id,
                    summary="Cited insight",
                    importance=8,
                    status="active",
                    supporting_queries=[DatasetSource(execution_id="exec_abc")],
                ),
            ],
        )

        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=outline,
            hints={"citation_map": {"exec_abc": 1}},
        )

        content = Path(result["output_path"]).read_text()
        assert "[[1]]" in content
        assert "#citation-1" in content


class TestMarkdownImageHandling:
    """Test image/chart handling modes."""

    def test_relative_image_mode_copies_files(self, renderer, outline_with_charts, tmp_path):
        """Relative mode should copy images to images/ directory."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=outline_with_charts,
            options={"image_mode": "relative"},
        )

        assert result["images_copied"] >= 1
        images_dir = report_dir / "images"
        assert images_dir.exists()

    def test_base64_image_mode_embeds(self, renderer, outline_with_charts, tmp_path):
        """Base64 mode should embed images as data URIs."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=outline_with_charts,
            options={"image_mode": "base64"},
        )

        content = Path(result["output_path"]).read_text()
        assert "data:image/" in content
        assert ";base64," in content

    def test_absolute_image_mode_uses_paths(self, renderer, outline_with_charts, tmp_path):
        """Absolute mode should use original file paths."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=outline_with_charts,
            options={"image_mode": "absolute"},
        )

        content = Path(result["output_path"]).read_text()
        # Should contain absolute path to charts
        assert "charts/" in content or str(tmp_path) in content


class TestMarkdownFooter:
    """Test footer generation."""

    def test_footer_included(self, renderer, sample_outline, tmp_path):
        """Footer should be included."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
        )

        content = Path(result["output_path"]).read_text()
        assert "Generated by" in content
        assert "igloo-mcp" in content


class TestMarkdownWarnings:
    """Test warning generation."""

    def test_missing_chart_warning(self, renderer, tmp_path):
        """Missing chart files should generate warnings."""
        outline = Outline(
            report_id=make_report_id(),
            title="Missing Chart Test",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            outline_version=1,
            metadata={
                "charts": {
                    "missing_chart": {
                        "path": "/nonexistent/path/chart.png",
                        "description": "Missing chart",
                    },
                },
            },
            sections=[],
            insights=[],
        )

        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=outline,
            options={"image_mode": "relative"},
        )

        assert "warnings" in result
        assert len(result["warnings"]) >= 1
        assert any("not found" in w.lower() for w in result["warnings"])


class TestMarkdownPlatformOptions:
    """Test platform-specific options."""

    def test_github_platform(self, renderer, sample_outline, tmp_path):
        """GitHub platform should work."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
            options={"platform": "github"},
        )

        content = Path(result["output_path"]).read_text()
        assert "layout: default" in content

    def test_gitlab_platform(self, renderer, sample_outline, tmp_path):
        """GitLab platform should work."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
            options={"platform": "gitlab"},
        )

        # Should render without errors
        assert Path(result["output_path"]).exists()

    def test_generic_platform(self, renderer, sample_outline, tmp_path):
        """Generic platform should work."""
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        result = renderer.render(
            report_dir=report_dir,
            outline=sample_outline,
            options={"platform": "generic"},
        )

        # Should render without errors
        assert Path(result["output_path"]).exists()
