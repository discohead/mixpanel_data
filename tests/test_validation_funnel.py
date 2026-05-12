"""Unit tests for funnel argument validation rules (F1-F6).

Tests ``validate_funnel_args()`` which validates Python-level arguments
before funnel bookmark construction. Each rule class covers one validation
rule, plus a multi-error collection class to verify all errors are returned
in a single pass.

Validation rules:
    F1: At least 2 steps required.
    F2: Each step event must be a non-empty string.
    F3: Positive conversion window.
    F4: Non-empty exclusion event names.
    F5: Time validation (delegated to ``validate_time_args``).
    F6: Group-by validation (delegated to ``validate_group_by_args``).
"""

from __future__ import annotations

from typing import Any

import pytest

from mixpanel_headless._internal.validation import validate_funnel_args
from mixpanel_headless.exceptions import ValidationError
from mixpanel_headless.types import Exclusion, FunnelStep, GroupBy

# =============================================================================
# Helper
# =============================================================================


def _valid_funnel_args(**overrides: Any) -> dict[str, Any]:
    """Build a default-valid kwargs dict for ``validate_funnel_args``.

    All defaults pass validation. Override individual keys to inject
    specific invalid values for targeted testing.

    Args:
        **overrides: Keyword arguments to override in the defaults.

    Returns:
        Dict suitable for unpacking into ``validate_funnel_args(**d)``.
    """
    defaults: dict[str, Any] = {
        "steps": ["Signup", "Purchase"],
        "conversion_window": 14,
        "conversion_window_unit": "day",
        "math": "conversion_rate_unique",
        "math_property": None,
        "exclusions": None,
        "holding_constant": None,
        "from_date": None,
        "to_date": None,
        "last": 30,
        "group_by": None,
    }
    defaults.update(overrides)
    return defaults


def _codes(errors: list[ValidationError]) -> list[str]:
    """Extract error codes from a list of ValidationError objects.

    Args:
        errors: List of validation errors.

    Returns:
        List of error code strings.
    """
    return [e.code for e in errors]


# =============================================================================
# F1: At least 2 steps required
# =============================================================================


class TestValidateFunnelArgsF1:
    """Tests for F1: minimum step count validation."""

    def test_empty_steps_returns_f1_error(self) -> None:
        """An empty steps list must produce an F1_MIN_STEPS error."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=[]))
        assert any(e.code == "F1_MIN_STEPS" for e in errors)

    def test_single_step_returns_f1_error(self) -> None:
        """A single step must produce an F1_MIN_STEPS error."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=["A"]))
        assert any(e.code == "F1_MIN_STEPS" for e in errors)

    def test_single_funnel_step_object_returns_f1_error(self) -> None:
        """A single FunnelStep object must produce an F1_MIN_STEPS error."""
        errors = validate_funnel_args(
            **_valid_funnel_args(steps=[FunnelStep("Signup")])
        )
        assert any(e.code == "F1_MIN_STEPS" for e in errors)

    def test_two_steps_no_f1_error(self) -> None:
        """Two steps must not produce an F1_MIN_STEPS error."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=["A", "B"]))
        assert "F1_MIN_STEPS" not in _codes(errors)

    def test_three_steps_no_f1_error(self) -> None:
        """Three or more steps must not produce an F1_MIN_STEPS error."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=["A", "B", "C"]))
        assert "F1_MIN_STEPS" not in _codes(errors)

    def test_f1_error_message_contains_count(self) -> None:
        """The F1 error message must indicate the actual step count."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=["A"]))
        f1_errors = [e for e in errors if e.code == "F1_MIN_STEPS"]
        assert len(f1_errors) == 1
        assert "1" in f1_errors[0].message

    def test_f1_error_path_is_steps(self) -> None:
        """The F1 error path must point to 'steps'."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=[]))
        f1_errors = [e for e in errors if e.code == "F1_MIN_STEPS"]
        assert len(f1_errors) == 1
        assert f1_errors[0].path == "steps"


# =============================================================================
# F2: Each step event must be non-empty string
# =============================================================================


class TestValidateFunnelArgsF2:
    """Tests for F2: non-empty step event names."""

    def test_empty_string_step_returns_f2_error(self) -> None:
        """An empty string step must produce an F2_EMPTY_STEP_EVENT error."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=["Signup", ""]))
        assert any(e.code == "F2_EMPTY_STEP_EVENT" for e in errors)

    def test_empty_string_funnel_step_raises_at_construction(self) -> None:
        """A FunnelStep with an empty event must raise ValueError at construction."""

        with pytest.raises(
            ValueError, match="FunnelStep.event must be a non-empty string"
        ):
            FunnelStep("")

    def test_whitespace_only_step_returns_f2_error(self) -> None:
        """A whitespace-only step must produce an F2_EMPTY_STEP_EVENT error."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=["  ", "Purchase"]))
        assert any(e.code == "F2_EMPTY_STEP_EVENT" for e in errors)

    def test_whitespace_only_funnel_step_raises_at_construction(self) -> None:
        """A FunnelStep with whitespace-only event raises ValueError."""

        with pytest.raises(
            ValueError, match="FunnelStep.event must be a non-empty string"
        ):
            FunnelStep("  \t  ")

    def test_f2_error_path_contains_index(self) -> None:
        """The F2 error path must reference the step index."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=["Signup", ""]))
        f2_errors = [e for e in errors if e.code == "F2_EMPTY_STEP_EVENT"]
        assert len(f2_errors) == 1
        assert f2_errors[0].path == "steps[1]"

    def test_f2_error_for_first_step(self) -> None:
        """The F2 error path must be steps[0] when the first step is empty."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=["", "Purchase"]))
        f2_errors = [e for e in errors if e.code == "F2_EMPTY_STEP_EVENT"]
        assert len(f2_errors) == 1
        assert f2_errors[0].path == "steps[0]"

    def test_multiple_empty_steps_produce_multiple_f2_errors(self) -> None:
        """Each empty step must produce its own F2 error."""
        errors = validate_funnel_args(
            **_valid_funnel_args(steps=["", "  ", "Purchase"])
        )
        f2_errors = [e for e in errors if e.code == "F2_EMPTY_STEP_EVENT"]
        assert len(f2_errors) == 2
        paths = {e.path for e in f2_errors}
        assert paths == {"steps[0]", "steps[1]"}

    def test_valid_steps_no_f2_error(self) -> None:
        """Valid non-empty step names must not produce F2 errors."""
        errors = validate_funnel_args(
            **_valid_funnel_args(steps=["Signup", "Purchase"])
        )
        assert "F2_EMPTY_STEP_EVENT" not in _codes(errors)

    def test_valid_funnel_step_objects_no_f2_error(self) -> None:
        """Valid FunnelStep objects must not produce F2 errors."""
        errors = validate_funnel_args(
            **_valid_funnel_args(steps=[FunnelStep("Signup"), FunnelStep("Purchase")])
        )
        assert "F2_EMPTY_STEP_EVENT" not in _codes(errors)

    def test_mixed_string_and_funnel_step_valid(self) -> None:
        """A mix of valid strings and FunnelStep objects must pass F2."""
        errors = validate_funnel_args(
            **_valid_funnel_args(steps=["Signup", FunnelStep("Purchase")])
        )
        assert "F2_EMPTY_STEP_EVENT" not in _codes(errors)


