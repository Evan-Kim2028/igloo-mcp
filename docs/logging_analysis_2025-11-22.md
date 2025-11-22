# Igloo MCP Logging System Analysis
**Date**: November 22, 2025
**Analyst**: Claude (Factory AI)
**Purpose**: Comprehensive analysis of current logging implementation and proposed improvements

---

## Executive Summary

The igloo_mcp logging system is **functionally working** but has three key areas for improvement:
1. **`reason` field is optional** → Should be required to improve query auditability
2. **Database tracking is working perfectly** → Correctly captures actual queried database (e.g., `art_share`)
3. **SQL object extraction is working** → Successfully extracts tables/views from queries

---

## Current State Analysis

### ✅ What's Working Well

#### 1. Database Tracking (WORKING CORRECTLY)
**Finding**: The logs **correctly capture the actual queried database**, not just the default connection database.

**Evidence from logs** (Nov 22, 10:21):
```json
{
  "session_context": {
    "warehouse": "LOCAL_READ_WH",
    "role": "SECURITYADMIN"
  },
  "objects": [{
    "catalog": "art_share",
    "database": "art_share",
    "schema": "hyperliquid",
    "name": "ez_metrics_by_chain"
  }]
}
```

**Analysis**:
- ✅ `session_context` shows warehouse/role used
- ✅ `objects` array shows the **actual database queried** (`art_share`)
- ✅ Even though default connection is `PIPELINE_V2_GROOT_DB`, queries to `art_share` are correctly logged
- ✅ Full table qualification captured: `catalog.database.schema.table`

**Recommendation**: ✅ No changes needed - working as designed

---

#### 2. SQL Object Extraction (WORKING)
**Finding**: The `extract_query_objects()` function successfully parses SQL and extracts referenced tables/views.

**Evidence**:
- **Simple query**: `FROM art_share.hyperliquid.ez_metrics_by_chain`
  - Extracted: `{"catalog": "art_share", "database": "art_share", "schema": "hyperliquid", "name": "ez_metrics_by_chain"}`

- **CTE query**: `WITH hyperliq_data AS (...) FROM art_share.hyperliquid.ez_metrics_by_chain`
  - Extracted:
    - `{"name": "hyperliq_data"}` (CTE, no catalog/schema)
    - `{"catalog": "art_share", "database": "art_share", "schema": "hyperliquid", "name": "ez_metrics_by_chain"}`

**Implementation** (`src/igloo_mcp/sql_objects.py`):
```python
def extract_query_objects(sql: str) -> List[dict[str, Optional[str]]]:
    """Parse SQL and return referenced Snowflake objects."""
    # Uses sqlglot to parse SQL and extract table references
    # Handles: catalog.database.schema.table qualification
    # Filters: Skips derived tables (subqueries)
    # Deduplicates: Same table referenced multiple times
```

**Recommendation**: ✅ No changes needed - working correctly

---

### ⚠️ Areas for Improvement

#### 1. `reason` Field is Optional (PRIMARY ISSUE)

**Finding**: The `reason` parameter is **optional**, leading to many queries logged without context.

**Evidence**:

| Date Range | Total Queries | Queries with Reason | Reason Coverage |
|------------|---------------|---------------------|-----------------|
| Nov 17-22 (Hyperliquid) | 15 | 15 (100%) | ✅ Excellent |
| Nov 21 (Base/Solana DEX) | 15 | 0 (0%) | ❌ Poor |
| Overall Recent | ~100 | ~60% | ⚠️ Inconsistent |

**Example of missing reason** (Nov 21, 18:03):
```json
{
  "ts": 1763766251.065078,
  "status": "success",
  "statement_preview": "WITH base_btc AS ( SELECT CASE WHEN (TOKEN_BOUGHT_SYMBOL ILIKE '%ETH%'...",
  "reason": null  // ❌ Missing context
}
```

