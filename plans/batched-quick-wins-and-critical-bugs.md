# Batched Implementation Plan: Quick Wins + Critical Bugs

## Overview

This plan addresses **8 issues** grouped into **3 independent batches** based on file conflicts and dependencies. Each batch can be implemented and merged separately, or all three can be worked on in parallel for maximum efficiency.

**Total Estimated Effort:** 4-6 hours
**Recommended Approach:** Implement all 3 batches in parallel, create 3 separate PRs

---

## Batch Grouping Strategy

### Batch A: Config & Tooling (No Code Changes)
**Issues:** #78, #79, #82, #83
**Files:** `pyproject.toml`, `.pre-commit-config.yaml`, `.env.example` (new), line-length fixes
**Risk:** LOW - Configuration only, no logic changes
**Effort:** 1 hour
**Can merge first:** Yes - No dependencies on other batches

### Batch B: Type Safety & Validation Errors
**Issues:** #77, #66, #75
**Files:** `changes_schema.py`, `sql_validation.py`
**Risk:** MEDIUM - Fixes actual bugs, needs careful testing
**Effort:** 2-3 hours
**Can merge first:** Yes - Independent from config changes

### Batch C: Documentation & API Consistency
**Issues:** #65
**Files:** `get_report_schema.py`
**Risk:** LOW - Documentation only, no behavior changes
**Effort:** 1 hour
**Can merge first:** Yes - Independent from other batches

---

## Batch A: Config & Tooling Cleanup

### Issues Included
- **#78** - Fix invalid `[tool.uv.build]` in pyproject.toml
- **#79** - Simplify pre-commit config (remove black/isort)
- **#82** - Add `.env.example` documenting environment variables
- **#83** - Fix ruff linting warnings (E501, E731)

### Implementation Order
1. Fix #78 (pyproject.toml) - 5 minutes
2. Fix #79 (pre-commit) - 15 minutes
3. Create #82 (.env.example) - 20 minutes
4. Fix #83 (ruff warnings) - 20 minutes

### Detailed Implementation

#### Issue #78: Fix pyproject.toml

**Problem:** Invalid `[tool.uv.build]` section causes TOML parse warnings

**Current (Lines 44-48):**
```toml
[tool.uv.build]
# Include template files in package distribution
include = [
    "src/igloo_mcp/living_reports/templates/*.j2",
]
```

**Solution:** The configuration is correct but the warning is misleading. According to uv documentation, `tool.uv` is valid. However, the specific `build` subsection may not be recognized in older uv versions.

**Fix Option 1 (Recommended): Use standard setuptools package-data**
```toml
# Remove [tool.uv.build] section entirely (lines 44-48)

[tool.setuptools.package-data]
igloo_mcp = ["living_reports/templates/*.j2"]
```

**Fix Option 2: Move to build-system requires (if using setuptools backend)**
```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
igloo_mcp = ["living_reports/templates/*.j2"]
```

**Fix Option 3: Keep uv_build but remove invalid section**
```toml
# Just delete lines 44-48 since uv_build automatically includes
# files in the module directory
```

**Verification:**
```bash
uv run mypy --version 2>&1 | grep -i "TOML parse error"
# Should return nothing
uv build
unzip -l dist/*.whl | grep .j2
# Should show template files
```

**Files Modified:**
- `/Users/evandekim/Documents/igloo_mcp/pyproject.toml` (lines 44-48)

---

#### Issue #79: Simplify Pre-commit Config

**Problem:** Redundant black and isort hooks when ruff handles both

**Current (.pre-commit-config.yaml lines 12-28):**
```yaml
  - repo: https://github.com/psf/black
    rev: 25.1.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 6.0.1
    hooks:
      - id: isort
        args: ["--profile", "black"]

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: ["--fix"]
```

**Solution:**
```yaml
  # REMOVE black and isort sections (lines 12-22)

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.6  # UPDATE version
    hooks:
      - id: ruff
        args: ["--fix"]
      - id: ruff-format  # ADD: Replaces black
```

**Also update pyproject.toml to enable import sorting:**
```toml
[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # ADD: isort (import sorting)
]
```

