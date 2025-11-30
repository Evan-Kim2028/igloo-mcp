# Citation System

Citations provide traceability for insights by linking to data sources. Every insight should cite where its information comes from—whether that's a Snowflake query, external API, web article, manual observation, or document.

## Why Citations Matter

**Data Quality**: Citations enable verification and reproducibility
**Audit Trail**: Track where insights originate for compliance
**Credibility**: Backed-up claims are more trustworthy
**Discovery**: Find all insights using a specific source

## Citation Types

Igloo MCP supports 5 citation types to cover all research workflows:

| Type | Use For | Common Providers |
|------|---------|------------------|
| `query` | SQL database queries | snowflake, allium, dune, flipside |
| `api` | REST/GraphQL API calls | defillama, coingecko, etherscan |
| `url` | Web pages, articles, blogs | Any website |
| `observation` | Manual/visual analysis | Human judgment, charts |
| `document` | Files, PDFs, whitepapers | Local files, drives |

## Quick Start

### Query Citation (Snowflake)

```python
# Execute query and get execution_id
result = execute_query(
    statement="SELECT SUM(amount) FROM orders WHERE date >= '2025-01-01'",
    reason="Q1 revenue analysis"
)
exec_id = result["execution_id"]

# Add insight with query citation
evolve_report(
    report_selector="Q1 Report",
    instruction="Add revenue insight with query citation",
    proposed_changes={
        "insights_to_add": [{
            "summary": "Q1 revenue reached $2.4M, up 25% YoY",
            "importance": 9,
            "citations": [{
                "source": "query",
                "provider": "snowflake",
                "execution_id": exec_id,
                "description": "Q1 revenue aggregation"
            }]
        }]
    }
)
```

### URL Citation (Web Source)

```python
evolve_report(
    report_selector="Market Research",
    instruction="Add insight from official announcement",
    proposed_changes={
        "insights_to_add": [{
            "summary": "Monad TGE announced for Q1 2025",
            "importance": 8,
            "citations": [{
                "source": "url",
                "url": "https://monad.xyz/blog/tge-announcement",
                "title": "Official TGE Announcement",
                "accessed_at": "2025-11-30T10:00:00Z",
                "description": "Official blog post confirming TGE timeline"
            }]
        }]
    }
)
```

### API Citation (External Data)

```python
evolve_report(
    report_selector="DeFi Analysis",
    instruction="Add TVL data from DeFiLlama",
    proposed_changes={
        "insights_to_add": [{
            "summary": "Protocol TVL reached $150M",
            "importance": 7,
            "citations": [{
                "source": "api",
                "provider": "defillama",
                "endpoint": "/tvl/monad",
                "description": "Current TVL data pull"
            }]
        }]
    }
)
```

### Observation Citation (Manual Analysis)

```python
evolve_report(
    report_selector="Trading Analysis",
    instruction="Add observation from price chart",
    proposed_changes={
        "insights_to_add": [{
            "summary": "Price spike coincided with announcement",
            "importance": 6,
            "citations": [{
                "source": "observation",
                "description": "Visible spike on DexScreener 15min chart",
                "observed_at": "2025-11-30T14:30:00Z"
            }]
        }]
    }
)
```

### Document Citation (Research Papers)

```python
evolve_report(
    report_selector="Tokenomics Review",
    instruction="Add insight from whitepaper",
    proposed_changes={
        "insights_to_add": [{
            "summary": "70% of tokens allocated to community",
            "importance": 9,
            "citations": [{
                "source": "document",
                "path": "/docs/monad-whitepaper.pdf",
                "page": "12",
                "title": "Monad Tokenomics Whitepaper",
                "description": "Token allocation breakdown"
            }]
        }]
    }
)
```

## Citation Fields Reference

### Common Fields (All Types)

```python
{
    "source": str,        # REQUIRED: "query", "api", "url", "observation", "document"
    "provider": str,      # Optional: "snowflake", "allium", "defillama", etc.
    "description": str,   # Optional: Human-readable context
}
```

### Query-Specific Fields

