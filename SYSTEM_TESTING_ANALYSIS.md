# System Testing Analysis & Implementation Plan

**Date:** 2025-11-28
**Branch:** feature/v0.3.2-upgrade
**Test Suite Status:** 578 tests, 99.7% pass rate (345/346 passing)

---

## Executive Summary

This document analyzes the current system and integration test coverage for the Igloo MCP Living Reports system and provides a concrete implementation plan to achieve comprehensive end-to-end validation.

**Key Findings:**
- ✅ Strong unit test coverage (95%+ of modules)
- ✅ Good component-level integration (7 existing integration tests)
- ⚠️ Limited true end-to-end workflow tests
- ⚠️ Minimal production scenario testing (concurrency, large data, recovery)
- ❌ No explicit test markers for integration/system tests

**Recommendation:** Implement 15-20 new system tests organized into 3 phases over 2-3 weeks.

---

## Current Test Landscape

### Test Distribution (578 total tests)

| Category | Count | Coverage | Files |
|----------|-------|----------|-------|
| **Unit Tests** | ~520 | Excellent | 48 test files |
| **Integration Tests** | 7 | Good | test_living_reports_integration.py |
| **Smoke Tests** | 8 | Good | test_smoke_integration.py |
| **Regression Tests** | 14 | Excellent | test_regression_v032.py |
| **System Tests** | 0 | **MISSING** | None |
| **Property Tests** | 3 | Minimal | test_sql_validation_property.py |

### Existing Integration Tests

**File: `test_living_reports_integration.py`** (7 tests)
1. `test_full_lifecycle_create_evolve_render_revert` - Basic lifecycle
2. `test_bulk_operations_workflow` - Multi-report operations
3. `test_fork_and_synthesize_workflow` - Report forking
4. `test_concurrent_agents_version_conflict` - Version conflict detection
5. `test_template_to_advanced_workflow` - Template progression
6. `test_mcp_tool_integration_workflow` - MCP tools working together
7. `test_error_recovery_workflow` - Error handling

**Coverage Assessment:**
- ✅ Basic workflows covered
- ✅ Error paths partially covered
- ⚠️ Limited cross-component integration
- ❌ No production scenario testing
- ❌ No performance/scale testing

**File: `test_smoke_integration.py`** (8 tests)
- Focuses on mocked end-to-end without Snowflake
- Good for CI/CD validation
- Does not test real production scenarios

---

## Testing Gaps Identified

### 1. Complete User Workflows (CRITICAL)

**Missing:**
- Analyst journey: Query → Cache → History → Report → Insight → Render
- Multi-session analyst workflow (save, resume, iterate)
- Cross-tool flows (execute_query → create_report → evolve_report → render_report)
- Template → Content → Review → Finalize → Archive lifecycle

**Impact:** We cannot verify that a user can complete real tasks end-to-end.

### 2. Cross-Component Integration (HIGH)

**Missing:**
- Query execution → History logging → Cache storage → Report citation
- Index synchronization across concurrent operations
- Storage atomicity under concurrent reads/writes
- Quarto rendering with full outline structure (currently mocked)

**Impact:** Component boundaries may have integration bugs in production.

### 3. Production Scenarios (HIGH)

**Missing:**
- Large reports (50+ sections, 200+ insights)
- Concurrent editing by multiple agents/users
- Cache performance with large result sets
- Error recovery from corrupted state
- Backup pruning and retention policies
- Index corruption recovery

**Impact:** System behavior under load is unknown.

### 4. Data Flow Validation (MEDIUM)

**Missing:**
- Query result → Cache → Insight → Section → Render chain
- Template application → Section creation → Index update
- Fork operation → Data duplication → Index consistency
- Synthesize operation → Data merging → Citation preservation

**Impact:** Data integrity across operations not validated.

### 5. Performance & Scale (LOW)

**Missing:**
- Query caching performance benchmarks
- Large outline serialization/deserialization
- Index search performance with 100+ reports
- Concurrent write performance

**Impact:** Performance regressions may go unnoticed.

---

## System Testing Implementation Plan

### Phase 1: Complete User Workflows (Week 1)

**Priority:** CRITICAL
**Effort:** 3-5 days
**New Tests:** 6-8 tests

#### Test 1: Quarterly Analysis Complete Workflow
```python
test_quarterly_analysis_complete_workflow()
```
**Scenario:** Analyst creates Q4 2024 report from scratch
- Execute 3-5 queries (revenue, costs, customers)
- Results cached and logged to history
- Create report from quarterly_review template
- Add inline insights from queries
- Reference cached queries in citations
- Render to HTML with full citation map
- Verify all components working together

**Validates:**
- execute_query → cache → history flow
- create_report → template application
- evolve_report → insight addition + citation
- render_report → Quarto rendering
- Citation mapping across components

