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
    _transform_profile,
)
from mixpanel_data._internal.transforms import transform_event
from mixpanel_data.exceptions import DateRangeTooLargeError, TableExistsError
from mixpanel_data.types import FetchResult

# =============================================================================
# Transform Function Tests
# =============================================================================


class TestTransformEvent:
    """Tests for transform_event function."""

    def testtransform_event_with_valid_data(self) -> None:
        """transform_event should transform API event to storage format."""
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

        result = transform_event(api_event)

        assert result["event_name"] == "Sign Up"
        # Unix timestamp 1609459200 = 2021-01-01 00:00:00 UTC
        assert result["event_time"] == datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert result["distinct_id"] == "user_123"
        assert result["insert_id"] == "abc-123-def"
        assert result["properties"] == {"browser": "Chrome", "country": "US"}

    def testtransform_event_with_missing_insert_id(self) -> None:
        """transform_event should generate UUID when $insert_id is missing."""
        api_event = {
            "event": "Page View",
            "properties": {
                "distinct_id": "user_456",
                "time": 1609459300,
                "page": "/home",
            },
        }

        result = transform_event(api_event)

        assert result["event_name"] == "Page View"
        assert result["distinct_id"] == "user_456"
        assert result["insert_id"] is not None
        assert len(result["insert_id"]) == 36  # UUID length
        assert result["properties"] == {"page": "/home"}

    def testtransform_event_does_not_mutate_input(self) -> None:
        """transform_event should not mutate the input dictionary."""
        api_event: dict[str, Any] = {
            "event": "Test Event",
            "properties": {
                "distinct_id": "user_789",
                "time": 1609459400,
                "$insert_id": "xyz-789",
                "extra": "data",
            },
        }

        # Make a copy for comparison
        original_props = api_event["properties"].copy()

        transform_event(api_event)

        # Original should be unchanged
        assert api_event["properties"] == original_props

    def testtransform_event_with_empty_properties(self) -> None:
        """transform_event should handle empty properties."""
        api_event = {
            "event": "Empty Event",
            "properties": {
                "distinct_id": "user_000",
                "time": 1609459500,
                "$insert_id": "empty-id",
            },
        }

        result = transform_event(api_event)

        assert result["event_name"] == "Empty Event"
        assert result["properties"] == {}

    def testtransform_event_with_missing_event_key(self) -> None:
        """transform_event should handle missing event key."""
        api_event = {
            "properties": {
                "distinct_id": "user_111",
                "time": 1609459600,
                "$insert_id": "no-event-key",
            },
        }

        result = transform_event(api_event)

        assert result["event_name"] == ""

    def testtransform_event_with_missing_properties(self) -> None:
        """transform_event should handle missing properties."""
        api_event = {
            "event": "No Properties",
        }

        result = transform_event(api_event)

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
        api_profile: dict[str, Any] = {
            "$distinct_id": "user_789",
            "$properties": {
                "$last_seen": "2024-01-16T12:00:00",
                "extra": "data",
            },
        }

        # Make a copy for comparison
        original_props = api_profile["$properties"].copy()

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

        # Verify result (sequential fetch returns FetchResult)
        assert isinstance(result, FetchResult)
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

    def test_fetch_profiles_passes_cohort_id_to_api_client(self) -> None:
        """fetch_profiles should pass cohort_id to API client."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_profiles.return_value = iter([])
        mock_storage.create_profiles_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_profiles(
            name="cohort_profiles",
            cohort_id="cohort_12345",
        )

        call_kwargs = mock_api_client.export_profiles.call_args.kwargs
        assert call_kwargs["cohort_id"] == "cohort_12345"

    def test_fetch_profiles_passes_output_properties_to_api_client(self) -> None:
        """fetch_profiles should pass output_properties to API client."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_profiles.return_value = iter([])
        mock_storage.create_profiles_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_profiles(
            name="limited_profiles",
            output_properties=["$email", "$name", "plan"],
        )

        call_kwargs = mock_api_client.export_profiles.call_args.kwargs
        assert call_kwargs["output_properties"] == ["$email", "$name", "plan"]

    def test_fetch_profiles_metadata_includes_cohort_id(self) -> None:
        """fetch_profiles should include cohort_id in metadata."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_profiles.return_value = iter([])
        mock_storage.create_profiles_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_profiles(
            name="profiles",
            cohort_id="cohort_abc",
        )

        # Get the metadata passed to storage
        call_kwargs = mock_storage.create_profiles_table.call_args.kwargs
        metadata = call_kwargs["metadata"]
        assert metadata.filter_cohort_id == "cohort_abc"

    def test_fetch_profiles_metadata_includes_output_properties(self) -> None:
        """fetch_profiles should include output_properties in metadata."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_profiles.return_value = iter([])
        mock_storage.create_profiles_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_profiles(
            name="profiles",
            output_properties=["$email"],
        )

        # Get the metadata passed to storage
        call_kwargs = mock_storage.create_profiles_table.call_args.kwargs
        metadata = call_kwargs["metadata"]
        assert metadata.filter_output_properties == ["$email"]

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