# =============================================================================
# F3: Positive conversion window
# =============================================================================


class TestValidateFunnelArgsF3:
    """Tests for F3: positive conversion window."""

    def test_zero_conversion_window_returns_f3_error(self) -> None:
        """A zero conversion window must produce an F3 error."""
        errors = validate_funnel_args(**_valid_funnel_args(conversion_window=0))
        assert any(e.code == "F3_CONVERSION_WINDOW_POSITIVE" for e in errors)

    def test_negative_conversion_window_returns_f3_error(self) -> None:
        """A negative conversion window must produce an F3 error."""
        errors = validate_funnel_args(**_valid_funnel_args(conversion_window=-1))
        assert any(e.code == "F3_CONVERSION_WINDOW_POSITIVE" for e in errors)

    def test_large_negative_conversion_window_returns_f3_error(self) -> None:
        """A large negative conversion window must produce an F3 error."""
        errors = validate_funnel_args(**_valid_funnel_args(conversion_window=-100))
        assert any(e.code == "F3_CONVERSION_WINDOW_POSITIVE" for e in errors)

    def test_positive_conversion_window_no_f3_error(self) -> None:
        """A positive conversion window must not produce an F3 error."""
        errors = validate_funnel_args(**_valid_funnel_args(conversion_window=14))
        assert "F3_CONVERSION_WINDOW_POSITIVE" not in _codes(errors)

    def test_conversion_window_one_no_f3_error(self) -> None:
        """A conversion window of 1 (minimum positive) must pass F3."""
        errors = validate_funnel_args(**_valid_funnel_args(conversion_window=1))
        assert "F3_CONVERSION_WINDOW_POSITIVE" not in _codes(errors)

    def test_f3_error_path_is_conversion_window(self) -> None:
        """The F3 error path must point to 'conversion_window'."""
        errors = validate_funnel_args(**_valid_funnel_args(conversion_window=0))
        f3_errors = [e for e in errors if e.code == "F3_CONVERSION_WINDOW_POSITIVE"]
        assert len(f3_errors) == 1
        assert f3_errors[0].path == "conversion_window"

    def test_f3_error_message_mentions_positive(self) -> None:
        """The F3 error message must mention 'positive'."""
        errors = validate_funnel_args(**_valid_funnel_args(conversion_window=-5))
        f3_errors = [e for e in errors if e.code == "F3_CONVERSION_WINDOW_POSITIVE"]
        assert len(f3_errors) == 1
        assert "positive" in f3_errors[0].message.lower()


# =============================================================================
# F4: Non-empty exclusion event names
# =============================================================================


