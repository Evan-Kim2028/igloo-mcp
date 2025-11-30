# Citation Search

Find insights backed by specific sources across all your reports. Citation search enables powerful audit workflows, source verification, and discovery of related research.

## Quick Start

```python
# Find all insights citing DeFiLlama
results = search_citations(provider="defillama")

print(f"Found {results['matches_found']} insights")
for cit in results['citations']:
    insight = cit['insight']
    report = cit['report']
    print(f"- {insight['summary']}")
    print(f"  Report: {report['title']}")
```

## Search Filters

### By Source Type

Find all insights using a specific citation type:

```python
# Query citations (SQL databases)
search_citations(source_type="query")

# URL citations (web sources)
search_citations(source_type="url")

# API citations (external APIs)
search_citations(source_type="api")

# Observations (manual analysis)
search_citations(source_type="observation")

# Documents (PDFs, whitepapers)
search_citations(source_type="document")
```

### By Provider

Find all insights from a specific data provider:

```python
# Snowflake queries
search_citations(provider="snowflake")

# DeFiLlama API
search_citations(provider="defillama")

# Allium queries
search_citations(provider="allium")

# CoinGecko API
search_citations(provider="coingecko")
```

### By URL Pattern

Find all insights citing URLs matching a pattern:

```python
# All monad.xyz citations
search_citations(url_contains="monad.xyz")

# All Medium articles
search_citations(url_contains="medium.com")

# Specific blog
search_citations(url_contains="example.com/blog")
```

### By Description

Search citation descriptions:

```python
# Find TVL-related citations
search_citations(description_contains="tvl")

# Find revenue analyses
search_citations(description_contains="revenue")
```

### By Execution ID

Find insights backed by a specific query:

```python
# Exact match on execution_id
search_citations(execution_id="exec-550e8400-...")
```

## Grouping Results

### Group by Source Type

See citation distribution across types:

```python
results = search_citations(group_by="source")

# Results structure:
{
    "matches_found": 45,
    "grouped_results": {
        "groups": {
            "query": [...],  # 20 query citations
            "url": [...],    # 15 URL citations
            "api": [...]     # 10 API citations
        },
        "summary": {
            "query": 20,
            "url": 15,
            "api": 10
        }
    }
}
```

### Group by Provider

Audit which providers you're using:

```python
results = search_citations(group_by="provider")

# Results structure:
{
    "grouped_results": {
        "groups": {
            "snowflake": [...],  # 25 citations
            "defillama": [...],  # 12 citations
            "allium": [...]      # 8 citations
        },
        "summary": {
            "snowflake": 25,
            "defillama": 12,
            "allium": 8
        }
    }
}
```

## Result Structure

Each result includes full context:

```python
{
    "status": "success",
    "matches_found": 10,
    "returned": 10,
    "citations": [
        {
            "citation": {
                "source": "query",
                "provider": "snowflake",
                "execution_id": "exec-123",
                "description": "Revenue analysis"
            },
            "insight": {
                "insight_id": "550e8400-...",
                "summary": "Revenue grew 25% YoY",
                "importance": 9
            },
            "report": {
                "report_id": "rpt-abc...",
                "title": "Q1 Revenue Report"
            }
        },
        // ... more results
    ],
    "timing": {
        "total_duration_ms": 45.2
    }
}
```

## Common Use Cases

### Use Case 1: Source Audit

Verify what sources back your research:

```python
# Get all sources grouped
results = search_citations(group_by="provider")

print("Data Sources Audit:")
for provider, count in results['grouped_results']['summary'].items():
    print(f"- {provider}: {count} insights")

# Output:
# Data Sources Audit:
# - snowflake: 45 insights
# - defillama: 23 insights
# - allium: 12 insights
# - manual: 8 insights
```

### Use Case 2: Find Related Research

Find all insights using a specific source:

```python
# Find all research citing a whitepaper
results = search_citations(
    source_type="document",
    description_contains="whitepaper"
)

print(f"Found {results['matches_found']} whitepaper-backed insights:")
for cit in results['citations']:
    doc = cit['citation']
    insight = cit['insight']
    print(f"- {insight['summary']}")
    print(f"  Source: {doc.get('title', doc.get('path'))}")
```

### Use Case 3: Query Impact Analysis

See which insights depend on a specific query:

```python
# Find all insights using a query
results = search_citations(execution_id="exec-123")

if results['matches_found'] > 0:
    print(f"Query exec-123 backs {results['matches_found']} insights:")
    for cit in results['citations']:
        print(f"- {cit['insight']['summary']}")
        print(f"  Report: {cit['report']['title']}")
else:
    print("Query exec-123 is not cited in any insights")
```

### Use Case 4: External Source Tracking

Track usage of external APIs/URLs:

```python
# Find all DeFiLlama usage
defi_results = search_citations(provider="defillama", group_by="provider")

# Find all blog citations
blog_results = search_citations(source_type="url", url_contains="blog")

print(f"DeFiLlama API: {defi_results['matches_found']} insights")
print(f"Blog articles: {blog_results['matches_found']} insights")
```

### Use Case 5: Compliance Review

Generate citation report for compliance:

