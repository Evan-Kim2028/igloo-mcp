<!-- abf98c47-7d42-4fe3-81ea-7e0cf69bee15 6b414684-eb92-4bdc-861c-056d16efb2f5 -->
# v2.0.1 Migration Evaluation and Implementation Plan

## Scope

- Replace Snowflake Labs MCP with SnowCLI-only architecture.
- Update code, tests, and documentation accordingly.
- Preserve MCP tool interfaces and improve maintainability.
- Add naming migration from `igloo_mcp` → `igloo_mcp` (import) and `igloo-mcp` → `igloo-mcp` (CLI).

## Code Changes

### 1) Remove Snowflake Labs MCP dependency

- File: `pyproject.toml`
- Remove dependency: `"snowflake-labs-mcp>=1.3.3"`.
- Ensure `sqlglot` is present (add if missing) for local SQL validation.

### 2) Server lifecycle and CLI args

- File: `src/igloo_mcp/mcp_server.py`
- Remove imports: `mcp_server_snowflake.server`, `.utils` (`create_lifespan`, `SnowflakeService`, `get_login_params`, `warn_deprecated_params`).
- Implement `create_nanuk_lifespan(args)` async context manager to initialize `MCPHealthMonitor`, `MCPResourceManager`, run profile health check, and cleanup on exit.
- Replace `parse_arguments` to define standard args: `--profile|-p`, `--warehouse|-w`, `--database|-d`, `--schema|-s`, `--role|-r`, `--log-level`.
- Remove `warn_deprecated_params()` invocation.
- Update environment handling to set `SNOWFLAKE_PROFILE` only if user passes `--profile`.

### 3) Registration and tool wiring

- File: `src/igloo_mcp/mcp_server.py`
- Change `register_igloo_mcp(server: FastMCP, *, enable_cli_bridge: bool = False)` (remove `snowflake_service` param).
- Instantiate services: `QueryService`, `CatalogService`, `DependencyService`.
- For tools (`ExecuteQueryTool`, `HealthCheckTool`, `PreviewTableTool`, `ConnectionTestTool`), pass only required deps and allow each to create its own `SnowCLIService`.
- Keep registration guard (`_igloo_mcp_registered`).

### 4) SnowCLI-based service compatibility

- File: `src/igloo_mcp/services.py`
- Add `SnowCLIService` that wraps `SnowCLI` and provides a compatibility cursor via `get_connection(use_dict_cursor=True, session_parameters=None)` with `execute`, `fetchone`, `fetchall`, `rowcount` and a `threading.Lock` for thread safety.
- Ensure `test_connection()` and `execute_query()` delegate to `SnowCLI`.
- Keep existing `RobustSnowflakeService` if valuable, or re-alias it to use `SnowCLIService` internally.

### 5) Session utilities and query service

- File: `src/igloo_mcp/service_layer/query.py`
- No signature changes; ensure it only relies on `get_connection()` and `get_query_tag_param()` — both provided by `SnowCLIService`.
- File: `src/igloo_mcp/session_utils.py`
- Verify `ensure_session_lock(service)` attaches a lock attribute to arbitrary service instances (works for `SnowCLIService`).
- No change if it doesn’t import Snowflake Labs MCP types.

### 6) MCP tools refactor (4 files)

- Files: `src/igloo_mcp/mcp/tools/execute_query.py`, `health.py`, `preview_table.py`, `test_connection.py`
- Constructors: remove `snowflake_service` param; create `SnowCLIService(profile)` internally (from `Config` or resolved profile).
- Ensure calls use `QueryService.execute_with_service(self.snowflake_service, ...)` so session handling remains centralized.
- Confirm `get_query_tag_param()` is available via `SnowCLIService`.

### 7) SQL validation

- File: `src/igloo_mcp/sql_validation.py`
- Remove imports from `mcp_server_snowflake.query_manager.tools`.
- Implement `get_statement_type()` and `validate_sql_type()` using `sqlglot`, including mapping and case-insensitive checks.
- Keep existing safe alternative generation.

### 8) Imports cleanup

- Remove all `mcp_server_snowflake.*` imports across the repo (`mcp_server.py`, `sql_validation.py`); update type hints if any reference `SnowflakeService`.

## Tests

### 9) Unit tests

- New: `tests/test_snowcli_service.py` for `SnowCLIService` behavior (execute, connection context, rowcount, thread safety).
- Update: `tests/test_mcp_server.py` to reflect new lifecycle and registration; remove assumptions about upstream service.
- Update: `tests/test_sql_validation.py` to validate local SQL validation mapping and behavior.
- Update: `tests/test_services.py` and any tests referring to `SnowflakeService` to use `SnowCLIService` or mocks.

### 10) Integration tests

- Ensure server starts with `create_nanuk_lifespan` and registers all tools.
- Validate end-to-end tool invocations (`execute_query`, `build_catalog`, `query_lineage`, etc.) using mocked SnowCLI or offline fixtures.

### 11) Performance tests (optional but recommended)

- Basic looped execution timing for `SnowCLIService.execute_query()`.
- Memory usage sanity check when instantiating multiple services.

