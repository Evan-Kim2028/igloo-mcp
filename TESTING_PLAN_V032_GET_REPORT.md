# Testing Coverage Plan: v0.3.2 get_report & Token Efficiency Features

**Date:** 2025-11-28
**Implementation Spec:** v0-3-2-final-implementation-spec-get_report-get_report_schema.md
**Current Status:** Basic unit tests passing (23/23), **needs comprehensive coverage**

---

## Executive Summary

This document provides a comprehensive testing plan for the v0.3.2 features:
1. **New MCP Tools**: `get_report` and `get_report_schema`
2. **Token Efficiency Enhancements**: `evolve_report`, `search_report`, `render_report`

### Current Test Coverage

| Component | Unit Tests | Integration Tests | System Tests | Production Tests | Total Coverage |
|-----------|------------|-------------------|--------------|------------------|----------------|
| `get_report` | 7 ✅ | 0 ❌ | 0 ❌ | 0 ❌ | **30%** |
| `get_report_schema` | 11 ✅ | 0 ❌ | 0 ❌ | 0 ❌ | **40%** |
| Token Efficiency | 5 ✅ | 0 ❌ | 0 ❌ | 0 ❌ | **20%** |
| **Overall** | **23/23 passing** | **0/0** | **0/0** | **0/0** | **~30%** |

### Testing Gaps Identified

**CRITICAL GAPS:**
- ❌ No integration tests (tools working together)
- ❌ No system tests (complete workflows)
- ❌ No production scenario tests (scale, performance)
- ❌ No regression tests (backward compatibility)
- ❌ Limited edge case coverage
- ❌ No token efficiency validation tests

---

## Part 1: get_report Tool - Testing Requirements

### Current Coverage (7 tests)

✅ **Basic Functionality:**
- `test_get_report_summary_mode` - Summary mode returns overview
- `test_get_report_sections_mode` - Sections mode returns details
- `test_get_report_insights_mode_with_filter` - Insights filtering works
- `test_get_report_invalid_mode` - Invalid mode validation
- `test_get_report_not_found` - Selector error handling

**Coverage:** ~30% (basic happy paths only)

### Missing Tests - CRITICAL

#### 1. Mode Coverage (Missing 6 tests)

**Test:** `test_get_report_full_mode`
```python
async def test_get_report_full_mode(tmp_path):
    """Verify full mode returns complete outline structure."""
    # Create report with sections, insights, content
    # Get full mode
    # Verify: all sections, all insights, all metadata returned
    # Verify: pagination works for large reports
```

**Test:** `test_get_report_sections_by_title_fuzzy_match`
```python
async def test_get_report_sections_by_title_fuzzy_match(tmp_path):
    """Test section title fuzzy matching."""
    # Create report with "Executive Summary", "Network Activity"
    # Search for section_titles=["executive", "network"]
    # Verify: both sections matched despite partial titles
```

**Test:** `test_get_report_sections_by_id`
```python
async def test_get_report_sections_by_id(tmp_path):
    """Test section retrieval by exact IDs."""
    # Create report with multiple sections
    # Get sections with section_ids=[id1, id2]
    # Verify: only requested sections returned
```

**Test:** `test_get_report_insights_multiple_filters`
```python
async def test_get_report_insights_multiple_filters(tmp_path):
    """Test combining multiple insight filters."""
    # Create insights with varying importance, status, sections
    # Filter: min_importance=7, section_ids=[sec1], status="active"
    # Verify: only insights matching ALL criteria returned
```

**Test:** `test_get_report_mode_sections_with_content`
```python
async def test_get_report_mode_sections_with_content(tmp_path):
    """Test include_content parameter in sections mode."""
    # Create section with prose content (markdown)
    # Get sections with include_content=True
    # Verify: content field populated
    # Get sections with include_content=False (default)
    # Verify: content field absent (token savings)
```

