"""Factory classes for creating lineage objects."""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Type

from .base import LineageAnalyzer, LineageExtractor, LineageStore
from .builder import LineageBuilder
from .column_parser import ColumnLineageExtractor
from .cross_db import CrossDatabaseLineageBuilder
from .exceptions import InvalidConfigurationError, UnsupportedOperationError
from .external import ExternalSourceMapper
from .graph import LineageGraph
from .history import LineageHistoryManager as LineageHistoryTracker
from .impact import ImpactAnalyzer
from .loader import CatalogLoader
from .sql_parser import SqlLineageExtractor
from .transformations import TransformationTracker
from .types import ObjectTypeStr

logger = logging.getLogger(__name__)


class ExtractorType(Enum):
    """Types of lineage extractors."""

    SQL = "sql"
    COLUMN = "column"
    EXTERNAL = "external"
    TRANSFORMATION = "transformation"
    CROSS_DATABASE = "cross_database"


class AnalyzerType(Enum):
    """Types of lineage analyzers."""

    IMPACT = "impact"
    HISTORY = "history"
    TRANSFORMATION = "transformation"


class StoreType(Enum):
    """Types of lineage stores."""

    FILE = "file"
    MEMORY = "memory"
    DATABASE = "database"


class LineageFactory:
    """Factory for creating lineage objects."""

    _extractors: Dict[ExtractorType, Type[LineageExtractor]] = {}
    _analyzers: Dict[AnalyzerType, Type[LineageAnalyzer]] = {}
    _stores: Dict[StoreType, Type[LineageStore]] = {}

    @classmethod
    def register_extractor(
        cls, extractor_type: ExtractorType, extractor_class: Type[LineageExtractor]
    ) -> None:
        """Register a lineage extractor."""
        cls._extractors[extractor_type] = extractor_class
        logger.debug(f"Registered extractor: {extractor_type.value}")

    @classmethod
    def register_analyzer(
        cls, analyzer_type: AnalyzerType, analyzer_class: Type[LineageAnalyzer]
    ) -> None:
        """Register a lineage analyzer."""
        cls._analyzers[analyzer_type] = analyzer_class
        logger.debug(f"Registered analyzer: {analyzer_type.value}")

    @classmethod
    def register_store(
        cls, store_type: StoreType, store_class: Type[LineageStore]
    ) -> None:
        """Register a lineage store."""
        cls._stores[store_type] = store_class
        logger.debug(f"Registered store: {store_type.value}")

    @classmethod
    def create_extractor(cls, extractor_type: ExtractorType, **kwargs) -> Any:
        """Create a lineage extractor."""
        if extractor_type == ExtractorType.SQL:
            return SqlLineageExtractor(**kwargs)
        elif extractor_type == ExtractorType.COLUMN:
            return ColumnLineageExtractor(**kwargs)
        elif extractor_type == ExtractorType.EXTERNAL:
            catalog_path = kwargs.get("catalog_path")
            if not catalog_path:
                raise InvalidConfigurationError(
                    "catalog_path", "Required for external extractor"
                )
            return ExternalSourceMapper(Path(catalog_path))
        elif extractor_type == ExtractorType.TRANSFORMATION:
            return TransformationTracker(**kwargs)
        elif extractor_type == ExtractorType.CROSS_DATABASE:
            catalog_paths = kwargs.get("catalog_paths")
            if not catalog_paths:
                raise InvalidConfigurationError(
                    "catalog_paths", "Required for cross-database extractor"
                )
            return CrossDatabaseLineageBuilder(catalog_paths)
        else:
            raise UnsupportedOperationError(
                f"create_extractor({extractor_type.value})",
                f"Unknown extractor type: {extractor_type.value}",
            )

    @classmethod
    def create_analyzer(
        cls, analyzer_type: AnalyzerType, graph: LineageGraph, **kwargs
    ) -> Any:
        """Create a lineage analyzer."""
        if analyzer_type == AnalyzerType.IMPACT:
            return ImpactAnalyzer(graph)
        elif analyzer_type == AnalyzerType.HISTORY:
            storage_path = kwargs.get("storage_path")
            return LineageHistoryTracker(storage_path)
        elif analyzer_type == AnalyzerType.TRANSFORMATION:
            return TransformationTracker(**kwargs)
        else:
            raise UnsupportedOperationError(
                f"create_analyzer({analyzer_type.value})",
                f"Unknown analyzer type: {analyzer_type.value}",
            )

    @classmethod
    def create_builder(cls, catalog_path: Path, **kwargs) -> LineageBuilder:
        """Create a lineage builder."""
        return LineageBuilder(catalog_path)

    @classmethod
    def create_loader(cls, catalog_path: Path, **kwargs) -> CatalogLoader:
        """Create a catalog loader."""
        return CatalogLoader(catalog_path)

    @classmethod
    def create_graph(cls, **kwargs) -> LineageGraph:
        """Create a lineage graph."""
        return LineageGraph()


class ObjectFactory:
    """Factory for creating database objects."""

    @staticmethod
    def create_object(
        object_type: ObjectTypeStr, name: str, **attributes
    ) -> Dict[str, Any]:
        """Create a database object representation."""
        base_object = {
            "object_type": object_type,
            "name": name,
            "database": attributes.get("database"),
            "schema": attributes.get("schema"),
            "fqn": f"{attributes.get('database', '')}.{attributes.get('schema', '')}.{name}",
        }

        # Add type-specific attributes
        if object_type == "table":
            base_object.update(
                {
                    "columns": attributes.get("columns", []),
                    "row_count": attributes.get("row_count"),
                    "bytes": attributes.get("bytes"),
                    "clustering_key": attributes.get("clustering_key"),
                }
            )
        elif object_type in ["view", "materialized_view"]:
            base_object.update(
                {
                    "definition": attributes.get("definition"),
                    "is_secure": attributes.get("is_secure", False),
                    "columns": attributes.get("columns", []),
                }
            )
        elif object_type == "dynamic_table":
            base_object.update(
                {
                    "target_lag": attributes.get("target_lag"),
                    "warehouse": attributes.get("warehouse"),
                    "query": attributes.get("query"),
                }
            )
        elif object_type == "task":
            base_object.update(
                {
                    "schedule": attributes.get("schedule"),
                    "warehouse": attributes.get("warehouse"),
                    "definition": attributes.get("definition"),
                    "predecessors": attributes.get("predecessors", []),
                }
            )
        elif object_type == "external_table":
            base_object.update(
                {
                    "location": attributes.get("location"),
                    "file_format": attributes.get("file_format"),
                    "pattern": attributes.get("pattern"),
                    "auto_refresh": attributes.get("auto_refresh", False),
                }
            )

        return base_object


class ConfigFactory:
    """Factory for creating configuration objects."""

    @staticmethod
    def create_default_config() -> Dict[str, Any]:
        """Create default configuration."""
        return {
            "timeout": {
                "default_build": 180,
                "default_impact_analysis": 60,
                "default_cross_db_build": 120,
                "default_path_finding": 30,
            },
            "limits": {
                "max_file_size": 100 * 1024 * 1024,
                "max_cache_size": 1000,
                "max_snapshots": 100,
                "max_path_depth": 10,
                "max_paths": 100,
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": None,
            },
            "storage": {
                "type": "file",
                "path": Path.home() / ".snowcli" / "lineage",
            },
        }

    @staticmethod
    def merge_config(
        default: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge configuration with overrides."""
        import copy

        result = copy.deepcopy(default)
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key].update(value)
            else:
                result[key] = value
        return result
