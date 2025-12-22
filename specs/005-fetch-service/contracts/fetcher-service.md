# FetcherService Contract

**Type**: Internal Python Service
**Location**: `src/mixpanel_data/_internal/services/fetcher.py`
**Date**: 2025-12-22

## Overview

The FetcherService is an internal service that coordinates data fetching from Mixpanel API to local DuckDB storage. It is not a REST API but rather a Python class used by the Workspace facade.

---

## Class Definition

```python
class FetcherService:
    """Coordinates data fetches from Mixpanel API to local storage.

    This service bridges the MixpanelAPIClient and StorageEngine,
    handling data transformation and progress reporting.

    Example:
        >>> from mixpanel_data._internal.api_client import MixpanelAPIClient
        >>> from mixpanel_data._internal.storage import StorageEngine
        >>> from mixpanel_data._internal.services.fetcher import FetcherService
        >>>
        >>> client = MixpanelAPIClient(credentials)
        >>> storage = StorageEngine(path)
        >>> fetcher = FetcherService(client, storage)
        >>>
        >>> result = fetcher.fetch_events(
        ...     name="events",
        ...     from_date="2024-01-01",
        ...     to_date="2024-01-31",
        ... )
        >>> print(f"Fetched {result.rows} events")
    """
```

---

## Constructor

```python
def __init__(
    self,
    api_client: MixpanelAPIClient,
    storage: StorageEngine,
) -> None:
    """Initialize the fetcher service.

    Args:
        api_client: Authenticated Mixpanel API client.
        storage: DuckDB storage engine for persisting data.
    """
```

**Contract**:
- `api_client` MUST be an authenticated `MixpanelAPIClient` instance
- `storage` MUST be an initialized `StorageEngine` instance
- Constructor MUST NOT make any API or database calls

---

## Methods

### fetch_events

```python
def fetch_events(
    self,
    name: str,
    from_date: str,
    to_date: str,
    *,
    events: list[str] | None = None,
    where: str | None = None,
    progress_callback: Callable[[int], None] | None = None,
) -> FetchResult:
    """Fetch events from Mixpanel and store in local database.

    Args:
        name: Table name to create (alphanumeric + underscore, no leading _).
        from_date: Start date (YYYY-MM-DD, inclusive).
        to_date: End date (YYYY-MM-DD, inclusive).
        events: Optional list of event names to filter.
        where: Optional filter expression.
        progress_callback: Optional callback invoked with row count during fetch.

    Returns:
        FetchResult with table name, row count, duration, and metadata.

    Raises:
        TableExistsError: If table with given name already exists.
        AuthenticationError: If API credentials are invalid.
        RateLimitError: If Mixpanel rate limit is exceeded.
        QueryError: If filter expression is invalid.
        ValueError: If table name is invalid.
    """
```

**Contract**:
- MUST create a new table with the specified name
- MUST raise `TableExistsError` if table already exists
- MUST stream data without loading entire dataset into memory
- MUST call `progress_callback` at least every 1,000 events (if provided)
- MUST return accurate `duration_seconds` (within 1 second of actual)
- MUST record metadata in the `_metadata` table
- MUST transform events from API format to storage format
- MUST rollback transaction on any error (no partial tables)

---

### fetch_profiles

```python
def fetch_profiles(
    self,
    name: str,
    *,
    where: str | None = None,
    progress_callback: Callable[[int], None] | None = None,
) -> FetchResult:
    """Fetch user profiles from Mixpanel and store in local database.

    Args:
        name: Table name to create (alphanumeric + underscore, no leading _).
        where: Optional filter expression.
        progress_callback: Optional callback invoked with row count during fetch.

    Returns:
        FetchResult with table name, row count, duration, and metadata.
        The date_range field will be None for profiles.

    Raises:
        TableExistsError: If table with given name already exists.
        AuthenticationError: If API credentials are invalid.
        RateLimitError: If Mixpanel rate limit is exceeded.
        ValueError: If table name is invalid.
    """
```

**Contract**:
- MUST create a new table with the specified name
- MUST raise `TableExistsError` if table already exists
- MUST stream data without loading entire dataset into memory
- MUST call `progress_callback` after each page (if provided)
- MUST return `FetchResult` with `date_range=None`
- MUST transform profiles from API format to storage format
- MUST rollback transaction on any error (no partial tables)

---

## Error Handling

| Exception | Condition | Recovery |
|-----------|-----------|----------|
| `TableExistsError` | Table already exists | Call `storage.drop_table(name)` first |
| `AuthenticationError` | Invalid credentials | Check credentials configuration |
| `RateLimitError` | Rate limit exceeded | Wait and retry (exponential backoff) |
| `QueryError` | Invalid filter expression | Fix the `where` parameter |
| `ValueError` | Invalid table name | Use alphanumeric + underscore only |

---

## Usage Patterns

### Basic Event Fetch

```python
fetcher = FetcherService(api_client, storage)
result = fetcher.fetch_events(
    name="events",
    from_date="2024-01-01",
    to_date="2024-01-31",
)
print(f"Fetched {result.rows} events in {result.duration_seconds:.1f}s")
```

### Filtered Event Fetch

```python
result = fetcher.fetch_events(
    name="purchases",
    from_date="2024-01-01",
    to_date="2024-01-31",
    events=["Purchase"],
    where='properties["amount"] > 100',
)
```

### Progress Monitoring

```python
def on_progress(count: int) -> None:
    print(f"Fetched {count} events...", file=sys.stderr)

result = fetcher.fetch_events(
    name="events",
    from_date="2024-01-01",
    to_date="2024-01-31",
    progress_callback=on_progress,
)
```

### Profile Fetch

```python
result = fetcher.fetch_profiles(
    name="profiles",
    where='user["plan"] == "premium"',
)
```

---

## Dependencies

### Required Imports

```python
from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data.types import FetchResult, TableMetadata
from mixpanel_data.exceptions import TableExistsError
```

### Runtime Dependencies

- `MixpanelAPIClient` methods: `export_events()`, `export_profiles()`
- `StorageEngine` methods: `create_events_table()`, `create_profiles_table()`
- `FetchResult` and `TableMetadata` dataclasses from `types.py`
