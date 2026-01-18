"""Tests for rate limiting middleware.

These tests verify the MixpanelRateLimitMiddleware enforces rate limits correctly.
Also tests RateLimitedWorkspace wrapper for composed/intelligent tool rate limiting.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError

from mp_mcp_server.middleware.rate_limiting import (
    EXPORT_API_TOOLS,
    QUERY_API_TOOLS,
    MixpanelRateLimitMiddleware,
    RateLimitConfig,
    RateLimitedWorkspace,
    RateLimitState,
    create_export_rate_limiter,
    create_query_rate_limiter,
)


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_default_values(self) -> None:
        """RateLimitConfig should have sensible defaults."""
        config = RateLimitConfig()
        assert config.hourly_limit == 60
        assert config.concurrent_limit == 5
        assert config.per_second_limit is None

    def test_custom_values(self) -> None:
        """RateLimitConfig should accept custom values."""
        config = RateLimitConfig(
            hourly_limit=120,
            concurrent_limit=10,
            per_second_limit=5,
        )
        assert config.hourly_limit == 120
        assert config.concurrent_limit == 10
        assert config.per_second_limit == 5


class TestRateLimitState:
    """Tests for RateLimitState dataclass."""

    def test_default_values(self) -> None:
        """RateLimitState should initialize with empty collections."""
        state = RateLimitState()
        assert len(state.request_times) == 0
        assert len(state.per_second_times) == 0
        assert isinstance(state.active_semaphore, asyncio.Semaphore)

    def test_custom_semaphore(self) -> None:
        """RateLimitState should accept custom semaphore."""
        custom_semaphore = asyncio.Semaphore(10)
        state = RateLimitState(active_semaphore=custom_semaphore)
        assert state.active_semaphore is custom_semaphore


class TestToolSets:
    """Tests for tool set constants."""

    def test_query_api_tools_is_frozenset(self) -> None:
        """QUERY_API_TOOLS should be immutable."""
        assert isinstance(QUERY_API_TOOLS, frozenset)

    def test_query_api_tools_contains_expected(self) -> None:
        """QUERY_API_TOOLS should contain expected tools."""
        expected = {"segmentation", "funnel", "retention", "jql"}
        assert expected.issubset(QUERY_API_TOOLS)

    def test_export_api_tools_is_frozenset(self) -> None:
        """EXPORT_API_TOOLS should be immutable."""
        assert isinstance(EXPORT_API_TOOLS, frozenset)

    def test_export_api_tools_contains_expected(self) -> None:
        """EXPORT_API_TOOLS should contain expected tools."""
        expected = {"fetch_events", "fetch_profiles", "stream_events", "stream_profiles"}
        assert expected == EXPORT_API_TOOLS


class TestMixpanelRateLimitMiddleware:
    """Tests for MixpanelRateLimitMiddleware class."""

    def test_init_with_defaults(self) -> None:
        """Middleware should use default configs when none provided."""
        middleware = MixpanelRateLimitMiddleware()
        assert middleware.query_config.hourly_limit == 60
        assert middleware.query_config.concurrent_limit == 5
        assert middleware.export_config.hourly_limit == 60
        assert middleware.export_config.concurrent_limit == 100
        assert middleware.export_config.per_second_limit == 3

    def test_init_with_custom_configs(self) -> None:
        """Middleware should use provided configs."""
        query_config = RateLimitConfig(hourly_limit=30, concurrent_limit=3)
        export_config = RateLimitConfig(hourly_limit=20, concurrent_limit=50, per_second_limit=2)

        middleware = MixpanelRateLimitMiddleware(
            query_config=query_config,
            export_config=export_config,
        )

        assert middleware.query_config.hourly_limit == 30
        assert middleware.export_config.hourly_limit == 20

    @pytest.mark.asyncio
    async def test_non_api_tool_not_rate_limited(self) -> None:
        """Non-API tools should not be rate limited."""
        middleware = MixpanelRateLimitMiddleware()

        mock_context = MagicMock()
        mock_context.message.name = "list_tables"  # Not an API tool

        expected_result: dict[str, list[str]] = {"tables": []}
        mock_call_next = AsyncMock(return_value=expected_result)

        result = await middleware.on_call_tool(mock_context, mock_call_next)

        assert result == expected_result  # type: ignore[comparison-overlap]
        mock_call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_api_tool_rate_limited(self) -> None:
        """Query API tools should be rate limited."""
        middleware = MixpanelRateLimitMiddleware()

        mock_context = MagicMock()
        mock_context.message.name = "segmentation"  # Query API tool

        expected_result: dict[str, dict[str, str]] = {"data": {}}
        mock_call_next = AsyncMock(return_value=expected_result)

        result = await middleware.on_call_tool(mock_context, mock_call_next)

        assert result == expected_result  # type: ignore[comparison-overlap]
        mock_call_next.assert_called_once()
        # Request should be recorded
        assert len(middleware._query_state.request_times) == 1

    @pytest.mark.asyncio
    async def test_export_api_tool_rate_limited(self) -> None:
        """Export API tools should be rate limited."""
        middleware = MixpanelRateLimitMiddleware()

        mock_context = MagicMock()
        mock_context.message.name = "fetch_events"  # Export API tool

        expected_result: dict[str, str] = {"table": "events"}
        mock_call_next = AsyncMock(return_value=expected_result)

        result = await middleware.on_call_tool(mock_context, mock_call_next)

        assert result == expected_result  # type: ignore[comparison-overlap]
        mock_call_next.assert_called_once()
        # Request should be recorded
        assert len(middleware._export_state.request_times) == 1

    @pytest.mark.asyncio
    async def test_concurrent_limit_enforced(self) -> None:
        """Middleware should limit concurrent requests."""
        # Create middleware with low concurrent limit
        query_config = RateLimitConfig(hourly_limit=1000, concurrent_limit=2)
        middleware = MixpanelRateLimitMiddleware(query_config=query_config)

        concurrent_count = 0
        max_concurrent = 0

        async def slow_call_next(_ctx: MagicMock) -> dict[str, str]:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.1)
            concurrent_count -= 1
            return {"result": "ok"}

        # Create multiple contexts
        contexts = []
        for _ in range(5):
            ctx = MagicMock()
            ctx.message.name = "segmentation"
            contexts.append(ctx)

        # Run all requests concurrently
        tasks = [
            middleware.on_call_tool(ctx, slow_call_next)  # type: ignore[arg-type]
            for ctx in contexts
        ]
        await asyncio.gather(*tasks)

        # Max concurrent should not exceed limit
        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_wait_for_rate_limit_cleans_old_timestamps(self) -> None:
        """_wait_for_rate_limit should clean up old timestamps."""
        middleware = MixpanelRateLimitMiddleware()
        state = middleware._query_state
        config = middleware.query_config

        # Add an old timestamp (more than 1 hour ago)
        import time
        old_time = time.time() - 4000  # More than 1 hour ago
        state.request_times.append(old_time)

        # Wait for rate limit should clean it up
        await middleware._wait_for_rate_limit(state, config)

        # Old timestamp should be removed
        assert old_time not in state.request_times


class TestCreateQueryRateLimiter:
    """Tests for create_query_rate_limiter factory function."""

    def test_default_params(self) -> None:
        """create_query_rate_limiter should use defaults."""
        middleware = create_query_rate_limiter()
        assert middleware.query_config.hourly_limit == 60
        assert middleware.query_config.concurrent_limit == 5
        # Export should be effectively unlimited
        assert middleware.export_config.hourly_limit == 10000

    def test_custom_params(self) -> None:
        """create_query_rate_limiter should accept custom params."""
        middleware = create_query_rate_limiter(
            hourly_limit=30,
            concurrent_limit=3,
        )
        assert middleware.query_config.hourly_limit == 30
        assert middleware.query_config.concurrent_limit == 3


class TestCreateExportRateLimiter:
    """Tests for create_export_rate_limiter factory function."""

    def test_default_params(self) -> None:
        """create_export_rate_limiter should use defaults."""
        middleware = create_export_rate_limiter()
        assert middleware.export_config.hourly_limit == 60
        assert middleware.export_config.concurrent_limit == 100
        assert middleware.export_config.per_second_limit == 3
        # Query should be effectively unlimited
        assert middleware.query_config.hourly_limit == 10000

    def test_custom_params(self) -> None:
        """create_export_rate_limiter should accept custom params."""
        middleware = create_export_rate_limiter(
            hourly_limit=30,
            concurrent_limit=50,
            per_second_limit=2,
        )
        assert middleware.export_config.hourly_limit == 30
        assert middleware.export_config.concurrent_limit == 50
        assert middleware.export_config.per_second_limit == 2


class TestPerSecondRateLimiting:
    """Tests for per-second rate limiting."""

    @pytest.mark.asyncio
    async def test_per_second_limiting_cleans_old_timestamps(self) -> None:
        """_wait_for_rate_limit should clean old per-second timestamps."""
        import time

        export_config = RateLimitConfig(
            hourly_limit=1000,
            concurrent_limit=100,
            per_second_limit=5,
        )
        middleware = MixpanelRateLimitMiddleware(export_config=export_config)
        state = middleware._export_state

        # Add an old per-second timestamp (more than 1 second ago)
        old_time = time.time() - 2.0
        state.per_second_times.append(old_time)

        # Wait for rate limit should clean it up
        await middleware._wait_for_rate_limit(state, export_config)

        # Old timestamp should be removed
        assert old_time not in state.per_second_times

    @pytest.mark.asyncio
    async def test_per_second_limiting_records_timestamps(self) -> None:
        """_wait_for_rate_limit should record per-second timestamps."""
        export_config = RateLimitConfig(
            hourly_limit=1000,
            concurrent_limit=100,
            per_second_limit=5,
        )
        middleware = MixpanelRateLimitMiddleware(export_config=export_config)
        state = middleware._export_state

        # Call wait to record timestamp
        await middleware._wait_for_rate_limit(state, export_config)

        # Should have recorded a timestamp
        assert len(state.per_second_times) == 1

    @pytest.mark.asyncio
    async def test_export_tool_uses_per_second_limiting(self) -> None:
        """Export tools should use per-second rate limiting."""
        export_config = RateLimitConfig(
            hourly_limit=1000,
            concurrent_limit=100,
            per_second_limit=10,
        )
        middleware = MixpanelRateLimitMiddleware(export_config=export_config)

        mock_context = MagicMock()
        mock_context.message.name = "fetch_events"  # Export API tool

        expected_result: dict[str, str] = {"table": "events"}
        mock_call_next = AsyncMock(return_value=expected_result)

        result = await middleware.on_call_tool(mock_context, mock_call_next)

        assert result == expected_result  # type: ignore[comparison-overlap]
        # Per-second timestamps should be recorded
        assert len(middleware._export_state.per_second_times) == 1


class TestRateLimitWaitingBehavior:
    """Tests for rate limit waiting behavior (hitting limits)."""

    @pytest.mark.asyncio
    async def test_waits_when_hourly_limit_reached(self) -> None:
        """_wait_for_rate_limit should wait when at hourly limit."""
        import time
        from unittest.mock import patch

        # Very low limit to easily hit it
        config = RateLimitConfig(hourly_limit=2, concurrent_limit=10)
        middleware = MixpanelRateLimitMiddleware(query_config=config)
        state = middleware._query_state

        # Fill up the limit with timestamps that will be old after mock time advances
        now = time.time()
        # Add timestamps that are just under an hour old
        state.request_times.append(now - 3590)
        state.request_times.append(now - 3580)

        sleep_called = False

        async def mock_sleep(_duration: float) -> None:
            nonlocal sleep_called
            sleep_called = True
            # Simulate time passing by removing old timestamps
            state.request_times.popleft()

        with patch("asyncio.sleep", side_effect=mock_sleep):
            await middleware._wait_for_rate_limit(state, config)

        # Sleep should have been called to wait
        assert sleep_called

    @pytest.mark.asyncio
    async def test_waits_when_per_second_limit_reached(self) -> None:
        """_wait_for_rate_limit should wait when at per-second limit."""
        import time
        from unittest.mock import patch

        # Very low per-second limit
        config = RateLimitConfig(
            hourly_limit=1000,
            concurrent_limit=10,
            per_second_limit=2,
        )
        middleware = MixpanelRateLimitMiddleware(export_config=config)
        state = middleware._export_state

        # Fill up the per-second limit with timestamps that are just under a second old
        now = time.time()
        state.per_second_times.append(now - 0.9)
        state.per_second_times.append(now - 0.8)

        sleep_called = False

        async def mock_sleep(_duration: float) -> None:
            nonlocal sleep_called
            sleep_called = True
            # Simulate time passing by removing old timestamps
            state.per_second_times.popleft()

        with patch("asyncio.sleep", side_effect=mock_sleep):
            await middleware._wait_for_rate_limit(state, config)

        # Sleep should have been called
        assert sleep_called

    @pytest.mark.asyncio
    async def test_cleans_stale_hourly_timestamps_in_wait_loop(self) -> None:
        """_wait_for_rate_limit should clean stale timestamps in wait loop."""
        import time
        from unittest.mock import patch

        config = RateLimitConfig(hourly_limit=1, concurrent_limit=10)
        middleware = MixpanelRateLimitMiddleware(query_config=config)
        state = middleware._query_state

        # Add timestamps at limit - all recent so we hit the wait loop
        now = time.time()
        state.request_times.append(now - 0.5)  # Recent, at limit

        iterations = 0

        async def mock_sleep(_duration: float) -> None:
            nonlocal iterations
            iterations += 1
            # Simulate time passing - make timestamp old enough to clean
            if state.request_times:
                state.request_times.popleft()

        with patch("asyncio.sleep", side_effect=mock_sleep):
            await middleware._wait_for_rate_limit(state, config)

        # Should have gone through wait loop
        assert iterations >= 1

    @pytest.mark.asyncio
    async def test_cleans_stale_per_second_timestamps_in_wait_loop(self) -> None:
        """_wait_for_rate_limit should clean stale per-second timestamps in wait loop."""
        import time
        from unittest.mock import patch

        config = RateLimitConfig(
            hourly_limit=1000,
            concurrent_limit=10,
            per_second_limit=1,
        )
        middleware = MixpanelRateLimitMiddleware(export_config=config)
        state = middleware._export_state

        # Add timestamp at limit - recent so we hit the wait loop
        now = time.time()
        state.per_second_times.append(now - 0.5)   # Recent, at limit

        iterations = 0

        async def mock_sleep(_duration: float) -> None:
            nonlocal iterations
            iterations += 1
            # Simulate time passing
            if state.per_second_times:
                state.per_second_times.popleft()

        with patch("asyncio.sleep", side_effect=mock_sleep):
            await middleware._wait_for_rate_limit(state, config)

        # Should have gone through wait loop at least once
        assert iterations >= 1


class TestRateLimitedWorkspace:
    """Tests for RateLimitedWorkspace wrapper class."""

    def test_proxies_non_rate_limited_attributes(self) -> None:
        """RateLimitedWorkspace should proxy non-API attributes directly."""
        mock_workspace = MagicMock()
        mock_workspace.some_property = "test_value"
        rate_limiter = MixpanelRateLimitMiddleware()

        wrapped = RateLimitedWorkspace(mock_workspace, rate_limiter)

        # Non-callable attributes should be proxied directly
        assert wrapped.some_property == "test_value"

    def test_proxies_non_rate_limited_methods(self) -> None:
        """RateLimitedWorkspace should proxy non-API methods without rate limiting."""
        mock_workspace = MagicMock()
        mock_workspace.events.return_value = ["signup", "login"]
        rate_limiter = MixpanelRateLimitMiddleware()

        wrapped = RateLimitedWorkspace(mock_workspace, rate_limiter)

        result = wrapped.events()

        assert result == ["signup", "login"]
        mock_workspace.events.assert_called_once()
        # No rate limit should be recorded
        assert len(rate_limiter._query_state.request_times) == 0

    def test_rate_limits_query_methods(self) -> None:
        """RateLimitedWorkspace should rate limit Query API methods."""
        mock_workspace = MagicMock()
        mock_workspace.segmentation.return_value = {"data": []}
        rate_limiter = MixpanelRateLimitMiddleware()

        wrapped = RateLimitedWorkspace(mock_workspace, rate_limiter)

        result = wrapped.segmentation(event="login")

        assert result == {"data": []}
        mock_workspace.segmentation.assert_called_once_with(event="login")
        # Rate limit should be recorded
        assert len(rate_limiter._query_state.request_times) == 1

    def test_rate_limits_export_methods(self) -> None:
        """RateLimitedWorkspace should rate limit Export API methods."""
        mock_workspace = MagicMock()
        mock_workspace.fetch_events.return_value = {"table": "events"}
        rate_limiter = MixpanelRateLimitMiddleware()

        wrapped = RateLimitedWorkspace(mock_workspace, rate_limiter)

        result = wrapped.fetch_events(from_date="2024-01-01", to_date="2024-01-31")

        assert result == {"table": "events"}
        mock_workspace.fetch_events.assert_called_once_with(
            from_date="2024-01-01", to_date="2024-01-31"
        )
        # Rate limit should be recorded
        assert len(rate_limiter._export_state.request_times) == 1

    def test_rate_limits_all_query_methods(self) -> None:
        """RateLimitedWorkspace should rate limit all Query API methods."""
        mock_workspace = MagicMock()
        rate_limiter = MixpanelRateLimitMiddleware()
        wrapped = RateLimitedWorkspace(mock_workspace, rate_limiter)

        for method_name in RateLimitedWorkspace.QUERY_METHODS:
            getattr(mock_workspace, method_name).return_value = {}
            getattr(wrapped, method_name)()

        # All query methods should be rate limited
        assert len(rate_limiter._query_state.request_times) == len(
            RateLimitedWorkspace.QUERY_METHODS
        )

    def test_rate_limits_all_export_methods(self) -> None:
        """RateLimitedWorkspace should rate limit all Export API methods."""
        mock_workspace = MagicMock()
        rate_limiter = MixpanelRateLimitMiddleware()
        wrapped = RateLimitedWorkspace(mock_workspace, rate_limiter)

        for method_name in RateLimitedWorkspace.EXPORT_METHODS:
            getattr(mock_workspace, method_name).return_value = {}
            getattr(wrapped, method_name)()

        # All export methods should be rate limited
        assert len(rate_limiter._export_state.request_times) == len(
            RateLimitedWorkspace.EXPORT_METHODS
        )

    def test_close_delegates_to_workspace(self) -> None:
        """RateLimitedWorkspace.close() should delegate to underlying workspace."""
        mock_workspace = MagicMock()
        rate_limiter = MixpanelRateLimitMiddleware()

        wrapped = RateLimitedWorkspace(mock_workspace, rate_limiter)
        wrapped.close()

        mock_workspace.close.assert_called_once()

    def test_shares_rate_limit_state_with_middleware(self) -> None:
        """RateLimitedWorkspace should share rate limit state with middleware."""
        mock_workspace = MagicMock()
        mock_workspace.segmentation.return_value = {}
        rate_limiter = MixpanelRateLimitMiddleware()

        wrapped = RateLimitedWorkspace(mock_workspace, rate_limiter)

        # Call via wrapper
        wrapped.segmentation()
        assert len(rate_limiter._query_state.request_times) == 1

        # Call via another wrapper with same limiter
        wrapped2 = RateLimitedWorkspace(mock_workspace, rate_limiter)
        wrapped2.segmentation()

        # Should share state
        assert len(rate_limiter._query_state.request_times) == 2


class TestSyncRateLimitMethods:
    """Tests for synchronous rate limit methods."""

    def test_wait_for_query_limit_sync_records_timestamp(self) -> None:
        """wait_for_query_limit_sync should record request timestamp."""
        rate_limiter = MixpanelRateLimitMiddleware()

        rate_limiter.wait_for_query_limit_sync()

        assert len(rate_limiter._query_state.request_times) == 1

    def test_wait_for_export_limit_sync_records_timestamp(self) -> None:
        """wait_for_export_limit_sync should record request timestamp."""
        rate_limiter = MixpanelRateLimitMiddleware()

        rate_limiter.wait_for_export_limit_sync()

        assert len(rate_limiter._export_state.request_times) == 1

    def test_sync_wait_cleans_old_timestamps(self) -> None:
        """_wait_for_rate_limit_sync should clean old timestamps."""
        rate_limiter = MixpanelRateLimitMiddleware()
        state = rate_limiter._query_state
        config = rate_limiter.query_config

        # Add an old timestamp (more than 1 hour ago)
        old_time = time.time() - 4000
        state.request_times.append(old_time)

        rate_limiter._wait_for_rate_limit_sync(state, config)

        # Old timestamp should be removed
        assert old_time not in state.request_times

    def test_sync_wait_timeout_raises_error(self) -> None:
        """_wait_for_rate_limit_sync should raise ToolError on timeout."""
        # Very low limit to easily hit it
        config = RateLimitConfig(hourly_limit=1, concurrent_limit=10)
        rate_limiter = MixpanelRateLimitMiddleware(query_config=config)
        state = rate_limiter._query_state

        # Fill up the limit with a recent timestamp
        now = time.time()
        state.request_times.append(now - 0.5)  # Recent, at limit

        # Should timeout with very short max_wait
        with pytest.raises(ToolError) as exc_info:
            rate_limiter._wait_for_rate_limit_sync(state, config, max_wait=0.01)

        assert "Rate limit timeout" in str(exc_info.value)

    def test_sync_wait_logs_when_rate_limited(self) -> None:
        """_wait_for_rate_limit_sync should log when rate limited."""
        config = RateLimitConfig(hourly_limit=1, concurrent_limit=10)
        rate_limiter = MixpanelRateLimitMiddleware(query_config=config)
        state = rate_limiter._query_state

        # Fill up the limit with a recent timestamp
        now = time.time()
        state.request_times.append(now - 0.5)

        with patch("mp_mcp_server.middleware.rate_limiting.logger") as mock_logger:
            with pytest.raises(ToolError):
                rate_limiter._wait_for_rate_limit_sync(state, config, max_wait=0.1)

            # Should have logged rate limit info
            assert mock_logger.info.called

    def test_sync_wait_per_second_limiting(self) -> None:
        """_wait_for_rate_limit_sync should handle per-second limiting."""
        config = RateLimitConfig(
            hourly_limit=1000,
            concurrent_limit=100,
            per_second_limit=1,
        )
        rate_limiter = MixpanelRateLimitMiddleware(export_config=config)
        state = rate_limiter._export_state

        # Fill up per-second limit
        now = time.time()
        state.per_second_times.append(now - 0.5)  # Recent, at limit

        # Should timeout since we hit per-second limit
        with pytest.raises(ToolError) as exc_info:
            rate_limiter._wait_for_rate_limit_sync(state, config, max_wait=0.01)

        assert "Rate limit timeout" in str(exc_info.value)

    def test_sync_wait_waits_and_succeeds(self) -> None:
        """_wait_for_rate_limit_sync should wait and eventually succeed."""
        config = RateLimitConfig(hourly_limit=1, concurrent_limit=10)
        rate_limiter = MixpanelRateLimitMiddleware(query_config=config)
        state = rate_limiter._query_state

        # Add a timestamp that will expire soon (just over 1 hour ago)
        old_time = time.time() - 3601  # Just over an hour ago
        state.request_times.append(old_time)

        # Should succeed immediately since old timestamp is stale
        rate_limiter._wait_for_rate_limit_sync(state, config, max_wait=1.0)

        # Old timestamp should be cleaned up, new one added
        assert old_time not in state.request_times
        assert len(state.request_times) == 1
