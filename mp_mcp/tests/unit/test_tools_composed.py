"""Tests for composed analytics tools.

These tests verify the cohort_comparison, product_health_dashboard,
and gqm_investigation tools work correctly.
"""

from unittest.mock import MagicMock


class TestCohortHelpers:
    """Tests for cohort comparison helper functions."""

    def test_get_default_date_range(self) -> None:
        """_get_default_date_range should return valid dates."""
        from mp_mcp.tools.composed.cohort import _get_default_date_range

        from_date, to_date = _get_default_date_range()
        assert from_date < to_date
        assert len(from_date) == 10  # YYYY-MM-DD format
        assert len(to_date) == 10

    def test_get_default_date_range_custom_days(self) -> None:
        """_get_default_date_range should accept custom days."""
        from mp_mcp.tools.composed.cohort import _get_default_date_range

        from_date, to_date = _get_default_date_range(days_back=7)
        assert from_date < to_date

    def test_build_event_comparison_jql(self) -> None:
        """_build_event_comparison_jql should generate valid JQL."""
        from mp_mcp.tools.composed.cohort import _build_event_comparison_jql

        jql = _build_event_comparison_jql(
            cohort_a_filter='properties["sessions"] >= 10',
            cohort_b_filter='properties["sessions"] < 3',
        )
        assert "function main()" in jql
        assert "cohort_a" in jql
        assert "cohort_b" in jql

    def test_build_event_comparison_jql_with_event_selector(self) -> None:
        """_build_event_comparison_jql should include event_selectors when event provided."""
        from mp_mcp.tools.composed.cohort import _build_event_comparison_jql

        jql = _build_event_comparison_jql(
            cohort_a_filter='properties["cluster"] == "prod-1"',
            cohort_b_filter='properties["cluster"] == "prod-2"',
            event="sql-query",
        )
        assert "function main()" in jql
        assert 'event_selectors: [{event: "sql-query"}]' in jql
        assert "cohort_a" in jql
        assert "cohort_b" in jql

    def test_build_event_comparison_jql_without_event_selector(self) -> None:
        """_build_event_comparison_jql should not include event_selectors when no event."""
        from mp_mcp.tools.composed.cohort import _build_event_comparison_jql

        jql = _build_event_comparison_jql(
            cohort_a_filter='properties["sessions"] >= 10',
            cohort_b_filter='properties["sessions"] < 3',
        )
        assert "event_selectors" not in jql

    def test_build_user_count_jql(self) -> None:
        """_build_user_count_jql should generate valid JQL for single cohort."""
        from mp_mcp.tools.composed.cohort import _build_user_count_jql

        jql = _build_user_count_jql(
            cohort_filter='properties["country"] == "US"',
        )
        assert "function main()" in jql
        assert "groupByUser" in jql
        assert ".reduce(mixpanel.reducer.count())" in jql

    def test_build_user_count_jql_with_event_selector(self) -> None:
        """_build_user_count_jql should include event_selectors when event provided."""
        from mp_mcp.tools.composed.cohort import _build_user_count_jql

        jql = _build_user_count_jql(
            cohort_filter='properties["$browser"] == "Chrome"',
            event="AI Prompt Sent",
        )
        assert 'event_selectors: [{event: "AI Prompt Sent"}]' in jql
        assert ".reduce(mixpanel.reducer.count())" in jql

    def test_build_user_count_jql_converts_properties(self) -> None:
        """_build_user_count_jql should convert properties to event.properties."""
        from mp_mcp.tools.composed.cohort import _build_user_count_jql

        jql = _build_user_count_jql(
            cohort_filter='properties["$browser"] == "Chrome"',
        )
        assert 'event.properties["$browser"]' in jql

    def test_parse_event_comparison_results_empty(self) -> None:
        """_parse_event_comparison_results should handle empty results."""
        from mp_mcp.tools.composed.cohort import _parse_event_comparison_results

        result = _parse_event_comparison_results([])
        assert result["cohort_a_frequency"] == {}
        assert result["cohort_b_frequency"] == {}
        assert result["differences"] == []

    def test_parse_event_comparison_results_with_data(self) -> None:
        """_parse_event_comparison_results should parse JQL results."""
        from mp_mcp.tools.composed.cohort import _parse_event_comparison_results

        jql_results = [
            {"key": ["login", "cohort_a"], "value": 100},
            {"key": ["login", "cohort_b"], "value": 50},
            {"key": ["signup", "cohort_a"], "value": 30},
        ]

        result = _parse_event_comparison_results(jql_results)
        assert result["cohort_a_frequency"]["login"] == 100
        assert result["cohort_b_frequency"]["login"] == 50
        assert result["cohort_a_frequency"]["signup"] == 30

    def test_extract_user_count_from_list(self) -> None:
        """_extract_user_count should extract count from JQL reduce result."""
        from mp_mcp.tools.composed.cohort import _extract_user_count

        # JQL .reduce(mixpanel.reducer.count()) returns [count]
        assert _extract_user_count([414]) == 414
        assert _extract_user_count([0]) == 0
        assert _extract_user_count([]) == 0

    def test_extract_user_count_from_jql_result(self) -> None:
        """_extract_user_count should handle JQLResult objects with .raw attribute."""
        from mp_mcp.tools.composed.cohort import _extract_user_count

        jql_result = MagicMock()
        jql_result.raw = [360]
        assert _extract_user_count(jql_result) == 360

    def test_extract_user_count_handles_empty(self) -> None:
        """_extract_user_count should return 0 for empty/invalid results."""
        from mp_mcp.tools.composed.cohort import _extract_user_count

        assert _extract_user_count([]) == 0
        assert _extract_user_count(None) == 0
        assert _extract_user_count({}) == 0

    def test_compute_user_ratio(self) -> None:
        """_compute_user_ratio should calculate ratio correctly."""
        from mp_mcp.tools.composed.cohort import _compute_user_ratio

        assert _compute_user_ratio(500, 200) == 2.5
        assert _compute_user_ratio(414, 360) == 1.15
        assert _compute_user_ratio(100, 0) == float("inf")
        assert _compute_user_ratio(0, 100) == 0.0


