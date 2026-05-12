"""Property-based tests for round-trip bookmark validation soundness.

Proves that valid Layer 1 inputs always produce bookmarks that pass
Layer 2 validation — the critical property for agent reliability.
If ``build_*_params()`` returns without raising
``BookmarkValidationError``, the round-trip is sound.

Covers all four query types: Insights, Funnels, Retention, and Flows.
"""

from __future__ import annotations

from typing import Any, get_args
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.types import (
    Formula,
    FunnelStep,
    Metric,
    PerUserAggregation,
    RetentionMathType,
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
# Strategies
# =============================================================================

# Safe event names: non-empty, no control chars, no invisible-only
safe_event_names = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

# Valid last values (1..3650)
valid_last = st.integers(min_value=1, max_value=3650)

# Property names for property-based math
property_names = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=1,
    max_size=20,
)

# --- Insights math strategies ---

# Counting math: no property needed, no per_user allowed for some
_counting_math_no_per_user = st.sampled_from(["unique", "dau", "wau", "mau"])
_counting_math_with_per_user = st.just("total")

# Property-required math (not percentile or histogram — those have extra deps)
_property_math = st.sampled_from(
    ["average", "median", "min", "max", "p25", "p75", "p90", "p99"]
)

# Insights math args: valid (math, math_property, per_user) triples
insights_math_args: st.SearchStrategy[dict[str, Any]] = st.one_of(
    # Counting math without per_user (unique/dau/wau/mau)
    _counting_math_no_per_user.map(
        lambda m: {"math": m, "math_property": None, "per_user": None}
    ),
    # total without property
    st.just({"math": "total", "math_property": None, "per_user": None}),
    # total with property (MATH_PROPERTY_OPTIONAL)
    property_names.map(
        lambda p: {"math": "total", "math_property": p, "per_user": None}
    ),
    # Property-required math with property
    st.tuples(_property_math, property_names).map(
        lambda t: {"math": t[0], "math_property": t[1], "per_user": None}
    ),
    # total with per_user (requires property)
    st.tuples(
        property_names,
        st.sampled_from(list(get_args(PerUserAggregation))),
    ).map(lambda t: {"math": "total", "math_property": t[0], "per_user": t[1]}),
)

# --- Funnel math strategies ---

# Non-property funnel math types
_funnel_counting_math = st.sampled_from(
    [
        "conversion_rate_unique",
        "conversion_rate_total",
        "unique",
        "total",
    ]
)

# Property funnel math types
_funnel_property_math = st.sampled_from(
    ["average", "median", "min", "max", "p25", "p75", "p90", "p99"]
)

funnel_math_args: st.SearchStrategy[dict[str, Any]] = st.one_of(
    # Non-property math
    _funnel_counting_math.map(
        lambda m: {
            "math": m,
            "math_property": None,
            "conversion_window_unit": "day",
        }
    ),
    # Property math with property
    st.tuples(_funnel_property_math, property_names).map(
        lambda t: {
            "math": t[0],
            "math_property": t[1],
            "conversion_window_unit": "day",
        }
    ),
    # Session math with session window
    st.just(
        {
            "math": "conversion_rate_session",
            "math_property": None,
            "conversion_window_unit": "session",
        }
    ),
)

# --- Flow direction strategies ---

flow_directions = st.tuples(
    st.integers(min_value=0, max_value=5),
    st.integers(min_value=0, max_value=5),
).filter(lambda t: t[0] + t[1] >= 1)


# =============================================================================
# Helper
# =============================================================================


