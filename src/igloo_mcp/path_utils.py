"""Path helpers for history and artifact storage defaults."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

DEFAULT_HISTORY_PATH = Path("logs/doc.jsonl")
DEFAULT_ARTIFACT_ROOT = Path("logs/artifacts")
DEFAULT_CACHE_SUBDIR = Path("cache")


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
    """Return the desired path to the JSONL history file."""

    repo_root = find_repo_root(start=start)
    candidate = raw if raw is not None else os.environ.get("IGLOO_MCP_QUERY_HISTORY")
    if candidate:
        return _resolve_with_repo_root(candidate, repo_root)
    return (repo_root / DEFAULT_HISTORY_PATH).resolve()


def resolve_artifact_root(
    raw: Optional[str] = None, *, start: Optional[Path] = None
) -> Path:
    """Return the root directory for artifacts (queries/results/meta)."""

    repo_root = find_repo_root(start=start)
    candidate = raw if raw is not None else os.environ.get("IGLOO_MCP_ARTIFACT_ROOT")
    if candidate:
        return _resolve_with_repo_root(candidate, repo_root)
    return (repo_root / DEFAULT_ARTIFACT_ROOT).resolve()


def resolve_cache_root(
    raw: Optional[str] = None,
    *,
    start: Optional[Path] = None,
    artifact_root: Optional[Path] = None,
) -> Path:
    """Return the root directory for cached query results."""

    repo_root = find_repo_root(start=start)
    candidate = raw if raw is not None else os.environ.get("IGLOO_MCP_CACHE_ROOT")
    if candidate:
        return _resolve_with_repo_root(candidate, repo_root)
    base_root = artifact_root or resolve_artifact_root(start=start)
    return (base_root / DEFAULT_CACHE_SUBDIR).resolve()