class TestCohortComparisonTool:
    """Tests for the cohort_comparison tool."""

    def test_tool_registered(self, registered_tool_names: list[str]) -> None:
        """cohort_comparison tool should be registered."""
        assert "cohort_comparison" in registered_tool_names

    def test_cohort_comparison_basic(self, mock_context: MagicMock) -> None:
        """cohort_comparison should return comparison results."""
        from mp_mcp.tools.composed.cohort import cohort_comparison

        # Set up mock JQL response
        jql_result = MagicMock()
        jql_result.raw = [
            {"key": ["login", "cohort_a"], "value": 100},
            {"key": ["login", "cohort_b"], "value": 50},
        ]
        mock_context.lifespan_context["workspace"].jql.return_value = jql_result

        result = cohort_comparison(  # type: ignore[operator]
            mock_context,
            cohort_a_filter='properties["sessions"] >= 10',
            cohort_b_filter='properties["sessions"] < 3',
        )

        assert "cohort_a" in result
        assert "cohort_b" in result
        assert "period" in result
        assert "comparisons" in result


class TestDashboardHelpers:
    """Tests for product health dashboard helper functions."""

    def test_get_default_date_range(self) -> None:
        """_get_default_date_range should return valid dates."""
        from mp_mcp.tools.composed.dashboard import _get_default_date_range

        from_date, to_date = _get_default_date_range()
        assert from_date < to_date

    def test_compute_health_score_acquisition_high(self) -> None:
        """_compute_health_score should score high acquisition."""
        from mp_mcp.tools.composed.dashboard import _compute_health_score
        from mp_mcp.types import AARRRMetrics, ProductHealthDashboard

        dashboard = ProductHealthDashboard(
            period={"from_date": "2024-01-01", "to_date": "2024-01-31"},
            acquisition=AARRRMetrics(
                category="acquisition",
                primary_metric=2000.0,
                trend={},
            ),
        )

        scores = _compute_health_score(dashboard)
        assert scores["acquisition"] == 8

    def test_compute_health_score_activation_rate(self) -> None:
        """_compute_health_score should score activation rate."""
        from mp_mcp.tools.composed.dashboard import _compute_health_score
        from mp_mcp.types import AARRRMetrics, ProductHealthDashboard

        dashboard = ProductHealthDashboard(
            period={"from_date": "2024-01-01", "to_date": "2024-01-31"},
            activation=AARRRMetrics(
                category="activation",
                primary_metric=0.6,  # 60% activation
                trend={},
            ),
        )

        scores = _compute_health_score(dashboard)
        assert scores["activation"] == 9

    def test_compute_health_score_retention_rate(self) -> None:
        """_compute_health_score should score retention rate."""
        from mp_mcp.tools.composed.dashboard import _compute_health_score
        from mp_mcp.types import AARRRMetrics, ProductHealthDashboard

        dashboard = ProductHealthDashboard(
            period={"from_date": "2024-01-01", "to_date": "2024-01-31"},
            retention=AARRRMetrics(
                category="retention",
                primary_metric=0.30,  # 30% D7 retention
                trend={},
            ),
        )

        scores = _compute_health_score(dashboard)
        assert scores["retention"] == 7


