"""Constants for the lineage module to avoid magic numbers and improve maintainability."""

from __future__ import annotations


# Timeout constants (in seconds)
class Timeouts:
    """Timeout values for various operations."""

    DEFAULT_BUILD = 180  # 3 minutes for building lineage
    DEFAULT_IMPACT_ANALYSIS = 60  # 1 minute for impact analysis
    DEFAULT_CROSS_DB_BUILD = 120  # 2 minutes for cross-database lineage
    DEFAULT_PATH_FINDING = 30  # 30 seconds for path finding
    DEFAULT_SQL_PARSE = 10  # 10 seconds for SQL parsing
    DEFAULT_NETWORK_REQUEST = 30  # 30 seconds for network requests


# Size limits
class Limits:
    """Size and count limits for various operations."""

    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB max file size
    MAX_CACHE_SIZE = 1000  # Max items in LRU cache
    MAX_SQL_CACHE_SIZE = 500  # Max SQL parse cache entries
    MAX_SNAPSHOTS = 100  # Max snapshots to retain in history
    MAX_SNAPSHOT_DAYS = 90  # Days to keep snapshots
    MAX_PATH_DEPTH = 10  # Max depth for path finding
    MAX_PATHS = 100  # Max paths to return in traversal
    MAX_IMPACT_DEPTH = 10  # Max depth for impact analysis
    MAX_HUB_CONNECTIONS = 5  # Min connections for database hubs
    MAX_PATTERN_FREQUENCY = 2  # Min frequency for transformation patterns
    MAX_SQL_LENGTH = 500  # Max SQL length for safe display
    MAX_HTML_LENGTH = 10000  # Max HTML content length


# Analysis thresholds
class Thresholds:
    """Threshold values for various analysis operations."""

    HIGH_RISK_SCORE = 0.8
    MEDIUM_RISK_SCORE = 0.5
    LOW_RISK_SCORE = 0.3
    CRITICAL_PATH_MIN_LENGTH = 3
    MIN_CONFIDENCE = 0.5
    HIGH_CONFIDENCE = 1.0
    SEVERITY_CRITICAL_WEIGHT = 10
    SEVERITY_HIGH_WEIGHT = 5
    SEVERITY_MEDIUM_WEIGHT = 2
    SEVERITY_LOW_WEIGHT = 1


# String constants
class Formats:
    """Format strings and patterns."""

    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    ISO_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
    SNAPSHOT_ID_LENGTH = 12
    TEMP_FILE_SUFFIX = ".tmp"
    JSON_INDENT = 2
    DEFAULT_DIALECT = "snowflake"


# Regular expression patterns
class Patterns:
    """Common regex patterns used throughout the codebase."""

    OBJECT_NAME = r"^[A-Za-z_][A-Za-z0-9_$]*$"
    QUOTED_IDENTIFIER = r'^".*"$'
    S3_BUCKET = r"s3://([^/]+)"
    AZURE_BLOB = r"azure://([^.]+)"
    GCS_BUCKET = r"gcs://([^/]+)"
    STAGE_REFERENCE = r"@(\w+(?:\.\w+)*)"
    EXTERNAL_URL = r"((?:s3|azure|gcs)://[^\s\)'\"]+)"
    COPY_INTO = r"copy\s+into\s+(\S+)\s+from\s+([^\s\)]+)"

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r";\s*(DROP|DELETE|TRUNCATE|ALTER|CREATE|INSERT|UPDATE|EXEC|EXECUTE)\s+",
        r"--[^\n]*",
        r"/\*.*?\*/",
        r"#.*$",
        r"\b(UNION\s+(ALL\s+)?SELECT|UNION\s+ALL)",
        r"\b(OR|AND)\s+(\d+\s*[=<>!]\s*\d+|'[^']*'\s*[=<>!]\s*'[^']*')",
        r"\b(WAITFOR|SLEEP|BENCHMARK|pg_sleep)\s*\(",
        r";\s*[A-Za-z]",
        r"\b(information_schema|sys\.tables|mysql\.user)",
        r"['\"`;].*['\"`;]",
        r"0x[0-9a-fA-F]+",
        r"<\s*script[^>]*>",
    ]

    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = ["../", "..\\", "%2e%2e", "..%2f", "..%5c"]


# Error messages
class ErrorMessages:
    """Standard error messages."""

    TIMEOUT = "Operation timed out after {seconds} seconds"
    OBJECT_NOT_FOUND = "Object {object} not found in lineage graph"
    INVALID_PATH = "Invalid path: {path}"
    INVALID_SQL = "Failed to parse SQL: {error}"
    FILE_TOO_LARGE = "File exceeds maximum size of {max_size} bytes"
    PARSE_ERROR = "Failed to parse {object_type}: {error}"
    MISSING_CREDENTIALS = "No credentials found for {source}"
    SQL_INJECTION_DETECTED = "Potential SQL injection detected in query"
    PATH_TRAVERSAL_DETECTED = "Path traversal attempt detected"


# Column names and attributes
class Attributes:
    """Common attribute and column names."""

    OBJECT_TYPE = "object_type"
    DATABASE = "database"
    SCHEMA = "schema"
    NAME = "name"
    FQN = "fqn"
    IN_CATALOG = "in_catalog"
    STATUS = "status"
    SOURCE = "source"
    TARGET = "target"
    TYPE = "type"
    TIMESTAMP = "timestamp"
    VERSION = "version"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    SEVERITY = "severity"
    CONFIDENCE = "confidence"
