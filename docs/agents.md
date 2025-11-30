# Igloo-MCP Agent Guide

## 🚨 CRITICAL: Morph MCP Tool Usage Rules

**MANDATORY TOOL USAGE - These rules are NON-NEGOTIABLE:**

**Configuration Status:** ✅ ALL_TOOLS="true" enabled in Factory CLI (~/.factory/mcp.json)
**Global Reference:** See ~/.claude/CLAUDE.md for complete tool catalog and usage patterns

### File Editing: ALWAYS use `morph-fast-tools___edit_file`
- ✅ **DO**: Use `morph-fast-tools___edit_file` for ALL file modifications
- ❌ **NEVER**: Use `sed`, `awk`, `perl`, or other bash commands for file edits
- ❌ **NEVER**: Use the legacy `Edit` tool when Morph is available
- **Why**: Morph is 10,500+ tokens/sec, prevents context pollution, 98% success rate

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
- **Speed**: 10,500+ tokens/sec vs traditional editing
- **Accuracy**: 98% success rate with intelligent context handling
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
