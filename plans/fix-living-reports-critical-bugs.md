# Fix Living Reports Critical Bugs: Citation Enforcement + Metadata Updates

## Overview

This plan addresses two critical bugs in the Living Reports system that undermine data integrity and prevent users from managing report metadata:

1. **Issue #89**: Citation enforcement only applies to `analyst_v1` template, allowing uncited quantitative claims in default template reports
2. **Issue #88**: `title_change` and `metadata_updates` fields are defined in schema but silently ignored during `evolve_report` operations

Both issues can be fixed together as they modify the same core file (`evolve_report.py`).

## Problem Statement

### Issue #89: Citation Enforcement Gap

**Current Behavior:**
- Citation validation ONLY enforces for `template="analyst_v1"` reports
- Default template reports can contain uncited quantitative claims like "$175.9M volume" with zero traceability
- Undermines Living Reports' core value proposition: reproducibility and data integrity

**Evidence:**
```python
# src/igloo_mcp/mcp/tools/evolve_report.py:711-790
if current_outline.metadata.get("template") == "analyst_v1":
    # Citation enforcement ONLY happens here
    for insight_data in changes.get("insights_to_add", []):
        if not supporting_queries or len(supporting_queries) == 0:
            issues.append("Analyst reports require citations...")
```

**Real-World Impact:**
- User created 43-insight report with ZERO citations (0% cited)
- Quantitative claims are unverifiable
- Retroactive citation addition is impractical
- Scientific rigor is optional instead of mandatory

### Issue #88: Metadata Updates Silently Ignored

**Current Behavior:**
- `ProposedChanges` schema defines `title_change` and `metadata_updates` fields
- Fields pass validation without errors
- Operation returns `success`
- Changes are silently discarded - title and metadata remain unchanged

**Root Cause:**
```python
# src/igloo_mcp/mcp/tools/evolve_report.py:815-1256
def _apply_changes(self, current_outline, changes):
    # Handles: insights_to_add, insights_to_modify, insights_to_remove
    # Handles: sections_to_add, sections_to_modify, sections_to_remove
    # MISSING: title_change, metadata_updates
    # Note: status_change IS handled separately at line 457
```

**User Experience:**
```python
# User attempts to rename report
evolve_report(
    report_selector="Old Title",
    proposed_changes={"title_change": "New Title"}
)
# Returns: {"status": "success"}
# Reality: Title unchanged, user confused
```

## Motivation

### Why Citations Must Be Universal

Citations are NOT a "template-specific premium feature" - they are **core to data integrity**:

1. **Data Integrity**: Quantitative claims require traceable sources regardless of template
2. **Reproducibility**: Core principle of data analysis, not template-dependent
3. **Auditability**: Compliance requirements don't change based on template choice
4. **Scientific Rigor**: A "$75.9M volume" claim has the same burden of proof in any template

**Correct Design Philosophy:**
> Templates should control FORMATTING, not DATA QUALITY requirements.

This is analogous to spell-checking: you don't disable it for "informal documents" - it's always on.

### Why Metadata Updates Matter

- Users need to rename reports without recreating them
- Metadata updates are advertised in the schema but don't work
- Silent failures create confusion and erode trust
- No workaround exists (would require manual file editing)

## Proposed Solution

### Phase 1: Citation Enforcement for All Templates

**Modify `/src/igloo_mcp/mcp/tools/evolve_report.py:711`:**

```python
# OLD CODE (line 711):
if current_outline.metadata.get("template") == "analyst_v1":
    # Citation enforcement for analyst reports
    for insight_data in changes.get("insights_to_add", []):
        # ... validation ...

# NEW CODE:
# Citation enforcement for ALL reports (universal requirement)
# Template should only control formatting, not data quality requirements
citation_validation_enabled = not constraints.get("skip_citation_validation", False)

if citation_validation_enabled:
    # Validate insights_to_add
    for insight_data in changes.get("insights_to_add", []):
        insight_id = insight_data.get("insight_id", "unknown")
        supporting_queries = insight_data.get("citations") or insight_data.get(
            "supporting_queries", []
        )

        if not supporting_queries or len(supporting_queries) == 0:
            issues.append(
                f"All insights require citations for reproducibility. Insight '{insight_id}' "
                "missing supporting_queries[0] with execution_id. "
                "Use execute_query() first to get an execution_id, then include it in citations. "
                "To disable validation (not recommended): set skip_citation_validation=True in constraints"
            )
        elif not supporting_queries[0].get("execution_id"):
            issues.append(
                f"All insights require citations. Insight '{insight_id}' "
                "missing execution_id in citations[0]. "
                "Use execute_query() first to get an execution_id, then include it in citations"
            )

    # Validate insights_to_modify (same logic)
    for insight_data in changes.get("insights_to_modify", []):
        # ... apply same validation ...
```

