"""Tests for MCP prompts.

These tests verify the MCP prompts are registered correctly.
"""


class TestAnalyticsWorkflowPrompt:
    """Tests for the analytics_workflow prompt."""

    def test_analytics_workflow_prompt_registered(self) -> None:
        """analytics_workflow prompt should be registered."""
        from mp_mcp_server.server import mcp

        prompt_names = list(mcp._prompt_manager._prompts.keys())
        assert "analytics_workflow" in prompt_names


class TestFunnelAnalysisPrompt:
    """Tests for the funnel_analysis prompt."""

    def test_funnel_analysis_prompt_registered(self) -> None:
        """funnel_analysis prompt should be registered."""
        from mp_mcp_server.server import mcp

        prompt_names = list(mcp._prompt_manager._prompts.keys())
        assert "funnel_analysis" in prompt_names


class TestRetentionAnalysisPrompt:
    """Tests for the retention_analysis prompt."""

    def test_retention_analysis_prompt_registered(self) -> None:
        """retention_analysis prompt should be registered."""
        from mp_mcp_server.server import mcp

        prompt_names = list(mcp._prompt_manager._prompts.keys())
        assert "retention_analysis" in prompt_names


class TestLocalAnalysisWorkflowPrompt:
    """Tests for the local_analysis_workflow prompt."""

    def test_local_analysis_workflow_prompt_registered(self) -> None:
        """local_analysis_workflow prompt should be registered."""
        from mp_mcp_server.server import mcp

        prompt_names = list(mcp._prompt_manager._prompts.keys())
        assert "local_analysis_workflow" in prompt_names


class TestPromptFunctionality:
    """Functional tests for prompt content."""

    def test_analytics_workflow_returns_content(self) -> None:
        """analytics_workflow should return workflow guide content."""
        from mp_mcp_server.prompts import analytics_workflow

        result = str(analytics_workflow.fn())
        assert "# Mixpanel Analytics Workflow" in result
        assert "list_events" in result
        assert "segmentation" in result

    def test_funnel_analysis_returns_content(self) -> None:
        """funnel_analysis should return funnel-specific content."""
        from mp_mcp_server.prompts import funnel_analysis

        result = str(funnel_analysis.fn(funnel_name="checkout"))
        assert "checkout" in result
        assert "funnel_id" in result

    def test_retention_analysis_returns_content(self) -> None:
        """retention_analysis should return retention-specific content."""
        from mp_mcp_server.prompts import retention_analysis

        result = str(retention_analysis.fn(event="login"))
        assert "login" in result
        assert "born_event" in result
        assert "Day 7 retention" in result

    def test_local_analysis_workflow_returns_content(self) -> None:
        """local_analysis_workflow should return SQL analysis guide."""
        from mp_mcp_server.prompts import local_analysis_workflow

        result = str(local_analysis_workflow.fn())
        assert "# Local Data Analysis Workflow" in result
        assert "fetch_events" in result
        assert "SQL" in result
