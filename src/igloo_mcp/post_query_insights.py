"""Lightweight heuristics for deriving post-query insights from returned rows."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

MAX_SAMPLE_ROWS = 2_000
TOP_VALUES_LIMIT = 5
TIME_HINT_KEYWORDS = ("timestamp", "_ts", "_time", "time", "date", "_dt", "at_ts")


def _normalize_row(row: Any, existing_columns: Sequence[str] | None) -> tuple[dict[str, Any], list[str] | None]:
    """Return a mapping representation of a row and inferred column names."""

    if isinstance(row, dict):
        mapping = dict(row)
        inferred: list[str] | None = None
        if not existing_columns:
            inferred = list(mapping.keys())
        return mapping, inferred

    if isinstance(row, (list, tuple)):
        names: list[str]
        names = list(existing_columns) if existing_columns else [f"column_{idx}" for idx in range(len(row))]
        mapping = {names[idx] if idx < len(names) else f"column_{idx}": value for idx, value in enumerate(row)}
        inferred = None if existing_columns else list(mapping.keys())
        return mapping, inferred

    # Scalar fallback
    return {"value": row}, ([] if existing_columns else ["value"])


def _coerce_numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        try:
            return float(value)
        except (OverflowError, ValueError):
            # Decimal too large or invalid for float conversion
            return None
    return None


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    return None


def _is_time_hint(column_name: str) -> bool:
    lower = column_name.lower()
    return any(hint in lower for hint in TIME_HINT_KEYWORDS)


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _summarize_column(
    column: str,
    rows: list[dict[str, Any]],
    sample_size: int,
) -> dict[str, Any] | None:
    if sample_size == 0:
        return None

    non_null = 0
    numeric_count = 0
    numeric_sum = 0.0
    numeric_min: float | None = None
    numeric_max: float | None = None
    time_count = 0
    time_min: datetime | None = None
    time_max: datetime | None = None
    categorical_counter: Counter[str] = Counter()

    for row in rows:
        value = row.get(column)
        if value is None:
            continue
        non_null += 1

        number = _coerce_numeric(value)
        if number is not None:
            numeric_count += 1
            numeric_sum += number
            numeric_min = number if numeric_min is None else min(numeric_min, number)
            numeric_max = number if numeric_max is None else max(numeric_max, number)

        moment = _coerce_datetime(value)
        if moment is not None:
            time_count += 1
            time_min = moment if time_min is None else min(time_min, moment)
            time_max = moment if time_max is None else max(time_max, moment)

        categorical_counter[_stringify(value)] += 1

    if non_null == 0:
        return None

    non_null_ratio = round(non_null / sample_size, 3)
    preferred_kind = "categorical"
    kind_score = sum(categorical_counter.values())

    if numeric_count >= max(time_count, kind_score) and numeric_count >= 2:
        preferred_kind = "numeric"
        kind_score = numeric_count

    if (_is_time_hint(column) and time_count > 0) or (time_count >= max(numeric_count, kind_score) and time_count >= 2):
        preferred_kind = "time"
        kind_score = time_count

    if preferred_kind == "numeric" and numeric_min is not None and numeric_max is not None:
        avg = numeric_sum / max(numeric_count, 1)
        return {
            "name": column,
            "kind": "numeric",
            "non_null_ratio": non_null_ratio,
            "min": round(numeric_min, 6),
            "max": round(numeric_max, 6),
            "avg": round(avg, 6),
        }

    if preferred_kind == "time" and time_min is not None and time_max is not None:
        span = (time_max - time_min).total_seconds() * 1000
        return {
            "name": column,
            "kind": "time",
            "non_null_ratio": non_null_ratio,
            "min_ts": time_min.isoformat(),
            "max_ts": time_max.isoformat(),
            "span_ms": int(span),
        }

    if categorical_counter:
        total = sum(categorical_counter.values()) or 1
        top_values = []
        for value, count in categorical_counter.most_common(TOP_VALUES_LIMIT):
            top_values.append(
                {
                    "value": value[:120],
                    "count": count,
                    "ratio": round(count / total, 3),
                }
            )
        return {
            "name": column,
            "kind": "categorical",
            "non_null_ratio": non_null_ratio,
            "top_values": top_values,
            "distinct_values": len(categorical_counter),
        }

    return None


def _compose_insights(key_metrics: dict[str, Any]) -> list[str]:
    insights: list[str] = []
    total_rows = key_metrics.get("total_rows")
    sampled_rows = key_metrics.get("sampled_rows")
    num_columns = key_metrics.get("num_columns")
    truncated = key_metrics.get("truncated_output", False)

    if isinstance(total_rows, int) and isinstance(num_columns, int):
        if isinstance(sampled_rows, int) and truncated and sampled_rows < total_rows:
            insights.append(f"Analyzed first {sampled_rows:,} of {total_rows:,} rows across {num_columns} columns.")
        else:
            insights.append(f"Returned {total_rows:,} rows across {num_columns} columns.")

    for column in key_metrics.get("columns", []):
        if len(insights) >= 5:
            break
        kind = column.get("kind")
        name = column.get("name", "column")
        if kind == "numeric" and column.get("min") is not None and column.get("max") is not None:
            insights.append(f"{name} spans {column['min']} → {column['max']} (avg {column.get('avg')}).")
        elif kind == "categorical" and column.get("top_values"):
            top = column["top_values"][0]
            pct = round(top.get("ratio", 0) * 100, 1)
            insights.append(f"{name} most frequent value '{top.get('value')}' (~{pct}% of sampled rows).")
        elif kind == "time" and column.get("min_ts") and column.get("max_ts"):
            span_ms = column.get("span_ms") or 0
            if span_ms >= 3_600_000:
                span_text = f"{round(span_ms / 3_600_000, 2)}h"
            elif span_ms >= 60_000:
                span_text = f"{round(span_ms / 60_000, 2)}m"
            else:
                span_text = f"{round(span_ms / 1000, 2)}s"
            insights.append(f"{name} covers {column['min_ts']} → {column['max_ts']} ({span_text}).")

    return insights


def build_default_insights(
    rows: Sequence[Any] | None,
    *,
    columns: Sequence[str] | None,
    total_rows: int | None,
    truncated: bool,
) -> tuple[dict[str, Any] | None, list[str]]:
    if not rows:
        return None, []

    sampled_rows: list[dict[str, Any]] = []
    column_names = list(columns) if columns else []
    for entry in rows[:MAX_SAMPLE_ROWS]:
        normalized, inferred = _normalize_row(entry, column_names or None)
        sampled_rows.append(normalized)
        if not column_names and inferred:
            column_names = inferred

    sample_size = len(sampled_rows)
    if sample_size == 0:
        return None, []

    metrics_columns: list[dict[str, Any]] = []
    for column in column_names:
        summary = _summarize_column(column, sampled_rows, sample_size)
        if summary:
            metrics_columns.append(summary)

    if not metrics_columns:
        return None, []

    key_metrics: dict[str, Any] = {
        "total_rows": total_rows if total_rows is not None else sample_size,
        "sampled_rows": sample_size,
        "num_columns": len(column_names),
        "columns": metrics_columns,
        "truncated_output": bool(truncated),
    }

    insights = _compose_insights(key_metrics)
    return key_metrics, insights
