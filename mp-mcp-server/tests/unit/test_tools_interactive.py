"""Tests for interactive analytics tools.

These tests verify the guided_analysis and safe_large_fetch
tools work correctly with elicitation handling.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestGuidedAnalysisHelpers:
    """Tests for guided_analysis helper functions."""

    def test_get_date_range_last_7_days(self) -> None:
        """_get_date_range_from_period should handle last_7_days."""
        from mp_mcp_server.tools.interactive.guided import _get_date_range_from_period

        from_date, to_date = _get_date_range_from_period("last_7_days")
        assert from_date < to_date

    def test_get_date_range_last_30_days(self) -> None:
        """_get_date_range_from_period should handle last_30_days."""
        from mp_mcp_server.tools.interactive.guided import _get_date_range_from_period

        from_date, to_date = _get_date_range_from_period("last_30_days")
        assert from_date < to_date

    def test_get_date_range_last_90_days(self) -> None:
        """_get_date_range_from_period should handle last_90_days."""
        from mp_mcp_server.tools.interactive.guided import _get_date_range_from_period

        from_date, to_date = _get_date_range_from_period("last_90_days")
        assert from_date < to_date

    def test_get_date_range_custom(self) -> None:
        """_get_date_range_from_period should handle custom dates."""
        from mp_mcp_server.tools.interactive.guided import _get_date_range_from_period

        from_date, to_date = _get_date_range_from_period(
            "custom",
            custom_start="2024-01-01",
            custom_end="2024-01-31",
        )
        assert from_date == "2024-01-01"
        assert to_date == "2024-01-31"

    def test_get_date_range_custom_without_dates(self) -> None:
        """_get_date_range_from_period should default when custom missing dates."""
        from mp_mcp_server.tools.interactive.guided import _get_date_range_from_period

        from_date, to_date = _get_date_range_from_period("custom")
        assert from_date < to_date  # Falls back to 30 days

    def test_run_initial_analysis(self, mock_context: MagicMock) -> None:
        """run_initial_analysis should run focus-specific queries."""
        from mp_mcp_server.tools.interactive.guided import run_initial_analysis

        result = run_initial_analysis(
            mock_context,
            focus_area="conversion",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert "focus_area" in result
        assert "period" in result
        assert result["focus_area"] == "conversion"

    def test_run_initial_analysis_retention(self, mock_context: MagicMock) -> None:
        """run_initial_analysis should handle retention focus."""
        from mp_mcp_server.tools.interactive.guided import run_initial_analysis

        result = run_initial_analysis(
            mock_context,
            focus_area="retention",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["focus_area"] == "retention"

    def test_run_initial_analysis_engagement(self, mock_context: MagicMock) -> None:
        """run_initial_analysis should handle engagement focus."""
        from mp_mcp_server.tools.interactive.guided import run_initial_analysis

        result = run_initial_analysis(
            mock_context,
            focus_area="engagement",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["focus_area"] == "engagement"

    def test_run_initial_analysis_revenue(self, mock_context: MagicMock) -> None:
        """run_initial_analysis should handle revenue focus."""
        from mp_mcp_server.tools.interactive.guided import run_initial_analysis

        result = run_initial_analysis(
            mock_context,
            focus_area="revenue",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["focus_area"] == "revenue"


class TestGuidedAnalysisTool:
    """Tests for the guided_analysis tool."""

    def test_tool_registered(self) -> None:
        """guided_analysis tool should be registered."""
        from mp_mcp_server.server import mcp

        tool_names = list(mcp._tool_manager._tools.keys())
        assert "guided_analysis" in tool_names

    @pytest.mark.asyncio
    async def test_guided_analysis_with_preset_focus(
        self, mock_context: MagicMock
    ) -> None:
        """guided_analysis should work with pre-selected focus area."""
        from mp_mcp_server.tools.interactive.guided import guided_analysis

        result = await guided_analysis.fn(
            mock_context,
            focus_area="retention",
        )

        assert "status" in result
        assert result["focus_area"] == "retention"

    @pytest.mark.asyncio
    async def test_guided_analysis_elicitation_unavailable(
        self, mock_context: MagicMock
    ) -> None:
        """guided_analysis should degrade when elicitation unavailable."""
        from mp_mcp_server.tools.interactive.guided import guided_analysis

        mock_context.elicit = AsyncMock(
            side_effect=Exception("Elicitation not supported")
        )

        result = await guided_analysis.fn(mock_context)

        assert "status" in result
        # When elicitation fails and no focus_area provided, returns guidance message
        assert result["status"] == "elicitation_unavailable"
        assert "focus_options" in result
        assert "message" in result

    @pytest.mark.asyncio
    async def test_guided_analysis_with_custom_dates(
        self, mock_context: MagicMock
    ) -> None:
        """guided_analysis should accept custom date range."""
        from mp_mcp_server.tools.interactive.guided import guided_analysis

        result = await guided_analysis.fn(
            mock_context,
            focus_area="engagement",
            time_period="custom",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["period"]["from_date"] == "2024-01-01"
        assert result["period"]["to_date"] == "2024-01-31"


class TestSafeFetchHelpers:
    """Tests for safe_large_fetch helper functions."""

    def test_get_default_date_range(self) -> None:
        """_get_default_date_range should return valid dates."""
        from mp_mcp_server.tools.interactive.safe_fetch import _get_default_date_range

        from_date, to_date = _get_default_date_range()
        assert from_date < to_date

    def test_estimate_event_count(self, mock_context: MagicMock) -> None:
        """estimate_event_count should estimate based on top_events."""
        from mp_mcp_server.tools.interactive.safe_fetch import estimate_event_count

        result = estimate_event_count(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert "estimated_count" in result
        assert "days_in_range" in result
        assert "confidence" in result

    def test_estimate_event_count_with_events_filter(
        self, mock_context: MagicMock
    ) -> None:
        """estimate_event_count should filter by event names."""
        from mp_mcp_server.tools.interactive.safe_fetch import estimate_event_count

        result = estimate_event_count(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=["login"],
        )

        assert "estimated_count" in result


class TestSafeLargeFetchTool:
    """Tests for the safe_large_fetch tool."""

    def test_tool_registered(self) -> None:
        """safe_large_fetch tool should be registered."""
        from mp_mcp_server.server import mcp

        tool_names = list(mcp._tool_manager._tools.keys())
        assert "safe_large_fetch" in tool_names

    @pytest.mark.asyncio
    async def test_safe_fetch_small_dataset(self, mock_context: MagicMock) -> None:
        """safe_large_fetch should proceed for small datasets."""
        from mp_mcp_server.tools.interactive.safe_fetch import safe_large_fetch

        # Mock top_events to return small counts
        mock_context.fastmcp._lifespan_result["workspace"].top_events.return_value = [
            MagicMock(to_dict=lambda: {"event": "login", "count": 100}),
        ]

        result = await safe_large_fetch.fn(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",  # Short range
        )

        assert "status" in result

    @pytest.mark.asyncio
    async def test_safe_fetch_elicitation_unavailable(
        self, mock_context: MagicMock
    ) -> None:
        """safe_large_fetch should proceed with warning when elicitation unavailable."""
        from mp_mcp_server.tools.interactive.safe_fetch import safe_large_fetch

        mock_context.elicit = AsyncMock(
            side_effect=Exception("Elicitation not supported")
        )

        # Mock to simulate large dataset
        mock_context.fastmcp._lifespan_result["workspace"].top_events.return_value = [
            MagicMock(to_dict=lambda: {"event": "login", "count": 10000000}),
        ]

        result = await safe_large_fetch.fn(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-12-31",  # Long range
        )

        assert "status" in result

    @pytest.mark.asyncio
    async def test_safe_fetch_with_specific_events(
        self, mock_context: MagicMock
    ) -> None:
        """safe_large_fetch should accept event filter."""
        from mp_mcp_server.tools.interactive.safe_fetch import safe_large_fetch

        result = await safe_large_fetch.fn(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=["login", "signup"],
        )

        assert "status" in result

    @pytest.mark.asyncio
    async def test_safe_fetch_with_table_name(self, mock_context: MagicMock) -> None:
        """safe_large_fetch should accept custom table name."""
        from mp_mcp_server.tools.interactive.safe_fetch import safe_large_fetch

        result = await safe_large_fetch.fn(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
            table="my_events",
        )

        assert "status" in result


class TestFocusDescriptions:
    """Tests for focus area descriptions constant."""

    def test_focus_descriptions_contains_all_areas(self) -> None:
        """FOCUS_DESCRIPTIONS should have all focus areas."""
        from mp_mcp_server.tools.interactive.guided import FOCUS_DESCRIPTIONS

        expected_areas = {"conversion", "retention", "engagement", "revenue"}
        assert set(FOCUS_DESCRIPTIONS.keys()) == expected_areas

    def test_focus_descriptions_values_are_strings(self) -> None:
        """FOCUS_DESCRIPTIONS values should be descriptive strings."""
        from mp_mcp_server.tools.interactive.guided import FOCUS_DESCRIPTIONS

        for _area, desc in FOCUS_DESCRIPTIONS.items():
            assert isinstance(desc, str)
            assert len(desc) > 10  # Should be descriptive


class TestAnalysisChoice:
    """Tests for AnalysisChoice dataclass."""

    def test_analysis_choice_defaults(self) -> None:
        """AnalysisChoice should have sensible defaults."""
        from mp_mcp_server.tools.interactive.guided import AnalysisChoice

        choice = AnalysisChoice(focus_area="retention")
        assert choice.focus_area == "retention"
        assert choice.time_period == "last_30_days"
        assert choice.custom_start is None
        assert choice.custom_end is None

    def test_analysis_choice_custom_period(self) -> None:
        """AnalysisChoice should accept custom period."""
        from mp_mcp_server.tools.interactive.guided import AnalysisChoice

        choice = AnalysisChoice(
            focus_area="conversion",
            time_period="custom",
            custom_start="2024-01-01",
            custom_end="2024-01-31",
        )
        assert choice.time_period == "custom"
        assert choice.custom_start == "2024-01-01"


class TestSegmentChoice:
    """Tests for SegmentChoice dataclass."""

    def test_segment_choice_defaults(self) -> None:
        """SegmentChoice should have sensible defaults."""
        from mp_mcp_server.tools.interactive.guided import SegmentChoice

        choice = SegmentChoice(segment_index=0)
        assert choice.segment_index == 0
        assert choice.investigate_further is True

    def test_segment_choice_no_further(self) -> None:
        """SegmentChoice should allow declining further investigation."""
        from mp_mcp_server.tools.interactive.guided import SegmentChoice

        choice = SegmentChoice(segment_index=1, investigate_further=False)
        assert choice.investigate_further is False


class TestFetchConfirmation:
    """Tests for FetchConfirmation dataclass."""

    def test_fetch_confirmation_defaults(self) -> None:
        """FetchConfirmation should have sensible defaults."""
        from mp_mcp_server.tools.interactive.safe_fetch import FetchConfirmation

        confirm = FetchConfirmation(proceed=True)
        assert confirm.proceed is True
        assert confirm.reduce_scope is False
        assert confirm.new_limit is None

    def test_fetch_confirmation_reduce_scope(self) -> None:
        """FetchConfirmation should allow scope reduction."""
        from mp_mcp_server.tools.interactive.safe_fetch import FetchConfirmation

        confirm = FetchConfirmation(
            proceed=True,
            reduce_scope=True,
            new_limit=10000,
        )
        assert confirm.reduce_scope is True
        assert confirm.new_limit == 10000


class TestEstimateEventCountEdgeCases:
    """Tests for estimate_event_count edge cases."""

    def test_estimate_event_count_handles_exception(
        self, mock_context: MagicMock
    ) -> None:
        """estimate_event_count should handle API exceptions."""
        from mp_mcp_server.tools.interactive.safe_fetch import estimate_event_count

        mock_context.fastmcp._lifespan_result["workspace"].top_events.side_effect = (
            Exception("API error")
        )

        result = estimate_event_count(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        # Should fall back to default estimate
        assert result["confidence"] == "low"
        assert "error" in result

    def test_estimate_event_count_with_dict_response(
        self, mock_context: MagicMock
    ) -> None:
        """estimate_event_count should handle dict response format."""
        from mp_mcp_server.tools.interactive.safe_fetch import estimate_event_count

        # Mock top_events to return dict with data key
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"data": {"login": 5000, "signup": 1000}}
        mock_context.fastmcp._lifespan_result["workspace"].top_events.return_value = (
            mock_result
        )

        result = estimate_event_count(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert "estimated_count" in result
        assert result["days_in_range"] == 31

    def test_estimate_event_count_with_events_key_format(
        self, mock_context: MagicMock
    ) -> None:
        """estimate_event_count should handle events key format."""
        from mp_mcp_server.tools.interactive.safe_fetch import estimate_event_count

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "events": [{"name": "login", "count": 5000}, {"name": "signup", "count": 1000}]
        }
        mock_context.fastmcp._lifespan_result["workspace"].top_events.return_value = (
            mock_result
        )

        result = estimate_event_count(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert "estimated_count" in result

    def test_estimate_event_count_high_confidence(
        self, mock_context: MagicMock
    ) -> None:
        """estimate_event_count should have high confidence with many events."""
        from mp_mcp_server.tools.interactive.safe_fetch import estimate_event_count

        # Mock many events as dicts (code checks isinstance(event, dict))
        events_list = [{"event": f"event_{i}", "count": 1000} for i in range(15)]
        mock_context.fastmcp._lifespan_result["workspace"].top_events.return_value = (
            events_list
        )

        result = estimate_event_count(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["confidence"] == "high"
        assert result["events_analyzed"] >= 10


class TestSafeFetchElicitation:
    """Tests for safe_large_fetch elicitation flows."""

    @pytest.mark.asyncio
    async def test_safe_fetch_declined(self, mock_context: MagicMock) -> None:
        """safe_large_fetch should handle declined elicitation."""
        from fastmcp.server.elicitation import DeclinedElicitation

        from mp_mcp_server.tools.interactive.safe_fetch import safe_large_fetch

        mock_context.elicit = AsyncMock(return_value=DeclinedElicitation())

        # Mock large dataset to trigger elicitation
        mock_context.fastmcp._lifespan_result["workspace"].top_events.return_value = [
            MagicMock(to_dict=lambda: {"event": "login", "count": 10000000}),
        ]

        result = await safe_large_fetch.fn(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-12-31",
        )

        assert result["status"] == "declined"

    @pytest.mark.asyncio
    async def test_safe_fetch_cancelled(self, mock_context: MagicMock) -> None:
        """safe_large_fetch should handle cancelled elicitation."""
        from fastmcp.server.elicitation import CancelledElicitation

        from mp_mcp_server.tools.interactive.safe_fetch import safe_large_fetch

        mock_context.elicit = AsyncMock(return_value=CancelledElicitation())

        # Mock large dataset to trigger elicitation
        mock_context.fastmcp._lifespan_result["workspace"].top_events.return_value = [
            MagicMock(to_dict=lambda: {"event": "login", "count": 10000000}),
        ]

        result = await safe_large_fetch.fn(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-12-31",
        )

        assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_safe_fetch_accepted_with_limit(
        self, mock_context: MagicMock
    ) -> None:
        """safe_large_fetch should handle accepted elicitation with limit."""
        from fastmcp.server.elicitation import AcceptedElicitation

        from mp_mcp_server.tools.interactive.safe_fetch import safe_large_fetch

        mock_context.elicit = AsyncMock(
            return_value=AcceptedElicitation(
                data={"proceed": True, "reduce_scope": True, "new_limit": 5000}
            )
        )

        # Mock large dataset to trigger elicitation
        mock_context.fastmcp._lifespan_result["workspace"].top_events.return_value = [
            MagicMock(to_dict=lambda: {"event": "login", "count": 10000000}),
        ]

        result = await safe_large_fetch.fn(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-12-31",
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_safe_fetch_accepted_not_proceed(
        self, mock_context: MagicMock
    ) -> None:
        """safe_large_fetch should handle accepted but not proceeding."""
        from fastmcp.server.elicitation import AcceptedElicitation

        from mp_mcp_server.tools.interactive.safe_fetch import safe_large_fetch

        mock_context.elicit = AsyncMock(
            return_value=AcceptedElicitation(data={"proceed": False})
        )

        # Mock large dataset to trigger elicitation
        mock_context.fastmcp._lifespan_result["workspace"].top_events.return_value = [
            MagicMock(to_dict=lambda: {"event": "login", "count": 10000000}),
        ]

        result = await safe_large_fetch.fn(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-12-31",
        )

        assert result["status"] == "declined"

    @pytest.mark.asyncio
    async def test_safe_fetch_fetch_error(self, mock_context: MagicMock) -> None:
        """safe_large_fetch should handle fetch errors."""
        from mp_mcp_server.tools.interactive.safe_fetch import safe_large_fetch

        # Small dataset, no elicitation needed
        mock_context.fastmcp._lifespan_result["workspace"].top_events.return_value = [
            MagicMock(to_dict=lambda: {"event": "login", "count": 100}),
        ]

        # Make fetch_events fail
        mock_context.fastmcp._lifespan_result["workspace"].fetch_events.side_effect = (
            Exception("Fetch failed")
        )

        result = await safe_large_fetch.fn(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
        )

        assert result["status"] == "error"
        assert "Fetch failed" in result["message"]


class TestGuidedAnalysisEdgeCases:
    """Tests for guided_analysis edge cases."""

    def test_run_initial_analysis_handles_error(self, mock_context: MagicMock) -> None:
        """run_initial_analysis should handle query errors."""
        from mp_mcp_server.tools.interactive.guided import run_initial_analysis

        mock_context.fastmcp._lifespan_result["workspace"].funnel.side_effect = (
            Exception("API error")
        )

        result = run_initial_analysis(
            mock_context,
            focus_area="conversion",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["focus_area"] == "conversion"
        # Should return with error info but not crash

    @pytest.mark.asyncio
    async def test_guided_analysis_with_time_period(
        self, mock_context: MagicMock
    ) -> None:
        """guided_analysis should accept time_period parameter."""
        from mp_mcp_server.tools.interactive.guided import guided_analysis

        result = await guided_analysis.fn(
            mock_context,
            focus_area="retention",
            time_period="last_7_days",
        )

        assert result["focus_area"] == "retention"

    @pytest.mark.asyncio
    async def test_guided_analysis_default_dates(
        self, mock_context: MagicMock
    ) -> None:
        """guided_analysis should use default dates when not provided."""
        from mp_mcp_server.tools.interactive.guided import guided_analysis

        result = await guided_analysis.fn(
            mock_context,
            focus_area="engagement",
        )

        assert "period" in result
        assert "from_date" in result["period"]
        assert "to_date" in result["period"]

    def test_run_initial_analysis_retention(self, mock_context: MagicMock) -> None:
        """run_initial_analysis should handle retention focus area."""
        from mp_mcp_server.tools.interactive.guided import run_initial_analysis

        result = run_initial_analysis(
            mock_context,
            focus_area="retention",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["focus_area"] == "retention"
        assert "segments" in result
        assert len(result["findings"]) > 0

    def test_run_initial_analysis_retention_error(self, mock_context: MagicMock) -> None:
        """run_initial_analysis should handle retention query errors."""
        from mp_mcp_server.tools.interactive.guided import run_initial_analysis

        mock_context.fastmcp._lifespan_result["workspace"].retention.side_effect = (
            Exception("Retention API error")
        )

        result = run_initial_analysis(
            mock_context,
            focus_area="retention",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["focus_area"] == "retention"
        assert any("error" in f.lower() for f in result["findings"])

    def test_run_initial_analysis_engagement(self, mock_context: MagicMock) -> None:
        """run_initial_analysis should handle engagement focus area."""
        from mp_mcp_server.tools.interactive.guided import run_initial_analysis

        result = run_initial_analysis(
            mock_context,
            focus_area="engagement",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["focus_area"] == "engagement"
        assert "frequency_suggestion" in result

    def test_run_initial_analysis_engagement_error(
        self, mock_context: MagicMock
    ) -> None:
        """run_initial_analysis should handle engagement errors."""
        from mp_mcp_server.tools.interactive.guided import run_initial_analysis

        mock_context.fastmcp._lifespan_result["workspace"].event_counts.side_effect = (
            Exception("Event counts error")
        )

        result = run_initial_analysis(
            mock_context,
            focus_area="engagement",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["focus_area"] == "engagement"
        assert any("error" in f.lower() for f in result["findings"])

    def test_run_initial_analysis_revenue(self, mock_context: MagicMock) -> None:
        """run_initial_analysis should handle revenue focus area."""
        from mp_mcp_server.tools.interactive.guided import run_initial_analysis

        # Mock events with a purchase event
        mock_context.fastmcp._lifespan_result["workspace"].events.return_value = [
            "purchase",
            "signup",
            "login",
        ]

        result = run_initial_analysis(
            mock_context,
            focus_area="revenue",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["focus_area"] == "revenue"
        assert "segments" in result

    def test_run_initial_analysis_revenue_no_events(
        self, mock_context: MagicMock
    ) -> None:
        """run_initial_analysis should handle revenue with no matching events."""
        from mp_mcp_server.tools.interactive.guided import run_initial_analysis

        # Mock events without revenue events
        mock_context.fastmcp._lifespan_result["workspace"].events.return_value = [
            "signup",
            "login",
            "view_page",
        ]

        result = run_initial_analysis(
            mock_context,
            focus_area="revenue",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["focus_area"] == "revenue"
        assert any("No revenue events" in f for f in result["findings"])

    def test_run_segment_analysis_retention(self, mock_context: MagicMock) -> None:
        """run_segment_analysis should handle retention focus area."""
        from mp_mcp_server.tools.interactive.guided import run_segment_analysis

        result = run_segment_analysis(
            mock_context,
            focus_area="retention",
            segment_property="$browser",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["segment_property"] == "$browser"
        assert "breakdown" in result

    def test_run_segment_analysis_other(self, mock_context: MagicMock) -> None:
        """run_segment_analysis should handle non-retention focus areas."""
        from mp_mcp_server.tools.interactive.guided import run_segment_analysis

        result = run_segment_analysis(
            mock_context,
            focus_area="conversion",
            segment_property="$os",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["segment_property"] == "$os"
        assert len(result["findings"]) > 0

    def test_run_segment_analysis_error(self, mock_context: MagicMock) -> None:
        """run_segment_analysis should handle errors."""
        from mp_mcp_server.tools.interactive.guided import run_segment_analysis

        mock_context.fastmcp._lifespan_result["workspace"].property_counts.side_effect = (
            Exception("Property counts error")
        )

        result = run_segment_analysis(
            mock_context,
            focus_area="engagement",
            segment_property="$browser",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert any("error" in f.lower() for f in result["findings"])

    @pytest.mark.asyncio
    async def test_guided_analysis_revenue(self, mock_context: MagicMock) -> None:
        """guided_analysis should handle revenue focus area."""
        from mp_mcp_server.tools.interactive.guided import guided_analysis

        mock_context.fastmcp._lifespan_result["workspace"].events.return_value = [
            "purchase",
            "signup",
        ]

        result = await guided_analysis.fn(
            mock_context,
            focus_area="revenue",
            time_period="last_30_days",
        )

        assert result["focus_area"] == "revenue"

    @pytest.mark.asyncio
    async def test_guided_analysis_last_90_days(self, mock_context: MagicMock) -> None:
        """guided_analysis should handle last_90_days time period."""
        from mp_mcp_server.tools.interactive.guided import guided_analysis

        result = await guided_analysis.fn(
            mock_context,
            focus_area="conversion",
            time_period="last_90_days",
        )

        assert result["focus_area"] == "conversion"
        assert "period" in result

    @pytest.mark.asyncio
    async def test_guided_analysis_custom_dates(self, mock_context: MagicMock) -> None:
        """guided_analysis should accept custom date range."""
        from mp_mcp_server.tools.interactive.guided import guided_analysis

        result = await guided_analysis.fn(
            mock_context,
            focus_area="retention",
            time_period="custom",
            from_date="2024-06-01",
            to_date="2024-06-30",
        )

        assert result["period"]["from_date"] == "2024-06-01"
        assert result["period"]["to_date"] == "2024-06-30"


class TestPromptFocusSelection:
    """Tests for prompt_focus_selection helper function."""

    @pytest.mark.asyncio
    async def test_prompt_focus_selection_accepted_dict(
        self, mock_context: MagicMock
    ) -> None:
        """prompt_focus_selection should handle accepted elicitation with dict."""
        from fastmcp.server.elicitation import AcceptedElicitation

        from mp_mcp_server.tools.interactive.guided import prompt_focus_selection

        mock_context.elicit = AsyncMock(
            return_value=AcceptedElicitation(
                data={
                    "focus_area": "retention",
                    "time_period": "last_7_days",
                    "custom_start": None,
                    "custom_end": None,
                }
            )
        )

        result = await prompt_focus_selection(mock_context)

        assert result is not None
        assert result.focus_area == "retention"
        assert result.time_period == "last_7_days"

    @pytest.mark.asyncio
    async def test_prompt_focus_selection_declined(
        self, mock_context: MagicMock
    ) -> None:
        """prompt_focus_selection should return None on declined."""
        from fastmcp.server.elicitation import DeclinedElicitation

        from mp_mcp_server.tools.interactive.guided import prompt_focus_selection

        mock_context.elicit = AsyncMock(return_value=DeclinedElicitation())

        result = await prompt_focus_selection(mock_context)

        assert result is None

    @pytest.mark.asyncio
    async def test_prompt_focus_selection_cancelled(
        self, mock_context: MagicMock
    ) -> None:
        """prompt_focus_selection should return None on cancelled."""
        from fastmcp.server.elicitation import CancelledElicitation

        from mp_mcp_server.tools.interactive.guided import prompt_focus_selection

        mock_context.elicit = AsyncMock(return_value=CancelledElicitation())

        result = await prompt_focus_selection(mock_context)

        assert result is None

    @pytest.mark.asyncio
    async def test_prompt_focus_selection_exception(
        self, mock_context: MagicMock
    ) -> None:
        """prompt_focus_selection should return None on exception."""
        from mp_mcp_server.tools.interactive.guided import prompt_focus_selection

        mock_context.elicit = AsyncMock(
            side_effect=Exception("Elicitation not available")
        )

        result = await prompt_focus_selection(mock_context)

        assert result is None

    @pytest.mark.asyncio
    async def test_prompt_focus_selection_non_dict_data(
        self, mock_context: MagicMock
    ) -> None:
        """prompt_focus_selection should return None for non-dict data."""
        from fastmcp.server.elicitation import AcceptedElicitation

        from mp_mcp_server.tools.interactive.guided import prompt_focus_selection

        # Return AcceptedElicitation with non-dict data
        mock_context.elicit = AsyncMock(
            return_value=AcceptedElicitation(data="not a dict")
        )

        result = await prompt_focus_selection(mock_context)

        assert result is None


class TestPromptSegmentSelection:
    """Tests for prompt_segment_selection helper function."""

    @pytest.mark.asyncio
    async def test_prompt_segment_selection_empty_segments(
        self, mock_context: MagicMock
    ) -> None:
        """prompt_segment_selection should return None for empty segments."""
        from mp_mcp_server.tools.interactive.guided import prompt_segment_selection

        result = await prompt_segment_selection(mock_context, segments=[])

        assert result is None

    @pytest.mark.asyncio
    async def test_prompt_segment_selection_accepted(
        self, mock_context: MagicMock
    ) -> None:
        """prompt_segment_selection should handle accepted elicitation."""
        from fastmcp.server.elicitation import AcceptedElicitation

        from mp_mcp_server.tools.interactive.guided import prompt_segment_selection

        mock_context.elicit = AsyncMock(
            return_value=AcceptedElicitation(data={"segment_index": 1})
        )

        segments = [
            {"name": "By Browser", "property": "$browser"},
            {"name": "By Platform", "property": "$os"},
        ]

        result = await prompt_segment_selection(mock_context, segments=segments)

        assert result is not None
        assert result.segment_index == 1

    @pytest.mark.asyncio
    async def test_prompt_segment_selection_declined(
        self, mock_context: MagicMock
    ) -> None:
        """prompt_segment_selection should return None on declined."""
        from fastmcp.server.elicitation import DeclinedElicitation

        from mp_mcp_server.tools.interactive.guided import prompt_segment_selection

        mock_context.elicit = AsyncMock(return_value=DeclinedElicitation())

        segments = [{"name": "By Browser", "property": "$browser"}]

        result = await prompt_segment_selection(mock_context, segments=segments)

        assert result is None

    @pytest.mark.asyncio
    async def test_prompt_segment_selection_cancelled(
        self, mock_context: MagicMock
    ) -> None:
        """prompt_segment_selection should return None on cancelled."""
        from fastmcp.server.elicitation import CancelledElicitation

        from mp_mcp_server.tools.interactive.guided import prompt_segment_selection

        mock_context.elicit = AsyncMock(return_value=CancelledElicitation())

        segments = [{"name": "By Browser", "property": "$browser"}]

        result = await prompt_segment_selection(mock_context, segments=segments)

        assert result is None

    @pytest.mark.asyncio
    async def test_prompt_segment_selection_exception(
        self, mock_context: MagicMock
    ) -> None:
        """prompt_segment_selection should return None on exception."""
        from mp_mcp_server.tools.interactive.guided import prompt_segment_selection

        mock_context.elicit = AsyncMock(
            side_effect=Exception("Elicitation not available")
        )

        segments = [{"name": "By Browser", "property": "$browser"}]

        result = await prompt_segment_selection(mock_context, segments=segments)

        assert result is None

    @pytest.mark.asyncio
    async def test_prompt_segment_selection_non_dict_data(
        self, mock_context: MagicMock
    ) -> None:
        """prompt_segment_selection should return None for non-dict data."""
        from fastmcp.server.elicitation import AcceptedElicitation

        from mp_mcp_server.tools.interactive.guided import prompt_segment_selection

        mock_context.elicit = AsyncMock(
            return_value=AcceptedElicitation(data="not a dict")
        )

        segments = [{"name": "By Browser", "property": "$browser"}]

        result = await prompt_segment_selection(mock_context, segments=segments)

        assert result is None


class TestRunInitialAnalysisErrors:
    """Tests for run_initial_analysis error handling."""

    def test_run_initial_analysis_events_error(self, mock_context: MagicMock) -> None:
        """run_initial_analysis should handle events() exception."""
        from mp_mcp_server.tools.interactive.guided import run_initial_analysis

        mock_context.fastmcp._lifespan_result["workspace"].events.side_effect = (
            Exception("Events API error")
        )

        result = run_initial_analysis(
            mock_context,
            focus_area="conversion",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["focus_area"] == "conversion"
        # Should still have required fields
        assert "findings" in result
        assert "segments" in result

    def test_run_initial_analysis_revenue_segmentation_error(
        self, mock_context: MagicMock
    ) -> None:
        """run_initial_analysis should handle revenue segmentation error."""
        from mp_mcp_server.tools.interactive.guided import run_initial_analysis

        # Mock events with purchase event
        mock_context.fastmcp._lifespan_result["workspace"].events.return_value = [
            "purchase",
            "login",
        ]
        # Make segmentation fail
        mock_context.fastmcp._lifespan_result["workspace"].segmentation.side_effect = (
            Exception("Segmentation API error")
        )

        result = run_initial_analysis(
            mock_context,
            focus_area="revenue",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["focus_area"] == "revenue"
        assert any("error" in f.lower() for f in result["findings"])

    def test_run_initial_analysis_conversion_funnels_error(
        self, mock_context: MagicMock
    ) -> None:
        """run_initial_analysis should handle funnels() exception."""
        from mp_mcp_server.tools.interactive.guided import run_initial_analysis

        mock_context.fastmcp._lifespan_result["workspace"].funnels.side_effect = (
            Exception("Funnels API error")
        )
        mock_context.fastmcp._lifespan_result["workspace"].top_events.side_effect = (
            Exception("Top events API error")
        )

        result = run_initial_analysis(
            mock_context,
            focus_area="conversion",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["focus_area"] == "conversion"
        assert any("error" in f.lower() for f in result["findings"])


class TestGuidedAnalysisElicitationFlows:
    """Tests for guided_analysis elicitation flows."""

    @pytest.mark.asyncio
    async def test_guided_analysis_with_focus_elicitation(
        self, mock_context: MagicMock
    ) -> None:
        """guided_analysis should use elicitation when focus_area not provided."""
        from fastmcp.server.elicitation import AcceptedElicitation

        from mp_mcp_server.tools.interactive.guided import guided_analysis

        mock_context.elicit = AsyncMock(
            return_value=AcceptedElicitation(
                data={
                    "focus_area": "engagement",
                    "time_period": "last_7_days",
                    "custom_start": None,
                    "custom_end": None,
                }
            )
        )

        result = await guided_analysis.fn(mock_context)

        assert result["focus_area"] == "engagement"
        assert "User selected focus via elicitation" in result["workflow_steps"]

    @pytest.mark.asyncio
    async def test_guided_analysis_with_segment_selection(
        self, mock_context: MagicMock
    ) -> None:
        """guided_analysis should handle segment selection."""
        from fastmcp.server.elicitation import AcceptedElicitation

        from mp_mcp_server.tools.interactive.guided import guided_analysis

        # First elicit returns None (using preset focus_area), second returns segment choice
        mock_context.elicit = AsyncMock(
            return_value=AcceptedElicitation(
                data={"segment_index": 0, "investigate_further": True}
            )
        )

        result = await guided_analysis.fn(
            mock_context,
            focus_area="conversion",
        )

        assert result["focus_area"] == "conversion"
        # Should have attempted segment analysis
        assert "segment_analysis" in result or "available_segments" in result

    @pytest.mark.asyncio
    async def test_guided_analysis_segment_selection_invalid_index(
        self, mock_context: MagicMock
    ) -> None:
        """guided_analysis should handle invalid segment index."""
        from fastmcp.server.elicitation import AcceptedElicitation

        from mp_mcp_server.tools.interactive.guided import guided_analysis

        # Return segment index out of range
        mock_context.elicit = AsyncMock(
            return_value=AcceptedElicitation(
                data={"segment_index": 99, "investigate_further": True}
            )
        )

        result = await guided_analysis.fn(
            mock_context,
            focus_area="conversion",
        )

        # Should skip invalid segment index
        assert any("Invalid segment index" in step for step in result["workflow_steps"])

    @pytest.mark.asyncio
    async def test_guided_analysis_segment_no_further_investigation(
        self, mock_context: MagicMock
    ) -> None:
        """guided_analysis should skip drill-down when investigate_further is False."""
        from fastmcp.server.elicitation import AcceptedElicitation

        from mp_mcp_server.tools.interactive.guided import guided_analysis

        # Return segment choice with investigate_further=False
        mock_context.elicit = AsyncMock(
            return_value=AcceptedElicitation(
                data={"segment_index": 0, "investigate_further": False}
            )
        )

        result = await guided_analysis.fn(
            mock_context,
            focus_area="retention",
        )

        # When investigate_further is False, segment is still selected but we verify
        # the workflow step says it was selected
        assert any("selected segment" in step.lower() for step in result["workflow_steps"])

    @pytest.mark.asyncio
    async def test_guided_analysis_suggestions_conversion(
        self, mock_context: MagicMock
    ) -> None:
        """guided_analysis should provide conversion-specific suggestions."""
        from mp_mcp_server.tools.interactive.guided import guided_analysis

        result = await guided_analysis.fn(
            mock_context,
            focus_area="conversion",
        )

        assert "suggestions" in result
        assert any("funnel" in s.lower() for s in result["suggestions"])

    @pytest.mark.asyncio
    async def test_guided_analysis_suggestions_engagement(
        self, mock_context: MagicMock
    ) -> None:
        """guided_analysis should provide engagement-specific suggestions."""
        from mp_mcp_server.tools.interactive.guided import guided_analysis

        result = await guided_analysis.fn(
            mock_context,
            focus_area="engagement",
        )

        assert "suggestions" in result
        assert any("feature" in s.lower() for s in result["suggestions"])

    @pytest.mark.asyncio
    async def test_guided_analysis_suggestions_revenue(
        self, mock_context: MagicMock
    ) -> None:
        """guided_analysis should provide revenue-specific suggestions."""
        from mp_mcp_server.tools.interactive.guided import guided_analysis

        mock_context.fastmcp._lifespan_result["workspace"].events.return_value = [
            "purchase",
            "signup",
        ]

        result = await guided_analysis.fn(
            mock_context,
            focus_area="revenue",
        )

        assert "suggestions" in result
        assert any("revenue" in s.lower() for s in result["suggestions"])


class TestSafeFetchWithFetchResultVariations:
    """Tests for safe_large_fetch with various fetch result formats."""

    @pytest.mark.asyncio
    async def test_safe_fetch_result_with_to_dict(
        self, mock_context: MagicMock
    ) -> None:
        """safe_large_fetch should handle result with to_dict method."""
        from mp_mcp_server.tools.interactive.safe_fetch import safe_large_fetch

        # Small dataset, no elicitation needed
        mock_context.fastmcp._lifespan_result["workspace"].top_events.return_value = []

        # Mock fetch result with to_dict
        fetch_result = MagicMock()
        fetch_result.to_dict.return_value = {"table_name": "events", "row_count": 1000}
        mock_context.fastmcp._lifespan_result["workspace"].fetch_events.return_value = (
            fetch_result
        )

        result = await safe_large_fetch.fn(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
        )

        assert result["status"] == "completed"
        assert result["actual_count"] == 1000
        assert result["table_name"] == "events"

    @pytest.mark.asyncio
    async def test_safe_fetch_result_with_attributes(
        self, mock_context: MagicMock
    ) -> None:
        """safe_large_fetch should handle result with table_name/row_count attrs."""
        from mp_mcp_server.tools.interactive.safe_fetch import safe_large_fetch

        # Small dataset, no elicitation needed
        mock_context.fastmcp._lifespan_result["workspace"].top_events.return_value = []

        # Mock fetch result with attributes but no to_dict
        fetch_result = MagicMock(spec=["table_name", "row_count"])
        fetch_result.table_name = "my_table"
        fetch_result.row_count = 500
        del fetch_result.to_dict  # Remove to_dict
        mock_context.fastmcp._lifespan_result["workspace"].fetch_events.return_value = (
            fetch_result
        )

        result = await safe_large_fetch.fn(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
        )

        assert result["status"] == "completed"
        assert result["actual_count"] == 500

    @pytest.mark.asyncio
    async def test_safe_fetch_result_dict(self, mock_context: MagicMock) -> None:
        """safe_large_fetch should handle dict result."""
        from mp_mcp_server.tools.interactive.safe_fetch import safe_large_fetch

        # Small dataset, no elicitation needed
        mock_context.fastmcp._lifespan_result["workspace"].top_events.return_value = []

        # Mock fetch result as plain dict
        mock_context.fastmcp._lifespan_result["workspace"].fetch_events.return_value = {
            "table_name": "raw_events",
            "row_count": 200,
        }

        result = await safe_large_fetch.fn(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
        )

        assert result["status"] == "completed"
        assert result["actual_count"] == 200

    @pytest.mark.asyncio
    async def test_safe_fetch_uses_default_dates(
        self, mock_context: MagicMock
    ) -> None:
        """safe_large_fetch should use default dates when not provided."""
        from mp_mcp_server.tools.interactive.safe_fetch import safe_large_fetch

        result = await safe_large_fetch.fn(mock_context)

        assert result["status"] == "completed"
        assert "estimation" in result
        # Default is 30 days ago to today, inclusive = 31 days
        assert result["estimation"]["days_in_range"] == 31
