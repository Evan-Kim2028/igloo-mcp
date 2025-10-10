"""Type definitions and type aliases for the lineage module."""

from __future__ import annotations

from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Protocol,
    Set,
    Tuple,
    TypeAlias,
    TypedDict,
    Union,
)

from typing_extensions import NotRequired

# Basic type aliases
NodeKey: TypeAlias = str
EdgeKey: TypeAlias = Tuple[str, str]
DatabaseName: TypeAlias = str
SchemaName: TypeAlias = str
ObjectName: TypeAlias = str
FQN: TypeAlias = str  # Fully Qualified Name
SQL: TypeAlias = str
JSON: TypeAlias = Dict[str, Any]

# Graph-related types
GraphPath: TypeAlias = List[NodeKey]
GraphPaths: TypeAlias = List[GraphPath]
NodeAttributes: TypeAlias = Dict[str, Union[str, int, float, bool]]
EdgeAttributes: TypeAlias = Dict[str, Union[str, int, float, bool]]

# Lineage-specific types
LineageDirection = Literal["upstream", "downstream", "both"]
ObjectTypeStr = Literal[
    "table", "view", "materialized_view", "dynamic_table", "task", "external_table"
]
ChangeTypeStr = Literal[
    "drop",
    "alter_schema",
    "alter_data_type",
    "rename",
    "add_column",
    "drop_column",
    "modify_logic",
    "permission_change",
    "refresh_schedule",
]
SeverityLevel = Literal["critical", "high", "medium", "low", "info"]
TransformationTypeStr = Literal[
    "direct",
    "alias",
    "function",
    "aggregate",
    "case",
    "window",
    "join",
    "subquery",
    "literal",
    "unknown",
]


class CatalogEntry(TypedDict):
    """Type definition for catalog entries."""

    object_type: ObjectTypeStr
    name: str
    database: NotRequired[str]
    schema: NotRequired[str]
    ddl: NotRequired[str]
    text: NotRequired[str]
    definition: NotRequired[str]


class ImpactSummary(TypedDict):
    """Type definition for impact analysis summary."""

    total_impacted: int
    by_severity: Dict[SeverityLevel, int]
    by_object_type: Dict[ObjectTypeStr, int]
    by_database: Dict[DatabaseName, int]
    average_distance: float
    max_distance: int
    direct_impacts: int


class TransformationSummary(TypedDict):
    """Type definition for transformation summary."""

    total_transformations: int
    transformation_types: Dict[TransformationTypeStr, int]
    categories: Dict[str, int]
    top_patterns: List[Dict[str, Any]]
    average_complexity: float
    most_transformed_columns: Dict[str, int]
    transformation_chains: List[List[str]]


class LineageSnapshot(TypedDict):
    """Type definition for lineage snapshot."""

    snapshot_id: str
    timestamp: str
    database: str
    nodes: Dict[NodeKey, NodeAttributes]
    edges: List[Dict[str, str]]
    metadata: Dict[str, Any]


class ExternalSourceInfo(TypedDict):
    """Type definition for external source information."""

    source_type: Literal["s3", "azure_blob", "gcs", "http", "stage"]
    location: str
    stage_name: NotRequired[str]
    file_pattern: NotRequired[str]
    file_format: NotRequired[str]
    has_credentials: bool
    credentials_ref: NotRequired[str]


# Protocol classes for better type checking
class LineageProvider(Protocol):
    """Protocol for objects that can provide lineage information."""

    def get_upstream_objects(self, object_name: str) -> Set[str]: ...

    def get_downstream_objects(self, object_name: str) -> Set[str]: ...

    def get_lineage_path(self, source: str, target: str) -> Optional[GraphPath]: ...


class SQLParser(Protocol):
    """Protocol for SQL parsing implementations."""

    def parse(self, sql: str, dialect: str = "snowflake") -> Optional[Any]: ...

    def extract_tables(self, sql: str) -> Set[str]: ...

    def extract_columns(self, sql: str) -> Set[str]: ...


class StorageBackend(Protocol):
    """Protocol for storage backend implementations."""

    def save(self, key: str, data: Any) -> bool: ...

    def load(self, key: str) -> Optional[Any]: ...

    def delete(self, key: str) -> bool: ...

    def exists(self, key: str) -> bool: ...


# Function type signatures
TransformFunc = Callable[[Any], Any]
ValidatorFunc = Callable[[str], bool]
FilterFunc = Callable[[NodeKey, NodeAttributes], bool]
ScoreFunc = Callable[[List[Any]], float]


# Result types
class OperationResult(TypedDict):
    """Type definition for operation results."""

    success: bool
    data: NotRequired[Any]
    error: NotRequired[str]
    warnings: NotRequired[List[str]]
    metadata: NotRequired[Dict[str, Any]]


class ValidationResult(TypedDict):
    """Type definition for validation results."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: NotRequired[List[str]]


# Complex nested types
GraphData: TypeAlias = Dict[NodeKey, Dict[NodeKey, EdgeAttributes]]
DependencyMap: TypeAlias = Dict[FQN, Set[FQN]]
TransformationChain: TypeAlias = List[Tuple[str, TransformationTypeStr, Optional[str]]]
ImpactPath: TypeAlias = List[Tuple[NodeKey, SeverityLevel, float]]

# Callback types
ProgressCallback = Callable[[int, int, str], None]
ErrorCallback = Callable[[Exception, Dict[str, Any]], None]
WarningCallback = Callable[[str, Dict[str, Any]], None]
