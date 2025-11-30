# Working with Charts

Charts bring visual impact to your Living Reports. Attach charts to insights, and they're automatically embedded in HTML output for seamless sharing.

## Quick Start

Attach a chart in 3 steps:

```python
# 1. Create your chart (matplotlib, plotly, etc.)
import matplotlib.pyplot as plt
plt.plot([1, 2, 3], [4, 5, 6])
plt.savefig("/path/to/revenue_trend.png")

# 2. Attach via evolve_report_batch
evolve_report_batch(
    report_selector="Q1 Revenue Report",
    instruction="Attach revenue trend chart",
    operations=[
        {
            "type": "attach_chart",
            "chart_path": "/path/to/revenue_trend.png",
            "insight_ids": ["insight-uuid"],
            "description": "Q1 revenue trend by month"
        }
    ]
)

# 3. Render to HTML (chart embedded automatically)
render_report(
    report_selector="Q1 Revenue Report",
    format="html_standalone"
)
```

Your chart is now embedded as base64 in a single HTML file—ready to share via email, Slack, or web.

## Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| PNG | `.png` | Best for most charts (recommended) |
| JPEG | `.jpg`, `.jpeg` | Good for photographs, larger files |
| SVG | `.svg` | Vector graphics, scales perfectly |
| GIF | `.gif` | Animations (use sparingly) |
| WebP | `.webp` | Modern format, excellent compression |

**Recommendation**: Use PNG for data visualizations. It offers lossless compression and broad compatibility.

## Size Limits

Igloo MCP enforces size limits to ensure reports remain shareable:

| Threshold | Action |
|-----------|--------|
| **< 1MB** | ✅ Optimal - no warnings |
| **1-5MB** | ⚠️  Acceptable - consider optimizing |
| **5-10MB** | ⚠️  Warning - report may be large |
| **10-50MB** | ⚠️  Warning - HTML will be very large |
| **> 50MB** | ❌ Rejected - exceeds hard limit |

### Optimizing Charts

**Before attaching large images:**

```bash
# Compress PNG (lossy)
pngquant --quality=65-80 chart.png -o chart_optimized.png

# Compress PNG (lossless)
optipng -o7 chart.png

# Convert to WebP (better compression)
cwebp -q 80 chart.png -o chart.webp
```

**In Python (matplotlib):**

```python
# Reduce DPI for smaller files
plt.savefig("chart.png", dpi=100)  # Default: 100
plt.savefig("chart.png", dpi=150)  # Higher quality, larger file

# Use tight bounding box to remove whitespace
plt.savefig("chart.png", bbox_inches='tight')

# Optimize PNG compression
plt.savefig("chart.png", optimize=True)
```

## Chart Metadata

When you attach a chart, Igloo MCP stores complete metadata:

```python
{
  "chart_uuid": {
    "path": "/absolute/path/chart.png",
    "format": "png",
    "created_at": "2025-11-30T12:38:00Z",
    "size_bytes": 177152,
    "linked_insights": ["insight-uuid"],
    "source": "matplotlib",  # or "plotly", "custom"
    "description": "Revenue trend Q3 2024"
  }
}
```

**Stored in**: `outline.metadata.charts`

## Linking Charts to Insights

Charts are linked via insight metadata:

```python
# Chart reference stored in insight metadata
{
  "insight_id": "550e8400-...",
  "summary": "Revenue grew 25% YoY",
  "metadata": {
    "chart_id": "chart-uuid"  # References outline.metadata.charts
  }
}
```

This design enables:
- **Chart reuse**: Link one chart to multiple insights
- **Lifecycle tracking**: Know which insights use which charts
- **Easy updates**: Update chart file, re-render report

## Rendering Behavior

### HTML Standalone

Charts are embedded as base64 data URIs:

```html
<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
     alt="Revenue trend Q3"
     loading="lazy" />
```

**Benefits**:
- ✅ Single file output (no external dependencies)
- ✅ Works offline
- ✅ Email/Slack friendly
- ✅ No broken image links

### Quarto (HTML/PDF)

Charts are referenced by file path:

```markdown
![Revenue trend Q3](/absolute/path/chart.png)
```

**Requirements**:
- Chart files must exist at render time
- Use absolute paths for portability
- PDF rendering requires accessible file system

## Common Workflows

### Workflow 1: Single Chart per Insight

```python
# Generate chart
plt.plot(data)
plt.savefig("/charts/revenue.png")

# Attach to specific insight
evolve_report_batch(
    report_selector="Q1 Report",
    instruction="Add revenue chart",
    operations=[{
        "type": "attach_chart",
        "chart_path": "/charts/revenue.png",
        "insight_ids": ["insight-uuid"],
        "description": "Monthly revenue"
    }]
)
```

### Workflow 2: Multiple Charts in One Report

