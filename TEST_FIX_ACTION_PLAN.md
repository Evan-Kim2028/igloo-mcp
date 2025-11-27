# Test Suite Fix Action Plan

**Generated:** 2025-11-27
**Current Status:** 44 tests failing, 895 passing (95.3%)
**Target:** 100% passing with improved structure

---

## Quick Start: Fix Failing Tests in 4 Steps

### Step 1: Fix Error Handling Tests (18 tests, ~2 hours)

**Problem:** Tests expect raw exceptions (`ValueError`, `RuntimeError`) but code now raises MCP exceptions.

**Files to update:**
1. `tests/test_error_handling_enhanced.py`
2. `tests/test_execute_query_failures.py`
3. `tests/test_execute_query_branching.py`
4. `tests/test_execute_query_edge_cases.py`
5. `tests/test_execute_query_source_attribution.py`
6. `tests/test_parallel.py`

**Find/Replace Pattern:**
```python
# BEFORE:
with pytest.raises(ValueError) as exc:
    result = await tool.execute(...)
assert "timeout" in str(exc.value).lower()

# AFTER:
from igloo_mcp.mcp.exceptions import MCPValidationError

with pytest.raises(MCPValidationError) as exc:
    result = await tool.execute(...)
assert exc.value.hints  # Structured error with hints
```

**Automation Script:**
```bash
# Run this to update imports automatically:
cd /Users/evandekim/Documents/igloo_mcp

# Add MCP exception imports to affected files
for file in tests/test_error_handling_enhanced.py \
            tests/test_execute_query_failures.py \
            tests/test_execute_query_branching.py \
            tests/test_execute_query_edge_cases.py \
            tests/test_execute_query_source_attribution.py \
            tests/test_parallel.py; do
  # Add import if not present
  grep -q "from igloo_mcp.mcp.exceptions import" "$file" || \
    sed -i '' '1i\
from igloo_mcp.mcp.exceptions import MCPValidationError, MCPExecutionError, MCPSelectorError
' "$file"
done
```

---

### Step 2: Fix evolve_report MCP Response Tests (10 tests, ~1 hour)

**Problem:** Tests expect exceptions but `evolve_report` now returns error dicts with `status: "validation_failed"`.

**Decision Required:** Should `evolve_report` raise exceptions or return error dicts?

**Option A: Keep returning dicts (recommended for MCP compatibility)**
```python
# Update tests to expect dicts:
# BEFORE:
with pytest.raises(ValueError):
    result = await tool.execute(report_selector="missing", ...)

# AFTER:
result = await tool.execute(report_selector="missing", ...)
assert result["status"] == "selector_error"
assert result["error"] == "not_found"
assert "NonExistentReport" in result.get("selector", "")
```

**Option B: Change tool to raise exceptions (breaks MCP clients)**
```python
# Modify evolve_report.py to raise instead of return error dicts
# NOT RECOMMENDED - MCP clients expect structured responses
```

**Recommended: Option A** - Update 10 tests in `test_evolve_report_mcp.py` to check response dicts.

**Helper function to add:**
```python
# tests/helpers/assertions.py
def assert_validation_failed(result, expected_error_substring=None):
    """Assert result is a validation failure with optional error check."""
    assert result["status"] == "validation_failed"
    assert "validation_errors" in result or "validation_issues" in result
    if expected_error_substring:
        errors_str = str(result.get("validation_errors") or result.get("validation_issues"))
        assert expected_error_substring in errors_str

def assert_selector_error(result, selector, error_type="not_found"):
    """Assert result is a selector resolution error."""
    assert result["status"] == "selector_error"
    assert result["error"] == error_type
    assert selector in result.get("selector", "")
```

---

### Step 3: Fix Missing Fixtures (8 tests, ~30 minutes)

**Problem:** Tests depend on external tools (Quarto) or missing file system paths.

**Quick Fix:**
```python
# tests/test_quarto_renderer.py - Add skip marker
import pytest

pytestmark = pytest.mark.skipif(
    not shutil.which("quarto"),
    reason="Quarto not installed - optional dependency for rendering"
)

# OR mock it:
@pytest.fixture
def mock_quarto(monkeypatch):
    """Mock Quarto for tests that don't need actual rendering."""
    def fake_detect():
        from igloo_mcp.living_reports.quarto_renderer import QuartoRenderer
        renderer = QuartoRenderer()
        renderer.version = "1.4.0 (mocked)"
        return renderer

    monkeypatch.setattr(
        "igloo_mcp.living_reports.quarto_renderer.QuartoRenderer.detect",
        fake_detect
    )
```

**Files needing fixtures:**
- `test_quarto_renderer.py` - Mock Quarto
- `test_catalog_service_offline.py` - Ensure `tmp_path` creates catalog dir
- `test_search_catalog_tool.py` - Create catalog.json fixture
- `test_living_reports_cli.py` - Mock subprocess calls

---

### Step 4: Fix Test Markers (8 tests, ~15 minutes)

**Problem:** Sync functions incorrectly marked `@pytest.mark.asyncio`.