class TestValidateFunnelArgsF4:
    """Tests for F4: non-empty exclusion event names."""

    def test_empty_exclusion_event_raises_at_construction(self) -> None:
        """An Exclusion with an empty event must raise ValueError at construction."""

        with pytest.raises(
            ValueError, match="Exclusion.event must be a non-empty string"
        ):
            Exclusion("")

    def test_whitespace_exclusion_event_raises_at_construction(self) -> None:
        """An Exclusion with a whitespace-only event raises ValueError."""

        with pytest.raises(
            ValueError, match="Exclusion.event must be a non-empty string"
        ):
            Exclusion("   ")

    def test_valid_exclusion_no_f4_error(self) -> None:
        """A valid Exclusion event name must not produce an F4 error."""
        errors = validate_funnel_args(
            **_valid_funnel_args(exclusions=[Exclusion("Logout")])
        )
        assert "F4_EMPTY_EXCLUSION_EVENT" not in _codes(errors)

    def test_none_exclusions_no_f4_error(self) -> None:
        """None exclusions must not produce an F4 error."""
        errors = validate_funnel_args(**_valid_funnel_args(exclusions=None))
        assert "F4_EMPTY_EXCLUSION_EVENT" not in _codes(errors)

    def test_empty_list_exclusions_no_f4_error(self) -> None:
        """An empty exclusions list must not produce an F4 error."""
        errors = validate_funnel_args(**_valid_funnel_args(exclusions=[]))
        assert "F4_EMPTY_EXCLUSION_EVENT" not in _codes(errors)

    def test_multiple_empty_exclusions_produce_multiple_construction_errors(
        self,
    ) -> None:
        """Empty and whitespace-only exclusions both raise at construction."""

        # Empty string is caught by __post_init__
        with pytest.raises(
            ValueError, match="Exclusion.event must be a non-empty string"
        ):
            Exclusion("")

        # Whitespace-only also caught by __post_init__
        with pytest.raises(
            ValueError, match="Exclusion.event must be a non-empty string"
        ):
            Exclusion("  ")

        # Valid exclusion constructs fine and produces no F4 errors
        errors = validate_funnel_args(
            **_valid_funnel_args(exclusions=[Exclusion("Valid")])
        )
        f4_errors = [e for e in errors if e.code == "F4_EMPTY_EXCLUSION_EVENT"]
        assert len(f4_errors) == 0

    def test_f4_error_path_contains_index(self) -> None:
        """Empty exclusion event raises ValueError at construction."""

        # Exclusion("") now raises at construction before reaching validation
        with pytest.raises(
            ValueError, match="Exclusion.event must be a non-empty string"
        ):
            Exclusion("")

    def test_f4_error_path_for_first_exclusion(self) -> None:
        """Empty exclusion event raises ValueError at construction."""

        with pytest.raises(
            ValueError, match="Exclusion.event must be a non-empty string"
        ):
            Exclusion("")

    def test_exclusion_with_step_range_valid(self) -> None:
        """An Exclusion with from_step/to_step and valid event must pass."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                exclusions=[Exclusion("Logout", from_step=0, to_step=1)]
            )
        )
        assert "F4_EMPTY_EXCLUSION_EVENT" not in _codes(errors)


# =============================================================================
# F5: Time validation (delegated to validate_time_args)
# =============================================================================


class TestValidateFunnelArgsF5:
    """Tests for F5: time validation delegated to validate_time_args."""

    def test_invalid_from_date_format_returns_v8_error(self) -> None:
        """An invalid from_date format must produce a V8_DATE_FORMAT error."""
        errors = validate_funnel_args(**_valid_funnel_args(from_date="invalid"))
        assert any(e.code == "V8_DATE_FORMAT" for e in errors)

    def test_invalid_to_date_format_returns_v8_error(self) -> None:
        """An invalid to_date format must produce a V8_DATE_FORMAT error."""
        errors = validate_funnel_args(
            **_valid_funnel_args(from_date="2024-01-01", to_date="not-a-date")
        )
        assert any(e.code == "V8_DATE_FORMAT" for e in errors)

    def test_valid_date_range_no_time_errors(self) -> None:
        """Valid from_date and to_date must not produce time errors."""
        errors = validate_funnel_args(
            **_valid_funnel_args(from_date="2024-01-01", to_date="2024-01-31", last=30)
        )
        time_codes = {"V7_LAST_POSITIVE", "V8_DATE_FORMAT", "V8_DATE_INVALID"}
        assert not any(e.code in time_codes for e in errors)

    def test_to_date_without_from_date_returns_v9_error(self) -> None:
        """Setting to_date without from_date must produce a V9 error."""
        errors = validate_funnel_args(**_valid_funnel_args(to_date="2024-01-31"))
        assert any(e.code == "V9_TO_REQUIRES_FROM" for e in errors)

    def test_negative_last_returns_v7_error(self) -> None:
        """A negative last value must produce a V7_LAST_POSITIVE error."""
        errors = validate_funnel_args(**_valid_funnel_args(last=-1))
        assert any(e.code == "V7_LAST_POSITIVE" for e in errors)

    def test_zero_last_returns_v7_error(self) -> None:
        """A zero last value must produce a V7_LAST_POSITIVE error."""
        errors = validate_funnel_args(**_valid_funnel_args(last=0))
        assert any(e.code == "V7_LAST_POSITIVE" for e in errors)

    def test_no_dates_with_default_last_no_time_errors(self) -> None:
        """Default arguments (no dates, last=30) must not produce time errors."""
        errors = validate_funnel_args(**_valid_funnel_args())
        time_codes = {
            "V7_LAST_POSITIVE",
            "V8_DATE_FORMAT",
            "V8_DATE_INVALID",
            "V9_TO_REQUIRES_FROM",
            "V10_DATE_LAST_EXCLUSIVE",
            "V15_DATE_ORDER",
            "V20_LAST_TOO_LARGE",
        }
        assert not any(e.code in time_codes for e in errors)

    def test_from_date_after_to_date_returns_v15_error(self) -> None:
        """from_date after to_date must produce a V15_DATE_ORDER error."""
        errors = validate_funnel_args(
            **_valid_funnel_args(from_date="2024-02-01", to_date="2024-01-01", last=30)
        )
        assert any(e.code == "V15_DATE_ORDER" for e in errors)

    def test_invalid_calendar_date_returns_v8_invalid(self) -> None:
        """A non-existent calendar date must produce a V8_DATE_INVALID error."""
        errors = validate_funnel_args(**_valid_funnel_args(from_date="2024-02-30"))
        assert any(e.code == "V8_DATE_INVALID" for e in errors)


# =============================================================================
# F6: Group-by validation (delegated to validate_group_by_args)
# =============================================================================


class TestValidateFunnelArgsF6:
    """Tests for F6: group-by validation delegated to validate_group_by_args."""

    def test_negative_bucket_size_raises_at_construction(self) -> None:
        """A negative bucket_size must raise ValueError at construction."""

        with pytest.raises(ValueError, match="GroupBy.bucket_size must be positive"):
            GroupBy(
                "revenue",
                property_type="number",
                bucket_size=-1,
                bucket_min=0,
                bucket_max=100,
            )

    def test_zero_bucket_size_raises_at_construction(self) -> None:
        """A zero bucket_size must raise ValueError at construction."""

        with pytest.raises(ValueError, match="GroupBy.bucket_size must be positive"):
            GroupBy(
                "revenue",
                property_type="number",
                bucket_size=0,
                bucket_min=0,
                bucket_max=100,
            )

    def test_string_group_by_no_errors(self) -> None:
        """A simple string group_by must not produce group-by errors."""
        errors = validate_funnel_args(**_valid_funnel_args(group_by="platform"))
        group_codes = {
            "V11_BUCKET_REQUIRES_SIZE",
            "V12_BUCKET_SIZE_POSITIVE",
            "V12B_BUCKET_REQUIRES_NUMBER",
            "V12C_BUCKET_REQUIRES_BOUNDS",
            "V18_BUCKET_ORDER",
            "V24_BUCKET_NOT_FINITE",
        }
        assert not any(e.code in group_codes for e in errors)

    def test_none_group_by_no_errors(self) -> None:
        """None group_by must not produce group-by errors."""
        errors = validate_funnel_args(**_valid_funnel_args(group_by=None))
        group_codes = {
            "V11_BUCKET_REQUIRES_SIZE",
            "V12_BUCKET_SIZE_POSITIVE",
            "V12B_BUCKET_REQUIRES_NUMBER",
            "V12C_BUCKET_REQUIRES_BOUNDS",
            "V18_BUCKET_ORDER",
            "V24_BUCKET_NOT_FINITE",
        }
        assert not any(e.code in group_codes for e in errors)

    def test_valid_numeric_group_by_no_errors(self) -> None:
        """A valid numeric GroupBy with bucket config must not produce errors."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                group_by=GroupBy(
                    "revenue",
                    property_type="number",
                    bucket_size=50,
                    bucket_min=0,
                    bucket_max=500,
                )
            )
        )
        group_codes = {
            "V11_BUCKET_REQUIRES_SIZE",
            "V12_BUCKET_SIZE_POSITIVE",
            "V12B_BUCKET_REQUIRES_NUMBER",
            "V12C_BUCKET_REQUIRES_BOUNDS",
            "V18_BUCKET_ORDER",
            "V24_BUCKET_NOT_FINITE",
        }
        assert not any(e.code in group_codes for e in errors)

    def test_bucket_min_exceeds_max_raises_at_construction(self) -> None:
        """bucket_min >= bucket_max must raise ValueError at construction."""

        with pytest.raises(ValueError, match="GroupBy.bucket_min.*must be less than"):
            GroupBy(
                "revenue",
                property_type="number",
                bucket_size=10,
                bucket_min=100,
                bucket_max=50,
            )

    def test_bucket_without_number_type_returns_v12b_error(self) -> None:
        """bucket_size on a non-number property must produce a V12B error."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                group_by=GroupBy(
                    "country",
                    property_type="string",
                    bucket_size=10,
                    bucket_min=0,
                    bucket_max=100,
                )
            )
        )
        assert any(e.code == "V12B_BUCKET_REQUIRES_NUMBER" for e in errors)

    def test_list_group_by_valid(self) -> None:
        """A list of valid group-by specs must not produce errors."""
        errors = validate_funnel_args(
            **_valid_funnel_args(group_by=["platform", "country"])
        )
        group_codes = {
            "V11_BUCKET_REQUIRES_SIZE",
            "V12_BUCKET_SIZE_POSITIVE",
            "V12B_BUCKET_REQUIRES_NUMBER",
            "V12C_BUCKET_REQUIRES_BOUNDS",
            "V18_BUCKET_ORDER",
            "V24_BUCKET_NOT_FINITE",
        }
        assert not any(e.code in group_codes for e in errors)

    def test_nan_bucket_size_returns_v24_error(self) -> None:
        """A NaN bucket_size must produce a V24_BUCKET_NOT_FINITE error."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                group_by=GroupBy(
                    "revenue",
                    property_type="number",
                    bucket_size=float("nan"),
                    bucket_min=0,
                    bucket_max=100,
                )
            )
        )
        assert any(e.code == "V24_BUCKET_NOT_FINITE" for e in errors)


