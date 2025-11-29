from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--snowflake",
        action="store_true",
        default=False,
        help="Run tests that require live Snowflake access",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requires_snowflake: mark test to require live Snowflake (skipped unless --snowflake)",
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (multi-component workflows)",
    )
    config.addinivalue_line(
        "markers",
        "living_reports: mark test as living reports functionality test",
    )
    config.addinivalue_line(
        "markers",
        "token_efficiency: mark test as token efficiency validation",
    )
    config.addinivalue_line(
        "markers",
        "regression: mark test as regression test for specific bug fix",
    )
    config.addinivalue_line(
        "markers",
        "property_based: mark test as property-based test (Hypothesis)",
    )
    config.addinivalue_line(
        "markers",
        "sql_validation: mark test as SQL validation test",
    )
    config.addinivalue_line(
        "markers",
        "catalog: mark test as catalog/metadata test",
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running (>1s)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--snowflake"):
        return
    skip_marker = pytest.mark.skip(reason="requires --snowflake to run")
    for item in items:
        if "requires_snowflake" in item.keywords:
            item.add_marker(skip_marker)


# =============================================================================
# Shared Fixtures for All Tests
# =============================================================================


@pytest.fixture
def valid_insight():
    """Create a valid Insight object for testing.

    Reduces duplication across living reports tests.
    """
    import uuid

    from igloo_mcp.living_reports.models import Insight

    return Insight(insight_id=str(uuid.uuid4()), importance=8, summary="Test insight summary")


@pytest.fixture
def valid_section():
    """Create a valid Section object for testing.

    Reduces duplication across living reports tests.
    """
    import uuid

    from igloo_mcp.living_reports.models import Section

    return Section(section_id=str(uuid.uuid4()), title="Test Section", order=1)


@pytest.fixture
def report_service(tmp_path):
    """Create a ReportService with temporary storage.

    Provides isolated test environment for living reports tests.
    """
    from igloo_mcp.living_reports.service import ReportService

    reports_root = tmp_path / "reports"
    reports_root.mkdir()
    return ReportService(reports_root=reports_root)


@pytest.fixture
def sql_permissions_default():
    """Default SQL permissions for testing.

    Provides standard allow/disallow lists for SQL validation tests.
    """
    from igloo_mcp.config import SQLPermissions

    perms = SQLPermissions()
    return {"allow_list": perms.get_allow_list(), "disallow_list": perms.get_disallow_list(), "permissions": perms}


@pytest.fixture
def sql_permissions_permissive():
    """Permissive SQL permissions for testing.

    Allows most operations for testing validation logic.
    """
    from igloo_mcp.config import SQLPermissions

    perms = SQLPermissions(select=True, insert=True, update=True, delete=True, show=True, describe=True)
    return {"allow_list": perms.get_allow_list(), "disallow_list": perms.get_disallow_list(), "permissions": perms}


# =============================================================================
# Configuration and Profile Fixtures
# =============================================================================


@pytest.fixture
def mock_config_with_profiles():
    """Mock configuration with specified profiles.

    Reusable across test_config.py, test_user_getting_started.py,
    test_mcp_profile_integration.py.

    Usage:
        with mock_config_with_profiles(["dev", "prod"], default="dev"):
            # Test code
    """
    from pathlib import Path
    from unittest.mock import Mock, patch

    def _mock(profiles: list[str], default: str | None = None):
        config_data: dict[str, dict[str, dict] | str] = {"connections": {profile: {} for profile in profiles}}
        if default:
            config_data["default_connection_name"] = default

        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.stat.return_value = Mock(st_mtime=123.0)

        return patch.multiple(
            "igloo_mcp.profile_utils",
            get_snowflake_config_path=Mock(return_value=mock_path),
            _load_snowflake_config=Mock(return_value=config_data),
        )

    return _mock


@pytest.fixture
def mock_empty_config():
    """Mock empty configuration (no profiles).

    Reusable across multiple test files.
    """
    from pathlib import Path
    from unittest.mock import Mock, patch

    def _mock():
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.stat.return_value = Mock(st_mtime=123.0)

        return patch.multiple(
            "igloo_mcp.profile_utils",
            get_snowflake_config_path=Mock(return_value=mock_path),
            _load_snowflake_config=Mock(return_value={"connections": {}}),
        )

    return _mock


@pytest.fixture
def base_config():
    """Provide a minimal Config for tool instantiation.

    Used in test_tool_schemas.py and other tool tests.
    """
    from igloo_mcp.config import Config, SnowflakeConfig

    return Config(snowflake=SnowflakeConfig(profile="TEST_PROFILE"))


# =============================================================================
# Living Reports Fixtures
# =============================================================================


@pytest.fixture
def temp_reports_dir(tmp_path):
    """Create temporary reports directory.

    Used by multiple living reports tests.
    """
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


@pytest.fixture
def report_service_with_report(report_service):
    """Create ReportService with a pre-created test report.

    Returns (service, report_id) tuple.
    """
    outline = report_service.create_report(title="Test Report", template="default")
    return report_service, outline.report_id


@pytest.fixture
def report_factory(tmp_path):
    """Create a ReportFactory for generating complex test data.

    Provides factory methods for creating reports with sections, insights,
    and various configurations without boilerplate setup code.

    Usage:
        report_id, insights = report_factory.create_with_insights(5)
        report_id, sections, insights = report_factory.create_large_report()
    """
    from tests.factories.report_factory import create_report_factory

    return create_report_factory(tmp_path)


@pytest.fixture
def mock_citation():
    """Create a mock citation for test insights.

    Provides a valid citation structure for tests that need citations
    but don't execute real queries.

    Usage:
        insight = {
            "summary": "Finding",
            "importance": 8,
            "citations": [mock_citation]
        }
    """
    from tests.helpers.schema_validators import create_mock_citation

    return create_mock_citation("mock-qid-test-123")


@pytest.fixture
def mock_insight_with_citation():
    """Create a valid insight with mock citation.

    Pre-configured insight that passes citation validation for tests
    without real query execution.

    Usage:
        await tool.execute(
            proposed_changes={"insights_to_add": [mock_insight_with_citation]}
        )
    """
    from tests.helpers.schema_validators import create_insight_with_citation

    return create_insight_with_citation("Test insight with citation", importance=8, execution_id="mock-test-qid")


@pytest.fixture
def skip_citation_constraints():
    """Constraints dict for skipping citation validation in tests.

    Use when testing insights without real query execution.

    Usage:
        await tool.execute(
            proposed_changes={...},
            constraints=skip_citation_constraints
        )
    """
    return {"skip_citation_validation": True}


@pytest.fixture
def create_test_insight():
    """Factory fixture for creating valid test insights.

    Returns a function that creates insights with guaranteed valid schema.

    Usage:
        insight = create_test_insight("Revenue up 25%", importance=9)
        insight_with_citation = create_test_insight(
            "Key finding",
            importance=8,
            with_citation=True
        )
    """
    from tests.helpers.schema_validators import (
        create_insight_with_citation,
        create_valid_insight,
    )

    def _create(summary: str, importance: int, with_citation: bool = False, **kwargs):
        if with_citation:
            return create_insight_with_citation(summary, importance, **kwargs)
        return create_valid_insight(summary, importance, **kwargs)

    return _create


@pytest.fixture
def create_test_section():
    """Factory fixture for creating valid test sections.

    Returns a function that creates sections with guaranteed valid schema.

    Usage:
        section = create_test_section("Revenue", order=1)
        section_with_insights = create_test_section(
            "Findings",
            order=2,
            with_insights=[("Finding 1", 8), ("Finding 2", 7)]
        )
    """
    from tests.helpers.schema_validators import (
        create_section_with_insights,
        create_valid_section,
    )

    def _create(title: str, order: int, with_insights=None, **kwargs):
        if with_insights:
            return create_section_with_insights(title, order, with_insights, **kwargs)
        return create_valid_section(title, order, **kwargs)

    return _create


# =============================================================================
# Snowflake Service Mocking Fixtures
# =============================================================================


@pytest.fixture
def fake_snowflake_service():
    """Factory fixture for creating FakeSnowflakeService instances.

    Usage:
        service = fake_snowflake_service(
            plans=[FakeQueryPlan(statement=..., rows=...)]
        )
    """
    from tests.helpers.fake_snowflake_connector import (
        FakeSessionDefaults,
        FakeSnowflakeService,
    )

    def _create_service(plans, session_defaults=None):
        defaults = session_defaults or FakeSessionDefaults()
        return FakeSnowflakeService(plans=plans, session_defaults=defaults)

    return _create_service