```python
operations = []

for metric in ["revenue", "customers", "churn"]:
    # Generate chart
    plt.plot(metrics[metric])
    plt.savefig(f"/charts/{metric}.png")

    # Add attach operation
    operations.append({
        "type": "attach_chart",
        "chart_path": f"/charts/{metric}.png",
        "insight_ids": [insight_ids[metric]],
        "description": f"{metric.title()} trend"
    })

evolve_report_batch(
    report_selector="Q1 Report",
    instruction="Attach all metric charts",
    operations=operations
)
```

### Workflow 3: Shared Chart Across Insights

```python
# Attach chart to multiple insights
evolve_report_batch(
    report_selector="Q1 Report",
    instruction="Link chart to multiple insights",
    operations=[{
        "type": "attach_chart",
        "chart_path": "/charts/combined_metrics.png",
        "insight_ids": [
            "revenue-insight-uuid",
            "growth-insight-uuid",
            "forecast-insight-uuid"
        ],
        "description": "Combined metrics dashboard"
    }]
)
```

## Troubleshooting

### Chart Not Displaying

**Problem**: Chart appears as broken image or missing

**Solutions**:
1. **Check file exists**: Verify chart file at specified path
2. **Use absolute paths**: `"/Users/you/charts/chart.png"` not `"chart.png"`
3. **Check permissions**: Ensure file is readable
4. **Verify format**: Use supported formats (PNG, JPG, SVG, etc.)

### HTML File Too Large

**Problem**: Rendered HTML exceeds 10MB

**Solutions**:
1. **Optimize images**: Use compression tools (see "Optimizing Charts")
2. **Reduce resolution**: Lower DPI in matplotlib/plotly
3. **Convert format**: PNG → WebP for better compression
4. **Fewer charts**: Attach only essential visualizations

### Charts Missing After Render

**Problem**: Charts were attached but don't appear in output

**Solutions**:
1. **Check format**: Ensure using `format="html_standalone"` for embedded charts
2. **Verify metadata**: Inspect `outline.metadata.charts` has entries
3. **Check linking**: Verify `insight.metadata.chart_id` references exist
4. **Re-render**: Try `regenerate_outline_view=True`

## Best Practices

### DO ✅

- **Optimize before attaching**: Compress images to reduce file size
- **Use absolute paths**: Ensures portability across environments
- **Add descriptions**: Help readers understand what chart shows
- **Test rendering**: Verify charts display correctly in HTML
- **Version charts**: Update chart files, re-render to update reports

### DON'T ❌

- **Don't attach huge files**: Keep charts under 5MB when possible
- **Don't use relative paths**: Can break when report moves
- **Don't skip descriptions**: Context helps readers interpret charts
- **Don't forget format**: Use `html_standalone` for embedded charts
- **Don't duplicate unnecessarily**: Reuse charts across insights when appropriate

## Examples

### Matplotlib Chart

```python
import matplotlib.pyplot as plt
import numpy as np

# Generate data
months = ['Jan', 'Feb', 'Mar', 'Apr']
revenue = [120, 150, 180, 210]

# Create chart
plt.figure(figsize=(10, 6))
plt.plot(months, revenue, marker='o', linewidth=2, color='#2563eb')
plt.title("Q1 Revenue Growth", fontsize=16, fontweight='bold')
plt.xlabel("Month")
plt.ylabel("Revenue ($K)")
plt.grid(True, alpha=0.3)
plt.tight_layout()

# Save optimized
plt.savefig("/charts/q1_revenue.png", dpi=150, bbox_inches='tight')

# Attach to report
evolve_report_batch(
    report_selector="Q1 Report",
    instruction="Add revenue growth chart",
    operations=[{
        "type": "attach_chart",
        "chart_path": "/charts/q1_revenue.png",
        "insight_ids": ["revenue-growth-insight"],
        "description": "Q1 revenue grew 75% from Jan to Apr",
        "source": "matplotlib"
    }]
)
```

### Plotly Interactive Chart

```python
import plotly.graph_objects as go

# Create interactive chart
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=['Jan', 'Feb', 'Mar', 'Apr'],
    y=[120, 150, 180, 210],
    mode='lines+markers',
    name='Revenue'
))

fig.update_layout(
    title="Q1 Revenue Growth",
    xaxis_title="Month",
    yaxis_title="Revenue ($K)"
)

# Save as static image (for reports)
fig.write_image("/charts/q1_revenue_plotly.png", width=1000, height=600)

# Or save as HTML for interactivity (larger file)
fig.write_html("/charts/q1_revenue_interactive.html")
```

## Related Topics

- **[Citations](./citations.md)**: Link data sources to insights
- **[Template Customization](./template-customization.md)**: Customize chart rendering
- **[User Guide](./user-guide.md)**: Complete Living Reports overview
