"""Property-based tests for Cohort Definition Builder using Hypothesis.

These tests verify invariants of CohortCriteria and CohortDefinition
that should hold for all possible inputs, catching edge cases that
example-based tests miss.

Usage:
    # Run with default profile (100 examples)
    pytest tests/test_cohort_definition_pbt.py

    # Run with dev profile (10 examples, verbose)
    HYPOTHESIS_PROFILE=dev pytest tests/test_cohort_definition_pbt.py

    # Run with CI profile (200 examples, deterministic)
    HYPOTHESIS_PROFILE=ci pytest tests/test_cohort_definition_pbt.py
"""

from __future__ import annotations

import json
from typing import Any, Literal, cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_headless.types import (
    CohortCriteria,
    CohortDefinition,
)

# =============================================================================
# Custom Strategies
# =============================================================================

# Non-empty event names (visible characters)
event_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

# Non-empty property names
property_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

# Non-negative integers for frequency params
frequencies = st.integers(min_value=0, max_value=10000)

# Positive integers for time windows
time_values = st.integers(min_value=1, max_value=365)

# Positive integers for cohort IDs
cohort_ids = st.integers(min_value=1, max_value=1000000)

# Frequency param choices
freq_param_choice = st.sampled_from(["at_least", "at_most", "exactly"])

# Time constraint choices
time_constraint_choice = st.sampled_from(
    ["within_days", "within_weeks", "within_months"]
)

# Property operator choices
property_operators = st.sampled_from(
    ["equals", "not_equals", "contains", "not_contains", "greater_than", "less_than"]
)


@st.composite
def valid_did_event_params(
    draw: st.DrawFn,
) -> dict[str, Any]:
    """Generate valid parameters for CohortCriteria.did_event().

    Generates either rolling-window or absolute date-range time constraints.

    Args:
        draw: Hypothesis draw function.

    Returns:
        Dict of valid did_event keyword arguments.
    """
    event = draw(event_names)
    freq_type = draw(freq_param_choice)
    freq_value = draw(frequencies)

    params: dict[str, Any] = {
        "event": event,
        freq_type: freq_value,
    }

    use_date_range = draw(st.booleans())
    if use_date_range:
        # Generate valid date range (2020-01-01 to 2025-12-31)
        start_ordinal = draw(st.integers(min_value=737425, max_value=739250))
        end_ordinal = draw(
            st.integers(min_value=start_ordinal, max_value=start_ordinal + 365)
        )
        from datetime import date as dt_date

        params["from_date"] = dt_date.fromordinal(start_ordinal).isoformat()
        params["to_date"] = dt_date.fromordinal(end_ordinal).isoformat()
    else:
        time_type = draw(time_constraint_choice)
        time_value = draw(time_values)
        params[time_type] = time_value

    return params


@st.composite
def behavioral_criteria(
    draw: st.DrawFn,
) -> CohortCriteria:
    """Generate valid CohortCriteria via did_event().

    Args:
        draw: Hypothesis draw function.

    Returns:
        Valid CohortCriteria instance.
    """
    params = draw(valid_did_event_params())
    return CohortCriteria.did_event(**params)


@st.composite
def property_criteria(
    draw: st.DrawFn,
) -> CohortCriteria:
    """Generate valid CohortCriteria via has_property().

    Args:
        draw: Hypothesis draw function.

    Returns:
        Valid CohortCriteria instance.
    """
    name = draw(property_names)
    value = draw(
        st.one_of(
            st.text(min_size=1, max_size=20),
            st.integers(min_value=-1000, max_value=1000),
            st.floats(
                allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6
            ),
            st.booleans(),
            st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=5),
        )
    )
    op = cast(
        Literal[
            "equals",
            "not_equals",
            "contains",
            "not_contains",
            "greater_than",
            "less_than",
        ],
        draw(property_operators),
    )
    return CohortCriteria.has_property(name, value, operator=op)


@st.composite
def cohort_ref_criteria(
    draw: st.DrawFn,
) -> CohortCriteria:
    """Generate valid CohortCriteria via in_cohort() or not_in_cohort().

    Args:
        draw: Hypothesis draw function.

    Returns:
        Valid CohortCriteria instance.
    """
    cid = draw(cohort_ids)
    if draw(st.booleans()):
        return CohortCriteria.in_cohort(cid)
    return CohortCriteria.not_in_cohort(cid)