# =============================================================================
# Multiple errors collected
# =============================================================================


class TestValidateFunnelArgsMultipleErrors:
    """Tests for multiple errors collected together.

    Verifies that ``validate_funnel_args`` returns ALL errors in a single
    pass, not just the first one encountered.
    """

    def test_f1_and_f3_errors_collected(self) -> None:
        """Both F1 (too few steps) and F3 (bad window) must be returned."""
        errors = validate_funnel_args(
            **_valid_funnel_args(steps=["A"], conversion_window=0)
        )
        codes = _codes(errors)
        assert "F1_MIN_STEPS" in codes
        assert "F3_CONVERSION_WINDOW_POSITIVE" in codes

    def test_f1_f2_f3_f4_errors_collected(self) -> None:
        """F1, F2, F3 collected; Exclusion("") and Exclusion("  ") raise at construction."""

        # Exclusion("") raises at construction
        with pytest.raises(
            ValueError, match="Exclusion.event must be a non-empty string"
        ):
            Exclusion("")

        # Exclusion("  ") also raises at construction
        with pytest.raises(
            ValueError, match="Exclusion.event must be a non-empty string"
        ):
            Exclusion("  ")

        # F1, F2, F3 still collected together (no F4 — exclusions caught at construction)
        errors = validate_funnel_args(
            **_valid_funnel_args(
                steps=[""],
                conversion_window=-1,
            )
        )
        codes = _codes(errors)
        assert "F1_MIN_STEPS" in codes
        assert "F2_EMPTY_STEP_EVENT" in codes
        assert "F3_CONVERSION_WINDOW_POSITIVE" in codes

    def test_funnel_and_time_errors_collected(self) -> None:
        """Funnel-specific and delegated time errors must all be returned."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                steps=["A"],
                from_date="bad-date",
            )
        )
        codes = _codes(errors)
        assert "F1_MIN_STEPS" in codes
        assert "V8_DATE_FORMAT" in codes

    def test_funnel_and_group_by_errors_collected(self) -> None:
        """GroupBy with negative bucket_size raises at construction; F3 tested separately."""

        # GroupBy with negative bucket_size now raises at construction
        with pytest.raises(ValueError, match="GroupBy.bucket_size must be positive"):
            GroupBy(
                "revenue",
                property_type="number",
                bucket_size=-1,
                bucket_min=0,
                bucket_max=100,
            )

        # F3 still works independently
        errors = validate_funnel_args(**_valid_funnel_args(conversion_window=0))
        codes = _codes(errors)
        assert "F3_CONVERSION_WINDOW_POSITIVE" in codes

    def test_all_rules_violated_at_once(self) -> None:
        """Exclusion("") and GroupBy(bucket_size=-1) raise at construction; remaining rules collected."""

        # Exclusion("") raises at construction
        with pytest.raises(
            ValueError, match="Exclusion.event must be a non-empty string"
        ):
            Exclusion("")

        # GroupBy with negative bucket_size raises at construction
        with pytest.raises(ValueError, match="GroupBy.bucket_size must be positive"):
            GroupBy(
                "revenue",
                property_type="number",
                bucket_size=-1,
                bucket_min=0,
                bucket_max=100,
            )

        # Exclusion("  ") also raises at construction
        with pytest.raises(
            ValueError, match="Exclusion.event must be a non-empty string"
        ):
            Exclusion("  ")

        # Remaining rules still collected (no exclusion — caught at construction)
        errors = validate_funnel_args(
            steps=[""],
            conversion_window=0,
            exclusions=None,
            from_date="not-a-date",
            to_date=None,
            last=30,
            group_by="revenue",
        )
        codes = _codes(errors)
        assert "F1_MIN_STEPS" in codes
        assert "F2_EMPTY_STEP_EVENT" in codes
        assert "F3_CONVERSION_WINDOW_POSITIVE" in codes
        assert "V8_DATE_FORMAT" in codes

    def test_valid_args_return_empty_error_list(self) -> None:
        """Valid default arguments must return an empty error list."""
        errors = validate_funnel_args(**_valid_funnel_args())
        assert errors == []

    def test_valid_args_with_all_fields_populated(self) -> None:
        """Valid arguments with all optional fields populated must pass."""
        errors = validate_funnel_args(
            steps=["Signup", FunnelStep("Add to Cart"), "Purchase"],
            conversion_window=30,
            exclusions=[
                Exclusion("Logout"),
                Exclusion("Refund", from_step=1, to_step=2),
            ],
            from_date="2024-01-01",
            to_date="2024-01-31",
            last=30,
            group_by="platform",
        )
        assert errors == []

    def test_error_count_matches_distinct_violations(self) -> None:
        """The number of errors must match the number of distinct violations."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                steps=["", "  ", "Valid"],
                conversion_window=-1,
            )
        )
        f2_count = sum(1 for e in errors if e.code == "F2_EMPTY_STEP_EVENT")
        f3_count = sum(1 for e in errors if e.code == "F3_CONVERSION_WINDOW_POSITIVE")
        # Two empty steps and one bad conversion window
        assert f2_count == 2
        assert f3_count == 1


# =============================================================================
# T040: Exclusion step range validation (F4b, F4c, F4d)
# =============================================================================


