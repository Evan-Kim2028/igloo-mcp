# Test Suite Analysis & Improvement Plan

**Date:** 2025-11-27
**Scope:** Complete test suite review for igloo-mcp v0.3.2
**Status:** 895 passing / 44 failing (95.3% pass rate)

---

## Executive Summary

### Current State
- **Total Tests:** 941 tests across 76 test files
- **Pass Rate:** 95.3% (895 passing, 44 failing, 2 skipped)
- **Test Coverage:** Comprehensive but with structural issues
- **Main Issues:**
  1. Error handling changes broke 18 tests expecting old exception behavior
  2. MCP exception refactoring broke selector/validation error tests (10 tests)
  3. Missing test fixtures/dependencies (8 tests)
  4. Deprecated test patterns (8 tests with incorrect async markers)

### Key Findings

**✅ Strengths:**
- Extensive coverage of core functionality (execute_query, living reports, catalog)
- Good separation of unit/integration tests
- Comprehensive edge case coverage (unicode, SQL injection, encoding)
- Test helpers (fake connectors, fixtures) enable isolated testing

**⚠️  Weaknesses:**
- Tests tightly coupled to exception types (brittle to refactoring)
- Inconsistent error assertion patterns across test files
- No contract tests for MCP response schemas
- Missing regression tests for GitHub issues #57-#60
- Quarto renderer tests fail in CI (external dependency)

---

## Detailed Failure Analysis

### Category 1: Error Handling Refactoring (18 tests)

**Root Cause:** Tests expect raw exceptions but new code wraps them in `MCPValidationError`, `MCPExecutionError`, or `MCPSelectorError`.

**Affected Tests:**
```python
# Old pattern (fails now):
with pytest.raises(ValueError) as exc:
    await tool.execute(...)
assert "not found" in str(exc.value)

# New pattern (required):
with pytest.raises(MCPSelectorError) as exc:
    await tool.execute(...)
assert exc.value.error == "not_found"
```

**Files:**
- `test_error_handling_enhanced.py` (5 failures)
- `test_execute_query_failures.py` (2 failures)
- `test_execute_query_branching.py` (3 failures)
- `test_execute_query_edge_cases.py` (1 failure)
- `test_execute_query_source_attribution.py` (4 failures)
- `test_parallel.py` (3 failures)

**Fix Strategy:**
1. Update all `pytest.raises(ValueError)` to `pytest.raises(MCPValidationError)`
2. Update all `pytest.raises(RuntimeError)` to `pytest.raises(MCPExecutionError)`
3. Change assertions from string matching to structured field checks
4. Add `from igloo_mcp.mcp.exceptions import *` imports

---

### Category 2: MCP Response Schema Changes (10 tests)

**Root Cause:** `evolve_report` validation errors now return dictionaries with `status: "validation_failed"` instead of raising exceptions.

**Example:**
```python
# Old (raises exception):
with pytest.raises(ValueError):
    await evolve_tool.execute(report_selector="missing", ...)

# New (returns error dict):
result = await evolve_tool.execute(report_selector="missing", ...)
assert result["status"] == "selector_error"  # or "validation_failed"
assert result["error"] == "not_found"
```

**Affected Tests:**
- `test_evolve_report_mcp.py` (6 failures)
- `test_evolve_report_integration.py` (2 failures)
- `test_evolve_report_tool.py` (1 failure)
- `test_mcp_error_handling.py` (1 failure)

**Fix Strategy:**
1. Replace exception assertions with status code checks
2. Add schema validation for error responses
3. Create helper: `assert_validation_failed(result, expected_error)`

---

### Category 3: Missing Fixtures/Dependencies (8 tests)

**Root Cause:** Tests depend on Quarto, file system paths, or external tools not available in test environment.

**Affected:**
- `test_quarto_renderer.py` (5 tests) - Quarto not installed
- `test_catalog_service_offline.py` (2 tests) - Missing catalog directory
- `test_search_catalog_tool.py` (2 tests) - Missing catalog files
- `test_living_reports_cli.py` (1 test) - CLI subprocess issues

**Fix Strategy:**
1. Mock Quarto with `monkeypatch` for renderer tests
2. Use `tmp_path` fixture for all file system tests
3. Add `@pytest.mark.requires_quarto` skip marker
4. Ensure fixtures create necessary directories

---

### Category 4: Test Pattern Issues (8 tests)

