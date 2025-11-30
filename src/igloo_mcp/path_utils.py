"""Path helpers for history and artifact storage defaults."""

from __future__ import annotations

import os
from pathlib import Path

from igloo_mcp.mcp.exceptions import MCPValidationError

DEFAULT_HISTORY_PATH = Path("logs/doc.jsonl")
DEFAULT_ARTIFACT_ROOT = Path("logs/artifacts")
DEFAULT_CACHE_SUBDIR = Path("cache")
DEFAULT_REPORTS_SUBDIR = Path("reports")
DEFAULT_CATALOG_SUBDIR = Path("catalogs")


def _get_log_scope() -> str:
    """Get log scope from environment (global|repo)."""
    return os.environ.get("IGLOO_MCP_LOG_SCOPE", "global").lower()


def _is_namespaced_logs() -> bool:
    """Check if namespaced logs are enabled."""
    val = os.environ.get("IGLOO_MCP_NAMESPACED_LOGS", "false").lower()
    return val in ("true", "1", "yes", "on")


def get_global_base() -> Path:
    """Return global base directory (~/.igloo_mcp)."""
    return Path.home() / ".igloo_mcp"


def apply_namespacing(subpath: Path) -> Path:
    """Apply namespacing if enabled (logs/igloo_mcp/... instead of logs/...).

    Args:
        subpath: Relative path to modify (e.g., Path("logs/doc.jsonl"))

    Returns:
        Modified path with igloo_mcp inserted if namespacing enabled
    """
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


def find_repo_root(start: Path | None = None) -> Path:
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


def resolve_history_path(raw: str | None = None, *, start: Path | None = None) -> Path:
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
        base = get_global_base()
        subpath = apply_namespacing(DEFAULT_HISTORY_PATH)
        return (base / subpath).resolve()
    else:
        # repo scope
        repo_root = find_repo_root(start=start)
        subpath = apply_namespacing(DEFAULT_HISTORY_PATH)
        return (repo_root / subpath).resolve()


def resolve_artifact_root(raw: str | None = None, *, start: Path | None = None) -> Path:
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
        base = get_global_base()
        subpath = apply_namespacing(DEFAULT_ARTIFACT_ROOT)
        return (base / subpath).resolve()
    else:
        # repo scope
        repo_root = find_repo_root(start=start)
        subpath = apply_namespacing(DEFAULT_ARTIFACT_ROOT)
        return (repo_root / subpath).resolve()


