"""Unit tests for flow argument and flow bookmark validation rules.

Tests ``validate_flow_args()`` which validates Python-level arguments
before flow bookmark construction (rules FL1-FL10, enum validation).
Tests ``validate_flow_bookmark()`` which validates the structural integrity
of a flat flow bookmark params dict (rules FLB1-FLB6).

Flow argument validation rules:
    FL1: steps list must be non-empty.
    FL2: Each step event name must be non-empty, no control chars, no invisible-only.
    FL3: forward must be in range 0-5.
    FL4: reverse must be in range 0-5.
    FL5: forward + reverse must be > 0 (at least one direction).
    FL6: cardinality must be in range 1-50.
    FL7: conversion_window must be a positive integer.
    FL8: Time validation delegated to ``validate_time_args``.
    Enum: count_type and mode must be valid enum values.

Flow bookmark validation rules:
    FLB1: steps must be present and non-empty.
    FLB2: Each step event name must be non-empty.
    FLB3: count_type must be a valid enum value.
    FLB4: chartType must be a valid enum value.
    FLB5: date_range must be present.
    FLB6: version must be 2.
"""

from __future__ import annotations

from typing import Any

from mixpanel_headless._internal.validation import (
    validate_flow_args,
    validate_flow_bookmark,
)
from mixpanel_headless.exceptions import ValidationError

# =============================================================================
# Helpers
# =============================================================================


def _valid_flow_args(**overrides: Any) -> dict[str, Any]:
    """Build a default-valid kwargs dict for ``validate_flow_args``.

    All defaults pass validation. Override individual keys to inject
    specific invalid values for targeted testing.

    Args:
        **overrides: Keyword arguments to override in the defaults.

    Returns:
        Dict suitable for unpacking into ``validate_flow_args(**d)``.
    """
    defaults: dict[str, Any] = {
        "steps": ["Purchase"],
        "forward": 3,
        "reverse": 0,
        "count_type": "unique",
        "mode": "sankey",
        "cardinality": 3,
        "conversion_window": 7,
        "from_date": None,
        "to_date": None,
        "last": 30,
    }
    defaults.update(overrides)
    return defaults


