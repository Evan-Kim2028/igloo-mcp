# Igloo-MCP Agent Guide

## 🚨 CRITICAL: Morph MCP Tool Usage Rules

**MANDATORY TOOL USAGE - These rules are NON-NEGOTIABLE:**

**Configuration Status:** ✅ ALL_TOOLS="true" enabled in Factory CLI (~/.factory/mcp.json)
**Global Reference:** See ~/.claude/CLAUDE.md for complete tool catalog and usage patterns

### File Editing: ALWAYS use `morph-fast-tools___edit_file`
- ✅ **DO**: Use `morph-fast-tools___edit_file` for ALL file modifications
- ❌ **NEVER**: Use `sed`, `awk`, `perl`, or other bash commands for file edits
- ❌ **NEVER**: Use the legacy `Edit` tool when Morph is available
- **Why**: Fast editing, prevents context pollution, high accuracy

### Code Search: ALWAYS use `morph-fast-tools___warp_grep`
- ✅ **DO**: Use `morph-fast-tools___warp_grep` for ALL code searches and exploration
- ❌ **NEVER**: Use `grep`, `rg`, `find`, or bash commands for code searching
- ❌ **NEVER**: Read entire files with `Read` tool when searching for specific code
- **Why**: AI-powered search finds exact code with context, no unnecessary file reads

### Web Search: ALWAYS use `exa___web_search_exa`
- ✅ **DO**: Use `exa___web_search_exa` for ALL web searches and online documentation research
- ❌ **NEVER**: Use legacy `WebSearch` tool or curl/wget for web scraping
- **Why**: AI-powered semantic search with live web content optimized for LLM consumption

### Performance Benefits
- **Speed**: Fast token processing vs traditional editing
- **Accuracy**: High success rate with intelligent context handling
- **Efficiency**: Only changed lines shown, no context pollution
- **Intelligence**: AI-powered code understanding and precise targeting

### Example Usage
```bash
# ✅ CORRECT - File editing
morph-fast-tools___edit_file(path="...", code_edit="...", instruction="...")

# ✅ CORRECT - Code search
morph-fast-tools___warp_grep(repoPath="...", query="Find JWT validation logic")

# ❌ WRONG - Don't use these
Edit(file_path="...", old_str="...", new_str="...")  # Legacy tool
Execute(command="sed -i 's/old/new/' file.py")      # Bash editing
Grep(pattern="JWT", ...)                             # Basic grep
Read(file_path="...")                                # Blind file reading
```

---

## 💡 Pro Tips: Tool Selection Decision Trees

### File Editing: When to Batch vs Split
**Rule:** Perform edits to one file in a single `morph-fast-tools___edit_file` call instead of multiple.
- ✅ **DO**: Make all changes to a single file in one edit_file call
- ❌ **NEVER**: Split edits to the same file across multiple tool invocations
- **Why**: Faster execution, prevents merge conflicts, maintains atomic changes
- **Example**: If updating imports, function signature, and docstring in `utils.py`, do all three edits in one call

### Code Search: grep vs warp_grep Decision Tree
**Question: Can you write the exact pattern to search for?**

- **YES → Use `Grep`** (100ms, instant results)
  - Example: "Find all occurrences of `execute_query(`"
  - Example: "Search for `from igloo_mcp import` statements"
  - Example: "Find FIXME comments in tests/"
  - **When**: You know the exact string/regex pattern to match

- **NO → Use `morph-fast-tools___warp_grep`** (5-10s, worth it for complex queries!)
  - Example: "How is the Living Reports cache invalidated?"
  - Example: "Where are Snowflake connection credentials validated?"
  - Example: "What files implement the query result modes?"
  - **When**:
    - Asking "how/where/what" questions about code behavior
    - Query spans 3+ files or crosses architectural boundaries
    - Tracing data/execution flow through the codebase
    - Understanding unfamiliar code patterns or architecture
    - Need contextual understanding, not just literal matches

**Rule of thumb:** If your search query is a natural language question, use `warp_grep`. If it's a literal string or regex pattern, use `Grep`.

---

