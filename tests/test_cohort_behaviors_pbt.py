"""Property-based tests for cohort behavior types using Hypothesis.

These tests verify invariants of Filter.in_cohort/not_in_cohort,
CohortBreakdown, and CohortMetric that should hold for all valid
inputs. Covers tasks T052-T055.

Usage:
    # Run with default profile (100 examples)
    pytest tests/test_cohort_behaviors_pbt.py

    # Run with dev profile (10 examples)
    HYPOTHESIS_PROFILE=dev pytest tests/test_cohort_behaviors_pbt.py
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mixpanel_headless._internal.bookmark_builders import (
    build_filter_entry,
    build_group_section,
)
from mixpanel_headless.types import (
    CohortBreakdown,
    CohortCriteria,
    CohortDefinition,
    CohortMetric,
    Filter,
)

# =============================================================================
# Custom Strategies
# =============================================================================

positive_ints = st.integers(min_value=1, max_value=10_000_000)

non_empty_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

optional_names = st.one_of(st.none(), non_empty_names)

inline_cohort_defs = st.builds(
    lambda: CohortDefinition(
        CohortCriteria.did_event("Purchase", at_least=1, within_days=30)
    ),
)

cohort_ids = st.one_of(
    positive_ints,
    inline_cohort_defs,
)


# =============================================================================
# T052: Filter.in_cohort / Filter.not_in_cohort invariants
# =============================================================================


class TestFilterCohortPBT:
    """Property-based tests for cohort filter construction (T052)."""

    @given(cohort_id=positive_ints, name=optional_names)
    def test_in_cohort_property_is_always_cohorts(
        self, cohort_id: int, name: str | None
    ) -> None:
        """Filter.in_cohort always sets _property to '$cohorts'.

        Args:
            cohort_id: Any positive integer.
            name: Optional display name.
        """
        f = Filter.in_cohort(cohort_id, name)
        assert f._property == "$cohorts"

    @given(cohort_id=positive_ints, name=optional_names)
    def test_in_cohort_operator_is_contains(
        self, cohort_id: int, name: str | None
    ) -> None:
        """Filter.in_cohort always uses 'contains' operator.

        Args:
            cohort_id: Any positive integer.
            name: Optional display name.
        """
        f = Filter.in_cohort(cohort_id, name)
        assert f._operator == "contains"

    @given(cohort_id=positive_ints, name=optional_names)
    def test_not_in_cohort_operator_is_does_not_contain(
        self, cohort_id: int, name: str | None
    ) -> None:
        """Filter.not_in_cohort always uses 'does not contain' operator.

        Args:
            cohort_id: Any positive integer.
            name: Optional display name.
        """
        f = Filter.not_in_cohort(cohort_id, name)
        assert f._operator == "does not contain"

    @given(cohort_id=positive_ints, name=optional_names)
    def test_in_cohort_value_is_list_of_one_dict(
        self, cohort_id: int, name: str | None
    ) -> None:
        """Filter.in_cohort _value is always [{"cohort": {...}}].

        Args:
            cohort_id: Any positive integer.
            name: Optional display name.
        """
        f = Filter.in_cohort(cohort_id, name)
        assert isinstance(f._value, list)
        assert len(f._value) == 1
        assert isinstance(f._value[0], dict)
        assert "cohort" in f._value[0]

    @given(cohort_id=positive_ints, name=optional_names)
    def test_in_cohort_bookmark_entry_has_correct_structure(
        self, cohort_id: int, name: str | None
    ) -> None:
        """build_filter_entry produces valid bookmark JSON for any cohort filter.

        Args:
            cohort_id: Any positive integer.
            name: Optional display name.
        """
        f = Filter.in_cohort(cohort_id, name)
        entry = build_filter_entry(f)
        assert entry["value"] == "$cohorts"
        assert entry["filterType"] == "list"
        assert entry["filterOperator"] == "contains"
        assert isinstance(entry["filterValue"], list)
        assert len(entry["filterValue"]) == 1

    @given(cohort_id=st.integers(max_value=0))
    def test_in_cohort_rejects_non_positive(self, cohort_id: int) -> None:
        """Filter.in_cohort rejects non-positive cohort IDs.

        Args:
            cohort_id: Zero or negative integer.
        """
        with pytest.raises(ValueError, match="cohort must be a positive integer"):
            Filter.in_cohort(cohort_id)

    @given(
        name=st.text(
            alphabet=st.characters(whitelist_categories=["Zs"]),
            min_size=1,
            max_size=10,
        )
    )
    def test_in_cohort_rejects_whitespace_only_name(self, name: str) -> None:
        """Filter.in_cohort rejects whitespace-only names.

        Args:
            name: Whitespace-only string.
        """
        with pytest.raises(ValueError, match="cohort name must be non-empty"):
            Filter.in_cohort(1, name)


# =============================================================================
# T053: CohortBreakdown invariants
# =============================================================================


class TestCohortBreakdownPBT:
    """Property-based tests for CohortBreakdown construction (T053)."""

    @given(cohort_id=positive_ints, name=optional_names, include_negated=st.booleans())
    def test_construction_always_succeeds_with_valid_args(
        self, cohort_id: int, name: str | None, include_negated: bool
    ) -> None:
        """CohortBreakdown constructs successfully for valid args.

        Args:
            cohort_id: Positive integer.
            name: Optional non-empty name.
            include_negated: Boolean flag.
        """
        cb = CohortBreakdown(cohort_id, name, include_negated)
        assert cb.cohort == cohort_id
        assert cb.name == name
        assert cb.include_negated == include_negated

    @given(cohort_id=positive_ints, name=optional_names, include_negated=st.booleans())
    def test_group_section_produces_non_empty_cohorts(
        self, cohort_id: int, name: str | None, include_negated: bool
    ) -> None:
        """build_group_section always produces non-empty cohorts array.

        Args:
            cohort_id: Positive integer.
            name: Optional non-empty name.
            include_negated: Boolean flag.
        """
        cb = CohortBreakdown(cohort_id, name, include_negated)
        group = build_group_section(cb)
        assert len(group) == 1
        entry = group[0]
        assert "cohorts" in entry
        cohorts: list[dict[str, Any]] = entry["cohorts"]
        assert len(cohorts) >= 1

        if include_negated:
            assert len(cohorts) == 2
            assert cohorts[0]["negated"] is False
            assert cohorts[1]["negated"] is True
        else:
            assert len(cohorts) == 1
            assert cohorts[0]["negated"] is False

    @given(cohort_id=positive_ints, name=non_empty_names)
    def test_group_section_value_labels_contain_name(
        self, cohort_id: int, name: str
    ) -> None:
        """Group section value labels always contain the cohort name.

        Args:
            cohort_id: Positive integer.
            name: Non-empty display name.
        """
        cb = CohortBreakdown(cohort_id, name)
        group = build_group_section(cb)
        value_labels: list[str] = group[0]["value"]
        assert name in value_labels

    @given(cohort_id=st.integers(max_value=0))
    def test_rejects_non_positive_id(self, cohort_id: int) -> None:
        """CohortBreakdown rejects non-positive cohort IDs.

        Args:
            cohort_id: Zero or negative integer.
        """
        with pytest.raises(ValueError, match="cohort must be a positive integer"):
            CohortBreakdown(cohort_id)


# =============================================================================
# T054: CohortMetric invariants
# =============================================================================


class TestCohortMetricPBT:
    """Property-based tests for CohortMetric construction (T054)."""

    @given(cohort_id=positive_ints, name=optional_names)
    def test_construction_always_succeeds_with_valid_args(
        self, cohort_id: int, name: str | None
    ) -> None:
        """CohortMetric constructs successfully for valid args.

        Args:
            cohort_id: Positive integer.
            name: Optional non-empty name.
        """
        cm = CohortMetric(cohort_id, name)
        assert cm.cohort == cohort_id
        assert cm.name == name

    @given(cohort_id=positive_ints, name=optional_names)
    def test_is_frozen(self, cohort_id: int, name: str | None) -> None:
        """CohortMetric is immutable (frozen dataclass).

        Args:
            cohort_id: Positive integer.
            name: Optional non-empty name.
        """
        cm = CohortMetric(cohort_id, name)
        with pytest.raises(AttributeError):
            cm.cohort = 999  # type: ignore[misc]

    @given(cohort_id=st.integers(max_value=0))
    def test_rejects_non_positive_id(self, cohort_id: int) -> None:
        """CohortMetric rejects non-positive cohort IDs.

        Args:
            cohort_id: Zero or negative integer.
        """
        with pytest.raises(ValueError, match="cohort must be a positive integer"):
            CohortMetric(cohort_id)


# =============================================================================
# T055: Integration with CohortDefinition
# =============================================================================


class TestCohortDefinitionIntegrationPBT:
    """Property-based tests for inline CohortDefinition integration (T055)."""

    @given(name=non_empty_names)
    def test_filter_in_cohort_with_inline_def(self, name: str) -> None:
        """Filter.in_cohort with inline CohortDefinition always has raw_cohort.

        Args:
            name: Non-empty display name.
        """
        cd = CohortDefinition(
            CohortCriteria.did_event("Purchase", at_least=1, within_days=30)
        )
        f = Filter.in_cohort(cd, name=name)
        assert isinstance(f._value, list)
        first = f._value[0]
        assert isinstance(first, dict)
        cohort_data: dict[str, Any] = first["cohort"]
        assert "raw_cohort" in cohort_data
        assert "id" not in cohort_data
        assert cohort_data["name"] == name

    @given(name=non_empty_names, include_negated=st.booleans())
    def test_cohort_breakdown_with_inline_def(
        self, name: str, include_negated: bool
    ) -> None:
        """CohortBreakdown with inline CohortDefinition uses raw_cohort.

        Args:
            name: Non-empty display name.
            include_negated: Whether to include negated segment.
        """
        cd = CohortDefinition(
            CohortCriteria.did_event("Purchase", at_least=1, within_days=30)
        )
        cb = CohortBreakdown(cd, name=name, include_negated=include_negated)
        group = build_group_section(cb)
        cohorts: list[dict[str, Any]] = group[0]["cohorts"]
        assert "raw_cohort" in cohorts[0]
        assert "id" not in cohorts[0]

    @given(name=non_empty_names)
    def test_cohort_metric_with_inline_def_rejected_cm5(self, name: str) -> None:
        """CM5: CohortMetric rejects inline CohortDefinition at construction.

        Args:
            name: Non-empty display name.
        """
        cd = CohortDefinition(
            CohortCriteria.did_event("Purchase", at_least=1, within_days=30)
        )
        with pytest.raises(ValueError, match="does not support inline"):
            CohortMetric(cd, name=name)
