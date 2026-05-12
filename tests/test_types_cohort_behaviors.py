"""Unit tests for cohort behavior types: Filter.in_cohort/not_in_cohort,
CohortBreakdown, and CohortMetric.

Covers type construction (T002, T004, T019, T037) and validation rules
CF1-CF2, CB1-CB2, CM1-CM2. Each test class verifies a single type or
validation concern.
"""

from __future__ import annotations

from typing import Any

import pytest

from mixpanel_headless.types import (
    CohortBreakdown,
    CohortCriteria,
    CohortDefinition,
    CohortMetric,
    Filter,
)

# =============================================================================
# Helpers
# =============================================================================


def _simple_cohort_def() -> CohortDefinition:
    """Create a minimal CohortDefinition for testing.

    Returns:
        CohortDefinition with a single ``did_event`` criterion.
    """
    return CohortDefinition(
        CohortCriteria.did_event("Purchase", at_least=1, within_days=30)
    )


def _cohort_value(f: Filter) -> dict[str, Any]:
    """Extract the cohort dict from a cohort filter's _value.

    Type-narrows _value from its union type and returns the inner
    ``{"cohort": {...}}`` dict.

    Args:
        f: A cohort Filter (from in_cohort/not_in_cohort).

    Returns:
        The first element of _value (a dict with "cohort" key).
    """
    assert isinstance(f._value, list), f"Expected list, got {type(f._value)}"
    entry = f._value[0]
    assert isinstance(entry, dict), f"Expected dict, got {type(entry)}"
    return entry


# =============================================================================
# US1: Filter.in_cohort() — T002
# =============================================================================


class TestFilterInCohort:
    """Tests for Filter.in_cohort() construction with saved and inline cohorts."""

    def test_saved_cohort_sets_property(self) -> None:
        """Verify _property is '$cohorts' for a saved cohort filter."""
        f = Filter.in_cohort(123, "Power Users")
        assert f._property == "$cohorts"

    def test_saved_cohort_sets_operator_contains(self) -> None:
        """Verify _operator is 'contains' for in_cohort."""
        f = Filter.in_cohort(123, "Power Users")
        assert f._operator == "contains"

    def test_saved_cohort_sets_property_type_list(self) -> None:
        """Verify _property_type is 'list' for cohort filters."""
        f = Filter.in_cohort(123)
        assert f._property_type == "list"

    def test_saved_cohort_sets_resource_type_events(self) -> None:
        """Verify _resource_type is 'events' for cohort filters."""
        f = Filter.in_cohort(123)
        assert f._resource_type == "events"

    def test_saved_cohort_value_structure(self) -> None:
        """Verify _value has correct structure for saved cohort."""
        f = Filter.in_cohort(123, "Power Users")
        assert isinstance(f._value, list)
        assert len(f._value) == 1
        entry = _cohort_value(f)
        assert "cohort" in entry
        cohort = entry["cohort"]
        assert cohort["id"] == 123
        assert cohort["name"] == "Power Users"
        assert cohort["negated"] is False

    def test_saved_cohort_without_name(self) -> None:
        """Verify _value structure when name is not provided."""
        f = Filter.in_cohort(123)
        cohort = _cohort_value(f)["cohort"]
        assert cohort["id"] == 123
        assert cohort["name"] == ""

    def test_inline_cohort_sets_property(self) -> None:
        """Verify _property is '$cohorts' for an inline cohort filter."""
        cohort_def = _simple_cohort_def()
        f = Filter.in_cohort(cohort_def, name="Buyers")
        assert f._property == "$cohorts"

    def test_inline_cohort_value_has_raw_cohort(self) -> None:
        """Verify _value has raw_cohort instead of id for inline definition."""
        cohort_def = _simple_cohort_def()
        f = Filter.in_cohort(cohort_def, name="Buyers")
        assert isinstance(f._value, list)
        cohort = _cohort_value(f)["cohort"]
        assert "raw_cohort" in cohort
        assert "id" not in cohort
        assert cohort["name"] == "Buyers"
        assert cohort["negated"] is False

    def test_inline_cohort_raw_cohort_has_selector_and_behaviors(self) -> None:
        """Verify raw_cohort has selector and behaviors from CohortDefinition.

        The raw_cohort is a sanitized copy of to_dict() with null
        event_selector.selector keys removed for API compatibility.
        """
        cohort_def = _simple_cohort_def()
        f = Filter.in_cohort(cohort_def, name="Buyers")
        cohort = _cohort_value(f)["cohort"]
        raw = cohort["raw_cohort"]
        assert "selector" in raw
        assert "behaviors" in raw
        assert raw["selector"] == cohort_def.to_dict()["selector"]

    def test_inline_cohort_operator_contains(self) -> None:
        """Verify _operator is 'contains' for inline in_cohort."""
        cohort_def = _simple_cohort_def()
        f = Filter.in_cohort(cohort_def)
        assert f._operator == "contains"


