"""Parallel Fetcher Service for concurrent Mixpanel data export.

Implements multi-threaded event fetching with producer-consumer pattern
to handle DuckDB's single-writer constraint (feature 017-parallel-export).
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from mixpanel_data._internal.date_utils import split_date_range
from mixpanel_data._internal.rate_limiter import RateLimiter
from mixpanel_data._internal.transforms import transform_event
from mixpanel_data.types import (
    BatchProgress,
    ParallelFetchResult,
    TableMetadata,
)

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient
    from mixpanel_data._internal.storage import StorageEngine

_logger = logging.getLogger(__name__)

# Sentinel value to signal writer thread to stop
_STOP_SENTINEL = object()


@dataclass
class _WriteTask:
    """Task item for the writer queue.

    Encapsulates all data needed to write a batch and track its result.

    Attributes:
        data: Transformed event records to write.
        metadata: Table metadata for the batch.
        batch_idx: Index of this batch (0-based).
        chunk_from: Start date of the chunk (YYYY-MM-DD).
        chunk_to: End date of the chunk (YYYY-MM-DD).
        rows: Number of rows in this batch.
    """

    data: list[dict[str, Any]]
    metadata: TableMetadata
    batch_idx: int
    chunk_from: str
    chunk_to: str
    rows: int


class ParallelFetcherService:
    """Parallel fetcher for concurrent Mixpanel event export.

    Splits date ranges into chunks and fetches them in parallel using
    ThreadPoolExecutor. Uses a producer-consumer pattern with a queue
    to serialize DuckDB writes (single-writer constraint).

    Attributes:
        _api_client: Mixpanel API client for fetching events.
        _storage: DuckDB storage engine for persisting data.
        _default_max_workers: Default number of concurrent fetch threads.
        _chunk_days: Number of days per chunk for date range splitting.

    Example:
        ```python
        fetcher = ParallelFetcherService(api_client, storage)
        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-03-31",
            max_workers=10,
        )
        print(f"Fetched {result.total_rows} rows in {result.duration_seconds}s")
        ```
    """

    def __init__(
        self,
        api_client: MixpanelAPIClient,
        storage: StorageEngine,
    ) -> None:
        """Initialize the parallel fetcher service.

        Args:
            api_client: Authenticated Mixpanel API client.
            storage: DuckDB storage engine for persisting data.
        """
        self._api_client = api_client
        self._storage = storage
        self._default_max_workers = 10

    def fetch_events(
        self,
        name: str,
        from_date: str,
        to_date: str,
        *,
        events: list[str] | None = None,
        where: str | None = None,
        max_workers: int | None = None,
        on_batch_complete: Callable[[BatchProgress], None] | None = None,
        append: bool = False,
        batch_size: int = 1000,
        chunk_days: int = 7,
    ) -> ParallelFetchResult:
        """Fetch events in parallel and store in local database.

        Splits the date range into chunks and fetches them concurrently.
        Uses a producer-consumer pattern to serialize DuckDB writes.

        Args:
            name: Table name to create or append to.
            from_date: Start date (YYYY-MM-DD, inclusive).
            to_date: End date (YYYY-MM-DD, inclusive).
            events: Optional list of event names to filter.
            where: Optional filter expression.
            max_workers: Maximum concurrent fetch threads. Defaults to 10.
            on_batch_complete: Callback invoked when each batch completes.
            append: If True, append to existing table. If False (default), create new.
            batch_size: Number of rows per INSERT/COMMIT cycle.
            chunk_days: Days per chunk for date range splitting. Defaults to 7.

        Returns:
            ParallelFetchResult with aggregated statistics and any failures.

        Raises:
            TableExistsError: If table exists and append=False.
            TableNotFoundError: If table doesn't exist and append=True.
        """
        start_time = datetime.now(UTC)
        workers = max_workers or self._default_max_workers

        # Split date range into chunks
        chunks = split_date_range(from_date, to_date, chunk_days=chunk_days)
        total_batches = len(chunks)

        _logger.info(
            "Starting parallel fetch: %d chunks, %d workers", total_batches, workers
        )

        # Rate limiter for concurrent API calls
        rate_limiter = RateLimiter(max_concurrent=workers)

        # Queue for serializing writes to DuckDB (bounded to provide backpressure)
        write_queue: queue.Queue[_WriteTask | object] = queue.Queue(maxsize=workers * 2)

        # Results tracking
        results_lock = threading.Lock()
        total_rows = 0
        successful_batches = 0
        failed_batches = 0
        failed_date_ranges: list[tuple[str, str]] = []
        table_created = False

        def fetch_chunk(
            chunk_from: str,
            chunk_to: str,
            batch_idx: int,
        ) -> None:
            """Fetch a single date range chunk and queue for writing.

            API fetch errors are tracked immediately as failures.
            Write success/failure is tracked by writer_thread after write completes.
            """
            nonlocal failed_batches

            try:
                with rate_limiter.acquire():
                    # Fetch events from API
                    events_iter = self._api_client.export_events(
                        from_date=chunk_from,
                        to_date=chunk_to,
                        events=events,
                        where=where,
                    )

                    # Transform and collect events
                    transformed = [transform_event(e) for e in events_iter]
                    rows = len(transformed)

                    # Create metadata for this batch
                    metadata = TableMetadata(
                        type="events",
                        fetched_at=datetime.now(UTC),
                        from_date=chunk_from,
                        to_date=chunk_to,
                        filter_events=events,
                        filter_where=where,
                    )

                    # Queue for writing - include all info needed for tracking
                    # Success/failure will be determined by writer_thread after write
                    write_queue.put(
                        _WriteTask(
                            data=transformed,
                            metadata=metadata,
                            batch_idx=batch_idx,
                            chunk_from=chunk_from,
                            chunk_to=chunk_to,
                            rows=rows,
                        )
                    )

                    _logger.debug(
                        "Batch %d/%d fetched: %s to %s, %d rows (queued for write)",
                        batch_idx + 1,
                        total_batches,
                        chunk_from,
                        chunk_to,
                        rows,
                    )

            except Exception as e:
                # API fetch failed - track immediately
                _logger.warning(
                    "Batch %d/%d fetch failed: %s to %s, error: %s",
                    batch_idx + 1,
                    total_batches,
                    chunk_from,
                    chunk_to,
                    str(e),
                )

                with results_lock:
                    failed_batches += 1
                    failed_date_ranges.append((chunk_from, chunk_to))

                # Invoke callback with error
                if on_batch_complete:
                    progress = BatchProgress(
                        from_date=chunk_from,
                        to_date=chunk_to,
                        batch_index=batch_idx,
                        total_batches=total_batches,
                        rows=0,
                        success=False,
                        error=str(e),
                    )
                    on_batch_complete(progress)

        def writer_thread() -> None:
            """Single writer thread for DuckDB.

            Handles success/failure accounting AFTER write completes.
            This ensures reported success reflects actual data persistence.
            """
            nonlocal table_created, total_rows, successful_batches, failed_batches

            while True:
                item = write_queue.get()
                if item is _STOP_SENTINEL:
                    break

                # Type narrow to _WriteTask (sentinel already handled above)
                task = item if isinstance(item, _WriteTask) else None
                if task is None:
                    continue

                if not task.data:
                    # Empty batch - still count as successful (no data to write)
                    with results_lock:
                        successful_batches += 1
                    if on_batch_complete:
                        progress = BatchProgress(
                            from_date=task.chunk_from,
                            to_date=task.chunk_to,
                            batch_index=task.batch_idx,
                            total_batches=total_batches,
                            rows=0,
                            success=True,
                            error=None,
                        )
                        on_batch_complete(progress)
                    continue

                try:
                    if not table_created and not append:
                        actual_rows = self._storage.create_events_table(
                            name=name,
                            data=iter(task.data),
                            metadata=task.metadata,
                            batch_size=batch_size,
                        )
                        table_created = True
                    else:
                        actual_rows = self._storage.append_events_table(
                            name=name,
                            data=iter(task.data),
                            metadata=task.metadata,
                            batch_size=batch_size,
                        )

                    # Write succeeded - now mark as successful
                    # Use actual_rows (after deduplication) not task.rows (raw API count)
                    with results_lock:
                        total_rows += actual_rows
                        successful_batches += 1

                    if on_batch_complete:
                        progress = BatchProgress(
                            from_date=task.chunk_from,
                            to_date=task.chunk_to,
                            batch_index=task.batch_idx,
                            total_batches=total_batches,
                            rows=actual_rows,
                            success=True,
                            error=None,
                        )
                        on_batch_complete(progress)

                    _logger.debug(
                        "Batch %d/%d written: %s to %s, %d rows",
                        task.batch_idx + 1,
                        total_batches,
                        task.chunk_from,
                        task.chunk_to,
                        actual_rows,
                    )

                except Exception as e:
                    # Write failed - track as failure
                    _logger.error(
                        "Batch %d/%d write failed: %s to %s, error: %s",
                        task.batch_idx + 1,
                        total_batches,
                        task.chunk_from,
                        task.chunk_to,
                        str(e),
                    )

                    with results_lock:
                        failed_batches += 1
                        failed_date_ranges.append((task.chunk_from, task.chunk_to))

                    if on_batch_complete:
                        progress = BatchProgress(
                            from_date=task.chunk_from,
                            to_date=task.chunk_to,
                            batch_index=task.batch_idx,
                            total_batches=total_batches,
                            rows=0,
                            success=False,
                            error=f"Write failed: {e}",
                        )
                        on_batch_complete(progress)

        # Start writer thread
        writer = threading.Thread(target=writer_thread, daemon=True)
        writer.start()

        # Submit fetch tasks to thread pool
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = []
            for idx, (chunk_from, chunk_to) in enumerate(chunks):
                future = executor.submit(fetch_chunk, chunk_from, chunk_to, idx)
                futures.append(future)

            # Wait for all fetches to complete
            for future in as_completed(futures):
                # Just wait for completion, errors handled in fetch_chunk
                try:
                    future.result()
                except Exception as e:
                    _logger.error("Unexpected error in fetch task: %s", str(e))

        # Signal writer to stop and wait
        write_queue.put(_STOP_SENTINEL)
        writer.join()

        # Calculate duration
        completed_at = datetime.now(UTC)
        duration_seconds = (completed_at - start_time).total_seconds()

        _logger.info(
            "Parallel fetch completed: %d rows, %d/%d batches successful, %.2fs",
            total_rows,
            successful_batches,
            total_batches,
            duration_seconds,
        )

        return ParallelFetchResult(
            table=name,
            total_rows=total_rows,
            successful_batches=successful_batches,
            failed_batches=failed_batches,
            failed_date_ranges=tuple(failed_date_ranges),
            duration_seconds=duration_seconds,
            fetched_at=completed_at,
        )
