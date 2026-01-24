"""Rate limiting middleware for MCP server.

This module provides rate limiting middleware that respects Mixpanel's
API rate limits for both Query API and Export API endpoints.

Mixpanel Rate Limits:
- Query API: 60 queries/hour, 5 concurrent
- Export API: 60 queries/hour, 3/second, 100 concurrent

Also provides RateLimitedWorkspace wrapper to ensure composed/intelligent
tools that call Workspace methods directly still respect rate limits.

Example:
    ```python
    from mp_mcp.middleware.rate_limiting import (
        MixpanelRateLimitMiddleware,
        RateLimitedWorkspace,
    )

    rate_limiter = MixpanelRateLimitMiddleware()
    mcp.add_middleware(rate_limiter)

    # In context.py
    wrapped = RateLimitedWorkspace(workspace, rate_limiter)
    ```
"""

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

import mcp.types as mt
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.tool import ToolResult

if TYPE_CHECKING:
    from mixpanel_data import Workspace

logger = logging.getLogger(__name__)

T = TypeVar("T")

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

    def wait_for_query_limit_sync(
        self,
        max_wait: float = 120.0,
    ) -> None:
        """Synchronous rate limit check for Query API.

        Used by RateLimitedWorkspace to apply rate limiting to
        direct Workspace method calls from composed/intelligent tools.

        Args:
            max_wait: Maximum seconds to wait before raising error.

        Raises:
            ToolError: If rate limit timeout is exceeded.
        """
        self._wait_for_rate_limit_sync(self._query_state, self.query_config, max_wait)

    def wait_for_export_limit_sync(
        self,
        max_wait: float = 120.0,
    ) -> None:
        """Synchronous rate limit check for Export API.

        Used by RateLimitedWorkspace to apply rate limiting to
        direct Workspace method calls from composed/intelligent tools.

        Args:
            max_wait: Maximum seconds to wait before raising error.

        Raises:
            ToolError: If rate limit timeout is exceeded.
        """
        self._wait_for_rate_limit_sync(self._export_state, self.export_config, max_wait)

    def _wait_for_rate_limit_sync(
        self,
        state: RateLimitState,
        config: RateLimitConfig,
        max_wait: float = 120.0,
    ) -> None:
        """Synchronous version of _wait_for_rate_limit.

        Uses time.sleep() instead of asyncio.sleep() for use in
        synchronous contexts (e.g., Workspace method wrappers).

        Args:
            state: Current rate limit state.
            config: Rate limit configuration.
            max_wait: Maximum seconds to wait before raising error.

        Raises:
            ToolError: If rate limit timeout is exceeded.
        """
        start_time = time.monotonic()
        now = time.time()
        hour_ago = now - 3600

        # Clean up old timestamps
        while state.request_times and state.request_times[0] < hour_ago:
            state.request_times.popleft()

        # Wait if at hourly limit
        while len(state.request_times) >= config.hourly_limit:
            elapsed = time.monotonic() - start_time
            if elapsed >= max_wait:
                raise ToolError(
                    "Rate limit timeout exceeded. "
                    f"Waited {elapsed:.1f}s for rate limit to clear. "
                    "Try again later."
                )

            oldest = state.request_times[0]
            wait_time = oldest - hour_ago + 0.1
            if wait_time > 0:
                actual_wait = min(wait_time, max_wait - elapsed)
                logger.info(
                    "Rate limited (Query API), waiting %.1fs "
                    "(%.1fs elapsed, %.1fs max)",
                    actual_wait,
                    elapsed,
                    max_wait,
                )
                time.sleep(actual_wait)

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
                elapsed = time.monotonic() - start_time
                if elapsed >= max_wait:
                    raise ToolError(
                        "Rate limit timeout exceeded (per-second limit). "
                        f"Waited {elapsed:.1f}s. Try again later."
                    )

                oldest = state.per_second_times[0]
                wait_time = oldest - second_ago + 0.1
                if wait_time > 0:
                    actual_wait = min(wait_time, max_wait - elapsed)
                    logger.info(
                        "Rate limited (per-second), waiting %.1fs",
                        actual_wait,
                    )
                    time.sleep(actual_wait)

                now = time.time()
                second_ago = now - 1.0
                while state.per_second_times and state.per_second_times[0] < second_ago:
                    state.per_second_times.popleft()

            state.per_second_times.append(now)

        # Record this request
        state.request_times.append(time.time())


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