# Any valid criterion
any_criteria = st.one_of(
    behavioral_criteria(), property_criteria(), cohort_ref_criteria()
)


@st.composite
def definition_trees(
    draw: st.DrawFn,
    max_depth: int = 3,
) -> CohortDefinition:
    """Generate CohortDefinition trees with varying depth and criteria types.

    Args:
        draw: Hypothesis draw function.
        max_depth: Maximum nesting depth.

    Returns:
        Valid CohortDefinition instance.
    """
    if max_depth <= 1 or draw(st.booleans()):
        # Leaf level: 1-3 criteria
        n = draw(st.integers(min_value=1, max_value=3))
        criteria = [draw(any_criteria) for _ in range(n)]
        op = draw(st.sampled_from(["all_of", "any_of"]))
        if op == "all_of":
            return CohortDefinition.all_of(*criteria)
        return CohortDefinition.any_of(*criteria)

    # Branch: mix of criteria and nested definitions
    children: list[CohortCriteria | CohortDefinition] = []
    n = draw(st.integers(min_value=2, max_value=3))
    for _ in range(n):
        if draw(st.booleans()):
            children.append(draw(any_criteria))
        else:
            children.append(draw(definition_trees(max_depth=max_depth - 1)))

    op = draw(st.sampled_from(["all_of", "any_of"]))
    if op == "all_of":
        return CohortDefinition.all_of(*children)
    return CohortDefinition.any_of(*children)


# =============================================================================
# PBT Tests for CohortCriteria Construction (T053)
# =============================================================================


class TestCohortCriteriaPBT:
    """Property-based tests for CohortCriteria construction."""

    @given(params=valid_did_event_params())
    def test_did_event_never_crashes(self, params: dict[str, Any]) -> None:
        """did_event with valid params never raises."""
        c = CohortCriteria.did_event(**params)
        assert c._selector_node is not None

    @given(params=valid_did_event_params())
    def test_did_event_always_behavioral(self, params: dict[str, Any]) -> None:
        """did_event always produces behavioral criteria with behavior key."""
        c = CohortCriteria.did_event(**params)
        assert c._selector_node["property"] == "behaviors"
        assert c._behavior_key is not None
        assert c._behavior is not None

    @given(params=valid_did_event_params())
    def test_did_event_selector_structure(self, params: dict[str, Any]) -> None:
        """did_event selector node always has required fields."""
        c = CohortCriteria.did_event(**params)
        node = c._selector_node
        assert "property" in node
        assert "value" in node
        assert "operator" in node
        assert "operand" in node
        assert node["operator"] in (">=", "<=", "==")

    @given(name=property_names, value=st.text(min_size=1, max_size=20))
    def test_has_property_never_crashes(self, name: str, value: str) -> None:
        """has_property with valid name/value never raises."""
        c = CohortCriteria.has_property(name, value)
        assert c._selector_node["property"] == "user"
        assert c._behavior_key is None
        assert c._behavior is None

    @given(cid=cohort_ids)
    def test_in_cohort_never_crashes(self, cid: int) -> None:
        """in_cohort with positive ID never raises."""
        c = CohortCriteria.in_cohort(cid)
        assert c._selector_node["property"] == "cohort"
        assert c._selector_node["value"] == cid


# =============================================================================
# PBT Tests for CohortDefinition.to_dict() (T054)
# =============================================================================


