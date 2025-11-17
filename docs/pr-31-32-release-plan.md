## Context

- PR #31 (`issue-29-report-manifest-builder`): introduces manifest-driven reporting primitives: `igloo_mcp.reporting` package, `igloo-report` CLI (build/lint/scaffold), history index, example manifests, and focused tests. At creation time, a few `execute_query`-related tests on `main` were already failing; new reporting tests were green.
- PR #32 (`feature/query-tooling-upgrades`): adds a Snowflake REST query driver, query optimizer/advisor and `igloo` CLI entrypoint, SQL object parsing, hardened `ExecuteQueryTool` guardrails, and consolidates reporting MCP tools (`report_scaffold` / `report_build`) on top of the manifest model. Full test suite is currently passing on this branch.
- Both PRs touch reporting surfaces (manifests + CLI + MCP tools) and query execution surfaces (history, cache, guardrails), so they should be reviewed and released as a coherent upgrade rather than in isolation.

## Key findings

- Reporting stack structure:
  - PR #31 establishes the core reporting model: `reporting.manifest`, `reporting.builder`, `reporting.history_index`, `report_cli`, example manifests, and tests.
  - PR #32 reuses these primitives from the MCP server, exposing `report_scaffold` and `report_build` tools for agent workflows and slightly adjusts behavior/params (e.g. `validate_only`, richer descriptions, provenance and output-path handling).
  - There is intentional overlap between `igloo-report` CLI and the MCP tools; they should remain thin wrappers over the same reporting core to avoid divergence.
- Query / cache / history:
  - PR #32 hardens `ExecuteQueryTool` by pulling profile health and SQL-permission checks into reusable helpers and ensuring they run up front for both sync and async paths.
  - SQL object parsing (`sql_objects.extract_query_objects`) is wired through to cache manifests and history entries so downstream tools (including reporting and optimizer) can introspect referenced tables.
  - Query result cache manifests and history records gain an `objects` field alongside existing `key_metrics`/`insights`, which is a cross-cutting change touching cache, history, and MCP tool logic.
- REST driver and optimizer:
  - REST driver (`snow_rest.SnowRestClient`) provides an alternative execution path used by `QueryService` behind an env-flag; it relies on key-pair JWT auth and Snowflake SQL REST semantics.
  - Query optimizer (`query_optimizer` + `igloo.cli query optimize`) consumes history/cache metadata (including `objects`) to emit human/agent-readable findings.
- Risk/ordering considerations:
  - Reporting features from PR #31 are a dependency of the reporting MCP tools in PR #32; when reviewing, treat #31 as the base reporting layer and #32 as an integration/expansion on top.
  - Guardrail and history changes in #32 affect a wide surface (MCP tools, cache, history, optimizer); they should be validated against existing tests and any manual workflows you rely on before release.
  - There are no intentional behavioral changes to existing CLI entrypoints beyond the new `igloo`/`igloo-report` commands and stricter guardrails; regressions should be treated as bugs.

## Review plan for PR #31 (reporting + igloo-report)

1. **Surface-level pass**
   - Skim `pyproject.toml` additions to confirm `jinja2` + `igloo-report` script entry are correct and version bump is appropriate for a new CLI surface (likely next minor, e.g. `0.3.0`).
   - Note new modules and tests: `src/igloo_mcp/reporting/*`, `src/igloo_mcp/report_cli.py`, `tests/test_reporting_*`, `tests/test_report_mcp_tools.py` hooks.
2. **Model and builder review**
   - Review `reporting.manifest` models for:
     - Backwards-compatible YAML shape (ids, templates, datasets, outputs) and clear invariants (dataset source identifiers, required fields).
     - JSON schema helper coverage and how it is intended to be used by agents or tooling.
   - Review `reporting.builder` for:
     - How it resolves datasets from cache/history (`HistoryIndex`, cache manifests) and builds provenance.
     - Clear error modes and `LintIssue` coverage for missing cache manifests, unresolvable datasets, or malformed history entries.