def _make_workspace() -> Workspace:
    """Create a Workspace with mocked dependencies for testing.

    Uses dependency injection so no real credentials or network access
    are needed. Built as a plain function (not a pytest fixture) so it
    can be called inside ``@given``-decorated tests without triggering
    Hypothesis's ``function_scoped_fixture`` health check.

    Returns:
        Workspace instance with mocked config and API client.
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
# Insights Round-Trip
# =============================================================================


class TestInsightsRoundTrip:
    """Round-trip soundness tests for insights/segmentation queries.

    Proves that valid L1 inputs always produce L2-valid bookmarks
    when passed through ``build_params()``.
    """

    @given(event=safe_event_names, last=valid_last, math_args=insights_math_args)
    @settings(max_examples=100)
    def test_simple_event_roundtrip(
        self,
        event: str,
        last: int,
        math_args: dict[str, Any],
    ) -> None:
        """Single string event with valid math and last produces a valid bookmark.

        Args:
            event: Safe event name string.
            last: Valid relative time range in days.
            math_args: Valid (math, math_property, per_user) triple.
        """
        ws = _make_workspace()
        # Should not raise BookmarkValidationError
        ws.build_params(
            events=event,
            last=last,
            math=math_args["math"],
            math_property=math_args["math_property"],
            per_user=math_args["per_user"],
        )

    @given(
        event=safe_event_names,
        last=valid_last,
        math=_property_math,
        prop=property_names,
    )
    @settings(max_examples=100)
    def test_metric_object_roundtrip(
        self,
        event: str,
        last: int,
        math: str,
        prop: str,
    ) -> None:
        """Metric object with per-metric math and property produces a valid bookmark.

        Args:
            event: Safe event name string.
            last: Valid relative time range in days.
            math: Property-requiring math type.
            prop: Property name for aggregation.
        """
        ws = _make_workspace()
        metric = Metric(event=event, math=math, property=prop)  # type: ignore[arg-type]
        ws.build_params(events=metric, last=last)

    @given(
        event_a=safe_event_names,
        event_b=safe_event_names,
        last=valid_last,
    )
    @settings(max_examples=100)
    def test_multi_event_with_formula_roundtrip(
        self,
        event_a: str,
        event_b: str,
        last: int,
    ) -> None:
        """Two events plus a Formula produces a valid bookmark.

        Args:
            event_a: First event name.
            event_b: Second event name.
            last: Valid relative time range in days.
        """
        ws = _make_workspace()
        ws.build_params(
            events=[event_a, event_b, Formula(expression="A + B")],
            last=last,
        )


# =============================================================================
# Funnel Round-Trip
# =============================================================================


class TestFunnelRoundTrip:
    """Round-trip soundness tests for funnel queries."""

    @given(
        steps=st.lists(safe_event_names, min_size=2, max_size=5),
        last=valid_last,
        math_args=funnel_math_args,
        conversion_window=st.integers(min_value=1, max_value=30),
    )
    @settings(max_examples=100)
    def test_funnel_roundtrip(
        self,
        steps: list[str | FunnelStep],
        last: int,
        math_args: dict[str, Any],
        conversion_window: int,
    ) -> None:
        """Valid funnel steps with valid math and window produce a valid bookmark.

        Args:
            steps: 2-5 safe event name strings.
            last: Valid relative time range in days.
            math_args: Valid (math, math_property, conversion_window_unit) triple.
            conversion_window: Positive conversion window size.
        """
        ws = _make_workspace()
        cw = (
            1 if math_args["conversion_window_unit"] == "session" else conversion_window
        )
        ws.build_funnel_params(
            steps=steps,
            last=last,
            math=math_args["math"],
            math_property=math_args["math_property"],
            conversion_window=cw,
            conversion_window_unit=math_args["conversion_window_unit"],
        )


# =============================================================================
# Retention Round-Trip
# =============================================================================


class TestRetentionRoundTrip:
    """Round-trip soundness tests for retention queries."""

    @given(
        born_event=safe_event_names,
        return_event=safe_event_names,
        last=valid_last,
        math=st.sampled_from(list(get_args(RetentionMathType))),
        retention_unit=st.sampled_from(["day", "week", "month"]),
        alignment=st.sampled_from(["birth", "interval_start"]),
        mode=st.sampled_from(["curve", "trends", "table"]),
    )
    @settings(max_examples=100)
    def test_retention_roundtrip(
        self,
        born_event: str,
        return_event: str,
        last: int,
        math: str,
        retention_unit: str,
        alignment: str,
        mode: str,
    ) -> None:
        """Valid retention args with valid enums produce a valid bookmark.

        Args:
            born_event: Event defining cohort membership.
            return_event: Event defining return.
            last: Valid relative time range in days.
            math: Valid retention math type.
            retention_unit: Valid retention period unit.
            alignment: Valid retention alignment mode.
            mode: Valid display mode.
        """
        ws = _make_workspace()
        ws.build_retention_params(
            born_event=born_event,
            return_event=return_event,
            last=last,
            math=math,  # type: ignore[arg-type]
            retention_unit=retention_unit,  # type: ignore[arg-type]
            alignment=alignment,  # type: ignore[arg-type]
            mode=mode,  # type: ignore[arg-type]
        )


# =============================================================================
# Flow Round-Trip
# =============================================================================


class TestFlowRoundTrip:
    """Round-trip soundness tests for flow queries."""

    @given(
        event=safe_event_names,
        last=valid_last,
        direction=flow_directions,
        count_type=st.sampled_from(["unique", "total"]),
        mode=st.sampled_from(["sankey", "paths"]),
        cardinality=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_flow_simple_roundtrip(
        self,
        event: str,
        last: int,
        direction: tuple[int, int],
        count_type: str,
        mode: str,
        cardinality: int,
    ) -> None:
        """Single event with valid flow params produces a valid bookmark.

        Args:
            event: Safe event name string.
            last: Valid relative time range in days.
            direction: (forward, reverse) tuple where sum >= 1.
            count_type: Valid non-session count type.
            mode: Valid display mode.
            cardinality: Valid cardinality (1-50).
        """
        ws = _make_workspace()
        ws.build_flow_params(
            event=event,
            forward=direction[0],
            reverse=direction[1],
            last=last,
            count_type=count_type,  # type: ignore[arg-type]
            mode=mode,  # type: ignore[arg-type]
            cardinality=cardinality,
        )

    @given(event=safe_event_names, last=valid_last)
    @settings(max_examples=100)
    def test_flow_session_coupling_roundtrip(
        self,
        event: str,
        last: int,
    ) -> None:
        """Session count_type with session window and conversion_window=1 is valid.

        Args:
            event: Safe event name string.
            last: Valid relative time range in days.
        """
        ws = _make_workspace()
        ws.build_flow_params(
            event=event,
            last=last,
            count_type="session",
            conversion_window_unit="session",
            conversion_window=1,
        )
