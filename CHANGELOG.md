# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2025-10-31

### Fixed
- Miscellaneous bug fixes from the "bug fixes" PR; no public API changes.

### Notes
- Patch release; no breaking changes detected.

## [0.2.0] - 2025-10-26

### Added
- SHA-256 indexed SQL artifact storage with repo-local defaults (`logs/doc.jsonl`, `logs/artifacts/`).
- `scripts/export_report_bundle.py` to build audit bundles from the history file and artifacts.
- MCP resource template `igloo://queries/by-sha/{sql_sha256}.sql` for direct SQL retrieval.

### Changed
- History logging is enabled by default; set `IGLOO_MCP_QUERY_HISTORY=""` to disable logging and artifact creation.
- Timeout parsing now accepts numeric strings and the exporter validates SHA inputs before reading from disk.

### Tests
- Added coverage for numeric string timeouts, history disablement, exporter CLI, and SQL resource helper.

## [0.1.2] - 2025-10-21

### Added
- Clarified SQL safety messaging when Snowflake falls back to the generic `Command` type.

### Changed
- Default SQL permissions now block INSERT/UPDATE/CREATE/ALTER alongside DELETE/DROP/TRUNCATE.
- Documentation highlights the stricter defaults and how to opt back into write verbs.

### Fixed
- Ensure DML-only execute tests run by explicitly opting into INSERT permissions.

## [0.1.1] - 2025-10-20

### Changed
- Patch release aligning packaging and version metadata after 0.1.0.
- Published to PyPI: `igloo-mcp==0.1.1`.

### Notes
- No functional code changes beyond version bump.

## [0.1.0] - 2025-10-20

### Added
- Rich MCP tool discovery metadata and JSON parameter schemas across tools.
- `schema_utils.py` with helpers for parameter schemas.
- Comprehensive tests for tool schemas.

### Changed
- Dependency graph tool now respects provided scope parameters.

### Fixed
- SQL validation: Treat set operators and CTE SELECTs as `SELECT`.
  - `UNION` / `UNION ALL` / `INTERSECT` / `EXCEPT` / `MINUS` inherit `SELECT` permissions.
  - `WITH ... SELECT` recognized as `SELECT`.
- Adds tests for validator and `ExecuteQuery` tool behavior.

### Compatibility
- Backward compatible. Note: tool parameter schemas use `additionalProperties=false`; clients should avoid extra parameters.

## [2.0.0] - 2025-10-07

### BREAKING CHANGES

**🐻‍❄️ Package Rebrand: snowcli-tools → igloo-mcp**

The package has been renamed to better reflect its MCP-first architecture and create a unique brand identity.

#### Changed
- **Package name**: `snowcli-tools` → `igloo-mcp`
- **Import namespace**: `from snowcli_tools` → `from igloo_mcp`
- **PyPI package**: `pip install snowcli-tools` → `pip install igloo-mcp`
- **MCP command**: `snowcli-mcp` → `igloo-mcp`
- **GitHub repository**: `Evan-Kim2028/snowcli-tools` → `Evan-Kim2028/igloo-mcp`

**CLI Interface Removed**

The legacy CLI interface (`nanuk` command) has been removed. Igloo is now MCP-only.

#### Removed
- `nanuk` CLI command and all subcommands
- `src/igloo_mcp/cli.py` and `src/igloo_mcp/commands/` directory (~774 LOC)
- CLI-specific dependency: `click>=8.0.0`
- CLI-specific tests

#### Migration
- **Rebrand migration**: See [Migration Guide](docs/migration-guide.md) for package name changes and CLI to MCP migration
- **CLI migration**: See [CLI Migration Guide](docs/cli-to-mcp-migration.md) for transitioning to MCP tools
- All CLI functionality is available through MCP tools (see table in migration guide)

#### Rationale
- Package name is "nanuk-**mcp**" - should be MCP-only
- Reduces codebase by 774 LOC (40% reduction in interface code)
- Eliminates user confusion about which interface to use
- Aligns with AI-first architecture

#### Why "Nanuk"?
- 🐻‍❄️ Nanuk (polar bear in Inuit) connects to Snowflake's arctic theme
- 🎯 MCP-first: Name reflects focus on Model Context Protocol
- ✨ Unique & memorable: Stands out in the MCP ecosystem
- 🚀 Future-proof: Positions as premier Snowflake MCP provider

## [1.9.0] - 2025-01-04

### Phase 1: Code Simplification (Completed)

#### Added
- New simplified lineage models: `models.py`, `traversal.py`, `format.py` (~400 LOC total)
- Consolidated `health.HealthCheckTool` combining health_check, check_profile_config, and get_resource_status
- Cortex AI availability check in health tool (`include_cortex` parameter)
- Simplified `test_connection` tool as lightweight wrapper
- Migration guide: `docs/v1.9.0_migration.md`

#### Changed
- Lineage module reduced from 6,874 LOC to ~400 LOC (94% reduction)
- Health tools reduced from 5 tools (426 LOC) to 2 tools (150 LOC)
- `LineageGraph` aliased to `Graph` for backward compatibility
- `query_lineage` tool updated to use simplified lineage API

#### Removed
- `column_parser.py` (584 LOC) - Column-level lineage (too granular for common use cases)
- `cross_db.py` (509 LOC) - Cross-database lineage (niche use case)
- `impact.py` (830 LOC) - Impact analysis (move to optional package in future)
- `history.py` (889 LOC) - Lineage history tracking (complex, rarely used)
- `transformations.py` (~600 LOC) - Transformation metadata (overlaps with column parser)
- `external.py` (~400 LOC) - External source mapping (not implemented)
- `check_resource_dependencies` MCP tool (88 LOC) - Confusing API, rarely used
- `check_profile_config` MCP tool - Merged into HealthCheckTool
- `get_resource_status` MCP tool - Merged into HealthCheckTool

**Total Phase 1 Impact**: -4,088 LOC (66% code reduction)
