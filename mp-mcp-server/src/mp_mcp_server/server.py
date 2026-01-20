"""FastMCP server with lifespan pattern for Mixpanel analytics.

This module defines the MCP server that wraps mixpanel_data capabilities,
managing a Workspace instance through the server lifespan.

Includes middleware for:
- Audit logging (timing and outcomes)
- Rate limiting (Mixpanel API limits)
- Response caching (discovery operations)

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
from mp_mcp_server.sampling import create_sampling_handler

# Module-level account setting (set by CLI before server starts)
_account: str | None = None

# Module-level rate limiter (created at import time, shared with lifespan)
_rate_limiter: "MixpanelRateLimitMiddleware | None" = None


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


def get_rate_limiter() -> "MixpanelRateLimitMiddleware":
    """Get the rate limiter middleware instance.

    Returns:
        The MixpanelRateLimitMiddleware instance.

    Raises:
        RuntimeError: If rate limiter is not initialized.
    """
    if _rate_limiter is None:
        raise RuntimeError("Rate limiter not initialized")
    return _rate_limiter


# Rate limit bypass headers for internal MCP server requests
_INTERNAL_API_HEADERS = {
    "Internal-Source": "mcp.server",
    "User-Agent": "FastMCP-Mixpanel-Client-Internal",
}


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
    workspace = (
        Workspace(
            account=account,
            api_headers=_INTERNAL_API_HEADERS,
        )
        if account
        else Workspace(api_headers=_INTERNAL_API_HEADERS)
    )

    try:
        yield {"workspace": workspace, "rate_limiter": get_rate_limiter()}
    finally:
        workspace.close()


# Create sampling handler for OpenAI fallback (when client doesn't support sampling)
_sampling_handler = create_sampling_handler()

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
- Intelligent Analysis: AI-powered metric diagnosis and natural language queries
- Product Health: AARRR dashboards and GQM investigations
- Interactive Workflows: Guided analysis and safe large fetches

Use the tools to help users understand their Mixpanel data.
""",
    lifespan=lifespan,
    sampling_handler=_sampling_handler,
    sampling_handler_behavior="fallback",
)

# Register middleware (order: Logging -> Rate Limiting -> Caching)
# Imports happen here to avoid circular imports
from mp_mcp_server.middleware import (  # noqa: E402
    MixpanelRateLimitMiddleware,
    create_audit_middleware,
    create_caching_middleware,
)

# Store rate limiter at module level for lifespan access
_rate_limiter = MixpanelRateLimitMiddleware()

mcp.add_middleware(create_audit_middleware())
mcp.add_middleware(_rate_limiter)
mcp.add_middleware(create_caching_middleware())

# Import tool modules to register them with the server
# These imports must happen after mcp is defined
from mp_mcp_server import prompts, resources  # noqa: E402, F401
from mp_mcp_server.tools import (  # noqa: E402, F401  # noqa: E402, F401
    composed,
    discovery,
    fetch,
    intelligent,
    interactive,
    live_query,
    local,
)