**Verification:**
```bash
pre-commit run --all-files
# Should pass with only ruff hooks
```

**Files Modified:**
- `/Users/evandekim/Documents/igloo_mcp/.pre-commit-config.yaml` (lines 12-28)
- `/Users/evandekim/Documents/igloo_mcp/pyproject.toml` (add "I" to select)

---

#### Issue #82: Add .env.example

**Problem:** No centralized documentation of environment variables

**Solution:** Create comprehensive `.env.example` file

**New File: `/Users/evandekim/Documents/igloo_mcp/.env.example`**
```bash
# ============================================================================
# Igloo MCP - Environment Configuration
# ============================================================================
# Copy this file to `.env` and customize for your environment
#
# SECURITY: Never commit your actual `.env` file to version control!
# ============================================================================

# ----------------------------------------------------------------------------
# Storage Configuration (Optional)
# ----------------------------------------------------------------------------
# All paths default to ~/.igloo_mcp/<category>/ if not specified

# Query history log directory
# Default: ~/.igloo_mcp/logs/doc.jsonl
# IGLOO_MCP_QUERY_HISTORY=~/.igloo_mcp/logs

# Artifact storage directory
# Default: ~/.igloo_mcp/logs/artifacts
# IGLOO_MCP_ARTIFACT_ROOT=~/.igloo_mcp/artifacts

# Living reports output directory
# Default: ~/.igloo_mcp/reports
# IGLOO_MCP_REPORTS_ROOT=~/.igloo_mcp/reports

# Catalog metadata directory
# Default: ~/.igloo_mcp/catalogs
# IGLOO_MCP_CATALOG_ROOT=~/.igloo_mcp/catalogs

# Cache directory
# Default: ~/.igloo_mcp/cache
# IGLOO_MCP_CACHE_ROOT=~/.igloo_mcp/cache

# Cache mode: "enabled", "disabled", "readonly"
# Default: enabled
# IGLOO_MCP_CACHE_MODE=enabled

# Logging scope: "global" or "namespaced"
# Default: global
# IGLOO_MCP_LOG_SCOPE=global

# Enable per-namespace log directories (true/false)
# Default: false
# IGLOO_MCP_NAMESPACED_LOGS=false

# ----------------------------------------------------------------------------
# Snowflake Connection (Required)
# ----------------------------------------------------------------------------
# Snowflake CLI profile name from ~/.snowflake/config.toml
# Default: Uses default profile from Snowflake CLI
SNOWFLAKE_PROFILE=default

# Alternative: Direct Snowflake REST API connection (bypasses CLI)
# Only use these if NOT using SNOWFLAKE_PROFILE
# SNOWFLAKE_REST_ACCOUNT=your-account.region.cloud
# SNOWFLAKE_REST_USER=your-username
# SNOWFLAKE_REST_PRIVATE_KEY=~/.snowflake/rsa_key.p8
# SNOWFLAKE_REST_WAREHOUSE=COMPUTE_WH
# SNOWFLAKE_REST_DATABASE=MY_DATABASE
# SNOWFLAKE_REST_SCHEMA=PUBLIC
# SNOWFLAKE_REST_ROLE=ACCOUNTADMIN
# SNOWFLAKE_REST_HOST=your-account.snowflakecomputing.com

# Default connection name (for multiple connections)
# SNOWFLAKE_DEFAULT_CONNECTION_NAME=default

# ----------------------------------------------------------------------------
# MCP Server Configuration (Optional)
# ----------------------------------------------------------------------------
# Transport: "stdio" (default) or "sse"
# SNOWCLI_MCP_TRANSPORT=stdio

# SSE endpoint path (only for SSE transport)
# SNOWCLI_MCP_ENDPOINT=/mcp

# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Default: INFO
# SNOWCLI_MCP_LOG_LEVEL=INFO

# Service configuration file path (advanced)
# SERVICE_CONFIG_FILE=./config/service.yaml

# ----------------------------------------------------------------------------
# External APIs (Optional)
# ----------------------------------------------------------------------------
# Dune Analytics API key (for blockchain data)
# DUNE_API_KEY=your-api-key-here

# ----------------------------------------------------------------------------
# Development & Testing (Optional)
# ----------------------------------------------------------------------------
# Enable debug mode (verbose logging)
# DEBUG=false

# Skip Snowflake connection check on startup (for testing)
# SKIP_SNOWFLAKE_CHECK=false

# Use mock Snowflake responses (for local development without Snowflake)
# MOCK_SNOWFLAKE=false
```

