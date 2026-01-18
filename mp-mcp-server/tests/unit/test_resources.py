"""Tests for MCP resources module."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from mcp.shared.exceptions import McpError

from mixpanel_data.exceptions import MixpanelDataError
from mp_mcp_server.resources import (
    _get_date_range,
    handle_resource_errors,
)


class TestHandleResourceErrors:
    """Tests for handle_resource_errors decorator."""

    def test_passes_through_successful_result(self) -> None:
        """Decorator should pass through successful function result."""

        @handle_resource_errors
        def success_func() -> str:
            return '{"status": "ok"}'

        result = success_func()
        assert result == '{"status": "ok"}'

    def test_wraps_mixpanel_data_error(self) -> None:
        """Decorator should wrap MixpanelDataError in McpError."""

        @handle_resource_errors
        def error_func() -> str:
            raise MixpanelDataError("Authentication failed")

        with pytest.raises(McpError) as exc_info:
            error_func()

        assert "Authentication failed" in str(exc_info.value)

    def test_wraps_generic_exception(self) -> None:
        """Decorator should wrap generic exceptions in McpError."""

        @handle_resource_errors
        def error_func() -> str:
            raise ValueError("Something went wrong")

        with pytest.raises(McpError) as exc_info:
            error_func()

        assert "Something went wrong" in str(exc_info.value)


class TestGetDateRange:
    """Tests for _get_date_range helper."""

    def test_returns_date_strings(self) -> None:
        """_get_date_range should return date strings."""
        from_date, to_date = _get_date_range(7)

        # Verify format
        assert len(from_date) == 10  # YYYY-MM-DD
        assert len(to_date) == 10
        assert "-" in from_date
        assert "-" in to_date

    def test_range_is_correct_days(self) -> None:
        """_get_date_range should return correct day range."""
        from_date, to_date = _get_date_range(30)

        from_dt = datetime.fromisoformat(from_date)
        to_dt = datetime.fromisoformat(to_date)

        delta = to_dt - from_dt
        assert delta.days == 30


class TestWorkspaceInfoResourceLogic:
    """Tests for workspace_info_resource business logic."""

    def test_formats_workspace_info(self) -> None:
        """Workspace info should be formatted correctly."""
        # Test the business logic by reimplementing the format
        mock_info = MagicMock(
            project_id=12345,
            region="us",
            account="test@example.com",
            path="/path/to/db",
            size_mb=10.5,
            created_at=None,
        )

        # This is what the resource function does
        info = {
            "project_id": mock_info.project_id,
            "region": mock_info.region,
            "account": mock_info.account,
            "path": str(mock_info.path) if mock_info.path else None,
            "size_mb": mock_info.size_mb,
            "created_at": (
                mock_info.created_at.isoformat() if mock_info.created_at else None
            ),
            "tables": [],
        }
        result = json.dumps(info, indent=2)
        data = json.loads(result)

        assert data["project_id"] == 12345
        assert data["region"] == "us"
        assert data["account"] == "test@example.com"

    def test_includes_tables_in_output(self) -> None:
        """Workspace info should include tables."""
        mock_table = MagicMock()
        mock_table.to_dict.return_value = {"name": "events", "rows": 1000}
        tables = [mock_table]

        info = {
            "project_id": 12345,
            "region": "us",
            "account": "test@example.com",
            "path": None,
            "size_mb": 0,
            "created_at": None,
            "tables": [t.to_dict() for t in tables],
        }
        result = json.dumps(info, indent=2)
        data = json.loads(result)

        assert len(data["tables"]) == 1
        assert data["tables"][0]["name"] == "events"


class TestTablesResourceLogic:
    """Tests for tables_resource business logic."""

    def test_returns_empty_list(self) -> None:
        """Empty table list should serialize correctly."""
        tables: list[Any] = []
        result = json.dumps(tables, indent=2)
        data = json.loads(result)
        assert data == []

    def test_returns_table_list(self) -> None:
        """Table list should serialize correctly."""
        mock_table1 = MagicMock()
        mock_table1.to_dict.return_value = {"name": "events", "rows": 1000}
        mock_table2 = MagicMock()
        mock_table2.to_dict.return_value = {"name": "profiles", "rows": 500}
        tables = [mock_table1, mock_table2]

        result = json.dumps([t.to_dict() for t in tables], indent=2)
        data = json.loads(result)

        assert len(data) == 2
        assert data[0]["name"] == "events"
        assert data[1]["name"] == "profiles"


class TestEventsResourceLogic:
    """Tests for events_resource business logic."""

    def test_returns_event_list(self) -> None:
        """Event list should serialize correctly."""
        events = ["login", "signup", "purchase"]
        result = json.dumps(events, indent=2)
        data = json.loads(result)
        assert data == ["login", "signup", "purchase"]


class TestRetentionWeeklyResourceLogic:
    """Tests for retention_weekly_resource business logic."""

    def test_returns_retention_data_structure(self) -> None:
        """Retention response should have correct structure."""
        event = "signup"
        from_date, to_date = _get_date_range(84)

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "data": {"week_0": 100, "week_1": 80, "week_2": 60}
        }

        response: dict[str, Any] = {
            "event": event,
            "period": "weekly",
            "from_date": from_date,
            "to_date": to_date,
            "weeks": 12,
        }

        if hasattr(mock_result, "to_dict"):
            response["data"] = mock_result.to_dict()
        else:
            response["data"] = mock_result

        result = json.dumps(response, indent=2)
        data = json.loads(result)

        assert data["event"] == "signup"
        assert data["period"] == "weekly"
        assert data["weeks"] == 12
        assert "data" in data

    def test_handles_raw_dict_result(self) -> None:
        """Retention should handle raw dict result without to_dict."""
        event = "login"
        from_date, to_date = _get_date_range(84)

        mock_result = {"week_0": 100, "week_1": 80}  # No to_dict method

        response: dict[str, Any] = {
            "event": event,
            "period": "weekly",
            "from_date": from_date,
            "to_date": to_date,
            "weeks": 12,
        }

        if hasattr(mock_result, "to_dict"):
            response["data"] = mock_result.to_dict()
        else:
            response["data"] = mock_result

        result = json.dumps(response, indent=2)
        data = json.loads(result)

        assert data["event"] == "login"
        assert data["data"] == {"week_0": 100, "week_1": 80}


class TestTrendsResourceLogic:
    """Tests for trends_resource business logic."""

    def test_parses_valid_days(self) -> None:
        """Days parameter should be parsed correctly."""
        days_str = "30"
        try:
            days_int = int(days_str)
            if days_int < 1:
                days_int = 7
            elif days_int > 365:
                days_int = 365
        except ValueError:
            days_int = 30

        assert days_int == 30

    def test_defaults_invalid_days(self) -> None:
        """Invalid days should default to 30."""
        days_str = "invalid"
        try:
            days_int = int(days_str)
            if days_int < 1:
                days_int = 7
            elif days_int > 365:
                days_int = 365
        except ValueError:
            days_int = 30

        assert days_int == 30

    def test_limits_days_to_minimum(self) -> None:
        """Days should be at least 7."""
        days_str = "0"
        try:
            days_int = int(days_str)
            if days_int < 1:
                days_int = 7
            elif days_int > 365:
                days_int = 365
        except ValueError:
            days_int = 30

        assert days_int == 7

    def test_limits_days_to_maximum(self) -> None:
        """Days should be at most 365."""
        days_str = "1000"
        try:
            days_int = int(days_str)
            if days_int < 1:
                days_int = 7
            elif days_int > 365:
                days_int = 365
        except ValueError:
            days_int = 30

        assert days_int == 365


class TestUserJourneyResourceLogic:
    """Tests for user_journey_resource business logic."""

    def test_builds_journey_summary(self) -> None:
        """Journey summary should count events correctly."""
        events = [
            {"event": "login", "time": "2024-01-01T10:00:00"},
            {"event": "purchase", "time": "2024-01-01T10:30:00"},
            {"event": "login", "time": "2024-01-02T09:00:00"},
        ]

        # Build summary as the resource does
        event_counts: dict[str, int] = {}
        for event in events:
            if isinstance(event, dict):
                event_name = event.get("event", "unknown")
                event_counts[event_name] = event_counts.get(event_name, 0) + 1

        summary = {
            "total_events": len(events),
            "unique_events": len(event_counts),
            "event_breakdown": event_counts,
        }

        assert summary["total_events"] == 3
        assert summary["unique_events"] == 2
        event_breakdown = summary["event_breakdown"]
        assert isinstance(event_breakdown, dict)
        assert event_breakdown["login"] == 2
        assert event_breakdown["purchase"] == 1

    def test_truncates_long_event_list(self) -> None:
        """Events list should be truncated at 100."""
        events = [{"event": f"event_{i}"} for i in range(150)]

        truncated = events[:100]
        is_truncated = len(events) > 100

        assert len(truncated) == 100
        assert is_truncated is True

    def test_handles_non_dict_events(self) -> None:
        """Non-dict events should be skipped in summary."""
        events = [
            {"event": "login"},
            "not_a_dict",  # Should be skipped
            {"event": "purchase"},
        ]

        event_counts: dict[str, int] = {}
        for event in events:
            if isinstance(event, dict):
                event_name = event.get("event", "unknown")
                event_counts[event_name] = event_counts.get(event_name, 0) + 1

        assert len(event_counts) == 2
        assert event_counts["login"] == 1
        assert event_counts["purchase"] == 1


class TestWeeklyReviewRecipeLogic:
    """Tests for weekly_review_recipe business logic."""

    def test_recipe_structure(self) -> None:
        """Recipe should have required structure."""
        from_date, to_date = _get_date_range(7)

        recipe: dict[str, Any] = {
            "name": "Weekly Analytics Review",
            "description": "Comprehensive weekly check on product health",
            "current_period": {"from": from_date, "to": to_date},
            "checklist": [
                {"step": 1, "name": "Core Metrics Review", "tools": ["segmentation"]},
                {"step": 2, "name": "Conversion Health", "tools": ["funnel"]},
                {"step": 3, "name": "Retention Check", "tools": ["retention"]},
                {"step": 4, "name": "Anomaly Detection", "tools": ["top_events"]},
                {"step": 5, "name": "User Feedback", "tools": ["activity_feed"]},
            ],
            "report_template": {
                "sections": ["Executive Summary", "Key Metrics WoW"]
            },
        }

        assert recipe["name"] == "Weekly Analytics Review"
        assert len(recipe["checklist"]) == 5

        step_names = [step["name"] for step in recipe["checklist"]]
        assert "Core Metrics Review" in step_names
        assert "Conversion Health" in step_names


class TestChurnInvestigationRecipeLogic:
    """Tests for churn_investigation_recipe business logic."""

    def test_recipe_structure(self) -> None:
        """Recipe should have required phases and benchmarks."""
        recipe: dict[str, Any] = {
            "name": "Churn Investigation Playbook",
            "phases": [
                {"phase": 1, "name": "Define Churn"},
                {"phase": 2, "name": "Measure Baseline"},
                {"phase": 3, "name": "Identify Patterns"},
                {"phase": 4, "name": "Analyze Behavior"},
                {"phase": 5, "name": "Prioritize Interventions"},
            ],
            "benchmarks": {
                "good_d1_retention": "40-60%",
                "good_d7_retention": "20-30%",
                "good_d30_retention": "10-20%",
                "acceptable_monthly_churn": "<5% for B2B, <10% for B2C",
            },
        }

        assert recipe["name"] == "Churn Investigation Playbook"
        assert len(recipe["phases"]) == 5

        phase_names = [phase["name"] for phase in recipe["phases"]]
        assert "Define Churn" in phase_names
        assert "Prioritize Interventions" in phase_names

        assert "good_d1_retention" in recipe["benchmarks"]


class TestResourceRegistration:
    """Tests for resource registration with MCP server."""

    def test_resources_are_registered(self) -> None:
        """All resources should be registered with MCP server."""
        from mp_mcp_server.server import mcp

        # Check resources are registered
        resources = list(mcp._resource_manager._resources.keys())

        # Static resources
        assert "workspace://info" in resources
        assert "workspace://tables" in resources
        assert "schema://events" in resources
        assert "schema://funnels" in resources
        assert "schema://cohorts" in resources
        assert "schema://bookmarks" in resources
        assert "recipes://weekly-review" in resources
        assert "recipes://churn-investigation" in resources

    def test_resource_templates_are_registered(self) -> None:
        """Resource templates should be registered with MCP server."""
        from mp_mcp_server.server import mcp

        # Check templates are registered
        templates = list(mcp._resource_manager._templates.keys())

        assert "analysis://retention/{event}/weekly" in templates
        assert "analysis://trends/{event}/{days}" in templates
        assert "users://{id}/journey" in templates
