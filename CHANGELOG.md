# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

# [0.3.5] - 2025-11-30

## Added

### Query Optimization - `result_mode` Parameter (#100, #102)

**Token-Efficient Query Responses**: New `result_mode` parameter for `execute_query` reduces response size by 60-90%.

**Modes**:
- `full` (default): Return all rows unchanged
- `summary`: Return key_metrics + 5 sample rows only (~90% reduction)
- `schema_only`: Return column names/types only, no rows (~95% reduction)
- `sample`: Return first 10 rows only (~60-80% reduction for large results)

**Response Format**:
All non-full modes add `result_mode` and `result_mode_info` fields:
```json
{
  "result_mode": "summary",
  "result_mode_info": {
    "mode": "summary",
    "total_rows": 10000,
    "rows_returned": 5,
    "sample_size": 5,
    "columns_count": 8,
    "hint": "Use result_mode='full' to retrieve all rows"
  },
  "rows": [...5 rows...],
  "key_metrics": {...}
}
```

**Use Cases**:
- `schema_only`: Schema discovery without data transfer
- `sample`: Quick data preview for validation
- `summary`: Get metrics + representative sample for analysis
- `full`: Complete data retrieval (backward compatible default)

### Living Reports - Batch Operations (#101)

**`evolve_report_batch` Tool**: Atomic multi-operation report evolution.

**Benefits**:
- Reduce round-trips: Perform multiple operations in one call
- Ensure consistency: All-or-nothing transactional semantics
- Improve ergonomics: Natural batching for multi-insight reports

**Supported Operations** (8 types):
- `add_insight` / `modify_insight` / `remove_insight`
- `add_section` / `modify_section` / `remove_section`
- `update_title` / `update_metadata`

**Example**:
```python
evolve_report_batch(
    report_selector="Q1 Revenue Report",
    instruction="Add revenue analysis section with insights",
    operations=[
        {
            "type": "add_insight",
            "summary": "Enterprise revenue grew 45% YoY",
            "importance": 9,
            "citations": [{"execution_id": "exec-123"}]
        },
        {
            "type": "add_section",
            "title": "Revenue Analysis",
            "order": 1,
            "insight_ids": ["<generated-uuid>"]
        }
    ]
)
```

## Fixed

### CI/CD & Test Compatibility

- **Python 3.12/3.13 Compatibility**: Fixed threading.Lock type checking issues
  - Fixed `isinstance(lock, threading.Lock)` errors in `session_utils.py`
  - Updated test assertions to use proper type comparison
  - `threading.Lock` is a factory function, not a direct type in Python 3.12
  - All 715 tests now pass on both Python 3.12 and 3.13

- **Config Caching Test**: Fixed `test_config_loading_is_cached_by_mtime`
  - Added delay to ensure mtime changes on fast filesystems
  - Added mtime change verification
  - Enhanced test reliability across different platforms

## Changed

### CI/CD Infrastructure

- **Python Version Support**: Added Python 3.13 to CI test matrix
  - CI now tests both Python 3.12 and 3.13 in parallel
  - Updated `requires-python` to `>=3.12,<3.14`
  - Ensures compatibility across both versions on every commit

- **Multi-version Testing**: All CI jobs now run for both Python versions
  - `lint` job: Runs on Python 3.12 and 3.13
  - `type-check` job: Runs on Python 3.12 and 3.13
  - `test` job: Runs on Python 3.12 and 3.13

## Infrastructure

- **Testing**: All 715 tests passing on both Python 3.12 and 3.13
- **CI Duration**: ~1 minute total (parallel execution)
- **Coverage**: Maintained 68%+ coverage across both Python versions

## Summary

**v0.3.5 delivers token efficiency and batch operations** for optimized AI workflows.

**Key Improvements**:
1. **Token Efficiency**: 60-90% reduction in query response sizes via `result_mode`
2. **Batch Operations**: Atomic multi-operation report evolution
3. **Python Support**: Robust 3.12/3.13 compatibility with CI verification

All changes are **backward compatible** with sensible defaults.

# [0.3.4] - 2025-11-29

## Added

### CI/CD & Automation (#76)

- **GitHub Actions CI**: Automated testing, linting, and type-checking
  - Parallel jobs: `lint` (ruff), `type-check` (mypy), `test` (pytest with coverage)
  - Skips Snowflake integration tests (`-m "not requires_snowflake"`)
  - Codecov integration for coverage reporting
  - Uses `uv` package manager for fast, reproducible builds

- **GitHub Actions Release**: Automated PyPI publishing
  - Triggered on version tags (`v*`)
  - Uses trusted publishing (no API token needed)
  - Runs `uv build` and `uv publish`

### Error Handling Enhancements (#95, #97)