**Key Changes:**
1. Remove `if current_outline.metadata.get("template") == "analyst_v1":` condition
2. Add opt-out mechanism: `skip_citation_validation: true` in constraints (for rare edge cases)
3. Update error messages to be template-agnostic
4. Default behavior: citations REQUIRED unless explicitly disabled

### Phase 2: Implement Title and Metadata Updates

**Modify `/src/igloo_mcp/mcp/tools/evolve_report.py:815-1256` (in `_apply_changes` method):**

```python
def _apply_changes(
    self,
    current_outline: Outline,
    changes: Dict[str, Any]
) -> Outline:
    """Apply proposed changes to outline."""

    # Create mutable copy
    new_outline = current_outline.model_copy(deep=True)

    # ... existing logic for insights and sections ...

    # PHASE 2 FIX: Apply title change
    if changes.get("title_change"):
        new_outline.title = changes["title_change"]
        logger.info(
            "Applied title change",
            extra={
                "old_title": current_outline.title,
                "new_title": new_outline.title
            }
        )

    # PHASE 2 FIX: Apply metadata updates
    if changes.get("metadata_updates"):
        # Merge metadata updates (shallow merge)
        new_outline.metadata.update(changes["metadata_updates"])
        logger.info(
            "Applied metadata updates",
            extra={
                "updated_keys": list(changes["metadata_updates"].keys())
            }
        )

    # Increment outline version for optimistic locking
    new_outline.outline_version = current_outline.outline_version + 1
    new_outline.updated_at = datetime.now(UTC).isoformat()

    return new_outline
```

**Key Changes:**
1. Add title change application before returning
2. Add metadata update application (shallow merge with `update()`)
3. Add structured logging for audit trail
4. Ensure `outline_version` and `updated_at` are still incremented

## Technical Approach

### Implementation Strategy

**Single PR Approach:**
- Both fixes modify the same file (`evolve_report.py`)
- No dependencies between fixes
- Can be implemented and tested together
- Reduces review overhead

**File Modifications:**
1. `/src/igloo_mcp/mcp/tools/evolve_report.py` (lines 711-790, 815-1256)
2. `/tests/test_evolve_report_tool.py` (add new test cases)
3. `/docs/api/tools/evolve_report.md` (update documentation)

### Testing Requirements

**Phase 1 Tests (Citation Enforcement):**

```python
# tests/test_evolve_report_tool.py

@pytest.mark.asyncio
async def test_citation_enforcement_for_default_template():
    """Citations are required for default template reports."""
    # Create report with default template
    outline = service.create_report(title="Test Report", template="default")

    # Attempt to add insight without citations
    changes = {
        "insights_to_add": [{
            "section_title": "Analysis",
            "summary": "Revenue is $100M",
            "content": "Detailed analysis...",
            "importance": 8,
            "tags": ["revenue"]
            # NO citations field
        }]
    }

    # Should raise validation error
    with pytest.raises(MCPValidationError) as exc_info:
        await tool.execute(
            report_selector="Test Report",
            proposed_changes=changes
        )

    assert "require citations" in str(exc_info.value).lower()
    assert "execution_id" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_citation_enforcement_for_analyst_template():
    """Citations still required for analyst_v1 template (backward compatibility)."""
    # Create report with analyst template
    outline = service.create_report(title="Analyst Report", template="analyst_v1")

    # Attempt to add insight without citations
    changes = {
        "insights_to_add": [{
            "section_title": "Findings",
            "summary": "Transaction volume increased 34%",
            "content": "Analysis...",
            "importance": 9,
            "tags": ["metrics"]
        }]
    }

    # Should still raise validation error
    with pytest.raises(MCPValidationError) as exc_info:
        await tool.execute(
            report_selector="Analyst Report",
            proposed_changes=changes
        )

    assert "require citations" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_citation_enforcement_can_be_disabled():
    """Citation validation can be explicitly disabled via constraints."""
    outline = service.create_report(title="Test Report", template="default")

    changes = {
        "insights_to_add": [{
            "section_title": "Draft",
            "summary": "Placeholder insight",
            "content": "TBD",
            "importance": 1,
            "tags": ["draft"]
            # NO citations
        }]
    }

    # Should succeed when validation is disabled
    result = await tool.execute(
        report_selector="Test Report",
        proposed_changes=changes,
        constraints={"skip_citation_validation": True}
    )

    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_insights_with_citations_succeed():
    """Insights with proper citations are accepted."""
    outline = service.create_report(title="Test Report", template="default")

    changes = {
        "insights_to_add": [{
            "section_title": "Revenue Analysis",
            "summary": "Q4 revenue reached $50M",
            "content": "Detailed breakdown...",
            "importance": 10,
            "tags": ["revenue", "q4"],
            "citations": [{
                "execution_id": "abc123-def456-789",
                "database": "ANALYTICS_DB",
                "schema": "SALES",
                "table": "REVENUE_DAILY"
            }]
        }]
    }

    # Should succeed with citations
    result = await tool.execute(
        report_selector="Test Report",
        proposed_changes=changes
    )

    assert result["status"] == "success"
    assert len(result["insights_added"]) == 1
```

