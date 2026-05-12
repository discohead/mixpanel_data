"""Property-based tests for funnel query types using Hypothesis.

These tests verify invariants of FunnelStep, FunnelQueryResult,
FunnelMathType, and build_funnel_params that should hold for all
possible inputs, catching edge cases that example-based tests miss.

Usage:
    # Run with default profile (100 examples)
    pytest tests/test_types_funnel_pbt.py

    # Run with dev profile (10 examples, verbose)
    HYPOTHESIS_PROFILE=dev pytest tests/test_types_funnel_pbt.py

    # Run with CI profile (200 examples, deterministic)
    HYPOTHESIS_PROFILE=ci pytest tests/test_types_funnel_pbt.py
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any, get_args
from unittest.mock import MagicMock

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.types import (
    FunnelMathType,
    FunnelQueryResult,
    FunnelStep,
)
from tests.conftest import make_session

# ---- 042 redesign: canonical fake Session for Workspace(session=…) ----
_TEST_SESSION = Session(
    account=ServiceAccount(
        name="test_account",
        region="us",
        username="test_user",
        secret=SecretStr("test_secret"),
        default_project="12345",
    ),
    project=Project(id="12345"),
)

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for event names (non-empty, non-whitespace-only strings)
event_names = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

# Strategy for lists of event names (2+ steps for valid funnels).
# Typed as list[str | FunnelStep] so mypy accepts them as build_funnel_params
# input (list is invariant, so list[str] is not list[str | FunnelStep]).
step_lists: st.SearchStrategy[list[str | FunnelStep]] = st.lists(
    event_names, min_size=2, max_size=5
)

# Strategy for FunnelStep objects
funnel_steps = st.builds(FunnelStep, event=event_names)

# Strategy for date strings (YYYY-MM-DD format)
date_strings = st.dates().map(lambda d: d.strftime("%Y-%m-%d"))

# Strategy for valid steps_data dict entries
step_data_entries = st.fixed_dictionaries(
    {
        "event": event_names,
        "count": st.integers(min_value=0, max_value=1_000_000),
        "step_conv_ratio": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        "overall_conv_ratio": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        "avg_time": st.floats(min_value=0.0, allow_nan=False, allow_infinity=False),
        "avg_time_from_start": st.floats(
            min_value=0.0, allow_nan=False, allow_infinity=False
        ),
    }
)


# =============================================================================
# Helpers
# =============================================================================


def _make_workspace() -> Workspace:
    """Create a Workspace instance with mocked dependencies.

    Uses dependency injection so no real credentials or network access
    are needed.  Built as a plain function (not a pytest fixture) so it
    can be called inside ``@given``-decorated tests without triggering
    Hypothesis's ``function_scoped_fixture`` health check.
    """
    creds = make_session(
        username="test_user",
        secret="test_secret",
        project_id="12345",
        region="us",
    )
    manager = MagicMock()
    manager.config_version.return_value = 1
    manager.resolve_credentials.return_value = creds
    client = MagicMock(spec=MixpanelAPIClient)
    client.close = MagicMock()
    return Workspace(
        session=_TEST_SESSION,
        _api_client=client,
    )


# =============================================================================
# FunnelStep Property Tests
# =============================================================================


class TestFunnelStepProperties:
    """Property-based tests for FunnelStep frozen dataclass.

    Verifies immutability, equality, and field preservation invariants
    that should hold for all possible FunnelStep instances.
    """

    @given(event=event_names)
    def test_immutability_event(self, event: str) -> None:
        """Assigning to the event attribute of a frozen FunnelStep raises FrozenInstanceError."""
        step = FunnelStep(event=event)
        with pytest.raises(dataclasses.FrozenInstanceError):
            step.event = "other"  # type: ignore[misc]

    @given(event=event_names)
    def test_immutability_label(self, event: str) -> None:
        """Assigning to the label attribute of a frozen FunnelStep raises FrozenInstanceError."""
        step = FunnelStep(event=event, label="original")
        with pytest.raises(dataclasses.FrozenInstanceError):
            step.label = "changed"  # type: ignore[misc]

    @given(event=event_names)
    def test_immutability_filters(self, event: str) -> None:
        """Assigning to the filters attribute of a frozen FunnelStep raises FrozenInstanceError."""
        step = FunnelStep(event=event)
        with pytest.raises(dataclasses.FrozenInstanceError):
            step.filters = []  # type: ignore[misc]

    @given(event=event_names)
    def test_immutability_filters_combinator(self, event: str) -> None:
        """Assigning to filters_combinator on a frozen FunnelStep raises FrozenInstanceError."""
        step = FunnelStep(event=event)
        with pytest.raises(dataclasses.FrozenInstanceError):
            step.filters_combinator = "any"  # type: ignore[misc]

    @given(event=event_names)
    def test_immutability_order(self, event: str) -> None:
        """Assigning to the order attribute of a frozen FunnelStep raises FrozenInstanceError."""
        step = FunnelStep(event=event)
        with pytest.raises(dataclasses.FrozenInstanceError):
            step.order = "any"  # type: ignore[misc]

    @given(event=event_names)
    def test_equality_same_event(self, event: str) -> None:
        """Two FunnelSteps with the same event name are equal."""
        step_a = FunnelStep(event=event)
        step_b = FunnelStep(event=event)
        assert step_a == step_b

    @given(event=event_names)
    def test_field_preservation_event(self, event: str) -> None:
        """The event field is preserved after construction."""
        step = FunnelStep(event=event)
        assert step.event == event

    @given(
        event=event_names,
        label=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    )
    def test_field_preservation_label(self, event: str, label: str | None) -> None:
        """The label field is preserved after construction."""
        step = FunnelStep(event=event, label=label)
        assert step.label == label

    @given(event=event_names)
    def test_field_preservation_defaults(self, event: str) -> None:
        """Default values for optional fields are preserved after construction."""
        step = FunnelStep(event=event)
        assert step.label is None
        assert step.filters is None
        assert step.filters_combinator == "all"
        assert step.order is None

    @given(
        event=event_names,
        combinator=st.sampled_from(["all", "any"]),
        order=st.one_of(st.none(), st.sampled_from(["loose", "any"])),
    )
    def test_field_preservation_all_fields(
        self,
        event: str,
        combinator: str,
        order: str | None,
    ) -> None:
        """All fields are preserved when constructing with explicit values."""
        step = FunnelStep(
            event=event,
            filters_combinator=combinator,  # type: ignore[arg-type]
            order=order,  # type: ignore[arg-type]
        )
        assert step.event == event
        assert step.filters_combinator == combinator
        assert step.order == order


# =============================================================================
# FunnelQueryResult Property Tests
# =============================================================================


class TestFunnelQueryResultProperties:
    """Property-based tests for FunnelQueryResult.

    Verifies DataFrame shape, column presence, overall_conversion_rate
    behavior, immutability, and to_dict round-trip invariants.
    """

    @given(steps_data=st.lists(step_data_entries, min_size=0, max_size=10))
    def test_df_row_count_matches_steps_data(
        self, steps_data: list[dict[str, Any]]
    ) -> None:
        """DataFrame has exactly len(steps_data) rows."""
        result = FunnelQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date="2025-01-01",
            to_date="2025-01-31",
            steps_data=steps_data,
        )
        assert len(result.df) == len(steps_data)

    @given(steps_data=st.lists(step_data_entries, min_size=0, max_size=10))
    def test_df_always_has_seven_columns(
        self, steps_data: list[dict[str, Any]]
    ) -> None:
        """DataFrame always has exactly 7 columns regardless of steps_data content."""
        result = FunnelQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date="2025-01-01",
            to_date="2025-01-31",
            steps_data=steps_data,
        )
        expected_columns = [
            "step",
            "event",
            "count",
            "step_conv_ratio",
            "overall_conv_ratio",
            "avg_time",
            "avg_time_from_start",
        ]
        assert list(result.df.columns) == expected_columns

    def test_empty_steps_data_produces_zero_rows(self) -> None:
        """An empty steps_data produces a DataFrame with 0 rows but correct columns."""
        result = FunnelQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date="2025-01-01",
            to_date="2025-01-31",
            steps_data=[],
        )
        assert len(result.df) == 0
        assert list(result.df.columns) == [
            "step",
            "event",
            "count",
            "step_conv_ratio",
            "overall_conv_ratio",
            "avg_time",
            "avg_time_from_start",
        ]

    @given(steps_data=st.lists(step_data_entries, min_size=0, max_size=10))
    def test_overall_conversion_rate_returns_float(
        self, steps_data: list[dict[str, Any]]
    ) -> None:
        """overall_conversion_rate always returns a float value."""
        result = FunnelQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date="2025-01-01",
            to_date="2025-01-31",
            steps_data=steps_data,
        )
        rate = result.overall_conversion_rate
        assert isinstance(rate, float)

    def test_overall_conversion_rate_empty_returns_zero(self) -> None:
        """overall_conversion_rate returns 0.0 when steps_data is empty."""
        result = FunnelQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date="2025-01-01",
            to_date="2025-01-31",
            steps_data=[],
        )
        assert result.overall_conversion_rate == 0.0

    @given(
        overall_conv_ratio=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    def test_overall_conversion_rate_matches_last_step(
        self, overall_conv_ratio: float
    ) -> None:
        """overall_conversion_rate equals the overall_conv_ratio of the last step."""
        steps_data = [
            {
                "event": "Step1",
                "count": 100,
                "step_conv_ratio": 1.0,
                "overall_conv_ratio": 1.0,
                "avg_time": 0.0,
                "avg_time_from_start": 0.0,
            },
            {
                "event": "Step2",
                "count": 50,
                "step_conv_ratio": 0.5,
                "overall_conv_ratio": overall_conv_ratio,
                "avg_time": 60.0,
                "avg_time_from_start": 60.0,
            },
        ]
        result = FunnelQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date="2025-01-01",
            to_date="2025-01-31",
            steps_data=steps_data,
        )
        assert result.overall_conversion_rate == overall_conv_ratio

    @given(
        computed_at=st.text(min_size=1, max_size=30),
        from_date=date_strings,
        to_date=date_strings,
    )
    def test_immutability_computed_at(
        self, computed_at: str, from_date: str, to_date: str
    ) -> None:
        """Assigning to computed_at on a frozen FunnelQueryResult raises FrozenInstanceError."""
        result = FunnelQueryResult(
            computed_at=computed_at,
            from_date=from_date,
            to_date=to_date,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.computed_at = "changed"  # type: ignore[misc]

    @given(from_date=date_strings, to_date=date_strings)
    def test_immutability_from_date(self, from_date: str, to_date: str) -> None:
        """Assigning to from_date on a frozen FunnelQueryResult raises FrozenInstanceError."""
        result = FunnelQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date=from_date,
            to_date=to_date,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.from_date = "changed"  # type: ignore[misc]

    @given(from_date=date_strings, to_date=date_strings)
    def test_immutability_to_date(self, from_date: str, to_date: str) -> None:
        """Assigning to to_date on a frozen FunnelQueryResult raises FrozenInstanceError."""
        result = FunnelQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date=from_date,
            to_date=to_date,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.to_date = "changed"  # type: ignore[misc]

    @given(from_date=date_strings, to_date=date_strings)
    def test_immutability_steps_data(self, from_date: str, to_date: str) -> None:
        """Assigning to steps_data on a frozen FunnelQueryResult raises FrozenInstanceError."""
        result = FunnelQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date=from_date,
            to_date=to_date,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.steps_data = []  # type: ignore[misc]

    @given(
        computed_at=st.text(min_size=1, max_size=30),
        from_date=date_strings,
        to_date=date_strings,
        steps_data=st.lists(step_data_entries, min_size=0, max_size=5),
    )
    def test_to_dict_returns_all_expected_keys(
        self,
        computed_at: str,
        from_date: str,
        to_date: str,
        steps_data: list[dict[str, Any]],
    ) -> None:
        """to_dict() always returns a dict with all expected keys."""
        result = FunnelQueryResult(
            computed_at=computed_at,
            from_date=from_date,
            to_date=to_date,
            steps_data=steps_data,
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        expected_keys = {
            "computed_at",
            "from_date",
            "to_date",
            "steps_data",
            "series",
            "params",
            "meta",
        }
        assert set(d.keys()) == expected_keys

    @given(
        computed_at=st.text(min_size=1, max_size=30),
        from_date=date_strings,
        to_date=date_strings,
        steps_data=st.lists(step_data_entries, min_size=0, max_size=5),
    )
    def test_to_dict_is_json_serializable(
        self,
        computed_at: str,
        from_date: str,
        to_date: str,
        steps_data: list[dict[str, Any]],
    ) -> None:
        """to_dict() output is always JSON-serializable."""
        result = FunnelQueryResult(
            computed_at=computed_at,
            from_date=from_date,
            to_date=to_date,
            steps_data=steps_data,
        )
        d = result.to_dict()
        json_str = json.dumps(d)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    @given(steps_data=st.lists(step_data_entries, min_size=1, max_size=10))
    def test_df_caching_returns_same_object(
        self, steps_data: list[dict[str, Any]]
    ) -> None:
        """Repeated df access returns the same cached DataFrame object."""
        result = FunnelQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date="2025-01-01",
            to_date="2025-01-31",
            steps_data=steps_data,
        )
        df1 = result.df
        df2 = result.df
        assert df1 is df2

    @given(steps_data=st.lists(step_data_entries, min_size=1, max_size=10))
    def test_df_step_column_is_1_indexed(
        self, steps_data: list[dict[str, Any]]
    ) -> None:
        """The step column in the DataFrame is 1-indexed and sequential."""
        result = FunnelQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date="2025-01-01",
            to_date="2025-01-31",
            steps_data=steps_data,
        )
        expected_steps = list(range(1, len(steps_data) + 1))
        assert list(result.df["step"]) == expected_steps

    @given(steps_data=st.lists(step_data_entries, min_size=1, max_size=10))
    def test_deterministic_df_conversion(
        self, steps_data: list[dict[str, Any]]
    ) -> None:
        """Same steps_data always produces structurally identical DataFrames."""
        result1 = FunnelQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date="2025-01-01",
            to_date="2025-01-31",
            steps_data=steps_data,
        )
        result2 = FunnelQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date="2025-01-01",
            to_date="2025-01-31",
            steps_data=steps_data,
        )
        pd.testing.assert_frame_equal(result1.df, result2.df)


# =============================================================================
# FunnelMathType Property Tests
# =============================================================================


class TestFunnelMathTypeProperties:
    """Property-based tests for FunnelMathType Literal type.

    Verifies the exact set of 14 valid values and membership invariants.
    """

    EXPECTED_VALUES: frozenset[str] = frozenset(
        [
            "conversion_rate_unique",
            "conversion_rate_total",
            "conversion_rate_session",
            "unique",
            "total",
            "average",
            "median",
            "min",
            "max",
            "p25",
            "p75",
            "p90",
            "p99",
            "histogram",
        ]
    )

    def test_exactly_14_valid_values(self) -> None:
        """FunnelMathType has exactly 14 valid values."""
        actual = set(get_args(FunnelMathType))
        assert len(actual) == 14

    def test_exact_set_of_values(self) -> None:
        """FunnelMathType contains exactly the expected 14 values."""
        actual = set(get_args(FunnelMathType))
        assert actual == self.EXPECTED_VALUES

    @given(value=st.sampled_from(sorted(EXPECTED_VALUES)))
    def test_all_valid_values_are_in_literal(self, value: str) -> None:
        """Every expected value is present in the FunnelMathType Literal type."""
        actual = set(get_args(FunnelMathType))
        assert value in actual

    @given(
        value=st.text(min_size=1, max_size=50).filter(
            lambda s: s not in TestFunnelMathTypeProperties.EXPECTED_VALUES
        )
    )
    def test_invalid_values_not_in_literal(self, value: str) -> None:
        """Arbitrary strings not in the expected set are not valid FunnelMathType values."""
        actual = set(get_args(FunnelMathType))
        assert value not in actual


# =============================================================================
# build_funnel_params Property Tests
# =============================================================================


class TestBuildFunnelParamsProperties:
    """Property-based tests for Workspace.build_funnel_params output structure.

    Verifies that for any valid inputs, the output always has the
    expected top-level structure, step count, behavior type, and
    display options.

    Uses ``_make_workspace()`` instead of pytest fixtures to avoid
    Hypothesis's ``function_scoped_fixture`` health check.
    """

    @given(steps=step_lists)
    def test_output_has_sections_and_display_options(
        self, steps: list[str | FunnelStep]
    ) -> None:
        """Output always has 'sections' and 'displayOptions' keys."""
        ws = _make_workspace()
        result = ws.build_funnel_params(steps)
        assert "sections" in result
        assert "displayOptions" in result

    @given(steps=step_lists)
    def test_sections_show_is_nonempty_list(
        self, steps: list[str | FunnelStep]
    ) -> None:
        """sections.show is always a non-empty list."""
        ws = _make_workspace()
        result = ws.build_funnel_params(steps)
        show = result["sections"]["show"]
        assert isinstance(show, list)
        assert len(show) > 0

    @given(steps=step_lists)
    def test_behavior_type_is_funnel(self, steps: list[str | FunnelStep]) -> None:
        """sections.show[0].behavior.type is always 'funnel'."""
        ws = _make_workspace()
        result = ws.build_funnel_params(steps)
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["type"] == "funnel"

    @given(
        steps=step_lists,
        mode=st.sampled_from(["steps", "trends", "table"]),
    )
    def test_chart_type_matches_mode(
        self, steps: list[str | FunnelStep], mode: str
    ) -> None:
        """displayOptions.chartType maps correctly from mode parameter."""
        ws = _make_workspace()
        result = ws.build_funnel_params(steps, mode=mode)  # type: ignore[arg-type]
        expected_map = {
            "steps": "funnel-steps",
            "trends": "line",
            "table": "table",
        }
        assert result["displayOptions"]["chartType"] == expected_map[mode]

    @given(steps=step_lists)
    def test_behavior_count_matches_step_count(
        self, steps: list[str | FunnelStep]
    ) -> None:
        """The number of behaviors equals the number of input steps."""
        ws = _make_workspace()
        result = ws.build_funnel_params(steps)
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert len(behaviors) == len(steps)

    @given(steps=step_lists)
    def test_behavior_names_match_step_names(
        self, steps: list[str | FunnelStep]
    ) -> None:
        """Each behavior name matches the corresponding input step string."""
        ws = _make_workspace()
        result = ws.build_funnel_params(steps)
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        for behavior, step_name in zip(behaviors, steps, strict=True):
            assert behavior["name"] == step_name

    @given(
        steps=step_lists,
        order=st.sampled_from(["loose", "any"]),
    )
    def test_funnel_order_matches_input(
        self, steps: list[str | FunnelStep], order: str
    ) -> None:
        """funnelOrder in the behavior block matches the order parameter."""
        ws = _make_workspace()
        result = ws.build_funnel_params(steps, order=order)  # type: ignore[arg-type]
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["funnelOrder"] == order

    @given(
        steps=step_lists,
        window=st.integers(min_value=1, max_value=365),
    )
    def test_conversion_window_matches_input(
        self, steps: list[str | FunnelStep], window: int
    ) -> None:
        """conversionWindowDuration matches the conversion_window parameter."""
        ws = _make_workspace()
        result = ws.build_funnel_params(steps, conversion_window=window)
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["conversionWindowDuration"] == window

    @given(funnel_steps_list=st.lists(funnel_steps, min_size=2, max_size=5))
    def test_funnel_step_objects_produce_valid_output(
        self, funnel_steps_list: list[FunnelStep]
    ) -> None:
        """FunnelStep objects produce valid output with correct structure."""
        ws = _make_workspace()
        step_input: list[str | FunnelStep] = list(funnel_steps_list)
        result = ws.build_funnel_params(step_input)
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert len(behaviors) == len(funnel_steps_list)
        for behavior, step in zip(behaviors, funnel_steps_list, strict=True):
            assert behavior["name"] == step.event

    @given(steps=step_lists)
    def test_output_is_json_serializable(self, steps: list[str | FunnelStep]) -> None:
        """build_funnel_params output is always JSON-serializable."""
        ws = _make_workspace()
        result = ws.build_funnel_params(steps)
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    @given(steps=step_lists)
    def test_sections_contains_expected_keys(
        self, steps: list[str | FunnelStep]
    ) -> None:
        """sections dict always contains show, time, filter, group, formula."""
        ws = _make_workspace()
        result = ws.build_funnel_params(steps)
        sections = result["sections"]
        for key in ("show", "time", "filter", "group", "formula"):
            assert key in sections
