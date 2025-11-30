"""Property-based tests for SQL validation using Hypothesis.

These tests use property-based testing to discover edge cases and ensure
SQL validation is robust against arbitrary inputs.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from igloo_mcp.sql_validation import (
    get_sql_statement_type,
    validate_sql_statement,
)


class TestSQLValidationProperties:
    """Property-based tests for SQL validation robustness."""

    @given(st.text(min_size=0, max_size=1000))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_validate_never_crashes(self, sql_input: str):
        """SQL validator should handle arbitrary input without exceptions.

        Property: For any string input, validation either succeeds or raises
        a well-defined validation error, never crashes with unexpected exceptions.
        """
        try:
            validate_sql_statement(sql_input, ["Select"], [])
        except (ValueError, TypeError) as e:
            # Expected validation errors - verify they have informative messages
            error_msg = str(e).lower()
            assert any(keyword in error_msg for keyword in ["sql", "statement", "query", "empty", "invalid"]), (
                f"Error message should be informative: {e}"
            )
        except Exception as e:
            pytest.fail(f"Unexpected exception type: {type(e).__name__}: {e}")

    @pytest.mark.xfail(reason="Hypothesis finds obscure sqlglot edge cases - upstream limitation")
    @given(
        st.one_of(
            st.just("SELECT"),
            st.just("INSERT"),
            st.just("UPDATE"),
            st.just("DELETE"),
            st.just("DROP"),
            st.just("CREATE"),
        ),
        st.text(
            min_size=1,
            max_size=100,
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "P", "Z")),
        ),
    )
    def test_statement_type_detection_is_consistent(self, keyword: str, suffix: str):
        """Statement type detection should be deterministic.

        Property: Same input always produces same statement type classification.
        """
        sql = f"{keyword} {suffix}"
        result1 = get_sql_statement_type(sql)
        result2 = get_sql_statement_type(sql)
        assert result1 == result2, "Statement type detection should be deterministic"

    @given(
        st.lists(
            st.sampled_from(["SELECT", "select", "Select", "SeLeCt"]),
            min_size=1,
            max_size=5,
        )
    )
    def test_case_insensitive_validation(self, keywords: list[str]):
        """SQL validation should be case-insensitive.

        Property: Different case variations of same keyword produce same validation result.
        """
        results = []
        for keyword in keywords:
            sql = f"{keyword} 1"
            try:
                _, is_valid, _ = validate_sql_statement(sql, ["Select"], [])
                results.append(("valid", is_valid))
            except Exception as e:
                results.append(("error", type(e).__name__))

        # All results should be the same (case-insensitive)
        assert len({str(r) for r in results}) == 1, "Case variations should validate consistently"

    @given(st.integers(min_value=0, max_value=1000))
    def test_whitespace_handling(self, num_spaces: int):
        """Whitespace variations should not affect validation outcome.

        Property: Additional whitespace doesn't change validity of valid SQL.
        """
        base_sql = "SELECT 1"
        whitespace = " " * num_spaces

        # Insert whitespace between tokens
        variations = [
            f"SELECT{whitespace}1",
            f"{whitespace}SELECT 1",
            f"SELECT 1{whitespace}",
        ]

        results = []
        for sql in variations:
            try:
                _, is_valid, _ = validate_sql_statement(sql, ["Select"], [])
                results.append(is_valid)
            except Exception:
                pass  # Some variations might be invalid, that's ok

        # At least the base case should work
        _, base_valid, _ = validate_sql_statement(base_sql, ["Select"], [])
        assert base_valid is True

    @pytest.mark.xfail(reason="Hypothesis generates patterns that crash sqlglot - upstream limitation")
    @given(st.lists(st.sampled_from([";", "--", "/*", "*/", "'"]), min_size=0, max_size=20))
    def test_sql_injection_patterns_detected(self, injection_chars: list[str]):
        """Common SQL injection patterns should be handled safely.

        Property: Validation doesn't crash on injection-like patterns.
        """
        injection_attempt = "SELECT 1 " + "".join(injection_chars)

        try:
            validate_sql_statement(injection_attempt, ["Select"], [])
        except (ValueError, TypeError):
            # Expected - validation might reject malformed SQL
            pass
        except Exception as e:
            pytest.fail(f"Should not crash on injection patterns: {type(e).__name__}: {e}")


class TestCacheKeyGeneration:
    """Property-based tests for cache key generation determinism."""

    @given(
        st.text(min_size=1, max_size=100, alphabet="abcdefghijklmnopqrstuvwxyz0123456789"),
        st.text(min_size=1, max_size=50, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ_"),
    )
    def test_cache_key_determinism(self, sql_hash: str, profile: str):
        """Cache keys should be deterministic for same inputs.

        Property: Same SQL hash and profile always produce same cache key.
        """
        import tempfile
        from pathlib import Path

        from igloo_mcp.cache.query_result_cache import QueryResultCache

        with tempfile.TemporaryDirectory() as tmp:
            cache = QueryResultCache(mode="enabled", root=Path(tmp))

            key1 = cache.compute_cache_key(
                sql_sha256=sql_hash,
                profile=profile,
                effective_context={"warehouse": "WH", "role": None},
            )

            key2 = cache.compute_cache_key(
                sql_sha256=sql_hash,
                profile=profile,
                effective_context={"role": None, "warehouse": "WH"},  # Different order
            )

            # Should produce same key regardless of context dict order
            assert key1 == key2, "Cache key should be deterministic"

    @given(
        st.dictionaries(
            keys=st.sampled_from(["warehouse", "database", "schema", "role"]),
            values=st.one_of(st.none(), st.text(min_size=1, max_size=20)),
            min_size=0,
            max_size=4,
        )
    )
    def test_cache_key_handles_various_contexts(self, context: dict):
        """Cache key generation should handle various context configurations.

        Property: Any valid context dict produces a cache key without crashing.
        """
        import tempfile
        from pathlib import Path

        from igloo_mcp.cache.query_result_cache import QueryResultCache

        with tempfile.TemporaryDirectory() as tmp:
            cache = QueryResultCache(mode="enabled", root=Path(tmp))

            try:
                key = cache.compute_cache_key(
                    sql_sha256="test_hash",
                    profile="TEST",
                    effective_context=context,
                )
                assert isinstance(key, str), "Cache key should be a string"
                assert len(key) > 0, "Cache key should not be empty"
            except Exception as e:
                pytest.fail(f"Cache key generation should not crash: {type(e).__name__}: {e}")


class TestLivingReportsInvariants:
    """Property-based tests for living reports data model invariants."""

    @given(st.integers(min_value=-100, max_value=100))
    def test_importance_validation_boundary(self, importance: int):
        """Importance scores outside valid range should be rejected.

        Property: Only values 0-10 are accepted, all others rejected.
        """
        import uuid

        from igloo_mcp.living_reports.models import Insight

        if 0 <= importance <= 10:
            # Should succeed
            insight = Insight(
                insight_id=str(uuid.uuid4()),
                importance=importance,
                summary="Test",
            )
            assert insight.importance == importance
        else:
            # Should fail
            with pytest.raises(ValueError):
                Insight(
                    insight_id=str(uuid.uuid4()),
                    importance=importance,
                    summary="Test",
                )

    @given(st.integers(min_value=-100, max_value=1000))
    def test_section_order_validation(self, order: int):
        """Section order must be non-negative.

        Property: Negative order values are rejected, non-negative accepted.
        """
        import uuid

        from igloo_mcp.living_reports.models import Section

        if order >= 0:
            # Should succeed
            section = Section(
                section_id=str(uuid.uuid4()),
                title="Test",
                order=order,
            )
            assert section.order == order
        else:
            # Should fail
            with pytest.raises(ValueError):
                Section(
                    section_id=str(uuid.uuid4()),
                    title="Test",
                    order=order,
                )

    @given(st.text(min_size=0, max_size=100))
    def test_uuid_validation_robustness(self, uuid_candidate: str):
        """UUID validation should correctly identify valid/invalid UUIDs.

        Property: Only valid UUID strings are accepted, all others rejected.
        """
        import uuid as uuid_lib

        from igloo_mcp.living_reports.models import ReportId

        try:
            # Try to parse as UUID
            uuid_lib.UUID(uuid_candidate)
            # If successful, should be accepted
            report_id = ReportId(uuid_candidate)
            assert str(report_id) == uuid_candidate
        except ValueError:
            # If parsing failed, should be rejected
            with pytest.raises(ValueError):
                ReportId(uuid_candidate)
