# Session Parameter Security

## Overview

This document describes the security measures implemented for session parameter handling in the `execute_query` tool to prevent SQL injection attacks.

## Security Measures

### 1. Parameter Name Whitelist

All session parameter names are validated against a strict whitelist (`ALLOWED_SESSION_PARAMETERS`). Only pre-approved parameters can be accessed or modified.

**Whitelisted Parameters:**
- `QUERY_TAG`
- `STATEMENT_TIMEOUT_IN_SECONDS`
- `AUTOCOMMIT`
- `ABORT_DETACHED_QUERY`
- `BINARY_INPUT_FORMAT`
- `BINARY_OUTPUT_FORMAT`
- `DATE_INPUT_FORMAT`
- `DATE_OUTPUT_FORMAT`
- `TIMESTAMP_INPUT_FORMAT`
- `TIMESTAMP_OUTPUT_FORMAT`
- `TIMESTAMP_LTZ_OUTPUT_FORMAT`
- `TIMESTAMP_NTZ_OUTPUT_FORMAT`
- `TIMESTAMP_TZ_OUTPUT_FORMAT`
- `TIME_INPUT_FORMAT`
- `TIME_OUTPUT_FORMAT`

**Security Benefit:** Prevents injection through parameter names. Even if an attacker attempts to use malicious parameter names like `"QUERY_TAG'; DROP TABLE users; --"`, the whitelist check will reject it before any SQL is constructed.

### 2. SQL Value Escaping

All parameter values are escaped before being inserted into SQL statements:

- **Tag Values:** Single quotes are escaped by doubling them (`'` → `''`)
- **Numeric Values:** Validated as integers/floats before use (no string interpolation)
- **String Values:** Single quotes are escaped and values are wrapped in quotes

**Example:**
```python
# Input: "tag' OR '1'='1"
# Escaped: "tag'' OR ''1''=''1"
# SQL: ALTER SESSION SET QUERY_TAG = 'tag'' OR ''1''=''1'
```

### 3. SQL Identifier Escaping

Parameter names used in LIKE clauses are escaped to prevent injection:

- **Single Quotes:** Escaped by doubling (`'` → `''`)
- **LIKE Wildcards:** Escaped to prevent pattern matching (`%` → `\%`, `_` → `\_`)
- **Backslashes:** Escaped first to prevent escape sequence injection (`\` → `\\`)

```python
# Input: "QUERY_TAG' OR '1'='1"
# Escaped: "QUERY_TAG'' OR ''1''=''1"
# SQL: SHOW PARAMETERS LIKE 'QUERY_TAG'' OR ''1''=''1' IN SESSION

# Input: "QUERY_TAG%"
# Escaped: "QUERY_TAG\%"
# SQL: SHOW PARAMETERS LIKE 'QUERY_TAG\%' IN SESSION
# (Prevents matching QUERY_TAG_ANY_SUFFIX)

# Input: "QUERY_TAG_"
# Escaped: "QUERY_TAG\_"
# SQL: SHOW PARAMETERS LIKE 'QUERY_TAG\_' IN SESSION
# (Prevents matching QUERY_TAGX where X is any character)
```

### 4. Numeric Validation

Timeout values are strictly validated as integers within allowed range (1-3600 seconds). Non-numeric values are rejected before SQL construction.

## Security Assumptions

1. **Snowflake SQL Escaping:** We assume Snowflake properly handles escaped single quotes in string literals. The `''` (doubled single quote) pattern is the standard SQL escaping mechanism.

2. **Whitelist Completeness:** We assume the whitelist contains all necessary session parameters and does not include dangerous parameters that could be exploited.

3. **Parameter Binding Limitation:** Snowflake's `ALTER SESSION` statements do not support parameterized queries in the same way as regular SQL statements. Therefore, we use string escaping with f-strings, which is safe when combined with:
   - Whitelist validation
   - Proper escaping functions
   - Input validation

4. **Case Insensitivity:** Parameter name validation is case-insensitive (converted to uppercase), ensuring consistent security regardless of input casing.

## Attack Vectors Mitigated

### SQL Injection via Parameter Names
- **Attack:** `"QUERY_TAG'; DROP TABLE users; --"`
- **Mitigation:** Whitelist check rejects non-whitelisted names before SQL construction

### SQL Injection via Parameter Values
- **Attack:** `"tag'; DELETE FROM logs; --"`
- **Mitigation:** Single quotes are escaped (`''`), making the value a literal string

### SQL Injection via LIKE Clause
- **Attack:** `"QUERY_TAG' OR '1'='1"` or `"QUERY_TAG%"` (wildcard injection)
- **Mitigation:** Identifier escaping prevents injection in LIKE patterns, including wildcard characters (`%`, `_`) which are escaped to prevent unintended pattern matching

### Type Confusion Attacks
- **Attack:** Passing non-numeric values for timeout parameters
- **Mitigation:** Strict type validation and conversion to int before SQL construction

## SQL Statement Parameter Security

The SQL `statement` parameter itself is handled securely:

1. **Direct Execution:** The statement is passed directly to Snowflake's `cursor.execute(statement)` method, which uses parameterized queries internally. The statement is **never** interpolated into other SQL strings.

2. **Length Validation:** Statements exceeding `MAX_SQL_STATEMENT_LENGTH` are rejected before execution.

3. **Type Validation:** Statements are validated against permission lists (allow/disallow) using `validate_sql_statement()`.

4. **Multi-Statement Detection:** Multiple statements in a single request are detected and blocked.

5. **No String Interpolation:** Unlike session parameters, the SQL statement is not constructed via string formatting, eliminating SQL injection risk for the statement itself.

**Note:** The primary SQL injection risk is in session parameter handling (which is mitigated above), not in the statement parameter itself.

## Limitations and Future Improvements

1. **Parameterized Queries:** Currently not possible with Snowflake's `ALTER SESSION` syntax. If Snowflake adds support for parameterized session parameter operations, we should migrate to that approach.

2. **Additional Escaping:** Consider using Snowflake's identifier quoting functions if available for additional safety.

3. **Input Length Limits:** Very long parameter values could potentially cause issues. Current implementation relies on Snowflake's limits.

4. **Statement Sanitization:** While the statement is not interpolated, consider adding null-byte detection and other control character checks for defense-in-depth.

## Testing

Comprehensive SQL injection tests are located in `tests/test_sql_injection_security.py` covering:
- Whitelist enforcement
- Escaping functions (single quotes, LIKE wildcards, backslashes)
- Malicious input patterns
- LIKE clause wildcard injection prevention
- Edge cases (Unicode, special characters, null values)
- Extremely long values

## References

- [Snowflake SQL Injection Prevention](https://docs.snowflake.com/en/user-guide/security-best-practices)
- [OWASP SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