**Phase 2 Tests (Metadata Updates):**

```python
# tests/test_evolve_report_tool.py

@pytest.mark.asyncio
async def test_title_change_applied():
    """title_change is applied to report."""
    # Create report
    outline = service.create_report(title="Old Title", template="default")
    original_title = outline.title

    # Change title
    result = await tool.execute(
        report_selector="Old Title",
        proposed_changes={"title_change": "New Title"}
    )

    assert result["status"] == "success"

    # Verify title changed
    updated_outline = service.get_report(report_id=outline.report_id)
    assert updated_outline.title == "New Title"
    assert updated_outline.title != original_title


@pytest.mark.asyncio
async def test_metadata_updates_applied():
    """metadata_updates are merged into report metadata."""
    # Create report with initial metadata
    outline = service.create_report(
        title="Test Report",
        template="default"
    )
    outline.metadata["original_key"] = "original_value"
    service._save_outline(outline)

    # Update metadata
    result = await tool.execute(
        report_selector="Test Report",
        proposed_changes={
            "metadata_updates": {
                "new_key": "new_value",
                "status": "in_progress"
            }
        }
    )

    assert result["status"] == "success"

    # Verify metadata updated
    updated_outline = service.get_report(report_id=outline.report_id)
    assert updated_outline.metadata["new_key"] == "new_value"
    assert updated_outline.metadata["status"] == "in_progress"
    assert updated_outline.metadata["original_key"] == "original_value"  # Preserved


@pytest.mark.asyncio
async def test_title_and_metadata_updates_together():
    """title_change and metadata_updates can be applied simultaneously."""
    outline = service.create_report(title="Old Title", template="default")

    result = await tool.execute(
        report_selector="Old Title",
        proposed_changes={
            "title_change": "New Title",
            "metadata_updates": {
                "author": "Claude",
                "version": "2.0"
            }
        }
    )

    assert result["status"] == "success"

    # Verify both changes applied
    updated_outline = service.get_report(report_id=outline.report_id)
    assert updated_outline.title == "New Title"
    assert updated_outline.metadata["author"] == "Claude"
    assert updated_outline.metadata["version"] == "2.0"


@pytest.mark.asyncio
async def test_outline_version_incremented_on_metadata_change():
    """Outline version increments when metadata is updated."""
    outline = service.create_report(title="Test Report", template="default")
    original_version = outline.outline_version

    await tool.execute(
        report_selector="Test Report",
        proposed_changes={"metadata_updates": {"key": "value"}}
    )

    updated_outline = service.get_report(report_id=outline.report_id)
    assert updated_outline.outline_version == original_version + 1
```

### Regression Testing

**Ensure existing functionality still works:**

```python
@pytest.mark.asyncio
async def test_status_change_still_works():
    """status_change is still applied correctly (handled at line 457)."""
    outline = service.create_report(title="Test Report", template="default")

    result = await tool.execute(
        report_selector="Test Report",
        proposed_changes={"status_change": "archived"}
    )

    assert result["status"] == "success"
    updated_outline = service.get_report(report_id=outline.report_id)
    assert updated_outline.metadata.get("status") == "archived"
```

