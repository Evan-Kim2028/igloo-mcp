# Citation Backfill Plan for MON TGE Report

**Report ID**: `812fa95b-6d45-4d98-a99f-05adc14e133d`
**Total Insights**: 43
**Insights with Citations**: 0 (0%)
**Target**: 100% citation coverage

---

## Phase 1: Audit Current State

### Step 1.1: Extract All Insights with Metadata
**Goal**: Get complete list of insights needing citations

**Action**:
```bash
# Get all insights from report
get_report(
    report_selector="812fa95b-6d45-4d98-a99f-05adc14e133d",
    mode="insights"
)
```

**Output**: Create structured mapping file:
```json
{
    "insight_id": "...",
    "summary": "...",
    "section_title": "...",
    "importance": 10,
    "has_citations": false,
    "citation_count": 0
}
```

**Deliverable**: `insights_audit.json` (43 insights)

---

### Step 1.2: Analyze Query History
**Goal**: Build timeline of all queries executed during report creation

**Action**:
```bash
# Extract relevant queries from doc.jsonl
cat /Users/evandekim/.igloo_mcp/logs/doc.jsonl | \
  jq 'select(.status == "success" and .timestamp >= "2025-11-24")' | \
  jq '{execution_id, timestamp, reason, sql_sha256, tables}' > query_history.jsonl
```

**Filters**:
- Status: `success` only
- Date range: Nov 24-28, 2025 (report creation period)
- Must have: `execution_id` and `sql_sha256`

**Deliverable**: `query_history.jsonl` (all successful queries)

---

### Step 1.3: Map Insights to Queries
**Goal**: Match each insight to the query that generated its data

**Method**: Manual review with automated assistance

**Approach**:
1. Group insights by section
2. For each insight, identify the data claim (e.g., "$175.9M volume")
3. Search query history for matching `reason` or `sql_sha256`
4. Use query timestamp to narrow down candidates
5. Verify by reading SQL file from `/artifacts/queries/by_sha/{sha256}.sql`

**Tools**:
- Search by reason: `jq '.reason | contains("volume")' query_history.jsonl`
- Search by date: `jq 'select(.timestamp | startswith("2025-11-24"))' query_history.jsonl`
- Read SQL: `cat /Users/evandekim/.igloo_mcp/logs/artifacts/queries/by_sha/{sha256}.sql`

**Deliverable**: `insight_to_query_mapping.json`
```json
{
    "insight_id": "1073f89c-a7e9-4d09-afe4-abd43780a8d9",
    "summary": "Total Solana spot volume: $175.9M...",
    "execution_id": "abc123...",
    "sql_sha256": "def456...",
    "database": "MYSTEN_LABS__SOLANA",
    "schema": "DEX",
    "table": "TRADES",
    "confidence": "high|medium|low"
}
```

---

## Phase 2: Categorize Insights by Data Source

### Step 2.1: Group by Table Source
**Categories**:

1. **MYSTEN_LABS__SOLANA.DEX.TRADES** (Solana spot data)
   - Token verification
   - Solana spot volume
   - DEX market share
   - DEX routing patterns
   - Solana traders

2. **Hyperliquid API/Data** (Perps data)
   - Hyperliquid perps volume
   - Perps vs spot comparison
   - Price convergence analysis

3. **Cross-Platform** (Both sources)
   - Executive summary insights
   - Comparative analysis

4. **Derivative/Calculated** (No direct query)
   - Data limitations section
   - Methodology insights

---

### Step 2.2: Identify Citation Complexity
**Complexity Levels**:

**EASY** (Single query, direct metrics):
- Example: "Total Solana spot volume: $175.9M"
- Citation: One execution_id, straightforward mapping

**MEDIUM** (Multiple queries aggregated):
- Example: "Humidifi dominated with 40% market share"
- Citation: 2-3 execution_ids, may need to list all contributing queries

**HARD** (Calculated insights, no direct query):
- Example: "3-hour convergence validates perps price discovery"
- Citation: Requires citing the underlying hourly VWAP queries + manual calculation

**ESTIMATED** (No data, industry knowledge):
- Example: "20-40% failure rate typical for launches"
- Citation: External source or marked as "industry estimate"

---

## Phase 3: Execute Citation Backfill

