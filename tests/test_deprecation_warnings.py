"""Tests for Python deprecation warnings.

Tests that verify proper DeprecationWarning is emitted for deprecated parameters.
"""

import warnings

import pytest

from igloo_mcp.mcp.validation_helpers import validate_response_mode


class TestDeprecationWarnings:
    """Test suite for deprecation warnings."""

    def test_result_mode_emits_deprecation_warning(self):
        """Should emit DeprecationWarning when result_mode parameter is used."""
        with warnings.catch_warnings(record=True) as w:
            # Enable all warnings
            warnings.simplefilter("always")

            # Call function with deprecated parameter
            result = validate_response_mode(
                response_mode=None,
                legacy_param_name="result_mode",
                legacy_param_value="full",
                valid_modes=("full", "summary", "schema_only", "sample"),
                default="summary",
            )

            # Should still work correctly
            assert result == "full"

            # Should emit exactly one warning
            assert len(w) == 1

            # Should be a DeprecationWarning
            assert issubclass(w[0].category, DeprecationWarning)

            # Should have correct message
            assert "result_mode is deprecated" in str(w[0].message)
            assert "use response_mode instead" in str(w[0].message)
            assert "Will be removed in v0.6.0" in str(w[0].message)

    def test_no_warning_when_using_response_mode(self):
        """Should NOT emit warning when using response_mode parameter."""
        with warnings.catch_warnings(record=True) as w:
            # Enable all warnings
            warnings.simplefilter("always")

            # Call function with new parameter
            result = validate_response_mode(
                response_mode="full",
                valid_modes=("full", "summary", "schema_only", "sample"),
                default="summary",
            )

            # Should work correctly
            assert result == "full"

            # Should NOT emit any warnings
            deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0

    def test_response_mode_preferred_over_legacy_no_warning(self):
        """Should NOT emit warning when both provided (response_mode takes precedence)."""
        with warnings.catch_warnings(record=True) as w:
            # Enable all warnings
            warnings.simplefilter("always")

            # Call with both parameters - response_mode should win
            result = validate_response_mode(
                response_mode="minimal",
                legacy_param_name="result_mode",
                legacy_param_value="full",
                valid_modes=("minimal", "full", "summary"),
                default="summary",
            )

            # Should use response_mode value
            assert result == "minimal"

            # Should NOT emit warning since response_mode was provided
            deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0

    @pytest.mark.parametrize(
        ("legacy_param_name", "legacy_param_value"),
        [
            ("result_mode", "full"),
            ("detail_level", "minimal"),
            ("mode", "summary"),
            ("response_detail", "standard"),
        ],
    )
    def test_all_legacy_parameters_emit_warning(self, legacy_param_name, legacy_param_value):
        """Should emit deprecation warning for any legacy parameter name."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            validate_response_mode(
                response_mode=None,
                legacy_param_name=legacy_param_name,
                legacy_param_value=legacy_param_value,
                valid_modes=("minimal", "standard", "full", "summary"),
                default="standard",
            )

            # Should emit exactly one warning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert legacy_param_name in str(w[0].message)
            assert "use response_mode instead" in str(w[0].message)
