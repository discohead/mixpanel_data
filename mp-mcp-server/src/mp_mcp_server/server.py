"""FastMCP server with lifespan pattern for Mixpanel analytics.

This module defines the MCP server that wraps mixpanel_data capabilities,
managing a Workspace instance through the server lifespan.

Example:
    Run the server for Claude Desktop:

    ```python
    from mp_mcp_server.server import mcp
    mcp.run()
    ```
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP

from mixpanel_data import Workspace

# Module-level account setting (set by CLI before server starts)
_account: str | None = None


def set_account(account: str | None) -> None:
    """Set the account name to use when creating the Workspace.

    Args:
        account: The account name from ~/.mp/config.toml, or None for default.
    """
    global _account
    _account = account


def get_account() -> str | None:
    """Get the currently configured account name.

    Returns:
        The account name, or None if using default.
    """
    return _account


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Manage Workspace lifecycle for the MCP server session.

    Creates a Workspace on startup and ensures proper cleanup on shutdown.
    The Workspace is stored in the lifespan state and accessible to all tools.

    Args:
        _server: The FastMCP server instance (unused, required by signature).

    Yields:
        Dict containing the workspace in lifespan state format.

    Example:
        ```python
        @mcp.tool
        def list_events(ctx: Context) -> list[str]:
            ws = ctx.request_context.lifespan_state["workspace"]
            return ws.events()
        ```
    """
    account = get_account()
    workspace = Workspace(account=account) if account else Workspace()

    try:
        yield {"workspace": workspace}
    finally:
        workspace.close()


# Create the FastMCP server instance
mcp = FastMCP(
    name="mixpanel",
    instructions="""Mixpanel Analytics MCP Server

This server provides tools for Mixpanel analytics through the mixpanel_data library.

Capabilities:
- Schema Discovery: Explore events, properties, funnels, cohorts, and bookmarks
- Live Analytics: Run segmentation, funnel, and retention queries
- Data Fetching: Download events and profiles to local storage
- Local Analysis: Execute SQL queries against fetched data

Use the tools to help users understand their Mixpanel data.
""",
    lifespan=lifespan,
)

# Import tool modules to register them with the server
# These imports must happen after mcp is defined
from mp_mcp_server import prompts, resources  # noqa: E402, F401
from mp_mcp_server.tools import discovery, fetch, live_query, local  # noqa: E402, F401
