"""Unit tests for cohort-related bookmark validation rules.

Tests Layer 2 bookmark validation (B22-B26) and Layer 1 retention
argument validation (CB3) for cohort behaviors.

Validation rules:
    B25: Cohort filter ``value`` must be ``"$cohorts"``.
    B26: Cohort group entry must have non-empty ``cohorts`` array.
    B22: Cohort behavior requires positive int ``id``.
    B23: Cohort behavior ``resourceType`` must be ``"cohorts"``.
    B24: Cohort behavior ``math`` must be ``"unique"``.
    CB3: Cannot mix CohortBreakdown with GroupBy in retention.

Pattern follows ``test_validation_funnel.py``.
"""

from __future__ import annotations

from typing import Any

from mixpanel_headless._internal.validation import (
    validate_bookmark,
    validate_retention_args,
)
from mixpanel_headless.exceptions import ValidationError
from mixpanel_headless.types import CohortBreakdown, GroupBy

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


def _valid_cohort_show() -> dict[str, Any]:
    """Build a valid bookmark dict with a cohort show clause.

    Returns:
        Dict with sections containing a valid cohort behavior
        in show, plus required time, filter, group, and
        displayOptions fields.
    """
    return {
        "sections": {
            "show": [
                {
                    "type": "metric",
                    "behavior": {
                        "type": "cohort",
                        "name": "Power Users",
                        "id": 123,
                        "resourceType": "cohorts",
                        "dataGroupId": None,
                        "dataset": "$mixpanel",
                        "filtersDeterminer": "all",
                        "filters": [],
                    },
                    "measurement": {
                        "math": "unique",
                        "property": None,
                        "perUserAggregation": None,
                    },
                    "isHidden": False,
                }
            ],
            "time": [
                {
                    "dateRangeType": "in the last",
                    "window": {"value": 30, "unit": "day"},
                    "unit": "day",
                }
            ],
            "filter": [],
            "group": [],
            "formula": [],
        },
        "displayOptions": {"chartType": "line"},
    }


def _valid_cohort_filter_entry() -> dict[str, Any]:
    """Build a valid cohort filter entry dict.

    Returns:
        Dict representing a single cohort filter clause
        in sections.filter.
    """
    return {
        "resourceType": "events",
        "filterType": "list",
        "defaultType": "list",
        "value": "$cohorts",
        "filterValue": [
            {
                "cohort": {
                    "id": 123,
                    "name": "Power Users",
                    "negated": False,
                }
            }
        ],
        "filterOperator": "contains",
    }


def _valid_cohort_group_entry() -> dict[str, Any]:
    """Build a valid cohort group entry dict.

    Returns:
        Dict representing a single cohort group clause
        in sections.group.
    """
    return {
        "value": ["Power Users", "Not In Power Users"],
        "resourceType": "events",
        "profileType": None,
        "search": "",
        "dataGroupId": None,
        "propertyType": None,
        "typeCast": None,
        "cohorts": [
            {
                "id": 123,
                "name": "Power Users",
                "negated": False,
                "data_group_id": None,
                "groups": [],
            },
            {
                "id": 123,
                "name": "Power Users",
                "negated": True,
                "data_group_id": None,
                "groups": [],
            },
        ],
        "isHidden": False,
    }