def _valid_flow_bookmark(**overrides: Any) -> dict[str, Any]:
    """Build a default-valid params dict for ``validate_flow_bookmark``.

    All defaults pass validation. Override individual keys to inject
    specific invalid values for targeted testing.

    Args:
        **overrides: Keyword arguments to override in the defaults.

    Returns:
        Dict suitable for passing to ``validate_flow_bookmark(d)``.
    """
    defaults: dict[str, Any] = {
        "steps": [{"event": "Purchase", "forward": 3, "reverse": 0}],
        "date_range": {
            "type": "in the last",
            "from_date": {"unit": "day", "value": 30},
            "to_date": "$now",
        },
        "chartType": "sankey",
        "count_type": "unique",
        "version": 2,
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
# T016: FL1 — steps must be non-empty
# =============================================================================


class TestValidateFlowFL1:
    """Tests for FL1: steps list must be non-empty."""

    def test_empty_steps_returns_fl1_error(self) -> None:
        """An empty steps list must produce an FL1_EMPTY_STEPS error."""
        errors = validate_flow_args(**_valid_flow_args(steps=[]))
        assert any(e.code == "FL1_EMPTY_STEPS" for e in errors)

    def test_non_empty_steps_no_fl1_error(self) -> None:
        """A non-empty steps list must not produce an FL1 error."""
        errors = validate_flow_args(**_valid_flow_args(steps=["Purchase"]))
        assert "FL1_EMPTY_STEPS" not in _codes(errors)

    def test_fl1_error_path_is_steps(self) -> None:
        """The FL1 error path must point to 'steps'."""
        errors = validate_flow_args(**_valid_flow_args(steps=[]))
        fl1_errors = [e for e in errors if e.code == "FL1_EMPTY_STEPS"]
        assert len(fl1_errors) == 1
        assert fl1_errors[0].path == "steps"

    def test_multiple_steps_no_fl1_error(self) -> None:
        """Multiple steps must not produce an FL1 error."""
        errors = validate_flow_args(
            **_valid_flow_args(steps=["Purchase", "Signup", "Login"])
        )
        assert "FL1_EMPTY_STEPS" not in _codes(errors)


# =============================================================================
# T016: FL2 — step event name must be non-empty, no control/invisible chars
# =============================================================================


class TestValidateFlowFL2:
    """Tests for FL2: each step event name must be non-empty, visible string."""

    def test_empty_event_name_returns_fl2_error(self) -> None:
        """An empty string event name must produce an FL2_EMPTY_STEP_EVENT error."""
        errors = validate_flow_args(**_valid_flow_args(steps=[""]))
        assert any(e.code == "FL2_EMPTY_STEP_EVENT" for e in errors)

    def test_whitespace_only_event_name_returns_fl2_error(self) -> None:
        """A whitespace-only event name must produce an FL2_EMPTY_STEP_EVENT error."""
        errors = validate_flow_args(**_valid_flow_args(steps=["   "]))
        assert any(e.code == "FL2_EMPTY_STEP_EVENT" for e in errors)

    def test_tab_only_event_name_returns_fl2_error(self) -> None:
        """A tab-only event name must produce an FL2_EMPTY_STEP_EVENT error."""
        errors = validate_flow_args(**_valid_flow_args(steps=["\t"]))
        assert any(e.code == "FL2_EMPTY_STEP_EVENT" for e in errors)

    def test_control_char_in_event_name_returns_fl2_control_error(self) -> None:
        """A null byte in an event name must produce FL2_CONTROL_CHAR_STEP_EVENT."""
        errors = validate_flow_args(**_valid_flow_args(steps=["\x00Login"]))
        assert any(e.code == "FL2_CONTROL_CHAR_STEP_EVENT" for e in errors)

    def test_bell_char_in_event_name_returns_fl2_control_error(self) -> None:
        """A bell character in an event name must produce FL2_CONTROL_CHAR_STEP_EVENT."""
        errors = validate_flow_args(**_valid_flow_args(steps=["Pur\x07chase"]))
        assert any(e.code == "FL2_CONTROL_CHAR_STEP_EVENT" for e in errors)

    def test_invisible_only_event_name_returns_fl2_invisible_error(self) -> None:
        """An event name with only zero-width spaces must produce FL2_INVISIBLE_STEP_EVENT."""
        errors = validate_flow_args(**_valid_flow_args(steps=["\u200b"]))
        assert any(e.code == "FL2_INVISIBLE_STEP_EVENT" for e in errors)

    def test_zero_width_joiner_only_returns_fl2_invisible_error(self) -> None:
        """An event name with only zero-width joiners must produce FL2_INVISIBLE_STEP_EVENT."""
        errors = validate_flow_args(**_valid_flow_args(steps=["\u200d\u200d"]))
        assert any(e.code == "FL2_INVISIBLE_STEP_EVENT" for e in errors)

    def test_valid_event_name_no_fl2_error(self) -> None:
        """A valid event name must not produce any FL2 errors."""
        errors = validate_flow_args(**_valid_flow_args(steps=["Purchase"]))
        fl2_codes = {
            "FL2_EMPTY_STEP_EVENT",
            "FL2_CONTROL_CHAR_STEP_EVENT",
            "FL2_INVISIBLE_STEP_EVENT",
        }
        assert not any(e.code in fl2_codes for e in errors)

    def test_fl2_error_path_includes_index(self) -> None:
        """The FL2 error path must include the step index."""
        errors = validate_flow_args(**_valid_flow_args(steps=["Purchase", ""]))
        fl2_errors = [e for e in errors if e.code == "FL2_EMPTY_STEP_EVENT"]
        assert len(fl2_errors) == 1
        assert fl2_errors[0].path == "steps[1]"

    def test_multiple_invalid_steps_report_all(self) -> None:
        """Multiple invalid step names must all produce errors."""
        errors = validate_flow_args(**_valid_flow_args(steps=["", "   "]))
        fl2_errors = [e for e in errors if e.code == "FL2_EMPTY_STEP_EVENT"]
        assert len(fl2_errors) == 2


# =============================================================================
# T016: FL3 — forward must be in range 0-5
# =============================================================================


class TestValidateFlowFL3:
    """Tests for FL3: forward must be in range 0-5."""

    def test_negative_forward_returns_fl3_error(self) -> None:
        """A negative forward value must produce an FL3_FORWARD_RANGE error."""
        errors = validate_flow_args(**_valid_flow_args(forward=-1))
        assert any(e.code == "FL3_FORWARD_RANGE" for e in errors)

    def test_forward_exceeds_max_returns_fl3_error(self) -> None:
        """forward=6 must produce an FL3_FORWARD_RANGE error."""
        errors = validate_flow_args(**_valid_flow_args(forward=6))
        assert any(e.code == "FL3_FORWARD_RANGE" for e in errors)

    def test_forward_zero_no_fl3_error(self) -> None:
        """forward=0 with reverse>0 must not produce an FL3 error."""
        errors = validate_flow_args(**_valid_flow_args(forward=0, reverse=1))
        assert "FL3_FORWARD_RANGE" not in _codes(errors)

    def test_forward_five_no_fl3_error(self) -> None:
        """forward=5 must not produce an FL3 error."""
        errors = validate_flow_args(**_valid_flow_args(forward=5))
        assert "FL3_FORWARD_RANGE" not in _codes(errors)

    def test_forward_three_no_fl3_error(self) -> None:
        """forward=3 (default) must not produce an FL3 error."""
        errors = validate_flow_args(**_valid_flow_args(forward=3))
        assert "FL3_FORWARD_RANGE" not in _codes(errors)

    def test_fl3_error_path_is_forward(self) -> None:
        """The FL3 error path must point to 'forward'."""
        errors = validate_flow_args(**_valid_flow_args(forward=-1))
        fl3_errors = [e for e in errors if e.code == "FL3_FORWARD_RANGE"]
        assert len(fl3_errors) == 1
        assert fl3_errors[0].path == "forward"


# =============================================================================
# T016: FL4 — reverse must be in range 0-5
# =============================================================================


class TestValidateFlowFL4:
    """Tests for FL4: reverse must be in range 0-5."""

    def test_negative_reverse_returns_fl4_error(self) -> None:
        """A negative reverse value must produce an FL4_REVERSE_RANGE error."""
        errors = validate_flow_args(**_valid_flow_args(reverse=-1))
        assert any(e.code == "FL4_REVERSE_RANGE" for e in errors)

    def test_reverse_exceeds_max_returns_fl4_error(self) -> None:
        """reverse=6 must produce an FL4_REVERSE_RANGE error."""
        errors = validate_flow_args(**_valid_flow_args(reverse=6))
        assert any(e.code == "FL4_REVERSE_RANGE" for e in errors)

    def test_reverse_zero_no_fl4_error(self) -> None:
        """reverse=0 must not produce an FL4 error."""
        errors = validate_flow_args(**_valid_flow_args(reverse=0))
        assert "FL4_REVERSE_RANGE" not in _codes(errors)

    def test_reverse_five_no_fl4_error(self) -> None:
        """reverse=5 must not produce an FL4 error."""
        errors = validate_flow_args(**_valid_flow_args(reverse=5, forward=0))
        assert "FL4_REVERSE_RANGE" not in _codes(errors)

    def test_fl4_error_path_is_reverse(self) -> None:
        """The FL4 error path must point to 'reverse'."""
        errors = validate_flow_args(**_valid_flow_args(reverse=-1))
        fl4_errors = [e for e in errors if e.code == "FL4_REVERSE_RANGE"]
        assert len(fl4_errors) == 1
        assert fl4_errors[0].path == "reverse"


# =============================================================================
# T016: FL5 — forward + reverse must be > 0
# =============================================================================


class TestValidateFlowFL5:
    """Tests for FL5: forward + reverse must be > 0 (at least one direction)."""

    def test_both_zero_returns_fl5_error(self) -> None:
        """forward=0 and reverse=0 must produce an FL5_NO_DIRECTION error."""
        errors = validate_flow_args(**_valid_flow_args(forward=0, reverse=0))
        assert any(e.code == "FL5_NO_DIRECTION" for e in errors)

    def test_forward_one_reverse_zero_no_fl5_error(self) -> None:
        """forward=1 and reverse=0 must not produce an FL5 error."""
        errors = validate_flow_args(**_valid_flow_args(forward=1, reverse=0))
        assert "FL5_NO_DIRECTION" not in _codes(errors)

    def test_forward_zero_reverse_one_no_fl5_error(self) -> None:
        """forward=0 and reverse=1 must not produce an FL5 error."""
        errors = validate_flow_args(**_valid_flow_args(forward=0, reverse=1))
        assert "FL5_NO_DIRECTION" not in _codes(errors)

    def test_both_nonzero_no_fl5_error(self) -> None:
        """forward=2 and reverse=2 must not produce an FL5 error."""
        errors = validate_flow_args(**_valid_flow_args(forward=2, reverse=2))
        assert "FL5_NO_DIRECTION" not in _codes(errors)

    def test_fl5_error_path_is_forward(self) -> None:
        """The FL5 error path must point to 'forward'."""
        errors = validate_flow_args(**_valid_flow_args(forward=0, reverse=0))
        fl5_errors = [e for e in errors if e.code == "FL5_NO_DIRECTION"]
        assert len(fl5_errors) == 1
        assert fl5_errors[0].path == "forward"


# =============================================================================
# T016: FL6 — cardinality must be in range 1-50
# =============================================================================


class TestValidateFlowFL6:
    """Tests for FL6: cardinality must be in range 1-50."""

    def test_cardinality_zero_returns_fl6_error(self) -> None:
        """cardinality=0 must produce an FL6_CARDINALITY_RANGE error."""
        errors = validate_flow_args(**_valid_flow_args(cardinality=0))
        assert any(e.code == "FL6_CARDINALITY_RANGE" for e in errors)

    def test_cardinality_negative_returns_fl6_error(self) -> None:
        """cardinality=-1 must produce an FL6_CARDINALITY_RANGE error."""
        errors = validate_flow_args(**_valid_flow_args(cardinality=-1))
        assert any(e.code == "FL6_CARDINALITY_RANGE" for e in errors)

    def test_cardinality_51_returns_fl6_error(self) -> None:
        """cardinality=51 must produce an FL6_CARDINALITY_RANGE error."""
        errors = validate_flow_args(**_valid_flow_args(cardinality=51))
        assert any(e.code == "FL6_CARDINALITY_RANGE" for e in errors)

    def test_cardinality_one_no_fl6_error(self) -> None:
        """cardinality=1 (lower bound) must not produce an FL6 error."""
        errors = validate_flow_args(**_valid_flow_args(cardinality=1))
        assert "FL6_CARDINALITY_RANGE" not in _codes(errors)

    def test_cardinality_50_no_fl6_error(self) -> None:
        """cardinality=50 (upper bound) must not produce an FL6 error."""
        errors = validate_flow_args(**_valid_flow_args(cardinality=50))
        assert "FL6_CARDINALITY_RANGE" not in _codes(errors)

    def test_cardinality_three_no_fl6_error(self) -> None:
        """cardinality=3 (default) must not produce an FL6 error."""
        errors = validate_flow_args(**_valid_flow_args(cardinality=3))
        assert "FL6_CARDINALITY_RANGE" not in _codes(errors)

    def test_fl6_error_path_is_cardinality(self) -> None:
        """The FL6 error path must point to 'cardinality'."""
        errors = validate_flow_args(**_valid_flow_args(cardinality=0))
        fl6_errors = [e for e in errors if e.code == "FL6_CARDINALITY_RANGE"]
        assert len(fl6_errors) == 1
        assert fl6_errors[0].path == "cardinality"


# =============================================================================
# T016: FL7 — conversion_window must be positive
# =============================================================================


class TestValidateFlowFL7:
    """Tests for FL7: conversion_window must be a positive integer."""

    def test_conversion_window_zero_returns_fl7_error(self) -> None:
        """conversion_window=0 must produce an FL7_CONVERSION_WINDOW_POSITIVE error."""
        errors = validate_flow_args(**_valid_flow_args(conversion_window=0))
        assert any(e.code == "FL7_CONVERSION_WINDOW_POSITIVE" for e in errors)

    def test_conversion_window_negative_returns_fl7_error(self) -> None:
        """conversion_window=-1 must produce an FL7_CONVERSION_WINDOW_POSITIVE error."""
        errors = validate_flow_args(**_valid_flow_args(conversion_window=-1))
        assert any(e.code == "FL7_CONVERSION_WINDOW_POSITIVE" for e in errors)

    def test_conversion_window_positive_no_fl7_error(self) -> None:
        """conversion_window=7 must not produce an FL7 error."""
        errors = validate_flow_args(**_valid_flow_args(conversion_window=7))
        assert "FL7_CONVERSION_WINDOW_POSITIVE" not in _codes(errors)

    def test_conversion_window_one_no_fl7_error(self) -> None:
        """conversion_window=1 (minimum valid) must not produce an FL7 error."""
        errors = validate_flow_args(**_valid_flow_args(conversion_window=1))
        assert "FL7_CONVERSION_WINDOW_POSITIVE" not in _codes(errors)

    def test_fl7_error_path_is_conversion_window(self) -> None:
        """The FL7 error path must point to 'conversion_window'."""
        errors = validate_flow_args(**_valid_flow_args(conversion_window=0))
        fl7_errors = [e for e in errors if e.code == "FL7_CONVERSION_WINDOW_POSITIVE"]
        assert len(fl7_errors) == 1
        assert fl7_errors[0].path == "conversion_window"


# =============================================================================
# T016b: FL7b — conversion_window per-unit maximum
# =============================================================================


class TestValidateFlowFL7Max:
    """Tests for FL7b: conversion_window per-unit max (366d/52w/12m)."""

    def test_day_max_exceeded(self) -> None:
        """conversion_window=367 with unit='day' must produce FL7_CONVERSION_WINDOW_MAX."""
        errors = validate_flow_args(
            **_valid_flow_args(conversion_window=367, conversion_window_unit="day")
        )
        assert any(e.code == "FL7_CONVERSION_WINDOW_MAX" for e in errors)

    def test_day_max_at_boundary(self) -> None:
        """conversion_window=366 with unit='day' must not produce FL7_CONVERSION_WINDOW_MAX."""
        errors = validate_flow_args(
            **_valid_flow_args(conversion_window=366, conversion_window_unit="day")
        )
        assert "FL7_CONVERSION_WINDOW_MAX" not in _codes(errors)

    def test_week_max_exceeded(self) -> None:
        """conversion_window=53 with unit='week' must produce FL7_CONVERSION_WINDOW_MAX."""
        errors = validate_flow_args(
            **_valid_flow_args(conversion_window=53, conversion_window_unit="week")
        )
        assert any(e.code == "FL7_CONVERSION_WINDOW_MAX" for e in errors)

    def test_week_max_at_boundary(self) -> None:
        """conversion_window=52 with unit='week' must not produce FL7_CONVERSION_WINDOW_MAX."""
        errors = validate_flow_args(
            **_valid_flow_args(conversion_window=52, conversion_window_unit="week")
        )
        assert "FL7_CONVERSION_WINDOW_MAX" not in _codes(errors)

    def test_month_max_exceeded(self) -> None:
        """conversion_window=13 with unit='month' must produce FL7_CONVERSION_WINDOW_MAX."""
        errors = validate_flow_args(
            **_valid_flow_args(conversion_window=13, conversion_window_unit="month")
        )
        assert any(e.code == "FL7_CONVERSION_WINDOW_MAX" for e in errors)

    def test_month_max_at_boundary(self) -> None:
        """conversion_window=12 with unit='month' must not produce FL7_CONVERSION_WINDOW_MAX."""
        errors = validate_flow_args(
            **_valid_flow_args(conversion_window=12, conversion_window_unit="month")
        )
        assert "FL7_CONVERSION_WINDOW_MAX" not in _codes(errors)

    def test_session_unit_skips_max_check(self) -> None:
        """conversion_window with unit='session' has no max limit."""
        errors = validate_flow_args(
            **_valid_flow_args(
                conversion_window=1,
                conversion_window_unit="session",
                count_type="session",
            )
        )
        assert "FL7_CONVERSION_WINDOW_MAX" not in _codes(errors)

    def test_fl7_max_error_message_includes_limit(self) -> None:
        """FL7_CONVERSION_WINDOW_MAX error message includes the per-unit limit."""
        errors = validate_flow_args(
            **_valid_flow_args(conversion_window=400, conversion_window_unit="day")
        )
        fl7_max = [e for e in errors if e.code == "FL7_CONVERSION_WINDOW_MAX"]
        assert len(fl7_max) == 1
        assert "366" in fl7_max[0].message


# =============================================================================
# T016: FL8 — time validation delegated to validate_time_args
# =============================================================================


class TestValidateFlowFL8:
    """Tests for FL8: time validation delegated to validate_time_args."""

    def test_zero_last_returns_v7_error(self) -> None:
        """last=0 must produce a V7_LAST_POSITIVE error (delegated)."""
        errors = validate_flow_args(**_valid_flow_args(last=0))
        assert any(e.code == "V7_LAST_POSITIVE" for e in errors)

    def test_negative_last_returns_v7_error(self) -> None:
        """last=-5 must produce a V7_LAST_POSITIVE error (delegated)."""
        errors = validate_flow_args(**_valid_flow_args(last=-5))
        assert any(e.code == "V7_LAST_POSITIVE" for e in errors)

    def test_positive_last_no_v7_error(self) -> None:
        """last=30 must not produce a V7_LAST_POSITIVE error."""
        errors = validate_flow_args(**_valid_flow_args(last=30))
        assert "V7_LAST_POSITIVE" not in _codes(errors)

    def test_invalid_from_date_format_returns_v8_error(self) -> None:
        """An invalid from_date format must produce a V8_DATE_FORMAT error (delegated)."""
        errors = validate_flow_args(**_valid_flow_args(from_date="invalid"))
        assert any(e.code == "V8_DATE_FORMAT" for e in errors)

    def test_to_date_without_from_date_returns_v9_error(self) -> None:
        """Setting to_date without from_date must produce a V9 error (delegated)."""
        errors = validate_flow_args(**_valid_flow_args(to_date="2024-01-31"))
        assert any(e.code == "V9_TO_REQUIRES_FROM" for e in errors)

    def test_valid_dates_no_time_errors(self) -> None:
        """Valid from_date and to_date must not produce time errors."""
        errors = validate_flow_args(
            **_valid_flow_args(from_date="2024-01-01", to_date="2024-01-31", last=30)
        )
        time_codes = {"V7_LAST_POSITIVE", "V8_DATE_FORMAT", "V8_DATE_INVALID"}
        assert not any(e.code in time_codes for e in errors)

    def test_no_dates_with_default_last_no_time_errors(self) -> None:
        """Default arguments (no dates, last=30) must not produce time errors."""
        errors = validate_flow_args(**_valid_flow_args())
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


# =============================================================================
# T016: Enum validation — count_type, mode
# =============================================================================


class TestValidateFlowEnums:
    """Tests for enum validation: count_type and mode."""

    # -- count_type --

    def test_invalid_count_type_returns_error(self) -> None:
        """An invalid count_type must produce an FL_INVALID_COUNT_TYPE error."""
        errors = validate_flow_args(**_valid_flow_args(count_type="invalid"))
        assert any(e.code == "FL_INVALID_COUNT_TYPE" for e in errors)

    def test_valid_count_type_unique_no_error(self) -> None:
        """count_type='unique' must not produce an FL_INVALID_COUNT_TYPE error."""
        errors = validate_flow_args(**_valid_flow_args(count_type="unique"))
        assert "FL_INVALID_COUNT_TYPE" not in _codes(errors)

    def test_valid_count_type_total_no_error(self) -> None:
        """count_type='total' must not produce an FL_INVALID_COUNT_TYPE error."""
        errors = validate_flow_args(**_valid_flow_args(count_type="total"))
        assert "FL_INVALID_COUNT_TYPE" not in _codes(errors)

    def test_valid_count_type_session_no_error(self) -> None:
        """count_type='session' must not produce an FL_INVALID_COUNT_TYPE error."""
        errors = validate_flow_args(**_valid_flow_args(count_type="session"))
        assert "FL_INVALID_COUNT_TYPE" not in _codes(errors)

    def test_count_type_close_match_has_suggestion(self) -> None:
        """A close-match count_type must include a suggestion."""
        errors = validate_flow_args(**_valid_flow_args(count_type="uniqe"))
        ct_errors = [e for e in errors if e.code == "FL_INVALID_COUNT_TYPE"]
        assert len(ct_errors) == 1
        assert ct_errors[0].suggestion is not None
        assert "unique" in ct_errors[0].suggestion

    def test_count_type_error_path(self) -> None:
        """The FL_INVALID_COUNT_TYPE error path must point to 'count_type'."""
        errors = validate_flow_args(**_valid_flow_args(count_type="bad"))
        ct_errors = [e for e in errors if e.code == "FL_INVALID_COUNT_TYPE"]
        assert len(ct_errors) == 1
        assert ct_errors[0].path == "count_type"

    # -- mode --

    def test_invalid_mode_returns_error(self) -> None:
        """An invalid mode must produce an FL_INVALID_MODE error."""
        errors = validate_flow_args(**_valid_flow_args(mode="invalid"))
        assert any(e.code == "FL_INVALID_MODE" for e in errors)

    def test_valid_mode_sankey_no_error(self) -> None:
        """mode='sankey' must not produce an FL_INVALID_MODE error."""
        errors = validate_flow_args(**_valid_flow_args(mode="sankey"))
        assert "FL_INVALID_MODE" not in _codes(errors)

    def test_valid_mode_paths_no_error(self) -> None:
        """mode='paths' must not produce an FL_INVALID_MODE error."""
        errors = validate_flow_args(**_valid_flow_args(mode="paths"))
        assert "FL_INVALID_MODE" not in _codes(errors)

    def test_valid_mode_tree_no_error(self) -> None:
        """mode='tree' must not produce an FL_INVALID_MODE error."""
        errors = validate_flow_args(**_valid_flow_args(mode="tree"))
        assert "FL_INVALID_MODE" not in _codes(errors)

    def test_mode_close_match_has_suggestion(self) -> None:
        """A close-match mode must include a suggestion."""
        errors = validate_flow_args(**_valid_flow_args(mode="sanke"))
        mode_errors = [e for e in errors if e.code == "FL_INVALID_MODE"]
        assert len(mode_errors) == 1
        assert mode_errors[0].suggestion is not None
        assert "sankey" in mode_errors[0].suggestion

    def test_mode_error_path(self) -> None:
        """The FL_INVALID_MODE error path must point to 'mode'."""
        errors = validate_flow_args(**_valid_flow_args(mode="bad"))
        mode_errors = [e for e in errors if e.code == "FL_INVALID_MODE"]
        assert len(mode_errors) == 1
        assert mode_errors[0].path == "mode"


# =============================================================================
# FL9/FL10: Session count_type + conversion_window_unit constraints
# =============================================================================


class TestValidateFlowFL9:
    """Tests for FL9: count_type='session' requires conversion_window_unit='session'."""

    def test_session_count_type_without_session_window(self) -> None:
        """count_type='session' with default unit='day' must produce FL9 error."""
        errors = validate_flow_args(
            **_valid_flow_args(count_type="session", conversion_window_unit="day")
        )
        assert any(e.code == "FL9_SESSION_REQUIRES_SESSION_WINDOW" for e in errors)

    def test_session_count_type_with_session_window(self) -> None:
        """count_type='session' with unit='session' and window=1 is valid."""
        errors = validate_flow_args(
            **_valid_flow_args(
                count_type="session",
                conversion_window_unit="session",
                conversion_window=1,
            )
        )
        assert not any(e.code == "FL9_SESSION_REQUIRES_SESSION_WINDOW" for e in errors)

    def test_non_session_count_type_with_any_unit(self) -> None:
        """count_type='unique' with any window unit must not produce FL9 error."""
        errors = validate_flow_args(**_valid_flow_args(count_type="unique"))
        assert not any(e.code == "FL9_SESSION_REQUIRES_SESSION_WINDOW" for e in errors)


class TestValidateFlowFL10:
    """Tests for FL10: conversion_window_unit='session' requires conversion_window=1."""

    def test_session_window_requires_one(self) -> None:
        """conversion_window_unit='session' with window!=1 must produce FL10 error."""
        errors = validate_flow_args(
            **_valid_flow_args(
                count_type="session",
                conversion_window_unit="session",
                conversion_window=7,
            )
        )
        assert any(e.code == "FL10_SESSION_WINDOW_REQUIRES_ONE" for e in errors)

    def test_session_window_with_one(self) -> None:
        """conversion_window_unit='session' with window=1 must not produce FL10 error."""
        errors = validate_flow_args(
            **_valid_flow_args(
                count_type="session",
                conversion_window_unit="session",
                conversion_window=1,
            )
        )
        assert not any(e.code == "FL10_SESSION_WINDOW_REQUIRES_ONE" for e in errors)


class TestValidateFlowWindowUnit:
    """Tests for conversion_window_unit enum validation."""

    def test_invalid_window_unit(self) -> None:
        """Invalid conversion_window_unit must produce error."""
        errors = validate_flow_args(
            **_valid_flow_args(conversion_window_unit="invalid")
        )
        assert any(e.code == "FL_INVALID_WINDOW_UNIT" for e in errors)

    def test_valid_window_units(self) -> None:
        """All valid units must pass."""
        for unit in ("day", "week", "month", "session"):
            kwargs = _valid_flow_args(conversion_window_unit=unit)
            if unit == "session":
                kwargs["count_type"] = "session"
                kwargs["conversion_window"] = 1
            errors = validate_flow_args(**kwargs)
            assert not any(e.code == "FL_INVALID_WINDOW_UNIT" for e in errors), (
                f"unit={unit!r} incorrectly rejected"
            )


# =============================================================================
# T016: Multi-error collection
# =============================================================================


class TestValidateFlowMultiError:
    """Tests for fail-fast validation collecting multiple errors."""

    def test_multiple_errors_collected(self) -> None:
        """Multiple simultaneous validation failures must all be reported."""
        errors = validate_flow_args(
            **_valid_flow_args(
                steps=[],
                forward=-1,
                count_type="invalid",
            )
        )
        codes = _codes(errors)
        assert "FL1_EMPTY_STEPS" in codes
        assert "FL3_FORWARD_RANGE" in codes
        assert "FL_INVALID_COUNT_TYPE" in codes

    def test_four_simultaneous_errors(self) -> None:
        """Four simultaneous validation errors must all be collected."""
        errors = validate_flow_args(
            **_valid_flow_args(
                steps=[""],
                forward=6,
                reverse=-1,
                cardinality=0,
            )
        )
        codes = _codes(errors)
        assert "FL2_EMPTY_STEP_EVENT" in codes
        assert "FL3_FORWARD_RANGE" in codes
        assert "FL4_REVERSE_RANGE" in codes
        assert "FL6_CARDINALITY_RANGE" in codes


# =============================================================================
# T016: All defaults pass
# =============================================================================


class TestValidateFlowDefaults:
    """Tests that default valid arguments produce no errors."""

    def test_all_defaults_pass_validation(self) -> None:
        """Default valid args must produce no errors."""
        errors = validate_flow_args(**_valid_flow_args())
        assert errors == []


# =============================================================================
# T018: FLB1 — steps must be present and non-empty
# =============================================================================


class TestValidateFlowBookmarkFLB1:
    """Tests for FLB1: steps must be present and non-empty in bookmark params."""

    def test_empty_steps_returns_flb1_error(self) -> None:
        """An empty steps list must produce an FLB1_EMPTY_STEPS error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(steps=[]))
        assert any(e.code == "FLB1_EMPTY_STEPS" for e in errors)

    def test_missing_steps_key_returns_flb1_error(self) -> None:
        """A missing steps key must produce an FLB1_EMPTY_STEPS error."""
        params = _valid_flow_bookmark()
        del params["steps"]
        errors = validate_flow_bookmark(params)
        assert any(e.code == "FLB1_EMPTY_STEPS" for e in errors)

    def test_valid_steps_no_flb1_error(self) -> None:
        """Valid steps must not produce an FLB1 error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark())
        assert "FLB1_EMPTY_STEPS" not in _codes(errors)

    def test_flb1_error_path_is_steps(self) -> None:
        """The FLB1 error path must point to 'steps'."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(steps=[]))
        flb1_errors = [e for e in errors if e.code == "FLB1_EMPTY_STEPS"]
        assert len(flb1_errors) == 1
        assert flb1_errors[0].path == "steps"


# =============================================================================
# T018: FLB2 — step event name must be non-empty
# =============================================================================


class TestValidateFlowBookmarkFLB2:
    """Tests for FLB2: each step event name must be non-empty in bookmark params."""

    def test_empty_event_returns_flb2_error(self) -> None:
        """An empty event string must produce an FLB2_EMPTY_STEP_EVENT error."""
        errors = validate_flow_bookmark(
            _valid_flow_bookmark(steps=[{"event": "", "forward": 3, "reverse": 0}])
        )
        assert any(e.code == "FLB2_EMPTY_STEP_EVENT" for e in errors)

    def test_whitespace_only_event_returns_flb2_error(self) -> None:
        """A whitespace-only event string must produce an FLB2_EMPTY_STEP_EVENT error."""
        errors = validate_flow_bookmark(
            _valid_flow_bookmark(steps=[{"event": "   ", "forward": 3, "reverse": 0}])
        )
        assert any(e.code == "FLB2_EMPTY_STEP_EVENT" for e in errors)

    def test_missing_event_key_returns_flb2_error(self) -> None:
        """A step dict missing the event key must produce an FLB2_EMPTY_STEP_EVENT error."""
        errors = validate_flow_bookmark(
            _valid_flow_bookmark(steps=[{"forward": 3, "reverse": 0}])
        )
        assert any(e.code == "FLB2_EMPTY_STEP_EVENT" for e in errors)

    def test_valid_event_no_flb2_error(self) -> None:
        """A valid event name must not produce an FLB2 error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark())
        assert "FLB2_EMPTY_STEP_EVENT" not in _codes(errors)

    def test_flb2_error_path_includes_index(self) -> None:
        """The FLB2 error path must include the step index."""
        errors = validate_flow_bookmark(
            _valid_flow_bookmark(
                steps=[
                    {"event": "Purchase", "forward": 3, "reverse": 0},
                    {"event": "", "forward": 3, "reverse": 0},
                ]
            )
        )
        flb2_errors = [e for e in errors if e.code == "FLB2_EMPTY_STEP_EVENT"]
        assert len(flb2_errors) == 1
        assert flb2_errors[0].path == "steps[1].event"