class TestProductHealthDashboardTool:
    """Tests for the product_health_dashboard tool."""

    def test_tool_registered(self, registered_tool_names: list[str]) -> None:
        """product_health_dashboard tool should be registered."""
        assert "product_health_dashboard" in registered_tool_names

    def test_dashboard_basic(self, mock_context: MagicMock) -> None:
        """product_health_dashboard should return AARRR metrics."""
        from mp_mcp.tools.composed.dashboard import product_health_dashboard

        result = product_health_dashboard(mock_context)  # type: ignore[operator]

        assert "period" in result
        assert "acquisition" in result
        assert "activation" in result
        assert "retention" in result

    def test_dashboard_with_custom_events(self, mock_context: MagicMock) -> None:
        """product_health_dashboard should accept custom events."""
        from mp_mcp.tools.composed.dashboard import product_health_dashboard

        result = product_health_dashboard(  # type: ignore[operator]
            mock_context,
            acquisition_event="register",
            revenue_event="purchase",
        )

        assert "revenue" in result


class TestGQMHelpers:
    """Tests for GQM investigation helper functions."""

    def test_classify_aarrr_category_retention(self) -> None:
        """classify_aarrr_category should detect retention goals."""
        from mp_mcp.tools.composed.gqm import classify_aarrr_category

        result = classify_aarrr_category("why is user retention declining")
        assert result == "retention"

    def test_classify_aarrr_category_acquisition(self) -> None:
        """classify_aarrr_category should detect acquisition goals."""
        from mp_mcp.tools.composed.gqm import classify_aarrr_category

        result = classify_aarrr_category("how are signups performing this month")
        assert result == "acquisition"

    def test_classify_aarrr_category_revenue(self) -> None:
        """classify_aarrr_category should detect revenue goals."""
        from mp_mcp.tools.composed.gqm import classify_aarrr_category

        result = classify_aarrr_category("analyze purchase conversion rates")
        assert result == "revenue"

    def test_classify_aarrr_category_default(self) -> None:
        """classify_aarrr_category should default to retention."""
        from mp_mcp.tools.composed.gqm import classify_aarrr_category

        result = classify_aarrr_category("what is happening")
        assert result == "retention"

    def test_generate_questions(self) -> None:
        """generate_questions should return question list."""
        from mp_mcp.tools.composed.gqm import generate_questions

        questions = generate_questions("understand retention", "retention", 3)
        assert len(questions) <= 3
        assert all("question" in q for q in questions)
        assert all("query_type" in q for q in questions)


