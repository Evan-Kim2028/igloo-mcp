# Issue #2 Plan — “[bug] Union keyword blocked”

Link: https://github.com/Evan-Kim2028/igloo-mcp/issues/2

## Summary
- Report: A query using `UNION` is blocked by SQL safety with error:
  - `SQL statement type 'Union' is not permitted. Allowed types: Select, Show, Describe, Use, Insert, Update, Create, Alter`
- Impact: Legitimate read-only queries that include `UNION`/`UNION ALL` fail.
- Expectation: `UNION` should be treated as part of a `SELECT` statement and allowed when `SELECT` is allowed.

## Hypothesis (Root Cause)
- Our validation delegates to upstream `validate_sql_type` which can return `"Union"` for set-operator queries.
- Our allow-list includes `Select`, but not `Union`, so the wrapper treats it as disallowed.

## Goals
- Permit queries that include `UNION`/`UNION ALL` when `SELECT` is allowed.
- Preserve blocking of destructive operations (DELETE, DROP, TRUNCATE, etc.).
- Keep error messages precise and user-friendly.

## Non‑Goals
- Broaden allowed statements beyond the existing policy.
- Implement a full SQL parser in-house (we continue to rely on upstream classification and sqlglot for hints).

## Proposed Fix
- Post‑process upstream classification in `validate_sql_statement`:
  - Normalize `Union` → `Select` (treat as allowed if `Select` is allowed).
  - Consider similar normalization for `With` leading CTE selects if upstream classifies them separately.
- Optionally, adjust `get_sql_statement_type` to map `Union` to `Select` for consistency across diagnostics.

## Edge Cases to Cover
- UNION vs UNION ALL
- Queries starting with `WITH` (CTE) that contain UNION sets
- Parenthesized subselects with UNION
- Mixed comments/whitespace before the first token
- Multiple UNION chains

## Test Plan
- Unit tests in a new file (e.g., `tests/test_sql_union_allowlist.py`):
  - simple_union: `SELECT 1 UNION SELECT 2` → allowed
  - union_all: `SELECT 1 UNION ALL SELECT 2` → allowed
  - cte_union: `WITH a AS (...), b AS (...) SELECT ... FROM a UNION SELECT ... FROM b` → allowed
  - destructive still blocked: `DELETE FROM t` → blocked with alternatives
- Integration test path (optional): run through `execute_query` tool with safety on to ensure queries pass/fail as expected.

## Acceptance Criteria
- Queries with UNION/UNION ALL succeed when `Select` is allowed.
- No regressions in blocking destructive statements (DELETE/DROP/TRUNCATE).
- Helpful error messages remain intact for disallowed statements.

## Rollout & Risks
- Low risk; normalization is narrow in scope.
- Add a configuration toggle if needed later (not required for this bug fix).

## Tasks (TODOs)
- [ ] Implement normalization in `src/igloo_mcp/sql_validation.py`
- [ ] Add unit tests for UNION/UNION ALL scenarios
- [ ] (Optional) Add a note to README Troubleshooting about UNION fix
- [ ] Verify existing tests pass