**Test:** `test_get_report_mode_insights_with_citations`
```python
async def test_get_report_mode_insights_with_citations(tmp_path):
    """Test citation information in insights mode."""
    # Create insights with supporting_queries (citations)
    # Get insights mode
    # Verify: has_citations=True, citation_count correct
    # Verify: section_id shows which section owns insight
```

#### 2. Pagination Tests (Missing 4 tests)

**Test:** `test_get_report_pagination_sections`
```python
async def test_get_report_pagination_sections(tmp_path):
    """Test pagination for sections mode."""
    # Create report with 100 sections
    # Get first page: limit=20, offset=0
    # Verify: returns 20 sections, total_matched=100
    # Get second page: limit=20, offset=20
    # Verify: returns next 20 sections, no overlap
```

**Test:** `test_get_report_pagination_insights`
```python
async def test_get_report_pagination_insights(tmp_path):
    """Test pagination for insights mode."""
    # Create report with 150 insights
    # Paginate through: limit=50, offset=0/50/100
    # Verify: all 150 insights retrieved across pages
    # Verify: no duplicates, correct ordering
```

**Test:** `test_get_report_pagination_default_limits`
```python
async def test_get_report_pagination_default_limits(tmp_path):
    """Test default pagination limits."""
    # Create report with 75 sections
    # Get sections without limit/offset
    # Verify: default limit=50 applied
    # Verify: offset=0 by default
```

**Test:** `test_get_report_pagination_edge_cases`
```python
async def test_get_report_pagination_edge_cases(tmp_path):
    """Test pagination edge cases."""
    # Test: offset > total_matched (returns empty)
    # Test: limit=0 (returns empty with total_matched)
    # Test: limit > total (returns all available)
    # Test: negative offset/limit (validation error)
```

#### 3. Audit Trail Tests (Missing 2 tests)

**Test:** `test_get_report_with_audit_trail`
```python
async def test_get_report_with_audit_trail(tmp_path):
    """Test include_audit parameter."""
    # Create report, make several modifications
    # Get with include_audit=True
    # Verify: recent_audit contains last N events
    # Verify: events have action_type, actor, timestamp
```

**Test:** `test_get_report_audit_pagination`
```python
async def test_get_report_audit_pagination(tmp_path):
    """Test audit trail respects pagination."""
    # Create report with 100 audit events
    # Get with include_audit=True, limit_audit=10
    # Verify: only last 10 events returned
```

#### 4. Error Handling Tests (Missing 5 tests)

**Test:** `test_get_report_invalid_section_ids`
```python
async def test_get_report_invalid_section_ids(tmp_path):
    """Test behavior with non-existent section IDs."""
    # Get sections with section_ids=[non_existent_uuid]
    # Verify: returns empty list, total_matched=0
    # Verify: no error raised (graceful handling)
```

**Test:** `test_get_report_invalid_insight_ids`
```python
async def test_get_report_invalid_insight_ids(tmp_path):
    """Test behavior with non-existent insight IDs."""
    # Similar to section IDs test
```

**Test:** `test_get_report_malformed_uuids`
```python
async def test_get_report_malformed_uuids(tmp_path):
    """Test validation of UUID format."""
    # Attempt section_ids=["not-a-uuid"]
    # Verify: MCPValidationError raised
    # Verify: error message mentions invalid UUID format
```

**Test:** `test_get_report_conflicting_parameters`
```python
async def test_get_report_conflicting_parameters(tmp_path):
    """Test parameter conflict validation."""
    # Attempt: mode="summary" with section_ids=[...]
    # Verify: MCPValidationError (section_ids only valid for sections/insights mode)
    # Test other invalid combinations
```

**Test:** `test_get_report_empty_report`
```python
async def test_get_report_empty_report(tmp_path):
    """Test getting empty report (no sections/insights)."""
    # Create report with template="default" (empty)
    # Get all modes: summary, full, sections, insights
    # Verify: all return success with empty structures
    # Verify: total counts = 0
```

#### 5. Token Efficiency Validation (Missing 3 tests)

