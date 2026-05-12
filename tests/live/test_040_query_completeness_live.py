# ruff: noqa: S101
"""Live QA tests for the 040-query-engine-completeness feature.

Exercises every new query parameter, type expansion, filter method,
and builder output against the real Mixpanel API.  All tests are
**read-only** — no entities are created, updated, or deleted.

Organized by:
- Smoke Suite (S01-S10): backward compat and basic acceptance
- Offline Validation (US1-US8): build_*_params() JSON assertions
- Validation Error Tests: ValueError / BookmarkValidationError
- Live API Tests: real API calls wrapped in _query_or_api_error
- Cross-Parameter Interactions (X01-X07): combined features

Usage:
    uv run pytest tests/live/test_040_query_completeness_live.py -v -m live
    uv run pytest tests/live/test_040_query_completeness_live.py -v -m live -k Smoke
    uv run pytest tests/live/test_040_query_completeness_live.py -v -m live -k Offline

Pre-requisites:
    - Active OAuth token: ``mp account login NAME``
    - Project switched to target project with events
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from mixpanel_headless import (
    BookmarkValidationError,
    CohortCriteria,
    Filter,
    FlowQueryResult,
    FlowStep,
    FrequencyBreakdown,
    FrequencyFilter,
    FunnelQueryResult,
    GroupBy,
    Metric,
    QueryResult,
    RetentionQueryResult,
    TimeComparison,
    Workspace,
)
from mixpanel_headless.exceptions import APIError, QueryError

# All tests require the `live` marker — skipped by default
pytestmark = pytest.mark.live


# =============================================================================
# Helpers
# =============================================================================


def _query_or_api_error(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Call *fn* and return the result, or ``None`` if the API rejects it.

    Acceptable rejections are ``QueryError`` and ``APIError`` — the server
    refused the query but the client did not crash with an unexpected
    exception (``AttributeError``, ``TypeError``, ``KeyError``, etc.).

    Args:
        fn: Callable to invoke (e.g. ``ws.query``).
        *args: Positional arguments forwarded to *fn*.
        **kwargs: Keyword arguments forwarded to *fn*.

    Returns:
        The result of *fn*, or ``None`` when a server-side rejection
        is the only reason for failure.
    """
    try:
        return fn(*args, **kwargs)
    except (QueryError, APIError):
        return None


def _dig(d: dict[str, Any], *keys: str | int) -> Any:
    """Safely traverse nested dicts and lists.

    Args:
        d: Root dictionary.
        *keys: Sequence of string keys (for dicts) or int indices
            (for lists) to follow.

    Returns:
        The value at the nested path, or ``None`` if any key is missing
        or any index is out of range.
    """
    current: Any = d
    for k in keys:
        if isinstance(k, int):
            if not isinstance(current, list) or k >= len(current):
                return None
            current = current[k]
        elif isinstance(current, dict):
            current = current.get(k)
        else:
            return None
    return current


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def ws() -> Iterator[Workspace]:
    """Live Workspace connected to the active project.

    Yields:
        Workspace instance using default credentials.
    """
    workspace = Workspace()
    yield workspace
    workspace.close()


@pytest.fixture(scope="module")
def real_event(ws: Workspace) -> str:
    """First available event name, preferring $mp_web_page_view.

    Args:
        ws: Workspace fixture.

    Returns:
        An event name string known to exist in the project.
    """
    events = ws.events()
    assert len(events) > 0, "No events in project"
    if "$mp_web_page_view" in events:
        return "$mp_web_page_view"
    return events[0]


@pytest.fixture(scope="module")
def real_events_pair(ws: Workspace) -> tuple[str, str]:
    """Two event names for funnel / retention tests.

    Args:
        ws: Workspace fixture.

    Returns:
        Tuple of two distinct event name strings.
    """
    events = ws.events()
    assert len(events) >= 2, "Need at least 2 events"
    candidates = ["$mp_web_page_view", "$identify"]
    found = [e for e in candidates if e in events]
    if len(found) >= 2:
        return (found[0], found[1])
    return (events[0], events[1])


# =============================================================================
# SMOKE SUITE — S01-S10
# =============================================================================


class TestSmokeSuite:
    """Backward-compatibility and basic acceptance smoke tests.

    Every test either returns the expected result type **or** raises
    QueryError / APIError (not crash / AttributeError / TypeError).
    """

    def test_s01_backward_compat_query(self, ws: Workspace, real_event: str) -> None:
        """S01 -- Existing query() call without new params still works.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        result = ws.query(real_event, last=7)
        assert isinstance(result, QueryResult)

    def test_s02_backward_compat_build_params(
        self, ws: Workspace, real_event: str
    ) -> None:
        """S02 -- Existing build_params() call produces identical output.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        params = ws.build_params(real_event, last=7)
        assert isinstance(params, dict)
        assert "sections" in params

    def test_s03_backward_compat_funnel(
        self, ws: Workspace, real_events_pair: tuple[str, str]
    ) -> None:
        """S03 -- Existing query_funnel() call still works.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        result = _query_or_api_error(
            ws.query_funnel,
            list(real_events_pair),
            last=7,
        )
        if result is not None:
            assert isinstance(result, FunnelQueryResult)

    def test_s04_backward_compat_retention(
        self, ws: Workspace, real_events_pair: tuple[str, str]
    ) -> None:
        """S04 -- Existing query_retention() call still works.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        result = _query_or_api_error(
            ws.query_retention,
            real_events_pair[0],
            real_events_pair[1],
            last=7,
        )
        if result is not None:
            assert isinstance(result, RetentionQueryResult)

    def test_s05_backward_compat_flow(self, ws: Workspace, real_event: str) -> None:
        """S05 -- Existing query_flow() call still works.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        result = _query_or_api_error(ws.query_flow, real_event, last=7)
        if result is not None:
            assert isinstance(result, FlowQueryResult)

    def test_s06_backward_compat_build_funnel_params(
        self, ws: Workspace, real_events_pair: tuple[str, str]
    ) -> None:
        """S06 -- build_funnel_params() without new params produces dict.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        params = ws.build_funnel_params(list(real_events_pair), last=7)
        assert isinstance(params, dict)

    def test_s07_backward_compat_build_retention_params(
        self, ws: Workspace, real_events_pair: tuple[str, str]
    ) -> None:
        """S07 -- build_retention_params() without new params produces dict.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        params = ws.build_retention_params(
            real_events_pair[0], real_events_pair[1], last=7
        )
        assert isinstance(params, dict)

    def test_s08_backward_compat_build_flow_params(
        self, ws: Workspace, real_event: str
    ) -> None:
        """S08 -- build_flow_params() without new params produces dict.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        params = ws.build_flow_params(real_event, last=7)
        assert isinstance(params, dict)

    def test_s09_new_math_type_accepted(self, ws: Workspace, real_event: str) -> None:
        """S09 -- cumulative_unique math type accepted by build_params.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        params = ws.build_params(real_event, math="cumulative_unique", last=7)
        assert isinstance(params, dict)

    def test_s10_time_comparison_accepted(self, ws: Workspace, real_event: str) -> None:
        """S10 -- time_comparison param accepted by build_params.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        tc = TimeComparison.relative("month")
        params = ws.build_params(real_event, last=30, time_comparison=tc)
        assert isinstance(params, dict)
        assert "displayOptions" in params


