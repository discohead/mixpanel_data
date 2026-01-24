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


class TestQuerySavedReportTool:
    """Tests for the query_saved_report tool."""

    def test_query_saved_report_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """query_saved_report tool should be registered with the MCP server."""
        assert "query_saved_report" in registered_tool_names

    def test_query_saved_report_returns_report_data(
        self, mock_context: MagicMock
    ) -> None:
        """query_saved_report should return report data from Workspace."""
        from mp_mcp.tools.live_query import query_saved_report

        result = query_saved_report(mock_context, bookmark_id=12345)  # type: ignore[operator]
        assert "bookmark_id" in result
        assert result["report_type"] == "insights"


class TestQueryFlowsTool:
    """Tests for the query_flows tool."""

    def test_query_flows_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """query_flows tool should be registered with the MCP server."""
        assert "query_flows" in registered_tool_names

    def test_query_flows_returns_flows_data(self, mock_context: MagicMock) -> None:
        """query_flows should return flows report data from Workspace."""
        from mp_mcp.tools.live_query import query_flows

        result = query_flows(mock_context, bookmark_id=67890)  # type: ignore[operator]
        assert "steps" in result
        assert "conversion_rate" in result


class TestSegmentationNumericTool:
    """Tests for the segmentation_numeric tool."""

    def test_segmentation_numeric_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """segmentation_numeric tool should be registered with the MCP server."""
        assert "segmentation_numeric" in registered_tool_names

    def test_segmentation_numeric_returns_bucketed_data(
        self, mock_context: MagicMock
    ) -> None:
        """segmentation_numeric should return bucketed data from Workspace."""
        from mp_mcp.tools.live_query import segmentation_numeric

        result = segmentation_numeric(  # type: ignore[operator]
            mock_context,
            event="purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            on='properties["amount"]',
        )
        assert "buckets" in result


class TestSegmentationSumTool:
    """Tests for the segmentation_sum tool."""

    def test_segmentation_sum_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """segmentation_sum tool should be registered with the MCP server."""
        assert "segmentation_sum" in registered_tool_names

    def test_segmentation_sum_returns_sum_data(self, mock_context: MagicMock) -> None:
        """segmentation_sum should return sum values from Workspace."""
        from mp_mcp.tools.live_query import segmentation_sum

        result = segmentation_sum(  # type: ignore[operator]
            mock_context,
            event="purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            on='properties["revenue"]',
        )
        assert "data" in result


class TestSegmentationAverageTool:
    """Tests for the segmentation_average tool."""

    def test_segmentation_average_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """segmentation_average tool should be registered with the MCP server."""
        assert "segmentation_average" in registered_tool_names

    def test_segmentation_average_returns_avg_data(
        self, mock_context: MagicMock
    ) -> None:
        """segmentation_average should return average values from Workspace."""
        from mp_mcp.tools.live_query import segmentation_average

        result = segmentation_average(  # type: ignore[operator]
            mock_context,
            event="purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            on='properties["amount"]',
        )
        assert "data" in result


class TestPropertyDistributionTool:
    """Tests for the property_distribution tool."""

    def test_property_distribution_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """property_distribution tool should be registered with the MCP server."""
        assert "property_distribution" in registered_tool_names

    def test_property_distribution_returns_value_counts(
        self, mock_context: MagicMock
    ) -> None:
        """property_distribution should return value counts from Workspace."""
        from mp_mcp.tools.live_query import property_distribution

        result = property_distribution(  # type: ignore[operator]
            mock_context,
            event="purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        assert "values" in result


class TestNumericSummaryTool:
    """Tests for the numeric_summary tool."""

    def test_numeric_summary_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """numeric_summary tool should be registered with the MCP server."""
        assert "numeric_summary" in registered_tool_names

    def test_numeric_summary_returns_statistics(self, mock_context: MagicMock) -> None:
        """numeric_summary should return statistics from Workspace."""
        from mp_mcp.tools.live_query import numeric_summary

        result = numeric_summary(  # type: ignore[operator]
            mock_context,
            event="purchase",
            property_name="amount",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        assert "count" in result
        assert "min" in result
        assert "max" in result
        assert "avg" in result


class TestDailyCountsTool:
    """Tests for the daily_counts tool."""

    def test_daily_counts_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """daily_counts tool should be registered with the MCP server."""
        assert "daily_counts" in registered_tool_names

    def test_daily_counts_returns_counts(self, mock_context: MagicMock) -> None:
        """daily_counts should return daily event counts from Workspace."""
        from mp_mcp.tools.live_query import daily_counts

        result = daily_counts(  # type: ignore[operator]
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
        )
        assert "counts" in result


class TestEngagementDistributionTool:
    """Tests for the engagement_distribution tool."""

    def test_engagement_distribution_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """engagement_distribution tool should be registered with the MCP server."""
        assert "engagement_distribution" in registered_tool_names

    def test_engagement_distribution_returns_buckets(
        self, mock_context: MagicMock
    ) -> None:
        """engagement_distribution should return user buckets from Workspace."""
        from mp_mcp.tools.live_query import engagement_distribution

        result = engagement_distribution(  # type: ignore[operator]
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        assert "buckets" in result


class TestPropertyCoverageTool:
    """Tests for the property_coverage tool."""

    def test_property_coverage_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """property_coverage tool should be registered with the MCP server."""
        assert "property_coverage" in registered_tool_names

    def test_property_coverage_returns_coverage_stats(
        self, mock_context: MagicMock
    ) -> None:
        """property_coverage should return coverage stats from Workspace."""
        from mp_mcp.tools.live_query import property_coverage

        result = property_coverage(  # type: ignore[operator]
            mock_context,
            event="purchase",
            properties=["coupon_code", "referrer"],
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        assert "coverage" in result
