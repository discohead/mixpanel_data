"""Unit tests for FetcherService.

Tests use mocked API client and storage engine for deterministic behavior.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from mixpanel_data._internal.services.fetcher import (
    FetcherService,
    _transform_event,
    _transform_profile,
)
from mixpanel_data.exceptions import TableExistsError

# =============================================================================
# Transform Function Tests
# =============================================================================


class TestTransformEvent:
    """Tests for _transform_event function."""

    def test_transform_event_with_valid_data(self) -> None:
        """_transform_event should transform API event to storage format."""
        api_event = {
            "event": "Sign Up",
            "properties": {
                "distinct_id": "user_123",
                "time": 1609459200,
                "$insert_id": "abc-123-def",
                "browser": "Chrome",
                "country": "US",
            },
        }

        result = _transform_event(api_event)

        assert result["event_name"] == "Sign Up"
        # Unix timestamp 1609459200 = 2021-01-01 00:00:00 UTC
        assert result["event_time"] == datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert result["distinct_id"] == "user_123"
        assert result["insert_id"] == "abc-123-def"
        assert result["properties"] == {"browser": "Chrome", "country": "US"}

    def test_transform_event_with_missing_insert_id(self) -> None:
        """_transform_event should generate UUID when $insert_id is missing."""
        api_event = {
            "event": "Page View",
            "properties": {
                "distinct_id": "user_456",
                "time": 1609459300,
                "page": "/home",
            },
        }

        result = _transform_event(api_event)

        assert result["event_name"] == "Page View"
        assert result["distinct_id"] == "user_456"
        assert result["insert_id"] is not None
        assert len(result["insert_id"]) == 36  # UUID length
        assert result["properties"] == {"page": "/home"}

    def test_transform_event_does_not_mutate_input(self) -> None:
        """_transform_event should not mutate the input dictionary."""
        api_event = {
            "event": "Test Event",
            "properties": {
                "distinct_id": "user_789",
                "time": 1609459400,
                "$insert_id": "xyz-789",
                "extra": "data",
            },
        }

        # Make a deep copy for comparison
        original_props = dict(api_event["properties"])

        _transform_event(api_event)

        # Original should be unchanged
        assert api_event["properties"] == original_props

    def test_transform_event_with_empty_properties(self) -> None:
        """_transform_event should handle empty properties."""
        api_event = {
            "event": "Empty Event",
            "properties": {
                "distinct_id": "user_000",
                "time": 1609459500,
                "$insert_id": "empty-id",
            },
        }

        result = _transform_event(api_event)

        assert result["event_name"] == "Empty Event"
        assert result["properties"] == {}

    def test_transform_event_with_missing_event_key(self) -> None:
        """_transform_event should handle missing event key."""
        api_event = {
            "properties": {
                "distinct_id": "user_111",
                "time": 1609459600,
                "$insert_id": "no-event-key",
            },
        }

        result = _transform_event(api_event)

        assert result["event_name"] == ""

    def test_transform_event_with_missing_properties(self) -> None:
        """_transform_event should handle missing properties."""
        api_event = {
            "event": "No Properties",
        }

        result = _transform_event(api_event)

        assert result["event_name"] == "No Properties"
        assert result["distinct_id"] == ""
        # Unix timestamp 0 = 1970-01-01 00:00:00 UTC (epoch)
        assert result["event_time"] == datetime(1970, 1, 1, 0, 0, 0, tzinfo=UTC)


class TestTransformProfile:
    """Tests for _transform_profile function."""

    def test_transform_profile_with_valid_data(self) -> None:
        """_transform_profile should transform API profile to storage format."""
        api_profile = {
            "$distinct_id": "user_123",
            "$properties": {
                "$last_seen": "2024-01-15T10:30:00",
                "$email": "user@example.com",
                "plan": "premium",
            },
        }

        result = _transform_profile(api_profile)

        assert result["distinct_id"] == "user_123"
        assert result["last_seen"] == "2024-01-15T10:30:00"
        assert result["properties"] == {
            "$email": "user@example.com",
            "plan": "premium",
        }

    def test_transform_profile_with_missing_last_seen(self) -> None:
        """_transform_profile should return None when $last_seen is missing."""
        api_profile = {
            "$distinct_id": "user_456",
            "$properties": {
                "$email": "another@example.com",
                "status": "active",
            },
        }

        result = _transform_profile(api_profile)

        assert result["distinct_id"] == "user_456"
        assert result["last_seen"] is None
        assert result["properties"] == {
            "$email": "another@example.com",
            "status": "active",
        }

    def test_transform_profile_does_not_mutate_input(self) -> None:
        """_transform_profile should not mutate the input dictionary."""
        api_profile = {
            "$distinct_id": "user_789",
            "$properties": {
                "$last_seen": "2024-01-16T12:00:00",
                "extra": "data",
            },
        }

        # Make a deep copy for comparison
        original_props = dict(api_profile["$properties"])

        _transform_profile(api_profile)

        # Original should be unchanged
        assert api_profile["$properties"] == original_props

    def test_transform_profile_with_empty_properties(self) -> None:
        """_transform_profile should handle empty properties."""
        api_profile = {
            "$distinct_id": "user_000",
            "$properties": {
                "$last_seen": "2024-01-17T08:00:00",
            },
        }

        result = _transform_profile(api_profile)

        assert result["distinct_id"] == "user_000"
        assert result["last_seen"] == "2024-01-17T08:00:00"
        assert result["properties"] == {}

    def test_transform_profile_with_missing_distinct_id(self) -> None:
        """_transform_profile should handle missing $distinct_id."""
        api_profile = {
            "$properties": {
                "$last_seen": "2024-01-18T09:00:00",
            },
        }

        result = _transform_profile(api_profile)

        assert result["distinct_id"] == ""

    def test_transform_profile_with_missing_properties(self) -> None:
        """_transform_profile should handle missing $properties."""
        api_profile = {
            "$distinct_id": "user_111",
        }

        result = _transform_profile(api_profile)

        assert result["distinct_id"] == "user_111"
        assert result["last_seen"] is None
        assert result["properties"] == {}


# =============================================================================
# FetcherService Initialization Tests
# =============================================================================


class TestFetcherServiceInit:
    """Tests for FetcherService initialization."""

    def test_init_stores_dependencies(self) -> None:
        """FetcherService should store api_client and storage as private attributes."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        fetcher = FetcherService(mock_api_client, mock_storage)

        assert fetcher._api_client is mock_api_client
        assert fetcher._storage is mock_storage