```python
{
    "source": "query",
    "provider": "snowflake",          # snowflake, allium, dune, etc.
    "execution_id": str,              # From query history
    "query_id": str,                  # For external platforms (Allium, Dune)
    "sql_sha256": str,                # SQL hash for deduplication
    "cache_manifest": str,            # Path to cached results
    "description": str,               # What query does
}
```

### URL-Specific Fields

```python
{
    "source": "url",
    "url": str,                       # RECOMMENDED: Full URL
    "title": str,                     # Page/article title
    "accessed_at": str,               # ISO 8601 timestamp
    "description": str,               # Why this source matters
}
```

### API-Specific Fields

```python
{
    "source": "api",
    "provider": str,                  # defillama, coingecko, etc.
    "endpoint": str,                  # API path (e.g., "/tvl/monad")
    "response_hash": str,             # Optional: hash for verification
    "description": str,               # What data was retrieved
}
```

### Document-Specific Fields

```python
{
    "source": "document",
    "path": str,                      # File path (absolute recommended)
    "page": str,                      # Page number/section
    "title": str,                     # Document title
    "description": str,               # Relevant content summary
}
```

### Observation-Specific Fields

```python
{
    "source": "observation",
    "description": str,               # RECOMMENDED: What was observed
    "observed_at": str,               # ISO 8601 timestamp
}
```

## Migration from supporting_queries

Igloo MCP automatically migrates legacy `supporting_queries` to `citations`:

### Old Way (Deprecated)

```python
{
    "summary": "Revenue grew 25% YoY",
    "supporting_queries": [{
        "execution_id": "exec-123",
        "sql_sha256": "abc..."
    }]
}
```

### New Way (Recommended)

```python
{
    "summary": "Revenue grew 25% YoY",
    "citations": [{
        "source": "query",
        "provider": "snowflake",
        "execution_id": "exec-123",
        "sql_sha256": "abc...",
        "description": "Revenue aggregation query"
    }]
}
```

**Migration is automatic**:
- Old reports with `supporting_queries` work unchanged
- `supporting_queries` auto-converts to `citations` on read
- Query citations auto-convert back to `supporting_queries` for legacy tools

**No breaking changes**: Existing workflows continue working.

## Validation Rules

**Every insight requires at least one citation**:

```python
# ❌ This fails validation
{
    "summary": "Revenue grew 25%",
    "citations": []  # Empty - validation error
}

# ✅ This passes
{
    "summary": "Revenue grew 25%",
    "citations": [{
        "source": "observation",
        "description": "Known from internal dashboard"
    }]
}
```

**Minimal valid citation**:

```python
# Simplest possible citation
{
    "source": "observation",
    "description": "Common knowledge in the industry"
}
```

## Best Practices by Use Case

### Data Analysis Reports

**Use**: `query` citations for all SQL-backed insights

```python
{
    "summary": "Top 10 customers account for 40% of revenue",
    "citations": [{
        "source": "query",
        "provider": "snowflake",
        "execution_id": "exec-456",
        "description": "Customer revenue ranking query"
    }]
}
```

### Market Research

**Use**: Mix of `url`, `api`, and `observation` citations

```python
{
    "summary": "Competitor launched similar feature last month",
    "citations": [
        {
            "source": "url",
            "url": "https://competitor.com/blog/feature-launch",
            "title": "Feature Launch Announcement"
        },
        {
            "source": "observation",
            "description": "Confirmed by testing their product"
        }
    ]
}
```

### Blockchain Analysis

**Use**: `query` (Allium/Dune) + `api` (DeFiLlama) + `url` (announcements)

```python
{
    "summary": "DEX volume spiked 300% after listing",
    "citations": [
        {
            "source": "query",
            "provider": "allium",
            "query_id": "q_abc123",
            "description": "Sui DEX trades aggregation"
        },
        {
            "source": "url",
            "url": "https://dex.xyz/listings/new",
            "title": "New Listing Announcement"
        }
    ]
}
```

### Whitepaper Reviews

**Use**: `document` citations with page numbers

```python
{
    "summary": "Staking rewards capped at 8% APY",
    "citations": [{
        "source": "document",
        "path": "/docs/protocol-whitepaper.pdf",
        "page": "18",
        "title": "Protocol Whitepaper v2.1",
        "description": "Staking economics section"
    }]
}
```

