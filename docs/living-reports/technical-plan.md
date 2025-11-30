# Igloo Reports 0.3.0 – Living, Auditable, Agent-Assisted Reports

> **📐 Technical Design Document**
> This document describes the v0.3.0 implementation architecture.
> **For user-facing documentation**, see [User Guide](user-guide.md).
> **Last updated**: November 2025
>
> **Audience**: Contributors, architects, maintainers
> **Scope**: Design decisions, data models, invariants
> **Status**: Implemented in v0.3.0+

## 1. Purpose and Scope
- Define a production-grade reporting subsystem for `igloo-mcp` that creates Obsidian/Notion-style "living" documents fully backed by audited Snowflake data.
- Cover all technical steps, invariants, and integration points required for a robust 0.3.0 release, including a small bundle of existing GitHub issues.

## 2. Goals and Non-Goals
- **Goals**
  - Treat human-authored prose as sacred: the LLM never free-writes narrative, only proposes structured edits for approval.
  - Use a single source of truth (`outline.json`) for insight ranking, section order, and query references; `report.qmd` is always derived.
  - Keep everything local, offline-first, and auditable using `.jsonl` logs consistent with igloo-mcp's existing query history.
  - Ensure rename/move/delete immunity via UUID-based storage and a resilient global index.
  - Guarantee zero silent failures: all mutations are atomic, logged, lock-protected, and revertible.
- **Non-Goals**
  - Cloud sync or real-time multi-user collaboration.
  - Storing reports in a database instead of the filesystem.
  - Allowing the LLM to invent metrics or write long-form prose without grounding in audited query results.

## 3. High-Level Architecture
- **Three-layer model**
  - **Layer 3 – Presentation**: `report.qmd` (Quarto markdown) + rendered artifacts (HTML/PDF/DOCX) consumed by humans.
  - **Layer 2 – Machine Truth**: `outline.json` (sections, insights, 0–10 importance scores, links to query execution_ids/SQL hashes).
  - **Layer 1 – Immutable Memory**: per-report `audit.jsonl` and a global `reports/index.jsonl` aligned with existing history/audit style.
- **Filesystem layout** (under repo root resolved via `find_repo_root()`):
  - `reports/`
    - `by_id/<report_uuid>/`
      - `report.qmd`
      - `outline.json`
      - `audit.jsonl`
      - `assets/` (charts, images, tables, CSV exports)
      - `backups/outline.json.<iso8601>.bak`
    - `index.jsonl` (global mapping `{report_id, current_title, tags, created_at, updated_at}`).
- **Integration points**
  - Use `igloo_mcp.path_utils.find_repo_root()` to resolve `reports/` similar to existing log/history paths.
  - Leverage `igloo_mcp.living_reports.history_index.HistoryIndex` and existing cache manifests to tie report insights back to audited query results.
  - Ensure logs and audit events mirror the JSONL patterns already used for query execution history.

## 4. Data Model and File Formats

### 4.1 Report Identity and Index
- **ReportId**: stable string ID (e.g., `rpt_<url-safe-uuid>`), never reused.
- **Index entry** (stored as JSONL records in `reports/index.jsonl`):
  - `report_id`, `current_title`, `created_at` (UTC ISO8601), `updated_at`, `tags` (list), `status` (e.g., active/archived), `path` (relative path to UUID folder).
- **Index invariants**
  - No symlinks; index always points to real directories.
  - Titles are not unique; CLI resolves title → report_id by best match, but ties are broken by suffix `(2)`, `(3)` on create and by explicit selection when necessary.
  - Index is rebuilt on demand if corruption is detected or UUID folders have drifted.

### 4.2 `outline.json` Schema (Machine Truth)
- Top-level structure (conceptual):
  - `report_id`, `title`, `created_at`, `updated_at`, `version`, `sections` (ordered list), `insights` (list), `metadata` (e.g., tags, owner).
- **Section** object:
  - `section_id` (UUID), `title`, `order`, `insight_ids` (ordered list), optional `notes` (human prose snippets, never edited directly by LLM).
- **Insight** object:
  - `insight_id` (UUID), `importance` (0–10), `status` (active/archived/killed), `summary` (short human-approved text), `supporting_queries` (list of `{execution_id | sql_sha256}`), optional `draft_changes` (pending patches).
- Schema enforcement:
  - Define a Pydantic (or `dataclasses` + validators) model for `Outline` and subtypes.
  - Validate on every load and before every write; reject malformed or unrecognized fields with explicit errors.

### 4.3 `audit.jsonl` Schema (Per-Report History)
- Each line is a JSON object describing a single immutable event:
  - Common fields: `action_id` (UUID), `report_id`, `ts` (UTC ISO8601), `actor` (`"cli"`, `"agent"`, `"human"`), `action_type` (create, evolve, revert, rename, tag_update, render, manual_edit_detected, etc.), `request_id` (optional correlation id).
  - Action-specific payload under `payload` (e.g., patch metadata, previous vs new title, render target path, referenced query_ids).