#### Test 2: Iterative Refinement Workflow
```python
test_iterative_refinement_workflow()
```
**Scenario:** Analyst drafts, reviews, refines, finalizes report
- Session 1: Create report, add initial insights
- Session 2: Resume, modify sections, reorder insights
- Session 3: Review with stakeholder, revert changes
- Session 4: Finalize, archive

**Validates:**
- Multi-session workflows
- State persistence
- Revert functionality in realistic scenario
- Audit trail completeness

#### Test 3: Template to Publication Workflow
```python
test_template_to_publication_workflow()
```
**Scenario:** Start with analyst_v1 template, complete to final PDF
- Apply analyst_v1 template (enforces citations)
- Add 5+ insights with supporting queries
- Link insights to sections
- Add section prose content
- Render to HTML and PDF
- Verify citation enforcement

**Validates:**
- Template constraint enforcement
- Section prose content rendering
- Multi-format rendering
- Citation requirement validation

#### Test 4: Concurrent Agent Collaboration
```python
test_concurrent_agent_collaboration()
```
**Scenario:** Two agents work on same report simultaneously
- Agent 1: Add insights to Executive Summary
- Agent 2: Add insights to Methodology (concurrent)
- Both agents: Commit changes
- Verify: One succeeds, one gets version conflict
- Resolve: Second agent retries with fresh version
- Verify: Both changes present in final state

**Validates:**
- Optimistic locking under concurrent writes
- Version conflict detection
- Conflict resolution workflow
- Index synchronization

#### Test 5: Multi-Report Research Workflow
```python
test_multi_report_research_workflow()
```
**Scenario:** Analyst manages multiple related reports
- Create 3 reports: "Q4 Revenue", "Q4 Costs", "Q4 Summary"
- Populate each with domain-specific insights
- Synthesize all 3 into "Q4 Full Analysis"
- Tag all with "Q4_2024"
- Search by tag, verify all 4 reports returned
- Archive originals, keep synthesis active

**Validates:**
- Multi-report management
- Synthesize operation with multiple sources
- Tagging and search
- Bulk operations (archive)

#### Test 6: Error Recovery and Resume Workflow
```python
test_error_recovery_and_resume_workflow()
```
**Scenario:** Analyst encounters errors and recovers
- Create report, add insights
- Attempt invalid evolve (missing required field)
- Verify: Error returned, report unchanged
- Retry with valid changes
- Verify: Report updated correctly
- Simulate crash during render (kill process)
- Resume: Render completes on retry
- Verify: No corruption, audit trail intact

**Validates:**
- Error handling doesn't corrupt state
- Transactional semantics
- Crash recovery
- Audit log completeness

---

### Phase 2: Production Scenarios (Week 2)

**Priority:** HIGH
**Effort:** 4-6 days
**New Tests:** 6-8 tests

#### Test 7: Large Report Handling
```python
test_large_report_handling()
```
**Scenario:** Create report with 50 sections, 200 insights
- Generate realistic section/insight structure
- Link insights to sections (realistic distribution)
- Add section prose content (500-1000 words each)
- Render to HTML
- Measure: Serialization time, render time
- Verify: All insights rendered, citations correct

**Validates:**
- Performance at scale
- Serialization/deserialization of large outlines
- Quarto handling of large documents
- Citation mapping at scale

#### Test 8: Concurrent Section Editing
```python
test_concurrent_section_editing()
```
**Scenario:** 5 agents edit different sections simultaneously
- Create report with 10 sections
- Spawn 5 threads, each modifying 2 sections
- Execute concurrent evolve_report calls
- Verify: All changes applied (no lost updates)
- Verify: Audit log has all 5 actions
- Verify: Index consistent with final state

**Validates:**
- Thread safety of storage layer
- Lock contention handling
- Atomic operations under load
- Index integrity under concurrent writes

#### Test 9: Cache Performance Under Load
```python
test_cache_performance_under_load()
```
**Scenario:** Execute 100 queries, 50% cache hits
- Execute 50 unique queries (cache misses)
- Re-execute same 50 queries (cache hits)
- Measure: Cache hit latency vs miss latency
- Verify: Cache hit <10ms, miss >100ms
- Verify: All 100 queries logged to history
- Verify: Cache directory has 50 entries

**Validates:**
- Cache performance characteristics
- Cache hit/miss behavior
- History logging under load
- Cache directory management

#### Test 10: Index Corruption Recovery
```python
test_index_corruption_recovery()
```
**Scenario:** Recover from corrupted index
- Create 10 reports
- Manually corrupt index.jsonl (truncate midline)
- Attempt to list reports
- Verify: Error detected, graceful fallback
- Rebuild index from storage
- Verify: All 10 reports recovered
- Verify: Index consistent with storage

**Validates:**
- Index corruption detection
- Index rebuild capability
- Graceful degradation
- Data recovery procedures

