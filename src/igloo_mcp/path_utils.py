"""Path helpers for history and artifact storage defaults."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

DEFAULT_HISTORY_PATH = Path("logs/doc.jsonl")
DEFAULT_ARTIFACT_ROOT = Path("logs/artifacts")
DEFAULT_CACHE_SUBDIR = Path("cache")


def _get_log_scope() -> str:
    """Get log scope from environment (global|repo)."""
    return os.environ.get("IGLOO_MCP_LOG_SCOPE", "global").lower()


def _is_namespaced_logs() -> bool:
    """Check if namespaced logs are enabled."""
    val = os.environ.get("IGLOO_MCP_NAMESPACED_LOGS", "false").lower()
    return val in ("true", "1", "yes", "on")


def _get_global_base() -> Path:
    """Return global base directory (~/.igloo_mcp)."""
    return Path.home() / ".igloo_mcp"


def _apply_namespacing(base: Path, subpath: Path) -> Path:
    """Apply namespacing if enabled (logs/igloo_mcp/... instead of logs/...)."""
    if _is_namespaced_logs():
        # Replace logs/ with logs/igloo_mcp/
        parts = list(subpath.parts)
        if parts and parts[0] == "logs":
            parts.insert(1, "igloo_mcp")
            subpath = Path(*parts)
    return subpath


def _iter_candidate_roots(start: Path) -> list[Path]:
    """Return candidate repo roots walking up from *start*."""

    if not start.is_absolute():
        start = start.resolve()
    candidates = [start]
    candidates.extend(start.parents)
    return candidates


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Best-effort detection of the repository root.

    Walks upward from *start* (default: current working directory) until a
    directory containing a ``.git`` entry is found. Falls back to *start* if
    no explicit marker is detected.
    """

    start_path = start or Path.cwd()
    for candidate in _iter_candidate_roots(start_path):
        if (candidate / ".git").exists():
            return candidate
    return start_path


def _resolve_with_repo_root(raw: str, repo_root: Path) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def resolve_history_path(
    raw: Optional[str] = None, *, start: Optional[Path] = None
) -> Path:
    """Return the desired path to the JSONL history file.

    Precedence:
    1. Explicit env path (IGLOO_MCP_QUERY_HISTORY) if raw is None
    2. Scope/namespacing defaults if no explicit path
    3. Fallback to repo-based defaults

    Args:
        raw: Explicit path override (takes highest precedence)
        start: Starting directory for repo root detection

    Returns:
        Resolved path to history file
    """
    # Explicit path takes precedence (back-compat)
    candidate = raw if raw is not None else os.environ.get("IGLOO_MCP_QUERY_HISTORY")
    if candidate:
        repo_root = find_repo_root(start=start)
        return _resolve_with_repo_root(candidate, repo_root)

    # Scope-based resolution
    scope = _get_log_scope()
    if scope == "global":
        base = _get_global_base()
        subpath = _apply_namespacing(base, DEFAULT_HISTORY_PATH)
        return (base / subpath).resolve()
    else:
        # repo scope
        repo_root = find_repo_root(start=start)
        subpath = _apply_namespacing(repo_root, DEFAULT_HISTORY_PATH)
        return (repo_root / subpath).resolve()


def resolve_artifact_root(
    raw: Optional[str] = None, *, start: Optional[Path] = None
) -> Path:
    """Return the root directory for artifacts (queries/results/meta).

    Precedence:
    1. Explicit env path (IGLOO_MCP_ARTIFACT_ROOT) if raw is None
    2. Scope/namespacing defaults if no explicit path
    3. Fallback to repo-based defaults

    Args:
        raw: Explicit path override (takes highest precedence)
        start: Starting directory for repo root detection

    Returns:
        Resolved path to artifact root directory
    """
    # Explicit path takes precedence (back-compat)
    candidate = raw if raw is not None else os.environ.get("IGLOO_MCP_ARTIFACT_ROOT")
    if candidate:
        repo_root = find_repo_root(start=start)
        return _resolve_with_repo_root(candidate, repo_root)

    # Scope-based resolution
    scope = _get_log_scope()
    if scope == "global":
        base = _get_global_base()
        subpath = _apply_namespacing(base, DEFAULT_ARTIFACT_ROOT)
        return (base / subpath).resolve()
    else:
        # repo scope
        repo_root = find_repo_root(start=start)
        subpath = _apply_namespacing(repo_root, DEFAULT_ARTIFACT_ROOT)
        return (repo_root / subpath).resolve()


def resolve_cache_root(
    raw: Optional[str] = None,
    *,
    start: Optional[Path] = None,
    artifact_root: Optional[Path] = None,
) -> Path:
    """Return the root directory for cached query results.

    Precedence:
    1. Explicit env path (IGLOO_MCP_CACHE_ROOT) if raw is None
    2. Derived from artifact_root if provided
    3. Scope/namespacing defaults if no explicit path
    4. Fallback to repo-based defaults

    Args:
        raw: Explicit path override (takes highest precedence)
        start: Starting directory for repo root detection
        artifact_root: Optional artifact root (cache is subdirectory)

    Returns:
        Resolved path to cache root directory
    """
    # Explicit path takes precedence (back-compat)
    candidate = raw if raw is not None else os.environ.get("IGLOO_MCP_CACHE_ROOT")
    if candidate:
        repo_root = find_repo_root(start=start)
        return _resolve_with_repo_root(candidate, repo_root)

    # Derive from artifact_root if provided
    if artifact_root is not None:
        return (artifact_root / DEFAULT_CACHE_SUBDIR).resolve()

    # Scope-based resolution (inherits from artifact_root resolution)
    artifact_path = resolve_artifact_root(start=start)
    return (artifact_path / DEFAULT_CACHE_SUBDIR).resolve()
