"""Integration tests for FetcherService.

These tests use real DuckDB storage with mocked API client to verify
end-to-end fetch and query workflows.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mixpanel_data._internal.services.fetcher import FetcherService
from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data.exceptions import TableExistsError

# =============================================================================
# User Story 1: Fetch Events Integration Tests
# =============================================================================


def test_fetch_events_with_real_duckdb(tmp_path: Path) -> None:
    """Integration test: fetch events and verify they are queryable via SQL.

    This is the key integration test for User Story 1:
    1. Fetch events from mocked API into real DuckDB
    2. Verify events are stored correctly
    3. Verify events are queryable via SQL
    """
    db_path = tmp_path / "events.db"

    # Setup mock API client
    mock_api_client = MagicMock()

    def mock_export_events(**_kwargs: Any) -> Iterator[dict[str, Any]]:
        events = [
            {
                "event": "Sign Up",
                "properties": {
                    "distinct_id": "user_1",
                    "time": 1704067200,  # 2024-01-01 00:00:00 UTC
                    "$insert_id": "evt-001",
                    "plan": "free",
                },
            },
            {
                "event": "Login",
                "properties": {
                    "distinct_id": "user_1",
                    "time": 1704153600,  # 2024-01-02 00:00:00 UTC
                    "$insert_id": "evt-002",
                    "device": "mobile",
                },
            },
            {
                "event": "Sign Up",
                "properties": {
                    "distinct_id": "user_2",
                    "time": 1704240000,  # 2024-01-03 00:00:00 UTC
                    "$insert_id": "evt-003",
                    "plan": "premium",
                },
            },
        ]
        yield from events

    mock_api_client.export_events.return_value = mock_export_events()

    with StorageEngine(path=db_path, read_only=False) as storage:
        fetcher = FetcherService(mock_api_client, storage)

        # Fetch events
        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        # Verify result
        assert result.table == "events"
        assert result.rows == 3
        assert result.type == "events"
        assert result.date_range == ("2024-01-01", "2024-01-31")

        # Query events via SQL
        df = storage.execute_df("SELECT * FROM events ORDER BY insert_id")
        assert len(df) == 3

        # Verify event names
        event_names = df["event_name"].tolist()
        assert event_names == ["Sign Up", "Login", "Sign Up"]

        # Verify distinct_ids
        distinct_ids = df["distinct_id"].tolist()
        assert distinct_ids == ["user_1", "user_1", "user_2"]

        # Query with aggregation
        counts = storage.execute_df("""
            SELECT event_name, COUNT(*) as count
            FROM events
            GROUP BY event_name
            ORDER BY event_name
        """)
        assert counts["event_name"].tolist() == ["Login", "Sign Up"]
        assert counts["count"].tolist() == [1, 2]


def test_fetch_events_json_properties_queryable(tmp_path: Path) -> None:
    """Test that JSON properties can be queried with DuckDB JSON extraction."""
    db_path = tmp_path / "json_test.db"

    mock_api_client = MagicMock()

    def mock_export_events(**_kwargs: Any) -> Iterator[dict[str, Any]]:
        yield {
            "event": "Purchase",
            "properties": {
                "distinct_id": "user_1",
                "time": 1704067200,
                "$insert_id": "evt-001",
                "amount": 99.99,
                "currency": "USD",
                "country": "US",
            },
        }
        yield {
            "event": "Purchase",
            "properties": {
                "distinct_id": "user_2",
                "time": 1704153600,
                "$insert_id": "evt-002",
                "amount": 149.50,
                "currency": "EUR",
                "country": "DE",
            },
        }

    mock_api_client.export_events.return_value = mock_export_events()

    with StorageEngine(path=db_path, read_only=False) as storage:
        fetcher = FetcherService(mock_api_client, storage)
        fetcher.fetch_events(
            name="purchases",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        # Query JSON properties using DuckDB JSON extraction
        df = storage.execute_df("""
            SELECT
                distinct_id,
                properties->>'$.amount' as amount,
                properties->>'$.currency' as currency
            FROM purchases
            ORDER BY distinct_id
        """)

        assert df["distinct_id"].tolist() == ["user_1", "user_2"]
        # JSON extraction returns strings (float formatting may vary)
        assert df["amount"].tolist() == ["99.99", "149.5"]
        assert df["currency"].tolist() == ["USD", "EUR"]


def test_fetch_events_table_exists_error_with_real_storage(tmp_path: Path) -> None:
    """Test that TableExistsError is raised when table already exists."""
    db_path = tmp_path / "exists_test.db"

    mock_api_client = MagicMock()
    mock_api_client.export_events.return_value = iter(
        [
            {
                "event": "Test",
                "properties": {
                    "distinct_id": "user_1",
                    "time": 1704067200,
                    "$insert_id": "evt-001",
                },
            }
        ]
    )

    with StorageEngine(path=db_path, read_only=False) as storage:
        fetcher = FetcherService(mock_api_client, storage)

        # First fetch should succeed
        fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        # Reset mock for second call
        mock_api_client.export_events.return_value = iter([])

        # Second fetch to same table should fail
        with pytest.raises(TableExistsError) as exc_info:
            fetcher.fetch_events(
                name="events",
                from_date="2024-01-01",
                to_date="2024-01-31",
            )

        assert "events" in str(exc_info.value)


def test_fetch_events_progress_callback_integration(tmp_path: Path) -> None:
    """Test that progress callback is invoked during event fetch."""
    db_path = tmp_path / "progress_test.db"

    mock_api_client = MagicMock()

    # Capture the on_batch callback and invoke it
    def mock_export_events(**kwargs: Any) -> Iterator[dict[str, Any]]:
        on_batch = kwargs.get("on_batch")
        events = []
        for i in range(5):
            events.append(
                {
                    "event": f"Event_{i}",
                    "properties": {
                        "distinct_id": f"user_{i}",
                        "time": 1704067200 + i,
                        "$insert_id": f"evt-{i:03d}",
                    },
                }
            )
        # Invoke callback during iteration
        for i, event in enumerate(events):
            yield event
            if on_batch:
                on_batch(i + 1)

    mock_api_client.export_events.side_effect = mock_export_events

    with StorageEngine(path=db_path, read_only=False) as storage:
        fetcher = FetcherService(mock_api_client, storage)

        progress_values: list[int] = []

        def on_progress(count: int) -> None:
            progress_values.append(count)

        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
            progress_callback=on_progress,
        )

        # Should have received progress updates
        assert len(progress_values) == 5
        assert progress_values == [1, 2, 3, 4, 5]
        assert result.rows == 5


# =============================================================================
# User Story 2: Fetch Profiles Integration Tests
# =============================================================================


def test_fetch_profiles_with_real_duckdb(tmp_path: Path) -> None:
    """Integration test: fetch profiles and verify they are queryable via SQL.

    This is the key integration test for User Story 2:
    1. Fetch profiles from mocked API into real DuckDB
    2. Verify profiles are stored correctly
    3. Verify profiles are queryable via SQL
    """
    db_path = tmp_path / "profiles.db"

    mock_api_client = MagicMock()

    def mock_export_profiles(**_kwargs: Any) -> Iterator[dict[str, Any]]:
        profiles = [
            {
                "$distinct_id": "user_1",
                "$properties": {
                    "$last_seen": "2024-01-15T10:30:00",
                    "$email": "alice@example.com",
                    "plan": "premium",
                },
            },
            {
                "$distinct_id": "user_2",
                "$properties": {
                    "$last_seen": "2024-01-16T14:00:00",
                    "$email": "bob@example.com",
                    "plan": "free",
                },
            },
            {
                "$distinct_id": "user_3",
                "$properties": {
                    "$email": "charlie@example.com",
                    "plan": "enterprise",
                },  # Missing $last_seen
            },
        ]
        yield from profiles

    mock_api_client.export_profiles.return_value = mock_export_profiles()

    with StorageEngine(path=db_path, read_only=False) as storage:
        fetcher = FetcherService(mock_api_client, storage)

        # Fetch profiles
        result = fetcher.fetch_profiles(name="profiles")

        # Verify result
        assert result.table == "profiles"
        assert result.rows == 3
        assert result.type == "profiles"
        assert result.date_range is None

        # Query profiles via SQL
        df = storage.execute_df("SELECT * FROM profiles ORDER BY distinct_id")
        assert len(df) == 3

        # Verify distinct_ids
        distinct_ids = df["distinct_id"].tolist()
        assert distinct_ids == ["user_1", "user_2", "user_3"]

        # Verify last_seen (user_3 should have NULL)
        import pandas as pd

        last_seen = df["last_seen"]
        assert pd.notna(last_seen.iloc[0])  # user_1
        assert pd.notna(last_seen.iloc[1])  # user_2
        assert pd.isna(last_seen.iloc[2])  # user_3 has no $last_seen


def test_fetch_profiles_json_properties_queryable(tmp_path: Path) -> None:
    """Test that profile JSON properties can be queried with DuckDB."""
    db_path = tmp_path / "profile_json_test.db"

    mock_api_client = MagicMock()

    def mock_export_profiles(**_kwargs: Any) -> Iterator[dict[str, Any]]:
        yield {
            "$distinct_id": "user_1",
            "$properties": {
                "$last_seen": "2024-01-15T10:30:00",
                "$email": "user1@example.com",
                "subscription": "annual",
                "credits": 100,
            },
        }
        yield {
            "$distinct_id": "user_2",
            "$properties": {
                "$last_seen": "2024-01-16T11:00:00",
                "$email": "user2@example.com",
                "subscription": "monthly",
                "credits": 50,
            },
        }

    mock_api_client.export_profiles.return_value = mock_export_profiles()

    with StorageEngine(path=db_path, read_only=False) as storage:
        fetcher = FetcherService(mock_api_client, storage)
        fetcher.fetch_profiles(name="users")

        # Query JSON properties
        df = storage.execute_df("""
            SELECT
                distinct_id,
                properties->>'$.$email' as email,
                properties->>'$.subscription' as subscription
            FROM users
            ORDER BY distinct_id
        """)

        assert df["distinct_id"].tolist() == ["user_1", "user_2"]
        assert df["email"].tolist() == ["user1@example.com", "user2@example.com"]
        assert df["subscription"].tolist() == ["annual", "monthly"]


def test_fetch_profiles_table_exists_error_with_real_storage(tmp_path: Path) -> None:
    """Test that TableExistsError is raised when profile table already exists."""
    db_path = tmp_path / "profile_exists_test.db"

    mock_api_client = MagicMock()
    mock_api_client.export_profiles.return_value = iter(
        [
            {
                "$distinct_id": "user_1",
                "$properties": {
                    "$last_seen": "2024-01-15T10:30:00",
                },
            }
        ]
    )

    with StorageEngine(path=db_path, read_only=False) as storage:
        fetcher = FetcherService(mock_api_client, storage)

        # First fetch should succeed
        fetcher.fetch_profiles(name="profiles")

        # Reset mock for second call
        mock_api_client.export_profiles.return_value = iter([])

        # Second fetch to same table should fail
        with pytest.raises(TableExistsError) as exc_info:
            fetcher.fetch_profiles(name="profiles")

        assert "profiles" in str(exc_info.value)


def test_events_and_profiles_can_be_joined(tmp_path: Path) -> None:
    """Test that events and profiles tables can be joined via SQL."""
    db_path = tmp_path / "join_test.db"

    mock_api_client = MagicMock()

    # Events data
    def mock_export_events(**_kwargs: Any) -> Iterator[dict[str, Any]]:
        yield {
            "event": "Purchase",
            "properties": {
                "distinct_id": "user_1",
                "time": 1704067200,
                "$insert_id": "evt-001",
                "amount": 100,
            },
        }
        yield {
            "event": "Purchase",
            "properties": {
                "distinct_id": "user_2",
                "time": 1704153600,
                "$insert_id": "evt-002",
                "amount": 200,
            },
        }

    # Profile data
    def mock_export_profiles(**_kwargs: Any) -> Iterator[dict[str, Any]]:
        yield {
            "$distinct_id": "user_1",
            "$properties": {
                "$last_seen": "2024-01-15T10:30:00",
                "name": "Alice",
            },
        }
        yield {
            "$distinct_id": "user_2",
            "$properties": {
                "$last_seen": "2024-01-16T11:00:00",
                "name": "Bob",
            },
        }

    with StorageEngine(path=db_path, read_only=False) as storage:
        fetcher = FetcherService(mock_api_client, storage)

        # Fetch events
        mock_api_client.export_events.return_value = mock_export_events()
        fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        # Fetch profiles
        mock_api_client.export_profiles.return_value = mock_export_profiles()
        fetcher.fetch_profiles(name="profiles")

        # Join events with profiles
        df = storage.execute_df("""
            SELECT
                e.event_name,
                e.distinct_id,
                e.properties->>'$.amount' as amount,
                p.properties->>'$.name' as user_name
            FROM events e
            JOIN profiles p ON e.distinct_id = p.distinct_id
            ORDER BY e.insert_id
        """)

        assert len(df) == 2
        assert df["event_name"].tolist() == ["Purchase", "Purchase"]
        assert df["user_name"].tolist() == ["Alice", "Bob"]
        assert df["amount"].tolist() == ["100", "200"]