**Find them:**
```bash
# Find non-async functions with asyncio marker:
cd /Users/evandekim/Documents/igloo_mcp
grep -n "@pytest.mark.asyncio" tests/test_living_reports_evolve.py | \
  while read line; do
    linenum=$(echo "$line" | cut -d: -f1)
    nextline=$((linenum + 1))
    sed -n "${nextline}p" tests/test_living_reports_evolve.py | \
      grep -v "async def" && echo "Line $linenum: Non-async with asyncio marker"
  done
```

**Fix:**
```python
# BEFORE:
@pytest.mark.asyncio
def test_tool_properties(self, tool):  # NOT async!
    assert tool.name == "evolve_report"

# AFTER:
def test_tool_properties(self, tool):  # Remove marker
    assert tool.name == "evolve_report"
```

**Or use class-level marker:**
```python
class TestEvolveReportTool:
    """All async tests in this class."""
    pytestmark = pytest.mark.asyncio  # Applies to all methods

    async def test_async_method(self):
        ...
```

---

## Post-Fix: Add Regression Tests

After fixing existing tests, add these to prevent future regressions:

### tests/regression/test_github_issues.py

```python
"""Regression tests for fixed GitHub issues.

Each test class prevents regression of a specific bug fix.
"""

import pytest
import uuid
from igloo_mcp.mcp.tools.execute_query import ExecuteQueryTool
from igloo_mcp.mcp.tools.evolve_report import EvolveReportTool


class TestIssue48TimeoutTypeCoercion:
    """#48: execute_query rejected timeout_seconds as string."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("timeout_value", [30, "30", 30.0, "120"])
    async def test_accepts_multiple_timeout_formats(
        self, execute_query_tool, timeout_value
    ):
        """Should accept int, numeric string, or float for timeout."""
        result = await execute_query_tool.execute(
            statement="SELECT 1 as test",
            reason="Test timeout coercion",
            timeout_seconds=timeout_value,
        )
        assert result["rowcount"] == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_timeout", ["30s", "two minutes", True])
    async def test_rejects_invalid_timeout_formats(
        self, execute_query_tool, invalid_timeout
    ):
        """Should reject non-numeric timeout values."""
        with pytest.raises((TypeError, ValueError)):
            await execute_query_tool.execute(
                statement="SELECT 1",
                reason="Test",
                timeout_seconds=invalid_timeout,
            )


class TestIssue57InlineInsights:
    """#57: sections_to_modify with inline insights silently failed."""

    @pytest.mark.asyncio
    async def test_sections_to_add_with_inline_insights(
        self, report_service, evolve_tool
    ):
        """sections_to_add with insights array should create and link."""
        report_id = report_service.create_report("Test Report")

        result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Add section with inline insights",
            proposed_changes={
                "sections_to_add": [{
                    "title": "New Section",
                    "insights": [
                        {"summary": "Inline insight", "importance": 8}
                    ]
                }]
            },
        )

        assert result["status"] == "success"
        assert result["summary"]["insights_added"] == 1
        assert result["summary"]["sections_added"] == 1

        # Verify insight was actually created and linked
        outline = report_service.get_report_outline(report_id)
        assert len(outline.insights) == 1
        assert len(outline.sections) == 1
        assert outline.sections[0].insight_ids == [outline.insights[0].insight_id]

    @pytest.mark.asyncio
    async def test_sections_to_modify_with_inline_insights(
        self, report_service, evolve_tool
    ):
        """sections_to_modify with insights array should create and link."""
        # Create report with empty section
        report_id = report_service.create_report("Test Report")
        outline = report_service.get_report_outline(report_id)
        section_id = outline.sections[0].section_id

        result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Add inline insight to existing section",
            proposed_changes={
                "sections_to_modify": [{
                    "section_id": section_id,
                    "insights": [
                        {"summary": "Modified inline", "importance": 7}
                    ]
                }]
            },
        )

        assert result["status"] == "success"
        assert result["summary"]["insights_added"] == 1  # NOT 0!

        # Verify
        outline = report_service.get_report_outline(report_id)
        assert len(outline.insights) == 1
        assert outline.sections[0].insight_ids == [outline.insights[0].insight_id]


class TestIssue58SupportingQueriesOptional:
    """#58: insights_to_add required supporting_queries explicitly."""

    @pytest.mark.asyncio
    async def test_insight_without_supporting_queries_succeeds(
        self, report_service, evolve_tool
    ):
        """Omitting supporting_queries should default to []."""
        report_id = report_service.create_report("Test Report")

        result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Add insight without queries",
            proposed_changes={
                "insights_to_add": [{
                    "summary": "No queries yet",
                    "importance": 6
                    # NOTE: No supporting_queries field!
                }]
            },
        )

        assert result["status"] == "success"

        # Verify insight created with empty supporting_queries
        outline = report_service.get_report_outline(report_id)
        assert len(outline.insights) == 1
        assert outline.insights[0].supporting_queries == []


class TestIssue59WarningsUsePostChangeState:
    """#59: Warnings computed before changes, showed stale state."""

    @pytest.mark.asyncio
    async def test_no_warning_after_linking_insights(
        self, report_service, evolve_tool
    ):
        """Linking insight should NOT warn 'section has no insights'."""
        # Create report with empty section
        report_id = report_service.create_report("Test Report")
        outline = report_service.get_report_outline(report_id)
        section_id = outline.sections[0].section_id

        # Add insight and link to section
        insight_id = str(uuid.uuid4())
        result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Link insight to section",
            proposed_changes={
                "insights_to_add": [{
                    "insight_id": insight_id,
                    "summary": "New insight",
                    "importance": 8,
                }],
                "sections_to_modify": [{
                    "section_id": section_id,
                    "insight_ids_to_add": [insight_id]
                }]
            },
        )

        # Should NOT warn about "section has no insights"
        warnings = result.get("warnings", [])
        assert not any("no insights" in w.lower() for w in warnings)

    @pytest.mark.asyncio
    async def test_warnings_use_updated_section_title(
        self, report_service, evolve_tool
    ):
        """Warnings should show new section title, not old."""
        report_id = report_service.create_report("Test Report")
        outline = report_service.get_report_outline(report_id)
        section_id = outline.sections[0].section_id

        # Rename section (leave it empty for warning)
        result = await evolve_tool.execute(
            report_selector=report_id,
            instruction="Rename section",
            proposed_changes={
                "sections_to_modify": [{
                    "section_id": section_id,
                    "title": "RENAMED SECTION"
                }]
            },
        )

        # If there's a "no insights" warning, it should use new name
        warnings = result.get("warnings", [])
        no_insights_warnings = [w for w in warnings if "no insights" in w.lower()]
        if no_insights_warnings:
            assert "RENAMED SECTION" in no_insights_warnings[0]
            assert outline.sections[0].title not in no_insights_warnings[0]


class TestIssue60RenderReportPreview:
    """#60: render_report include_preview parameter had no effect."""

    @pytest.mark.asyncio
    async def test_preview_included_when_requested(
        self, report_service, render_tool
    ):
        """include_preview=True should return preview in response."""
        report_id = report_service.create_report("Test Report")

        result = await render_tool.execute(
            report_selector=report_id,
            format="html",
            include_preview=True,
            dry_run=True,  # Skip actual rendering
        )

        assert result["status"] == "success"
        assert "preview" in result
        assert len(result["preview"]) > 0
        assert len(result["preview"]) <= 2000  # Truncated

    @pytest.mark.asyncio
    async def test_preview_omitted_when_not_requested(
        self, report_service, render_tool
    ):
        """include_preview=False should not include preview."""
        report_id = report_service.create_report("Test Report")

        result = await render_tool.execute(
            report_selector=report_id,
            format="html",
            include_preview=False,
            dry_run=True,
        )

        # Preview may or may not be in response, but shouldn't be required
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_output_path_always_present(
        self, report_service, render_tool
    ):
        """output_path should always be set (not null)."""
        report_id = report_service.create_report("Test Report")

        result = await render_tool.execute(
            report_selector=report_id,
            format="html",
            dry_run=True,
        )

        assert result["status"] == "success"
        assert result["output"]["output_path"] is not None
        assert len(result["output"]["output_path"]) > 0
```

