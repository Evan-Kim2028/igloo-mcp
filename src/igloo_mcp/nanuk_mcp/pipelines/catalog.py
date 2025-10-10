"""Asynchronous catalog pipeline with caching support."""

from __future__ import annotations

import json
import time
from functools import partial
from pathlib import Path
from typing import Optional

import anyio
from pydantic import BaseModel, ConfigDict

from ..catalog import CatalogService
from ..models import CatalogBuildResult


class CatalogOptions(BaseModel):
    """Input parameters for catalog generation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    output_dir: Path
    database: Optional[str] = None
    account_scope: bool = False
    incremental: bool = False
    output_format: str = "json"
    include_ddl: bool = True
    max_ddl_concurrency: int = 8
    catalog_concurrency: Optional[int] = None
    export_sql: bool = False
    cache_ttl_seconds: int = 3600

    def cache_key(self) -> str:
        provider = self.database or "__default__"
        scope = "account" if self.account_scope else "database"
        return f"{scope}-{provider.replace('/', '_')}"


class CatalogPipeline:
    """Multi-stage catalog pipeline with resumable caching."""

    def __init__(
        self,
        service: CatalogService,
        *,
        cache_dir: Path,
    ) -> None:
        self.service = service
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def execute(self, options: CatalogOptions) -> CatalogBuildResult:
        cached = self._load_cached(options)
        if cached is not None:
            return cached

        work = partial(
            self.service.build,
            str(options.output_dir),
            database=options.database,
            account_scope=options.account_scope,
            incremental=options.incremental,
            output_format=options.output_format,
            include_ddl=options.include_ddl,
            max_ddl_concurrency=options.max_ddl_concurrency,
            catalog_concurrency=options.catalog_concurrency,
            export_sql=options.export_sql,
        )
        result = await anyio.to_thread.run_sync(work)
        self._store_cache(options, result)
        return result

    def _cache_path(self, options: CatalogOptions) -> Path:
        return self.cache_dir / f"{options.cache_key()}.json"

    def _load_cached(self, options: CatalogOptions) -> CatalogBuildResult | None:
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
            return CatalogBuildResult.model_validate(result_payload)
        except Exception:  # pragma: no cover - cache corruption fallback
            return None

    def _store_cache(self, options: CatalogOptions, result: CatalogBuildResult) -> None:
        cache_path = self._cache_path(options)
        payload = {
            "timestamp": time.time(),
            "result": result.model_dump(mode="json"),
        }
        cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