**Verification:**
```bash
# File should exist and be readable
cat .env.example | head -5
```

**Files Created:**
- `/Users/evandekim/Documents/igloo_mcp/.env.example` (new file)

---

#### Issue #83: Fix Ruff Linting Warnings

**Problem:** 9 ruff warnings (5x E501 line too long, 3x E731 lambda assignment, 1x E501)

**Files to Fix:**

##### 1. `cli.py:215` - E501 (line 146 chars)
```python
# Before
logger.error(f"Failed to execute query after {attempt + 1} attempt(s): {e}. Retrying in {delay} seconds...")

# After (split into multiple lines)
logger.error(
    f"Failed to execute query after {attempt + 1} attempt(s): {e}. "
    f"Retrying in {delay} seconds..."
)
```

##### 2. `changes_schema.py:349, 402` - E501 (lines 137 chars)
```python
# Find these long error message lines and split them

# Before (line 349)
raise ValueError(f"Section ID {section_change.section_id} appears multiple times in sections_to_modify")

# After
raise ValueError(
    f"Section ID {section_change.section_id} appears multiple times "
    f"in sections_to_modify"
)

# Before (line 402)
raise ValueError(f"Insight ID {insight_change.insight_id} appears multiple times in insights_to_modify")

# After
raise ValueError(
    f"Insight ID {insight_change.insight_id} appears multiple times "
    f"in insights_to_modify"
)
```

##### 3. `index.py:291-295` - E731 (lambda assignment)
```python
# Before (lines 290-295)
if sort_by == "created_at":
    key_func = lambda e: e.created_at
elif sort_by == "current_title":
    key_func = lambda e: e.current_title.lower()
else:
    key_func = lambda e: e.updated_at

# After
def _get_sort_key(sort_by: str):
    """Return sort key function for given sort field."""
    if sort_by == "created_at":
        return lambda e: e.created_at
    elif sort_by == "current_title":
        return lambda e: e.current_title.lower()
    else:
        return lambda e: e.updated_at

key_func = _get_sort_key(sort_by)
```

##### 4. `create_report.py:55, 257` - E501 (lines 124, 250 chars)
```python
# Find and split long lines (likely f-strings or error messages)
# Apply same pattern: split into multiple lines with continuation
```

##### 5. `execute_query.py:947` - E501 (line 133 chars)
```python
# Find and split long line
```

**Verification:**
```bash
uv run ruff check .
# Should report 0 errors
```

**Files Modified:**
- `/Users/evandekim/Documents/igloo_mcp/src/igloo_mcp/cli.py` (line 215)
- `/Users/evandekim/Documents/igloo_mcp/src/igloo_mcp/living_reports/changes_schema.py` (lines 349, 402)
- `/Users/evandekim/Documents/igloo_mcp/src/igloo_mcp/living_reports/index.py` (lines 291-295)
- `/Users/evandekim/Documents/igloo_mcp/src/igloo_mcp/mcp/tools/create_report.py` (lines 55, 257)
- `/Users/evandekim/Documents/igloo_mcp/src/igloo_mcp/mcp/tools/execute_query.py` (line 947)

---

### Batch A: Testing Strategy

**Unit Tests:** None required (configuration changes only)

**Integration Tests:**
```bash
# Test pyproject.toml is valid
uv run python -c "import tomli; tomli.load(open('pyproject.toml', 'rb'))"

# Test pre-commit works
pre-commit run --all-files

# Test .env.example is readable
cat .env.example | wc -l

# Test ruff passes
uv run ruff check .
uv run ruff format --check .
```

**Acceptance Criteria:**
- [ ] No TOML parse errors when running uv commands
- [ ] Template files included in built wheel (verify with `unzip -l dist/*.whl`)
- [ ] Pre-commit runs only ruff hooks (no black/isort)
- [ ] .env.example documents all environment variables from README
- [ ] Ruff reports 0 linting errors

