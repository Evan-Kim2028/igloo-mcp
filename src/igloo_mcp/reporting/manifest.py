from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class TemplatesConfig(BaseModel):
    """Template configuration for a report manifest.

    Attributes:
        main: Path to the primary narrative template, relative to the manifest file.
        engine: Template engine identifier (e.g. "jinja").
        search_paths: Optional additional search paths for templates, relative to
            the manifest directory.
    """

    model_config = ConfigDict(extra="forbid")

    main: str = Field(..., description="Primary narrative template path")
    engine: str = Field("jinja", description="Template engine name")
    search_paths: List[str] = Field(
        default_factory=list,
        description="Additional template search paths, relative to manifest dir",
    )


class DatasetSource(BaseModel):
    """Source binding for a dataset within a report.

    At least one of execution_id, sql_sha256, or cache_manifest must be
    provided so the resolver can bind this dataset to concrete history/cache
    artifacts.
    """

    model_config = ConfigDict(extra="forbid")

    execution_id: Optional[str] = Field(
        default=None,
        description="Execution ID from audit_info.execution_id or history JSONL",
    )
    sql_sha256: Optional[str] = Field(
        default=None,
        description="SHA-256 hash of the SQL text (statement_sha256)",
    )
    cache_manifest: Optional[str] = Field(
        default=None,
        description=(
            "Path to a cache manifest.json (absolute or repo-relative). When "
            "provided, this takes precedence over history lookups."
        ),
    )
    cache_only: bool = Field(
        default=False,
        description="If true, do not attempt to re-run queries (reserved).",
    )

    # Future hints for profile/context overrides (stored but unused for now).
    profile: Optional[str] = Field(default=None)
    warehouse: Optional[str] = Field(default=None)
    database: Optional[str] = Field(default=None)
    db_schema: Optional[str] = Field(default=None, alias="schema")
    role: Optional[str] = Field(default=None)

    @model_validator(mode="after")
    def _ensure_identifier(self) -> "DatasetSource":  # pragma: no cover - simple guard
        if not (self.execution_id or self.sql_sha256 or self.cache_manifest):
            raise ValueError(
                "DatasetSource requires at least one of execution_id, "
                "sql_sha256, or cache_manifest"
            )
        return self


class DatasetRef(BaseModel):
    """Logical dataset used by a report.

    The name is used as the key inside the template context under
    ``datasets[name]``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Template-visible dataset identifier")
    description: Optional[str] = Field(
        default=None, description="Optional human-readable description"
    )
    source: DatasetSource = Field(..., description="Backing query/cache binding")
    tags: List[str] = Field(default_factory=list)


class ReportOutput(BaseModel):
    """Single named output for a report build.

    For example, a Markdown narrative, an HTML export, or a JSON payload used by
    downstream systems.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Logical name for this output")
    format: Literal["markdown", "html", "json"] = Field(
        ...,
        description="Output format identifier",
    )
    path: str = Field(
        ...,
        description="Destination path for the rendered output",
    )
    from_output: Optional[str] = Field(
        default=None,
        description=(
            "Optional upstream output to derive from (e.g. HTML from Markdown)."
        ),
    )


class ReportManifest(BaseModel):
    """Top-level manifest describing a narrative analytics report."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable identifier for this report")
    title: Optional[str] = Field(default=None)
    version: Optional[str] = Field(default=None)
    author: Optional[str] = Field(default=None)
    created_at: Optional[str] = Field(default=None)
    updated_at: Optional[str] = Field(default=None)

    templates: TemplatesConfig
    datasets: List[DatasetRef] = Field(default_factory=list)
    outputs: List[ReportOutput] = Field(default_factory=list)


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Manifest file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise ValueError(
            f"Expected mapping at root of manifest {path}, got {type(data)!r}"
        )
    return data


def load_manifest(path: Path | str) -> ReportManifest:
    """Load and validate a report manifest from YAML.

    The *path* may be absolute or relative. Relative paths are resolved
    relative to the current working directory. Callers that need repo-root
    resolution should construct an absolute path beforehand.
    """

    manifest_path = Path(path).expanduser().resolve()
    data = _load_yaml_file(manifest_path)
    try:
        return ReportManifest(**data)
    except ValidationError as exc:
        # Re-raise as ValueError for a simpler public surface while keeping
        # the original error for debugging when needed.
        raise ValueError(f"Invalid report manifest at {manifest_path}: {exc}") from exc


def manifest_json_schema() -> Dict[str, Any]:
    """Return the JSON schema for :class:`ReportManifest`."""

    return ReportManifest.model_json_schema()


__all__ = [
    "TemplatesConfig",
    "DatasetSource",
    "DatasetRef",
    "ReportOutput",
    "ReportManifest",
    "load_manifest",
    "manifest_json_schema",
]