class TestValidateFunnelArgsExclusionRanges:
    """Tests for exclusion step range validation (F4b/F4c/F4d).

    Validates that exclusion ``from_step`` and ``to_step`` values are
    consistent with each other and within the bounds of the funnel's
    step count.

    Rules:
        F4b: ``to_step`` must be >= ``from_step`` (F4_EXCLUSION_STEP_ORDER).
        F4c: ``to_step`` must not exceed the funnel step count
             (F4_EXCLUSION_STEP_BOUNDS).
        F4d: ``from_step`` must not exceed the funnel step count
             (F4_EXCLUSION_STEP_BOUNDS).
    """

    # -- F4b: to_step < from_step rejected --

    def test_to_step_less_than_from_step_raises_at_construction(
        self,
    ) -> None:
        """An exclusion with to_step < from_step must raise ValueError at construction."""

        with pytest.raises(ValueError, match="Exclusion.to_step.*must be >= from_step"):
            Exclusion("Logout", from_step=2, to_step=1)

    # -- F4c: to_step exceeding step count rejected --

    def test_to_step_exceeds_step_count_returns_bounds_error(self) -> None:
        """An exclusion with to_step beyond the last step must produce F4_EXCLUSION_STEP_BOUNDS."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                steps=["A", "B"],  # 2 steps, indices 0-1
                exclusions=[Exclusion("Logout", from_step=0, to_step=5)],
            )
        )
        assert any(e.code == "F4_EXCLUSION_STEP_BOUNDS" for e in errors)

    # -- F4d: from_step exceeding step count rejected --

    def test_from_step_exceeds_step_count_returns_bounds_error(self) -> None:
        """An exclusion with from_step beyond the last step must produce F4_EXCLUSION_STEP_BOUNDS."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                steps=["A", "B"],
                exclusions=[Exclusion("Logout", from_step=3)],
            )
        )
        assert any(e.code == "F4_EXCLUSION_STEP_BOUNDS" for e in errors)

    # -- Valid exclusion ranges pass --

    def test_valid_exclusion_range_no_range_errors(self) -> None:
        """An exclusion with from_step=0, to_step=1 on 2 steps must not produce range errors."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                steps=["A", "B"],
                exclusions=[Exclusion("X", from_step=0, to_step=1)],
            )
        )
        range_codes = {"F4_EXCLUSION_STEP_ORDER", "F4_EXCLUSION_STEP_BOUNDS"}
        assert not any(e.code in range_codes for e in errors)

    def test_exclusion_with_default_steps_no_range_errors(self) -> None:
        """An exclusion with default from_step=0 and to_step=None must not produce range errors."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                exclusions=[Exclusion("X")],
            )
        )
        range_codes = {"F4_EXCLUSION_STEP_ORDER", "F4_EXCLUSION_STEP_BOUNDS"}
        assert not any(e.code in range_codes for e in errors)

    def test_mixed_valid_and_invalid_exclusions(self) -> None:
        """Invalid exclusion (to_step < from_step) raises at construction."""

        # Valid exclusion constructs fine
        valid = Exclusion("Valid", from_step=0, to_step=1)
        assert valid.event == "Valid"

        # Invalid exclusion raises at construction
        with pytest.raises(ValueError, match="Exclusion.to_step.*must be >= from_step"):
            Exclusion("Invalid", from_step=2, to_step=1)

    # -- Edge cases --

    def test_same_from_and_to_step_is_rejected(self) -> None:
        """An exclusion with from_step == to_step is rejected (server requires strict from < to)."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                steps=["A", "B"],
                exclusions=[Exclusion("X", from_step=0, to_step=0)],
            )
        )
        assert "F4_EXCLUSION_STEP_ORDER" in _codes(errors)

    def test_adjacent_steps_is_valid(self) -> None:
        """An exclusion with to_step = from_step + 1 is valid (minimum valid range)."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                steps=["A", "B", "C"],
                exclusions=[Exclusion("X", from_step=0, to_step=1)],
            )
        )
        range_codes = {"F4_EXCLUSION_STEP_ORDER", "F4_EXCLUSION_STEP_BOUNDS"}
        assert not any(e.code in range_codes for e in errors)


class TestValidateFunnelArgsF7:
    """Tests for F7: conversion window unit validation."""

    def test_invalid_unit_returns_f7_error(self) -> None:
        """Invalid conversion_window_unit produces F7 error."""
        errors = validate_funnel_args(
            **_valid_funnel_args(conversion_window_unit="invalid")
        )
        assert "F7_INVALID_WINDOW_UNIT" in _codes(errors)

    def test_valid_units_no_f7_error(self) -> None:
        """All valid conversion_window_unit values produce no F7 error."""
        for unit in ["second", "minute", "hour", "day", "week", "month", "session"]:
            errors = validate_funnel_args(
                **_valid_funnel_args(conversion_window=2, conversion_window_unit=unit)
            )
            f7 = [e for e in errors if e.code.startswith("F7")]
            assert f7 == [], f"unit='{unit}' should be valid, got {f7}"

    def test_invalid_unit_has_suggestion(self) -> None:
        """F7 error includes fuzzy-matched suggestion."""
        errors = validate_funnel_args(
            **_valid_funnel_args(conversion_window_unit="hou")
        )
        f7 = [e for e in errors if e.code == "F7_INVALID_WINDOW_UNIT"]
        assert len(f7) == 1
        assert f7[0].suggestion is not None
        assert "hour" in f7[0].suggestion

    def test_second_unit_min_2_returns_f7b_error(self) -> None:
        """conversion_window=1 with unit='second' produces F7b error."""
        errors = validate_funnel_args(
            **_valid_funnel_args(conversion_window=1, conversion_window_unit="second")
        )
        assert "F7_SECOND_MIN_WINDOW" in _codes(errors)

    def test_second_unit_with_2_passes(self) -> None:
        """conversion_window=2 with unit='second' produces no F7b error."""
        errors = validate_funnel_args(
            **_valid_funnel_args(conversion_window=2, conversion_window_unit="second")
        )
        assert "F7_SECOND_MIN_WINDOW" not in _codes(errors)

    def test_day_unit_with_1_passes(self) -> None:
        """conversion_window=1 with unit='day' is valid (no min constraint)."""
        errors = validate_funnel_args(
            **_valid_funnel_args(conversion_window=1, conversion_window_unit="day")
        )
        f7 = [e for e in errors if e.code.startswith("F7")]
        assert f7 == []

    def test_f7b_error_has_suggestion(self) -> None:
        """F7b error includes suggestion of minimum value."""
        errors = validate_funnel_args(
            **_valid_funnel_args(conversion_window=1, conversion_window_unit="second")
        )
        f7b = [e for e in errors if e.code == "F7_SECOND_MIN_WINDOW"]
        assert len(f7b) == 1
        assert f7b[0].suggestion is not None
        assert "2" in f7b[0].suggestion

    def test_default_unit_is_day(self) -> None:
        """Default conversion_window_unit is 'day' (no error when omitted)."""
        errors = validate_funnel_args(**_valid_funnel_args())
        f7 = [e for e in errors if e.code.startswith("F7")]
        assert f7 == []


# =============================================================================
# F1 max: Maximum 100 steps (G2)
# =============================================================================


