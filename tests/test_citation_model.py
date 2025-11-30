"""Tests for Citation model and migration shim."""

import pytest

from igloo_mcp.living_reports.models import Citation, DatasetSource, Insight


class TestCitationModel:
    """Test Citation model validation."""

    def test_citation_query_type_validation(self):
        """Test query citation with valid fields."""
        citation = Citation(
            source="query",
            provider="snowflake",
            execution_id="exec-123",
            sql_sha256="abc123",
            description="Revenue query",
        )
        assert citation.source == "query"
        assert citation.provider == "snowflake"
        assert citation.execution_id == "exec-123"

    def test_citation_api_type_validation(self):
        """Test API citation with valid fields."""
        citation = Citation(
            source="api",
            provider="defillama",
            endpoint="/tvl/monad",
            description="TVL data",
        )
        assert citation.source == "api"
        assert citation.provider == "defillama"
        assert citation.endpoint == "/tvl/monad"

    def test_citation_url_type_validation(self):
        """Test URL citation with valid fields."""
        citation = Citation(
            source="url",
            url="https://monad.xyz/blog/tge",
            title="TGE Announcement",
            accessed_at="2025-11-30T10:00:00Z",
            description="Official announcement",
        )
        assert citation.source == "url"
        assert citation.url == "https://monad.xyz/blog/tge"
        assert citation.title == "TGE Announcement"

    def test_citation_observation_type_validation(self):
        """Test observation citation with valid fields."""
        citation = Citation(
            source="observation",
            description="Price spike visible on chart",
            observed_at="2025-11-30T10:30:00Z",
        )
        assert citation.source == "observation"
        assert citation.description == "Price spike visible on chart"

    def test_citation_document_type_validation(self):
        """Test document citation with valid fields."""
        citation = Citation(
            source="document",
            path="/docs/whitepaper.pdf",
            page="12",
            title="Monad Whitepaper",
            description="Tokenomics section",
        )
        assert citation.source == "document"
        assert citation.path == "/docs/whitepaper.pdf"
        assert citation.page == "12"

    def test_invalid_source_type_raises_error(self):
        """Test that invalid source type raises validation error."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            Citation(source="invalid_type")

    def test_citation_with_optional_fields(self):
        """Test citation with minimal required fields."""
        citation = Citation(source="observation")
        assert citation.source == "observation"
        assert citation.provider is None
        assert citation.description is None


class TestMigrationShim:
    """Test supporting_queries → citations migration."""

    def test_supporting_queries_auto_converts_to_citations(self):
        """Test that supporting_queries automatically converts to citations."""
        ds = DatasetSource(execution_id="exec-123", sql_sha256="abc")
        insight = Insight(
            insight_id="550e8400-e29b-11d4-a716-446655440000",
            importance=8,
            summary="Test insight",
            supporting_queries=[ds],
        )

        # Should have auto-converted
        assert len(insight.citations) == 1
        assert insight.citations[0].source == "query"
        assert insight.citations[0].provider == "snowflake"
        assert insight.citations[0].execution_id == "exec-123"
        assert insight.citations[0].sql_sha256 == "abc"

    def test_citations_converts_back_to_supporting_queries(self):
        """Test that query citations convert back to supporting_queries."""
        citation = Citation(
            source="query",
            provider="snowflake",
            execution_id="exec-456",
            sql_sha256="def",
        )
        insight = Insight(
            insight_id="550e8400-e29b-11d4-a716-446655440001",
            importance=9,
            summary="Test insight 2",
            citations=[citation],
        )

        # Should have converted back
        assert len(insight.supporting_queries) == 1
        assert insight.supporting_queries[0].execution_id == "exec-456"
        assert insight.supporting_queries[0].sql_sha256 == "def"

    def test_non_query_citations_dont_convert_to_supporting_queries(self):
        """Test that non-query citations don't create supporting_queries."""
        citation = Citation(
            source="url",
            url="https://example.com",
            title="Example",
        )
        insight = Insight(
            insight_id="550e8400-e29b-11d4-a716-446655440002",
            importance=7,
            summary="Test insight 3",
            citations=[citation],
        )

        # URL citation should not convert to supporting_queries
        assert len(insight.supporting_queries) == 0

    def test_both_fields_present_prefers_citations(self):
        """Test that citations takes precedence when both fields provided."""
        ds = DatasetSource(execution_id="old-123")
        citation = Citation(source="query", execution_id="new-456")

        insight = Insight(
            insight_id="550e8400-e29b-11d4-a716-446655440003",
            importance=6,
            summary="Test insight 4",
            supporting_queries=[ds],
            citations=[citation],
        )

        # Citations should be preserved
        assert len(insight.citations) == 1
        assert insight.citations[0].execution_id == "new-456"

    def test_empty_supporting_queries_returns_empty_citations(self):
        """Test that empty supporting_queries results in empty citations."""
        insight = Insight(
            insight_id="550e8400-e29b-11d4-a716-446655440004",
            importance=5,
            summary="Test insight 5",
            supporting_queries=[],
        )

        assert len(insight.citations) == 0
        assert len(insight.supporting_queries) == 0

    def test_mixed_citation_types_in_one_insight(self):
        """Test insight with multiple citation types."""
        citations = [
            Citation(source="query", execution_id="exec-1"),
            Citation(source="url", url="https://example.com"),
            Citation(source="api", provider="defillama", endpoint="/tvl"),
        ]

        insight = Insight(
            insight_id="550e8400-e29b-11d4-a716-446655440005",
            importance=10,
            summary="Multi-source insight",
            citations=citations,
        )

        assert len(insight.citations) == 3
        # Only query citation should convert to supporting_queries
        assert len(insight.supporting_queries) == 1
        assert insight.supporting_queries[0].execution_id == "exec-1"
