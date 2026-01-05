"""Unit tests for Workspace streaming methods.

Tests for stream_events() and stream_profiles() methods that
stream data directly from Mixpanel API without local storage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_data import ConfigError, Workspace
from mixpanel_data._internal.config import ConfigManager, Credentials
from mixpanel_data._internal.storage import StorageEngine

if TYPE_CHECKING:
    from collections.abc import Callable


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_credentials() -> Credentials:
    """Create mock credentials for testing."""
    return Credentials(
        username="test_user",
        secret=SecretStr("test_secret"),
        project_id="12345",
        region="us",
    )


@pytest.fixture
def mock_config_manager(mock_credentials: Credentials) -> MagicMock:
    """Create mock ConfigManager that returns credentials."""
    manager = MagicMock(spec=ConfigManager)
    manager.resolve_credentials.return_value = mock_credentials
    return manager


@pytest.fixture
def mock_storage() -> StorageEngine:
    """Create ephemeral storage for testing."""
    return StorageEngine.ephemeral()


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create mock API client for testing."""
    from mixpanel_data._internal.api_client import MixpanelAPIClient

    client = MagicMock(spec=MixpanelAPIClient)
    client.close = MagicMock()
    return client


@pytest.fixture
def workspace_factory(
    mock_config_manager: MagicMock,
    mock_storage: StorageEngine,
    mock_api_client: MagicMock,
) -> Callable[..., Workspace]:
    """Factory for creating Workspace instances with mocked dependencies."""

    def factory(**kwargs: Any) -> Workspace:
        defaults: dict[str, Any] = {
            "_config_manager": mock_config_manager,
            "_storage": mock_storage,
            "_api_client": mock_api_client,
        }
        defaults.update(kwargs)
        return Workspace(**defaults)

    return factory


# =============================================================================
# Sample Data
# =============================================================================


def raw_event(
    name: str = "PageView",
    distinct_id: str = "user_123",
    timestamp: int = 1705328400,
    **extra_props: Any,
) -> dict[str, Any]:
    """Create a raw event in Mixpanel API format."""
    props = {
        "distinct_id": distinct_id,
        "time": timestamp,
        "$insert_id": f"evt_{timestamp}",
        **extra_props,
    }
    return {"event": name, "properties": props}


def raw_profile(
    distinct_id: str = "user_123",
    last_seen: str | None = "2024-01-15T14:30:00",
    **extra_props: Any,
) -> dict[str, Any]:
    """Create a raw profile in Mixpanel API format."""
    props = {**extra_props}
    if last_seen:
        props["$last_seen"] = last_seen
    return {"$distinct_id": distinct_id, "$properties": props}


# =============================================================================
# Phase 3: User Story 1 - Stream Events Tests (T003-T006)
# =============================================================================


