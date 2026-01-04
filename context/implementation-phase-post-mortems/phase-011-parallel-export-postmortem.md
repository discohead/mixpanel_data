# Post-Mortem: Parallel Export Implementation (Feature 017)

## Overview

Feature 017 implemented parallel event fetching to achieve up to 10x speedup for large date range exports. This post-mortem captures learnings to optimize the follow-up work: **parallelizing profile fetching**.

## Implementation Summary

### What Was Built

| Component | Purpose | Location |
|-----------|---------|----------|
| `ParallelFetcherService` | Orchestrates parallel API fetches with single-writer DuckDB | `_internal/services/parallel_fetcher.py` |
| `RateLimiter` | Semaphore-based concurrency control | `_internal/rate_limiter.py` |
| `split_date_range()` | Chunks date ranges into configurable segments | `_internal/date_utils.py` |
| `BatchProgress` | Progress callback data structure | `types.py` |
| `ParallelFetchResult` | Aggregated result with failure tracking | `types.py` |
| CLI flags | `--parallel/-p`, `--workers`, `--chunk-days` | `cli/commands/fetch.py` |

### Architecture Pattern: Producer-Consumer

```
┌─────────────────────────────────────────────────────────────┐
│                    ThreadPoolExecutor                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Fetch    │  │ Fetch    │  │ Fetch    │  │ Fetch    │    │
│  │ Thread 1 │  │ Thread 2 │  │ Thread 3 │  │ Thread N │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │             │             │             │           │
│       └─────────────┴──────┬──────┴─────────────┘           │
│                            ▼                                 │
│                    ┌───────────────┐                        │
│                    │  Write Queue  │                        │
│                    └───────┬───────┘                        │
│                            ▼                                 │
│                    ┌───────────────┐                        │
│                    │ Writer Thread │ ◄── Single writer for  │
│                    │   (DuckDB)    │     DuckDB constraint  │
│                    └───────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

This pattern was chosen because:
1. DuckDB has a single-writer constraint
2. API fetches are I/O bound and benefit from parallelism
3. Decouples fetch rate from write rate

---

## Critical Insight: Events vs Profiles Chunking Strategy

### Events: Date-Based Chunking ✅ (Implemented)

Events have natural date boundaries with **configurable chunk size** (1-100 days):
```python
# Events are partitioned by date range (default: 7 days, configurable via --chunk-days)
chunks = split_date_range("2024-01-01", "2024-03-31", chunk_days=7)
# Returns: [("2024-01-01", "2024-01-07"), ("2024-01-08", "2024-01-14"), ...]

# For high-volume data, smaller chunks may improve parallelism:
chunks = split_date_range("2024-01-01", "2024-03-31", chunk_days=1)
# Returns: [("2024-01-01", "2024-01-01"), ("2024-01-02", "2024-01-02"), ...]
```

Each chunk is an independent API call with distinct date parameters. The `--chunk-days` CLI option (default: 7, valid: 1-100) allows tuning based on data volume.

### Profiles: Page-Index Parallelism ✅ (RECOMMENDED APPROACH)

**Key Discovery**: The Mixpanel Engage API returns `total` count and `page_size` upfront!

```python
# First page response structure
{
    "results": [...],           # First page of profiles
    "total": 50000,             # Total profiles matching query
    "page_size": 1000,          # Profiles per page
    "page": 0,                  # Current page index (0-based)
    "session_id": "abc123"      # Required for subsequent pages
}
```

This enables **page-index parallelism**: after fetching page 0, we know exactly how many pages exist and can fetch them all in parallel!

```
┌─────────────────────────────────────────────────────────────┐
│  SEQUENTIAL: Fetch Page 0                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Response: total=50000, page_size=1000, session_id   │   │
│  │  → Calculate: num_pages = ceil(50000/1000) = 50      │   │
│  └──────────────────────────────────────────────────────┘   │
│                            │                                 │
│                            ▼                                 │
│  PARALLEL: Fetch Pages 1-49 (all use same session_id)       │
│  ┌────────┐ ┌────────┐ ┌────────┐     ┌─────────┐          │
│  │ Page 1 │ │ Page 2 │ │ Page 3 │ ... │ Page 49 │          │
│  └────────┘ └────────┘ └────────┘     └─────────┘          │
└─────────────────────────────────────────────────────────────┘
```

**Why This Works**:
1. Page indices are independent - no cursor chain dependency!
2. `session_id` from page 0 is reused for all parallel requests
3. Each `page=N` request returns exactly that page's results
4. Total pages known upfront: `num_pages = ceil(total / page_size)`

### Reference Implementation (mixpanel-utils)

The old `mixpanel-utils` package used `ConcurrentPaginator` with this exact pattern:

```python
# Old implementation (multiprocessing.pool.ThreadPool)
class ConcurrentPaginator:
    def fetch_all(self, params=None):
        # 1. Fetch first page to get total, session_id
        first_page = self.get_func(params)
        results = first_page["results"]
        params["session_id"] = first_page["session_id"]

        # 2. Calculate remaining pages
        num_pages = math.ceil(first_page["total"] / first_page["page_size"])

        # 3. Fetch pages 1..N in parallel
        fetcher = lambda page: self.get_func({**params, "page": page})["results"]
        pool = ThreadPool(processes=self.concurrency)
        remaining = list(itertools.chain(*pool.map(fetcher, range(1, num_pages))))

        return results + remaining