**Test:** `test_get_report_response_sizes`
```python
async def test_get_report_response_sizes(tmp_path):
    """Measure and validate response token usage."""
    # Create standardized report (10 sections, 30 insights)
    # Measure response sizes for each mode:
    # - summary: should be ~200-300 tokens
    # - sections (1 section): should be ~100-150 tokens
    # - insights (filtered): should be ~150-200 tokens per insight
    # - full: baseline comparison
    # Verify: progressive disclosure saves tokens
```

**Test:** `test_get_report_selective_retrieval_workflow`
```python
async def test_get_report_selective_retrieval_workflow(tmp_path):
    """Test recommended workflow for token efficiency."""
    # Workflow: summary → specific section → specific insights
    # Track cumulative token usage
    # Compare to: getting full report upfront
    # Verify: selective approach uses 50-70% fewer tokens
```

**Test:** `test_get_report_include_content_token_impact`
```python
async def test_get_report_include_content_token_impact(tmp_path):
    """Test token impact of include_content parameter."""
    # Create section with large prose content (1000 words)
    # Get without include_content: measure size
    # Get with include_content: measure size
    # Verify: difference matches content size
    # Verify: content adds ~300-500 tokens per section
```

### Total Missing Tests for get_report: **20 tests**

---

## Part 2: get_report_schema Tool - Testing Requirements

### Current Coverage (11 tests)

✅ **Basic Functionality:**
- JSON schema, examples, compact formats tested
- Invalid schema_type/format validation
- All schemas retrieval
- Individual schema retrieval (insight, section)

**Coverage:** ~40% (good basic coverage, missing integration)

### Missing Tests - HIGH PRIORITY

#### 1. Schema Accuracy Tests (Missing 4 tests)

**Test:** `test_schema_matches_actual_models`
```python
async def test_schema_matches_actual_models():
    """Verify generated schemas match Pydantic model definitions."""
    # Get proposed_changes schema
    # Load actual ProposedChanges model
    # Compare: required fields match
    # Compare: field types match
    # Compare: validation rules match
```

**Test:** `test_schema_examples_are_executable`
```python
async def test_schema_examples_are_executable():
    """Verify all examples can be used in evolve_report."""
    # Get all examples
    # For each example:
    #   - Create test report
    #   - Execute evolve_report with example payload
    #   - Verify: success (no validation errors)
```

**Test:** `test_schema_completeness`
```python
async def test_schema_completeness():
    """Verify all change operations have examples."""
    # Get examples
    # Verify examples exist for:
    #   - add_insight
    #   - add_section
    #   - modify_insight
    #   - modify_section
    #   - remove_insight
    #   - remove_section
    #   - add_section_with_insights (atomic)
    #   - status_change
```

**Test:** `test_schema_version_tracking`
```python
async def test_schema_version_tracking():
    """Verify schema_version is tracked correctly."""
    # Get schema
    # Verify: schema_version field present
    # Verify: version matches CHANGELOG.md
    # Future: test backward compatibility across versions
```

#### 2. Format Consistency Tests (Missing 3 tests)

**Test:** `test_compact_format_consistency`
```python
async def test_compact_format_consistency():
    """Verify compact format is consistent across all schemas."""
    # Get compact format for all schema types
    # Verify: all use string notation (e.g., "Array<...>")
    # Verify: optional fields marked with "?"
    # Verify: type constraints shown (e.g., "0-10" for importance)
```

**Test:** `test_json_schema_format_validity`
```python
async def test_json_schema_format_validity():
    """Verify JSON schemas are valid JSON Schema Draft 7."""
    # Get JSON schema for all types
    # Validate against JSON Schema meta-schema
    # Verify: $schema field present
    # Verify: required/properties structure correct
```

**Test:** `test_format_conversion_accuracy`
```python
async def test_format_conversion_accuracy():
    """Verify all formats represent same underlying schema."""
    # Get all three formats for same schema_type
    # Extract field definitions from each
    # Verify: same fields present across all formats
    # Verify: no information loss between formats
```

#### 3. Integration with evolve_report (Missing 3 tests)

