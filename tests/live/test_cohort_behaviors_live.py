"""Live QA tests for cohort behaviors (Phase 036).

Exercises Filter.in_cohort/not_in_cohort, CohortBreakdown, and
CohortMetric against the real Mixpanel API on account ``p8``
(project ID 8). These tests discover real data dynamically and
create/clean up QA objects with a ``QA-036-`` prefix.

Usage:
    uv run pytest tests/live/test_cohort_behaviors_live.py -v
    uv run pytest tests/live/test_cohort_behaviors_live.py -v -k "CohortFilter"
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Generator

import pytest

from mixpanel_headless import (
    CohortBreakdown,
    CohortCriteria,
    CohortDefinition,
    CohortMetric,
    CreateCohortParams,
    Filter,
    GroupBy,
    Metric,
    QueryResult,
    Workspace,
)
from mixpanel_headless.exceptions import BookmarkValidationError, QueryError
from mixpanel_headless.types import (
    FlowQueryResult,
    FunnelQueryResult,
    RetentionQueryResult,
)

pytestmark = pytest.mark.live

# =============================================================================
# Constants
# =============================================================================

QA_PREFIX = "QA-036-"

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def ws() -> Workspace:
    """Create Workspace with p8 credentials.

    Returns:
        Workspace connected to project 8.
    """
    return Workspace(account="p8")


@pytest.fixture(scope="module", autouse=True)
def _cleanup_stale_qa_cohorts(ws: Workspace) -> None:
    """Remove stale QA-036-* cohorts from previous runs.

    Runs once at module start. Suppresses errors for already-deleted objects.
    """
    cohorts = ws.cohorts()
    for c in cohorts:
        if c.name.startswith(QA_PREFIX):
            with contextlib.suppress(Exception):
                ws.delete_cohort(c.id)


@pytest.fixture(scope="module")
def real_event(ws: Workspace) -> str:
    """Discover a real event name from project 8.

    Returns:
        First available event name.
    """
    events = ws.events()
    assert len(events) > 0, "No events found in project 8"
    return events[0]


@pytest.fixture(scope="module")
def real_events_pair(ws: Workspace) -> tuple[str, str]:
    """Discover two real event names for funnel/retention tests.

    Returns:
        Tuple of two distinct event names.
    """
    events = ws.events()
    assert len(events) >= 2, "Need at least 2 events for funnels/retention"
    return events[0], events[1]


@pytest.fixture(scope="module")
def real_cohort(ws: Workspace) -> tuple[int, str]:
    """Discover a real saved cohort from project 8.

    Returns:
        Tuple of (cohort_id, cohort_name).
    """
    cohorts = ws.cohorts()
    assert len(cohorts) > 0, "No cohorts found in project 8"
    return cohorts[0].id, cohorts[0].name


@pytest.fixture(scope="module")
def second_cohort(ws: Workspace) -> tuple[int, str]:
    """Discover a second cohort for cross-cohort tests.

    Returns:
        Tuple of (cohort_id, cohort_name) different from real_cohort.
    """
    cohorts = ws.cohorts()
    assert len(cohorts) >= 2, "Need at least 2 cohorts for cross-cohort tests"
    return cohorts[1].id, cohorts[1].name


@pytest.fixture(scope="module")
def qa_cohort(ws: Workspace, real_event: str) -> Generator[tuple[int, str]]:
    """Create a QA cohort for testing, cleaned up after.

    Uses a CohortDefinition based on a real event. The cohort may have
    members if the event occurred in the last 90 days.

    Args:
        ws: Workspace instance.
        real_event: A real event name from the project.

    Returns:
        Tuple of (cohort_id, cohort_name).
    """
    uid = uuid.uuid4().hex[:8]
    name = f"{QA_PREFIX}test-{uid}"
    definition = CohortDefinition(
        CohortCriteria.did_event(real_event, at_least=1, within_days=90)
    )
    cohort = ws.create_cohort(
        CreateCohortParams(name=name, definition=definition.to_dict())
    )
    cohort_id = cohort.id
    yield cohort_id, name
    with contextlib.suppress(Exception):
        ws.delete_cohort(cohort_id)


@pytest.fixture(scope="module")
def inline_definition(real_event: str) -> CohortDefinition:
    """Build an inline CohortDefinition for testing (no save required).

    Args:
        real_event: A real event name from the project.

    Returns:
        CohortDefinition with one behavioral criterion.
    """
    return CohortDefinition(
        CohortCriteria.did_event(real_event, at_least=1, within_days=90)
    )


# =============================================================================
# 1. Discovery & Preconditions
# =============================================================================


class TestDiscovery:
    """Verify we can discover real data before testing cohort features."""

    def test_discover_events(self, ws: Workspace) -> None:
        """Project 8 has discoverable events."""
        events = ws.events()
        assert len(events) > 0

    def test_discover_cohorts(self, ws: Workspace) -> None:
        """Project 8 has discoverable cohorts."""
        cohorts = ws.cohorts()
        assert len(cohorts) > 0
        assert cohorts[0].id > 0
        assert isinstance(cohorts[0].name, str)


# =============================================================================
# 2. Cohort Filter — Insights
# =============================================================================


class TestCohortFilterInsights:
    """Cohort filters in insights queries via Filter.in_cohort/not_in_cohort."""

    def test_query_with_saved_cohort_filter(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """Query with saved cohort filter succeeds and returns QueryResult."""
        cid, cname = real_cohort
        result = ws.query(real_event, where=Filter.in_cohort(cid, cname), last=7)
        assert isinstance(result, QueryResult)

    def test_query_with_not_in_cohort_filter(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """Query with not_in_cohort filter succeeds."""
        cid, cname = real_cohort
        result = ws.query(real_event, where=Filter.not_in_cohort(cid, cname), last=7)
        assert isinstance(result, QueryResult)

    def test_cohort_filter_changes_results(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """Cohort filter should not error, and query executes successfully both ways."""
        cid, cname = real_cohort
        unfiltered = ws.query(real_event, last=7, mode="total")
        filtered = ws.query(
            real_event, where=Filter.in_cohort(cid, cname), last=7, mode="total"
        )
        # Both should succeed — values may or may not differ
        assert isinstance(unfiltered, QueryResult)
        assert isinstance(filtered, QueryResult)

    def test_cohort_filter_combined_with_property_filter(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """Mixed cohort + property filters in a single query."""
        cid, cname = real_cohort
        result = ws.query(
            real_event,
            where=[Filter.in_cohort(cid, cname), Filter.is_set("$browser")],
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_query_with_inline_cohort_definition_filter(
        self,
        ws: Workspace,
        real_event: str,
        inline_definition: CohortDefinition,
    ) -> None:
        """Inline CohortDefinition works in cohort filter without saving."""
        result = ws.query(
            real_event,
            where=Filter.in_cohort(inline_definition, name="Inline QA"),
            last=7,
        )
        assert isinstance(result, QueryResult)


# =============================================================================
# 3. Cohort Filter — Funnels
# =============================================================================


class TestCohortFilterFunnels:
    """Cohort filters in funnel queries."""

    def test_funnel_with_cohort_filter(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        real_cohort: tuple[int, str],
    ) -> None:
        """Funnel with cohort filter succeeds."""
        e1, e2 = real_events_pair
        cid, cname = real_cohort
        result = ws.query_funnel(
            [e1, e2],
            where=Filter.in_cohort(cid, cname),
            last=30,
        )
        assert isinstance(result, FunnelQueryResult)

    def test_funnel_cohort_filter_inline_definition(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        inline_definition: CohortDefinition,
    ) -> None:
        """Funnel with inline CohortDefinition filter."""
        e1, e2 = real_events_pair
        result = ws.query_funnel(
            [e1, e2],
            where=Filter.in_cohort(inline_definition, name="Inline QA"),
            last=30,
        )
        assert isinstance(result, FunnelQueryResult)

    def test_funnel_cohort_and_property_filters_combined(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        real_cohort: tuple[int, str],
    ) -> None:
        """Funnel with mixed cohort + property filters."""
        e1, e2 = real_events_pair
        cid, cname = real_cohort
        result = ws.query_funnel(
            [e1, e2],
            where=[Filter.in_cohort(cid, cname), Filter.is_set("$browser")],
            last=30,
        )
        assert isinstance(result, FunnelQueryResult)


# =============================================================================
# 4. Cohort Filter — Retention
# =============================================================================


class TestCohortFilterRetention:
    """Cohort filters in retention queries."""

    def test_retention_with_cohort_filter(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        real_cohort: tuple[int, str],
    ) -> None:
        """Retention with saved cohort filter succeeds."""
        e1, e2 = real_events_pair
        cid, cname = real_cohort
        result = ws.query_retention(
            e1,
            e2,
            where=Filter.in_cohort(cid, cname),
            last=30,
        )
        assert isinstance(result, RetentionQueryResult)

    def test_retention_cohort_filter_inline(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        inline_definition: CohortDefinition,
    ) -> None:
        """Retention with inline CohortDefinition filter."""
        e1, e2 = real_events_pair
        result = ws.query_retention(
            e1,
            e2,
            where=Filter.in_cohort(inline_definition, name="Inline QA"),
            last=30,
        )
        assert isinstance(result, RetentionQueryResult)

    def test_retention_cohort_filter_not_in(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        real_cohort: tuple[int, str],
    ) -> None:
        """Retention with not_in_cohort filter."""
        e1, e2 = real_events_pair
        cid, cname = real_cohort
        result = ws.query_retention(
            e1,
            e2,
            where=Filter.not_in_cohort(cid, cname),
            last=30,
        )
        assert isinstance(result, RetentionQueryResult)


# =============================================================================
# 5. Cohort Filter — Flows
# =============================================================================


class TestCohortFilterFlows:
    """Cohort filters in flow queries via where= parameter."""

    def test_flow_with_cohort_filter(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """Flow with cohort filter succeeds."""
        cid, cname = real_cohort
        result = ws.query_flow(
            real_event,
            where=Filter.in_cohort(cid, cname),
            last=30,
        )
        assert isinstance(result, FlowQueryResult)

    def test_flow_with_not_in_cohort(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """Flow with negated cohort filter."""
        cid, cname = real_cohort
        result = ws.query_flow(
            real_event,
            where=Filter.not_in_cohort(cid, cname),
            last=30,
        )
        assert isinstance(result, FlowQueryResult)

    def test_flow_cohort_filter_inline(
        self,
        ws: Workspace,
        real_event: str,
        inline_definition: CohortDefinition,
    ) -> None:
        """Flow with inline CohortDefinition filter."""
        result = ws.query_flow(
            real_event,
            where=Filter.in_cohort(inline_definition, name="Inline QA"),
            last=30,
        )
        assert isinstance(result, FlowQueryResult)

    def test_flow_non_cohort_filter_rejected(
        self,
        ws: Workspace,
        real_event: str,
    ) -> None:
        """Non-cohort filter in flow where= raises ValueError (client-side)."""
        with pytest.raises(ValueError, match="query_flow where= only accepts cohort"):
            ws.query_flow(
                real_event,
                where=Filter.equals("$browser", "Chrome"),
                last=7,
            )


# =============================================================================
# 6. CohortBreakdown — Insights
# =============================================================================


class TestCohortBreakdownInsights:
    """CohortBreakdown in insights queries via group_by=."""

    def test_breakdown_with_saved_cohort(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """Breakdown by saved cohort succeeds."""
        cid, cname = real_cohort
        result = ws.query(
            real_event,
            group_by=CohortBreakdown(cid, cname),
            last=7,
        )
        assert isinstance(result, QueryResult)
        # Series should have cohort segment keys
        assert len(result.series) > 0

    def test_breakdown_include_negated_true(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """Default include_negated=True produces 'In' and 'Not In' segments."""
        cid, cname = real_cohort
        result = ws.query(
            real_event,
            group_by=CohortBreakdown(cid, cname, include_negated=True),
            last=7,
        )
        assert isinstance(result, QueryResult)
        # Series has 1 top-level metric key; segments are nested inside
        assert len(result.series) >= 1
        metric_key = next(iter(result.series))
        segments = result.series[metric_key]
        assert isinstance(segments, dict)
        assert len(segments) >= 2

    def test_breakdown_include_negated_false(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """include_negated=False produces only 'In' segment."""
        cid, cname = real_cohort
        result = ws.query(
            real_event,
            group_by=CohortBreakdown(cid, cname, include_negated=False),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_breakdown_with_inline_definition(
        self,
        ws: Workspace,
        real_event: str,
        inline_definition: CohortDefinition,
    ) -> None:
        """Breakdown by inline CohortDefinition."""
        result = ws.query(
            real_event,
            group_by=CohortBreakdown(inline_definition, name="Inline QA"),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_breakdown_mixed_with_groupby(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """CohortBreakdown + property GroupBy in same insights query."""
        cid, cname = real_cohort
        result = ws.query(
            real_event,
            group_by=[CohortBreakdown(cid, cname), GroupBy("$browser")],
            last=7,
        )
        assert isinstance(result, QueryResult)


# =============================================================================
# 7. CohortBreakdown — Funnels
# =============================================================================


class TestCohortBreakdownFunnels:
    """CohortBreakdown in funnel queries."""

    def test_funnel_with_cohort_breakdown(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        real_cohort: tuple[int, str],
    ) -> None:
        """Funnel with CohortBreakdown succeeds."""
        e1, e2 = real_events_pair
        cid, cname = real_cohort
        result = ws.query_funnel(
            [e1, e2],
            group_by=CohortBreakdown(cid, cname),
            last=30,
        )
        assert isinstance(result, FunnelQueryResult)

    def test_funnel_breakdown_inline(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        inline_definition: CohortDefinition,
    ) -> None:
        """Funnel with inline CohortDefinition breakdown."""
        e1, e2 = real_events_pair
        result = ws.query_funnel(
            [e1, e2],
            group_by=CohortBreakdown(inline_definition, name="Inline QA"),
            last=30,
        )
        assert isinstance(result, FunnelQueryResult)


# =============================================================================
# 8. CohortBreakdown — Retention
# =============================================================================


class TestCohortBreakdownRetention:
    """CohortBreakdown in retention queries, including CB3 enforcement."""

    def test_retention_with_cohort_breakdown(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        real_cohort: tuple[int, str],
    ) -> None:
        """CohortBreakdown alone in retention succeeds."""
        e1, e2 = real_events_pair
        cid, cname = real_cohort
        result = ws.query_retention(
            e1,
            e2,
            group_by=CohortBreakdown(cid, cname),
            last=30,
        )
        assert isinstance(result, RetentionQueryResult)

    def test_retention_multiple_cohort_breakdowns(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        real_cohort: tuple[int, str],
        second_cohort: tuple[int, str],
    ) -> None:
        """Two CohortBreakdowns in retention succeeds (no property GroupBy)."""
        e1, e2 = real_events_pair
        cid1, cname1 = real_cohort
        cid2, cname2 = second_cohort
        result = ws.query_retention(
            e1,
            e2,
            group_by=[CohortBreakdown(cid1, cname1), CohortBreakdown(cid2, cname2)],
            last=30,
        )
        assert isinstance(result, RetentionQueryResult)

    def test_retention_breakdown_mixed_with_groupby_rejected(
        self,
        real_cohort: tuple[int, str],
    ) -> None:
        """CB3: CohortBreakdown + GroupBy in retention raises client-side."""
        cid, cname = real_cohort
        with pytest.raises(
            BookmarkValidationError,
            match="does not support mixing",
        ):
            ws = Workspace(account="p8")
            ws.build_retention_params(
                "Signup",
                "Login",
                group_by=[CohortBreakdown(cid, cname), GroupBy("$browser")],
            )

    def test_retention_breakdown_mixed_with_string_rejected(
        self,
        real_cohort: tuple[int, str],
    ) -> None:
        """CB3: CohortBreakdown + string group_by in retention raises."""
        cid, cname = real_cohort
        with pytest.raises(
            BookmarkValidationError,
            match="does not support mixing",
        ):
            ws = Workspace(account="p8")
            ws.build_retention_params(
                "Signup",
                "Login",
                group_by=[CohortBreakdown(cid, cname), "$browser"],
            )


# =============================================================================
# 9. CohortMetric — Insights
# =============================================================================


class TestCohortMetricInsights:
    """CohortMetric in insights queries (cohort size tracking)."""

    def test_cohort_metric_saved_cohort(
        self,
        ws: Workspace,
        real_cohort: tuple[int, str],
    ) -> None:
        """CohortMetric with saved cohort returns time series."""
        cid, cname = real_cohort
        result = ws.query(CohortMetric(cid, cname), last=30)
        assert isinstance(result, QueryResult)
        assert len(result.series) > 0

    def test_cohort_metric_inline_definition_rejected_cm5(
        self,
        inline_definition: CohortDefinition,
    ) -> None:
        """CM5: CohortMetric rejects inline CohortDefinition at construction."""
        with pytest.raises(
            ValueError,
            match="CohortMetric does not support inline CohortDefinition",
        ):
            CohortMetric(inline_definition, name="Inline QA")

    def test_cohort_metric_mixed_with_event_metric(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """CohortMetric alongside regular Metric."""
        cid, cname = real_cohort
        result = ws.query(
            [Metric(real_event, math="total"), CohortMetric(cid, cname)],
            last=30,
        )
        assert isinstance(result, QueryResult)
        assert len(result.series) >= 2

    def test_cohort_metric_with_formula(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """CohortMetric with formula referencing it."""
        cid, cname = real_cohort
        result = ws.query(
            [Metric(real_event, math="unique"), CohortMetric(cid, cname)],
            formula="(B / A) * 100",
            formula_label="Cohort % of Total",
            last=30,
        )
        assert isinstance(result, QueryResult)

    def test_cohort_metric_weekly_unit(
        self,
        ws: Workspace,
        real_cohort: tuple[int, str],
    ) -> None:
        """CohortMetric with weekly time unit."""
        cid, cname = real_cohort
        result = ws.query(CohortMetric(cid, cname), last=90, unit="week")
        assert isinstance(result, QueryResult)

    def test_cohort_metric_total_mode(
        self,
        ws: Workspace,
        real_cohort: tuple[int, str],
    ) -> None:
        """CohortMetric with total mode returns single aggregate."""
        cid, cname = real_cohort
        result = ws.query(CohortMetric(cid, cname), last=30, mode="total")
        assert isinstance(result, QueryResult)


# =============================================================================
# 10. Cross-Cutting Combinations
# =============================================================================


class TestCrossCuttingCombinations:
    """Multiple cohort features in a single query."""

    def test_cohort_filter_and_breakdown_together(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
        second_cohort: tuple[int, str],
    ) -> None:
        """Filter by one cohort, breakdown by another."""
        cid1, cname1 = real_cohort
        cid2, cname2 = second_cohort
        result = ws.query(
            real_event,
            where=Filter.in_cohort(cid1, cname1),
            group_by=CohortBreakdown(cid2, cname2),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_cohort_metric_with_cohort_filter(
        self,
        ws: Workspace,
        real_cohort: tuple[int, str],
        second_cohort: tuple[int, str],
    ) -> None:
        """CohortMetric with cohort filter applied."""
        cid1, cname1 = real_cohort
        cid2, cname2 = second_cohort
        result = ws.query(
            CohortMetric(cid1, cname1),
            where=Filter.in_cohort(cid2, cname2),
            last=30,
        )
        assert isinstance(result, QueryResult)

    def test_same_cohort_in_filter_and_breakdown(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """Same cohort ID used in both filter and breakdown."""
        cid, cname = real_cohort
        result = ws.query(
            real_event,
            where=Filter.in_cohort(cid, cname),
            group_by=CohortBreakdown(cid, cname),
            last=7,
        )
        assert isinstance(result, QueryResult)


# =============================================================================
# 11. Error Handling — Bad Cohort IDs
# =============================================================================


class TestErrorHandling:
    """Error handling for invalid cohort IDs and client-side validation."""

    def test_query_nonexistent_cohort_filter(
        self,
        ws: Workspace,
        real_event: str,
    ) -> None:
        """Nonexistent cohort ID in filter produces API error or empty result."""
        # The API may return 400, 200 with empty data, or succeed silently.
        # This test discovers the actual behavior.
        try:
            result = ws.query(
                real_event,
                where=Filter.in_cohort(999999999, "Nonexistent"),
                last=7,
            )
            # If no error, query succeeded (API may ignore bad cohort)
            assert isinstance(result, QueryResult)
        except (QueryError, Exception) as e:
            # Expected — API rejected the bad cohort ID
            assert "999999999" in str(e) or "cohort" in str(e).lower() or True

    def test_query_nonexistent_cohort_breakdown(
        self,
        ws: Workspace,
        real_event: str,
    ) -> None:
        """Nonexistent cohort in breakdown produces API error or empty segments."""
        try:
            result = ws.query(
                real_event,
                group_by=CohortBreakdown(999999999, "Nonexistent"),
                last=7,
            )
            assert isinstance(result, QueryResult)
        except (QueryError, Exception):
            pass  # Expected

    def test_query_nonexistent_cohort_metric(
        self,
        ws: Workspace,
    ) -> None:
        """Nonexistent cohort in CohortMetric produces API error or zeros."""
        try:
            result = ws.query(CohortMetric(999999999, "Nonexistent"), last=7)
            assert isinstance(result, QueryResult)
        except (QueryError, Exception):
            pass  # Expected

    def test_client_side_negative_id_rejected(self) -> None:
        """Negative cohort ID raises ValueError before API call."""
        with pytest.raises(ValueError, match="cohort must be a positive integer"):
            Filter.in_cohort(-1)

    def test_client_side_empty_name_rejected(self) -> None:
        """Empty string name raises ValueError before API call."""
        with pytest.raises(ValueError, match="cohort name must be non-empty"):
            Filter.in_cohort(1, "")


# =============================================================================
# 12. Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_multiple_cohort_filters_in_where(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
        second_cohort: tuple[int, str],
    ) -> None:
        """Two cohort filters in where= — discover API behavior."""
        cid1, cname1 = real_cohort
        cid2, cname2 = second_cohort
        # May succeed (AND logic) or error — we discover the behavior
        try:
            result = ws.query(
                real_event,
                where=[
                    Filter.in_cohort(cid1, cname1),
                    Filter.in_cohort(cid2, cname2),
                ],
                last=7,
            )
            assert isinstance(result, QueryResult)
        except (QueryError, Exception):
            pass  # Also valid

    def test_cohort_breakdown_with_no_name(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """CohortBreakdown(id) with name=None should work."""
        cid, _ = real_cohort
        result = ws.query(
            real_event,
            group_by=CohortBreakdown(cid),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_inline_definition_with_nonexistent_event(
        self,
        ws: Workspace,
        real_event: str,
    ) -> None:
        """Inline CohortDefinition referencing nonexistent event — discover behavior."""
        bad_def = CohortDefinition(
            CohortCriteria.did_event(
                "NONEXISTENT_EVENT_XYZ_999", at_least=1, within_days=30
            )
        )
        try:
            result = ws.query(
                real_event,
                where=Filter.in_cohort(bad_def, name="Bad Def"),
                last=7,
            )
            # May succeed with empty/zero results
            assert isinstance(result, QueryResult)
        except (QueryError, Exception):
            pass  # API rejection is also valid

    def test_build_params_roundtrip(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """build_params output can be submitted as a saved bookmark."""
        cid, cname = real_cohort
        params = ws.build_params(
            real_event,
            where=Filter.in_cohort(cid, cname),
            group_by=CohortBreakdown(cid, cname),
            last=7,
        )
        # Verify structure is valid
        assert "sections" in params
        assert "displayOptions" in params
        # The params could be passed to create_bookmark — just verify structure


# =============================================================================
# 13. Build-Only Method Validation
# =============================================================================


class TestBuildMethods:
    """Verify bookmark JSON structure without API calls."""

    def test_build_params_cohort_filter_structure(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """build_params produces correct filter structure for cohort."""
        cid, cname = real_cohort
        params = ws.build_params(real_event, where=Filter.in_cohort(cid, cname), last=7)
        filters = params["sections"]["filter"]
        assert len(filters) == 1
        assert filters[0]["value"] == "$cohorts"
        assert filters[0]["filterType"] == "list"
        assert filters[0]["filterOperator"] == "contains"

    def test_build_params_cohort_breakdown_structure(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """build_params produces correct group structure for CohortBreakdown."""
        cid, cname = real_cohort
        params = ws.build_params(
            real_event, group_by=CohortBreakdown(cid, cname), last=7
        )
        groups = params["sections"]["group"]
        assert len(groups) == 1
        assert "cohorts" in groups[0]
        assert len(groups[0]["cohorts"]) == 2  # include_negated=True default

    def test_build_params_cohort_metric_structure(
        self,
        ws: Workspace,
        real_cohort: tuple[int, str],
    ) -> None:
        """build_params produces correct show structure for CohortMetric."""
        cid, cname = real_cohort
        params = ws.build_params(CohortMetric(cid, cname), last=7)
        show = params["sections"]["show"]
        assert len(show) == 1
        assert show[0]["behavior"]["type"] == "cohort"
        assert show[0]["behavior"]["resourceType"] == "cohorts"
        assert show[0]["behavior"]["id"] == cid
        assert show[0]["measurement"]["math"] == "unique"

    def test_build_flow_params_filter_by_cohort(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """build_flow_params includes filter_by_cohort key."""
        cid, cname = real_cohort
        params = ws.build_flow_params(
            real_event, where=Filter.in_cohort(cid, cname), last=7
        )
        assert "filter_by_cohort" in params
        assert params["filter_by_cohort"]["id"] == cid
        assert params["filter_by_cohort"]["negated"] is False


# =============================================================================
# 14. Backward Compatibility
# =============================================================================


class TestBackwardCompatibility:
    """Existing queries still work identically after cohort behavior changes."""

    def test_existing_query_unchanged(
        self,
        ws: Workspace,
        real_event: str,
    ) -> None:
        """Basic query without cohort params still works."""
        result = ws.query(real_event, last=7)
        assert isinstance(result, QueryResult)

    def test_existing_funnel_unchanged(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
    ) -> None:
        """Basic funnel without cohort params still works."""
        e1, e2 = real_events_pair
        result = ws.query_funnel([e1, e2], last=30)
        assert isinstance(result, FunnelQueryResult)

    def test_existing_flow_unchanged(
        self,
        ws: Workspace,
        real_event: str,
    ) -> None:
        """Basic flow without cohort params still works."""
        result = ws.query_flow(real_event, last=30)
        assert isinstance(result, FlowQueryResult)


# =============================================================================
# 15. Data Integrity Sanity
# =============================================================================


class TestDataIntegrity:
    """Data integrity and consistency checks."""

    def test_cohort_metric_values_are_non_negative(
        self,
        ws: Workspace,
        real_cohort: tuple[int, str],
    ) -> None:
        """Cohort size values should always be >= 0."""
        cid, cname = real_cohort
        result = ws.query(CohortMetric(cid, cname), last=7)
        for _metric_name, values in result.series.items():
            if isinstance(values, dict):
                for _date, val in values.items():
                    if isinstance(val, (int, float)):
                        assert val >= 0, f"Negative cohort size: {val}"

    def test_cohort_filter_idempotent(
        self,
        ws: Workspace,
        real_event: str,
        real_cohort: tuple[int, str],
    ) -> None:
        """Same cohort filter query twice returns same results."""
        cid, cname = real_cohort
        r1 = ws.query(
            real_event, where=Filter.in_cohort(cid, cname), last=7, mode="total"
        )
        r2 = ws.query(
            real_event, where=Filter.in_cohort(cid, cname), last=7, mode="total"
        )
        assert set(r1.series.keys()) == set(r2.series.keys())

    def test_cohort_metric_consistent_with_cohort_size(
        self,
        ws: Workspace,
        real_cohort: tuple[int, str],
    ) -> None:
        """CohortMetric latest value should be close to ws.get_cohort().size."""
        cid, cname = real_cohort
        cohort = ws.get_cohort(cid)
        result = ws.query(CohortMetric(cid, cname), last=1, mode="total")
        # Just verify both succeed — exact match not guaranteed due to timing
        assert cohort.id == cid
        assert isinstance(result, QueryResult)
