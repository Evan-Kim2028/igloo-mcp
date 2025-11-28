# Release Notes: v0.3.2 - Living Reports Tooling Ecosystem

**Release Date:** November 28, 2025

**Summary:** Complete implementation of v0.3.2 with new MCP tools and significant token efficiency improvements. This release closes 9 open issues and delivers ~70% token reduction in typical multi-turn workflows through selective retrieval and configurable verbosity.

---

## 🎯 Highlights

### Complete Agentic Workflow Support
Agents can now execute full report lifecycle:
1. **Discover** - Find reports efficiently with `search_report`
2. **Read** - Understand structure with `get_report`
3. **Learn** - Discover schemas with `get_report_schema`
4. **Modify** - Update precisely with `evolve_report`
5. **Verify** - Confirm changes with selective filtering
6. **Render** - Generate outputs with `render_report`

### Token Efficiency Breakthrough
- **70% reduction** in multi-turn workflow token usage
- **Progressive disclosure** - start lightweight, drill down as needed
- **Configurable verbosity** - control response detail levels
- **Selective field retrieval** - request only what you need

### Enhanced Developer Experience
- **Self-documenting APIs** - runtime schema introspection
- **Better error messages** - field paths, examples, validation hints
- **Dry-run improvements** - validate before applying changes
- **Backward compatible** - all defaults preserved

---

## 📦 What's New

### New MCP Tools

#### `get_report` - Progressive Report Disclosure (Closes #51)
Read living reports with selective retrieval for token efficiency.

**4 Retrieval Modes:**
- `summary` - Lightweight overview (~100-200 tokens)
- `sections` - Section details without full insights
- `insights` - Insight details for analysis
- `full` - Complete report structure

**Selective Filtering:**
- Filter by `section_ids`, `section_titles`, `insight_ids`
- Importance filtering with `min_importance`
- Pagination with `limit` and `offset`

**Example Usage:**
```json
{
  "report_selector": "quarterly-analysis",
  "mode": "summary"
}
```

#### `get_report_schema` - API Discovery (Closes #51)
Self-documenting schema introspection for report structures.

**3 Output Formats:**
- `json_schema` - Full JSON Schema draft 7
- `examples` - Copy-paste-ready payloads
- `compact` - Quick reference guide

**Schema Types:**
- `proposed_changes` - Complete evolve_report payload
- `insight`, `section`, `outline` - Individual components
- `all` - Everything at once

**Example Usage:**
```json
{
  "schema_type": "proposed_changes",
  "format": "examples"
}
```

### Enhanced Existing Tools

#### `evolve_report` - Response Detail Control (Closes #53, #54)
New `response_detail` parameter for 50-80% token reduction.

**Response Levels:**
- `minimal` (~200 tokens) - Status, ID, version, counts only
- `standard` (~400 tokens, default) - Adds created IDs and warnings
- `full` (~1000+ tokens) - Complete details with applied changes echo

**Example:**
```json
{
  "report_selector": "quarterly-analysis",
  "instruction": "Add revenue insight",
  "proposed_changes": {...},
  "response_detail": "minimal"
}
```

#### `search_report` - Field Selection (Closes #56)
New `fields` parameter for 30-50% token reduction.

**Selective Fields:**
- Choose exactly what you need
- Valid fields: `report_id`, `title`, `created_at`, `updated_at`, `tags`, `status`, `path`
- Default: all fields (backward compatible)

**Example:**
```json
{
  "title": "quarterly",
  "fields": ["report_id", "title", "tags"]
}
```

#### `render_report` - Preview Size Control
New `preview_max_chars` parameter for configurable preview truncation.

**Options:**
- Range: 100-10,000 characters
- Default: 2000 characters
- Allows smaller previews for token efficiency

---

## 🐛 Bug Fixes

### #48 - `timeout_seconds` Type Handling
Fixed type coercion issue in `execute_query` tool.
- **Problem:** Some MCP clients pass timeout as string
- **Solution:** Accept both integer and numeric string values
- **Impact:** Better MCP client compatibility

### #60 - `render_report` Preview Returns
Fixed preview content not being returned when requested.
- **Problem:** `include_preview=True` was ignored
- **Solution:** Correctly return truncated rendered content
- **Impact:** Agents can now preview rendered output

### #59 - `evolve_report` Stale Warnings
Fixed warnings computed before changes applied.
- **Problem:** Warnings referenced old state
- **Solution:** Compute warnings AFTER applying changes
- **Impact:** Accurate validation feedback

### #58 - `supporting_queries` Optional
Made `supporting_queries` optional with sensible defaults.
- **Problem:** Required empty array boilerplate
- **Solution:** Default to `[]` when not provided
- **Impact:** Less verbose insight creation

### #57 - Inline Insights Support
Enabled atomic insight creation in section operations.
- **Problem:** Separate add-and-link operations required
- **Solution:** Support `insights` array in section changes
- **Impact:** Atomic section+insight creation

---

## 💥 Breaking Changes

### Query Result Truncation Limits
Default limits significantly reduced to prevent context overflow.

**New Defaults:**
- `RESULT_SIZE_LIMIT_MB`: 100 MB → **1 MB** (100x reduction)
- `RESULT_KEEP_FIRST_ROWS`: 1000 → **500** (2x reduction)
- `RESULT_KEEP_LAST_ROWS`: 1000 → **50** (20x reduction)
- `RESULT_TRUNCATION_THRESHOLD`: 10000 → **1000** (10x reduction)

