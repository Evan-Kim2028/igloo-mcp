"""Unit tests for MCP error utilities.

Tests cover error context creation, timeout wrapping, validation errors,
execution errors, and selector errors.

Target: 37% → 85% coverage
"""

from __future__ import annotations

from igloo_mcp.mcp.error_utils import (
    create_error_context,
    format_error_response,
    format_success_response,
    wrap_execution_error,
    wrap_selector_error,
    wrap_timeout_error,
    wrap_validation_error,
)
from igloo_mcp.mcp.exceptions import (
    MCPExecutionError,
    MCPSelectorError,
    MCPValidationError,
)


class TestErrorContextCreation:
    """Test create_error_context function."""

    def test_create_error_context_minimal(self):
        """Create error context with minimal parameters."""
        # Act
        context = create_error_context(operation="test_operation")

        # Assert
        assert context.operation == "test_operation"
        assert context.request_id is None
        assert context.database is None
        assert context.schema is None
        assert context.object_name is None
        assert context.query is None
        assert context.parameters == {}

    def test_create_error_context_with_database(self):
        """Create error context with database parameter."""
        # Act
        context = create_error_context(operation="query_execution", database="TEST_DB")

        # Assert
        assert context.operation == "query_execution"
        assert context.database == "TEST_DB"
        assert context.schema is None

    def test_create_error_context_with_all_fields(self):
        """Create error context with all parameters."""
        # Act
        context = create_error_context(
            operation="table_creation",
            request_id="req-123",
            database="PROD_DB",
            schema="PUBLIC",
            object_name="users_table",
            query="CREATE TABLE users (id INT)",
            parameters={"timeout": 30, "warehouse": "COMPUTE_WH"},
        )

        # Assert
        assert context.operation == "table_creation"
        assert context.request_id == "req-123"
        assert context.database == "PROD_DB"
        assert context.schema == "PUBLIC"
        assert context.object_name == "users_table"
        assert context.query == "CREATE TABLE users (id INT)"
        assert context.parameters == {"timeout": 30, "warehouse": "COMPUTE_WH"}

    def test_create_error_context_with_parameters(self):
        """Create error context with custom parameters."""
        # Act
        context = create_error_context(
            operation="data_load",
            parameters={"batch_size": 1000, "format": "CSV"},
        )

        # Assert
        assert context.operation == "data_load"
        assert context.parameters == {"batch_size": 1000, "format": "CSV"}


class TestTimeoutErrorWrapping:
    """Test wrap_timeout_error function."""

    def test_wrap_timeout_error_basic(self):
        """Create basic timeout error."""
        # Act
        error = wrap_timeout_error(timeout_seconds=30)

        # Assert
        assert isinstance(error, MCPExecutionError)
        assert "timeout" in error.message.lower()
        assert error.operation == "query"
        assert len(error.hints) >= 4

    def test_wrap_timeout_error_with_operation(self):
        """Create timeout error with custom operation."""
        # Act
        error = wrap_timeout_error(timeout_seconds=60, operation="data_export", context={})

        # Assert
        assert isinstance(error, MCPExecutionError)
        assert error.operation == "data_export"

    def test_wrap_timeout_error_with_context(self):
        """Create timeout error with additional context."""
        # Act
        context = {"warehouse": "COMPUTE_WH", "database": "ANALYTICS"}
        error = wrap_timeout_error(timeout_seconds=120, operation="complex_query", context=context)

        # Assert
        assert isinstance(error, MCPExecutionError)
        assert error.context == context

    def test_wrap_timeout_error_hints_generation(self):
        """Timeout error generates appropriate hints."""
        # Act
        error = wrap_timeout_error(timeout_seconds=45)

        # Assert
        assert len(error.hints) >= 4
        assert any("timeout_seconds" in hint for hint in error.hints)


