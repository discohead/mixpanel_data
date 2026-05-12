# Research: Parallel Export Performance

**Date**: 2026-01-04
**Feature**: 017-parallel-export

## Research Questions

1. What threading model should be used for parallel fetching?
2. How should date ranges be chunked for parallel processing?
3. How should concurrent writes to DuckDB be handled?
4. What rate limiting strategy should be used?
5. How should partial failures be handled?

---

## 1. Threading Model

### Decision: `concurrent.futures.ThreadPoolExecutor`

### Rationale
- The entire `mixpanel_data` codebase is 100% synchronous
- Introducing `asyncio` would require refactoring all I/O operations (httpx client, DuckDB storage)
- `ThreadPoolExecutor` provides simple, familiar API for parallel I/O-bound work
- Part of Python stdlib - no new dependencies

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| `asyncio` with `aiohttp` | Requires rewriting entire I/O stack; too invasive |
| `multiprocessing.Pool` | Overhead of process spawning; serialization complexity |
| `threading.Thread` (manual) | More boilerplate; ThreadPoolExecutor handles lifecycle |

### Implementation Pattern
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(fetch_chunk, chunk): chunk for chunk in chunks}
    for future in as_completed(futures):
        chunk = futures[future]
        result = future.result()  # raises if failed
```

---

## 2. Date Range Chunking

### Decision: Fixed 7-day chunks

### Rationale
- Simple and predictable behavior
- 7 days is a reasonable balance: large enough to amortize API overhead, small enough to parallelize effectively
- For a 90-day range: 13 chunks = 13 parallel requests
- Easy to reason about and debug

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Adaptive chunking based on data density | Requires data profiling; adds complexity; premature optimization |
| 1-day chunks | Too many requests; higher API overhead |
| 30-day chunks | Too few chunks for parallelism; less speedup |

### Edge Cases
- Range < 7 days: Single chunk (sequential fallback)
- Range = 8 days: Two chunks (7 days + 1 day)
- Range = 100 days: ~15 chunks

### Implementation
```python
def split_date_range(
    from_date: str,
    to_date: str,
    chunk_days: int = 7
) -> list[tuple[str, str]]:
    """Split date range into non-overlapping chunks."""
```

---

## 3. DuckDB Write Strategy

### Decision: Producer-Consumer with Single Writer Thread

### Rationale
- DuckDB has a single-writer constraint (only one connection can write at a time)
- Multiple workers produce data; single writer consumes and writes
- Bounded queue provides backpressure (prevents memory exhaustion)
- Queue size of 10-20 provides buffer without excessive memory

### Architecture
```
[Worker 1] ─┐
[Worker 2] ─┼──► [Queue (bounded)] ──► [Writer Thread] ──► [DuckDB]
[Worker N] ─┘
```

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Sequential writes with lock | Serializes I/O; loses parallelism benefit |
| Multiple DuckDB connections | DuckDB single-writer constraint prevents this |
| Write to separate files, merge | Complex; requires cleanup; merge overhead |

### Implementation
```python
from queue import Queue
from threading import Thread

result_queue: Queue[BatchResult | None] = Queue(maxsize=20)

def writer_thread():
    while True:
        batch = result_queue.get()
        if batch is None:  # Poison pill
            break
        storage.append_events_batch(batch.data)
```

---

## 4. Rate Limiting

### Decision: Semaphore-based concurrency control with 10 default workers

### Rationale
- Mixpanel Export API allows 100 concurrent requests
- Using 10% of limit (10 workers) provides safety margin
- Semaphore is thread-safe and simple
- No need for complex token bucket or sliding window

### Mixpanel Rate Limits (from docs)
- Export API: 60 queries/hour, 3 queries/second, 100 max concurrent

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Token bucket rate limiter | Overkill for simple concurrency control |
| Per-second rate limiting | ThreadPoolExecutor naturally limits; semaphore sufficient |
| 50+ workers | Risk of hitting rate limits under heavy use |

### Implementation
```python
import threading

class RateLimiter:
    def __init__(self, max_concurrent: int = 10):
        self._semaphore = threading.Semaphore(max_concurrent)

    @contextmanager
    def acquire(self):
        self._semaphore.acquire()
        try:
            yield
        finally:
            self._semaphore.release()
```

---

## 5. Partial Failure Handling

### Decision: Continue on failure, report failed ranges

### Rationale
- For large exports, losing all progress due to one failure is frustrating
- Users can retry only failed date ranges
- Clear failure reporting enables automation

### Result Structure
```python
@dataclass(frozen=True)
class ParallelFetchResult:
    table: str
    total_rows: int
    successful_batches: int
    failed_batches: int
    failed_date_ranges: list[tuple[str, str]]  # Retry info
    duration_seconds: float

    @property
    def has_failures(self) -> bool:
        return len(self.failed_date_ranges) > 0
```

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Fail fast on first error | Loses successful work; poor UX for large exports |
| Automatic retry | Adds complexity; user can manually retry with failed ranges |
| Ignore failures silently | Violates Explicit Over Implicit principle |

---

## 6. Progress Reporting

### Decision: Per-batch callback with aggregated progress

### Rationale
- Consistent with existing `progress_callback` pattern in FetcherService
- `on_batch_complete` callback provides batch-level visibility
- CLI can show progress bar or batch completion messages

### Implementation
```python
def on_batch_complete(progress: BatchProgress) -> None:
    """Called when a batch completes."""
    print(f"Batch {progress.from_date} to {progress.to_date}: {progress.rows} rows")
```

---

## Summary of Decisions

| Question | Decision |
|----------|----------|
| Threading model | `concurrent.futures.ThreadPoolExecutor` |
| Date chunking | Fixed 7-day chunks |
| DuckDB writes | Producer-consumer with single writer |
| Rate limiting | Semaphore with 10 default workers |
| Failure handling | Continue on failure, report failed ranges |
| Progress | Per-batch callback |

All decisions align with constitution principles:
- **Library-First**: All features in library, CLI wraps
- **Explicit Over Implicit**: Opt-in parallel mode, explicit failure reporting
- **Technology Stack**: stdlib only, no new dependencies