class TestStreamEvents:
    """Tests for stream_events() method."""

    def test_stream_events_basic(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T006: Test basic streaming of events with default (normalized) format."""
        ws = workspace_factory()
        try:
            # Set up mock to return raw events
            mock_api_client.export_events.return_value = iter(
                [
                    raw_event("PageView", "user_1", 1705328400, page="/home"),
                    raw_event("Click", "user_2", 1705328500, button="signup"),
                ]
            )

            events = list(
                ws.stream_events(from_date="2024-01-15", to_date="2024-01-15")
            )

            assert len(events) == 2

            # Verify normalized format
            assert events[0]["event_name"] == "PageView"
            assert events[0]["distinct_id"] == "user_1"
            assert isinstance(events[0]["event_time"], datetime)
            assert events[0]["properties"]["page"] == "/home"

            assert events[1]["event_name"] == "Click"
            assert events[1]["distinct_id"] == "user_2"

            # Verify API client was called correctly
            mock_api_client.export_events.assert_called_once_with(
                from_date="2024-01-15",
                to_date="2024-01-15",
                events=None,
                where=None,
                limit=None,
            )
        finally:
            ws.close()

    def test_stream_events_with_event_filter(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T006: Test streaming events with event name filter."""
        ws = workspace_factory()
        try:
            mock_api_client.export_events.return_value = iter(
                [raw_event("Purchase", "user_1", 1705328400, amount=99.99)]
            )

            events = list(
                ws.stream_events(
                    from_date="2024-01-15",
                    to_date="2024-01-15",
                    events=["Purchase", "Signup"],
                )
            )

            assert len(events) == 1
            assert events[0]["event_name"] == "Purchase"

            mock_api_client.export_events.assert_called_once_with(
                from_date="2024-01-15",
                to_date="2024-01-15",
                events=["Purchase", "Signup"],
                where=None,
                limit=None,
            )
        finally:
            ws.close()

    def test_stream_events_with_where_filter(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T006: Test streaming events with WHERE filter."""
        ws = workspace_factory()
        try:
            mock_api_client.export_events.return_value = iter(
                [raw_event("PageView", "user_1", 1705328400, country="US")]
            )

            where_clause = 'properties["country"]=="US"'
            events = list(
                ws.stream_events(
                    from_date="2024-01-15",
                    to_date="2024-01-15",
                    where=where_clause,
                )
            )

            assert len(events) == 1
            assert events[0]["properties"]["country"] == "US"

            mock_api_client.export_events.assert_called_once_with(
                from_date="2024-01-15",
                to_date="2024-01-15",
                events=None,
                where=where_clause,
                limit=None,
            )
        finally:
            ws.close()

    def test_stream_events_raw_true(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T006: Test streaming events with raw=True returns Mixpanel API format."""
        ws = workspace_factory()
        try:
            raw_events = [
                raw_event("PageView", "user_1", 1705328400, page="/home"),
                raw_event("Click", "user_2", 1705328500, button="signup"),
            ]
            mock_api_client.export_events.return_value = iter(raw_events)

            events = list(
                ws.stream_events(from_date="2024-01-15", to_date="2024-01-15", raw=True)
            )

            assert len(events) == 2

            # Verify raw format (Mixpanel API structure)
            assert events[0]["event"] == "PageView"
            assert "properties" in events[0]
            assert events[0]["properties"]["distinct_id"] == "user_1"
            assert events[0]["properties"]["time"] == 1705328400  # Unix timestamp
            assert events[0]["properties"]["$insert_id"] == "evt_1705328400"
        finally:
            ws.close()

    def test_stream_events_raw_false_transforms(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T006: Test streaming events with raw=False (default) transforms data."""
        ws = workspace_factory()
        try:
            mock_api_client.export_events.return_value = iter(
                [raw_event("Purchase", "user_123", 1705328400, amount=49.99)]
            )

            events = list(
                ws.stream_events(
                    from_date="2024-01-15", to_date="2024-01-15", raw=False
                )
            )

            assert len(events) == 1
            event = events[0]

            # Verify normalized format
            assert event["event_name"] == "Purchase"
            assert event["distinct_id"] == "user_123"
            assert isinstance(event["event_time"], datetime)
            assert event["event_time"].tzinfo == UTC
            assert event["insert_id"] == "evt_1705328400"

            # Properties should NOT include distinct_id, time, $insert_id
            assert "distinct_id" not in event["properties"]
            assert "time" not in event["properties"]
            assert "$insert_id" not in event["properties"]
            assert event["properties"]["amount"] == 49.99
        finally:
            ws.close()

    def test_stream_events_empty_result(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Test streaming events returns empty iterator when no events."""
        ws = workspace_factory()
        try:
            mock_api_client.export_events.return_value = iter([])

            events = list(
                ws.stream_events(from_date="2024-01-15", to_date="2024-01-15")
            )

            assert events == []
        finally:
            ws.close()

    def test_stream_events_is_lazy_iterator(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Test stream_events returns a lazy iterator."""
        ws = workspace_factory()
        try:
            call_count = 0

            def mock_iterator() -> Any:
                nonlocal call_count
                for i in range(3):
                    call_count += 1
                    yield raw_event("Event", f"user_{i}", 1705328400 + i)

            mock_api_client.export_events.return_value = mock_iterator()

            # Get iterator but don't consume it
            iterator = ws.stream_events(from_date="2024-01-15", to_date="2024-01-15")

            # No events should have been yielded yet (lazy evaluation)
            assert call_count == 0

            # Consume first event
            next(iterator)
            assert call_count == 1

            # Consume remaining
            list(iterator)
            assert call_count == 3
        finally:
            ws.close()

    def test_stream_events_with_limit(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Test streaming events with limit parameter."""
        ws = workspace_factory()
        try:
            mock_api_client.export_events.return_value = iter(
                [raw_event("Event", "user_1", 1705328400)]
            )

            list(
                ws.stream_events(
                    from_date="2024-01-15", to_date="2024-01-15", limit=5000
                )
            )

            mock_api_client.export_events.assert_called_once_with(
                from_date="2024-01-15",
                to_date="2024-01-15",
                events=None,
                where=None,
                limit=5000,
            )
        finally:
            ws.close()


# =============================================================================
# Phase 4: User Story 3 - Stream Profiles Tests (T007-T010)
# =============================================================================


class TestStreamProfiles:
    """Tests for stream_profiles() method."""

    def test_stream_profiles_basic(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T010: Test basic streaming of profiles with default (normalized) format."""
        ws = workspace_factory()
        try:
            mock_api_client.export_profiles.return_value = iter(
                [
                    raw_profile("user_1", "2024-01-15T10:00:00", name="Alice"),
                    raw_profile("user_2", "2024-01-15T11:00:00", name="Bob"),
                ]
            )

            profiles = list(ws.stream_profiles())

            assert len(profiles) == 2

            # Verify normalized format
            assert profiles[0]["distinct_id"] == "user_1"
            assert profiles[0]["last_seen"] == "2024-01-15T10:00:00"
            assert profiles[0]["properties"]["name"] == "Alice"

            assert profiles[1]["distinct_id"] == "user_2"
            assert profiles[1]["properties"]["name"] == "Bob"

            mock_api_client.export_profiles.assert_called_once_with(
                where=None,
                cohort_id=None,
                output_properties=None,
                distinct_id=None,
                distinct_ids=None,
                group_id=None,
                behaviors=None,
                as_of_timestamp=None,
                include_all_users=False,
            )
        finally:
            ws.close()

    def test_stream_profiles_with_where_filter(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T010: Test streaming profiles with WHERE filter."""
        ws = workspace_factory()
        try:
            mock_api_client.export_profiles.return_value = iter(
                [raw_profile("user_1", plan="premium")]
            )

            where_clause = 'properties["plan"]=="premium"'
            profiles = list(ws.stream_profiles(where=where_clause))

            assert len(profiles) == 1
            assert profiles[0]["properties"]["plan"] == "premium"

            mock_api_client.export_profiles.assert_called_once_with(
                where=where_clause,
                cohort_id=None,
                output_properties=None,
                distinct_id=None,
                distinct_ids=None,
                group_id=None,
                behaviors=None,
                as_of_timestamp=None,
                include_all_users=False,
            )
        finally:
            ws.close()

    def test_stream_profiles_with_cohort_id(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """stream_profiles should pass cohort_id to API client."""
        ws = workspace_factory()
        try:
            mock_api_client.export_profiles.return_value = iter(
                [raw_profile("user_1", plan="premium")]
            )

            profiles = list(ws.stream_profiles(cohort_id="cohort_12345"))

            assert len(profiles) == 1

            mock_api_client.export_profiles.assert_called_once_with(
                where=None,
                cohort_id="cohort_12345",
                output_properties=None,
                distinct_id=None,
                distinct_ids=None,
                group_id=None,
                behaviors=None,
                as_of_timestamp=None,
                include_all_users=False,
            )
        finally:
            ws.close()

    def test_stream_profiles_with_output_properties(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """stream_profiles should pass output_properties to API client."""
        ws = workspace_factory()
        try:
            mock_api_client.export_profiles.return_value = iter(
                [raw_profile("user_1", email="test@example.com")]
            )

            profiles = list(
                ws.stream_profiles(output_properties=["$email", "$name", "plan"])
            )

            assert len(profiles) == 1

            mock_api_client.export_profiles.assert_called_once_with(
                where=None,
                cohort_id=None,
                output_properties=["$email", "$name", "plan"],
                distinct_id=None,
                distinct_ids=None,
                group_id=None,
                behaviors=None,
                as_of_timestamp=None,
                include_all_users=False,
            )
        finally:
            ws.close()

    def test_stream_profiles_with_all_filters(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """stream_profiles should pass all filter params to API client."""
        ws = workspace_factory()
        try:
            mock_api_client.export_profiles.return_value = iter([raw_profile("user_1")])

            where_clause = 'properties["plan"]=="premium"'
            list(
                ws.stream_profiles(
                    where=where_clause,
                    cohort_id="cohort_abc",
                    output_properties=["$email"],
                )
            )

            mock_api_client.export_profiles.assert_called_once_with(
                where=where_clause,
                cohort_id="cohort_abc",
                output_properties=["$email"],
                distinct_id=None,
                distinct_ids=None,
                group_id=None,
                behaviors=None,
                as_of_timestamp=None,
                include_all_users=False,
            )
        finally:
            ws.close()

    def test_stream_profiles_raw_true(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T010: Test streaming profiles with raw=True returns Mixpanel API format."""
        ws = workspace_factory()
        try:
            raw_profiles = [
                raw_profile("user_1", "2024-01-15T10:00:00", name="Alice"),
                raw_profile("user_2", None, name="Bob"),
            ]
            mock_api_client.export_profiles.return_value = iter(raw_profiles)

            profiles = list(ws.stream_profiles(raw=True))

            assert len(profiles) == 2

            # Verify raw format (Mixpanel API structure with $ prefixes)
            assert profiles[0]["$distinct_id"] == "user_1"
            assert "$properties" in profiles[0]
            assert profiles[0]["$properties"]["$last_seen"] == "2024-01-15T10:00:00"
            assert profiles[0]["$properties"]["name"] == "Alice"

            # Second profile has no $last_seen
            assert "$last_seen" not in profiles[1]["$properties"]
        finally:
            ws.close()

    def test_stream_profiles_raw_false_transforms(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T010: Test streaming profiles with raw=False (default) transforms data."""
        ws = workspace_factory()
        try:
            mock_api_client.export_profiles.return_value = iter(
                [
                    raw_profile(
                        "user_abc", "2024-01-15T14:30:00", email="test@example.com"
                    )
                ]
            )

            profiles = list(ws.stream_profiles(raw=False))

            assert len(profiles) == 1
            profile = profiles[0]

            # Verify normalized format
            assert profile["distinct_id"] == "user_abc"
            assert profile["last_seen"] == "2024-01-15T14:30:00"
            assert profile["properties"]["email"] == "test@example.com"

            # Properties should NOT include $last_seen
            assert "$last_seen" not in profile["properties"]
        finally:
            ws.close()

    def test_stream_profiles_empty_result(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Test streaming profiles returns empty iterator when no profiles."""
        ws = workspace_factory()
        try:
            mock_api_client.export_profiles.return_value = iter([])

            profiles = list(ws.stream_profiles())

            assert profiles == []
        finally:
            ws.close()


# =============================================================================
# ConfigError Tests (Query-Only Mode)
# =============================================================================


class TestStreamingConfigError:
    """Tests for ConfigError when streaming without credentials."""

    def test_stream_events_raises_config_error_in_query_only_mode(
        self,
        temp_dir: Path,
    ) -> None:
        """Test stream_events raises ConfigError when opened without credentials."""
        # Create a database file
        db_path = temp_dir / "test.db"
        storage = StorageEngine(path=db_path, read_only=False)
        storage.close()

        ws = Workspace.open(db_path)
        try:
            with pytest.raises(ConfigError) as exc_info:
                list(ws.stream_events(from_date="2024-01-01", to_date="2024-01-31"))

            assert "API access requires credentials" in str(exc_info.value)
        finally:
            ws.close()

    def test_stream_profiles_raises_config_error_in_query_only_mode(
        self,
        temp_dir: Path,
    ) -> None:
        """Test stream_profiles raises ConfigError when opened without credentials."""
        # Create a database file
        db_path = temp_dir / "test.db"
        storage = StorageEngine(path=db_path, read_only=False)
        storage.close()

        ws = Workspace.open(db_path)
        try:
            with pytest.raises(ConfigError) as exc_info:
                list(ws.stream_profiles())

            assert "API access requires credentials" in str(exc_info.value)
        finally:
            ws.close()


# =============================================================================
# Phase 6: User Story 4 - Output Format Verification Tests (T019-T022)
# =============================================================================


class TestNormalizedEventFormat:
    """T019: Tests verifying normalized event format matches data-model.md."""

    def test_normalized_event_has_required_fields(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Verify normalized events have all required fields from data-model.md."""
        ws = workspace_factory()
        try:
            mock_api_client.export_events.return_value = iter(
                [raw_event("Purchase", "user_abc123", 1705328400, amount=99.99)]
            )

            events = list(
                ws.stream_events(from_date="2024-01-15", to_date="2024-01-15")
            )

            event = events[0]
            # Required fields per data-model.md
            assert "event_name" in event
            assert "event_time" in event
            assert "distinct_id" in event
            assert "insert_id" in event
            assert "properties" in event

            # Type checks
            assert isinstance(event["event_name"], str)
            assert isinstance(event["event_time"], datetime)
            assert isinstance(event["distinct_id"], str)
            assert isinstance(event["insert_id"], str)
            assert isinstance(event["properties"], dict)
        finally:
            ws.close()


class TestRawEventFormat:
    """T020: Tests verifying raw event format matches Mixpanel API structure."""

    def test_raw_event_has_api_structure(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Verify raw events have Mixpanel API structure with Unix timestamp."""
        ws = workspace_factory()
        try:
            mock_api_client.export_events.return_value = iter(
                [raw_event("Purchase", "user_abc123", 1705328400, amount=99.99)]
            )

            events = list(
                ws.stream_events(from_date="2024-01-15", to_date="2024-01-15", raw=True)
            )

            event = events[0]
            # Raw format per data-model.md
            assert "event" in event
            assert "properties" in event
            assert event["properties"]["time"] == 1705328400  # Unix timestamp
            assert event["properties"]["distinct_id"] == "user_abc123"
            assert "$insert_id" in event["properties"]
        finally:
            ws.close()


class TestNormalizedProfileFormat:
    """T021: Tests verifying normalized profile format matches data-model.md."""

    def test_normalized_profile_has_required_fields(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Verify normalized profiles have all required fields from data-model.md."""
        ws = workspace_factory()
        try:
            mock_api_client.export_profiles.return_value = iter(
                [raw_profile("user_abc123", "2024-01-15T14:30:00", name="Alice")]
            )

            profiles = list(ws.stream_profiles())

            profile = profiles[0]
            # Required fields per data-model.md
            assert "distinct_id" in profile
            assert "last_seen" in profile
            assert "properties" in profile

            # Type checks
            assert isinstance(profile["distinct_id"], str)
            assert isinstance(profile["last_seen"], str | type(None))
            assert isinstance(profile["properties"], dict)
        finally:
            ws.close()


class TestRawProfileFormat:
    """T022: Tests verifying raw profile format matches Mixpanel API structure."""

    def test_raw_profile_has_api_structure(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Verify raw profiles have Mixpanel API structure with $ prefixes."""
        ws = workspace_factory()
        try:
            mock_api_client.export_profiles.return_value = iter(
                [raw_profile("user_abc123", "2024-01-15T14:30:00", name="Alice")]
            )

            profiles = list(ws.stream_profiles(raw=True))

            profile = profiles[0]
            # Raw format per data-model.md
            assert "$distinct_id" in profile
            assert "$properties" in profile
            assert profile["$distinct_id"] == "user_abc123"
            assert profile["$properties"]["$last_seen"] == "2024-01-15T14:30:00"
        finally:
            ws.close()
