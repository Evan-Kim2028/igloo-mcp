# Igloo MCP Testing Infrastructure

Comprehensive guide to the testing infrastructure for Igloo MCP v0.3.3+.

## Quick Start

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/igloo_mcp --cov-report=html

# Run specific test categories
uv run pytest -m integration
uv run pytest -m living_reports
uv run pytest -m token_efficiency

# Run tests in parallel
uv run pytest -n auto

# Validate schema compatibility
python scripts/validate_schema_compatibility.py
```

## Test Infrastructure Components

### 1. Schema Validation Helpers (`tests/helpers/schema_validators.py`)

Factory functions for creating valid test data with guaranteed schema compliance.

**Usage:**
```python
from tests.helpers.schema_validators import (
    create_valid_insight,
    create_valid_section,
    create_insight_with_citation,
    create_section_with_insights,
)

# Create valid insight
insight = create_valid_insight("Revenue grew 25%", importance=9)

# Create insight with mock citation
insight_with_citation = create_insight_with_citation(
    "Key finding",
    importance=8,
    execution_id="qid-123"
)

# Create section with inline insights
section = create_section_with_insights(
    "Findings",
    order=1,
    insights=[
        ("Finding 1", 8),
        ("Finding 2", 7),
    ]
)
```

### 2. Test Fixtures (`tests/conftest.py`)

Pre-configured fixtures for common testing scenarios.

**Available Fixtures:**
```python
def test_example(
    mock_citation,                  # Mock citation dict
    mock_insight_with_citation,     # Pre-configured insight with citation
    skip_citation_constraints,      # {"skip_citation_validation": True}
    create_test_insight,            # Factory function for insights
    create_test_section,            # Factory function for sections
    report_factory,                 # ReportFactory instance
    report_service,                 # ReportService with temp storage
):
    # Use fixtures...
    insight = create_test_insight("Test", 8, with_citation=True)

    # Or use report factory for complex scenarios
    report_id, insights = report_factory.create_with_insights(5)
```

### 3. Field Name Constants (`src/igloo_mcp/living_reports/schema_constants.py`)

Centralized constants for all schema field names.

**Usage:**
```python
from igloo_mcp.living_reports.schema_constants import (
    ProposedChangesFields,
    SectionChangeFields,
    InsightChangeFields,
    ResponseFields,
)

# Use constants instead of hardcoded strings
changes = {
    ProposedChangesFields.SECTIONS_TO_ADD: [...],
    ProposedChangesFields.INSIGHTS_TO_MODIFY: [...],
}

# Access response fields safely
section_ids = result[ResponseFields.SECTION_IDS_ADDED]
timing = result[ResponseFields.TIMING]
```

### 4. Test Data Factories (`tests/factories/report_factory.py`)

Factory for generating complex test reports.

**Usage:**
```python
from tests.factories.report_factory import ReportFactory, create_report_factory

def test_complex_scenario(tmp_path):
    factory = create_report_factory(tmp_path)

    # Create report with 5 insights
    report_id, insight_ids = factory.create_with_insights(5)

    # Create report with 3 sections
    report_id, section_ids = factory.create_with_sections(3)

    # Create complex report (3 sections, 2 insights each)
    report_id, sections, insights = factory.create_with_sections_and_insights(3, 2)

    # Create large report for performance testing
    report_id, sections, insights = factory.create_large_report(
        section_count=10,
        insight_count=20
    )
```

### 5. Schema Change Detection (`scripts/validate_schema_compatibility.py`)

Automated validation to catch breaking schema changes.

**Usage:**
```bash
# Run manually
python scripts/validate_schema_compatibility.py

# Add to CI
- name: Validate Schema Compatibility
  run: python scripts/validate_schema_compatibility.py
```

## Test Categories (Pytest Markers)

Use markers to run specific test categories:

```bash
# Integration tests (multi-component workflows)
pytest -m integration

# Living reports tests
pytest -m living_reports

# Token efficiency tests
pytest -m token_efficiency

# Regression tests (bug fixes)
pytest -m regression

# Property-based tests (Hypothesis)
pytest -m property_based

# SQL validation tests
pytest -m sql_validation

# Catalog/metadata tests
pytest -m catalog

# Slow tests
pytest -m slow

# Exclude slow tests
pytest -m "not slow"

# Combine markers
pytest -m "living_reports and not slow"
```

**Adding markers to tests:**
```python
import pytest

