"""Typed models for dependency graph outputs."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DependencyNode(BaseModel):
    id: str
    type: Optional[str] = None


class DependencyEdge(BaseModel):
    source: str
    target: str
    relationship: Optional[str] = None


class DependencyCounts(BaseModel):
    nodes: int
    edges: int


class DependencyScope(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    database: Optional[str] = None
    schema_name: Optional[str] = Field(default=None, alias="schema")
    account_scope: bool


class DependencyGraph(BaseModel):
    nodes: list[DependencyNode]
    edges: list[DependencyEdge]
    counts: DependencyCounts
    scope: DependencyScope