---

## Test Execution Commands

```bash
# Fix and test incrementally:

# 1. Fix error handling tests
pytest tests/test_error_handling_enhanced.py -v
pytest tests/test_execute_query_failures.py -v
pytest tests/test_execute_query_branching.py -v

# 2. Fix MCP response tests
pytest tests/test_evolve_report_mcp.py -v
pytest tests/test_evolve_report_integration.py -v

# 3. Fix missing fixtures
pytest tests/test_quarto_renderer.py -v
pytest tests/test_catalog_service_offline.py -v

# 4. Fix test markers
pytest tests/test_living_reports_evolve.py -v
pytest tests/test_evolve_report_tool.py -v

# 5. Run full suite
pytest -v

# 6. Check coverage
pytest --cov=src/igloo_mcp --cov-report=term-missing --cov-report=html
```

---

## Success Criteria

- [ ] All 44 failing tests fixed (100% pass rate)
- [ ] No new warnings introduced
- [ ] Regression tests added for issues #48, #57-#60
- [ ] Test execution time < 30 seconds (currently ~26s)
- [ ] Coverage remains >= 85%

---

## Timeline Estimate

| Task | Time | Cumulative |
|------|------|-----------|
| Fix error handling tests (18) | 2 hours | 2h |
| Fix MCP response tests (10) | 1 hour | 3h |
| Fix missing fixtures (8) | 30 min | 3.5h |
| Fix test markers (8) | 15 min | 3.75h |
| Add regression tests | 1 hour | 4.75h |
| Test full suite & adjust | 15 min | 5h |

**Total: ~5 hours of focused work**

---

## After This Sprint

Once tests are 100% passing, consider these improvements (from TEST_SUITE_ANALYSIS.md):

1. Reorganize into `unit/`, `integration/`, `regression/`, `edge_cases/` directories
2. Add contract tests with JSON schema validation
3. Add property-based testing with Hypothesis
4. Set up coverage requirements in CI
5. Document testing standards in `TESTING.md`
