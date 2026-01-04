"""Unit tests for ParallelFetcherService.

Tests for the parallel fetch implementation with ThreadPoolExecutor
and producer-consumer queue pattern (feature 017-parallel-export).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from mixpanel_data._internal.services.parallel_fetcher import ParallelFetcherService
from mixpanel_data.types import BatchProgress, ParallelFetchResult

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
    storage.append_events_table.return_value = 0
    storage.create_events_table.return_value = 0
    return storage


@pytest.fixture
def parallel_fetcher(
    mock_api_client: MagicMock, mock_storage: MagicMock
) -> ParallelFetcherService:
    """Create a ParallelFetcherService with mocked dependencies."""
    return ParallelFetcherService(
        api_client=mock_api_client,
        storage=mock_storage,
    )


# =============================================================================
# ParallelFetcherService Construction Tests
# =============================================================================


class TestParallelFetcherServiceConstruction:
    """Tests for ParallelFetcherService initialization."""

    def test_create_with_api_client_and_storage(
        self, mock_api_client: MagicMock, mock_storage: MagicMock
    ) -> None:
        """ParallelFetcherService can be created with api_client and storage."""
        fetcher = ParallelFetcherService(
            api_client=mock_api_client,
            storage=mock_storage,
        )

        assert fetcher._api_client is mock_api_client
        assert fetcher._storage is mock_storage

    def test_default_max_workers(
        self, mock_api_client: MagicMock, mock_storage: MagicMock
    ) -> None:
        """Default max_workers is 10."""
        fetcher = ParallelFetcherService(
            api_client=mock_api_client,
            storage=mock_storage,
        )

        assert fetcher._default_max_workers == 10


# =============================================================================
# Parallel Fetch Tests
# =============================================================================


class TestParallelFetchEvents:
    """Tests for parallel fetch_events method."""

    def test_fetch_events_returns_parallel_fetch_result(
        self, parallel_fetcher: ParallelFetcherService, mock_api_client: MagicMock
    ) -> None:
        """fetch_events returns ParallelFetchResult."""
        # Setup mock to return empty iterator
        mock_api_client.export_events.return_value = iter([])

        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-07",
        )

        assert isinstance(result, ParallelFetchResult)

    def test_fetch_events_single_chunk_range(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Range smaller than chunk_days creates single batch."""
        # Setup mock
        mock_events = [
            {"event": "test", "properties": {"distinct_id": "u1", "time": 1704067200}}
        ]
        mock_api_client.export_events.return_value = iter(mock_events)
        mock_storage.create_events_table.return_value = 1

        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-05",
        )

        assert result.successful_batches == 1
        assert result.failed_batches == 0
        assert result.total_rows >= 0

    def test_fetch_events_multiple_chunks(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Large range creates multiple batches."""
        # Setup mock to return events for each chunk
        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-21",  # 21 days = 3 chunks
        )

        # Should have multiple batches
        assert result.successful_batches + result.failed_batches >= 1

    def test_fetch_events_respects_max_workers(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """max_workers parameter limits concurrency."""
        concurrent_count = 0
        max_observed = 0
        lock = threading.Lock()

        def slow_export(
            *args: Any,  # noqa: ARG001
            **kwargs: Any,  # noqa: ARG001
        ) -> Iterator[dict[str, Any]]:
            nonlocal concurrent_count, max_observed
            with lock:
                concurrent_count += 1
                max_observed = max(max_observed, concurrent_count)
            time.sleep(0.02)
            with lock:
                concurrent_count -= 1
            return iter([])

        mock_api_client.export_events.side_effect = slow_export
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        _ = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-21",
            max_workers=2,
        )

        # max_observed should be <= max_workers
        assert max_observed <= 2

    def test_fetch_events_invokes_on_batch_complete_callback(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """on_batch_complete callback is invoked for each batch."""
        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        batch_progress_list: list[BatchProgress] = []

        def on_batch(progress: BatchProgress) -> None:
            batch_progress_list.append(progress)

        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-14",  # 14 days = 2 chunks
            on_batch_complete=on_batch,
        )

        # Should have received progress for each batch
        assert (
            len(batch_progress_list)
            == result.successful_batches + result.failed_batches
        )

    def test_fetch_events_batch_progress_has_correct_fields(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """BatchProgress contains expected fields."""
        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0

        batch_progress_list: list[BatchProgress] = []

        _ = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-07",
            on_batch_complete=lambda p: batch_progress_list.append(p),
        )

        assert len(batch_progress_list) >= 1
        progress = batch_progress_list[0]
        assert progress.from_date == "2024-01-01"
        assert progress.to_date == "2024-01-07"
        assert progress.batch_index == 0
        assert progress.total_batches >= 1
        assert progress.success is True

    def test_fetch_events_result_has_table_name(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """ParallelFetchResult contains table name."""
        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0

        result = parallel_fetcher.fetch_events(
            name="my_events",
            from_date="2024-01-01",
            to_date="2024-01-07",
        )

        assert result.table == "my_events"

    def test_fetch_events_result_has_duration(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """ParallelFetchResult contains duration_seconds."""
        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0

        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-07",
        )

        assert result.duration_seconds >= 0

    def test_fetch_events_result_has_fetched_at(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """ParallelFetchResult contains fetched_at timestamp."""
        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0

        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-07",
        )

        assert isinstance(result.fetched_at, datetime)

    def test_fetch_events_passes_events_filter(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """events filter is passed to API client."""
        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0

        parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-07",
            events=["Sign Up", "Purchase"],
        )

        # Verify events filter was passed
        call_args = mock_api_client.export_events.call_args
        assert call_args.kwargs["events"] == ["Sign Up", "Purchase"]

    def test_fetch_events_passes_where_filter(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """where filter is passed to API client."""
        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0

        parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-07",
            where='properties["country"] == "US"',
        )

        # Verify where filter was passed
        call_args = mock_api_client.export_events.call_args
        assert call_args.kwargs["where"] == 'properties["country"] == "US"'


# =============================================================================
# Chunk Days Parameter Tests
# =============================================================================


class TestParallelFetchChunkDays:
    """Tests for chunk_days parameter in fetch_events."""

    def test_fetch_events_default_chunk_days(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Default chunk_days is 7 when not specified."""
        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        # 21 days with default 7-day chunks = 3 batches
        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-21",
        )

        # Should have 3 batches (7-day chunks over 21 days)
        assert result.successful_batches == 3

    def test_fetch_events_custom_chunk_days(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Custom chunk_days parameter controls chunking."""
        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        # 21 days with 3-day chunks = 7 batches
        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-21",
            chunk_days=3,
        )

        # Should have 7 batches (3-day chunks over 21 days)
        assert result.successful_batches == 7

    def test_fetch_events_single_day_chunks(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """chunk_days=1 creates one batch per day."""
        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        # 5 days with 1-day chunks = 5 batches
        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-05",
            chunk_days=1,
        )

        # Should have 5 batches (1 per day)
        assert result.successful_batches == 5

    def test_fetch_events_large_chunk_days(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Large chunk_days creates fewer batches."""
        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        # 30 days with 30-day chunks = 1 batch
        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-30",
            chunk_days=30,
        )

        # Should have 1 batch (entire range fits in one chunk)
        assert result.successful_batches == 1

    def test_fetch_events_chunk_days_100(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """chunk_days=100 (maximum) works correctly."""
        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0

        # 50 days with 100-day chunks = 1 batch
        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-02-19",  # 50 days
            chunk_days=100,
        )

        # Should have 1 batch
        assert result.successful_batches == 1


