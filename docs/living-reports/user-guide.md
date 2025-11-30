# Living Reports User Guide

Living Reports are structured, auditable business reports that evolve safely with LLM assistance. Unlike traditional documents, Living Reports maintain their integrity while allowing intelligent evolution through AI.

## Core Concepts

### What Makes a Report "Living"?

- **Structured Data**: Reports are backed by JSON schemas with sections, insights, and supporting queries
- **Auditable**: Every change is logged with timestamps and actor information
- **LLM-Evolvable**: AI can safely propose and apply changes without breaking report integrity
- **Query-Backed**: All insights reference actual executed queries for traceability

### Key Components

1. **Sections**: Logical groupings of related insights (e.g., "Revenue Analysis", "User Metrics")
2. **Insights**: Key findings with importance scores (0-10) and supporting query references
3. **Queries**: Links to audited SQL executions that back up the insights
4. **Audit Trail**: Complete history of all changes with rollback capability

## Getting Started

### Storage Location

Living reports are stored in your igloo-mcp instance directory:
- Default: `~/.igloo-mcp/reports/`
- Configurable via: `IGLOO_MCP_REPORTS_ROOT` environment variable
- Follows: `IGLOO_MCP_LOG_SCOPE` setting (global or repo)

All reports are stored alongside your query history and artifacts for easy access across projects.

### Creating Your First Report

Living reports are created and managed entirely through MCP tools in your AI assistant:

```python
# Create a new report via MCP
create_report(
    title="Q1 Revenue Analysis",
    template="default",
    tags=["q1", "revenue", "analysis"]
)
```

This creates a new living report structure ready for evolution. You can also use the CLI for administrative operations if needed:

```bash
# Administrative CLI alternative (optional)
igloo report create "Q1 Revenue Analysis" --template default
```

### Complete Report Creation Workflow

Here's the recommended workflow for creating and evolving living reports:

#### Phase 1: Data Exploration & Query Building
1. **Execute queries** to explore your data and gather insights:
   ```python
   # Explore data and gather insights
   result1 = await execute_query(
       statement="SELECT COUNT(*) as total_orders, SUM(amount) as total_revenue FROM orders WHERE created_at >= '2025-01-01'",
       reason="Initial revenue analysis for Q1 report"
   )
   result2 = await execute_query(
       statement="SELECT customer_segment, COUNT(*) as customers, AVG(order_value) as avg_order FROM customers GROUP BY customer_segment",
       reason="Customer segmentation analysis"
   )
   ```

2. **Build context** by running multiple related queries to understand your data landscape.

#### Phase 2: Report Creation
3. **Create the report** using MCP tools:
   ```python
   # Create report via MCP (recommended)
   create_report(
       title="Q1 Business Performance",
       template="default",
       tags=["q1", "revenue", "operations"]
   )
   ```
   This creates an empty report structure ready for evolution. The index is automatically synchronized, so the report is immediately available for evolution.

#### Phase 3: Report Evolution
4. **Evolve the report** by adding insights, sections, and content:
   ```python
   # Add an executive summary section
   evolve_report(
       report_selector="Q1 Business Performance",
       instruction="Add an executive summary section with key metrics and findings",
       proposed_changes={
           "sections_to_add": [{
               "section_id": "executive_summary",
               "title": "Executive Summary",
               "order": 1
           }],
           "insights_to_add": [{
               "insight_id": "revenue_growth",
               "summary": "Revenue grew 25% YoY to $2.4M in Q1",
               "importance": 9,
               "supporting_queries": [{
                   "execution_id": "abc123",  # From your query results
                   "sql_sha256": "def456"
               }]
           }]
       }
   )
   ```

#### Phase 4: Content Refinement
5. **Iterate and refine** by adding more insights and sections:
   ```python
   # Add customer analysis section
   evolve_report(
       report_selector="Q1 Business Performance",
       instruction="Add customer segmentation analysis section",
       proposed_changes={
           "sections_to_add": [{
               "section_id": "customer_analysis",
               "title": "Customer Analysis",
               "order": 2
           }],
           "insights_to_modify": [{
               "insight_id": "revenue_growth",
               "summary": "Revenue grew 25% YoY to $2.4M, driven by enterprise segment expansion"
           }]
       }
   )
   ```

#### Phase 5: Report Rendering
6. **Render the final report** in your preferred format:
   ```python
   # Render as HTML for sharing
   render_report(
       report_selector="Q1 Business Performance",
       format="html",
       persist_output=True
   )

   # Or render as Markdown for documentation
   render_report(
       report_selector="Q1 Business Performance",
       format="markdown"
   )
   ```

