"""Markdown renderer for living reports.

Generates clean Markdown files suitable for publishing to GitHub, GitLab,
or other Markdown-based platforms.
"""

from __future__ import annotations

import base64
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from igloo_mcp.living_reports.models import Insight, Outline, Section


class MarkdownRenderer:
    """Renderer that produces Markdown files for GitHub/GitLab publishing.

    Features:
    - YAML frontmatter for static site generators (Jekyll, Hugo)
    - Table of Contents generation
    - Insight blockquotes with citations
    - Platform-specific options (github, gitlab, generic)
    - Image handling modes (relative, base64, absolute)
    """

    def render(
        self,
        report_dir: Path,
        outline: Outline,
        datasets: dict[str, Any] | None = None,
        hints: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Render report to Markdown format.

        Args:
            report_dir: Directory containing report data
            outline: Report outline object
            datasets: Optional dataset sources
            hints: Render hints (citation_map, query_provenance, etc.)
            options: Additional options:
                - include_frontmatter: bool (default: True)
                - include_toc: bool (default: True)
                - image_mode: 'relative' | 'base64' | 'absolute' (default: 'relative')
                - platform: 'github' | 'gitlab' | 'generic' (default: 'generic')
                - output_filename: str (default: 'README.md')

        Returns:
            Dictionary with:
            - output_path: Path to generated Markdown file
            - size_bytes: File size
            - images_copied: Number of images copied (if image_mode='relative')
            - warnings: List of warnings
        """
        datasets = datasets or {}
        hints = hints or {}
        options = options or {}

        warnings: list[str] = []
        images_copied = 0

        # Extract options
        include_frontmatter = options.get("include_frontmatter", True)
        include_toc = options.get("include_toc", True)
        image_mode = options.get("image_mode", "relative")
        platform = options.get("platform", "generic")
        output_filename = options.get("output_filename", "report.md")

        # Extract hints
        citation_map = hints.get("citation_map", {})
        citation_details = hints.get("citation_details", {})

        # Handle images if image_mode is 'relative'
        images_dir = None
        if image_mode == "relative":
            images_dir = report_dir / "images"
            images_dir.mkdir(exist_ok=True)
            images_copied = self._copy_images_to_dir(outline, report_dir, images_dir, warnings)

        # Generate Markdown content
        md_parts = []

        # Frontmatter
        if include_frontmatter:
            md_parts.append(self._render_frontmatter(outline, platform))

        # Title
        md_parts.append(f"# {outline.title}\n")

        # Table of Contents
        if include_toc:
            md_parts.append(self._render_toc(outline))

        # Sections
        sorted_sections = sorted(outline.sections, key=lambda s: s.order)
        for section in sorted_sections:
            md_parts.append(self._render_section(section, outline, citation_map, image_mode, images_dir))

        # Data Sources appendix (if citations exist)
        if citation_map:
            md_parts.append(self._render_citations_appendix(citation_map, citation_details))

        # Footer
        md_parts.append(self._render_footer(outline))

        # Join and write content
        content = "\n".join(md_parts)
        output_path = report_dir / output_filename
        output_path.write_text(content, encoding="utf-8")

        size_bytes = output_path.stat().st_size

        return {
            "output_path": str(output_path),
            "size_bytes": size_bytes,
            "images_copied": images_copied,
            "warnings": warnings,
        }

    def _render_frontmatter(self, outline: Outline, platform: str) -> str:
        """Render YAML frontmatter for static site generators.

        Args:
            outline: Report outline
            platform: Target platform (github, gitlab, generic)

        Returns:
            YAML frontmatter string
        """
        frontmatter: dict[str, Any] = {
            "title": outline.title,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "generator": "igloo-mcp",
        }

        # Add tags if present
        tags = outline.metadata.get("tags", [])
        if tags:
            frontmatter["tags"] = tags

        # Platform-specific additions
        if platform == "github":
            # GitHub Pages / Jekyll compatible
            frontmatter["layout"] = "default"
        elif platform == "gitlab":
            # GitLab Pages compatible
            pass

        # Format as YAML
        yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
        return f"---\n{yaml_str}---\n"

    def _render_toc(self, outline: Outline) -> str:
        """Render table of contents.

        Args:
            outline: Report outline

        Returns:
            Markdown table of contents
        """
        lines = ["## Table of Contents\n"]

        sorted_sections = sorted(outline.sections, key=lambda s: s.order)
        for section in sorted_sections:
            # Create anchor from title (lowercase, spaces to dashes)
            anchor = section.title.lower().replace(" ", "-")
            # Remove special characters that might break anchors
            anchor = "".join(c for c in anchor if c.isalnum() or c == "-")
            lines.append(f"- [{section.title}](#{anchor})")

        # Add Data Sources link if there are citations
        has_citations = any((insight.citations or insight.supporting_queries) for insight in outline.insights)
        if has_citations:
            lines.append("- [Data Sources](#data-sources)")

        lines.append("")  # Empty line after TOC
        lines.append("---\n")

        return "\n".join(lines)

    def _render_section(
        self,
        section: Section,
        outline: Outline,
        citation_map: dict[str, int],
        image_mode: str,
        images_dir: Path | None,
    ) -> str:
        """Render a single section.

        Args:
            section: Section object
            outline: Full outline (to look up insights)
            citation_map: Citation number mapping
            image_mode: Image handling mode
            images_dir: Directory for relative images

        Returns:
            Markdown for the section
        """
        parts = [f"## {section.title}\n"]

        # Section content (prose)
        has_content = bool(section.content)
        if section.content:
            parts.append(section.content)
            parts.append("")
        elif section.notes:
            parts.append(section.notes)
            parts.append("")

        # Render insights as blockquotes (only if no prose content)
        if not has_content and section.insight_ids:
            for insight_id in section.insight_ids:
                try:
                    insight = outline.get_insight(insight_id)

                    # Render chart if insight has one
                    chart_id = insight.metadata.get("chart_id") if insight.metadata else None
                    if chart_id:
                        chart_md = self._render_chart(outline, chart_id, image_mode, images_dir)
                        if chart_md:
                            parts.append(chart_md)

                    # Render insight
                    insight_md = self._render_insight(insight, citation_map)
                    parts.append(insight_md)
                except ValueError:
                    parts.append(f"> *Insight not found: {insight_id}*\n")

        parts.append("---\n")
        return "\n".join(parts)

    def _render_insight(self, insight: Insight, citation_map: dict[str, int]) -> str:
        """Render a single insight as a blockquote.

        Args:
            insight: Insight object
            citation_map: Citation number mapping

        Returns:
            Markdown blockquote for the insight
        """
        # Get citation reference
        citation_ref = ""
        references = insight.citations or insight.supporting_queries
        if references and len(references) > 0:
            exec_id = references[0].execution_id
            if exec_id and exec_id in citation_map:
                citation_num = citation_map[exec_id]
                citation_ref = f" [[{citation_num}]](#citation-{citation_num})"

        # Importance indicator
        stars = "★" * min(insight.importance, 5)
        importance_text = f"*Importance: {insight.importance}/10*"

        # Build blockquote
        lines = [
            f"> **Insight:** {insight.summary}{citation_ref}",
            ">",
            f"> {importance_text} {stars}",
            "",
        ]
        return "\n".join(lines)

    def _render_chart(
        self,
        outline: Outline,
        chart_id: str,
        image_mode: str,
        images_dir: Path | None,
    ) -> str | None:
        """Render a chart image.

        Args:
            outline: Report outline
            chart_id: Chart identifier
            image_mode: Image handling mode
            images_dir: Directory for relative images

        Returns:
            Markdown image string or None
        """
        charts_metadata = outline.metadata.get("charts", {})
        chart_meta = charts_metadata.get(chart_id)
        if not chart_meta:
            return None

        chart_path = Path(chart_meta.get("path", ""))
        if not chart_path.exists():
            return f"*[Chart not found: {chart_id}]*\n"

        description = chart_meta.get("description", "Chart")

        if image_mode == "base64":
            # Embed as base64 data URI
            try:
                data = chart_path.read_bytes()
                b64 = base64.b64encode(data).decode("utf-8")
                ext = chart_path.suffix.lower().lstrip(".")
                mime_types = {
                    "png": "image/png",
                    "jpg": "image/jpeg",
                    "jpeg": "image/jpeg",
                    "gif": "image/gif",
                    "svg": "image/svg+xml",
                }
                mime = mime_types.get(ext, "image/png")
                return f"![{description}](data:{mime};base64,{b64})\n"
            except Exception:
                return f"*[Failed to embed chart: {chart_id}]*\n"

        elif image_mode == "relative" and images_dir:
            # Use relative path (assumes image was copied)
            rel_path = f"images/{chart_path.name}"
            return f"![{description}]({rel_path})\n"

        else:
            # Absolute path
            return f"![{description}]({chart_path})\n"

    def _render_citations_appendix(
        self,
        citation_map: dict[str, int],
        citation_details: dict[str, Any],
    ) -> str:
        """Render the data sources appendix.

        Args:
            citation_map: Mapping of execution_id to citation number
            citation_details: Details for each citation

        Returns:
            Markdown for citations appendix
        """
        lines = ["## Data Sources\n"]

        sorted_citations = sorted(citation_map.items(), key=lambda x: x[1])

        for exec_id, citation_num in sorted_citations:
            details = citation_details.get(exec_id, {})
            timestamp = details.get("timestamp", "Unknown")
            statement = details.get("statement_preview", "")
            rowcount = details.get("rowcount", "N/A")

            lines.append(f'<a id="citation-{citation_num}"></a>')
            lines.append(f"**[{citation_num}]** Query `{exec_id[:12]}...`")
            lines.append(f"- Executed: {timestamp}")
            lines.append(f"- Rows returned: {rowcount}")
            if statement:
                lines.append(f"- Preview: `{statement[:80]}...`")
            lines.append("")

        return "\n".join(lines)

    def _render_footer(self, outline: Outline) -> str:
        """Render document footer.

        Args:
            outline: Report outline

        Returns:
            Footer markdown
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        return f"\n---\n\n*Generated by [igloo-mcp](https://github.com/yourusername/igloo-mcp) on {now}*\n"

    def _copy_images_to_dir(
        self,
        outline: Outline,
        report_dir: Path,
        images_dir: Path,
        warnings: list[str],
    ) -> int:
        """Copy chart images to the images directory.

        Args:
            outline: Report outline
            report_dir: Report directory
            images_dir: Target images directory
            warnings: List to append warnings to

        Returns:
            Number of images copied
        """
        copied = 0
        charts_metadata = outline.metadata.get("charts", {})

        for chart_id, chart_meta in charts_metadata.items():
            chart_path = Path(chart_meta.get("path", ""))
            if not chart_path.exists():
                warnings.append(f"Chart file not found: {chart_path}")
                continue

            try:
                dest_path = images_dir / chart_path.name
                # Handle name conflicts
                counter = 1
                while dest_path.exists():
                    stem = chart_path.stem
                    suffix = chart_path.suffix
                    dest_path = images_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

                shutil.copy2(chart_path, dest_path)
                copied += 1
            except Exception as e:
                warnings.append(f"Failed to copy chart {chart_id}: {e}")

        return copied


__all__ = ["MarkdownRenderer"]