@pytest.mark.integration
@pytest.mark.living_reports
async def test_workflow(report_factory):
    """Test multi-component workflow."""
    pass

@pytest.mark.property_based
@pytest.mark.sql_validation
def test_edge_cases(sql_input):
    """Property-based test for SQL validation."""
    pass
```

## Coverage Reporting

```bash
# Generate HTML coverage report
uv run pytest --cov=src/igloo_mcp --cov-report=html

# View coverage report
open htmlcov/index.html

# Generate terminal report
uv run pytest --cov=src/igloo_mcp --cov-report=term-missing

# Generate JSON report
uv run pytest --cov=src/igloo_mcp --cov-report=json

# Set minimum coverage threshold
uv run pytest --cov=src/igloo_mcp --cov-fail-under=80
```

## Best Practices

### ✅ DO

```python
# Use schema validators for guaranteed validity
from tests.helpers.schema_validators import create_valid_insight

insight = create_valid_insight("Finding", importance=8)

# Use constants for field names
from igloo_mcp.living_reports.schema_constants import ProposedChangesFields

changes = {ProposedChangesFields.SECTIONS_TO_ADD: [...]}

# Use fixtures for common scenarios
def test_example(skip_citation_constraints, create_test_insight):
    insight = create_test_insight("Test", 8)
    await tool.execute(
        proposed_changes={"insights_to_add": [insight]},
        constraints=skip_citation_constraints
    )

# Use factories for complex data
def test_large_workflow(report_factory):
    report_id, sections, insights = report_factory.create_large_report()
```

### ❌ DON'T

```python
# Don't hardcode schema structure
insight = {
    "summary": "Test",
    "title": "Wrong",  # Invalid field!
    "level": 5,  # Invalid field!
}

# Don't use hardcoded field names
result[" sections_to_update"]  # Typo! Use constants

# Don't use invalid UUIDs
insight = {"insight_id": "not-a-uuid", ...}  # Validation error!

# Don't skip using fixtures
# Bad: Manual setup everywhere
citation = {"execution_id": "qid-123"}
insight = {"summary": "Test", "importance": 8, "citations": [citation]}

# Good: Use fixture
def test_example(mock_insight_with_citation):
    insight = mock_insight_with_citation
```

## Troubleshooting

### Schema Validation Errors

If you get schema validation errors:

1. Use `create_valid_insight()` or `create_valid_section()` helpers
2. Check field names match constants in `schema_constants.py`
3. Ensure UUIDs are valid (or omit for auto-generation)
4. Use `skip_citation_validation` for tests without real queries

### Citation Validation Errors

```python
# Option 1: Use skip_citation_validation
await tool.execute(
    proposed_changes={...},
    constraints={"skip_citation_validation": True}
)

# Option 2: Use create_insight_with_citation()
from tests.helpers.schema_validators import create_insight_with_citation

insight = create_insight_with_citation("Finding", 8)

# Option 3: Use mock_insight_with_citation fixture
def test_example(mock_insight_with_citation):
    await tool.execute(
        proposed_changes={"insights_to_add": [mock_insight_with_citation]}
    )
```

### Breaking Tests After Schema Changes

1. Run schema validation: `python scripts/validate_schema_compatibility.py`
2. Update `schema_constants.py` to match new schema
3. Update tests using the schema validators and constants
4. Re-run tests

## Migration Guide

### Updating Existing Tests

**Before:**
```python
# Old approach - manual dict creation
def test_old_way(report_service):
    changes = {
        "insights_to_add": [{
            "insight_id": "test-1",  # Invalid UUID!
            "summary": "Test",
            "title": "Wrong field",  # Invalid!
            "importance": 8,
        }]
    }
```

**After:**
```python
# New approach - use helpers
def test_new_way(report_service, create_test_insight):
    insight = create_test_insight("Test", 8)
    changes = {
        ProposedChangesFields.INSIGHTS_TO_ADD: [insight]
    }
```

## CI Integration

Add to `.github/workflows/test.yml`:

```yaml
- name: Run Tests with Coverage
  run: |
    uv run pytest --cov=src/igloo_mcp --cov-report=xml --cov-report=term-missing

- name: Validate Schema Compatibility
  run: python scripts/validate_schema_compatibility.py

- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
```

## Additional Resources

- [Testing Report](../TESTING_REPORT_v0.3.3.md) - Comprehensive testing analysis
- [Contributing Guide](../CONTRIBUTING.md) - Contribution guidelines
- [API Documentation](../docs/api/README.md) - API reference