**Test:** `test_schema_evolve_report_integration`
```python
async def test_schema_evolve_report_integration():
    """Test schema examples work with actual evolve_report tool."""
    # Get schema examples
    # For each example:
    #   - Pass to evolve_report
    #   - Verify: validation passes
    #   - Verify: changes applied correctly
```

**Test:** `test_schema_error_messages_accuracy`
```python
async def test_schema_error_messages_accuracy():
    """Verify schema helps agents fix validation errors."""
    # Intentionally create invalid proposed_changes
    # Get schema to check requirements
    # Fix based on schema
    # Verify: second attempt succeeds
    # Verify: schema provided correct guidance
```

**Test:** `test_schema_covers_all_evolve_operations`
```python
async def test_schema_covers_all_evolve_operations():
    """Verify schema documents all possible evolve operations."""
    # Get evolve_report tool capabilities
    # Get schema examples
    # Verify: every operation type has an example
    # Verify: every field in ProposedChanges has documentation
```

### Total Missing Tests for get_report_schema: **10 tests**

---

## Part 3: Token Efficiency Enhancements - Testing Requirements

### Current Coverage (5 tests)

✅ **Basic Functionality:**
- `evolve_report` response_detail levels tested (minimal, standard, full)
- `search_report` fields parameter tested
- `render_report` preview_max_chars tested

**Coverage:** ~20% (minimal coverage, needs validation)

### Missing Tests - CRITICAL

#### 1. evolve_report Token Savings Tests (Missing 6 tests)

**Test:** `test_evolve_response_detail_token_measurements`
```python
async def test_evolve_response_detail_token_measurements(tmp_path):
    """Measure actual token savings across response_detail levels."""
    # Standard operation: add 5 insights, 2 sections
    # Get responses for: minimal, standard, full
    # Measure response sizes
    # Verify: minimal ~200 tokens, standard ~400, full ~1000+
    # Verify: minimal is 50-80% smaller than full
```

**Test:** `test_evolve_minimal_preserves_essential_info`
```python
async def test_evolve_minimal_preserves_essential_info(tmp_path):
    """Verify minimal response includes everything agent needs."""
    # Execute evolve with response_detail="minimal"
    # Verify response includes:
    #   - status (success/failed)
    #   - report_id (for next operation)
    #   - outline_version (for optimistic locking)
    #   - summary counts (verification)
    # Verify: agent can continue workflow without full response
```

**Test:** `test_evolve_standard_provides_ids`
```python
async def test_evolve_standard_provides_ids(tmp_path):
    """Verify standard response includes IDs for verification."""
    # Execute evolve adding multiple items
    # Response should include: section_ids_added, insight_ids_added
    # Verify: agent can reference new IDs without querying report
```

**Test:** `test_evolve_full_includes_debugging_info`
```python
async def test_evolve_full_includes_debugging_info(tmp_path):
    """Verify full response includes all debugging information."""
    # Execute evolve with response_detail="full"
    # Verify: changes_applied (full echo), timing, warnings
    # Use case: debugging complex changes, performance analysis
```

**Test:** `test_evolve_response_detail_with_errors`
```python
async def test_evolve_response_detail_with_errors(tmp_path):
    """Test response_detail behavior when validation fails."""
    # Attempt invalid evolve with each response_detail level
    # Verify: all levels return full error information
    # Verify: validation_errors present regardless of detail level
```

**Test:** `test_evolve_backward_compatibility`
```python
async def test_evolve_backward_compatibility(tmp_path):
    """Verify omitting response_detail uses standard default."""
    # Execute evolve without response_detail parameter
    # Verify: response structure matches standard level
    # Verify: no breaking changes for existing agents
```

#### 2. search_report Token Savings Tests (Missing 5 tests)

**Test:** `test_search_fields_token_measurements`
```python
async def test_search_fields_token_measurements(tmp_path):
    """Measure token savings with fields parameter."""
    # Create 20 reports with full metadata
    # Search all: measure full response size
    # Search with fields=["report_id", "title"]: measure size
    # Verify: filtered response is 30-50% smaller
```

