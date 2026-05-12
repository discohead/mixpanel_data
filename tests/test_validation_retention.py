"""Unit tests for retention argument validation rules (R1-R12).

Tests ``validate_retention_args()`` which validates Python-level arguments
before retention bookmark construction. Each rule class covers one or more
validation rules, plus delegation tests verify shared validators are called.

Validation rules:
    R1: born_event must be a non-empty string (no control chars, no invisible-only).
    R2: return_event must be a non-empty string (no control chars, no invisible-only).
    R3: Time validation (delegated to ``validate_time_args``).
    R4: Group-by validation (delegated to ``validate_group_by_args``).
    R5: bucket_sizes values must be positive integers.
    R6: bucket_sizes must be in strictly ascending order.
    R7: retention_unit must be in {"day", "week", "month"}.
    R8: alignment must be in {"birth", "interval_start"}.
    R9: math must be in {"retention_rate", "unique"}.
    R10: mode must be in {"curve", "trends", "table"}.
    R11: unit must be in {"day", "week", "month"}.
    R12: group_by strings must be non-empty.

Also tests multi-error collection (fail-fast validation).
"""

from __future__ import annotations

from typing import Any

import pytest

from mixpanel_headless._internal.validation import validate_retention_args
from mixpanel_headless.exceptions import ValidationError
from mixpanel_headless.types import GroupBy

# =============================================================================
# Helpers
# =============================================================================


def _valid_retention_args(**overrides: Any) -> dict[str, Any]:
    """Build a default-valid kwargs dict for ``validate_retention_args``.

    All defaults pass validation. Override individual keys to inject
    specific invalid values for targeted testing.

    Args:
        **overrides: Keyword arguments to override in the defaults.

    Returns:
        Dict suitable for unpacking into ``validate_retention_args(**d)``.
    """
    defaults: dict[str, Any] = {
        "born_event": "Signup",
        "return_event": "Login",
        "retention_unit": "week",
        "alignment": "birth",
        "bucket_sizes": None,
        "math": "retention_rate",
        "mode": "curve",
        "unit": "day",
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
# T011: R1 — born_event must be non-empty string
# =============================================================================


class TestValidateRetentionR1:
    """Tests for R1: born_event must be a non-empty, visible string."""

    def test_empty_born_event_returns_r1_error(self) -> None:
        """An empty string born_event must produce an R1_EMPTY_BORN_EVENT error."""
        errors = validate_retention_args(**_valid_retention_args(born_event=""))
        assert any(e.code == "R1_EMPTY_BORN_EVENT" for e in errors)

    def test_whitespace_only_born_event_returns_r1_error(self) -> None:
        """A whitespace-only born_event must produce an R1_EMPTY_BORN_EVENT error."""
        errors = validate_retention_args(**_valid_retention_args(born_event="   "))
        assert any(e.code == "R1_EMPTY_BORN_EVENT" for e in errors)

    def test_tab_only_born_event_returns_r1_error(self) -> None:
        """A tab-only born_event must produce an R1_EMPTY_BORN_EVENT error."""
        errors = validate_retention_args(**_valid_retention_args(born_event="\t\t"))
        assert any(e.code == "R1_EMPTY_BORN_EVENT" for e in errors)

    def test_control_char_in_born_event_returns_r1_control_error(self) -> None:
        """A born_event containing a null byte must produce R1_CONTROL_CHAR_BORN_EVENT."""
        errors = validate_retention_args(
            **_valid_retention_args(born_event="Sign\x00up")
        )
        assert any(e.code == "R1_CONTROL_CHAR_BORN_EVENT" for e in errors)

    def test_bell_char_in_born_event_returns_r1_control_error(self) -> None:
        """A born_event containing a bell character must produce R1_CONTROL_CHAR_BORN_EVENT."""
        errors = validate_retention_args(
            **_valid_retention_args(born_event="Sign\x07up")
        )
        assert any(e.code == "R1_CONTROL_CHAR_BORN_EVENT" for e in errors)

    def test_invisible_only_born_event_returns_r1_invisible_error(self) -> None:
        """A born_event with only zero-width spaces must produce R1_INVISIBLE_BORN_EVENT."""
        errors = validate_retention_args(**_valid_retention_args(born_event="\u200b"))
        assert any(e.code == "R1_INVISIBLE_BORN_EVENT" for e in errors)

    def test_zero_width_joiner_only_returns_r1_invisible_error(self) -> None:
        """A born_event with only zero-width joiners must produce R1_INVISIBLE_BORN_EVENT."""
        errors = validate_retention_args(
            **_valid_retention_args(born_event="\u200d\u200d")
        )
        assert any(e.code == "R1_INVISIBLE_BORN_EVENT" for e in errors)

    def test_valid_born_event_no_r1_error(self) -> None:
        """A valid born_event must not produce any R1 errors."""
        errors = validate_retention_args(**_valid_retention_args(born_event="Signup"))
        r1_codes = {
            "R1_EMPTY_BORN_EVENT",
            "R1_CONTROL_CHAR_BORN_EVENT",
            "R1_INVISIBLE_BORN_EVENT",
        }
        assert not any(e.code in r1_codes for e in errors)

    def test_born_event_with_spaces_is_valid(self) -> None:
        """A born_event with spaces between visible chars must not produce R1 errors."""
        errors = validate_retention_args(
            **_valid_retention_args(born_event="User Signup")
        )
        r1_codes = {
            "R1_EMPTY_BORN_EVENT",
            "R1_CONTROL_CHAR_BORN_EVENT",
            "R1_INVISIBLE_BORN_EVENT",
        }
        assert not any(e.code in r1_codes for e in errors)

    def test_r1_error_path_is_born_event(self) -> None:
        """The R1 error path must point to 'born_event'."""
        errors = validate_retention_args(**_valid_retention_args(born_event=""))
        r1_errors = [e for e in errors if e.code == "R1_EMPTY_BORN_EVENT"]
        assert len(r1_errors) == 1
        assert r1_errors[0].path == "born_event"


# =============================================================================
# T012: R2 — return_event must be non-empty string
# =============================================================================


class TestValidateRetentionR2:
    """Tests for R2: return_event must be a non-empty, visible string."""

    def test_empty_return_event_returns_r2_error(self) -> None:
        """An empty string return_event must produce an R2_EMPTY_RETURN_EVENT error."""
        errors = validate_retention_args(**_valid_retention_args(return_event=""))
        assert any(e.code == "R2_EMPTY_RETURN_EVENT" for e in errors)

    def test_whitespace_only_return_event_returns_r2_error(self) -> None:
        """A whitespace-only return_event must produce an R2_EMPTY_RETURN_EVENT error."""
        errors = validate_retention_args(**_valid_retention_args(return_event="   "))
        assert any(e.code == "R2_EMPTY_RETURN_EVENT" for e in errors)

    def test_tab_only_return_event_returns_r2_error(self) -> None:
        """A tab-only return_event must produce an R2_EMPTY_RETURN_EVENT error."""
        errors = validate_retention_args(**_valid_retention_args(return_event="\t\t"))
        assert any(e.code == "R2_EMPTY_RETURN_EVENT" for e in errors)

    def test_control_char_in_return_event_returns_r2_control_error(self) -> None:
        """A return_event containing a null byte must produce R2_CONTROL_CHAR_RETURN_EVENT."""
        errors = validate_retention_args(
            **_valid_retention_args(return_event="Log\x00in")
        )
        assert any(e.code == "R2_CONTROL_CHAR_RETURN_EVENT" for e in errors)

    def test_escape_char_in_return_event_returns_r2_control_error(self) -> None:
        """A return_event containing an escape char must produce R2_CONTROL_CHAR_RETURN_EVENT."""
        errors = validate_retention_args(
            **_valid_retention_args(return_event="Log\x1bin")
        )
        assert any(e.code == "R2_CONTROL_CHAR_RETURN_EVENT" for e in errors)

    def test_invisible_only_return_event_returns_r2_invisible_error(self) -> None:
        """A return_event with only zero-width spaces must produce R2_INVISIBLE_RETURN_EVENT."""
        errors = validate_retention_args(**_valid_retention_args(return_event="\u200b"))
        assert any(e.code == "R2_INVISIBLE_RETURN_EVENT" for e in errors)

    def test_zero_width_non_joiner_only_returns_r2_invisible_error(self) -> None:
        """A return_event with only zero-width non-joiners must produce R2_INVISIBLE_RETURN_EVENT."""
        errors = validate_retention_args(
            **_valid_retention_args(return_event="\u200c\u200c")
        )
        assert any(e.code == "R2_INVISIBLE_RETURN_EVENT" for e in errors)

    def test_valid_return_event_no_r2_error(self) -> None:
        """A valid return_event must not produce any R2 errors."""
        errors = validate_retention_args(**_valid_retention_args(return_event="Login"))
        r2_codes = {
            "R2_EMPTY_RETURN_EVENT",
            "R2_CONTROL_CHAR_RETURN_EVENT",
            "R2_INVISIBLE_RETURN_EVENT",
        }
        assert not any(e.code in r2_codes for e in errors)

    def test_return_event_with_unicode_is_valid(self) -> None:
        """A return_event with visible unicode chars must not produce R2 errors."""
        errors = validate_retention_args(
            **_valid_retention_args(return_event="Compra Realizada")
        )
        r2_codes = {
            "R2_EMPTY_RETURN_EVENT",
            "R2_CONTROL_CHAR_RETURN_EVENT",
            "R2_INVISIBLE_RETURN_EVENT",
        }
        assert not any(e.code in r2_codes for e in errors)

    def test_r2_error_path_is_return_event(self) -> None:
        """The R2 error path must point to 'return_event'."""
        errors = validate_retention_args(**_valid_retention_args(return_event=""))
        r2_errors = [e for e in errors if e.code == "R2_EMPTY_RETURN_EVENT"]
        assert len(r2_errors) == 1
        assert r2_errors[0].path == "return_event"


# =============================================================================
# T013: R7/R8/R9 — enum validations with fuzzy suggestion
# =============================================================================


class TestValidateRetentionR7R8R9:
    """Tests for R7 (retention_unit), R8 (alignment), R9 (math) enum validation."""

    # -- R7: retention_unit --

    def test_invalid_retention_unit_returns_r7_error(self) -> None:
        """An invalid retention_unit must produce an R7_INVALID_RETENTION_UNIT error."""
        errors = validate_retention_args(
            **_valid_retention_args(retention_unit="invalid")
        )
        assert any(e.code == "R7_INVALID_RETENTION_UNIT" for e in errors)

    def test_valid_retention_unit_day_no_r7_error(self) -> None:
        """retention_unit='day' must not produce an R7 error."""
        errors = validate_retention_args(**_valid_retention_args(retention_unit="day"))
        assert "R7_INVALID_RETENTION_UNIT" not in _codes(errors)

    def test_valid_retention_unit_week_no_r7_error(self) -> None:
        """retention_unit='week' must not produce an R7 error."""
        errors = validate_retention_args(**_valid_retention_args(retention_unit="week"))
        assert "R7_INVALID_RETENTION_UNIT" not in _codes(errors)

    def test_valid_retention_unit_month_no_r7_error(self) -> None:
        """retention_unit='month' must not produce an R7 error."""
        errors = validate_retention_args(
            **_valid_retention_args(retention_unit="month")
        )
        assert "R7_INVALID_RETENTION_UNIT" not in _codes(errors)

    def test_retention_unit_close_match_has_suggestion(self) -> None:
        """A close-match retention_unit must include a suggestion."""
        errors = validate_retention_args(**_valid_retention_args(retention_unit="wek"))
        r7_errors = [e for e in errors if e.code == "R7_INVALID_RETENTION_UNIT"]
        assert len(r7_errors) == 1
        assert r7_errors[0].suggestion is not None
        assert "week" in r7_errors[0].suggestion

    def test_retention_unit_case_sensitive(self) -> None:
        """retention_unit='Week' (wrong case) must produce an R7 error."""
        errors = validate_retention_args(**_valid_retention_args(retention_unit="Week"))
        assert any(e.code == "R7_INVALID_RETENTION_UNIT" for e in errors)

    def test_r7_error_path_is_retention_unit(self) -> None:
        """The R7 error path must point to 'retention_unit'."""
        errors = validate_retention_args(
            **_valid_retention_args(retention_unit="invalid")
        )
        r7_errors = [e for e in errors if e.code == "R7_INVALID_RETENTION_UNIT"]
        assert len(r7_errors) == 1
        assert r7_errors[0].path == "retention_unit"

    # -- R8: alignment --

    def test_invalid_alignment_returns_r8_error(self) -> None:
        """An invalid alignment must produce an R8_INVALID_ALIGNMENT error."""
        errors = validate_retention_args(**_valid_retention_args(alignment="invalid"))
        assert any(e.code == "R8_INVALID_ALIGNMENT" for e in errors)

    def test_valid_alignment_birth_no_r8_error(self) -> None:
        """alignment='birth' must not produce an R8 error."""
        errors = validate_retention_args(**_valid_retention_args(alignment="birth"))
        assert "R8_INVALID_ALIGNMENT" not in _codes(errors)

    def test_valid_alignment_interval_start_no_r8_error(self) -> None:
        """alignment='interval_start' must not produce an R8 error."""
        errors = validate_retention_args(
            **_valid_retention_args(alignment="interval_start")
        )
        assert "R8_INVALID_ALIGNMENT" not in _codes(errors)

    def test_alignment_close_match_has_suggestion(self) -> None:
        """A close-match alignment must include a suggestion."""
        errors = validate_retention_args(**_valid_retention_args(alignment="brith"))
        r8_errors = [e for e in errors if e.code == "R8_INVALID_ALIGNMENT"]
        assert len(r8_errors) == 1
        assert r8_errors[0].suggestion is not None
        assert "birth" in r8_errors[0].suggestion

    def test_alignment_case_sensitive(self) -> None:
        """alignment='Birth' (wrong case) must produce an R8 error."""
        errors = validate_retention_args(**_valid_retention_args(alignment="Birth"))
        assert any(e.code == "R8_INVALID_ALIGNMENT" for e in errors)

    def test_r8_error_path_is_alignment(self) -> None:
        """The R8 error path must point to 'alignment'."""
        errors = validate_retention_args(**_valid_retention_args(alignment="invalid"))
        r8_errors = [e for e in errors if e.code == "R8_INVALID_ALIGNMENT"]
        assert len(r8_errors) == 1
        assert r8_errors[0].path == "alignment"

    # -- R9: math --

    def test_invalid_math_returns_r9_error(self) -> None:
        """An invalid math must produce an R9_INVALID_MATH error."""
        errors = validate_retention_args(**_valid_retention_args(math="invalid"))
        assert any(e.code == "R9_INVALID_MATH" for e in errors)

    def test_valid_math_retention_rate_no_r9_error(self) -> None:
        """math='retention_rate' must not produce an R9 error."""
        errors = validate_retention_args(**_valid_retention_args(math="retention_rate"))
        assert "R9_INVALID_MATH" not in _codes(errors)

    def test_valid_math_unique_no_r9_error(self) -> None:
        """math='unique' must not produce an R9 error."""
        errors = validate_retention_args(**_valid_retention_args(math="unique"))
        assert "R9_INVALID_MATH" not in _codes(errors)

    def test_math_close_match_has_suggestion(self) -> None:
        """A close-match math must include a suggestion."""
        errors = validate_retention_args(**_valid_retention_args(math="uniue"))
        r9_errors = [e for e in errors if e.code == "R9_INVALID_MATH"]
        assert len(r9_errors) == 1
        assert r9_errors[0].suggestion is not None
        assert "unique" in r9_errors[0].suggestion

    def test_math_case_sensitive(self) -> None:
        """math='Unique' (wrong case) must produce an R9 error."""
        errors = validate_retention_args(**_valid_retention_args(math="Unique"))
        assert any(e.code == "R9_INVALID_MATH" for e in errors)

    def test_r9_error_path_is_math(self) -> None:
        """The R9 error path must point to 'math'."""
        errors = validate_retention_args(**_valid_retention_args(math="invalid"))
        r9_errors = [e for e in errors if e.code == "R9_INVALID_MATH"]
        assert len(r9_errors) == 1
        assert r9_errors[0].path == "math"

    # -- All defaults pass --

    def test_all_defaults_pass_validation(self) -> None:
        """Default valid args must produce no errors."""
        errors = validate_retention_args(**_valid_retention_args())
        assert errors == []


# =============================================================================
# T014: R3/R4 — delegation to shared validators
# =============================================================================


class TestValidateRetentionDelegation:
    """Tests for R3 (time) and R4 (group-by) delegation to shared validators."""

    # -- R3: time validation delegated to validate_time_args --

    def test_zero_last_returns_v7_error(self) -> None:
        """A zero last value must produce a V7_LAST_POSITIVE error (delegated)."""
        errors = validate_retention_args(**_valid_retention_args(last=0))
        assert any(e.code == "V7_LAST_POSITIVE" for e in errors)

    def test_negative_last_returns_v7_error(self) -> None:
        """A negative last value must produce a V7_LAST_POSITIVE error (delegated)."""
        errors = validate_retention_args(**_valid_retention_args(last=-5))
        assert any(e.code == "V7_LAST_POSITIVE" for e in errors)

    def test_positive_last_no_v7_error(self) -> None:
        """A positive last value must not produce a V7_LAST_POSITIVE error."""
        errors = validate_retention_args(**_valid_retention_args(last=30))
        assert "V7_LAST_POSITIVE" not in _codes(errors)

    def test_invalid_from_date_format_returns_v8_error(self) -> None:
        """An invalid from_date format must produce a V8_DATE_FORMAT error (delegated)."""
        errors = validate_retention_args(**_valid_retention_args(from_date="invalid"))
        assert any(e.code == "V8_DATE_FORMAT" for e in errors)

    def test_to_date_without_from_date_returns_v9_error(self) -> None:
        """Setting to_date without from_date must produce a V9 error (delegated)."""
        errors = validate_retention_args(**_valid_retention_args(to_date="2024-01-31"))
        assert any(e.code == "V9_TO_REQUIRES_FROM" for e in errors)

    def test_valid_date_range_no_time_errors(self) -> None:
        """Valid from_date and to_date must not produce time errors."""
        errors = validate_retention_args(
            **_valid_retention_args(
                from_date="2024-01-01", to_date="2024-01-31", last=30
            )
        )
        time_codes = {"V7_LAST_POSITIVE", "V8_DATE_FORMAT", "V8_DATE_INVALID"}
        assert not any(e.code in time_codes for e in errors)

    def test_no_dates_with_default_last_no_time_errors(self) -> None:
        """Default arguments (no dates, last=30) must not produce time errors."""
        errors = validate_retention_args(**_valid_retention_args())
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
        """from_date after to_date must produce a V15_DATE_ORDER error (delegated)."""
        errors = validate_retention_args(
            **_valid_retention_args(
                from_date="2024-02-01", to_date="2024-01-01", last=30
            )
        )
        assert any(e.code == "V15_DATE_ORDER" for e in errors)

    # -- R4: group-by validation delegated to validate_group_by_args --

    def test_negative_bucket_size_returns_v12_error(self) -> None:
        """A negative bucket_size must be rejected by GroupBy.__post_init__."""
        with pytest.raises(ValueError, match="bucket_size must be positive"):
            GroupBy(
                "revenue",
                property_type="number",
                bucket_size=-1,
                bucket_min=0,
                bucket_max=100,
            )

    def test_zero_bucket_size_returns_v12_error(self) -> None:
        """A zero bucket_size must be rejected by GroupBy.__post_init__."""
        with pytest.raises(ValueError, match="bucket_size must be positive"):
            GroupBy(
                "revenue",
                property_type="number",
                bucket_size=0,
                bucket_min=0,
                bucket_max=100,
            )

    def test_string_group_by_no_errors(self) -> None:
        """A simple string group_by must not produce group-by errors."""
        errors = validate_retention_args(**_valid_retention_args(group_by="platform"))
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
        errors = validate_retention_args(**_valid_retention_args(group_by=None))
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
        errors = validate_retention_args(
            **_valid_retention_args(
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

    def test_bucket_min_exceeds_max_returns_v18_error(self) -> None:
        """bucket_min >= bucket_max must be rejected by GroupBy.__post_init__."""
        with pytest.raises(ValueError, match="bucket_min.*must be less than"):
            GroupBy(
                "revenue",
                property_type="number",
                bucket_size=10,
                bucket_min=100,
                bucket_max=50,
            )

    def test_list_group_by_valid(self) -> None:
        """A list of valid group-by specs must not produce errors."""
        errors = validate_retention_args(
            **_valid_retention_args(group_by=["platform", "country"])
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


# =============================================================================
# T-US3: R5/R6 — bucket_sizes validation
# =============================================================================


class TestValidateRetentionR5R6:
    """Tests for R5 (bucket_sizes positive integers) and R6 (ascending order)."""

    def test_bucket_sizes_positive_integers_pass(self) -> None:
        """Valid positive integer bucket_sizes must produce no R5 errors."""
        errors = validate_retention_args(
            **_valid_retention_args(bucket_sizes=[1, 3, 7])
        )
        assert "R5_BUCKET_SIZES_POSITIVE" not in _codes(errors)
        assert "R5_BUCKET_SIZES_INTEGER" not in _codes(errors)

    def test_bucket_sizes_zero_returns_r5_error(self) -> None:
        """A zero in bucket_sizes must produce an R5_BUCKET_SIZES_POSITIVE error."""
        errors = validate_retention_args(**_valid_retention_args(bucket_sizes=[0, 3]))
        assert any(e.code == "R5_BUCKET_SIZES_POSITIVE" for e in errors)

    def test_bucket_sizes_negative_returns_r5_error(self) -> None:
        """A negative value in bucket_sizes must produce an R5_BUCKET_SIZES_POSITIVE error."""
        errors = validate_retention_args(**_valid_retention_args(bucket_sizes=[-1, 3]))
        assert any(e.code == "R5_BUCKET_SIZES_POSITIVE" for e in errors)

    def test_bucket_sizes_float_returns_r5_error(self) -> None:
        """A float in bucket_sizes must produce an R5_BUCKET_SIZES_INTEGER error."""
        errors = validate_retention_args(**_valid_retention_args(bucket_sizes=[1.5, 3]))
        assert any(e.code == "R5_BUCKET_SIZES_INTEGER" for e in errors)

    def test_bucket_sizes_ascending_pass(self) -> None:
        """Strictly ascending bucket_sizes must produce no R6 errors."""
        errors = validate_retention_args(
            **_valid_retention_args(bucket_sizes=[1, 3, 7, 14])
        )
        assert "R6_BUCKET_SIZES_ASCENDING" not in _codes(errors)

    def test_bucket_sizes_not_ascending_returns_r6_error(self) -> None:
        """Descending bucket_sizes must produce an R6_BUCKET_SIZES_ASCENDING error."""
        errors = validate_retention_args(
            **_valid_retention_args(bucket_sizes=[7, 3, 1])
        )
        assert any(e.code == "R6_BUCKET_SIZES_ASCENDING" for e in errors)

    def test_bucket_sizes_duplicates_returns_r6_error(self) -> None:
        """Duplicate values in bucket_sizes must produce an R6_BUCKET_SIZES_ASCENDING error."""
        errors = validate_retention_args(
            **_valid_retention_args(bucket_sizes=[3, 3, 7])
        )
        assert any(e.code == "R6_BUCKET_SIZES_ASCENDING" for e in errors)

    def test_bucket_sizes_none_no_errors(self) -> None:
        """None bucket_sizes must produce no R5 or R6 errors."""
        errors = validate_retention_args(**_valid_retention_args(bucket_sizes=None))
        r5r6_codes = {
            "R5_BUCKET_SIZES_POSITIVE",
            "R5_BUCKET_SIZES_INTEGER",
            "R6_BUCKET_SIZES_ASCENDING",
        }
        assert not any(e.code in r5r6_codes for e in errors)

    def test_bucket_sizes_with_invalid_types_skips_r6(self) -> None:
        """When bucket_sizes has invalid types, R6 ascending check is skipped."""
        errors = validate_retention_args(
            **_valid_retention_args(bucket_sizes=[3, 1.5, 7])
        )
        assert any(e.code == "R5_BUCKET_SIZES_INTEGER" for e in errors)
        assert "R6_BUCKET_SIZES_ASCENDING" not in _codes(errors)

    def test_bucket_sizes_with_non_positive_skips_r6(self) -> None:
        """When bucket_sizes has non-positive values, R6 ascending check is skipped."""
        errors = validate_retention_args(
            **_valid_retention_args(bucket_sizes=[0, -1, 3])
        )
        assert any(e.code == "R5_BUCKET_SIZES_POSITIVE" for e in errors)
        assert "R6_BUCKET_SIZES_ASCENDING" not in _codes(errors)


# =============================================================================
# T-US5: Multi-error collection
# =============================================================================


class TestValidateRetentionMultiError:
    """Tests for fail-fast validation collecting multiple errors."""

    def test_multiple_errors_collected(self) -> None:
        """Both empty born_event AND invalid retention_unit must be reported together."""
        errors = validate_retention_args(
            **_valid_retention_args(born_event="", retention_unit="invalid")
        )
        codes = _codes(errors)
        assert "R1_EMPTY_BORN_EVENT" in codes
        assert "R7_INVALID_RETENTION_UNIT" in codes

    def test_three_simultaneous_errors(self) -> None:
        """Three simultaneous validation errors must all be collected."""
        errors = validate_retention_args(
            **_valid_retention_args(
                born_event="",
                return_event="",
                math="invalid",
            )
        )
        codes = _codes(errors)
        assert "R1_EMPTY_BORN_EVENT" in codes
        assert "R2_EMPTY_RETURN_EVENT" in codes
        assert "R9_INVALID_MATH" in codes


# =============================================================================
# R10: mode validation
# =============================================================================


class TestValidateRetentionR10:
    """Tests for R10: mode must be in {curve, trends, table}."""

    def test_invalid_mode_returns_r10_error(self) -> None:
        """An invalid mode must produce an R10_INVALID_MODE error."""
        errors = validate_retention_args(**_valid_retention_args(mode="pwned"))
        assert any(e.code == "R10_INVALID_MODE" for e in errors)

    def test_none_mode_returns_r10_error(self) -> None:
        """None mode must produce an R10_INVALID_MODE error."""
        errors = validate_retention_args(**_valid_retention_args(mode=None))
        assert any(e.code == "R10_INVALID_MODE" for e in errors)

    def test_valid_mode_curve_no_error(self) -> None:
        """mode='curve' must not produce an R10 error."""
        errors = validate_retention_args(**_valid_retention_args(mode="curve"))
        assert "R10_INVALID_MODE" not in _codes(errors)

    def test_valid_mode_trends_no_error(self) -> None:
        """mode='trends' must not produce an R10 error."""
        errors = validate_retention_args(**_valid_retention_args(mode="trends"))
        assert "R10_INVALID_MODE" not in _codes(errors)

    def test_valid_mode_table_no_error(self) -> None:
        """mode='table' must not produce an R10 error."""
        errors = validate_retention_args(**_valid_retention_args(mode="table"))
        assert "R10_INVALID_MODE" not in _codes(errors)

    def test_r10_error_path_is_mode(self) -> None:
        """The R10 error path must point to 'mode'."""
        errors = validate_retention_args(**_valid_retention_args(mode="bad"))
        r10_errors = [e for e in errors if e.code == "R10_INVALID_MODE"]
        assert len(r10_errors) == 1
        assert r10_errors[0].path == "mode"

    def test_mode_close_match_has_suggestion(self) -> None:
        """A close-match mode must include a suggestion."""
        errors = validate_retention_args(**_valid_retention_args(mode="curv"))
        r10_errors = [e for e in errors if e.code == "R10_INVALID_MODE"]
        assert len(r10_errors) == 1
        assert r10_errors[0].suggestion is not None
        assert "curve" in r10_errors[0].suggestion


# =============================================================================
# R5c: bucket_sizes max count
# =============================================================================


class TestValidateRetentionR5c:
    """Tests for R5c: bucket_sizes max count (730)."""

    def test_too_many_buckets_returns_error(self) -> None:
        """More than 730 bucket_sizes must produce R5_BUCKET_SIZES_TOO_MANY."""
        errors = validate_retention_args(
            **_valid_retention_args(bucket_sizes=list(range(1, 1001)))
        )
        assert any(e.code == "R5_BUCKET_SIZES_TOO_MANY" for e in errors)

    def test_730_buckets_no_error(self) -> None:
        """Exactly 730 bucket_sizes must not produce R5_BUCKET_SIZES_TOO_MANY."""
        errors = validate_retention_args(
            **_valid_retention_args(bucket_sizes=list(range(1, 731)))
        )
        assert "R5_BUCKET_SIZES_TOO_MANY" not in _codes(errors)

    def test_error_message_includes_count(self) -> None:
        """The R5c error message must include the actual count."""
        errors = validate_retention_args(
            **_valid_retention_args(bucket_sizes=list(range(1, 1001)))
        )
        r5c = [e for e in errors if e.code == "R5_BUCKET_SIZES_TOO_MANY"]
        assert len(r5c) == 1
        assert "1000" in r5c[0].message


# =============================================================================
# R11: unit validation for retention context
# =============================================================================


class TestValidateRetentionR11:
    """Tests for R11: unit must be in {day, week, month} for retention."""

    def test_invalid_unit_hour_returns_r11_error(self) -> None:
        """unit='hour' must produce R11_INVALID_UNIT for retention queries."""
        errors = validate_retention_args(**_valid_retention_args(unit="hour"))
        assert any(e.code == "R11_INVALID_UNIT" for e in errors)

    def test_invalid_unit_minute_returns_r11_error(self) -> None:
        """unit='minute' must produce R11_INVALID_UNIT for retention queries."""
        errors = validate_retention_args(**_valid_retention_args(unit="minute"))
        assert any(e.code == "R11_INVALID_UNIT" for e in errors)

    def test_invalid_unit_quarter_returns_r11_error(self) -> None:
        """unit='quarter' must produce R11_INVALID_UNIT for retention queries."""
        errors = validate_retention_args(**_valid_retention_args(unit="quarter"))
        assert any(e.code == "R11_INVALID_UNIT" for e in errors)

    def test_valid_unit_day_no_error(self) -> None:
        """unit='day' must not produce R11 error."""
        errors = validate_retention_args(**_valid_retention_args(unit="day"))
        assert "R11_INVALID_UNIT" not in _codes(errors)

    def test_valid_unit_week_no_error(self) -> None:
        """unit='week' must not produce R11 error."""
        errors = validate_retention_args(**_valid_retention_args(unit="week"))
        assert "R11_INVALID_UNIT" not in _codes(errors)

    def test_valid_unit_month_no_error(self) -> None:
        """unit='month' must not produce R11 error."""
        errors = validate_retention_args(**_valid_retention_args(unit="month"))
        assert "R11_INVALID_UNIT" not in _codes(errors)

    def test_r11_error_path_is_unit(self) -> None:
        """The R11 error path must point to 'unit'."""
        errors = validate_retention_args(**_valid_retention_args(unit="hour"))
        r11 = [e for e in errors if e.code == "R11_INVALID_UNIT"]
        assert len(r11) == 1
        assert r11[0].path == "unit"

    def test_r11_has_suggestion_for_close_match(self) -> None:
        """A close-match unit must include a suggestion."""
        errors = validate_retention_args(**_valid_retention_args(unit="dya"))
        r11 = [e for e in errors if e.code == "R11_INVALID_UNIT"]
        assert len(r11) == 1
        assert r11[0].suggestion is not None
        assert "day" in r11[0].suggestion


# =============================================================================
# R12: group_by empty string validation
# =============================================================================


class TestValidateRetentionR12:
    """Tests for R12: group_by strings must be non-empty."""

    def test_empty_string_group_by_returns_r12_error(self) -> None:
        """An empty string group_by must produce R12_EMPTY_GROUP_BY."""
        errors = validate_retention_args(**_valid_retention_args(group_by=""))
        assert any(e.code == "R12_EMPTY_GROUP_BY" for e in errors)

    def test_whitespace_only_group_by_returns_r12_error(self) -> None:
        """A whitespace-only group_by must produce R12_EMPTY_GROUP_BY."""
        errors = validate_retention_args(**_valid_retention_args(group_by="   "))
        assert any(e.code == "R12_EMPTY_GROUP_BY" for e in errors)

    def test_empty_string_in_list_returns_r12_error(self) -> None:
        """An empty string in a group_by list must produce R12_EMPTY_GROUP_BY."""
        errors = validate_retention_args(
            **_valid_retention_args(group_by=["platform", ""])
        )
        assert any(e.code == "R12_EMPTY_GROUP_BY" for e in errors)

    def test_valid_group_by_no_r12_error(self) -> None:
        """A valid group_by string must not produce R12 error."""
        errors = validate_retention_args(**_valid_retention_args(group_by="platform"))
        assert "R12_EMPTY_GROUP_BY" not in _codes(errors)

    def test_r12_error_path_is_group_by(self) -> None:
        """The R12 error path must point to 'group_by'."""
        errors = validate_retention_args(**_valid_retention_args(group_by=""))
        r12 = [e for e in errors if e.code == "R12_EMPTY_GROUP_BY"]
        assert len(r12) == 1
        assert r12[0].path == "group_by"


# =============================================================================
# R5: bucket_sizes boolean edge case
# =============================================================================


# =============================================================================
# T010: R13 — unbounded_mode validation
# =============================================================================


class TestValidateRetentionR13UnboundedMode:
    """Tests for R13: unbounded_mode validation."""

    def test_valid_unbounded_mode_none_no_error(self) -> None:
        """unbounded_mode='none' must not produce R13 error."""
        errors = validate_retention_args(**_valid_retention_args(unbounded_mode="none"))
        assert "R13_INVALID_UNBOUNDED_MODE" not in _codes(errors)

    def test_valid_unbounded_mode_carry_back_no_error(self) -> None:
        """unbounded_mode='carry_back' must not produce R13 error."""
        errors = validate_retention_args(
            **_valid_retention_args(unbounded_mode="carry_back")
        )
        assert "R13_INVALID_UNBOUNDED_MODE" not in _codes(errors)

    def test_valid_unbounded_mode_carry_forward_no_error(self) -> None:
        """unbounded_mode='carry_forward' must not produce R13 error."""
        errors = validate_retention_args(
            **_valid_retention_args(unbounded_mode="carry_forward")
        )
        assert "R13_INVALID_UNBOUNDED_MODE" not in _codes(errors)

    def test_valid_unbounded_mode_consecutive_forward_no_error(self) -> None:
        """unbounded_mode='consecutive_forward' must not produce R13 error."""
        errors = validate_retention_args(
            **_valid_retention_args(unbounded_mode="consecutive_forward")
        )
        assert "R13_INVALID_UNBOUNDED_MODE" not in _codes(errors)

    def test_none_unbounded_mode_no_error(self) -> None:
        """unbounded_mode=None (default) must not produce R13 error."""
        errors = validate_retention_args(**_valid_retention_args(unbounded_mode=None))
        assert "R13_INVALID_UNBOUNDED_MODE" not in _codes(errors)

    def test_invalid_unbounded_mode_returns_r13_error(self) -> None:
        """unbounded_mode='invalid' must produce R13_INVALID_UNBOUNDED_MODE error."""
        errors = validate_retention_args(
            **_valid_retention_args(unbounded_mode="invalid")
        )
        assert "R13_INVALID_UNBOUNDED_MODE" in _codes(errors)

    def test_r13_error_path_is_unbounded_mode(self) -> None:
        """The R13 error path must point to 'unbounded_mode'."""
        errors = validate_retention_args(**_valid_retention_args(unbounded_mode="bad"))
        r13 = [e for e in errors if e.code == "R13_INVALID_UNBOUNDED_MODE"]
        assert len(r13) == 1
        assert r13[0].path == "unbounded_mode"


class TestValidateRetentionR5Boolean:
    """Tests for R5: boolean values in bucket_sizes are rejected.

    Python's ``bool`` is a subclass of ``int``, so ``True``/``False``
    pass ``isinstance(val, int)``. The validator must explicitly reject
    booleans.
    """

    def test_boolean_true_rejected(self) -> None:
        """bucket_sizes=[True, 3] must produce R5_BUCKET_SIZES_POSITIVE."""
        errors = validate_retention_args(
            **_valid_retention_args(bucket_sizes=[True, 3])
        )
        assert any(e.code == "R5_BUCKET_SIZES_POSITIVE" for e in errors)

    def test_boolean_false_rejected(self) -> None:
        """bucket_sizes=[False] must produce R5_BUCKET_SIZES_POSITIVE."""
        errors = validate_retention_args(**_valid_retention_args(bucket_sizes=[False]))
        assert any(e.code == "R5_BUCKET_SIZES_POSITIVE" for e in errors)


# =============================================================================
# Layer 2: B20/B21 filter validation (via validate_bookmark)
# =============================================================================


class TestValidateBookmarkRetentionB20:
    """Tests for B20: filterValue must not be an empty list.

    These rules apply to all bookmark types. Tested here with
    ``bookmark_type="retention"`` since B20/B21 were added in this PR.
    """

    def test_empty_filter_value_list_rejected(self) -> None:
        """filterValue=[] must produce B20_EMPTY_FILTER_VALUE."""
        from mixpanel_headless._internal.validation import validate_bookmark

        bookmark: dict[str, Any] = {
            "sections": {
                "show": [
                    {
                        "behavior": {
                            "type": "event",
                            "resourceType": "events",
                            "value": {"name": "Signup"},
                        },
                        "measurement": {"math": "retention_rate"},
                    }
                ],
                "time": [{"unit": "day", "dateRangeType": "in the last", "value": 30}],
                "filter": [
                    {
                        "filterType": "string",
                        "filterOperator": "in",
                        "filterValue": [],
                        "propertyObjectKey": "properties",
                        "resourceType": "events",
                        "propertyName": "country",
                    }
                ],
                "group": [],
            },
            "displayOptions": {"chartType": "line", "analysis": "linear"},
        }
        errors = validate_bookmark(bookmark, bookmark_type="retention")
        assert any(e.code == "B20_EMPTY_FILTER_VALUE" for e in errors)


class TestValidateBookmarkRetentionB21:
    """Tests for B21: filterValue list must not exceed max size."""

    def test_filter_value_too_many_rejected(self) -> None:
        """filterValue with >1000 entries must produce B21_FILTER_VALUE_TOO_MANY."""
        from mixpanel_headless._internal.validation import validate_bookmark

        bookmark: dict[str, Any] = {
            "sections": {
                "show": [
                    {
                        "behavior": {
                            "type": "event",
                            "resourceType": "events",
                            "value": {"name": "Signup"},
                        },
                        "measurement": {"math": "retention_rate"},
                    }
                ],
                "time": [{"unit": "day", "dateRangeType": "in the last", "value": 30}],
                "filter": [
                    {
                        "filterType": "string",
                        "filterOperator": "in",
                        "filterValue": [f"val_{i}" for i in range(1001)],
                        "propertyObjectKey": "properties",
                        "resourceType": "events",
                        "propertyName": "country",
                    }
                ],
                "group": [],
            },
            "displayOptions": {"chartType": "line", "analysis": "linear"},
        }
        errors = validate_bookmark(bookmark, bookmark_type="retention")
        assert any(e.code == "B21_FILTER_VALUE_TOO_MANY" for e in errors)


# =============================================================================
# Layer 2: B9 retention math dispatch
# =============================================================================


class TestValidateBookmarkRetentionB9MathDispatch:
    """Tests for B9: retention bookmarks route to VALID_MATH_RETENTION.

    Ensures that insights-only math types (e.g., ``"dau"``) are rejected
    when the bookmark type is ``"retention"``.
    """

    def test_insights_only_math_rejected_for_retention(self) -> None:
        """math='dau' must produce B9_INVALID_MATH for retention bookmarks."""
        from mixpanel_headless._internal.validation import validate_bookmark

        bookmark: dict[str, Any] = {
            "sections": {
                "show": [
                    {
                        "behavior": {
                            "type": "event",
                            "resourceType": "events",
                            "value": {"name": "Signup"},
                        },
                        "measurement": {"math": "dau"},
                    }
                ],
                "time": [{"unit": "day", "dateRangeType": "in the last", "value": 30}],
                "filter": [],
                "group": [],
            },
            "displayOptions": {"chartType": "line", "analysis": "linear"},
        }
        errors = validate_bookmark(bookmark, bookmark_type="retention")
        assert any(e.code == "B9_INVALID_MATH" for e in errors)

    def test_valid_retention_math_accepted(self) -> None:
        """math='retention_rate' must not produce B9_INVALID_MATH for retention."""
        from mixpanel_headless._internal.validation import validate_bookmark

        bookmark: dict[str, Any] = {
            "sections": {
                "show": [
                    {
                        "behavior": {
                            "type": "event",
                            "resourceType": "events",
                            "value": {"name": "Signup"},
                        },
                        "measurement": {"math": "retention_rate"},
                    }
                ],
                "time": [{"unit": "day", "dateRangeType": "in the last", "value": 30}],
                "filter": [],
                "group": [],
            },
            "displayOptions": {"chartType": "line", "analysis": "linear"},
        }
        errors = validate_bookmark(bookmark, bookmark_type="retention")
        assert not any(e.code == "B9_INVALID_MATH" for e in errors)


# =============================================================================
# T036: data_group_id validation for retention
# =============================================================================


class TestDataGroupIdValidationRetention:
    """Tests for data_group_id validation in validate_retention_args (T036)."""

    def test_valid_data_group_id(self) -> None:
        """Positive integer data_group_id passes retention validation."""
        errors = validate_retention_args(**_valid_retention_args(data_group_id=5))
        assert not any(e.code == "DG1_INVALID_DATA_GROUP_ID" for e in errors)

    def test_none_data_group_id(self) -> None:
        """None data_group_id passes retention validation."""
        errors = validate_retention_args(**_valid_retention_args(data_group_id=None))
        assert not any(e.code == "DG1_INVALID_DATA_GROUP_ID" for e in errors)

    def test_zero_data_group_id(self) -> None:
        """data_group_id=0 fails retention validation."""
        errors = validate_retention_args(**_valid_retention_args(data_group_id=0))
        dg_errors = [e for e in errors if e.code == "DG1_INVALID_DATA_GROUP_ID"]
        assert len(dg_errors) == 1

    def test_negative_data_group_id(self) -> None:
        """Negative data_group_id fails retention validation."""
        errors = validate_retention_args(**_valid_retention_args(data_group_id=-2))
        dg_errors = [e for e in errors if e.code == "DG1_INVALID_DATA_GROUP_ID"]
        assert len(dg_errors) == 1
