"""Tests for Cohort Definition Builder types.

Tests CohortCriteria and CohortDefinition frozen dataclasses including
behavioral criteria (did_event), property criteria (has_property),
cohort references (in_cohort), boolean composition (all_of/any_of),
serialization (to_dict), validation, and CRUD integration.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from mixpanel_headless.types import (
    _FILTER_TO_SELECTOR_SUPPORTED,
    _PROPERTY_OPERATOR_MAP,
    CohortCriteria,
    CohortDefinition,
    CreateCohortParams,
    Filter,
)

# =============================================================================
# Operator Mapping Tests
# =============================================================================


class TestOperatorMaps:
    """Tests for operator mapping dicts (T005, T006)."""

    def test_property_operator_map_has_all_operators(self) -> None:
        """_PROPERTY_OPERATOR_MAP maps all expected CohortCriteria operators."""
        expected = {
            "equals": "==",
            "not_equals": "!=",
            "contains": "in",
            "not_contains": "not in",
            "greater_than": ">",
            "less_than": "<",
            "is_set": "defined",
            "is_not_set": "not defined",
        }
        assert expected == _PROPERTY_OPERATOR_MAP

    def test_filter_to_selector_supported_has_all_operators(self) -> None:
        """_FILTER_TO_SELECTOR_SUPPORTED contains all expected Filter._operator strings."""
        expected = {
            "equals",
            "does not equal",
            "contains",
            "does not contain",
            "is greater than",
            "is less than",
            "is set",
            "is not set",
            "is between",
        }
        assert expected == _FILTER_TO_SELECTOR_SUPPORTED


# =============================================================================
# Behavioral Criteria (did_event)
# =============================================================================


class TestCohortCriteriaDidEvent:
    """Tests for CohortCriteria.did_event() (T007-T013)."""

    def test_at_least_within_days(self) -> None:
        """did_event with at_least + within_days produces correct selector and behavior."""
        c = CohortCriteria.did_event("Purchase", at_least=3, within_days=30)

        # Selector node
        assert c._selector_node["property"] == "behaviors"
        assert c._selector_node["operator"] == ">="
        assert c._selector_node["operand"] == 3

        # Behavior key
        assert c._behavior_key is not None

        # Behavior entry
        assert c._behavior is not None
        assert c._behavior["count"]["event_selector"]["event"] == "Purchase"
        assert c._behavior["count"]["event_selector"]["selector"] is None
        assert c._behavior["count"]["type"] == "absolute"
        assert c._behavior["window"] == {"unit": "day", "value": 30}

    def test_at_most_frequency(self) -> None:
        """did_event with at_most maps to <= operator."""
        c = CohortCriteria.did_event("Login", at_most=5, within_days=7)
        assert c._selector_node["operator"] == "<="
        assert c._selector_node["operand"] == 5

    def test_exactly_frequency(self) -> None:
        """did_event with exactly maps to == operator."""
        c = CohortCriteria.did_event("Signup", exactly=1, within_days=14)
        assert c._selector_node["operator"] == "=="
        assert c._selector_node["operand"] == 1

    def test_within_weeks(self) -> None:
        """did_event with within_weeks uses week unit."""
        c = CohortCriteria.did_event("Purchase", at_least=1, within_weeks=4)
        assert c._behavior is not None
        assert c._behavior["window"] == {"unit": "week", "value": 4}

    def test_within_months(self) -> None:
        """did_event with within_months uses month unit."""
        c = CohortCriteria.did_event("Purchase", at_least=1, within_months=3)
        assert c._behavior is not None
        assert c._behavior["window"] == {"unit": "month", "value": 3}

    def test_from_date_to_date(self) -> None:
        """did_event with absolute date range stores from_date/to_date."""
        c = CohortCriteria.did_event(
            "Purchase",
            at_least=1,
            from_date="2024-01-01",
            to_date="2024-03-31",
        )
        assert c._behavior is not None
        assert "window" not in c._behavior
        assert c._behavior["from_date"] == "2024-01-01"
        assert c._behavior["to_date"] == "2024-03-31"

    def test_where_single_filter(self) -> None:
        """did_event with single where filter builds Insights bookmark filter node."""
        c = CohortCriteria.did_event(
            "Purchase",
            at_least=1,
            within_days=30,
            where=Filter.equals("plan", "premium"),
        )
        assert c._behavior is not None
        selector = c._behavior["count"]["event_selector"]["selector"]
        assert selector is not None
        assert selector["operator"] == "and"
        assert len(selector["children"]) == 1
        child = selector["children"][0]
        assert child["resourceType"] == "events"
        assert child["value"] == "plan"
        assert child["filterOperator"] == "equals"
        assert child["filterValue"] == ["premium"]
        assert child["filterType"] == "string"
        assert child["defaultType"] == "string"

    def test_where_multiple_filters(self) -> None:
        """did_event with multiple where filters produces AND-combined children."""
        c = CohortCriteria.did_event(
            "Purchase",
            at_least=1,
            within_days=30,
            where=[
                Filter.equals("plan", "premium"),
                Filter.greater_than("amount", 100),
            ],
        )
        assert c._behavior is not None
        selector = c._behavior["count"]["event_selector"]["selector"]
        assert selector is not None
        assert selector["operator"] == "and"
        assert len(selector["children"]) == 2

        # First child: plan equals premium
        assert selector["children"][0]["value"] == "plan"
        assert selector["children"][0]["filterOperator"] == "equals"

        # Second child: amount > 100
        assert selector["children"][1]["value"] == "amount"
        assert selector["children"][1]["filterOperator"] == "is greater than"
        assert selector["children"][1]["filterValue"] == 100
        assert selector["children"][1]["filterType"] == "number"

    def test_exactly_zero_is_valid(self) -> None:
        """did_event with exactly=0 is valid (used by did_not_do_event)."""
        c = CohortCriteria.did_event("Login", exactly=0, within_days=30)
        assert c._selector_node["operator"] == "=="
        assert c._selector_node["operand"] == 0


class TestCohortCriteriaDidEventValidation:
    """Validation error tests for did_event (T012)."""

    def test_cd1_conflicting_frequency_params(self) -> None:
        """ValueError when multiple frequency params are set (CD1)."""
        with pytest.raises(ValueError, match="exactly one of"):
            CohortCriteria.did_event("Login", at_least=1, at_most=5, within_days=30)

    def test_cd1_no_frequency_params(self) -> None:
        """ValueError when no frequency params are set (CD1)."""
        with pytest.raises(ValueError, match="exactly one of"):
            CohortCriteria.did_event("Login", within_days=30)

    def test_cd2_negative_frequency(self) -> None:
        """ValueError when frequency is negative (CD2)."""
        with pytest.raises(ValueError, match="frequency value must be >= 0"):
            CohortCriteria.did_event("Login", at_least=-1, within_days=30)

    def test_cd3_no_time_constraint(self) -> None:
        """ValueError when no time constraint is provided (CD3)."""
        with pytest.raises(ValueError, match="exactly one time constraint"):
            CohortCriteria.did_event("Login", at_least=1)

    def test_cd3_both_rolling_and_date_range(self) -> None:
        """ValueError when both rolling window and date range are set (CD3)."""
        with pytest.raises(ValueError, match="exactly one time constraint"):
            CohortCriteria.did_event(
                "Login",
                at_least=1,
                within_days=30,
                from_date="2024-01-01",
                to_date="2024-03-31",
            )

    def test_cd4_empty_event_name(self) -> None:
        """ValueError when event name is empty (CD4)."""
        with pytest.raises(ValueError, match="event name must be non-empty"):
            CohortCriteria.did_event("", at_least=1, within_days=30)

    def test_cd4_whitespace_event_name(self) -> None:
        """ValueError when event name is whitespace only (CD4)."""
        with pytest.raises(ValueError, match="event name must be non-empty"):
            CohortCriteria.did_event("   ", at_least=1, within_days=30)

    def test_cd5_from_date_without_to_date(self) -> None:
        """ValueError when from_date is set without to_date (CD5)."""
        with pytest.raises(ValueError, match="from_date requires to_date"):
            CohortCriteria.did_event("Login", at_least=1, from_date="2024-01-01")

    def test_cd5_to_date_without_from_date(self) -> None:
        """ValueError when to_date is set without from_date."""
        with pytest.raises(ValueError, match="to_date requires from_date"):
            CohortCriteria.did_event("Login", at_least=1, to_date="2024-03-31")

    def test_cd6_invalid_date_format(self) -> None:
        """ValueError when dates are not YYYY-MM-DD format (CD6)."""
        with pytest.raises(ValueError, match="dates must be YYYY-MM-DD"):
            CohortCriteria.did_event(
                "Login",
                at_least=1,
                from_date="01-01-2024",
                to_date="03-31-2024",
            )

    def test_cd3_multiple_rolling_windows(self) -> None:
        """ValueError when multiple rolling windows are set."""
        with pytest.raises(ValueError, match="exactly one time constraint"):
            CohortCriteria.did_event(
                "Login", at_least=1, within_days=30, within_weeks=4
            )

    def test_unsupported_filter_operator_raises(self) -> None:
        """ValueError when Filter uses an operator not in _FILTER_TO_SELECTOR_SUPPORTED."""
        with pytest.raises(ValueError, match="unsupported filter operator"):
            CohortCriteria.did_event(
                "Login",
                at_least=1,
                within_days=30,
                where=Filter.is_true("flag"),
            )

    def test_cd6_invalid_calendar_date(self) -> None:
        """ValueError for syntactically valid but calendrically invalid date."""
        with pytest.raises(ValueError, match="not a valid calendar date"):
            CohortCriteria.did_event(
                "Login",
                at_least=1,
                from_date="2024-02-30",
                to_date="2024-03-01",
            )


class TestCohortCriteriaImmutability:
    """Immutability tests for CohortCriteria (T013)."""

    def test_frozen_rejects_attribute_assignment(self) -> None:
        """Frozen dataclass rejects attribute assignment after construction."""
        c = CohortCriteria.did_event("Login", at_least=1, within_days=30)
        with pytest.raises(AttributeError):
            c._selector_node = {}  # type: ignore[misc]
        with pytest.raises(AttributeError):
            c._behavior_key = "other"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            c._behavior = {}  # type: ignore[misc]


# =============================================================================
# Definition Composition (all_of / any_of)
# =============================================================================


class TestCohortDefinitionInit:
    """Tests for CohortDefinition.__init__() (T017)."""

    def test_single_criterion(self) -> None:
        """CohortDefinition with single criterion stores it and defaults to AND."""
        c = CohortCriteria.did_event("Login", at_least=1, within_days=30)
        d = CohortDefinition(c)
        assert d._criteria == (c,)
        assert d._operator == "and"

    def test_to_dict_produces_selector_and_behaviors(self) -> None:
        """to_dict() produces dict with selector and behaviors keys."""
        c = CohortCriteria.did_event("Login", at_least=1, within_days=30)
        d = CohortDefinition(c)
        result = d.to_dict()
        assert "selector" in result
        assert "behaviors" in result

    def test_to_dict_selector_is_combinator(self) -> None:
        """to_dict() selector is always a combinator node at top level."""
        c = CohortCriteria.did_event("Login", at_least=1, within_days=30)
        d = CohortDefinition(c)
        result = d.to_dict()
        selector = result["selector"]
        assert selector["operator"] == "and"
        assert "children" in selector


class TestCohortDefinitionAllOf:
    """Tests for CohortDefinition.all_of() (T018)."""

    def test_two_behavioral_criteria(self) -> None:
        """all_of with two behavioral criteria produces AND with two children."""
        a = CohortCriteria.did_event("Login", at_least=1, within_days=7)
        b = CohortCriteria.did_event("Purchase", at_least=3, within_days=30)
        d = CohortDefinition.all_of(a, b)
        result = d.to_dict()

        selector = result["selector"]
        assert selector["operator"] == "and"
        assert len(selector["children"]) == 2

        behaviors = result["behaviors"]
        assert len(behaviors) == 2
        assert "bhvr_0" in behaviors
        assert "bhvr_1" in behaviors

    def test_behavior_keys_are_unique(self) -> None:
        """all_of produces globally unique behavior keys."""
        a = CohortCriteria.did_event("Login", at_least=1, within_days=7)
        b = CohortCriteria.did_event("Purchase", at_least=3, within_days=30)
        d = CohortDefinition.all_of(a, b)
        result = d.to_dict()
        keys = list(result["behaviors"].keys())
        assert len(keys) == len(set(keys))

    def test_selector_references_match_behavior_keys(self) -> None:
        """Selector node values reference the correct behavior keys."""
        a = CohortCriteria.did_event("Login", at_least=1, within_days=7)
        b = CohortCriteria.did_event("Purchase", at_least=3, within_days=30)
        d = CohortDefinition.all_of(a, b)
        result = d.to_dict()

        children = result["selector"]["children"]
        behavior_keys = set(result["behaviors"].keys())
        selector_refs = {c["value"] for c in children}
        assert selector_refs == behavior_keys


class TestCohortDefinitionAnyOf:
    """Tests for CohortDefinition.any_of() (T019)."""

    def test_any_of_uses_or_operator(self) -> None:
        """any_of produces selector with OR operator."""
        a = CohortCriteria.did_event("Login", at_least=1, within_days=7)
        b = CohortCriteria.did_event("Purchase", at_least=1, within_days=30)
        d = CohortDefinition.any_of(a, b)
        result = d.to_dict()
        assert result["selector"]["operator"] == "or"


class TestCohortDefinitionNesting:
    """Tests for nested definitions (T020, T021)."""

    def test_nested_any_of_all_of(self) -> None:
        """any_of(all_of(A, B), C) produces correct nested selector tree."""
        a = CohortCriteria.did_event("Login", at_least=1, within_days=7)
        b = CohortCriteria.did_event("Purchase", at_least=3, within_days=30)
        c = CohortCriteria.did_event("Signup", at_least=1, within_days=14)

        nested = CohortDefinition.any_of(
            CohortDefinition.all_of(a, b),
            c,
        )
        result = nested.to_dict()

        # Top level is OR
        selector = result["selector"]
        assert selector["operator"] == "or"
        assert len(selector["children"]) == 2

        # First child is AND (nested)
        inner = selector["children"][0]
        assert inner["operator"] == "and"
        assert len(inner["children"]) == 2

        # Second child is a leaf (criterion C)
        leaf = selector["children"][1]
        assert leaf["property"] == "behaviors"

        # All three behaviors collected with unique keys
        assert len(result["behaviors"]) == 3
        keys = list(result["behaviors"].keys())
        assert keys == ["bhvr_0", "bhvr_1", "bhvr_2"]

    def test_deeply_nested_three_levels(self) -> None:
        """3+ levels of nesting produces correct tree and unique behavior keys."""
        a = CohortCriteria.did_event("A", at_least=1, within_days=7)
        b = CohortCriteria.did_event("B", at_least=1, within_days=7)
        c = CohortCriteria.did_event("C", at_least=1, within_days=7)
        d = CohortCriteria.did_event("D", at_least=1, within_days=7)

        deep = CohortDefinition.any_of(
            CohortDefinition.all_of(
                CohortDefinition.any_of(a, b),
                c,
            ),
            d,
        )
        result = deep.to_dict()

        # 4 behaviors, all unique
        assert len(result["behaviors"]) == 4
        keys = sorted(result["behaviors"].keys())
        assert keys == ["bhvr_0", "bhvr_1", "bhvr_2", "bhvr_3"]

    def test_behavior_key_uniqueness_across_nesting(self) -> None:
        """No duplicate behavior keys across arbitrary nesting."""
        criteria = [
            CohortCriteria.did_event(f"Event{i}", at_least=1, within_days=7)
            for i in range(5)
        ]
        nested = CohortDefinition.any_of(
            CohortDefinition.all_of(*criteria[:3]),
            CohortDefinition.all_of(*criteria[3:]),
        )
        result = nested.to_dict()
        keys = list(result["behaviors"].keys())
        assert len(keys) == 5
        assert len(set(keys)) == 5


class TestCohortDefinitionValidation:
    """Validation tests for CohortDefinition (T022)."""

    def test_cd9_zero_criteria_init(self) -> None:
        """ValueError when CohortDefinition() called with zero criteria (CD9)."""
        with pytest.raises(ValueError, match="requires at least one criterion"):
            CohortDefinition()

    def test_cd9_zero_criteria_all_of(self) -> None:
        """ValueError when all_of() called with zero criteria."""
        with pytest.raises(ValueError, match="requires at least one criterion"):
            CohortDefinition.all_of()

    def test_cd9_zero_criteria_any_of(self) -> None:
        """ValueError when any_of() called with zero criteria."""
        with pytest.raises(ValueError, match="requires at least one criterion"):
            CohortDefinition.any_of()


class TestCohortDefinitionImmutability:
    """Immutability tests for CohortDefinition (T023)."""

    def test_frozen_rejects_attribute_assignment(self) -> None:
        """Frozen dataclass rejects attribute assignment after construction."""
        c = CohortCriteria.did_event("Login", at_least=1, within_days=30)
        d = CohortDefinition(c)
        with pytest.raises(AttributeError):
            d._criteria = ()  # type: ignore[misc]
        with pytest.raises(AttributeError):
            d._operator = "or"  # type: ignore[misc]


# =============================================================================
# Property-Based Criteria
# =============================================================================


class TestCohortCriteriaHasProperty:
    """Tests for CohortCriteria.has_property() (T030-T035b)."""

    def test_has_property_default_operator(self) -> None:
        """has_property with default operator produces equals selector node."""
        c = CohortCriteria.has_property("plan", "premium")
        assert c._selector_node["property"] == "user"
        assert c._selector_node["value"] == "plan"
        assert c._selector_node["operator"] == "=="
        assert c._selector_node["operand"] == "premium"
        assert c._selector_node["type"] == "string"
        assert c._behavior_key is None
        assert c._behavior is None

    @pytest.mark.parametrize(
        ("operator", "expected_selector_op"),
        [
            ("equals", "=="),
            ("not_equals", "!="),
            ("contains", "in"),
            ("not_contains", "not in"),
            ("greater_than", ">"),
            ("less_than", "<"),
        ],
    )
    def test_has_property_all_operators(
        self, operator: str, expected_selector_op: str
    ) -> None:
        """has_property maps all operators correctly via _PROPERTY_OPERATOR_MAP."""
        c = CohortCriteria.has_property("age", 25, operator=operator)  # type: ignore[arg-type]
        assert c._selector_node["operator"] == expected_selector_op

    def test_has_property_number_type(self) -> None:
        """has_property with property_type='number' sets type field."""
        c = CohortCriteria.has_property(
            "age", 25, operator="greater_than", property_type="number"
        )
        assert c._selector_node["type"] == "number"

    def test_property_is_set(self) -> None:
        """property_is_set produces 'defined' operator."""
        c = CohortCriteria.property_is_set("email")
        assert c._selector_node["property"] == "user"
        assert c._selector_node["value"] == "email"
        assert c._selector_node["operator"] == "defined"
        assert c._behavior_key is None
        assert c._behavior is None

    def test_property_is_not_set(self) -> None:
        """property_is_not_set produces 'not defined' operator."""
        c = CohortCriteria.property_is_not_set("phone")
        assert c._selector_node["operator"] == "not defined"

    def test_cd7_empty_property_name(self) -> None:
        """ValueError when property name is empty (CD7)."""
        with pytest.raises(ValueError, match="property name must be non-empty"):
            CohortCriteria.has_property("", "value")

    def test_cd7_whitespace_property_name(self) -> None:
        """ValueError when property name is whitespace only (CD7)."""
        with pytest.raises(ValueError, match="property name must be non-empty"):
            CohortCriteria.has_property("   ", "value")

    def test_cd7_property_is_set_empty_name(self) -> None:
        """ValueError when property_is_set receives empty name."""
        with pytest.raises(ValueError, match="property name must be non-empty"):
            CohortCriteria.property_is_set("")

    def test_property_in_to_dict_empty_behaviors(self) -> None:
        """Property-only definition produces empty behaviors dict."""
        c = CohortCriteria.has_property("plan", "premium")
        d = CohortDefinition(c)
        result = d.to_dict()
        assert result["behaviors"] == {}

    def test_definition_with_only_property_criteria(self) -> None:
        """Definition with only property criteria has empty behaviors dict."""
        d = CohortDefinition.all_of(
            CohortCriteria.has_property("plan", "premium"),
            CohortCriteria.property_is_set("email"),
        )
        result = d.to_dict()
        assert result["behaviors"] == {}
        assert result["selector"]["operator"] == "and"
        assert len(result["selector"]["children"]) == 2


# =============================================================================
# Cohort Reference Criteria
# =============================================================================


class TestCohortCriteriaCohortRef:
    """Tests for CohortCriteria.in_cohort() and not_in_cohort() (T039-T042)."""

    def test_in_cohort(self) -> None:
        """in_cohort produces correct cohort reference selector node."""
        c = CohortCriteria.in_cohort(456)
        assert c._selector_node["property"] == "cohort"
        assert c._selector_node["value"] == 456
        assert c._selector_node["operator"] == "in"
        assert c._behavior_key is None
        assert c._behavior is None

    def test_not_in_cohort(self) -> None:
        """not_in_cohort produces 'not in' operator."""
        c = CohortCriteria.not_in_cohort(456)
        assert c._selector_node["property"] == "cohort"
        assert c._selector_node["value"] == 456
        assert c._selector_node["operator"] == "not in"
        assert c._behavior_key is None
        assert c._behavior is None

    def test_cd8_zero_cohort_id(self) -> None:
        """ValueError when cohort_id is 0 (CD8)."""
        with pytest.raises(ValueError, match="cohort_id must be a positive integer"):
            CohortCriteria.in_cohort(0)

    def test_cd8_negative_cohort_id(self) -> None:
        """ValueError when cohort_id is negative (CD8)."""
        with pytest.raises(ValueError, match="cohort_id must be a positive integer"):
            CohortCriteria.in_cohort(-1)

    def test_cd8_not_in_cohort_validation(self) -> None:
        """not_in_cohort also validates cohort_id (CD8)."""
        with pytest.raises(ValueError, match="cohort_id must be a positive integer"):
            CohortCriteria.not_in_cohort(0)

    def test_cohort_in_to_dict(self) -> None:
        """Cohort-only definition produces correct selector and empty behaviors."""
        c = CohortCriteria.in_cohort(456)
        d = CohortDefinition(c)
        result = d.to_dict()
        assert result["behaviors"] == {}
        leaf = result["selector"]["children"][0]
        assert leaf["property"] == "cohort"
        assert leaf["value"] == 456
        assert leaf["operator"] == "in"


# =============================================================================
# CRUD Integration
# =============================================================================


class TestCohortDefinitionCRUDIntegration:
    """Integration tests with CreateCohortParams (T045-T047)."""

    def test_definition_with_create_cohort_params(self) -> None:
        """CohortDefinition.to_dict() integrates with CreateCohortParams."""
        cohort_def = CohortDefinition.all_of(
            CohortCriteria.has_property("plan", "premium"),
            CohortCriteria.did_event("Purchase", at_least=3, within_days=30),
        )
        params = CreateCohortParams(
            name="Premium Purchasers",
            definition=cohort_def.to_dict(),
        )
        data = params.model_dump(exclude_none=True)

        # Top-level keys: name, selector, behaviors (definition flattened)
        assert "name" in data
        assert data["name"] == "Premium Purchasers"
        assert "selector" in data
        assert "behaviors" in data
        assert "definition" not in data

    def test_nested_definition_with_crud(self) -> None:
        """Complex nested definition flattens correctly via CreateCohortParams."""
        cohort_def = CohortDefinition.any_of(
            CohortDefinition.all_of(
                CohortCriteria.has_property("plan", "premium"),
                CohortCriteria.did_event("Login", at_least=5, within_days=30),
            ),
            CohortCriteria.in_cohort(789),
        )
        params = CreateCohortParams(
            name="Test",
            definition=cohort_def.to_dict(),
        )
        data = params.model_dump(exclude_none=True)

        assert "selector" in data
        assert data["selector"]["operator"] == "or"
        assert "behaviors" in data
        assert len(data["behaviors"]) == 1  # Only Login is behavioral

    def test_to_dict_is_json_serializable(self) -> None:
        """to_dict() output is fully JSON-serializable."""
        cohort_def = CohortDefinition.all_of(
            CohortCriteria.has_property("plan", "premium"),
            CohortCriteria.did_event(
                "Purchase",
                at_least=3,
                within_days=30,
                where=Filter.greater_than("amount", 100),
            ),
            CohortCriteria.in_cohort(456),
        )
        result = cohort_def.to_dict()
        serialized = json.dumps(result)
        assert isinstance(serialized, str)
        deserialized = json.loads(serialized)
        assert deserialized == result


# =============================================================================
# did_not_do_event Shorthand
# =============================================================================


class TestCohortCriteriaDidNotDoEvent:
    """Tests for CohortCriteria.did_not_do_event()."""

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"within_days": 30},
            {"within_weeks": 4},
            {"within_months": 3},
            {"from_date": "2024-01-01", "to_date": "2024-03-31"},
        ],
    )
    def test_equivalent_to_did_event_exactly_zero(self, kwargs: dict[str, Any]) -> None:
        """did_not_do_event is equivalent to did_event(exactly=0)."""
        a = CohortCriteria.did_not_do_event("Login", **kwargs)
        b = CohortCriteria.did_event("Login", exactly=0, **kwargs)
        assert a._selector_node == b._selector_node
        assert a._behavior == b._behavior


# =============================================================================
# Mixed Criteria Tests
# =============================================================================


class TestMixedCriteria:
    """Tests for definitions mixing behavioral, property, and cohort criteria."""

    def test_mixed_behavioral_and_property(self) -> None:
        """Definition with behavioral + property criteria serializes correctly."""
        d = CohortDefinition.all_of(
            CohortCriteria.has_property("plan", "premium"),
            CohortCriteria.did_event("Purchase", at_least=3, within_days=30),
        )
        result = d.to_dict()
        assert len(result["behaviors"]) == 1
        assert len(result["selector"]["children"]) == 2

        # Property child has no behavior reference
        prop_child = result["selector"]["children"][0]
        assert prop_child["property"] == "user"

        # Behavioral child references behavior
        behav_child = result["selector"]["children"][1]
        assert behav_child["property"] == "behaviors"
        assert behav_child["value"] == "bhvr_0"

    def test_all_criteria_types(self) -> None:
        """Definition with all three criteria types serializes correctly."""
        d = CohortDefinition.all_of(
            CohortCriteria.has_property("plan", "premium"),
            CohortCriteria.did_event("Purchase", at_least=1, within_days=30),
            CohortCriteria.in_cohort(456),
        )
        result = d.to_dict()
        assert len(result["behaviors"]) == 1  # Only behavioral has a behavior
        assert len(result["selector"]["children"]) == 3


# =============================================================================
# Edge Cases & Regression Tests
# =============================================================================


class TestToDictIsolation:
    """Tests that to_dict() does not leak internal mutable state."""

    def test_modifying_output_does_not_corrupt_criteria(self) -> None:
        """Mutating to_dict() output must not affect the frozen criterion."""
        c = CohortCriteria.did_event("Login", at_least=1, within_days=30)
        d = CohortDefinition(c)
        result = d.to_dict()
        result["behaviors"]["bhvr_0"]["window"]["value"] = 999
        # The original criterion must be untouched
        assert c._behavior is not None
        assert c._behavior["window"]["value"] == 30

    def test_multiple_to_dict_calls_are_independent(self) -> None:
        """Successive to_dict() calls produce independent dicts."""
        c = CohortCriteria.did_event("Login", at_least=1, within_days=30)
        d = CohortDefinition(c)
        r1 = d.to_dict()
        r2 = d.to_dict()
        r1["behaviors"]["bhvr_0"]["window"]["value"] = 888
        assert r2["behaviors"]["bhvr_0"]["window"]["value"] == 30

    def test_reused_criterion_behaviors_are_independent(self) -> None:
        """Same criterion used twice produces independent behavior copies."""
        c = CohortCriteria.did_event("Login", at_least=1, within_days=30)
        d = CohortDefinition.all_of(c, c)
        result = d.to_dict()
        result["behaviors"]["bhvr_0"]["window"]["value"] = 777
        assert result["behaviors"]["bhvr_1"]["window"]["value"] == 30

    def test_mutable_operand_list_not_leaked(self) -> None:
        """Mutating list operand in to_dict() output must not corrupt criterion."""
        c = CohortCriteria.has_property("tags", ["premium", "active"])
        d = CohortDefinition(c)
        result = d.to_dict()
        result["selector"]["children"][0]["operand"].append("CORRUPTED")
        assert c._selector_node["operand"] == ["premium", "active"]


class TestEmptyWhereList:
    """Tests for where=[] edge case."""

    def test_empty_where_list_treated_as_no_filter(self) -> None:
        """where=[] should produce None selector (same as no filter)."""
        c_no_filter = CohortCriteria.did_event("Login", at_least=1, within_days=30)
        c_empty = CohortCriteria.did_event(
            "Login", at_least=1, within_days=30, where=[]
        )
        assert c_no_filter._behavior is not None
        assert c_empty._behavior is not None
        assert c_no_filter._behavior["count"]["event_selector"]["selector"] is None
        assert c_empty._behavior["count"]["event_selector"]["selector"] is None


class TestTimeWindowValidation:
    """Tests for rolling window value validation."""

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"within_days": 0},
            {"within_days": -5},
            {"within_weeks": 0},
            {"within_months": -1},
        ],
    )
    def test_nonpositive_time_window_raises(self, kwargs: dict[str, Any]) -> None:
        """Non-positive time window values raise ValueError."""
        with pytest.raises(ValueError, match="time window value must be positive"):
            CohortCriteria.did_event("Login", at_least=1, **kwargs)


class TestDateRangeOrdering:
    """Tests for from_date <= to_date validation."""

    def test_from_date_after_to_date_raises(self) -> None:
        """from_date > to_date should raise ValueError."""
        with pytest.raises(
            ValueError, match="from_date must be before or equal to to_date"
        ):
            CohortCriteria.did_event(
                "Login",
                at_least=1,
                from_date="2025-12-31",
                to_date="2024-01-01",
            )

    def test_from_date_equals_to_date_is_valid(self) -> None:
        """from_date == to_date should be accepted (single day)."""
        c = CohortCriteria.did_event(
            "Login",
            at_least=1,
            from_date="2024-06-15",
            to_date="2024-06-15",
        )
        assert c._behavior is not None
        assert c._behavior["from_date"] == "2024-06-15"