# =============================================================================
# T018: FLB3 — count_type must be valid
# =============================================================================


class TestValidateFlowBookmarkFLB3:
    """Tests for FLB3: count_type must be a valid enum value."""

    def test_invalid_count_type_returns_flb3_error(self) -> None:
        """An invalid count_type must produce an FLB3_INVALID_COUNT_TYPE error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(count_type="invalid"))
        assert any(e.code == "FLB3_INVALID_COUNT_TYPE" for e in errors)

    def test_valid_count_type_unique_no_error(self) -> None:
        """count_type='unique' must not produce an FLB3 error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(count_type="unique"))
        assert "FLB3_INVALID_COUNT_TYPE" not in _codes(errors)

    def test_valid_count_type_total_no_error(self) -> None:
        """count_type='total' must not produce an FLB3 error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(count_type="total"))
        assert "FLB3_INVALID_COUNT_TYPE" not in _codes(errors)

    def test_valid_count_type_session_no_error(self) -> None:
        """count_type='session' must not produce an FLB3 error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(count_type="session"))
        assert "FLB3_INVALID_COUNT_TYPE" not in _codes(errors)

    def test_flb3_close_match_has_suggestion(self) -> None:
        """A close-match count_type must include a suggestion."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(count_type="uniqe"))
        flb3_errors = [e for e in errors if e.code == "FLB3_INVALID_COUNT_TYPE"]
        assert len(flb3_errors) == 1
        assert flb3_errors[0].suggestion is not None
        assert "unique" in flb3_errors[0].suggestion

    def test_flb3_error_path_is_count_type(self) -> None:
        """The FLB3 error path must point to 'count_type'."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(count_type="bad"))
        flb3_errors = [e for e in errors if e.code == "FLB3_INVALID_COUNT_TYPE"]
        assert len(flb3_errors) == 1
        assert flb3_errors[0].path == "count_type"