# =============================================================================
# US1: Filter.not_in_cohort() — T002
# =============================================================================


class TestFilterNotInCohort:
    """Tests for Filter.not_in_cohort() construction with saved and inline cohorts."""

    def test_saved_cohort_sets_operator_does_not_contain(self) -> None:
        """Verify _operator is 'does not contain' for not_in_cohort."""
        f = Filter.not_in_cohort(789, "Bots")
        assert f._operator == "does not contain"

    def test_saved_cohort_sets_property(self) -> None:
        """Verify _property is '$cohorts' for not_in_cohort."""
        f = Filter.not_in_cohort(789)
        assert f._property == "$cohorts"

    def test_saved_cohort_value_negated_true(self) -> None:
        """Verify _value cohort entry has negated=True."""
        f = Filter.not_in_cohort(789, "Bots")
        cohort = _cohort_value(f)["cohort"]
        assert cohort["negated"] is True
        assert cohort["id"] == 789
        assert cohort["name"] == "Bots"

    def test_saved_cohort_sets_property_type_list(self) -> None:
        """Verify _property_type is 'list' for not_in_cohort."""
        f = Filter.not_in_cohort(789)
        assert f._property_type == "list"

    def test_inline_cohort_negated(self) -> None:
        """Verify inline CohortDefinition produces negated=True."""
        cohort_def = _simple_cohort_def()
        f = Filter.not_in_cohort(cohort_def, name="Inactive")
        cohort = _cohort_value(f)["cohort"]
        assert "raw_cohort" in cohort
        assert cohort["negated"] is True
        assert cohort["name"] == "Inactive"

    def test_inline_cohort_operator_does_not_contain(self) -> None:
        """Verify _operator is 'does not contain' for inline not_in_cohort."""
        cohort_def = _simple_cohort_def()
        f = Filter.not_in_cohort(cohort_def)
        assert f._operator == "does not contain"


# =============================================================================
# US1: Filter cohort validation — T004
# =============================================================================


class TestFilterCohortValidation:
    """Tests for CF1 and CF2 validation on Filter.in_cohort/not_in_cohort."""

    def test_cf1_zero_cohort_id_raises(self) -> None:
        """CF1: Zero cohort ID raises ValueError."""
        with pytest.raises(ValueError, match="cohort must be a positive integer"):
            Filter.in_cohort(0, "Bad")

    def test_cf1_negative_cohort_id_raises(self) -> None:
        """CF1: Negative cohort ID raises ValueError."""
        with pytest.raises(ValueError, match="cohort must be a positive integer"):
            Filter.in_cohort(-5, "Bad")

    def test_cf1_not_in_cohort_zero_raises(self) -> None:
        """CF1: Zero cohort ID on not_in_cohort raises ValueError."""
        with pytest.raises(ValueError, match="cohort must be a positive integer"):
            Filter.not_in_cohort(0)

    def test_cf1_not_in_cohort_negative_raises(self) -> None:
        """CF1: Negative cohort ID on not_in_cohort raises ValueError."""
        with pytest.raises(ValueError, match="cohort must be a positive integer"):
            Filter.not_in_cohort(-1)

    def test_cf2_empty_name_raises(self) -> None:
        """CF2: Empty name string raises ValueError."""
        with pytest.raises(
            ValueError, match="cohort name must be non-empty when provided"
        ):
            Filter.in_cohort(123, "")

    def test_cf2_whitespace_only_name_raises(self) -> None:
        """CF2: Whitespace-only name raises ValueError."""
        with pytest.raises(
            ValueError, match="cohort name must be non-empty when provided"
        ):
            Filter.in_cohort(123, "   ")

    def test_cf2_not_in_cohort_empty_name_raises(self) -> None:
        """CF2: Empty name on not_in_cohort raises ValueError."""
        with pytest.raises(
            ValueError, match="cohort name must be non-empty when provided"
        ):
            Filter.not_in_cohort(123, "")

    def test_cf1_positive_id_no_error(self) -> None:
        """CF1: Positive ID does not raise."""
        f = Filter.in_cohort(1)
        assert f._property == "$cohorts"

    def test_cf2_none_name_no_error(self) -> None:
        """CF2: None name does not raise."""
        f = Filter.in_cohort(123)
        assert f._property == "$cohorts"

    def test_cf2_valid_name_no_error(self) -> None:
        """CF2: Valid non-empty name does not raise."""
        f = Filter.in_cohort(123, "Power Users")
        cohort = _cohort_value(f)["cohort"]
        assert cohort["name"] == "Power Users"

    def test_cf1_inline_cohort_definition_no_id_check(self) -> None:
        """CF1: CohortDefinition argument skips positive-int check."""
        cohort_def = _simple_cohort_def()
        f = Filter.in_cohort(cohort_def)
        assert f._property == "$cohorts"