def _bookmark_with_filter(filter_entry: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal valid bookmark with a single filter entry.

    Args:
        filter_entry: The filter clause dict to include.

    Returns:
        Complete bookmark dict with the filter in sections.filter.
    """
    return {
        "sections": {
            "show": [
                {
                    "behavior": {
                        "type": "event",
                        "name": "Login",
                        "resourceType": "events",
                    },
                    "measurement": {
                        "math": "total",
                        "property": None,
                        "perUserAggregation": None,
                    },
                }
            ],
            "time": [
                {
                    "dateRangeType": "in the last",
                    "window": {"value": 30, "unit": "day"},
                    "unit": "day",
                }
            ],
            "filter": [filter_entry],
            "group": [],
            "formula": [],
        },
        "displayOptions": {"chartType": "line"},
    }


def _bookmark_with_group(group_entry: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal valid bookmark with a single group entry.

    Args:
        group_entry: The group clause dict to include.

    Returns:
        Complete bookmark dict with the group in sections.group.
    """
    return {
        "sections": {
            "show": [
                {
                    "behavior": {
                        "type": "event",
                        "name": "Login",
                        "resourceType": "events",
                    },
                    "measurement": {
                        "math": "total",
                        "property": None,
                        "perUserAggregation": None,
                    },
                }
            ],
            "time": [
                {
                    "dateRangeType": "in the last",
                    "window": {"value": 30, "unit": "day"},
                    "unit": "day",
                }
            ],
            "filter": [],
            "group": [group_entry],
            "formula": [],
        },
        "displayOptions": {"chartType": "line"},
    }


# =============================================================================
# B25: Cohort filter value must be "$cohorts"
# =============================================================================


class TestCohortFilterValidation:
    """Tests for B25: cohort filter ``value`` must be ``"$cohorts"`` (T008)."""

    def test_valid_cohort_filter_no_b25_error(self) -> None:
        """Valid cohort filter entry does not produce B25 error."""
        entry = _valid_cohort_filter_entry()
        params = _bookmark_with_filter(entry)
        errors = validate_bookmark(params)
        assert "B25_COHORT_FILTER_VALUE" not in _codes(errors)

    def test_cohort_filter_with_wrong_value_returns_b25_error(self) -> None:
        """Cohort filter with filterType='list' but wrong value produces B25 error."""
        entry = _valid_cohort_filter_entry()
        entry["value"] = "wrong_property"
        params = _bookmark_with_filter(entry)
        errors = validate_bookmark(params)
        assert "B25_COHORT_FILTER_VALUE" in _codes(errors)

    def test_non_cohort_list_filter_no_b25_error(self) -> None:
        """Non-cohort filter (filterType != 'list') does not produce B25 error."""
        entry = {
            "resourceType": "events",
            "filterType": "string",
            "value": "country",
            "filterValue": ["US"],
            "filterOperator": "equals",
        }
        params = _bookmark_with_filter(entry)
        errors = validate_bookmark(params)
        assert "B25_COHORT_FILTER_VALUE" not in _codes(errors)


# =============================================================================
# B26: Cohort group entry must have non-empty cohorts array
# =============================================================================


class TestCohortGroupValidation:
    """Tests for B26: cohort group entry must have non-empty ``cohorts`` (T023)."""

    def test_valid_cohort_group_no_b26_error(self) -> None:
        """Valid cohort group entry does not produce B26 error."""
        entry = _valid_cohort_group_entry()
        params = _bookmark_with_group(entry)
        errors = validate_bookmark(params)
        assert "B26_EMPTY_COHORTS" not in _codes(errors)

    def test_empty_cohorts_array_returns_b26_error(self) -> None:
        """Cohort group entry with empty cohorts array produces B26 error."""
        entry = _valid_cohort_group_entry()
        entry["cohorts"] = []
        params = _bookmark_with_group(entry)
        errors = validate_bookmark(params)
        assert "B26_EMPTY_COHORTS" in _codes(errors)

    def test_group_without_cohorts_key_no_b26_error(self) -> None:
        """Group entry without 'cohorts' key does not produce B26 error."""
        entry = {
            "value": "country",
            "resourceType": "events",
            "propertyType": "string",
        }
        params = _bookmark_with_group(entry)
        errors = validate_bookmark(params)
        assert "B26_EMPTY_COHORTS" not in _codes(errors)


# =============================================================================
# B22-B24: Cohort show clause validation
# =============================================================================


class TestCohortShowValidation:
    """Tests for B22-B24: cohort behavior validation in show clause (T042, T043)."""

    def test_valid_cohort_show_no_errors(self) -> None:
        """Valid cohort show clause produces no B22/B23/B24 errors."""
        params = _valid_cohort_show()
        errors = validate_bookmark(params)
        cohort_codes = {
            "B22_COHORT_BEHAVIOR_ID",
            "B23_COHORT_RESOURCE_TYPE",
            "B24_COHORT_MATH",
        }
        assert not any(e.code in cohort_codes for e in errors)

    def test_b22_negative_id_returns_error(self) -> None:
        """B22: Negative cohort id produces B22 error."""
        params = _valid_cohort_show()
        params["sections"]["show"][0]["behavior"]["id"] = -1
        errors = validate_bookmark(params)
        assert "B22_COHORT_BEHAVIOR_ID" in _codes(errors)

    def test_b22_zero_id_returns_error(self) -> None:
        """B22: Zero cohort id produces B22 error."""
        params = _valid_cohort_show()
        params["sections"]["show"][0]["behavior"]["id"] = 0
        errors = validate_bookmark(params)
        assert "B22_COHORT_BEHAVIOR_ID" in _codes(errors)

    def test_b22_missing_id_with_raw_cohort_no_error(self) -> None:
        """B22: Missing id but has raw_cohort (inline) does not produce B22 error."""
        params = _valid_cohort_show()
        behavior = params["sections"]["show"][0]["behavior"]
        del behavior["id"]
        behavior["raw_cohort"] = {"selector": {}, "behaviors": {}}
        errors = validate_bookmark(params)
        assert "B22_COHORT_BEHAVIOR_ID" not in _codes(errors)

    def test_b23_wrong_resource_type_returns_error(self) -> None:
        """B23: Wrong resourceType produces B23 error."""
        params = _valid_cohort_show()
        params["sections"]["show"][0]["behavior"]["resourceType"] = "events"
        errors = validate_bookmark(params)
        assert "B23_COHORT_RESOURCE_TYPE" in _codes(errors)

    def test_b23_correct_resource_type_no_error(self) -> None:
        """B23: Correct resourceType='cohorts' does not produce B23 error."""
        params = _valid_cohort_show()
        errors = validate_bookmark(params)
        assert "B23_COHORT_RESOURCE_TYPE" not in _codes(errors)

    def test_b24_wrong_math_returns_error(self) -> None:
        """B24: Non-'unique' math for cohort behavior produces B24 error."""
        params = _valid_cohort_show()
        params["sections"]["show"][0]["measurement"]["math"] = "total"
        errors = validate_bookmark(params)
        assert "B24_COHORT_MATH" in _codes(errors)

    def test_b24_correct_math_no_error(self) -> None:
        """B24: math='unique' for cohort behavior does not produce B24 error."""
        params = _valid_cohort_show()
        errors = validate_bookmark(params)
        assert "B24_COHORT_MATH" not in _codes(errors)


# =============================================================================
# CB3: Retention mutual exclusivity — CohortBreakdown + GroupBy
# =============================================================================


class TestRetentionCohortMixValidation:
    """Tests for CB3: no mixing CohortBreakdown with GroupBy in retention (T022).

    Uses ``validate_retention_args()`` directly.
    """

    def test_cohort_breakdown_alone_no_cb3_error(self) -> None:
        """CohortBreakdown alone in retention group_by does not produce CB3 error."""
        errors = validate_retention_args(
            born_event="Signup",
            return_event="Login",
            group_by=CohortBreakdown(123, "PU"),
        )
        assert "CB3_RETENTION_MIXED_BREAKDOWN" not in _codes(errors)

    def test_string_group_by_alone_no_cb3_error(self) -> None:
        """String group_by alone in retention does not produce CB3 error."""
        errors = validate_retention_args(
            born_event="Signup",
            return_event="Login",
            group_by="platform",
        )
        assert "CB3_RETENTION_MIXED_BREAKDOWN" not in _codes(errors)

    def test_mixed_cohort_and_groupby_returns_cb3_error(self) -> None:
        """CohortBreakdown mixed with GroupBy in retention produces CB3 error."""
        errors = validate_retention_args(
            born_event="Signup",
            return_event="Login",
            group_by=[CohortBreakdown(123, "PU"), GroupBy("platform")],
        )
        assert "CB3_RETENTION_MIXED_BREAKDOWN" in _codes(errors)

    def test_mixed_cohort_and_string_returns_cb3_error(self) -> None:
        """CohortBreakdown mixed with string in retention produces CB3 error."""
        errors = validate_retention_args(
            born_event="Signup",
            return_event="Login",
            group_by=[CohortBreakdown(123, "PU"), "platform"],
        )
        assert "CB3_RETENTION_MIXED_BREAKDOWN" in _codes(errors)

    def test_cb3_error_message_mentions_mixing(self) -> None:
        """CB3 error message mentions mixing CohortBreakdown with property GroupBy."""
        errors = validate_retention_args(
            born_event="Signup",
            return_event="Login",
            group_by=[CohortBreakdown(123, "PU"), "platform"],
        )
        cb3_errors = [e for e in errors if e.code == "CB3_RETENTION_MIXED_BREAKDOWN"]
        assert len(cb3_errors) == 1
        assert (
            "mixing" in cb3_errors[0].message.lower()
            or "mix" in cb3_errors[0].message.lower()
        )

    def test_multiple_cohort_breakdowns_no_cb3_error(self) -> None:
        """Multiple CohortBreakdowns (no property GroupBy) do not produce CB3 error."""
        errors = validate_retention_args(
            born_event="Signup",
            return_event="Login",
            group_by=[CohortBreakdown(123, "PU"), CohortBreakdown(456, "New Users")],
        )
        assert "CB3_RETENTION_MIXED_BREAKDOWN" not in _codes(errors)

    def test_none_group_by_no_cb3_error(self) -> None:
        """None group_by does not produce CB3 error."""
        errors = validate_retention_args(
            born_event="Signup",
            return_event="Login",
            group_by=None,
        )
        assert "CB3_RETENTION_MIXED_BREAKDOWN" not in _codes(errors)


# =============================================================================
# B22: Cohort behavior missing identifier
# =============================================================================


class TestCohortBehaviorMissingIdentifier:
    """Test B22_COHORT_MISSING_IDENTIFIER — neither id nor raw_cohort."""

    def test_missing_both_id_and_raw_cohort(self) -> None:
        """Cohort behavior with neither id nor raw_cohort triggers B22."""
        bookmark: dict[str, Any] = {
            "sections": {
                "show": [
                    {
                        "dataset": "$mixpanel",
                        "value": "Login",
                        "resourceType": "events",
                        "profileType": None,
                        "search": "",
                        "dataGroupId": None,
                        "math": "total",
                        "property": None,
                        "perUserAggregation": None,
                        "type": "number",
                        "measurement": {"property": None},
                    },
                    {
                        "dataset": "$mixpanel",
                        "resourceType": "cohorts",
                        "math": "unique",
                        "type": "number",
                        "behavior": {
                            "type": "cohort",
                            "resourceType": "cohorts",
                            # Missing both "id" and "raw_cohort"
                        },
                        "value": "Test Cohort",
                        "measurement": {"property": None},
                    },
                ],
                "filter": [],
                "group": [],
                "formula": [],
                "time": {"dateRange": "30d", "unit": "day"},
            },
            "displayOptions": {
                "chartType": "line",
                "plotStyle": "standard",
                "analysis": "linear",
            },
        }
        errors = validate_bookmark(bookmark)
        assert "B22_COHORT_MISSING_IDENTIFIER" in _codes(errors)