### Step 3.1: Prepare Citation Payloads
**Goal**: Create `evolve_report()` payloads for each insight

**Template**:
```json
{
    "insights_to_modify": [
        {
            "insight_id": "1073f89c-a7e9-4d09-afe4-abd43780a8d9",
            "citations": [
                {
                    "execution_id": "abc123def456...",
                    "database": "MYSTEN_LABS__SOLANA",
                    "schema": "DEX",
                    "table": "TRADES"
                }
            ]
        }
    ]
}
```

**Batch Strategy**: Group insights by section for efficient updates
- Batch 1: Token Verification (1 insight)
- Batch 2: Hyperliquid Perps (4 insights)
- Batch 3: Solana Spot Volume (6 insights)
- Batch 4: DEX Market Share (6 insights)
- Batch 5: Perps vs Spot (8 insights)
- Batch 6: DEX Routing Patterns (7 insights)
- Batch 7: Solana Traders (4 insights)
- Batch 8: Data Limitations (3 insights)
- Batch 9: Executive Summary (4 insights)

---

### Step 3.2: Execute Updates in Batches
**Process** (per batch):

1. **Prepare payload**:
   ```python
   evolve_report(
       report_selector="812fa95b-6d45-4d98-a99f-05adc14e133d",
       instruction="Add citations to [Section Name] insights",
       proposed_changes={
           "insights_to_modify": [
               {
                   "insight_id": "...",
                   "citations": [{"execution_id": "..."}]
               },
               # ... more insights in this batch
           ]
       }
   )
   ```

2. **Validate** after each batch:
   ```python
   get_report(
       report_selector="812fa95b-6d45-4d98-a99f-05adc14e133d",
       mode="insights",
       section_ids=["section_id_for_batch"]
   )
   ```

3. **Verify** `has_citations: true` and `citation_count > 0`

---

### Step 3.3: Handle Special Cases

#### Case 1: Multi-Query Insights
**Example**: "Multi-hop trades represent 34% of transactions but 49.6% of volume"

**Citation Strategy**: Include ALL contributing queries
```json
{
    "citations": [
        {
            "execution_id": "query_1_txn_classification",
            "database": "MYSTEN_LABS__SOLANA",
            "schema": "DEX",
            "table": "TRADES"
        },
        {
            "execution_id": "query_2_volume_aggregation",
            "database": "MYSTEN_LABS__SOLANA",
            "schema": "DEX",
            "table": "TRADES"
        }
    ]
}
```

#### Case 2: Calculated/Derived Insights
**Example**: "Perps achieved price stability in 16 minutes"

**Citation Strategy**: Cite the raw data query + note calculation in content
```json
{
    "citations": [
        {
            "execution_id": "minute_level_vwap_query",
            "database": "HYPERLIQUID",
            "note": "Stability calculated as stddev(VWAP) < 0.001"
        }
    ]
}
```

#### Case 3: External/Estimated Data
**Example**: "Estimated 20-40% failure rate based on typical launches"

**Citation Strategy**: Use `note` field for provenance
```json
{
    "citations": [
        {
            "note": "Industry estimate based on historical Solana token launch patterns (no direct data available)"
        }
    ]
}
```

---

## Phase 4: Validation & Quality Assurance

### Step 4.1: Run Citation Coverage Report
**Goal**: Verify 100% citation coverage

**Check**:
```python
get_report(
    report_selector="812fa95b-6d45-4d98-a99f-05adc14e133d",
    mode="insights"
)
```

**Metrics**:
- Total insights: 43
- Insights with citations: **43** (target: 100%)
- Average citations per insight: ≥1.0
- Sections with 0% coverage: **0**

---

### Step 4.2: Verify Citation Quality
**Manual Spot Checks** (10% sample = 4-5 insights):

For each sampled insight:
1. Read the cited SQL query from `/artifacts/queries/by_sha/{sha}.sql`
2. Verify the query actually produces the claimed metric
3. Check execution_id exists in `doc.jsonl`
4. Confirm database/schema/table are correct

**Quality Criteria**:
- ✅ Execution ID is valid and traceable
- ✅ SQL query matches the insight's claim
- ✅ Database provenance is accurate
- ✅ No placeholder or fake execution IDs

---

