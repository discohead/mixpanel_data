"""Tests for MCP resources.

These tests verify the MCP resources are registered and return correct data.

Note: Resource function invocation is covered by integration tests in
test_server_integration.py, which tests the full MCP client workflow.
"""

from typing import Any, cast

import pytest
from mcp.shared.exceptions import McpError

from mixpanel_data.exceptions import (
    AuthenticationError,
    MixpanelDataError,
    RateLimitError,
)


def get_error_data(error: McpError) -> dict[str, Any]:
    """Extract error data from McpError, asserting it exists.

    Args:
        error: The McpError to extract data from.

    Returns:
        The error data dictionary.

    Raises:
        AssertionError: If error data is None.
    """
    assert error.error.data is not None, "Expected error.data to be present"
    return cast(dict[str, Any], error.error.data)


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

    def test_mixpanel_error_raises_mcp_error(self) -> None:
        """MixpanelDataError should raise McpError with structured data."""
        from mp_mcp_server.resources import handle_resource_errors

        @handle_resource_errors
        def failing_resource() -> str:
            raise AuthenticationError("Invalid credentials")

        with pytest.raises(McpError) as exc_info:
            failing_resource()

        error = exc_info.value
        data = get_error_data(error)
        assert error.error.code == -32603  # INTERNAL_ERROR
        assert "Invalid credentials" in error.error.message
        assert data["code"] == "AUTH_FAILED"

    def test_rate_limit_error_includes_retry_after(self) -> None:
        """RateLimitError should include retry_after in error data."""
        from mp_mcp_server.resources import handle_resource_errors

        @handle_resource_errors
        def failing_resource() -> str:
            raise RateLimitError("Rate limited", retry_after=30)

        with pytest.raises(McpError) as exc_info:
            failing_resource()

        error = exc_info.value
        data = get_error_data(error)
        assert data["code"] == "RATE_LIMITED"
        assert data["details"]["retry_after"] == 30

    def test_generic_error_raises_mcp_error(self) -> None:
        """Non-MixpanelDataError should raise McpError with INTERNAL_ERROR."""
        from mp_mcp_server.resources import handle_resource_errors

        @handle_resource_errors
        def failing_resource() -> str:
            raise ValueError("Something unexpected")

        with pytest.raises(McpError) as exc_info:
            failing_resource()

        error = exc_info.value
        data = get_error_data(error)
        assert error.error.code == -32603  # INTERNAL_ERROR
        assert "Something unexpected" in error.error.message
        assert data["code"] == "INTERNAL_ERROR"
        assert data["details"]["error_type"] == "ValueError"

    def test_error_data_is_structured(self) -> None:
        """Error data should preserve structured details."""
        from mp_mcp_server.resources import handle_resource_errors

        @handle_resource_errors
        def failing_resource() -> str:
            raise MixpanelDataError(
                "Test error",
                code="TEST_CODE",
                details={"key": "value", "nested": {"a": 1}},
            )

        with pytest.raises(McpError) as exc_info:
            failing_resource()

        error = exc_info.value
        data = get_error_data(error)
        assert data["details"]["key"] == "value"
        assert data["details"]["nested"]["a"] == 1

    def test_error_chains_original_exception(self) -> None:
        """McpError should chain the original exception."""
        from mp_mcp_server.resources import handle_resource_errors

        @handle_resource_errors
        def failing_resource() -> str:
            raise AuthenticationError("Invalid credentials")

        with pytest.raises(McpError) as exc_info:
            failing_resource()

        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, AuthenticationError)


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


