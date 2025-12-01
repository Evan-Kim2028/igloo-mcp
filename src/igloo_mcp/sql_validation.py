"""SQL validation and safe alternative generation for igloo-mcp.

This module provides SQL statement type validation and generates safe alternatives
for blocked operations like DELETE, DROP, and TRUNCATE.
"""

from __future__ import annotations

import time

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
SAFE_ALTERNATIVES: dict[str, dict[str, str]] = {
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

    return bool(canonical.startswith(_SELECT_EQUIVALENT_PREFIXES))


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
        if isinstance(parsed, exp.Drop) and hasattr(parsed, "this"):
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
) -> list[str]:
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


def _strip_leading_comments_and_whitespace(statement: str) -> str:
    """Return statement without leading whitespace or SQL comments."""

    if not statement:
        return ""

    length = len(statement)
    idx = 0

    while idx < length:
        # Skip whitespace characters
        while idx < length and statement[idx].isspace():
            idx += 1

        if idx >= length:
            break

        two = statement[idx : idx + 2]

        # Line comment starting with --
        if two == "--":
            idx += 2
            while idx < length and statement[idx] not in "\n\r":
                idx += 1
            while idx < length and statement[idx] in "\n\r":
                idx += 1
            continue

        # Block comment starting with /* ... */
        if two == "/*":
            idx += 2
            while idx < length and statement[idx : idx + 2] != "*/":
                idx += 1
            idx = min(length, idx + 2)
            continue

        break

    return statement[idx:]


