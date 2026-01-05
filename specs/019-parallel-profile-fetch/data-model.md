# Data Model: Parallel Profile Fetching

**Feature**: 019-parallel-profile-fetch
**Date**: 2026-01-05

## New Types

### ProfileBatchProgress

Progress update for a parallel profile fetch page.

```
ProfileBatchProgress
├── page_index: int          # 0-based page index
├── total_pages: int         # Total number of pages
├── rows: int                # Profiles in this page (0 if failed)
├── success: bool            # Whether page completed successfully
└── error: str | None        # Error message if failed
```

**Validation Rules**:
- `page_index >= 0`
- `total_pages > 0`
- `page_index < total_pages`
- `rows >= 0`
- `error` must be None when `success=True`

**State Transitions**: Immutable (frozen dataclass)

### ParallelProfileFetchResult

Aggregated result of a parallel profile fetch operation.

```
ParallelProfileFetchResult
├── table: str                           # Created/appended table name
├── total_rows: int                      # Rows fetched across all pages
├── successful_pages: int                # Pages completed successfully
├── failed_pages: int                    # Pages that failed
├── failed_page_indices: tuple[int, ...] # Failed page indices for retry
├── duration_seconds: float              # Total operation time
├── fetched_at: datetime                 # Completion timestamp
└── has_failures: bool (property)        # Computed: failed_pages > 0
```

**Validation Rules**:
- `total_rows >= 0`
- `successful_pages >= 0`
- `failed_pages >= 0`
- `successful_pages + failed_pages == total_pages` (invariant)
- `len(failed_page_indices) == failed_pages`
- `duration_seconds >= 0`

**State Transitions**: Immutable (frozen dataclass)

### _ProfileWriteTask (Internal)

Internal task for writer queue. Not part of public API.

```
_ProfileWriteTask
├── data: list[dict[str, Any]]  # Transformed profile records
├── metadata: TableMetadata     # For database metadata table
├── page_index: int             # For tracking/logging
└── rows: int                   # Row count for progress
```

## Existing Types (Unchanged)

### TableMetadata

Already supports profiles via `type="profiles"`. No changes needed.

### FetchResult

Existing type for sequential fetch. Returned when `parallel=False`.

## Type Relationships

```
fetch_profiles(parallel=False)  →  FetchResult
fetch_profiles(parallel=True)   →  ParallelProfileFetchResult
                                      │
                                      └── on_batch_complete callback
                                              │
                                              └── ProfileBatchProgress
```

## Database Schema

No schema changes. Profiles are stored in existing table structure:

```sql
CREATE TABLE {name} (
    distinct_id VARCHAR PRIMARY KEY,
    properties JSON,
    last_seen TIMESTAMP
);
```

Metadata recorded in `_metadata` table with `type='profiles'`.