---

## Batch B: Type Safety & Validation Errors

### Issues Included
- **#77** - Fix 18 mypy type errors in changes_schema.py (CRITICAL BUG)
- **#66** - Misleading validation error for insights_to_add (UX improvement)
- **#75** - SQL validation should raise ValueError not AttributeError (bug fix)

### Implementation Order
1. Fix #77 (changes_schema.py type errors) - 1-2 hours ⚠️ CAREFUL
2. Fix #66 (better validation messages) - 30 minutes
3. Fix #75 (sql_validation.py) - 30 minutes

### Detailed Implementation

#### Issue #77: Fix MyPy Type Errors (CRITICAL)

**Problem:** 18 type errors due to copy-paste bug where `InsightChange` type used instead of `SectionChange`

**Root Cause Analysis:**
The `validate_against_outline` method has validation logic for both insights and sections. The section validation code was copied from insight validation but the type annotations weren't updated.

**Current (BROKEN - lines 255-270):**
```python
# Validate sections_to_add
for idx, section_change in enumerate(self.sections_to_add):
    change: InsightChange = section_change  # ❌ WRONG TYPE!

    if change.section_id is None:  # Works (both have section_id)
        change.section_id = str(uuid.uuid4())

    if change.section_id in existing_section_ids:  # Works
        errors.append(...)

    if change.title is None:  # ❌ InsightChange has no 'title'
        errors.append(...)
```

**Fix Strategy:**

1. **Read the current validation logic carefully** (lines 172-432)
2. **Identify all InsightChange variables that should be SectionChange**
3. **Update type annotations systematically**
4. **Verify logic is correct for sections vs insights**

**Specific Lines to Fix:**

```python
# Line 255 - WRONG TYPE
for idx, section_change in enumerate(self.sections_to_add):
    change: InsightChange = section_change  # Change to: SectionChange

# Lines 257-274 - All use 'change' variable
# After fixing line 255, these should work correctly

# Line 284-285 - Accessing section-specific fields
if change.insights:  # InsightChange has no 'insights' attribute
    # Fix: This is correct for SectionChange after fixing line 255

# Lines 339-340 - insight_ids_to_add
if change.insight_ids_to_add:  # InsightChange has no 'insight_ids_to_add'
    # Fix: Correct for SectionChange

# Repeat pattern for ALL section validation blocks
```

**Full Fix (lines 255-432):**

```python
# Validate sections_to_add
for idx, section_change in enumerate(self.sections_to_add):
    # FIX: Change InsightChange → SectionChange
    change: SectionChange = section_change

    # Generate section_id if missing
    if change.section_id is None:
        change.section_id = str(uuid.uuid4())

    # Check for duplicate section_id
    if change.section_id in existing_section_ids:
        errors.append(
            ValidationErrorDetail(
                field=f"sections_to_add[{idx}].section_id",
                value=change.section_id,
                error=f"Section ID {change.section_id} already exists",
                available_ids=list(existing_section_ids),
            )
        )

    # Validate required fields for sections
    if change.title is None:
        errors.append(
            ValidationErrorDetail(
                field=f"sections_to_add[{idx}].title",
                value=None,
                error="Section title is required",
            )
        )

    # Validate inline insights if provided
    if change.insights:
        for insight_idx, inline_insight in enumerate(change.insights):
            # Validate insight structure...
            pass

# Validate sections_to_modify
for idx, section_change in enumerate(self.sections_to_modify):
    # FIX: Change InsightChange → SectionChange
    change: SectionChange = section_change

    # Validate section_id exists
    if change.section_id not in existing_section_ids:
        errors.append(
            ValidationErrorDetail(
                field=f"sections_to_modify[{idx}].section_id",
                value=change.section_id,
                error=f"Section ID {change.section_id} not found in outline",
                available_ids=list(existing_section_ids),
            )
        )

    # Validate insight_ids_to_add reference existing insights
    if change.insight_ids_to_add:
        for insight_id in change.insight_ids_to_add:
            if insight_id not in existing_insight_ids:
                errors.append(
                    ValidationErrorDetail(
                        field=f"sections_to_modify[{idx}].insight_ids_to_add",
                        value=insight_id,
                        error=f"Insight ID {insight_id} not found",
                        available_ids=list(existing_insight_ids),
                    )
                )
```