**Test:** `test_search_fields_all_combinations`
```python
async def test_search_fields_all_combinations(tmp_path):
    """Test all valid field combinations."""
    # Test: each field individually
    # Test: common combinations (id+title, id+status, etc.)
    # Test: all fields (equivalent to default)
    # Verify: each combination returns only requested fields
```

**Test:** `test_search_fields_validation`
```python
async def test_search_fields_validation(tmp_path):
    """Test fields parameter validation."""
    # Test: valid fields from spec (report_id, title, created_at, etc.)
    # Test: invalid fields (nonsense, typos)
    # Verify: clear error message listing valid fields
    # Verify: error message includes actual invalid field name
```

**Test:** `test_search_fields_empty_list`
```python
async def test_search_fields_empty_list(tmp_path):
    """Test behavior with fields=[]."""
    # Search with fields=[]
    # Verify: validation error or returns all fields
    # Document expected behavior
```

**Test:** `test_search_backward_compatibility`
```python
async def test_search_backward_compatibility(tmp_path):
    """Verify omitting fields returns all metadata."""
    # Search without fields parameter
    # Verify: all fields present (created_at, updated_at, tags, etc.)
    # Verify: no breaking changes
```

#### 3. render_report Preview Tests (Missing 3 tests)

**Test:** `test_render_preview_truncation`
```python
async def test_render_preview_truncation(tmp_path):
    """Test preview is truncated at preview_max_chars."""
    # Create report, render with preview
    # Set preview_max_chars=100
    # Verify: preview length <= 100 chars
    # Verify: truncation indicator present if truncated
```

**Test:** `test_render_preview_default_2000`
```python
async def test_render_preview_default_2000(tmp_path):
    """Verify default preview_max_chars is 2000."""
    # Render without preview_max_chars parameter
    # Verify: preview truncated at 2000 chars (if longer)
```

**Test:** `test_render_preview_disabled`
```python
async def test_render_preview_disabled(tmp_path):
    """Test include_preview=False omits preview entirely."""
    # Render with include_preview=False
    # Verify: no preview field in response
    # Verify: token savings from omitting preview
```

### Total Missing Tests for Token Efficiency: **14 tests**

---

## Part 4: Integration Tests - CRITICAL GAP

### Currently: **0 integration tests exist**

Integration tests verify tools work together correctly in multi-step workflows.

#### Workflow Integration Tests (Need 8 tests)

**Test:** `test_search_get_evolve_workflow`
```python
async def test_search_get_evolve_workflow(tmp_path):
    """Test: search → get → evolve flow."""
    # 1. search_report to find report
    # 2. get_report (summary) to understand structure
    # 3. get_report (sections) to get specific section_id
    # 4. evolve_report to modify that section
    # 5. get_report to verify changes
    # Verify: complete workflow works without errors
    # Measure: cumulative token usage
```

**Test:** `test_schema_guided_evolution`
```python
async def test_schema_guided_evolution(tmp_path):
    """Test: get_schema → construct change → evolve."""
    # 1. get_report_schema (examples format)
    # 2. Adapt example to actual report structure
    # 3. evolve_report with constructed change
    # Verify: schema helps agent build valid changes
```

**Test:** `test_progressive_disclosure_workflow`
```python
async def test_progressive_disclosure_workflow(tmp_path):
    """Test: summary → filter insights → get details."""
    # 1. get_report (summary) - find high-level structure
    # 2. get_report (insights, min_importance=8) - find key insights
    # 3. get_report (sections, section_ids=[...]) - get details for sections with key insights
    # Verify: agent builds complete understanding incrementally
    # Verify: uses 50-70% fewer tokens than full mode
```

**Test:** `test_create_with_schema_workflow`
```python
async def test_create_with_schema_workflow(tmp_path):
    """Test: create → schema → initial structure → verify."""
    # 1. create_report with template
    # 2. get_report_schema to learn structure
    # 3. evolve_report to add initial content
    # 4. get_report to verify structure
    # Common pattern: agent creating new report from scratch
```

