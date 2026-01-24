"""Tests for MCP prompts.

These tests verify the MCP prompts are registered correctly.
"""


class TestAnalyticsWorkflowPrompt:
    """Tests for the analytics_workflow prompt."""

    def test_analytics_workflow_prompt_registered(
        self, registered_prompt_names: list[str]
    ) -> None:
        """analytics_workflow prompt should be registered."""
        assert "analytics_workflow" in registered_prompt_names


class TestFunnelAnalysisPrompt:
    """Tests for the funnel_analysis prompt."""

    def test_funnel_analysis_prompt_registered(
        self, registered_prompt_names: list[str]
    ) -> None:
        """funnel_analysis prompt should be registered."""
        assert "funnel_analysis" in registered_prompt_names


class TestRetentionAnalysisPrompt:
    """Tests for the retention_analysis prompt."""

    def test_retention_analysis_prompt_registered(
        self, registered_prompt_names: list[str]
    ) -> None:
        """retention_analysis prompt should be registered."""
        assert "retention_analysis" in registered_prompt_names


class TestLocalAnalysisWorkflowPrompt:
    """Tests for the local_analysis_workflow prompt."""

    def test_local_analysis_workflow_prompt_registered(
        self, registered_prompt_names: list[str]
    ) -> None:
        """local_analysis_workflow prompt should be registered."""
        assert "local_analysis_workflow" in registered_prompt_names


class TestPromptFunctionality:
    """Functional tests for prompt content."""

    def test_analytics_workflow_returns_content(self) -> None:
        """analytics_workflow should return workflow guide content."""
        from mp_mcp.prompts import analytics_workflow

        result = str(analytics_workflow())  # type: ignore[operator]
        assert "# Mixpanel Analytics Workflow" in result
        assert "list_events" in result
        assert "segmentation" in result

    def test_funnel_analysis_returns_content(self) -> None:
        """funnel_analysis should return funnel-specific content."""
        from mp_mcp.prompts import funnel_analysis

        result = str(funnel_analysis(funnel_name="checkout"))  # type: ignore[operator]
        assert "checkout" in result
        assert "funnel_id" in result

    def test_retention_analysis_returns_content(self) -> None:
        """retention_analysis should return retention-specific content."""
        from mp_mcp.prompts import retention_analysis

        result = str(retention_analysis(event="login"))  # type: ignore[operator]
        assert "login" in result
        assert "born_event" in result
        assert "Day 7 retention" in result

    def test_local_analysis_workflow_returns_content(self) -> None:
        """local_analysis_workflow should return SQL analysis guide."""
        from mp_mcp.prompts import local_analysis_workflow

        result = str(local_analysis_workflow())  # type: ignore[operator]
        assert "# Local Data Analysis Workflow" in result
        assert "fetch_events" in result
        assert "SQL" in result

    def test_gqm_decomposition_returns_content(self) -> None:
        """gqm_decomposition should return GQM framework content."""
        from mp_mcp.prompts import gqm_decomposition

        result = str(gqm_decomposition(goal="improve retention"))  # type: ignore[operator]
        assert "# Goal-Question-Metric (GQM) Investigation Framework" in result
        assert "improve retention" in result
        assert "Metrics" in result

    def test_gqm_decomposition_default_goal(self) -> None:
        """gqm_decomposition should use default goal."""
        from mp_mcp.prompts import gqm_decomposition

        result = str(gqm_decomposition())  # type: ignore[operator]
        assert "understand user retention" in result

    def test_growth_accounting_returns_content(self) -> None:
        """growth_accounting should return AARRR framework content."""
        from mp_mcp.prompts import growth_accounting

        result = str(growth_accounting(acquisition_event="register"))  # type: ignore[operator]
        assert "# Growth Accounting: AARRR Framework Analysis" in result
        assert "register" in result
        assert "Acquisition" in result
        assert "Retention" in result
        assert "Revenue" in result

    def test_growth_accounting_default_event(self) -> None:
        """growth_accounting should use default acquisition event."""
        from mp_mcp.prompts import growth_accounting

        result = str(growth_accounting())  # type: ignore[operator]
        assert "signup" in result

    def test_experiment_analysis_returns_content(self) -> None:
        """experiment_analysis should return A/B test guidance."""
        from mp_mcp.prompts import experiment_analysis

        result = str(experiment_analysis(experiment_name="button_color_test"))  # type: ignore[operator]
        assert "# A/B Test Analysis: button_color_test" in result
        assert "Statistical significance" in result
        assert "control" in result
        assert "treatment" in result

    def test_experiment_analysis_default_name(self) -> None:
        """experiment_analysis should use default experiment name."""
        from mp_mcp.prompts import experiment_analysis

        result = str(experiment_analysis())  # type: ignore[operator]
        assert "homepage_redesign" in result

    def test_data_quality_audit_returns_content(self) -> None:
        """data_quality_audit should return audit checklist."""
        from mp_mcp.prompts import data_quality_audit

        result = str(data_quality_audit(event="purchase"))  # type: ignore[operator]
        assert "# Data Quality Audit: purchase" in result
        assert "purchase" in result
        assert "Coverage" in result
        assert "Completeness" in result

    def test_data_quality_audit_default_event(self) -> None:
        """data_quality_audit should use default event."""
        from mp_mcp.prompts import data_quality_audit

        result = str(data_quality_audit())  # type: ignore[operator]
        assert "signup" in result


class TestAllPromptsRegistered:
    """Verify all prompts are registered with MCP server."""

    def test_gqm_decomposition_registered(
        self, registered_prompt_names: list[str]
    ) -> None:
        """gqm_decomposition should be registered."""
        assert "gqm_decomposition" in registered_prompt_names

    def test_growth_accounting_registered(
        self, registered_prompt_names: list[str]
    ) -> None:
        """growth_accounting should be registered."""
        assert "growth_accounting" in registered_prompt_names

    def test_experiment_analysis_registered(
        self, registered_prompt_names: list[str]
    ) -> None:
        """experiment_analysis should be registered."""
        assert "experiment_analysis" in registered_prompt_names

    def test_data_quality_audit_registered(
        self, registered_prompt_names: list[str]
    ) -> None:
        """data_quality_audit should be registered."""
        assert "data_quality_audit" in registered_prompt_names
