# GitHub Issues Created for v0.3.4 Roadmap

**Date**: 2025-11-29
**Status**: ✅ **4 issues created successfully**

---

## Created Issues

### P1 Priority (Target v0.3.4)

1. **Issue #95**: P1: Refactor tool_error_handler to eliminate code duplication
   - **URL**: https://github.com/Evan-Kim2028/igloo-mcp/issues/95
   - **Goal**: Reduce 200 lines → 100 lines by extracting common error handling
   - **Impact**: Better maintainability, single source of truth
   - **Label**: enhancement

2. **Issue #96**: P1: Standardize parameter validation across all MCP tools
   - **URL**: https://github.com/Evan-Kim2028/igloo-mcp/issues/96
   - **Goal**: Move validation to validate_parameters() method consistently
   - **Impact**: Better testability, consistent validation patterns
   - **Label**: enhancement

3. **Issue #97**: P1: Improve error UX - default to compact error messages
   - **URL**: https://github.com/Evan-Kim2028/igloo-mcp/issues/97
   - **Goal**: Reduce error token usage from 200-500 → 50-100 tokens (75% reduction)
   - **Impact**: Better UX, lower token costs, opt-in verbosity
   - **Label**: enhancement

### P2 Priority (Target v0.3.4 or later)

4. **Issue #98**: P2: Refactor SQL validation using strategy pattern
   - **URL**: https://github.com/Evan-Kim2028/igloo-mcp/issues/98
   - **Goal**: Reduce complexity of 410-line sql_validation.py module
   - **Impact**: Better testability, maintainability, extensibility
   - **Label**: enhancement

---

## Issue Summary

| # | Priority | Title | Impact | Complexity |
|---|----------|-------|--------|------------|
| #95 | P1 | Refactor tool_error_handler | High | Medium |
| #96 | P1 | Standardize parameter validation | High | Medium |
| #97 | P1 | Improve error UX | High | Low |
| #98 | P2 | Refactor SQL validation | Medium | High |

---

## Recommended Implementation Order

**Phase 1 (Quick Wins)**:
1. ✅ Issue #97 - Improve error UX (Low complexity, high impact)
   - Estimated effort: 2-4 hours
   - Direct token cost reduction

**Phase 2 (Code Quality)**:
2. ✅ Issue #96 - Standardize parameter validation (Medium complexity, high impact)
   - Estimated effort: 4-6 hours
   - Enables better testing

3. ✅ Issue #95 - Refactor tool_error_handler (Medium complexity, high impact)
   - Estimated effort: 4-6 hours
   - Reduces code by 50%

**Phase 3 (Technical Debt)**:
4. ✅ Issue #98 - Refactor SQL validation (High complexity, medium impact)
   - Estimated effort: 8-12 hours
   - Can be deferred if needed

---

## Total Estimated Effort

- **P1 Issues**: 10-16 hours
- **P2 Issues**: 8-12 hours
- **Total**: 18-28 hours (approximately 3-4 working days)

---

## Related Documentation

- **Production Readiness Report**: `/Users/evandekim/Documents/igloo_mcp/PRODUCTION_READINESS_IMPLEMENTATION.md`
- **Regression Testing Summary**: `/Users/evandekim/Documents/igloo_mcp/REGRESSION_TESTING_SUMMARY.md`
- **Spec**: `~/.factory/specs/2025-11-29-production-readiness-evaluation-v0-3-3-branch.md`

---

## Notes

**Not Blockers for v0.3.3**:
- All P1/P2 issues are improvements, not critical bugs
- v0.3.3 can be released without these changes
- These are quality-of-life and technical debt issues for v0.3.4

**Labels Applied**:
- All issues tagged with `enhancement`
- Priority tracked in issue title (P1/P2)
- Consider adding custom P1/P2 labels in repository settings for better filtering

---

## Next Steps

1. ✅ Review issues with team
2. ✅ Prioritize for v0.3.4 milestone
3. ✅ Assign to developers
4. ✅ Consider adding to project board

**All issues successfully created!** 🚀