**Test:** `test_token_efficient_modification_workflow`
```python
async def test_token_efficient_modification_workflow(tmp_path):
    """Test: efficient search → targeted get → minimal evolve."""
    # 1. search_report (fields=["report_id", "title"])
    # 2. get_report (insights, min_importance=8)
    # 3. evolve_report (response_detail="minimal")
    # Measure: total tokens across workflow
    # Compare: to non-efficient approach (full search, full get, full evolve)
    # Verify: 60-70% token reduction
```

**Test:** `test_multi_section_editing_workflow`
```python
async def test_multi_section_editing_workflow(tmp_path):
    """Test: editing multiple sections across turns."""
    # Turn 1: get_report (summary) - overview
    # Turn 2: get_report (sections, section_titles=["Section 1"])
    # Turn 3: evolve_report (modify Section 1)
    # Turn 4: get_report (sections, section_titles=["Section 2"])
    # Turn 5: evolve_report (modify Section 2)
    # Verify: can edit sections independently
    # Verify: outline_version increments correctly
```

**Test:** `test_insight_focused_workflow`
```python
async def test_insight_focused_workflow(tmp_path):
    """Test: working primarily with insights."""
    # 1. get_report (insights) - all insights
    # 2. Filter/analyze insights in agent
    # 3. get_report_schema for modification structure
    # 4. evolve_report to modify/remove insights
    # 5. get_report (insights) to verify
    # Use case: agent reviewing and refining insights
```

**Test:** `test_render_verification_workflow`
```python
async def test_render_verification_workflow(tmp_path):
    """Test: build → verify → render → review."""
    # 1. create_report, evolve_report (build content)
    # 2. get_report (full) - final verification before render
    # 3. render_report (preview_max_chars=500) - quick preview
    # 4. If OK: render_report (include_preview=False) - final render
    # Verify: complete preparation → render workflow
```

### Total Integration Tests Needed: **8 tests**

---

## Part 5: System Tests - End-to-End Workflows

### Currently: **0 system tests for v0.3.2 features**

System tests validate complete user journeys with new features.

#### System Test Requirements (Need 4 tests)

**Test:** `test_system_analyst_research_workflow`
```python
async def test_system_analyst_research_workflow(full_service_stack):
    """Test complete analyst workflow using new tools."""
    # Analyst researching network activity:
    # 1. search_report to find existing research
    # 2. get_report (summary) to review existing reports
    # 3. create_report for new analysis
    # 4. execute_query for data (from system test fixtures)
    # 5. get_report_schema to learn how to add insights
    # 6. evolve_report to add query results as insights
    # 7. get_report (insights) to verify
    # 8. evolve_report to organize into sections
    # 9. render_report for final output
    # Verify: complete workflow end-to-end
```

**Test:** `test_system_report_review_and_refine`
```python
async def test_system_report_review_and_refine(full_service_stack):
    """Test reviewing and refining existing report."""
    # Scenario: reviewing Q1 report, focusing on high-priority items
    # 1. search_report (fields=minimal) to find report
    # 2. get_report (insights, min_importance=8) - high-priority only
    # 3. Agent reviews insights
    # 4. get_report (sections) to understand organization
    # 5. evolve_report (response_detail="minimal") to reorganize
    # 6. get_report (full) for final review
    # Verify: efficient review workflow
```

**Test:** `test_system_multi_report_synthesis`
```python
async def test_system_multi_report_synthesis(full_service_stack):
    """Test synthesizing insights from multiple reports."""
    # Scenario: creating summary from multiple analysis reports
    # 1. search_report to find related reports (3-4 reports)
    # 2. For each: get_report (insights, min_importance=7)
    # 3. create_report for synthesis
    # 4. get_report_schema for structure
    # 5. evolve_report to combine key insights
    # 6. Verify: insights from all source reports included
```

