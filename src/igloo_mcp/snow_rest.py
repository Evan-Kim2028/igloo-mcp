"""Snowflake SQL REST API client used as an alternative execution driver."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt

from .snow_cli import QueryOutput


class SnowRestError(RuntimeError):
    """Raised when the Snowflake SQL REST API returns an error."""


def _load_private_key(path: Path) -> str:
    data = path.read_text(encoding="utf-8")
    if "BEGIN" not in data:
        raise SnowRestError("Invalid private key PEM contents")
    return data


@dataclass
class SnowRestConfig:
    account: str
    user: str
    private_key_path: Path
    warehouse: str | None = None
    database: str | None = None
    schema: str | None = None
    role: str | None = None
    host_override: str | None = None


class SnowRestClient:
    STATEMENTS_PATH = "/api/v2/statements"

    def __init__(
        self,
        config: SnowRestConfig,
        *,
        default_context: dict[str, str | None] | None = None,
        request_timeout: int = 120,
        poll_interval: float = 0.5,
    ) -> None:
        self.config = config
        self.default_context = default_context or {}
        self.request_timeout = request_timeout
        self.poll_interval = poll_interval
        self._private_key = _load_private_key(config.private_key_path)
        self._token: str | None = None
        self._token_expiry: float = 0.0
        host = config.host_override or f"{config.account}.snowflakecomputing.com"
        self.base_url = f"https://{host.strip()}"

    @classmethod
    def from_env(
        cls,
        *,
        default_context: dict[str, str | None] | None = None,
    ) -> SnowRestClient:
        account = os.environ.get("SNOWFLAKE_REST_ACCOUNT") or os.environ.get("SNOWFLAKE_ACCOUNT")
        user = os.environ.get("SNOWFLAKE_REST_USER") or os.environ.get("SNOWFLAKE_USER")
        key_path = os.environ.get("SNOWFLAKE_REST_PRIVATE_KEY") or os.environ.get("SNOWFLAKE_PRIVATE_KEY")
        if not account or not user or not key_path:
            raise SnowRestError(
                "SNOWFLAKE_REST_ACCOUNT, SNOWFLAKE_REST_USER, and SNOWFLAKE_REST_PRIVATE_KEY must be set"
            )
        config = SnowRestConfig(
            account=account.strip(),
            user=user.strip(),
            private_key_path=Path(key_path).expanduser(),
            warehouse=os.environ.get("SNOWFLAKE_REST_WAREHOUSE"),
            database=os.environ.get("SNOWFLAKE_REST_DATABASE"),
            schema=os.environ.get("SNOWFLAKE_REST_SCHEMA"),
            role=os.environ.get("SNOWFLAKE_REST_ROLE"),
            host_override=os.environ.get("SNOWFLAKE_REST_HOST"),
        )
        return cls(config, default_context=default_context)

    def run_query(
        self,
        query: str,
        *,
        ctx_overrides: dict[str, str | None] | None = None,
        timeout: int | None = None,
    ) -> QueryOutput:
        payload: dict[str, Any] = {"statement": query}
        if timeout:
            payload["timeout"] = timeout
        context = self._merge_context(ctx_overrides)
        for key, value in context.items():
            if value:
                payload[key] = value
        payload.setdefault("warehouse", self.config.warehouse)
        payload.setdefault("database", self.config.database)
        payload.setdefault("schema", self.config.schema)
        payload.setdefault("role", self.config.role)

        response = self._request("POST", self.STATEMENTS_PATH, payload)
        handle = response.get("statementHandle")
        if not handle:
            raise SnowRestError("Missing statement handle in REST response")
        status = response.get("status")
        data = response
        while status in {"RUNNING", "PENDING"}:
            time.sleep(self.poll_interval)
            data = self._request("GET", f"{self.STATEMENTS_PATH}/{handle}")
            status = data.get("status")

        if status != "SUCCESS":
            message = data.get("message") or data.get("errorMessage") or "Query failed"
            raise SnowRestError(message)

        rows, columns = self._collect_rows(data)
        profile = {
            "statementHandle": handle,
            "queryId": data.get("queryId"),
            "status": status,
            "resultSetMetaData": data.get("resultSetMetaData"),
            "database": data.get("database"),
            "schema": data.get("schema"),
            "warehouse": data.get("warehouse"),
            "role": data.get("role"),
        }

        return QueryOutput(
            raw_stdout=json.dumps(data),
            raw_stderr="",
            returncode=0,
            rows=rows,
            columns=columns,
            metadata=profile,
        )

    def _merge_context(self, overrides: dict[str, str | None] | None) -> dict[str, str | None]:
        combined = dict(self.default_context)
        if overrides:
            combined.update(overrides)
        return combined

    def _collect_rows(self, response: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
        meta = response.get("resultSetMetaData") or {}
        row_types: Iterable[dict[str, Any]] = meta.get("rowType") or []
        columns = [rt.get("name") or f"column_{idx}" for idx, rt in enumerate(row_types)]
        rows = list(self._rows_from_response(response, columns))

        for url in response.get("resultSetUrls") or []:
            rows.extend(self._rows_from_response(self._request_url(url), columns))

        next_url = response.get("nextResultUrl")
        while next_url:
            block = self._request_url(next_url)
            rows.extend(self._rows_from_response(block, columns))
            next_url = block.get("nextResultUrl")

        return rows, columns

    def _rows_from_response(self, response: dict[str, Any], columns: list[str]) -> Iterable[dict[str, Any]]:
        data_blocks: list[list[Any]] = []
        if isinstance(response.get("data"), list):
            data_blocks.append(response["data"])
        if isinstance(response.get("resultSet"), dict):
            block = response["resultSet"].get("data")
            if isinstance(block, list):
                data_blocks.append(block)
        for block in data_blocks:
            for row in block:
                if isinstance(row, dict):
                    yield row
                    continue
                record: dict[str, Any] = {}
                for idx, value in enumerate(row):
                    key = columns[idx] if idx < len(columns) else f"column_{idx}"
                    record[key] = value
                yield record

    def _request_url(self, url: str) -> dict[str, Any]:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme:
            path = url
        else:
            path = f"{self.base_url}{url}"
        return self._request("GET", path, absolute=True)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        absolute: bool = False,
    ) -> dict[str, Any]:
        if absolute:
            url = path
        else:
            url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Snowflake-Authorization-Token-Type": "KEYPAIR_JWT",
        }
        request = urllib.request.Request(url, data=data, method=method.upper())
        for key, value in headers.items():
            request.add_header(key, value)

        try:
            with urllib.request.urlopen(request, timeout=self.request_timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:  # pragma: no cover - network errors
            body = exc.read().decode("utf-8") if hasattr(exc, "read") else ""
            raise SnowRestError(body or str(exc)) from exc
        except urllib.error.URLError as exc:  # pragma: no cover
            raise SnowRestError(str(exc.reason)) from exc

    def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expiry - 60:
            return self._token
        self._token = self._generate_token()
        return self._token

    def _generate_token(self) -> str:
        now = datetime.now(UTC)
        expires = now + timedelta(minutes=55)
        account = self.config.account.upper()
        user = self.config.user.upper()
        parsed = urllib.parse.urlparse(self.base_url)
        netloc = parsed.netloc
        if ":" not in netloc:
            netloc = f"{netloc}:443"
        audience = urllib.parse.urlunparse(parsed._replace(netloc=netloc))
        payload = {
            "iss": f"{account}.{user}",
            "sub": f"{account}.{user}",
            "aud": audience,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
        }
        token = jwt.encode(payload, self._private_key, algorithm="RS256")
        self._token_expiry = expires.timestamp()
        return token
