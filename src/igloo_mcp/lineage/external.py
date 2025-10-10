"""External source mapping utilities for lineage."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .constants import Limits
from .utils import validate_path


class ExternalSourceType(str, Enum):
    """Supported external source backends."""

    S3 = "s3"
    AZURE_BLOB = "azure_blob"
    GCS = "gcs"
    HTTP = "http"
    STAGE = "stage"


@dataclass
class ExternalSource:
    """Representation of a mapped external source."""

    source_type: ExternalSourceType
    location: str
    stage_name: Optional[str] = None
    file_pattern: Optional[str] = None
    file_format: Optional[str] = None
    credentials_ref: Optional[str] = None
    encryption: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type.value,
            "location": self.location,
            "stage_name": self.stage_name,
            "file_pattern": self.file_pattern,
            "file_format": self.file_format,
            "has_credentials": self.credentials_ref is not None,
            "encryption": self.encryption or {},
        }


@dataclass
class ExternalMappingResult:
    """Container for mapping operations (useful for testing)."""

    sources: List[ExternalSource] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)

    def add_issue(self, message: str) -> None:
        self.issues.append(message)


class ExternalSourceMapper:
    """Best-effort mapper that inspects catalog exports for external sources."""

    def __init__(self, catalog_path: Path) -> None:
        self.catalog_path = Path(catalog_path)

    def map_sources(self) -> ExternalMappingResult:
        result = ExternalMappingResult()
        if not self.catalog_path.exists():
            result.add_issue(f"Catalog path '{self.catalog_path}' does not exist")
            return result

        manifest_files = list(self.catalog_path.glob("external_sources*.jsonl"))
        if not manifest_files:
            return result

        for payload in self._iter_rows(manifest_files):
            source = self._row_to_source(payload)
            if source:
                result.sources.append(source)

        if len(result.sources) > Limits.MAX_PATHS:
            result.sources = result.sources[: Limits.MAX_PATHS]
            result.add_issue("External source list truncated to MAX_PATHS items")

        return result

    def _iter_rows(self, files: Iterable[Path]) -> Iterable[Dict[str, Any]]:
        for file_path in files:
            if not validate_path(file_path, must_exist=True, allow_absolute_only=False):
                continue
            try:
                with file_path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
            except OSError:
                continue

    def _row_to_source(self, payload: Dict[str, Any]) -> Optional[ExternalSource]:
        location = payload.get("location") or payload.get("url")
        if not location:
            return None

        source_type = self._infer_type(location)
        credentials_ref = payload.get("credentials_ref")
        if credentials_ref and not isinstance(credentials_ref, str):
            credentials_ref = None

        return ExternalSource(
            source_type=source_type,
            location=location,
            stage_name=payload.get("stage_name"),
            file_pattern=payload.get("file_pattern"),
            file_format=payload.get("file_format"),
            credentials_ref=credentials_ref,
            encryption=payload.get("encryption"),
        )

    def _infer_type(self, location: str) -> ExternalSourceType:
        lowered = location.lower()
        if lowered.startswith("s3://"):
            return ExternalSourceType.S3
        if lowered.startswith("azure://"):
            return ExternalSourceType.AZURE_BLOB
        if lowered.startswith("gcs://"):
            return ExternalSourceType.GCS
        if lowered.startswith("http://") or lowered.startswith("https://"):
            return ExternalSourceType.HTTP
        return ExternalSourceType.STAGE


__all__ = [
    "ExternalSource",
    "ExternalSourceMapper",
    "ExternalSourceType",
    "ExternalMappingResult",
]