# =============================================================================
# Date Range Validation Tests
# =============================================================================


class TestDateRangeValidation:
    """Tests for FetcherService._validate_date_range()."""

    def test_valid_date_range_within_limit(self) -> None:
        """Should accept valid date ranges within 100 days."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()
        fetcher = FetcherService(mock_api_client, mock_storage)

        # Should not raise for 30-day range
        fetcher._validate_date_range("2024-01-01", "2024-01-30")

    def test_valid_date_range_exactly_100_days(self) -> None:
        """Should accept exactly 100 days (inclusive)."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()
        fetcher = FetcherService(mock_api_client, mock_storage)

        # 100 days: Jan 1 to Apr 9 (inclusive)
        fetcher._validate_date_range("2024-01-01", "2024-04-09")

    def test_date_range_too_large_raises_error(self) -> None:
        """Should raise DateRangeTooLargeError for ranges over 100 days."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()
        fetcher = FetcherService(mock_api_client, mock_storage)

        with pytest.raises(DateRangeTooLargeError) as exc_info:
            fetcher._validate_date_range("2024-01-01", "2024-06-30")

        assert exc_info.value.from_date == "2024-01-01"
        assert exc_info.value.to_date == "2024-06-30"
        assert exc_info.value.days_requested == 182
        assert exc_info.value.max_days == 100

    def test_invalid_date_format_raises_value_error(self) -> None:
        """Should raise ValueError for invalid date format."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()
        fetcher = FetcherService(mock_api_client, mock_storage)

        with pytest.raises(ValueError) as exc_info:
            fetcher._validate_date_range("01-01-2024", "2024-01-31")

        assert "Invalid date format" in str(exc_info.value)

    def test_from_date_after_to_date_raises_value_error(self) -> None:
        """Should raise ValueError when from_date is after to_date."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()
        fetcher = FetcherService(mock_api_client, mock_storage)

        with pytest.raises(ValueError) as exc_info:
            fetcher._validate_date_range("2024-02-01", "2024-01-01")

        assert "must be before or equal to" in str(exc_info.value)

    def test_same_day_range_is_valid(self) -> None:
        """Should accept same-day range (1 day)."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()
        fetcher = FetcherService(mock_api_client, mock_storage)

        # Same day = 1 day, which is valid
        fetcher._validate_date_range("2024-01-15", "2024-01-15")

    def test_fetch_events_validates_date_range(self) -> None:
        """fetch_events should validate date range before calling API."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()
        fetcher = FetcherService(mock_api_client, mock_storage)

        with pytest.raises(DateRangeTooLargeError):
            fetcher.fetch_events(
                name="test_events",
                from_date="2024-01-01",
                to_date="2024-12-31",
            )

        # API should NOT have been called since validation failed first
        mock_api_client.export_events.assert_not_called()


# =============================================================================
# Append Mode Tests
# =============================================================================


class TestFetchEventsAppend:
    """Tests for FetcherService.fetch_events() with append=True."""

    def test_fetch_events_append_calls_append_method(self) -> None:
        """fetch_events with append=True should call append_events_table."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        def mock_export() -> Iterator[dict[str, Any]]:
            yield {
                "event": "Event",
                "properties": {
                    "distinct_id": "user_1",
                    "time": 1609459200,
                    "$insert_id": "id-1",
                },
            }

        mock_api_client.export_events.return_value = mock_export()
        mock_storage.append_events_table.return_value = 1

        fetcher = FetcherService(mock_api_client, mock_storage)

        result = fetcher.fetch_events(
            name="existing_events",
            from_date="2024-01-15",
            to_date="2024-01-15",
            append=True,
        )

        # Should call append, not create
        mock_storage.append_events_table.assert_called_once()
        mock_storage.create_events_table.assert_not_called()

        # Verify result (sequential fetch returns FetchResult)
        assert isinstance(result, FetchResult)
        assert result.table == "existing_events"
        assert result.rows == 1

    def test_fetch_events_append_false_calls_create_method(self) -> None:
        """fetch_events with append=False (default) should call create_events_table."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        def mock_export() -> Iterator[dict[str, Any]]:
            yield {
                "event": "Event",
                "properties": {
                    "distinct_id": "user_1",
                    "time": 1609459200,
                    "$insert_id": "id-1",
                },
            }

        mock_api_client.export_events.return_value = mock_export()
        mock_storage.create_events_table.return_value = 1

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_events(
            name="new_events",
            from_date="2024-01-15",
            to_date="2024-01-15",
            append=False,
        )

        # Should call create, not append
        mock_storage.create_events_table.assert_called_once()
        mock_storage.append_events_table.assert_not_called()


class TestFetchProfilesAppend:
    """Tests for FetcherService.fetch_profiles() with append=True."""

    def test_fetch_profiles_append_calls_append_method(self) -> None:
        """fetch_profiles with append=True should call append_profiles_table."""
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

        mock_api_client.export_profiles.return_value = mock_export()
        mock_storage.append_profiles_table.return_value = 1

        fetcher = FetcherService(mock_api_client, mock_storage)

        result = fetcher.fetch_profiles(
            name="existing_profiles",
            append=True,
        )

        # Should call append, not create
        mock_storage.append_profiles_table.assert_called_once()
        mock_storage.create_profiles_table.assert_not_called()

        # Verify result
        assert result.table == "existing_profiles"
        assert result.rows == 1

    def test_fetch_profiles_append_false_calls_create_method(self) -> None:
        """fetch_profiles with append=False (default) should call create_profiles_table."""
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

        mock_api_client.export_profiles.return_value = mock_export()
        mock_storage.create_profiles_table.return_value = 1

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_profiles(
            name="new_profiles",
            append=False,
        )

        # Should call create, not append
        mock_storage.create_profiles_table.assert_called_once()
        mock_storage.append_profiles_table.assert_not_called()


# =============================================================================
# Batch Size Parameter Tests
# =============================================================================


class TestFetchEventsBatchSize:
    """Tests for batch_size parameter in fetch_events."""

    def test_fetch_events_passes_batch_size_to_create(self) -> None:
        """fetch_events should pass batch_size to create_events_table."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        def mock_export() -> Iterator[dict[str, Any]]:
            yield {
                "event": "Event",
                "properties": {
                    "distinct_id": "user_1",
                    "time": 1609459200,
                    "$insert_id": "id-1",
                },
            }

        mock_api_client.export_events.return_value = mock_export()
        mock_storage.create_events_table.return_value = 1

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
            batch_size=500,
        )

        # Verify batch_size was passed to storage
        call_kwargs = mock_storage.create_events_table.call_args.kwargs
        assert call_kwargs.get("batch_size") == 500

    def test_fetch_events_passes_batch_size_to_append(self) -> None:
        """fetch_events with append=True should pass batch_size to append_events_table."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        def mock_export() -> Iterator[dict[str, Any]]:
            yield {
                "event": "Event",
                "properties": {
                    "distinct_id": "user_1",
                    "time": 1609459200,
                    "$insert_id": "id-1",
                },
            }

        mock_api_client.export_events.return_value = mock_export()
        mock_storage.append_events_table.return_value = 1

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
            append=True,
            batch_size=250,
        )

        # Verify batch_size was passed to storage
        call_kwargs = mock_storage.append_events_table.call_args.kwargs
        assert call_kwargs.get("batch_size") == 250

    def test_fetch_events_default_batch_size(self) -> None:
        """fetch_events should use default batch_size of 1000."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        def mock_export() -> Iterator[dict[str, Any]]:
            yield {
                "event": "Event",
                "properties": {
                    "distinct_id": "user_1",
                    "time": 1609459200,
                    "$insert_id": "id-1",
                },
            }

        mock_api_client.export_events.return_value = mock_export()
        mock_storage.create_events_table.return_value = 1

        fetcher = FetcherService(mock_api_client, mock_storage)

        # Don't specify batch_size - should use default
        fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        # Verify default batch_size of 1000
        call_kwargs = mock_storage.create_events_table.call_args.kwargs
        assert call_kwargs.get("batch_size") == 1000