## Acceptance Criteria

### Phase 1: Citation Enforcement

- [ ] Citation validation applies to ALL templates (default, analyst_v1, custom)
- [ ] Insights without `citations` or `supporting_queries` are rejected
- [ ] Insights without `execution_id` in first citation are rejected
- [ ] Error messages are clear and template-agnostic
- [ ] Opt-out mechanism works: `skip_citation_validation: true` in constraints
- [ ] Existing `analyst_v1` reports continue to work (backward compatibility)
- [ ] All Phase 1 tests pass

### Phase 2: Metadata Updates

- [ ] `title_change` is applied to `outline.title`
- [ ] `metadata_updates` are merged into `outline.metadata`
- [ ] Both changes can be applied simultaneously
- [ ] `outline_version` increments when metadata changes
- [ ] `updated_at` timestamp updates
- [ ] Changes are logged with structured logging
- [ ] `status_change` still works (no regression)
- [ ] All Phase 2 tests pass

### Documentation

- [ ] Update `/docs/api/tools/evolve_report.md` with new validation rules
- [ ] Update `/docs/living-reports/user-guide.md` to clarify citations are universal
- [ ] Update error catalog with new error messages
- [ ] Add migration guide for users with uncited reports

### Quality Gates

- [ ] All tests pass (unit, integration, regression)
- [ ] Code coverage maintains 80%+ for modified files
- [ ] Type checking passes (`uv run mypy src/`)
- [ ] Linting passes (`uv run ruff check .`)
- [ ] Pre-commit hooks pass

## Dependencies & Prerequisites

**None** - This is a standalone fix with no external dependencies.

**Files to Modify:**
1. `src/igloo_mcp/mcp/tools/evolve_report.py` (core logic)
2. `tests/test_evolve_report_tool.py` (test coverage)
3. `docs/api/tools/evolve_report.md` (documentation)
4. `docs/living-reports/user-guide.md` (user documentation)

## Risk Analysis & Mitigation

### Risk 1: Breaking Existing Uncited Reports

**Impact:** Users with existing default template reports that have uncited insights may fail validation when adding new insights.

**Mitigation:**
1. Citation validation only applies to NEW insights being added
2. Existing uncited insights are grandfathered (not re-validated)
3. Provide clear error messages with actionable hints
4. Document migration path for users to add citations retroactively
5. Opt-out mechanism allows emergency bypass if needed

### Risk 2: Performance Impact

**Impact:** Adding validation for all templates could slow down `evolve_report`.

**Mitigation:**
1. Validation is in-memory (no I/O operations)
2. Complexity is O(n) where n = number of insights being added
3. Typical operations have < 10 insights, so impact is negligible
4. No performance regression expected

### Risk 3: User Confusion from Error Messages

**Impact:** Users may not understand how to fix citation errors.

**Mitigation:**
1. Error messages include specific field names and required values
2. Hints suggest using `execute_query()` first to get `execution_id`
3. Documentation includes examples of proper citation format
4. Error catalog documents all validation errors with solutions

## Alternative Approaches Considered

### Alternative 1: Leave Citations Optional, Add Warnings

**Rejected because:**
- Warnings are easily ignored
- Doesn't address core issue: uncited claims undermine report credibility
- Creates two classes of reports (cited vs uncited) with no clear distinction

### Alternative 2: Add New "strict" Template

**Rejected because:**
- Adds complexity (yet another template)
- Doesn't fix existing default template reports
- Users must opt-in to data quality (should be default)

### Alternative 3: Make Templates Enforce Different Rules

**Rejected because:**
- Violates separation of concerns (templates = formatting, not validation)
- Creates inconsistent user experience
- Makes it unclear which template to use for different scenarios

**Selected Approach:**
- Enforce citations universally (with explicit opt-out)
- Templates control formatting only
- Clear, consistent user experience

## Success Metrics

**Immediate Metrics:**
1. Zero test failures in CI/CD pipeline
2. Code coverage maintains 80%+ for modified files
3. No mypy type errors introduced
4. Documentation updated and reviewed

