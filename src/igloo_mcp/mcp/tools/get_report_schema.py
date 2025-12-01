"""Get Report Schema MCP Tool - Self-documenting schema introspection.

This tool provides runtime schema introspection for Living Reports,
allowing agents to discover valid structures before constructing payloads.
"""

from __future__ import annotations

import time
from typing import Any

from igloo_mcp.config import Config
from igloo_mcp.living_reports.changes_schema import (
    CURRENT_CHANGES_SCHEMA_VERSION,
    ProposedChanges,
)
from igloo_mcp.living_reports.models import Insight, Outline, Section
from igloo_mcp.mcp.exceptions import MCPValidationError
from igloo_mcp.mcp.tools.base import MCPTool, ensure_request_id, tool_error_handler

try:
    from fastmcp.utilities.logging import get_logger
except ImportError:
    from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class GetReportSchemaTool(MCPTool):
    """MCP tool for schema introspection - self-documenting API."""

    def __init__(self, config: Config):
        """Initialize get report schema tool.

        Args:
            config: Application configuration
        """
        self.config = config

    @property
    def name(self) -> str:
        return "get_report_schema"

    @property
    def description(self) -> str:
        return (
            "Discover valid report structures and get copy-paste examples. "
            "Use when unsure how to structure proposed_changes for evolve_report. "
            "format='examples' provides ready-to-use templates."
        )

    @property
    def category(self) -> str:
        return "reports"

    @property
    def tags(self) -> list[str]:
        return ["reports", "schema", "introspection", "documentation"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
        return [
            {
                "description": "Get JSON Schema for evolve_report proposed_changes",
                "parameters": {
                    "schema_type": "proposed_changes",
                    "format": "json_schema",
                },
            },
            {
                "description": "Get example payloads for common operations",
                "parameters": {
                    "schema_type": "proposed_changes",
                    "format": "examples",
                },
            },
            {
                "description": "Get quick reference for all schemas",
                "parameters": {
                    "schema_type": "all",
                    "format": "compact",
                },
            },
        ]

    @tool_error_handler("get_report_schema")
    async def execute(
        self,
        schema_type: str = "proposed_changes",
        format: str = "json_schema",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute schema introspection.

        Args:
            schema_type: What schema to return ('proposed_changes', 'insight', 'section', 'outline', 'all')
            format: Output format ('json_schema', 'examples', 'compact')
            request_id: Optional request correlation ID

        Returns:
            Schema information in requested format

        Raises:
            MCPValidationError: If parameters are invalid
        """
        start_time = time.time()
        request_id = ensure_request_id(request_id)

        # Validate schema_type
        valid_types = ("proposed_changes", "insight", "section", "outline", "all")
        if schema_type not in valid_types:
            raise MCPValidationError(
                f"Invalid schema_type '{schema_type}'. Must be one of: {', '.join(valid_types)}",
                validation_errors=[f"Invalid schema_type: {schema_type}"],
                hints=[
                    "Use 'proposed_changes' for evolve_report schema (most common)",
                    "Use 'insight', 'section', or 'outline' for individual models",
                    "Use 'all' to get all schemas at once",
                ],
                context={"request_id": request_id},
            )

        # Validate format
        valid_formats = ("json_schema", "examples", "compact")
        if format not in valid_formats:
            raise MCPValidationError(
                f"Invalid format '{format}'. Must be one of: {', '.join(valid_formats)}",
                validation_errors=[f"Invalid format: {format}"],
                hints=[
                    "Use 'json_schema' for full JSON Schema draft 7",
                    "Use 'examples' for copy-paste-ready payload examples",
                    "Use 'compact' for minimal quick reference",
                ],
                context={"request_id": request_id},
            )

        logger.info(
            "get_report_schema_started",
            extra={
                "schema_type": schema_type,
                "format": format,
                "request_id": request_id,
            },
        )

        # Build response based on format
        if format == "json_schema":
            response = self._build_json_schema_response(schema_type)
        elif format == "examples":
            response = self._build_examples_response(schema_type)
        elif format == "compact":
            response = self._build_compact_response(schema_type)

        total_duration = (time.time() - start_time) * 1000

        # Add common fields
        response["request_id"] = request_id
        response["timing"] = {
            "total_duration_ms": round(total_duration, 2),
        }

        logger.info(
            "get_report_schema_completed",
            extra={
                "schema_type": schema_type,
                "format": format,
                "request_id": request_id,
                "total_duration_ms": total_duration,
            },
        )

        return response

    def _build_json_schema_response(self, schema_type: str) -> dict[str, Any]:
        """Build JSON Schema format response."""
        schemas = {
            "proposed_changes": ProposedChanges.model_json_schema(),
            "insight": Insight.model_json_schema(),
            "section": Section.model_json_schema(),
            "outline": Outline.model_json_schema(),
        }

        if schema_type == "all":
            return {
                "status": "success",
                "schema_type": "all",
                "schema_version": CURRENT_CHANGES_SCHEMA_VERSION,
                "schemas": schemas,
            }
        return {
            "status": "success",
            "schema_type": schema_type,
            "schema_version": CURRENT_CHANGES_SCHEMA_VERSION,
            "json_schema": schemas[schema_type],
        }

    def _build_examples_response(self, schema_type: str) -> dict[str, Any]:
        """Build examples format response."""
        examples = {
            "proposed_changes": {
                "add_insight": {
                    "description": "Create an insight and link it to a section",
                    "workflow": [
                        "1. Create the insight with insights_to_add",
                        "2. Link it to a section with sections_to_modify",
                    ],
                    "proposed_changes": {
                        "insights_to_add": [
                            {
                                "insight_id": "550e8400-e29b-41d4-a716-446655440099",
                                "summary": "Revenue grew 25% YoY to $2.4M",
                                "importance": 9,
                                "supporting_queries": [
                                    {
                                        "execution_id": "01234567-89ab-cdef-0123-456789abcdef",
                                        "description": "Revenue YoY query",
                                    }
                                ],
                            }
                        ],
                        "sections_to_modify": [
                            {
                                "section_id": "550e8400-e29b-41d4-a716-446655440012",
                                "insight_ids_to_add": ["550e8400-e29b-41d4-a716-446655440099"],
                            }
                        ],
                    },
                },
                "add_section_with_insights": {
                    "description": "Add a new section with inline insights (atomic)",
                    "proposed_changes": {
                        "sections_to_add": [
                            {
                                "title": "Executive Summary",
                                "order": 0,
                                "insights": [
                                    {
                                        "summary": "Record quarterly performance across all metrics",
                                        "importance": 10,
                                    },
                                    {
                                        "summary": "Customer retention improved 15% QoQ",
                                        "importance": 8,
                                    },
                                ],
                            }
                        ]
                    },
                },
                "modify_insight": {
                    "description": "Update an existing insight's properties",
                    "proposed_changes": {
                        "insights_to_modify": [
                            {
                                "insight_id": "550e8400-e29b-41d4-a716-446655440099",
                                "importance": 10,
                                "summary": "Updated summary with new data",
                            }
                        ]
                    },
                },
                "modify_section": {
                    "description": "Update section properties and link/unlink insights",
                    "proposed_changes": {
                        "sections_to_modify": [
                            {
                                "section_id": "550e8400-e29b-41d4-a716-446655440012",
                                "title": "Revenue & Growth Metrics",
                                "insight_ids_to_add": [
                                    "insight-uuid-1",
                                    "insight-uuid-2",
                                ],
                            }
                        ]
                    },
                },
                "remove_items": {
                    "description": "Remove sections or insights",
                    "proposed_changes": {
                        "sections_to_remove": ["550e8400-e29b-41d4-a716-446655440013"],
                        "insights_to_remove": ["550e8400-e29b-41d4-a716-446655440088"],
                    },
                },
                "change_status": {
                    "description": "Archive or restore a report",
                    "proposed_changes": {"status_change": "archived"},
                },
            },
            "insight": {
                "basic_insight": {
                    "insight_id": "550e8400-e29b-41d4-a716-446655440099",
                    "summary": "Q1 revenue grew 25% YoY",
                    "importance": 9,
                    "status": "active",
                    "supporting_queries": [],
                },
                "insight_with_citation": {
                    "insight_id": "550e8400-e29b-41d4-a716-446655440100",
                    "summary": "Network processed 2.4M transactions in Q1",
                    "importance": 8,
                    "status": "active",
                    "supporting_queries": [{"execution_id": "exec_abc123", "sql_sha256": "def456..."}],
                },
            },
            "section": {
                "basic_section": {
                    "section_id": "550e8400-e29b-41d4-a716-446655440012",
                    "title": "Revenue Analysis",
                    "order": 1,
                    "insight_ids": ["ins_1", "ins_2"],
                },
                "section_with_content": {
                    "section_id": "550e8400-e29b-41d4-a716-446655440013",
                    "title": "Methodology",
                    "order": 2,
                    "content": "## Data Collection\n\nWe analyzed...",
                    "content_format": "markdown",
                    "insight_ids": [],
                },
            },
        }

        if schema_type == "all":
            return {
                "status": "success",
                "schema_type": "all",
                "examples": examples,
            }
        if schema_type in examples:
            return {
                "status": "success",
                "schema_type": schema_type,
                "examples": examples[schema_type],
            }
        # For outline, provide minimal example
        return {
            "status": "success",
            "schema_type": schema_type,
            "examples": {
                "note": f"Schema type '{schema_type}' is primarily used internally. "
                "Use 'proposed_changes' for evolve_report operations."
            },
        }

    def _build_compact_response(self, schema_type: str) -> dict[str, Any]:
        """Build compact format response (quick reference)."""
        compact_refs = {
            "proposed_changes": {
                "insights_to_add": (
                    "Array<{section_id: UUID, insight: "
                    "{summary: string, importance: 0-10, supporting_queries?: Array}}>"
                ),
                "sections_to_add": ("Array<{title: string, order?: int, content?: string, insights?: Array<insight>}>"),
                "insights_to_modify": (
                    "Array<{insight_id: UUID, summary?: string, importance?: 0-10, status?: string}>"
                ),
                "sections_to_modify": (
                    "Array<{section_id: UUID, title?: string, order?: int, "
                    "insight_ids_to_add?: Array<UUID>, insight_ids_to_remove?: Array<UUID>, "
                    "insights?: Array<insight>}>"
                ),
                "insights_to_remove": "Array<UUID>",
                "sections_to_remove": "Array<UUID>",
                "status_change": "'active' | 'archived' | 'deleted'",
                "title_change": "string",
                "metadata_updates": "object",
            },
            "insight": {
                "insight_id": "UUID (auto-generated if omitted for additions)",
                "summary": "string (required)",
                "importance": "int 0-10 (required)",
                "status": "'active' | 'archived' | 'killed' (default: 'active')",
                "supporting_queries": "Array<{execution_id?: string, sql_sha256?: string}> (default: [])",
            },
            "section": {
                "section_id": "UUID (auto-generated if omitted for additions)",
                "title": "string (required)",
                "order": "int >= 0 (required)",
                "insight_ids": "Array<UUID> (default: [])",
                "content": "string (optional prose content)",
                "content_format": "'markdown' | 'html' | 'plain' (default: 'markdown')",
                "notes": "string (optional metadata)",
            },
        }

        if schema_type == "all":
            return {
                "status": "success",
                "schema_type": "all",
                "quick_reference": compact_refs,
            }
        if schema_type in compact_refs:
            return {
                "status": "success",
                "schema_type": schema_type,
                "quick_reference": compact_refs[schema_type],
            }
        return {
            "status": "success",
            "schema_type": schema_type,
            "quick_reference": {
                "note": f"Schema type '{schema_type}' is complex. Use format='json_schema' for complete definition."
            },
        }

    def get_parameter_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "title": "Get Report Schema Parameters",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "schema_type": {
                    "type": "string",
                    "description": "What schema to return",
                    "enum": [
                        "proposed_changes",
                        "insight",
                        "section",
                        "outline",
                        "all",
                    ],
                    "default": "proposed_changes",
                    "examples": ["proposed_changes", "insight", "all"],
                },
                "format": {
                    "type": "string",
                    "description": "Output format for schema",
                    "enum": ["json_schema", "examples", "compact"],
                    "default": "json_schema",
                    "examples": ["examples", "compact"],
                },
                "request_id": {
                    "type": "string",
                    "description": "Optional request correlation ID for tracing",
                },
            },
        }


__all__ = ["GetReportSchemaTool"]
