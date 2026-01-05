"""Parallel Profile Fetcher Service for concurrent Mixpanel profile export.

Implements multi-threaded profile fetching with producer-consumer pattern
to handle DuckDB's single-writer constraint (feature 019-parallel-profile-fetch).
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

from mixpanel_data._internal.transforms import transform_profile
from mixpanel_data.types import (
    ParallelProfileResult,
    ProfilePageResult,
    ProfileProgress,
    TableMetadata,
)

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient
    from mixpanel_data._internal.storage import StorageEngine

_logger = logging.getLogger(__name__)

# Sentinel value to signal writer thread to stop
_STOP_SENTINEL = object()

# Maximum workers for profile fetching (more conservative than events)
_MAX_WORKERS_CAP = 5

# Threshold for rate limit warnings (60 requests/hour limit)
_RATE_LIMIT_WARNING_THRESHOLD = 48


@dataclass
class _ProfileWriteTask:
    """Task item for the writer queue.

    Encapsulates all data needed to write a batch and track its result.

    Attributes:
        data: Transformed profile records to write.
        metadata: Table metadata for the batch.
        page_idx: Page index for this batch.
        rows: Number of rows in this batch.
    """

    data: list[dict[str, Any]]
    metadata: TableMetadata
    page_idx: int
    rows: int


class ParallelProfileFetcherService:
    """Parallel fetcher for concurrent Mixpanel profile export.

    Fetches profile pages in parallel using ThreadPoolExecutor. Uses a
    producer-consumer pattern with a queue to serialize DuckDB writes
    (single-writer constraint).

    The Engage API uses session-based pagination where page 0 is fetched
    first to get a session_id, then subsequent pages use that session_id
    to maintain consistency during the export.

    Attributes:
        _api_client: Mixpanel API client for fetching profiles.
        _storage: DuckDB storage engine for persisting data.
        _default_max_workers: Default number of concurrent fetch threads.

    Example:
        ```python
        fetcher = ParallelProfileFetcherService(api_client, storage)
        result = fetcher.fetch_profiles(
            name="profiles",
            max_workers=5,
        )
        print(f"Fetched {result.total_rows} rows in {result.duration_seconds}s")
        ```
    """

    def __init__(
        self,
        api_client: MixpanelAPIClient,
        storage: StorageEngine,
    ) -> None:
        """Initialize the parallel profile fetcher service.

        Args:
            api_client: Authenticated Mixpanel API client.
            storage: DuckDB storage engine for persisting data.
        """
        self._api_client = api_client
        self._storage = storage
        self._default_max_workers = 5

    def fetch_profiles(
        self,
        name: str,
        *,
        where: str | None = None,
        cohort_id: str | None = None,
        output_properties: list[str] | None = None,
        max_workers: int | None = None,
        on_page_complete: Callable[[ProfileProgress], None] | None = None,
        append: bool = False,
        batch_size: int = 1000,
    ) -> ParallelProfileResult:
        """Fetch profiles in parallel and store in local database.

        Fetches page 0 first to get the session_id, then spawns parallel
        workers to fetch remaining pages. Uses a producer-consumer pattern
        to serialize DuckDB writes.

        Args:
            name: Table name to create or append to.
            where: Optional filter expression.
            cohort_id: Optional cohort ID filter.
            output_properties: Optional list of properties to include.
            max_workers: Maximum concurrent fetch threads. Defaults to 5, capped at 5.
            on_page_complete: Callback invoked when each page completes.
            append: If True, append to existing table. If False (default), create new.
            batch_size: Number of rows per INSERT/COMMIT cycle.

        Returns:
            ParallelProfileResult with aggregated statistics and any failures.

        Raises:
            TableExistsError: If table exists and append=False.
            TableNotFoundError: If table doesn't exist and append=True.
        """
        start_time = datetime.now(UTC)

        # Cap workers at maximum
        requested_workers = max_workers or self._default_max_workers
        workers = min(requested_workers, _MAX_WORKERS_CAP)

        _logger.info("Starting parallel profile fetch with %d workers", workers)

        # Fetch page 0 to get session_id and first batch of profiles
        page_0_result = self._api_client.export_profiles_page(
            page=0,
            session_id=None,
            where=where,
            cohort_id=cohort_id,
            output_properties=output_properties,
        )

        session_id = page_0_result.session_id

        # Track results
        results_lock = threading.Lock()
        total_rows = 0
        successful_pages = 0
        failed_pages = 0
        failed_page_indices: list[int] = []
        table_created = False
        cumulative_rows = 0

        # Queue for serializing writes to DuckDB (bounded for backpressure)
        write_queue: queue.Queue[_ProfileWriteTask | object] = queue.Queue(
            maxsize=workers * 2
        )

        def process_page_0() -> None:
            """Process the initial page 0 that was already fetched."""
            nonlocal table_created, total_rows, successful_pages, failed_pages
            nonlocal cumulative_rows

            if not page_0_result.profiles:
                with results_lock:
                    successful_pages += 1
                if on_page_complete:
                    progress = ProfileProgress(
                        page_index=0,
                        total_pages=None,
                        rows=0,
                        success=True,
                        error=None,
                        cumulative_rows=0,
                    )
                    on_page_complete(progress)
                return

            # Transform profiles
            transformed = [transform_profile(p) for p in page_0_result.profiles]

            try:
                metadata = TableMetadata(
                    type="profiles",
                    fetched_at=datetime.now(UTC),
                    filter_where=where,
                )

                if not append:
                    actual_rows = self._storage.create_profiles_table(
                        name=name,
                        data=iter(transformed),
                        metadata=metadata,
                        batch_size=batch_size,
                    )
                    table_created = True
                else:
                    actual_rows = self._storage.append_profiles_table(
                        name=name,
                        data=iter(transformed),
                        metadata=metadata,
                        batch_size=batch_size,
                    )

                with results_lock:
                    total_rows += actual_rows
                    successful_pages += 1
                    cumulative_rows = total_rows

                if on_page_complete:
                    progress = ProfileProgress(
                        page_index=0,
                        total_pages=None,
                        rows=actual_rows,
                        success=True,
                        error=None,
                        cumulative_rows=cumulative_rows,
                    )
                    on_page_complete(progress)

                _logger.debug("Page 0 processed: %d rows", actual_rows)

            except Exception as e:
                _logger.error("Page 0 write failed: %s", str(e))
                with results_lock:
                    failed_pages += 1
                    failed_page_indices.append(0)

                if on_page_complete:
                    progress = ProfileProgress(
                        page_index=0,
                        total_pages=None,
                        rows=0,
                        success=False,
                        error=str(e),
                        cumulative_rows=cumulative_rows,
                    )
                    on_page_complete(progress)

        # Process page 0
        process_page_0()

        # If no more pages, return early
        if not page_0_result.has_more:
            completed_at = datetime.now(UTC)
            duration_seconds = (completed_at - start_time).total_seconds()

            return ParallelProfileResult(
                table=name,
                total_rows=total_rows,
                successful_pages=successful_pages,
                failed_pages=failed_pages,
                failed_page_indices=tuple(failed_page_indices),
                duration_seconds=duration_seconds,
                fetched_at=completed_at,
            )

        # Use session_id from page 0 for subsequent pages
        current_session_id = session_id
        warned_about_rate_limits = False

        def fetch_page(page_idx: int) -> tuple[int, ProfilePageResult | Exception]:
            """Fetch a single page and return result or exception."""
            try:
                result = self._api_client.export_profiles_page(
                    page=page_idx,
                    session_id=current_session_id,
                    where=where,
                    cohort_id=cohort_id,
                    output_properties=output_properties,
                )
                return (page_idx, result)
            except Exception as e:
                return (page_idx, e)

        def writer_thread() -> None:
            """Single writer thread for DuckDB."""
            nonlocal table_created, total_rows, successful_pages, failed_pages
            nonlocal cumulative_rows

            while True:
                item = write_queue.get()
                if item is _STOP_SENTINEL:
                    break

                task = item if isinstance(item, _ProfileWriteTask) else None
                if task is None:
                    continue

                if not task.data:
                    with results_lock:
                        successful_pages += 1
                    if on_page_complete:
                        progress = ProfileProgress(
                            page_index=task.page_idx,
                            total_pages=None,
                            rows=0,
                            success=True,
                            error=None,
                            cumulative_rows=cumulative_rows,
                        )
                        on_page_complete(progress)
                    continue

                try:
                    if not table_created and not append:
                        actual_rows = self._storage.create_profiles_table(
                            name=name,
                            data=iter(task.data),
                            metadata=task.metadata,
                            batch_size=batch_size,
                        )
                        table_created = True
                    else:
                        actual_rows = self._storage.append_profiles_table(
                            name=name,
                            data=iter(task.data),
                            metadata=task.metadata,
                            batch_size=batch_size,
                        )

                    with results_lock:
                        total_rows += actual_rows
                        successful_pages += 1
                        cumulative_rows = total_rows

                    if on_page_complete:
                        progress = ProfileProgress(
                            page_index=task.page_idx,
                            total_pages=None,
                            rows=actual_rows,
                            success=True,
                            error=None,
                            cumulative_rows=cumulative_rows,
                        )
                        on_page_complete(progress)

                    _logger.debug(
                        "Page %d written: %d rows", task.page_idx, actual_rows
                    )

                except Exception as e:
                    _logger.error("Page %d write failed: %s", task.page_idx, str(e))

                    with results_lock:
                        failed_pages += 1
                        failed_page_indices.append(task.page_idx)

                    if on_page_complete:
                        progress = ProfileProgress(
                            page_index=task.page_idx,
                            total_pages=None,
                            rows=0,
                            success=False,
                            error=f"Write failed: {e}",
                            cumulative_rows=cumulative_rows,
                        )
                        on_page_complete(progress)

        # Start writer thread
        writer = threading.Thread(target=writer_thread, daemon=True)
        writer.start()

        # Track state for dynamic page discovery
        more_pages_exist = True
        max_page_submitted = 0
        pages_discovered = 0

        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Start with just page 1 (page 0 already processed)
            pending_pages: set[int] = {1}
            max_page_submitted = 1
            future_to_page: dict[Any, int] = {executor.submit(fetch_page, 1): 1}

            while pending_pages or (more_pages_exist and future_to_page):
                # Wait for any completed futures
                completed_futures = []
                for future in list(future_to_page.keys()):
                    if future.done():
                        completed_futures.append(future)

                if not completed_futures and future_to_page:
                    # Wait for at least one to complete
                    for future in as_completed(list(future_to_page.keys())[:1]):
                        completed_futures.append(future)
                        break

                for future in completed_futures:
                    page_idx = future_to_page.pop(future)
                    pending_pages.discard(page_idx)

                    try:
                        result = future.result()
                        page_num, page_result = result

                        if isinstance(page_result, Exception):
                            # Fetch failed
                            _logger.warning(
                                "Page %d fetch failed: %s", page_num, str(page_result)
                            )
                            with results_lock:
                                failed_pages += 1
                                failed_page_indices.append(page_num)

                            if on_page_complete:
                                progress = ProfileProgress(
                                    page_index=page_num,
                                    total_pages=None,
                                    rows=0,
                                    success=False,
                                    error=str(page_result),
                                    cumulative_rows=cumulative_rows,
                                )
                                on_page_complete(progress)
                        else:
                            # Fetch succeeded
                            pages_discovered += 1

                            # Warn about rate limits if we've discovered many pages
                            if (
                                not warned_about_rate_limits
                                and pages_discovered >= _RATE_LIMIT_WARNING_THRESHOLD
                            ):
                                warned_about_rate_limits = True
                                _logger.warning(
                                    "Large profile export: %d+ pages may exceed "
                                    "rate limits. Consider using cohort filters or "
                                    "output_properties to reduce dataset size.",
                                    pages_discovered,
                                )

                            # Check if more pages exist and submit next page
                            if page_result.has_more:
                                next_page = max_page_submitted + 1
                                if next_page not in pending_pages:
                                    pending_pages.add(next_page)
                                    max_page_submitted = next_page
                                    future = executor.submit(fetch_page, next_page)
                                    future_to_page[future] = next_page
                            else:
                                # This page has no more pages after it
                                more_pages_exist = False

                            # Queue profiles for writing
                            transformed = [
                                transform_profile(p) for p in page_result.profiles
                            ]
                            metadata = TableMetadata(
                                type="profiles",
                                fetched_at=datetime.now(UTC),
                                filter_where=where,
                            )
                            write_queue.put(
                                _ProfileWriteTask(
                                    data=transformed,
                                    metadata=metadata,
                                    page_idx=page_num,
                                    rows=len(transformed),
                                )
                            )

                    except Exception as e:
                        _logger.error(
                            "Unexpected error processing page %d: %s", page_idx, str(e)
                        )

                # Break if no more pending and no more pages to discover
                if not pending_pages and not future_to_page:
                    break
                if not more_pages_exist and not future_to_page:
                    break

        # Signal writer to stop and wait
        write_queue.put(_STOP_SENTINEL)
        writer.join()

        # Calculate duration
        completed_at = datetime.now(UTC)
        duration_seconds = (completed_at - start_time).total_seconds()

        _logger.info(
            "Parallel profile fetch completed: %d rows, %d/%d pages successful, %.2fs",
            total_rows,
            successful_pages,
            successful_pages + failed_pages,
            duration_seconds,
        )

        return ParallelProfileResult(
            table=name,
            total_rows=total_rows,
            successful_pages=successful_pages,
            failed_pages=failed_pages,
            failed_page_indices=tuple(failed_page_indices),
            duration_seconds=duration_seconds,
            fetched_at=completed_at,
        )
