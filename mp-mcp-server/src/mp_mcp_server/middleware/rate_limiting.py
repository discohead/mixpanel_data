"""Rate limiting middleware for MCP server.

This module provides rate limiting middleware that respects Mixpanel's
API rate limits for both Query API and Export API endpoints.

Mixpanel Rate Limits:
- Query API: 60 queries/hour, 5 concurrent
- Export API: 60 queries/hour, 3/second, 100 concurrent

Example:
    ```python
    from mp_mcp_server.middleware.rate_limiting import (
        create_query_rate_limiter,
        create_export_rate_limiter,
    )

    mcp.add_middleware(create_query_rate_limiter())
    mcp.add_middleware(create_export_rate_limiter())
    ```
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field

import mcp.types as mt
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.tool import ToolResult

# Query API tools
QUERY_API_TOOLS: frozenset[str] = frozenset(
    [
        "segmentation",
        "funnel",
        "retention",
        "jql",
        "event_counts",
        "property_counts",
        "activity_feed",
        "frequency",
    ]
)

# Export API tools
EXPORT_API_TOOLS: frozenset[str] = frozenset(
    [
        "fetch_events",
        "fetch_profiles",
        "stream_events",
        "stream_profiles",
    ]
)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting.

    Attributes:
        hourly_limit: Maximum requests per hour.
        concurrent_limit: Maximum concurrent requests.
        per_second_limit: Maximum requests per second (optional).

    Example:
        ```python
        config = RateLimitConfig(
            hourly_limit=60,
            concurrent_limit=5,
        )
        ```
    """

    hourly_limit: int = 60
    """Maximum requests per hour."""

    concurrent_limit: int = 5
    """Maximum concurrent requests."""

    per_second_limit: int | None = None
    """Maximum requests per second (optional)."""


@dataclass
class RateLimitState:
    """Internal state for tracking rate limits.

    Attributes:
        request_times: Deque of timestamps for recent requests.
        active_semaphore: Semaphore for concurrent request limiting.
        per_second_times: Deque of timestamps for per-second tracking.

    Example:
        ```python
        state = RateLimitState(
            request_times=deque(),
            active_semaphore=asyncio.Semaphore(5),
        )
        ```
    """

    request_times: deque[float] = field(default_factory=deque)
    """Deque of timestamps for recent requests."""

    active_semaphore: asyncio.Semaphore = field(
        default_factory=lambda: asyncio.Semaphore(5)
    )
    """Semaphore for concurrent request limiting."""

    per_second_times: deque[float] = field(default_factory=deque)
    """Deque of timestamps for per-second tracking."""