3. **History index and integration points**
   - Inspect `reporting.history_index` to understand how it reads history JSONL and exposes a stable API for both CLI and MCP tools.
   - Verify it does not assume a particular history layout that might be changed by the query tooling in PR #32; note fields it relies on (`execution_id`, `sql_sha256`, `artifacts.cache_manifest`, etc.).
4. **CLI behavior and UX**
   - Exercise `igloo-report` locally (build, lint, scaffold) using example manifests under `examples/reports`:
     - Confirm path resolution rules (relative to repo root vs absolute) and error messages are clear.
     - Validate that scaffolded manifests are minimal but usable, and lint/build behave predictably on them.
5. **Tests and quality gates**
   - Run `ruff`, `mypy`, and `pytest` on `issue-29-report-manifest-builder`.
   - Confirm that only the previously-known `execute_query` failures reproduce on `main` and that all new reporting tests pass.
   - Capture any deviations from this expectation as blockers for merging #31.

## Review plan for PR #32 (query tooling + reporting MCP tools)

1. **Surface-level pass**
   - Review `pyproject.toml` updates (`pyjwt`, CLI entries) and ensure they are compatible with changes from #31 (no duplicate/conflicting script definitions).
   - Map new/changed files: `snow_rest`, `query_optimizer`, `sql_objects`, `mcp/tools/execute_query.py` guardrails, `cache/query_result_cache.py`, `mcp_server.py` reporting tools, `cli.py`, and associated tests (`test_query_service_rest`, `test_sql_objects`, `test_report_mcp_tools`, etc.).
2. **REST driver and query service**
   - Review `SnowRestConfig`/`SnowRestClient` for:
     - Correct environment variable contract (`SNOWFLAKE_REST_*`) and safe error surfaces.
     - JWT generation details (issuer/subject, audience with `:443`, expiry) and request headers.
   - Check `QueryService` driver selection logic and fallback behavior when REST config is incomplete, ensuring no regressions to the CLI driver path.
3. **Guardrails and permissions**
   - Review changes to `ExecuteQueryTool` for:
     - Centralized profile health validation (`_ensure_profile_health`) and SQL permission enforcement (`_enforce_sql_permissions`).
     - Consistent behavior across `sync`, `async`, and `auto` response modes, including how inline wait budgets are computed and when async jobs are scheduled.
   - Confirm that error types remain `ValueError` for invalid SQL or profiles so existing tests and clients do not break.
4. **SQL object parsing and propagation**
   - Inspect `sql_objects.extract_query_objects` and its tests to ensure it:
     - Handles typical Snowflake 3-part names and aliases and returns unique objects.
     - Fails safely (e.g., empty or unparsable SQL) without crashing the execution path.
   - Trace how `objects` are attached to cache manifests, history records, and `ExecuteQueryTool` responses for downstream consumers.
5. **Optimizer and CLI**
   - Review `query_optimizer` and `igloo.cli` for:
     - How they consume history/cache metadata (including `objects`, `key_metrics`, `insights`) to produce findings.
     - Output format stability for both text and JSON, so agents and humans can rely on the structure.
6. **Reporting MCP tools integration**
   - Compare MCP `report_scaffold` / `report_build` implementations in `mcp_server` with the CLI + builder from #31:
     - Ensure they delegate to `reporting.builder`/`reporting.manifest` and do not fork logic.
     - Check parameter descriptions for agent friendliness (clear defaults, path semantics, behavior of `validate_only`, `fail_on_issues`, `persist_output`).
   - Confirm tests in `test_report_mcp_tools` cover key behaviors: scaffold shape, validation failures, and build outputs.
7. **Tests and quality gates**
   - Run `ruff`, `mypy`, and `pytest` on `feature/query-tooling-upgrades` and verify all checks pass.
   - Pay special attention to tests around history, cache, and guardrails to confirm no regressions were introduced by the new `objects` field or async behavior.

## Integration and release plan (no implementation yet)

This section describes the future integration steps; **do not perform them yet**. The goal is a single cohesive release that ships both PRs together.