def resolve_cache_root(
    raw: str | None = None,
    *,
    start: Path | None = None,
    artifact_root: Path | None = None,
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


def resolve_reports_root(
    raw: str | None = None,
    *,
    start: Path | None = None,
) -> Path:
    """Return the root directory for living reports.

    Precedence:
    1. Explicit env path (IGLOO_MCP_REPORTS_ROOT) if raw is None
    2. Derived from instance-specific history/artifact paths (for bundling)
    3. Scope/namespacing defaults if no explicit path
    4. Fallback to repo-based defaults

    Args:
        raw: Explicit path override (takes highest precedence)
        start: Starting directory for repo root detection

    Returns:
        Resolved path to reports root directory
    """
    # Explicit path takes precedence
    candidate = raw if raw is not None else os.environ.get("IGLOO_MCP_REPORTS_ROOT")
    if candidate:
        repo_root = find_repo_root(start=start)
        return _resolve_with_repo_root(candidate, repo_root)

    # Try to derive from instance-specific paths (for bundling with history/artifacts)
    # Check if history or artifacts paths indicate an instance-specific directory
    history_path = os.environ.get("IGLOO_MCP_QUERY_HISTORY")
    artifact_path = os.environ.get("IGLOO_MCP_ARTIFACT_ROOT")

    for instance_path in [history_path, artifact_path]:
        if instance_path:
            try:
                # Expand and resolve the path
                expanded = Path(instance_path).expanduser()
                if expanded.is_absolute():
                    # Extract the base directory (parent of logs/artifacts)
                    # E.g., ~/.igloo-mcp-experimental/logs/query_history.jsonl -> ~/.igloo-mcp-experimental
                    if "logs" in expanded.parts or "artifacts" in expanded.parts:
                        # Find the base igloo-mcp directory
                        parts = expanded.parts
                        for i, part in enumerate(parts):
                            if part in ["logs", "artifacts"]:
                                base_parts = parts[:i]
                                if base_parts:
                                    base_name = base_parts[-1]
                                    if base_name.startswith(".igloo-mcp") or base_name.startswith(".igloo_mcp"):
                                        base_path = Path(*base_parts)
                                        return (base_path / DEFAULT_REPORTS_SUBDIR).resolve()
            except (ValueError, OSError):
                pass  # Invalid path, continue to fallback

    # Scope-based resolution (fallback)
    scope = _get_log_scope()
    if scope == "global":
        base = get_global_base()
        return (base / DEFAULT_REPORTS_SUBDIR).resolve()
    else:
        # repo scope
        repo_root = find_repo_root(start=start)
        return (repo_root / DEFAULT_REPORTS_SUBDIR).resolve()


def resolve_catalog_root(
    raw: str | None = None,
    *,
    start: Path | None = None,
) -> Path:
    """Return the root directory for catalog storage.

    Precedence:
    1. Explicit env path (IGLOO_MCP_CATALOG_ROOT) if raw is None
    2. Derived from instance-specific history/artifact paths (for bundling)
    3. Scope/namespacing defaults if no explicit path
    4. Fallback to repo-based defaults

    Args:
        raw: Explicit path override (takes highest precedence)
        start: Starting directory for repo root detection

    Returns:
        Resolved path to catalog root directory
    """
    # Explicit path takes precedence
    candidate = raw if raw is not None else os.environ.get("IGLOO_MCP_CATALOG_ROOT")
    if candidate:
        repo_root = find_repo_root(start=start)
        return _resolve_with_repo_root(candidate, repo_root)

    # Try to derive from instance-specific paths (for bundling with history/artifacts)
    # Check if history or artifacts paths indicate an instance-specific directory
    history_path = os.environ.get("IGLOO_MCP_QUERY_HISTORY")
    artifact_path = os.environ.get("IGLOO_MCP_ARTIFACT_ROOT")

    for instance_path in [history_path, artifact_path]:
        if instance_path:
            try:
                # Expand and resolve the path
                expanded = Path(instance_path).expanduser()
                if expanded.is_absolute():
                    # Extract the base directory (parent of logs/artifacts)
                    # E.g., ~/.igloo-mcp-experimental/logs/query_history.jsonl -> ~/.igloo-mcp-experimental
                    if "logs" in expanded.parts or "artifacts" in expanded.parts:
                        # Find the base igloo-mcp directory
                        parts = expanded.parts
                        for i, part in enumerate(parts):
                            if part in ["logs", "artifacts"]:
                                base_parts = parts[:i]
                                if base_parts:
                                    base_name = base_parts[-1]
                                    if base_name.startswith(".igloo-mcp") or base_name.startswith(".igloo_mcp"):
                                        base_path = Path(*base_parts)
                                        return (base_path / DEFAULT_CATALOG_SUBDIR).resolve()
            except (ValueError, OSError):
                pass  # Invalid path, continue to fallback

    # Scope-based resolution (fallback)
    scope = _get_log_scope()
    if scope == "global":
        base = get_global_base()
        return (base / DEFAULT_CATALOG_SUBDIR).resolve()
    else:
        # repo scope
        repo_root = find_repo_root(start=start)
        return (repo_root / DEFAULT_CATALOG_SUBDIR).resolve()


def resolve_catalog_path(
    database: str | None = None,
    account_scope: bool = False,
    *,
    catalog_root: Path | None = None,
    start: Path | None = None,
) -> Path:
    """Return the catalog directory path for a specific database or account.

    Args:
        database: Database name (None for current database)
        account_scope: Whether this is an account-wide catalog
        catalog_root: Optional catalog root directory (defaults to resolved root)
        start: Starting directory for repo root detection

    Returns:
        Resolved path to catalog directory:
        - ~/.igloo_mcp/catalogs/account/ for account-wide catalogs
        - ~/.igloo_mcp/catalogs/{database}/ for database-specific catalogs
        - ~/.igloo_mcp/catalogs/current/ for current database (when database is None)
    """
    if catalog_root is None:
        catalog_root = resolve_catalog_root(start=start)

    if account_scope:
        # Account-wide catalogs go to catalogs/account/
        return (catalog_root / "account").resolve()
    elif database:
        # Database-specific catalogs go to catalogs/{database}/
        # Sanitize database name for filesystem safety
        safe_db_name = database.replace("/", "_").replace("\\", "_")
        return (catalog_root / safe_db_name).resolve()
    else:
        # Current database (unknown) goes to catalogs/current/
        return (catalog_root / "current").resolve()


def validate_safe_path(
    path: str | Path,
    *,
    reject_parent_dirs: bool = True,
    reject_absolute: bool = False,
    base_dir: Path | None = None,
) -> Path:
    """Validate and sanitize a file path to prevent path traversal attacks.

    This function ensures that:
    - Paths do not contain parent directory references (..) when reject_parent_dirs=True
    - Paths are relative when reject_absolute=True
    - Paths stay within base_dir when provided
    - Paths do not contain null bytes or other dangerous characters

    Args:
        path: Path string or Path object to validate
        reject_parent_dirs: If True, reject paths containing '..' (default: True)
        reject_absolute: If True, reject absolute paths (default: False)
        base_dir: Optional base directory to restrict paths within

    Returns:
        Validated and resolved Path object

    Raises:
        MCPValidationError: If path is unsafe or invalid

    Examples:
        >>> validate_safe_path("./data_catalogue")
        Path('data_catalogue')

        >>> validate_safe_path("../etc/passwd", reject_parent_dirs=True)
        MCPValidationError: Path contains parent directory references

        >>> validate_safe_path("/etc/passwd", reject_absolute=True)
        MCPValidationError: Absolute paths are not allowed
    """
    # Convert to Path object
    if isinstance(path, str):
        path_obj = Path(path)
    else:
        path_obj = path

    # Check for null bytes (path traversal indicator)
    path_str = str(path_obj)
    if "\x00" in path_str:
        raise MCPValidationError(
            "Path contains null bytes which are not allowed",
            validation_errors=[f"Invalid path: {path_str}"],
            hints=["Remove null bytes from the path"],
        )

    # Expand user directory (~)
    try:
        path_obj = path_obj.expanduser()
    except (ValueError, RuntimeError) as e:
        raise MCPValidationError(
            f"Invalid path format: {e!s}",
            validation_errors=[f"Path expansion failed: {path_str}"],
            hints=["Check that the path is properly formatted"],
        ) from e

    # Reject absolute paths if requested
    if reject_absolute and path_obj.is_absolute():
        raise MCPValidationError(
            "Absolute paths are not allowed",
            validation_errors=[f"Path is absolute: {path_str}"],
            hints=["Use a relative path instead"],
        )

    # Check for parent directory references
    if reject_parent_dirs:
        # Check string representation for '..'
        if ".." in path_str:
            raise MCPValidationError(
                "Path contains parent directory references (..) which are not allowed",
                validation_errors=[f"Path contains '..': {path_str}"],
                hints=[
                    "Remove '..' from the path",
                    "Use a relative path within the current directory",
                ],
            )

        # Also check resolved path to catch symlink-based traversal
        try:
            resolved = path_obj.resolve()
            # Check if resolved path goes outside base_dir
            if base_dir is not None:
                base_resolved = base_dir.resolve()
                try:
                    resolved.relative_to(base_resolved)
                except ValueError:
                    raise MCPValidationError(
                        "Path resolves outside the allowed base directory",
                        validation_errors=[
                            f"Path: {path_str}",
                            f"Resolved to: {resolved}",
                            f"Base directory: {base_resolved}",
                        ],
                        hints=["Ensure the path stays within the base directory"],
                    )
        except (OSError, ValueError) as e:
            # Path might not exist yet, which is okay for validation
            # But if it's a clear traversal attempt, we should catch it
            if ".." in str(e).lower() or "parent" in str(e).lower():
                raise MCPValidationError(
                    f"Path validation failed: {e!s}",
                    validation_errors=[f"Path: {path_str}"],
                    hints=["Check that the path is valid and does not contain '..'"],
                ) from e

    # Normalize the path (remove redundant separators, etc.)
    try:
        normalized = path_obj.resolve() if path_obj.is_absolute() else path_obj
        return normalized
    except (OSError, ValueError):
        # If path doesn't exist, return the normalized path object anyway
        # (it will be created later)
        return path_obj
