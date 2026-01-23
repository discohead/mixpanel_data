"""Tests for fetch tools.

These tests verify the data fetching tools are registered and return
correct data from the Workspace.
"""

from unittest.mock import MagicMock

import pytest


class TestFetchEventsTool:
    """Tests for the fetch_events tool."""

    @pytest.mark.asyncio
    async def test_fetch_events_creates_table(self, mock_context: MagicMock) -> None:
        """fetch_events should store events in a DuckDB table."""
        from mp_mcp_server.tools.fetch import fetch_events

        result = await fetch_events(  # type: ignore[operator]
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
        )
        assert "table_name" in result
        assert result["table_name"] == "events_jan"

    @pytest.mark.asyncio
    async def test_fetch_events_returns_fetch_result(
        self, mock_context: MagicMock
    ) -> None:
        """fetch_events should return row count and metadata."""
        from mp_mcp_server.tools.fetch import fetch_events

        result = await fetch_events(  # type: ignore[operator]
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
        )
        assert "row_count" in result
        # 7 days (01-01 to 01-07 inclusive) × 1000 rows per mock call = 7000
        assert result["row_count"] == 7000

    @pytest.mark.asyncio
    async def test_fetch_events_with_date_range(self, mock_context: MagicMock) -> None:
        """fetch_events should accept date range parameters."""
        from mp_mcp_server.tools.fetch import fetch_events

        result = await fetch_events(  # type: ignore[operator]
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-31",
            table="january_events",
        )
        assert "table_name" in result


class TestFetchProfilesTool:
    """Tests for the fetch_profiles tool."""

    @pytest.mark.asyncio
    async def test_fetch_profiles_creates_table(self, mock_context: MagicMock) -> None:
        """fetch_profiles should store profiles in a DuckDB table."""
        from mp_mcp_server.tools.fetch import fetch_profiles

        result = await fetch_profiles(mock_context)  # type: ignore[operator]
        assert "table_name" in result
        assert result["table_name"] == "profiles"

    @pytest.mark.asyncio
    async def test_fetch_profiles_returns_fetch_result(
        self, mock_context: MagicMock
    ) -> None:
        """fetch_profiles should return row count."""
        from mp_mcp_server.tools.fetch import fetch_profiles

        result = await fetch_profiles(mock_context)  # type: ignore[operator]
        assert "row_count" in result
        assert result["row_count"] == 500

    @pytest.mark.asyncio
    async def test_fetch_profiles_with_options(self, mock_context: MagicMock) -> None:
        """fetch_profiles should accept optional parameters."""
        from mp_mcp_server.tools.fetch import fetch_profiles

        result = await fetch_profiles(  # type: ignore[operator]
            mock_context,
            table="my_profiles",
            where="email is not null",
            parallel=True,
            workers=8,
        )
        assert "table_name" in result

    @pytest.mark.asyncio
    async def test_fetch_events_with_parallel(self, mock_context: MagicMock) -> None:
        """fetch_events should accept parallel parameters."""
        from mp_mcp_server.tools.fetch import fetch_events

        result = await fetch_events(  # type: ignore[operator]
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=["login"],
            parallel=True,
            workers=8,
        )
        assert "table_name" in result


class TestStreamEventsTool:
    """Tests for the stream_events tool."""

    def test_stream_events_returns_list(self, mock_context: MagicMock) -> None:
        """stream_events should return list of events."""
        from mp_mcp_server.tools.fetch import stream_events

        result = stream_events(  # type: ignore[operator]
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
        )
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0]["name"] == "login"

    def test_stream_events_with_event_filter(self, mock_context: MagicMock) -> None:
        """stream_events should accept events filter."""
        from mp_mcp_server.tools.fetch import stream_events

        # Reset the mock for fresh iterator
        ws = mock_context.lifespan_context["workspace"]
        ws.stream_events.return_value = iter(
            [{"name": "login", "distinct_id": "user1", "time": 1704067200}]
        )

        result = stream_events(  # type: ignore[operator]
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
            events=["login"],
        )
        assert isinstance(result, list)

    def test_stream_events_respects_limit(self, mock_context: MagicMock) -> None:
        """stream_events should pass limit parameter to workspace."""
        from mp_mcp_server.tools.fetch import stream_events

        # Reset with events - the limit is now passed to ws.stream_events
        ws = mock_context.lifespan_context["workspace"]
        ws.stream_events.return_value = iter(
            [{"event": f"event{i}", "properties": {}} for i in range(5)]
        )

        result = stream_events(  # type: ignore[operator]
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
            limit=5,
        )
        # Verify limit was passed to workspace method
        call_kwargs = ws.stream_events.call_args[1]
        assert call_kwargs["limit"] == 5
        assert call_kwargs["raw"] is True
        assert len(result) == 5


