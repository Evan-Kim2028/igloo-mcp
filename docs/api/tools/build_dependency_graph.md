# Tool: build_dependency_graph

Build dependency relationships across Snowflake objects for quick lineage insights.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `database` | string | ❌ No | current | Database to analyze (Snowflake identifier). |
| `schema` | string | ❌ No | current | Schema to analyze (some service implementations may ignore this). |
| `account_scope` | boolean | ❌ No | true | Include broad account relationships when supported. |
| `format` | string | ❌ No | json | Output format (`json` or `dot`). |

> Identifiers may be unquoted (e.g., `ANALYTICS`) or quoted (`"Sales Analytics"`). Set `account_scope=false` to limit results to the active session context.

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
  "database": "ANALYTICS",
  "format": "json",
  "output_dir": "./dependencies",
  "nodes": 10,
  "edges": 15
}
```

Custom service backends can extend this payload with richer metadata as needed.

## Examples

```json
{
  "tool": "build_dependency_graph",
  "arguments": {
    "database": "ANALYTICS",
    "schema": "REPORTING",
    "account_scope": false,
    "format": "dot"
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
- **No edges returned** – There may be no registered dependencies in the current scope; try enabling `account_scope` or building the catalog first.

## Related Tools

- [build_catalog](build_catalog.md) – Export comprehensive catalog metadata.
- [get_catalog_summary](get_catalog_summary.md) – Inspect catalog health and totals.