# =============================================================================
# US2: CohortBreakdown construction — T019
# =============================================================================


class TestCohortBreakdown:
    """Tests for CohortBreakdown frozen dataclass construction."""

    def test_saved_cohort_fields(self) -> None:
        """Verify fields are set correctly for a saved cohort."""
        cb = CohortBreakdown(cohort=123, name="Power Users")
        assert cb.cohort == 123
        assert cb.name == "Power Users"
        assert cb.include_negated is True

    def test_default_include_negated_true(self) -> None:
        """Verify include_negated defaults to True."""
        cb = CohortBreakdown(cohort=123)
        assert cb.include_negated is True

    def test_include_negated_false(self) -> None:
        """Verify include_negated can be set to False."""
        cb = CohortBreakdown(cohort=123, name="PU", include_negated=False)
        assert cb.include_negated is False

    def test_inline_cohort_definition(self) -> None:
        """Verify CohortBreakdown accepts inline CohortDefinition."""
        cohort_def = _simple_cohort_def()
        cb = CohortBreakdown(cohort=cohort_def, name="Active")
        assert cb.cohort is cohort_def
        assert cb.name == "Active"

    def test_name_defaults_to_none(self) -> None:
        """Verify name defaults to None."""
        cb = CohortBreakdown(cohort=123)
        assert cb.name is None

    def test_frozen_dataclass(self) -> None:
        """Verify CohortBreakdown is frozen (immutable)."""
        cb = CohortBreakdown(cohort=123, name="PU")
        with pytest.raises(AttributeError):
            cb.cohort = 456  # type: ignore[misc]


# =============================================================================
# US2: CohortBreakdown validation — T019
# =============================================================================


class TestCohortBreakdownValidation:
    """Tests for CB1-CB2 validation in CohortBreakdown.__post_init__."""

    def test_cb1_zero_cohort_id_raises(self) -> None:
        """CB1: Zero cohort ID raises ValueError."""
        with pytest.raises(ValueError, match="cohort must be a positive integer"):
            CohortBreakdown(cohort=0, name="Bad")

    def test_cb1_negative_cohort_id_raises(self) -> None:
        """CB1: Negative cohort ID raises ValueError."""
        with pytest.raises(ValueError, match="cohort must be a positive integer"):
            CohortBreakdown(cohort=-10, name="Bad")

    def test_cb2_empty_name_raises(self) -> None:
        """CB2: Empty name raises ValueError."""
        with pytest.raises(
            ValueError, match="cohort name must be non-empty when provided"
        ):
            CohortBreakdown(cohort=123, name="")

    def test_cb2_whitespace_only_name_raises(self) -> None:
        """CB2: Whitespace-only name raises ValueError."""
        with pytest.raises(
            ValueError, match="cohort name must be non-empty when provided"
        ):
            CohortBreakdown(cohort=123, name="   \t  ")

    def test_cb1_positive_id_no_error(self) -> None:
        """CB1: Positive ID does not raise."""
        cb = CohortBreakdown(cohort=1)
        assert cb.cohort == 1

    def test_cb2_none_name_no_error(self) -> None:
        """CB2: None name does not raise."""
        cb = CohortBreakdown(cohort=123)
        assert cb.name is None

    def test_cb1_inline_definition_no_id_check(self) -> None:
        """CB1: CohortDefinition argument skips positive-int check."""
        cohort_def = _simple_cohort_def()
        cb = CohortBreakdown(cohort=cohort_def)
        assert cb.cohort is cohort_def


# =============================================================================
# US3: CohortMetric construction — T037
# =============================================================================


