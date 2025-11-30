---
status: pending
priority: p1
issue_id: "002"
tags: [code-review, data-integrity, critical, bug]
dependencies: []
---

# Fix Cache Column Derivation Data Loss

## Problem Statement

The query result cache derives column names from the first row when not provided in metadata. If the first row has NULL values or missing keys, subsequent rows with additional columns will have data silently truncated when written to CSV.

**Location:** `src/igloo_mcp/cache/query_result_cache.py:367-373`

**Why it matters:**
- **Permanent data loss** in cached CSV files
- Cache hits return incomplete data
- Violations of data consistency between JSON and CSV formats
- Silent failure (no warnings or errors)

## Findings

### Current Implementation
```python
columns = metadata.get("columns")
if not columns:
    # Derive columns from first row for CSV readability.
    column_set: List[str] = []
    if rows:
        column_set = list(rows[0].keys())
    metadata["columns"] = column_set
```

### Data Loss Scenario
```python
# First row missing 'email' column (NULL in database)
rows = [
    {"id": 1, "name": "Alice"},  # Derived columns: ["id", "name"]
    {"id": 2, "name": "Bob", "email": "bob@example.com"}  # email LOST in CSV!
]
```

**Impact:**
1. CSV writer uses incomplete column list
2. Second row's `email` field is silently dropped
3. Cache lookup returns corrupted data
4. No error or warning generated

## Proposed Solutions

### Option 1: Collect All Columns Across All Rows (RECOMMENDED)
**Effort:** Small (30 minutes)
**Risk:** Low
**Impact:** High (prevents data loss)

```python
if not columns and rows:
    # Collect ALL unique columns across ALL rows
    column_set = set()
    for row in rows:
        column_set.update(row.keys())
    metadata["columns"] = sorted(column_set)  # Deterministic ordering
```

**Pros:**
- Prevents data loss completely
- Deterministic column ordering (sorted)
- Simple implementation
- Backward compatible (more complete than before)

**Cons:**
- Requires iterating all rows (O(n * m) where n=rows, m=avg keys per row)
- For large result sets (5000+ rows), adds ~10-50ms overhead

### Option 2: Require Columns in Metadata
**Effort:** Medium (2 hours)
**Risk:** Medium
**Impact:** High

Make `columns` required in `store()` method, derive from Snowflake cursor description.

**Pros:**
- No iteration overhead
- Enforces metadata correctness
- Aligns with Snowflake cursor.description

**Cons:**
- Requires changes to all call sites
- Breaking change for any external callers

### Option 3: Add Validation Warning
**Effort:** Small (15 minutes)
**Risk:** Low
**Impact:** Low

Keep current behavior but add warning if rows have inconsistent columns.

**Pros:**
- Minimal changes
- Alerts to potential issues

**Cons:**
- Doesn't prevent data loss
- Still corrupts cache

## Recommended Action

**Use Option 1: Collect all columns across all rows**

This is the safest fix that prevents data loss with minimal performance impact. For typical query results (<1000 rows), the overhead is negligible.

**Additional Enhancement:**
Add validation to warn if column count varies across rows (indicates potential data quality issue):

```python
if not columns and rows:
    column_set = set()
    for row in rows:
        column_set.update(row.keys())
    metadata["columns"] = sorted(column_set)

    # Warn if rows have inconsistent columns (data quality check)
    if len(rows) > 1:
        first_keys = set(rows[0].keys())
        for i, row in enumerate(rows[1:], start=1):
            if set(row.keys()) != first_keys:
                logger.warning(
                    f"Inconsistent columns detected in cache rows: "
                    f"row 0 has {sorted(first_keys)}, row {i} has {sorted(row.keys())}"
                )
                break  # Only log once
```

## Technical Details

**Affected Files:**
- `src/igloo_mcp/cache/query_result_cache.py` (lines 367-373)

**Affected Components:**
- Query result caching (all queries that omit column metadata)
- CSV cache file format

**Database Changes:** None

**Breaking Changes:** None (improvement only)

## Acceptance Criteria

- [ ] Update column derivation to collect from all rows
- [ ] Add deterministic sorting of column names
- [ ] Add validation warning for inconsistent columns
- [ ] Write test case for NULL column scenario:
  ```python
  def test_cache_column_derivation_with_nulls():
      rows = [
          {"id": 1, "name": "Alice"},  # Missing email
          {"id": 2, "name": "Bob", "email": "bob@example.com"}
      ]
      cache.store("key", rows=rows, metadata={})
      hit = cache.lookup("key")
      assert "email" in hit.rows[1]  # Must not be lost
  ```
- [ ] Verify CSV round-trip preserves all columns
- [ ] Run performance benchmarks (should add <50ms for 5000 rows)

## Work Log

### 2025-11-30 - Critical Finding
- **Action:** Data integrity review identified silent data loss in cache
- **Impact:** P1 severity - can corrupt cached query results
- **Risk:** Production data loss if cache is relied upon
- **Next Step:** Implement fix before merge to main

## Resources

- **Related Issues:** #010 (cache checksum verification)
- **Documentation:** CSV writer uses DictWriter with fieldnames
- **Similar Patterns:** Pandas DataFrame column inference
- **Test Gap:** No test coverage for inconsistent row schemas
