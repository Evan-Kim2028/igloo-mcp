# API Completeness Batch Implementation Plan

## Overview

This plan addresses 6 related API completeness issues that enhance response metadata, traceability, and consistency across MCP tools.

**Issues in Batch:**
- #67: Add `insight_ids_removed` and `section_ids_removed` to evolve_report response
- #68: Add `section_ids_removed` to audit trail
- #69: create_report should return `section_ids_added` and `insight_ids_added`
- #71: Add `request_id` to catalog and health tool responses
- #70: Add `timing` field to catalog and health tool responses
- #73: Add `warnings` field to more tool responses

**Motivation:**
- **Response Symmetry**: "If you add X, also return X in the response"
- **Distributed Tracing**: request_id correlation across multiple tool calls
- **Performance Monitoring**: timing data for optimization
- **User Feedback**: warnings for non-fatal issues
- **Audit Completeness**: Full tracking of removed entities

## Critical Questions Requiring Decisions

### Q1: Response Size vs. Completeness Trade-off
**Question:** For tools returning large result sets (search_catalog, list queries), should we include full timing/request_id metadata in every response?

**Options:**
- A) Always include (consistency first)
- B) Make optional via `include_metadata=true` parameter
- C) Only include in standard/full detail levels

**Recommendation:** Option A - Always include. Metadata overhead is minimal (~50 bytes) vs. typical response sizes (1-100KB).

### Q2: Backward Compatibility Strategy
**Question:** Should we maintain backward compatibility for existing consumers expecting old response shapes?

**Options:**
- A) Breaking change with version bump (0.3.3 → 0.4.0)
- B) Additive only (new fields, preserve existing)
- C) Deprecation period with warnings

**Recommendation:** Option B - Additive changes only. All new fields are additions, no existing fields removed. Version 0.3.3 is appropriate.

### Q3: Timing Granularity
**Question:** What timing metrics should we include?

**Options:**
- A) Total duration only: `{"timing": {"total_duration_ms": 1250}}`
- B) Operation breakdown: `{"timing": {"query_ms": 800, "processing_ms": 350, "total_ms": 1150}}`
- C) Detailed with I/O: `{"timing": {"db_ms": 500, "network_ms": 200, "compute_ms": 150}}`

**Recommendation:** Option A for catalog/health tools (simple operations), Option B for evolve_report/create_report (multi-step operations).

### Q4: Warnings Field Structure
**Question:** What structure should the `warnings` field use?

**Options:**
- A) Array of strings: `["Warning message 1", "Warning message 2"]`
- B) Structured objects: `[{"code": "W001", "message": "...", "context": {...}}]`
- C) Severity levels: `{"low": [...], "medium": [...], "high": [...]}`

**Recommendation:** Option B - Structured for programmatic handling:
```python
{
  "warnings": [
    {
      "code": "PARTIAL_RESULTS",
      "message": "3 tables excluded due to permissions",
      "severity": "medium",
      "context": {"excluded_count": 3}
    }
  ]
}
```

### Q5: Empty vs. Null for Optional Fields
**Question:** Should optional fields return empty collections or be omitted entirely?

**Options:**
- A) Always include: `"warnings": []`, `"insight_ids_removed": []`
- B) Omit when empty (JSON schema allows both)
- C) Null when empty: `"warnings": null`

**Recommendation:** Option A - Always include empty arrays for consistency and easier client code (no null checks needed).

### Q6: request_id Generation Strategy
**Question:** How should request_id be generated when not provided?

**Current Implementation:** `ensure_request_id()` generates UUID4 if not provided
**Question:** Should we support correlation prefixes like `req_batch_001_step_1`?

**Recommendation:** Keep current UUID4 approach. Clients needing batch correlation can provide their own request_id values.

## Implementation Approach

### Issue #67: Add insight_ids_removed and section_ids_removed to evolve_report

**File:** `src/igloo_mcp/mcp/tools/evolve_report.py`

**Changes Required:**

1. **Add removed IDs to response (lines 576-577)**
```python
# Current (line 576-577):
"insight_ids_added": [c.insight_id for c in changes_obj.insights_to_add],
"section_ids_added": [c.section_id for c in changes_obj.sections_to_add],

# Add after line 577:
"insight_ids_removed": [c for c in changes_obj.insights_to_remove],
"section_ids_removed": [c for c in changes_obj.sections_to_remove],
```

2. **Update response schema documentation (lines 315-340)**
```python
{
  "type": "object",
  "properties": {
    "insight_ids_added": {"type": "array", "items": {"type": "string"}},
    "section_ids_added": {"type": "array", "items": {"type": "string"}},
    "insight_ids_removed": {"type": "array", "items": {"type": "string"}},  # NEW
    "section_ids_removed": {"type": "array", "items": {"type": "string"}},  # NEW
    ...
  }
}
```