#### Test 11: Backup Pruning Strategy
```python
test_backup_pruning_strategy()
```
**Scenario:** Verify backup retention policies
- Create report, make 100 modifications
- Verify: 100 backup files created
- Trigger pruning (if implemented)
- Verify: Critical backups retained (create, major versions)
- Verify: Intermediate backups pruned
- Verify: Can still revert to critical points

**Validates:**
- Backup creation under heavy modification
- Pruning strategy (if implemented)
- Critical backup preservation
- Revert functionality with pruned backups

#### Test 12: Query History to Report Citation Flow
```python
test_query_history_to_report_citation_flow()
```
**Scenario:** Full integration from query to citation
- Execute query with post_query_insight
- Verify: Logged to history with insight
- Create report
- Add insight referencing query ID
- Evolve report to link insight to section
- Render report
- Verify: Citation map includes query
- Verify: Rendered HTML has citation link
- Verify: Citation link resolves to history entry

**Validates:**
- Execute_query → history → cache → insight → citation chain
- Citation map generation
- Citation rendering in output
- End-to-end query provenance

#### Test 13: Template to Storage to Index Flow
```python
test_template_to_storage_to_index_flow()
```
**Scenario:** Verify template application updates all layers
- Create report with analyst_v1 template
- Verify: Storage has outline.json with sections
- Verify: Index has entry with correct metadata
- Verify: Audit log has "create_report" event
- Verify: Backup created for initial state
- Load report from different service instance
- Verify: Template structure preserved

**Validates:**
- Template → outline → storage → index chain
- Storage persistence
- Index synchronization
- Cross-instance consistency

#### Test 14: Render with All Content Types
```python
test_render_with_all_content_types()
```
**Scenario:** Render report with all v0.3.2 features
- Create report with sections
- Add insights with citations
- Add section prose content (markdown, HTML, plain)
- Add inline insights to sections
- Render to HTML and PDF
- Verify: All content types rendered correctly
- Verify: Prose content formatted properly
- Verify: Inline insights visible
- Verify: Citations linked correctly

**Validates:**
- v0.3.2 section prose content rendering
- v0.3.2 inline insights rendering
- Multiple content format support
- Quarto template compatibility

---

### Phase 3: Advanced Scenarios (Week 3 - Optional)

**Priority:** MEDIUM
**Effort:** 2-3 days
**New Tests:** 3-5 tests

#### Test 15: Cross-Database Query Workflow
```python
test_cross_database_query_workflow()
```
**Scenario:** Execute queries across databases, consolidate in report
- Execute query in ANALYTICS_DB
- Execute query in PROD_DB
- Cache both queries
- Create report
- Add insights from both databases
- Verify: Citations reference correct databases
- Verify: Cache keys include database context

**Validates:**
- Multi-database support
- Cache key differentiation
- Context preservation in citations
- Cross-database insight correlation

#### Test 16: Snowflake Session Management
```python
test_snowflake_session_management()
```
**Scenario:** Verify session parameter handling
- Set session params (warehouse, role)
- Execute query with overrides
- Verify: Query uses override params
- Verify: Session params restored after query
- Verify: History logs correct params

**Validates:**
- Session parameter isolation
- Override handling
- Parameter restoration
- Context logging

#### Test 17: Render Output Validation
```python
test_render_output_validation()
```
**Scenario:** Validate rendered output quality
- Create report with known content
- Render to HTML
- Parse HTML, verify structure:
  - All sections present
  - All insights rendered
  - Citations linked
  - Prose content formatted
- Render to PDF
- Verify: PDF created successfully
- Verify: PDF size reasonable

**Validates:**
- Quarto output quality
- HTML structure correctness
- PDF generation
- Content completeness in output

---

## Implementation Strategy

### Test Organization

Create new test file structure:

```
tests/
├── system/                          # NEW
│   ├── __init__.py
│   ├── conftest.py                  # Shared fixtures
│   ├── test_user_workflows.py       # Phase 1 tests
│   ├── test_production_scenarios.py # Phase 2 tests
│   └── test_advanced_scenarios.py   # Phase 3 tests
├── integration/                     # REFACTOR EXISTING
│   ├── test_living_reports_integration.py (keep)
│   └── test_smoke_integration.py (keep)
└── unit/                           # MOVE EXISTING
    └── (all existing test_*.py files)
```

### Test Markers

Add pytest markers for test categorization:

```python
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "unit: Unit tests (fast, isolated)",
    "integration: Integration tests (cross-component)",
    "system: System tests (end-to-end workflows)",
    "performance: Performance and scale tests",
    "slow: Slow-running tests (>5s)",
]
```

Usage:
```bash
pytest -m unit           # Run only unit tests (fast)
pytest -m "not slow"     # Skip slow tests
pytest -m system         # Run system tests only
```

