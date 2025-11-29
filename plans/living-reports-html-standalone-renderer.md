# Living Reports: HTML Standalone Renderer Enhancement

**Issue**: Current Quarto rendering requires external files and can fail with formatting errors. Users want a **single self-contained file** with embedded charts.

**Solution**: Add `html_standalone` format to `render_report` that generates a single HTML file with all assets (charts, CSS) embedded as base64.

---

## Problem Statement

### Current Pain Points

1. **Multiple files**: Quarto HTML generates separate files for charts/assets
2. **Broken links**: `file://` paths break when report is moved/shared
3. **Quarto dependency**: Requires Quarto installation (can fail)
4. **Format errors**: Percentage signs and special chars break Jinja2 rendering
5. **Sharing friction**: Can't easily email/Slack a single report

### User Need

> "Ideally is there a better way to just give me a single link that has all of the charts embedded into it?"

Users want:
- ✅ Single HTML file
- ✅ Charts embedded (no external dependencies)
- ✅ Works offline
- ✅ Email/Slack friendly
- ✅ Print to PDF from browser

---

## Proposed Solution

### 1. Add New Renderer: `HTMLStandaloneRenderer`

**File**: `src/igloo_mcp/living_reports/renderers/html_standalone.py`

```python
"""Self-contained HTML renderer with embedded charts."""

import base64
from pathlib import Path
from typing import Any, Dict, Optional

from ..models import Outline


class HTMLStandaloneRenderer:
    """Render living reports as self-contained HTML with embedded charts."""

    def render(
        self,
        report_dir: Path,
        outline: Outline,
        datasets: Optional[Dict[str, Any]] = None,
        hints: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Render report to self-contained HTML.

        Args:
            report_dir: Report directory
            outline: Outline object
            datasets: Dataset sources (unused for now)
            hints: Render hints (chart paths, etc.)
            options: Render options (theme, etc.)

        Returns:
            Path to generated HTML file
        """
        # 1. Collect all charts from sections
        charts = self._collect_charts(outline, report_dir, hints)

        # 2. Embed charts as base64
        embedded_charts = self._embed_charts(charts)

        # 3. Render HTML from template
        html_content = self._render_template(
            outline=outline,
            embedded_charts=embedded_charts,
            options=options or {},
        )

        # 4. Write to report_dir
        output_path = report_dir / "report.html"
        output_path.write_text(html_content, encoding="utf-8")

        return output_path

    def _collect_charts(
        self,
        outline: Outline,
        report_dir: Path,
        hints: Optional[Dict[str, Any]],
    ) -> Dict[str, Path]:
        """Collect chart file paths from outline metadata.

        Returns:
            Dict mapping chart_id -> absolute file path
        """
        charts = {}

        # Strategy 1: From hints (if provided)
        if hints and "charts" in hints:
            for chart_id, chart_path in hints["charts"].items():
                charts[chart_id] = Path(chart_path)

        # Strategy 2: From section content (scan for image markdown)
        # TODO: Parse ![](path) from section.content

        # Strategy 3: From report_dir/charts/ directory
        chart_dir = report_dir / "charts"
        if chart_dir.exists():
            for chart_file in chart_dir.glob("*.png"):
                charts[chart_file.stem] = chart_file

        return charts

    def _embed_charts(self, charts: Dict[str, Path]) -> Dict[str, str]:
        """Convert chart files to base64 data URIs.

        Args:
            charts: Dict mapping chart_id -> file path

        Returns:
            Dict mapping chart_id -> data URI (data:image/png;base64,...)
        """
        embedded = {}

        for chart_id, chart_path in charts.items():
            if not chart_path.exists():
                continue

            # Read file as binary
            with open(chart_path, "rb") as f:
                chart_bytes = f.read()

            # Encode as base64
            b64_data = base64.b64encode(chart_bytes).decode("utf-8")

            # Determine mime type from extension
            mime_type = "image/png"
            if chart_path.suffix.lower() == ".jpg" or chart_path.suffix.lower() == ".jpeg":
                mime_type = "image/jpeg"
            elif chart_path.suffix.lower() == ".svg":
                mime_type = "image/svg+xml"

            # Create data URI
            embedded[chart_id] = f"data:{mime_type};base64,{b64_data}"

        return embedded

    def _render_template(
        self,
        outline: Outline,
        embedded_charts: Dict[str, str],
        options: Dict[str, Any],
    ) -> str:
        """Render HTML template with outline content and embedded charts.

        Args:
            outline: Outline object
            embedded_charts: Dict mapping chart_id -> data URI
            options: Render options (theme, toc, etc.)

        Returns:
            Complete HTML string
        """
        from jinja2 import Environment, FileSystemLoader

        # Load template
        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))

        # Add custom filter for chart embedding
        def embed_chart(chart_ref: str) -> str:
            """Replace chart reference with embedded data URI."""
            # Handle various formats:
            # - chart_id (simple lookup)
            # - file:///path/to/chart.png (extract and lookup)
            # - /path/to/chart.png (extract and lookup)

            if chart_ref.startswith("file://"):
                chart_id = Path(chart_ref.replace("file://", "")).stem
            elif chart_ref.startswith("/"):
                chart_id = Path(chart_ref).stem
            else:
                chart_id = chart_ref

            return embedded_charts.get(chart_id, chart_ref)

        env.filters["embed_chart"] = embed_chart

        template = env.get_template("standalone.html.j2")

        # Render
        return template.render(
            outline=outline,
            charts=embedded_charts,
            options=options,
        )
```