**Testing:**
- Test case: Remove 2 insights, verify `insight_ids_removed` contains both IDs
- Test case: Remove 1 section, verify `section_ids_removed` contains ID
- Test case: No removals, verify fields return empty arrays `[]`

---

### Issue #68: Add section_ids_removed to audit trail

**File:** `src/igloo_mcp/living_reports/service.py`

**Changes Required:**

1. **Add section_ids_removed to audit entry (line 355)**

```python
# Current (lines 345-365):
audit_entry = {
    "timestamp": datetime.now(UTC).isoformat(),
    "actor": actor,
    "action": "evolve",
    "report_id": report_id,
    "changes_summary": {
        "insights_added": len(changes_obj.insights_to_add),
        "insights_removed": len(changes_obj.insights_to_remove),
        "sections_added": len(changes_obj.sections_to_add),
        "sections_removed": len(changes_obj.sections_to_remove),
    },
    "insight_ids_added": insight_ids_added,
    "insight_ids_removed": insight_ids_removed,
    # ADD HERE (after line 355):
    "section_ids_removed": section_ids_removed,  # Variable already computed at line 332
    "section_ids_added": section_ids_added,
}
```

**Note:** The `section_ids_removed` variable is already computed at line 332:
```python
section_ids_removed = [c for c in changes_obj.sections_to_remove]
```

**Testing:**
- Test case: Verify audit trail JSON includes `section_ids_removed` field
- Test case: Remove 2 sections, verify audit entry has `"section_ids_removed": ["id1", "id2"]`
- Test case: Validate audit trail immutability (append-only log)

---

### Issue #69: create_report should return section_ids_added and insight_ids_added

**File:** `src/igloo_mcp/mcp/tools/create_report.py`

**Changes Required:**

1. **Retrieve created IDs after report creation (after line 176)**

```python
# Current (line 170-176):
try:
    report_id = self.report_service.create_report(
        title=title,
        template=template,
        actor="agent",
        initial_sections=initial_sections,
        **metadata,
    )

# ADD AFTER line 176:
    # Get outline to retrieve created section/insight IDs
    outline = self.report_service.get_report_outline(report_id)
    section_ids_added = [s.section_id for s in outline.sections]
    insight_ids_added = [i.insight_id for i in outline.insights]
```

2. **Add to response dictionary (lines 226-238)**

```python
# Current return (lines 226-238):
return {
    "status": "success",
    "report_id": report_id,
    "title": title,
    "template": template,
    "tags": tags or [],
    "message": f"Created report '{title}' with ID: {report_id}",
    "request_id": request_id,
    "timing": {
        "create_duration_ms": round(create_duration, 2),
        "total_duration_ms": round(total_duration, 2),
    },
}

# UPDATED return:
return {
    "status": "success",
    "report_id": report_id,
    "section_ids_added": section_ids_added,  # NEW
    "insight_ids_added": insight_ids_added,  # NEW
    "title": title,
    "template": template,
    "tags": tags or [],
    "message": f"Created report '{title}' with ID: {report_id}",
    "request_id": request_id,
    "timing": {
        "create_duration_ms": round(create_duration, 2),
        "outline_duration_ms": round(outline_duration, 2),  # NEW timing
        "total_duration_ms": round(total_duration, 2),
    },
}
```

3. **Update response schema (lines 240-323)**

Add to schema properties:
```python
"section_ids_added": {
    "type": "array",
    "items": {"type": "string"},
    "description": "IDs of sections created from template or initial_sections",
},
"insight_ids_added": {
    "type": "array",
    "items": {"type": "string"},
    "description": "IDs of insights created from template or initial_sections",
},
```

**Testing:**
- Test case: Create with `template="default"`, verify both arrays empty `[]`
- Test case: Create with `template="monthly_sales"`, verify section_ids_added contains 3+ sections
- Test case: Create with `initial_sections` containing inline insights, verify both arrays populated
- Test case: Timing breakdown includes `outline_duration_ms`

---

### Issue #71: Add request_id to catalog and health tool responses

**Files to Update:**
1. `src/igloo_mcp/mcp/tools/build_catalog.py`
2. `src/igloo_mcp/mcp/tools/get_catalog_summary.py`
3. `src/igloo_mcp/mcp/tools/search_catalog.py`
4. `src/igloo_mcp/mcp/tools/health.py`

**Pattern to Apply (All Files):**

