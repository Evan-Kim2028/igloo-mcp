# Tool: build_dependency_graph

Build dependency relationships across Snowflake objects for quick lineage insights.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `database` | string | ❌ No | current | Database to analyze (Snowflake identifier). |
| `schema` | string | ❌ No | current | Schema to analyze (some service implementations may ignore this). |
| `account` | boolean | ❌ No | false | Include broad account relationships when supported. |
| `format` | string | ❌ No | json | Output format (`json` or `dot`). |
| `timeout_seconds` | integer \| string | ❌ No | 60 | Optional graph build timeout override (1-3600). Falls back to `IGLOO_MCP_TOOL_TIMEOUT_SECONDS` when set. |
| `request_id` | string | ❌ No | auto-generated | Optional request correlation ID for tracing. |

> Identifiers may be unquoted (e.g., `ANALYTICS`) or quoted (`"Sales Analytics"`). Set `account=false` to limit results to the active session context.

## Discovery Metadata

- **Category:** `metadata`
- **Tags:** `dependencies`, `lineage`, `graph`, `metadata`
- **Usage Examples:**
  1. Generate a JSON dependency summary for account-wide analysis.
  2. Produce a DOT graph for visual tooling by passing `format="dot"`.

## Returns

The default implementation returns a lightweight dictionary describing where artifacts were written and the counts reported by the dependency service:

```json
{
  "status": "success",
  "request_id": "550e8400-e29b-41d4-a716-446655440001",
  "database": "ANALYTICS",
  "format": "json",
  "output_dir": "./dependencies",
  "nodes": 10,
  "edges": 15,
  "timeout": {
    "seconds": 60,
    "source": "default"
  },
  "timing": {
    "total_duration_ms": 134.22
  },
  "warnings": []
}
```

Custom service backends can extend this payload with richer metadata as needed. `timeout.source` is one of `parameter`, `env`, or `default`.

## Examples

```json
{
  "tool": "build_dependency_graph",
  "arguments": {
    "database": "ANALYTICS",
    "schema": "REPORTING",
    "account": false,
    "format": "dot",
    "timeout_seconds": 180
  }
}
```

## Common Use Cases

- Capture dependency context for architecture diagrams.
- Estimate change impact by viewing connected objects before deploying updates.
- Generate quick lineage previews without running a full catalog export.

## Troubleshooting

- **`Database 'XYZ' not found`** – Check the spelling and ensure your Snowflake profile has access.
- **`Dependency graph build failed`** – Review the error for permission or connectivity issues; the service writes to `./dependencies` and requires access to that path.
- **No edges returned** – There may be no registered dependencies in the current scope; try enabling `account` or building the catalog first.

## Related Tools

- [build_catalog](build_catalog.md) – Export comprehensive catalog metadata.
- [get_catalog_summary](get_catalog_summary.md) – Inspect catalog health and totals.