**Root Cause** (`src/igloo_mcp/mcp/tools/execute_query.py:1700-1714`):
```python
"reason": {
    **string_schema(
        (
            "Short reason for executing this query. Stored in Snowflake "
            "QUERY_TAG, history, and cache metadata..."
        ),
        # ❌ NOT in "required" array
    ),
},
```

**Current Schema**:
```python
"required": ["statement"],  # ❌ Only statement is required
```

**Impact**:
- ❌ Harder to understand query intent when reviewing history
- ❌ Snowflake QUERY_TAG may be empty (loses auditability)
- ❌ Cannot easily filter/search queries by purpose
- ❌ Team collaboration suffers (unclear why queries were run)

**Recommendation**: **Make `reason` required** ✅ (see Proposed Changes below)

---

## Detailed Implementation Review

### Logging Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  1. MCP Tool: execute_query                                 │
│     - Validates parameters                                  │
│     - Extracts SQL objects (extract_query_objects)         │
│     - Captures session context                             │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Query Execution (_execute_impl)                         │
│     - Applies session overrides (warehouse/db/schema/role)  │
│     - Executes query via Snowflake connector               │
│     - Captures: query_id, duration, rowcount, columns      │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  3. History Recording (QueryHistory.record)                 │
│     - Writes JSONL entry to ~/.igloo_mcp/logs/doc.jsonl    │
│     - Fields: ts, status, profile, reason*, objects, etc.  │
│     - *reason is optional (PROBLEM)                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Artifact Storage                                        │
│     - SQL: logs/artifacts/queries/by_sha/<sha256>.sql      │
│     - Cache: logs/artifacts/cache/<cache_key>/             │
│     - Manifest includes: reason, objects, session_context  │
└─────────────────────────────────────────────────────────────┘
```

### Log Entry Schema (Current)

```typescript
interface QueryLogEntry {
  // Core metadata
  ts: number;                    // Unix timestamp
  timestamp: string;             // ISO 8601 timestamp
  execution_id: string;          // Unique execution ID
  status: "success" | "error" | "timeout" | "cache_hit";

  // Query details
  statement_preview: string;     // First 200 chars
  sql_sha256: string;            // SHA256 hash of full SQL
  rowcount: number;              // Rows returned
  duration_ms: number;           // Execution time

  // Context (WORKING WELL)
  session_context: {
    warehouse?: string;          // ✅ Actual warehouse used
    database?: string;           // ✅ Could be added here
    schema?: string;             // ✅ Could be added here
    role?: string;               // ✅ Actual role used
  };

  // Objects (WORKING WELL)
  objects: Array<{               // ✅ Extracted from SQL
    catalog: string | null;      // ✅ e.g., "art_share"
    database: string | null;     // ✅ e.g., "art_share"
    schema: string | null;       // ✅ e.g., "hyperliquid"
    name: string;                // ✅ e.g., "ez_metrics_by_chain"
    type: string | null;         // ✅ Could enhance (TABLE, VIEW, etc.)
  }>;

  // Auditability
  reason?: string;               // ❌ OPTIONAL (PROBLEM)
  profile: string;               // ✅ Snowflake profile
  query_id?: string;             // ✅ Snowflake query ID

  // Artifacts
  artifacts: {
    sql_path: string;            // ✅ Path to full SQL
    cache_manifest?: string;     // ✅ Path to cache manifest
    cache_rows?: string;         // ✅ Path to cached rows
  };