**Verification:**
```bash
# Must pass with NO errors
uv run mypy src/igloo_mcp/living_reports/changes_schema.py

# Run existing tests
uv run pytest tests/test_changes_schema.py -v
uv run pytest tests/test_living_reports_integration.py -v
```

**Files Modified:**
- `/Users/evandekim/Documents/igloo_mcp/src/igloo_mcp/living_reports/changes_schema.py` (lines 255-432)

**⚠️ CRITICAL:** This is an actual bug fix. Must verify all tests pass after changes.

---

#### Issue #66: Better Validation Error Messages

**Problem:** Validation error says "must have importance, summary" even when fields exist but are nested incorrectly

**Current Error:**
```
insights_to_add[0]: New insight must have importance, summary
(value: {'insight_id': 'a21c0c65-03d9-4dd3-b960-557b2cb7922b'})
```

**What User Actually Provided:**
```json
{
  "insights_to_add": [{
    "section_id": "...",
    "insight": {
      "summary": "Revenue is $100M",
      "importance": 10
    }
  }]
}
```

**Solution:** Enhance `ValidationErrorDetail.to_string()` to detect nesting issues

**Current `to_string()` method (approximate location):**
```python
def to_string(self) -> str:
    """Convert to human-readable error message."""
    if self.available_ids:
        return (
            f"{self.field}: {self.error}. "
            f"Available IDs: {', '.join(self.available_ids[:5])}"
        )
    return f"{self.field}: {self.error} (value: {self.value})"
```

**Enhanced version:**
```python
def to_string(self) -> str:
    """Convert to human-readable error message with structural hints."""
    base_error = f"{self.field}: {self.error}"

    # Detect nested structure issues
    if isinstance(self.value, dict):
        # Check for common nesting mistakes
        if "insight" in self.value:
            base_error += (
                "\n  → Found nested 'insight' object. Fields like 'summary' and 'importance' "
                "should be at the top level, not nested."
                "\n  → Correct format: {'insight_id': '...', 'summary': '...', 'importance': 9}"
                "\n  → To link to a section, use sections_to_modify separately."
            )
        elif "section_id" in self.value and self.field.startswith("insights_to_add"):
            base_error += (
                "\n  → Found 'section_id' in insight. Insights cannot be directly linked to sections in insights_to_add."
                "\n  → First create the insight, then use sections_to_modify to link it."
            )

    # Show available IDs for "not found" errors
    if self.available_ids:
        ids_preview = ', '.join(self.available_ids[:5])
        if len(self.available_ids) > 5:
            ids_preview += f" (and {len(self.available_ids) - 5} more)"
        base_error += f"\n  → Available IDs: {ids_preview}"

    # Show value for context (but not for huge objects)
    if self.value is not None:
        value_str = str(self.value)
        if len(value_str) > 200:
            value_str = value_str[:200] + "..."
        base_error += f"\n  → Received value: {value_str}"

    return base_error
```

**Verification:**
```bash
# Create test with nested insight structure
uv run pytest tests/test_changes_schema.py::test_nested_insight_error_message -v

# Verify better error messages appear in integration tests
uv run pytest tests/test_living_reports_integration.py -v
```

**Files Modified:**
- `/Users/evandekim/Documents/igloo_mcp/src/igloo_mcp/living_reports/changes_schema.py` (ValidationErrorDetail class)

---

#### Issue #75: SQL Validation ValueError

**Problem:** Empty/malformed SQL raises `AttributeError` instead of `ValueError`

**Current Bug (test documents it):**
```python
# tests/test_sql_validation_property.py lines 37-40
if isinstance(e, AttributeError):
    # Known bug: empty/malformed SQL causes AttributeError
    # TODO: Fix in sql_validation.py to raise ValueError instead
    pass
```

