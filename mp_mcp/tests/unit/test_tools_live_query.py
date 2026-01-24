"""Tests for live query tools.

These tests verify the live analytics query tools are registered and return
correct data from the Workspace.
"""

from unittest.mock import MagicMock


class TestSegmentationTool:
    """Tests for the segmentation tool."""

    def test_segmentation_returns_time_series(self, mock_context: MagicMock) -> None:
        """Segmentation should return time series data."""
        from mp_mcp.tools.live_query import segmentation

        result = segmentation(  # type: ignore[operator]
            mock_context,
            event="login",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        assert "data" in result
        assert "values" in result["data"]

    def test_segmentation_with_segment_property(self, mock_context: MagicMock) -> None:
        """Segmentation should support property segmentation."""
        from mp_mcp.tools.live_query import segmentation

        result = segmentation(  # type: ignore[operator]
            mock_context,
            event="login",
            from_date="2024-01-01",
            to_date="2024-01-31",
            segment_property="browser",
        )
        assert "data" in result


class TestFunnelTool:
    """Tests for the funnel tool."""

    def test_funnel_returns_conversion_data(self, mock_context: MagicMock) -> None:
        """Funnel should return conversion step data."""
        from mp_mcp.tools.live_query import funnel

        result = funnel(  # type: ignore[operator]
            mock_context,
            funnel_id=1,
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        assert "data" in result
        assert "steps" in result["data"]


class TestRetentionTool:
    """Tests for the retention tool."""

    def test_retention_returns_cohort_data(self, mock_context: MagicMock) -> None:
        """Retention should return cohort retention data."""
        from mp_mcp.tools.live_query import retention

        result = retention(  # type: ignore[operator]
            mock_context,
            born_event="signup",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        assert "data" in result


class TestJqlTool:
    """Tests for the jql tool."""

    def test_jql_executes_script(self, mock_context: MagicMock) -> None:
        """Jql should execute JQL script and return results."""
        from mp_mcp.tools.live_query import jql

        result = jql(  # type: ignore[operator]
            mock_context,
            script="function main() { return Events({}); }",
        )
        assert isinstance(result, list)
        assert len(result) == 1


class TestEventCountsTool:
    """Tests for the event_counts tool."""

    def test_event_counts_returns_multi_event_series(
        self, mock_context: MagicMock
    ) -> None:
        """event_counts should return counts for multiple events."""
        from mp_mcp.tools.live_query import event_counts

        result = event_counts(  # type: ignore[operator]
            mock_context,
            events=["login", "signup"],
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        # EventCountsResult.to_dict() returns events, series, unit, type, dates
        assert "events" in result
        assert "series" in result


class TestPropertyCountsTool:
    """Tests for the property_counts tool."""

    def test_property_counts_returns_value_breakdown(
        self, mock_context: MagicMock
    ) -> None:
        """property_counts should return property value breakdown."""
        from mp_mcp.tools.live_query import property_counts

        result = property_counts(  # type: ignore[operator]
            mock_context,
            event="login",
            property_name="browser",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        assert "data" in result


class TestActivityFeedTool:
    """Tests for the activity_feed tool."""

    def test_activity_feed_returns_user_events(self, mock_context: MagicMock) -> None:
        """activity_feed should return events for a user."""
        from mp_mcp.tools.live_query import activity_feed

        result = activity_feed(  # type: ignore[operator]
            mock_context,
            distinct_id="user123",
        )
        assert isinstance(result, dict)
        assert "events" in result


class TestFrequencyTool:
    """Tests for the frequency tool."""

    def test_frequency_returns_distribution(self, mock_context: MagicMock) -> None:
        """Frequency should return event frequency distribution."""
        from mp_mcp.tools.live_query import frequency

        result = frequency(  # type: ignore[operator]
            mock_context,
            event="login",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        assert "data" in result
