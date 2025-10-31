"""Fixture-backed SnowCLI implementation for offline testing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

from igloo_mcp.snow_cli import QueryOutput, SnowCLIError


@dataclass
class RecordedCall:
    """Metadata about a recorded SnowCLI invocation in tests."""

    query: str
    key: str


class FixtureSnowCLI:
    """Lightweight SnowCLI stand-in that replays stored CLI outputs.

    The real SnowCLI shells out to the `snow` binary and requires network
    connectivity. For offline tests we instead load canned responses from disk
    and return them through the same `QueryOutput` contract.
    """

    def __init__(
        self,
        fixture_dir: str | Path,
        *,
        raise_on: Optional[Dict[str, Exception]] = None,
    ) -> None:
        self.fixture_dir = Path(fixture_dir)
        self.raise_on = {key.upper(): exc for key, exc in (raise_on or {}).items()}
        self.call_log: list[RecordedCall] = []

    # --- Public API -----------------------------------------------------
    def run_query(
        self,
        query: str,
        *,
        output_format: Optional[str] = None,  # noqa: ARG002 - unused
        ctx_overrides: Optional[Dict[str, Optional[str]]] = None,  # noqa: ARG002
        timeout: Optional[int] = None,  # noqa: ARG002
    ) -> QueryOutput:
        key = self._key_for_query(query)
        self.call_log.append(RecordedCall(query=query, key=key))

        for match, exc in self.raise_on.items():
            if key.upper() == match or query.upper().startswith(match):
                raise exc

        data = self._load_fixture(key)

        rows: list[Dict[str, object]] = data.get("rows", [])  # type: ignore[assignment]
        stdout = data.get("stdout")
        if stdout is None:
            stdout = json.dumps(rows)

        return QueryOutput(
            raw_stdout=stdout,
            raw_stderr=data.get("stderr", ""),
            returncode=data.get("returncode", 0),
            rows=rows,
            columns=data.get("columns"),
        )

    def run_file(
        self,
        file_path: str,  # noqa: ARG002
        *,
        output_format: Optional[str] = None,  # noqa: ARG002
        ctx_overrides: Optional[Dict[str, Optional[str]]] = None,  # noqa: ARG002
        timeout: Optional[int] = None,  # noqa: ARG002
    ) -> QueryOutput:
        raise SnowCLIError("FixtureSnowCLI.run_file is not implemented for tests")

    def test_connection(self) -> bool:
        return True

    # --- Internal helpers -----------------------------------------------
    def _load_fixture(self, key: str) -> Dict[str, object]:
        path = self.fixture_dir / f"{key}.json"
        if not path.exists():
            raise SnowCLIError(
                f"No fixture found for query key '{key}'. " f"Expected file at {path}."
            )
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if not isinstance(data, dict):
                raise SnowCLIError(
                    f"Fixture for '{key}' must be a JSON object with a 'rows' key."
                )
            return data

    def _key_for_query(self, query: str) -> str:
        normalized = " ".join(query.strip().split())
        upper = normalized.upper()

        mappings: Iterable[tuple[str, str]] = (
            ("SHOW DATABASES", "show_databases"),
            ("SHOW SCHEMAS", "show_schemas"),
            ("SHOW TABLES", "show_tables"),
            ("SHOW VIEWS", "show_views"),
            ("SHOW MATERIALIZED VIEWS", "show_materialized_views"),
            ("SHOW DYNAMIC TABLES", "show_dynamic_tables"),
            ("SHOW TASKS", "show_tasks"),
            ("SHOW PROCEDURES", "show_procedures"),
        )

        for prefix, key in mappings:
            if upper.startswith(prefix):
                return key

        if "INFORMATION_SCHEMA.FUNCTIONS" in upper:
            return "select_information_schema_functions"
        if "INFORMATION_SCHEMA.COLUMNS" in upper:
            return "select_information_schema_columns"

        raise SnowCLIError(f"Unmapped query for fixtures: {query}")
