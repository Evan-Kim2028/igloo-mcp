# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

# [0.3.0] - 2025-11-23

### Added
- **Living Reports System**: Complete implementation of auditable, LLM-assisted report generation with three-layer architecture (Presentation/Quarto, Machine Truth/JSON, Immutable Memory/audit logs)
- **MCP `evolve_report` Tool**: LLM-agnostic framework for structured report evolution
- **MCP `render_report` Tool**: Quarto-based rendering to HTML/PDF/Markdown/DOCX
- **CLI Report Commands**: `igloo report create/evolve/render/revert/open/list` subcommands for full report lifecycle management
- **Report Storage & Locking**: Atomic writes, crash recovery, cross-platform file locking, and backup rotation
- **HistoryIndex Integration**: Reports can reference cached query results via execution_id/sql_sha256 for provenance
- **Pydantic Data Models**: Complete type system for reports, insights, sections, audit events, and index entries
- **Global Report Index**: UUID-based report registry with title resolution and filesystem reconciliation
- `IGLOO_MCP_REPORTS_ROOT` environment variable for explicit reports directory control
- Automatic reports directory creation on first use

### Removed
- `preview_table` tool (replaced by `execute_query` with `SELECT * FROM table LIMIT n`)
- **report_scaffold** tool (deprecated in favor of direct report creation via CLI)

### Fixed
- **DESCRIBE TABLE Classification** (#41): DESCRIBE statements now correctly classified as 'Describe' type instead of 'Command', enabling proper permission handling
- **Timeout Error Messaging** (#42): Error messages now prioritize catalog-based filtering and clustering key guidance before suggesting timeout increases

### Changed
- **BREAKING**: Living reports now use unified storage with query history and artifacts
  - Default location: `~/.igloo-mcp/reports/` (follows IGLOO_MCP_LOG_SCOPE)
  - Configure via: `IGLOO_MCP_REPORTS_ROOT` environment variable
  - Migration: Move existing reports from `<repo>/reports/` to `~/.igloo-mcp/reports/`
- Major version upgrade: Version bump to **0.3.0** reflecting significant improvements and new features

# [0.2.7] - 2025-01-XX

### Added
- **Auto-generated UUIDs**: `insight_id` and `section_id` are now optional for additions (`insights_to_add`, `sections_to_add`). UUIDs are automatically generated if not provided, reducing boilerplate code.
- **Partial Update Support**: When modifying insights or sections, only specified fields are updated. Fields not provided (or set to `None`) remain unchanged, enabling granular updates.
- **Atomic Add-and-Link**: New `insights` field in `SectionChange` allows creating insights inline within section additions. Insights are created atomically with the section and automatically linked, eliminating the need for separate add-and-link operations.
- **Enhanced Error Messages**: Validation errors now include structured information with field paths (e.g., `insights_to_modify[0].insight_id`), actual values, and available IDs for "not found" errors. Both string format (backward compatible) and structured format (in `context.structured_errors`) are provided.

### Changed
- **BREAKING**: `validate_against_outline()` now returns `List[ValidationErrorDetail]` instead of `List[str]`. String format is maintained via `to_string()` method for backward compatibility.
- Validation now requires at least one non-ID field for modifications to prevent empty update operations.

### Fixed
- Improved error messages for invalid insight/section IDs now include available IDs to help users find the correct values.

# [0.2.5] - 2025-11-22

### Added
- Structured source attribution in `execute_query` responses/history. `source_databases` and fully-qualified `tables` now appear for cache hits, successes, timeouts, and errors so cross-database usage is auditable even when the session default database differs.
- New regression suite (`tests/test_execute_query_source_attribution.py`) covering extractor edge cases plus async/trio integration flows, ensuring the feature no longer depends on ad-hoc reproduction scripts.

### Changed
- Refactored payload enrichment into `_enrich_payload_with_objects` to remove duplication across cache/timeout/error logging paths.
- Version bump to **0.2.5** with README/CONTRIBUTING/doc updates and release automation notes.

### Fixed
- `HealthCheckTool` now calls `MCPHealthMonitor.get_comprehensive_health` when available and gracefully falls back to legacy `get_health_status`, restoring compatibility with existing tests and ensuring accurate `system.healthy` reporting.
- Eliminated stray `tmp_repro_38` artifacts now that coverage exists in the test suite.

# [0.2.4] - 2025-11-22

### Added
- Made `reason` parameter **required** in `execute_query` tool (minLength: 5) for improved auditability in Snowflake QUERY_TAG, history, and cache manifests.
- Enhanced `session_context` logging to always include `database` and `schema` alongside `warehouse`/`role`.

### Changed
- Updated `execute_query` schema description/examples to emphasize `reason` importance.
- Tests updated to reflect required `reason`.

### Breaking Changes
- `execute_query` calls without `reason` will now fail validation in MCP clients.

### Migration
- Add `reason="brief purpose"` to all `execute_query` calls (e.g., "Validate Q3 revenue", "Debug null orders").
- No impact on existing logs (backward compatible).

## [0.2.3] - 2025-11-22

### Added
- Automatic cache insights: key metrics/insight summaries are recorded in history docs and cache manifests whenever `post_query_insight` or auto-insight generation runs, with fixture coverage.

### Changed
- `execute_query` now consumes as much of the MCP RPC timeout budget as possible before transparently falling back to async polling, so long-running statements always return an `execution_id`. Related docs cover inline wait budgeting and `fetch_async_query_result` parity.
- SQL validation recognizes SHOW statements even when they begin with whitespace or SQL comments, ensuring permissions apply uniformly.

### Tests
- Expanded `tests/test_execute_query_tool.py`, cache fixture builders, and `tests/test_sql_validation_enhanced.py` to cover auto insights, auto async fallback, and SHOW lexical detection with comment prefixes.

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