def validate_sql_statement(
    statement: str,
    allow_list: list[str],
    disallow_list: list[str],
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
    # Input validation (Fix #75)
    if statement is None:
        raise ValueError("SQL cannot be None")

    if not isinstance(statement, str):
        raise TypeError(f"SQL must be a string, got {type(statement).__name__}")

    if not statement.strip():
        raise ValueError("SQL cannot be empty or whitespace-only")

    # Build effective allow list: include SELECT-equivalent statements when SELECT is allowed
    allow_set = {item.lower() for item in allow_list}
    disallow_set = {item.lower() for item in disallow_list}
    # CRITICAL FIX: Ensure all lists are lowercase for upstream validation compatibility
    effective_allow_list = [item.lower() for item in allow_list]

    if "select" in allow_set:
        for extra in _SELECT_EQUIVALENT_ALLOWLIST:
            if extra not in allow_set:
                effective_allow_list.append(extra)
                allow_set.add(extra)

    # ENHANCEMENT: Fallback validation with sqlglot for better robustness
    fallback_stmt_type: str | None = None
    select_like_hint = False
    multi_statement_detected = False
    parsed_expressions: list[exp.Expression] = []

    if HAS_SQLGLOT:
        try:
            parsed_expressions = [e for e in sqlglot.parse(statement, dialect="snowflake") if e is not None]
        except Exception:
            parsed_expressions = []

    if parsed_expressions:
        primary_expression = parsed_expressions[0]
        # Guard against None expressions from malformed input like ';'
        if primary_expression is not None:
            key = primary_expression.key or ""
            fallback_stmt_type = key.upper() or None
        multi_statement_detected = len(parsed_expressions) > 1

        if not multi_statement_detected and primary_expression is not None:
            select_like_hint = _is_select_like_statement(statement, parsed=primary_expression)

            if not select_like_hint and fallback_stmt_type in {"SELECT", "WITH"}:
                statement_upper = statement.upper()
                if "LATERAL FLATTEN" in statement_upper or "CROSS JOIN LATERAL" in statement_upper:
                    select_like_hint = True

    # CRITICAL FIX: Use lowercase lists for upstream validation (it's case-sensitive)
    lowercase_disallow_list = [item.lower() for item in disallow_list]
    try:
        stmt_type, is_valid = validate_sql_type(statement, effective_allow_list, lowercase_disallow_list)
    except (ValueError, TypeError):
        # Re-raise expected validation errors as-is
        raise
    except Exception as e:
        # Wrap ALL sqlglot/parsing errors as ValueError
        # This handles TokenError, ParseError, IndexError, and other sqlglot internals
        error_type = type(e).__name__
        raise ValueError(f"Invalid SQL syntax ({error_type}): {e}") from e

    # FIX #41: Reclassify DESCRIBE statements from 'Command' to 'Describe'
    statement_upper = statement.strip().upper()
    if stmt_type == "Command" and statement_upper.startswith("DESCRIBE"):
        stmt_type = "Describe"
        # Re-evaluate validity with the corrected type, respecting disallow_list
        if "describe" in disallow_set:
            is_valid = False
        elif "describe" in allow_set:
            is_valid = True
        else:
            is_valid = False

    if multi_statement_detected:
        detected: list[str] = []
        for expr in parsed_expressions:
            # Guard against None expressions in multi-statement detection
            if expr is not None:
                name = (expr.key or "UNKNOWN").upper()
                if name not in detected:
                    detected.append(name)

        pretty_detected = ", ".join(t.title() for t in detected) if detected else "Unknown"
        error_msg = (
            "Multiple SQL statements detected in a single request. "
            "Only a single statement is permitted for execute_query. "
            f"Detected statements: {pretty_detected}."
        )
        return "MultipleStatements", False, error_msg

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

    if select_like_hint and "select" in allow_set and not multi_statement_detected:
        if is_valid:
            return "Select", True, None

        if canonical_stmt in {"", "unknown", "command"}:
            return "Select", True, None

        if _is_select_equivalent(stmt_type):
            return "Select", True, None

    if is_valid:
        return stmt_type, True, None

    # Safe lexical fallback for Snowflake SHOW statements
    # Upstream parsers (including sqlglot) often classify SHOW as Command/Unknown.
    # Since SHOW is read-only and already governed by the 'show' permission, we
    # recognize it lexically to avoid false blocks.
    try:
        stripped = _strip_leading_comments_and_whitespace(statement)
    except Exception:  # pragma: no cover - extremely defensive
        stripped = statement.lstrip() if hasattr(statement, "lstrip") else statement

    if stripped.upper().startswith("SHOW"):
        # Always normalize to the "Show" statement type for clarity.
        stmt_type = "Show"

        # Disallow entries must win even if SHOW appears in allow_list.
        if "show" in disallow_set:
            is_valid = False
        elif "show" in allow_set:
            return "Show", True, None

    # Generate error message with alternatives
    alternatives = generate_sql_alternatives(statement, stmt_type)

    # Enhanced structured error messages
    structured_error = {
        "code": "SQL_TYPE_NOT_ALLOWED",
        "statement_type": stmt_type,
        "allowed_types": [t.capitalize() for t in allow_list] if allow_list else [],
        "suggestions": [],
    }

    if alternatives:
        alt_text = "\n".join(alternatives)
        error_msg = f"SQL statement type '{stmt_type}' is not permitted.\n\nSafe alternatives:\n{alt_text}"
        structured_error["suggestions"] = ["Use safe alternatives provided above"]
    else:
        # Capitalize allow_list for display (they're lowercase for validation)
        display_allowed = [t.capitalize() for t in allow_list]
        canonical_stmt = _canonicalize_statement_type(stmt_type)
        details = [f"SQL statement type '{stmt_type}' is not permitted."]

        if canonical_stmt == "command":
            details.append(
                "Snowflake returned 'Command' for this SQL, which is a fallback when the parser "
                "cannot classify the statement. Such statements are always blocked."
            )
        else:
            details.append("Detected type is provided by the Snowflake parser.")

        # Enhanced suggestions for common issues
        if "Unknown" in stmt_type:
            # Special handling for Unknown type errors
            if "LATERAL" in statement.upper():
                details.append("\n💡 This query contains LATERAL operations.")
                details.append("   If this is a SELECT query, LATERAL should be supported.")
                structured_error["suggestions"].append(
                    "Check if this is actually a SELECT query with LATERAL operations"
                )
            elif "WITH" in statement.upper():
                details.append("\n💡 This query starts WITH (CTE pattern).")
                details.append("   If this is a SELECT with CTE, it should be supported.")
                structured_error["suggestions"].append("Verify this is a SELECT statement with Common Table Expression")

            # Add sqlglot fallback information if available
            if fallback_stmt_type and fallback_stmt_type != "UNKNOWN":
                details.append(f"\n🔍 sqlglot detected this as: {fallback_stmt_type}")
                if fallback_stmt_type in ["SELECT", "WITH"] and "select" in allow_set:
                    details.append("   This appears to be a SELECT query that should be allowed.")
                    structured_error["suggestions"].append(
                        "Consider enabling SELECT statements if this is a data query"
                    )

        if display_allowed:
            details.append(f"\nAllowed types: {', '.join(display_allowed)}")
            structured_error["allowed_types"] = display_allowed

        error_msg = "\n".join(details)

    return stmt_type, False, error_msg


def _is_select_like_statement(statement: str, parsed: exp.Expression | None = None) -> bool:
    """Return True when the SQL behaves like a SELECT or set operation."""

    if not HAS_SQLGLOT:
        return False

    if parsed is None:
        try:
            parsed = sqlglot.parse_one(statement, dialect="snowflake")
        except Exception:
            return False

    def is_select_like(node: exp.Expression | None) -> bool:
        if node is None:
            return False

        if isinstance(node, (exp.Select, exp.SetOperation)):
            return True

        if isinstance(node, exp.With):
            target = node.this or node.args.get("expression")
            return is_select_like(target)

        if isinstance(node, (exp.Subquery, exp.Paren)):
            return is_select_like(node.this)

        if isinstance(node, exp.Query):
            return is_select_like(node.this)

        return False

    def strip_comments(sql: str) -> str:
        """Remove block and line comments while preserving string literals."""

        def remove_block_comments(source: str) -> str:
            result: list[str] = []
            in_single = False
            in_double = False
            idx = 0

            while idx < len(source):
                char = source[idx]

                if char == "'" and not in_double:
                    in_single = not in_single
                    result.append(char)
                    idx += 1
                    continue

                if char == '"' and not in_single:
                    in_double = not in_double
                    result.append(char)
                    idx += 1
                    continue

                if not in_single and not in_double and source.startswith("/*", idx):
                    idx += 2
                    depth = 1
                    while idx < len(source) and depth > 0:
                        if source.startswith("/*", idx):
                            depth += 1
                            idx += 2
                            continue
                        if source.startswith("*/", idx):
                            depth -= 1
                            idx += 2
                            continue
                        idx += 1
                    continue

                result.append(char)
                idx += 1

            return "".join(result)

        def remove_line_comments(source: str) -> str:
            lines: list[str] = []
            for line in source.splitlines():
                in_single = False
                in_double = False
                idx = 0
                while idx < len(line):
                    char = line[idx]
                    if char == "'" and not in_double:
                        in_single = not in_single
                    elif char == '"' and not in_single:
                        in_double = not in_double
                    elif (
                        char == "-" and not in_single and not in_double and idx + 1 < len(line) and line[idx + 1] == "-"
                    ):
                        line = line[:idx]
                        break
                    idx += 1
                lines.append(line)
            return "\n".join(lines)

        without_blocks = remove_block_comments(sql)
        return remove_line_comments(without_blocks)

    structural_select = is_select_like(parsed)
    if not structural_select:
        return False

    upper_without_line_comments = strip_comments(statement).upper()
    keyword_tokens = ("UNION", "INTERSECT", "EXCEPT", "MINUS")
    contains_keywords = any(token in upper_without_line_comments for token in keyword_tokens)

    if not contains_keywords:
        return True

    has_set_operation = isinstance(parsed, exp.SetOperation)
    if not has_set_operation:
        has_set_operation = any(isinstance(node, exp.SetOperation) for node in parsed.walk())

    return bool(has_set_operation)


def get_sql_statement_type(statement: str) -> str:
    """Get the type of a SQL statement.

    Args:
        statement: SQL statement to analyze

    Returns:
        Statement type (e.g., "Select", "Delete", "Unknown")

    Raises:
        ValueError: If SQL statement cannot be parsed
    """
    try:
        stmt_type = get_statement_type(statement)
    except (ValueError, TypeError):
        # Re-raise expected validation errors as-is
        raise
    except Exception as e:
        # Wrap ALL sqlglot/parsing errors (TokenError, ParseError, etc.) as ValueError
        # to maintain consistent error contract for property-based tests
        error_type = type(e).__name__
        raise ValueError(f"Invalid SQL syntax ({error_type}): {e}") from e

    if _is_select_equivalent(stmt_type):
        return "Select"

    return stmt_type