1. **Stabilize `main` and branches**
   - Ensure `main` is green or at least that any outstanding failures are understood and documented.
   - Rebase `issue-29-report-manifest-builder` (#31) onto the latest `main` and re-run `ruff`/`mypy`/`pytest`; resolve conflicts and regressions on that branch.
   - Rebase `feature/query-tooling-upgrades` (#32) onto the latest `main` (or onto the rebased #31 once it lands in `main`, depending on conflict patterns); re-run checks.
2. **Decide release scope and versioning**
   - Treat the combined changes as a minor version bump (e.g. from `0.2.3` to `0.3.0`) given the new CLIs, REST driver, and reporting surfaces.
   - Draft high-level release notes covering:
     - New features: manifest-driven reporting (`igloo-report` + MCP tools), REST driver & query optimizer, SQL object extraction.
     - Behavioral changes: stricter SQL/profile guardrails, richer history/cache metadata (including `objects`).
     - Migration notes: any new env vars (`SNOWFLAKE_REST_*`), recommended workflows for agents using reporting tools.
3. **Create a release branch (future)**
   - From the up-to-date `main`, create `release/v0.3.0` (or similar) to group the upgrade train.
   - Merge PR #31 into `release/v0.3.0` (fast-forward or via `git merge --no-ff`), resolving conflicts and ensuring tests pass.
   - Merge PR #32 into `release/v0.3.0`, resolving conflicts:
     - Pay particular attention to overlapping files: `pyproject.toml`, `mcp_server`, reporting modules, history/cache code.
     - Keep `reporting` models/builder as the single point of truth; avoid duplicating reporting logic between CLI and MCP tools.
4. **Full validation on the release branch**
   - On `release/v0.3.0`, run:
     - `ruff` and `mypy` against `src/` and `tests/`.
     - Full `pytest` and, if available, any smoke or integration scripts (`uv run -- pytest`, additional scripts under `scripts/`).
   - Optionally perform manual smoke tests:
     - Run `igloo-mcp` locally and exercise a few `execute_query` calls (success, invalid SQL, invalid profile) to ensure guardrails behave as expected.
     - Use `igloo-report scaffold/lint/build` and MCP `report_scaffold`/`report_build` tools on sample history to validate the end-to-end reporting flow.
5. **Ship to `main` and tag**
   - Open a “Release v0.3.0” PR from `release/v0.3.0` into `main` with consolidated release notes.
   - Require at least one reviewer to sign off on both reporting and query tooling aspects.
   - Once merged, tag the release (e.g. `v0.3.0`) and, if used, publish to PyPI.

## Pattern for future multi-PR upgrade trains

- **Planning and scoping**
  - When multiple features (e.g. reporting, query tooling, MCP surfaces) are intended to ship together, create a GitHub milestone and label (e.g. `release:v0.3.0`) and attach all related issues/PRs.
  - Keep each feature in its own PR/branch, but require a lightweight “release plan” document like this one for any non-trivial train.
- **Branch and PR discipline**
  - Ensure each PR is:
    - Independently reviewable and testable.
    - Kept rebased on `main` (or a shared integration branch) to minimize conflict drift.
    - Focused on one concern (e.g. reporting core vs query tooling) with clear boundaries.
- **Release branch workflow**
  - For each train, create a temporary `release/vX.Y.Z` branch from `main` once the constituent PRs are close to ready.
  - Merge the feature PRs into that release branch in dependency order (core libraries first, integrations second), resolving conflicts once.
  - Run full checks only on the release branch, then merge that branch back into `main` via a single “release” PR.
- **Documentation and communication**
  - Maintain a short `notes/` or `docs/` entry for each train summarizing:
    - Features included and their user-facing impact.
    - Any guardrail or behavior changes.
    - Migration and configuration steps.
  - Use this as the basis for release notes and for bringing reviewers up to speed quickly.

This file is intentionally planning-only and should not be used as a substitute for code review or automated checks; it is a checklist and rationale for how to review and ship PRs #31 and #32 together as a cohesive release.