### 2. Add Template: `templates/standalone.html.j2`

**File**: `src/igloo_mcp/living_reports/renderers/templates/standalone.html.j2`

```jinja2
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ outline.title }}</title>
    <style>
        /* Modern, professional CSS */
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #34495e;
            margin-top: 40px;
            border-left: 4px solid #3498db;
            padding-left: 15px;
        }
        h3 {
            color: #555;
            margin-top: 30px;
        }
        .section {
            margin: 30px 0;
        }
        .insight {
            background: #f8f9fa;
            border-left: 4px solid #3498db;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }
        .chart {
            margin: 30px 0;
            text-align: center;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .chart img {
            max-width: 100%;
            height: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #3498db;
            color: white;
        }
        tr:hover {
            background: #f5f5f5;
        }
        .metadata {
            background: #e8f4f8;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            font-size: 0.9em;
        }
        .citation {
            font-size: 0.85em;
            color: #666;
            margin-top: 10px;
        }

        /* Print styles */
        @media print {
            body {
                background: white;
            }
            .container {
                box-shadow: none;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ outline.title }}</h1>

        {% if outline.metadata.summary %}
        <div class="metadata">
            {{ outline.metadata.summary }}
        </div>
        {% endif %}

        <div class="metadata">
            <strong>Created:</strong> {{ outline.created_at }}<br>
            <strong>Last Updated:</strong> {{ outline.updated_at }}<br>
            <strong>Version:</strong> {{ outline.outline_version }}<br>
            <strong>Report ID:</strong> <code>{{ outline.report_id }}</code>
        </div>

        {% for section in outline.sections %}
        <div class="section">
            <h2>{{ section.title }}</h2>

            {% if section.notes %}
            <p>{{ section.notes }}</p>
            {% endif %}

            {% if section.content %}
            <div class="section-content">
                {# Replace chart references with embedded data URIs #}
                {{ section.content | replace_charts(charts) | safe }}
            </div>
            {% endif %}

            {% for insight_id in section.insight_ids %}
            {% set insight = outline.get_insight(insight_id) %}
            {% if insight %}
            <div class="insight">
                <h3>{{ insight.summary }}</h3>

                <p><strong>Importance:</strong> {{ insight.importance }}/10</p>

                {% if insight.citations %}
                <div class="citation">
                    <strong>Citations:</strong>
                    {% for citation in insight.citations %}
                    <code>{{ citation.execution_id }}</code>{% if not loop.last %}, {% endif %}
                    {% endfor %}
                </div>
                {% endif %}
            </div>
            {% endif %}
            {% endfor %}
        </div>
        {% endfor %}
    </div>
</body>
</html>
```

### 3. Update `render_report` Tool

**File**: `src/igloo_mcp/mcp/tools/render_report.py` (modifications)

```python
# Add import
from igloo_mcp.living_reports.renderers.html_standalone import HTMLStandaloneRenderer

# In tool execution:
def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
    format = arguments.get("format", "html")

    # ... existing code ...

    # Route to appropriate renderer
    if format == "html_standalone":
        # Use standalone renderer
        renderer = HTMLStandaloneRenderer()
        output_path = renderer.render(
            report_dir=report_dir,
            outline=outline,
            datasets=datasets,
            hints=render_hints,
            options=options,
        )

        return {
            "status": "success",
            "output_path": str(output_path),
            "format": "html_standalone",
            "message": "Self-contained HTML report generated (charts embedded)",
        }

    elif format in ["html", "pdf", "markdown"]:
        # Use existing Quarto renderer
        # ... existing code ...
```

---

## Implementation Plan

### Phase 1: Basic Renderer (Week 1)
- [ ] Create `HTMLStandaloneRenderer` class
- [ ] Create `standalone.html.j2` template
- [ ] Add chart collection logic (from file paths)
- [ ] Add base64 embedding logic
- [ ] Basic HTML generation (sections + insights)

### Phase 2: Chart Integration (Week 2)
- [ ] Support `file://` path replacement in section content
- [ ] Support chart registry in report metadata
- [ ] Handle multiple chart formats (PNG, JPG, SVG)
- [ ] Add chart size limits (warn if >5MB)
- [ ] Fallback to external links if chart missing

