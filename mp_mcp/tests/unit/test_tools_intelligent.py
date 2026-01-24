"""Tests for intelligent analytics tools.

These tests verify the ask_mixpanel, diagnose_metric_drop,
and funnel_optimization_report tools work correctly.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestAskMixpanelHelpers:
    """Tests for ask_mixpanel helper functions."""

    def test_get_default_date_range(self) -> None:
        """_get_default_date_range should return valid dates."""
        from mp_mcp.tools.intelligent.ask import _get_default_date_range

        from_date, to_date = _get_default_date_range()
        assert from_date < to_date
        assert len(from_date) == 10  # YYYY-MM-DD format

    def test_get_default_date_range_custom_days(self) -> None:
        """_get_default_date_range should accept custom days."""
        from mp_mcp.tools.intelligent.ask import _get_default_date_range

        from_date, to_date = _get_default_date_range(days_back=7)
        assert from_date < to_date

    def test_get_available_events(self, mock_context: MagicMock) -> None:
        """_get_available_events should return event list."""
        from mp_mcp.tools.intelligent.ask import _get_available_events

        events = _get_available_events(mock_context)
        assert events == ["signup", "login", "purchase"]

    def test_get_available_events_with_limit(self, mock_context: MagicMock) -> None:
        """_get_available_events should respect limit."""
        from mp_mcp.tools.intelligent.ask import _get_available_events

        events = _get_available_events(mock_context, limit=2)
        assert len(events) <= 2

    def test_execute_queries(self, mock_context: MagicMock) -> None:
        """_execute_queries should execute plan queries."""
        from mp_mcp.tools.intelligent.ask import _execute_queries
        from mp_mcp.types import ExecutionPlan, QuerySpec

        plan = ExecutionPlan(
            intent="Test",
            query_type="trend",
            queries=[
                QuerySpec(
                    method="segmentation",
                    params={
                        "event": "signup",
                        "from_date": "2024-01-01",
                        "to_date": "2024-01-31",
                    },
                ),
            ],
            date_range={"from_date": "2024-01-01", "to_date": "2024-01-31"},
        )

        results = _execute_queries(mock_context, plan)
        assert "query_0_segmentation" in results

    def test_execute_queries_handles_errors(self, mock_context: MagicMock) -> None:
        """_execute_queries should handle query errors gracefully."""
        from mp_mcp.tools.intelligent.ask import _execute_queries
        from mp_mcp.types import ExecutionPlan, QuerySpec

        # Make segmentation raise an error
        mock_context.lifespan_context[
            "workspace"
        ].segmentation.side_effect = ValueError("Query failed")

        plan = ExecutionPlan(
            intent="Test",
            query_type="trend",
            queries=[
                QuerySpec(
                    method="segmentation",
                    params={"event": "signup"},
                ),
            ],
            date_range={"from_date": "2024-01-01", "to_date": "2024-01-31"},
        )

        results = _execute_queries(mock_context, plan)
        assert "error" in results["query_0_segmentation"]


class TestAskMixpanelTool:
    """Tests for the ask_mixpanel tool."""

    def test_tool_registered(self, registered_tool_names: list[str]) -> None:
        """ask_mixpanel tool should be registered."""
        assert "ask_mixpanel" in registered_tool_names

    @pytest.mark.asyncio
    async def test_ask_mixpanel_sampling_unavailable(
        self, mock_context: MagicMock
    ) -> None:
        """ask_mixpanel should handle sampling being unavailable."""
        from mp_mcp.tools.intelligent.ask import ask_mixpanel

        # Make sample raise an error indicating it's not supported
        mock_context.sample = AsyncMock(side_effect=Exception("Sampling not supported"))

        result = await ask_mixpanel(  # type: ignore[operator]
            mock_context,
            question="What events are most popular?",
        )

        assert result["status"] == "sampling_unavailable"
        assert "analysis_hints" in result


class TestDiagnoseHelpers:
    """Tests for diagnose_metric_drop helper functions."""

    def test_calculate_date_range(self) -> None:
        """_calculate_date_range should calculate baseline period."""
        from mp_mcp.tools.intelligent.diagnose import _calculate_date_range

        from_date, to_date = _calculate_date_range("2024-01-10", days_before=7)
        assert from_date == "2024-01-03"
        assert to_date == "2024-01-09"

    def test_gather_diagnosis_data(self, mock_context: MagicMock) -> None:
        """_gather_diagnosis_data should collect baseline and drop data."""
        from mp_mcp.tools.intelligent.diagnose import _gather_diagnosis_data

        data = _gather_diagnosis_data(
            mock_context,
            event="signup",
            date="2024-01-10",
        )

        assert "baseline_data" in data
        assert "drop_data" in data
        assert "segment_data" in data
        assert "baseline_period" in data
        assert "drop_period" in data

    def test_build_synthesis_prompt(self) -> None:
        """_build_synthesis_prompt should format prompt correctly."""
        from mp_mcp.tools.intelligent.diagnose import _build_synthesis_prompt

        raw_data = {
            "baseline_data": {"total": 1000},
            "drop_data": {"total": 500},
            "segment_data": {},
        }

        prompt = _build_synthesis_prompt("signup", "2024-01-10", raw_data)

        assert "signup" in prompt
        assert "2024-01-10" in prompt
        assert "baseline" in prompt.lower()

    def test_parse_synthesis_result_valid_json(self) -> None:
        """_parse_synthesis_result should parse valid JSON."""
        from mp_mcp.tools.intelligent.diagnose import _parse_synthesis_result

        json_text = """{
            "drop_confirmed": true,
            "drop_percentage": -25.5,
            "primary_driver": {
                "dimension": "browser",
                "segment": "Chrome",
                "contribution_pct": 65.0,
                "baseline_value": 1000,
                "current_value": 650,
                "description": "Chrome users dropped"
            },
            "secondary_factors": [],
            "recommendations": ["Check Chrome issues"],
            "confidence": "high",
            "caveats": []
        }"""

        result = _parse_synthesis_result(json_text)

        assert result.drop_confirmed is True
        assert result.drop_percentage == -25.5
        assert result.primary_driver is not None
        assert result.primary_driver.dimension == "browser"

    def test_parse_synthesis_result_markdown_json(self) -> None:
        """_parse_synthesis_result should handle markdown code blocks."""
        from mp_mcp.tools.intelligent.diagnose import _parse_synthesis_result

        markdown_text = """Here's my analysis:

