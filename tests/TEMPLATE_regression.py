"""Regression test template.

When fixing a bug:
1. Copy this template
2. Rename file: test_regression_issue_<NUM>_<description>.py
3. Add marker: @pytest.mark.regression(issue_id="<NUM>")
4. Document bug in docstring
5. Write test that reproduces bug + verifies fix
"""

import pytest

# Template - copy this and replace placeholders:
# @pytest.mark.regression(issue_id="<ISSUE_NUMBER>")
# def test_regression_issue_<NUM>_<description>():
#     """Regression test for Issue #<NUM>.
#
#     Bug: <What broke - be specific>
#
#     Root Cause: <Why it broke - technical explanation>
#
#     Fix: <How it was fixed - code changes made>
#
#     This test ensures the bug doesn't reoccur.
#     """
#     # GIVEN: Setup that triggers the bug
#     # WHEN: Execute the action that previously caused the bug
#     # THEN: Assert that the bug is fixed
#     assert True


# Example regression test structure:
@pytest.mark.regression(issue_id="999")
def test_regression_issue_999_sql_injection_in_query_validation():
    """Regression test for Issue #999 - SQL injection vulnerability.

    Bug: execute_query accepted unsanitized user input allowing SQL injection

    Root Cause: Missing parameter validation in sql_validation.py validate_sql()

    Fix: Added parameterized query validation and input sanitization

    This test ensures SQL injection is prevented.
    """

    # GIVEN: Malicious SQL with injection attempt
    # malicious_sql = "SELECT * FROM users WHERE id = '1' OR '1'='1'"  # Example only

    # WHEN: Attempting to execute malicious SQL
    # (In the actual test, you would call the vulnerable function)

    # THEN: Validation should reject the SQL
    # (Example - adjust to match your actual validation logic)
    # with pytest.raises(ValueError, match="SQL injection detected"):
    #     validate_sql(malicious_sql)

    # For template purposes
    assert True


# Another example for different bug types:
@pytest.mark.regression(issue_id="1000")
async def test_regression_issue_1000_race_condition_in_cache():
    """Regression test for Issue #1000 - Race condition in query cache.

    Bug: Concurrent cache writes caused data corruption

    Root Cause: No locking mechanism in QueryResultCache.set()

    Fix: Added file locking using FileLock in cache operations

    This test verifies thread-safe cache operations.
    """
    from igloo_mcp.cache import QueryResultCache

    # GIVEN: Cache instance and multiple concurrent operations
    cache = QueryResultCache.from_env()

    # WHEN: Multiple threads write to cache simultaneously
    # (Example concurrent operations)
    async def write_to_cache(key: str, value: str) -> None:
        cache.set(key, {}, {"rows": [value]})

    # THEN: All writes should succeed without corruption
    # (In actual test, verify no data corruption occurs)
    # await asyncio.gather(*[write_to_cache(f"key_{i}", f"value_{i}") for i in range(10)])

    # For template purposes
    assert True