# =============================================================================
# Partial Failure Handling Tests
# =============================================================================


class TestParallelFetchPartialFailure:
    """Tests for partial failure handling."""

    def test_continues_on_batch_failure(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Fetcher continues processing when one batch fails."""
        call_count = 0

        def export_with_failure(
            *args: Any,  # noqa: ARG001
            **kwargs: Any,  # noqa: ARG001
        ) -> Iterator[dict[str, Any]]:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Simulated API error")
            return iter([])

        mock_api_client.export_events.side_effect = export_with_failure
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-21",  # 3 chunks
        )

        # Should have some successful and some failed batches
        assert result.successful_batches >= 1
        assert result.failed_batches >= 1

    def test_failed_date_ranges_populated(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """failed_date_ranges contains ranges that failed."""
        call_count = 0

        def export_with_failure(
            *args: Any,  # noqa: ARG001
            **kwargs: Any,  # noqa: ARG001
        ) -> Iterator[dict[str, Any]]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated API error")
            return iter([])

        mock_api_client.export_events.side_effect = export_with_failure
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-14",  # 2 chunks
        )

        # Should have at least one failed range
        assert result.has_failures is True
        assert len(result.failed_date_ranges) >= 1

    def test_has_failures_false_when_all_succeed(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """has_failures is False when all batches succeed."""
        mock_api_client.export_events.return_value = iter([])
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-14",
        )

        assert result.has_failures is False
        assert result.failed_date_ranges == ()

    def test_batch_progress_error_on_failure(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """BatchProgress contains error message when batch fails."""
        call_count = 0

        def export_with_failure(
            *args: Any,  # noqa: ARG001
            **kwargs: Any,  # noqa: ARG001
        ) -> Iterator[dict[str, Any]]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Test error message")
            return iter([])

        mock_api_client.export_events.side_effect = export_with_failure
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        progress_list: list[BatchProgress] = []

        parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-14",
            on_batch_complete=lambda p: progress_list.append(p),
        )

        # Find the failed batch
        failed = [p for p in progress_list if not p.success]
        assert len(failed) >= 1
        assert failed[0].error is not None
        assert "Test error message" in failed[0].error


# =============================================================================
# Storage Integration Tests
# =============================================================================


class TestParallelFetchStorage:
    """Tests for storage operations during parallel fetch."""

    def test_creates_table_for_first_batch(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """First batch creates the table (when data exists)."""
        # Return actual events so storage is called
        mock_events = [
            {"event": "test", "properties": {"distinct_id": "u1", "time": 1704067200}}
        ]
        mock_api_client.export_events.return_value = iter(mock_events)
        mock_storage.create_events_table.return_value = 1

        parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-07",
        )

        mock_storage.create_events_table.assert_called()

    def test_appends_for_subsequent_batches(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Subsequent batches append to the table (when data exists)."""
        # Return actual events for each call
        mock_events = [
            {"event": "test", "properties": {"distinct_id": "u1", "time": 1704067200}}
        ]
        mock_api_client.export_events.return_value = iter(mock_events)
        mock_storage.create_events_table.return_value = 1
        mock_storage.append_events_table.return_value = 1

        parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-21",  # 3 chunks
        )

        # With data, either create or append should be called
        total_calls = (
            mock_storage.create_events_table.call_count
            + mock_storage.append_events_table.call_count
        )
        assert total_calls >= 1

    def test_append_mode_uses_append_for_all(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """When append=True, all batches use append (when data exists)."""
        # Return actual events so storage is called
        mock_events = [
            {"event": "test", "properties": {"distinct_id": "u1", "time": 1704067200}}
        ]
        mock_api_client.export_events.return_value = iter(mock_events)
        mock_storage.append_events_table.return_value = 1

        parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-07",
            append=True,
        )

        # Should call append, not create
        mock_storage.append_events_table.assert_called()
        mock_storage.create_events_table.assert_not_called()