### Automatic Index Synchronization

The `evolve_report` tool automatically refreshes the report index before and after operations, ensuring seamless synchronization between CLI and MCP workflows. Reports created via CLI are immediately visible to MCP tools when you use `evolve_report` - no manual refresh needed.

### Best Practices

- **Start with data exploration** before creating reports
- **Use meaningful report titles** for easy selection
- **Tag reports** for organization (via `tags` parameter in `create_report`)
- **Build incrementally** - add one section/insight at a time
- **Reference query executions** - link insights to actual SQL runs
- **Use MCP tools for full workflow** - create, evolve, and render all via MCP for seamless experience


### Evolving Reports

Use the `evolve_report` MCP tool to modify reports:

```python
evolve_report(
    report_selector="Q1 Revenue Analysis",
    instruction="Add insights about top revenue drivers",
    proposed_changes={
        "insights_to_add": [{
            "insight_id": "insight_uuid_123",
            "summary": "Enterprise segment drove 45% YoY growth",
            "importance": 9
        }]
    }
)
```

### MCP Tool Usage

> **⚠️ EXPERIMENTAL**: The `evolve_report` tool currently uses sample change generation. Full LLM integration is in progress. For now, manually edit `outline.json` files and use `dry_run=True` to validate changes.

The `evolve_report` MCP tool provides a framework for LLM-assisted report evolution:

```python
# Basic evolution
result = await evolve_report(
    report_selector="Q1 Sales Analysis",
    instruction="Add insights about customer retention trends"
)

# With constraints to control changes
result = await evolve_report(
    report_selector="rpt_550e8400e29b11d4a716446655440000",
    instruction="Prioritize revenue metrics over user acquisition",
    constraints={
        "max_importance_delta": 2,  # Limit how much importance can change
        "sections": ["Revenue Analysis"]  # Only modify specific sections
    }
)

# Dry run to validate changes
result = await evolve_report(
    report_selector="Customer Study",
    instruction="Add competitive analysis",
    dry_run=True
)
```

## Report Structure

### Sections
- **Title**: Human-readable name (e.g., "Revenue Analysis")
- **Order**: Display position (lower numbers appear first)
- **Notes**: Optional prose or context
- **Insight IDs**: Ordered list of insight references

### Insights
- **ID**: UUID for stable referencing
- **Importance**: Score 0-10 (10 = highest priority)
- **Summary**: Human-readable finding or observation
- **Status**: "active", "archived", or "killed"
- **Supporting Queries**: Links to executed SQL that backs the insight

### Constraints System

The evolution system includes safety constraints:

- **Importance Bounds**: Prevent extreme importance changes
- **Section Limits**: Restrict changes to specific sections
- **Validation**: Ensure all references remain valid
- **Audit Logging**: Track all changes with actor and timestamp

## Best Practices

### For Report Authors
1. **Start Simple**: Create reports with basic sections and insights
2. **Use Clear Titles**: Make report and section names descriptive
3. **Tag Strategically**: Use tags for filtering and organization
4. **Reference Queries**: Always back insights with actual query executions

### For LLM Evolution
1. **Be Specific**: Provide clear, actionable instructions
2. **Use Constraints**: Limit changes to maintain report integrity
3. **Dry Run First**: Preview changes before applying
4. **Iterate Gradually**: Make small, focused changes

### For Teams
1. **Audit Regularly**: Review change history for quality control
2. **Version Control**: Keep reports in git for collaboration
3. **Document Conventions**: Establish naming and tagging standards
4. **Review Changes**: Use dry-run mode for peer review

## Troubleshooting

### Common Issues

**"Report not found"**
- Check spelling and use `igloo report list` to see available reports
- Use report IDs for exact matching: `rpt_550e8400e29b11d4a716446655440000`

**"Validation failed"**
- Review the validation issues in the error message
- Use `--dry-run` to see what would change without applying
- Adjust constraints or instruction specificity

**"No permission"**
- Ensure you're running in a directory with igloo-mcp configuration
- Check that the reports directory is writable

### Recovery

**Undo Changes**
```bash
# View recent changes
igloo report history "My Report"

# Rollback if supported (future feature)
# igloo report rollback "My Report" --to-change-id "abc123"
```

**Rebuild Index**
```bash
# If reports disappear from listings
igloo report rebuild-index
```