class TestValidateFunnelArgsF1Max:
    """Tests for F1_MAX_STEPS: maximum step count validation (100 steps)."""

    def test_101_steps_returns_f1_max_error(self) -> None:
        """101 steps must produce an F1_MAX_STEPS error."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=["A"] * 101))
        assert "F1_MAX_STEPS" in _codes(errors)

    def test_100_steps_no_f1_max_error(self) -> None:
        """Exactly 100 steps must not produce an F1_MAX_STEPS error."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=["A"] * 100))
        assert "F1_MAX_STEPS" not in _codes(errors)

    def test_2_steps_no_f1_max_error(self) -> None:
        """Two steps (minimum valid) must not produce an F1_MAX_STEPS error."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=["A"] * 2))
        assert "F1_MAX_STEPS" not in _codes(errors)


# =============================================================================
# F3 max: Maximum conversion window per unit (G1)
# =============================================================================


class TestValidateFunnelArgsF3Max:
    """Tests for F3_CONVERSION_WINDOW_MAX: per-unit max conversion window."""

    def test_day_368_returns_f3_max_error(self) -> None:
        """conversion_window=368 with unit='day' must produce F3_CONVERSION_WINDOW_MAX."""
        errors = validate_funnel_args(
            **_valid_funnel_args(conversion_window=368, conversion_window_unit="day")
        )
        assert "F3_CONVERSION_WINDOW_MAX" in _codes(errors)

    def test_day_367_no_f3_max_error(self) -> None:
        """conversion_window=367 with unit='day' must not produce F3_CONVERSION_WINDOW_MAX."""
        errors = validate_funnel_args(
            **_valid_funnel_args(conversion_window=367, conversion_window_unit="day")
        )
        assert "F3_CONVERSION_WINDOW_MAX" not in _codes(errors)

    def test_week_53_returns_f3_max_error(self) -> None:
        """conversion_window=53 with unit='week' must produce F3_CONVERSION_WINDOW_MAX."""
        errors = validate_funnel_args(
            **_valid_funnel_args(conversion_window=53, conversion_window_unit="week")
        )
        assert "F3_CONVERSION_WINDOW_MAX" in _codes(errors)

    def test_week_52_no_f3_max_error(self) -> None:
        """conversion_window=52 with unit='week' must not produce F3_CONVERSION_WINDOW_MAX."""
        errors = validate_funnel_args(
            **_valid_funnel_args(conversion_window=52, conversion_window_unit="week")
        )
        assert "F3_CONVERSION_WINDOW_MAX" not in _codes(errors)

    def test_month_13_returns_f3_max_error(self) -> None:
        """conversion_window=13 with unit='month' must produce F3_CONVERSION_WINDOW_MAX."""
        errors = validate_funnel_args(
            **_valid_funnel_args(conversion_window=13, conversion_window_unit="month")
        )
        assert "F3_CONVERSION_WINDOW_MAX" in _codes(errors)

    def test_month_12_no_f3_max_error(self) -> None:
        """conversion_window=12 with unit='month' must not produce F3_CONVERSION_WINDOW_MAX."""
        errors = validate_funnel_args(
            **_valid_funnel_args(conversion_window=12, conversion_window_unit="month")
        )
        assert "F3_CONVERSION_WINDOW_MAX" not in _codes(errors)

    def test_f3_max_error_message_includes_max_and_unit(self) -> None:
        """The F3_CONVERSION_WINDOW_MAX error message must include the max value and unit name."""
        errors = validate_funnel_args(
            **_valid_funnel_args(conversion_window=368, conversion_window_unit="day")
        )
        f3_max = [e for e in errors if e.code == "F3_CONVERSION_WINDOW_MAX"]
        assert len(f3_max) == 1
        assert "367" in f3_max[0].message
        assert "day" in f3_max[0].message


# =============================================================================
# F4 negative: Negative from_step in exclusions (G3)
# =============================================================================


class TestValidateFunnelArgsF4Negative:
    """Tests for F4_EXCLUSION_NEGATIVE_STEP: negative from_step validation."""

    def test_negative_one_from_step_raises_at_construction(self) -> None:
        """Exclusion with from_step=-1 must raise ValueError at construction."""

        with pytest.raises(ValueError, match="Exclusion.from_step must be >= 0"):
            Exclusion("X", from_step=-1)

    def test_large_negative_from_step_raises_at_construction(self) -> None:
        """Exclusion with from_step=-100 must raise ValueError at construction."""

        with pytest.raises(ValueError, match="Exclusion.from_step must be >= 0"):
            Exclusion("X", from_step=-100)

    def test_zero_from_step_no_negative_error(self) -> None:
        """Exclusion with from_step=0 must not produce F4_EXCLUSION_NEGATIVE_STEP."""
        errors = validate_funnel_args(
            **_valid_funnel_args(exclusions=[Exclusion("X", from_step=0)])
        )
        assert "F4_EXCLUSION_NEGATIVE_STEP" not in _codes(errors)


# =============================================================================
# F4 control chars: Control characters in exclusion events (G7)
# =============================================================================


class TestValidateFunnelArgsF4ControlChars:
    """Tests for F4_CONTROL_CHAR_EXCLUSION: control chars in exclusion event names."""

    def test_null_byte_in_exclusion_raises_at_construction(self) -> None:
        """Exclusion event containing a null byte must raise ValueError at construction."""

        with pytest.raises(
            ValueError, match="Exclusion.event contains control characters"
        ):
            Exclusion("X\x00Y")

    def test_valid_exclusion_no_control_char_error(self) -> None:
        """Exclusion with a valid event name must not produce F4_CONTROL_CHAR_EXCLUSION."""
        errors = validate_funnel_args(
            **_valid_funnel_args(exclusions=[Exclusion("Valid")])
        )
        assert "F4_CONTROL_CHAR_EXCLUSION" not in _codes(errors)


# =============================================================================
# F2 control chars: Control/invisible characters in step events (G8)
# =============================================================================


class TestValidateFunnelArgsF2ControlChars:
    """Tests for F2_CONTROL_CHAR_STEP_EVENT and F2_INVISIBLE_STEP_EVENT."""

    def test_null_byte_in_step_returns_control_char_error(self) -> None:
        """Step event containing a null byte must produce F2_CONTROL_CHAR_STEP_EVENT."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=["A\x00B", "C"]))
        assert "F2_CONTROL_CHAR_STEP_EVENT" in _codes(errors)

    def test_zero_width_space_only_returns_invisible_error(self) -> None:
        """Step event with only a zero-width space must produce F2_INVISIBLE_STEP_EVENT."""
        errors = validate_funnel_args(**_valid_funnel_args(steps=["\u200b", "C"]))
        assert "F2_INVISIBLE_STEP_EVENT" in _codes(errors)

    def test_valid_steps_no_control_or_invisible_errors(self) -> None:
        """Valid step event names must not produce F2 control/invisible errors."""
        errors = validate_funnel_args(
            **_valid_funnel_args(steps=["Valid", "Also Valid"])
        )
        assert "F2_CONTROL_CHAR_STEP_EVENT" not in _codes(errors)
        assert "F2_INVISIBLE_STEP_EVENT" not in _codes(errors)


# =============================================================================
# F8 max holding: Maximum 3 holding constants (G5)
# =============================================================================