class TestCohortMetric:
    """Tests for CohortMetric frozen dataclass construction."""

    def test_saved_cohort_fields(self) -> None:
        """Verify fields are set correctly for a saved cohort."""
        cm = CohortMetric(cohort=123, name="Power Users")
        assert cm.cohort == 123
        assert cm.name == "Power Users"

    def test_name_defaults_to_none(self) -> None:
        """Verify name defaults to None."""
        cm = CohortMetric(cohort=123)
        assert cm.name is None

    def test_inline_cohort_definition_rejected_cm5(self) -> None:
        """CM5: CohortMetric rejects inline CohortDefinition at construction."""
        cohort_def = _simple_cohort_def()
        with pytest.raises(
            ValueError,
            match="CohortMetric does not support inline CohortDefinition",
        ):
            CohortMetric(cohort=cohort_def, name="Active")

    def test_frozen_dataclass(self) -> None:
        """Verify CohortMetric is frozen (immutable)."""
        cm = CohortMetric(cohort=123, name="PU")
        with pytest.raises(AttributeError):
            cm.cohort = 456  # type: ignore[misc]


# =============================================================================
# US3: CohortMetric validation — T037
# =============================================================================


class TestCohortMetricValidation:
    """Tests for CM1-CM2 validation in CohortMetric.__post_init__."""

    def test_cm1_zero_cohort_id_raises(self) -> None:
        """CM1: Zero cohort ID raises ValueError."""
        with pytest.raises(ValueError, match="cohort must be a positive integer"):
            CohortMetric(cohort=0, name="Bad")

    def test_cm1_negative_cohort_id_raises(self) -> None:
        """CM1: Negative cohort ID raises ValueError."""
        with pytest.raises(ValueError, match="cohort must be a positive integer"):
            CohortMetric(cohort=-3, name="Bad")

    def test_cm2_empty_name_raises(self) -> None:
        """CM2: Empty name raises ValueError."""
        with pytest.raises(
            ValueError, match="cohort name must be non-empty when provided"
        ):
            CohortMetric(cohort=123, name="")

    def test_cm2_whitespace_only_name_raises(self) -> None:
        """CM2: Whitespace-only name raises ValueError."""
        with pytest.raises(
            ValueError, match="cohort name must be non-empty when provided"
        ):
            CohortMetric(cohort=123, name="  \t ")

    def test_cm1_positive_id_no_error(self) -> None:
        """CM1: Positive ID does not raise."""
        cm = CohortMetric(cohort=1)
        assert cm.cohort == 1

    def test_cm2_none_name_no_error(self) -> None:
        """CM2: None name does not raise."""
        cm = CohortMetric(cohort=123)
        assert cm.name is None

    def test_cm1_inline_definition_rejected_cm5(self) -> None:
        """CM5: CohortDefinition rejected at construction (before CM1 applies)."""
        cohort_def = _simple_cohort_def()
        with pytest.raises(
            ValueError,
            match="CohortMetric does not support inline CohortDefinition",
        ):
            CohortMetric(cohort=cohort_def)


# =============================================================================
# _sanitize_raw_cohort — direct unit tests
# =============================================================================


class TestSanitizeRawCohort:
    """Tests for the _sanitize_raw_cohort helper function."""

    def test_removes_null_selector(self) -> None:
        """Null selector in event_selector is removed."""
        from mixpanel_headless.types import _sanitize_raw_cohort

        raw: dict[str, Any] = {
            "behaviors": {
                "b1": {
                    "count": {
                        "event_selector": {"selector": None, "event": "Login"},
                    }
                }
            }
        }
        result = _sanitize_raw_cohort(raw)
        es = result["behaviors"]["b1"]["count"]["event_selector"]
        assert "selector" not in es
        assert es["event"] == "Login"

    def test_preserves_valid_selector(self) -> None:
        """Non-null selector is preserved."""
        from mixpanel_headless.types import _sanitize_raw_cohort

        raw: dict[str, Any] = {
            "behaviors": {
                "b1": {
                    "count": {
                        "event_selector": {
                            "selector": {"type": "and", "children": []},
                            "event": "Login",
                        },
                    }
                }
            }
        }
        result = _sanitize_raw_cohort(raw)
        assert result["behaviors"]["b1"]["count"]["event_selector"]["selector"] == {
            "type": "and",
            "children": [],
        }

    def test_no_behaviors_key(self) -> None:
        """Dict without behaviors key returns copy without error."""
        from mixpanel_headless.types import _sanitize_raw_cohort

        raw: dict[str, Any] = {"name": "Test", "version": 1}
        result = _sanitize_raw_cohort(raw)
        assert result == raw
        assert result is not raw

    def test_multiple_behaviors_mixed_selectors(self) -> None:
        """Mixed null/valid selectors — only nulls are removed."""
        from mixpanel_headless.types import _sanitize_raw_cohort

        raw: dict[str, Any] = {
            "behaviors": {
                "b1": {
                    "count": {
                        "event_selector": {"selector": None, "event": "A"},
                    }
                },
                "b2": {
                    "count": {
                        "event_selector": {
                            "selector": {"type": "or"},
                            "event": "B",
                        },
                    }
                },
            }
        }
        result = _sanitize_raw_cohort(raw)
        assert "selector" not in result["behaviors"]["b1"]["count"]["event_selector"]
        assert result["behaviors"]["b2"]["count"]["event_selector"]["selector"] == {
            "type": "or",
        }

    def test_deep_copy_semantics(self) -> None:
        """Original dict is not mutated."""
        from mixpanel_headless.types import _sanitize_raw_cohort

        raw: dict[str, Any] = {
            "behaviors": {
                "b1": {
                    "count": {
                        "event_selector": {"selector": None, "event": "X"},
                    }
                }
            }
        }
        _sanitize_raw_cohort(raw)
        # Original should still have selector: None
        assert raw["behaviors"]["b1"]["count"]["event_selector"]["selector"] is None