## Analyst Report Pattern

The analyst template mode (`analyst_v1`) provides a standardized, high-quality report format optimized for blockchain and data analysis. It features fixed section layouts, paragraph-style prose, and automatic citation management.

### Creating Analyst Reports

Create an analyst report using the `analyst_v1` template:

```python
# Via MCP tool
create_report(
    title="Q1 Network Analysis",
    template="analyst_v1",
    tags=["network", "analysis", "q1"]
)
```

This creates a report with:
- `metadata.template = "analyst_v1"` (controls rendering mode)
- Pre-configured sections: Network Activity, DEX Trading, Objects, Events
- Citation enforcement (all insights must have citations)

### Standard Sections

Analyst reports use a fixed section structure:

1. **Executive Summary** (auto-generated or manually curated)
   - High-importance insights (importance >= 8) are automatically included
   - Or specify via `outline.metadata.executive_summary_insight_ids`

2. **Network Activity** - Network-level metrics and activity patterns

3. **DEX Trading** - Decentralized exchange trading analysis

4. **Objects** - On-chain objects and contract analysis

5. **Events** - Significant events and transactions

6. **Appendix: Query References** - Automatically generated citation list

### Citation System

Analyst reports enforce citations for all insights:

- Each insight must have `supporting_queries[0]` with an `execution_id`
- Citations are automatically numbered `[1]`, `[2]`, etc.
- Citation numbers are stable across renders (based on execution_id)
- One citation per paragraph (from `supporting_queries[0]`)

**Example workflow:**

```python
# 1. Execute query to get execution_id
result = await execute_query(
    statement="SELECT COUNT(*) FROM transactions WHERE date >= '2025-01-01'",
    reason="Network activity analysis"
)
execution_id = result["audit_info"]["execution_id"]

# 2. Add insight with citation
evolve_report(
    report_selector="Q1 Network Analysis",
    instruction="Add network activity insight",
    proposed_changes={
        "insights_to_add": [{
            "insight_id": str(uuid.uuid4()),
            "summary": "Network processed 2.4M transactions in Q1, up 15% YoY",
            "importance": 9,
            "supporting_queries": [{
                "execution_id": execution_id
            }]
        }]
    }
)
```

### Citation Enforcement

When using `evolve_report` with analyst reports, citations are automatically validated:

- **Required**: `supporting_queries[0].execution_id` must be present
- **Error message**: Clear guidance if citation is missing
- **Hint**: Suggests using `execute_query()` first

**Example error:**

```
Analyst reports require citations. Insight 'abc-123' missing supporting_queries[0] with execution_id.
Use execute_query() first to get an execution_id, then include it in supporting_queries
```

### Executive Summary Configuration

The Executive Summary can be configured in two ways:

**Option 1: Auto-population (default)**
- Automatically includes insights with `importance >= 8`
- No configuration needed

**Option 2: Manual curation**
```python
# Set specific insight IDs in metadata
evolve_report(
    report_selector="Q1 Network Analysis",
    instruction="Update executive summary",
    proposed_changes={
        "metadata_updates": {
            "executive_summary_insight_ids": [
                "insight-uuid-1",
                "insight-uuid-2"
            ]
        }
    }
)
```

### Rendering Analyst Reports

Analyst reports render with:
- Paragraph-style prose (no bold, minimal headings)
- Inline citation markers `[N]` at end of each paragraph
- Query References appendix with full citation details
- Fixed section order regardless of section.order values

```python
# Render analyst report
render_report(
    report_selector="Q1 Network Analysis",
    format="html"
)
```

### Example Outline Structure

Minimal analyst report outline:

```json
{
  "report_id": "rpt_...",
  "title": "Q1 Network Analysis",
  "metadata": {
    "template": "analyst_v1"
  },
  "sections": [
    {
      "section_id": "...",
      "title": "Network Activity",
      "order": 0,
      "metadata": {"category": "network_activity"}
    }
  ],
  "insights": [
    {
      "insight_id": "...",
      "summary": "Network processed 2.4M transactions",
      "importance": 9,
      "supporting_queries": [{
        "execution_id": "exec_123"
      }]
    }
  ]
}
```

## Advanced Usage

### Custom Constraints
```python
# Complex constraints for controlled evolution
result = await evolve_report(
    report_selector="Complex Report",
    instruction="Restructure for new priorities",
    constraints={
        "max_importance_delta": 1,
        "sections": ["Core Metrics", "KPIs"],
        "require_query_backing": True
    }
)
```