```

### Modernized Implementation Strategy

Replace `multiprocessing.pool.ThreadPool` with `concurrent.futures.ThreadPoolExecutor`:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import math

def fetch_profiles_parallel(
    api_client,
    storage,
    params: dict,
    max_workers: int = 10,
    on_batch_complete: Callable[[BatchProgress], None] | None = None,
) -> ParallelFetchResult:
    """Fetch all profiles using page-index parallelism."""

    # 1. Fetch page 0 to get metadata
    first_response = api_client.query_engage({**params, "page": 0})
    total = first_response["total"]
    page_size = first_response["page_size"]
    session_id = first_response["session_id"]

    num_pages = math.ceil(total / page_size)

    if num_pages <= 1:
        # Single page - no parallelism needed
        return _store_results(first_response["results"])

    # 2. Queue first page results for writing
    write_queue.put(first_response["results"])

    # 3. Fetch remaining pages in parallel
    def fetch_page(page_idx: int) -> list[dict]:
        response = api_client.query_engage({
            **params,
            "session_id": session_id,
            "page": page_idx,
        })
        return response["results"]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_page, page): page
            for page in range(1, num_pages)
        }

        for future in as_completed(futures):
            page_idx = futures[future]
            try:
                results = future.result()
                write_queue.put(results)
                # Progress callback...
            except Exception as e:
                # Error handling...
```

**Key Improvements over old mixpanel-utils**:
1. `ThreadPoolExecutor` is simpler than `multiprocessing.pool.ThreadPool`
2. `as_completed()` enables progress callbacks as each page finishes
3. Producer-consumer pattern with write queue for DuckDB compatibility
4. Proper error handling with partial failure tracking

---

## Reusable Components for Profile Work

### Can Reuse Directly

| Component | Why Reusable |
|-----------|--------------|
| `RateLimiter` | Generic semaphore, not event-specific |
| `BatchProgress` | Fields are generic (batch_index, rows, success, error) |
| `ParallelFetchResult` | Structure works for any parallel operation |
| Producer-consumer pattern | DuckDB constraint applies equally |
| CLI integration pattern | `--parallel`, `--workers`, `--chunk-days` flags |
| Error handling approach | Continue on failure, track failed ranges |
| Parameter threading pattern | Layer-by-layer with defaults for backward compatibility |

### Must Adapt or Replace

| Component | Why Needs Change |
|-----------|------------------|
| `split_date_range()` | Profiles don't use date ranges |
| `_transform_event()` | Profile structure differs from events |
| Date-based `failed_date_ranges` | Profiles need different failure tracking |

### New Components Needed

| Component | Purpose |
|-----------|---------|
| `split_profiles_query()` | Strategy for partitioning profile fetches |
| `_transform_profile()` | Normalize profile data for storage |
| Profile-specific failure tracking | Track failed shards/cohorts instead of date ranges |

---

## Lessons Learned & Pitfalls to Avoid

### 1. MagicMock Attribute Access Trap

**Problem**: `hasattr(mock_result, "has_failures")` returns `True` for MagicMock

```python
# BAD - MagicMock has any attribute
if hasattr(result, "has_failures") and result.has_failures:
    raise typer.Exit(1)

# GOOD - Explicit type check
from mixpanel_data.types import ParallelFetchResult
if isinstance(result, ParallelFetchResult) and result.has_failures:
    raise typer.Exit(1)
```

**Fix**: Use `isinstance()` for type discrimination in CLI code.

### 2. Short Flag Conflicts

**Problem**: `-w` was used for both `--where` and `--workers`

```python
# Caused warning: "parameter -w is used more than once"
workers: Annotated[int | None, typer.Option("--workers", "-w", ...)]
```

**Fix**: Audit existing short flags before adding new ones. `--workers` has no short flag.

### 3. Import Location for Type Checks

**Problem**: Importing `ParallelFetchResult` at module top caused issues

```python
# Import inside function to avoid circular imports
def fetch_events(...):
    ...
    from mixpanel_data.types import ParallelFetchResult
    if isinstance(result, ParallelFetchResult):
        ...
```

**Fix**: Late imports for type checks are acceptable.

### 4. Test Structure for Parallel Code

**Good Pattern**: Test callback invocation counts

```python
def test_progress_callback_called_for_each_batch():
    progress_updates: list[BatchProgress] = []
    result = fetcher.fetch_events(
        ...,
        on_batch_complete=lambda p: progress_updates.append(p),
    )
    assert len(progress_updates) == result.successful_batches + result.failed_batches
```

### 5. Partial Failure Design

**Pattern**: Continue processing, aggregate failures