### Phase 3: Tool Integration (Week 3)
- [ ] Update `render_report` tool to support `format="html_standalone"`
- [ ] Add validation for chart paths
- [ ] Add user-facing documentation
- [ ] Update tool schema

### Phase 4: Advanced Features (Week 4)
- [ ] CSS theme options (light/dark, color schemes)
- [ ] Table of contents generation
- [ ] Citation footnotes
- [ ] Export to PDF via browser print
- [ ] Collapsible sections

---

## Chart Management Architecture

### Proposed: Chart Registry in Report Metadata

```json
{
  "report_id": "...",
  "title": "MON TGE Analysis",
  "metadata": {
    "charts": {
      "chart1_infrastructure": {
        "path": "/Users/.../chart1_infrastructure_superiority.png",
        "created_at": "2025-11-28T12:38:00Z",
        "linked_insights": ["insight_uuid_1"],
        "linked_sections": ["section_uuid_1"],
        "format": "png",
        "size_bytes": 177152
      },
      "chart2_multihop": {
        "path": "/Users/.../chart2_multihop_segmentation.png",
        "created_at": "2025-11-28T12:38:00Z",
        "linked_insights": ["insight_uuid_2"],
        "format": "png"
      }
    }
  }
}
```

### Proposed: Section Content with Chart References

```markdown
## Finding #1: Infrastructure

![Infrastructure Comparison](chart://chart1_infrastructure)

Or alternatively:

![Infrastructure Comparison](file:///absolute/path/to/chart.png)
```

The renderer would:
1. Parse markdown for `![](chart://...)` or `![](file://...)`
2. Look up chart in registry
3. Replace with `![](data:image/png;base64,...)`

---

## Benefits

### For Users
✅ **Single file** - No external dependencies
✅ **Shareable** - Email/Slack/AirDrop friendly
✅ **Offline** - Works without internet
✅ **Print-ready** - Browser print → PDF
✅ **No Quarto** - Works even if Quarto fails

### For Developers
✅ **Simpler** - Pure Python + Jinja2, no Quarto complexity
✅ **Reliable** - No string formatting edge cases
✅ **Testable** - Easy to unit test template rendering
✅ **Extensible** - Easy to add themes, layouts

### For Living Reports
✅ **Chart lifecycle** - Track chart creation/usage
✅ **Chart reuse** - Reference charts across insights
✅ **Versioning** - Track chart updates
✅ **Storage** - Centralized chart management

---

## Alternative Approaches Considered

### 1. Fix Quarto Template
**Pros**: Keeps existing architecture
**Cons**: Still requires Quarto, still multiple files, harder to debug

### 2. Use Jupyter Notebook Export
**Pros**: Supports interactive charts
**Cons**: Requires nbconvert, more dependencies

### 3. Generate PDF Directly
**Pros**: Universal format
**Cons**: Can't copy text easily, larger file sizes

### 4. Static Site Generator (MkDocs)
**Pros**: Beautiful output, navigation
**Cons**: Multiple files, needs server for best experience

**Decision**: **HTML Standalone** provides best UX with minimal complexity.

---

## Migration Path

### Backward Compatibility

- Existing `format="html"` continues using Quarto
- New `format="html_standalone"` uses standalone renderer
- Eventually deprecate Quarto renderer (or keep as optional enhancement)

### Default Behavior

**Option A**: Keep `html` → Quarto (safe, no breaking changes)
**Option B**: Make `html` → Standalone, `html_quarto` → Quarto (better UX)

**Recommendation**: Option A for v1, migrate to Option B in v2 after user feedback.

---

## Open Questions

1. **Chart storage**: Should charts be copied to `report_dir/charts/` or referenced from original location?
2. **Chart updates**: If source chart changes, should report auto-update or keep snapshot?
3. **File size limits**: What's max size for self-contained HTML? (currently ~1-5MB is reasonable)
4. **Chart formats**: Support only raster (PNG/JPG) or also vector (SVG)?
5. **CSS themes**: Bundle multiple themes or allow custom CSS injection?

---

## Success Criteria

✅ User can render report with `format="html_standalone"`
✅ Output is single HTML file with all charts embedded
✅ File opens in any browser without errors
✅ Charts display correctly at full resolution
✅ File size < 10MB for typical reports
✅ No external dependencies (works offline)
✅ Can print to PDF from browser

---

## Next Steps

1. **Create GitHub issue** with this spec
2. **Prototype renderer** (1-2 days)
3. **User testing** with MON TGE report
4. **Iterate on template** (styling, layout)
5. **Integrate into MCP tool** (tool schema updates)
6. **Documentation** (user guide, examples)
7. **Release as beta** (mark experimental)
8. **Gather feedback** and iterate

---

**Estimated Timeline**: 2-3 weeks for full implementation
**Risk Level**: Low (isolated new feature, doesn't touch existing code)
**User Impact**: High (solves major UX pain point)