**Migration:**
Configure via environment variables if larger limits needed:
```bash
export IGLOO_MCP_RESULT_SIZE_LIMIT_MB=10
export IGLOO_MCP_RESULT_KEEP_FIRST_ROWS=1000
export IGLOO_MCP_RESULT_KEEP_LAST_ROWS=1000
export IGLOO_MCP_RESULT_TRUNCATION_THRESHOLD=5000
```

---

## 📊 Performance Impact

### Token Savings Example
**Before v0.3.2:**
```
search_report (full metadata)     ~800 tokens
evolve_report (standard response) ~500 tokens
Total:                           ~1,300 tokens
```

**After v0.3.2:**
```
search_report (fields=["report_id", "title"])  ~200 tokens
evolve_report (response_detail="minimal")      ~150 tokens
Total:                                         ~350 tokens
```

**Savings: ~73% reduction** 🎉

### Workflow Comparison

**Multi-turn Analysis Workflow:**
1. Find report → Read summary → Modify section → Verify changes

**Before:** ~3,500 tokens across 4 operations
**After:** ~1,000 tokens across 4 operations
**Savings: 71% reduction**

---

## 🧪 Testing

### Test Coverage
- **631/631 tests passing** (100% pass rate)
- **23 new tests** for v0.3.2 features
- **6 new system-level** workflow tests
- **35 redundant tests** removed

### Test Distribution
- Unit tests: 458 tests
- Integration tests: 143 tests
- System tests: 30 tests

---

## 📁 Files Changed

### New Files
- `src/igloo_mcp/tools/get_report.py` - Progressive disclosure tool
- `src/igloo_mcp/tools/get_report_schema.py` - Schema introspection
- `tests/test_get_report_*.py` - 12 new test files
- `tests/test_get_report_schema_*.py` - 6 new test files
- `docs/user_guide_v0.3.2_additions.md` - Enhanced documentation

### Enhanced Files
- `src/igloo_mcp/tools/evolve_report.py` - Response detail parameter
- `src/igloo_mcp/tools/search_report.py` - Fields parameter
- `src/igloo_mcp/tools/render_report.py` - Preview size control
- `CHANGELOG.md` - Complete v0.3.2 changelog
- `README.md` - Updated examples and API reference

### Removed Files
- 35 redundant test files (~11,668 lines)
- Consolidated into focused test suites

---

## 🔄 Migration Guide

### Upgrading from v0.3.1

**No Breaking Changes** for existing tool usage (except query result limits).

**Optional Improvements:**

1. **Use Progressive Disclosure:**
```python
# Instead of always getting full report
get_report(report_selector="my-report", mode="full")

# Start with summary, drill down as needed
get_report(report_selector="my-report", mode="summary")
get_report(report_selector="my-report", mode="sections", section_ids=["sec-123"])
```

2. **Reduce Token Usage:**
```python
# Before
search_report(title="quarterly")
evolve_report(..., response_detail="full")

# After
search_report(title="quarterly", fields=["report_id", "title"])
evolve_report(..., response_detail="minimal")
```

3. **Use Schema Discovery:**
```python
# Instead of guessing structure
get_report_schema(schema_type="proposed_changes", format="examples")
```

### Adjusting Result Limits

If you need larger result sets:

```bash
# .env or shell configuration
export IGLOO_MCP_RESULT_SIZE_LIMIT_MB=10
export IGLOO_MCP_RESULT_KEEP_FIRST_ROWS=2000
export IGLOO_MCP_RESULT_KEEP_LAST_ROWS=200
export IGLOO_MCP_RESULT_TRUNCATION_THRESHOLD=5000
```

---

## 🎯 Issues Closed

This release closes **9 issues**:
- #48 - timeout_seconds type handling
- #49 - Enhanced validation errors
- #50 - Field path error messages
- #51 - New tools (get_report, get_report_schema)
- #52 - JSON schema documentation
- #53 - Response detail control
- #54 - Token efficiency (evolve_report)
- #55 - Enhanced dry_run validation
- #56 - Token efficiency (search_report)

---

## 🙏 Acknowledgments

Thanks to all contributors and users who provided feedback on the Living Reports system!

Special recognition for issue reports and feature requests that shaped this release.

---

## 📚 Documentation

### Updated Documentation
- [CHANGELOG.md](./CHANGELOG.md) - Complete version history
- [README.md](./README.md) - Updated examples and quick start
- User guide additions - Token efficiency patterns

### New Documentation
- Schema introspection guide
- Progressive disclosure patterns
- Token optimization strategies

---

## 🚀 Installation

### Via PyPI
```bash
pip install igloo-mcp==0.3.2
```

### Via uv
```bash
uv pip install igloo-mcp==0.3.2
```

### Verify Installation
```bash
igloo_mcp --version
# Output: igloo-mcp 0.3.2
```

---

## 🔗 Links

- **GitHub Repository:** https://github.com/Evan-Kim2028/igloo-mcp
- **Pull Request:** https://github.com/Evan-Kim2028/igloo-mcp/pull/64
- **PyPI Package:** https://pypi.org/project/igloo-mcp/0.3.2/
- **Documentation:** https://github.com/Evan-Kim2028/igloo-mcp#readme

---

## 📋 Checksums

Generated after PyPI publication.

---

**Full Changelog:** https://github.com/Evan-Kim2028/igloo-mcp/compare/v0.3.1...v0.3.2