```python
# Get all citations grouped by source
results = search_citations(group_by="source", limit=200)

print("=== Citation Compliance Report ===\n")

for source_type, citations in results['grouped_results']['groups'].items():
    print(f"{source_type.upper()}: {len(citations)} citations")

    for cit in citations[:5]:  # Show top 5
        citation = cit['citation']
        insight = cit['insight']

        print(f"  - {insight['summary'][:60]}...")
        if 'url' in citation:
            print(f"    URL: {citation['url']}")
        elif 'execution_id' in citation:
            print(f"    Query: {citation['execution_id']}")

    if len(citations) > 5:
        print(f"  ... and {len(citations) - 5} more")
    print()
```

## Pagination

Control result size with `limit`:

```python
# First 10 results
page1 = search_citations(provider="snowflake", limit=10)

# Get all (up to 200)
all_results = search_citations(provider="snowflake", limit=200)

print(f"Total matches: {all_results['matches_found']}")
print(f"Returned: {all_results['returned']}")
```

**Limits**:
- Default: 50 results
- Maximum: 200 results
- Use `matches_found` to see total (may exceed returned count)

## Performance

Citation search is optimized for fast discovery:

```python
# Typical performance (100 reports)
results = search_citations(provider="snowflake")

# timing.total_duration_ms: ~50ms
```

**Performance tips**:
- **Specific filters**: Faster than broad searches
- **Grouping**: Minimal overhead (~10ms)
- **Limit**: Doesn't affect search speed, only result size

## Combining Filters

Combine multiple filters for precise searches:

```python
# Snowflake queries about revenue
search_citations(
    source_type="query",
    provider="snowflake",
    description_contains="revenue"
)

# DeFiLlama API calls for Monad
search_citations(
    provider="defillama",
    description_contains="monad"
)

# Any URL from official blogs
search_citations(
    source_type="url",
    url_contains="blog"
)
```

## Troubleshooting

### No Results Found

**Problem**: `matches_found: 0` but you expect results

**Solutions**:
1. **Check filter spelling**: Provider names are case-sensitive
2. **Try broader search**: Use fewer filters
3. **Verify citations exist**: Check reports have citations
4. **Check source type**: Ensure matching correct type (query vs url)

```python
# Too specific - might find nothing
search_citations(
    source_type="query",
    provider="snowflake",
    description_contains="very specific phrase"
)

# Broader - more likely to match
search_citations(provider="snowflake")
```

### Slow Search

**Problem**: Search takes >1 second

**Solutions**:
1. **Rebuild index**: Reports index may be out of sync
2. **Reduce report count**: Archive old reports
3. **Check report sizes**: Very large outlines slow search

### Unexpected Results

**Problem**: Results don't match expectations

**Solutions**:
1. **Case sensitivity**: Filters are case-insensitive (url_contains, description_contains)
2. **Partial matches**: url_contains matches substrings
3. **Check report status**: Only searches active reports by default

## Best Practices

### DO ✅

- **Use specific filters**: Faster and more relevant results
- **Group for overview**: Use `group_by` for audits
- **Limit results**: Start with default (50), increase if needed
- **Check timing**: Monitor `total_duration_ms` for performance
- **Combine filters**: Narrow results with multiple criteria

### DON'T ❌

- **Don't search without filters**: Returns too many results
- **Don't ignore matches_found**: May exceed returned count
- **Don't assume case-sensitive**: All text searches are case-insensitive
- **Don't forget archived reports**: Archived reports excluded by default

## Examples

### Example 1: Data Source Inventory

```python
"""Generate inventory of all data sources."""

results = search_citations(group_by="provider", limit=200)

print("=== Data Source Inventory ===\n")
print(f"Total citations: {results['matches_found']}\n")

summary = results['grouped_results']['summary']
for provider, count in sorted(summary.items(), key=lambda x: x[1], reverse=True):
    percentage = (count / results['matches_found']) * 100
    print(f"{provider:20} {count:5} citations ({percentage:.1f}%)")
```

### Example 2: Query Dependency Report

```python
"""Find all insights depending on a specific query."""

exec_id = "exec-550e8400-..."
results = search_citations(execution_id=exec_id)

if results['matches_found'] == 0:
    print(f"No insights cite query {exec_id}")
    print("Safe to deprecate this query.")
else:
    print(f"⚠️  {results['matches_found']} insights depend on {exec_id}:")
    for cit in results['citations']:
        print(f"\n- Insight: {cit['insight']['summary']}")
        print(f"  Report: {cit['report']['title']}")
        print(f"  Importance: {cit['insight']['importance']}/10")
```

### Example 3: External URL Audit

```python
"""Audit all external URL citations."""

results = search_citations(source_type="url", limit=200)

print(f"=== External URL Audit ===")
print(f"Total URL citations: {results['matches_found']}\n")

# Group by domain
domains = {}
for cit in results['citations']:
    url = cit['citation'].get('url', '')
    if url:
        domain = url.split('/')[2] if len(url.split('/')) > 2 else 'unknown'
        domains[domain] = domains.get(domain, 0) + 1

print("Top domains:")
for domain, count in sorted(domains.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"  {domain:40} {count:3} citations")
```

## Related Topics

- **[Citations](./citations.md)**: Learn about citation types
- **[User Guide](./user-guide.md)**: Complete Living Reports overview
