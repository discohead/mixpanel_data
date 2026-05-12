"""Unit tests for Workspace.query_user() aggregate mode (T017).

Tests cover aggregate query execution via _execute_user_aggregate()
which calls api_client.engage_stats(). Each test mocks engage_stats()
to return controlled aggregate responses.

Coverage:
- Count aggregate returns scalar value via result.value
- extremes/numeric_summary/percentile with aggregate_property
- Segmented aggregate returns DataFrame with segment/value columns
- aggregate_property required for non-count (U14)
- aggregate_property prohibited for count (U15)
- segment_by requires mode="aggregate" (U16)
- Profile-only params rejected in aggregate mode (U18-U22)
- engage_stats() called with correct action expression
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import BookmarkValidationError, Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.types import UserQueryResult

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

if TYPE_CHECKING:
    from collections.abc import Callable


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create mock API client for testing."""
    from mixpanel_headless._internal.api_client import MixpanelAPIClient

    client = MagicMock(spec=MixpanelAPIClient)
    client.close = MagicMock()
    return client


@pytest.fixture
def workspace_factory(
    mock_api_client: MagicMock,
) -> Callable[..., Workspace]:
    """Factory for creating Workspace instances with mocked dependencies."""

    def factory(**kwargs: Any) -> Workspace:
        """Create a Workspace with mocked config and API client.

        Args:
            **kwargs: Overrides for default Workspace constructor arguments.

        Returns:
            Workspace instance with mocked dependencies.
        """
        defaults: dict[str, Any] = {
            "session": _TEST_SESSION,
            "_api_client": mock_api_client,
        }
        defaults.update(kwargs)
        return Workspace(**defaults)

    return factory


# =============================================================================
# Helpers
# =============================================================================


def _make_stats_response(
    results: int | float | dict[str, Any],
    *,
    computed_at: str = "2025-01-15T10:00:00",
    status: str = "ok",
) -> dict[str, Any]:
    """Build a mock engage_stats() response dict.

    Args:
        results: Aggregate result — scalar for unsegmented, dict for
            segmented.
        computed_at: ISO timestamp for when the query was computed.
        status: API response status.

    Returns:
        Dict matching the engage_stats() response format.
    """
    return {
        "results": results,
        "status": status,
        "computed_at": computed_at,
    }


# =============================================================================
# Test: Count aggregate returns scalar value via result.value
# =============================================================================


