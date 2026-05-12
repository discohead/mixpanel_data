"""Unit tests for funnel query types (FunnelStep, Exclusion, HoldingConstant, FunnelQueryResult)."""

from __future__ import annotations

import dataclasses
import json

import pandas as pd
import pytest

from mixpanel_headless.types import (
    Exclusion,
    Filter,
    FunnelQueryResult,
    FunnelStep,
    HoldingConstant,
)

# =============================================================================
# FunnelStep Tests (T004)
# =============================================================================


class TestFunnelStep:
    """Tests for FunnelStep frozen dataclass."""

    def test_construction_with_event_only(self) -> None:
        """FunnelStep can be constructed with just an event name."""
        step = FunnelStep("Signup")

        assert step.event == "Signup"

    def test_defaults(self) -> None:
        """FunnelStep defaults: label=None, filters=None, filters_combinator='all', order=None."""
        step = FunnelStep("Signup")

        assert step.label is None
        assert step.filters is None
        assert step.filters_combinator == "all"
        assert step.order is None

    def test_construction_with_all_fields(self) -> None:
        """FunnelStep accepts all fields explicitly."""
        f = Filter.equals("country", "US")
        step = FunnelStep(
            event="Purchase",
            label="High-Value Purchase",
            filters=[f],
            filters_combinator="any",
            order="loose",
        )

        assert step.event == "Purchase"
        assert step.label == "High-Value Purchase"
        assert step.filters is not None
        assert len(step.filters) == 1
        assert step.filters_combinator == "any"
        assert step.order == "loose"

    def test_construction_with_label(self) -> None:
        """FunnelStep accepts an optional label."""
        step = FunnelStep("Signup", label="User Registration")

        assert step.label == "User Registration"

    def test_construction_with_multiple_filters(self) -> None:
        """FunnelStep accepts multiple filters in a list."""
        f1 = Filter.equals("country", "US")
        f2 = Filter.greater_than("amount", 50)
        step = FunnelStep("Purchase", filters=[f1, f2])

        assert step.filters is not None
        assert len(step.filters) == 2

    def test_construction_with_order_any(self) -> None:
        """FunnelStep accepts order='any' for per-step ordering override."""
        step = FunnelStep("Checkout", order="any")

        assert step.order == "any"

    def test_frozen_immutability_event(self) -> None:
        """Assigning to FunnelStep.event raises FrozenInstanceError."""
        step = FunnelStep("Signup")

        with pytest.raises(dataclasses.FrozenInstanceError):
            step.event = "Modified"  # type: ignore[misc]

    def test_frozen_immutability_label(self) -> None:
        """Assigning to FunnelStep.label raises FrozenInstanceError."""
        step = FunnelStep("Signup", label="Original")

        with pytest.raises(dataclasses.FrozenInstanceError):
            step.label = "Modified"  # type: ignore[misc]

    def test_frozen_immutability_filters(self) -> None:
        """Assigning to FunnelStep.filters raises FrozenInstanceError."""
        step = FunnelStep("Signup")

        with pytest.raises(dataclasses.FrozenInstanceError):
            step.filters = []  # type: ignore[misc]

    def test_frozen_immutability_filters_combinator(self) -> None:
        """Assigning to FunnelStep.filters_combinator raises FrozenInstanceError."""
        step = FunnelStep("Signup")

        with pytest.raises(dataclasses.FrozenInstanceError):
            step.filters_combinator = "any"  # type: ignore[misc]

    def test_frozen_immutability_order(self) -> None:
        """Assigning to FunnelStep.order raises FrozenInstanceError."""
        step = FunnelStep("Signup")

        with pytest.raises(dataclasses.FrozenInstanceError):
            step.order = "loose"  # type: ignore[misc]

    def test_string_interchangeability_in_list(self) -> None:
        """FunnelStep objects and plain strings can coexist in a list."""
        steps: list[FunnelStep | str] = [
            "Signup",
            FunnelStep("Add to Cart"),
            "Purchase",
        ]

        assert len(steps) == 3
        assert isinstance(steps[0], str)
        assert isinstance(steps[1], FunnelStep)
        assert isinstance(steps[2], str)

    def test_filters_combinator_defaults_to_all(self) -> None:
        """FunnelStep filters_combinator defaults to 'all' (AND logic)."""
        step = FunnelStep("Purchase", filters=[Filter.equals("country", "US")])

        assert step.filters_combinator == "all"

    def test_empty_filters_list(self) -> None:
        """FunnelStep accepts an empty filters list."""
        step = FunnelStep("Signup", filters=[])

        assert step.filters == []


# =============================================================================
# Exclusion Tests (T005)
# =============================================================================


