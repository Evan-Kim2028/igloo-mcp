from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .identifiers import QualifiedName, format_fqn, normalize


class ObjectType(str, Enum):
    TABLE = "table"
    VIEW = "view"
    MATERIALIZED_VIEW = "materialized_view"
    DYNAMIC_TABLE = "dynamic_table"
    TASK = "task"

    @property
    def is_dataset(self) -> bool:
        return self in {
            ObjectType.TABLE,
            ObjectType.VIEW,
            ObjectType.MATERIALIZED_VIEW,
            ObjectType.DYNAMIC_TABLE,
        }


@dataclass
class CatalogObject:
    object_type: ObjectType
    name: str
    database: Optional[str]
    schema: Optional[str]
    payload: Dict
    source_file: Path

    def qualified_name(self) -> QualifiedName:
        return QualifiedName(
            normalize(self.database),
            normalize(self.schema),
            normalize(self.name) or self.name,
        )

    def fqn(self) -> str:
        return format_fqn(self.database, self.schema, self.name)

    def ddl(self) -> Optional[str]:
        ddl_text = self.payload.get("ddl")
        if isinstance(ddl_text, str) and ddl_text.strip():
            return ddl_text.strip()
        if self.object_type == ObjectType.VIEW:
            view_def = self.payload.get("VIEW_DEFINITION")
            if isinstance(view_def, str) and view_def.strip():
                return view_def.strip()
        if self.object_type == ObjectType.MATERIALIZED_VIEW:
            text = self.payload.get("text") or self.payload.get("TEXT")
            if isinstance(text, str) and text.strip():
                return text.strip()
        if self.object_type == ObjectType.DYNAMIC_TABLE:
            text = self.payload.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
        if self.object_type == ObjectType.TASK:
            definition = self.payload.get("definition")
            if isinstance(definition, str) and definition.strip():
                return definition.strip()
        return None

    def sql_for_lineage(self) -> Optional[str]:
        if self.object_type == ObjectType.TASK:
            definition = self.payload.get("definition")
            if isinstance(definition, str) and definition.strip():
                return definition.strip()
            ddl_text = self.payload.get("ddl")
            if isinstance(ddl_text, str):
                return ddl_text
            return None
        return self.ddl()


class CatalogLoader:
    FILE_MAP = {
        ObjectType.TABLE: "tables",
        ObjectType.VIEW: "views",
        ObjectType.MATERIALIZED_VIEW: "materialized_views",
        ObjectType.DYNAMIC_TABLE: "dynamic_tables",
        ObjectType.TASK: "tasks",
    }

    def __init__(self, catalog_dir: Path | str) -> None:
        self.catalog_dir = Path(catalog_dir)
        if not self.catalog_dir.exists():
            raise FileNotFoundError(
                f"Catalog directory does not exist: {self.catalog_dir}"
            )

    def load(
        self, object_types: Optional[Iterable[ObjectType]] = None
    ) -> List[CatalogObject]:
        types = set(object_types) if object_types else set(self.FILE_MAP)
        objects: List[CatalogObject] = []
        for obj_type in types:
            base = self.FILE_MAP[obj_type]
            path = self._find_file(base)
            if not path:
                continue
            rows = self._load_rows(path)
            for row in rows:
                name = row.get("TABLE_NAME") or row.get("name")
                db = (
                    row.get("TABLE_CATALOG")
                    or row.get("catalog_name")
                    or row.get("database_name")
                    or row.get("DATABASE_NAME")
                )
                schema = (
                    row.get("TABLE_SCHEMA")
                    or row.get("schema_name")
                    or row.get("SCHEMA_NAME")
                )
                if not name:
                    continue
                objects.append(
                    CatalogObject(
                        object_type=obj_type,
                        name=str(name),
                        database=str(db) if db else None,
                        schema=str(schema) if schema else None,
                        payload=row,
                        source_file=path,
                    )
                )
        return objects

    def _find_file(self, base: str) -> Optional[Path]:
        for ext in (".json", ".jsonl"):
            candidate = self.catalog_dir / f"{base}{ext}"
            if candidate.exists():
                return candidate
        return None

    def _load_rows(self, path: Path) -> List[Dict]:
        if path.suffix.lower() == ".jsonl":
            rows: List[Dict] = []
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rows.append(json.loads(line))
            return rows
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
