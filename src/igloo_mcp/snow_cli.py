"""Thin wrapper around the official Snowflake CLI (`snow`).

This module shells out to the `snow` binary to execute SQL commands using
configured profiles. It provides helpers to run inline SQL, files, and parse
CSV/JSON output where available.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from io import StringIO
from typing import Any

from .config import get_config

logger = logging.getLogger(__name__)


class SnowCLIError(RuntimeError):
    pass


def _ensure_snow_available() -> None:
    if shutil.which("snow") is None:
        raise SnowCLIError(
            "`snow` CLI not found. Install with `pip install snowflake-cli` and configure a profile.",
        )


@dataclass
class QueryOutput:
    raw_stdout: str
    raw_stderr: str
    returncode: int
    # Optional parsed forms
    rows: list[dict[str, Any]] | None = None
    columns: list[str] | None = None
    metadata: dict[str, Any] | None = None


class SnowCLI:
    """Runner for Snowflake CLI commands."""

    def __init__(self, profile: str | None = None):
        cfg = get_config()
        self.profile = profile or cfg.snowflake.profile
        self.default_ctx = {
            "warehouse": cfg.snowflake.warehouse,
            "database": cfg.snowflake.database,
            "schema": cfg.snowflake.schema,
            "role": cfg.snowflake.role,
        }

    def _base_args(self, ctx_overrides: dict[str, str | None] | None = None) -> list[str]:
        # Use --connection/-c to select the configured connection name
        args = ["snow", "sql", "--connection", self.profile]
        ctx = {**self.default_ctx}
        if ctx_overrides:
            ctx.update({k: v for k, v in ctx_overrides.items() if v})
        for key in ("warehouse", "database", "schema", "role"):
            val = ctx.get(key)
            if val:
                args.extend([f"--{key}", str(val)])
        return args

    def run_query(
        self,
        query: str,
        *,
        output_format: str | None = None,  # "csv" or "json" if supported
        ctx_overrides: dict[str, str | None] | None = None,
        timeout: int | None = None,
    ) -> QueryOutput:
        """Execute an inline SQL statement using Snowflake CLI.

        Attempts to parse output when `output_format` is provided. Falls back
        to raw stdout if parsing is not possible.
        """
        _ensure_snow_available()

        args = self._base_args(ctx_overrides)
        args.extend(["-q", query])

        # Try to set format if supported by user's CLI version. We don't fail
        # if it's not supported; parsing simply won't happen.
        if output_format in {"csv", "json"}:
            args.extend(["--format", output_format])

        if os.getenv("IGLOO_MCP_DEBUG") == "1":
            try:
                # Log the command about to run (without printing sensitive env)
                debug_cmd = " ".join(args)
                logger.debug(f"Executing: {debug_cmd}")
                # Log SQL query for debugging (best-effort, don't fail on logging errors)
                try:
                    trimmed = " ".join(query.split())
                    logger.debug(f"SQL: {trimmed}")
                except (AttributeError, ValueError):
                    pass
            except (AttributeError, TypeError, ValueError):  # Debug logging is best-effort
                logger.debug("Failed to log SQL debug info", exc_info=True)

        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        out = QueryOutput(proc.stdout, proc.stderr, proc.returncode)

        if proc.returncode != 0:
            raise SnowCLIError(proc.stderr.strip() or "Snowflake CLI returned an error")

        # Parse if user requested a format
        if output_format == "json":
            try:
                data = json.loads(proc.stdout)
                # Expect either a list of rows or an object with data
                if isinstance(data, list):
                    out.rows = data
                    # Extract column names from first row if available
                    if data and isinstance(data[0], dict):
                        out.columns = list(data[0].keys())
                elif isinstance(data, dict):
                    rows = data.get("data") or data.get("rows")
                    if isinstance(rows, list):
                        out.rows = rows
                        # Extract column names from first row if available
                        if rows and isinstance(rows[0], dict):
                            out.columns = list(rows[0].keys())
            except json.JSONDecodeError:
                pass
        elif output_format == "csv":
            try:
                sio = StringIO(proc.stdout)
                reader = csv.DictReader(sio)
                out.rows = list(reader)  # type: ignore
                out.columns = list(reader.fieldnames or [])
            except (AttributeError, TypeError, ValueError):  # Debug logging is best-effort
                logger.debug("Failed to log SQL debug info", exc_info=True)

        return out

    def run_file(
        self,
        file_path: str,
        *,
        output_format: str | None = None,
        ctx_overrides: dict[str, str | None] | None = None,
        timeout: int | None = None,
    ) -> QueryOutput:
        _ensure_snow_available()
        args = self._base_args(ctx_overrides)
        args.extend(["-f", file_path])
        if output_format in {"csv", "json"}:
            args.extend(["--format", output_format])

        if os.getenv("IGLOO_MCP_DEBUG") == "1":
            try:
                debug_cmd = " ".join(args)
                logger.debug(f"Executing file: {debug_cmd}")
                logger.debug(f"File: {file_path}")
            except (AttributeError, TypeError, ValueError):  # Debug logging is best-effort
                logger.debug("Failed to log SQL debug info", exc_info=True)

        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        out = QueryOutput(proc.stdout, proc.stderr, proc.returncode)
        if proc.returncode != 0:
            raise SnowCLIError(proc.stderr.strip() or "Snowflake CLI returned an error")
        return out

    def test_connection(self) -> bool:
        try:
            out = self.run_query("SELECT 1", output_format="csv")
            if out.rows and len(out.rows) > 0:
                # try to extract numeric 1
                row = list(out.rows[0].values())
                return any(str(v).strip() == "1" for v in row)
            return bool(out.raw_stdout.strip())
        except SnowCLIError:
            return False

    # Connection management helpers
    def list_connections(self) -> list[dict[str, Any]]:
        _ensure_snow_available()
        proc = subprocess.run(
            ["snow", "connection", "list", "--format", "JSON"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise SnowCLIError(proc.stderr.strip() or "Failed to list connections")
        try:
            data = json.loads(proc.stdout or "[]")
        except json.JSONDecodeError:
            data = []
        return data if isinstance(data, list) else []

    def connection_exists(self, name: str) -> bool:
        try:
            conns = self.list_connections()
            return any((c.get("name") or c.get("connection_name")) == name for c in conns)
        except SnowCLIError:
            return False

    def add_connection(
        self,
        name: str,
        *,
        account: str,
        user: str,
        private_key_file: str,
        role: str | None = None,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
        make_default: bool = False,
    ) -> None:
        _ensure_snow_available()
        args = [
            "snow",
            "connection",
            "add",
            "--connection-name",
            name,
            "--account",
            account,
            "--user",
            user,
            "--private-key",
            private_key_file,
            "--no-interactive",
        ]
        if role:
            args.extend(["--role", role])
        if warehouse:
            args.extend(["--warehouse", warehouse])
        if database:
            args.extend(["--database", database])
        if schema:
            args.extend(["--schema", schema])
        if make_default:
            args.append("--default")

        proc = subprocess.run(args, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise SnowCLIError(proc.stderr.strip() or "Failed to add connection")

    def set_default_connection(self, name: str) -> None:
        _ensure_snow_available()
        proc = subprocess.run(
            ["snow", "connection", "set-default", name],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise SnowCLIError(proc.stderr.strip() or "Failed to set default connection")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass
