"""Unit tests for query_user() validation rules.

Tests Layer 1 argument validation (U1-U24) via ``validate_user_args()``
and Layer 2 param validation (UP1-UP4) via ``validate_user_params()``.

Both functions currently raise ``NotImplementedError`` — these tests are
written first per strict TDD. They define the expected behavior and will
fail until implementation is complete.

Pattern follows ``test_validation_cohort.py``.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

from mixpanel_headless._internal.query.user_validators import (
    validate_user_args,
    validate_user_params,
)
from mixpanel_headless.exceptions import ValidationError
from mixpanel_headless.types import CohortCriteria, CohortDefinition, Filter

# =============================================================================
# Helpers
# =============================================================================


def _codes(errors: list[ValidationError]) -> list[str]:
    """Extract error codes from a list of ValidationError objects.

    Args:
        errors: List of validation errors.

    Returns:
        List of error code strings.
    """
    return [e.code for e in errors]


def _has_code(errors: list[ValidationError], code: str) -> bool:
    """Check whether a specific error code appears in the error list.

    Args:
        errors: List of validation errors.
        code: Error code to search for.

    Returns:
        True if the code appears at least once.
    """
    return any(e.code == code for e in errors)


def _only_code(errors: list[ValidationError], code: str) -> bool:
    """Check that exactly one error is present and it has the given code.

    Args:
        errors: List of validation errors.
        code: Expected single error code.

    Returns:
        True if exactly one error with the given code exists.
    """
    return len(errors) == 1 and errors[0].code == code


def _make_cohort_definition() -> CohortDefinition:
    """Build a valid CohortDefinition for testing.

    Returns:
        A CohortDefinition with a single behavioral criterion.
    """
    return CohortDefinition.all_of(
        CohortCriteria.did_event("Purchase", at_least=1, within_days=30),
    )


# =============================================================================
# TestValidateUserArgsValid — Happy-path tests
# =============================================================================


class TestValidateUserArgsValid:
    """Tests that valid argument combinations produce no errors."""

    def test_defaults_are_valid(self) -> None:
        """Default arguments (no overrides) should pass validation."""
        errors = validate_user_args()
        assert errors == []

    def test_profiles_mode_with_filter(self) -> None:
        """Profiles mode with a Filter where clause is valid."""
        errors = validate_user_args(
            where=Filter.equals("plan", "premium"),
            mode="profiles",
        )
        assert errors == []

    def test_profiles_mode_with_string_where(self) -> None:
        """Profiles mode with a raw string where clause is valid."""
        errors = validate_user_args(
            where='properties["plan"] == "premium"',
            mode="profiles",
        )
        assert errors == []

    def test_profiles_mode_with_filter_list(self) -> None:
        """Profiles mode with a list of Filters is valid."""
        errors = validate_user_args(
            where=[
                Filter.equals("plan", "premium"),
                Filter.greater_than("age", 18),
            ],
            mode="profiles",
        )
        assert errors == []

    def test_profiles_mode_with_cohort_id(self) -> None:
        """Profiles mode with a saved cohort ID is valid."""
        errors = validate_user_args(cohort=123, mode="profiles")
        assert errors == []

    def test_profiles_mode_with_cohort_definition(self) -> None:
        """Profiles mode with a CohortDefinition is valid."""
        errors = validate_user_args(
            cohort=_make_cohort_definition(),
            mode="profiles",
        )
        assert errors == []

    def test_profiles_mode_with_properties(self) -> None:
        """Profiles mode with property selection is valid."""
        errors = validate_user_args(
            properties=["$email", "$name"],
            mode="profiles",
        )
        assert errors == []

    def test_profiles_mode_with_sort_by(self) -> None:
        """Profiles mode with sort_by is valid."""
        errors = validate_user_args(sort_by="$last_seen", mode="profiles")
        assert errors == []

    def test_profiles_mode_with_search(self) -> None:
        """Profiles mode with search is valid."""
        errors = validate_user_args(search="john", mode="profiles")
        assert errors == []

    def test_profiles_mode_with_distinct_id(self) -> None:
        """Profiles mode with distinct_id is valid."""
        errors = validate_user_args(distinct_id="user123", mode="profiles")
        assert errors == []

    def test_profiles_mode_with_distinct_ids(self) -> None:
        """Profiles mode with distinct_ids is valid."""
        errors = validate_user_args(
            distinct_ids=["user1", "user2"],
            mode="profiles",
        )
        assert errors == []

    def test_profiles_mode_with_parallel(self) -> None:
        """Profiles mode with parallel=True is valid."""
        errors = validate_user_args(parallel=True, mode="profiles")
        assert errors == []

    def test_profiles_mode_with_as_of_date(self) -> None:
        """Profiles mode with a valid past as_of date is valid."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        errors = validate_user_args(as_of=yesterday, mode="profiles")
        assert errors == []

    def test_profiles_mode_with_as_of_today(self) -> None:
        """Profiles mode with as_of set to today is valid (not future)."""
        today = date.today().isoformat()
        errors = validate_user_args(as_of=today, mode="profiles")
        assert errors == []

    def test_profiles_mode_with_as_of_int(self) -> None:
        """Profiles mode with an integer as_of (timestamp) is valid."""
        errors = validate_user_args(as_of=1700000000, mode="profiles")
        assert errors == []

    def test_aggregate_mode_count(self) -> None:
        """Aggregate mode with count is valid without aggregate_property."""
        errors = validate_user_args(mode="aggregate", aggregate="count")
        assert errors == []

    def test_aggregate_mode_extremes_with_property(self) -> None:
        """Aggregate mode with extremes requires aggregate_property."""
        errors = validate_user_args(
            mode="aggregate",
            aggregate="extremes",
            aggregate_property="ltv",
        )
        assert errors == []

    def test_aggregate_mode_numeric_summary_with_property(self) -> None:
        """Aggregate mode with numeric_summary requires aggregate_property."""
        errors = validate_user_args(
            mode="aggregate",
            aggregate="numeric_summary",
            aggregate_property="revenue",
        )
        assert errors == []

    def test_aggregate_mode_percentile_with_property(self) -> None:
        """Aggregate mode with percentile requires aggregate_property and percentile."""
        errors = validate_user_args(
            mode="aggregate",
            aggregate="percentile",
            aggregate_property="age",
            percentile=50,
        )
        assert errors == []

    def test_aggregate_mode_with_segment_by(self) -> None:
        """Aggregate mode with segment_by is valid."""
        errors = validate_user_args(
            mode="aggregate",
            aggregate="count",
            segment_by=[1, 2, 3],
        )
        assert errors == []

    def test_aggregate_mode_with_cohort_filter(self) -> None:
        """Aggregate mode with cohort param is valid."""
        errors = validate_user_args(
            mode="aggregate",
            aggregate="count",
            cohort=123,
        )
        assert errors == []

    def test_include_all_users_with_cohort(self) -> None:
        """include_all_users with a cohort is valid."""
        errors = validate_user_args(
            cohort=123,
            include_all_users=True,
            mode="profiles",
        )
        assert errors == []

    def test_workers_valid_range(self) -> None:
        """Workers between 1 and 5 are valid."""
        for n in (1, 2, 3, 4, 5):
            errors = validate_user_args(workers=n, mode="profiles")
            assert errors == [], f"workers={n} should be valid"

    def test_single_in_cohort_filter_in_where(self) -> None:
        """A single Filter.in_cohort() in where list is valid."""
        errors = validate_user_args(
            where=[Filter.in_cohort(123)],
            mode="profiles",
        )
        assert errors == []


# =============================================================================
# TestValidateUserArgsMutualExclusion — Rules U1, U2, U9
# =============================================================================


class TestValidateUserArgsMutualExclusion:
    """Tests for mutual exclusion rules U1, U2, U9."""

    def test_u1_distinct_id_and_distinct_ids_mutually_exclusive(self) -> None:
        """U1: distinct_id and distinct_ids cannot both be provided."""
        errors = validate_user_args(
            distinct_id="user1",
            distinct_ids=["user2", "user3"],
            mode="profiles",
        )
        assert _has_code(errors, "U1")

    def test_u1_only_distinct_id_is_valid(self) -> None:
        """U1: distinct_id alone is valid."""
        errors = validate_user_args(distinct_id="user1", mode="profiles")
        assert not _has_code(errors, "U1")

    def test_u1_only_distinct_ids_is_valid(self) -> None:
        """U1: distinct_ids alone is valid."""
        errors = validate_user_args(
            distinct_ids=["user1"],
            mode="profiles",
        )
        assert not _has_code(errors, "U1")

    def test_u2_cohort_and_in_cohort_filter_mutually_exclusive(self) -> None:
        """U2: cohort param and Filter.in_cohort() in where are exclusive."""
        errors = validate_user_args(
            cohort=123,
            where=[Filter.in_cohort(456)],
            mode="profiles",
        )
        assert _has_code(errors, "U2")

    def test_u2_cohort_without_in_cohort_filter_is_valid(self) -> None:
        """U2: cohort param alone (no in_cohort in where) is valid."""
        errors = validate_user_args(
            cohort=123,
            where=Filter.equals("plan", "premium"),
            mode="profiles",
        )
        assert not _has_code(errors, "U2")

    def test_u2_in_cohort_filter_without_cohort_is_valid(self) -> None:
        """U2: Filter.in_cohort() in where without cohort param is valid."""
        errors = validate_user_args(
            where=[Filter.in_cohort(456)],
            mode="profiles",
        )
        assert not _has_code(errors, "U2")

    def test_u2_cohort_definition_and_in_cohort_filter(self) -> None:
        """U2: CohortDefinition cohort and Filter.in_cohort() are exclusive."""
        errors = validate_user_args(
            cohort=_make_cohort_definition(),
            where=[Filter.in_cohort(789)],
            mode="profiles",
        )
        assert _has_code(errors, "U2")

    def test_u9_where_type_is_either_string_or_filter_not_both(self) -> None:
        """U9: where must be either a string or Filter/list[Filter], not mixed.

        Since where is a single parameter, this tests that passing a
        non-Filter, non-string, non-list type is caught.
        """
        # A valid string is fine
        errors_str = validate_user_args(
            where='properties["plan"] == "premium"',
            mode="profiles",
        )
        assert not _has_code(errors_str, "U9")

        # A valid Filter is fine
        errors_filter = validate_user_args(
            where=Filter.equals("plan", "premium"),
            mode="profiles",
        )
        assert not _has_code(errors_filter, "U9")


# =============================================================================
# TestValidateUserArgsBasic — Rules U3-U6, U8, U10, U11, U23
# =============================================================================


class TestValidateUserArgsBasic:
    """Tests for basic value validation rules."""

    def test_u3_limit_must_be_positive(self) -> None:
        """U3: limit must be positive if provided."""
        errors = validate_user_args(limit=0, mode="profiles")
        assert _has_code(errors, "U3")

    def test_u3_negative_limit(self) -> None:
        """U3: negative limit is invalid."""
        errors = validate_user_args(limit=-5, mode="profiles")
        assert _has_code(errors, "U3")

    def test_u3_positive_limit_is_valid(self) -> None:
        """U3: positive limit is valid."""
        errors = validate_user_args(limit=10, mode="profiles")
        assert not _has_code(errors, "U3")

    def test_u3_large_limit_is_valid(self) -> None:
        """U3: Large positive limit is valid."""
        errors = validate_user_args(limit=100_000, mode="profiles")
        assert not _has_code(errors, "U3")

    def test_u4_distinct_ids_must_be_non_empty(self) -> None:
        """U4: distinct_ids must be a non-empty list."""
        errors = validate_user_args(distinct_ids=[], mode="profiles")
        assert _has_code(errors, "U4")

    def test_u4_non_empty_distinct_ids_is_valid(self) -> None:
        """U4: non-empty distinct_ids is valid."""
        errors = validate_user_args(
            distinct_ids=["user1"],
            mode="profiles",
        )
        assert not _has_code(errors, "U4")

    def test_u5_sort_by_must_be_non_empty_string(self) -> None:
        """U5: sort_by must be a non-empty string."""
        errors = validate_user_args(sort_by="", mode="profiles")
        assert _has_code(errors, "U5")

    def test_u5_whitespace_only_sort_by(self) -> None:
        """U5: whitespace-only sort_by is invalid."""
        errors = validate_user_args(sort_by="   ", mode="profiles")
        assert _has_code(errors, "U5")

    def test_u5_valid_sort_by(self) -> None:
        """U5: non-empty sort_by is valid."""
        errors = validate_user_args(sort_by="$last_seen", mode="profiles")
        assert not _has_code(errors, "U5")

    def test_u6_as_of_string_must_be_valid_date(self) -> None:
        """U6: as_of string must be valid YYYY-MM-DD format."""
        errors = validate_user_args(as_of="not-a-date", mode="profiles")
        assert _has_code(errors, "U6")

    def test_u6_invalid_date_format_slash(self) -> None:
        """U6: slash-delimited date is not YYYY-MM-DD."""
        errors = validate_user_args(as_of="2025/01/15", mode="profiles")
        assert _has_code(errors, "U6")

    def test_u6_invalid_calendar_date(self) -> None:
        """U6: valid format but impossible date (Feb 30) is invalid."""
        errors = validate_user_args(as_of="2025-02-30", mode="profiles")
        assert _has_code(errors, "U6")

    def test_u6_valid_date_string(self) -> None:
        """U6: valid YYYY-MM-DD date is accepted."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        errors = validate_user_args(as_of=yesterday, mode="profiles")
        assert not _has_code(errors, "U6")

    def test_u6_integer_as_of_skips_date_validation(self) -> None:
        """U6: integer as_of (timestamp) skips date format validation."""
        errors = validate_user_args(as_of=1700000000, mode="profiles")
        assert not _has_code(errors, "U6")

    def test_u8_as_of_must_not_be_in_future(self) -> None:
        """U8: as_of date must not be in the future."""
        future = (date.today() + timedelta(days=30)).isoformat()
        errors = validate_user_args(as_of=future, mode="profiles")
        assert _has_code(errors, "U8")

    def test_u8_today_is_not_future(self) -> None:
        """U8: today's date is valid (boundary case)."""
        today = date.today().isoformat()
        errors = validate_user_args(as_of=today, mode="profiles")
        assert not _has_code(errors, "U8")

    def test_u8_past_date_is_valid(self) -> None:
        """U8: past date is valid."""
        past = (date.today() - timedelta(days=365)).isoformat()
        errors = validate_user_args(as_of=past, mode="profiles")
        assert not _has_code(errors, "U8")

    def test_u10_filter_property_names_must_be_non_empty(self) -> None:
        """U10: Filter property names must be non-empty strings.

        Uses internal construction to bypass Filter factory validation.
        """
        # Build a Filter with an empty property name directly
        f = Filter(
            _property="",
            _operator="equals",
            _value=["test"],
            _property_type="string",
        )
        errors = validate_user_args(where=f, mode="profiles")
        assert _has_code(errors, "U10")

    def test_u10_filter_with_valid_property_name(self) -> None:
        """U10: Filter with non-empty property name is valid."""
        errors = validate_user_args(
            where=Filter.equals("country", "US"),
            mode="profiles",
        )
        assert not _has_code(errors, "U10")

    def test_u10_filter_list_with_empty_property(self) -> None:
        """U10: Any Filter in a list with empty property triggers U10."""
        f_valid = Filter.equals("plan", "premium")
        f_invalid = Filter(
            _property="",
            _operator="equals",
            _value=["test"],
            _property_type="string",
        )
        errors = validate_user_args(
            where=[f_valid, f_invalid],
            mode="profiles",
        )
        assert _has_code(errors, "U10")

    def test_u29_empty_properties_list(self) -> None:
        """U29: properties must be a non-empty list."""
        errors = validate_user_args(properties=[], mode="profiles")
        assert _has_code(errors, "U29")

    def test_u29_non_empty_properties_is_valid(self) -> None:
        """U29: non-empty properties list is valid."""
        errors = validate_user_args(
            properties=["$email"],
            mode="profiles",
        )
        assert not _has_code(errors, "U29")

    def test_u29_none_properties_is_valid(self) -> None:
        """U29: None properties is valid (optional field)."""
        errors = validate_user_args(properties=None, mode="profiles")
        assert not _has_code(errors, "U29")

    def test_u11_properties_items_must_be_non_empty(self) -> None:
        """U11: items in properties list must be non-empty strings."""
        errors = validate_user_args(
            properties=["$email", ""],
            mode="profiles",
        )
        assert _has_code(errors, "U11")

    def test_u11_whitespace_only_property(self) -> None:
        """U11: whitespace-only property name is invalid."""
        errors = validate_user_args(
            properties=["  "],
            mode="profiles",
        )
        assert _has_code(errors, "U11")

    def test_u11_valid_properties(self) -> None:
        """U11: non-empty property names are valid."""
        errors = validate_user_args(
            properties=["$email", "$name", "plan"],
            mode="profiles",
        )
        assert not _has_code(errors, "U11")

    def test_u23_workers_below_minimum(self) -> None:
        """U23: workers must be at least 1."""
        errors = validate_user_args(workers=0, mode="profiles")
        assert _has_code(errors, "U23")

    def test_u23_workers_negative(self) -> None:
        """U23: negative workers is invalid."""
        errors = validate_user_args(workers=-1, mode="profiles")
        assert _has_code(errors, "U23")

    def test_u23_workers_above_maximum(self) -> None:
        """U23: workers must be at most 5."""
        errors = validate_user_args(workers=6, mode="profiles")
        assert _has_code(errors, "U23")

    def test_u23_workers_at_boundaries(self) -> None:
        """U23: workers at boundaries (1 and 5) are valid."""
        for n in (1, 5):
            errors = validate_user_args(workers=n, mode="profiles")
            assert not _has_code(errors, "U23"), f"workers={n} should be valid"


# =============================================================================
# TestValidateUserArgsCohortDependency — Rules U7, U12, U13, U24
# =============================================================================


class TestValidateUserArgsCohortDependency:
    """Tests for cohort-related validation rules."""

    def test_u7_include_all_users_requires_cohort(self) -> None:
        """U7: include_all_users=True requires cohort param."""
        errors = validate_user_args(
            include_all_users=True,
            mode="profiles",
        )
        assert _has_code(errors, "U7")

    def test_u7_include_all_users_with_cohort_is_valid(self) -> None:
        """U7: include_all_users=True with cohort is valid."""
        errors = validate_user_args(
            include_all_users=True,
            cohort=123,
            mode="profiles",
        )
        assert not _has_code(errors, "U7")

    def test_u7_include_all_users_false_without_cohort_is_valid(self) -> None:
        """U7: include_all_users=False without cohort is valid."""
        errors = validate_user_args(
            include_all_users=False,
            mode="profiles",
        )
        assert not _has_code(errors, "U7")

    def test_u12_not_in_cohort_filter_not_supported(self) -> None:
        """U12: Filter.not_in_cohort() is not supported in where."""
        errors = validate_user_args(
            where=Filter.not_in_cohort(123),
            mode="profiles",
        )
        assert _has_code(errors, "U12")

    def test_u12_not_in_cohort_in_list(self) -> None:
        """U12: Filter.not_in_cohort() in a list is not supported."""
        errors = validate_user_args(
            where=[
                Filter.equals("plan", "premium"),
                Filter.not_in_cohort(123),
            ],
            mode="profiles",
        )
        assert _has_code(errors, "U12")

    def test_u12_in_cohort_is_valid(self) -> None:
        """U12: Filter.in_cohort() (non-negated) is valid."""
        errors = validate_user_args(
            where=Filter.in_cohort(123),
            mode="profiles",
        )
        assert not _has_code(errors, "U12")

    def test_u13_at_most_one_in_cohort_in_where(self) -> None:
        """U13: At most one Filter.in_cohort() allowed in where list."""
        errors = validate_user_args(
            where=[
                Filter.in_cohort(123),
                Filter.in_cohort(456),
            ],
            mode="profiles",
        )
        assert _has_code(errors, "U13")

    def test_u13_single_in_cohort_is_valid(self) -> None:
        """U13: A single Filter.in_cohort() is valid."""
        errors = validate_user_args(
            where=[Filter.in_cohort(123)],
            mode="profiles",
        )
        assert not _has_code(errors, "U13")

    def test_u13_no_in_cohort_is_valid(self) -> None:
        """U13: No Filter.in_cohort() in where is valid."""
        errors = validate_user_args(
            where=[Filter.equals("plan", "premium")],
            mode="profiles",
        )
        assert not _has_code(errors, "U13")

    def test_u24_cohort_definition_to_dict_must_succeed(self) -> None:
        """U24: CohortDefinition.to_dict() must succeed.

        Uses a mock that raises to simulate a broken definition.
        """
        broken = MagicMock(spec=CohortDefinition)
        broken.to_dict.side_effect = ValueError("broken definition")
        errors = validate_user_args(
            cohort=broken,
            mode="profiles",
        )
        assert _has_code(errors, "U24")

    def test_u24_valid_cohort_definition(self) -> None:
        """U24: Valid CohortDefinition passes U24."""
        errors = validate_user_args(
            cohort=_make_cohort_definition(),
            mode="profiles",
        )
        assert not _has_code(errors, "U24")


# =============================================================================
# TestValidateUserArgsAggregateRules — Rules U14, U15, U16, U17
# =============================================================================


class TestValidateUserArgsAggregateRules:
    """Tests for aggregate-mode specific validation rules."""

    def test_u14_aggregate_property_required_for_non_count(self) -> None:
        """U14: aggregate_property is required when aggregate is not 'count'."""
        for agg in ("extremes", "percentile", "numeric_summary"):
            errors = validate_user_args(
                mode="aggregate",
                aggregate=agg,
            )
            assert _has_code(errors, "U14"), (
                f"aggregate='{agg}' without aggregate_property should trigger U14"
            )

    def test_u14_count_without_property_is_valid(self) -> None:
        """U14: aggregate='count' without aggregate_property is valid."""
        errors = validate_user_args(
            mode="aggregate",
            aggregate="count",
        )
        assert not _has_code(errors, "U14")

    def test_u14_extremes_with_property_is_valid(self) -> None:
        """U14: non-count aggregate with aggregate_property is valid."""
        errors = validate_user_args(
            mode="aggregate",
            aggregate="extremes",
            aggregate_property="ltv",
        )
        assert not _has_code(errors, "U14")

    def test_u15_aggregate_property_must_not_be_set_for_count(self) -> None:
        """U15: aggregate_property must not be set when aggregate is 'count'."""
        errors = validate_user_args(
            mode="aggregate",
            aggregate="count",
            aggregate_property="ltv",
        )
        assert _has_code(errors, "U15")

    def test_u15_count_without_property_is_valid(self) -> None:
        """U15: count without aggregate_property is valid."""
        errors = validate_user_args(
            mode="aggregate",
            aggregate="count",
        )
        assert not _has_code(errors, "U15")

    def test_u16_segment_by_requires_aggregate_mode(self) -> None:
        """U16: segment_by requires mode='aggregate'."""
        errors = validate_user_args(
            segment_by=[1, 2],
            mode="profiles",
        )
        assert _has_code(errors, "U16")

    def test_u16_segment_by_in_aggregate_mode_is_valid(self) -> None:
        """U16: segment_by in aggregate mode is valid."""
        errors = validate_user_args(
            segment_by=[1, 2],
            mode="aggregate",
            aggregate="count",
        )
        assert not _has_code(errors, "U16")

    def test_u17_segment_by_ids_must_be_positive(self) -> None:
        """U17: segment_by IDs must be positive integers."""
        errors = validate_user_args(
            segment_by=[1, 0, -1],
            mode="aggregate",
            aggregate="count",
        )
        assert _has_code(errors, "U17")

    def test_u17_zero_id(self) -> None:
        """U17: segment_by with zero ID is invalid."""
        errors = validate_user_args(
            segment_by=[0],
            mode="aggregate",
            aggregate="count",
        )
        assert _has_code(errors, "U17")

    def test_u17_negative_id(self) -> None:
        """U17: segment_by with negative ID is invalid."""
        errors = validate_user_args(
            segment_by=[-5],
            mode="aggregate",
            aggregate="count",
        )
        assert _has_code(errors, "U17")

    def test_u17_all_positive_ids_valid(self) -> None:
        """U17: all positive segment_by IDs are valid."""
        errors = validate_user_args(
            segment_by=[1, 2, 3],
            mode="aggregate",
            aggregate="count",
        )
        assert not _has_code(errors, "U17")


# =============================================================================
# TestValidateUserArgsModeSpecific — Rules U18-U22
# =============================================================================


class TestValidateUserArgsModeSpecific:
    """Tests for mode-specific parameter restrictions.

    Rules U18-U22 ensure profile-only params are not used in aggregate
    mode and vice versa.
    """

    def test_u18_parallel_only_profiles_mode(self) -> None:
        """U18: parallel=True only applies to mode='profiles'."""
        errors = validate_user_args(
            parallel=True,
            mode="aggregate",
            aggregate="count",
        )
        assert _has_code(errors, "U18")

    def test_u18_parallel_in_profiles_mode_is_valid(self) -> None:
        """U18: parallel=True in profiles mode is valid."""
        errors = validate_user_args(parallel=True, mode="profiles")
        assert not _has_code(errors, "U18")

    def test_u18_parallel_false_in_aggregate_is_valid(self) -> None:
        """U18: parallel=False in aggregate mode is valid (default)."""
        errors = validate_user_args(
            parallel=False,
            mode="aggregate",
            aggregate="count",
        )
        assert not _has_code(errors, "U18")

    def test_u19_sort_by_only_profiles_mode(self) -> None:
        """U19: sort_by only applies to mode='profiles'."""
        errors = validate_user_args(
            sort_by="$last_seen",
            mode="aggregate",
            aggregate="count",
        )
        assert _has_code(errors, "U19")

    def test_u19_sort_by_in_profiles_mode_is_valid(self) -> None:
        """U19: sort_by in profiles mode is valid."""
        errors = validate_user_args(sort_by="$last_seen", mode="profiles")
        assert not _has_code(errors, "U19")

    def test_u20_search_only_profiles_mode(self) -> None:
        """U20: search only applies to mode='profiles'."""
        errors = validate_user_args(
            search="john",
            mode="aggregate",
            aggregate="count",
        )
        assert _has_code(errors, "U20")

    def test_u20_search_in_profiles_mode_is_valid(self) -> None:
        """U20: search in profiles mode is valid."""
        errors = validate_user_args(search="john", mode="profiles")
        assert not _has_code(errors, "U20")

    def test_u21_distinct_id_only_profiles_mode(self) -> None:
        """U21: distinct_id only applies to mode='profiles'."""
        errors = validate_user_args(
            distinct_id="user1",
            mode="aggregate",
            aggregate="count",
        )
        assert _has_code(errors, "U21")

    def test_u21_distinct_ids_only_profiles_mode(self) -> None:
        """U21: distinct_ids only applies to mode='profiles'."""
        errors = validate_user_args(
            distinct_ids=["user1"],
            mode="aggregate",
            aggregate="count",
        )
        assert _has_code(errors, "U21")

    def test_u21_distinct_id_in_profiles_mode_is_valid(self) -> None:
        """U21: distinct_id in profiles mode is valid."""
        errors = validate_user_args(distinct_id="user1", mode="profiles")
        assert not _has_code(errors, "U21")

    def test_u22_properties_only_profiles_mode(self) -> None:
        """U22: properties only applies to mode='profiles'."""
        errors = validate_user_args(
            properties=["$email"],
            mode="aggregate",
            aggregate="count",
        )
        assert _has_code(errors, "U22")

    def test_u22_properties_in_profiles_mode_is_valid(self) -> None:
        """U22: properties in profiles mode is valid."""
        errors = validate_user_args(
            properties=["$email"],
            mode="profiles",
        )
        assert not _has_code(errors, "U22")

    def test_u30_as_of_in_aggregate_mode_rejected(self) -> None:
        """U30: as_of only applies to mode='profiles'."""
        errors = validate_user_args(
            as_of="2025-01-01",
            mode="aggregate",
            aggregate="count",
        )
        assert _has_code(errors, "U30")

    def test_u30_as_of_int_in_aggregate_mode_rejected(self) -> None:
        """U30: as_of integer timestamp in aggregate mode is rejected."""
        errors = validate_user_args(
            as_of=1735689600,
            mode="aggregate",
            aggregate="count",
        )
        assert _has_code(errors, "U30")

    def test_u30_as_of_in_profiles_mode_is_valid(self) -> None:
        """U30: as_of in profiles mode is valid."""
        errors = validate_user_args(
            as_of="2025-01-01",
            mode="profiles",
        )
        assert not _has_code(errors, "U30")


# =============================================================================
# TestValidateUserArgsPercentileRules — Rules U26, U27, U28
# =============================================================================


class TestValidateUserArgsPercentileRules:
    """Tests for percentile-specific validation rules U26, U27, U28."""

    def test_u26_percentile_required_for_percentile_aggregate(self) -> None:
        """U26: percentile param is required when aggregate='percentile'."""
        errors = validate_user_args(
            mode="aggregate",
            aggregate="percentile",
            aggregate_property="age",
        )
        assert _has_code(errors, "U26")

    def test_u26_percentile_provided_is_valid(self) -> None:
        """U26: percentile param provided with aggregate='percentile' is valid."""
        errors = validate_user_args(
            mode="aggregate",
            aggregate="percentile",
            aggregate_property="age",
            percentile=50,
        )
        assert not _has_code(errors, "U26")

    def test_u27_percentile_prohibited_for_non_percentile(self) -> None:
        """U27: percentile param must not be set for non-percentile aggregates."""
        for agg in ("count", "extremes", "numeric_summary"):
            kwargs: dict[str, object] = {
                "mode": "aggregate",
                "aggregate": agg,
                "percentile": 50,
            }
            if agg != "count":
                kwargs["aggregate_property"] = "ltv"
            errors = validate_user_args(**kwargs)  # type: ignore[arg-type]
            assert _has_code(errors, "U27"), (
                f"aggregate='{agg}' with percentile should trigger U27"
            )

    def test_u27_no_percentile_for_extremes_is_valid(self) -> None:
        """U27: no percentile param with aggregate='extremes' is valid."""
        errors = validate_user_args(
            mode="aggregate",
            aggregate="extremes",
            aggregate_property="ltv",
        )
        assert not _has_code(errors, "U27")

    def test_u28_percentile_must_be_between_0_and_100_exclusive(self) -> None:
        """U28: percentile must be between 0 and 100 (exclusive boundaries)."""
        for val in (0, 100, -1, 101, 0.0, 100.0):
            errors = validate_user_args(
                mode="aggregate",
                aggregate="percentile",
                aggregate_property="age",
                percentile=val,
            )
            assert _has_code(errors, "U28"), f"percentile={val} should trigger U28"

    def test_u28_valid_percentile_values(self) -> None:
        """U28: valid percentile values between 0 and 100 exclusive pass."""
        for val in (0.1, 1, 25, 50, 75, 99, 99.9):
            errors = validate_user_args(
                mode="aggregate",
                aggregate="percentile",
                aggregate_property="age",
                percentile=val,
            )
            assert not _has_code(errors, "U28"), f"percentile={val} should be valid"

    def test_u28_boundary_values(self) -> None:
        """U28: boundary values 0 and 100 are invalid (exclusive range)."""
        errors_zero = validate_user_args(
            mode="aggregate",
            aggregate="percentile",
            aggregate_property="age",
            percentile=0,
        )
        assert _has_code(errors_zero, "U28")

        errors_hundred = validate_user_args(
            mode="aggregate",
            aggregate="percentile",
            aggregate_property="age",
            percentile=100,
        )
        assert _has_code(errors_hundred, "U28")


# =============================================================================
# TestValidateUserArgsMultipleViolations — Simultaneous error collection
# =============================================================================


class TestValidateUserArgsMultipleViolations:
    """Tests that multiple violations are collected in a single pass."""

    def test_multiple_basic_violations(self) -> None:
        """Multiple basic violations are all reported."""
        errors = validate_user_args(
            limit=-1,
            distinct_ids=[],
            sort_by="",
            mode="profiles",
        )
        codes = _codes(errors)
        assert "U3" in codes, "negative limit should produce U3"
        assert "U4" in codes, "empty distinct_ids should produce U4"
        assert "U5" in codes, "empty sort_by should produce U5"

    def test_mutual_exclusion_plus_value_violations(self) -> None:
        """Mutual exclusion and value violations collected together."""
        errors = validate_user_args(
            distinct_id="user1",
            distinct_ids=[],
            mode="profiles",
        )
        codes = _codes(errors)
        assert "U1" in codes, "U1 for mutual exclusion"
        assert "U4" in codes, "U4 for empty distinct_ids"

    def test_mode_violations_collected_together(self) -> None:
        """Multiple mode-specific violations are all reported."""
        errors = validate_user_args(
            parallel=True,
            sort_by="$last_seen",
            search="john",
            distinct_id="user1",
            properties=["$email"],
            as_of="2025-01-01",
            mode="aggregate",
            aggregate="count",
        )
        codes = _codes(errors)
        assert "U18" in codes, "parallel in aggregate mode"
        assert "U19" in codes, "sort_by in aggregate mode"
        assert "U20" in codes, "search in aggregate mode"
        assert "U21" in codes, "distinct_id in aggregate mode"
        assert "U22" in codes, "properties in aggregate mode"
        assert "U30" in codes, "as_of in aggregate mode"

    def test_aggregate_violations_collected(self) -> None:
        """Aggregate-specific violations are all reported."""
        errors = validate_user_args(
            mode="aggregate",
            aggregate="extremes",
            # Missing aggregate_property → U14
            segment_by=[0, -1],  # Invalid IDs → U17
        )
        codes = _codes(errors)
        assert "U14" in codes, "missing aggregate_property"
        assert "U17" in codes, "non-positive segment_by IDs"

    def test_cross_mode_and_basic_violations(self) -> None:
        """Cross-mode violations combined with basic violations."""
        errors = validate_user_args(
            workers=0,
            include_all_users=True,  # No cohort → U7
            mode="profiles",
        )
        codes = _codes(errors)
        assert "U23" in codes, "workers=0"
        assert "U7" in codes, "include_all_users without cohort"


# =============================================================================
# TestValidateUserArgsErrorShape — ValidationError structure
# =============================================================================


class TestValidateUserArgsErrorShape:
    """Tests that ValidationError fields are populated correctly."""

    def test_error_has_path(self) -> None:
        """Validation errors include a meaningful path."""
        errors = validate_user_args(limit=-1, mode="profiles")
        assert len(errors) >= 1
        error = next(e for e in errors if e.code == "U3")
        assert error.path, "path should be non-empty"

    def test_error_has_message(self) -> None:
        """Validation errors include a human-readable message."""
        errors = validate_user_args(limit=-1, mode="profiles")
        assert len(errors) >= 1
        error = next(e for e in errors if e.code == "U3")
        assert error.message, "message should be non-empty"

    def test_error_has_code(self) -> None:
        """Validation errors include a machine-readable code."""
        errors = validate_user_args(limit=-1, mode="profiles")
        assert len(errors) >= 1
        error = next(e for e in errors if e.code == "U3")
        assert error.code == "U3"

    def test_error_severity_is_error(self) -> None:
        """Validation errors default to severity 'error'."""
        errors = validate_user_args(limit=-1, mode="profiles")
        assert len(errors) >= 1
        error = next(e for e in errors if e.code == "U3")
        assert error.severity == "error"


# =============================================================================
# TestValidateUserParams — Layer 2 rules UP1-UP4
# =============================================================================


class TestValidateUserParamsValid:
    """Tests that valid param dicts produce no errors."""

    def test_empty_params_are_valid(self) -> None:
        """Empty params dict produces no errors."""
        errors = validate_user_params({})
        assert errors == []

    def test_valid_params_with_sort_order(self) -> None:
        """Params with valid sort_order are valid."""
        errors = validate_user_params({"sort_order": "ascending"})
        assert errors == []

    def test_valid_params_with_output_properties(self) -> None:
        """Params with non-empty output_properties array are valid."""
        errors = validate_user_params({"output_properties": ["$email", "$name"]})
        assert errors == []

    def test_valid_params_with_filter_by_cohort_id(self) -> None:
        """Params with filter_by_cohort containing 'id' are valid."""
        errors = validate_user_params({"filter_by_cohort": {"id": 123}})
        assert errors == []

    def test_valid_params_with_filter_by_cohort_raw(self) -> None:
        """Params with filter_by_cohort containing 'raw_cohort' are valid."""
        errors = validate_user_params(
            {"filter_by_cohort": {"raw_cohort": {"selector": {}, "behaviors": {}}}}
        )
        assert errors == []

    def test_valid_params_with_action(self) -> None:
        """Params with valid action expressions are valid."""
        for action in (
            "count()",
            'extremes(properties["ltv"])',
            'numeric_summary(properties["revenue"])',
            'percentile(properties["age"], 50)',
        ):
            errors = validate_user_params({"action": action})
            assert errors == [], f"action='{action}' should be valid"


class TestValidateUserParamsUP1:
    """Tests for UP1: sort_order must be 'ascending' or 'descending'."""

    def test_up1_invalid_sort_order(self) -> None:
        """UP1: invalid sort_order value is rejected."""
        errors = validate_user_params({"sort_order": "asc"})
        assert _has_code(errors, "UP1")

    def test_up1_random_string(self) -> None:
        """UP1: arbitrary string sort_order is rejected."""
        errors = validate_user_params({"sort_order": "random"})
        assert _has_code(errors, "UP1")

    def test_up1_ascending_is_valid(self) -> None:
        """UP1: 'ascending' is a valid sort_order."""
        errors = validate_user_params({"sort_order": "ascending"})
        assert not _has_code(errors, "UP1")

    def test_up1_descending_is_valid(self) -> None:
        """UP1: 'descending' is a valid sort_order."""
        errors = validate_user_params({"sort_order": "descending"})
        assert not _has_code(errors, "UP1")

    def test_up1_missing_sort_order_is_valid(self) -> None:
        """UP1: missing sort_order is valid (optional field)."""
        errors = validate_user_params({})
        assert not _has_code(errors, "UP1")


class TestValidateUserParamsUP2:
    """Tests for UP2: filter_by_cohort must have 'id' or 'raw_cohort' key."""

    def test_up2_missing_both_keys(self) -> None:
        """UP2: filter_by_cohort without 'id' or 'raw_cohort' is invalid."""
        errors = validate_user_params({"filter_by_cohort": {"name": "Power Users"}})
        assert _has_code(errors, "UP2")

    def test_up2_empty_dict(self) -> None:
        """UP2: empty filter_by_cohort dict is invalid."""
        errors = validate_user_params({"filter_by_cohort": {}})
        assert _has_code(errors, "UP2")

    def test_up2_with_id_is_valid(self) -> None:
        """UP2: filter_by_cohort with 'id' key is valid."""
        errors = validate_user_params({"filter_by_cohort": {"id": 123}})
        assert not _has_code(errors, "UP2")

    def test_up2_with_raw_cohort_is_valid(self) -> None:
        """UP2: filter_by_cohort with 'raw_cohort' key is valid."""
        errors = validate_user_params(
            {"filter_by_cohort": {"raw_cohort": {"selector": {}}}}
        )
        assert not _has_code(errors, "UP2")

    def test_up2_missing_filter_by_cohort_is_valid(self) -> None:
        """UP2: missing filter_by_cohort is valid (optional field)."""
        errors = validate_user_params({})
        assert not _has_code(errors, "UP2")


class TestValidateUserParamsUP3:
    """Tests for UP3: output_properties must be non-empty array if present."""

    def test_up3_empty_output_properties(self) -> None:
        """UP3: empty output_properties array is invalid."""
        errors = validate_user_params({"output_properties": []})
        assert _has_code(errors, "UP3")

    def test_up3_non_empty_output_properties_is_valid(self) -> None:
        """UP3: non-empty output_properties array is valid."""
        errors = validate_user_params({"output_properties": ["$email"]})
        assert not _has_code(errors, "UP3")

    def test_up3_json_encoded_empty_array(self) -> None:
        """UP3: JSON-encoded empty array string is also rejected."""
        errors = validate_user_params({"output_properties": "[]"})
        assert _has_code(errors, "UP3")

    def test_up3_json_encoded_non_empty_array_is_valid(self) -> None:
        """UP3: JSON-encoded non-empty array string is valid."""
        errors = validate_user_params({"output_properties": '["$email"]'})
        assert not _has_code(errors, "UP3")

    def test_up3_missing_output_properties_is_valid(self) -> None:
        """UP3: missing output_properties is valid (optional field)."""
        errors = validate_user_params({})
        assert not _has_code(errors, "UP3")


class TestValidateUserParamsUP4:
    """Tests for UP4: action must be valid aggregation expression."""

    def test_up4_invalid_action_expression(self) -> None:
        """UP4: invalid action expression is rejected."""
        errors = validate_user_params({"action": "invalid"})
        assert _has_code(errors, "UP4")

    def test_up4_empty_string_action(self) -> None:
        """UP4: empty string action is rejected."""
        errors = validate_user_params({"action": ""})
        assert _has_code(errors, "UP4")

    def test_up4_count_is_valid(self) -> None:
        """UP4: 'count()' is a valid action."""
        errors = validate_user_params({"action": "count()"})
        assert not _has_code(errors, "UP4")

    def test_up4_extremes_with_property_is_valid(self) -> None:
        """UP4: 'extremes(properties[\"prop\"])' is a valid action."""
        errors = validate_user_params({"action": 'extremes(properties["ltv"])'})
        assert not _has_code(errors, "UP4")

    def test_up4_numeric_summary_with_property_is_valid(self) -> None:
        """UP4: 'numeric_summary(properties[\"prop\"])' is a valid action."""
        errors = validate_user_params(
            {"action": 'numeric_summary(properties["revenue"])'}
        )
        assert not _has_code(errors, "UP4")

    def test_up4_percentile_with_property_is_valid(self) -> None:
        """UP4: 'percentile(properties[\"prop\"], N)' is a valid action."""
        errors = validate_user_params({"action": 'percentile(properties["age"], 50)'})
        assert not _has_code(errors, "UP4")

    def test_up4_missing_action_is_valid(self) -> None:
        """UP4: missing action is valid (optional field)."""
        errors = validate_user_params({})
        assert not _has_code(errors, "UP4")

    def test_up4_unsupported_function(self) -> None:
        """UP4: unsupported aggregation function is rejected."""
        errors = validate_user_params({"action": "median(ltv)"})
        assert _has_code(errors, "UP4")


class TestValidateUserParamsMultipleViolations:
    """Tests that multiple Layer 2 violations are collected together."""

    def test_multiple_param_violations(self) -> None:
        """Multiple param violations are all reported in a single pass."""
        errors = validate_user_params(
            {
                "sort_order": "invalid",
                "output_properties": [],
                "filter_by_cohort": {},
                "action": "bad",
            }
        )
        codes = _codes(errors)
        assert "UP1" in codes, "invalid sort_order"
        assert "UP2" in codes, "empty filter_by_cohort"
        assert "UP3" in codes, "empty output_properties"
        assert "UP4" in codes, "invalid action"


# =============================================================================
# PR #118 review fixes — U0 type-check and U7 false-positive
# =============================================================================


class TestValidateUserArgsWhereTypeCheck:
    """Tests for U0: where list items must be Filter instances."""

    def test_u0_non_filter_in_where_list(self) -> None:
        """U0: Non-Filter item in where list produces ValidationError."""
        errors = validate_user_args(
            where=["not-a-filter"],  # type: ignore[list-item]
        )
        assert _has_code(errors, "U0")

    def test_u0_mixed_filter_and_non_filter(self) -> None:
        """U0: Mixed list with both Filter and non-Filter items."""
        errors = validate_user_args(
            where=[Filter.equals("plan", "premium"), 42],  # type: ignore[list-item]
        )
        assert _has_code(errors, "U0")


class TestValidateUserArgsU7WithInCohortFilter:
    """Tests for U7 fix: include_all_users with Filter.in_cohort()."""

    def test_u7_include_all_users_with_in_cohort_filter_is_valid(self) -> None:
        """U7: include_all_users=True with Filter.in_cohort() is valid."""
        errors = validate_user_args(
            include_all_users=True,
            where=[Filter.in_cohort(42)],
        )
        assert not _has_code(errors, "U7")

    def test_u7_include_all_users_without_any_cohort_is_invalid(self) -> None:
        """U7: include_all_users=True without any cohort source is invalid."""
        errors = validate_user_args(
            include_all_users=True,
        )
        assert _has_code(errors, "U7")
