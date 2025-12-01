"""Utilities for loading and searching local catalog artifacts."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class CatalogObject:
    """Normalized catalog object returned from search results."""

    object_type: str
    database: str | None
    schema: str | None
    name: str
    comment: str | None
    columns: list[dict[str, str | None]]
    raw: dict[str, Any]


class CatalogIndex:
    """Lightweight reader for catalog artifacts produced by build_catalog."""

    def __init__(self, catalog_dir: Path | str) -> None:
        self.catalog_dir = Path(catalog_dir)

    # ------------------------------------------------------------------
    def search(
        self,
        *,
        object_types: Sequence[str] | None = None,
        database: str | None = None,
        schema: str | None = None,
        name_contains: str | None = None,
        column_contains: str | None = None,
        limit: int = 20,
    ) -> tuple[list[CatalogObject], int, dict[str, Any]]:
        """Search catalog artifacts using simple substring filters.

        Returns a tuple of ``(results, total_matches, metadata)`` where results
        are capped by ``limit`` but total matches reflect the number of objects
        that satisfied the filters.
        """

        catalog = self._load_catalog()
        meta = cast("dict[str, Any]", catalog.get("metadata", {}))
        raw_columns = cast("Iterable[dict[str, Any]]", catalog.get("columns") or [])
        column_index = self._build_column_index(raw_columns)

        normalized_object_types = {obj.lower() for obj in object_types} if object_types else None

        db_filter = database.lower() if database else None
        schema_filter = schema.lower() if schema else None
        name_filter = name_contains.lower() if name_contains else None
        column_filter = column_contains.lower() if column_contains else None

        results: list[CatalogObject] = []
        total_matches = 0

        for object_type, source_key in self._object_sources().items():
            if normalized_object_types and object_type not in normalized_object_types:
                continue

            raw_entries = cast("Iterable[dict[str, Any]]", catalog.get(source_key, []) or [])
            for raw in raw_entries:
                entry = self._normalize_object(object_type, raw)
                if entry is None:
                    continue

                if db_filter and (entry.database or "").lower() != db_filter:
                    continue
                if schema_filter:
                    schema_value = entry.schema or ""
                    if schema_value.lower() != schema_filter:
                        continue
                if name_filter and name_filter not in entry.name.lower():
                    continue

                columns = column_index.get((entry.database or "", entry.schema or "", entry.name))

                if column_filter and (
                    not columns or not any(column_filter in (col.get("name") or "").lower() for col in columns)
                ):
                    continue

                total_matches += 1
                if len(results) >= limit:
                    continue

                results.append(
                    CatalogObject(
                        object_type=object_type,
                        database=entry.database,
                        schema=entry.schema,
                        name=entry.name,
                        comment=entry.comment,
                        columns=columns or [],
                        raw=raw,
                    )
                )

        return results, total_matches, meta

    # ------------------------------------------------------------------
    def _load_catalog(self) -> dict[str, Any]:
        catalog_json = self.catalog_dir / "catalog.json"
        catalog_jsonl = self.catalog_dir / "catalog.jsonl"

        if catalog_json.exists():
            with catalog_json.open("r", encoding="utf-8") as handle:
                return cast("dict[str, Any]", json.load(handle))
        if catalog_jsonl.exists():
            with catalog_jsonl.open("r", encoding="utf-8") as handle:
                return cast("dict[str, Any]", json.loads(handle.read()))

        raise FileNotFoundError(f"Catalog not found in {self.catalog_dir}. Run build_catalog first.")

    @staticmethod
    def _object_sources() -> dict[str, str]:
        return {
            "database": "databases",
            "schema": "schemas",
            "table": "tables",
            "view": "views",
            "materialized_view": "materialized_views",
            "dynamic_table": "dynamic_tables",
            "task": "tasks",
            "function": "functions",
            "procedure": "procedures",
        }

    @staticmethod
    def _normalize_object(object_type: str, raw: dict[str, Any]) -> CatalogObject | None:
        name_keys: Iterable[str] = (
            "name",
            "table_name",
            "view_name",
            "function_name",
            "procedure_name",
        )
        schema_keys = ("schema_name", "schema", "table_schema", "function_schema")
        database_keys = (
            "database_name",
            "database",
            "table_catalog",
            "function_catalog",
        )
        comment_keys = ("comment", "description")

        name: str | None = None
        for key in name_keys:
            value = raw.get(key)
            if isinstance(value, str) and value:
                name = value
                break

        if not name:
            return None

        schema_value: str | None = None
        for key in schema_keys:
            value = raw.get(key)
            if isinstance(value, str) and value:
                schema_value = value
                break

        database_value: str | None = None
        for key in database_keys:
            value = raw.get(key)
            if isinstance(value, str) and value:
                database_value = value
                break

        comment_value: str | None = None
        for key in comment_keys:
            value = raw.get(key)
            if isinstance(value, str) and value:
                comment_value = value
                break

        return CatalogObject(
            object_type=object_type,
            database=database_value,
            schema=schema_value,
            name=name,
            comment=comment_value,
            columns=[],  # populated later from column index
            raw=raw,
        )

    @staticmethod
    def _build_column_index(
        rows: Iterable[dict[str, Any]],
    ) -> dict[tuple[str, str, str], list[dict[str, str | None]]]:
        index: dict[tuple[str, str, str], list[dict[str, str | None]]] = {}
        for row in rows:
            db = CatalogIndex._first_str(row, ("database_name", "table_catalog")) or ""
            schema = CatalogIndex._first_str(row, ("schema_name", "table_schema")) or ""
            table = CatalogIndex._first_str(row, ("table_name", "name"))
            column = CatalogIndex._first_str(row, ("column_name", "name"))
            if not table or not column:
                continue

            key = (db, schema, table)
            column_entry = {
                "name": column,
                "data_type": CatalogIndex._first_str(row, ("data_type",)),
                "comment": CatalogIndex._first_str(row, ("comment",)),
            }
            index.setdefault(key, []).append(column_entry)

        return index

    @staticmethod
    def _first_str(source: dict[str, Any], keys: Iterable[str]) -> str | None:
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value:
                return value
        return None