class MixpanelRateLimitMiddleware(Middleware):
    """Rate limiting middleware for Mixpanel API tools.

    This middleware applies different rate limits based on whether
    the tool uses the Query API or Export API.

    Attributes:
        query_config: Rate limit configuration for Query API tools.
        export_config: Rate limit configuration for Export API tools.

    Example:
        ```python
        middleware = MixpanelRateLimitMiddleware()
        mcp.add_middleware(middleware)
        ```
    """

    def __init__(
        self,
        query_config: RateLimitConfig | None = None,
        export_config: RateLimitConfig | None = None,
    ) -> None:
        """Initialize the rate limiting middleware.

        Args:
            query_config: Configuration for Query API rate limits.
                Defaults to 60/hour, 5 concurrent.
            export_config: Configuration for Export API rate limits.
                Defaults to 60/hour, 3/second, 100 concurrent.
        """
        self.query_config = query_config or RateLimitConfig(
            hourly_limit=60,
            concurrent_limit=5,
        )
        self.export_config = export_config or RateLimitConfig(
            hourly_limit=60,
            concurrent_limit=100,
            per_second_limit=3,
        )

        # Initialize state for each API type
        self._query_state = RateLimitState(
            active_semaphore=asyncio.Semaphore(self.query_config.concurrent_limit)
        )
        self._export_state = RateLimitState(
            active_semaphore=asyncio.Semaphore(self.export_config.concurrent_limit)
        )

    async def _wait_for_rate_limit(
        self,
        state: RateLimitState,
        config: RateLimitConfig,
    ) -> None:
        """Wait until rate limit allows a new request.

        Args:
            state: Current rate limit state.
            config: Rate limit configuration.
        """
        now = time.time()
        hour_ago = now - 3600

        # Clean up old timestamps
        while state.request_times and state.request_times[0] < hour_ago:
            state.request_times.popleft()

        # Wait if at hourly limit
        while len(state.request_times) >= config.hourly_limit:
            oldest = state.request_times[0]
            wait_time = oldest - hour_ago + 0.1
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            now = time.time()
            hour_ago = now - 3600
            while state.request_times and state.request_times[0] < hour_ago:
                state.request_times.popleft()

        # Per-second limiting (if configured)
        if config.per_second_limit is not None:
            second_ago = now - 1.0
            while state.per_second_times and state.per_second_times[0] < second_ago:
                state.per_second_times.popleft()

            while len(state.per_second_times) >= config.per_second_limit:
                oldest = state.per_second_times[0]
                wait_time = oldest - second_ago + 0.1
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                now = time.time()
                second_ago = now - 1.0
                while state.per_second_times and state.per_second_times[0] < second_ago:
                    state.per_second_times.popleft()

            state.per_second_times.append(now)

        # Record this request
        state.request_times.append(time.time())

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        """Apply rate limiting before tool execution.

        Args:
            context: The middleware context with request information.
            call_next: Function to call the next middleware or tool.

        Returns:
            The result from the tool execution.
        """
        tool_name = context.message.name

        # Determine which API this tool uses
        if tool_name in QUERY_API_TOOLS:
            state = self._query_state
            config = self.query_config
        elif tool_name in EXPORT_API_TOOLS:
            state = self._export_state
            config = self.export_config
        else:
            # No rate limiting for non-API tools
            return await call_next(context)

        # Wait for rate limit
        await self._wait_for_rate_limit(state, config)

        # Acquire semaphore for concurrent limiting
        async with state.active_semaphore:
            return await call_next(context)


def create_query_rate_limiter(
    hourly_limit: int = 60,
    concurrent_limit: int = 5,
) -> MixpanelRateLimitMiddleware:
    """Create a rate limiter configured for Query API only.

    Args:
        hourly_limit: Maximum queries per hour. Default 60.
        concurrent_limit: Maximum concurrent queries. Default 5.

    Returns:
        A configured MixpanelRateLimitMiddleware instance.

    Example:
        ```python
        middleware = create_query_rate_limiter()
        mcp.add_middleware(middleware)
        ```
    """
    return MixpanelRateLimitMiddleware(
        query_config=RateLimitConfig(
            hourly_limit=hourly_limit,
            concurrent_limit=concurrent_limit,
        ),
        export_config=RateLimitConfig(
            hourly_limit=10000,  # Effectively unlimited
            concurrent_limit=1000,
        ),
    )


def create_export_rate_limiter(
    hourly_limit: int = 60,
    concurrent_limit: int = 100,
    per_second_limit: int = 3,
) -> MixpanelRateLimitMiddleware:
    """Create a rate limiter configured for Export API only.

    Args:
        hourly_limit: Maximum exports per hour. Default 60.
        concurrent_limit: Maximum concurrent exports. Default 100.
        per_second_limit: Maximum exports per second. Default 3.

    Returns:
        A configured MixpanelRateLimitMiddleware instance.

    Example:
        ```python
        middleware = create_export_rate_limiter()
        mcp.add_middleware(middleware)
        ```
    """
    return MixpanelRateLimitMiddleware(
        query_config=RateLimitConfig(
            hourly_limit=10000,  # Effectively unlimited
            concurrent_limit=1000,
        ),
        export_config=RateLimitConfig(
            hourly_limit=hourly_limit,
            concurrent_limit=concurrent_limit,
            per_second_limit=per_second_limit,
        ),
    )