# =============================================================================
# User Story 1: fetch_events Tests
# =============================================================================


class TestFetchEvents:
    """Tests for FetcherService.fetch_events()."""

    def test_fetch_events_with_mocked_api_client(self) -> None:
        """fetch_events should call API client and storage with correct parameters."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        # Setup API client to return an iterator
        def mock_export() -> Iterator[dict[str, Any]]:
            yield {
                "event": "Sign Up",
                "properties": {
                    "distinct_id": "user_1",
                    "time": 1609459200,
                    "$insert_id": "id-1",
                },
            }
            yield {
                "event": "Login",
                "properties": {
                    "distinct_id": "user_2",
                    "time": 1609459300,
                    "$insert_id": "id-2",
                },
            }

        mock_api_client.export_events.return_value = mock_export()
        mock_storage.create_events_table.return_value = 2

        fetcher = FetcherService(mock_api_client, mock_storage)

        result = fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        # Verify API client was called correctly
        mock_api_client.export_events.assert_called_once()
        call_kwargs = mock_api_client.export_events.call_args.kwargs
        assert call_kwargs["from_date"] == "2024-01-01"
        assert call_kwargs["to_date"] == "2024-01-31"
        assert call_kwargs["events"] is None
        assert call_kwargs["where"] is None

        # Verify storage was called
        mock_storage.create_events_table.assert_called_once()
        storage_call = mock_storage.create_events_table.call_args
        assert storage_call.kwargs["name"] == "test_events"

        # Verify result
        assert result.table == "test_events"
        assert result.rows == 2
        assert result.type == "events"
        assert result.date_range == ("2024-01-01", "2024-01-31")
        assert isinstance(result.fetched_at, datetime)

    def test_fetch_events_with_filters(self) -> None:
        """fetch_events should pass event filter and where clause to API."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_events(
            name="filtered_events",
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=["Sign Up", "Purchase"],
            where='properties["amount"] > 100',
        )

        call_kwargs = mock_api_client.export_events.call_args.kwargs
        assert call_kwargs["events"] == ["Sign Up", "Purchase"]
        assert call_kwargs["where"] == 'properties["amount"] > 100'

    def test_fetch_events_table_exists_error(self) -> None:
        """fetch_events should propagate TableExistsError from storage."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.side_effect = TableExistsError(
            "Table 'existing' already exists"
        )

        fetcher = FetcherService(mock_api_client, mock_storage)

        with pytest.raises(TableExistsError) as exc_info:
            fetcher.fetch_events(
                name="existing",
                from_date="2024-01-01",
                to_date="2024-01-31",
            )

        assert "existing" in str(exc_info.value)

    def test_fetch_events_progress_callback(self) -> None:
        """fetch_events should forward progress callback to API client."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        captured_callback = None

        def capture_on_batch(**kwargs: Any) -> Iterator[dict[str, Any]]:
            nonlocal captured_callback
            captured_callback = kwargs.get("on_batch")
            return iter([])

        mock_api_client.export_events.side_effect = capture_on_batch
        mock_storage.create_events_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        progress_values: list[int] = []

        def progress_callback(count: int) -> None:
            progress_values.append(count)

        fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
            progress_callback=progress_callback,
        )

        # Verify callback was captured and forwarding works
        assert captured_callback is not None
        captured_callback(1000)
        captured_callback(2000)
        assert progress_values == [1000, 2000]

    def test_fetch_events_metadata_construction(self) -> None:
        """fetch_events should construct TableMetadata with correct values."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=["Sign Up"],
            where='properties["country"] == "US"',
        )

        # Get the metadata passed to storage
        storage_call = mock_storage.create_events_table.call_args
        metadata = storage_call.kwargs["metadata"]

        assert metadata.type == "events"
        assert metadata.from_date == "2024-01-01"
        assert metadata.to_date == "2024-01-31"
        assert metadata.filter_events == ["Sign Up"]
        assert metadata.filter_where == 'properties["country"] == "US"'
        assert isinstance(metadata.fetched_at, datetime)

    def test_fetch_events_result_timing(self) -> None:
        """fetch_events should calculate accurate duration."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        # Duration should be a positive float
        assert isinstance(result.duration_seconds, float)
        assert result.duration_seconds >= 0


