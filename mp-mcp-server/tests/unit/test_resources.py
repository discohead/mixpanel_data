"""Tests for MCP resources.

These tests verify the MCP resources are registered and return correct data.
"""

import json

from mixpanel_data.exceptions import (
    AuthenticationError,
    MixpanelDataError,
    RateLimitError,
)


class TestHandleResourceErrors:
    """Tests for the handle_resource_errors decorator."""

    def test_successful_resource_returns_value(self) -> None:
        """Successful resources should return their value unchanged."""
        from mp_mcp_server.resources import handle_resource_errors

        @handle_resource_errors
        def successful_resource() -> str:
            return '{"data": "value"}'

        result = successful_resource()
        assert result == '{"data": "value"}'

    def test_mixpanel_error_returns_json_error(self) -> None:
        """MixpanelDataError should return JSON error object."""
        from mp_mcp_server.resources import handle_resource_errors

        @handle_resource_errors
        def failing_resource() -> str:
            raise AuthenticationError("Invalid credentials")

        result = failing_resource()
        data = json.loads(result)

        assert data["error"] is True
        assert data["code"] == "AUTH_FAILED"
        assert "Invalid credentials" in data["message"]

    def test_rate_limit_error_returns_json_with_retry(self) -> None:
        """RateLimitError should include retry_after in JSON error."""
        from mp_mcp_server.resources import handle_resource_errors

        @handle_resource_errors
        def failing_resource() -> str:
            raise RateLimitError("Rate limited", retry_after=30)

        result = failing_resource()
        data = json.loads(result)

        assert data["error"] is True
        assert data["code"] == "RATE_LIMITED"
        assert data["details"]["retry_after"] == 30

    def test_generic_error_returns_json_error(self) -> None:
        """Non-MixpanelDataError should return INTERNAL_ERROR JSON."""
        from mp_mcp_server.resources import handle_resource_errors

        @handle_resource_errors
        def failing_resource() -> str:
            raise ValueError("Something unexpected")

        result = failing_resource()
        data = json.loads(result)

        assert data["error"] is True
        assert data["code"] == "INTERNAL_ERROR"
        assert "Something unexpected" in data["message"]
        assert data["details"]["error_type"] == "ValueError"

    def test_error_json_is_parseable(self) -> None:
        """Error responses should be valid, parseable JSON."""
        from mp_mcp_server.resources import handle_resource_errors

        @handle_resource_errors
        def failing_resource() -> str:
            raise MixpanelDataError(
                "Test error",
                code="TEST_CODE",
                details={"key": "value", "nested": {"a": 1}},
            )

        result = failing_resource()
        # Should not raise
        data = json.loads(result)
        assert data["details"]["key"] == "value"
        assert data["details"]["nested"]["a"] == 1


class TestWorkspaceInfoResource:
    """Tests for the workspace://info resource."""

    def test_workspace_info_resource_registered(self) -> None:
        """workspace://info resource should be registered."""
        from mp_mcp_server.server import mcp

        resource_uris = list(mcp._resource_manager._resources.keys())
        assert "workspace://info" in resource_uris


class TestTablesResource:
    """Tests for the workspace://tables resource."""

    def test_tables_resource_registered(self) -> None:
        """workspace://tables resource should be registered."""
        from mp_mcp_server.server import mcp

        resource_uris = list(mcp._resource_manager._resources.keys())
        assert "workspace://tables" in resource_uris


class TestEventsResource:
    """Tests for the schema://events resource."""

    def test_events_resource_registered(self) -> None:
        """schema://events resource should be registered."""
        from mp_mcp_server.server import mcp

        resource_uris = list(mcp._resource_manager._resources.keys())
        assert "schema://events" in resource_uris


class TestFunnelsResource:
    """Tests for the schema://funnels resource."""

    def test_funnels_resource_registered(self) -> None:
        """schema://funnels resource should be registered."""
        from mp_mcp_server.server import mcp

        resource_uris = list(mcp._resource_manager._resources.keys())
        assert "schema://funnels" in resource_uris


class TestCohortsResource:
    """Tests for the schema://cohorts resource."""

    def test_cohorts_resource_registered(self) -> None:
        """schema://cohorts resource should be registered."""
        from mp_mcp_server.server import mcp

        resource_uris = list(mcp._resource_manager._resources.keys())
        assert "schema://cohorts" in resource_uris


class TestBookmarksResource:
    """Tests for the schema://bookmarks resource."""

    def test_bookmarks_resource_registered(self) -> None:
        """schema://bookmarks resource should be registered."""
        from mp_mcp_server.server import mcp

        resource_uris = list(mcp._resource_manager._resources.keys())
        assert "schema://bookmarks" in resource_uris