class TestExclusion:
    """Tests for Exclusion frozen dataclass."""

    def test_construction_with_event_only(self) -> None:
        """Exclusion can be constructed with just an event name."""
        ex = Exclusion("Logout")

        assert ex.event == "Logout"

    def test_defaults(self) -> None:
        """Exclusion defaults: from_step=0, to_step=None."""
        ex = Exclusion("Logout")

        assert ex.from_step == 0
        assert ex.to_step is None

    def test_construction_with_all_fields(self) -> None:
        """Exclusion accepts all fields explicitly."""
        ex = Exclusion("Refund", from_step=1, to_step=2)

        assert ex.event == "Refund"
        assert ex.from_step == 1
        assert ex.to_step == 2

    def test_construction_with_from_step_only(self) -> None:
        """Exclusion accepts from_step without to_step."""
        ex = Exclusion("Cancel", from_step=2)

        assert ex.from_step == 2
        assert ex.to_step is None

    def test_construction_with_to_step_only(self) -> None:
        """Exclusion accepts to_step without from_step (from_step defaults to 0)."""
        ex = Exclusion("Cancel", to_step=3)

        assert ex.from_step == 0
        assert ex.to_step == 3

    def test_string_shorthand_equivalence(self) -> None:
        """Exclusion('X') has from_step=0 and to_step=None, equivalent to full-range exclusion."""
        ex = Exclusion("Logout")

        assert ex.event == "Logout"
        assert ex.from_step == 0
        assert ex.to_step is None

    def test_frozen_immutability_event(self) -> None:
        """Assigning to Exclusion.event raises FrozenInstanceError."""
        ex = Exclusion("Logout")

        with pytest.raises(dataclasses.FrozenInstanceError):
            ex.event = "Modified"  # type: ignore[misc]

    def test_frozen_immutability_from_step(self) -> None:
        """Assigning to Exclusion.from_step raises FrozenInstanceError."""
        ex = Exclusion("Logout")

        with pytest.raises(dataclasses.FrozenInstanceError):
            ex.from_step = 5  # type: ignore[misc]

    def test_frozen_immutability_to_step(self) -> None:
        """Assigning to Exclusion.to_step raises FrozenInstanceError."""
        ex = Exclusion("Logout")

        with pytest.raises(dataclasses.FrozenInstanceError):
            ex.to_step = 3  # type: ignore[misc]

    def test_zero_indexed_step_range(self) -> None:
        """Exclusion step indices are 0-indexed."""
        ex = Exclusion("Refund", from_step=0, to_step=0)

        assert ex.from_step == 0
        assert ex.to_step == 0


# =============================================================================
# HoldingConstant Tests (T006)
# =============================================================================


class TestHoldingConstant:
    """Tests for HoldingConstant frozen dataclass."""

    def test_construction_with_property_only(self) -> None:
        """HoldingConstant can be constructed with just a property name."""
        hc = HoldingConstant("platform")

        assert hc.property == "platform"

    def test_default_resource_type(self) -> None:
        """HoldingConstant defaults resource_type to 'events'."""
        hc = HoldingConstant("platform")

        assert hc.resource_type == "events"

    def test_construction_with_events_resource_type(self) -> None:
        """HoldingConstant accepts resource_type='events' explicitly."""
        hc = HoldingConstant("browser", resource_type="events")

        assert hc.resource_type == "events"

    def test_construction_with_people_resource_type(self) -> None:
        """HoldingConstant accepts resource_type='people' for user-profile properties."""
        hc = HoldingConstant("plan_tier", resource_type="people")

        assert hc.property == "plan_tier"
        assert hc.resource_type == "people"

    def test_frozen_immutability_property(self) -> None:
        """Assigning to HoldingConstant.property raises FrozenInstanceError."""
        hc = HoldingConstant("platform")

        with pytest.raises(dataclasses.FrozenInstanceError):
            hc.property = "modified"  # type: ignore[misc]

    def test_frozen_immutability_resource_type(self) -> None:
        """Assigning to HoldingConstant.resource_type raises FrozenInstanceError."""
        hc = HoldingConstant("platform")

        with pytest.raises(dataclasses.FrozenInstanceError):
            hc.resource_type = "people"  # type: ignore[misc]


# =============================================================================
# FunnelQueryResult Tests (T007)
# =============================================================================


_SAMPLE_STEPS_DATA = [
    {
        "event": "Signup",
        "count": 1000,
        "step_conv_ratio": 1.0,
        "overall_conv_ratio": 1.0,
        "avg_time": 0.0,
        "avg_time_from_start": 0.0,
    },
    {
        "event": "Purchase",
        "count": 120,
        "step_conv_ratio": 0.12,
        "overall_conv_ratio": 0.12,
        "avg_time": 86400.0,
        "avg_time_from_start": 86400.0,
    },
]


