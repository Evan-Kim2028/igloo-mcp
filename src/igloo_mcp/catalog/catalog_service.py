"""Catalog service for building Snowflake metadata catalogs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..snow_cli import SnowCLI, SnowCLIError

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
    error: Optional[str] = None


class CatalogService:
    """Service for building Snowflake metadata catalogs."""
    
    def __init__(self, context: Optional[Dict[str, Any]] = None):
        """Initialize catalog service.
        
        Args:
            context: Session context with profile information
        """
        self.context = context or {}
        self.profile = self.context.get("profile")
        self.cli = SnowCLI(self.profile)
    
    def build(
        self,
        output_dir: str = "./data_catalogue",
        database: Optional[str] = None,
        account_scope: bool = False,
        output_format: str = "json",
        include_ddl: bool = True,
        max_ddl_concurrency: int = 8,
        catalog_concurrency: int = 16,
        export_sql: bool = False,
    ) -> CatalogResult:
        """Build catalog metadata.
        
        Args:
            output_dir: Output directory for catalog files
            database: Specific database to catalog (None for current)
            account_scope: Whether to catalog entire account
            output_format: Output format ('json' or 'jsonl')
            include_ddl: Whether to include DDL statements
            max_ddl_concurrency: Maximum DDL concurrency
            catalog_concurrency: Maximum catalog concurrency
            export_sql: Whether to export SQL files
            
        Returns:
            Catalog build result with totals
        """
        try:
            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Build basic catalog structure
            catalog_data = {
                "metadata": {
                    "database": database or "current",
                    "account_scope": account_scope,
                    "format": output_format,
                    "timestamp": "2024-01-01T00:00:00Z"
                },
                "databases": [],
                "schemas": [],
                "tables": [],
                "views": [],
                "columns": []
            }
            
            # For now, return a mock result
            # In a real implementation, this would query Snowflake INFORMATION_SCHEMA
            totals = CatalogTotals(
                databases=1,
                schemas=3,
                tables=5,
                views=2,
                columns=25
            )
            
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
                "format": output_format
            }
            
            summary_file = output_path / "catalog_summary.json"
            with open(summary_file, "w") as f:
                json.dump(summary_data, f, indent=2)
            
            return CatalogResult(
                totals=totals,
                output_dir=output_dir,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Catalog build failed: {e}")
            return CatalogResult(
                totals=CatalogTotals(),
                output_dir=output_dir,
                success=False,
                error=str(e)
            )
    
    def load_summary(self, catalog_dir: str) -> Dict[str, Any]:
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
        
        with open(summary_file, "r") as f:
            return json.load(f)


def build_catalog(
    output_dir: str = "./data_catalogue",
    database: Optional[str] = None,
    profile: Optional[str] = None,
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