class TestValidateFunnelArgsF8MaxHolding:
    """Tests for F8_MAX_HOLDING_CONSTANT: maximum holding constant properties."""

    def test_four_holding_constants_returns_f8_error(self) -> None:
        """Four holding constants must produce F8_MAX_HOLDING_CONSTANT."""
        errors = validate_funnel_args(
            **_valid_funnel_args(holding_constant=["a", "b", "c", "d"])
        )
        assert "F8_MAX_HOLDING_CONSTANT" in _codes(errors)

    def test_three_holding_constants_no_f8_error(self) -> None:
        """Three holding constants (the maximum) must not produce F8_MAX_HOLDING_CONSTANT."""
        errors = validate_funnel_args(
            **_valid_funnel_args(holding_constant=["a", "b", "c"])
        )
        assert "F8_MAX_HOLDING_CONSTANT" not in _codes(errors)

    def test_none_holding_constant_no_f8_error(self) -> None:
        """None holding_constant must not produce F8_MAX_HOLDING_CONSTANT."""
        errors = validate_funnel_args(**_valid_funnel_args(holding_constant=None))
        assert "F8_MAX_HOLDING_CONSTANT" not in _codes(errors)

    def test_f8_error_message_includes_count(self) -> None:
        """The F8 error message must include the actual count of holding constants."""
        errors = validate_funnel_args(
            **_valid_funnel_args(holding_constant=["a", "b", "c", "d"])
        )
        f8 = [e for e in errors if e.code == "F8_MAX_HOLDING_CONSTANT"]
        assert len(f8) == 1
        assert "4" in f8[0].message


# =============================================================================
# F9 session math: Session math/window constraints (G6)
# =============================================================================


