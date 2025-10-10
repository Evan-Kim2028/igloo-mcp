"""Base classes and protocols for the lineage module."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Set

from .types import (
    FQN,
    NodeAttributes,
    NodeKey,
)

logger = logging.getLogger(__name__)


class LineageExtractor(ABC):
    """Abstract base class for lineage extraction."""

    @abstractmethod
    def extract(self, source: Any) -> "LineageResult":
        """Extract lineage from a source."""
        pass

    @abstractmethod
    def validate(self, source: Any) -> bool:
        """Validate if source is suitable for extraction."""
        pass


class LineageAnalyzer(ABC):
    """Abstract base class for lineage analysis."""

    @abstractmethod
    def analyze(self, graph: Any) -> "AnalysisResult":
        """Analyze a lineage graph."""
        pass

    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Get analysis metrics."""
        pass


class LineageStore(ABC):
    """Abstract base class for lineage storage."""

    @abstractmethod
    def save(self, key: str, data: Any) -> bool:
        """Save lineage data."""
        pass

    @abstractmethod
    def load(self, key: str) -> Optional[Any]:
        """Load lineage data."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete lineage data."""
        pass

    @abstractmethod
    def list_keys(self, pattern: Optional[str] = None) -> List[str]:
        """List stored keys matching pattern."""
        pass


class GraphProvider(Protocol):
    """Protocol for graph providers."""

    def get_nodes(self) -> Set[NodeKey]:
        """Get all nodes in the graph."""
        ...

    def get_edges(self) -> Set[tuple[NodeKey, NodeKey]]:
        """Get all edges in the graph."""
        ...

    def get_node_attributes(self, node: NodeKey) -> NodeAttributes:
        """Get attributes for a node."""
        ...

    def has_path(self, source: NodeKey, target: NodeKey) -> bool:
        """Check if path exists between nodes."""
        ...


@dataclass
class BaseResult:
    """Base class for operation results."""

    success: bool
    message: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        self.success = False

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "message": self.message,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


@dataclass
class LineageResult(BaseResult):
    """Result from lineage extraction."""

    upstreams: Set[FQN] = field(default_factory=set)
    downstreams: Set[FQN] = field(default_factory=set)
    nodes: Dict[NodeKey, NodeAttributes] = field(default_factory=dict)
    edges: List[tuple[NodeKey, NodeKey]] = field(default_factory=list)


@dataclass
class AnalysisResult(BaseResult):
    """Result from lineage analysis."""

    findings: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


class BaseAnalyzer:
    """Base class for analyzers with common functionality."""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self._metrics: Dict[str, Any] = {}

    def log_debug(self, message: str, **kwargs) -> None:
        """Log debug message with context."""
        self.logger.debug(f"[{self.name}] {message}", extra=kwargs)

    def log_info(self, message: str, **kwargs) -> None:
        """Log info message with context."""
        self.logger.info(f"[{self.name}] {message}", extra=kwargs)

    def log_warning(self, message: str, **kwargs) -> None:
        """Log warning message with context."""
        self.logger.warning(f"[{self.name}] {message}", extra=kwargs)

    def log_error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log error message with context."""
        self.logger.error(f"[{self.name}] {message}", exc_info=exc_info, extra=kwargs)

    def update_metric(self, key: str, value: Any) -> None:
        """Update a metric value."""
        self._metrics[key] = value

    def increment_metric(self, key: str, amount: int = 1) -> None:
        """Increment a metric counter."""
        self._metrics[key] = self._metrics.get(key, 0) + amount

    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics."""
        return self._metrics.copy()


class BaseExtractor(BaseAnalyzer):
    """Base class for extractors with common functionality."""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name)
        self.config = config or {}
        self._cache: Dict[str, Any] = {}

    def get_from_cache(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        return self._cache.get(key)

    def set_cache(self, key: str, value: Any) -> None:
        """Set value in cache."""
        self._cache[key] = value

    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()


class BaseTransformer(ABC):
    """Base class for data transformers."""

    @abstractmethod
    def transform(self, data: Any) -> Any:
        """Transform data."""
        pass

    @abstractmethod
    def can_transform(self, data: Any) -> bool:
        """Check if data can be transformed."""
        pass


class BaseValidator(ABC):
    """Base class for validators."""

    @abstractmethod
    def validate(self, data: Any) -> bool:
        """Validate data."""
        pass

    @abstractmethod
    def get_errors(self) -> List[str]:
        """Get validation errors."""
        pass


@dataclass
class OperationContext:
    """Context for operations with metadata."""

    operation_id: str
    user: Optional[str] = None
    database: Optional[str] = None
    schema: Optional[str] = None
    dry_run: bool = False
    verbose: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation_id": self.operation_id,
            "user": self.user,
            "database": self.database,
            "schema": self.schema,
            "dry_run": self.dry_run,
            "verbose": self.verbose,
            "metadata": self.metadata,
        }
