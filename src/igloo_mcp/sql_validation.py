"""SQL validation and safe alternative generation for igloo-mcp.

This module provides SQL statement type validation and generates safe alternatives
for blocked operations like DELETE, DROP, and TRUNCATE.
"""

from __future__ import annotations

import time
from typing import Dict, List

# Import upstream validation from snowflake-labs-mcp
from mcp_server_snowflake.query_manager.tools import (
    get_statement_type,
    validate_sql_type,
)

try:
    import sqlglot
    from sqlglot import exp

    HAS_SQLGLOT = True
except ImportError:  # pragma: no cover
    HAS_SQLGLOT = False


# Template-based safe alternatives for blocked SQL operations
SAFE_ALTERNATIVES: Dict[str, Dict[str, str]] = {
    "Delete": {
        "soft_delete": "UPDATE {table} SET deleted_at = CURRENT_TIMESTAMP() WHERE {condition}",
        "create_view": "CREATE VIEW active_{table} AS SELECT * FROM {table} WHERE NOT ({condition})",
    },
    "Drop": {
        "rename": "ALTER TABLE {table} RENAME TO {table}_deprecated_{timestamp}",
        "comment": "ALTER TABLE {table} SET COMMENT = 'Deprecated {timestamp}'",
    },
    "Truncate": {
        "delete_all": "DELETE FROM {table}  -- Add WHERE clause for safety",
    },
    "TruncateTable": {  # Upstream may return this variant
        "delete_all": "DELETE FROM {table}  -- Add WHERE clause for safety",
    },
}

# Statement types that should inherit SELECT permissions (case insensitive).
_SELECT_EQUIVALENT_PREFIXES = ("union", "intersect", "except", "minus")
_SELECT_EQUIVALENT_ALLOWLIST = {
    "union",
    "union all",
    "union_all",
    "unionall",
    "intersect",
    "intersect all",
    "intersect_all",
    "intersectall",
    "except",
    "except all",
    "except_all",
    "exceptall",
    "minus",
    "minus all",
    "minus_all",
    "minusall",
}


def _canonicalize_statement_type(stmt_type: str | None) -> str:
    """Return a lowercase canonical representation of a statement type."""

    if not stmt_type:
        return ""

    normalized = stmt_type.replace("_", "")
    normalized = normalized.replace(" ", "")
    return normalized.lower()


def _is_select_equivalent(stmt_type: str | None) -> bool:
    """Determine if a statement type should be treated as SELECT."""

    canonical = _canonicalize_statement_type(stmt_type)

    if not canonical:
        return False

    if canonical.startswith(_SELECT_EQUIVALENT_PREFIXES):
        return True

    return False


def extract_table_name(sql_statement: str) -> str:
    """Extract table name from SQL statement using sqlglot.

    Args:
        sql_statement: SQL statement to parse

    Returns:
        Table name or "<table_name>" if extraction fails

    Raises:
        ValueError: If sqlglot is not available
    """
    if not HAS_SQLGLOT:  # pragma: no cover
        raise ValueError("sqlglot is required for table name extraction")

    try:
        parsed = sqlglot.parse_one(sql_statement)

        # Try to find any Table node in the AST
        for table in parsed.find_all(exp.Table):
            if table.name:
                return table.name
            # Try to get the string representation
            table_str = str(table)
            if table_str and table_str != "<table_name>":
                return table_str

        # Special handling for DROP which uses Identifier
        if isinstance(parsed, exp.Drop):
            if hasattr(parsed, "this"):
                # Get the identifier
                identifier = parsed.this
                if hasattr(identifier, "name"):
                    return identifier.name
                return str(identifier)

    except Exception:
        # If parsing fails, return placeholder
        pass

    return "<table_name>"


