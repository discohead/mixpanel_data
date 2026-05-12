# Quickstart: Parallel Export

**Feature**: 017-parallel-export

This guide shows how to use parallel export for faster data fetching.

---

## Library Usage

### Basic Parallel Export

```python
import mixpanel_data as mp

# Connect to workspace
ws = mp.Workspace(account="my-account", db="analytics.db")

# Parallel export (up to 10x faster for large date ranges)
result = ws.fetch_events(
    name="events_q4",
    from_date="2024-10-01",
    to_date="2024-12-31",
    parallel=True,  # Enable parallel fetching
)

print(f"Fetched {result.total_rows} rows in {result.duration_seconds:.1f}s")
```

### Custom Worker Count

```python
# Use more workers for faster exports (up to ~20 recommended)
result = ws.fetch_events(
    name="events_2024",
    from_date="2024-01-01",
    to_date="2024-12-31",
    parallel=True,
    max_workers=15,  # Default is 10
)
```

### Progress Tracking

```python
from mixpanel_data.types import BatchProgress

def on_batch(progress: BatchProgress) -> None:
    """Called when each batch completes."""
    status = "✓" if progress.success else "✗"
    print(f"[{status}] Batch {progress.batch_index + 1}/{progress.total_batches}: "
          f"{progress.from_date} to {progress.to_date} ({progress.rows} rows)")

result = ws.fetch_events(
    name="events_q4",
    from_date="2024-10-01",
    to_date="2024-12-31",
    parallel=True,
    on_batch_complete=on_batch,
)
```

### Handling Partial Failures

```python
result = ws.fetch_events(
    name="events_q4",
    from_date="2024-10-01",
    to_date="2024-12-31",
    parallel=True,
)

if result.has_failures:
    print(f"Warning: {result.failed_batches} batches failed")
    print("Failed date ranges (can retry):")
    for from_date, to_date in result.failed_date_ranges:
        print(f"  {from_date} to {to_date}")
else:
    print(f"All {result.successful_batches} batches completed successfully")
```

### Retry Failed Batches

```python
# Initial fetch
result = ws.fetch_events(
    name="events_q4",
    from_date="2024-10-01",
    to_date="2024-12-31",
    parallel=True,
)

# Retry any failed batches by appending
for from_date, to_date in result.failed_date_ranges:
    retry_result = ws.fetch_events(
        name="events_q4",
        from_date=from_date,
        to_date=to_date,
        append=True,  # Append to existing table
    )
    print(f"Retried {from_date} to {to_date}: {retry_result.rows} rows")
```

---

## CLI Usage

### Basic Parallel Export

```bash
# Enable parallel mode with --parallel flag
mp fetch events --parallel \
  --from 2024-10-01 \
  --to 2024-12-31 \
  --name events_q4
```

### Custom Worker Count

```bash
# Use 15 workers instead of default 10
mp fetch events --parallel --workers 15 \
  --from 2024-01-01 \
  --to 2024-12-31 \
  --name events_2024
```

### Example Output

```
Fetching events from 2024-10-01 to 2024-12-31 (parallel mode, 10 workers)
[✓] Batch 1/13: 2024-10-01 to 2024-10-07 (15,234 rows)
[✓] Batch 2/13: 2024-10-08 to 2024-10-14 (14,891 rows)
[✓] Batch 3/13: 2024-10-15 to 2024-10-21 (16,102 rows)
...
[✓] Batch 13/13: 2024-12-25 to 2024-12-31 (12,456 rows)

Completed: 189,432 rows in 45.2s (13 batches)
Table: events_q4
```

### Partial Failure Output

```
Fetching events from 2024-10-01 to 2024-12-31 (parallel mode, 10 workers)
[✓] Batch 1/13: 2024-10-01 to 2024-10-07 (15,234 rows)
[✗] Batch 2/13: 2024-10-08 to 2024-10-14 (Rate limit exceeded)
[✓] Batch 3/13: 2024-10-15 to 2024-10-21 (16,102 rows)
...

Completed with errors: 174,198 rows in 52.1s
  Successful: 12/13 batches
  Failed: 1/13 batches

Failed date ranges (retry with sequential fetch):
  2024-10-08 to 2024-10-14

Exit code: 1
```

---

## When to Use Parallel Export

| Scenario | Recommendation |
|----------|----------------|
| Date range < 7 days | Use sequential (default) - no benefit from parallel |
| Date range 7-30 days | Parallel optional - modest speedup |
| Date range 30-100 days | **Use parallel** - significant speedup |
| Date range > 100 days | **Use parallel** - major speedup (requires chunking) |

---

## Performance Expectations

| Date Range | Sequential | Parallel (10 workers) | Speedup |
|------------|------------|----------------------|---------|
| 7 days | ~2 min | ~2 min | 1x |
| 30 days | ~10 min | ~2 min | 5x |
| 90 days | ~30 min | ~4 min | 7.5x |

*Actual speedup depends on network latency and data volume per day.*

---

## Comparison: Sequential vs Parallel

### Sequential (Default)

```python
# Single request for entire date range
result = ws.fetch_events(
    name="events",
    from_date="2024-10-01",
    to_date="2024-12-31",
)
# Returns: FetchResult
```

### Parallel

```python
# Multiple concurrent requests (7-day chunks)
result = ws.fetch_events(
    name="events",
    from_date="2024-10-01",
    to_date="2024-12-31",
    parallel=True,
)
# Returns: ParallelFetchResult
```

Key differences:
- Return type: `FetchResult` vs `ParallelFetchResult`
- Error handling: All-or-nothing vs partial success
- Progress: Single callback vs batch callbacks
