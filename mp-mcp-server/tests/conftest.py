"""Shared test fixtures for mp-mcp-server tests.

This module provides common fixtures used across unit and integration tests,
including mock Workspace instances and FastMCP client fixtures.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any, TypeVar
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from mp_mcp_server.middleware.rate_limiting import MixpanelRateLimitMiddleware


@pytest.fixture
def mock_workspace() -> MagicMock:
    """Create a mock Workspace instance for unit tests.

    Returns:
        MagicMock configured with common Workspace methods.
    """
    workspace = MagicMock()

    # Discovery methods
    workspace.events.return_value = ["signup", "login", "purchase"]
    # properties() returns list[str] (property names only) - matching real Workspace API
    workspace.properties.return_value = ["browser", "price"]
    workspace.property_values.return_value = ["Chrome", "Firefox", "Safari"]

    # Methods returning objects with to_dict()
    funnel_mock = MagicMock()
    funnel_mock.to_dict.return_value = {
        "funnel_id": 1,
        "name": "Signup Funnel",
        "steps": 3,
    }
    workspace.funnels.return_value = [funnel_mock]

    cohort_mock = MagicMock()
    cohort_mock.to_dict.return_value = {
        "cohort_id": 1,
        "name": "Active Users",
        "count": 1000,
    }
    workspace.cohorts.return_value = [cohort_mock]

    bookmark_mock = MagicMock()
    bookmark_mock.to_dict.return_value = {
        "bookmark_id": 1,
        "name": "Daily Signups",
        "report_type": "insights",
    }
    workspace.list_bookmarks.return_value = [bookmark_mock]

    top_event_mock = MagicMock()
    top_event_mock.to_dict.return_value = {"event": "login", "count": 5000}
    top_event_mock2 = MagicMock()
    top_event_mock2.to_dict.return_value = {"event": "signup", "count": 1000}
    workspace.top_events.return_value = [top_event_mock, top_event_mock2]

    # Live query methods
    workspace.segmentation.return_value = MagicMock(
        to_dict=lambda: {"data": {"values": {"2024-01-01": 100}}}
    )
    workspace.funnel.return_value = MagicMock(
        to_dict=lambda: {"data": {"steps": [{"count": 100}, {"count": 50}]}}
    )
    workspace.retention.return_value = MagicMock(
        to_dict=lambda: {"data": {"cohorts": []}}
    )
    jql_result_mock = MagicMock()
    jql_result_mock.raw = [{"user": "alice", "count": 10}]
    workspace.jql.return_value = jql_result_mock

    # Fetch methods
    workspace.fetch_events.return_value = MagicMock(
        table_name="events_jan",
        row_count=1000,
        to_dict=lambda: {"table_name": "events_jan", "row_count": 1000},
    )
    workspace.fetch_profiles.return_value = MagicMock(
        table_name="profiles",
        row_count=500,
        to_dict=lambda: {"table_name": "profiles", "row_count": 500},
    )

    # Streaming methods (return iterators)
    workspace.stream_events.return_value = iter(
        [
            {"name": "login", "distinct_id": "user1", "time": 1704067200},
            {"name": "login", "distinct_id": "user2", "time": 1704067300},
            {"name": "signup", "distinct_id": "user3", "time": 1704067400},
        ]
    )
    workspace.stream_profiles.return_value = iter(
        [
            {"$distinct_id": "user1", "$properties": {"email": "a@example.com"}},
            {"$distinct_id": "user2", "$properties": {"email": "b@example.com"}},
        ]
    )

    # Local methods
    sql_rows_mock = MagicMock()
    sql_rows_mock.to_dicts.return_value = [{"name": "login", "count": 100}]
    workspace.sql_rows.return_value = sql_rows_mock
    workspace.sql_scalar.return_value = 42

    table_mock = MagicMock()
    table_mock.to_dict.return_value = {
        "name": "events_jan",
        "row_count": 1000,
        "type": "events",
    }
    workspace.tables.return_value = [table_mock]

    col1_mock = MagicMock()
    col1_mock.to_dict.return_value = {"column": "name", "type": "VARCHAR"}
    col2_mock = MagicMock()
    col2_mock.to_dict.return_value = {"column": "time", "type": "TIMESTAMP"}
    schema_mock = MagicMock()
    schema_mock.columns = [col1_mock, col2_mock]
    workspace.table_schema.return_value = schema_mock

    sample_df_mock = MagicMock()
    sample_df_mock.to_dict.return_value = [{"name": "login", "time": "2024-01-01"}]
    workspace.sample.return_value = sample_df_mock

    summarize_col1 = MagicMock()
    summarize_col1.to_dict.return_value = {"name": "event", "type": "VARCHAR"}
    summarize_col2 = MagicMock()
    summarize_col2.to_dict.return_value = {"name": "time", "type": "TIMESTAMP"}
    summarize_mock = MagicMock()
    summarize_mock.table = "events_jan"
    summarize_mock.row_count = 1000
    summarize_mock.columns = [summarize_col1, summarize_col2]
    workspace.summarize.return_value = summarize_mock

    # Table management
    workspace.drop.return_value = None
    workspace.drop_all.return_value = None

    # Info - use info() method which returns WorkspaceInfo object
    workspace.info.return_value = MagicMock(
        project_id=123456,
        region="us",
        tables=[],
    )

    # Add event_counts() method for multi-event counting
    workspace.event_counts.return_value = MagicMock(
        to_dict=lambda: {
            "events": ["login", "signup"],
            "from_date": "2024-01-01",
            "to_date": "2024-01-31",
            "unit": "day",
            "type": "general",
            "series": {"login": {"2024-01-01": 100}, "signup": {"2024-01-01": 50}},
        }
    )

    # Add frequency() method for addiction analysis
    workspace.frequency.return_value = MagicMock(
        to_dict=lambda: {
            "event": None,
            "from_date": "2024-01-01",
            "to_date": "2024-01-07",
            "unit": "day",
            "addiction_unit": "hour",
            "data": {"2024-01-01": [100, 50, 25, 10]},
        }
    )

    # Add activity_feed() method for Activity Stream API
    workspace.activity_feed.return_value = MagicMock(
        to_dict=lambda: {
            "distinct_ids": ["user1"],
            "from_date": None,
            "to_date": None,
            "events": [
                {"event": "login", "time": 1704067200, "distinct_id": "user1"},
                {"event": "purchase", "time": 1704070800, "distinct_id": "user1"},
            ],
        }
    )

    # Add property_counts() method for property value breakdown
    workspace.property_counts.return_value = MagicMock(
        to_dict=lambda: {
            "event": "login",
            "property_name": "browser",
            "from_date": "2024-01-01",
            "to_date": "2024-01-31",
            "type": "general",
            "unit": "day",
            "data": {"Chrome": 100, "Firefox": 50, "Safari": 25},
        }
    )

    # Add property_keys() method for extracting unique property keys
    workspace.property_keys.return_value = ["browser", "country", "device"]

    return workspace


@pytest.fixture
def mock_rate_limiter() -> "MixpanelRateLimitMiddleware":
    """Create a rate limiter for unit tests.

    Returns:
        MixpanelRateLimitMiddleware instance.
    """
    from mp_mcp_server.middleware.rate_limiting import MixpanelRateLimitMiddleware

    # Create a real rate limiter for testing (lightweight, no external deps)
    return MixpanelRateLimitMiddleware()


@pytest.fixture
def mock_lifespan_state(
    mock_workspace: MagicMock, mock_rate_limiter: object
) -> dict[str, Any]:
    """Create a mock lifespan state with workspace and rate limiter.

    Args:
        mock_workspace: The mock workspace fixture.
        mock_rate_limiter: The mock rate limiter fixture.

    Returns:
        Dict containing the workspace and rate limiter in lifespan state format.
    """
    return {"workspace": mock_workspace, "rate_limiter": mock_rate_limiter}


@pytest.fixture
def mock_context(mock_lifespan_state: dict[str, Any]) -> MagicMock:
    """Create a mock FastMCP Context.

    Args:
        mock_lifespan_state: The mock lifespan state fixture.

    Returns:
        MagicMock configured as a FastMCP Context.
    """
    ctx = MagicMock()
    # FastMCP 3.0 uses public lifespan_context property
    ctx.lifespan_context = mock_lifespan_state
    # Make report_progress an async mock for tools that use progress reporting
    ctx.report_progress = AsyncMock(return_value=None)
    return ctx


@pytest.fixture
async def mcp_client() -> AsyncIterator[Any]:
    """Create an in-memory FastMCP client for integration tests.

    Yields:
        FastMCP Client connected to the server.
    """
    # Import here to avoid circular imports during collection
    from fastmcp import Client

    from mp_mcp_server.server import mcp

    async with Client(mcp) as client:
        yield client


# ============================================================================
# FastMCP v3 Registration Check Helpers
# ============================================================================

T = TypeVar("T")


def _get_mcp_items(
    list_func: Callable[[], Awaitable[Sequence[T]]], extractor: Callable[[T], str]
) -> list[str]:
    """Run an async MCP list function and extract item properties.

    Args:
        list_func: Async function that returns a sequence of MCP items.
        extractor: Function to extract a string property from each item.

    Returns:
        List of extracted string values.
    """

    async def get_items() -> list[str]:
        items = await list_func()
        return [extractor(item) for item in items]

    return asyncio.run(get_items())


@pytest.fixture
def registered_tool_names() -> list[str]:
    """Get list of registered tool names using FastMCP v3 API.

    Returns:
        List of tool names registered with the MCP server.
    """
    from mp_mcp_server.server import mcp

    return _get_mcp_items(mcp.list_tools, lambda t: t.name)


@pytest.fixture
def registered_resource_uris() -> list[str]:
    """Get list of registered resource URIs using FastMCP v3 API.

    Returns:
        List of resource URIs registered with the MCP server.
    """
    from mp_mcp_server.server import mcp

    return _get_mcp_items(mcp.list_resources, lambda r: str(r.uri))


@pytest.fixture
def registered_prompt_names() -> list[str]:
    """Get list of registered prompt names using FastMCP v3 API.

    Returns:
        List of prompt names registered with the MCP server.
    """
    from mp_mcp_server.server import mcp

    return _get_mcp_items(mcp.list_prompts, lambda p: p.name)


@pytest.fixture
def registered_resource_template_uris() -> list[str]:
    """Get list of registered resource template URIs using FastMCP v3 API.

    Returns:
        List of resource template URIs registered with the MCP server.
    """
    from mp_mcp_server.server import mcp

    return _get_mcp_items(mcp.list_resource_templates, lambda t: str(t.uri_template))