class TestValidateFunnelArgsF9SessionMath:
    """Tests for F9: session math requires session window and vice versa."""

    def test_session_math_with_day_unit_returns_f9_error(self) -> None:
        """math='conversion_rate_session' with unit='day' must produce F9_SESSION_MATH_REQUIRES_SESSION_WINDOW."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                math="conversion_rate_session",
                conversion_window_unit="day",
            )
        )
        assert "F9_SESSION_MATH_REQUIRES_SESSION_WINDOW" in _codes(errors)

    def test_session_math_with_session_unit_no_f9_error(self) -> None:
        """math='conversion_rate_session' with unit='session' must not produce F9 errors."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                math="conversion_rate_session",
                conversion_window_unit="session",
                conversion_window=1,
            )
        )
        f9_codes = {
            "F9_SESSION_MATH_REQUIRES_SESSION_WINDOW",
            "F9_SESSION_WINDOW_REQUIRES_ONE",
        }
        assert not any(e.code in f9_codes for e in errors)

    def test_session_unit_with_non_session_math_window_2_returns_f9_error(self) -> None:
        """conversion_window_unit='session' with non-session math and window=2 must produce F9_SESSION_WINDOW_REQUIRES_ONE."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                conversion_window_unit="session",
                conversion_window=2,
            )
        )
        assert "F9_SESSION_WINDOW_REQUIRES_ONE" in _codes(errors)

    def test_session_unit_with_non_session_math_window_1_no_f9_error(self) -> None:
        """conversion_window_unit='session' with non-session math and window=1 must not produce F9 errors."""
        errors = validate_funnel_args(
            **_valid_funnel_args(
                conversion_window_unit="session",
                conversion_window=1,
                math="conversion_rate_unique",
            )
        )
        f9_codes = {
            "F9_SESSION_MATH_REQUIRES_SESSION_WINDOW",
            "F9_SESSION_WINDOW_REQUIRES_ONE",
        }
        assert not any(e.code in f9_codes for e in errors)


class TestValidateFunnelArgsF3Type:
    """Tests for F3_CONVERSION_WINDOW_TYPE: conversion_window must be int."""

    def test_float_returns_type_error(self) -> None:
        """Float conversion_window produces F3_CONVERSION_WINDOW_TYPE."""
        errors = validate_funnel_args(**_valid_funnel_args(conversion_window=14.5))
        assert "F3_CONVERSION_WINDOW_TYPE" in _codes(errors)

    def test_bool_returns_type_error(self) -> None:
        """Boolean conversion_window produces F3_CONVERSION_WINDOW_TYPE."""
        errors = validate_funnel_args(**_valid_funnel_args(conversion_window=True))
        assert "F3_CONVERSION_WINDOW_TYPE" in _codes(errors)

    def test_int_no_type_error(self) -> None:
        """Integer conversion_window produces no F3_CONVERSION_WINDOW_TYPE."""
        errors = validate_funnel_args(**_valid_funnel_args(conversion_window=14))
        assert "F3_CONVERSION_WINDOW_TYPE" not in _codes(errors)


class TestValidateFunnelArgsF10MathProperty:
    """Tests for F10: property math requires math_property."""

    def test_average_without_property_returns_f10_error(self) -> None:
        """math='average' without math_property produces F10_MATH_MISSING_PROPERTY."""
        errors = validate_funnel_args(
            **_valid_funnel_args(math="average", math_property=None)
        )
        assert "F10_MATH_MISSING_PROPERTY" in _codes(errors)

    def test_median_without_property_returns_f10_error(self) -> None:
        """math='median' without math_property produces F10_MATH_MISSING_PROPERTY."""
        errors = validate_funnel_args(
            **_valid_funnel_args(math="median", math_property=None)
        )
        assert "F10_MATH_MISSING_PROPERTY" in _codes(errors)

    def test_p99_without_property_returns_f10_error(self) -> None:
        """math='p99' without math_property produces F10_MATH_MISSING_PROPERTY."""
        errors = validate_funnel_args(
            **_valid_funnel_args(math="p99", math_property=None)
        )
        assert "F10_MATH_MISSING_PROPERTY" in _codes(errors)

    def test_average_with_property_no_f10_error(self) -> None:
        """math='average' with math_property produces no F10 error."""
        errors = validate_funnel_args(
            **_valid_funnel_args(math="average", math_property="amount")
        )
        assert "F10_MATH_MISSING_PROPERTY" not in _codes(errors)

    def test_conversion_rate_unique_without_property_no_f10_error(self) -> None:
        """math='conversion_rate_unique' without math_property produces no F10 error."""
        errors = validate_funnel_args(
            **_valid_funnel_args(math="conversion_rate_unique", math_property=None)
        )
        assert "F10_MATH_MISSING_PROPERTY" not in _codes(errors)

    def test_unique_without_property_no_f10_error(self) -> None:
        """math='unique' without math_property produces no F10 error."""
        errors = validate_funnel_args(
            **_valid_funnel_args(math="unique", math_property=None)
        )
        assert "F10_MATH_MISSING_PROPERTY" not in _codes(errors)


class TestValidateFunnelArgsF11MathRejectsProperty:
    """Tests for F11: non-property math rejects math_property."""

    def test_conversion_rate_unique_with_property_returns_f11_error(self) -> None:
        """math='conversion_rate_unique' with math_property produces F11_MATH_REJECTS_PROPERTY."""
        errors = validate_funnel_args(
            **_valid_funnel_args(math="conversion_rate_unique", math_property="amount")
        )
        assert "F11_MATH_REJECTS_PROPERTY" in _codes(errors)

    def test_unique_with_property_returns_f11_error(self) -> None:
        """math='unique' with math_property produces F11_MATH_REJECTS_PROPERTY."""
        errors = validate_funnel_args(
            **_valid_funnel_args(math="unique", math_property="amount")
        )
        assert "F11_MATH_REJECTS_PROPERTY" in _codes(errors)

    def test_total_with_property_no_f11_error(self) -> None:
        """math='total' is in MATH_PROPERTY_OPTIONAL, so math_property is accepted."""
        errors = validate_funnel_args(
            **_valid_funnel_args(math="total", math_property="amount")
        )
        assert "F11_MATH_REJECTS_PROPERTY" not in _codes(errors)

    def test_average_with_property_no_f11_error(self) -> None:
        """math='average' with math_property produces no F11 error."""
        errors = validate_funnel_args(
            **_valid_funnel_args(math="average", math_property="amount")
        )
        assert "F11_MATH_REJECTS_PROPERTY" not in _codes(errors)


# =============================================================================
# F8b: HoldingConstant property validation
# =============================================================================


# =============================================================================
# T010: F12 — reentry_mode validation
# =============================================================================


class TestValidateFunnelArgsF12ReentryMode:
    """Tests for F12: reentry_mode validation."""

    def test_valid_reentry_mode_default_no_error(self) -> None:
        """reentry_mode='default' must not produce F12 error."""
        errors = validate_funnel_args(**_valid_funnel_args(reentry_mode="default"))
        assert "F12_INVALID_REENTRY_MODE" not in _codes(errors)

    def test_valid_reentry_mode_basic_no_error(self) -> None:
        """reentry_mode='basic' must not produce F12 error."""
        errors = validate_funnel_args(**_valid_funnel_args(reentry_mode="basic"))
        assert "F12_INVALID_REENTRY_MODE" not in _codes(errors)

    def test_valid_reentry_mode_aggressive_no_error(self) -> None:
        """reentry_mode='aggressive' must not produce F12 error."""
        errors = validate_funnel_args(**_valid_funnel_args(reentry_mode="aggressive"))
        assert "F12_INVALID_REENTRY_MODE" not in _codes(errors)

    def test_valid_reentry_mode_optimized_no_error(self) -> None:
        """reentry_mode='optimized' must not produce F12 error."""
        errors = validate_funnel_args(**_valid_funnel_args(reentry_mode="optimized"))
        assert "F12_INVALID_REENTRY_MODE" not in _codes(errors)

    def test_none_reentry_mode_no_error(self) -> None:
        """reentry_mode=None must not produce F12 error."""
        errors = validate_funnel_args(**_valid_funnel_args(reentry_mode=None))
        assert "F12_INVALID_REENTRY_MODE" not in _codes(errors)

    def test_invalid_reentry_mode_returns_f12_error(self) -> None:
        """reentry_mode='invalid' must produce F12_INVALID_REENTRY_MODE error."""
        errors = validate_funnel_args(**_valid_funnel_args(reentry_mode="invalid"))
        assert "F12_INVALID_REENTRY_MODE" in _codes(errors)

    def test_f12_error_path_is_reentry_mode(self) -> None:
        """The F12 error path must point to 'reentry_mode'."""
        errors = validate_funnel_args(**_valid_funnel_args(reentry_mode="bad"))
        f12 = [e for e in errors if e.code == "F12_INVALID_REENTRY_MODE"]
        assert len(f12) == 1
        assert f12[0].path == "reentry_mode"


class TestF8bHoldingConstantPropertyValidation:
    """Tests for F8b: empty holding constant property names."""

    def test_empty_string_property_raises_at_construction(self) -> None:
        """HoldingConstant with empty property name raises ValueError at construction."""

        from mixpanel_headless.types import HoldingConstant

        with pytest.raises(
            ValueError, match="HoldingConstant.property must be a non-empty string"
        ):
            HoldingConstant("")

    def test_whitespace_only_property_raises_at_construction(self) -> None:
        """HoldingConstant with whitespace-only property raises ValueError at construction."""

        from mixpanel_headless.types import HoldingConstant

        with pytest.raises(
            ValueError, match="HoldingConstant.property must be a non-empty string"
        ):
            HoldingConstant("   ")

    def test_valid_property_no_error(self) -> None:
        """HoldingConstant with valid property name produces no F8b error."""
        from mixpanel_headless.types import HoldingConstant

        errors = validate_funnel_args(
            **_valid_funnel_args(
                holding_constant=[HoldingConstant("platform")],
            )
        )
        assert "F8_EMPTY_HOLDING_CONSTANT_PROPERTY" not in _codes(errors)

    def test_multiple_with_one_empty_raises_at_construction(self) -> None:
        """HoldingConstant("") raises ValueError at construction."""

        from mixpanel_headless.types import HoldingConstant

        # Valid one constructs fine
        valid = HoldingConstant("platform")
        assert valid.property == "platform"

        # Empty one raises at construction
        with pytest.raises(
            ValueError, match="HoldingConstant.property must be a non-empty string"
        ):
            HoldingConstant("")


# =============================================================================
# T036: data_group_id validation for funnels
# =============================================================================


class TestDataGroupIdValidationFunnel:
    """Tests for data_group_id validation in validate_funnel_args (T036)."""

    def test_valid_data_group_id(self) -> None:
        """Positive integer data_group_id passes funnel validation."""
        errors = validate_funnel_args(**_valid_funnel_args(data_group_id=5))
        assert not any(e.code == "DG1_INVALID_DATA_GROUP_ID" for e in errors)

    def test_none_data_group_id(self) -> None:
        """None data_group_id passes funnel validation."""
        errors = validate_funnel_args(**_valid_funnel_args(data_group_id=None))
        assert not any(e.code == "DG1_INVALID_DATA_GROUP_ID" for e in errors)

    def test_zero_data_group_id(self) -> None:
        """data_group_id=0 fails funnel validation."""
        errors = validate_funnel_args(**_valid_funnel_args(data_group_id=0))
        dg_errors = [e for e in errors if e.code == "DG1_INVALID_DATA_GROUP_ID"]
        assert len(dg_errors) == 1

    def test_negative_data_group_id(self) -> None:
        """Negative data_group_id fails funnel validation."""
        errors = validate_funnel_args(**_valid_funnel_args(data_group_id=-3))
        dg_errors = [e for e in errors if e.code == "DG1_INVALID_DATA_GROUP_ID"]
        assert len(dg_errors) == 1