1. **Add request_id parameter to execute() signature**
```python
async def execute(
    self,
    # ... existing params ...
    request_id: Optional[str] = None,  # NEW
) -> Dict[str, Any]:
```

2. **Add request_id handling at start of execute()**
```python
start_time = time.time()
request_id = ensure_request_id(request_id)  # NEW

logger.info(
    "tool_started",
    extra={"request_id": request_id, ...},  # NEW
)
```

3. **Add to response dictionary**
```python
return {
    "status": "success",
    "request_id": request_id,  # NEW - Add before timing
    # ... existing fields ...
}
```

4. **Update parameter schema**
```python
"request_id": {
    "type": "string",
    "description": "Optional request correlation ID for tracing (auto-generated if not provided)",
},
```

**Specific Changes Per File:**

**build_catalog.py (lines 115-150)**
- Add `request_id` parameter to execute()
- Add `ensure_request_id()` call after line 124
- Add to response at line 145
- Update schema at line 190

**get_catalog_summary.py (lines 85-120)**
- Add `request_id` parameter to execute()
- Add `ensure_request_id()` call after line 94
- Add to response at line 115
- Update schema at line 160

**search_catalog.py (lines 125-180)**
- Add `request_id` parameter to execute()
- Add `ensure_request_id()` call after line 135
- Add to response at line 175
- Update schema at line 230

**health.py (lines 65-95)**
- Add `request_id` parameter to execute()
- Add `ensure_request_id()` call after line 73
- Add to response at line 90
- Update schema at line 125

**Testing:**
- Test case: Call without request_id, verify auto-generated UUID format
- Test case: Call with custom request_id, verify same ID returned
- Test case: Make 3 sequential calls with same request_id, verify correlation in logs

---

### Issue #70: Add timing field to catalog and health tool responses