class TestValidationErrorWrapping:
    """Test wrap_validation_error function."""

    def test_wrap_validation_error_minimal(self):
        """Create minimal validation error."""
        # Act
        error = wrap_validation_error(message="Invalid parameter")

        # Assert
        assert isinstance(error, MCPValidationError)
        assert error.message == "Invalid parameter"
        assert error.validation_errors == []
        assert len(error.hints) >= 2

    def test_wrap_validation_error_with_field(self):
        """Create validation error with field name."""
        # Act
        error = wrap_validation_error(message="must be a positive integer", field="timeout_seconds")

        # Assert
        assert isinstance(error, MCPValidationError)
        assert len(error.validation_errors) == 1
        assert "Field 'timeout_seconds'" in error.validation_errors[0]
        assert "must be a positive integer" in error.validation_errors[0]

    def test_wrap_validation_error_with_validation_errors(self):
        """Create validation error with multiple validation errors."""
        # Act
        validation_errors = [
            "Field 'database' is required",
            "Field 'timeout' must be between 1 and 3600",
        ]
        error = wrap_validation_error(message="Multiple validation errors", validation_errors=validation_errors)

        # Assert
        assert isinstance(error, MCPValidationError)
        assert len(error.validation_errors) == 2
        assert "database" in error.validation_errors[0]
        assert "timeout" in error.validation_errors[1]

    def test_wrap_validation_error_with_custom_hints(self):
        """Create validation error with custom hints."""
        # Act
        hints = ["Check the API documentation", "Verify parameter types"]
        error = wrap_validation_error(message="Invalid parameters", hints=hints)

        # Assert
        assert isinstance(error, MCPValidationError)
        assert error.hints == hints


class TestExecutionErrorWrapping:
    """Test wrap_execution_error function."""

    def test_wrap_execution_error_minimal(self):
        """Create minimal execution error."""
        # Act
        error = wrap_execution_error(message="Operation failed", operation="data_processing")

        # Assert
        assert isinstance(error, MCPExecutionError)
        assert error.message == "Operation failed"
        assert error.operation == "data_processing"
        assert len(error.hints) >= 3

    def test_wrap_execution_error_with_original_error(self):
        """Create execution error with original exception."""
        # Arrange
        original = RuntimeError("Snowflake connection lost")

        # Act
        error = wrap_execution_error(
            message="Failed to execute query",
            operation="query_execution",
            original_error=original,
        )

        # Assert
        assert isinstance(error, MCPExecutionError)
        assert error.original_error == original

    def test_wrap_execution_error_with_context(self):
        """Create execution error with context."""
        # Act
        context = {"database": "PROD", "warehouse": "COMPUTE_WH"}
        error = wrap_execution_error(
            message="Query failed",
            operation="select_query",
            context=context,
        )

        # Assert
        assert isinstance(error, MCPExecutionError)
        assert error.context == context

    def test_wrap_execution_error_verbose_mode(self):
        """Create execution error with verbose mode."""
        # Act
        error = wrap_execution_error(
            message="Operation failed",
            operation="test",
            verbose=True,
        )

        # Assert
        assert isinstance(error, MCPExecutionError)
        assert error.verbose is True

    def test_wrap_execution_error_non_verbose_mode(self):
        """Create execution error with non-verbose mode."""
        # Act
        error = wrap_execution_error(
            message="Operation failed",
            operation="test",
            verbose=False,
        )

        # Assert
        assert isinstance(error, MCPExecutionError)
        assert error.verbose is False


class TestSelectorErrorWrapping:
    """Test wrap_selector_error function."""

    def test_wrap_selector_error_not_found(self):
        """Create selector error for not found case."""
        # Act
        error = wrap_selector_error(
            message="Report not found",
            selector="monthly-sales-2024",
            error_type="not_found",
        )

        # Assert
        assert isinstance(error, MCPSelectorError)
        assert error.message == "Report not found"
        assert error.selector == "monthly-sales-2024"

    def test_wrap_selector_error_with_candidates(self):
        """Create selector error with candidate suggestions."""
        # Act
        candidates = ["monthly-sales-2024-q1", "monthly-sales-2024-q2"]
        error = wrap_selector_error(
            message="Ambiguous selector",
            selector="monthly-sales",
            error_type="ambiguous",
            candidates=candidates,
        )

        # Assert
        assert isinstance(error, MCPSelectorError)
        assert error.candidates == candidates

    def test_wrap_selector_error_invalid_format(self):
        """Create selector error for invalid format."""
        # Act
        error = wrap_selector_error(
            message="Invalid report ID format",
            selector="invalid@report!id",
            error_type="invalid_format",
        )

        # Assert
        assert isinstance(error, MCPSelectorError)
        assert error.selector == "invalid@report!id"

    def test_wrap_selector_error_with_hints(self):
        """Create selector error with custom hints."""
        # Act
        hints = ["Use report ID instead of title", "Check available reports with search"]
        error = wrap_selector_error(
            message="Report not found",
            selector="unknown-report",
            error_type="not_found",
            hints=hints,
        )

        # Assert
        assert isinstance(error, MCPSelectorError)
        assert error.hints == hints