- **Revertability**
  - For any state-changing action, store a minimal reversible representation (e.g., `before_outline_sha256`, `after_outline_sha256`, or a full pre-image snapshot for small reports).
  - `igloo report revert` uses `audit.jsonl` to reconstruct prior `outline.json` states and writes them back via the same atomic write pipeline.

### 4.4 Backups and Log Rotation
- On any successful `outline.json` write, also write a timestamped backup into `backups/` before replacing the main file.
- Rotate `audit.jsonl` monthly or when exceeding a configurable size (e.g., 50 MB) by rolling to `audit-YYYY-MM.jsonl` and updating index metadata.

## 5. MCP Tool Design: `evolve_report`

### 5.1 Responsibilities
- Single, primary MCP tool responsible for:
  - Loading `outline.json` and relevant `HistoryIndex` records based on referenced datasets.
  - Accepting a high-level user instruction (e.g., "pivot to DAU+revenue"), plus optional constraints (max changes, sections to focus on).
  - Producing **only structured patches** (JSON Patch for `outline.json`, optionally unified diffs for `report.qmd` snippets), no free-form narrative.
  - Applying patches via a safe patch engine, recording every mutation in `audit.jsonl`, and updating backups.

### 5.2 MCP Input Contract
- Tool name: e.g., `evolve_report` under the existing MCP server.
- Parameters:
  - `report_selector`: union of `{report_id, title}`.
  - `instruction`: short natural-language instruction.
  - `constraints`: optional struct (`max_importance_delta`, `sections`, `dry_run`, `max_tokens`, etc.).
  - `context`: optional hints like related report_ids for future multi-report synthesis (v2.0, not in 0.3.0).

### 5.3 MCP Output Contract
- On success:
  - `outline_diff`: machine-readable JSON Patch and/or summary of applied actions.
  - `new_outline`: optional full outline snapshot for clients that want to cache.
  - `audit_entries`: list of action_ids written, for traceability.
  - `warnings`: e.g., skipped patches, validation warnings, manual review required.
- On failure:
  - Never partially write: either no filesystem changes or a fully consistent new outline + audit record.
  - Structured error codes (e.g., `REPORT_NOT_FOUND`, `LOCK_TIMEOUT`, `PATCH_VALIDATION_FAILED`, `IO_ERROR`).

### 5.4 Patch Safety and LLM Guardrails
- LLM must produce strictly-typed output; tool wrapper:
  - Validates JSON against a strict schema.
  - Attempts 3× self-repair on invalid patches, then falls back to a no-op with a `manual_review_required` warning and logged audit event.
- Patch application rules:
  - Use 3-way merge semantics when outline has changed since the LLM read it; on conflict, abort and emit a clear error in `audit.jsonl`.
  - Never modify `report_id`, immutable timestamps, or historical audit records.

## 6. CLI Surface: `igloo report ...`

### 6.1 Commands and Semantics
- `igloo report create "Title"`
  - Allocate new UUID folder, write initial `outline.json` with a stub section and no insights, create initial `audit.jsonl` with `create` event, update `index.jsonl`.
- `igloo report evolve <id|title> "Instruction"`
  - Resolve selector via index, acquire lock, call MCP `evolve_report`, apply patches, append audit entries, update index timestamps.
- `igloo report render <id|title> [--to pdf|docx|html]`
  - Derive `report.qmd` from `outline.json` and render via Quarto; log a `render` action.
- `igloo report revert <id|title> <action_id>`
  - Use `audit.jsonl` to reconstruct the outline state prior to `action_id`, write it back atomically, append a `revert` event.
- `igloo report open "Title"`
  - Resolve title via index and open the report folder or primary artifact with the OS default application.
- `igloo report list [--filter tag:monthly]`
  - Pretty-print a table of reports using `index.jsonl`, with filters over tags/status/time.

### 6.2 Implementation Notes
- Implement CLI via the existing `igloo` entrypoint and click/typer-style patterns already used in the repo.
- Keep all filesystem-side logic in a dedicated report service module; CLI commands should mostly orchestrate arguments and error presentation.

## 7. Storage, Concurrency, and Failure Handling

### 7.1 Locking Protocol
- Per-report lock file (e.g., `<report_dir>/.lock`) acquired before any mutation.
- Implement lock using a cross-platform file locking library (e.g., `portalocker`) already compatible with Windows/macOS/Linux, or a minimal custom wrapper if needed.
- If lock acquisition times out, surface a `LOCK_TIMEOUT` error and log an audit event without mutating state.

