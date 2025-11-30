"""Get Catalog Summary MCP Tool - Retrieve catalog summary information.

Part of v1.8.0 Phase 2.2 - extracted from mcp_server.py.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

import anyio

from igloo_mcp.catalog import CatalogService
from igloo_mcp.mcp.exceptions import (
    MCPSelectorError,
    MCPValidationError,
)
from igloo_mcp.mcp.validation_helpers import validate_response_mode
from igloo_mcp.path_utils import resolve_catalog_path, validate_safe_path

from .base import MCPTool, ensure_request_id, tool_error_handler
from .schema_utils import string_schema

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class GetCatalogSummaryTool(MCPTool):
    """MCP tool for getting catalog summary."""

    def __init__(self, catalog_service: CatalogService):
        """Initialize get catalog summary tool.

        Args:
            catalog_service: Catalog service instance
        """
        self.catalog_service = catalog_service

    @property
    def name(self) -> str:
        return "get_catalog_summary"

    @property
    def description(self) -> str:
        return (
            "Retrieve high-level summary statistics from an existing catalog built via build_catalog. "
            "Returns aggregate counts (databases, schemas, tables, etc.) and metadata. "
            "Use search_catalog to find specific objects or filter by name/column. "
            "Use this tool to get overview statistics about a catalog directory."
        )

    @property
    def category(self) -> str:
        return "metadata"

    @property
    def tags(self) -> list[str]:
        return ["catalog", "summary", "metadata"]

    @property
    def usage_examples(self) -> list[Dict[str, Any]]:
        return [
            {
                "description": "Inspect default catalog directory",
                "parameters": {},
            },
            {
                "description": "Load summary from custom artifacts folder",
                "parameters": {"catalog_dir": "./artifacts/catalog"},
            },
        ]

    @tool_error_handler("get_catalog_summary")
    async def execute(
        self,
        catalog_dir: str = "./data_catalogue",
        response_mode: Optional[str] = None,
        mode: Optional[str] = None,  # DEPRECATED in v0.3.5
        request_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Get catalog summary with progressive disclosure.

        Args:
            catalog_dir: Directory containing catalog artifacts
            response_mode: Response verbosity level (STANDARD):
                - "minimal": Just total object counts (~30 tokens)
                - "standard": + Database breakdown (~100 tokens, default)
                - "full": + Column statistics (~200+ tokens)
            mode: DEPRECATED - use response_mode instead
            request_id: Optional request ID for tracing

        Returns:
            Catalog summary with requested detail level
        """
        request_id = ensure_request_id(request_id)

        # Validate response_mode with backward compatibility
        effective_mode = validate_response_mode(
            response_mode,
            legacy_param_name="mode",
            legacy_param_value=mode,
            valid_modes=("minimal", "standard", "full"),
            default="standard",
        )

        # Timing and request correlation
        start_time = time.time()

        # If catalog_dir is default, try to resolve to unified storage
        if catalog_dir == "./data_catalogue":
            try:
                resolved_path = resolve_catalog_path(
                    account_scope=False,
                )
                catalog_dir = str(resolved_path)
            except Exception:
                # If resolution fails, use default path (backward compatibility)
                pass

        logger.info(
            "get_catalog_summary_started",
            extra={
                "catalog_dir": catalog_dir,
                "request_id": request_id,
            },
        )

        # Validate catalog directory path (prevent path traversal)
        # Skip validation for unified storage paths (absolute paths from resolve_catalog_path)
        # Only validate relative paths
        catalog_path = Path(catalog_dir)
        if not catalog_path.is_absolute():
            try:
                validated_catalog_dir = validate_safe_path(
                    catalog_dir,
                    reject_parent_dirs=True,
                )
                catalog_dir = str(validated_catalog_dir)
            except MCPValidationError:
                raise  # Re-raise validation errors
            except Exception as e:
                raise MCPValidationError(
                    f"Invalid catalog directory path: {str(e)}",
                    validation_errors=[f"Path validation failed: {catalog_dir}"],
                    hints=[
                        "Use a relative path within the current directory",
                        "Do not use '..' in paths",
                    ],
                ) from e

        try:
            summary = await anyio.to_thread.run_sync(self.catalog_service.load_summary, catalog_dir)

            # Calculate total duration
            total_duration = (time.time() - start_time) * 1000

            logger.info(
                "get_catalog_summary_completed",
                extra={
                    "catalog_dir": catalog_dir,
                    "request_id": request_id,
                    "total_duration_ms": total_duration,
                },
            )

            # Build response based on response_mode
            if effective_mode == "minimal":
                # Minimal - just counts
                return {
                    "status": "success",
                    "request_id": request_id,
                    "total_objects": summary.get("total_objects"),
                    "databases": summary.get("databases"),
                    "timestamp": summary.get("created_at"),
                    "timing": {
                        "total_duration_ms": total_duration,
                    },
                }

            # Summary mode (current behavior)
            response = {
                "status": "success",
                "request_id": request_id,
                "summary": summary,
                "database_breakdown": summary.get("database_breakdown"),
                "timestamp": summary.get("created_at"),
                "timing": {
                    "total_duration_ms": total_duration,
                },
            }

            if effective_mode == "full":
                # Add detailed statistics if available
                detailed_stats = {}

                if "column_stats" in summary:
                    detailed_stats["column_statistics"] = summary["column_stats"]

                if "distribution" in summary:
                    detailed_stats["data_distribution"] = summary["distribution"]

                if detailed_stats:
                    response["detailed_stats"] = detailed_stats

            return response

        except FileNotFoundError as e:
            logger.warning(
                "get_catalog_summary_not_found",
                extra={
                    "catalog_dir": catalog_dir,
                    "error": str(e),
                    "request_id": request_id,
                },
            )

            raise MCPSelectorError(
                f"No catalog found in '{catalog_dir}'. Run build_catalog first to generate the catalog.",
                selector=catalog_dir,
                error="not_found",
                hints=[
                    f"Verify catalog_dir exists: {catalog_dir}",
                    "Run build_catalog first to create catalog artifacts",
                ],
            ) from e

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Catalog Summary Parameters",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "catalog_dir": string_schema(
                    "Catalog directory path containing summary artifacts. "
                    "Defaults to './data_catalogue' which resolves to unified storage "
                    "at ~/.igloo_mcp/catalogs/{database}/. Specify a custom path to override.",
                    title="Catalog Directory",
                    default="./data_catalogue",
                    examples=["./data_catalogue", "./artifacts/catalog"],
                ),
                "request_id": {
                    "type": "string",
                    "description": "Optional request correlation ID for tracing (auto-generated if not provided)",
                },
            },
        }
