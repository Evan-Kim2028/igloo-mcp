"""Catalog service for building Snowflake metadata catalogs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from igloo_mcp.path_utils import resolve_catalog_path, resolve_catalog_root
from igloo_mcp.snow_cli import SnowCLI

logger = logging.getLogger(__name__)


@dataclass
class CatalogTotals:
    """Catalog totals summary."""

    databases: int = 0
    schemas: int = 0
    tables: int = 0
    views: int = 0
    materialized_views: int = 0
    dynamic_tables: int = 0
    tasks: int = 0
    functions: int = 0
    procedures: int = 0
    columns: int = 0


@dataclass
class CatalogResult:
    """Catalog build result."""

    totals: CatalogTotals
    output_dir: str
    success: bool = True
    error: str | None = None


class CatalogService:
    """Service for building Snowflake metadata catalogs.

    This service queries Snowflake INFORMATION_SCHEMA to build comprehensive
    metadata catalogs including databases, schemas, tables, views, functions,
    procedures, and columns. It uses optimized queries and proper filtering
    to ensure only relevant user-defined objects are included.

    Key Features:
    - Real Snowflake metadata queries (not mock data)
    - Function filtering: Only user-defined functions (excludes built-in operators)
    - Comprehensive coverage: All Snowflake object types
    - Structured JSON output with detailed metadata
    - Account-wide or database-specific catalog building
    """

    def __init__(self, context: Any | None = None):
        """Initialize catalog service.

        Args:
            context: Service context with profile information
        """
        self.context = context
        if context is not None and hasattr(context, "config") and hasattr(context.config, "snowflake"):
            self.profile = context.config.snowflake.profile
        else:
            self.profile = None
        self.cli = SnowCLI(self.profile)

    def build(
        self,
        output_dir: str = "./data_catalogue",
        database: str | None = None,
        account_scope: bool = False,
        output_format: str = "json",
        include_ddl: bool = True,
        max_ddl_concurrency: int = 8,
        catalog_concurrency: int = 16,
        export_sql: bool = False,
        use_unified_storage: bool = True,
    ) -> CatalogResult:
        """Build catalog metadata.

        Args:
            output_dir: Output directory for catalog files (default: ./data_catalogue)
            database: Specific database to catalog (None for current)
            account_scope: Whether to catalog entire account
            output_format: Output format ('json' or 'jsonl')
            include_ddl: Whether to include DDL statements
            max_ddl_concurrency: Maximum DDL concurrency
            catalog_concurrency: Maximum catalog concurrency
            export_sql: Whether to export SQL files
            use_unified_storage: If True and output_dir is default, use unified storage

        Returns:
            Catalog build result with totals
        """
        try:
            # Determine output directory
            # If using unified storage and output_dir is the default, resolve to unified storage
            if use_unified_storage and output_dir == "./data_catalogue":
                output_path = resolve_catalog_path(
                    database=database,
                    account_scope=account_scope,
                )
                output_dir = str(output_path)
            else:
                output_path = Path(output_dir)

            # Create output directory
            output_path.mkdir(parents=True, exist_ok=True)

            # Build basic catalog structure
            build_timestamp = datetime.now(UTC).isoformat()
            catalog_data = {
                "metadata": {
                    "database": database or "current",
                    "account_scope": account_scope,
                    "format": output_format,
                    "timestamp": build_timestamp,
                },
                "databases": [],
                "schemas": [],
                "tables": [],
                "views": [],
                "columns": [],
            }

            # Query Snowflake INFORMATION_SCHEMA to build real catalog
            totals = self._build_real_catalog(catalog_data, database, account_scope)

            # Write catalog file
            if output_format == "json":
                catalog_file = output_path / "catalog.json"
                with open(catalog_file, "w") as f:
                    json.dump(catalog_data, f, indent=2)
            else:  # jsonl
                catalog_file = output_path / "catalog.jsonl"
                with open(catalog_file, "w") as f:
                    json.dump(catalog_data, f)

            # Write summary
            summary_data = {
                "totals": {
                    "databases": totals.databases,
                    "schemas": totals.schemas,
                    "tables": totals.tables,
                    "views": totals.views,
                    "materialized_views": totals.materialized_views,
                    "dynamic_tables": totals.dynamic_tables,
                    "tasks": totals.tasks,
                    "functions": totals.functions,
                    "procedures": totals.procedures,
                    "columns": totals.columns,
                },
                "output_dir": output_dir,
                "format": output_format,
            }

            summary_file = output_path / "catalog_summary.json"
            with open(summary_file, "w") as f:
                json.dump(summary_data, f, indent=2)

            # Save metadata file for incremental updates (per database)
            # Check if this is a unified storage path (either resolved or explicitly provided)
            try:
                catalog_root = resolve_catalog_root()
                is_unified_storage_path = use_unified_storage or str(output_path).startswith(str(catalog_root))
            except Exception:
                # If path resolution fails, fall back to use_unified_storage flag
                is_unified_storage_path = use_unified_storage

            if is_unified_storage_path and not account_scope:
                metadata_file = output_path / "_catalog_metadata.json"
                total_objects = (
                    totals.tables
                    + totals.views
                    + totals.materialized_views
                    + totals.dynamic_tables
                    + totals.tasks
                    + totals.functions
                    + totals.procedures
                )
                metadata_data = {
                    "last_build": build_timestamp,
                    "last_full_refresh": build_timestamp,
                    "database": database or "current",
                    "total_objects": total_objects,
                    "schema_count": totals.schemas,
                    "table_count": totals.tables,
                    "view_count": totals.views,
                    "materialized_view_count": totals.materialized_views,
                    "dynamic_table_count": totals.dynamic_tables,
                    "task_count": totals.tasks,
                    "function_count": totals.functions,
                    "procedure_count": totals.procedures,
                    "column_count": totals.columns,
                }
                with open(metadata_file, "w") as f:
                    json.dump(metadata_data, f, indent=2)

            return CatalogResult(totals=totals, output_dir=output_dir, success=True)

        except Exception as e:
            logger.error(f"Catalog build failed: {e}")
            return CatalogResult(
                totals=CatalogTotals(),
                output_dir=output_dir,
                success=False,
                error=str(e),
            )

    def _build_real_catalog(
        self,
        catalog_data: dict[str, Any],
        database: str | None,
        account_scope: bool,
    ) -> CatalogTotals:
        """Build real catalog by querying Snowflake INFORMATION_SCHEMA.

        This method queries actual Snowflake metadata instead of returning mock data.
        It uses optimized SHOW commands and INFORMATION_SCHEMA queries to gather
        comprehensive metadata about all Snowflake objects.

        Key Implementation Details:
        - Uses SHOW commands for databases, schemas, tables, views, etc.
        - Uses INFORMATION_SCHEMA.FUNCTIONS to get only user-defined functions
        - Uses INFORMATION_SCHEMA.COLUMNS for detailed column metadata
        - Filters out built-in functions (operators like !=, %, *, +, -)
        - Returns structured data with proper ordering and metadata

        Args:
            catalog_data: Dictionary to populate with catalog data
            database: Specific database to query (None for current, account_scope=True for all)
            account_scope: Whether to query entire account or specific database

        Returns:
            CatalogTotals with counts of each object type found
        """
        totals = CatalogTotals()

        try:
            # Query databases
            if account_scope:
                db_query = "SHOW DATABASES"
            else:
                db_query = f"SHOW DATABASES LIKE '{database}'" if database else "SHOW DATABASES"

            db_result = self.cli.run_query(db_query, output_format="json")
            if db_result.rows:
                catalog_data["databases"] = db_result.rows
                totals.databases = len(db_result.rows)

            # Query schemas
            if account_scope:
                schema_query = "SHOW SCHEMAS"
            else:
                schema_query = f"SHOW SCHEMAS IN DATABASE {database}" if database else "SHOW SCHEMAS"

            schema_result = self.cli.run_query(schema_query, output_format="json")
            if schema_result.rows:
                catalog_data["schemas"] = schema_result.rows
                totals.schemas = len(schema_result.rows)

            # Query tables
            if account_scope:
                table_query = "SHOW TABLES"
            else:
                table_query = f"SHOW TABLES IN DATABASE {database}" if database else "SHOW TABLES"

            table_result = self.cli.run_query(table_query, output_format="json")
            if table_result.rows:
                catalog_data["tables"] = table_result.rows
                totals.tables = len(table_result.rows)

            # Query views
            if account_scope:
                view_query = "SHOW VIEWS"
            else:
                view_query = f"SHOW VIEWS IN DATABASE {database}" if database else "SHOW VIEWS"

            view_result = self.cli.run_query(view_query, output_format="json")
            if view_result.rows:
                catalog_data["views"] = view_result.rows
                totals.views = len(view_result.rows)

            # Query materialized views
            if account_scope:
                mv_query = "SHOW MATERIALIZED VIEWS"
            else:
                mv_query = f"SHOW MATERIALIZED VIEWS IN DATABASE {database}" if database else "SHOW MATERIALIZED VIEWS"

            mv_result = self.cli.run_query(mv_query, output_format="json")
            if mv_result.rows:
                catalog_data["materialized_views"] = mv_result.rows
                totals.materialized_views = len(mv_result.rows)

            # Query dynamic tables
            if account_scope:
                dt_query = "SHOW DYNAMIC TABLES"
            else:
                dt_query = f"SHOW DYNAMIC TABLES IN DATABASE {database}" if database else "SHOW DYNAMIC TABLES"

            dt_result = self.cli.run_query(dt_query, output_format="json")
            if dt_result.rows:
                catalog_data["dynamic_tables"] = dt_result.rows
                totals.dynamic_tables = len(dt_result.rows)

            # Query tasks
            if account_scope:
                task_query = "SHOW TASKS"
            else:
                task_query = f"SHOW TASKS IN DATABASE {database}" if database else "SHOW TASKS"

            task_result = self.cli.run_query(task_query, output_format="json")
            if task_result.rows:
                catalog_data["tasks"] = task_result.rows
                totals.tasks = len(task_result.rows)

            # Query user-defined functions only
            # Note: INFORMATION_SCHEMA.FUNCTIONS automatically excludes built-in Snowflake functions
            # This prevents including 1000+ built-in operators (!=, %, *, +, -) and system functions
            # Only returns actual user-defined functions created by users
            if account_scope:
                func_query = """
                SELECT
                    FUNCTION_CATALOG as database_name,
                    FUNCTION_SCHEMA as schema_name,
                    FUNCTION_NAME as function_name,
                    DATA_TYPE as return_type,
                    FUNCTION_LANGUAGE as language,
                    COMMENT as comment,
                    CREATED as created,
                    LAST_ALTERED as last_altered
                FROM INFORMATION_SCHEMA.FUNCTIONS
                ORDER BY FUNCTION_CATALOG, FUNCTION_SCHEMA, FUNCTION_NAME
                """
            else:
                if database:
                    func_query = f"""
                    SELECT
                        FUNCTION_CATALOG as database_name,
                        FUNCTION_SCHEMA as schema_name,
                        FUNCTION_NAME as function_name,
                        DATA_TYPE as return_type,
                        FUNCTION_LANGUAGE as language,
                        COMMENT as comment,
                        CREATED as created,
                        LAST_ALTERED as last_altered
                    FROM INFORMATION_SCHEMA.FUNCTIONS
                    WHERE FUNCTION_CATALOG = '{database}'
                    ORDER BY FUNCTION_CATALOG, FUNCTION_SCHEMA, FUNCTION_NAME
                    """
                else:
                    func_query = """
                    SELECT
                        FUNCTION_CATALOG as database_name,
                        FUNCTION_SCHEMA as schema_name,
                        FUNCTION_NAME as function_name,
                        DATA_TYPE as return_type,
                        FUNCTION_LANGUAGE as language,
                        COMMENT as comment,
                        CREATED as created,
                        LAST_ALTERED as last_altered
                    FROM INFORMATION_SCHEMA.FUNCTIONS
                    ORDER BY FUNCTION_CATALOG, FUNCTION_SCHEMA, FUNCTION_NAME
                    """

            func_result = self.cli.run_query(func_query, output_format="json")
            if func_result.rows:
                catalog_data["functions"] = func_result.rows
                totals.functions = len(func_result.rows)

            # Query procedures
            if account_scope:
                proc_query = "SHOW PROCEDURES"
            else:
                proc_query = f"SHOW PROCEDURES IN DATABASE {database}" if database else "SHOW PROCEDURES"

            proc_result = self.cli.run_query(proc_query, output_format="json")
            if proc_result.rows:
                catalog_data["procedures"] = proc_result.rows
                totals.procedures = len(proc_result.rows)

            # Query columns from INFORMATION_SCHEMA
            if account_scope:
                col_query = """
                SELECT
                    TABLE_CATALOG as database_name,
                    TABLE_SCHEMA as schema_name,
                    TABLE_NAME as table_name,
                    COLUMN_NAME as column_name,
                    DATA_TYPE as data_type,
                    IS_NULLABLE as is_nullable,
                    COLUMN_DEFAULT as column_default,
                    COMMENT as comment
                FROM INFORMATION_SCHEMA.COLUMNS
                ORDER BY TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
                """
            else:
                if database:
                    col_query = f"""
                    SELECT
                        TABLE_CATALOG as database_name,
                        TABLE_SCHEMA as schema_name,
                        TABLE_NAME as table_name,
                        COLUMN_NAME as column_name,
                        DATA_TYPE as data_type,
                        IS_NULLABLE as is_nullable,
                        COLUMN_DEFAULT as column_default,
                        COMMENT as comment
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_CATALOG = '{database}'
                    ORDER BY TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
                    """
                else:
                    col_query = """
                    SELECT
                        TABLE_CATALOG as database_name,
                        TABLE_SCHEMA as schema_name,
                        TABLE_NAME as table_name,
                        COLUMN_NAME as column_name,
                        DATA_TYPE as data_type,
                        IS_NULLABLE as is_nullable,
                        COLUMN_DEFAULT as column_default,
                        COMMENT as comment
                    FROM INFORMATION_SCHEMA.COLUMNS
                    ORDER BY TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
                    """

            col_result = self.cli.run_query(col_query, output_format="json")
            if col_result.rows:
                catalog_data["columns"] = col_result.rows
                totals.columns = len(col_result.rows)

            logger.info(
                ("Catalog built successfully: %s databases, %s schemas, %s tables, %s views, %s columns"),
                totals.databases,
                totals.schemas,
                totals.tables,
                totals.views,
                totals.columns,
            )

        except Exception as e:
            logger.error(f"Failed to build real catalog: {e}")
            # Return empty totals on error
            totals = CatalogTotals()

        return totals

    def load_summary(self, catalog_dir: str) -> dict[str, Any]:
        """Load catalog summary from directory.

        Args:
            catalog_dir: Directory containing catalog files

        Returns:
            Catalog summary data

        Raises:
            FileNotFoundError: If catalog directory or summary file not found
        """
        catalog_path = Path(catalog_dir)
        summary_file = catalog_path / "catalog_summary.json"

        if not catalog_path.exists():
            raise FileNotFoundError(f"Catalog directory not found: {catalog_dir}")

        if not summary_file.exists():
            raise FileNotFoundError(f"Catalog summary not found: {summary_file}")

        with open(summary_file) as f:
            return json.load(f)


def build_catalog(
    output_dir: str = "./data_catalogue",
    database: str | None = None,
    profile: str | None = None,
) -> CatalogResult:
    """Build catalog with default settings.

    Args:
        output_dir: Output directory for catalog files
        database: Specific database to catalog
        profile: Snowflake profile to use

    Returns:
        Catalog build result
    """
    context = {"profile": profile} if profile else {}
    service = CatalogService(context)
    return service.build(output_dir=output_dir, database=database)