class TestCohortDefinitionToDictPBT:
    """Property-based tests for CohortDefinition.to_dict()."""

    @given(tree=definition_trees())
    @settings(max_examples=50)
    def test_to_dict_always_has_selector_and_behaviors(
        self, tree: CohortDefinition
    ) -> None:
        """to_dict() always returns dict with selector and behaviors."""
        result = tree.to_dict()
        assert "selector" in result
        assert "behaviors" in result

    @given(tree=definition_trees())
    @settings(max_examples=50)
    def test_to_dict_behavior_keys_unique(self, tree: CohortDefinition) -> None:
        """to_dict() never produces duplicate behavior keys."""
        result = tree.to_dict()
        keys = list(result["behaviors"].keys())
        assert len(keys) == len(set(keys))

    @given(tree=definition_trees())
    @settings(max_examples=50)
    def test_to_dict_behavior_keys_sequential(self, tree: CohortDefinition) -> None:
        """to_dict() produces sequential bhvr_N keys starting from 0."""
        result = tree.to_dict()
        keys = list(result["behaviors"].keys())
        for i, key in enumerate(keys):
            assert key == f"bhvr_{i}"

    @given(tree=definition_trees())
    @settings(max_examples=50)
    def test_to_dict_json_serializable(self, tree: CohortDefinition) -> None:
        """to_dict() output is always JSON-serializable."""
        result = tree.to_dict()
        serialized = json.dumps(result)
        assert isinstance(serialized, str)
        deserialized = json.loads(serialized)
        assert deserialized == result

    @given(tree=definition_trees())
    @settings(max_examples=50)
    def test_selector_tree_valid_structure(self, tree: CohortDefinition) -> None:
        """Selector tree nodes are all valid (combinator or leaf)."""
        result = tree.to_dict()

        def _check_node(node: dict[str, Any]) -> None:
            """Validate a selector tree node recursively.

            Args:
                node: Selector node to validate.
            """
            if "children" in node:
                # Combinator node
                assert "operator" in node
                assert node["operator"] in ("and", "or")
                for child in node["children"]:
                    _check_node(child)
            else:
                # Leaf node
                assert "property" in node
                assert node["property"] in ("behaviors", "user", "cohort")

        _check_node(result["selector"])

    @given(tree=definition_trees())
    @settings(max_examples=50)
    def test_selector_behavior_refs_match_behaviors_dict(
        self, tree: CohortDefinition
    ) -> None:
        """All behavior references in selector match keys in behaviors dict."""
        result = tree.to_dict()
        behavior_keys = set(result["behaviors"].keys())

        def _collect_refs(node: dict[str, Any]) -> set[str]:
            """Collect all behavior key references from selector tree.

            Args:
                node: Selector node to scan.

            Returns:
                Set of behavior key references found.
            """
            refs: set[str] = set()
            if "children" in node:
                for child in node["children"]:
                    refs |= _collect_refs(child)
            elif node.get("property") == "behaviors":
                refs.add(node["value"])
            return refs

        selector_refs = _collect_refs(result["selector"])
        assert selector_refs == behavior_keys


# =============================================================================
# PBT Tests for Validation Rules (T055)
# =============================================================================


class TestValidationPBT:
    """Property-based tests for validation rules."""

    @given(
        at_least=st.integers(min_value=0, max_value=100),
        at_most=st.integers(min_value=0, max_value=100),
    )
    def test_conflicting_frequency_always_raises(
        self, at_least: int, at_most: int
    ) -> None:
        """Multiple frequency params always raise ValueError (CD1)."""
        with pytest.raises(ValueError, match="exactly one of"):
            CohortCriteria.did_event(
                "Login",
                at_least=at_least,
                at_most=at_most,
                within_days=30,
            )

    @given(freq=st.integers(max_value=-1))
    def test_negative_frequency_always_raises(self, freq: int) -> None:
        """Negative frequency always raises ValueError (CD2)."""
        with pytest.raises(ValueError, match="frequency value must be >= 0"):
            CohortCriteria.did_event("Login", at_least=freq, within_days=30)

    @given(event_name=st.text(max_size=10).filter(lambda s: not s or not s.strip()))
    def test_empty_event_name_always_raises(self, event_name: str) -> None:
        """Empty/whitespace event names always raise ValueError (CD4)."""
        with pytest.raises(ValueError, match="event name must be non-empty"):
            CohortCriteria.did_event(event_name, at_least=1, within_days=30)

    @given(prop_name=st.text(max_size=10).filter(lambda s: not s or not s.strip()))
    def test_empty_property_name_always_raises(self, prop_name: str) -> None:
        """Empty/whitespace property names always raise ValueError (CD7)."""
        with pytest.raises(ValueError, match="property name must be non-empty"):
            CohortCriteria.has_property(prop_name, "value")

    @given(cid=st.integers(max_value=0))
    def test_nonpositive_cohort_id_always_raises(self, cid: int) -> None:
        """Non-positive cohort IDs always raise ValueError (CD8)."""
        with pytest.raises(ValueError, match="cohort_id must be a positive integer"):
            CohortCriteria.in_cohort(cid)