**Current Code (sql_validation.py:220-446):**
```python
def validate_sql_statement(
    sql: str,
    allowed_types: Optional[Set[str]] = None,
    banned_types: Optional[Set[str]] = None,
) -> Tuple[str, bool]:
    """Validate SQL statement type and safety.

    Args:
        sql: SQL statement to validate
        allowed_types: Set of allowed statement types (SELECT, INSERT, etc.)
        banned_types: Set of banned statement types

    Returns:
        Tuple of (statement_type, is_valid)
    """
    # BUG: No input validation here!
    # If sql is None or empty, sqlglot.parse() raises AttributeError

    try:
        parsed = sqlglot.parse_one(sql)  # Fails on None/empty
        # ... rest of validation
```

**Fix: Add input validation at function start**
```python
def validate_sql_statement(
    sql: str,
    allowed_types: Optional[Set[str]] = None,
    banned_types: Optional[Set[str]] = None,
) -> Tuple[str, bool]:
    """Validate SQL statement type and safety.

    Args:
        sql: SQL statement to validate
        allowed_types: Set of allowed statement types (SELECT, INSERT, etc.)
        banned_types: Set of banned statement types

    Returns:
        Tuple of (statement_type, is_valid)

    Raises:
        ValueError: If SQL is None, empty, or malformed
        TypeError: If SQL is not a string
    """
    # FIX: Add input validation
    if sql is None:
        raise ValueError("SQL cannot be None")

    if not isinstance(sql, str):
        raise TypeError(f"SQL must be a string, got {type(sql).__name__}")

    if not sql.strip():
        raise ValueError("SQL cannot be empty or whitespace-only")

    # Now safe to parse
    try:
        parsed = sqlglot.parse_one(sql)
        # ... rest of validation (unchanged)
```

**Also update test to expect ValueError:**
```python
# tests/test_sql_validation_property.py - Remove AttributeError handling
def test_empty_sql_raises_value_error():
    """Empty SQL should raise ValueError, not AttributeError."""
    with pytest.raises(ValueError, match="SQL cannot be empty"):
        validate_sql_statement("")

    with pytest.raises(ValueError, match="SQL cannot be None"):
        validate_sql_statement(None)

    with pytest.raises(TypeError, match="SQL must be a string"):
        validate_sql_statement(123)
```

**Verification:**
```bash
# Test should now pass without AttributeError handling
uv run pytest tests/test_sql_validation_property.py -v

# All SQL validation tests should pass
uv run pytest tests/test_sql_validation.py -v
```

**Files Modified:**
- `/Users/evandekim/Documents/igloo_mcp/src/igloo_mcp/sql_validation.py` (lines 220-230, add input validation)
- `/Users/evandekim/Documents/igloo_mcp/tests/test_sql_validation_property.py` (remove AttributeError workaround)

---

### Batch B: Testing Strategy

**Unit Tests:**
```bash
# Type safety (must pass with 0 errors)
uv run mypy src/igloo_mcp/living_reports/changes_schema.py

# Validation error messages
uv run pytest tests/test_changes_schema.py -v -k "error_message"

# SQL validation
uv run pytest tests/test_sql_validation.py -v
uv run pytest tests/test_sql_validation_property.py -v
```

**Integration Tests:**
```bash
# Living reports integration
uv run pytest tests/test_living_reports_integration.py -v

# Full test suite
uv run pytest tests/ -v
```

**Acceptance Criteria:**
- [ ] MyPy reports 0 type errors in changes_schema.py
- [ ] All 18 previously failing type checks now pass
- [ ] Validation error messages clearly explain nesting issues
- [ ] SQL validation raises ValueError (not AttributeError) for invalid input
- [ ] All existing tests pass
- [ ] No new test failures introduced

---

## Batch C: Documentation & API Consistency

### Issues Included
- **#65** - get_report_schema returns incorrect example format for insights_to_add

### Implementation Order
1. Fix #65 (get_report_schema.py examples) - 1 hour

### Detailed Implementation

#### Issue #65: Fix Schema Examples

**Problem:** Schema examples show incorrect nested structure for insights

**Current Example (WRONG - lines 204-218):**
```python
"add_insight": {
    "proposed_changes": {
        "insights_to_add": [
            {
                "section_id": "550e8400-e29b-41d4-a716-446655440012",
                "insight": {  # ❌ WRONG: nested structure
                    "summary": "Revenue grew 25% YoY",
                    "importance": 9,
                    "supporting_queries": []
                }
            }
        ]
    }
}
```