class TestStreamProfilesTool:
    """Tests for the stream_profiles tool."""

    def test_stream_profiles_returns_list(self, mock_context: MagicMock) -> None:
        """stream_profiles should return list of profiles."""
        from mp_mcp_server.tools.fetch import stream_profiles

        # Reset mock
        ws = mock_context.lifespan_context["workspace"]
        ws.stream_profiles.return_value = iter(
            [
                {"$distinct_id": "user1", "$properties": {"email": "a@example.com"}},
                {"$distinct_id": "user2", "$properties": {"email": "b@example.com"}},
            ]
        )

        result = stream_profiles(mock_context)  # type: ignore[operator]
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["$distinct_id"] == "user1"

    def test_stream_profiles_with_where(self, mock_context: MagicMock) -> None:
        """stream_profiles should accept where filter."""
        from mp_mcp_server.tools.fetch import stream_profiles

        ws = mock_context.lifespan_context["workspace"]
        ws.stream_profiles.return_value = iter([{"$distinct_id": "user1"}])

        result = stream_profiles(mock_context, where="email is not null")  # type: ignore[operator]
        assert isinstance(result, list)

    def test_stream_profiles_with_distinct_id(self, mock_context: MagicMock) -> None:
        """stream_profiles should accept distinct_id parameter."""
        from mp_mcp_server.tools.fetch import stream_profiles

        ws = mock_context.lifespan_context["workspace"]
        ws.stream_profiles.return_value = iter(
            [{"$distinct_id": "user1", "$properties": {"email": "a@example.com"}}]
        )

        result = stream_profiles(mock_context, distinct_id="user1")  # type: ignore[operator]
        assert len(result) == 1
        assert result[0]["$distinct_id"] == "user1"
        ws.stream_profiles.assert_called_once()
        call_kwargs = ws.stream_profiles.call_args[1]
        assert call_kwargs["distinct_id"] == "user1"


class TestFetchEventsOptionalParams:
    """Tests for fetch_events optional parameters coverage."""

    @pytest.mark.asyncio
    async def test_fetch_events_with_where_filter(
        self, mock_context: MagicMock
    ) -> None:
        """fetch_events should pass where filter to workspace."""
        from mp_mcp_server.tools.fetch import fetch_events

        ws = mock_context.lifespan_context["workspace"]

        await fetch_events(  # type: ignore[operator]
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
            where='properties["country"] == "US"',
        )

        call_kwargs = ws.fetch_events.call_args[1]
        assert call_kwargs["where"] == 'properties["country"] == "US"'

    @pytest.mark.asyncio
    async def test_fetch_events_with_limit(self, mock_context: MagicMock) -> None:
        """fetch_events should pass limit to workspace."""
        from mp_mcp_server.tools.fetch import fetch_events

        ws = mock_context.lifespan_context["workspace"]

        await fetch_events(  # type: ignore[operator]
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
            limit=500,
        )

        call_kwargs = ws.fetch_events.call_args[1]
        assert call_kwargs["limit"] == 500

    @pytest.mark.asyncio
    async def test_fetch_events_with_append(self, mock_context: MagicMock) -> None:
        """fetch_events should pass append flag to workspace."""
        from mp_mcp_server.tools.fetch import fetch_events

        ws = mock_context.lifespan_context["workspace"]

        await fetch_events(  # type: ignore[operator]
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
            append=True,
        )

        call_kwargs = ws.fetch_events.call_args[1]
        assert call_kwargs["append"] is True