# =============================================================================
# User Story 2: fetch_profiles Tests
# =============================================================================


class TestFetchProfiles:
    """Tests for FetcherService.fetch_profiles()."""

    def test_fetch_profiles_with_mocked_api_client(self) -> None:
        """fetch_profiles should call API client and storage with correct parameters."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        def mock_export() -> Iterator[dict[str, Any]]:
            yield {
                "$distinct_id": "user_1",
                "$properties": {
                    "$last_seen": "2024-01-15T10:00:00",
                    "plan": "premium",
                },
            }
            yield {
                "$distinct_id": "user_2",
                "$properties": {
                    "$last_seen": "2024-01-16T11:00:00",
                    "plan": "free",
                },
            }

        mock_api_client.export_profiles.return_value = mock_export()
        mock_storage.create_profiles_table.return_value = 2

        fetcher = FetcherService(mock_api_client, mock_storage)

        result = fetcher.fetch_profiles(name="test_profiles")

        # Verify API client was called correctly
        mock_api_client.export_profiles.assert_called_once()
        call_kwargs = mock_api_client.export_profiles.call_args.kwargs
        assert call_kwargs["where"] is None

        # Verify storage was called
        mock_storage.create_profiles_table.assert_called_once()
        storage_call = mock_storage.create_profiles_table.call_args
        assert storage_call.kwargs["name"] == "test_profiles"

        # Verify result
        assert result.table == "test_profiles"
        assert result.rows == 2
        assert result.type == "profiles"
        assert result.date_range is None
        assert isinstance(result.fetched_at, datetime)

    def test_fetch_profiles_with_where_filter(self) -> None:
        """fetch_profiles should pass where clause to API."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_profiles.return_value = iter([])
        mock_storage.create_profiles_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_profiles(
            name="premium_profiles",
            where='user["plan"] == "premium"',
        )

        call_kwargs = mock_api_client.export_profiles.call_args.kwargs
        assert call_kwargs["where"] == 'user["plan"] == "premium"'

    def test_fetch_profiles_table_exists_error(self) -> None:
        """fetch_profiles should propagate TableExistsError from storage."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_profiles.return_value = iter([])
        mock_storage.create_profiles_table.side_effect = TableExistsError(
            "Table 'existing_profiles' already exists"
        )

        fetcher = FetcherService(mock_api_client, mock_storage)

        with pytest.raises(TableExistsError) as exc_info:
            fetcher.fetch_profiles(name="existing_profiles")

        assert "existing_profiles" in str(exc_info.value)

    def test_fetch_profiles_progress_callback(self) -> None:
        """fetch_profiles should forward progress callback to API client."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        captured_callback = None

        def capture_on_batch(**kwargs: Any) -> Iterator[dict[str, Any]]:
            nonlocal captured_callback
            captured_callback = kwargs.get("on_batch")
            return iter([])

        mock_api_client.export_profiles.side_effect = capture_on_batch
        mock_storage.create_profiles_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        progress_values: list[int] = []

        def progress_callback(count: int) -> None:
            progress_values.append(count)

        fetcher.fetch_profiles(
            name="profiles",
            progress_callback=progress_callback,
        )

        # Verify callback was captured and forwarding works
        assert captured_callback is not None
        captured_callback(100)
        captured_callback(200)
        assert progress_values == [100, 200]

    def test_fetch_profiles_metadata_has_no_dates(self) -> None:
        """fetch_profiles should construct TableMetadata with None dates."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_profiles.return_value = iter([])
        mock_storage.create_profiles_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_profiles(
            name="profiles",
            where='user["status"] == "active"',
        )

        # Get the metadata passed to storage
        storage_call = mock_storage.create_profiles_table.call_args
        metadata = storage_call.kwargs["metadata"]

        assert metadata.type == "profiles"
        assert metadata.from_date is None
        assert metadata.to_date is None
        assert metadata.filter_events is None
        assert metadata.filter_where == 'user["status"] == "active"'
        assert isinstance(metadata.fetched_at, datetime)

    def test_fetch_profiles_result_has_none_date_range(self) -> None:
        """fetch_profiles should return FetchResult with date_range=None."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_profiles.return_value = iter([])
        mock_storage.create_profiles_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        result = fetcher.fetch_profiles(name="profiles")

        assert result.date_range is None