**Files to Update:** (Same 4 files as #71)
1. `src/igloo_mcp/mcp/tools/build_catalog.py`
2. `src/igloo_mcp/mcp/tools/get_catalog_summary.py`
3. `src/igloo_mcp/mcp/tools/search_catalog.py`
4. `src/igloo_mcp/mcp/tools/health.py`

**Pattern to Apply:**

1. **Add timing capture at start of execute()**
```python
start_time = time.time()
request_id = ensure_request_id(request_id)
```

2. **Add operation-specific timing markers (for multi-step operations)**
```python
# Example from build_catalog:
catalog_start = time.time()
catalog_data = self.snowflake_service.get_catalog(...)
catalog_duration = (time.time() - catalog_start) * 1000
```

3. **Calculate total duration before return**
```python
total_duration = (time.time() - start_time) * 1000
```

4. **Add timing to response**
```python
return {
    "status": "success",
    "request_id": request_id,
    "timing": {
        "total_duration_ms": round(total_duration, 2),
        # Optional breakdown for complex operations:
        "catalog_fetch_ms": round(catalog_duration, 2),
        "processing_ms": round(processing_duration, 2),
    },
    # ... existing fields ...
}
```

**Specific Timing Breakdowns:**

**build_catalog.py** (Complex - use breakdown):
```python
"timing": {
    "catalog_fetch_ms": round(catalog_duration, 2),
    "write_duration_ms": round(write_duration, 2),
    "total_duration_ms": round(total_duration, 2),
}
```

**get_catalog_summary.py** (Simple - total only):
```python
"timing": {
    "total_duration_ms": round(total_duration, 2),
}
```

**search_catalog.py** (Medium - optional breakdown):
```python
"timing": {
    "search_duration_ms": round(search_duration, 2),
    "total_duration_ms": round(total_duration, 2),
}
```

**health.py** (Simple - total only):
```python
"timing": {
    "total_duration_ms": round(total_duration, 2),
}
```

**Testing:**
- Test case: Verify all durations are positive numbers
- Test case: Verify `total_duration_ms >= sum(breakdown_durations)` (allows for measurement overhead)
- Test case: Slow operation (>1000ms), verify timing reflects actual duration
- Performance baseline: Document median durations for each tool

---

### Issue #73: Add warnings field to more tool responses

**Candidate Tools for Warnings:**

1. **build_catalog.py** - Warnings when:
   - Tables excluded due to permissions
   - Partial catalog built (some databases inaccessible)
   - Cache inconsistencies detected

2. **search_catalog.py** - Warnings when:
   - Results truncated (limit applied)
   - Partial matches only (no exact matches)
   - Deprecated query patterns used

3. **evolve_report.py** - Warnings when:
   - Insights removed had active references
   - Sections reordered affecting narrative flow
   - Validation passed with soft errors

4. **execute_query.py** - Warnings when:
   - Query timeout approaching
   - Result set truncated
   - Deprecated SQL functions used

**Warning Structure (Option B from Q4):**
```python
{
  "code": "WARNING_CODE",
  "message": "Human-readable description",
  "severity": "low" | "medium" | "high",
  "context": {...}  # Optional additional data
}
```

**Implementation Pattern:**

1. **Add warnings collection**
```python
warnings = []

# During operation:
if some_condition:
    warnings.append({
        "code": "PARTIAL_RESULTS",
        "message": "3 tables excluded due to insufficient permissions",
        "severity": "medium",
        "context": {"excluded_count": 3, "required_role": "ACCOUNTADMIN"},
    })
```

2. **Add to response**
```python
return {
    "status": "success",
    "warnings": warnings,  # Always include, even if empty []
    # ... other fields ...
}
```

3. **Update schema**
```python
"warnings": {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "message": {"type": "string"},
            "severity": {"type": "string", "enum": ["low", "medium", "high"]},
            "context": {"type": "object"},
        },
        "required": ["code", "message", "severity"],
    },
    "description": "Non-fatal warnings about the operation",
}
```

**Warning Codes to Implement:**

**build_catalog.py:**
- `PARTIAL_CATALOG`: Some databases/schemas inaccessible
- `PERMISSION_DENIED`: Tables excluded due to permissions
- `CACHE_STALE`: Cached data may be outdated

**search_catalog.py:**
- `RESULTS_TRUNCATED`: Limit applied to result set
- `FUZZY_MATCH`: No exact matches, returning fuzzy results
- `DEPRECATED_PATTERN`: Query pattern will be deprecated in future version

**evolve_report.py:**
- `ORPHANED_INSIGHTS`: Removed sections had linked insights
- `REFERENCE_BROKEN`: Removed insights had active references
- `VALIDATION_SOFT_FAIL`: Non-critical validation issues

**execute_query.py:**
- `TIMEOUT_WARNING`: Query approaching timeout limit
- `LARGE_RESULT_SET`: Result set truncated (use LIMIT clause)
- `DEPRECATED_SQL`: SQL function will be deprecated

**Testing:**
- Test case: Trigger permission error, verify `PERMISSION_DENIED` warning with context
- Test case: No warnings triggered, verify `"warnings": []` (not null, not omitted)
- Test case: Multiple warnings, verify all included in array
- Test case: Validate warning schema compliance (all required fields present)

---

## Acceptance Criteria

### Issue #67
- [ ] `evolve_report` response includes `insight_ids_removed` array
- [ ] `evolve_report` response includes `section_ids_removed` array
- [ ] Empty arrays returned when no entities removed
- [ ] Schema documentation updated
- [ ] Tests verify correct IDs returned

### Issue #68
- [ ] Audit trail JSON includes `section_ids_removed` field
- [ ] Field populated correctly when sections removed
- [ ] Empty array when no sections removed
- [ ] Audit trail remains append-only immutable
- [ ] Tests verify audit entry structure

### Issue #69
- [ ] `create_report` returns `section_ids_added` array
- [ ] `create_report` returns `insight_ids_added` array
- [ ] IDs match sections/insights in created report
- [ ] Works with all templates (default, monthly_sales, etc.)
- [ ] Works with `initial_sections` parameter
- [ ] Schema updated, tests pass

### Issue #71
- [ ] All 4 catalog/health tools accept optional `request_id` parameter
- [ ] Auto-generated UUID if not provided
- [ ] Response includes `request_id` field
- [ ] Logs include request_id for correlation
- [ ] Schema updated for all tools
- [ ] Tests verify correlation across multiple calls

### Issue #70
- [ ] All 4 catalog/health tools include `timing` object in response
- [ ] `timing.total_duration_ms` present and accurate
- [ ] Complex tools (build_catalog) include operation breakdown
- [ ] All durations are positive numbers
- [ ] Schema updated for all tools
- [ ] Tests verify timing accuracy

### Issue #73
- [ ] `warnings` field added to 4 candidate tools
- [ ] Structured warning format (code, message, severity, context)
- [ ] Empty array `[]` when no warnings (not null, not omitted)
- [ ] Warning codes implemented per tool
- [ ] Schema updated with warning structure
- [ ] Tests verify warning triggering and structure

## Dependencies and Conflicts

### Dependencies
- **#68 depends on #67**: Audit trail uses same `section_ids_removed` variable
- **#70 depends on #71**: Both modify same tool signatures (combine changes)
- **#73 uses same pattern as #70/#71**: Response structure additions

### Potential Conflicts
- **Response size**: Adding timing/warnings/request_id increases payload size by ~100-200 bytes per response
  - **Mitigation**: Acceptable overhead, modern systems handle easily

- **Backward compatibility**: Existing clients may not expect new fields
  - **Mitigation**: Additive changes only, version bump to 0.3.3 (not 0.4.0)

- **Test maintenance**: 6 issues × 3-5 tests each = ~25 new tests
  - **Mitigation**: Share test utilities for common patterns (timing validation, request_id correlation)

## Implementation Order

**Phase 1: Foundation (Issues #71, #70)**
1. Add `request_id` and `timing` to all 4 catalog/health tools
2. Update schemas
3. Add tests for request_id correlation and timing accuracy

**Phase 2: Report Tools (Issues #67, #68, #69)**
4. Add removed IDs to `evolve_report` response (#67)
5. Add `section_ids_removed` to audit trail (#68)
6. Add created IDs to `create_report` response (#69)
7. Update schemas and tests

**Phase 3: Warnings (Issue #73)**
8. Implement warning structure and codes
9. Add warnings to 4 candidate tools
10. Update schemas and tests

**Rationale:**
- Phase 1 establishes consistent metadata pattern across simpler tools
- Phase 2 applies to complex report tools with dependencies
- Phase 3 adds warnings after base functionality proven

## Testing Strategy

### Unit Tests (per issue)
- **#67**: Test insight/section removal ID tracking (3 tests)
- **#68**: Test audit trail structure (2 tests)
- **#69**: Test created ID tracking with templates and initial_sections (4 tests)
- **#71**: Test request_id generation and correlation (3 tests per tool = 12 tests)
- **#70**: Test timing accuracy and breakdown (2 tests per tool = 8 tests)
- **#73**: Test warning triggering and structure (3 tests per tool = 12 tests)

**Total new tests: ~44**

### Integration Tests
- Multi-step workflow with request_id correlation across 3 tools
- Create report with initial_sections, verify IDs match outline
- Evolve report with removals, verify audit trail and response match
- Trigger warnings in build_catalog, verify structured format

### Regression Tests
- All existing tests must pass (verify additive changes don't break existing behavior)
- Response schema validation (Pydantic models enforce structure)

## Risks and Mitigations

### Risk 1: Performance Impact
**Risk:** Adding timing measurement overhead to hot paths
**Likelihood:** Low
**Impact:** Low (microseconds per call)
**Mitigation:** Use `time.time()` (fastest timer), measure overhead in benchmarks

### Risk 2: Test Coverage Gaps
**Risk:** 44 new tests may miss edge cases
**Likelihood:** Medium
**Impact:** Medium
**Mitigation:**
- Use property-based testing (Hypothesis) for ID tracking
- Add integration tests for multi-step workflows
- Manual QA for warning triggers

### Risk 3: Merge Conflicts
**Risk:** 6 parallel implementations may conflict
**Likelihood:** Medium (4 tools modified by multiple issues)
**Impact:** Low (git merge can resolve)
**Mitigation:**
- Follow implementation order (Phase 1 → 2 → 3)
- Coordinate file ownership (assign tools to specific implementers)
- Use feature branch per issue, merge to v0.3.3

### Risk 4: Schema Drift
**Risk:** Manual schema updates may diverge from implementation
**Likelihood:** Low (Pydantic auto-generates schemas)
**Impact:** Medium (MCP clients rely on accurate schemas)
**Mitigation:**
- Validate schemas in CI (JSON Schema validation)
- Generate schema documentation from Pydantic models
- Add schema regression tests

## References

### Research Findings
- **Best Practices Document:** `API_RESPONSE_BEST_PRACTICES.md`
- **MCP Protocol:** JSON-RPC 2.0, ContentBlock format
- **FastMCP Patterns:** ToolResult, structured content
- **Audit Trail Standards:** 5 W's + How (Who/What/When/Where/Why/How)
- **Response Symmetry Principle:** "If you add X, also return X"

### Related Issues
- #91: Custom dune data loaders (future work)
- #87: Add `removed_insight_ids` to evolve_report (DUPLICATE of #67)
- #72: Enable request_id correlation (related to #71)

### Code Locations
- MCP Tools: `src/igloo_mcp/mcp/tools/`
- Report Service: `src/igloo_mcp/living_reports/service.py`
- Base Tool: `src/igloo_mcp/mcp/tools/base.py` (contains `ensure_request_id()`)
- Tests: `tests/mcp/tools/`, `tests/living_reports/`

---

**Plan Prepared:** 2025-11-28
**Target Version:** 0.3.3
**Estimated Effort:** 6 issues × 2-4 hours = 12-24 hours (parallelizable to 4-6 hours with 4 engineers)