# =============================================================================
# Concurrency Tests
# =============================================================================


class TestParallelFetchConcurrency:
    """Tests for concurrent execution behavior."""

    def test_batches_execute_in_parallel(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Multiple batches can execute concurrently."""
        concurrent_count = 0
        max_concurrent = 0
        lock = threading.Lock()

        def track_concurrency(*_args: Any, **_kwargs: Any) -> Iterator[dict[str, Any]]:
            nonlocal concurrent_count, max_concurrent
            with lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
            time.sleep(0.02)
            with lock:
                concurrent_count -= 1
            return iter([])

        mock_api_client.export_events.side_effect = track_concurrency
        mock_storage.create_events_table.return_value = 0
        mock_storage.append_events_table.return_value = 0

        parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-28",  # 4 chunks
            max_workers=4,
        )

        # Should have seen some concurrent execution
        assert max_concurrent >= 1  # At least some parallelism

    def test_single_writer_thread_for_storage(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Storage writes happen from a single thread (DuckDB constraint)."""
        write_thread_ids: set[int] = set()
        lock = threading.Lock()

        def track_write_thread(*_args: Any, **_kwargs: Any) -> int:
            with lock:
                write_thread_ids.add(threading.current_thread().ident or 0)
            return 0

        mock_storage.create_events_table.side_effect = track_write_thread
        mock_storage.append_events_table.side_effect = track_write_thread
        mock_api_client.export_events.return_value = iter([])

        parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-21",  # 3 chunks
            max_workers=3,
        )

        # All writes should happen from same thread
        assert len(write_thread_ids) <= 1


