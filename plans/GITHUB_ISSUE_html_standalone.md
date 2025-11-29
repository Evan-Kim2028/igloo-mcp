# [Feature] Add `html_standalone` format to Living Reports renderer

## Problem

Current Quarto-based HTML rendering creates **multiple files** (HTML + chart images), making reports difficult to share. Users want a **single self-contained file** with embedded charts.

**User quote:**
> "Ideally is there a better way to just give me a single link that has all of the charts embedded into it?"

### Current Pain Points

1. ❌ **Multiple files**: Quarto HTML generates separate files for charts/assets
2. ❌ **Broken links**: `file://` paths break when report is moved/shared
3. ❌ **Quarto dependency**: Requires Quarto installation (can fail)
4. ❌ **Format errors**: Percentage signs and special chars can break Jinja2 rendering
5. ❌ **Sharing friction**: Can't easily email/Slack a single report

## Proposed Solution

Add new `format="html_standalone"` option to `render_report` that generates a **single HTML file** with:

✅ All charts embedded as base64 data URIs
✅ Modern CSS styling (responsive, print-ready)
✅ Works offline (no external dependencies)
✅ Email/Slack friendly (single file)
✅ Print to PDF from browser

### Example Usage

```python
igloo_mcp.render_report(
    report_selector="MON TGE Analysis",
    format="html_standalone",  # NEW FORMAT
    include_preview=False
)
```

**Output**: Single `report.html` file (~1-5MB) that opens in any browser.

## Implementation Plan

### 1. Create `HTMLStandaloneRenderer`

**File**: `src/igloo_mcp/living_reports/renderers/html_standalone.py`

```python
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
        """Render report to self-contained HTML with embedded charts."""
        # 1. Collect charts from sections/metadata
        # 2. Convert to base64 data URIs
        # 3. Render HTML template with embedded charts
        # 4. Write single HTML file
```

**Key features**:
- Chart collection from multiple sources (hints, metadata, section content)
- Base64 encoding for PNG/JPG/SVG
- Jinja2 template rendering with custom filters
- Chart reference replacement (`file://` → `data:` URIs)

### 2. Add HTML Template

**File**: `src/igloo_mcp/living_reports/renderers/templates/standalone.html.j2`

**Features**:
- Clean, modern CSS (similar to GitHub/Notion)
- Responsive design (mobile-friendly)
- Print styles (PDF export via browser)
- Sections, insights, citations properly formatted
- Chart embedding via custom Jinja2 filter

### 3. Update `render_report` Tool

**File**: `src/igloo_mcp/mcp/tools/render_report.py`

Add format routing:

```python
if format == "html_standalone":
    renderer = HTMLStandaloneRenderer()
    output_path = renderer.render(...)
    return {"status": "success", "output_path": str(output_path)}
elif format in ["html", "pdf", "markdown"]:
    # Existing Quarto renderer
```

### 4. Chart Management (Future Enhancement)

Add chart registry to report metadata:

```json
{
  "metadata": {
    "charts": {
      "chart1_infrastructure": {
        "path": "/absolute/path/to/chart.png",
        "created_at": "2025-11-28T12:38:00Z",
        "linked_insights": ["insight_uuid"],
        "format": "png",
        "size_bytes": 177152
      }
    }
  }
}
```

This enables:
- Chart lifecycle tracking
- Chart reuse across insights
- Versioning and updates
- Size warnings (>5MB charts)

## Benefits

### For Users
✅ **Single file** - No external dependencies
✅ **Shareable** - Email/Slack/AirDrop friendly
✅ **Offline** - Works without internet
✅ **Print-ready** - Browser print → PDF
✅ **No Quarto** - Works even if Quarto fails

### For Developers
✅ **Simpler** - Pure Python + Jinja2
✅ **Reliable** - No Quarto edge cases
✅ **Testable** - Easy to unit test
✅ **Extensible** - Easy to add themes

## Implementation Phases

### Phase 1: MVP (Week 1)
- [ ] Create `HTMLStandaloneRenderer` class
- [ ] Create basic `standalone.html.j2` template
- [ ] Chart collection from file paths
- [ ] Base64 embedding (PNG only)
- [ ] Basic section/insight rendering

### Phase 2: Integration (Week 2)
- [ ] Update `render_report` tool
- [ ] Support `file://` path replacement
- [ ] Handle multiple chart formats (PNG, JPG, SVG)
- [ ] Add validation and error handling
- [ ] User documentation

### Phase 3: Polish (Week 3)
- [ ] CSS themes (light/dark)
- [ ] Table of contents
- [ ] Citation footnotes
- [ ] Chart size warnings
- [ ] Print optimization

### Phase 4: Chart Management (Week 4)
- [ ] Chart registry in metadata
- [ ] `evolve_report` support for adding charts
- [ ] Chart lifecycle tracking
- [ ] Chart reuse across insights

## Backward Compatibility

✅ **No breaking changes**
- Existing `format="html"` continues using Quarto
- New `format="html_standalone"` is opt-in
- Both formats coexist

**Future**: Consider making `html_standalone` the default in v2.0 after user feedback.

## Example Output

**Current** (Quarto):
```
report_dir/
├── report.html           # 50KB, has <img src="chart1.png">
├── chart1.png           # 173KB
├── chart2.png           # 314KB
└── chart3.png           # 418KB
```
❌ 4 files, links break if moved

**Proposed** (Standalone):
```
report_dir/
└── report.html          # 1.2MB, charts embedded as base64
```
✅ 1 file, self-contained, shareable

## Success Criteria

- [ ] User can render report with `format="html_standalone"`
- [ ] Output is single HTML file with all charts embedded
- [ ] File opens in any browser without errors
- [ ] Charts display correctly at full resolution
- [ ] File size < 10MB for typical reports
- [ ] Works offline (no internet required)
- [ ] Can print to PDF from browser with good layout
- [ ] No regression in existing Quarto renderer

## Alternative Approaches Considered

1. **Fix Quarto Template** - Still requires Quarto, still multiple files
2. **Jupyter Notebook** - Requires nbconvert, more dependencies
3. **PDF Direct** - Can't copy text, larger files
4. **MkDocs** - Multiple files, needs server

**Decision**: HTML Standalone provides best UX with minimal complexity.

## Related Issues

- #89 - Citation enforcement (complementary feature)
- Related to general Living Reports UX improvements

## Labels

- `enhancement`
- `living-reports`
- `good-first-issue` (for Phase 1 MVP)
- `user-requested`

---

**Estimated Effort**: 2-3 weeks for full implementation
**Risk Level**: Low (isolated new feature)
**User Impact**: High (solves major UX pain point)

## Proof of Concept

A working prototype was created for the MON TGE Analysis report:
- Output: Single 1.2MB HTML file
- 3 embedded charts (base64)
- Modern CSS styling
- Opens directly in browser, no dependencies

**User feedback**: "This is exactly what I needed!"
