"""Transformation tracking utilities for lineage analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .base import BaseAnalyzer
from .constants import Thresholds


@dataclass
class TransformationRecord:
    """Individual column transformation metadata."""

    target_column: str
    source_columns: List[str]
    expression: Optional[str] = None
    transformation_type: str = "direct"
    confidence: float = Thresholds.HIGH_CONFIDENCE

    def to_dict(self) -> Dict[str, object]:
        return {
            "target_column": self.target_column,
            "source_columns": list(self.source_columns),
            "expression": self.expression,
            "transformation_type": self.transformation_type,
            "confidence": self.confidence,
        }


class TransformationTracker(BaseAnalyzer):
    """Utility for aggregating transformation statistics."""

    def __init__(self, *, name: str = "transformation_tracker") -> None:
        super().__init__(name)
        self._records: List[TransformationRecord] = []

    def add_transformation(
        self,
        target_column: str,
        source_columns: Iterable[str],
        *,
        expression: Optional[str] = None,
        transformation_type: str = "direct",
        confidence: float = Thresholds.HIGH_CONFIDENCE,
    ) -> None:
        record = TransformationRecord(
            target_column=target_column,
            source_columns=list(source_columns),
            expression=expression,
            transformation_type=transformation_type,
            confidence=confidence,
        )
        self._records.append(record)
        self.increment_metric("transformations_recorded")

    def get_records(self) -> List[TransformationRecord]:
        return list(self._records)

    def summarize(self) -> Dict[str, object]:
        counts = Counter(record.transformation_type for record in self._records)
        avg_confidence = (
            sum(record.confidence for record in self._records) / len(self._records)
            if self._records
            else 0.0
        )
        self.update_metric("average_confidence", avg_confidence)
        self.update_metric("transformation_types", dict(counts))
        return self.get_metrics()


__all__ = ["TransformationTracker", "TransformationRecord"]
