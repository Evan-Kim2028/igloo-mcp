"""Lineage history management utilities."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .builder import LineageBuilder
from .constants import Formats, Limits
from .utils import validate_path


@dataclass
class LineageSnapshot:
    """Metadata describing a captured lineage snapshot."""

    snapshot_id: str
    timestamp: str
    catalog_path: str
    tag: Optional[str] = None
    description: Optional[str] = None
    storage_file: Optional[str] = None


class LineageHistoryManager:
    """Persist lineage snapshots with simple file-based storage."""

    INDEX_FILE = "snapshots.json"

    def __init__(self, *, storage_path: Optional[Path] = None) -> None:
        self.storage_path = Path(storage_path or Path.cwd() / "lineage_history")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.index_path = self.storage_path / self.INDEX_FILE
        if not self.index_path.exists():
            self._write_index([])

    # ------------------------------------------------------------------
    # Snapshot lifecycle
    # ------------------------------------------------------------------
    def capture_snapshot(
        self,
        catalog_path: Path,
        *,
        tag: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> LineageSnapshot:
        if not validate_path(catalog_path, must_exist=True, allow_absolute_only=False):
            raise ValueError(f"Catalog path '{catalog_path}' is invalid or does not exist")

        builder = LineageBuilder(catalog_path)
        result = builder.build()

        snapshot_id = self._generate_snapshot_id()
        timestamp = datetime.now(timezone.utc).strftime(Formats.ISO_DATE_FORMAT)
        file_name = f"{snapshot_id}.json"

        snapshot = LineageSnapshot(
            snapshot_id=snapshot_id,
            timestamp=timestamp,
            catalog_path=str(Path(catalog_path)),
            tag=tag,
            description=description,
            storage_file=file_name,
        )

        self._save_snapshot(
            snapshot,
            graph_payload=self._graph_to_dict(result.graph),
            audit_payload=self._audit_to_dict(result.audit),
            metadata=metadata or {},
        )
        self._append_snapshot(snapshot)
        self._enforce_retention()
        return snapshot

    def list_snapshots(self, *, tags_only: bool = False) -> List[LineageSnapshot]:
        snapshots = self._read_index()
        if tags_only:
            return [snap for snap in snapshots if snap.tag]
        return snapshots

    def load_snapshot(self, snapshot_id: str) -> Dict:
        for snapshot in self._read_index():
            if snapshot.snapshot_id == snapshot_id:
                if not snapshot.storage_file:
                    raise FileNotFoundError("Snapshot payload missing from index")
                file_path = self.storage_path / snapshot.storage_file
                if not file_path.exists():
                    raise FileNotFoundError(f"Snapshot file '{file_path}' not found")
                return json.loads(file_path.read_text(encoding="utf-8"))
        raise KeyError(f"Snapshot '{snapshot_id}' not found")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _generate_snapshot_id(self) -> str:
        return secrets.token_hex(6)  # 12 characters

    def _append_snapshot(self, snapshot: LineageSnapshot) -> None:
        snapshots = self._read_index()
        snapshots.append(snapshot)
        self._write_index(snapshots)

    def _save_snapshot(
        self,
        snapshot: LineageSnapshot,
        *,
        graph_payload: Dict,
        audit_payload: Dict,
        metadata: Dict[str, str],
    ) -> None:
        storage_file = self.storage_path / (snapshot.storage_file or "")
        payload = {
            "graph": graph_payload,
            "audit": audit_payload,
            "metadata": metadata,
            "captured_at": snapshot.timestamp,
            "catalog_path": snapshot.catalog_path,
            "tag": snapshot.tag,
            "description": snapshot.description,
        }
        storage_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _enforce_retention(self) -> None:
        snapshots = self._read_index()
        if len(snapshots) <= Limits.MAX_SNAPSHOTS:
            return
        surplus = len(snapshots) - Limits.MAX_SNAPSHOTS
        for snapshot in snapshots[:surplus]:
            if snapshot.storage_file:
                try:
                    (self.storage_path / snapshot.storage_file).unlink(missing_ok=True)
                except OSError:
                    pass
        self._write_index(snapshots[surplus:])

    def _read_index(self) -> List[LineageSnapshot]:
        try:
            raw = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [self._snapshot_from_dict(item) for item in raw]

    def _write_index(self, snapshots: List[LineageSnapshot]) -> None:
        payload = [snapshot.__dict__ for snapshot in snapshots]
        self.index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _snapshot_from_dict(self, payload: Dict[str, str]) -> LineageSnapshot:
        return LineageSnapshot(
            snapshot_id=payload.get("snapshot_id", ""),
            timestamp=payload.get("timestamp", ""),
            catalog_path=payload.get("catalog_path", ""),
            tag=payload.get("tag"),
            description=payload.get("description"),
            storage_file=payload.get("storage_file"),
        )

    def _graph_to_dict(self, graph: object) -> Dict:
        if hasattr(graph, "to_dict"):
            try:
                payload = graph.to_dict()  # type: ignore[call-arg]
                if isinstance(payload, dict):
                    return payload
            except Exception:
                pass
        return {"nodes": [], "edges": []}

    def _audit_to_dict(self, audit: object) -> Dict:
        if hasattr(audit, "to_dict"):
            try:
                payload = audit.to_dict()  # type: ignore[call-arg]
                if isinstance(payload, dict):
                    return payload
            except Exception:
                pass
        return {"entries": [], "unknown_references": {}, "totals": {}}


__all__ = ["LineageHistoryManager", "LineageSnapshot"]
