# Tool: query_lineage

> **⚠️ DEPRECATED**: This tool has been removed. Use `build_dependency_graph` instead for dependency analysis.

## Status

This tool is no longer available. It has been removed from igloo-mcp as lineage functionality is not part of the core feature set.

## Replacement

Use the **[build_dependency_graph](build_dependency_graph.md)** tool to generate dependency graphs:

```python
# Generate dependency graph for a database
build_dependency_graph(
    database="ANALYTICS",
    format="json"  # or "dot" for Graphviz
)
```

## Related Tools

- [build_dependency_graph](build_dependency_graph.md) - Generate dependency graphs in JSON or DOT format
- [build_catalog](build_catalog.md) - Build catalog metadata (required for dependency analysis)
