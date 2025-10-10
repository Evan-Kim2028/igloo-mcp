from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .loader import ObjectType


@dataclass
class ObjectAuditEntry:
    key: str
    object_type: ObjectType
    status: str
    issues: List[str] = field(default_factory=list)
    upstreams: int = 0
    produces: int = 0

    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "object_type": self.object_type.value,
            "status": self.status,
            "issues": self.issues,
            "upstreams": self.upstreams,
            "produces": self.produces,
        }


@dataclass
class LineageAudit:
    entries: List[ObjectAuditEntry] = field(default_factory=list)
    unknown_references: Dict[str, int] = field(default_factory=dict)

    def totals(self) -> Dict[str, int]:
        totals: Dict[str, int] = {
            "objects": len(self.entries),
            "parsed": sum(1 for e in self.entries if e.status == "parsed"),
            "missing_sql": sum(1 for e in self.entries if e.status == "missing_sql"),
            "parse_error": sum(1 for e in self.entries if e.status == "parse_error"),
        }
        return totals

    def to_dict(self) -> Dict:
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "unknown_references": self.unknown_references,
            "totals": self.totals(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "LineageAudit":
        audit = cls()
        audit.entries = [
            ObjectAuditEntry(
                key=entry["key"],
                object_type=ObjectType(entry["object_type"]),
                status=entry["status"],
                issues=entry.get("issues", []),
                upstreams=entry.get("upstreams", 0),
                produces=entry.get("produces", 0),
            )
            for entry in data.get("entries", [])
        ]
        audit.unknown_references = data.get("unknown_references", {})
        return audit