# =============================================================================
# T018: FLB4 — chartType must be valid
# =============================================================================


class TestValidateFlowBookmarkFLB4:
    """Tests for FLB4: chartType must be a valid enum value."""

    def test_invalid_chart_type_returns_flb4_error(self) -> None:
        """An invalid chartType must produce an FLB4_INVALID_CHART_TYPE error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(chartType="invalid"))
        assert any(e.code == "FLB4_INVALID_CHART_TYPE" for e in errors)

    def test_valid_chart_type_sankey_no_error(self) -> None:
        """chartType='sankey' must not produce an FLB4 error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(chartType="sankey"))
        assert "FLB4_INVALID_CHART_TYPE" not in _codes(errors)

    def test_valid_chart_type_top_paths_no_error(self) -> None:
        """chartType='top-paths' must not produce an FLB4 error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(chartType="top-paths"))
        assert "FLB4_INVALID_CHART_TYPE" not in _codes(errors)

    def test_valid_chart_type_tree_no_error(self) -> None:
        """chartType='tree' must not produce an FLB4 error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(chartType="tree"))
        assert "FLB4_INVALID_CHART_TYPE" not in _codes(errors)

    def test_flb4_close_match_has_suggestion(self) -> None:
        """A close-match chartType must include a suggestion."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(chartType="sanke"))
        flb4_errors = [e for e in errors if e.code == "FLB4_INVALID_CHART_TYPE"]
        assert len(flb4_errors) == 1
        assert flb4_errors[0].suggestion is not None
        assert "sankey" in flb4_errors[0].suggestion

    def test_flb4_error_path_is_chart_type(self) -> None:
        """The FLB4 error path must point to 'chartType'."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(chartType="bad"))
        flb4_errors = [e for e in errors if e.code == "FLB4_INVALID_CHART_TYPE"]
        assert len(flb4_errors) == 1
        assert flb4_errors[0].path == "chartType"