# =============================================================================
# US5: CohortCriteria.did_event() — aggregation params (T027)
# =============================================================================


class TestCohortCriteriaAggregation:
    """Tests for aggregation and aggregation_property params on did_event()."""

    def test_aggregation_with_property_succeeds(self) -> None:
        """did_event with aggregation + aggregation_property creates criteria."""
        c = CohortCriteria.did_event(
            "Purchase",
            aggregation="average",
            aggregation_property="amount",
            at_least=50,
            within_days=30,
        )
        assert c._behavior is not None

    @pytest.mark.parametrize(
        "agg_type",
        ["total", "unique", "average", "min", "max", "median"],
    )
    def test_all_six_aggregation_operators_accepted(self, agg_type: Any) -> None:
        """All 6 CohortAggregationType values are accepted without error."""
        c = CohortCriteria.did_event(
            "Purchase",
            aggregation=agg_type,
            aggregation_property="amount",
            at_least=1,
            within_days=30,
        )
        assert c._behavior is not None

    def test_ca1_aggregation_without_property_raises(self) -> None:
        """CA1: aggregation without aggregation_property raises ValueError."""
        with pytest.raises(
            ValueError,
            match="aggregation and aggregation_property must both be set or both be None",
        ):
            CohortCriteria.did_event(
                "Purchase",
                aggregation="average",
                at_least=50,
                within_days=30,
            )

    def test_ca2_aggregation_property_without_aggregation_raises(self) -> None:
        """CA2: aggregation_property without aggregation raises ValueError."""
        with pytest.raises(
            ValueError,
            match="aggregation and aggregation_property must both be set or both be None",
        ):
            CohortCriteria.did_event(
                "Purchase",
                aggregation_property="amount",
                at_least=50,
                within_days=30,
            )


class TestCohortCriteriaAggregationSerialization:
    """Tests for aggregation serialization in behavior dict."""

    def test_serialization_includes_aggregation_operator(self) -> None:
        """Behavior dict includes aggregationOperator when aggregation is set."""
        c = CohortCriteria.did_event(
            "Purchase",
            aggregation="average",
            aggregation_property="amount",
            at_least=50,
            within_days=30,
        )
        assert c._behavior is not None
        count = c._behavior["count"]
        assert count["aggregationOperator"] == "average"

    def test_serialization_includes_property(self) -> None:
        """Behavior dict includes property when aggregation_property is set."""
        c = CohortCriteria.did_event(
            "Purchase",
            aggregation="total",
            aggregation_property="revenue",
            at_least=100,
            within_days=7,
        )
        assert c._behavior is not None
        count = c._behavior["count"]
        assert count["property"] == "revenue"

    def test_no_aggregation_behavior_unchanged(self) -> None:
        """Behavior dict has no aggregationOperator/property when not set."""
        c = CohortCriteria.did_event(
            "Purchase",
            at_least=1,
            within_days=30,
        )
        assert c._behavior is not None
        count = c._behavior["count"]
        assert "aggregationOperator" not in count
        assert "property" not in count

    @pytest.mark.parametrize(
        "agg_type",
        ["total", "unique", "average", "min", "max", "median"],
    )
    def test_all_operators_serialize_correctly(self, agg_type: Any) -> None:
        """Each aggregation operator serializes as its string value."""
        c = CohortCriteria.did_event(
            "Purchase",
            aggregation=agg_type,
            aggregation_property="amount",
            at_least=1,
            within_days=30,
        )
        assert c._behavior is not None
        assert c._behavior["count"]["aggregationOperator"] == agg_type
        assert c._behavior["count"]["property"] == "amount"