class TestFetchEventsLimit:
    """Tests for limit parameter in fetch_events."""

    def test_fetch_events_passes_limit_to_api_client(self) -> None:
        """fetch_events should pass limit to API client."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        def mock_export() -> Iterator[dict[str, Any]]:
            yield {
                "event": "Event",
                "properties": {
                    "distinct_id": "user_1",
                    "time": 1609459200,
                    "$insert_id": "id-1",
                },
            }

        mock_api_client.export_events.return_value = mock_export()
        mock_storage.create_events_table.return_value = 1

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
            limit=5000,
        )

        # Verify limit was passed to API client
        call_kwargs = mock_api_client.export_events.call_args.kwargs
        assert call_kwargs.get("limit") == 5000

    def test_fetch_events_no_limit_by_default(self) -> None:
        """fetch_events should not pass limit when not specified."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        def mock_export() -> Iterator[dict[str, Any]]:
            yield {
                "event": "Event",
                "properties": {
                    "distinct_id": "user_1",
                    "time": 1609459200,
                    "$insert_id": "id-1",
                },
            }

        mock_api_client.export_events.return_value = mock_export()
        mock_storage.create_events_table.return_value = 1

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        # Verify limit is None by default
        call_kwargs = mock_api_client.export_events.call_args.kwargs
        assert call_kwargs.get("limit") is None