## Documentation

### 12) User-facing docs

- File: `README.md`
- Remove references to Snowflake Labs MCP and “Upstream Snowflake Labs MCP Tools”.
- Update feature list to “SnowCLI-only”, fix quickstart note (“Snowflake CLI required”).
- File: `docs/architecture.md`
- Update architecture diagrams: replace the “Snowflake Labs MCP layer” with “SnowCLI Integration Layer”.
- Remove mentions of upstream connection pooling.
- File: `docs/configuration.md`
- Emphasize Snowflake CLI profiles as the only auth mechanism.
- Add examples for testing profiles via `snow sql` and via MCP server.
- File: `docs/migration-v2.0.1.md`
- Already created; link prominently in README and docs index.
- File: `docs/api/README.md` and `docs/api/tools/*`
- Update tool docs to reflect SnowCLI backing, error samples, and parameter defaults.
- File: `CHANGELOG.md`
- Add v2.0.1 entry: removal of Snowflake Labs MCP, SnowCLI-only architecture, migration notes.

### 13) Inline code documentation

- Add/refresh docstrings:
- `SnowCLIService`: document cursor compatibility, thread safety, and limitations (no true server-side pooling; relies on CLI invocations).
- MCP tools constructors: document that they internally manage `SnowCLIService`.
- `create_nanuk_lifespan`: document lifecycle phases and health checks.
- `sql_validation.py`: document mapping choices and behavior differences vs upstream.
- Remove stale comments referencing “upstream Snowflake MCP layer” in `mcp_server.py` and tool files.

## 17) Package and naming migration

### Naming decisions

- Dist/project name (PyPI, CLI): `igloo-mcp` (hyphen is conventional for CLI and packages).
- Python module/import: `igloo_mcp` (underscore required for import safety).
- CLI entrypoint: `igloo-mcp` (keep `igloo-mcp` as an alias during deprecation).

### Code and packaging changes

- Rename package dir: `src/igloo_mcp/` → `src/igloo_mcp/`.
- Update all imports from `igloo_mcp` → `igloo_mcp`.
- Add compatibility shim: `src/igloo_mcp/__init__.py` re-exporting public API from `igloo_mcp` and emitting `DeprecationWarning`.
- Update entry points in `pyproject.toml`:
- Add `igloo-mcp = "igloo_mcp.mcp_server:main"`.
- Point `igloo-mcp` to `igloo_mcp.mcp_server:main` and emit deprecation on startup.
- Consider delaying `[project].name` rename to `igloo-mcp` until 2.1.0 to avoid breakage (publish both if repo/org supports).

### Documentation and comms

- Update README, docs, examples to prefer `igloo-mcp`/`igloo_mcp`.
- Add migration note: `igloo_mcp`/`igloo-mcp` remain as aliases for one minor release.
- Update badges/links; if repository renamed, update URLs.

### Testing

- Add smoke tests:
- `import igloo_mcp` works; `import igloo_mcp` works with `DeprecationWarning`.
- Both `igloo-mcp` and `igloo-mcp` start the server.

### Deprecation policy

- Emit `DeprecationWarning` on `import igloo_mcp` and when using `igloo-mcp` CLI.
- Document timeline: remove aliases in next major release.

## Validation and QA

### 14) Static analysis and style

- Run: `uv run black . && uv run isort . && uv run flake8 && uv run mypy src`.
- Fix any new type hints for the compatibility cursor (`Protocol` if needed).

### 15) Backward compatibility

- Keep function names, tool names, and MCP arguments stable.
- Maintain environment variable support (`SNOWFLAKE_PROFILE` et al.).
- Provide clear error if user references removed upstream-specific flags.
- Backward-compatible imports/CLI via shims and aliases for one minor release.

### 16) Release and rollout

- Build: `uv build`.
- Tests: `uv run pytest -q`.
- Publish after green build; update docs links.
- If renaming the project on PyPI, publish `igloo-mcp` as a new project and sunset `igloo-mcp` with meta-package or README deprecation.

## Notes on Complexity

- Lifecycle swap: low complexity (local context manager).
- Tools refactor: medium (constructor and service injection changes in 4 files).
- SQL validation: medium (local mapping, ensure parity for common statements).
- Naming migration: medium (repo-wide refactors + shims + docs).

## Acceptance Criteria

- All tests green; no imports from `mcp_server_snowflake.*` remain.
- MCP tools function identically via SnowCLI-only backend.
- Docs and inline docstrings align with new architecture.
- Users can run quickstart with only Snowflake CLI configured.
- New name adopted with compatibility shims: `igloo_mcp` imports OK, `igloo-mcp` CLI works; `igloo_mcp`/`igloo-mcp` emit deprecations but continue to work.

### To-dos

- [ ] Rename package to igloo_mcp and update imports
- [ ] Add igloo-mcp entrypoint; keep igloo-mcp alias with deprecation
- [ ] Create igloo_mcp shim that re-exports igloo_mcp with DeprecationWarning
- [ ] Update README/docs/examples to igloo-mcp/igloo_mcp naming
- [ ] Add tests for deprecation shims and dual CLI commands