class TestAggregateCount:
    """Tests for aggregate mode with count aggregation."""

    def test_count_returns_scalar_value(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Count aggregate returns an integer via result.value."""
        mock_api_client.engage_stats.return_value = _make_stats_response(42)

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="aggregate", aggregate="count")

            assert isinstance(result, UserQueryResult)
            assert result.mode == "aggregate"
            assert result.value == 42
        finally:
            ws.close()

    def test_count_result_has_empty_profiles(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Aggregate mode returns an empty profiles list."""
        mock_api_client.engage_stats.return_value = _make_stats_response(100)

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="aggregate", aggregate="count")

            assert result.profiles == []
        finally:
            ws.close()

    def test_count_aggregate_data_is_scalar(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """aggregate_data stores the raw scalar for unsegmented count."""
        mock_api_client.engage_stats.return_value = _make_stats_response(256)

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="aggregate", aggregate="count")

            assert result.aggregate_data == 256
        finally:
            ws.close()

    def test_count_calls_engage_stats_with_count_action(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Count aggregate calls engage_stats with action='count()'."""
        mock_api_client.engage_stats.return_value = _make_stats_response(10)

        ws = workspace_factory()
        try:
            ws.query_user(mode="aggregate", aggregate="count")

            mock_api_client.engage_stats.assert_called_once()
            call_kwargs = mock_api_client.engage_stats.call_args.kwargs
            assert call_kwargs.get("action") == "count()"
        finally:
            ws.close()

    def test_count_with_where_filter_passes_selector(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Count with a where filter passes the selector to engage_stats."""
        mock_api_client.engage_stats.return_value = _make_stats_response(5)

        ws = workspace_factory()
        try:
            ws.query_user(
                mode="aggregate",
                aggregate="count",
                where='properties["plan"] == "premium"',
            )

            mock_api_client.engage_stats.assert_called_once()
        finally:
            ws.close()

    def test_count_result_has_computed_at(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Aggregate result includes a computed_at timestamp."""
        mock_api_client.engage_stats.return_value = _make_stats_response(
            42, computed_at="2025-06-01T12:00:00"
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="aggregate", aggregate="count")

            assert isinstance(result.computed_at, str)
            assert len(result.computed_at) > 0
        finally:
            ws.close()


# =============================================================================
# Test: extremes/numeric_summary/percentile with aggregate_property
# =============================================================================


class TestAggregateWithProperty:
    """Tests for aggregate mode with property-based aggregations."""

    def test_extremes_with_aggregate_property(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Extremes aggregation returns dict with max/min and uses correct action."""
        extremes_result: dict[str, Any] = {
            "max": 99999.99,
            "min": 10.0,
            "nth_percentile": 500.0,
        }
        mock_api_client.engage_stats.return_value = _make_stats_response(
            extremes_result
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="aggregate",
                aggregate="extremes",
                aggregate_property="revenue",
            )

            assert isinstance(result.aggregate_data, dict)
            assert result.aggregate_data == extremes_result
            assert result.value is None  # dict results have no scalar value
            call_kwargs = mock_api_client.engage_stats.call_args.kwargs
            assert call_kwargs.get("action") == 'extremes(properties["revenue"])'
        finally:
            ws.close()

    def test_numeric_summary_with_aggregate_property(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Numeric summary returns dict with count/mean/var/sum_of_squares."""
        summary_result: dict[str, Any] = {
            "count": 150,
            "mean": 42.7,
            "var": 123.4,
            "sum_of_squares": 18510.0,
        }
        mock_api_client.engage_stats.return_value = _make_stats_response(summary_result)

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="aggregate",
                aggregate="numeric_summary",
                aggregate_property="ltv",
            )

            assert isinstance(result.aggregate_data, dict)
            assert result.aggregate_data == summary_result
            assert result.value is None  # dict results have no scalar value
            call_kwargs = mock_api_client.engage_stats.call_args.kwargs
            assert call_kwargs.get("action") == 'numeric_summary(properties["ltv"])'
        finally:
            ws.close()

    def test_percentile_with_aggregate_property(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Percentile aggregation returns dict with percentile and result."""
        percentile_result: dict[str, Any] = {
            "percentile": 50,
            "result": 35.0,
        }
        mock_api_client.engage_stats.return_value = _make_stats_response(
            percentile_result
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="aggregate",
                aggregate="percentile",
                aggregate_property="age",
                percentile=50,
            )

            assert isinstance(result.aggregate_data, dict)
            assert result.aggregate_data == percentile_result
            assert result.value is None  # dict results have no scalar value
            call_kwargs = mock_api_client.engage_stats.call_args.kwargs
            assert call_kwargs.get("action") == 'percentile(properties["age"], 50)'
        finally:
            ws.close()

    def test_percentile_with_fractional_value(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Percentile with a fractional value passes correct action string."""
        percentile_result: dict[str, Any] = {
            "percentile": 99.5,
            "result": 980.0,
        }
        mock_api_client.engage_stats.return_value = _make_stats_response(
            percentile_result
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="aggregate",
                aggregate="percentile",
                aggregate_property="score",
                percentile=99.5,
            )

            assert isinstance(result.aggregate_data, dict)
            call_kwargs = mock_api_client.engage_stats.call_args.kwargs
            assert call_kwargs.get("action") == 'percentile(properties["score"], 99.5)'
        finally:
            ws.close()

    def test_aggregate_with_property_mode_is_aggregate(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Property-based aggregation sets mode='aggregate' on result."""
        extremes_result: dict[str, Any] = {"max": 500.0, "min": 1.0}
        mock_api_client.engage_stats.return_value = _make_stats_response(
            extremes_result
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="aggregate",
                aggregate="extremes",
                aggregate_property="revenue",
            )

            assert result.mode == "aggregate"
        finally:
            ws.close()

    def test_aggregate_with_property_has_params(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Aggregate result includes the params dict used for the API call."""
        summary_result: dict[str, Any] = {
            "count": 50,
            "mean": 100.0,
            "var": 25.0,
            "sum_of_squares": 5000.0,
        }
        mock_api_client.engage_stats.return_value = _make_stats_response(summary_result)

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="aggregate",
                aggregate="numeric_summary",
                aggregate_property="score",
            )

            assert isinstance(result.params, dict)
            assert result.params.get("action") == 'numeric_summary(properties["score"])'
        finally:
            ws.close()


# =============================================================================
# Test: Segmented aggregate returns DataFrame with segment/value columns
# =============================================================================


class TestAggregateSegmented:
    """Tests for segmented aggregate mode with segment_by cohort IDs."""

    def test_segmented_aggregate_returns_dict_data(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Segmented aggregate stores a dict in aggregate_data."""
        segmented_results: dict[str, Any] = {
            "123": 145.0,
            "456": 320.5,
        }
        mock_api_client.engage_stats.return_value = _make_stats_response(
            segmented_results
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="aggregate",
                aggregate="count",
                segment_by=[123, 456],
            )

            assert isinstance(result.aggregate_data, dict)
            assert result.aggregate_data == segmented_results
        finally:
            ws.close()

    def test_segmented_aggregate_value_is_none(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Segmented aggregate result.value returns None (not a scalar)."""
        segmented_results: dict[str, Any] = {
            "123": 145.0,
            "456": 320.5,
        }
        mock_api_client.engage_stats.return_value = _make_stats_response(
            segmented_results
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="aggregate",
                aggregate="count",
                segment_by=[123, 456],
            )

            assert result.value is None
        finally:
            ws.close()

    def test_segmented_aggregate_df_has_segment_and_value_columns(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Segmented aggregate DataFrame has 'segment' and 'value' columns."""
        segmented_results: dict[str, Any] = {
            "cohort_123": 145.0,
            "cohort_456": 320.5,
        }
        mock_api_client.engage_stats.return_value = _make_stats_response(
            segmented_results
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="aggregate",
                aggregate="count",
                segment_by=[123, 456],
            )

            df = result.df
            assert "segment" in df.columns
            assert "value" in df.columns
        finally:
            ws.close()

    def test_segmented_aggregate_df_row_count(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Segmented aggregate DataFrame has one row per segment."""
        segmented_results: dict[str, Any] = {
            "100": 10,
            "200": 20,
            "300": 30,
        }
        mock_api_client.engage_stats.return_value = _make_stats_response(
            segmented_results
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="aggregate",
                aggregate="count",
                segment_by=[100, 200, 300],
            )

            assert len(result.df) == 3
        finally:
            ws.close()

    def test_segmented_aggregate_passes_segment_by_cohorts(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """segment_by cohort IDs are serialized and passed to engage_stats."""
        mock_api_client.engage_stats.return_value = _make_stats_response(
            {"123": 10, "456": 20}
        )

        ws = workspace_factory()
        try:
            ws.query_user(
                mode="aggregate",
                aggregate="count",
                segment_by=[123, 456],
            )

            mock_api_client.engage_stats.assert_called_once()
        finally:
            ws.close()

    def test_segmented_aggregate_profiles_is_empty(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Segmented aggregate returns empty profiles list."""
        mock_api_client.engage_stats.return_value = _make_stats_response({"123": 10})

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="aggregate",
                aggregate="extremes",
                aggregate_property="revenue",
                segment_by=[123],
            )

            assert result.profiles == []
        finally:
            ws.close()


# =============================================================================
# Test: aggregate_property required for non-count (U14)
# =============================================================================


class TestValidationU14AggregatePropertyRequired:
    """Tests for U14: aggregate_property required for non-count aggregation."""

    @pytest.mark.parametrize(
        "agg_func",
        ["extremes", "percentile", "numeric_summary"],
        ids=["extremes", "percentile", "numeric_summary"],
    )
    def test_non_count_without_property_raises_u14(
        self,
        workspace_factory: Callable[..., Workspace],
        agg_func: str,
    ) -> None:
        """Non-count aggregate without aggregate_property raises U14."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="aggregate",
                    aggregate=agg_func,  # type: ignore[arg-type]
                )

            errors = exc_info.value.errors
            codes = [e.code for e in errors]
            assert "U14" in codes
        finally:
            ws.close()

    def test_u14_error_message_mentions_aggregate_property(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """U14 error message mentions aggregate_property."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="aggregate",
                    aggregate="extremes",
                )

            u14_errors = [e for e in exc_info.value.errors if e.code == "U14"]
            assert len(u14_errors) == 1
            assert "aggregate_property" in u14_errors[0].message
        finally:
            ws.close()


# =============================================================================
# Test: aggregate_property prohibited for count (U15)
# =============================================================================


class TestValidationU15AggregatePropertyProhibited:
    """Tests for U15: aggregate_property must not be set for count."""

    def test_count_with_property_raises_u15(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Count aggregate with aggregate_property raises U15."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="aggregate",
                    aggregate="count",
                    aggregate_property="revenue",
                )

            errors = exc_info.value.errors
            codes = [e.code for e in errors]
            assert "U15" in codes
        finally:
            ws.close()

    def test_u15_error_message_mentions_count(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """U15 error message explains that count does not take a property."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="aggregate",
                    aggregate="count",
                    aggregate_property="ltv",
                )

            u15_errors = [e for e in exc_info.value.errors if e.code == "U15"]
            assert len(u15_errors) == 1
            assert "count" in u15_errors[0].message.lower()
        finally:
            ws.close()


# =============================================================================
# Test: segment_by requires mode="aggregate" (U16)
# =============================================================================


class TestValidationU16SegmentByRequiresAggregate:
    """Tests for U16: segment_by requires mode='aggregate'."""

    def test_segment_by_in_profiles_mode_raises_u16(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """segment_by with mode='profiles' raises U16."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="profiles",
                    segment_by=[123],
                )

            errors = exc_info.value.errors
            codes = [e.code for e in errors]
            assert "U16" in codes
        finally:
            ws.close()

    def test_segment_by_in_aggregate_mode_no_u16(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """segment_by with mode='aggregate' does not raise U16."""
        mock_api_client.engage_stats.return_value = _make_stats_response({"123": 10})

        ws = workspace_factory()
        try:
            # Should not raise
            result = ws.query_user(
                mode="aggregate",
                aggregate="count",
                segment_by=[123],
            )
            assert isinstance(result, UserQueryResult)
        finally:
            ws.close()


# =============================================================================
# Test: Profile-only params rejected in aggregate mode (U18-U22)
# =============================================================================


class TestValidationU18ParallelProfilesOnly:
    """Tests for U18: parallel only applies to mode='profiles'."""

    def test_parallel_in_aggregate_mode_raises_u18(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """parallel=True with mode='aggregate' raises U18."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="aggregate",
                    aggregate="count",
                    parallel=True,
                )

            errors = exc_info.value.errors
            codes = [e.code for e in errors]
            assert "U18" in codes
        finally:
            ws.close()


class TestValidationU19SortByProfilesOnly:
    """Tests for U19: sort_by only applies to mode='profiles'."""

    def test_sort_by_in_aggregate_mode_raises_u19(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """sort_by with mode='aggregate' raises U19."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="aggregate",
                    aggregate="count",
                    sort_by="$last_seen",
                )

            errors = exc_info.value.errors
            codes = [e.code for e in errors]
            assert "U19" in codes
        finally:
            ws.close()


class TestValidationU20SearchProfilesOnly:
    """Tests for U20: search only applies to mode='profiles'."""

    def test_search_in_aggregate_mode_raises_u20(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """search with mode='aggregate' raises U20."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="aggregate",
                    aggregate="count",
                    search="alice",
                )

            errors = exc_info.value.errors
            codes = [e.code for e in errors]
            assert "U20" in codes
        finally:
            ws.close()


class TestValidationU21DistinctIdProfilesOnly:
    """Tests for U21: distinct_id/distinct_ids only apply to mode='profiles'."""

    def test_distinct_id_in_aggregate_mode_raises_u21(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """distinct_id with mode='aggregate' raises U21."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="aggregate",
                    aggregate="count",
                    distinct_id="user_001",
                )

            errors = exc_info.value.errors
            codes = [e.code for e in errors]
            assert "U21" in codes
        finally:
            ws.close()

    def test_distinct_ids_in_aggregate_mode_raises_u21(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """distinct_ids with mode='aggregate' raises U21."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="aggregate",
                    aggregate="count",
                    distinct_ids=["user_001", "user_002"],
                )

            errors = exc_info.value.errors
            codes = [e.code for e in errors]
            assert "U21" in codes
        finally:
            ws.close()


class TestValidationU22PropertiesProfilesOnly:
    """Tests for U22: properties only applies to mode='profiles'."""

    def test_properties_in_aggregate_mode_raises_u22(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """properties with mode='aggregate' raises U22."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="aggregate",
                    aggregate="count",
                    properties=["$email", "plan"],
                )

            errors = exc_info.value.errors
            codes = [e.code for e in errors]
            assert "U22" in codes
        finally:
            ws.close()


# =============================================================================
# Test: Multiple validation errors reported together
# =============================================================================


class TestValidationMultipleErrors:
    """Tests that multiple validation violations are reported in one error."""

    def test_multiple_profile_params_in_aggregate_mode(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Multiple profile-only params in aggregate mode produce multiple errors."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="aggregate",
                    aggregate="count",
                    sort_by="$last_seen",
                    search="alice",
                    properties=["$email"],
                )

            errors = exc_info.value.errors
            codes = {e.code for e in errors}
            # Should report U19 (sort_by), U20 (search), U22 (properties)
            assert "U19" in codes
            assert "U20" in codes
            assert "U22" in codes
        finally:
            ws.close()

    def test_missing_property_and_invalid_profile_params(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Missing aggregate_property and profile-only params are all reported."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="aggregate",
                    aggregate="extremes",
                    # Missing aggregate_property (U14)
                    search="bob",  # U20
                )

            errors = exc_info.value.errors
            codes = {e.code for e in errors}
            assert "U14" in codes
            assert "U20" in codes
        finally:
            ws.close()


# =============================================================================
# Test: engage_stats() called with correct parameters
# =============================================================================


class TestEngageStatsCallParameters:
    """Tests verifying engage_stats() receives correct parameters."""

    def test_count_action_expression(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Count aggregate passes action='count()' to engage_stats."""
        mock_api_client.engage_stats.return_value = _make_stats_response(10)

        ws = workspace_factory()
        try:
            ws.query_user(mode="aggregate", aggregate="count")

            call_kwargs = mock_api_client.engage_stats.call_args.kwargs
            assert call_kwargs["action"] == "count()"
        finally:
            ws.close()

    def test_extremes_action_expression(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Extremes aggregate passes correct action to engage_stats."""
        extremes_result: dict[str, Any] = {"max": 500.0, "min": 1.0}
        mock_api_client.engage_stats.return_value = _make_stats_response(
            extremes_result
        )

        ws = workspace_factory()
        try:
            ws.query_user(
                mode="aggregate",
                aggregate="extremes",
                aggregate_property="revenue",
            )

            call_kwargs = mock_api_client.engage_stats.call_args.kwargs
            assert call_kwargs["action"] == 'extremes(properties["revenue"])'
        finally:
            ws.close()

    def test_numeric_summary_action_expression(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Numeric summary passes correct action to engage_stats."""
        summary_result: dict[str, Any] = {"count": 10, "mean": 25.0}
        mock_api_client.engage_stats.return_value = _make_stats_response(summary_result)

        ws = workspace_factory()
        try:
            ws.query_user(
                mode="aggregate",
                aggregate="numeric_summary",
                aggregate_property="score",
            )

            call_kwargs = mock_api_client.engage_stats.call_args.kwargs
            assert call_kwargs["action"] == 'numeric_summary(properties["score"])'
        finally:
            ws.close()

    def test_percentile_action_expression(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Percentile aggregate passes correct action to engage_stats."""
        percentile_result: dict[str, Any] = {"percentile": 90, "result": 150.0}
        mock_api_client.engage_stats.return_value = _make_stats_response(
            percentile_result
        )

        ws = workspace_factory()
        try:
            ws.query_user(
                mode="aggregate",
                aggregate="percentile",
                aggregate_property="age",
                percentile=90,
            )

            call_kwargs = mock_api_client.engage_stats.call_args.kwargs
            assert call_kwargs["action"] == 'percentile(properties["age"], 90)'
        finally:
            ws.close()

    def test_percentile_action_with_decimal(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Percentile with decimal value passes correct action to engage_stats."""
        percentile_result: dict[str, Any] = {"percentile": 95.5, "result": 200.0}
        mock_api_client.engage_stats.return_value = _make_stats_response(
            percentile_result
        )

        ws = workspace_factory()
        try:
            ws.query_user(
                mode="aggregate",
                aggregate="percentile",
                aggregate_property="ltv",
                percentile=95.5,
            )

            call_kwargs = mock_api_client.engage_stats.call_args.kwargs
            assert call_kwargs["action"] == 'percentile(properties["ltv"], 95.5)'
        finally:
            ws.close()

    def test_group_id_forwarded_to_engage_stats(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """group_id is forwarded to engage_stats for group analytics."""
        mock_api_client.engage_stats.return_value = _make_stats_response(50)

        ws = workspace_factory()
        try:
            ws.query_user(
                mode="aggregate",
                aggregate="count",
                group_id="companies",
            )

            call_kwargs = mock_api_client.engage_stats.call_args.kwargs
            assert call_kwargs.get("group_id") == "companies"
        finally:
            ws.close()

    def test_as_of_rejected_in_aggregate_mode(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """as_of in aggregate mode is rejected by validation (U30).

        The ``/engage/stats`` endpoint does not support ``as_of_timestamp``,
        so validation catches this before the API call is made.

        Args:
            workspace_factory: Factory for Workspace instances.
            mock_api_client: Mocked API client.
        """
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="aggregate",
                    aggregate="count",
                    as_of=1704067200,
                )
            assert any(e.code == "U30" for e in exc_info.value.errors), (
                "Expected U30 validation error"
            )
            # engage_stats should never be called
            mock_api_client.engage_stats.assert_not_called()
        finally:
            ws.close()

    def test_include_all_users_forwarded_to_engage_stats(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """include_all_users is forwarded to engage_stats when cohort is set."""
        mock_api_client.engage_stats.return_value = _make_stats_response(100)

        ws = workspace_factory()
        try:
            ws.query_user(
                mode="aggregate",
                aggregate="count",
                cohort=42,
                include_all_users=True,
            )

            call_kwargs = mock_api_client.engage_stats.call_args.kwargs
            assert call_kwargs.get("include_all_users") is True
        finally:
            ws.close()


# =============================================================================
# Test: Aggregate result metadata and structure
# =============================================================================


class TestAggregateResultMetadata:
    """Tests for aggregate UserQueryResult structure and metadata."""

    def test_result_is_user_query_result(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Aggregate query returns a UserQueryResult instance."""
        mock_api_client.engage_stats.return_value = _make_stats_response(42)

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="aggregate", aggregate="count")

            assert isinstance(result, UserQueryResult)
        finally:
            ws.close()

    def test_result_has_meta_dict(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Aggregate result includes a meta dict with execution metadata."""
        mock_api_client.engage_stats.return_value = _make_stats_response(42)

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="aggregate", aggregate="count")

            assert isinstance(result.meta, dict)
        finally:
            ws.close()

    def test_result_distinct_ids_empty_for_aggregate(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Aggregate result has empty distinct_ids list."""
        mock_api_client.engage_stats.return_value = _make_stats_response(42)

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="aggregate", aggregate="count")

            assert result.distinct_ids == []
        finally:
            ws.close()

    def test_result_total_for_count_aggregate(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Count aggregate total reflects the count result."""
        mock_api_client.engage_stats.return_value = _make_stats_response(1500)

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="aggregate", aggregate="count")

            # For count aggregates, total should reflect the count
            assert result.total == 1500
        finally:
            ws.close()

    def test_unsegmented_aggregate_df_single_row(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Unsegmented aggregate DataFrame has a single row with the value."""
        mock_api_client.engage_stats.return_value = _make_stats_response(42)

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="aggregate", aggregate="count")

            df = result.df
            assert len(df) == 1
            assert "value" in df.columns
        finally:
            ws.close()


# =============================================================================
# Test: Credentials check in aggregate mode
# =============================================================================


# TestAggregateConfigError removed in B1 (Fix 10): Workspace.__init__
# now always populates ``_credentials`` via the v3 session shim, so the
# "no credentials" path is unreachable.