class TestFetchProfilesOptionalParams:
    """Tests for fetch_profiles optional parameters coverage."""

    @pytest.mark.asyncio
    async def test_fetch_profiles_with_cohort_id(
        self, mock_context: MagicMock
    ) -> None:
        """fetch_profiles should pass cohort_id to workspace."""
        from mp_mcp_server.tools.fetch import fetch_profiles

        ws = mock_context.lifespan_context["workspace"]

        await fetch_profiles(mock_context, cohort_id="12345")  # type: ignore[operator]

        call_kwargs = ws.fetch_profiles.call_args[1]
        assert call_kwargs["cohort_id"] == "12345"

    @pytest.mark.asyncio
    async def test_fetch_profiles_with_output_properties(
        self, mock_context: MagicMock
    ) -> None:
        """fetch_profiles should pass output_properties to workspace."""
        from mp_mcp_server.tools.fetch import fetch_profiles

        ws = mock_context.lifespan_context["workspace"]

        await fetch_profiles(mock_context, output_properties=["email", "name"])  # type: ignore[operator]

        call_kwargs = ws.fetch_profiles.call_args[1]
        assert call_kwargs["output_properties"] == ["email", "name"]

    @pytest.mark.asyncio
    async def test_fetch_profiles_with_distinct_id(
        self, mock_context: MagicMock
    ) -> None:
        """fetch_profiles should pass distinct_id to workspace."""
        from mp_mcp_server.tools.fetch import fetch_profiles

        ws = mock_context.lifespan_context["workspace"]

        await fetch_profiles(mock_context, distinct_id="user123")  # type: ignore[operator]

        call_kwargs = ws.fetch_profiles.call_args[1]
        assert call_kwargs["distinct_id"] == "user123"

    @pytest.mark.asyncio
    async def test_fetch_profiles_with_distinct_ids(
        self, mock_context: MagicMock
    ) -> None:
        """fetch_profiles should pass distinct_ids list to workspace."""
        from mp_mcp_server.tools.fetch import fetch_profiles

        ws = mock_context.lifespan_context["workspace"]

        await fetch_profiles(mock_context, distinct_ids=["user1", "user2", "user3"])  # type: ignore[operator]

        call_kwargs = ws.fetch_profiles.call_args[1]
        assert call_kwargs["distinct_ids"] == ["user1", "user2", "user3"]

    @pytest.mark.asyncio
    async def test_fetch_profiles_with_group_id(self, mock_context: MagicMock) -> None:
        """fetch_profiles should pass group_id to workspace."""
        from mp_mcp_server.tools.fetch import fetch_profiles

        ws = mock_context.lifespan_context["workspace"]

        await fetch_profiles(mock_context, group_id="company")  # type: ignore[operator]

        call_kwargs = ws.fetch_profiles.call_args[1]
        assert call_kwargs["group_id"] == "company"

    @pytest.mark.asyncio
    async def test_fetch_profiles_with_append(self, mock_context: MagicMock) -> None:
        """fetch_profiles should pass append flag to workspace."""
        from mp_mcp_server.tools.fetch import fetch_profiles

        ws = mock_context.lifespan_context["workspace"]

        await fetch_profiles(mock_context, append=True)  # type: ignore[operator]

        call_kwargs = ws.fetch_profiles.call_args[1]
        assert call_kwargs["append"] is True

    @pytest.mark.asyncio
    async def test_fetch_profiles_with_behaviors(
        self, mock_context: MagicMock
    ) -> None:
        """fetch_profiles should pass behaviors to workspace."""
        from mp_mcp_server.tools.fetch import fetch_profiles

        ws = mock_context.lifespan_context["workspace"]
        behaviors = [{"event": "login", "count": {"min": 1}}]

        await fetch_profiles(mock_context, behaviors=behaviors)  # type: ignore[operator]

        call_kwargs = ws.fetch_profiles.call_args[1]
        assert call_kwargs["behaviors"] == behaviors

    @pytest.mark.asyncio
    async def test_fetch_profiles_with_as_of_timestamp(
        self, mock_context: MagicMock
    ) -> None:
        """fetch_profiles should pass as_of_timestamp to workspace."""
        from mp_mcp_server.tools.fetch import fetch_profiles

        ws = mock_context.lifespan_context["workspace"]

        await fetch_profiles(mock_context, as_of_timestamp=1704067200)  # type: ignore[operator]

        call_kwargs = ws.fetch_profiles.call_args[1]
        assert call_kwargs["as_of_timestamp"] == 1704067200

    @pytest.mark.asyncio
    async def test_fetch_profiles_with_include_all_users(
        self, mock_context: MagicMock
    ) -> None:
        """fetch_profiles should pass include_all_users to workspace."""
        from mp_mcp_server.tools.fetch import fetch_profiles

        ws = mock_context.lifespan_context["workspace"]

        await fetch_profiles(mock_context, include_all_users=True)  # type: ignore[operator]

        call_kwargs = ws.fetch_profiles.call_args[1]
        assert call_kwargs["include_all_users"] is True


