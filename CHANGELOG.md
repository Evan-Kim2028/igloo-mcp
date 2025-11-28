# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

# [0.3.3] - 2025-11-28

## Added

### API Enhancements (Distributed Tracing & Monitoring)

- **Distributed Tracing**: Added `request_id` (UUID4) to catalog and health tools
  - Tools affected: `build_catalog`, `get_catalog_summary`, `search_catalog`, `health_check`
  - Auto-generated if not provided; enables correlation across multi-step operations
  - Included in all log entries for end-to-end tracing

- **Performance Monitoring**: Added `timing` metrics to all catalog/health tools
  - `timing` object with `total_duration_ms` (all tools)
  - Operation breakdowns: `build_catalog` includes `catalog_fetch_ms`, `search_catalog` includes `search_duration_ms`
  - Enables optimization and SLA monitoring

- **Response Symmetry**: Complete ID tracking for audit completeness
  - `evolve_report`: Added `insight_ids_removed` and `section_ids_removed` arrays
  - `create_report`: Added `section_ids_added` and `insight_ids_added` arrays
  - Audit trail now includes `section_ids_removed` field

- **Warnings Infrastructure**: Structured non-fatal issue reporting
  - `build_catalog` and `search_catalog` include `warnings` array (empty when none)
  - Structure: `[{"code": str, "message": str, "severity": str, "context": dict}]`
  - Enables clients to handle partial results gracefully

## Fixed

### Type Safety & Validation

- **#77**: Fixed 18 MyPy type errors in `changes_schema.py` (copy-paste type annotations)
- **#66**: Improved validation error messages with structural hints for nested objects
- **#75**: SQL validation now raises `ValueError` (not `AttributeError`) for malformed SQL

### Bug Fixes

- **#88**: `title_change` and `metadata_updates` now properly applied in `evolve_report`
- **#89**: Universal citation enforcement across all templates (not just analyst_v1)

### Developer Experience

- **#78**: Removed invalid `[tool.uv.build]` section from pyproject.toml
- **#79**: Simplified pre-commit config (ruff only, removed black/isort)
- **#82**: Added comprehensive `.env.example` documenting all environment variables
- **#83**: Fixed 9 ruff linting warnings (E501 line length, E731 lambda assignment)

## Changed

### API Additions (Non-Breaking)

All changes are **backward compatible** - new fields are additions, no existing fields removed.

- Catalog tools: Signatures now include optional `request_id` parameter
- Report tools: Responses now include complete ID tracking arrays
- All tools: Responses include `timing` and `warnings` where applicable

## Infrastructure

- Added 57 tests across 4 files covering API completeness
- Added 9 regression tests for citation and metadata features
- All ruff linting checks pass

## Summary

**v0.3.3 completes API completeness**, closing all 16 issues:

**Issues Closed**: #65, #66, #67, #68, #69, #70, #71, #73, #75, #77, #78, #79, #82, #83, #88, #89

**Key Improvements**:
1. **Distributed Tracing**: request_id enables end-to-end correlation across multi-step workflows
2. **Audit Completeness**: All CRUD operations (Create/Read/Update/Delete) now tracked symmetrically
3. **Type Safety**: MyPy errors resolved, better validation error UX
4. **Developer Experience**: Simplified tooling, comprehensive environment documentation

All enhancements are **backward compatible** with sensible defaults.

# [0.3.2] - 2025-11-28

### Added

#### New MCP Tools