### 7.2 Atomic Write Strategy
- Write new versions of `outline.json`, `audit.jsonl`, and `index.jsonl` to `*.tmp` files first.
- `fsync` temp file and directory, then `os.replace()` to guarantee atomic rename semantics across platforms.
- On crash or disk-full mid-write, detect orphaned `*.tmp` files on next access and either roll forward or roll back depending on integrity checks.

### 7.3 Crash Recovery and Manual Edits
- On load, validate `outline.json` against schema and ensure required invariants; if invalid, emit `manual_edit_detected` audit event and either:
  - auto-repair minor issues (e.g., missing non-critical fields), or
  - refuse to mutate until user runs `igloo report doctor` (future) or fixes schema.
- If the user manually deletes or moves a report folder, `igloo report list` rescans `reports/by_id/` and reconciles/repairs `index.jsonl`.

## 8. Integration with Existing igloo-mcp Systems

- Reuse `HistoryIndex` and cache manifest structures to attach concrete datasets and provenance to each insight.
- Tie report audit events into the same high-level audit vocabulary as query executions (matching field names where reasonable).
- Adopt existing `path_utils` helpers for repo-relative paths so that reports behave consistently with logs and catalog artifacts.
- Ensure Snowflake credentials and connection handling live entirely in existing MCP query tools; reports only refer to `execution_id` or cached artifacts.

## 9. Testing, Validation, and Hardening

### 9.1 Unit and Integration Tests
- Unit tests for:
  - `outline.json` models and validation (happy path and malformed inputs).
  - `audit.jsonl` append and rotation behavior.
  - Index rebuild logic when folders are missing, duplicated, or renamed.
- Integration tests for:
  - End-to-end `igloo report create → evolve → render → revert` with a tiny sample dataset.
  - Concurrent evolve attempts on the same report to validate locking.
  - Crash simulation by interrupting between temp write and atomic rename.

### 9.2 Cross-Platform Concerns
- CI matrix should include Windows, macOS, and Linux runs for the new tests.
- Avoid symlinks and any platform-specific paths; rely only on directories and regular files.

### 9.3 Observability
- Add structured logging around `evolve_report` execution, lock acquisition/release, and file writes.
- Ensure error messages surfaced to users suggest corrective actions (e.g., "report locked by another process", "outline schema invalid").

## 10. 0.3.0 Release Scope and Related Issues

### 10.1 Core Igloo Reports Scope (This Document)
- Implement the storage layout, data models, MCP tool, CLI surface, and safety mechanisms described above.
- Wire up a minimal but stable Quarto pipeline for `report.qmd` rendering, with graceful errors if Quarto is not installed.

### 10.2 Existing GitHub Issues to Bundle into 0.3.0
- **#41 – `[BUG] DESCRIBE TABLE misclassified as 'Command'`**
  - Fix SQL classification for `DESCRIBE TABLE` so it is treated as `Describe` and allowed via the MCP layer.
  - Add regression tests to ensure Snowflake `DESCRIBE` statements route correctly.
- **#42 – `[enhancement] Timeout errors: suggest catalog search/filtering by clustering keys before increasing timeout`**
  - Update timeout error messaging and helper suggestions in `query_optimizer`/`mcp_server` to prioritize catalog-based clustering/filtering guidance before increasing `timeout_seconds`.
  - Add tests/fixtures ensuring the new message ordering appears for representative large clustered tables.

## 11. Implementation Phases Checklist

1. **Scaffold reports package and paths**
   - Create `igloo_mcp/reports/` (or similar) module with data models, path resolution, and basic index handling.
2. **Implement data models and schema validation**
   - Define `Outline`, `Section`, `Insight`, `AuditEvent`, and `IndexEntry` types plus JSON (de)serialization and validation.
3. **Implement storage + locking + atomic writes**
   - Add helpers for safely reading/writing `outline.json`, `audit.jsonl`, and `index.jsonl` with locking and backups.
4. **Implement MCP `evolve_report` tool**
   - Define MCP schema, wrap LLM calls, implement patch validation and application, and hook into audit/storage.
5. **Wire CLI commands**
   - Add `igloo report create/evolve/render/revert/open/list` commands that delegate to the report service.
6. **Integrate with HistoryIndex and query artifacts**
   - Implement resolution from insight references to cached rows/manifests and ensure no direct Snowflake queries are issued here.
7. **Add tests, crash/locking simulations, and cross-platform CI coverage**
   - Cover all invariants and error paths described above.
8. **Tackle bundled issues #41 and #42**
   - Implement fixes and tests for DESCRIBE classification and improved timeout guidance.

This plan is the authoritative technical blueprint for the 0.3.0 Igloo Reports release; future PRs should reference relevant sections and mark completed checklist items as they land.

## See Also

- [Living Reports User Guide](user-guide.md) - User-facing documentation
- [API Reference](../api/README.md) - MCP tools documentation
- [Getting Started Guide](../getting-started.md) - Quick start overview
