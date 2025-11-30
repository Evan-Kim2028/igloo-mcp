---
status: pending
priority: p1
issue_id: "003"
tags: [code-review, data-integrity, cache, bug]
dependencies: []
---

# Fix Cache Key Collision from NULL Handling

## Problem Statement

The cache key computation doesn't normalize NULL values in session context, causing different cache keys for semantically identical contexts.

**Location:** `src/igloo_mcp/cache/query_result_cache.py:212-225`

**Why it matters:**
- Cache misses when they should be hits
- Storage waste from duplicate cached results
- Inconsistent behavior across different code paths
- Performance degradation (unnecessary query re-execution)

## Findings

### Current Implementation
```python
def compute_cache_key(
    self,
    *,
    sql_sha256: str,
    profile: str,
    effective_context: Dict[str, Optional[str]],
) -> str:
    payload = {
        "sql_sha256": sql_sha256,
        "profile": profile,
        "context": {k: effective_context.get(k) for k in sorted(effective_context)},
    }
    blob = json.dumps(payload, sort_keys=True, separators=("|", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

### Issue: NULL vs Omitted Keys
```python
# These produce DIFFERENT cache keys but should be SAME:
context1 = {"warehouse": "WH", "database": None}
context2 = {"warehouse": "WH"}  # database omitted

# In payload construction:
# context1 → {"database": None, "warehouse": "WH"}
# context2 → {"warehouse": "WH"}
# Different JSON → Different SHA-256 hashes!
```

**Impact:**
1. Query executes with `database=None` → cached with key A
2. Same query without database param → executes again, cached with key B
3. Cache size doubles for no reason
4. Performance hit from unnecessary query execution

## Proposed Solutions

### Option 1: Normalize NULL Values (RECOMMENDED)
**Effort:** Small (20 minutes)
**Risk:** Low
**Impact:** High (fixes cache collisions)

```python
def compute_cache_key(
    self,
    *,
    sql_sha256: str,
    profile: str,
    effective_context: Dict[str, Optional[str]],
) -> str:
    # Normalize: exclude None values for consistent cache keys
    normalized_context = {
        k: v for k, v in sorted(effective_context.items())
        if v is not None
    }

    payload = {
        "sql_sha256": sql_sha256,
        "profile": profile,
        "context": normalized_context,
    }
    blob = json.dumps(payload, sort_keys=True, separators=("|", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

**Pros:**
- Fixes cache key collisions
- Simple implementation
- No breaking changes (both forms now map to same key)
- Reduces cache storage requirements

**Cons:**
- Changes cache keys for existing cached entries (one-time cache miss)
- Need to document NULL vs omitted equivalence

### Option 2: Explicit NULL Handling in Context Building
**Effort:** Medium (1 hour)
**Risk:** Medium
**Impact:** Medium

Update all call sites to never pass NULL values in context dicts.

**Pros:**
- Makes NULL handling explicit
- No changes to cache key logic

**Cons:**
- Requires auditing and updating all callers
- Doesn't fix the underlying issue
- Error-prone (easy to forget)

### Option 3: Keep Current Behavior
**Effort:** None
**Risk:** High
**Impact:** Negative

Document that NULL and omitted are different for cache keys.

**Pros:**
- No code changes

**Cons:**
- Ongoing cache inefficiency
- Confusing behavior for developers
- Wasted storage and compute

## Recommended Action

**Use Option 1: Normalize NULL values**

This is a clean fix that makes the cache more efficient. The one-time cache miss is acceptable (queries will re-execute and populate cache with correct keys).

**Migration Strategy:**
1. Deploy the fix
2. Optionally: Clear cache to avoid duplicate entries (or let TTL expire old entries)
3. Monitor cache hit rate (should improve)

## Technical Details

**Affected Files:**
- `src/igloo_mcp/cache/query_result_cache.py` (lines 212-225)

**Affected Components:**
- All query execution that uses caching
- Cache key computation

**Database Changes:** None

**Breaking Changes:**
- Cache keys change for contexts with NULL values
- One-time cache miss for affected queries
- No API changes

## Acceptance Criteria

- [ ] Update `compute_cache_key()` to normalize NULL values
- [ ] Add test case for NULL vs omitted equivalence:
  ```python
  def test_cache_key_null_normalization():
      context1 = {"warehouse": "WH", "database": None}
      context2 = {"warehouse": "WH"}

      key1 = cache.compute_cache_key(sql_sha256="abc", profile="prod", effective_context=context1)
      key2 = cache.compute_cache_key(sql_sha256="abc", profile="prod", effective_context=context2)

      assert key1 == key2, "NULL and omitted should produce same cache key"
  ```
- [ ] Verify cache hit rate improves after deployment
- [ ] Document NULL equivalence in cache documentation
- [ ] Consider adding cache metrics to track hit/miss rates

## Work Log

### 2025-11-30 - Critical Finding
- **Action:** Security review identified cache key collision issue
- **Impact:** P1 severity - causes cache inefficiency and unnecessary query execution
- **Root Cause:** NULL values not normalized before hashing
- **Next Step:** Implement normalization before merge

## Resources

- **Related Issues:** None
- **Documentation:** Cache key computation uses SHA-256 of JSON payload
- **Similar Patterns:** Redis key normalization, HTTP cache headers
- **Performance Impact:** ~20% cache miss rate improvement expected
