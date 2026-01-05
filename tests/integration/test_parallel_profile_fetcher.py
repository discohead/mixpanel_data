"""Integration tests for ParallelProfileFetcherService.

These tests use real DuckDB storage with mocked API client to verify
end-to-end parallel profile fetch workflows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from mixpanel_data._internal.services.parallel_profile_fetcher import (
    ParallelProfileFetcherService,
)
from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data.types import ProfilePageResult, ProfileProgress

# =============================================================================
# User Story 1: Single Page Fetch Integration Tests
# =============================================================================


def test_single_page_fetch_with_real_duckdb(tmp_path: Path) -> None:
    """Integration test: single page parallel fetch stores profiles correctly.

    This verifies:
    1. Single page fetch works with real DuckDB
    2. Profiles are stored and queryable
    3. Result metadata is correct
    """
    db_path = tmp_path / "profiles.db"

    # Setup mock API client
    mock_api_client = MagicMock()

    # Mock export_profiles_page to return a single page with no more pages
    def mock_export_profiles_page(
        page: int = 0,
        session_id: str | None = None,
        **_kwargs: Any,
    ) -> ProfilePageResult:
        if page == 0:
            return ProfilePageResult(
                profiles=[
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
                ],
                page=0,
                session_id="test-session-123",
                has_more=False,
            )
        # No more pages
        return ProfilePageResult(
            profiles=[],
            page=page,
            session_id=session_id or "test-session-123",
            has_more=False,
        )

    mock_api_client.export_profiles_page.side_effect = mock_export_profiles_page

    with StorageEngine(path=db_path, read_only=False) as storage:
        fetcher = ParallelProfileFetcherService(mock_api_client, storage)

        # Fetch profiles
        result = fetcher.fetch_profiles(name="profiles")

        # Verify result
        assert result.table == "profiles"
        assert result.total_rows == 2
        assert result.successful_pages == 1
        assert result.failed_pages == 0

        # Query profiles via SQL
        df = storage.execute_df("SELECT * FROM profiles ORDER BY distinct_id")
        assert len(df) == 2

        # Verify distinct_ids
        distinct_ids = df["distinct_id"].tolist()
        assert distinct_ids == ["user_1", "user_2"]


# =============================================================================
# User Story 2: Multi-Page Parallel Fetch Integration Tests
# =============================================================================


def test_multi_page_parallel_fetch_with_real_duckdb(tmp_path: Path) -> None:
    """Integration test: multi-page parallel fetch with real DuckDB.

    This verifies:
    1. Multiple pages are fetched correctly
    2. All profiles are stored and queryable
    3. Order is preserved
    """
    db_path = tmp_path / "profiles.db"

    mock_api_client = MagicMock()

    # Mock export_profiles_page to return 3 pages
    def mock_export_profiles_page(
        page: int = 0,
        session_id: str | None = None,
        **_kwargs: Any,
    ) -> ProfilePageResult:
        pages_data = {
            0: [
                {"$distinct_id": "user_1", "$properties": {"name": "Alice"}},
                {"$distinct_id": "user_2", "$properties": {"name": "Bob"}},
            ],
            1: [
                {"$distinct_id": "user_3", "$properties": {"name": "Charlie"}},
                {"$distinct_id": "user_4", "$properties": {"name": "Diana"}},
            ],
            2: [
                {"$distinct_id": "user_5", "$properties": {"name": "Eve"}},
            ],
        }

        profiles = pages_data.get(page, [])
        has_more = page < 2

        return ProfilePageResult(
            profiles=profiles,
            page=page,
            session_id=session_id or "test-session-456",
            has_more=has_more,
        )

    mock_api_client.export_profiles_page.side_effect = mock_export_profiles_page

    with StorageEngine(path=db_path, read_only=False) as storage:
        fetcher = ParallelProfileFetcherService(mock_api_client, storage)

        result = fetcher.fetch_profiles(name="profiles", max_workers=2)

        # Verify result
        assert result.table == "profiles"
        assert result.total_rows == 5
        assert result.successful_pages == 3
        assert result.failed_pages == 0

        # Query all profiles
        df = storage.execute_df("SELECT * FROM profiles ORDER BY distinct_id")
        assert len(df) == 5

        # Verify all users are present
        distinct_ids = df["distinct_id"].tolist()
        assert distinct_ids == ["user_1", "user_2", "user_3", "user_4", "user_5"]


# =============================================================================
# User Story 3: Progress Callback Integration Tests
# =============================================================================


def test_progress_callback_with_real_duckdb(tmp_path: Path) -> None:
    """Integration test: progress callback is invoked with real DuckDB.

    This verifies:
    1. Callback is invoked for each page
    2. Progress tracking works correctly
    3. Cumulative row counts are accurate
    """
    db_path = tmp_path / "profiles.db"

    mock_api_client = MagicMock()

    def mock_export_profiles_page(
        page: int = 0,
        session_id: str | None = None,
        **_kwargs: Any,
    ) -> ProfilePageResult:
        pages_data = {
            0: [{"$distinct_id": "user_1", "$properties": {}}],
            1: [
                {"$distinct_id": "user_2", "$properties": {}},
                {"$distinct_id": "user_3", "$properties": {}},
            ],
        }

        profiles = pages_data.get(page, [])
        has_more = page < 1

        return ProfilePageResult(
            profiles=profiles,
            page=page,
            session_id=session_id or "test-session-789",
            has_more=has_more,
        )

    mock_api_client.export_profiles_page.side_effect = mock_export_profiles_page

    with StorageEngine(path=db_path, read_only=False) as storage:
        fetcher = ParallelProfileFetcherService(mock_api_client, storage)

        progress_updates: list[ProfileProgress] = []

        def on_page_complete(progress: ProfileProgress) -> None:
            progress_updates.append(progress)

        result = fetcher.fetch_profiles(
            name="profiles",
            on_page_complete=on_page_complete,
        )

        # Verify result
        assert result.total_rows == 3
        assert result.successful_pages == 2

        # Verify progress updates
        assert len(progress_updates) == 2

        # All pages should be successful
        for update in progress_updates:
            assert update.success is True
            assert update.error is None

        # Verify cumulative rows were tracked (order may vary due to parallelism)
        total_from_progress = sum(p.rows for p in progress_updates)
        assert total_from_progress == 3


# =============================================================================
# User Story 4: Partial Failure Integration Tests
# =============================================================================


def test_partial_failure_preserves_successful_data(tmp_path: Path) -> None:
    """Integration test: partial failures preserve successful data.

    This verifies:
    1. Successful pages are stored
    2. Failed pages are tracked
    3. Result indicates failure
    """
    db_path = tmp_path / "profiles.db"

    mock_api_client = MagicMock()

    call_count = 0

    def mock_export_profiles_page(
        page: int = 0,
        session_id: str | None = None,
        **_kwargs: Any,
    ) -> ProfilePageResult:
        nonlocal call_count
        call_count += 1

        if page == 0:
            # First page succeeds and indicates more pages
            return ProfilePageResult(
                profiles=[{"$distinct_id": "user_1", "$properties": {}}],
                page=0,
                session_id=session_id or "test-session-fail",
                has_more=True,
            )
        elif page == 1:
            # Second page fails
            raise Exception("API error on page 1")
        else:
            # No more pages
            return ProfilePageResult(
                profiles=[],
                page=page,
                session_id=session_id or "test-session-fail",
                has_more=False,
            )

    mock_api_client.export_profiles_page.side_effect = mock_export_profiles_page

    with StorageEngine(path=db_path, read_only=False) as storage:
        fetcher = ParallelProfileFetcherService(mock_api_client, storage)

        result = fetcher.fetch_profiles(name="profiles")

        # Verify result indicates failure
        assert result.has_failures is True
        assert result.failed_pages >= 1
        assert len(result.failed_page_indices) >= 1

        # Verify successful page data was preserved
        df = storage.execute_df("SELECT * FROM profiles")
        assert len(df) >= 1  # At least page 0 should be saved


# =============================================================================
# JSON Properties Queryable Tests
# =============================================================================


def test_json_properties_queryable_with_real_duckdb(tmp_path: Path) -> None:
    """Integration test: JSON properties are queryable with DuckDB."""
    db_path = tmp_path / "profiles.db"

    mock_api_client = MagicMock()

    def mock_export_profiles_page(
        page: int = 0,
        **_kwargs: Any,
    ) -> ProfilePageResult:
        if page == 0:
            return ProfilePageResult(
                profiles=[
                    {
                        "$distinct_id": "user_1",
                        "$properties": {
                            "$email": "alice@example.com",
                            "subscription": "annual",
                            "credits": 100,
                        },
                    },
                    {
                        "$distinct_id": "user_2",
                        "$properties": {
                            "$email": "bob@example.com",
                            "subscription": "monthly",
                            "credits": 50,
                        },
                    },
                ],
                page=0,
                session_id="test-session-json",
                has_more=False,
            )
        return ProfilePageResult(
            profiles=[],
            page=page,
            session_id="test-session-json",
            has_more=False,
        )

    mock_api_client.export_profiles_page.side_effect = mock_export_profiles_page

    with StorageEngine(path=db_path, read_only=False) as storage:
        fetcher = ParallelProfileFetcherService(mock_api_client, storage)
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
        assert df["email"].tolist() == ["alice@example.com", "bob@example.com"]
        assert df["subscription"].tolist() == ["annual", "monthly"]