# =============================================================================
# T018: FLB5 — date_range must be present
# =============================================================================


class TestValidateFlowBookmarkFLB5:
    """Tests for FLB5: date_range must be present in bookmark params."""

    def test_missing_date_range_returns_flb5_error(self) -> None:
        """A missing date_range must produce an FLB5_MISSING_DATE_RANGE error."""
        params = _valid_flow_bookmark()
        del params["date_range"]
        errors = validate_flow_bookmark(params)
        assert any(e.code == "FLB5_MISSING_DATE_RANGE" for e in errors)

    def test_present_date_range_no_flb5_error(self) -> None:
        """A present date_range must not produce an FLB5 error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark())
        assert "FLB5_MISSING_DATE_RANGE" not in _codes(errors)

    def test_flb5_error_path_is_date_range(self) -> None:
        """The FLB5 error path must point to 'date_range'."""
        params = _valid_flow_bookmark()
        del params["date_range"]
        errors = validate_flow_bookmark(params)
        flb5_errors = [e for e in errors if e.code == "FLB5_MISSING_DATE_RANGE"]
        assert len(flb5_errors) == 1
        assert flb5_errors[0].path == "date_range"


# =============================================================================
# T018: FLB6 — version must be 2
# =============================================================================


class TestValidateFlowBookmarkFLB6:
    """Tests for FLB6: version must be 2."""

    def test_version_one_returns_flb6_error(self) -> None:
        """version=1 must produce an FLB6_INVALID_VERSION error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(version=1))
        assert any(e.code == "FLB6_INVALID_VERSION" for e in errors)

    def test_version_three_returns_flb6_error(self) -> None:
        """version=3 must produce an FLB6_INVALID_VERSION error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(version=3))
        assert any(e.code == "FLB6_INVALID_VERSION" for e in errors)

    def test_version_two_no_flb6_error(self) -> None:
        """version=2 must not produce an FLB6 error."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(version=2))
        assert "FLB6_INVALID_VERSION" not in _codes(errors)

    def test_missing_version_returns_flb6_error(self) -> None:
        """A missing version key must produce an FLB6_INVALID_VERSION error."""
        params = _valid_flow_bookmark()
        del params["version"]
        errors = validate_flow_bookmark(params)
        assert any(e.code == "FLB6_INVALID_VERSION" for e in errors)

    def test_flb6_error_path_is_version(self) -> None:
        """The FLB6 error path must point to 'version'."""
        errors = validate_flow_bookmark(_valid_flow_bookmark(version=1))
        flb6_errors = [e for e in errors if e.code == "FLB6_INVALID_VERSION"]
        assert len(flb6_errors) == 1
        assert flb6_errors[0].path == "version"


