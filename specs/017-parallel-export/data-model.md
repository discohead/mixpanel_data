# Data Model: Parallel Export Performance

**Date**: 2026-01-04
**Feature**: 017-parallel-export

## New Types

This feature introduces three new types to `src/mixpanel_data/types.py` following the existing frozen dataclass pattern with `to_dict()` serialization.

---

### BatchProgress

Progress information for a single batch during parallel export.

```python
@dataclass(frozen=True)
class BatchProgress:
    """Progress update for a parallel fetch batch.

    Sent to the on_batch_complete callback when a batch finishes
    (successfully or with error).

    Attributes:
        from_date: Start date of this batch (YYYY-MM-DD).
        to_date: End date of this batch (YYYY-MM-DD).
        batch_index: Zero-based index of this batch.
        total_batches: Total number of batches in the parallel fetch.
        rows: Number of rows fetched in this batch (0 if failed).
        success: Whether this batch completed successfully.
        error: Error message if failed, None if successful.
    """

    from_date: str
    """Start date of this batch (YYYY-MM-DD)."""

    to_date: str
    """End date of this batch (YYYY-MM-DD)."""

    batch_index: int
    """Zero-based index of this batch."""

    total_batches: int
    """Total number of batches in the parallel fetch."""

    rows: int
    """Number of rows fetched in this batch (0 if failed)."""

    success: bool
    """Whether this batch completed successfully."""

    error: str | None = None
    """Error message if failed, None if successful."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "from_date": self.from_date,
            "to_date": self.to_date,
            "batch_index": self.batch_index,
            "total_batches": self.total_batches,
            "rows": self.rows,
            "success": self.success,
            "error": self.error,
        }
```

---

### BatchResult

Internal result of fetching a single date range chunk.

```python
@dataclass(frozen=True)
class BatchResult:
    """Result of fetching a single date range chunk.

    Internal type used by ParallelFetcherService to track batch outcomes.
    Contains either the fetched data (on success) or error info (on failure).

    Attributes:
        from_date: Start date of this batch (YYYY-MM-DD).
        to_date: End date of this batch (YYYY-MM-DD).
        rows: Number of rows fetched (0 if failed).
        success: Whether the batch completed successfully.
        error: Exception message if failed, None if successful.
        data: Iterator of transformed events (consumed by writer thread).
    """

    from_date: str
    """Start date of this batch (YYYY-MM-DD)."""

    to_date: str
    """End date of this batch (YYYY-MM-DD)."""

    rows: int
    """Number of rows fetched (0 if failed)."""

    success: bool
    """Whether the batch completed successfully."""

    error: str | None = None
    """Exception message if failed, None if successful."""

    # Note: data is not included in to_dict() - it's consumed by writer thread
    # and not serializable

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output (excludes data)."""
        return {
            "from_date": self.from_date,
            "to_date": self.to_date,
            "rows": self.rows,
            "success": self.success,
            "error": self.error,
        }
```

---

### ParallelFetchResult

Aggregated result from a parallel fetch operation.

```python
@dataclass(frozen=True)
class ParallelFetchResult:
    """Result of a parallel fetch operation.

    Aggregates results from all batches, providing summary statistics
    and information about any failures for retry.

    Attributes:
        table: Name of the created/appended table.
        total_rows: Total number of rows fetched across all batches.
        successful_batches: Number of batches that completed successfully.
        failed_batches: Number of batches that failed.
        failed_date_ranges: List of (from_date, to_date) tuples for failed batches.
        duration_seconds: Total time taken for the parallel fetch.
        fetched_at: Timestamp when fetch completed.
    """

    table: str
    """Name of the created/appended table."""

    total_rows: int
    """Total number of rows fetched across all batches."""

    successful_batches: int
    """Number of batches that completed successfully."""

    failed_batches: int
    """Number of batches that failed."""

    failed_date_ranges: tuple[tuple[str, str], ...]
    """Date ranges (from_date, to_date) of failed batches for retry."""

    duration_seconds: float
    """Total time taken for the parallel fetch."""

    fetched_at: datetime
    """Timestamp when fetch completed."""

    @property
    def has_failures(self) -> bool:
        """Check if any batches failed.

        Returns:
            True if at least one batch failed, False otherwise.
        """
        return self.failed_batches > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "table": self.table,
            "total_rows": self.total_rows,
            "successful_batches": self.successful_batches,
            "failed_batches": self.failed_batches,
            "failed_date_ranges": [
                list(dr) for dr in self.failed_date_ranges
            ],
            "duration_seconds": self.duration_seconds,
            "fetched_at": self.fetched_at.isoformat(),
            "has_failures": self.has_failures,
        }
```

---

## Internal Types (Not in types.py)

These types are internal to the parallel fetcher implementation.

### DateChunk (in date_utils.py)

Simple tuple type for date range chunks.

```python
DateChunk = tuple[str, str]  # (from_date, to_date)
```

### QueueItem (in parallel_fetcher.py)

Union type for items in the writer queue.

```python
QueueItem = BatchResult | None  # None is poison pill for shutdown
```

---

## Type Relationships

```
split_date_range() → list[DateChunk]
                            ↓
                    ParallelFetcherService
                            ↓
        ┌───────────────────┼───────────────────┐
        ↓                   ↓                   ↓
   BatchResult         BatchResult         BatchResult
        ↓                   ↓                   ↓
        └───────────────────┼───────────────────┘
                            ↓
                   ParallelFetchResult
```

---

## Existing Types Unchanged

The existing `FetchResult` type is unchanged. When `parallel=False` (default), `fetch_events()` continues to return `FetchResult`. When `parallel=True`, it returns `ParallelFetchResult`.

This maintains backward compatibility - existing code expecting `FetchResult` continues to work.

---

## Validation Rules

| Type | Field | Validation |
|------|-------|------------|
| BatchProgress | batch_index | Must be >= 0 and < total_batches |
| BatchProgress | total_batches | Must be > 0 |
| BatchProgress | rows | Must be >= 0 |
| BatchResult | rows | Must be >= 0 |
| ParallelFetchResult | total_rows | Must be >= 0 |
| ParallelFetchResult | successful_batches + failed_batches | Must equal total batch count |