### Step 4.3: Generate Audit Trail
**Deliverable**: `citation_backfill_audit.md`

**Contents**:
```markdown
# Citation Backfill Audit - MON TGE Report

**Date**: 2025-11-28
**Report ID**: 812fa95b-6d45-4d98-a99f-05adc14e133d
**Performer**: [Your Name/Droid]

## Summary
- Total insights: 43
- Citations added: 43
- Success rate: 100%
- Time taken: [X hours]

## Breakdown by Section
| Section | Insights | Citations Added | Status |
|---------|----------|----------------|--------|
| Executive Summary | 4 | 4 | ✅ Complete |
| Token Verification | 1 | 1 | ✅ Complete |
| Hyperliquid Perps | 4 | 4 | ✅ Complete |
| ... | ... | ... | ... |

## Special Cases Handled
1. Multi-query insights: 7 insights with 2+ citations
2. Calculated metrics: 3 insights with calculation notes
3. External estimates: 3 insights with industry benchmarks

## Quality Assurance
- Spot check sample: 5 insights (11.6%)
- Verification pass rate: 100%
- Issues found: 0

## Changes Made
- Outline version: 32 → [new version]
- Report updated: 2025-11-28 [timestamp]
```

---

## Phase 5: Documentation & Lessons Learned

### Step 5.1: Update Report Metadata
**Add to report description**:
```markdown
**Citation Completeness**: All 43 insights include source citations with execution IDs linking to query artifacts. Citations added retroactively on 2025-11-28 following discovery of template-specific citation enforcement bug (#89).
```

---

### Step 5.2: Document Process Improvements
**Lessons for Future Reports**:

1. **Use `analyst_v1` template** until citation enforcement is universal
2. **Add citations during insight creation**, not retroactively
3. **Keep mapping file** of insights → queries during analysis
4. **Use descriptive query reasons** to aid future citation mapping
5. **Test citation coverage early** (after first 10 insights)

---

## Execution Timeline

**Estimated Time**: 4-6 hours total

| Phase | Duration | Tasks |
|-------|----------|-------|
| Phase 1 | 1-1.5 hours | Audit state, extract query history, build mapping |
| Phase 2 | 0.5 hours | Categorize insights, assess complexity |
| Phase 3 | 2-3 hours | Execute citation backfill in batches |
| Phase 4 | 0.5-1 hour | Validation, spot checks, audit trail |
| Phase 5 | 0.5 hours | Documentation, lessons learned |

---

## Success Criteria

### Must Have ✅
- [ ] All 43 insights have `has_citations: true`
- [ ] All 43 insights have `citation_count >= 1`
- [ ] All execution IDs are valid and traceable
- [ ] All database/schema/table fields are accurate

### Should Have 🎯
- [ ] Average 1.2 citations per insight (multi-query insights boost average)
- [ ] 100% spot check verification pass rate
- [ ] Complete audit trail document
- [ ] Process documentation for future reports

### Nice to Have 💡
- [ ] Automated script for future citation backfills
- [ ] Template for insight → query mapping
- [ ] Citation quality scoring system

---

## Risk Mitigation

### Risk 1: Cannot Find Source Query
**Mitigation**:
- Search by multiple criteria (reason, timestamp, tables used)
- Review SQL file content to match metrics
- Worst case: Re-run query if logic is clear, cite new execution_id

### Risk 2: Insight Based on Multiple Queries
**Mitigation**:
- Include ALL contributing queries in citations array
- Add note field explaining aggregation logic
- Document in content which metric came from which query

### Risk 3: External/Estimated Data
**Mitigation**:
- Use citation note field for provenance
- Clearly mark as "industry estimate" or "external source"
- Consider lowering importance score for uncitable claims

### Risk 4: Breaking Report During Updates
**Mitigation**:
- Update in small batches (max 10 insights per batch)
- Validate after each batch before proceeding
- Keep backup of outline before starting

---

## Next Steps

1. ✅ **Plan complete** - Review and approve this plan
2. ⏭️ **Phase 1.1** - Extract all insights from report
3. ⏭️ **Phase 1.2** - Build query history from doc.jsonl
4. ⏭️ **Phase 1.3** - Map insights to queries (most time-consuming)
5. ⏭️ **Execute Phases 2-5** following timeline above

**Ready to begin?**