# =============================================================================
# T018: All defaults pass
# =============================================================================


class TestValidateFlowBookmarkDefaults:
    """Tests that default valid bookmark params produce no errors."""

    def test_all_defaults_pass_validation(self) -> None:
        """Default valid bookmark params must produce no errors."""
        errors = validate_flow_bookmark(_valid_flow_bookmark())
        assert errors == []


# =============================================================================
# T016: time_comparison validation for flows
# =============================================================================


class TestValidateFlowArgsTimeComparison:
    """Tests that validate_flow_args rejects time_comparison for flows."""

    def test_time_comparison_set_produces_error(self) -> None:
        """validate_flow_args() with time_comparison set produces a validation error."""
        from mixpanel_headless.types import TimeComparison

        tc = TimeComparison.relative("month")
        args = _valid_flow_args(time_comparison=tc)
        errors = validate_flow_args(**args)
        assert any(e.code == "FL_TIME_COMPARISON_NOT_SUPPORTED" for e in errors), (
            f"Expected FL_TIME_COMPARISON_NOT_SUPPORTED error, got: {errors}"
        )

    def test_time_comparison_none_no_error(self) -> None:
        """validate_flow_args() with time_comparison=None produces no error for it."""
        args = _valid_flow_args(time_comparison=None)
        errors = validate_flow_args(**args)
        assert not any(e.code == "FL_TIME_COMPARISON_NOT_SUPPORTED" for e in errors)

    def test_time_comparison_error_path(self) -> None:
        """The FL_TIME_COMPARISON_NOT_SUPPORTED error path points to 'time_comparison'."""
        from mixpanel_headless.types import TimeComparison

        tc = TimeComparison.relative("month")
        args = _valid_flow_args(time_comparison=tc)
        errors = validate_flow_args(**args)
        tc_errors = [e for e in errors if e.code == "FL_TIME_COMPARISON_NOT_SUPPORTED"]
        assert len(tc_errors) == 1
        assert tc_errors[0].path == "time_comparison"