**Root Cause:** Incorrect pytest markers or deprecated patterns.

**Affected:**
- `test_living_reports_evolve.py` - Non-async tests marked `@pytest.mark.asyncio`
- `test_evolve_report_tool.py` - Same issue
- `test_living_reports_index.py` - Corruption tests expecting old behavior

**Fix Strategy:**
1. Remove `@pytest.mark.asyncio` from sync test functions
2. Update corruption handling tests for graceful degradation
3. Use `pytestmark` class-level marker where appropriate

---

## Testing Gaps That Could Have Caught GitHub Issues

### Issue #48: timeout_seconds Type Error

**What Happened:** Parameter rejected numeric strings like `"240"`

**Missing Test:**
```python
@pytest.mark.parametrize("timeout_value", [30, "30", 30.0])
async def test_timeout_accepts_multiple_formats(timeout_value):
    """Regression test for #48 - accept int, str, float."""
    result = await execute_query(..., timeout_seconds=timeout_value)
    assert result["rowcount"] >= 0
```

**Lesson:** Need parametrized type coercion tests for all optional parameters.

---

### Issue #57: Inline Insights Silently Ignored

**What Happened:** `sections_to_modify` with `insights` array succeeded but created nothing.

**Missing Test:**
```python
async def test_inline_insights_on_section_modify_creates_insights():
    """Regression test for #57 - inline insights should be created."""
    result = await evolve_report(..., proposed_changes={
        "sections_to_modify": [{
            "section_id": existing_id,
            "insights": [{"summary": "New", "importance": 8}]
        }]
    })
    assert result["summary"]["insights_added"] == 1  # Should NOT be 0
```

**Lesson:** Need assertions on operation counts in summary, not just status.

---

### Issue #58: supporting_queries Required But Should Default

**What Happened:** Omitting `supporting_queries` caused Pydantic validation error.

**Missing Test:**
```python
async def test_insights_without_supporting_queries_defaults_to_empty():
    """Regression test for #58 - supporting_queries should default."""
    result = await evolve_report(..., proposed_changes={
        "insights_to_add": [{
            "summary": "Test",
            "importance": 7
            # No supporting_queries field
        }]
    })
    assert result["status"] == "success"
```

**Lesson:** Need tests that omit every optional field to verify defaults work.

---

### Issue #59: Warnings Computed Before Changes Applied

**What Happened:** Linking insights still showed "section has no insights" warning.

**Missing Test:**
```python
async def test_warnings_reflect_post_change_state():
    """Regression test for #59 - warnings use new state."""
    # Section starts with no insights
    result = await evolve_report(..., proposed_changes={
        "sections_to_modify": [{
            "section_id": section_id,
            "insight_ids_to_add": [new_insight_id]
        }]
    })
    # Should NOT warn about "no insights" after adding one
    assert not any("no insights" in w for w in result.get("warnings", []))
```

**Lesson:** Need state-transition tests checking intermediate vs final state.

---

### Issue #60: include_preview Had No Effect

**What Happened:** Parameter ignored, no preview in response.

**Missing Test:**
```python
async def test_render_report_preview_when_requested():
    """Regression test for #60 - preview should be included."""
    result = await render_report(..., include_preview=True)
    assert "preview" in result
    assert len(result["preview"]) > 0
    assert len(result["preview"]) <= 2000  # Truncated
```

**Lesson:** Need explicit tests for every response field when optional flags set.

---

## Proposed Testing Improvements

### 1. Contract Tests for MCP Responses

Create schema validators for all MCP tool responses:

```python
# tests/schemas/mcp_response_schemas.py
EVOLVE_REPORT_SUCCESS_SCHEMA = {
    "type": "object",
    "required": ["status", "report_id", "outline_version", "summary"],
    "properties": {
        "status": {"const": "success"},
        "report_id": {"type": "string", "pattern": "^rpt_"},
        "outline_version": {"type": "integer", "minimum": 1},
        "summary": {
            "type": "object",
            "required": ["insights_added", "sections_added"],
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
    }
}

EVOLVE_REPORT_ERROR_SCHEMA = {
    "type": "object",
    "required": ["status", "error"],
    "properties": {
        "status": {"enum": ["validation_failed", "selector_error", "error"]},
        "error": {"type": "string"},
        "validation_errors": {"type": "array"},
        "hints": {"type": "array"},
    }
}

def assert_valid_response(response, schema):
    """Validate response matches JSON schema."""
    from jsonschema import validate
    validate(instance=response, schema=schema)
```