```python
# Don't fail fast - continue with other batches
except Exception as e:
    with results_lock:
        failed_batches += 1
        failed_date_ranges.append((chunk_from, chunk_to))
    # Invoke callback with error
    if on_batch_complete:
        on_batch_complete(BatchProgress(..., success=False, error=str(e)))
```

### 6. Parameter Threading Through Layers (TDD Pattern)

**Problem**: Adding `--chunk-days` required threading through 4 layers

**Solution**: TDD with clear layer-by-layer test coverage

```
CLI (--chunk-days N)
    → Workspace.fetch_events(chunk_days=N)
        → FetcherService.fetch_events(chunk_days=N)
            → ParallelFetcherService.fetch_events(chunk_days=N)
                → split_date_range(chunk_days=N)
```

**TDD Approach**:
1. Write unit tests for each layer FIRST (bottom-up)
2. Implement each layer to make tests pass
3. Validate with integration tests at CLI level

**Key Pattern**: Default values at each layer maintain backward compatibility:
```python
# Each layer has default chunk_days=7
def fetch_events(self, ..., chunk_days: int = 7) -> ...:
```

This ensures existing code without `chunk_days` continues to work unchanged.

---

## Recommended Task Structure for Profile Parallelization

Based on this implementation, here's a suggested task breakdown:

### Phase 1: Analysis & Design (CRITICAL)

```
- [ ] Analyze Mixpanel Engage API pagination model
- [ ] Determine if parallel fetching is feasible for profiles
- [ ] Document chunking strategy decision (Strategy A/B/C/D)
- [ ] Update spec.md with profile-specific design
```

### Phase 2: Adapt Existing Components

```
- [ ] Create profile-specific transform function
- [ ] Adapt failure tracking for profiles (if parallel)
- [ ] Extend ParallelFetchResult if needed
```

### Phase 3: Implementation (if parallel feasible)

```
- [ ] Implement profile chunking strategy
- [ ] Create ParallelProfileFetcher (or extend existing)
- [ ] Add --parallel flag to mp fetch profiles
- [ ] Add tests following event tests as template
```

### Phase 4: If Sequential Only

```
- [ ] Document why parallelization isn't feasible
- [ ] Optimize sequential fetch (larger pages, connection reuse)
- [ ] Consider async/streaming optimizations instead
```

---

## Test Coverage Achieved

| Category | Tests Added | Coverage |
|----------|-------------|----------|
| Unit tests (parallel_fetcher) | 30 | 97% |
| Unit tests (fetcher_service) | 4 | 95% |
| Unit tests (workspace) | 4 | 94% |
| Integration tests (parallel_fetcher) | 8 | 100% |
| CLI tests (fetch commands) | 19 | 90% |
| Property-based tests | 4 | N/A |
| **Overall new code** | **69** | **93.61%** |

*Note: Tests include chunk_days parameter coverage across all layers (TDD implementation).*

---

## Performance Benchmarks

| Scenario | Sequential | Parallel (10 workers, 7-day chunks) | Speedup |
|----------|------------|-------------------------------------|---------|
| 7 days | ~5s | ~5s | 1x (no benefit) |
| 30 days | ~20s | ~5s | 4x |
| 90 days | ~60s | ~8s | 7.5x |

**Key Insights**:
- Parallelism only helps for date ranges > chunk_days
- Default chunk_days=7 is optimal for most use cases
- For very high-volume data, smaller chunks (e.g., `--chunk-days 1`) may improve throughput
- For sparse data, larger chunks (e.g., `--chunk-days 30`) reduce API overhead

---

## Files Modified (Reference for Profile Work)

```
src/mixpanel_data/
├── __init__.py                    # Export new types
├── types.py                       # BatchProgress, ParallelFetchResult
├── workspace.py                   # parallel, max_workers, on_batch_complete, chunk_days params
├── _internal/
│   ├── date_utils.py              # split_date_range (events only)
│   ├── rate_limiter.py            # RateLimiter (reusable)
│   └── services/
│       ├── fetcher.py             # Delegation to parallel fetcher, chunk_days forwarding
│       └── parallel_fetcher.py    # Core parallel implementation, chunk_days param
└── cli/commands/
    └── fetch.py                   # --parallel, --workers, --chunk-days, progress callback

tests/
├── unit/
│   ├── test_parallel_fetcher.py   # 30 tests (includes chunk_days tests)
│   ├── test_fetcher_service.py    # +4 chunk_days tests
│   ├── test_workspace.py          # +4 chunk_days validation tests
│   ├── test_rate_limiter.py       # 8 tests
│   └── test_date_utils.py         # 12 tests
└── integration/
    ├── test_parallel_fetcher.py   # 8 tests
    └── cli/test_fetch_commands.py # 19 tests (includes chunk_days CLI tests)
```

---

## Conclusion

The parallel event export implementation provides a solid foundation and reusable patterns. However, **profile parallelization requires a fundamentally different chunking strategy** due to cursor-based pagination.

**Recommendation**: Before implementing, thoroughly investigate the Mixpanel Engage API to determine if parallel fetching is even feasible. If not, focus on sequential optimizations and clearly document why parallelization isn't possible for profiles.
