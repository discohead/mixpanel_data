"""Unit tests for ParallelProfileFetcherService.

Tests for the parallel profile fetch implementation with ThreadPoolExecutor
and producer-consumer queue pattern (feature 019-parallel-profile-fetch).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any
from unittest.mock import MagicMock, call

import pytest

from mixpanel_data.types import (
    ParallelProfileResult,
    ProfilePageResult,
    ProfileProgress,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create a mock API client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_storage() -> MagicMock:
    """Create a mock storage engine."""
    storage = MagicMock()
    storage.append_profiles_table.return_value = 0
    storage.create_profiles_table.return_value = 0
    return storage


@pytest.fixture
def parallel_profile_fetcher(
    mock_api_client: MagicMock, mock_storage: MagicMock
) -> Any:
    """Create a ParallelProfileFetcherService with mocked dependencies."""
    from mixpanel_data._internal.services.parallel_profile_fetcher import (
        ParallelProfileFetcherService,
    )

    return ParallelProfileFetcherService(
        api_client=mock_api_client,
        storage=mock_storage,
    )


# =============================================================================
# ParallelProfileFetcherService Construction Tests (T009)
# =============================================================================


class TestParallelProfileFetcherServiceConstruction:
    """Tests for ParallelProfileFetcherService initialization."""

    def test_create_with_api_client_and_storage(
        self, mock_api_client: MagicMock, mock_storage: MagicMock
    ) -> None:
        """ParallelProfileFetcherService can be created with api_client and storage."""
        from mixpanel_data._internal.services.parallel_profile_fetcher import (
            ParallelProfileFetcherService,
        )

        fetcher = ParallelProfileFetcherService(
            api_client=mock_api_client,
            storage=mock_storage,
        )

        assert fetcher._api_client is mock_api_client
        assert fetcher._storage is mock_storage

    def test_default_max_workers_is_5(
        self, mock_api_client: MagicMock, mock_storage: MagicMock
    ) -> None:
        """Default max_workers is 5 for profiles (lower than events)."""
        from mixpanel_data._internal.services.parallel_profile_fetcher import (
            ParallelProfileFetcherService,
        )

        fetcher = ParallelProfileFetcherService(
            api_client=mock_api_client,
            storage=mock_storage,
        )

        assert fetcher._default_max_workers == 5


# =============================================================================
# Parallel Fetch Profiles Tests (T010)
# =============================================================================


class TestParallelFetchProfiles:
    """Tests for parallel fetch_profiles method."""

    def test_fetch_profiles_returns_parallel_profile_result(
        self, parallel_profile_fetcher: Any, mock_api_client: MagicMock
    ) -> None:
        """fetch_profiles returns ParallelProfileResult."""
        # Setup mock to return empty result on page 0
        mock_api_client.export_profiles_page.return_value = ProfilePageResult(
            profiles=[],
            session_id=None,
            page=0,
            has_more=False,
        )

        result = parallel_profile_fetcher.fetch_profiles(name="test_profiles")

        assert isinstance(result, ParallelProfileResult)

    def test_fetch_profiles_fetches_page_0_for_metadata(
        self, parallel_profile_fetcher: Any, mock_api_client: MagicMock
    ) -> None:
        """First page is fetched to get session_id for subsequent pages."""
        mock_api_client.export_profiles_page.return_value = ProfilePageResult(
            profiles=[{"$distinct_id": "user1"}],
            session_id=None,
            page=0,
            has_more=False,
        )

        parallel_profile_fetcher.fetch_profiles(name="test_profiles")

        # Verify page 0 was called first
        calls = mock_api_client.export_profiles_page.call_args_list
        assert len(calls) >= 1
        assert calls[0] == call(
            page=0, session_id=None, where=None, cohort_id=None, output_properties=None
        )

    def test_fetch_profiles_single_page_result(
        self,
        parallel_profile_fetcher: Any,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Single page fetch stores profiles correctly."""
        profiles = [
            {"$distinct_id": "user1", "$properties": {"name": "Alice"}},
            {"$distinct_id": "user2", "$properties": {"name": "Bob"}},
        ]
        mock_api_client.export_profiles_page.return_value = ProfilePageResult(
            profiles=profiles,
            session_id=None,
            page=0,
            has_more=False,
        )
        mock_storage.create_profiles_table.return_value = 2

        result = parallel_profile_fetcher.fetch_profiles(name="test_profiles")

        assert result.successful_pages == 1
        assert result.failed_pages == 0
        assert result.total_rows == 2

    def test_fetch_profiles_multiple_pages(
        self,
        parallel_profile_fetcher: Any,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Multiple page fetch retrieves all pages."""
        # Page 0 returns profiles and session_id
        page_0_result = ProfilePageResult(
            profiles=[{"$distinct_id": f"user{i}"} for i in range(1000)],
            session_id="session_abc",
            page=0,
            has_more=True,
        )
        # Page 1 returns more profiles
        page_1_result = ProfilePageResult(
            profiles=[{"$distinct_id": f"user{i}"} for i in range(1000, 2000)],
            session_id="session_abc",
            page=1,
            has_more=True,
        )
        # Page 2 is last page
        page_2_result = ProfilePageResult(
            profiles=[{"$distinct_id": f"user{i}"} for i in range(2000, 2500)],
            session_id=None,
            page=2,
            has_more=False,
        )

        mock_api_client.export_profiles_page.side_effect = [
            page_0_result,
            page_1_result,
            page_2_result,
        ]
        mock_storage.create_profiles_table.return_value = 1000
        mock_storage.append_profiles_table.return_value = 1000

        result = parallel_profile_fetcher.fetch_profiles(name="test_profiles")

        # All 3 pages should be fetched
        assert mock_api_client.export_profiles_page.call_count >= 3
        assert result.successful_pages >= 1

    def test_fetch_profiles_passes_where_filter(
        self, parallel_profile_fetcher: Any, mock_api_client: MagicMock
    ) -> None:
        """where filter is passed to API calls."""
        mock_api_client.export_profiles_page.return_value = ProfilePageResult(
            profiles=[],
            session_id=None,
            page=0,
            has_more=False,
        )

        parallel_profile_fetcher.fetch_profiles(
            name="test_profiles",
            where='properties["plan"] == "premium"',
        )

        call_args = mock_api_client.export_profiles_page.call_args
        assert call_args.kwargs["where"] == 'properties["plan"] == "premium"'

    def test_fetch_profiles_passes_cohort_id_filter(
        self, parallel_profile_fetcher: Any, mock_api_client: MagicMock
    ) -> None:
        """cohort_id filter is passed to API calls."""
        mock_api_client.export_profiles_page.return_value = ProfilePageResult(
            profiles=[],
            session_id=None,
            page=0,
            has_more=False,
        )

        parallel_profile_fetcher.fetch_profiles(
            name="test_profiles",
            cohort_id="cohort_123",
        )

        call_args = mock_api_client.export_profiles_page.call_args
        assert call_args.kwargs["cohort_id"] == "cohort_123"

    def test_fetch_profiles_passes_output_properties_filter(
        self, parallel_profile_fetcher: Any, mock_api_client: MagicMock
    ) -> None:
        """output_properties filter is passed to API calls."""
        mock_api_client.export_profiles_page.return_value = ProfilePageResult(
            profiles=[],
            session_id=None,
            page=0,
            has_more=False,
        )

        parallel_profile_fetcher.fetch_profiles(
            name="test_profiles",
            output_properties=["$name", "$email"],
        )

        call_args = mock_api_client.export_profiles_page.call_args
        assert call_args.kwargs["output_properties"] == ["$name", "$email"]


# =============================================================================
# Parallel Output Matches Sequential Output (T010b)
# =============================================================================


class TestParallelSequentialEquivalence:
    """Tests verifying parallel output matches sequential output."""

    def test_parallel_and_sequential_same_profiles(
        self,
        parallel_profile_fetcher: Any,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Parallel fetch stores same profiles as sequential would."""
        # Create consistent page responses
        profiles_page_0 = [{"$distinct_id": "user1"}, {"$distinct_id": "user2"}]
        profiles_page_1 = [{"$distinct_id": "user3"}]

        def mock_page_fetch(page: int, **kwargs: Any) -> ProfilePageResult:  # noqa: ARG001
            if page == 0:
                return ProfilePageResult(
                    profiles=profiles_page_0,
                    session_id="session_abc",
                    page=0,
                    has_more=True,
                )
            return ProfilePageResult(
                profiles=profiles_page_1 if page == 1 else [],
                session_id=None,
                page=page,
                has_more=False,
            )

        mock_api_client.export_profiles_page.side_effect = mock_page_fetch

        # Track all data written to storage
        all_written_data: list[dict[str, Any]] = []

        def capture_create(
            name: str,  # noqa: ARG001
            data: Any,
            metadata: Any,  # noqa: ARG001
            batch_size: int = 1000,  # noqa: ARG001
        ) -> int:
            profiles = list(data)
            all_written_data.extend(profiles)
            return len(profiles)

        def capture_append(
            name: str,  # noqa: ARG001
            data: Any,
            metadata: Any,  # noqa: ARG001
            batch_size: int = 1000,  # noqa: ARG001
        ) -> int:
            profiles = list(data)
            all_written_data.extend(profiles)
            return len(profiles)

        mock_storage.create_profiles_table.side_effect = capture_create
        mock_storage.append_profiles_table.side_effect = capture_append

        result = parallel_profile_fetcher.fetch_profiles(name="test_profiles")

        # Verify total rows
        assert result.total_rows == 3

        # Verify all expected distinct_ids were written
        written_ids = {p["distinct_id"] for p in all_written_data}
        assert written_ids == {"user1", "user2", "user3"}


# =============================================================================
# Worker Capping Tests (T011)
# =============================================================================


class TestWorkerCapping:
    """Tests for worker count capping at max 5."""

    def test_max_workers_capped_at_5(
        self,
        parallel_profile_fetcher: Any,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """max_workers cannot exceed 5 for profile fetching."""
        concurrent_count = 0
        max_observed = 0
        lock = threading.Lock()

        # Create many pages to test concurrency
        def create_page_result(page: int) -> ProfilePageResult:
            nonlocal concurrent_count, max_observed
            with lock:
                concurrent_count += 1
                max_observed = max(max_observed, concurrent_count)
            time.sleep(0.02)  # Simulate network delay
            with lock:
                concurrent_count -= 1

            if page < 10:
                return ProfilePageResult(
                    profiles=[{"$distinct_id": f"user{page}"}],
                    session_id="session_abc",
                    page=page,
                    has_more=True,
                )
            return ProfilePageResult(
                profiles=[],
                session_id=None,
                page=page,
                has_more=False,
            )

        mock_api_client.export_profiles_page.side_effect = (
            lambda page, **_kwargs: create_page_result(page)
        )
        mock_storage.create_profiles_table.return_value = 1
        mock_storage.append_profiles_table.return_value = 1

        # Request more workers than allowed
        _ = parallel_profile_fetcher.fetch_profiles(
            name="test_profiles",
            max_workers=20,  # Request 20, should be capped at 5
        )

        # max_observed should be <= 5
        assert max_observed <= 5

    def test_max_workers_default_is_5(
        self, mock_api_client: MagicMock, mock_storage: MagicMock
    ) -> None:
        """Default max_workers is 5."""
        from mixpanel_data._internal.services.parallel_profile_fetcher import (
            ParallelProfileFetcherService,
        )

        fetcher = ParallelProfileFetcherService(
            api_client=mock_api_client,
            storage=mock_storage,
        )

        assert fetcher._default_max_workers == 5

    def test_explicit_max_workers_respected_when_under_cap(
        self,
        parallel_profile_fetcher: Any,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Explicit max_workers < 5 is respected."""
        concurrent_count = 0
        max_observed = 0
        lock = threading.Lock()

        def create_page_result(page: int) -> ProfilePageResult:
            nonlocal concurrent_count, max_observed
            with lock:
                concurrent_count += 1
                max_observed = max(max_observed, concurrent_count)
            time.sleep(0.02)
            with lock:
                concurrent_count -= 1

            if page < 5:
                return ProfilePageResult(
                    profiles=[{"$distinct_id": f"user{page}"}],
                    session_id="session_abc",
                    page=page,
                    has_more=True,
                )
            return ProfilePageResult(
                profiles=[],
                session_id=None,
                page=page,
                has_more=False,
            )

        mock_api_client.export_profiles_page.side_effect = (
            lambda page, **_kwargs: create_page_result(page)
        )
        mock_storage.create_profiles_table.return_value = 1
        mock_storage.append_profiles_table.return_value = 1

        _ = parallel_profile_fetcher.fetch_profiles(
            name="test_profiles",
            max_workers=2,
        )

        # max_observed should be <= 2
        assert max_observed <= 2


# =============================================================================
# Rate Limit Warning Tests (T012)
# =============================================================================


class TestRateLimitWarnings:
    """Tests for rate limit warnings when pages > 48."""

    def test_warns_when_pages_exceed_48(
        self,
        parallel_profile_fetcher: Any,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Warning is logged when estimated pages > 48."""
        # Create a response indicating many pages (simulated via repeated has_more)
        # We'll simulate page 0 returning metadata that suggests 50+ pages
        page_0_profiles = [{"$distinct_id": f"user{i}"} for i in range(1000)]

        def create_page_result(page: int, **kwargs: Any) -> ProfilePageResult:  # noqa: ARG001
            if page < 50:
                return ProfilePageResult(
                    profiles=page_0_profiles
                    if page == 0
                    else [{"$distinct_id": f"p{page}"}],
                    session_id="session_abc",
                    page=page,
                    has_more=True,
                )
            return ProfilePageResult(
                profiles=[],
                session_id=None,
                page=page,
                has_more=False,
            )

        mock_api_client.export_profiles_page.side_effect = create_page_result
        mock_storage.create_profiles_table.return_value = 1000
        mock_storage.append_profiles_table.return_value = 1

        with caplog.at_level(logging.WARNING):
            _ = parallel_profile_fetcher.fetch_profiles(name="test_profiles")

        # Should have logged a warning about rate limits
        warning_messages = [
            r.message for r in caplog.records if r.levelno >= logging.WARNING
        ]
        # The warning should mention rate limit or pages
        assert any(
            "rate" in msg.lower() or "pages" in msg.lower() for msg in warning_messages
        )

    def test_no_warning_when_pages_under_48(
        self,
        parallel_profile_fetcher: Any,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """No warning when pages <= 48."""
        # Create a small response
        mock_api_client.export_profiles_page.return_value = ProfilePageResult(
            profiles=[{"$distinct_id": "user1"}],
            session_id=None,
            page=0,
            has_more=False,
        )
        mock_storage.create_profiles_table.return_value = 1

        with caplog.at_level(logging.WARNING):
            _ = parallel_profile_fetcher.fetch_profiles(name="test_profiles")

        # Should not have rate limit warnings
        warning_messages = [
            r.message for r in caplog.records if r.levelno >= logging.WARNING
        ]
        rate_limit_warnings = [
            msg
            for msg in warning_messages
            if "rate" in msg.lower() and "limit" in msg.lower()
        ]
        assert len(rate_limit_warnings) == 0


# =============================================================================
# Progress Callback Tests
# =============================================================================


class TestProgressCallback:
    """Tests for on_page_complete callback."""

    def test_callback_invoked_for_each_page(
        self,
        parallel_profile_fetcher: Any,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """on_page_complete callback is invoked for each page."""

        def mock_page_fetch(page: int, **kwargs: Any) -> ProfilePageResult:  # noqa: ARG001
            if page == 0:
                return ProfilePageResult(
                    profiles=[{"$distinct_id": "user1"}],
                    session_id="session_abc",
                    page=0,
                    has_more=True,
                )
            return ProfilePageResult(
                profiles=[{"$distinct_id": "user2"}] if page == 1 else [],
                session_id=None,
                page=page,
                has_more=False,
            )

        mock_api_client.export_profiles_page.side_effect = mock_page_fetch
        mock_storage.create_profiles_table.return_value = 1
        mock_storage.append_profiles_table.return_value = 1

        progress_updates: list[ProfileProgress] = []

        def on_page_complete(progress: ProfileProgress) -> None:
            progress_updates.append(progress)

        parallel_profile_fetcher.fetch_profiles(
            name="test_profiles",
            on_page_complete=on_page_complete,
        )

        # Should have 2 progress updates (page 0 and page 1)
        assert len(progress_updates) == 2
        # Both should be successful
        assert all(p.success for p in progress_updates)

    def test_callback_includes_cumulative_rows(
        self,
        parallel_profile_fetcher: Any,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Progress callback includes cumulative_rows field."""

        def mock_page_fetch(page: int, **kwargs: Any) -> ProfilePageResult:  # noqa: ARG001
            if page == 0:
                return ProfilePageResult(
                    profiles=[{"$distinct_id": f"user{i}"} for i in range(100)],
                    session_id="session_abc",
                    page=0,
                    has_more=True,
                )
            return ProfilePageResult(
                profiles=[{"$distinct_id": f"user{i}"} for i in range(100, 150)]
                if page == 1
                else [],
                session_id=None,
                page=page,
                has_more=False,
            )

        mock_api_client.export_profiles_page.side_effect = mock_page_fetch
        mock_storage.create_profiles_table.return_value = 100
        mock_storage.append_profiles_table.return_value = 50

        progress_updates: list[ProfileProgress] = []

        parallel_profile_fetcher.fetch_profiles(
            name="test_profiles",
            on_page_complete=lambda p: progress_updates.append(p),
        )

        # Should have 2 progress updates
        assert len(progress_updates) == 2
        # Cumulative rows should increase or stay same across pages
        cumulative_values = [p.cumulative_rows for p in progress_updates]
        for i in range(1, len(cumulative_values)):
            assert cumulative_values[i] >= cumulative_values[i - 1]


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in parallel profile fetcher."""

    def test_partial_failure_tracked(
        self,
        parallel_profile_fetcher: Any,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Partial failures are tracked in result."""
        # Page 0 succeeds, page 1 fails, page 2 succeeds
        page_0_result = ProfilePageResult(
            profiles=[{"$distinct_id": "user1"}],
            session_id="session_abc",
            page=0,
            has_more=True,
        )
        page_2_result = ProfilePageResult(
            profiles=[{"$distinct_id": "user3"}],
            session_id=None,
            page=2,
            has_more=False,
        )

        call_count = [0]

        def mock_page_fetch(page: int, **kwargs: Any) -> ProfilePageResult:  # noqa: ARG001
            call_count[0] += 1
            if page == 0:
                return page_0_result
            if page == 1:
                raise Exception("Network error")
            return page_2_result

        mock_api_client.export_profiles_page.side_effect = mock_page_fetch
        mock_storage.create_profiles_table.return_value = 1
        mock_storage.append_profiles_table.return_value = 1

        result = parallel_profile_fetcher.fetch_profiles(name="test_profiles")

        # Should have tracked the failure
        assert result.has_failures is True
        assert result.failed_pages >= 1
        assert len(result.failed_page_indices) >= 1

    def test_callback_invoked_on_failure(
        self,
        parallel_profile_fetcher: Any,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """on_page_complete callback is invoked with error on failure."""
        # Page 0 succeeds, then fails
        page_0_result = ProfilePageResult(
            profiles=[{"$distinct_id": "user1"}],
            session_id="session_abc",
            page=0,
            has_more=True,
        )

        def mock_page_fetch(page: int, **kwargs: Any) -> ProfilePageResult:  # noqa: ARG001
            if page == 0:
                return page_0_result
            raise Exception("API error")

        mock_api_client.export_profiles_page.side_effect = mock_page_fetch
        mock_storage.create_profiles_table.return_value = 1

        progress_updates: list[ProfileProgress] = []

        parallel_profile_fetcher.fetch_profiles(
            name="test_profiles",
            on_page_complete=lambda p: progress_updates.append(p),
        )

        # Should have at least one success and one failure
        successes = [p for p in progress_updates if p.success]
        failures = [p for p in progress_updates if not p.success]

        assert len(successes) >= 1
        assert len(failures) >= 1
        assert failures[0].error is not None