- **Compact Error Messages**: Token-efficient error responses (#97)
  - Default: Show first 2 hints + truncation notice
  - Add `verbose_errors=True` parameter to `execute_query` for full hints
  - Reduces token usage by 60%+ for common errors
  - Truncation notice: `{"hints_truncated": true, "hints_available": N}`

- **Error Handler Helpers**: Extracted common error handling logic (#95)
  - New functions: `handle_mcp_exception_decorator`, `handle_validation_error_decorator`, `handle_generic_exception_decorator`
  - Reduced `tool_error_handler` from ~200 lines to ~100 lines (50% reduction)
  - Eliminates ~100 lines of duplicated code
  - Improved maintainability and consistency

### Validation Helpers (#96)

- **Standardized Validation Functions**: Reusable parameter validation
  - `validate_required_string()`: String validation with min/max length
  - `validate_numeric_range()`: Numeric validation with range checks
  - `validate_enum_value()`: Enum validation with allowed values
  - Consistent MCPValidationError handling across all validators

## Fixed

### Error Handling & Consistency

- **#72**: Standardized error status values
  - Changed `"failed"` to `"error"` in health check responses
  - Consistent with other error status values across codebase

- **#95**: Error handler refactoring
  - Eliminated code duplication in exception handling
  - Improved error propagation with request_id context
  - Better verbose parameter handling through decorator helpers

### Bug Fixes

- **Path Comparison Bug**: Fixed `search_all_databases` mode in `search_catalog`
  - Path validation was stripping `./` prefix, breaking the feature
  - Now uses `Path(catalog_dir).name == "data_catalogue"` for normalization
  - Resolves test failures in `test_warnings_in_search_all_databases_mode`

## Changed

### Breaking Changes

**⚠️ BREAKING CHANGE: Compact Error Messages (#97)**

Error messages now show only the first 2 hints by default (previously showed all hints).

**Impact**:
- Clients expecting all hints in error responses will see truncated hints
- Error token usage reduced by 60%+ for common errors

**Migration**:
- **Option 1** (Recommended): Use first 2 hints (most actionable)
- **Option 2**: Pass `verbose_errors=True` to `execute_query` for full hints
- **Option 3**: Check `hints_truncated` and `hints_available` fields in error responses

**Example**:
```python
# Compact mode (default) - 2 hints
result = await execute_query(
    statement="SELECT * FROM table",
    reason="Analysis"
)

# Verbose mode - all hints
result = await execute_query(
    statement="SELECT * FROM table",
    reason="Analysis",
    verbose_errors=True
)
```

**⚠️ BREAKING CHANGE: Status Value Consistency (#72)**

The `status` field in health check error responses changed from `"failed"` to `"error"`.

**Impact**:
- Clients checking `status == "failed"` in health check responses will need updates
- Affects `health_check` tool connection failures

**Migration**:
- Update health check parsing to handle `status == "error"`
- Backward-compatible check: `status in ("failed", "error")`

### API Enhancements (Non-Breaking)

- `wrap_selector_error()` and `wrap_execution_error()` now accept `verbose` parameter
- Default `verbose=True` maintains backward compatibility with existing error creation
- Error decorators extract `verbose_errors` from kwargs for client control

## Infrastructure

- **Testing**: 708 tests passing (7 skipped, 1 xfailed, 1 xpassed)
- **Coverage**: 68.06% overall coverage maintained
- **CI/CD**: Automated workflows ensure quality on every commit
- **Code Quality**: Reduced error handling duplication by 50%

## Summary

**v0.3.4 focuses on production hardening** with CI/CD, error handling improvements, and code debt cleanup.

**Issues Closed**: #76, #95, #97, #96, #72

**Key Improvements**:
1. **CI/CD Automation**: GitHub Actions for testing, linting, and PyPI releases
2. **Token Efficiency**: 60%+ reduction in error message tokens with compact mode
3. **Code Quality**: 50% reduction in error handling duplication
4. **Validation**: Standardized parameter validation helpers

**Breaking Changes**: 2 (compact errors, status value consistency) - both with clear migration paths.

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
- All ruff linting checks pass for production code (src/)
- 21 pre-existing test linting issues deferred to v0.3.4

## Summary

**v0.3.3 completes API completeness**, closing all 16 issues:

**Issues Closed**: #65, #66, #67, #68, #69, #70, #71, #73, #75, #77, #78, #79, #82, #83, #88, #89

**Key Improvements**:
1. **Distributed Tracing**: request_id enables end-to-end correlation across multi-step workflows
2. **Audit Completeness**: All CRUD operations (Create/Read/Update/Delete) now tracked symmetrically
3. **Type Safety**: MyPy errors resolved, better validation error UX
4. **Developer Experience**: Simplified tooling, comprehensive environment documentation

All enhancements are **backward compatible** with sensible defaults.

## Migration Notes

### Citation Enforcement (Issue #89)

**BEHAVIOR CHANGE**: Citation validation now applies to **ALL templates** (previously only `analyst_v1`).

**Impact**: Reports using `default` or `deep_dive` templates now require citations on all insights.

**Migration**:
- **Option 1** (Recommended): Add citations to existing insights that lack them
- **Option 2** (Temporary): Use escape hatch in `evolve_report`:
  ```python
  constraints={"skip_citation_validation": True}
  ```

**Why this change**: Universal citation enforcement improves data quality and auditability across all report types.

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