# =============================================================================
# T036: data_group_id validation for flows
# =============================================================================


class TestDataGroupIdValidationFlow:
    """Tests for data_group_id validation in validate_flow_args (T036)."""

    def test_valid_data_group_id(self) -> None:
        """Positive integer data_group_id passes flow validation."""
        errors = validate_flow_args(**_valid_flow_args(data_group_id=5))
        assert not any(e.code == "DG1_INVALID_DATA_GROUP_ID" for e in errors)

    def test_none_data_group_id(self) -> None:
        """None data_group_id passes flow validation."""
        errors = validate_flow_args(**_valid_flow_args(data_group_id=None))
        assert not any(e.code == "DG1_INVALID_DATA_GROUP_ID" for e in errors)

    def test_zero_data_group_id(self) -> None:
        """data_group_id=0 fails flow validation."""
        errors = validate_flow_args(**_valid_flow_args(data_group_id=0))
        dg_errors = [e for e in errors if e.code == "DG1_INVALID_DATA_GROUP_ID"]
        assert len(dg_errors) == 1

    def test_negative_data_group_id(self) -> None:
        """Negative data_group_id fails flow validation."""
        errors = validate_flow_args(**_valid_flow_args(data_group_id=-1))
        dg_errors = [e for e in errors if e.code == "DG1_INVALID_DATA_GROUP_ID"]
        assert len(dg_errors) == 1
