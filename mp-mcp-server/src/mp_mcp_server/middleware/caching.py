"""Response caching middleware for MCP server.

This module provides caching middleware that wraps FastMCP's built-in
ResponseCachingMiddleware with Mixpanel-specific configuration for
discovery operations.

Example:
    ```python
    from mp_mcp_server.middleware.caching import create_caching_middleware

    mcp.add_middleware(create_caching_middleware())
    ```
"""

from fastmcp.server.middleware.caching import (
    CallToolSettings,
    ListToolsSettings,
    ResponseCachingMiddleware,
)

# Discovery tools that should be cached
CACHEABLE_DISCOVERY_TOOLS: frozenset[str] = frozenset(
    [
        "list_events",
        "list_properties",
        "list_property_values",
        "list_funnels",
        "list_cohorts",
        "list_bookmarks",
        "top_events",
        "workspace_info",
    ]
)

# Default TTL for discovery operations (5 minutes)
DEFAULT_DISCOVERY_TTL: int = 300


def create_caching_middleware(
    discovery_ttl: int = DEFAULT_DISCOVERY_TTL,
    cacheable_tools: frozenset[str] | None = None,
) -> ResponseCachingMiddleware:
    """Create a configured caching middleware for discovery operations.

    This middleware caches responses from discovery tools to reduce
    API calls and improve response times for repeated queries.

    Args:
        discovery_ttl: Time-to-live in seconds for cached discovery responses.
            Default is 300 seconds (5 minutes).
        cacheable_tools: Set of tool names to cache. Default is the standard
            set of discovery tools.

    Returns:
        A configured ResponseCachingMiddleware instance.

    Example:
        ```python
        # Use default configuration
        middleware = create_caching_middleware()
        mcp.add_middleware(middleware)

        # Custom TTL for longer caching
        middleware = create_caching_middleware(discovery_ttl=600)
        ```
    """
    tools_to_cache = (
        list(cacheable_tools)
        if cacheable_tools is not None
        else list(CACHEABLE_DISCOVERY_TOOLS)
    )

    return ResponseCachingMiddleware(
        list_tools_settings=ListToolsSettings(ttl=discovery_ttl),
        call_tool_settings=CallToolSettings(
            included_tools=tools_to_cache,
            ttl=discovery_ttl,
        ),
    )