### Bulk Operations
```bash
# List reports with specific tags
igloo report list --tags "quarterly,finance"

# Evolve multiple reports (future feature)
# igloo report batch-evolve --reports "rpt_1,rpt_2" --instruction "Update for new quarter"
```

## Administrative Operations

The following CLI commands are available for administrative and power-user operations. The primary interface for report work is through MCP tools (`create_report`, `evolve_report`, `render_report`) in your AI assistant.

### Report Creation

**Primary Method (MCP)**:
```python
# Create report via MCP (recommended)
create_report(
    title="Customer Retention Study",
    tags=["customers", "retention", "q1"]
)
```

**CLI Alternative** (for administrative operations):
```bash
# Create with tags for organization
igloo report create "Customer Retention Study" --tags "customers,retention,q1"
```

### List Reports
```bash
# Show all active reports
igloo report list

# Filter by tags
igloo report list --tags "sales,q1"
```

### Direct CLI Evolution
```bash
# Evolve by report ID
igloo report evolve "rpt_550e8400e29b11d4a716446655440000" \
  --instruction "Add insights about top revenue drivers and regional performance"

# Evolve by title (with confirmation for ambiguity)
igloo report evolve "Q1 Sales Analysis" \
  --instruction "Prioritize customer retention metrics over acquisition"

# Preview changes without applying
igloo report evolve "Q1 Sales Analysis" \
  --instruction "Add competitive analysis section" \
  --dry-run
```

### Report Management
```bash
# Show report structure and recent changes
igloo report show "Q1 Sales Analysis"

# View audit history
igloo report history "Q1 Sales Analysis"
```

Living Reports provide a new way to maintain business intelligence that's both human-friendly and AI-enhanced, ensuring reports stay current while maintaining their accuracy and auditability.

## Citations vs Supporting Queries

Insights support two fields for source references that serve different purposes:

### `supporting_queries` (Legacy Field)

The original field for linking insights to Snowflake query executions:

```json
{
  "supporting_queries": [{
    "execution_id": "exec_abc123",
    "sql_sha256": "def456..."
  }]
}
```

- **Purpose**: Link insights to specific Snowflake query executions
- **Source**: Snowflake `execute_query` results only
- **Usage**: Analyst reports enforce this field for citation numbering

### `citations` (Flexible Field)

A more flexible field supporting multiple source types beyond just Snowflake queries:

```json
{
  "citations": [
    {
      "source": "query",
      "provider": "snowflake",
      "execution_id": "exec_abc123",
      "statement": "SELECT COUNT(*) FROM orders"
    },
    {
      "source": "url",
      "url": "https://docs.example.com/api",
      "title": "Official API Documentation"
    },
    {
      "source": "observation",
      "content": "Observed during production deployment",
      "timestamp": "2025-11-27T10:30:00Z"
    },
    {
      "source": "document",
      "title": "Q4 Board Report",
      "location": "docs/board_reports/q4_2024.pdf"
    }
  ]
}
```

- **Purpose**: Multi-source attribution (queries, docs, URLs, observations, APIs)
- **Status**: Model-level field added for future multi-source support
- **Compatibility**: Backward compatible shim ensures existing code works

### When to Use Which?

**Use `supporting_queries` for:**
- Analyst reports (required for citation enforcement)
- Simple Snowflake-only reports
- Backward compatibility with existing reports

**Use `citations` for:**
- Reports combining data from multiple sources (Snowflake + APIs + documents)
- Observations and manual findings
- Web research and documentation references
- Future-proofing new reports

### Backward Compatibility

