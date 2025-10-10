"""Typed catalog models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CatalogBuildTotals(BaseModel):
    """Aggregate counts produced by a catalog build."""

    model_config = ConfigDict(extra="allow")

    databases: int = 0
    schemas: int = 0
    tables: int = 0
    views: int = 0
    materialized_views: int = Field(0, serialization_alias="materialized_views")
    dynamic_tables: int = Field(0, serialization_alias="dynamic_tables")
    tasks: int = 0
    functions: int = 0
    procedures: int = 0
    columns: int = 0


class CatalogMetadata(BaseModel):
    """Input parameters and context for a catalog build."""

    output_dir: Path
    output_format: Literal["json", "jsonl"]
    account_scope: bool
    incremental: bool
    include_ddl: bool
    export_sql: bool
    max_ddl_concurrency: int
    catalog_concurrency: Optional[int] = None


class CatalogBuildResult(BaseModel):
    """Encapsulates catalog build outputs and metadata."""

    totals: CatalogBuildTotals
    metadata: CatalogMetadata
