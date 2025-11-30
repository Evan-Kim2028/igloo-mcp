---
status: pending
priority: p2
issue_id: "001"
tags: [code-review, security, simplification, technical-debt]
dependencies: []
---

# Replace Manual HTML Escaping with Standard Library

## Problem Statement

The `HTMLStandaloneRenderer` class implements manual HTML escaping that reinvents the wheel and could introduce security issues if the order of operations is incorrect.

**Location:** `src/igloo_mcp/living_reports/renderers/html_standalone.py:647-664`

**Why it matters:**
- Security risk: Manual escaping is error-prone (must escape `&` first)
- Maintenance burden: Duplicates standard library functionality
- Code quality: Unnecessary code that could be replaced with battle-tested stdlib

## Findings

### Current Implementation
```python
def _escape_html(self, text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
```

### Issues Identified
1. **Reinventing the wheel** - Python's `html.escape()` exists for this purpose
2. **Order dependency** - Must escape `&` first (currently correct, but fragile)
3. **Maintenance cost** - 9 lines that could be 1 line
4. **Test coverage requirement** - Custom implementation needs its own tests

## Proposed Solutions

### Option 1: Use Standard Library (RECOMMENDED)
**Effort:** Small (15 minutes)
**Risk:** Very Low
**Impact:** High (removes custom code, improves security)

```python
from html import escape

def _escape_html(self, text: str) -> str:
    """Escape HTML special characters using stdlib."""
    return escape(text) if text else ""
```

**Pros:**
- Battle-tested implementation
- -9 LOC reduction
- No order dependency concerns
- Better security guarantees

**Cons:**
- None

### Option 2: Keep Current Implementation
**Effort:** None
**Risk:** Low
**Impact:** None

Keep manual escaping as-is with added documentation about order dependency.

**Pros:**
- No changes needed
- Explicit control over escaping

**Cons:**
- Ongoing maintenance burden
- Potential security issues if modified incorrectly
- Unnecessary code duplication

## Recommended Action

**Use Option 1: Replace with `html.escape()`**

This is a straightforward refactoring that improves code quality, reduces maintenance burden, and leverages battle-tested standard library code.

## Technical Details

**Affected Files:**
- `src/igloo_mcp/living_reports/renderers/html_standalone.py` (lines 647-664)
- Imports section (add `from html import escape`)

**Affected Components:**
- HTML renderer
- All methods calling `_escape_html()` (transparent change)

**Database Changes:** None

**Breaking Changes:** None (output remains identical)

## Acceptance Criteria

- [ ] Import `html.escape` from standard library
- [ ] Replace `_escape_html` implementation with stdlib version
- [ ] Verify all existing tests still pass
- [ ] Manually verify HTML output is identical for test reports
- [ ] Confirm XSS protection tests still pass (`test_escape_html_special_chars`)

## Work Log

### 2025-11-30 - Initial Finding
- **Action:** Code review identified manual HTML escaping as unnecessary
- **Finding:** Standard library provides equivalent functionality
- **Severity:** P2 (should fix, but not blocking merge)
- **Next Step:** Implement replacement after merge approval

## Resources

- **Related Issues:** None
- **Documentation:** https://docs.python.org/3/library/html.html#html.escape
- **Similar Patterns:** This is a common simplification in HTML renderers
- **Test Coverage:** `tests/test_html_standalone_renderer.py:405-415`