class TestFetchProfilesBatchSize:
    """Tests for batch_size parameter in fetch_profiles."""

    def test_fetch_profiles_passes_batch_size_to_create(self) -> None:
        """fetch_profiles should pass batch_size to create_profiles_table."""
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

        mock_api_client.export_profiles.return_value = mock_export()
        mock_storage.create_profiles_table.return_value = 1

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_profiles(
            name="profiles",
            batch_size=500,
        )

        # Verify batch_size was passed to storage
        call_kwargs = mock_storage.create_profiles_table.call_args.kwargs
        assert call_kwargs.get("batch_size") == 500

    def test_fetch_profiles_passes_batch_size_to_append(self) -> None:
        """fetch_profiles with append=True should pass batch_size to append_profiles_table."""
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

        mock_api_client.export_profiles.return_value = mock_export()
        mock_storage.append_profiles_table.return_value = 1

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_profiles(
            name="profiles",
            append=True,
            batch_size=250,
        )

        # Verify batch_size was passed to storage
        call_kwargs = mock_storage.append_profiles_table.call_args.kwargs
        assert call_kwargs.get("batch_size") == 250


# =============================================================================
# Parallel Fetch Delegation Tests (Feature 017)
# =============================================================================


class TestFetchEventsParallel:
    """Tests for parallel fetch delegation in FetcherService."""

    def test_parallel_false_uses_sequential_fetch(self) -> None:
        """fetch_events with parallel=False (default) uses sequential fetch."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        def mock_export() -> Iterator[dict[str, Any]]:
            yield {
                "event": "Event",
                "properties": {
                    "distinct_id": "user_1",
                    "time": 1609459200,
                    "$insert_id": "id-1",
                },
            }

        mock_api_client.export_events.return_value = mock_export()
        mock_storage.create_events_table.return_value = 1

        fetcher = FetcherService(mock_api_client, mock_storage)

        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
            parallel=False,
        )

        # Should return FetchResult (not ParallelFetchResult)
        from mixpanel_data.types import FetchResult

        assert isinstance(result, FetchResult)

    def test_parallel_true_returns_parallel_fetch_result(self) -> None:
        """fetch_events with parallel=True returns ParallelFetchResult."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
            parallel=True,
        )

        # Should return ParallelFetchResult
        from mixpanel_data.types import ParallelFetchResult

        assert isinstance(result, ParallelFetchResult)

    def test_parallel_with_max_workers(self) -> None:
        """fetch_events with parallel=True respects max_workers."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
            parallel=True,
            max_workers=5,
        )

        from mixpanel_data.types import ParallelFetchResult

        assert isinstance(result, ParallelFetchResult)

    def test_parallel_with_on_batch_complete(self) -> None:
        """fetch_events with parallel=True invokes on_batch_complete callback."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        progress_list: list[Any] = []

        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-07",
            parallel=True,
            on_batch_complete=lambda p: progress_list.append(p),
        )

        from mixpanel_data.types import BatchProgress, ParallelFetchResult

        assert isinstance(result, ParallelFetchResult)
        # Should have received at least one progress update
        assert len(progress_list) >= 1
        assert all(isinstance(p, BatchProgress) for p in progress_list)

    def test_parallel_passes_event_filter(self) -> None:
        """fetch_events with parallel=True passes events filter."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-07",
            events=["SignUp", "Purchase"],
            parallel=True,
        )

        # Verify events filter was passed to API
        call_kwargs = mock_api_client.export_events.call_args.kwargs
        assert call_kwargs["events"] == ["SignUp", "Purchase"]

    def test_parallel_passes_where_filter(self) -> None:
        """fetch_events with parallel=True passes where filter."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-07",
            where='properties["country"] == "US"',
            parallel=True,
        )

        # Verify where filter was passed to API
        call_kwargs = mock_api_client.export_events.call_args.kwargs
        assert call_kwargs["where"] == 'properties["country"] == "US"'

    def test_parallel_skips_date_range_validation(self) -> None:
        """fetch_events with parallel=True skips 100-day limit (handles internally)."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        # 120 days would fail with sequential, but parallel should handle it
        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-04-30",  # ~120 days
            parallel=True,
        )

        from mixpanel_data.types import ParallelFetchResult

        assert isinstance(result, ParallelFetchResult)

    def test_parallel_append_mode(self) -> None:
        """fetch_events with parallel=True and append=True works correctly."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        # Return actual mock events so storage methods get called
        mock_api_client.export_events.return_value = iter(
            [
                {
                    "event": "TestEvent",
                    "properties": {
                        "distinct_id": "user1",
                        "time": 1704067200,
                        "$insert_id": "insert1",
                    },
                }
            ]
        )
        mock_storage.append_events_table.return_value = 1

        fetcher = FetcherService(mock_api_client, mock_storage)

        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-07",
            parallel=True,
            append=True,
        )

        from mixpanel_data.types import ParallelFetchResult

        assert isinstance(result, ParallelFetchResult)
        # Append should call append_events_table, not create
        mock_storage.append_events_table.assert_called()

    def test_parallel_with_chunk_days(self) -> None:
        """fetch_events with parallel=True respects chunk_days parameter."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        # 21 days with 3-day chunks = 7 batches
        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-21",
            parallel=True,
            chunk_days=3,
        )

        from mixpanel_data.types import ParallelFetchResult

        assert isinstance(result, ParallelFetchResult)
        # With 21 days and 3-day chunks, should have 7 batches
        assert result.successful_batches == 7

    def test_parallel_default_chunk_days(self) -> None:
        """fetch_events with parallel=True uses default 7-day chunks."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        fetcher = FetcherService(mock_api_client, mock_storage)

        # 21 days with default 7-day chunks = 3 batches
        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-21",
            parallel=True,
        )

        from mixpanel_data.types import ParallelFetchResult

        assert isinstance(result, ParallelFetchResult)
        # With 21 days and 7-day chunks (default), should have 3 batches
        assert result.successful_batches == 3

    def test_chunk_days_ignored_for_sequential_fetch(self) -> None:
        """chunk_days parameter is ignored when parallel=False."""
        mock_api_client = MagicMock()
        mock_storage = MagicMock()

        def mock_export() -> Iterator[dict[str, Any]]:
            yield {
                "event": "Event",
                "properties": {
                    "distinct_id": "user_1",
                    "time": 1609459200,
                    "$insert_id": "id-1",
                },
            }

        mock_api_client.export_events.return_value = mock_export()
        mock_storage.create_events_table.return_value = 1

        fetcher = FetcherService(mock_api_client, mock_storage)

        # chunk_days should be ignored for sequential fetch
        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-21",
            parallel=False,
            chunk_days=3,
        )

        # Should return FetchResult (sequential), not ParallelFetchResult
        from mixpanel_data.types import FetchResult

        assert isinstance(result, FetchResult)