class TestGQMInvestigationTool:
    """Tests for the gqm_investigation tool."""

    def test_tool_registered(self, registered_tool_names: list[str]) -> None:
        """gqm_investigation tool should be registered."""
        assert "gqm_investigation" in registered_tool_names

    def test_investigation_basic(self, mock_context: MagicMock) -> None:
        """gqm_investigation should return investigation results."""
        from mp_mcp.tools.composed.gqm import gqm_investigation

        result = gqm_investigation(  # type: ignore[operator]
            mock_context,
            goal="understand why retention is declining",
        )

        assert "interpreted_goal" in result
        assert "aarrr_category" in result
        assert "period" in result
        assert "questions" in result
        assert "findings" in result
        assert "synthesis" in result
        assert "next_steps" in result

    def test_investigation_classifies_category(self, mock_context: MagicMock) -> None:
        """gqm_investigation should classify the goal."""
        from mp_mcp.tools.composed.gqm import gqm_investigation

        result = gqm_investigation(  # type: ignore[operator]
            mock_context,
            goal="analyze signup performance",
        )

        assert result["aarrr_category"] == "acquisition"

    def test_investigation_with_custom_dates(self, mock_context: MagicMock) -> None:
        """gqm_investigation should accept custom dates."""
        from mp_mcp.tools.composed.gqm import gqm_investigation

        result = gqm_investigation(  # type: ignore[operator]
            mock_context,
            goal="retention analysis",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["period"]["from_date"] == "2024-01-01"
        assert result["period"]["to_date"] == "2024-01-31"


class TestDashboardComputeFunctions:
    """Tests for individual AARRR compute functions."""

    def test_compute_acquisition(self, mock_context: MagicMock) -> None:
        """_compute_acquisition should compute acquisition metrics."""
        from mp_mcp.tools.composed.dashboard import _compute_acquisition

        # Set up mock segmentation response with series data
        mock_context.lifespan_context[
            "workspace"
        ].segmentation.return_value = MagicMock(
            to_dict=lambda: {
                "total": 1500,
                "series": {"signup": {"2024-01-01": 100, "2024-01-02": 150}},
            }
        )

        result = _compute_acquisition(
            mock_context,
            acquisition_event="signup",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result.category == "acquisition"
        assert result.primary_metric == 1500.0

    def test_compute_acquisition_with_segment(self, mock_context: MagicMock) -> None:
        """_compute_acquisition should support segmentation."""
        from mp_mcp.tools.composed.dashboard import _compute_acquisition

        mock_context.lifespan_context[
            "workspace"
        ].segmentation.return_value = MagicMock(
            to_dict=lambda: {
                "total": 1500,
                "series": {
                    "Chrome": {"2024-01-01": 100, "2024-01-02": 150},
                    "Firefox": {"2024-01-01": 50, "2024-01-02": 75},
                },
            }
        )

        result = _compute_acquisition(
            mock_context,
            acquisition_event="signup",
            from_date="2024-01-01",
            to_date="2024-01-31",
            segment_by="$browser",
        )

        assert result.category == "acquisition"
        assert result.by_segment is not None

    def test_compute_acquisition_handles_error(self, mock_context: MagicMock) -> None:
        """_compute_acquisition should handle errors gracefully."""
        from mp_mcp.tools.composed.dashboard import _compute_acquisition

        mock_context.lifespan_context["workspace"].segmentation.side_effect = Exception(
            "API error"
        )

        result = _compute_acquisition(
            mock_context,
            acquisition_event="signup",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result.category == "acquisition"
        assert result.primary_metric == 0.0
        assert result.by_segment is not None
        assert "_error" in result.by_segment

    def test_compute_activation(self, mock_context: MagicMock) -> None:
        """_compute_activation should compute activation rate."""
        from mp_mcp.tools.composed.dashboard import _compute_activation

        mock_context.lifespan_context[
            "workspace"
        ].segmentation.return_value = MagicMock(
            to_dict=lambda: {
                "total": 1000,
                "series": {"event": {"2024-01-01": 100}},
            }
        )

        result = _compute_activation(
            mock_context,
            activation_event="onboarding_complete",
            acquisition_event="signup",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result.category == "activation"
        # Rate is activation_total / acquisition_total
        assert result.primary_metric == 1.0  # 1000/1000

    def test_compute_activation_handles_error(self, mock_context: MagicMock) -> None:
        """_compute_activation should handle errors gracefully."""
        from mp_mcp.tools.composed.dashboard import _compute_activation

        mock_context.lifespan_context["workspace"].segmentation.side_effect = Exception(
            "API error"
        )

        result = _compute_activation(
            mock_context,
            activation_event="onboarding_complete",
            acquisition_event="signup",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result.primary_metric == 0.0
        assert result.by_segment is not None and "_error" in result.by_segment

    def test_compute_retention(self, mock_context: MagicMock) -> None:
        """_compute_retention should compute retention metrics from cohorts structure."""
        from mp_mcp.tools.composed.dashboard import _compute_retention

        # Mock actual RetentionResult.to_dict() structure
        mock_context.lifespan_context["workspace"].retention.return_value = MagicMock(
            to_dict=lambda: {
                "born_event": "login",
                "return_event": "login",
                "from_date": "2024-01-01",
                "to_date": "2024-01-31",
                "unit": "day",
                "cohorts": [
                    {
                        "date": "2024-01-01T00:00:00",
                        "size": 100,
                        "retention": [1.0, 0.8, 0.6, 0.5, 0.4, 0.35, 0.32, 0.30],
                    },
                    {
                        "date": "2024-01-02T00:00:00",
                        "size": 120,
                        "retention": [1.0, 0.75, 0.55, 0.45, 0.38, 0.33, 0.30, 0.28],
                    },
                ],
            }
        )

        result = _compute_retention(
            mock_context,
            retention_event="login",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result.category == "retention"
        # D7 average: (0.30 + 0.28) / 2 = 0.29
        assert abs(result.primary_metric - 0.29) < 0.01
        # Trend should have D0 retention for each cohort date
        assert "2024-01-01" in result.trend
        assert "2024-01-02" in result.trend
        assert result.trend["2024-01-01"] == 1.0
        assert result.trend["2024-01-02"] == 1.0

    def test_compute_retention_handles_error(self, mock_context: MagicMock) -> None:
        """_compute_retention should handle errors gracefully."""
        from mp_mcp.tools.composed.dashboard import _compute_retention

        mock_context.lifespan_context["workspace"].retention.side_effect = Exception(
            "API error"
        )

        result = _compute_retention(
            mock_context,
            retention_event="login",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result.primary_metric == 0.0

    def test_compute_revenue(self, mock_context: MagicMock) -> None:
        """_compute_revenue should compute revenue metrics."""
        from mp_mcp.tools.composed.dashboard import _compute_revenue

        mock_context.lifespan_context[
            "workspace"
        ].segmentation.return_value = MagicMock(
            to_dict=lambda: {
                "total": 5000,
                "series": {"purchase": {"2024-01-01": 500}},
            }
        )

        result = _compute_revenue(
            mock_context,
            revenue_event="purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result is not None
        assert result.category == "revenue"
        assert result.primary_metric == 5000.0

    def test_compute_revenue_none_event(self, mock_context: MagicMock) -> None:
        """_compute_revenue should return None when event is None."""
        from mp_mcp.tools.composed.dashboard import _compute_revenue

        result = _compute_revenue(
            mock_context,
            revenue_event=None,
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result is None

    def test_compute_revenue_handles_error(self, mock_context: MagicMock) -> None:
        """_compute_revenue should handle errors gracefully."""
        from mp_mcp.tools.composed.dashboard import _compute_revenue

        mock_context.lifespan_context["workspace"].segmentation.side_effect = Exception(
            "API error"
        )

        result = _compute_revenue(
            mock_context,
            revenue_event="purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result is not None
        assert result.primary_metric == 0.0

    def test_compute_referral(self, mock_context: MagicMock) -> None:
        """_compute_referral should compute referral metrics."""
        from mp_mcp.tools.composed.dashboard import _compute_referral

        mock_context.lifespan_context[
            "workspace"
        ].segmentation.return_value = MagicMock(
            to_dict=lambda: {
                "total": 200,
                "series": {"invite_sent": {"2024-01-01": 50}},
            }
        )

        result = _compute_referral(
            mock_context,
            referral_event="invite_sent",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result is not None
        assert result.category == "referral"
        assert result.primary_metric == 200.0

    def test_compute_referral_none_event(self, mock_context: MagicMock) -> None:
        """_compute_referral should return None when event is None."""
        from mp_mcp.tools.composed.dashboard import _compute_referral

        result = _compute_referral(
            mock_context,
            referral_event=None,
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result is None

    def test_compute_referral_handles_error(self, mock_context: MagicMock) -> None:
        """_compute_referral should handle errors gracefully."""
        from mp_mcp.tools.composed.dashboard import _compute_referral

        mock_context.lifespan_context["workspace"].segmentation.side_effect = Exception(
            "API error"
        )

        result = _compute_referral(
            mock_context,
            referral_event="invite_sent",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result is not None
        assert result.primary_metric == 0.0


class TestHealthScoreEdgeCases:
    """Tests for health score computation edge cases."""

    def test_compute_health_score_medium_acquisition(self) -> None:
        """_compute_health_score should score medium acquisition."""
        from mp_mcp.tools.composed.dashboard import _compute_health_score
        from mp_mcp.types import AARRRMetrics, ProductHealthDashboard

        dashboard = ProductHealthDashboard(
            period={"from_date": "2024-01-01", "to_date": "2024-01-31"},
            acquisition=AARRRMetrics(
                category="acquisition",
                primary_metric=500.0,  # Medium range
                trend={},
            ),
        )

        scores = _compute_health_score(dashboard)
        assert scores["acquisition"] == 6

    def test_compute_health_score_low_acquisition(self) -> None:
        """_compute_health_score should score low acquisition."""
        from mp_mcp.tools.composed.dashboard import _compute_health_score
        from mp_mcp.types import AARRRMetrics, ProductHealthDashboard

        dashboard = ProductHealthDashboard(
            period={"from_date": "2024-01-01", "to_date": "2024-01-31"},
            acquisition=AARRRMetrics(
                category="acquisition",
                primary_metric=50.0,  # Low range
                trend={},
            ),
        )

        scores = _compute_health_score(dashboard)
        assert scores["acquisition"] == 4

    def test_compute_health_score_zero_acquisition(self) -> None:
        """_compute_health_score should score zero acquisition."""
        from mp_mcp.tools.composed.dashboard import _compute_health_score
        from mp_mcp.types import AARRRMetrics, ProductHealthDashboard

        dashboard = ProductHealthDashboard(
            period={"from_date": "2024-01-01", "to_date": "2024-01-31"},
            acquisition=AARRRMetrics(
                category="acquisition",
                primary_metric=0.0,
                trend={},
            ),
        )

        scores = _compute_health_score(dashboard)
        assert scores["acquisition"] == 2

    def test_compute_health_score_various_activation_rates(self) -> None:
        """_compute_health_score should handle various activation rates."""
        from mp_mcp.tools.composed.dashboard import _compute_health_score
        from mp_mcp.types import AARRRMetrics, ProductHealthDashboard

        # Medium activation rate
        dashboard = ProductHealthDashboard(
            period={"from_date": "2024-01-01", "to_date": "2024-01-31"},
            activation=AARRRMetrics(
                category="activation",
                primary_metric=0.35,  # 35%
                trend={},
            ),
        )
        scores = _compute_health_score(dashboard)
        assert scores["activation"] == 7

        # Low activation rate
        dashboard.activation = AARRRMetrics(
            category="activation", primary_metric=0.15, trend={}
        )
        scores = _compute_health_score(dashboard)
        assert scores["activation"] == 5

        # Very low activation rate
        dashboard.activation = AARRRMetrics(
            category="activation", primary_metric=0.05, trend={}
        )
        scores = _compute_health_score(dashboard)
        assert scores["activation"] == 3

        # Zero activation rate
        dashboard.activation = AARRRMetrics(
            category="activation", primary_metric=0.0, trend={}
        )
        scores = _compute_health_score(dashboard)
        assert scores["activation"] == 1

    def test_compute_health_score_various_retention_rates(self) -> None:
        """_compute_health_score should handle various retention rates."""
        from mp_mcp.tools.composed.dashboard import _compute_health_score
        from mp_mcp.types import AARRRMetrics, ProductHealthDashboard

        # Low retention
        dashboard = ProductHealthDashboard(
            period={"from_date": "2024-01-01", "to_date": "2024-01-31"},
            retention=AARRRMetrics(category="retention", primary_metric=0.15, trend={}),
        )
        scores = _compute_health_score(dashboard)
        assert scores["retention"] == 5

        # Very low retention
        dashboard.retention = AARRRMetrics(
            category="retention", primary_metric=0.05, trend={}
        )
        scores = _compute_health_score(dashboard)
        assert scores["retention"] == 3

        # Zero retention
        dashboard.retention = AARRRMetrics(
            category="retention", primary_metric=0.0, trend={}
        )
        scores = _compute_health_score(dashboard)
        assert scores["retention"] == 1

    def test_compute_health_score_revenue(self) -> None:
        """_compute_health_score should score revenue metrics."""
        from mp_mcp.tools.composed.dashboard import _compute_health_score
        from mp_mcp.types import AARRRMetrics, ProductHealthDashboard

        dashboard = ProductHealthDashboard(
            period={"from_date": "2024-01-01", "to_date": "2024-01-31"},
            revenue=AARRRMetrics(category="revenue", primary_metric=500.0, trend={}),
        )
        scores = _compute_health_score(dashboard)
        assert scores["revenue"] == 6

        # Zero revenue
        dashboard.revenue = AARRRMetrics(
            category="revenue", primary_metric=0.0, trend={}
        )
        scores = _compute_health_score(dashboard)
        assert scores["revenue"] == 2

    def test_compute_health_score_referral(self) -> None:
        """_compute_health_score should score referral metrics."""
        from mp_mcp.tools.composed.dashboard import _compute_health_score
        from mp_mcp.types import AARRRMetrics, ProductHealthDashboard

        # High referral
        dashboard = ProductHealthDashboard(
            period={"from_date": "2024-01-01", "to_date": "2024-01-31"},
            referral=AARRRMetrics(category="referral", primary_metric=200.0, trend={}),
        )
        scores = _compute_health_score(dashboard)
        assert scores["referral"] == 8

        # Medium referral
        dashboard.referral = AARRRMetrics(
            category="referral", primary_metric=50.0, trend={}
        )
        scores = _compute_health_score(dashboard)
        assert scores["referral"] == 6

        # Low referral
        dashboard.referral = AARRRMetrics(
            category="referral", primary_metric=5.0, trend={}
        )
        scores = _compute_health_score(dashboard)
        assert scores["referral"] == 4

        # Zero referral
        dashboard.referral = AARRRMetrics(
            category="referral", primary_metric=0.0, trend={}
        )
        scores = _compute_health_score(dashboard)
        assert scores["referral"] == 2


class TestCohortHelpersExtended:
    """Extended tests for cohort comparison helper functions."""

    def test_get_default_date_range_extended(self) -> None:
        """_get_default_date_range should return valid dates."""
        from mp_mcp.tools.composed.cohort import _get_default_date_range

        from_date, to_date = _get_default_date_range()
        assert from_date < to_date
        assert len(from_date) == 10  # YYYY-MM-DD format

    def test_get_default_date_range_custom_days_extended(self) -> None:
        """_get_default_date_range should accept custom days."""
        from mp_mcp.tools.composed.cohort import _get_default_date_range

        from_date, to_date = _get_default_date_range(days_back=7)
        assert from_date < to_date

    def test_build_event_comparison_jql_detailed(self) -> None:
        """_build_event_comparison_jql should generate valid JQL."""
        from mp_mcp.tools.composed.cohort import _build_event_comparison_jql

        jql = _build_event_comparison_jql(
            cohort_a_filter='properties["sessions"] >= 10',
            cohort_b_filter='properties["sessions"] < 3',
        )

        assert "function main()" in jql
        assert "event.properties" in jql
        assert "cohort_a" in jql
        assert "cohort_b" in jql

    def test_build_user_count_jql_detailed(self) -> None:
        """_build_user_count_jql should generate valid JQL for user counting."""
        from mp_mcp.tools.composed.cohort import _build_user_count_jql

        jql = _build_user_count_jql(
            cohort_filter='properties["country"] == "US"',
        )

        assert "function main()" in jql
        assert "groupByUser" in jql
        assert ".reduce(mixpanel.reducer.count())" in jql

    def test_parse_event_comparison_results_basic(self) -> None:
        """_parse_event_comparison_results should parse JQL results."""
        from mp_mcp.tools.composed.cohort import _parse_event_comparison_results

        jql_results = [
            {"key": ["login", "cohort_a"], "value": 100},
            {"key": ["login", "cohort_b"], "value": 50},
            {"key": ["signup", "cohort_a"], "value": 30},
            {"key": ["signup", "cohort_b"], "value": 60},
        ]

        result = _parse_event_comparison_results(jql_results)

        assert result["cohort_a_frequency"]["login"] == 100
        assert result["cohort_b_frequency"]["login"] == 50
        assert "differences" in result

    def test_parse_event_comparison_results_with_differences(self) -> None:
        """_parse_event_comparison_results should identify significant differences."""
        from mp_mcp.tools.composed.cohort import _parse_event_comparison_results

        jql_results = [
            {"key": ["login", "cohort_a"], "value": 200},
            {"key": ["login", "cohort_b"], "value": 50},  # 4x difference
        ]

        result = _parse_event_comparison_results(jql_results)

        assert len(result["differences"]) > 0
        assert result["differences"][0]["ratio"] == 4.0

    def test_parse_event_comparison_results_only_one_cohort(self) -> None:
        """_parse_event_comparison_results should handle events in only one cohort."""
        from mp_mcp.tools.composed.cohort import _parse_event_comparison_results

        jql_results = [
            {"key": ["unique_event", "cohort_a"], "value": 50},
        ]

        result = _parse_event_comparison_results(jql_results)

        assert "unique_event" in result["cohort_a_frequency"]
        # Should identify as difference since only one cohort has it
        assert len(result["differences"]) > 0

    def test_parse_event_comparison_results_empty(self) -> None:
        """_parse_event_comparison_results should handle empty results."""
        from mp_mcp.tools.composed.cohort import _parse_event_comparison_results

        result = _parse_event_comparison_results([])

        assert result["cohort_a_frequency"] == {}
        assert result["cohort_b_frequency"] == {}

    def test_extract_user_count_with_dict_value(self) -> None:
        """_extract_user_count should handle dict format results."""
        from mp_mcp.tools.composed.cohort import _extract_user_count

        # Some JQL results may return dict format
        result = _extract_user_count([{"value": 500}])
        assert result == 500

    def test_extract_user_count_with_float(self) -> None:
        """_extract_user_count should handle float values."""
        from mp_mcp.tools.composed.cohort import _extract_user_count

        result = _extract_user_count([300.0])
        assert result == 300


class TestCohortComparison:
    """Tests for cohort_comparison tool."""

    def test_cohort_comparison_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """cohort_comparison tool should be registered."""
        assert "cohort_comparison" in registered_tool_names

    def test_cohort_comparison_with_mock(self, mock_context: MagicMock) -> None:
        """cohort_comparison should call JQL with proper scripts."""
        from mp_mcp.tools.composed.cohort import cohort_comparison

        # Mock JQL to return sample data
        jql_mock = MagicMock()
        jql_mock.raw = [
            {"key": ["login", "cohort_a"], "value": 100},
            {"key": ["login", "cohort_b"], "value": 50},
        ]
        mock_context.lifespan_context["workspace"].jql.return_value = jql_mock

        result = cohort_comparison(  # type: ignore[operator]
            mock_context,
            cohort_a_filter='properties["sessions"] >= 10',
            cohort_b_filter='properties["sessions"] < 3',
            cohort_a_name="Power Users",
            cohort_b_name="Casual Users",
        )

        assert "cohort_a" in result
        assert "cohort_b" in result
        assert result["cohort_a"]["name"] == "Power Users"

    def test_cohort_comparison_handles_jql_error(self, mock_context: MagicMock) -> None:
        """cohort_comparison should handle JQL errors."""
        from mp_mcp.tools.composed.cohort import cohort_comparison

        mock_context.lifespan_context["workspace"].jql.side_effect = Exception(
            "JQL error"
        )

        result = cohort_comparison(  # type: ignore[operator]
            mock_context,
            cohort_a_filter='properties["country"] == "US"',
            cohort_b_filter='properties["country"] == "UK"',
        )

        # Should still return a valid result structure
        assert "cohort_a" in result
        assert "cohort_b" in result

    def test_cohort_comparison_jql_returns_non_list_non_raw(
        self, mock_context: MagicMock
    ) -> None:
        """cohort_comparison should handle JQL result without .raw and not a list."""
        from mp_mcp.tools.composed.cohort import cohort_comparison

        # Return an object that is neither a list nor has .raw attribute
        jql_mock = MagicMock(spec=[])  # Empty spec = no attributes
        del jql_mock.raw  # Ensure .raw doesn't exist
        mock_context.lifespan_context["workspace"].jql.return_value = jql_mock

        result = cohort_comparison(  # type: ignore[operator]
            mock_context,
            cohort_a_filter='properties["sessions"] >= 10',
            cohort_b_filter='properties["sessions"] < 3',
            compare_dimensions=["event_frequency"],
        )

        # Should still return valid structure with empty comparisons
        assert "cohort_a" in result
        assert "cohort_b" in result
        assert "comparisons" in result

    def test_cohort_comparison_jql_returns_list_directly(
        self, mock_context: MagicMock
    ) -> None:
        """cohort_comparison should handle JQL result that is a list directly."""
        from mp_mcp.tools.composed.cohort import cohort_comparison

        # Return a plain list (no .raw attribute)
        jql_result = [
            {"key": ["login", "cohort_a"], "value": 100},
            {"key": ["login", "cohort_b"], "value": 50},
        ]
        mock_context.lifespan_context["workspace"].jql.return_value = jql_result

        result = cohort_comparison(  # type: ignore[operator]
            mock_context,
            cohort_a_filter='properties["sessions"] >= 10',
            cohort_b_filter='properties["sessions"] < 3',
            compare_dimensions=["event_frequency"],
        )

        assert "cohort_a" in result
        assert "cohort_b" in result
        assert "comparisons" in result
        # Should have processed the event data
        assert "event_frequency" in result["comparisons"]