class TestFunnelQueryResult:
    """Tests for FunnelQueryResult frozen dataclass."""

    def test_construction_with_required_fields(self) -> None:
        """FunnelQueryResult can be constructed with only required fields."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
        )

        assert result.computed_at == "2025-04-05T12:00:00Z"
        assert result.from_date == "2025-01-01"
        assert result.to_date == "2025-03-31"

    def test_default_values(self) -> None:
        """FunnelQueryResult defaults: steps_data=[], series={}, params={}, meta={}."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
        )

        assert result.steps_data == []
        assert result.series == {}
        assert result.params == {}
        assert result.meta == {}

    def test_construction_with_all_fields(self) -> None:
        """FunnelQueryResult accepts all fields explicitly."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=_SAMPLE_STEPS_DATA,
            series={"key": "value"},
            params={"funnel_type": "steps"},
            meta={"is_cached": True},
        )

        assert len(result.steps_data) == 2
        assert result.series == {"key": "value"}
        assert result.params == {"funnel_type": "steps"}
        assert result.meta == {"is_cached": True}

    def test_overall_conversion_rate_with_steps(self) -> None:
        """overall_conversion_rate returns last step's overall_conv_ratio."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=_SAMPLE_STEPS_DATA,
        )

        assert result.overall_conversion_rate == 0.12

    def test_overall_conversion_rate_empty_steps(self) -> None:
        """overall_conversion_rate returns 0.0 when steps_data is empty."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
        )

        assert result.overall_conversion_rate == 0.0

    def test_overall_conversion_rate_single_step(self) -> None:
        """overall_conversion_rate with a single step returns that step's ratio."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=[
                {
                    "event": "Signup",
                    "count": 500,
                    "step_conv_ratio": 1.0,
                    "overall_conv_ratio": 1.0,
                    "avg_time": 0.0,
                    "avg_time_from_start": 0.0,
                }
            ],
        )

        assert result.overall_conversion_rate == 1.0

    def test_overall_conversion_rate_missing_key(self) -> None:
        """overall_conversion_rate returns 0.0 if last step lacks overall_conv_ratio key."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=[{"event": "Signup", "count": 100}],
        )

        assert result.overall_conversion_rate == 0.0

    def test_df_returns_dataframe(self) -> None:
        """df property returns a pandas DataFrame."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=_SAMPLE_STEPS_DATA,
        )

        df = result.df
        assert isinstance(df, pd.DataFrame)

    def test_df_has_expected_columns(self) -> None:
        """df has columns: step, event, count, step_conv_ratio, overall_conv_ratio, avg_time, avg_time_from_start."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=_SAMPLE_STEPS_DATA,
        )

        df = result.df
        expected_cols = [
            "step",
            "event",
            "count",
            "step_conv_ratio",
            "overall_conv_ratio",
            "avg_time",
            "avg_time_from_start",
        ]
        assert list(df.columns) == expected_cols

    def test_df_row_count_matches_steps(self) -> None:
        """df has one row per step in steps_data."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=_SAMPLE_STEPS_DATA,
        )

        df = result.df
        assert len(df) == 2

    def test_df_step_numbers_are_one_indexed(self) -> None:
        """df step column is 1-indexed (1, 2, 3, ...)."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=_SAMPLE_STEPS_DATA,
        )

        df = result.df
        assert list(df["step"]) == [1, 2]

    def test_df_values_match_steps_data(self) -> None:
        """df values correspond to the steps_data input."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=_SAMPLE_STEPS_DATA,
        )

        df = result.df
        assert list(df["event"]) == ["Signup", "Purchase"]
        assert list(df["count"]) == [1000, 120]
        assert list(df["step_conv_ratio"]) == [1.0, 0.12]
        assert list(df["overall_conv_ratio"]) == [1.0, 0.12]
        assert list(df["avg_time"]) == [0.0, 86400.0]
        assert list(df["avg_time_from_start"]) == [0.0, 86400.0]

    def test_df_empty_steps_data(self) -> None:
        """df with empty steps_data returns empty DataFrame with correct columns."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
        )

        df = result.df
        assert len(df) == 0
        expected_cols = [
            "step",
            "event",
            "count",
            "step_conv_ratio",
            "overall_conv_ratio",
            "avg_time",
            "avg_time_from_start",
        ]
        assert list(df.columns) == expected_cols

    def test_df_cached(self) -> None:
        """df is cached on first access (same object returned on subsequent calls)."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=_SAMPLE_STEPS_DATA,
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2

    def test_df_handles_missing_keys_in_steps_data(self) -> None:
        """df uses sensible defaults when step dicts lack optional keys."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=[{"event": "Signup"}],
        )

        df = result.df
        assert len(df) == 1
        row = df.iloc[0]
        assert row["count"] == 0
        assert row["step_conv_ratio"] == 0.0
        assert row["overall_conv_ratio"] == 0.0
        assert row["avg_time"] == 0.0
        assert row["avg_time_from_start"] == 0.0

    def test_df_handles_missing_event_name(self) -> None:
        """df uses 'Step N' fallback when step dict lacks 'event' key."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=[{"count": 100}],
        )

        df = result.df
        assert df.iloc[0]["event"] == "Step 1"

    def test_to_dict_returns_all_fields(self) -> None:
        """to_dict returns a dict with all FunnelQueryResult fields."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=_SAMPLE_STEPS_DATA,
            series={"raw": "data"},
            params={"funnel_type": "steps"},
            meta={"is_cached": False},
        )

        data = result.to_dict()

        assert data["computed_at"] == "2025-04-05T12:00:00Z"
        assert data["from_date"] == "2025-01-01"
        assert data["to_date"] == "2025-03-31"
        assert data["steps_data"] == _SAMPLE_STEPS_DATA
        assert data["series"] == {"raw": "data"}
        assert data["params"] == {"funnel_type": "steps"}
        assert data["meta"] == {"is_cached": False}

    def test_to_dict_json_serializable(self) -> None:
        """to_dict output is JSON serializable."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=_SAMPLE_STEPS_DATA,
            params={"funnel_type": "steps"},
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "2025-04-05T12:00:00Z" in json_str
        assert "Signup" in json_str
        assert "Purchase" in json_str

    def test_to_dict_with_defaults(self) -> None:
        """to_dict with default values returns empty collections."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
        )

        data = result.to_dict()

        assert data["steps_data"] == []
        assert data["series"] == {}
        assert data["params"] == {}
        assert data["meta"] == {}

    def test_frozen_immutability_computed_at(self) -> None:
        """Assigning to FunnelQueryResult.computed_at raises FrozenInstanceError."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.computed_at = "modified"  # type: ignore[misc]

    def test_frozen_immutability_from_date(self) -> None:
        """Assigning to FunnelQueryResult.from_date raises FrozenInstanceError."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.from_date = "2025-02-01"  # type: ignore[misc]

    def test_frozen_immutability_to_date(self) -> None:
        """Assigning to FunnelQueryResult.to_date raises FrozenInstanceError."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.to_date = "2025-04-30"  # type: ignore[misc]

    def test_frozen_immutability_steps_data(self) -> None:
        """Assigning to FunnelQueryResult.steps_data raises FrozenInstanceError."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.steps_data = [{"event": "X"}]  # type: ignore[misc]

    def test_frozen_immutability_series(self) -> None:
        """Assigning to FunnelQueryResult.series raises FrozenInstanceError."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.series = {"new": "data"}  # type: ignore[misc]

    def test_frozen_immutability_params(self) -> None:
        """Assigning to FunnelQueryResult.params raises FrozenInstanceError."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.params = {"new": "params"}  # type: ignore[misc]

    def test_frozen_immutability_meta(self) -> None:
        """Assigning to FunnelQueryResult.meta raises FrozenInstanceError."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.meta = {"new": "meta"}  # type: ignore[misc]

    def test_three_step_funnel(self) -> None:
        """FunnelQueryResult works with a three-step funnel."""
        three_steps = [
            {
                "event": "View",
                "count": 5000,
                "step_conv_ratio": 1.0,
                "overall_conv_ratio": 1.0,
                "avg_time": 0.0,
                "avg_time_from_start": 0.0,
            },
            {
                "event": "Add to Cart",
                "count": 1200,
                "step_conv_ratio": 0.24,
                "overall_conv_ratio": 0.24,
                "avg_time": 300.0,
                "avg_time_from_start": 300.0,
            },
            {
                "event": "Purchase",
                "count": 360,
                "step_conv_ratio": 0.30,
                "overall_conv_ratio": 0.072,
                "avg_time": 600.0,
                "avg_time_from_start": 900.0,
            },
        ]

        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=three_steps,
        )

        assert result.overall_conversion_rate == 0.072
        assert len(result.df) == 3
        assert list(result.df["step"]) == [1, 2, 3]

    def test_to_table_dict(self) -> None:
        """to_table_dict (inherited from ResultWithDataFrame) returns list of dicts from df."""
        result = FunnelQueryResult(
            computed_at="2025-04-05T12:00:00Z",
            from_date="2025-01-01",
            to_date="2025-03-31",
            steps_data=_SAMPLE_STEPS_DATA,
        )

        table = result.to_table_dict()
        assert isinstance(table, list)
        assert len(table) == 2
        assert all(isinstance(row, dict) for row in table)
        assert table[0]["event"] == "Signup"
        assert table[1]["event"] == "Purchase"