**Test:** `test_system_template_based_report_building`
```python
async def test_system_template_based_report_building(full_service_stack):
    """Test building report using template structure."""
    # Scenario: using analyst_v1 template
    # 1. create_report (template="analyst_v1")
    # 2. get_report (summary) - see template structure
    # 3. get_report_schema for citation requirements
    # 4. For each template section:
    #    a. get_report (sections, section_titles=[...])
    #    b. evolve_report (add insights with citations)
    # 5. render_report to verify citations enforced
    # Verify: template constraints followed
```

### Total System Tests Needed: **4 tests**

---

## Part 6: Production & Regression Tests

### Production Scenario Tests (Need 6 tests)

**Test:** `test_production_large_report_get_performance`
```python
async def test_production_large_report_get_performance(tmp_path):
    """Test get_report performance with large reports."""
    # Create report: 100 sections, 500 insights
    # Time each mode:
    #   - summary: should be <100ms
    #   - sections (paginated): <200ms per page
    #   - insights (filtered): <300ms
    #   - full (paginated): <500ms per page
    # Verify: performance acceptable at scale
```

**Test:** `test_production_concurrent_get_operations`
```python
async def test_production_concurrent_get_operations(tmp_path):
    """Test concurrent get_report calls."""
    # Simulate: 5 concurrent agents reading same report
    # All execute get_report (different modes) simultaneously
    # Verify: all succeed without errors
    # Verify: no race conditions
```

**Test:** `test_production_token_budget_simulation`
```python
async def test_production_token_budget_simulation(tmp_path):
    """Simulate realistic token budget constraints."""
    # Agent has 8K token context budget
    # Task: understand and modify large report
    # Workflow: use token-efficient parameters
    # Verify: task completable within budget
    # Measure: token usage at each step
```

**Test:** `test_production_search_scalability`
```python
async def test_production_search_scalability(tmp_path):
    """Test search_report with many reports."""
    # Create 200 reports
    # Search with fields=["report_id", "title"]
    # Measure: response time and size
    # Verify: response time <500ms
    # Verify: response size manageable
```

**Test:** `test_production_pagination_consistency`
```python
async def test_production_pagination_consistency(tmp_path):
    """Test pagination consistency across multiple requests."""
    # Create large report
    # Paginate through all sections across multiple calls
    # Verify: no duplicates, no missing items
    # Verify: order consistent across pages
```

**Test:** `test_production_error_recovery`
```python
async def test_production_error_recovery(tmp_path):
    """Test graceful error handling in production scenarios."""
    # Scenario 1: get_report on archived report
    # Scenario 2: evolve_report fails, agent uses get_report to verify unchanged
    # Scenario 3: invalid parameters, agent uses get_report_schema to fix
    # Verify: agent can recover from errors using tools
```

### Regression Tests (Need 5 tests)

**Test:** `test_regression_evolve_without_response_detail`
```python
async def test_regression_evolve_without_response_detail(tmp_path):
    """Verify existing evolve_report calls still work."""
    # Execute evolve_report WITHOUT new response_detail parameter
    # Verify: behaves as before (standard level)
    # Verify: existing agent code doesn't break
```

**Test:** `test_regression_search_without_fields`
```python
async def test_regression_search_without_fields(tmp_path):
    """Verify existing search_report calls still work."""
    # Execute search_report WITHOUT new fields parameter
    # Verify: returns all fields as before
    # Verify: no breaking changes
```

**Test:** `test_regression_render_without_preview_params`
```python
async def test_regression_render_without_preview_params(tmp_path):
    """Verify existing render_report calls still work."""
    # Execute render_report WITHOUT new preview parameters
    # Verify: default behavior unchanged
```

**Test:** `test_regression_existing_workflows_unaffected`
```python
async def test_regression_existing_workflows_unaffected(tmp_path):
    """Test existing v0.3.1 workflows still work."""
    # Execute typical v0.3.1 workflow:
    #   create_report → evolve_report → render_report
    # Without using any new v0.3.2 features
    # Verify: no changes in behavior
    # Verify: no new required parameters
```