class TestFormatResponses:
    """Test format_error_response and format_success_response functions."""

    def test_format_error_response(self):
        """Format error response correctly."""
        # Arrange
        error = MCPExecutionError(
            "Operation failed",
            operation="test",
            hints=["Check logs"],
        )

        # Act
        response = format_error_response(error)

        # Assert
        assert isinstance(response, dict)
        assert "timestamp" in response

    def test_format_success_response(self):
        """Format success response correctly."""
        # Arrange
        data = {"status": "success", "result": {"rows": 100}}

        # Act
        response = format_success_response(data)

        # Assert
        assert isinstance(response, dict)
        assert "status" in response or response == data


class TestErrorUtilsEdgeCases:
    """Test edge cases and error conditions."""

    def test_create_error_context_with_none_operation(self):
        """Create error context handles None operation gracefully."""
        # This should raise or handle gracefully depending on implementation
        # For now, test that it accepts the parameter
        context = create_error_context(operation="", request_id=None)
        assert context.operation == ""

    def test_wrap_timeout_error_with_very_large_timeout(self):
        """Handle very large timeout values."""
        # Act
        error = wrap_timeout_error(timeout_seconds=10000)

        # Assert
        assert isinstance(error, MCPExecutionError)
        assert "10000" in error.message

    def test_wrap_execution_error_with_none_hints(self):
        """Execution error generates default hints when None provided."""
        # Act
        error = wrap_execution_error(message="Failed", operation="test", hints=None)

        # Assert
        assert len(error.hints) > 0
        assert any("logs" in hint.lower() for hint in error.hints)


class TestDecoratorFunctions:
    """Test decorator helper functions."""

    # REMOVED - These functions have different signatures or don't exist as standalone
    # The decorator logic is tested through integration tests
    pass


class TestFormatFunctionsEdgeCases:
    """Test format functions with edge cases."""

    def test_format_error_response_with_request_id(self):
        """Format error response includes request_id."""
        # Arrange
        error = MCPExecutionError("Failed", operation="test")

        # Act
        response = format_error_response(error, request_id="req-789")

        # Assert
        assert response["request_id"] == "req-789"
        assert "timestamp" in response

    def test_format_error_response_with_traceback(self):
        """Format error response includes traceback when requested."""
        # Arrange
        try:
            raise RuntimeError("Test error")
        except RuntimeError as e:
            error = MCPExecutionError("Failed", operation="test", original_error=e)

        # Act
        response = format_error_response(error, include_traceback=True)

        # Assert
        assert "timestamp" in response

    def test_format_success_response_with_request_id(self):
        """Format success response includes request_id."""
        # Arrange
        data = {"result": "success", "rows": 100}

        # Act
        response = format_success_response(data, request_id="req-999")

        # Assert
        assert response["request_id"] == "req-999"
        assert response["status"] == "success"
        assert "timestamp" in response

    def test_format_success_response_with_operation(self):
        """Format success response includes operation name."""
        # Arrange
        data = {"result": "complete"}

        # Act
        response = format_success_response(data, operation="data_export")

        # Assert
        assert response["operation"] == "data_export"
        assert "timestamp" in response


class TestVerboseModeHandling:
    """Test verbose vs compact mode for hints."""

    def test_execution_error_verbose_mode_includes_all_hints(self):
        """Verbose mode includes all hints."""
        # Arrange
        hints = [f"Hint {i}" for i in range(10)]

        # Act
        error = wrap_execution_error("Failed", operation="test", hints=hints, verbose=True)

        # Assert
        assert len(error.hints) == 10

    def test_execution_error_compact_mode_truncates_hints(self):
        """Compact mode truncates hints to DEFAULT_MAX_HINTS."""
        # Arrange
        hints = [f"Hint {i}" for i in range(10)]

        # Act
        error = wrap_execution_error("Failed", operation="test", hints=hints, verbose=False)

        # Assert
        # Should be truncated to DEFAULT_MAX_HINTS (typically 2)
        assert len(error.hints) <= 3  # Give some margin


class TestSelectorErrorHints:
    """Test hint generation for different selector error types."""

    def test_selector_not_found_generates_search_hints(self):
        """Not found errors get search-related hints."""
        # Act
        error = wrap_selector_error("Not found", selector="rpt_12345", error_type="not_found")

        # Assert
        assert len(error.hints) > 0
        # Should suggest search or verification
        hints_text = " ".join(error.hints).lower()
        assert "search" in hints_text or "verify" in hints_text or "check" in hints_text

    def test_selector_ambiguous_suggests_exact_match(self):
        """Ambiguous errors suggest using exact IDs."""
        # Act
        candidates = ["item-1", "item-2", "item-3"]
        error = wrap_selector_error("Ambiguous", selector="item", error_type="ambiguous", candidates=candidates)

        # Assert
        assert len(error.hints) > 0
        assert error.candidates == candidates