## Rendered Output

Citations appear grouped by type in report appendices:

### HTML Standalone

```
## Data Sources

### Query Executions
[1] Revenue aggregation (Snowflake: exec-123)
    - Executed: 2025-11-30T10:00:00Z
    - Duration: 1.2s
    - Rows: 1,247

### Web Sources
[2] Official TGE Announcement
    - URL: https://monad.xyz/blog/tge
    - Accessed: 2025-11-30

### API Sources
[3] DeFiLlama TVL data
    - Endpoint: /tvl/monad
```

### Quarto PDF

Citations render as numbered references with footnotes:

```markdown
Revenue grew 25% YoY [1], confirmed by official announcement [2].

## References
[1] Query: exec-123 (Snowflake)
[2] https://monad.xyz/blog/tge
```

## Common Workflows

### Workflow 1: SQL Analysis Report

```python
# 1. Run queries
revenue_result = execute_query(
    statement="SELECT SUM(amount) FROM orders...",
    reason="Revenue analysis"
)

customers_result = execute_query(
    statement="SELECT COUNT(DISTINCT user_id) FROM orders...",
    reason="Customer count"
)

# 2. Create insights with query citations
evolve_report(
    report_selector="Q1 Analysis",
    instruction="Add SQL-backed insights",
    proposed_changes={
        "insights_to_add": [
            {
                "summary": "Revenue: $2.4M",
                "importance": 10,
                "citations": [{
                    "source": "query",
                    "provider": "snowflake",
                    "execution_id": revenue_result["execution_id"]
                }]
            },
            {
                "summary": "1,247 active customers",
                "importance": 8,
                "citations": [{
                    "source": "query",
                    "provider": "snowflake",
                    "execution_id": customers_result["execution_id"]
                }]
            }
        ]
    }
)
```

### Workflow 2: Multi-Source Research

```python
# Combine SQL + web + API sources
evolve_report(
    report_selector="Market Analysis",
    instruction="Add multi-source insight",
    proposed_changes={
        "insights_to_add": [{
            "summary": "TVL reached $150M following announcement",
            "importance": 9,
            "citations": [
                {
                    "source": "query",
                    "provider": "allium",
                    "query_id": "tvl_query_123",
                    "description": "On-chain TVL calculation"
                },
                {
                    "source": "api",
                    "provider": "defillama",
                    "endpoint": "/tvl/protocol",
                    "description": "Third-party TVL verification"
                },
                {
                    "source": "url",
                    "url": "https://protocol.xyz/blog/tvl-milestone",
                    "title": "Official TVL Milestone Announcement"
                }
            ]
        }]
    }
)
```

### Workflow 3: Citation Audit

Find all insights using a specific source:

```python
# Find all DeFiLlama citations
results = search_citations(
    provider="defillama",
    group_by="provider"
)

print(f"Found {results['matches_found']} insights using DeFiLlama")
for cit in results['citations']:
    print(f"- {cit['insight']['summary']} (in {cit['report']['title']})")
```

## Troubleshooting

### Citation Validation Fails

**Problem**: Error: "At least one citation required"

**Solution**: Add minimal citation:

```python
"citations": [{
    "source": "observation",
    "description": "Based on team knowledge"
}]
```

### Wrong Citation Type

**Problem**: Used `url` for a query

**Solution**: Match source type to actual source:

```python
# ❌ Wrong
{"source": "url", "execution_id": "exec-123"}

# ✅ Correct
{"source": "query", "execution_id": "exec-123"}
```

### Missing Provider

**Problem**: Citation lacks context

**Solution**: Add provider and description:

```python
# ❌ Minimal context
{"source": "query", "execution_id": "exec-123"}

# ✅ Better context
{
    "source": "query",
    "provider": "snowflake",
    "execution_id": "exec-123",
    "description": "Customer revenue ranking analysis"
}
```

## Related Topics

- **[Citation Search](./citation-search.md)**: Find insights by source
- **[Charts](./charts.md)**: Attach visual evidence
- **[User Guide](./user-guide.md)**: Complete Living Reports overview