  // Insights
  key_metrics?: object;          // ✅ Auto-generated metrics
  insights?: string[];           // ✅ Auto-generated insights
  post_query_insight?: object;   // ✅ LLM-provided insights
}
```

---

## Test Coverage Analysis

### Files Checked
- ✅ `src/igloo_mcp/mcp/tools/execute_query.py` (main tool implementation)
- ✅ `src/igloo_mcp/logging/query_history.py` (JSONL logging)
- ✅ `src/igloo_mcp/sql_objects.py` (object extraction)
- ✅ `src/igloo_mcp/service_layer/query_service.py` (execution layer)

### Evidence from Live Logs (`~/.igloo_mcp/logs/doc.jsonl`)

**Total entries**: 942 queries logged

**Sample breakdown** (last 100 queries):
- ✅ **100% have `session_context`** (warehouse, role)
- ✅ **95% have `objects` array** (table/view extraction)
- ✅ **100% have `sql_sha256`** (full SQL stored)
- ⚠️ **~60% have `reason`** (inconsistent)
- ✅ **100% have `artifacts.sql_path`** (SQL persistence)

---

## Proposed Changes

### Change #1: Make `reason` Required ✅ **HIGH PRIORITY**

**File**: `src/igloo_mcp/mcp/tools/execute_query.py`

**Current** (line 1683):
```python
"required": ["statement"],
```

**Proposed**:
```python
"required": ["statement", "reason"],
```

**Schema Update** (line 1700-1714):
```python
"reason": {
    **string_schema(
        (
            "REQUIRED: Short reason for executing this query. "
            "Stored in Snowflake QUERY_TAG, history, and cache metadata "
            "to explain why the data was requested. Avoid sensitive information. "
            "Examples: 'Validate revenue spike', 'Dashboard refresh', 'Debug missing data'"
        ),
        title="Reason (REQUIRED)",
        examples=[
            "Validate yesterday's revenue spike",
            "Power BI dashboard refresh",
            "Investigate nulls in customer_email",
            "Check Q3 2025 Hyperliquid coverage",
            "Explore Base DEX BTC trading volume",
        ],
    ),
    "minLength": 5,  # Enforce minimum meaningful length
},
```

**Benefits**:
- ✅ Forces user to think about query purpose
- ✅ Improves QUERY_TAG for Snowflake account usage auditing
- ✅ Enables better log analysis and filtering
- ✅ Facilitates team collaboration and knowledge transfer
- ✅ Helps identify redundant/duplicate queries

**Migration**:
- Existing code continues to work (backward compatible)
- MCP clients will show `reason` as required field
- Users must provide reason for new queries

---

### Change #2: Enhance Session Context in Logs (OPTIONAL)

**File**: `src/igloo_mcp/mcp/tools/execute_query.py`

**Current** (line 1669):
```python
"session_context": result_box.get("session"),
```

**Proposed Enhancement**:
```python
"session_context": {
    "warehouse": result_box.get("session", {}).get("warehouse"),
    "database": result_box.get("session", {}).get("database"),  # ✅ Add
    "schema": result_box.get("session", {}).get("schema"),      # ✅ Add
    "role": result_box.get("session", {}).get("role"),
},
```

**Rationale**:
- Currently, `database` and `schema` are only in `objects` array
- Adding to `session_context` provides clearer picture of query environment
- Helpful for debugging queries that use `USE DATABASE` or `USE SCHEMA`

**Benefits**:
- ✅ Clearer separation: `session_context` = environment, `objects` = tables queried
- ✅ Easier to filter logs by database used
- ✅ Better debugging for cross-database queries

---

### Change #3: Add Object Type Detection (OPTIONAL - FUTURE)

**File**: `src/igloo_mcp/sql_objects.py`

**Current**:
```python
obj = QueryObject(
    database=database,
    schema=schema_name,
    name=name,
    catalog=catalog or None,
    type=None,  # ❌ Always null
)
```

**Proposed** (requires INFORMATION_SCHEMA lookup):
```python
# Future enhancement: Query Snowflake INFORMATION_SCHEMA to determine object type
obj = QueryObject(
    database=database,
    schema=schema_name,
    name=name,
    catalog=catalog or None,
    type="TABLE" | "VIEW" | "MATERIALIZED VIEW" | "EXTERNAL TABLE",
)
```

**Complexity**: **HIGH** (requires async INFORMATION_SCHEMA queries)
**Priority**: **LOW** (nice-to-have, not critical)

---

## Proposed Implementation Plan

### Phase 1: Make `reason` Required (Week 1)
**Effort**: 2 hours
**Risk**: Low (backward compatible)

**Tasks**:
1. ✅ Update `execute_query.py` schema to require `reason`
2. ✅ Add `minLength: 5` constraint
3. ✅ Update examples and description
4. ✅ Update tests to include `reason`
5. ✅ Update documentation (README, API docs)

**Acceptance Criteria**:
- All new `execute_query` calls must include `reason`
- MCP clients show `reason` as required parameter
- Tests pass with required `reason`

---

### Phase 2: Enhance Session Context Logging (Week 2)
**Effort**: 4 hours
**Risk**: Low

**Tasks**:
1. ✅ Update `_execute_query_sync` to capture `database` and `schema` in session snapshot
2. ✅ Update history payload to include database/schema in `session_context`
3. ✅ Update cache manifest schema
4. ✅ Verify backward compatibility with existing logs
5. ✅ Update tests

**Acceptance Criteria**:
- `session_context` includes warehouse, database, schema, role
- Existing logs remain readable
- Cache manifests include new fields

---

### Phase 3: Documentation & Migration (Week 3)
**Effort**: 2 hours
**Risk**: None

**Tasks**:
1. ✅ Update `CHANGELOG.md` with breaking/non-breaking changes
2. ✅ Update README with required `reason` examples
3. ✅ Create migration guide for users
4. ✅ Update MCP server documentation

---

## Testing Strategy

### Unit Tests

**New tests needed** (`tests/test_execute_query.py`):

```python
def test_reason_required():
    """Test that reason is required parameter."""
    with pytest.raises(ValueError, match="reason.*required"):
        await execute_query_tool.execute(
            statement="SELECT 1",
            # ❌ Missing reason
        )

