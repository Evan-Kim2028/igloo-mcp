---
status: pending
priority: p3
issue_id: "004"
tags: [code-review, simplification, technical-debt, dry]
dependencies: []
---

# Consolidate Duplicate Result Mode Hint Generation

## Problem Statement

The `_apply_result_mode()` function contains duplicated hint generation logic for SAMPLE and SUMMARY modes, violating the DRY (Don't Repeat Yourself) principle.

**Location:** `src/igloo_mcp/mcp/tools/execute_query.py:217-250`

**Why it matters:**
- Code duplication makes maintenance harder
- Identical logic in 2+ places increases bug risk
- Adding new modes requires duplicating hint logic
- ~15 LOC of unnecessary duplication

## Findings

### Current Implementation
```python
if mode == RESULT_MODE_SAMPLE:
    sample_rows = rows[:RESULT_MODE_SAMPLE_SIZE]
    result["rows"] = sample_rows

    # Generate helpful hint based on whether all rows fit in sample
    if rowcount <= RESULT_MODE_SAMPLE_SIZE:
        hint = f"All {rowcount} rows returned" if rowcount > 0 else None
    else:
        hint = f"Showing first {RESULT_MODE_SAMPLE_SIZE} of {rowcount} rows. Use result_mode='full' to retrieve all rows"

if mode == RESULT_MODE_SUMMARY:
    sample_rows = rows[:RESULT_MODE_SUMMARY_SAMPLE_SIZE]
    result["rows"] = sample_rows

    # Same logic duplicated
    if rowcount <= RESULT_MODE_SUMMARY_SAMPLE_SIZE:
        hint = f"All {rowcount} rows returned" if rowcount > 0 else None
    else:
        hint = f"Showing first {RESULT_MODE_SUMMARY_SAMPLE_SIZE} of {rowcount} rows. Use result_mode='full' to retrieve all rows"
```

### Issues
1. **Duplication:** Same hint logic appears twice
2. **Maintenance:** Changing hint format requires updating multiple places
3. **Extensibility:** Adding new modes requires copy-pasting hint logic
4. **Cognitive load:** Readers must verify both blocks are identical

## Proposed Solutions

### Option 1: Extract Hint Builder Function (RECOMMENDED)
**Effort:** Small (15 minutes)
**Risk:** Very Low
**Impact:** Medium (improves maintainability)

```python
def _build_hint(rowcount: int, sample_size: int) -> Optional[str]:
    """Build helpful hint for result mode."""
    if rowcount == 0:
        return None
    if rowcount <= sample_size:
        return f"All {rowcount} rows returned"
    return f"Showing first {sample_size} of {rowcount} rows. Use result_mode='full' to retrieve all rows"

def _apply_result_mode(result: Dict[str, Any], mode: str) -> Dict[str, Any]:
    # ...

    if mode == RESULT_MODE_SAMPLE:
        result["rows"] = rows[:RESULT_MODE_SAMPLE_SIZE]
        result["result_mode_info"] = {
            "mode": "sample",
            "total_rows": rowcount,
            "rows_returned": len(result["rows"]),
            "sample_size": RESULT_MODE_SAMPLE_SIZE,
            "hint": _build_hint(rowcount, RESULT_MODE_SAMPLE_SIZE),
        }

    if mode == RESULT_MODE_SUMMARY:
        result["rows"] = rows[:RESULT_MODE_SUMMARY_SAMPLE_SIZE]
        result["result_mode_info"] = {
            "mode": "summary",
            "total_rows": rowcount,
            "rows_returned": len(result["rows"]),
            "sample_size": RESULT_MODE_SUMMARY_SAMPLE_SIZE,
            "hint": _build_hint(rowcount, RESULT_MODE_SUMMARY_SAMPLE_SIZE),
        }
```

**Pros:**
- Eliminates duplication (-15 LOC)
- Single source of truth for hint logic
- Easier to add new modes
- Easier to change hint format

**Cons:**
- Adds one more function (minor)

### Option 2: Use Dispatch Table
**Effort:** Medium (30 minutes)
**Risk:** Low
**Impact:** High (more extensive refactoring)

```python
RESULT_MODE_CONFIGS = {
    RESULT_MODE_SAMPLE: {"sample_size": RESULT_MODE_SAMPLE_SIZE},
    RESULT_MODE_SUMMARY: {"sample_size": RESULT_MODE_SUMMARY_SAMPLE_SIZE},
}

def _apply_result_mode(result: Dict[str, Any], mode: str) -> Dict[str, Any]:
    if mode == RESULT_MODE_FULL:
        return result

    config = RESULT_MODE_CONFIGS.get(mode)
    if not config:
        return result

    sample_size = config["sample_size"]
    result["rows"] = rows[:sample_size]
    result["result_mode_info"] = {
        "mode": mode,
        "total_rows": rowcount,
        "rows_returned": len(result["rows"]),
        "hint": _build_hint(rowcount, sample_size),
    }
    return result
```

**Pros:**
- Even more consolidation (-20 LOC)
- Very easy to add new modes (just add to config dict)
- Clear configuration structure

**Cons:**
- Larger refactoring
- May be overkill for 2 modes

### Option 3: Keep Current Duplication
**Effort:** None
**Risk:** Low
**Impact:** None

Acknowledge duplication but keep for explicitness.

**Pros:**
- No changes needed
- Each mode is self-contained

**Cons:**
- Ongoing maintenance burden
- Violates DRY principle

## Recommended Action

**Use Option 1: Extract _build_hint() function**

This is a simple refactoring that eliminates duplication without over-engineering. If more result modes are added in the future, can consider upgrading to Option 2 (dispatch table).

## Technical Details

**Affected Files:**
- `src/igloo_mcp/mcp/tools/execute_query.py` (lines 217-250)

**Affected Components:**
- Result mode filtering
- Hint generation

**Database Changes:** None

**Breaking Changes:** None (output identical)

## Acceptance Criteria

- [ ] Extract `_build_hint()` helper function
- [ ] Update SAMPLE mode to use helper
- [ ] Update SUMMARY mode to use helper
- [ ] Verify hint text is identical before/after
- [ ] Run all result mode tests
- [ ] Confirm no behavioral changes

## Work Log

### 2025-11-30 - Minor Finding
- **Action:** Simplicity review identified code duplication
- **Severity:** P3 (nice-to-have improvement)
- **Impact:** Improves maintainability, no functional changes
- **Next Step:** Implement in follow-up PR after merge

## Resources

- **Related Issues:** None
- **Documentation:** Result modes documented in execute_query.md
- **Similar Patterns:** DRY principle, extract method refactoring
- **Test Coverage:** `tests/test_execute_query_result_modes.py`