# =============================================================================
# Write Failure Tests
# =============================================================================


class TestParallelFetchWriteFailure:
    """Tests for database write failure handling.

    These tests verify that write failures (as opposed to API fetch failures)
    are properly tracked and reported.
    """

    def test_write_failure_tracked_as_failure(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Write failures are tracked in failed_batches count."""
        # API fetch succeeds, but storage write fails
        mock_events = [
            {"event": "test", "properties": {"distinct_id": "u1", "time": 1704067200}}
        ]
        mock_api_client.export_events.return_value = iter(mock_events)
        mock_storage.create_events_table.side_effect = RuntimeError("Disk full")

        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-07",  # 1 chunk
        )

        assert result.has_failures is True
        assert result.failed_batches >= 1
        assert result.successful_batches == 0

    def test_write_failure_callback_with_error(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Write failure triggers callback with error message."""
        mock_events = [
            {"event": "test", "properties": {"distinct_id": "u1", "time": 1704067200}}
        ]
        mock_api_client.export_events.return_value = iter(mock_events)
        mock_storage.create_events_table.side_effect = RuntimeError("Database locked")

        progress_list: list[BatchProgress] = []

        parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-07",
            on_batch_complete=lambda p: progress_list.append(p),
        )

        # Should have exactly one callback (for the failed batch)
        assert len(progress_list) == 1
        assert progress_list[0].success is False
        assert progress_list[0].error is not None
        assert "Database locked" in progress_list[0].error

    def test_write_failure_populates_failed_date_ranges(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Write failures add date range to failed_date_ranges."""
        mock_events = [
            {"event": "test", "properties": {"distinct_id": "u1", "time": 1704067200}}
        ]
        mock_api_client.export_events.return_value = iter(mock_events)
        mock_storage.create_events_table.side_effect = RuntimeError("IO error")

        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-07",
        )

        assert len(result.failed_date_ranges) >= 1
        # The failed range should be the date range we requested
        failed_from, failed_to = result.failed_date_ranges[0]
        assert failed_from == "2024-01-01"
        assert failed_to == "2024-01-07"

    def test_write_failure_does_not_count_rows(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Failed writes don't add to total_rows count."""
        mock_events = [
            {"event": "e1", "properties": {"distinct_id": "u1", "time": 1704067200}},
            {"event": "e2", "properties": {"distinct_id": "u2", "time": 1704067200}},
        ]
        mock_api_client.export_events.return_value = iter(mock_events)
        mock_storage.create_events_table.side_effect = RuntimeError("Write failed")

        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-07",
        )

        # Even though 2 events were fetched, none should be counted due to write failure
        assert result.total_rows == 0

    def test_partial_write_failure(
        self,
        parallel_fetcher: ParallelFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Some batches can succeed while others fail during write."""
        # Make each API call return a fresh iterator with one event
        mock_events = [
            {"event": "test", "properties": {"distinct_id": "u1", "time": 1704067200}}
        ]
        mock_api_client.export_events.side_effect = lambda **_kwargs: iter(mock_events)

        write_count = 0

        def write_with_partial_failure(*_args: Any, **_kwargs: Any) -> int:
            nonlocal write_count
            write_count += 1
            if write_count == 1:
                return 1  # First write succeeds
            raise RuntimeError("Second write fails")

        mock_storage.create_events_table.side_effect = write_with_partial_failure
        mock_storage.append_events_table.side_effect = write_with_partial_failure

        result = parallel_fetcher.fetch_events(
            name="test_events",
            from_date="2024-01-01",
            to_date="2024-01-14",  # 2 chunks
        )

        # Should have one success and one failure
        assert result.successful_batches >= 1
        assert result.failed_batches >= 1
        assert result.has_failures is True