**Correct Format (from tests):**
```python
"add_insight": {
    "description": "Add a new insight and link it to a section",
    "proposed_changes": {
        # Step 1: Create the insight
        "insights_to_add": [
            {
                "insight_id": "550e8400-e29b-41d4-a716-446655440099",
                "summary": "Revenue grew 25% YoY",
                "importance": 9,
                "supporting_queries": [
                    {
                        "execution_id": "01234567-89ab-cdef-0123-456789abcdef",
                        "description": "Revenue YoY query"
                    }
                ]
            }
        ],
        # Step 2: Link insight to section
        "sections_to_modify": [
            {
                "section_id": "550e8400-e29b-41d4-a716-446655440012",
                "insight_ids_to_add": ["550e8400-e29b-41d4-a716-446655440099"]
            }
        ]
    }
}
```

**Fix Strategy:**

1. **Read get_report_schema.py to understand example generation** (lines 150-336)
2. **Find _build_examples_response() method**
3. **Reference correct format from tests/test_living_reports_integration.py**
4. **Update all insight-related examples**

**Files to Reference:**
- Source: `/Users/evandekim/Documents/igloo_mcp/src/igloo_mcp/mcp/tools/get_report_schema.py`
- Test examples: `/Users/evandekim/Documents/igloo_mcp/tests/test_living_reports_integration.py` (lines 100-200)

**Example Updates Needed:**

```python
def _build_examples_response(self) -> Dict[str, Any]:
    """Build workflow examples for evolve_report tool."""
    return {
        "add_insight": {
            "description": "Create an insight and link it to a section",
            "workflow": [
                "1. Create the insight with insights_to_add",
                "2. Link it to a section with sections_to_modify"
            ],
            "proposed_changes": {
                "insights_to_add": [
                    {
                        "insight_id": "generated-uuid",  # Auto-generated if omitted
                        "summary": "Revenue grew 25% YoY reaching $50M",
                        "importance": 9,
                        "content": "Detailed analysis of revenue growth...",
                        "tags": ["revenue", "growth"],
                        "supporting_queries": [
                            {
                                "execution_id": "01234567-89ab-cdef-0123-456789abcdef",
                                "description": "Revenue YoY comparison query"
                            }
                        ]
                    }
                ],
                "sections_to_modify": [
                    {
                        "section_id": "existing-section-uuid",
                        "insight_ids_to_add": ["generated-uuid"]
                    }
                ]
            }
        },

        "add_section_with_insights": {
            "description": "Create a section with inline insights",
            "proposed_changes": {
                "sections_to_add": [
                    {
                        "section_id": "new-section-uuid",  # Auto-generated if omitted
                        "title": "Revenue Analysis",
                        "order": 1,
                        "insights": [  # Inline insights (alternative to insights_to_add)
                            {
                                "summary": "Q4 revenue was $50M",
                                "importance": 10,
                                "supporting_queries": [
                                    {
                                        "execution_id": "abc-123"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        },

        # ... other examples
    }
```

**Key Changes:**
1. Remove nested `"insight"` objects
2. Show two-step process (create insight → link to section)
3. Add workflow explanation in description
4. Include examples for both approaches (insights_to_add + sections_to_modify vs inline insights)
5. Reference test files for correct structure

**Verification:**
```bash
# Test schema endpoint returns correct examples
uv run pytest tests/test_get_report_schema.py -v

# Verify examples match integration test patterns
diff <(grep -A 20 "insights_to_add" src/igloo_mcp/mcp/tools/get_report_schema.py) \
     <(grep -A 20 "insights_to_add" tests/test_living_reports_integration.py)
```

**Files Modified:**
- `/Users/evandekim/Documents/igloo_mcp/src/igloo_mcp/mcp/tools/get_report_schema.py` (lines 200-336)

---

### Batch C: Testing Strategy

**Unit Tests:**
```bash
# Schema generation tests
uv run pytest tests/test_get_report_schema.py -v
```