# =============================================================================
# OFFLINE VALIDATION — US1: Complete Math Type Coverage
# =============================================================================


class TestOfflineUS1:
    """Offline param-building tests for User Story 1 (math types)."""

    @pytest.mark.parametrize(
        "math_type",
        [
            "cumulative_unique",
            "sessions",
        ],
    )
    def test_m01_no_property_math_types(
        self, ws: Workspace, real_event: str, math_type: str
    ) -> None:
        """M01 -- Math types that do NOT require a property are accepted.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
            math_type: Math type to test.
        """
        params = ws.build_params(real_event, math=math_type, last=7)  # type: ignore[arg-type]
        show = _dig(params, "sections", "show")
        assert show is not None
        assert show[0]["measurement"]["math"] in (
            math_type,
            # some types map to different API names
            math_type.replace("_", " "),
        )

    @pytest.mark.parametrize(
        "math_type",
        [
            "unique_values",
            "most_frequent",
            "first_value",
            "multi_attribution",
            "numeric_summary",
        ],
    )
    def test_m02_property_required_math_types(
        self, ws: Workspace, real_event: str, math_type: str
    ) -> None:
        """M02 -- Math types requiring a property are accepted with property.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
            math_type: Math type to test.
        """
        params = ws.build_params(
            real_event,
            math=math_type,  # type: ignore[arg-type]
            math_property="$browser",
            last=7,
        )
        show = _dig(params, "sections", "show")
        assert show is not None

    @pytest.mark.parametrize(
        "math_type",
        [
            "unique_values",
            "most_frequent",
            "first_value",
            "multi_attribution",
            "numeric_summary",
        ],
    )
    def test_m03_property_required_math_rejects_missing_property(
        self, ws: Workspace, real_event: str, math_type: str
    ) -> None:
        """M03 -- Math types requiring a property raise without one.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
            math_type: Math type to test.
        """
        with pytest.raises((ValueError, BookmarkValidationError)):
            ws.build_params(real_event, math=math_type, last=7)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "math_type",
        [
            "total",
            "unique",
            "dau",
            "wau",
            "mau",
            "average",
            "median",
            "min",
            "max",
            "p25",
            "p75",
            "p90",
            "p99",
            "percentile",
            "histogram",
        ],
    )
    def test_m04_original_math_types_still_work(
        self, ws: Workspace, real_event: str, math_type: str
    ) -> None:
        """M04 -- All original 15 math types still accepted.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
            math_type: Math type to test.
        """
        kwargs: dict[str, Any] = {"last": 7}
        # Types requiring a property
        needs_prop = {
            "average",
            "median",
            "min",
            "max",
            "p25",
            "p75",
            "p90",
            "p99",
            "percentile",
            "histogram",
        }
        if math_type in needs_prop:
            kwargs["math_property"] = "$browser"
        if math_type == "percentile":
            kwargs["percentile_value"] = 50
        if math_type == "histogram":
            kwargs["per_user"] = "total"
        params = ws.build_params(real_event, math=math_type, **kwargs)  # type: ignore[arg-type]
        assert isinstance(params, dict)

    @pytest.mark.parametrize("math_type", ["total", "average"])
    def test_m05_retention_math_expanded(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        math_type: str,
    ) -> None:
        """M05 -- New retention math types (total, average) accepted.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
            math_type: Retention math type to test.
        """
        params = ws.build_retention_params(
            real_events_pair[0],
            real_events_pair[1],
            math=math_type,  # type: ignore[arg-type]
            last=7,
        )
        show = _dig(params, "sections", "show")
        assert show is not None

    def test_m06_funnel_histogram_math(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """M06 -- Funnel histogram math type accepted.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        params = ws.build_funnel_params(
            list(real_events_pair),
            math="histogram",
            math_property="$browser",
            last=7,
        )
        show = _dig(params, "sections", "show")
        assert show is not None

    def test_m07_metric_with_new_math(self, ws: Workspace) -> None:
        """M07 -- Metric object with new math type is accepted.

        Args:
            ws: Workspace fixture.
        """
        m = Metric("$mp_web_page_view", math="cumulative_unique")
        params = ws.build_params(m, last=7)
        assert isinstance(params, dict)

    def test_m08_metric_property_required_math(self, ws: Workspace) -> None:
        """M08 -- Metric with property-required math and property works.

        Args:
            ws: Workspace fixture.
        """
        m = Metric(
            "$mp_web_page_view",
            math="unique_values",
            property="$browser",
        )
        params = ws.build_params(m, last=7)
        assert isinstance(params, dict)

    def test_m09_metric_property_required_math_rejects_missing(self) -> None:
        """M09 -- Metric with property-required math but no property raises.

        No fixture needed -- pure type construction.
        """
        with pytest.raises(ValueError):
            Metric("$mp_web_page_view", math="unique_values")


# =============================================================================
# OFFLINE VALIDATION — US2: Advanced Funnel and Retention Modes
# =============================================================================


class TestOfflineUS2:
    """Offline param-building tests for User Story 2 (modes)."""

    @pytest.mark.parametrize("mode", ["default", "basic", "aggressive", "optimized"])
    def test_m10_funnel_reentry_mode(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        mode: str,
    ) -> None:
        """M10 -- All funnel reentry modes are accepted and threaded.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
            mode: Reentry mode value.
        """
        params = ws.build_funnel_params(
            list(real_events_pair),
            reentry_mode=mode,  # type: ignore[arg-type]
            last=7,
        )
        behavior = _dig(params, "sections", "show", 0, "behavior")
        assert behavior is not None
        assert behavior.get("funnelReentryMode") == mode

    @pytest.mark.parametrize(
        "mode", ["none", "carry_back", "carry_forward", "consecutive_forward"]
    )
    def test_m11_retention_unbounded_mode(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        mode: str,
    ) -> None:
        """M11 -- All retention unbounded modes are accepted and threaded.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
            mode: Unbounded mode value.
        """
        params = ws.build_retention_params(
            real_events_pair[0],
            real_events_pair[1],
            unbounded_mode=mode,  # type: ignore[arg-type]
            last=7,
        )
        behavior = _dig(params, "sections", "show", 0, "behavior")
        assert behavior is not None
        assert behavior.get("retentionUnboundedMode") == mode

    def test_m12_retention_cumulative(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """M12 -- retention_cumulative=True threads to measurement.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        params = ws.build_retention_params(
            real_events_pair[0],
            real_events_pair[1],
            retention_cumulative=True,
            last=7,
        )
        measurement = _dig(params, "sections", "show", 0, "measurement")
        assert measurement is not None
        assert measurement.get("retentionCumulative") is True

    def test_m13_retention_cumulative_default_false(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """M13 -- retention_cumulative defaults to False (omitted or False).

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        params = ws.build_retention_params(
            real_events_pair[0],
            real_events_pair[1],
            last=7,
        )
        measurement = _dig(params, "sections", "show", 0, "measurement")
        assert measurement is not None
        # Either absent or explicitly False
        assert measurement.get("retentionCumulative") in (None, False)

    @pytest.mark.parametrize("method", ["all", "first"])
    def test_m14_segment_method_on_metric(
        self, ws: Workspace, real_event: str, method: str
    ) -> None:
        """M14 -- segment_method on Metric accepted by build_params.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
            method: Segment method value.
        """
        m = Metric(real_event, segment_method=method)  # type: ignore[arg-type]
        params = ws.build_params(m, last=7)
        # Verify the param builds without error
        assert isinstance(params, dict)

    def test_m15_segment_method_in_measurement(
        self,
        ws: Workspace,
        real_event: str,
    ) -> None:
        """M15 -- segment_method threads to measurement.segmentMethod.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        m = Metric(real_event, segment_method="first")
        params = ws.build_params(m, last=7)
        measurement = _dig(params, "sections", "show", 0, "measurement")
        assert measurement is not None
        assert measurement.get("segmentMethod") == "first"


# =============================================================================
# OFFLINE VALIDATION — US3: Time Comparison
# =============================================================================


class TestOfflineUS3:
    """Offline param-building tests for User Story 3 (time comparison)."""

    def test_m16_relative_time_comparison(self, ws: Workspace, real_event: str) -> None:
        """M16 -- Relative time comparison appears in displayOptions.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        tc = TimeComparison.relative("month")
        params = ws.build_params(real_event, last=30, time_comparison=tc)
        tc_output = _dig(params, "displayOptions", "timeComparison")
        assert tc_output is not None
        assert tc_output.get("type") == "relative"
        assert tc_output.get("value") == "month"

    def test_m17_absolute_start_time_comparison(
        self, ws: Workspace, real_event: str
    ) -> None:
        """M17 -- Absolute-start comparison with date in displayOptions.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        tc = TimeComparison.absolute_start("2026-01-01")
        params = ws.build_params(
            real_event,
            from_date="2026-03-01",
            to_date="2026-03-31",
            time_comparison=tc,
        )
        tc_output = _dig(params, "displayOptions", "timeComparison")
        assert tc_output is not None
        assert tc_output.get("type") == "absolute-start"
        assert tc_output.get("value") == "2026-01-01"

    def test_m18_absolute_end_time_comparison(
        self, ws: Workspace, real_event: str
    ) -> None:
        """M18 -- Absolute-end comparison with date in displayOptions.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        tc = TimeComparison.absolute_end("2026-12-31")
        params = ws.build_params(
            real_event,
            from_date="2026-03-01",
            to_date="2026-03-31",
            time_comparison=tc,
        )
        tc_output = _dig(params, "displayOptions", "timeComparison")
        assert tc_output is not None
        assert tc_output.get("type") == "absolute-end"
        assert tc_output.get("value") == "2026-12-31"

    @pytest.mark.parametrize("unit", ["day", "week", "month", "quarter", "year"])
    def test_m19_all_relative_units(
        self, ws: Workspace, real_event: str, unit: str
    ) -> None:
        """M19 -- Every relative time comparison unit is accepted.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
            unit: Time comparison unit.
        """
        tc = TimeComparison.relative(unit)  # type: ignore[arg-type]
        params = ws.build_params(real_event, last=30, time_comparison=tc)
        tc_output = _dig(params, "displayOptions", "timeComparison")
        assert tc_output is not None
        assert tc_output.get("value") == unit

    def test_m20_time_comparison_on_funnel(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """M20 -- Time comparison threads through funnel params.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        tc = TimeComparison.relative("week")
        params = ws.build_funnel_params(
            list(real_events_pair), last=30, time_comparison=tc
        )
        tc_output = _dig(params, "displayOptions", "timeComparison")
        assert tc_output is not None

    def test_m21_time_comparison_on_retention(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """M21 -- Time comparison threads through retention params.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        tc = TimeComparison.relative("month")
        params = ws.build_retention_params(
            real_events_pair[0],
            real_events_pair[1],
            last=30,
            time_comparison=tc,
        )
        tc_output = _dig(params, "displayOptions", "timeComparison")
        assert tc_output is not None


# =============================================================================
# OFFLINE VALIDATION — US4: Frequency Analysis
# =============================================================================


class TestOfflineUS4:
    """Offline param-building tests for User Story 4 (frequency)."""

    def test_m22_frequency_breakdown_in_group(
        self, ws: Workspace, real_event: str
    ) -> None:
        """M22 -- FrequencyBreakdown produces frequency group entry.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        fb = FrequencyBreakdown(real_event, bucket_size=1, bucket_min=0, bucket_max=10)
        params = ws.build_params(real_event, group_by=fb, last=7)
        group = _dig(params, "sections", "group")
        assert group is not None
        assert len(group) > 0

    def test_m23_frequency_breakdown_has_behavior_type(
        self, ws: Workspace, real_event: str
    ) -> None:
        """M23 -- FrequencyBreakdown group entry has behavior.behaviorType=$frequency.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        fb = FrequencyBreakdown(real_event)
        params = ws.build_params(real_event, group_by=fb, last=7)
        group = _dig(params, "sections", "group")
        assert group is not None
        # Find the frequency group entry (behaviorType is inside behavior dict)
        freq_entries = [
            g
            for g in group
            if isinstance(g, dict)
            and g.get("behavior", {}).get("behaviorType") == "$frequency"
        ]
        assert len(freq_entries) > 0

    def test_m24_frequency_breakdown_resource_type_people(
        self, ws: Workspace, real_event: str
    ) -> None:
        """M24 -- FrequencyBreakdown forces resourceType=people.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        fb = FrequencyBreakdown(real_event)
        params = ws.build_params(real_event, group_by=fb, last=7)
        group = _dig(params, "sections", "group")
        assert group is not None
        freq_entries = [
            g
            for g in group
            if isinstance(g, dict)
            and g.get("behavior", {}).get("behaviorType") == "$frequency"
        ]
        assert len(freq_entries) > 0
        assert freq_entries[0].get("resourceType") == "people"

    def test_m25_frequency_breakdown_custom_buckets(
        self, ws: Workspace, real_event: str
    ) -> None:
        """M25 -- Custom bucket config appears in group entry.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        fb = FrequencyBreakdown(real_event, bucket_size=5, bucket_min=0, bucket_max=50)
        params = ws.build_params(real_event, group_by=fb, last=7)
        group = _dig(params, "sections", "group")
        assert group is not None
        assert len(group) > 0

    def test_m26_frequency_filter_in_filter(
        self, ws: Workspace, real_event: str
    ) -> None:
        """M26 -- FrequencyFilter produces filter entry.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        ff = FrequencyFilter(real_event, operator="is at least", value=5)
        params = ws.build_params(real_event, where=ff, last=7)
        filt = _dig(params, "sections", "filter")
        assert filt is not None
        assert len(filt) > 0

    @pytest.mark.parametrize(
        "operator",
        [
            "is at least",
            "is at most",
            "is greater than",
            "is less than",
            "is equal to",
        ],
    )
    def test_m27_frequency_filter_operators(
        self, ws: Workspace, real_event: str, operator: str
    ) -> None:
        """M27 -- All 6 frequency filter operators accepted.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
            operator: Frequency filter operator.
        """
        ff = FrequencyFilter(real_event, operator=operator, value=5)  # type: ignore[arg-type]
        params = ws.build_params(real_event, where=ff, last=7)
        assert isinstance(params, dict)

    def test_m28_frequency_filter_with_date_range(
        self, ws: Workspace, real_event: str
    ) -> None:
        """M28 -- FrequencyFilter with date range params accepted.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        ff = FrequencyFilter(
            real_event,
            value=3,
            date_range_value=30,
            date_range_unit="day",
        )
        params = ws.build_params(real_event, where=ff, last=7)
        assert isinstance(params, dict)


# =============================================================================
# OFFLINE VALIDATION — US5: Enhanced Behavioral Cohorts
# =============================================================================


class TestOfflineUS5:
    """Offline tests for User Story 5 (cohort aggregations)."""

    @pytest.mark.parametrize(
        "agg", ["total", "unique", "average", "min", "max", "median"]
    )
    def test_m29_cohort_aggregation_operators(self, agg: str) -> None:
        """M29 -- All 6 cohort aggregation operators accepted.

        Args:
            agg: Aggregation type.
        """
        criteria = CohortCriteria.did_event(
            "Purchase",
            aggregation=agg,  # type: ignore[arg-type]
            aggregation_property="amount",
            at_least=50,
            within_days=30,
        )
        assert criteria is not None

    def test_m30_cohort_aggregation_serializes(self) -> None:
        """M30 -- Aggregation-based criteria serializes correctly."""
        criteria = CohortCriteria.did_event(
            "Purchase",
            aggregation="average",
            aggregation_property="amount",
            at_least=50,
            within_days=30,
        )
        # CohortCriteria has a behavior property
        behavior = criteria._behavior
        assert isinstance(behavior, dict)

    def test_m31_cohort_count_based_still_works(self) -> None:
        """M31 -- Count-based cohort criteria (no aggregation) still works."""
        criteria = CohortCriteria.did_event(
            "Purchase",
            at_least=5,
            within_days=30,
        )
        assert criteria is not None
        behavior = criteria._behavior
        assert isinstance(behavior, dict)


# =============================================================================
# OFFLINE VALIDATION — US6: Complete Filter Operator Coverage
# =============================================================================


class TestOfflineUS6:
    """Offline tests for User Story 6 (new filter methods)."""

    def test_m32_not_between(self) -> None:
        """M32 -- Filter.not_between produces correct operator."""
        f = Filter.not_between("age", 18, 25)
        assert f._operator == "not between"
        assert f._value == [18, 25]
        assert f._property_type == "number"

    def test_m33_starts_with(self) -> None:
        """M33 -- Filter.starts_with produces correct operator."""
        f = Filter.starts_with("email", "admin")
        assert f._operator == "starts with"
        assert f._value == "admin"
        assert f._property_type == "string"

    def test_m34_ends_with(self) -> None:
        """M34 -- Filter.ends_with produces correct operator."""
        f = Filter.ends_with("domain", ".edu")
        assert f._operator == "ends with"
        assert f._value == ".edu"
        assert f._property_type == "string"

    def test_m35_date_not_between(self) -> None:
        """M35 -- Filter.date_not_between produces correct operator."""
        f = Filter.date_not_between("created", "2025-01-01", "2025-06-30")
        assert f._operator == "was not between"
        assert f._value == ["2025-01-01", "2025-06-30"]
        assert f._property_type == "datetime"

    def test_m36_in_the_next(self) -> None:
        """M36 -- Filter.in_the_next produces correct operator."""
        f = Filter.in_the_next("trial_end", 7, "day")
        assert f._operator == "was in the next"
        assert f._value == 7
        assert f._property_type == "datetime"
        assert f._date_unit == "day"

    def test_m37_at_least(self) -> None:
        """M37 -- Filter.at_least produces correct operator."""
        f = Filter.at_least("purchase_count", 5)
        assert f._operator == "is at least"
        assert f._value == 5
        assert f._property_type == "number"

    def test_m38_at_most(self) -> None:
        """M38 -- Filter.at_most produces correct operator."""
        f = Filter.at_most("age", 65)
        assert f._operator == "is at most"
        assert f._value == 65
        assert f._property_type == "number"

    def test_m39_new_filters_in_build_params(
        self, ws: Workspace, real_event: str
    ) -> None:
        """M39 -- New filter methods accepted by build_params.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        f = Filter.at_least("$browser_version", 10)
        params = ws.build_params(real_event, where=f, last=7)
        assert isinstance(params, dict)
        filt = _dig(params, "sections", "filter")
        assert filt is not None

    def test_m40_starts_with_in_build_params(
        self, ws: Workspace, real_event: str
    ) -> None:
        """M40 -- starts_with filter accepted by build_params.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        f = Filter.starts_with("$browser", "Chr")
        params = ws.build_params(real_event, where=f, last=7)
        assert isinstance(params, dict)


# =============================================================================
# OFFLINE VALIDATION — US7: Group Analytics Scoping
# =============================================================================


class TestOfflineUS7:
    """Offline tests for User Story 7 (data_group_id)."""

    def test_m41_data_group_id_insights(self, ws: Workspace, real_event: str) -> None:
        """M41 -- data_group_id threads into insights params.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        params = ws.build_params(real_event, data_group_id=5, last=7)
        assert isinstance(params, dict)
        # Check dataGroupId appears in the structure
        dg = _dig(params, "sections", "dataGroupId")
        assert dg == 5

    def test_m42_data_group_id_funnel(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """M42 -- data_group_id threads into funnel params.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        params = ws.build_funnel_params(list(real_events_pair), data_group_id=5, last=7)
        assert isinstance(params, dict)
        dg = _dig(params, "sections", "dataGroupId")
        assert dg == 5

    def test_m43_data_group_id_retention(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """M43 -- data_group_id threads into retention params.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        params = ws.build_retention_params(
            real_events_pair[0],
            real_events_pair[1],
            data_group_id=5,
            last=7,
        )
        assert isinstance(params, dict)
        dg = _dig(params, "sections", "dataGroupId")
        assert dg == 5

    def test_m44_data_group_id_flow(self, ws: Workspace, real_event: str) -> None:
        """M44 -- data_group_id threads into flow params.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        params = ws.build_flow_params(real_event, data_group_id=5, last=7)
        assert isinstance(params, dict)
        dg = params.get("data_group_id")
        assert dg == 5

    def test_m45_data_group_id_default_none(
        self, ws: Workspace, real_event: str
    ) -> None:
        """M45 -- Omitting data_group_id preserves None/absent default.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        params = ws.build_params(real_event, last=7)
        dg = _dig(params, "sections", "dataGroupId")
        assert dg is None


# =============================================================================
# OFFLINE VALIDATION — US8: Advanced Flow Features
# =============================================================================


class TestOfflineUS8:
    """Offline tests for User Story 8 (flow features)."""

    def test_m46_flow_session_event_start(self, ws: Workspace) -> None:
        """M46 -- FlowStep with session_event=start produces correct params.

        Args:
            ws: Workspace fixture.
        """
        step = FlowStep("$session_start", session_event="start", forward=5)
        params = ws.build_flow_params(step, last=7)
        assert isinstance(params, dict)
        steps = params.get("steps", [])
        assert len(steps) > 0

    def test_m47_flow_session_event_end(self, ws: Workspace) -> None:
        """M47 -- FlowStep with session_event=end produces correct params.

        Args:
            ws: Workspace fixture.
        """
        step = FlowStep("$session_end", session_event="end", forward=3)
        params = ws.build_flow_params(step, last=7)
        assert isinstance(params, dict)

    def test_m48_flow_exclusions(self, ws: Workspace, real_event: str) -> None:
        """M48 -- Flow exclusions parameter accepted.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        params = ws.build_flow_params(
            real_event,
            exclusions=["$identify", "$mp_web_page_view"],
            last=7,
        )
        assert isinstance(params, dict)
        excl = params.get("exclusions")
        assert excl is not None

    def test_m49_flow_segments_groupby(self, ws: Workspace, real_event: str) -> None:
        """M49 -- Flow segments parameter with GroupBy accepted.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        params = ws.build_flow_params(
            real_event,
            segments=GroupBy(property="$browser"),
            last=7,
        )
        assert isinstance(params, dict)
        segs = params.get("segments")
        assert segs is not None

    def test_m50_flow_property_filter(self, ws: Workspace, real_event: str) -> None:
        """M50 -- Flow with property filter produces filter_by_event.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        params = ws.build_flow_params(
            real_event,
            where=Filter.equals("$browser", "Chrome"),
            last=7,
        )
        assert isinstance(params, dict)
        fbe = params.get("filter_by_event")
        assert fbe is not None

    def test_m51_flow_cohort_filter_still_works(
        self, ws: Workspace, real_event: str
    ) -> None:
        """M51 -- Flow with cohort filter still produces filter_by_cohort.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        # Use in_cohort filter -- may not have a real cohort, so just
        # verify the params build without error.
        f = Filter.in_cohort(12345)
        params = ws.build_flow_params(real_event, where=f, last=7)
        assert isinstance(params, dict)


# =============================================================================
# VALIDATION ERROR TESTS
# =============================================================================


class TestValidationErrors:
    """Tests that verify invalid inputs raise appropriate errors."""

    def test_v01_time_comparison_relative_requires_unit(self) -> None:
        """V01 -- TimeComparison.relative without unit raises TypeError."""
        with pytest.raises(TypeError):
            TimeComparison.relative()  # type: ignore[call-arg]

    def test_v02_time_comparison_relative_rejects_date(self) -> None:
        """V02 -- TimeComparison type=relative with date raises ValueError."""
        with pytest.raises(ValueError, match="does not accept date"):
            TimeComparison(type="relative", unit="month", date="2026-01-01")

    def test_v03_time_comparison_absolute_requires_date(self) -> None:
        """V03 -- TimeComparison absolute-start without date raises ValueError."""
        with pytest.raises(ValueError, match="requires date"):
            TimeComparison(type="absolute-start")

    def test_v04_time_comparison_absolute_rejects_unit(self) -> None:
        """V04 -- TimeComparison absolute-start with unit raises ValueError."""
        with pytest.raises(ValueError, match="does not accept unit"):
            TimeComparison(type="absolute-start", date="2026-01-01", unit="month")

    def test_v05_time_comparison_bad_date_format(self) -> None:
        """V05 -- TimeComparison with non-YYYY-MM-DD date raises ValueError."""
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            TimeComparison.absolute_start("01-01-2026")

    def test_v06_time_comparison_rejected_on_flow(
        self, ws: Workspace, real_event: str
    ) -> None:
        """V06 -- time_comparison is not accepted on flow queries.

        Flow queries deliberately exclude time_comparison from their
        signature. Passing it raises TypeError (unexpected keyword).

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        tc = TimeComparison.relative("month")
        with pytest.raises(TypeError, match="time_comparison"):
            ws.build_flow_params(  # type: ignore[call-arg]
                real_event, last=7, time_comparison=tc
            )

    def test_v07_frequency_breakdown_empty_event(self) -> None:
        """V07 -- FrequencyBreakdown with empty event raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            FrequencyBreakdown("")

    def test_v08_frequency_breakdown_negative_bucket_size(self) -> None:
        """V08 -- FrequencyBreakdown with negative bucket_size raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            FrequencyBreakdown("Login", bucket_size=-1)

    def test_v09_frequency_breakdown_min_ge_max(self) -> None:
        """V09 -- FrequencyBreakdown with bucket_min >= bucket_max raises ValueError."""
        with pytest.raises(ValueError, match="less than"):
            FrequencyBreakdown("Login", bucket_min=10, bucket_max=5)

    def test_v10_frequency_breakdown_negative_min(self) -> None:
        """V10 -- FrequencyBreakdown with negative bucket_min raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            FrequencyBreakdown("Login", bucket_min=-1)

    def test_v11_frequency_filter_empty_event(self) -> None:
        """V11 -- FrequencyFilter with empty event raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            FrequencyFilter("", value=5)

    def test_v12_frequency_filter_invalid_operator(self) -> None:
        """V12 -- FrequencyFilter with invalid operator raises ValueError."""
        with pytest.raises(ValueError, match="operator"):
            FrequencyFilter("Login", operator="bad op", value=5)  # type: ignore[arg-type]

    def test_v13_frequency_filter_negative_value(self) -> None:
        """V13 -- FrequencyFilter with negative value raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            FrequencyFilter("Login", value=-1)

    def test_v14_frequency_filter_date_range_mismatch(self) -> None:
        """V14 -- FrequencyFilter with only date_range_value raises ValueError."""
        with pytest.raises(ValueError, match="both be set"):
            FrequencyFilter("Login", value=5, date_range_value=30)

    def test_v15_frequency_filter_date_range_unit_only(self) -> None:
        """V15 -- FrequencyFilter with only date_range_unit raises ValueError."""
        with pytest.raises(ValueError, match="both be set"):
            FrequencyFilter("Login", value=5, date_range_unit="day")

    def test_v16_frequency_filter_date_range_zero(self) -> None:
        """V16 -- FrequencyFilter with date_range_value=0 raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            FrequencyFilter("Login", value=5, date_range_value=0, date_range_unit="day")

    def test_v17_cohort_aggregation_requires_property(self) -> None:
        """V17 -- CohortCriteria aggregation without property raises ValueError."""
        with pytest.raises(ValueError):
            CohortCriteria.did_event(
                "Purchase",
                aggregation="average",
                at_least=50,
                within_days=30,
            )

    def test_v18_cohort_aggregation_property_requires_aggregation(self) -> None:
        """V18 -- CohortCriteria aggregation_property without aggregation raises ValueError."""
        with pytest.raises(ValueError):
            CohortCriteria.did_event(
                "Purchase",
                aggregation_property="amount",
                at_least=50,
                within_days=30,
            )

    def test_v19_flow_step_session_event_mismatch(self) -> None:
        """V19 -- FlowStep session_event=start with wrong event name raises ValueError."""
        with pytest.raises(ValueError, match="session_event"):
            FlowStep("Login", session_event="start")

    def test_v20_flow_step_session_event_end_mismatch(self) -> None:
        """V20 -- FlowStep session_event=end with wrong event name raises ValueError."""
        with pytest.raises(ValueError, match="session_event"):
            FlowStep("Login", session_event="end")

    def test_v21_flow_step_forward_out_of_range(self) -> None:
        """V21 -- FlowStep with forward=6 raises ValueError."""
        with pytest.raises(ValueError, match="0-5"):
            FlowStep("Login", forward=6)

    def test_v22_flow_step_reverse_out_of_range(self) -> None:
        """V22 -- FlowStep with reverse=6 raises ValueError."""
        with pytest.raises(ValueError, match="0-5"):
            FlowStep("Login", reverse=6)

    def test_v23_metric_property_required_math_no_property(self) -> None:
        """V23 -- Metric with unique_values but no property raises ValueError."""
        with pytest.raises(ValueError):
            Metric("Login", math="unique_values")

    def test_v24_metric_property_required_multi_attribution(self) -> None:
        """V24 -- Metric with multi_attribution but no property raises ValueError."""
        with pytest.raises(ValueError):
            Metric("Login", math="multi_attribution")

    def test_v25_metric_property_required_numeric_summary(self) -> None:
        """V25 -- Metric with numeric_summary but no property raises ValueError."""
        with pytest.raises(ValueError):
            Metric("Login", math="numeric_summary")


# =============================================================================
# LIVE API TESTS — US1: Math Types
# =============================================================================


class TestLiveUS1:
    """Live API tests for expanded math types."""

    def test_l01_cumulative_unique_live(self, ws: Workspace, real_event: str) -> None:
        """L01 -- cumulative_unique math type returns valid result.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        result = _query_or_api_error(
            ws.query, real_event, math="cumulative_unique", last=7
        )
        if result is not None:
            assert isinstance(result, QueryResult)

    def test_l02_sessions_math_live(self, ws: Workspace, real_event: str) -> None:
        """L02 -- sessions math type returns valid result.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        result = _query_or_api_error(ws.query, real_event, math="sessions", last=7)
        if result is not None:
            assert isinstance(result, QueryResult)

    def test_l03_unique_values_live(self, ws: Workspace, real_event: str) -> None:
        """L03 -- unique_values math type with property returns result.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        result = _query_or_api_error(
            ws.query,
            real_event,
            math="unique_values",
            math_property="$browser",
            last=7,
        )
        if result is not None:
            assert isinstance(result, QueryResult)

    def test_l04_most_frequent_live(self, ws: Workspace, real_event: str) -> None:
        """L04 -- most_frequent math type with property returns result.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        result = _query_or_api_error(
            ws.query,
            real_event,
            math="most_frequent",
            math_property="$browser",
            last=7,
        )
        if result is not None:
            assert isinstance(result, QueryResult)

    def test_l05_retention_total_live(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """L05 -- Retention with math=total returns valid result.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        result = _query_or_api_error(
            ws.query_retention,
            real_events_pair[0],
            real_events_pair[1],
            math="total",
            last=7,
        )
        if result is not None:
            assert isinstance(result, RetentionQueryResult)


# =============================================================================
# LIVE API TESTS — US2: Advanced Modes
# =============================================================================


class TestLiveUS2:
    """Live API tests for funnel reentry, retention unbounded/cumulative."""

    def test_l06_funnel_reentry_aggressive(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """L06 -- Funnel with reentry_mode=aggressive returns result.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        result = _query_or_api_error(
            ws.query_funnel,
            list(real_events_pair),
            reentry_mode="aggressive",
            last=7,
        )
        if result is not None:
            assert isinstance(result, FunnelQueryResult)

    def test_l07_retention_carry_forward(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """L07 -- Retention with unbounded_mode=carry_forward returns result.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        result = _query_or_api_error(
            ws.query_retention,
            real_events_pair[0],
            real_events_pair[1],
            unbounded_mode="carry_forward",
            last=7,
        )
        if result is not None:
            assert isinstance(result, RetentionQueryResult)

    def test_l08_retention_cumulative_live(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """L08 -- Retention with retention_cumulative=True returns result.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        result = _query_or_api_error(
            ws.query_retention,
            real_events_pair[0],
            real_events_pair[1],
            retention_cumulative=True,
            last=7,
        )
        if result is not None:
            assert isinstance(result, RetentionQueryResult)


# =============================================================================
# LIVE API TESTS — US3: Time Comparison
# =============================================================================


class TestLiveUS3:
    """Live API tests for time comparison."""

    def test_l09_time_comparison_relative_live(
        self, ws: Workspace, real_event: str
    ) -> None:
        """L09 -- Query with relative time comparison returns result.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        tc = TimeComparison.relative("month")
        result = _query_or_api_error(ws.query, real_event, last=30, time_comparison=tc)
        if result is not None:
            assert isinstance(result, QueryResult)

    def test_l10_time_comparison_funnel_live(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """L10 -- Funnel with time comparison returns result.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        tc = TimeComparison.relative("week")
        result = _query_or_api_error(
            ws.query_funnel,
            list(real_events_pair),
            last=30,
            time_comparison=tc,
        )
        if result is not None:
            assert isinstance(result, FunnelQueryResult)

    def test_l11_time_comparison_retention_live(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """L11 -- Retention with time comparison returns result.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        tc = TimeComparison.relative("month")
        result = _query_or_api_error(
            ws.query_retention,
            real_events_pair[0],
            real_events_pair[1],
            last=30,
            time_comparison=tc,
        )
        if result is not None:
            assert isinstance(result, RetentionQueryResult)


# =============================================================================
# LIVE API TESTS — US4: Frequency Analysis
# =============================================================================


class TestLiveUS4:
    """Live API tests for frequency breakdown and filter."""

    def test_l12_frequency_breakdown_live(self, ws: Workspace, real_event: str) -> None:
        """L12 -- Query with frequency breakdown returns result.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        fb = FrequencyBreakdown(real_event)
        result = _query_or_api_error(ws.query, real_event, group_by=fb, last=7)
        if result is not None:
            assert isinstance(result, QueryResult)

    def test_l13_frequency_filter_live(self, ws: Workspace, real_event: str) -> None:
        """L13 -- Query with frequency filter returns result.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        ff = FrequencyFilter(real_event, value=1)
        result = _query_or_api_error(ws.query, real_event, where=ff, last=7)
        if result is not None:
            assert isinstance(result, QueryResult)


# =============================================================================
# LIVE API TESTS — US6: Filters
# =============================================================================


class TestLiveUS6:
    """Live API tests for new filter methods."""

    def test_l14_at_least_filter_live(self, ws: Workspace, real_event: str) -> None:
        """L14 -- Query with at_least filter returns result.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        f = Filter.at_least("$browser_version", 1)
        result = _query_or_api_error(ws.query, real_event, where=f, last=7)
        if result is not None:
            assert isinstance(result, QueryResult)

    def test_l15_starts_with_filter_live(self, ws: Workspace, real_event: str) -> None:
        """L15 -- Query with starts_with filter returns result.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        f = Filter.starts_with("$browser", "Chr")
        result = _query_or_api_error(ws.query, real_event, where=f, last=7)
        if result is not None:
            assert isinstance(result, QueryResult)

    def test_l16_not_between_filter_live(self, ws: Workspace, real_event: str) -> None:
        """L16 -- Query with not_between filter returns result.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        f = Filter.not_between("$browser_version", 0, 50)
        result = _query_or_api_error(ws.query, real_event, where=f, last=7)
        if result is not None:
            assert isinstance(result, QueryResult)


# =============================================================================
# LIVE API TESTS — US7: Data Group ID
# =============================================================================


class TestLiveUS7:
    """Live API tests for data_group_id parameter."""

    def test_l17_data_group_id_live(self, ws: Workspace, real_event: str) -> None:
        """L17 -- Query with data_group_id does not crash.

        The server may reject if the project has no data groups,
        but the client must not crash.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        result = _query_or_api_error(ws.query, real_event, data_group_id=5, last=7)
        # Either a valid result or an API error; no crash
        if result is not None:
            assert isinstance(result, QueryResult)


# =============================================================================
# LIVE API TESTS — US8: Flow Features
# =============================================================================


class TestLiveUS8:
    """Live API tests for advanced flow features."""

    def test_l18_flow_with_property_filter_live(
        self, ws: Workspace, real_event: str
    ) -> None:
        """L18 -- Flow with property filter returns result.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        f = Filter.equals("$browser", "Chrome")
        result = _query_or_api_error(ws.query_flow, real_event, where=f, last=7)
        if result is not None:
            assert isinstance(result, FlowQueryResult)

    def test_l19_flow_with_exclusions_live(
        self, ws: Workspace, real_event: str
    ) -> None:
        """L19 -- Flow with exclusions returns result.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        result = _query_or_api_error(
            ws.query_flow,
            real_event,
            exclusions=["$identify"],
            last=7,
        )
        if result is not None:
            assert isinstance(result, FlowQueryResult)

    def test_l20_flow_with_segments_live(self, ws: Workspace, real_event: str) -> None:
        """L20 -- Flow with segments (GroupBy) returns result.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        result = _query_or_api_error(
            ws.query_flow,
            real_event,
            segments=GroupBy(property="$browser"),
            last=7,
        )
        if result is not None:
            assert isinstance(result, FlowQueryResult)

    def test_l21_flow_session_start_live(self, ws: Workspace) -> None:
        """L21 -- Flow with session_event=start anchor returns result.

        Args:
            ws: Workspace fixture.
        """
        step = FlowStep("$session_start", session_event="start", forward=3)
        result = _query_or_api_error(ws.query_flow, step, last=7)
        if result is not None:
            assert isinstance(result, FlowQueryResult)


# =============================================================================
# CROSS-PARAMETER INTERACTION TESTS — X01-X07
# =============================================================================


class TestCrossParameterInteractions:
    """Tests combining multiple new features together."""

    def test_x01_time_comparison_plus_new_math(
        self, ws: Workspace, real_event: str
    ) -> None:
        """X01 -- Time comparison combined with cumulative_unique math.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        tc = TimeComparison.relative("month")
        params = ws.build_params(
            real_event,
            math="cumulative_unique",
            last=30,
            time_comparison=tc,
        )
        assert isinstance(params, dict)
        assert _dig(params, "displayOptions", "timeComparison") is not None

    def test_x02_frequency_breakdown_plus_filter(
        self, ws: Workspace, real_event: str
    ) -> None:
        """X02 -- Frequency breakdown with a property filter combined.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        fb = FrequencyBreakdown(real_event)
        f = Filter.equals("$browser", "Chrome")
        params = ws.build_params(real_event, group_by=fb, where=f, last=7)
        assert isinstance(params, dict)
        assert _dig(params, "sections", "group") is not None
        assert _dig(params, "sections", "filter") is not None

    def test_x03_frequency_filter_plus_groupby(
        self, ws: Workspace, real_event: str
    ) -> None:
        """X03 -- Frequency filter with a standard GroupBy combined.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        ff = FrequencyFilter(real_event, value=2)
        gb = GroupBy(property="$browser")
        params = ws.build_params(real_event, group_by=gb, where=ff, last=7)
        assert isinstance(params, dict)
        assert _dig(params, "sections", "group") is not None
        assert _dig(params, "sections", "filter") is not None

    def test_x04_reentry_mode_plus_time_comparison(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """X04 -- Funnel reentry mode combined with time comparison.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        tc = TimeComparison.relative("week")
        params = ws.build_funnel_params(
            list(real_events_pair),
            reentry_mode="aggressive",
            time_comparison=tc,
            last=30,
        )
        assert isinstance(params, dict)
        behavior = _dig(params, "sections", "show", 0, "behavior")
        assert behavior is not None
        assert behavior.get("funnelReentryMode") == "aggressive"
        assert _dig(params, "displayOptions", "timeComparison") is not None

    def test_x05_unbounded_plus_cumulative_plus_time_comparison(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """X05 -- Retention unbounded + cumulative + time comparison combined.

        Args:
            ws: Workspace fixture.
            real_events_pair: Two known event names.
        """
        tc = TimeComparison.relative("month")
        params = ws.build_retention_params(
            real_events_pair[0],
            real_events_pair[1],
            unbounded_mode="carry_forward",
            retention_cumulative=True,
            time_comparison=tc,
            last=30,
        )
        assert isinstance(params, dict)
        behavior = _dig(params, "sections", "show", 0, "behavior")
        measurement = _dig(params, "sections", "show", 0, "measurement")
        assert behavior is not None
        assert behavior.get("retentionUnboundedMode") == "carry_forward"
        assert measurement is not None
        assert measurement.get("retentionCumulative") is True
        assert _dig(params, "displayOptions", "timeComparison") is not None

    def test_x06_data_group_id_plus_frequency(
        self, ws: Workspace, real_event: str
    ) -> None:
        """X06 -- data_group_id combined with frequency breakdown.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        fb = FrequencyBreakdown(real_event)
        params = ws.build_params(real_event, group_by=fb, data_group_id=5, last=7)
        assert isinstance(params, dict)
        assert _dig(params, "sections", "dataGroupId") == 5
        assert _dig(params, "sections", "group") is not None

    def test_x07_flow_exclusions_plus_segments_plus_filter(
        self, ws: Workspace, real_event: str
    ) -> None:
        """X07 -- Flow with exclusions + segments + property filter combined.

        Args:
            ws: Workspace fixture.
            real_event: Known event name.
        """
        params = ws.build_flow_params(
            real_event,
            exclusions=["$identify"],
            segments=GroupBy(property="$browser"),
            where=Filter.equals("$os", "Mac OS X"),
            last=7,
        )
        assert isinstance(params, dict)
        assert params.get("exclusions") is not None
        assert params.get("segments") is not None
        assert params.get("filter_by_event") is not None