Both fields are kept in sync automatically:
- Setting `supporting_queries` auto-populates `citations` with query type entries
- Existing reports continue working without changes
- Full migration path planned for future version (see #62)

**Current Status:**
- ✅ `citations` field exists in models
- ✅ Backward compatible shim in place
- ⏳ Full rendering/migration support in progress

## JSON Schema Reference

This section provides copy-paste-ready JSON examples for all `evolve_report` operations. These examples match the exact structure expected by the MCP tool.

### Adding Insights

**Required Fields:**
- `section_id` (UUID) - Section to add insight to
- `insight.summary` (string) - Insight content
- `insight.importance` (integer 1-10) - Importance score

**Optional Fields:**
- `insight.supporting_queries` (array) - Defaults to `[]` if omitted

**Example:**
```json
{
  "report_selector": "Q1 Analysis",
  "instruction": "Add revenue growth insight",
  "proposed_changes": {
    "insights_to_add": [{
      "section_id": "550e8400-e29b-41d4-a716-446655440012",
      "insight": {
        "summary": "Revenue grew 25% YoY to $2.4M",
        "importance": 9,
        "supporting_queries": []
      }
    }]
  }
}
```

### Adding Sections

**Required Fields:**
- `title` (string) - Section name

**Optional Fields:**
- `order` (integer) - Display order (defaults to append)
- `notes` (string) - Section metadata/notes
- `content` (string) - Free-form markdown/text content
- `content_format` (string) - Content format: "markdown" (default), "text", or "html"

**Example:**
```json
{
  "report_selector": "Q1 Analysis",
  "instruction": "Add executive summary section with overview",
  "proposed_changes": {
    "sections_to_add": [{
      "title": "Executive Summary",
      "order": 1,
      "notes": "High-level overview for stakeholders",
      "content": "## Overview\n\nQ1 performance exceeded expectations across all key metrics...",
      "content_format": "markdown"
    }]
  }
}
```

### Modifying Sections

**Required Fields:**
- `section_id` (UUID) - Section to modify

**Optional Fields** (at least one required):
- `title` (string) - New title
- `order` (integer) - New display order
- `notes` (string) - Updated notes
- `content` (string) - Updated content
- `content_format` (string) - Content format
- `insight_ids_to_add` (array of UUIDs) - Link existing insights
- `insight_ids_to_remove` (array of UUIDs) - Unlink insights

**Example:**
```json
{
  "report_selector": "Q1 Analysis",
  "instruction": "Rename section and link new insights",
  "proposed_changes": {
    "sections_to_modify": [{
      "section_id": "550e8400-e29b-41d4-a716-446655440012",
      "title": "Revenue & Growth Metrics",
      "order": 2,
      "insight_ids_to_add": ["insight-uuid-1", "insight-uuid-2"],
      "content": "Updated analysis with Q1 data..."
    }]
  }
}
```

### Removing Sections

**Required Fields:**
- Section IDs (array of UUIDs) to remove

**Example:**
```json
{
  "report_selector": "Q1 Analysis",
  "instruction": "Remove outdated preliminary analysis section",
  "proposed_changes": {
    "sections_to_remove": ["550e8400-e29b-41d4-a716-446655440013"]
  }
}
```

### Changing Report Status (Archive/Restore/Delete)

**Required Fields:**
- `status_change` (string) - "active", "archived", or "deleted"

**Important:** Status changes cannot be combined with content changes in the same operation.

**Example - Archive Report:**
```json
{
  "report_selector": "Q3 2024 Analysis",
  "instruction": "Archive obsolete quarterly report",
  "proposed_changes": {
    "status_change": "archived"
  }
}
```

**Example - Restore Archived Report:**
```json
{
  "report_selector": "Q3 2024 Analysis",
  "instruction": "Restore archived report for reference",
  "proposed_changes": {
    "status_change": "active"
  }
}
```

### Combining Multiple Operations

You can combine multiple operations in a single `evolve_report` call (except status changes):

**Example:**
```json
{
  "report_selector": "Q1 Analysis",
  "instruction": "Add new section with insights and update existing section",
  "proposed_changes": {
    "sections_to_add": [{
      "title": "Customer Acquisition",
      "order": 3,
      "content": "## CAC Analysis\n\nCustomer acquisition costs..."
    }],
    "insights_to_add": [{
      "section_id": "existing-section-uuid",
      "insight": {
        "summary": "CAC decreased 15% due to organic growth",
        "importance": 8,
        "supporting_queries": [{"execution_id": "exec_cac_analysis"}]
      }
    }],
    "sections_to_modify": [{
      "section_id": "existing-section-uuid",
      "title": "Updated Section Title"
    }]
  }
}
```

### Dry Run Validation

Use `dry_run: true` to validate changes without applying them:

**Example:**
```json
{
  "report_selector": "Q1 Analysis",
  "instruction": "Validate proposed structure changes",
  "proposed_changes": {
    "sections_to_add": [{"title": "New Section"}]
  },
  "dry_run": true
}
```

**Response includes:**
- `validation_passed`: boolean
- `planned_changes`: Preview of what would be applied
- `validation_errors`: Array of errors if validation fails
- `schema_examples`: Targeted examples for operations with errors

### Common Validation Errors

**Missing Required Field:**
```json
// Error response
{
  "status": "validation_failed",
  "validation_errors": [{
    "field": "insights_to_add[0].section_id",
    "message": "Missing required field",
    "input_value": null
  }],
  "schema_examples": {
    "insights_to_add": [
      {
        "section_id": "550e8400-e29b-41d4-a716-446655440012",
        "insight": {"summary": "...", "importance": 9}
      }
    ]
  }
}
```

**Invalid UUID Format:**
```json
// Error response
{
  "status": "validation_failed",
  "validation_errors": [{
    "field": "sections_to_modify[0].section_id",
    "message": "Input should be a valid UUID",
    "input_value": "not-a-uuid"
  }],
  "hints": ["insight_id and section_id must be valid UUID strings"],
  "examples": {"section_id": "550e8400-e29b-41d4-a716-446655440000"}
}
```

---

## Progressive Disclosure

Use `get_report` with selective retrieval modes for significant token reduction.

### Quick Start

```python
# Start with summary (lightweight overview)
summary = get_report(report_selector="Q1 Analysis", mode="summary")  # ~150 tokens

# Drill down to specific sections
sections = get_report(
    report_selector="Q1 Analysis",
    mode="sections",
    section_titles=["Revenue"]
)  # ~300 tokens

# Get high-priority insights only
insights = get_report(
    report_selector="Q1 Analysis",
    mode="insights",
    min_importance=8
)  # ~400 tokens
```

**Token Savings**: 60-92% reduction vs. always loading full reports.

See [get_report Tool Documentation](../api/tools/get_report.md) for complete details.

---

## API Discovery

Use `get_report_schema` to discover valid structures before constructing payloads.

### Quick Start

```python
# Get copy-paste ready examples
examples = get_report_schema(
    schema_type="proposed_changes",
    format="examples"
)

# Browse available operations
print(examples["examples"].keys())
# ['add_insight', 'modify_section', 'atomic_section_with_insights', ...]

# Adapt an example to your needs
my_changes = examples["examples"]["add_insight"]
# Modify and use in evolve_report...
```

**Benefits**: First-time-right submissions, fewer validation errors.

See [get_report_schema Tool Documentation](../api/tools/get_report_schema.md) for complete details.

---

## Token Optimization Tips

Achieve **70% token reduction** in multi-turn workflows:

### 1. Search with Minimal Fields
```python
# ✅ Efficient
search_report(title="Q1", fields=["report_id", "title"])  # ~250 tokens

# ❌ Wasteful
search_report(title="Q1")  # ~800 tokens (all fields)
```

### 2. Progressive Report Reading
```python
# ✅ Efficient
summary = get_report("Q1", mode="summary")  # ~150 tokens
# Only drill down if needed

# ❌ Wasteful
full = get_report("Q1", mode="full")  # ~2000 tokens
```

### 3. Minimal Evolution Responses
```python
# ✅ Efficient
evolve_report(..., response_detail="minimal")  # ~150 token response

# ❌ Wasteful
evolve_report(..., response_detail="full")  # ~1000+ token response
```

### 4. Compact Render Previews
```python
# ✅ Efficient
render_report(..., preview_max_chars=500)  # ~200 token response

# ❌ Wasteful
render_report(..., preview_max_chars=10000)  # ~3000 token response
```

### Complete Optimized Workflow

```python
# Multi-turn workflow with full optimization

# 1. Find (minimal fields)
reports = search_report(title="Q1", fields=["report_id"])  # ~100 tokens

# 2. Inspect (summary mode)
summary = get_report(reports["reports"][0]["report_id"], mode="summary")  # ~150 tokens

# 3. Modify (minimal response)
evolve_report(
    report_selector=reports["reports"][0]["report_id"],
    instruction="Add insight",
    proposed_changes={...},
    response_detail="minimal"
)  # ~150 tokens

# 4. Verify (selective)
get_report(
    reports["reports"][0]["report_id"],
    mode="sections",
    section_titles=["Revenue"]
)  # ~250 tokens

# Total: ~650 tokens (vs. 3,500+ tokens previously)
# Savings: 81%
```

---

## See Also

- [Progressive Disclosure](../api/PROGRESSIVE_DISCLOSURE.md) - Control response verbosity for token efficiency
- [create_report API](../api/tools/create_report.md)
- [evolve_report API](../api/tools/evolve_report.md)
- [evolve_report_batch API](../api/tools/evolve_report_batch.md)
- [get_report API](../api/tools/get_report.md)
- [render_report API](../api/tools/render_report.md)
- [search_report API](../api/tools/search_report.md)