class RateLimitedWorkspace:
    """Wrapper that applies rate limiting to Workspace API calls.

    This ensures composed/intelligent tools that call Workspace methods
    directly (bypassing MCP tool invocation) still respect Mixpanel API
    rate limits.

    The wrapper intercepts calls to Query API methods (segmentation, funnel,
    retention, jql, event_counts, property_counts, activity_feed, frequency)
    and Export API methods (fetch_events, fetch_profiles, stream_events,
    stream_profiles), applying the same rate limiting as the middleware.

    All other attributes are proxied directly to the wrapped Workspace.

    Attributes:
        QUERY_METHODS: Methods that use the Query API.
        EXPORT_METHODS: Methods that use the Export API.

    Example:
        ```python
        from mp_mcp.middleware.rate_limiting import (
            MixpanelRateLimitMiddleware,
            RateLimitedWorkspace,
        )
        from mixpanel_data import Workspace

        rate_limiter = MixpanelRateLimitMiddleware()
        workspace = Workspace()
        wrapped = RateLimitedWorkspace(workspace, rate_limiter)

        # This call is now rate-limited
        result = wrapped.segmentation(event="login", from_date="2024-01-01", ...)
        ```
    """

    QUERY_METHODS: frozenset[str] = frozenset(
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
    """Methods that use the Query API and need 60/hr rate limiting."""

    EXPORT_METHODS: frozenset[str] = frozenset(
        [
            "fetch_events",
            "fetch_profiles",
            "stream_events",
            "stream_profiles",
        ]
    )
    """Methods that use the Export API and need 60/hr + 3/sec rate limiting."""

    def __init__(
        self,
        workspace: "Workspace",
        rate_limiter: MixpanelRateLimitMiddleware,
    ) -> None:
        """Initialize the rate-limited workspace wrapper.

        Args:
            workspace: The Workspace instance to wrap.
            rate_limiter: The rate limiting middleware with shared state.
        """
        # Use object.__setattr__ to avoid triggering __getattr__
        object.__setattr__(self, "_ws", workspace)
        object.__setattr__(self, "_limiter", rate_limiter)

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        """Proxy attribute access to the wrapped workspace.

        For rate-limited methods, returns a wrapper that applies
        rate limiting before calling the original method.

        Args:
            name: The attribute name to access.

        Returns:
            The attribute from the wrapped workspace, possibly wrapped
            with rate limiting for API methods.
        """
        attr = getattr(self._ws, name)

        if callable(attr):
            if name in self.QUERY_METHODS:
                return self._make_rate_limited(attr, "query")
            elif name in self.EXPORT_METHODS:
                return self._make_rate_limited(attr, "export")

        return attr

    def _make_rate_limited(
        self,
        method: Callable[..., T],
        api_type: str,
    ) -> Callable[..., T]:
        """Wrap a method with synchronous rate limit checking.

        Args:
            method: The original Workspace method to wrap.
            api_type: Either "query" or "export" to select rate limit config.

        Returns:
            A wrapped method that applies rate limiting before execution.
        """
        limiter = self._limiter  # Capture for closure

        @wraps(method)
        def wrapper(*args: Any, **kwargs: Any) -> T:  # noqa: ANN401
            if api_type == "query":
                limiter.wait_for_query_limit_sync()
            else:
                limiter.wait_for_export_limit_sync()
            return method(*args, **kwargs)

        return wrapper

    def close(self) -> None:
        """Close the wrapped workspace.

        Delegates to the underlying Workspace.close() method.
        """
        self._ws.close()