- **`get_report` tool (#51)**: Read living reports with selective retrieval for token efficiency
  - 4 retrieval modes: `summary` (lightweight overview), `sections` (section details), `insights` (insight details), `full` (complete report)
  - Selective filtering: `section_ids`, `section_titles`, `insight_ids`, `min_importance`
  - Pagination support with `limit` and `offset` parameters
  - Enables progressive disclosure: agents can start with summary, then drill down to specific content
  - Critical for multi-turn workflows: agents can now read reports to get section_ids/insight_ids before modifying them

- **`get_report_schema` tool (#51)**: Self-documenting schema introspection
  - 3 output formats: `json_schema` (full JSON Schema draft 7), `examples` (copy-paste-ready payloads), `compact` (quick reference)
  - Auto-generated from Pydantic models (single source of truth)
  - Returns schemas for `proposed_changes`, `insight`, `section`, `outline`, or `all`
  - Enables agents to discover valid structures at runtime before constructing evolve_report payloads

#### Token Efficiency Enhancements

- **`evolve_report` response_detail parameter**: Control response verbosity for 50-80% token reduction
  - `minimal` (~200 tokens): Just status, report_id, version, and counts
  - `standard` (~400 tokens, default): Adds IDs of created items and warnings
  - `full` (~1000+ tokens): Complete details including changes_applied echo and timing
  - Backward compatible: defaults to `standard` for balanced responses

- **`search_report` fields parameter**: Filter returned fields for 30-50% token reduction
  - Specify which fields to return: `fields=["report_id", "title"]` for minimal responses
  - Valid fields: `report_id`, `title`, `created_at`, `updated_at`, `tags`, `status`, `path`
  - Default: all fields (backward compatible)
  - Enables efficient report discovery without loading full metadata

- **`render_report` preview_max_chars parameter**: Configurable preview truncation
  - Control preview size: 100-10,000 characters (default: 2000)
  - Allows agents to request smaller previews for token efficiency
  - Backward compatible with existing default

### Changed (Breaking)
- **Default result truncation limits significantly reduced** to optimize token usage and prevent context window overflow:
  - `RESULT_SIZE_LIMIT_MB`: 100 MB → 1 MB (100x reduction)
  - `RESULT_KEEP_FIRST_ROWS`: 1000 → 500 (2x reduction)
  - `RESULT_KEEP_LAST_ROWS`: 1000 → 50 (20x reduction)
  - `RESULT_TRUNCATION_THRESHOLD`: 10000 → 1000 (10x reduction)
  - **Impact**: Large query results will be truncated more aggressively by default
  - **Mitigation**: Configure via environment variables if you need larger limits:
    - `IGLOO_MCP_RESULT_SIZE_LIMIT_MB`
    - `IGLOO_MCP_RESULT_KEEP_FIRST_ROWS`
    - `IGLOO_MCP_RESULT_KEEP_LAST_ROWS`
    - `IGLOO_MCP_RESULT_TRUNCATION_THRESHOLD`

### Fixed
- **#48 timeout_seconds type error**: `execute_query` now accepts both integer and numeric string values (e.g., `240` or `"240"`), coercing strings to integers during validation. Fixes MCP client compatibility issues where timeouts were passed as strings.
- **#60 render_report preview**: `include_preview=True` now correctly returns truncated rendered content in the response. Also fixed `output_path` to always return the resolved absolute path to the rendered file (or QMD path for dry runs).
- **#59 evolve_report stale warnings**: Warnings are now computed AFTER changes are applied, ensuring accurate reporting (e.g., no "Section has no insights" warning after linking insights).
- **#58 supporting_queries optional**: `insights_to_add` now defaults `supporting_queries` to empty list `[]` when not provided, eliminating boilerplate for draft insights.
- **#57 inline insights**: `sections_to_add` and `sections_to_modify` now support inline `insights` array for atomic insight creation and linking. Summary counts correctly reflect inline-created insights.

### Added
- **Section prose content**: Sections now support optional `content` and `content_format` fields for free-form narrative text (markdown by default), enabling richer report structure beyond insights.
- **Status change support**: `evolve_report` now accepts `status_change` parameter to transition reports between `active`, `archived`, and `deleted` states with full audit trail.
- **Citations field (model-level)**: Insights now have `citations` field alongside `supporting_queries` for future multi-source support (web/API/manual). Backward compatible shim ensures existing code continues working.
- Enhanced `render_report` service to return usable `output_path` and optional `preview` in standardized response format.
- **#50, #49 Enhanced validation errors**: Validation errors now include field paths, input values, operation-specific schema examples, and hints for common mistakes. Makes debugging schema issues significantly easier for LLM agents and users.
- **#55 Enhanced dry_run**: Dry run validation now returns detailed validation errors with schema help when validation fails, enabling iterative debugging without applying changes.

### Changed
- **evolve_report validation**: Validation errors now return structured dictionaries (`status: "validation_failed"`) instead of raising exceptions, providing better MCP client compatibility.
- Improved test coverage: 58/58 evolve_report tests passing, 18/18 render_report tests passing, all execute_query tests passing.

### Documentation
- **#52 JSON Schema Reference**: Added comprehensive JSON schema reference section to user guide with copy-paste-ready examples for all operations (adding/modifying/removing insights, sections, status changes, dry run validation, etc.). Includes common validation error examples.

### Infrastructure
- Added comprehensive test suite for render service preview/output path behavior
- Added 23 tests for new tools and token efficiency enhancements (100% passing)
- Updated tool schemas to match new validation return format
- Enhanced error messages with clearer field-level validation feedback

### Summary

**v0.3.2 completes the Living Reports tooling ecosystem**, closing all 9 open issues and delivering significant token efficiency improvements:

**Issues Closed**: #48, #49, #50, #51, #52, #53, #54, #55, #56

**Token Savings**: Agents can now achieve ~70% reduction in response tokens through selective retrieval (`get_report`) and configurable verbosity (`response_detail`, `fields`, `preview_max_chars`).

**Workflow Impact**: Agents can now:
1. **Discover** reports efficiently (`search_report` with `fields`)
2. **Read** report structure (`get_report` with `mode="summary"`)
3. **Understand** schemas (`get_report_schema` with `format="examples"`)
4. **Modify** precisely (`evolve_report` with correct IDs from get_report)
5. **Verify** changes (`get_report` with selective filtering)
6. **Render** with control (`render_report` with `preview_max_chars`)

All enhancements are **backward compatible** with sensible defaults.

# [0.3.1] - 2025-11-24

### Fixed
- Handle corrupted `index.jsonl` gracefully: skip bad lines, back up the original, and rebuild from filesystem instead of crashing on startup.
- Patch SQL validation middleware wrapper to match FastMCP 2.13 signature and only validate `execute_query`; adds legacy fallback to avoid startup errors.

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