def generate_sql_alternatives(
    statement: str,
    stmt_type: str,
) -> List[str]:
    """Generate safe alternative SQL statements for blocked operations.

    Args:
        statement: Original SQL statement
        stmt_type: Statement type (Delete, Drop, Truncate, etc.)

    Returns:
        List of formatted alternative SQL statements with warnings
    """
    if stmt_type not in SAFE_ALTERNATIVES:
        return []

    # Try to extract table name
    try:
        table = extract_table_name(statement)
    except ValueError:
        # sqlglot not available, use placeholder
        table = "<table_name>"
    except Exception:
        table = "<table_name>"

    alternatives = []
    templates = SAFE_ALTERNATIVES[stmt_type]

    for name, template in templates.items():
        # Format template with extracted values
        formatted = template.format(
            table=table,
            condition="<your_condition>",
            timestamp=int(time.time()),
        )

        alternatives.append(f"  {name}: {formatted}")

    # Add warning
    alternatives.append("\n⚠️  Review and customize templates before executing.")

    return alternatives


def validate_sql_statement(
    statement: str,
    allow_list: List[str],
    disallow_list: List[str],
) -> tuple[str, bool, str | None]:
    """Validate SQL statement against permission lists.

    Args:
        statement: SQL statement to validate
        allow_list: List of allowed statement types (e.g., ["Select", "Insert"])
        disallow_list: List of disallowed statement types (e.g., ["Delete", "Drop"])

    Returns:
        Tuple of (statement_type, is_valid, error_message)
        - statement_type: The detected SQL statement type
        - is_valid: True if allowed, False if blocked
        - error_message: Detailed error with alternatives if blocked, None if valid
    """
    # Build effective allow list: include SELECT-equivalent statements when SELECT is allowed
    allow_set = {item.lower() for item in allow_list}
    disallow_set = {item.lower() for item in disallow_list}
    effective_allow_list = list(allow_list)

    if "select" in allow_set:
        for extra in _SELECT_EQUIVALENT_ALLOWLIST:
            if extra not in allow_set:
                effective_allow_list.append(extra)
                allow_set.add(extra)

    # Use upstream validation with the expanded allow list
    stmt_type, is_valid = validate_sql_type(
        statement, effective_allow_list, disallow_list
    )

    canonical_stmt = _canonicalize_statement_type(stmt_type)

    if canonical_stmt.startswith("with"):
        underlying_type = get_statement_type(statement)
        canonical_underlying = _canonicalize_statement_type(underlying_type)
        stmt_type = underlying_type or stmt_type

        if canonical_underlying == "select" and "select" in allow_set:
            return "Select", True, None

        if canonical_underlying in disallow_set:
            is_valid = False

    # Normalize statement types that should inherit SELECT permissions
    if _is_select_equivalent(stmt_type):
        stmt_type = "Select"
        if "select" in allow_set and not is_valid:
            # Treat SELECT-equivalent statements as allowed when SELECT is permitted
            return stmt_type, True, None

    if is_valid:
        return stmt_type, True, None

    # Generate error message with alternatives
    alternatives = generate_sql_alternatives(statement, stmt_type)

    if alternatives:
        alt_text = "\n".join(alternatives)
        error_msg = (
            f"SQL statement type '{stmt_type}' is not permitted.\n\n"
            f"Safe alternatives:\n{alt_text}"
        )
    else:
        # Capitalize allow_list for display (they're lowercase for validation)
        display_allowed = [t.capitalize() for t in allow_list]
        error_msg = (
            f"SQL statement type '{stmt_type}' is not permitted. "
            f"Allowed types: {', '.join(display_allowed)}"
        )

    return stmt_type, False, error_msg


def get_sql_statement_type(statement: str) -> str:
    """Get the type of a SQL statement.

    Args:
        statement: SQL statement to analyze

    Returns:
        Statement type (e.g., "Select", "Delete", "Unknown")
    """
    stmt_type = get_statement_type(statement)

    if _is_select_equivalent(stmt_type):
        return "Select"

    return stmt_type
