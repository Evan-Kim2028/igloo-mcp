"""Dependency pipeline with caching support."""

from __future__ import annotations

import json
import time
from functools import partial
from pathlib import Path
from typing import Optional

import anyio
from pydantic import BaseModel, ConfigDict, Field

from ..dependency import DependencyService
from ..models import DependencyGraph


class DependencyOptions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    database: Optional[str] = None
    schema_name: Optional[str] = Field(default=None, alias="schema")
    account_scope: bool = True
    cache_ttl_seconds: int = 1800

    def cache_key(self) -> str:
        db = self.database or "__all__"
        schema = self.schema_name or "__all__"
        scope = "account" if self.account_scope else "database"
        return f"{scope}-{db}-{schema}".replace("/", "_")


class DependencyPipeline:
    def __init__(self, service: DependencyService, *, cache_dir: Path) -> None:
        self.service = service
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def execute(self, options: DependencyOptions) -> DependencyGraph:
        cached = self._load_cached(options)
        if cached is not None:
            return cached

        work = partial(
            self.service.build,
            database=options.database,
            schema=options.schema_name,
            account_scope=options.account_scope,
        )
        result = await anyio.to_thread.run_sync(work)
        self._store_cache(options, result)
        return result

    def _cache_path(self, options: DependencyOptions) -> Path:
        return self.cache_dir / f"{options.cache_key()}.json"

    def _load_cached(self, options: DependencyOptions) -> DependencyGraph | None:
        cache_path = self._cache_path(options)
        if not cache_path.exists():
            return None
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            timestamp = payload.get("timestamp")
            if not isinstance(timestamp, (int, float)):
                return None
            if (time.time() - timestamp) > options.cache_ttl_seconds:
                return None
            result_payload = payload.get("result")
            if not isinstance(result_payload, dict):
                return None
            return DependencyGraph.model_validate(result_payload)
        except Exception:  # pragma: no cover - cache fallback on corruption
            return None

    def _store_cache(self, options: DependencyOptions, result: DependencyGraph) -> None:
        cache_path = self._cache_path(options)
        payload = {
            "timestamp": time.time(),
            "result": result.model_dump(by_alias=True),
        }
        cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