class TestStreamEventsOptionalParams:
    """Tests for stream_events optional parameters coverage."""

    def test_stream_events_with_where_filter(self, mock_context: MagicMock) -> None:
        """stream_events should pass where filter to workspace."""
        from mp_mcp_server.tools.fetch import stream_events

        ws = mock_context.lifespan_context["workspace"]
        ws.stream_events.return_value = iter([{"name": "login"}])

        stream_events(  # type: ignore[operator]
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-07",
            where='properties["platform"] == "mobile"',
        )

        call_kwargs = ws.stream_events.call_args[1]
        assert call_kwargs["where"] == 'properties["platform"] == "mobile"'


class TestStreamProfilesOptionalParams:
    """Tests for stream_profiles optional parameters coverage."""

    def test_stream_profiles_with_cohort_id(self, mock_context: MagicMock) -> None:
        """stream_profiles should pass cohort_id to workspace."""
        from mp_mcp_server.tools.fetch import stream_profiles

        ws = mock_context.lifespan_context["workspace"]
        ws.stream_profiles.return_value = iter([{"$distinct_id": "user1"}])

        stream_profiles(mock_context, cohort_id="12345")  # type: ignore[operator]

        call_kwargs = ws.stream_profiles.call_args[1]
        assert call_kwargs["cohort_id"] == "12345"

    def test_stream_profiles_with_output_properties(
        self, mock_context: MagicMock
    ) -> None:
        """stream_profiles should pass output_properties to workspace."""
        from mp_mcp_server.tools.fetch import stream_profiles

        ws = mock_context.lifespan_context["workspace"]
        ws.stream_profiles.return_value = iter([{"$distinct_id": "user1"}])

        stream_profiles(mock_context, output_properties=["email"])  # type: ignore[operator]

        call_kwargs = ws.stream_profiles.call_args[1]
        assert call_kwargs["output_properties"] == ["email"]

    def test_stream_profiles_with_distinct_ids(self, mock_context: MagicMock) -> None:
        """stream_profiles should pass distinct_ids list to workspace."""
        from mp_mcp_server.tools.fetch import stream_profiles

        ws = mock_context.lifespan_context["workspace"]
        ws.stream_profiles.return_value = iter([{"$distinct_id": "user1"}])

        stream_profiles(mock_context, distinct_ids=["user1", "user2"])  # type: ignore[operator]

        call_kwargs = ws.stream_profiles.call_args[1]
        assert call_kwargs["distinct_ids"] == ["user1", "user2"]

    def test_stream_profiles_with_group_id(self, mock_context: MagicMock) -> None:
        """stream_profiles should pass group_id to workspace."""
        from mp_mcp_server.tools.fetch import stream_profiles

        ws = mock_context.lifespan_context["workspace"]
        ws.stream_profiles.return_value = iter([{"$distinct_id": "company1"}])

        stream_profiles(mock_context, group_id="company")  # type: ignore[operator]

        call_kwargs = ws.stream_profiles.call_args[1]
        assert call_kwargs["group_id"] == "company"

    def test_stream_profiles_with_behaviors(self, mock_context: MagicMock) -> None:
        """stream_profiles should pass behaviors to workspace."""
        from mp_mcp_server.tools.fetch import stream_profiles

        ws = mock_context.lifespan_context["workspace"]
        ws.stream_profiles.return_value = iter([{"$distinct_id": "user1"}])
        behaviors = [{"event": "purchase", "count": {"min": 5}}]

        stream_profiles(mock_context, behaviors=behaviors)  # type: ignore[operator]

        call_kwargs = ws.stream_profiles.call_args[1]
        assert call_kwargs["behaviors"] == behaviors

    def test_stream_profiles_with_as_of_timestamp(
        self, mock_context: MagicMock
    ) -> None:
        """stream_profiles should pass as_of_timestamp to workspace."""
        from mp_mcp_server.tools.fetch import stream_profiles

        ws = mock_context.lifespan_context["workspace"]
        ws.stream_profiles.return_value = iter([{"$distinct_id": "user1"}])

        stream_profiles(mock_context, as_of_timestamp=1704067200)  # type: ignore[operator]

        call_kwargs = ws.stream_profiles.call_args[1]
        assert call_kwargs["as_of_timestamp"] == 1704067200

    def test_stream_profiles_with_include_all_users(
        self, mock_context: MagicMock
    ) -> None:
        """stream_profiles should pass include_all_users to workspace."""
        from mp_mcp_server.tools.fetch import stream_profiles

        ws = mock_context.lifespan_context["workspace"]
        ws.stream_profiles.return_value = iter([{"$distinct_id": "user1"}])

        stream_profiles(mock_context, include_all_users=True)  # type: ignore[operator]

        call_kwargs = ws.stream_profiles.call_args[1]
        assert call_kwargs["include_all_users"] is True
