# Quickstart: Parallel Profile Fetching

**Feature**: 019-parallel-profile-fetch

## Python API

### Basic Usage

```python
import mixpanel_data as mp

# Connect to workspace
ws = mp.Workspace(account="my-account")

# Parallel fetch (recommended for large profile sets)
result = ws.fetch_profiles(
    name="users",
    parallel=True,
)

print(f"Fetched {result.total_rows} profiles in {result.duration_seconds:.1f}s")
```

### With Progress Callback

```python
from mixpanel_data.types import ProfileBatchProgress

def on_progress(p: ProfileBatchProgress) -> None:
    status = "done" if p.success else f"FAILED: {p.error}"
    print(f"Page {p.page_index + 1}/{p.total_pages}: {p.rows} profiles ({status})")

result = ws.fetch_profiles(
    name="users",
    parallel=True,
    on_batch_complete=on_progress,
)
```

### With Filters

```python
# Filter by cohort
result = ws.fetch_profiles(
    name="premium_users",
    cohort_id="12345",
    parallel=True,
)

# Filter by expression
result = ws.fetch_profiles(
    name="us_users",
    where='properties["country"] == "US"',
    parallel=True,
)
```

### Handling Partial Failures

```python
result = ws.fetch_profiles(name="users", parallel=True)

if result.has_failures:
    print(f"Warning: {result.failed_pages} pages failed")
    print(f"Failed page indices: {result.failed_page_indices}")
    # Could retry failed pages individually
```

## CLI Usage

### Basic Parallel Fetch

```bash
# Enable parallel mode
mp fetch profiles --parallel

# With custom table name
mp fetch profiles --parallel --name users
```

### Control Concurrency

```bash
# Use 3 workers instead of default 5
mp fetch profiles --parallel --workers 3
```

### With Filters

```bash
# Filter by cohort
mp fetch profiles --parallel --cohort 12345

# Filter by expression
mp fetch profiles --parallel --where 'properties["country"] == "US"'
```

### JSON Output

```bash
mp fetch profiles --parallel --format json
```

Output:
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

## Performance Expectations

| Profiles | Pages | Sequential | Parallel (5 workers) |
|----------|-------|------------|---------------------|
| 1,000    | 1     | ~2s        | ~2s (no benefit)    |
| 5,000    | 5     | ~10s       | ~2s (~5x faster)    |
| 25,000   | 25    | ~50s       | ~10s (~5x faster)   |
| 60,000   | 60    | ~120s      | ~24s (~5x faster)   |

**Note**: Profile sets > 60,000 may encounter the 60 queries/hour rate limit.

## When to Use Parallel Mode

**Use parallel mode when**:
- Profile set has > 1,000 profiles (multiple pages)
- Speed is important
- You're not near the hourly rate limit

**Use sequential mode when**:
- Profile set is small (< 1,000 profiles)
- You've already made many Engage API queries this hour
- Debugging or need deterministic ordering