**User Impact Metrics** (post-deployment):
1. Reduction in uncited insights from 100% → < 5% within 30 days
2. Zero user complaints about silent metadata update failures
3. Positive feedback on citation enforcement clarity

## Future Considerations

### Enhanced Citation Features (Out of Scope)

1. **Citation Auto-Population**: Automatically add citations based on query history
2. **Citation Validation**: Verify `execution_id` exists in query history
3. **Citation Analytics**: Show citation coverage % in report summaries
4. **Bulk Citation Addition**: Tool to add citations to existing uncited insights

### Metadata Schema Validation (Out of Scope)

1. Define allowed metadata keys via schema
2. Validate metadata value types
3. Prevent accidental metadata overwrites

## Documentation Plan

### User-Facing Documentation

**Files to Update:**
1. `/docs/api/tools/evolve_report.md`
   - Add citation requirements section
   - Update parameter descriptions for `title_change` and `metadata_updates`
   - Add examples of proper citations
   - Document opt-out mechanism

2. `/docs/living-reports/user-guide.md`
   - Clarify citations are required for ALL templates
   - Remove language suggesting citations are template-specific
   - Add section on adding citations to insights
   - Include troubleshooting guide for citation errors

3. `/docs/api/ERROR_CATALOG.md`
   - Add entry for citation validation errors
   - Include field paths and error messages
   - Provide resolution steps

### Migration Guide

**Create `/docs/migrations/v0.3.3-citation-enforcement.md`:**

```markdown
# Migration Guide: v0.3.3 Citation Enforcement

## Summary

Starting in v0.3.3, citation enforcement applies to ALL report templates, not just `analyst_v1`.

## What Changed

**Before (v0.3.2 and earlier):**
- Citations only enforced for `template="analyst_v1"` reports
- Default template reports could have uncited insights

**After (v0.3.3):**
- Citations required for ALL templates by default
- Insights without `execution_id` in citations are rejected

## Impact on Existing Reports

**Existing uncited insights:**
- Grandfathered (not re-validated)
- Can continue to exist in reports

**New insights:**
- Must include `citations` or `supporting_queries` with `execution_id`
- Validation errors provide clear guidance

## How to Add Citations

### Step 1: Execute Query and Get execution_id

```python
result = execute_query(
    statement="SELECT SUM(revenue) FROM sales WHERE date = CURRENT_DATE()",
    reason="Calculate today's revenue for report insight"
)

# Save the execution_id
execution_id = result["query_id"]
```

### Step 2: Include Citation in Insight

```python
evolve_report(
    report_selector="My Report",
    proposed_changes={
        "insights_to_add": [{
            "section_title": "Revenue",
            "summary": "Today's revenue is $50M",
            "content": "Detailed analysis...",
            "importance": 10,
            "tags": ["revenue"],
            "citations": [{
                "execution_id": execution_id,
                "database": "ANALYTICS_DB",
                "schema": "SALES",
                "table": "REVENUE_DAILY"
            }]
        }]
    }
)
```

## Opt-Out (Not Recommended)

If you absolutely need to bypass citation validation:

```python
evolve_report(
    report_selector="My Report",
    proposed_changes={...},
    constraints={"skip_citation_validation": True}
)
```

**Warning:** This undermines report reproducibility and should only be used for non-analytical content.

## Questions?

Open an issue at https://github.com/Evan-Kim2028/igloo-mcp/issues
```

## References

**GitHub Issues:**
- Issue #89: https://github.com/Evan-Kim2028/igloo-mcp/issues/89
- Issue #88: https://github.com/Evan-Kim2028/igloo-mcp/issues/88

**Related Files:**
- `/src/igloo_mcp/mcp/tools/evolve_report.py` (lines 711-790, 815-1256)
- `/src/igloo_mcp/living_reports/models.py` (Insight model, lines 169-194)
- `/src/igloo_mcp/living_reports/changes_schema.py` (ProposedChanges model)
- `/tests/test_evolve_report_tool.py` (existing test coverage)

**Related Conversations:**
- User discovered citation issue after completing 43-insight report
- Retroactive citation addition deemed impractical
- Issue #89 comments clarify citations must be universal requirement

---

**Priority:** HIGH
**Effort:** Medium (4-6 hours total for both fixes)
**Type:** Bug Fix + Enhancement
**Scope:** Core Living Reports functionality

**Target Release:** v0.3.3
