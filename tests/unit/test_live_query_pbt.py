"""Property-based tests for LiveQueryService transform functions using Hypothesis.

These tests verify mathematical invariants that should hold for all possible inputs,
catching edge cases that example-based tests might miss.

Properties tested:
- _transform_funnel: Conversion rate bounds, first step is 1.0, division-by-zero safety
- _transform_retention: Retention bounds, cohort ordering, division-by-zero safety
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_data._internal.services.live_query import (
    _transform_funnel,
    _transform_retention,
)

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid date strings (YYYY-MM-DD format)
date_strings = st.dates().map(lambda d: d.strftime("%Y-%m-%d"))

# Strategy for event names
event_names = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
)

# Strategy for funnel step counts (non-negative integers)
step_counts = st.integers(min_value=0, max_value=1_000_000)

# Strategy for cohort sizes
cohort_sizes = st.integers(min_value=0, max_value=1_000_000)

# Strategy for retention count arrays (values <= cohort_size)
time_units = st.sampled_from(["day", "week", "month"])


@st.composite
def funnel_step(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a single funnel step as returned by the API."""
    event = draw(event_names)
    count = draw(step_counts)
    return {"event": event, "count": count}


@st.composite
def funnel_day_data(draw: st.DrawFn, num_steps: int) -> dict[str, Any]:
    """Generate funnel data for a single date."""
    steps = [draw(funnel_step()) for _ in range(num_steps)]
    return {"steps": steps, "analysis": {}}


