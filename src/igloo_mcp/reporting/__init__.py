"""Reporting utilities for manifest-driven analytics narratives.

This package provides:
- Pydantic models for report manifests
- Helpers for indexing query history and cache artifacts
- A small builder API for rendering manifests into deterministic outputs
"""

from __future__ import annotations

from .builder import LintIssue, build_report, lint_report
from .manifest import (
    DatasetRef,
    DatasetSource,
    ReportManifest,
    ReportOutput,
    TemplatesConfig,
    load_manifest,
    manifest_json_schema,
)

__all__ = [
    "DatasetRef",
    "DatasetSource",
    "ReportManifest",
    "ReportOutput",
    "TemplatesConfig",
    "LintIssue",
    "build_report",
    "lint_report",
    "load_manifest",
    "manifest_json_schema",
]