**Usage:**
```python
async def test_evolve_report_success_response_schema():
    result = await evolve_tool.execute(...)
    assert_valid_response(result, EVOLVE_REPORT_SUCCESS_SCHEMA)
```

---

### 2. Regression Test Suite for GitHub Issues

Create `tests/test_github_regressions.py`:

```python
"""Regression tests for fixed GitHub issues.

Each test documents the issue it prevents from recurring.
"""

class TestIssue48TimeoutTypeCoercion:
    """Prevent regression of #48 - timeout_seconds type error."""

    @pytest.mark.parametrize("timeout", [30, "30", 30.0, "120"])
    async def test_accepts_multiple_timeout_formats(self, timeout):
        result = await execute_query(..., timeout_seconds=timeout)
        assert result["rowcount"] >= 0

    async def test_rejects_invalid_timeout_formats(self):
        with pytest.raises(TypeError):
            await execute_query(..., timeout_seconds="30s")

class TestIssue57InlineInsights:
    """Prevent regression of #57 - inline insights ignored."""

    async def test_sections_to_add_with_inline_insights(self):
        result = await evolve_report(..., proposed_changes={
            "sections_to_add": [{
                "title": "New Section",
                "insights": [{"summary": "Inline", "importance": 8}]
            }]
        })
        assert result["summary"]["insights_added"] == 1
        assert result["summary"]["sections_added"] == 1

    async def test_sections_to_modify_with_inline_insights(self):
        # Currently FAILING - this is the actual bug from #57
        result = await evolve_report(..., proposed_changes={
            "sections_to_modify": [{
                "section_id": existing_section_id,
                "insights": [{"summary": "Inline", "importance": 8}]
            }]
        })
        assert result["summary"]["insights_added"] == 1
```

---

### 3. Property-Based Testing for Data Models

Use Hypothesis to generate random valid/invalid inputs:

```python
from hypothesis import given, strategies as st
from igloo_mcp.living_reports.models import Insight

# Generate random insights
insight_strategy = st.builds(
    Insight,
    insight_id=st.uuids().map(str),
    summary=st.text(min_size=1, max_size=500),
    importance=st.integers(min_value=0, max_value=10),
    supporting_queries=st.lists(st.builds(DatasetSource, ...))
)

@given(insight=insight_strategy)
def test_insight_serialization_roundtrip(insight):
    """Any valid Insight should serialize and deserialize."""
    json_data = insight.model_dump_json()
    restored = Insight.model_validate_json(json_data)
    assert restored == insight
```

---

### 4. Test Organization Improvements

**Current Structure (76 files, confusing):**
```
tests/
├── test_execute_query_tool.py
├── test_execute_query_failures.py
├── test_execute_query_branching.py
├── test_execute_query_edge_cases.py
├── test_execute_query_timeout_and_history.py
├── test_execute_query_additional.py
... (fragmented)
```

**Proposed Structure (consolidated):**
```
tests/
├── unit/
│   ├── mcp_tools/
│   │   ├── test_execute_query.py          # All execute_query unit tests
│   │   ├── test_evolve_report.py          # All evolve_report unit tests
│   │   ├── test_render_report.py
│   │   └── test_create_report.py
│   ├── living_reports/
│   │   ├── test_models.py
│   │   ├── test_storage.py
│   │   ├── test_index.py
│   │   └── test_service.py
│   ├── catalog/
│   │   └── test_catalog_service.py
│   └── core/
│       ├── test_config.py
│       ├── test_sql_validation.py
│       └── test_session_utils.py
├── integration/
│   ├── test_execute_query_integration.py  # End-to-end query tests
│   ├── test_living_reports_integration.py
│   └── test_mcp_server_integration.py
├── regression/
│   └── test_github_issues.py              # One test per fixed issue
├── edge_cases/
│   ├── test_unicode_handling.py
│   ├── test_sql_injection.py
│   └── test_malformed_data.py
├── fixtures/
│   ├── conftest.py                        # Shared fixtures
│   ├── fake_snowflake_connector.py
│   └── golden_fixtures/
└── helpers/
    └── assertions.py                      # assert_valid_mcp_response(), etc.
```

**Benefits:**
- Easier to find related tests
- Clearer separation of concerns
- Shared fixtures in obvious locations
- Less duplication