@st.composite
def raw_funnel_response(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a raw funnel API response.

    The API returns:
    {
        "data": {
            "2024-01-01": {"steps": [...], "analysis": {...}},
            "2024-01-02": {"steps": [...], "analysis": {...}},
        }
    }
    """
    num_dates = draw(st.integers(min_value=0, max_value=5))
    num_steps = draw(st.integers(min_value=0, max_value=10))

    dates = draw(
        st.lists(date_strings, min_size=num_dates, max_size=num_dates, unique=True)
    )

    data: dict[str, Any] = {}
    for date in dates:
        data[date] = draw(funnel_day_data(num_steps))

    return {"data": data}


@st.composite
def raw_retention_response(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a raw retention API response.

    The API returns:
    {
        "2024-01-01": {"first": cohort_size, "counts": [count0, count1, ...]},
        "2024-01-02": {"first": cohort_size, "counts": [...]},
    }
    """
    num_cohorts = draw(st.integers(min_value=0, max_value=10))
    num_periods = draw(st.integers(min_value=0, max_value=20))

    dates = draw(
        st.lists(date_strings, min_size=num_cohorts, max_size=num_cohorts, unique=True)
    )

    result: dict[str, Any] = {}
    for date in dates:
        cohort_size = draw(cohort_sizes)
        # Counts must be <= cohort_size to be realistic, but the transform function
        # should handle any counts (it just divides by cohort_size)
        counts = draw(
            st.lists(
                st.integers(min_value=0, max_value=max(1, cohort_size * 2)),
                min_size=num_periods,
                max_size=num_periods,
            )
        )
        result[date] = {"first": cohort_size, "counts": counts}

    return result


# =============================================================================
# _transform_funnel Property Tests
# =============================================================================


class TestTransformFunnelProperties:
    """Property-based tests for _transform_funnel function.

    The function transforms raw funnel API responses and must:
    1. Set first step conversion_rate to 1.0
    2. Keep all conversion rates in [0.0, 1.0] (when counts don't increase)
    3. Handle division by zero (prev_count=0 → conversion_rate=0.0)
    4. Calculate overall conversion correctly
    """

    @given(
        raw=raw_funnel_response(),
        funnel_id=st.integers(min_value=1, max_value=1_000_000),
        from_date=date_strings,
        to_date=date_strings,
    )
    @settings(max_examples=100)
    def test_first_step_conversion_is_always_one(
        self,
        raw: dict[str, Any],
        funnel_id: int,
        from_date: str,
        to_date: str,
    ) -> None:
        """First step conversion_rate should always be 1.0 for non-empty funnels.

        The first step represents 100% of users who entered the funnel,
        so its conversion rate is always 1.0 by definition.

        Args:
            raw: Raw funnel API response.
            funnel_id: Funnel identifier.
            from_date: Query start date.
            to_date: Query end date.
        """
        result = _transform_funnel(raw, funnel_id, from_date, to_date)

        if result.steps:
            assert result.steps[0].conversion_rate == 1.0

    @given(
        raw=raw_funnel_response(),
        funnel_id=st.integers(min_value=1, max_value=1_000_000),
        from_date=date_strings,
        to_date=date_strings,
    )
    @settings(max_examples=100)
    def test_conversion_rates_are_non_negative(
        self,
        raw: dict[str, Any],
        funnel_id: int,
        from_date: str,
        to_date: str,
    ) -> None:
        """All conversion rates should be non-negative.

        Conversion rates represent percentages and cannot be negative.

        Args:
            raw: Raw funnel API response.
            funnel_id: Funnel identifier.
            from_date: Query start date.
            to_date: Query end date.
        """
        result = _transform_funnel(raw, funnel_id, from_date, to_date)

        for step in result.steps:
            assert step.conversion_rate >= 0.0, (
                f"Step {step.event} has negative conversion_rate: {step.conversion_rate}"
            )

        assert result.conversion_rate >= 0.0

    @given(
        raw=raw_funnel_response(),
        funnel_id=st.integers(min_value=1, max_value=1_000_000),
        from_date=date_strings,
        to_date=date_strings,
    )
    @settings(max_examples=100)
    def test_overall_conversion_formula(
        self,
        raw: dict[str, Any],
        funnel_id: int,
        from_date: str,
        to_date: str,
    ) -> None:
        """Overall conversion should be last_count / first_count or 0.0.

        The overall conversion rate is defined as the percentage of users
        who completed the entire funnel (last step / first step).
        When first step count is 0, it should be 0.0 to avoid division by zero.

        Args:
            raw: Raw funnel API response.
            funnel_id: Funnel identifier.
            from_date: Query start date.
            to_date: Query end date.
        """
        result = _transform_funnel(raw, funnel_id, from_date, to_date)

        if result.steps:
            first_count = result.steps[0].count
            last_count = result.steps[-1].count

            if first_count > 0:
                expected = last_count / first_count
                assert abs(result.conversion_rate - expected) < 1e-9
            else:
                assert result.conversion_rate == 0.0
        else:
            assert result.conversion_rate == 0.0

    @given(
        raw=raw_funnel_response(),
        funnel_id=st.integers(min_value=1, max_value=1_000_000),
        from_date=date_strings,
        to_date=date_strings,
    )
    @settings(max_examples=100)
    def test_empty_funnel_has_zero_conversion(
        self,
        raw: dict[str, Any],
        funnel_id: int,
        from_date: str,
        to_date: str,
    ) -> None:
        """Empty funnels should have conversion_rate of 0.0.

        Args:
            raw: Raw funnel API response.
            funnel_id: Funnel identifier.
            from_date: Query start date.
            to_date: Query end date.
        """
        result = _transform_funnel(raw, funnel_id, from_date, to_date)

        if not result.steps:
            assert result.conversion_rate == 0.0

    @given(
        funnel_id=st.integers(min_value=1, max_value=1_000_000),
        from_date=date_strings,
        to_date=date_strings,
        date=date_strings,
        num_steps=st.integers(min_value=2, max_value=5),
    )
    def test_zero_previous_count_yields_zero_conversion(
        self,
        funnel_id: int,
        from_date: str,
        to_date: str,
        date: str,
        num_steps: int,
    ) -> None:
        """When previous step count is 0, conversion_rate should be 0.0.

        This tests the division-by-zero safety: if step N-1 has 0 users,
        step N's conversion rate should be 0.0, not cause an error.

        Args:
            funnel_id: Funnel identifier.
            from_date: Query start date.
            to_date: Query end date.
            date: Date for the funnel data.
            num_steps: Number of steps to generate.
        """
        # Create a funnel where one step has count=0
        steps = [{"event": f"Step {i}", "count": 100} for i in range(num_steps)]
        # Set a middle step to 0 to test division by zero
        zero_step_idx = num_steps // 2
        steps[zero_step_idx]["count"] = 0

        raw = {"data": {date: {"steps": steps, "analysis": {}}}}

        result = _transform_funnel(raw, funnel_id, from_date, to_date)

        # The step after the zero-count step should have conversion_rate 0.0
        if zero_step_idx + 1 < len(result.steps):
            assert result.steps[zero_step_idx + 1].conversion_rate == 0.0


# =============================================================================
# _transform_retention Property Tests
# =============================================================================


class TestTransformRetentionProperties:
    """Property-based tests for _transform_retention function.

    The function transforms raw retention API responses and must:
    1. Keep all retention values non-negative
    2. Handle division by zero (cohort_size=0 → retention=0.0)
    3. Sort cohorts by date ascending
    """

    @given(
        raw=raw_retention_response(),
        born_event=event_names,
        return_event=event_names,
        from_date=date_strings,
        to_date=date_strings,
        unit=time_units,
    )
    @settings(max_examples=100)
    def test_retention_values_are_non_negative(
        self,
        raw: dict[str, Any],
        born_event: str,
        return_event: str,
        from_date: str,
        to_date: str,
        unit: str,
    ) -> None:
        """All retention values should be non-negative.

        Retention represents a percentage and cannot be negative.

        Args:
            raw: Raw retention API response.
            born_event: Event defining cohort membership.
            return_event: Event defining return.
            from_date: Query start date.
            to_date: Query end date.
            unit: Time unit for retention periods.
        """
        result = _transform_retention(
            raw,
            born_event,
            return_event,
            from_date,
            to_date,
            unit,  # type: ignore[arg-type]
        )

        for cohort in result.cohorts:
            for i, retention_value in enumerate(cohort.retention):
                assert retention_value >= 0.0, (
                    f"Cohort {cohort.date} period {i} has negative retention: "
                    f"{retention_value}"
                )

    @given(
        raw=raw_retention_response(),
        born_event=event_names,
        return_event=event_names,
        from_date=date_strings,
        to_date=date_strings,
        unit=time_units,
    )
    @settings(max_examples=100)
    def test_cohorts_are_sorted_by_date(
        self,
        raw: dict[str, Any],
        born_event: str,
        return_event: str,
        from_date: str,
        to_date: str,
        unit: str,
    ) -> None:
        """Cohorts should be sorted by date in ascending order.

        This is explicitly documented in the docstring: "Cohorts sorted by date (ascending)."

        Args:
            raw: Raw retention API response.
            born_event: Event defining cohort membership.
            return_event: Event defining return.
            from_date: Query start date.
            to_date: Query end date.
            unit: Time unit for retention periods.
        """
        result = _transform_retention(
            raw,
            born_event,
            return_event,
            from_date,
            to_date,
            unit,  # type: ignore[arg-type]
        )

        dates = [cohort.date for cohort in result.cohorts]
        assert dates == sorted(dates), f"Cohorts not sorted: {dates}"

    @given(
        born_event=event_names,
        return_event=event_names,
        from_date=date_strings,
        to_date=date_strings,
        unit=time_units,
        date=date_strings,
        num_periods=st.integers(min_value=1, max_value=10),
    )
    def test_zero_cohort_size_yields_zero_retention(
        self,
        born_event: str,
        return_event: str,
        from_date: str,
        to_date: str,
        unit: str,
        date: str,
        num_periods: int,
    ) -> None:
        """When cohort size is 0, all retention values should be 0.0.

        This tests the division-by-zero safety: if no users are in the cohort,
        retention should be 0.0, not cause an error.

        Args:
            born_event: Event defining cohort membership.
            return_event: Event defining return.
            from_date: Query start date.
            to_date: Query end date.
            unit: Time unit for retention periods.
            date: Cohort date.
            num_periods: Number of retention periods.
        """
        # Create a cohort with size 0 but with counts (edge case)
        raw = {date: {"first": 0, "counts": [10] * num_periods}}

        result = _transform_retention(
            raw,
            born_event,
            return_event,
            from_date,
            to_date,
            unit,  # type: ignore[arg-type]
        )

        assert len(result.cohorts) == 1
        cohort = result.cohorts[0]

        # All retention values should be 0.0 (not errors from division by zero)
        for retention_value in cohort.retention:
            assert retention_value == 0.0

    @given(
        born_event=event_names,
        return_event=event_names,
        from_date=date_strings,
        to_date=date_strings,
        unit=time_units,
        date=date_strings,
        cohort_size=st.integers(min_value=1, max_value=1000),
        counts=st.lists(
            st.integers(min_value=0, max_value=1000), min_size=1, max_size=10
        ),
    )
    def test_retention_formula(
        self,
        born_event: str,
        return_event: str,
        from_date: str,
        to_date: str,
        unit: str,
        date: str,
        cohort_size: int,
        counts: list[int],
    ) -> None:
        """Retention values should equal count / cohort_size.

        This verifies the core calculation documented in the docstring.

        Args:
            born_event: Event defining cohort membership.
            return_event: Event defining return.
            from_date: Query start date.
            to_date: Query end date.
            unit: Time unit for retention periods.
            date: Cohort date.
            cohort_size: Number of users in cohort.
            counts: Return counts per period.
        """
        raw = {date: {"first": cohort_size, "counts": counts}}

        result = _transform_retention(
            raw,
            born_event,
            return_event,
            from_date,
            to_date,
            unit,  # type: ignore[arg-type]
        )

        assert len(result.cohorts) == 1
        cohort = result.cohorts[0]

        for i, count in enumerate(counts):
            expected = count / cohort_size
            assert abs(cohort.retention[i] - expected) < 1e-9, (
                f"Period {i}: expected {expected}, got {cohort.retention[i]}"
            )

    @given(
        born_event=event_names,
        return_event=event_names,
        from_date=date_strings,
        to_date=date_strings,
        unit=time_units,
    )
    def test_empty_response_yields_empty_cohorts(
        self,
        born_event: str,
        return_event: str,
        from_date: str,
        to_date: str,
        unit: str,
    ) -> None:
        """Empty API response should produce empty cohorts list.

        Args:
            born_event: Event defining cohort membership.
            return_event: Event defining return.
            from_date: Query start date.
            to_date: Query end date.
            unit: Time unit for retention periods.
        """
        raw: dict[str, Any] = {}

        result = _transform_retention(
            raw,
            born_event,
            return_event,
            from_date,
            to_date,
            unit,  # type: ignore[arg-type]
        )

        assert result.cohorts == []