## Querying Allium Data

 ## Issue Recap
 Imported Allium shares (e.g., MYSTEN_LABS__HYPERLIQUID) use **secure views** (DEX.TRADES) over raw tables (RAW.TRADES, 1B+ rows).
 INFORMATION_SCHEMA.TABLES lists tables only; views missed until `build_catalog`.
 Tool new-session-per-call requires **full qualification** (DB.SCHEMA.VIEW).
 `SHOW TABLES` blocked as 'Command'; use SELECT or DESCRIBE VIEW.

 ## Best Practices
 1. **build_catalog database=MYSTEN_LABS__HYPERLIQUID include_ddl=true** – reveals views/tables/DDL.
 2. **DESCRIBE VIEW DB.SCHEMA.TRADES** – schema (MARKET_TYPE, COIN, USD_AMOUNT, TIMESTAMP).
 3. Query fully qualified: `SELECT SUM(USD_AMOUNT) FROM MYSTEN_LABS__HYPERLIQUID.DEX.TRADES WHERE TIMESTAMP >= DATEADD(DAY, -7, CURRENT_TIMESTAMP()) AND COIN ILIKE '%BTC%' AND MARKET_TYPE='spot' GROUP BY COIN;`
 4. For Solana: TOKEN_SOLD_SYMBOL ILIKE '%BTC%', USD_SOLD_AMOUNT + USD_BOUGHT_AMOUNT.
 5. Daily corr: `date_trunc('day', TIMESTAMP)`, CORR(hyp_vol, sol_vol).

 ## BTC Volumes Example (Hyperliquid Spot/UNIT)
 ```
 SELECT COIN, MARKET_TYPE, SUM(USD_AMOUNT) vol_usd, COUNT(*) trades
 FROM MYSTEN_LABS__HYPERLIQUID.DEX.TRADES
 WHERE TIMESTAMP >= DATEADD(DAY, -7, CURRENT_TIMESTAMP())
   AND COIN ILIKE '%BTC%' AND MARKET_TYPE IN ('spot', 'unit')
 GROUP BY 1,2 ORDER BY vol_usd DESC LIMIT 10;
 ```

 Avoid: Table-only searches, unqualified names, multi-stmts, SHOW without IN.

 Success: Catalog first → qualify → query views → aggregate BTC spot vols/corr.

---

## 💡 Progressive Disclosure Best Practices

**Token Efficiency**: Use `response_mode` to control query result verbosity and save 60-95% tokens.

### Default Behavior
```python
# execute_query defaults to 'summary' mode (5 sample rows + metadata)
execute_query(
    "SELECT * FROM large_table",
    reason="Explore schema and data"
)
# Returns: 5 sample rows + key_metrics + hint for full retrieval
```

### Recommended Workflow Pattern

**1. Start with Schema Discovery**
```python
# Step 1: Discover structure (95% token savings)
execute_query(
    "SELECT * FROM sui.dex.trades",
    reason="Check schema",
    response_mode="schema_only"
)
# Returns: Column names + types, no rows
```

**2. Validate with Summary**
```python
# Step 2: Validate data quality (90% token savings - DEFAULT)
execute_query(
    "SELECT * FROM sui.dex.trades WHERE coin ILIKE '%SUI%'",
    reason="Validate SUI trades exist"
)
# Defaults to response_mode='summary' - returns 5 sample rows + metrics
```

**3. Full Export Only When Needed**
```python
# Step 3: Export final results (only when necessary)
execute_query(
    "SELECT date, SUM(volume) FROM sui.dex.trades GROUP BY 1 ORDER BY 1",
    reason="Export daily volumes",
    response_mode="full"
)
# Returns: All rows (no truncation)
```

### Response Mode Cheat Sheet

| Mode | When to Use | Token Savings |
|------|-------------|---------------|
| `schema_only` | "What columns exist?" | 95% |
| `summary` | "What's in the data?" (DEFAULT) | 90% |
| `sample` | "Show me 10 examples" | 60-80% |
| `full` | "Export all results" | baseline |

### Reading `result_mode_info` Hints

When using non-`full` modes, responses include guidance:

```python
result = execute_query(
    "SELECT * FROM big_table",
    reason="exploration"
)

print(result['result_mode_info'])
# Output:
# {
#   "mode": "summary",
#   "total_rows": 2100,
#   "rows_returned": 5,
#   "sample_size": 5,
#   "hint": "Showing first 5 of 2100 rows. Use response_mode='full' to retrieve all rows"
# }

# Follow the hint if you need all rows:
full_result = execute_query(
    "SELECT * FROM big_table",
    reason="full export",
    response_mode="full"
)
```

### Anti-Patterns to Avoid

❌ **Don't request `full` by default**
```python
# BAD: Wastes tokens on large results
execute_query(
    "SELECT * FROM million_row_table",
    reason="explore",
    response_mode="full"  # ← Don't do this for exploration
)
```

✅ **Do use progressive disclosure**
```python
# GOOD: Start minimal, drill down
execute_query(
    "SELECT * FROM million_row_table",
    reason="explore schema",
    response_mode="schema_only"  # ← Start here
)
# Then add filters and use summary/full as needed
```

---

## 📋 Version Naming Convention

**Rule**: Version names should be **functional and descriptive**, clearly indicating what the upgrade delivers.

### ✅ Good Names (Descriptive)
- `v0.3.5 - Result Modes & Batch Reports`
- `v0.3.4 - Living Reports & Query Caching`
- `v0.4.0 - Citations & HTML Standalone`

### ❌ Bad Names (Vague)
- `v0.3.5 - Morph-Inspired Enhancements` (doesn't say what it does)
- `v0.4.0 - Performance Improvements` (too generic)
- `v0.3.6 - Bug Fixes and Updates` (uninformative)

### Format
```
v{major}.{minor}.{patch} - {Feature 1} & {Feature 2}
```

### Guidelines
1. **Be specific**: Name the actual features/capabilities added
2. **Max 2-3 key features**: Don't list everything, just the highlights
3. **Use & for multiple**: "Result Modes & Batch Reports" not "Result Modes, Batch Reports, and..."
4. **Avoid buzzwords**: No "Enhanced", "Improved", "Better" without specifics
5. **Think user-facing**: What does the user get? Name that.
