# Internal API Contracts: Parallel Profile Fetching

**Feature**: 019-parallel-profile-fetch
**Date**: 2026-01-05

## MixpanelAPIClient.query_engage_page

New method for single-page profile fetching.

### Signature

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
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page` | `int` | Yes | Zero-based page index |
| `session_id` | `str \| None` | No | Session ID from page 0 (required for page > 0) |
| `where` | `str \| None` | No | Filter expression |
| `cohort_id` | `str \| None` | No | Cohort ID filter |
| `output_properties` | `list[str] \| None` | No | Properties to include |

### Returns

```python
{
    "results": [{"$distinct_id": str, "$properties": dict}, ...],
    "total": int,       # Total matching profiles
    "page_size": int,   # Profiles per page (typically 1000)
    "page": int,        # Current page index
    "session_id": str,  # Session ID for subsequent requests
}
```

### Errors

| Exception | Condition |
|-----------|-----------|
| `AuthenticationError` | Invalid credentials |
| `RateLimitError` | Rate limit exceeded (429) |
| `ServerError` | Server-side errors (5xx) |

---

## ParallelProfileFetcherService

New service class for parallel profile fetching.

### Constructor

```python
def __init__(
    self,
    api_client: MixpanelAPIClient,
    storage: StorageEngine,
) -> None:
```

### fetch_profiles Method

```python
def fetch_profiles(
    self,
    name: str,
    *,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
    max_workers: int | None = None,
    on_batch_complete: Callable[[ProfileBatchProgress], None] | None = None,
    append: bool = False,
    batch_size: int = 1000,
) -> ParallelProfileFetchResult:
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | Required | Table name |
| `where` | `str \| None` | `None` | Filter expression |
| `cohort_id` | `str \| None` | `None` | Cohort ID filter |
| `output_properties` | `list[str] \| None` | `None` | Properties to include |
| `max_workers` | `int \| None` | `5` | Max concurrent threads (capped at 5) |
| `on_batch_complete` | `Callable` | `None` | Progress callback |
| `append` | `bool` | `False` | Append to existing table |
| `batch_size` | `int` | `1000` | Rows per INSERT/COMMIT |

### Behavior

1. Fetch page 0 to get `total`, `page_size`, `session_id`
2. Calculate `num_pages = ceil(total / page_size)`
3. Log warning if `num_pages > 60` (hourly rate limit)
4. Spawn writer thread with bounded queue
5. Submit page fetches to ThreadPoolExecutor
6. Each fetch transforms and queues data
7. Writer thread creates/appends table
8. Return aggregated result

### Errors

| Exception | Condition |
|-----------|-----------|
| `TableExistsError` | Table exists and `append=False` |
| `TableNotFoundError` | Table missing and `append=True` |

---

## FetcherService.fetch_profiles (Updated)

### New Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `parallel` | `bool` | `False` | Enable parallel mode |
| `max_workers` | `int \| None` | `None` | Workers for parallel mode |
| `on_batch_complete` | `Callable` | `None` | Progress callback |

### Return Type

```python
FetchResult | ParallelProfileFetchResult
```

- Returns `FetchResult` when `parallel=False`
- Returns `ParallelProfileFetchResult` when `parallel=True`

---

## Workspace.fetch_profiles (Updated)

### New Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `parallel` | `bool` | `False` | Enable parallel mode |
| `max_workers` | `int \| None` | `None` | Workers for parallel mode |
| `on_batch_complete` | `Callable` | `None` | Progress callback |

### Return Type

```python
FetchResult | ParallelProfileFetchResult
```

### Progress Bar Behavior

When `parallel=True` and `progress=True`:
- Shows page-based progress bar
- Updates after each page completes
- Hides when custom `on_batch_complete` provided

---

## CLI: mp fetch profiles (Updated)

### New Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--parallel / -p` | flag | `False` | Enable parallel mode |
| `--workers` | `int` | `5` | Max concurrent threads |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (all pages) |
| 1 | Partial failure (some pages failed) |
| 2 | Authentication error |
| 3 | Invalid arguments |

### Output (JSON)

```json
{
  "table": "profiles",
  "total_rows": 25000,
  "successful_pages": 25,
  "failed_pages": 0,
  "failed_page_indices": [],
  "duration_seconds": 8.5,
  "fetched_at": "2026-01-05T10:30:00Z",
  "has_failures": false
}
```