```json
{
    "drop_confirmed": false,
    "drop_percentage": -5.0,
    "primary_driver": null,
    "secondary_factors": [],
    "recommendations": ["No action needed"],
    "confidence": "medium",
    "caveats": ["Small sample size"]
}
```
"""

        result = _parse_synthesis_result(markdown_text)
        assert result.drop_confirmed is False


class TestDiagnoseMetricDropTool:
    """Tests for the diagnose_metric_drop tool."""

    def test_tool_registered(self, registered_tool_names: list[str]) -> None:
        """diagnose_metric_drop tool should be registered."""
        assert "diagnose_metric_drop" in registered_tool_names

    @pytest.mark.asyncio
    async def test_diagnose_sampling_unavailable(self, mock_context: MagicMock) -> None:
        """diagnose_metric_drop should degrade when sampling unavailable."""
        from mp_mcp.tools.intelligent.diagnose import diagnose_metric_drop

        mock_context.sample = AsyncMock(side_effect=Exception("Sampling not supported"))

        result = await diagnose_metric_drop(  # type: ignore[operator]
            mock_context,
            event="signup",
            date="2024-01-10",
        )

        assert result["status"] == "sampling_unavailable"
        assert "raw_data" in result
        assert "analysis_hints" in result


class TestFunnelReportHelpers:
    """Tests for funnel_optimization_report helper functions."""

    def test_get_default_date_range(self) -> None:
        """_get_default_date_range should return valid dates."""
        from mp_mcp.tools.intelligent.funnel_report import (
            _get_default_date_range,
        )

        from_date, to_date = _get_default_date_range()
        assert from_date < to_date

    def test_analyze_funnel_steps(self, mock_context: MagicMock) -> None:
        """analyze_funnel_steps should analyze funnel data."""
        from mp_mcp.tools.intelligent.funnel_report import analyze_funnel_steps

        # Set up mock funnel response
        mock_context.lifespan_context["workspace"].funnel.return_value = MagicMock(
            to_dict=lambda: {
                "data": {
                    "steps": [
                        {"event": "signup", "count": 1000},
                        {"event": "onboarding", "count": 600},
                        {"event": "activation", "count": 300},
                    ]
                }
            }
        )

        result = analyze_funnel_steps(
            mock_context,
            funnel_id=123,
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert "steps" in result
        assert "overall_conversion" in result
        assert "bottleneck" in result
        assert len(result["steps"]) == 3


class TestFunnelOptimizationReportTool:
    """Tests for the funnel_optimization_report tool."""

    def test_tool_registered(self, registered_tool_names: list[str]) -> None:
        """funnel_optimization_report tool should be registered."""
        assert "funnel_optimization_report" in registered_tool_names

    @pytest.mark.asyncio
    async def test_funnel_report_sampling_unavailable(
        self, mock_context: MagicMock
    ) -> None:
        """funnel_optimization_report should degrade when sampling unavailable."""
        from mp_mcp.tools.intelligent.funnel_report import (
            funnel_optimization_report,
        )

        mock_context.sample = AsyncMock(side_effect=Exception("Sampling not supported"))

        # Set up mock funnel response
        mock_context.lifespan_context["workspace"].funnel.return_value = MagicMock(
            to_dict=lambda: {
                "data": {
                    "steps": [
                        {"event": "signup", "count": 1000},
                        {"event": "activation", "count": 500},
                    ]
                }
            }
        )

        result = await funnel_optimization_report(  # type: ignore[operator]
            mock_context,
            funnel_id=123,
        )

        assert result["status"] == "partial"
        assert "raw_data" in result
        assert "analysis_hints" in result


class TestAskMixpanelExecutionPlan:
    """Tests for execution plan generation and query execution."""

    def test_execute_queries_unknown_method(self, mock_context: MagicMock) -> None:
        """_execute_queries should handle unknown methods gracefully."""
        from mp_mcp.tools.intelligent.ask import _execute_queries
        from mp_mcp.types import ExecutionPlan, QuerySpec

        # Configure workspace to return None for unknown method (not default MagicMock)
        mock_context.lifespan_context["workspace"].unknown_method = None

        plan = ExecutionPlan(
            intent="Test",
            query_type="trend",
            queries=[
                QuerySpec(
                    method="unknown_method",  # type: ignore[arg-type]
                    params={"event": "signup"},
                ),
            ],
            date_range={"from_date": "2024-01-01", "to_date": "2024-01-31"},
        )

        results = _execute_queries(mock_context, plan)
        assert "error" in results["query_0_unknown_method"]
        assert "Unknown method" in results["query_0_unknown_method"]["error"]

    def test_execute_queries_with_raw_result(self, mock_context: MagicMock) -> None:
        """_execute_queries should handle results with raw attribute."""
        from mp_mcp.tools.intelligent.ask import _execute_queries
        from mp_mcp.types import ExecutionPlan, QuerySpec

        # Set up mock with raw attribute
        raw_result = MagicMock()
        raw_result.raw = [{"user": "test", "count": 5}]
        del raw_result.to_dict  # Remove to_dict so it uses raw
        mock_context.lifespan_context["workspace"].jql.return_value = raw_result

        plan = ExecutionPlan(
            intent="Test",
            query_type="trend",
            queries=[
                QuerySpec(
                    method="jql",
                    params={"script": "test"},
                ),
            ],
            date_range={"from_date": "2024-01-01", "to_date": "2024-01-31"},
        )

        results = _execute_queries(mock_context, plan)
        assert results["query_0_jql"] == [{"user": "test", "count": 5}]

    def test_get_available_events_handles_error(self, mock_context: MagicMock) -> None:
        """_get_available_events should return empty list on error."""
        from mp_mcp.tools.intelligent.ask import _get_available_events

        mock_context.lifespan_context["workspace"].events.side_effect = Exception(
            "API error"
        )

        events = _get_available_events(mock_context)
        assert events == []


class TestAskMixpanelSynthesis:
    """Tests for ask_mixpanel synthesis and error handling."""

    @pytest.mark.asyncio
    async def test_ask_mixpanel_plan_generation_error(
        self, mock_context: MagicMock
    ) -> None:
        """ask_mixpanel should handle plan generation errors."""
        from mp_mcp.tools.intelligent.ask import ask_mixpanel

        # Make sample raise a general error
        mock_context.sample = AsyncMock(
            side_effect=ValueError("Plan generation failed")
        )

        result = await ask_mixpanel(  # type: ignore[operator]
            mock_context,
            question="What events are most popular?",
        )

        assert result["status"] == "error"
        assert "Plan generation failed" in result["message"]

    @pytest.mark.asyncio
    async def test_ask_mixpanel_synthesis_error(self, mock_context: MagicMock) -> None:
        """ask_mixpanel should handle synthesis errors gracefully."""
        from mp_mcp.tools.intelligent.ask import ask_mixpanel

        # First sample call succeeds (plan generation), second fails (synthesis)
        plan_result = MagicMock()
        plan_result.text = """{
            "intent": "Find popular events",
            "query_type": "trend",
            "queries": [{"method": "segmentation", "params": {"event": "login", "from_date": "2024-01-01", "to_date": "2024-01-31"}}],
            "date_range": {"from_date": "2024-01-01", "to_date": "2024-01-31"},
            "comparison_needed": false,
            "reasoning": "test"
        }"""
        synthesis_error = ValueError("Synthesis failed")
        mock_context.sample = AsyncMock(side_effect=[plan_result, synthesis_error])

        result = await ask_mixpanel(  # type: ignore[operator]
            mock_context,
            question="What events are most popular?",
        )

        assert result["status"] == "partial"
        assert "plan" in result
        assert "results" in result


class TestGenerateExecutionPlanParsing:
    """Tests for _generate_execution_plan parsing edge cases."""

    @pytest.mark.asyncio
    async def test_generate_plan_empty_response(self, mock_context: MagicMock) -> None:
        """_generate_execution_plan should raise error on empty LLM response."""
        from mp_mcp.tools.intelligent.ask import _generate_execution_plan

        mock_context.sample = AsyncMock(return_value=MagicMock(text=None))

        with pytest.raises(ValueError, match="LLM returned empty response"):
            await _generate_execution_plan(mock_context, "What events are popular?")

    @pytest.mark.asyncio
    async def test_generate_plan_json_code_block(self, mock_context: MagicMock) -> None:
        """_generate_execution_plan should parse JSON from ```json code blocks."""
        from mp_mcp.tools.intelligent.ask import _generate_execution_plan

        mock_response = MagicMock()
        mock_response.text = """Here's the plan:
```json
{
    "intent": "Find popular events",
    "query_type": "trend",
    "queries": [{"method": "segmentation", "params": {"event": "login"}}],
    "date_range": {"from_date": "2024-01-01", "to_date": "2024-01-31"}
}
```
"""
        mock_context.sample = AsyncMock(return_value=mock_response)

        plan = await _generate_execution_plan(mock_context, "What events are popular?")

        assert plan.intent == "Find popular events"
        assert plan.query_type == "trend"

    @pytest.mark.asyncio
    async def test_generate_plan_plain_code_block(
        self, mock_context: MagicMock
    ) -> None:
        """_generate_execution_plan should parse JSON from plain ``` code blocks."""
        from mp_mcp.tools.intelligent.ask import _generate_execution_plan

        mock_response = MagicMock()
        mock_response.text = """Here's the plan:
```
{
    "intent": "Analyze retention",
    "query_type": "retention",
    "queries": [{"method": "retention", "params": {"born_event": "signup"}}],
    "date_range": {"from_date": "2024-01-01", "to_date": "2024-01-31"}
}
```
"""
        mock_context.sample = AsyncMock(return_value=mock_response)

        plan = await _generate_execution_plan(mock_context, "What's user retention?")

        assert plan.intent == "Analyze retention"
        assert plan.query_type == "retention"


class TestDiagnoseSegmentData:
    """Tests for segment data gathering in diagnose_metric_drop."""

    def test_gather_diagnosis_data_with_custom_dimensions(
        self, mock_context: MagicMock
    ) -> None:
        """_gather_diagnosis_data should accept custom dimensions."""
        from mp_mcp.tools.intelligent.diagnose import _gather_diagnosis_data

        data = _gather_diagnosis_data(
            mock_context,
            event="signup",
            date="2024-01-10",
            dimensions=["$browser", "$os"],
        )

        assert "segment_data" in data
        assert "$browser" in data["segment_data"]
        assert "$os" in data["segment_data"]

    def test_gather_diagnosis_data_handles_query_errors(
        self, mock_context: MagicMock
    ) -> None:
        """_gather_diagnosis_data should handle query errors gracefully."""
        from mp_mcp.tools.intelligent.diagnose import _gather_diagnosis_data

        mock_context.lifespan_context["workspace"].segmentation.side_effect = Exception(
            "API error"
        )

        data = _gather_diagnosis_data(
            mock_context,
            event="signup",
            date="2024-01-10",
        )

        assert "error" in data["baseline_data"]
        assert "error" in data["drop_data"]

    def test_gather_diagnosis_data_handles_property_counts_error(
        self, mock_context: MagicMock
    ) -> None:
        """_gather_diagnosis_data should skip dimensions when property_counts fails."""
        from mp_mcp.tools.intelligent.diagnose import _gather_diagnosis_data

        # Segmentation works but property_counts fails
        mock_context.lifespan_context[
            "workspace"
        ].property_counts.side_effect = Exception("Property not found")

        data = _gather_diagnosis_data(
            mock_context,
            event="signup",
            date="2024-01-10",
            dimensions=["$browser", "$os"],
        )

        # Should succeed overall, but segment_data should be empty
        assert "baseline_data" in data
        assert "drop_data" in data
        assert "segment_data" in data
        # No dimensions captured since property_counts failed
        assert data["segment_data"] == {}


class TestDiagnoseParseResults:
    """Tests for parsing diagnosis synthesis results."""

    def test_parse_synthesis_result_with_secondary_factors(self) -> None:
        """_parse_synthesis_result should parse secondary factors."""
        from mp_mcp.tools.intelligent.diagnose import _parse_synthesis_result

        json_text = """{
            "drop_confirmed": true,
            "drop_percentage": -25.5,
            "primary_driver": {
                "dimension": "browser",
                "segment": "Chrome",
                "contribution_pct": 65.0,
                "baseline_value": 1000,
                "current_value": 650,
                "description": "Chrome dropped"
            },
            "secondary_factors": [
                {
                    "dimension": "os",
                    "segment": "Windows",
                    "contribution_pct": 15.0,
                    "baseline_value": 500,
                    "current_value": 425,
                    "description": "Windows dropped"
                }
            ],
            "recommendations": ["Check Chrome", "Check Windows"],
            "confidence": "high",
            "caveats": ["Limited data"]
        }"""

        result = _parse_synthesis_result(json_text)

        assert result.drop_confirmed is True
        assert len(result.secondary_factors) == 1
        assert result.secondary_factors[0].dimension == "os"
        assert len(result.caveats) == 1

    def test_parse_synthesis_result_plain_code_block(self) -> None:
        """_parse_synthesis_result should handle plain code blocks."""
        from mp_mcp.tools.intelligent.diagnose import _parse_synthesis_result

        markdown_text = """Analysis:

```
{
    "drop_confirmed": true,
    "drop_percentage": -10.0,
    "primary_driver": null,
    "secondary_factors": [],
    "recommendations": [],
    "confidence": "low",
    "caveats": []
}
```
"""

        result = _parse_synthesis_result(markdown_text)
        assert result.drop_confirmed is True
        assert result.drop_percentage == -10.0


class TestFunnelReportSegmentation:
    """Tests for funnel segment analysis."""

    def test_segment_funnel_performance(self, mock_context: MagicMock) -> None:
        """segment_funnel_performance should analyze segments."""
        from mp_mcp.tools.intelligent.funnel_report import (
            segment_funnel_performance,
        )

        # Set up mock segmented funnel response
        mock_context.lifespan_context["workspace"].funnel.return_value = MagicMock(
            to_dict=lambda: {
                "data": {
                    "Chrome": {
                        "steps": [
                            {"event": "signup", "count": 1000},
                            {"event": "activation", "count": 500},
                        ]
                    },
                    "Firefox": {
                        "steps": [
                            {"event": "signup", "count": 500},
                            {"event": "activation", "count": 200},
                        ]
                    },
                }
            }
        )

        result = segment_funnel_performance(
            mock_context,
            funnel_id=123,
            from_date="2024-01-01",
            to_date="2024-01-31",
            segment_properties=["$browser"],
        )

        assert "top_segments" in result
        assert "underperforming_segments" in result

    def test_segment_funnel_performance_handles_errors(
        self, mock_context: MagicMock
    ) -> None:
        """segment_funnel_performance should handle segment errors."""
        from mp_mcp.tools.intelligent.funnel_report import (
            segment_funnel_performance,
        )

        mock_context.lifespan_context["workspace"].funnel.side_effect = Exception(
            "API error"
        )

        result = segment_funnel_performance(
            mock_context,
            funnel_id=123,
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["top_segments"] == []
        assert result["underperforming_segments"] == []


class TestFunnelReportRecommendations:
    """Tests for funnel optimization recommendations."""

    def test_generate_default_recommendations(self) -> None:
        """_generate_default_recommendations should create actionable items."""
        from mp_mcp.tools.intelligent.funnel_report import (
            _generate_default_recommendations,
        )

        bottleneck = {
            "step_name": "checkout",
            "drop_percentage": 0.5,
        }
        top_segments = [
            {"segment": "Chrome", "property": "$browser", "conversion_rate": 0.8}
        ]
        underperforming = [
            {"segment": "Safari", "property": "$browser", "conversion_rate": 0.2}
        ]

        recommendations = _generate_default_recommendations(
            bottleneck, top_segments, underperforming
        )

        assert len(recommendations) > 0
        assert any("checkout" in r.action for r in recommendations)
        assert any("Chrome" in r.action for r in recommendations)

    def test_generate_default_recommendations_no_bottleneck(self) -> None:
        """_generate_default_recommendations should handle missing bottleneck."""
        from mp_mcp.tools.intelligent.funnel_report import (
            _generate_default_recommendations,
        )

        recommendations = _generate_default_recommendations({}, [], [])

        # Should still return generic recommendations
        assert len(recommendations) > 0


class TestFunnelAnalysisFormats:
    """Tests for different funnel data format handling."""

    def test_analyze_funnel_steps_alternative_format(
        self, mock_context: MagicMock
    ) -> None:
        """analyze_funnel_steps should handle alternative analysis format."""
        from mp_mcp.tools.intelligent.funnel_report import analyze_funnel_steps

        # Mock funnel response with alternative "analysis" format
        mock_context.lifespan_context["workspace"].funnel.return_value = MagicMock(
            to_dict=lambda: {
                "data": {
                    "analysis": {
                        "steps": [
                            {"event": "view_page", "count": 1000},
                            {"event": "add_to_cart", "count": 400},
                            {"event": "checkout", "count": 100},
                        ]
                    }
                }
            }
        )

        result = analyze_funnel_steps(
            mock_context,
            funnel_id=123,
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert len(result["steps"]) == 3
        assert result["steps"][0]["step_name"] == "view_page"
        assert result["bottleneck"] is not None

    def test_analyze_funnel_steps_empty_steps(self, mock_context: MagicMock) -> None:
        """analyze_funnel_steps should handle empty steps gracefully."""
        from mp_mcp.tools.intelligent.funnel_report import analyze_funnel_steps

        mock_context.lifespan_context["workspace"].funnel.return_value = MagicMock(
            to_dict=lambda: {"data": {"steps": []}}
        )

        result = analyze_funnel_steps(
            mock_context,
            funnel_id=123,
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert result["steps"] == []
        assert result["overall_conversion"] == 0.0

    def test_analyze_funnel_steps_with_data_steps(
        self, mock_context: MagicMock
    ) -> None:
        """analyze_funnel_steps should handle data.steps format."""
        from mp_mcp.tools.intelligent.funnel_report import analyze_funnel_steps

        # Mock funnel response with standard "data.steps" format
        mock_context.lifespan_context["workspace"].funnel.return_value = MagicMock(
            to_dict=lambda: {
                "data": {
                    "steps": [
                        {"event": "signup", "count": 1000},
                        {"event": "activation", "count": 500},
                        {"event": "purchase", "count": 100},
                    ]
                }
            }
        )

        result = analyze_funnel_steps(
            mock_context,
            funnel_id=123,
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        assert len(result["steps"]) == 3
        assert result["overall_conversion"] == 0.1  # 100/1000

    def test_segment_funnel_performance_multiple_segments(
        self, mock_context: MagicMock
    ) -> None:
        """segment_funnel_performance should handle multiple segment properties."""
        from mp_mcp.tools.intelligent.funnel_report import (
            segment_funnel_performance,
        )

        result = segment_funnel_performance(
            mock_context,
            funnel_id=123,
            from_date="2024-01-01",
            to_date="2024-01-31",
            segment_properties=["$browser", "$os", "$country_code"],
        )

        # Should process all segment properties
        assert "top_segments" in result
        assert "underperforming_segments" in result