**Test:** `test_regression_api_response_structure`
```python
async def test_regression_api_response_structure(tmp_path):
    """Verify response structures maintain backward compatibility."""
    # For each existing tool, call without new params
    # Verify: response structure unchanged
    # Verify: no removed fields
    # Verify: new fields are optional/additive
```

### Total Production/Regression Tests Needed: **11 tests**

---

## Summary: Complete Testing Requirements

| Test Category | Current | Needed | Total Required | Priority |
|---------------|---------|--------|----------------|----------|
| **get_report Unit Tests** | 7 | 20 | 27 | 🔴 CRITICAL |
| **get_report_schema Unit Tests** | 11 | 10 | 21 | 🟡 HIGH |
| **Token Efficiency Unit Tests** | 5 | 14 | 19 | 🔴 CRITICAL |
| **Integration Tests** | 0 | 8 | 8 | 🔴 CRITICAL |
| **System Tests** | 0 | 4 | 4 | 🟡 HIGH |
| **Production Tests** | 0 | 6 | 6 | 🟡 HIGH |
| **Regression Tests** | 0 | 5 | 5 | 🔴 CRITICAL |
| **TOTAL** | **23** | **67** | **90** | |

### Coverage Goals

| Component | Current Coverage | Target Coverage | Tests Needed |
|-----------|------------------|-----------------|--------------|
| `get_report` | 30% | 90% | +20 tests |
| `get_report_schema` | 40% | 85% | +10 tests |
| Token Efficiency | 20% | 85% | +14 tests |
| Integration | 0% | 80% | +8 tests |
| System/E2E | 0% | 75% | +4 tests |
| Production | 0% | 70% | +6 tests |
| Regression | 0% | 100% | +5 tests |

---

## Implementation Phases

### Phase 1: Critical Unit Tests (Week 1)
**Goal:** Achieve 70% unit test coverage

- [ ] get_report: all modes, pagination, filtering (10 tests)
- [ ] Token efficiency: measurements and validation (8 tests)
- [ ] Error handling for all tools (7 tests)

**Deliverable:** 25 new tests, 48 total unit tests

### Phase 2: Integration & Workflows (Week 2)
**Goal:** Validate tools work together

- [ ] All 8 integration workflow tests
- [ ] All 4 system end-to-end tests

**Deliverable:** 12 new tests, 60 total tests

### Phase 3: Production & Regression (Week 3)
**Goal:** Production readiness validation

- [ ] All 6 production scenario tests
- [ ] All 5 regression tests
- [ ] Remaining unit tests (gaps from Phase 1)

**Deliverable:** 30 new tests, 90 total tests

---

## Success Criteria

**Phase 1 Complete:**
- ✅ 70% unit test coverage
- ✅ All critical paths tested
- ✅ Token measurements validated

**Phase 2 Complete:**
- ✅ 80% integration coverage
- ✅ All workflows validated end-to-end
- ✅ Multi-tool interactions tested

**Phase 3 Complete:**
- ✅ 85% overall coverage
- ✅ Production scenarios validated
- ✅ Backward compatibility confirmed
- ✅ Ready for v0.3.2 release

---

## Priority Testing Areas

### 🔴 CRITICAL (Must have before release)
1. Token efficiency validation tests
2. Regression tests (backward compatibility)
3. get_report mode coverage
4. Integration workflow tests
5. Error handling for all new parameters

### 🟡 HIGH (Should have before release)
6. Production scenario tests
7. Pagination edge cases
8. Schema accuracy validation
9. System end-to-end workflows
10. Token budget simulations

### 🟢 NICE TO HAVE (Post-release improvement)
11. Performance benchmarks
12. Concurrent access stress tests
13. Extended edge case coverage
14. Additional workflow variations

---

## Next Steps

**Immediate Actions:**
1. ✅ Review this testing plan
2. ⬜ Create test file structure (tests/integration/, tests/production/)
3. ⬜ Implement Phase 1 critical tests (Week 1)
4. ⬜ Run coverage analysis
5. ⬜ Document any spec deviations found during testing

**This testing plan ensures comprehensive validation of all v0.3.2 features before release!**