---

### 5. Test Execution Improvements

**Add pytest markers:**
```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
markers = [
    "unit: Fast unit tests (< 0.1s each)",
    "integration: Integration tests (may be slower)",
    "requires_quarto: Requires Quarto installation",
    "requires_snowflake: Requires Snowflake connection",
    "slow: Slow tests (> 1s)",
    "flaky: Tests that occasionally fail (investigate)",
]
```

**Usage:**
```bash
# Run only fast unit tests during development
pytest -m unit

# Run full suite in CI
pytest -m "not requires_snowflake"

# Debug flaky tests
pytest -m flaky --count=100  # Run 100 times
```

---

### 6. Coverage Requirements

**Current:** Unknown (no coverage report in CI)

**Proposed:**
```bash
pytest --cov=src/igloo_mcp --cov-report=html --cov-report=term-missing \
    --cov-fail-under=85
```

**Coverage Goals:**
- Overall: 85%
- MCP tools: 95% (critical path)
- Living reports: 90% (complex logic)
- Utilities: 80% (less critical)

**Exclude from coverage:**
- `__init__.py` files
- Test helpers
- Type stubs

---

## Action Plan

### Immediate (Fix Failing Tests)

1. **Update error assertions** (affects 18 tests)
   - Import MCP exception types
   - Replace `ValueError` → `MCPValidationError`
   - Replace `RuntimeError` → `MCPExecutionError`
   - Change string assertions to structured field checks

2. **Fix evolve_report response assertions** (affects 10 tests)
   - Replace exception expectations with status dict checks
   - Add helpers: `assert_validation_failed()`, `assert_selector_error()`

3. **Fix missing fixtures** (affects 8 tests)
   - Mock Quarto renderer
   - Ensure `tmp_path` used for all file operations
   - Add skip markers for external dependencies

4. **Clean up test markers** (affects 8 tests)
   - Remove `@pytest.mark.asyncio` from sync functions
   - Add class-level `pytestmark` where appropriate

### Short Term (Prevent Regressions)

5. **Add GitHub issue regression tests**
   - Create `tests/regression/test_github_issues.py`
   - One test class per fixed issue (#48, #57-#60)
   - Document what each test prevents

6. **Add contract tests**
   - Define JSON schemas for all MCP responses
   - Validate every tool response against schema
   - Catch breaking changes early

### Medium Term (Improve Structure)

7. **Reorganize test suite**
   - Create `unit/`, `integration/`, `regression/`, `edge_cases/` directories
   - Consolidate fragmented test files
   - Move shared fixtures to `fixtures/conftest.py`

8. **Add property-based tests**
   - Use Hypothesis for model serialization
   - Random SQL generation for validation tests
   - Fuzzing for robust error handling

### Long Term (Best Practices)

9. **Implement test coverage requirements**
   - Add coverage checks to CI
   - Require 85% overall coverage
   - Block PRs that reduce coverage

10. **Document testing standards**
    - Create `TESTING.md` guide
    - Test naming conventions
    - When to write unit vs integration tests
    - How to use test helpers

---

## Metrics

### Before Improvements
- **Tests:** 941
- **Passing:** 895 (95.3%)
- **Test Files:** 76
- **Avg Tests/File:** 12.4
- **Fragmentation:** High (execute_query split across 6 files)

### After Improvements (Target)
- **Tests:** ~1000 (add regression tests)
- **Passing:** 1000 (100%)
- **Test Files:** ~50 (consolidate)
- **Avg Tests/File:** 20
- **Fragmentation:** Low (grouped by component)
- **Coverage:** 85%+

---

## Conclusion

The test suite is **comprehensive but disorganized**. With 941 tests and 95% passing, coverage is good, but the failures reveal:

1. **Brittleness:** Tests too coupled to implementation details (exception types)
2. **Missing contracts:** No schema validation for MCP responses
3. **Poor organization:** 76 files make navigation difficult
4. **Gaps in regression testing:** Fixed bugs could easily regress

**Priority:** Fix the 44 failing tests immediately, then add regression tests for #48, #57-#60 to prevent future breaks.

The proposed improvements would:
- ✅ Catch all 5 recent GitHub issues before they reach users
- ✅ Make tests more maintainable (less coupling)
- ✅ Improve developer experience (faster test discovery)
- ✅ Enable confident refactoring (contract tests)
