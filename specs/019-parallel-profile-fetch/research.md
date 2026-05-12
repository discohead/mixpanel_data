# Research: Parallel Profile Fetching

**Feature**: 019-parallel-profile-fetch
**Date**: 2026-01-05

## Research Summary

All technical questions have been resolved through analysis of the existing codebase and Mixpanel API documentation.

## 1. Engage API Pagination Model

**Decision**: Use page-index parallelism with session_id consistency

**Rationale**: The Mixpanel Engage API uses a pagination model where:
- Page 0 returns: `total`, `page_size`, `session_id`, and first page of results
- Subsequent pages require the same `session_id` for consistent results
- Pages are 0-indexed with configurable `page_size` (default: 1000)

**Alternatives Considered**:
- Cursor-based pagination: Not supported by Engage API
- Offset pagination: Engage API uses page index, not offset

**Source**: [Mixpanel Engage API Documentation](context/mixpanel-http-api-specification.md), existing `export_profiles()` implementation

## 2. Engage API Rate Limits

**Decision**: Default to 5 workers, cap at API limit, warn at hourly threshold

**Rationale**: The Engage API uses Query API rate limits:
- Max 5 concurrent queries (hard limit enforced by API)
- 60 queries per hour (soft limit, then 429 responses)
- 10 second timeout per request

This is more restrictive than the Export API (which allows higher concurrency).

**Implementation**:
- Default `max_workers=5`
- Cap any user-specified workers to 5 with warning
- Warn when `num_pages > 60` (exceeds hourly quota)

**Alternatives Considered**:
- Allow >5 workers: Would cause immediate 429 errors
- No hourly warning: Users would encounter unexpected rate limits

**Source**: Mixpanel API documentation, community reports

## 3. DuckDB Single-Writer Constraint

**Decision**: Reuse producer-consumer pattern from parallel event fetcher

**Rationale**: DuckDB only allows one writer at a time. The existing `ParallelFetcherService` solved this with:
- Fetch threads produce data to a bounded queue
- Single writer thread consumes and writes to DuckDB
- Queue provides backpressure (bounded to `workers * 2`)

This pattern is proven and can be directly reused.

**Implementation**: Copy pattern from `parallel_fetcher.py`, adapt for page-based chunks

**Alternatives Considered**:
- Write locks per fetch thread: Would serialize writes anyway, more complex
- Batch writes after all fetches: Memory-intensive for large profile sets
- Connection pool: DuckDB doesn't benefit from this approach

## 4. New Types vs Reusing Existing Types

**Decision**: Create new `ProfileBatchProgress` and `ParallelProfileFetchResult` types

**Rationale**: Profiles use page indices, not date ranges. The existing types have:
- `BatchProgress.from_date`, `to_date`: Irrelevant for profiles
- `ParallelFetchResult.failed_date_ranges`: Should be `failed_page_indices`

New types allow:
- Clear semantics (page_index vs date range)
- Type safety (can't confuse profile and event results)
- Better IDE/mypy support

**Alternatives Considered**:
- Reuse existing types with optional fields: Confusing, loses type safety
- Generic base class: Adds complexity without benefit

## 5. API Method Design

**Decision**: Add `query_engage_page()` method that returns full response dict

**Rationale**: The existing `export_profiles()` iterates all pages internally. For parallel fetching:
- Need page 0 response metadata (total, page_size, session_id)
- Need to fetch arbitrary pages by index with session_id
- Need raw response, not transformed profiles (transform happens in fetcher)

**Implementation**:
```python
def query_engage_page(
    self,
    page: int,
    *,
    session_id: str | None = None,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch single page, return full response with metadata."""
```

**Alternatives Considered**:
- Modify `export_profiles()`: Would break existing interface
- Return tuple (data, metadata): Less clean than full response dict

## 6. Progress Callback Signature

**Decision**: Use `ProfileBatchProgress` dataclass for callbacks

**Rationale**: Follows existing pattern from `BatchProgress`. Provides:
- Page index and total pages (for progress calculation)
- Row count per page
- Success/failure status
- Error message if failed

**Implementation**:
```python
def on_batch_complete(progress: ProfileBatchProgress) -> None:
    pct = (progress.page_index + 1) / progress.total_pages * 100
    print(f"Page {progress.page_index + 1}/{progress.total_pages} ({pct:.0f}%)")
```

## 7. CLI Flag Names

**Decision**: Use `--parallel` and `--workers` flags

**Rationale**: Consistent with existing `mp fetch events` parallel flags (if added). Clear, conventional naming.

**Alternatives Considered**:
- `--concurrent`: Less common
- `--threads`: Implementation detail
- `-j` (make-style): Less discoverable

## Resolved Unknowns

All NEEDS CLARIFICATION items have been resolved:

| Item | Resolution |
|------|------------|
| Pagination model | Page-index with session_id |
| Rate limits | 5 concurrent, 60/hour |
| Worker default | 5 (API limit) |
| Type reuse | New types for profiles |
| Writer pattern | Producer-consumer queue |