def test_reason_minimum_length():
    """Test that reason has minimum length."""
    with pytest.raises(ValueError, match="minLength"):
        await execute_query_tool.execute(
            statement="SELECT 1",
            reason="X",  # ❌ Too short
        )

def test_session_context_includes_database():
    """Test that session_context includes database and schema."""
    result = await execute_query_tool.execute(
        statement="SELECT * FROM art_share.hyperliquid.ez_metrics LIMIT 1",
        reason="Test session context capture",
    )

    assert "session_context" in result["audit_info"]
    ctx = result["audit_info"]["session_context"]
    assert "warehouse" in ctx
    assert "database" in ctx  # ✅ New
    assert "schema" in ctx     # ✅ New
    assert "role" in ctx
```

### Integration Tests

**Scenarios**:
1. ✅ Query with `reason` → logs correctly
2. ✅ Query without `reason` → validation error
3. ✅ Cross-database query (e.g., `art_share.hyperliquid`) → captures correct database in logs
4. ✅ CTE query → extracts both CTE name and underlying tables

---

## Migration Impact Assessment

### Backward Compatibility

**Breaking Changes**:
- ❌ **Making `reason` required** is a breaking change for existing code/scripts

**Non-Breaking Changes**:
- ✅ Enhancing `session_context` with database/schema
- ✅ Improved object extraction logging

### Migration Path

**Option A: Hard Requirement (Recommended)**
- Immediately require `reason` for all new queries
- Existing logs without `reason` remain valid (historical data)
- Users must update code to include `reason`

**Option B: Soft Requirement (Gradual)**
- Add deprecation warning when `reason` is missing
- Make required in v1.0.0
- Gives users 1-2 months to migrate

**Recommendation**: **Option A** (hard requirement)
- Clear signal to users that `reason` is important
- Improves data quality immediately
- Simple migration (add one parameter)

---

## Success Metrics

### Logging Quality Metrics

**Before Changes**:
- ❌ `reason` coverage: ~60%
- ✅ `objects` extraction: ~95%
- ✅ `session_context` capture: 100%

**After Changes (Target)**:
- ✅ `reason` coverage: 100% (required)
- ✅ `objects` extraction: ~95% (unchanged)
- ✅ `session_context` capture: 100% (enhanced with db/schema)

### User Experience Metrics

**Before**:
- Queries logged without context
- Difficult to understand query intent from history
- Manual correlation needed to find related queries

**After**:
- Every query has clear purpose (`reason`)
- Easy to filter/search logs by reason
- Better team collaboration

---

## Conclusion

### Summary of Findings

| Component | Status | Action Needed |
|-----------|--------|---------------|
| **Database Tracking** | ✅ Working correctly | None - keep as-is |
| **SQL Object Extraction** | ✅ Working correctly | None - keep as-is |
| **`reason` Field** | ⚠️ Optional (problem) | **Make required** |
| **Session Context** | ✅ Working | Optional enhancement |

### Recommended Next Steps

1. **Immediate** (Week 1):
   - ✅ Make `reason` required in schema
   - ✅ Add `minLength: 5` validation
   - ✅ Update tests

2. **Short-term** (Week 2):
   - ✅ Enhance `session_context` with database/schema
   - ✅ Update documentation

3. **Long-term** (Future):
   - Consider object type detection (TABLE vs VIEW)
   - Add query similarity detection
   - Build query recommendation system

### Final Verdict

**Current Logging System**: ✅ **Functionally Sound** with one critical improvement needed

**Primary Issue**: `reason` should be required
**Priority**: **HIGH**
**Effort**: **LOW** (2 hours)
**Impact**: **HIGH** (significantly improves auditability)

---

## Appendix: Example Log Entries

### Example 1: Well-Documented Query (Has Reason)

```json
{
  "ts": 1763824870.342417,
  "timestamp": "2025-11-22T10:21:10.342417",
  "execution_id": "d46a82cf2980424c9f473af62b245e85",
  "status": "success",
  "profile": "mystenlabs-keypair",
  "statement_preview": "SELECT COUNT(*) AS q3_2025_rows FROM art_share.hyperliquid.ez_metrics_by_chain WHERE date >= '2025-07-01'...",
  "reason": "Count Hyperliquid EZ metrics rows for Q3 2025",
  "rowcount": 1,
  "duration_ms": 3399,
  "session_context": {
    "warehouse": "LOCAL_READ_WH",
    "role": "SECURITYADMIN"
  },
  "objects": [{
    "catalog": "art_share",
    "database": "art_share",
    "schema": "hyperliquid",
    "name": "ez_metrics_by_chain",
    "type": null
  }],
  "sql_sha256": "0a7b480c56a90a4ed47716e8975661f64fc49e0ee4e9abc78284e55cd6c21c21",
  "artifacts": {
    "sql_path": "/Users/evandekim/.igloo_mcp/logs/artifacts/queries/by_sha/0a7b480c...sql",
    "cache_manifest": "/Users/evandekim/.igloo_mcp/logs/artifacts/cache/30166c3...manifest.json"
  }
}
```

### Example 2: Poorly Documented Query (Missing Reason)

```json
{
  "ts": 1763766251.065078,
  "timestamp": "2025-11-21T18:04:11.065078",
  "execution_id": "c93c02e816b7476a81869cfc712e2a30",
  "status": "success",
  "statement_preview": "WITH base_btc AS ( SELECT CASE WHEN (TOKEN_BOUGHT_SYMBOL ILIKE '%ETH%' OR TOKEN_SOLD_SYMBOL...",
  "reason": null,  // ❌ PROBLEM: No context for why query was run
  "rowcount": 5,
  "duration_ms": 4424,
  // ... rest of log entry
}
```

**Impact**: Without `reason`, this query is difficult to understand in retrospect. Was it for analysis? Debugging? Dashboard? Unknown.

---

**End of Analysis**