### Fixtures Strategy

**Shared Fixtures (system/conftest.py):**
```python
@pytest.fixture
def full_service_stack(tmp_path):
    """Complete service stack for system tests."""
    return {
        'service': ReportService(...),
        'snowflake': FakeSnowflakeService(...),
        'history': QueryHistory(...),
        'cache': QueryResultCache(...),
    }

@pytest.fixture
def realistic_query_results():
    """Generate realistic query results for testing."""
    # 1000 rows of realistic data

@pytest.fixture
def large_report_fixture():
    """Pre-built large report (50 sections, 200 insights)."""
```

### Development Workflow

**Week 1: User Workflows**
- Day 1-2: Setup system test structure, shared fixtures
- Day 3-4: Implement Tests 1-3 (workflows)
- Day 5: Implement Tests 4-6 (concurrent, error recovery)

**Week 2: Production Scenarios**
- Day 1-2: Implement Tests 7-9 (scale, concurrency, cache)
- Day 3-4: Implement Tests 10-12 (recovery, pruning, citations)
- Day 5: Implement Tests 13-14 (integration flows)

**Week 3: Polish & Advanced (Optional)**
- Day 1-2: Implement Tests 15-17 (advanced scenarios)
- Day 3: Review, refactor, documentation
- Day 4: Performance tuning, optimization

### Success Criteria

**Phase 1 Complete:**
- ✅ 6+ user workflow tests passing
- ✅ All workflows execute without mocks
- ✅ Coverage of analyst journey scenarios

**Phase 2 Complete:**
- ✅ 6+ production scenario tests passing
- ✅ Large report handling validated (50+ sections)
- ✅ Concurrent operations tested
- ✅ Error recovery validated

**Phase 3 Complete (Optional):**
- ✅ 3+ advanced scenario tests passing
- ✅ Cross-database workflows validated
- ✅ Output quality validated

**Overall Success:**
- ✅ 15-20 new system tests
- ✅ Test suite >600 tests
- ✅ System test coverage >80%
- ✅ All critical user workflows validated
- ✅ Production readiness validated

---

## Risk Assessment

### Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Quarto dependency in tests | Tests fail in CI | Medium | Use dry_run mode, mock when needed |
| Long test execution time | Slow CI/CD | High | Use markers, run system tests separately |
| Snowflake dependency | Tests require real DB | Low | Use FakeSnowflakeService everywhere |
| Test data maintenance | Brittle tests | Medium | Use factories, avoid hardcoding |
| Flaky concurrent tests | Intermittent failures | Medium | Use proper synchronization, retries |

### Dependencies

**Required:**
- ✅ FakeSnowflakeService (exists)
- ✅ tmp_path fixture (pytest built-in)
- ✅ ReportService (exists)
- ⚠️ Quarto (optional, use dry_run)

**Optional:**
- pytest-xdist (parallel test execution)
- pytest-benchmark (performance testing)
- hypothesis (property-based testing)

---

## Next Steps

### Immediate (This Session)
1. ✅ Complete this analysis document
2. ⬜ Review and refine plan
3. ⬜ Create system/ test directory structure
4. ⬜ Implement first 2-3 workflow tests (proof of concept)

### Short-term (This Week)
1. Complete Phase 1 (user workflows)
2. Set up test markers and organization
3. Document system testing in README

### Medium-term (Next 2 Weeks)
1. Complete Phase 2 (production scenarios)
2. Integrate into CI/CD pipeline
3. Review and optimize test performance

### Long-term (Future)
1. Complete Phase 3 (advanced scenarios)
2. Add performance benchmarks
3. Expand property-based testing

---

## Metrics & Tracking

### Current Baseline
- **Total Tests:** 578
- **Pass Rate:** 99.7% (345/346)
- **Integration Tests:** 7
- **System Tests:** 0

### Target State
- **Total Tests:** 595-605
- **Pass Rate:** >99%
- **Integration Tests:** 7 (keep)
- **System Tests:** 15-20 (NEW)

### Progress Tracking
- [ ] Phase 1: User Workflows (0/6 complete)
- [ ] Phase 2: Production Scenarios (0/8 complete)
- [ ] Phase 3: Advanced Scenarios (0/3 complete)

---

## Conclusion

This system testing plan addresses critical gaps in end-to-end validation while building on the strong foundation of existing unit and integration tests. The phased approach ensures we deliver value incrementally:

1. **Phase 1** validates that users can complete real workflows
2. **Phase 2** ensures production readiness and resilience
3. **Phase 3** adds advanced scenario coverage

**Recommendation:** Proceed with Phase 1 implementation immediately. The 6 user workflow tests are CRITICAL for v0.3.2 validation and should be completed before merging to main.

**Estimated Effort:** 2-3 weeks for full implementation, 1 week for Phase 1 (critical path).