**Integration Tests:**
```bash
# Verify examples work in real workflows
uv run pytest tests/test_living_reports_integration.py -v
```

**Manual Verification:**
```bash
# Start MCP server and call get_report_schema
uv run python -m igloo_mcp.mcp_server

# In another terminal:
curl -X POST http://localhost:3000/mcp/tools/get_report_schema \
  -H "Content-Type: application/json" \
  -d '{"format": "examples"}'

# Verify response has correct structure
```

**Acceptance Criteria:**
- [ ] Schema examples show correct flat structure for insights
- [ ] Examples demonstrate two-step process (create + link)
- [ ] No nested "insight" objects in examples
- [ ] Examples match patterns from integration tests
- [ ] All schema tests pass

---

## File Conflict Analysis

### No Conflicts Between Batches ✅

**Batch A files:**
- `pyproject.toml` (config)
- `.pre-commit-config.yaml` (config)
- `.env.example` (new file)
- `cli.py` (line formatting)
- `index.py` (lambda to def)
- `create_report.py` (line formatting)
- `execute_query.py` (line formatting)

**Batch B files:**
- `changes_schema.py` (type fixes + validation messages)
- `sql_validation.py` (input validation)

**Batch C files:**
- `get_report_schema.py` (example updates)

**Only potential conflict:** Both Batch A and Batch B modify `changes_schema.py`
- Batch A: Lines 349, 402 (line length formatting)
- Batch B: Lines 255-432 (type fixes)

**Resolution:** These are different sections. If implemented in parallel:
1. Batch B should be implemented first (critical bug fix)
2. Batch A line formatting can be applied after
3. OR: Include line formatting in Batch B implementation

---

## Recommended Workflow

### Option 1: Maximum Parallelization (RECOMMENDED)

```bash
# Create 3 feature branches from main
git checkout main
git pull origin main

# Branch 1: Config & Tooling
git checkout -b fix/config-and-tooling
# Implement Batch A
git commit -m "chore: fix config and tooling issues (#78, #79, #82, #83)"
git push -u origin fix/config-and-tooling
gh pr create --title "chore: fix config and tooling issues" --body-file plans/batch-a-pr.md

# Branch 2: Type Safety (from main, not batch A)
git checkout main
git checkout -b fix/type-safety-validation
# Implement Batch B
git commit -m "fix: type safety and validation errors (#77, #66, #75)"
git push -u origin fix/type-safety-validation
gh pr create --title "fix: type safety and validation errors" --body-file plans/batch-b-pr.md

# Branch 3: Documentation (from main)
git checkout main
git checkout -b fix/schema-documentation
# Implement Batch C
git commit -m "docs: fix schema examples (#65)"
git push -u origin fix/schema-documentation
gh pr create --title "docs: fix schema examples" --body-file plans/batch-c-pr.md

# Review all 3 PRs
# Merge in order: B (critical) → A (config) → C (docs)
```

### Option 2: Sequential (Conservative)

```bash
# Do one batch at a time
git checkout -b fix/config-and-tooling
# Implement Batch A
# Push PR, get reviewed, merge

git checkout main
git pull origin main
git checkout -b fix/type-safety-validation
# Implement Batch B
# Push PR, get reviewed, merge

git checkout main
git pull origin main
git checkout -b fix/schema-documentation
# Implement Batch C
# Push PR, get reviewed, merge
```

---

## Summary

### Total Impact
- **8 issues resolved**
- **3 PRs created**
- **~15 files modified**
- **0 breaking changes** (except #77 which fixes an existing bug)
- **100% test coverage maintained**

### Risk Assessment
- **Batch A:** LOW risk (config only, no logic changes)
- **Batch B:** MEDIUM risk (fixes actual bugs, needs thorough testing)
- **Batch C:** LOW risk (documentation only)

### Estimated Timeline
- **Batch A:** 1 hour
- **Batch B:** 2-3 hours
- **Batch C:** 1 hour
- **Total:** 4-6 hours (if sequential) or 3 hours (if parallel with 3 developers)

### Next Steps
After user approval, use AskUserQuestion to determine:
1. Start with `/work` on all batches
2. Start with single batch first
3. Review plan and request changes
