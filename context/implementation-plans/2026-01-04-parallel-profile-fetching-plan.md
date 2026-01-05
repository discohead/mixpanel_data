# Parallel Profile Fetching Implementation Plan

**Goal:** Add parallel fetching capability to profile exports using page-index parallelism for up to 5x speedup.

**Architecture:** Unlike events (date-based chunking), profiles use page-index parallelism. The Mixpanel Engage API returns `total`, `page_size`, and `session_id` on page 0, enabling calculation of total pages and parallel fetching of pages 1..N using the same session_id.

**Tech Stack:** Python 3.11+, concurrent.futures.ThreadPoolExecutor, threading, queue (all stdlib - no new dependencies)

---

## Critical: Engage API Rate Limits

The Engage API uses **Query API rate limits**, which are more restrictive than the Export API:

| Limit | Value | Impact |
|-------|-------|--------|
| **Max concurrent queries** | 5 | Default `max_workers=5` (not 10 like events) |
| **Queries per hour** | 60 | A 50-page fetch = 50 queries (83% of hourly quota) |
| **Timeout** | 10 seconds | Individual page fetches may timeout |

### Implications for Implementation

1. **Default workers = 5**: The API rejects more than 5 concurrent requests
2. **Rate limit awareness**: Large profile sets (50+ pages) risk hitting 60/hour limit
3. **Automatic retry**: Leverage existing `RateLimitError` handling with exponential backoff
4. **User warning**: CLI should warn when approaching hourly limit

### When Parallelization Helps

| Profile Count | Pages (1000/page) | Queries Used | Speedup |
|---------------|-------------------|--------------|---------|
| < 1,000 | 1 | 1 | None (single page) |
| 5,000 | 5 | 5 | ~5x |
| 25,000 | 25 | 25 | ~5x |
| 50,000 | 50 | 50 | ~5x (uses 83% hourly quota) |
| 100,000 | 100 | 100 | ~5x (exceeds hourly limit!) |

**Recommendation**: For profile sets > 60,000 (60+ pages), warn users that they may hit the hourly rate limit and suggest sequential fetching or waiting between batches.

---

## Architecture Overview

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
│  └───┬────┘ └───┬────┘ └───┬────┘     └────┬────┘          │
│      └──────────┴─────┬────┴───────────────┘               │
│                       ▼                                     │
│               ┌───────────────┐                            │
│               │  Write Queue  │                            │
│               └───────┬───────┘                            │
│                       ▼                                     │
│               ┌───────────────┐                            │
│               │ Writer Thread │ ◄── Single writer for      │
│               │   (DuckDB)    │     DuckDB constraint      │
│               └───────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

## Reusable Components (from event parallel fetch)

| Component | Location | Reuse Strategy |
|-----------|----------|----------------|
| `RateLimiter` | `_internal/rate_limiter.py` | Use directly |
| `BatchProgress` | `types.py` | Adapt: use `page_index` instead of date fields |
| `ParallelFetchResult` | `types.py` | Adapt: `failed_pages` instead of `failed_date_ranges` |
| Producer-consumer pattern | `parallel_fetcher.py` | Copy pattern, adapt for pages |
| `_transform_profile()` | `fetcher.py` | Use directly (already exists) |

## New Types Needed

### ProfileBatchProgress (adapt BatchProgress)

```python
@dataclass(frozen=True)
class ProfileBatchProgress:
    """Progress update for a parallel profile fetch batch."""
    page_index: int          # 0-based page index
    total_pages: int         # Total number of pages
    rows: int                # Profiles in this page
    success: bool
    error: str | None = None
```

### ParallelProfileFetchResult (adapt ParallelFetchResult)

```python
@dataclass(frozen=True)
class ParallelProfileFetchResult:
    """Result of parallel profile fetch."""
    table: str
    total_rows: int
    successful_pages: int
    failed_pages: int
    failed_page_indices: tuple[int, ...]  # For retry
    duration_seconds: float
    fetched_at: datetime

    @property
    def has_failures(self) -> bool:
        return self.failed_pages > 0
```

---

## Task Breakdown

### Task 1: Add New Types to types.py

**Files:**
- Modify: `src/mixpanel_data/types.py`
- Test: `tests/unit/test_types.py`

**Step 1: Write failing tests for ProfileBatchProgress**

```python
# tests/unit/test_types.py - add to existing file

class TestProfileBatchProgress:
    """Tests for ProfileBatchProgress dataclass."""

    def test_create_successful_batch(self) -> None:
        """ProfileBatchProgress can be created for successful batch."""
        progress = ProfileBatchProgress(
            page_index=5,
            total_pages=50,
            rows=1000,
            success=True,
            error=None,
        )
        assert progress.page_index == 5
        assert progress.total_pages == 50
        assert progress.rows == 1000
        assert progress.success is True
        assert progress.error is None

    def test_create_failed_batch(self) -> None:
        """ProfileBatchProgress can be created for failed batch."""
        progress = ProfileBatchProgress(
            page_index=10,
            total_pages=50,
            rows=0,
            success=False,
            error="Connection timeout",
        )
        assert progress.success is False
        assert progress.error == "Connection timeout"

    def test_to_dict_serialization(self) -> None:
        """ProfileBatchProgress serializes to dict correctly."""
        progress = ProfileBatchProgress(
            page_index=1,
            total_pages=10,
            rows=500,
            success=True,
        )
        result = progress.to_dict()
        assert result == {
            "page_index": 1,
            "total_pages": 10,
            "rows": 500,
            "success": True,
            "error": None,
        }
```

**Step 2: Run tests to verify they fail**

Run: `just test -k TestProfileBatchProgress -v`
Expected: FAIL with "cannot import name 'ProfileBatchProgress'"

**Step 3: Implement ProfileBatchProgress**

```python
# src/mixpanel_data/types.py - add after BatchProgress

@dataclass(frozen=True)
class ProfileBatchProgress:
    """Progress update for a parallel profile fetch batch.

    Sent to the on_batch_complete callback when a page finishes
    (successfully or with error).

    Attributes:
        page_index: Zero-based page index being fetched.
        total_pages: Total number of pages in the parallel fetch.
        rows: Number of profiles fetched in this page (0 if failed).
        success: Whether this page completed successfully.
        error: Error message if failed, None if successful.

    Example:
        ```python
        def on_batch(progress: ProfileBatchProgress) -> None:
            pct = (progress.page_index + 1) / progress.total_pages * 100
            print(f"Page {progress.page_index + 1}/{progress.total_pages} ({pct:.0f}%)")

        result = ws.fetch_profiles(
            name="profiles",
            parallel=True,
            on_batch_complete=on_batch,
        )
        ```
    """

    page_index: int
    """Zero-based page index being fetched."""

    total_pages: int
    """Total number of pages in the parallel fetch."""

    rows: int
    """Number of profiles fetched in this page (0 if failed)."""

    success: bool
    """Whether this page completed successfully."""

    error: str | None = None
    """Error message if failed, None if successful."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all batch progress fields.
        """
        return {
            "page_index": self.page_index,
            "total_pages": self.total_pages,
            "rows": self.rows,
            "success": self.success,
            "error": self.error,
        }
```

**Step 4: Run tests to verify they pass**

Run: `just test -k TestProfileBatchProgress -v`
Expected: PASS

**Step 5: Write failing tests for ParallelProfileFetchResult**

```python
class TestParallelProfileFetchResult:
    """Tests for ParallelProfileFetchResult dataclass."""

    def test_create_successful_result(self) -> None:
        """ParallelProfileFetchResult can be created for successful fetch."""
        now = datetime.now(UTC)
        result = ParallelProfileFetchResult(
            table="profiles",
            total_rows=50000,
            successful_pages=50,
            failed_pages=0,
            failed_page_indices=(),
            duration_seconds=12.5,
            fetched_at=now,
        )
        assert result.table == "profiles"
        assert result.total_rows == 50000
        assert result.successful_pages == 50
        assert result.failed_pages == 0
        assert result.has_failures is False

    def test_has_failures_property(self) -> None:
        """has_failures returns True when failed_pages > 0."""
        result = ParallelProfileFetchResult(
            table="profiles",
            total_rows=45000,
            successful_pages=45,
            failed_pages=5,
            failed_page_indices=(10, 20, 30, 40, 45),
            duration_seconds=15.0,
            fetched_at=datetime.now(UTC),
        )
        assert result.has_failures is True
        assert result.failed_page_indices == (10, 20, 30, 40, 45)

    def test_to_dict_serialization(self) -> None:
        """ParallelProfileFetchResult serializes to dict correctly."""
        now = datetime.now(UTC)
        result = ParallelProfileFetchResult(
            table="profiles",
            total_rows=10000,
            successful_pages=10,
            failed_pages=0,
            failed_page_indices=(),
            duration_seconds=5.0,
            fetched_at=now,
        )
        d = result.to_dict()
        assert d["table"] == "profiles"
        assert d["total_rows"] == 10000
        assert d["has_failures"] is False
        assert d["fetched_at"] == now.isoformat()
```

**Step 6: Run tests to verify they fail**

Run: `just test -k TestParallelProfileFetchResult -v`
Expected: FAIL

**Step 7: Implement ParallelProfileFetchResult**

```python
@dataclass(frozen=True)
class ParallelProfileFetchResult:
    """Result of a parallel profile fetch operation.

    Aggregates results from all pages, providing summary statistics
    and information about any failures for retry.

    Attributes:
        table: Name of the created/appended table.
        total_rows: Total number of profiles fetched across all pages.
        successful_pages: Number of pages that completed successfully.
        failed_pages: Number of pages that failed.
        failed_page_indices: Page indices that failed (for retry).
        duration_seconds: Total time taken for the parallel fetch.
        fetched_at: Timestamp when fetch completed.

    Example:
        ```python
        result = ws.fetch_profiles(name="profiles", parallel=True)

        if result.has_failures:
            print(f"Warning: {result.failed_pages} pages failed")
            print(f"Failed pages: {result.failed_page_indices}")
        ```
    """

    table: str
    """Name of the created/appended table."""

    total_rows: int
    """Total number of profiles fetched across all pages."""

    successful_pages: int
    """Number of pages that completed successfully."""

    failed_pages: int
    """Number of pages that failed."""

    failed_page_indices: tuple[int, ...]
    """Page indices that failed (for retry)."""

    duration_seconds: float
    """Total time taken for the parallel fetch."""

    fetched_at: datetime
    """Timestamp when fetch completed."""

    @property
    def has_failures(self) -> bool:
        """Check if any pages failed.

        Returns:
            True if at least one page failed, False otherwise.
        """
        return self.failed_pages > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all result fields including has_failures.
        """
        return {
            "table": self.table,
            "total_rows": self.total_rows,
            "successful_pages": self.successful_pages,
            "failed_pages": self.failed_pages,
            "failed_page_indices": list(self.failed_page_indices),
            "duration_seconds": self.duration_seconds,
            "fetched_at": self.fetched_at.isoformat(),
            "has_failures": self.has_failures,
        }
```

**Step 8: Run tests and verify pass**

Run: `just test -k "TestProfileBatchProgress or TestParallelProfileFetchResult" -v`
Expected: PASS

**Step 9: Export new types from __init__.py**

```python
# src/mixpanel_data/__init__.py - add to exports
from mixpanel_data.types import (
    # ... existing exports ...
    ProfileBatchProgress,
    ParallelProfileFetchResult,
)
```

**Step 10: Commit**

```bash
git add src/mixpanel_data/types.py src/mixpanel_data/__init__.py tests/unit/test_types.py
git commit -m "$(cat <<'EOF'
feat(types): add ProfileBatchProgress and ParallelProfileFetchResult

Add new types for parallel profile fetching:
- ProfileBatchProgress: progress callback for page-based fetching
- ParallelProfileFetchResult: aggregated result with failure tracking

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Add query_engage_page Method to API Client

**Files:**
- Modify: `src/mixpanel_data/_internal/api_client.py`
- Test: `tests/unit/test_api_client.py`

**Step 1: Write failing test for query_engage_page**

```python
# tests/unit/test_api_client.py - add new test class

class TestQueryEngagePage:
    """Tests for query_engage_page method (single page fetch)."""

    def test_query_engage_page_returns_response_dict(
        self, api_client: MixpanelAPIClient, mock_transport: MockTransport
    ) -> None:
        """query_engage_page returns full response dict with metadata."""
        mock_transport.add_response(
            200,
            json.dumps({
                "results": [{"$distinct_id": "u1", "$properties": {"name": "Alice"}}],
                "total": 5000,
                "page_size": 1000,
                "page": 0,
                "session_id": "abc123",
            }),
        )

        response = api_client.query_engage_page(page=0)

        assert response["total"] == 5000
        assert response["page_size"] == 1000
        assert response["session_id"] == "abc123"
        assert len(response["results"]) == 1

    def test_query_engage_page_with_session_id(
        self, api_client: MixpanelAPIClient, mock_transport: MockTransport
    ) -> None:
        """query_engage_page passes session_id for subsequent pages."""
        mock_transport.add_response(
            200,
            json.dumps({
                "results": [{"$distinct_id": "u2", "$properties": {}}],
                "total": 5000,
                "page_size": 1000,
                "page": 5,
                "session_id": "abc123",
            }),
        )

        response = api_client.query_engage_page(
            page=5,
            session_id="abc123",
        )

        assert response["page"] == 5

    def test_query_engage_page_with_filters(
        self, api_client: MixpanelAPIClient, mock_transport: MockTransport
    ) -> None:
        """query_engage_page passes where and cohort_id filters."""
        mock_transport.add_response(
            200,
            json.dumps({
                "results": [],
                "total": 0,
                "page_size": 1000,
                "page": 0,
            }),
        )

        api_client.query_engage_page(
            page=0,
            where='properties["country"] == "US"',
            cohort_id="12345",
        )

        # Verify request was made (transport tracks this)
        assert mock_transport.request_count == 1
```

**Step 2: Run tests to verify they fail**

Run: `just test -k TestQueryEngagePage -v`
Expected: FAIL with "has no attribute 'query_engage_page'"

**Step 3: Implement query_engage_page**

```python
# src/mixpanel_data/_internal/api_client.py - add method

def query_engage_page(
    self,
    page: int,
    *,
    session_id: str | None = None,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch a single page of profiles from the Engage API.

    Unlike export_profiles() which iterates all pages, this method
    fetches a single page and returns the full response including
    pagination metadata (total, page_size, session_id).

    Used by parallel profile fetcher to:
    1. Fetch page 0 to get total count and session_id
    2. Fetch pages 1..N in parallel using the session_id

    Args:
        page: Zero-based page index to fetch.
        session_id: Session ID from page 0 response (required for page > 0).
        where: Optional filter expression.
        cohort_id: Optional cohort ID to filter by.
        output_properties: Optional list of property names to include.

    Returns:
        Full API response dict with keys:
        - results: List of profile dicts
        - total: Total matching profiles
        - page_size: Profiles per page
        - page: Current page index
        - session_id: Session ID for subsequent requests

    Raises:
        AuthenticationError: Invalid credentials.
        RateLimitError: Rate limit exceeded after max retries.
        ServerError: Server-side errors (5xx).
    """
    url = self._build_url("engage", "")

    params: dict[str, Any] = {
        "project_id": self._credentials.project_id,
        "page": page,
    }
    if session_id:
        params["session_id"] = session_id
    if where:
        params["where"] = where
    if cohort_id:
        params["filter_by_cohort"] = cohort_id
    if output_properties:
        params["output_properties"] = json.dumps(output_properties)

    result: dict[str, Any] = self._request("POST", url, data=params)
    return result
```

**Step 4: Run tests to verify they pass**

Run: `just test -k TestQueryEngagePage -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/mixpanel_data/_internal/api_client.py tests/unit/test_api_client.py
git commit -m "$(cat <<'EOF'
feat(api): add query_engage_page for single-page profile fetch

Add query_engage_page() method that returns full response dict
including pagination metadata (total, page_size, session_id).
Enables parallel profile fetching by page index.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Create ParallelProfileFetcherService

**Files:**
- Create: `src/mixpanel_data/_internal/services/parallel_profile_fetcher.py`
- Test: `tests/unit/test_parallel_profile_fetcher.py`

**Step 1: Write failing tests for basic construction**

```python
# tests/unit/test_parallel_profile_fetcher.py

"""Unit tests for ParallelProfileFetcherService.

Tests for the parallel profile fetch implementation with page-index
parallelism and producer-consumer queue pattern.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mixpanel_data._internal.services.parallel_profile_fetcher import (
    ParallelProfileFetcherService,
)
from mixpanel_data.types import ParallelProfileFetchResult, ProfileBatchProgress


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create a mock API client."""
    return MagicMock()


@pytest.fixture
def mock_storage() -> MagicMock:
    """Create a mock storage engine."""
    storage = MagicMock()
    storage.create_profiles_table.return_value = 0
    storage.append_profiles_table.return_value = 0
    return storage


@pytest.fixture
def parallel_fetcher(
    mock_api_client: MagicMock, mock_storage: MagicMock
) -> ParallelProfileFetcherService:
    """Create a ParallelProfileFetcherService with mocked dependencies."""
    return ParallelProfileFetcherService(
        api_client=mock_api_client,
        storage=mock_storage,
    )


class TestParallelProfileFetcherConstruction:
    """Tests for ParallelProfileFetcherService initialization."""

    def test_create_with_api_client_and_storage(
        self, mock_api_client: MagicMock, mock_storage: MagicMock
    ) -> None:
        """ParallelProfileFetcherService can be created with dependencies."""
        fetcher = ParallelProfileFetcherService(
            api_client=mock_api_client,
            storage=mock_storage,
        )

        assert fetcher._api_client is mock_api_client
        assert fetcher._storage is mock_storage

    def test_default_max_workers(
        self, mock_api_client: MagicMock, mock_storage: MagicMock
    ) -> None:
        """Default max_workers is 5 (Engage API concurrent limit)."""
        fetcher = ParallelProfileFetcherService(
            api_client=mock_api_client,
            storage=mock_storage,
        )

        assert fetcher._default_max_workers == 5


class TestEngageAPIRateLimits:
    """Tests for Engage API rate limit handling."""

    def test_max_workers_capped_to_5(
        self,
        parallel_fetcher: ParallelProfileFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Workers exceeding 5 are capped with warning."""
        mock_api_client.query_engage_page.return_value = {
            "results": [],
            "total": 0,
            "page_size": 1000,
            "page": 0,
            "session_id": "abc123",
        }

        # Request 10 workers - should be capped to 5
        parallel_fetcher.fetch_profiles(name="test", max_workers=10)

        # Verify warning was logged
        assert "exceeds Engage API limit of 5" in caplog.text

    def test_hourly_limit_warning_for_large_profile_sets(
        self,
        parallel_fetcher: ParallelProfileFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Warning logged when pages exceed 60 (hourly limit)."""
        mock_api_client.query_engage_page.return_value = {
            "results": [{"$distinct_id": "u1", "$properties": {}}],
            "total": 70000,  # 70 pages at 1000/page > 60 limit
            "page_size": 1000,
            "page": 0,
            "session_id": "abc123",
        }
        mock_storage.create_profiles_table.return_value = 1
        mock_storage.append_profiles_table.return_value = 1

        parallel_fetcher.fetch_profiles(name="test")

        assert "will exceed Engage API hourly limit" in caplog.text
```

**Step 2: Run tests to verify they fail**

Run: `just test -k TestParallelProfileFetcherConstruction -v`
Expected: FAIL with "No module named"

**Step 3: Create minimal ParallelProfileFetcherService**

```python
# src/mixpanel_data/_internal/services/parallel_profile_fetcher.py

"""Parallel Profile Fetcher Service for concurrent Mixpanel profile export.

Implements page-index parallelism with producer-consumer pattern
to handle DuckDB's single-writer constraint.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient
    from mixpanel_data._internal.storage import StorageEngine

_logger = logging.getLogger(__name__)


class ParallelProfileFetcherService:
    """Parallel fetcher for concurrent Mixpanel profile export.

    Uses page-index parallelism: fetches page 0 to get total count and
    session_id, then fetches pages 1..N in parallel.

    Attributes:
        _api_client: Mixpanel API client for fetching profiles.
        _storage: DuckDB storage engine for persisting data.
        _default_max_workers: Default number of concurrent fetch threads.

    Example:
        ```python
        fetcher = ParallelProfileFetcherService(api_client, storage)
        result = fetcher.fetch_profiles(name="profiles", max_workers=3)
        print(f"Fetched {result.total_rows} profiles")
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
        self._default_max_workers = 5  # Engage API limit: max 5 concurrent
```

**Step 4: Run tests to verify they pass**

Run: `just test -k TestParallelProfileFetcherConstruction -v`
Expected: PASS

**Step 5: Write failing tests for fetch_profiles**

```python
class TestParallelFetchProfiles:
    """Tests for parallel fetch_profiles method."""

    def test_fetch_profiles_returns_result(
        self, parallel_fetcher: ParallelProfileFetcherService, mock_api_client: MagicMock
    ) -> None:
        """fetch_profiles returns ParallelProfileFetchResult."""
        # Mock page 0 response with no profiles
        mock_api_client.query_engage_page.return_value = {
            "results": [],
            "total": 0,
            "page_size": 1000,
            "page": 0,
            "session_id": "abc123",
        }

        result = parallel_fetcher.fetch_profiles(name="test_profiles")

        assert isinstance(result, ParallelProfileFetchResult)

    def test_single_page_no_parallelism(
        self,
        parallel_fetcher: ParallelProfileFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Single page fetch doesn't use parallelism."""
        mock_api_client.query_engage_page.return_value = {
            "results": [
                {"$distinct_id": "u1", "$properties": {"name": "Alice"}},
            ],
            "total": 1,
            "page_size": 1000,
            "page": 0,
            "session_id": "abc123",
        }
        mock_storage.create_profiles_table.return_value = 1

        result = parallel_fetcher.fetch_profiles(name="test_profiles")

        assert result.successful_pages == 1
        assert result.total_rows == 1
        # Only page 0 should be fetched
        assert mock_api_client.query_engage_page.call_count == 1

    def test_multiple_pages_parallel(
        self,
        parallel_fetcher: ParallelProfileFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Multiple pages are fetched in parallel."""
        # Page 0: returns metadata indicating 3 pages total
        def mock_page_response(page: int, **kwargs: Any) -> dict[str, Any]:
            return {
                "results": [{"$distinct_id": f"u{page}", "$properties": {}}],
                "total": 2500,  # 3 pages at 1000 per page
                "page_size": 1000,
                "page": page,
                "session_id": "abc123",
            }

        mock_api_client.query_engage_page.side_effect = mock_page_response
        mock_storage.create_profiles_table.return_value = 1
        mock_storage.append_profiles_table.return_value = 1

        result = parallel_fetcher.fetch_profiles(name="test_profiles")

        # Should have fetched 3 pages (0, 1, 2)
        assert mock_api_client.query_engage_page.call_count == 3
        assert result.successful_pages == 3

    def test_progress_callback_invoked(
        self,
        parallel_fetcher: ParallelProfileFetcherService,
        mock_api_client: MagicMock,
        mock_storage: MagicMock,
    ) -> None:
        """Progress callback is invoked for each page."""
        mock_api_client.query_engage_page.return_value = {
            "results": [{"$distinct_id": "u1", "$properties": {}}],
            "total": 2000,
            "page_size": 1000,
            "page": 0,
            "session_id": "abc123",
        }
        mock_storage.create_profiles_table.return_value = 1
        mock_storage.append_profiles_table.return_value = 1

        progress_updates: list[ProfileBatchProgress] = []
        result = parallel_fetcher.fetch_profiles(
            name="test_profiles",
            on_batch_complete=lambda p: progress_updates.append(p),
        )

        assert len(progress_updates) == result.successful_pages + result.failed_pages
```

**Step 6: Run tests to verify they fail**

Run: `just test -k TestParallelFetchProfiles -v`
Expected: FAIL

**Step 7: Implement fetch_profiles method**

```python
# Add to parallel_profile_fetcher.py

import math
import queue
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from mixpanel_data._internal.rate_limiter import RateLimiter
from mixpanel_data._internal.services.fetcher import _transform_profile
from mixpanel_data.types import (
    ParallelProfileFetchResult,
    ProfileBatchProgress,
    TableMetadata,
)

# Sentinel value to signal writer thread to stop
_STOP_SENTINEL = object()


@dataclass
class _ProfileWriteTask:
    """Task item for the writer queue.

    Encapsulates all data needed to write a batch of profiles.

    Attributes:
        data: Transformed profile records to write.
        metadata: Table metadata for the batch.
        page_index: Index of this page (0-based).
        rows: Number of rows in this batch.
    """

    data: list[dict[str, Any]]
    metadata: TableMetadata
    page_index: int
    rows: int


class ParallelProfileFetcherService:
    # ... __init__ stays the same ...

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
        """Fetch profiles in parallel using page-index parallelism.

        Fetches page 0 first to get total count and session_id, then
        fetches pages 1..N in parallel. Uses producer-consumer pattern
        to serialize DuckDB writes.

        Args:
            name: Table name to create or append to.
            where: Optional filter expression.
            cohort_id: Optional cohort ID to filter by.
            output_properties: Optional list of property names to include.
            max_workers: Maximum concurrent fetch threads. Defaults to 5 (Engage API limit).
            on_batch_complete: Callback invoked when each page completes.
            append: If True, append to existing table.
            batch_size: Number of rows per INSERT/COMMIT cycle.

        Returns:
            ParallelProfileFetchResult with aggregated statistics.

        Raises:
            TableExistsError: If table exists and append=False.
            TableNotFoundError: If table doesn't exist and append=True.
        """
        start_time = datetime.now(UTC)
        workers = max_workers or self._default_max_workers

        # Engage API limit: max 5 concurrent queries
        _MAX_ENGAGE_CONCURRENT = 5
        if workers > _MAX_ENGAGE_CONCURRENT:
            _logger.warning(
                "max_workers=%d exceeds Engage API limit of %d concurrent queries. "
                "Capping to %d to avoid rate limit errors.",
                workers,
                _MAX_ENGAGE_CONCURRENT,
                _MAX_ENGAGE_CONCURRENT,
            )
            workers = _MAX_ENGAGE_CONCURRENT

        # 1. Fetch page 0 to get metadata
        first_response = self._api_client.query_engage_page(
            page=0,
            where=where,
            cohort_id=cohort_id,
            output_properties=output_properties,
        )

        total = first_response.get("total", 0)
        page_size = first_response.get("page_size", 1000)
        session_id = first_response.get("session_id")

        num_pages = math.ceil(total / page_size) if total > 0 else 1

        # Warn about hourly rate limit (60 queries/hour)
        _HOURLY_RATE_LIMIT = 60
        if num_pages > _HOURLY_RATE_LIMIT:
            _logger.warning(
                "Fetching %d pages will exceed Engage API hourly limit of %d queries. "
                "Consider using sequential fetch or expect rate limiting delays.",
                num_pages,
                _HOURLY_RATE_LIMIT,
            )

        _logger.info(
            "Starting parallel profile fetch: %d total, %d pages, %d workers",
            total,
            num_pages,
            workers,
        )

        # Rate limiter for concurrent API calls
        rate_limiter = RateLimiter(max_concurrent=workers)

        # Queue for serializing writes to DuckDB
        write_queue: queue.Queue[_ProfileWriteTask | object] = queue.Queue(
            maxsize=workers * 2
        )

        # Results tracking
        results_lock = threading.Lock()
        total_rows = 0
        successful_pages = 0
        failed_pages = 0
        failed_page_indices: list[int] = []
        table_created = False

        def fetch_page(page_idx: int) -> None:
            """Fetch a single page and queue for writing."""
            nonlocal failed_pages

            try:
                with rate_limiter.acquire():
                    if page_idx == 0:
                        # Already fetched page 0
                        profiles = first_response.get("results", [])
                    else:
                        response = self._api_client.query_engage_page(
                            page=page_idx,
                            session_id=session_id,
                            where=where,
                            cohort_id=cohort_id,
                            output_properties=output_properties,
                        )
                        profiles = response.get("results", [])

                    # Transform profiles
                    transformed = [_transform_profile(p) for p in profiles]
                    rows = len(transformed)

                    # Create metadata
                    metadata = TableMetadata(
                        type="profiles",
                        fetched_at=datetime.now(UTC),
                        filter_where=where,
                        filter_cohort_id=cohort_id,
                        filter_output_properties=output_properties,
                    )

                    # Queue for writing
                    write_queue.put(
                        _ProfileWriteTask(
                            data=transformed,
                            metadata=metadata,
                            page_index=page_idx,
                            rows=rows,
                        )
                    )

            except Exception as e:
                _logger.warning("Page %d fetch failed: %s", page_idx, str(e))

                with results_lock:
                    failed_pages += 1
                    failed_page_indices.append(page_idx)

                if on_batch_complete:
                    progress = ProfileBatchProgress(
                        page_index=page_idx,
                        total_pages=num_pages,
                        rows=0,
                        success=False,
                        error=str(e),
                    )
                    on_batch_complete(progress)

        def writer_thread() -> None:
            """Single writer thread for DuckDB."""
            nonlocal table_created, total_rows, successful_pages, failed_pages

            while True:
                item = write_queue.get()
                if item is _STOP_SENTINEL:
                    break

                task = item if isinstance(item, _ProfileWriteTask) else None
                if task is None:
                    continue

                if not task.data:
                    # Empty page - still count as successful
                    with results_lock:
                        successful_pages += 1
                    if on_batch_complete:
                        progress = ProfileBatchProgress(
                            page_index=task.page_index,
                            total_pages=num_pages,
                            rows=0,
                            success=True,
                        )
                        on_batch_complete(progress)
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

                    if on_batch_complete:
                        progress = ProfileBatchProgress(
                            page_index=task.page_index,
                            total_pages=num_pages,
                            rows=actual_rows,
                            success=True,
                        )
                        on_batch_complete(progress)

                except Exception as e:
                    _logger.error("Page %d write failed: %s", task.page_index, str(e))

                    with results_lock:
                        failed_pages += 1
                        failed_page_indices.append(task.page_index)

                    if on_batch_complete:
                        progress = ProfileBatchProgress(
                            page_index=task.page_index,
                            total_pages=num_pages,
                            rows=0,
                            success=False,
                            error=f"Write failed: {e}",
                        )
                        on_batch_complete(progress)

        # Start writer thread
        writer = threading.Thread(target=writer_thread, daemon=True)
        writer.start()

        # Submit fetch tasks
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = []
            for page_idx in range(num_pages):
                future = executor.submit(fetch_page, page_idx)
                futures.append(future)

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    _logger.error("Unexpected error in fetch task: %s", str(e))

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
            num_pages,
            duration_seconds,
        )

        return ParallelProfileFetchResult(
            table=name,
            total_rows=total_rows,
            successful_pages=successful_pages,
            failed_pages=failed_pages,
            failed_page_indices=tuple(failed_page_indices),
            duration_seconds=duration_seconds,
            fetched_at=completed_at,
        )
```

**Step 8: Run tests to verify they pass**

Run: `just test -k TestParallelFetchProfiles -v`
Expected: PASS

**Step 9: Commit**

```bash
git add src/mixpanel_data/_internal/services/parallel_profile_fetcher.py tests/unit/test_parallel_profile_fetcher.py
git commit -m "$(cat <<'EOF'
feat(fetch): add ParallelProfileFetcherService with page-index parallelism

Implement parallel profile fetching:
- Fetch page 0 to get total count and session_id
- Fetch pages 1..N in parallel using ThreadPoolExecutor
- Producer-consumer queue pattern for DuckDB single-writer constraint
- Progress callbacks for each page
- Partial failure tracking with failed_page_indices

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Integrate Parallel Fetcher into FetcherService

**Files:**
- Modify: `src/mixpanel_data/_internal/services/fetcher.py`
- Test: `tests/unit/test_fetcher_service.py`

**Step 1: Write failing test for parallel parameter**

```python
# tests/unit/test_fetcher_service.py - add tests

class TestFetchProfilesParallel:
    """Tests for parallel profile fetching delegation."""

    def test_fetch_profiles_parallel_delegates_to_parallel_fetcher(
        self, fetcher_service: FetcherService, mock_api_client: MagicMock
    ) -> None:
        """fetch_profiles with parallel=True delegates to ParallelProfileFetcherService."""
        # Mock page 0 response
        mock_api_client.query_engage_page.return_value = {
            "results": [],
            "total": 0,
            "page_size": 1000,
            "page": 0,
            "session_id": "abc123",
        }

        result = fetcher_service.fetch_profiles(
            name="test_profiles",
            parallel=True,
        )

        from mixpanel_data.types import ParallelProfileFetchResult
        assert isinstance(result, ParallelProfileFetchResult)

    def test_fetch_profiles_sequential_by_default(
        self, fetcher_service: FetcherService, mock_api_client: MagicMock
    ) -> None:
        """fetch_profiles uses sequential fetch by default."""
        mock_api_client.export_profiles.return_value = iter([])

        result = fetcher_service.fetch_profiles(name="test_profiles")

        from mixpanel_data.types import FetchResult
        assert isinstance(result, FetchResult)
```

**Step 2: Run tests to verify they fail**

Run: `just test -k TestFetchProfilesParallel -v`
Expected: FAIL

**Step 3: Add parallel parameter to FetcherService.fetch_profiles**

```python
# src/mixpanel_data/_internal/services/fetcher.py

def fetch_profiles(
    self,
    name: str,
    *,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
    progress_callback: Callable[[int], None] | None = None,
    append: bool = False,
    batch_size: int = 1000,
    parallel: bool = False,
    max_workers: int | None = None,
    on_batch_complete: Callable[[ProfileBatchProgress], None] | None = None,
) -> FetchResult | ParallelProfileFetchResult:
    """Fetch user profiles from Mixpanel and store in local database.

    Args:
        name: Table name to create or append to.
        where: Optional filter expression.
        cohort_id: Optional cohort ID to filter by.
        output_properties: Optional list of property names to include.
        progress_callback: Optional callback invoked with row count during fetch.
        append: If True, append to existing table.
        batch_size: Number of rows per INSERT/COMMIT cycle.
        parallel: If True, use parallel fetching with multiple threads.
        max_workers: Maximum concurrent fetch threads when parallel=True.
        on_batch_complete: Callback invoked when each page completes (parallel only).

    Returns:
        FetchResult when parallel=False, ParallelProfileFetchResult when parallel=True.

    Raises:
        TableExistsError: If table exists and append=False.
        TableNotFoundError: If table doesn't exist and append=True.
    """
    # Delegate to parallel fetcher if requested
    if parallel:
        from mixpanel_data._internal.services.parallel_profile_fetcher import (
            ParallelProfileFetcherService,
        )

        parallel_fetcher = ParallelProfileFetcherService(
            api_client=self._api_client,
            storage=self._storage,
        )
        return parallel_fetcher.fetch_profiles(
            name=name,
            where=where,
            cohort_id=cohort_id,
            output_properties=output_properties,
            max_workers=max_workers,
            on_batch_complete=on_batch_complete,
            append=append,
            batch_size=batch_size,
        )

    # Sequential fetch (existing code)
    # ... rest of existing implementation ...
```

**Step 4: Run tests to verify they pass**

Run: `just test -k TestFetchProfilesParallel -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/mixpanel_data/_internal/services/fetcher.py tests/unit/test_fetcher_service.py
git commit -m "$(cat <<'EOF'
feat(fetch): add parallel parameter to FetcherService.fetch_profiles

Add parallel=True option to fetch_profiles that delegates to
ParallelProfileFetcherService for page-index parallel fetching.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Integrate into Workspace

**Files:**
- Modify: `src/mixpanel_data/workspace.py`
- Test: `tests/unit/test_workspace.py`

**Step 1: Write failing test for parallel profile fetch**

```python
# tests/unit/test_workspace.py - add tests

class TestFetchProfilesParallel:
    """Tests for parallel profile fetching via Workspace."""

    def test_fetch_profiles_parallel_returns_parallel_result(
        self, workspace: Workspace
    ) -> None:
        """fetch_profiles with parallel=True returns ParallelProfileFetchResult."""
        # Mock the API client
        workspace._api_client.query_engage_page.return_value = {
            "results": [],
            "total": 0,
            "page_size": 1000,
            "page": 0,
            "session_id": "abc123",
        }

        result = workspace.fetch_profiles(
            name="test_profiles",
            parallel=True,
            progress=False,
        )

        from mixpanel_data.types import ParallelProfileFetchResult
        assert isinstance(result, ParallelProfileFetchResult)
```

**Step 2: Run tests to verify they fail**

Run: `just test -k "test_fetch_profiles_parallel_returns" -v`
Expected: FAIL

**Step 3: Add parallel parameter to Workspace.fetch_profiles**

```python
# src/mixpanel_data/workspace.py - modify fetch_profiles

def fetch_profiles(
    self,
    name: str = "profiles",
    *,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
    progress: bool = True,
    append: bool = False,
    batch_size: int = 1000,
    parallel: bool = False,
    max_workers: int | None = None,
    on_batch_complete: Callable[[ProfileBatchProgress], None] | None = None,
) -> FetchResult | ParallelProfileFetchResult:
    """Fetch user profiles from Mixpanel and store in local database.

    Args:
        name: Table name to create or append to (default: "profiles").
        where: Optional WHERE clause for filtering.
        cohort_id: Optional cohort ID to filter by.
        output_properties: Optional list of property names to include.
        progress: Show progress bar (default: True).
        append: If True, append to existing table.
        batch_size: Number of rows per INSERT/COMMIT cycle.
        parallel: If True, use parallel fetching with multiple threads.
            Fetches page 0 first, then remaining pages in parallel.
        max_workers: Maximum concurrent fetch threads when parallel=True.
            Default: 10. Ignored when parallel=False.
        on_batch_complete: Callback invoked when each page completes
            during parallel fetch. Receives ProfileBatchProgress with status.
            Ignored when parallel=False.

    Returns:
        FetchResult when parallel=False, ParallelProfileFetchResult when parallel=True.
    """
    # Validate batch_size
    _validate_batch_size(batch_size)

    # Delegate to parallel fetcher if requested
    if parallel:
        # Parallel mode uses on_batch_complete callback for progress
        # Create progress callback wrapper if progress=True and no custom callback
        actual_callback = on_batch_complete
        pbar = None

        if progress and sys.stderr.isatty() and on_batch_complete is None:
            try:
                from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

                pbar = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("{task.completed}/{task.total} pages"),
                )
                task = pbar.add_task("Fetching profiles...", total=None)
                pbar.start()

                def parallel_callback(p: ProfileBatchProgress) -> None:
                    if pbar is not None:
                        pbar.update(task, total=p.total_pages, completed=p.page_index + 1)

                actual_callback = parallel_callback
            except ImportError:
                pass

        try:
            return self._fetcher.fetch_profiles(
                name=name,
                where=where,
                cohort_id=cohort_id,
                output_properties=output_properties,
                append=append,
                batch_size=batch_size,
                parallel=True,
                max_workers=max_workers,
                on_batch_complete=actual_callback,
            )
        finally:
            if pbar is not None:
                pbar.stop()

    # Sequential fetch (existing code)
    # ... rest of existing implementation ...
```

**Step 4: Import ProfileBatchProgress in workspace.py**

Add to imports:
```python
from mixpanel_data.types import (
    # ... existing imports ...
    ProfileBatchProgress,
    ParallelProfileFetchResult,
)
```

**Step 5: Run tests to verify they pass**

Run: `just test -k "test_fetch_profiles_parallel" -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/mixpanel_data/workspace.py tests/unit/test_workspace.py
git commit -m "$(cat <<'EOF'
feat(workspace): add parallel parameter to fetch_profiles

Add parallel=True option with progress bar support for parallel
profile fetching. Uses page-index parallelism for up to 10x speedup.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Add CLI Flags for Parallel Profile Fetch

**Files:**
- Modify: `src/mixpanel_data/cli/commands/fetch.py`
- Test: `tests/integration/cli/test_fetch_commands.py`

**Step 1: Write failing CLI test**

```python
# tests/integration/cli/test_fetch_commands.py - add tests

class TestFetchProfilesParallelCLI:
    """Tests for mp fetch profiles --parallel CLI."""

    def test_parallel_flag_accepted(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """--parallel flag is accepted for profiles."""
        mock_workspace.fetch_profiles.return_value = ParallelProfileFetchResult(
            table="profiles",
            total_rows=0,
            successful_pages=1,
            failed_pages=0,
            failed_page_indices=(),
            duration_seconds=1.0,
            fetched_at=datetime.now(UTC),
        )

        result = cli_runner.invoke(
            app, ["fetch", "profiles", "--parallel", "--name", "test"]
        )

        assert result.exit_code == 0
        mock_workspace.fetch_profiles.assert_called_once()
        call_kwargs = mock_workspace.fetch_profiles.call_args.kwargs
        assert call_kwargs["parallel"] is True

    def test_workers_flag_passed(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """--workers flag is passed to workspace."""
        mock_workspace.fetch_profiles.return_value = ParallelProfileFetchResult(
            table="profiles",
            total_rows=0,
            successful_pages=1,
            failed_pages=0,
            failed_page_indices=(),
            duration_seconds=1.0,
            fetched_at=datetime.now(UTC),
        )

        result = cli_runner.invoke(
            app, ["fetch", "profiles", "--parallel", "--workers", "5", "--name", "test"]
        )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_profiles.call_args.kwargs
        assert call_kwargs["max_workers"] == 5
```

**Step 2: Run tests to verify they fail**

Run: `just test -k TestFetchProfilesParallelCLI -v`
Expected: FAIL

**Step 3: Add --parallel and --workers flags to fetch profiles command**

```python
# src/mixpanel_data/cli/commands/fetch.py - modify profiles command

@fetch_app.command("profiles")
def fetch_profiles(
    name: Annotated[
        str,
        typer.Option("--name", "-n", help="Table name to create"),
    ] = "profiles",
    where: Annotated[
        str | None,
        typer.Option("--where", "-w", help="Filter expression"),
    ] = None,
    cohort_id: Annotated[
        str | None,
        typer.Option("--cohort", help="Cohort ID to filter by"),
    ] = None,
    append: Annotated[
        bool,
        typer.Option("--append", "-a", help="Append to existing table"),
    ] = False,
    batch_size: Annotated[
        int,
        typer.Option("--batch-size", help="Rows per commit (100-100000)"),
    ] = 1000,
    parallel: Annotated[
        bool,
        typer.Option("--parallel", "-p", help="Use parallel fetching"),
    ] = False,
    workers: Annotated[
        int | None,
        typer.Option("--workers", help="Max concurrent fetch threads (default: 5, Engage API limit)"),
    ] = None,
    account: Annotated[
        str | None,
        typer.Option("--account", help="Named account from config"),
    ] = None,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.json,
) -> None:
    """Fetch user profiles and store locally.

    Examples:
        mp fetch profiles
        mp fetch profiles --where 'properties["country"] == "US"'
        mp fetch profiles --cohort 12345
        mp fetch profiles --parallel --workers 20
    """
    try:
        ws = get_workspace(account=account)
        result = ws.fetch_profiles(
            name=name,
            where=where,
            cohort_id=cohort_id,
            append=append,
            batch_size=batch_size,
            parallel=parallel,
            max_workers=workers,
        )

        # Handle parallel vs sequential result types
        from mixpanel_data.types import ParallelProfileFetchResult
        if isinstance(result, ParallelProfileFetchResult):
            output_result(result.to_dict(), format)
            if result.has_failures:
                console.print(
                    f"[yellow]Warning: {result.failed_pages} pages failed[/yellow]"
                )
                raise typer.Exit(1)
        else:
            output_result(result.to_dict(), format)

    except Exception as e:
        handle_error(e)
        raise typer.Exit(1) from e
```

**Step 4: Run tests to verify they pass**

Run: `just test -k TestFetchProfilesParallelCLI -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/mixpanel_data/cli/commands/fetch.py tests/integration/cli/test_fetch_commands.py
git commit -m "$(cat <<'EOF'
feat(cli): add --parallel and --workers flags to fetch profiles

Add CLI support for parallel profile fetching:
- --parallel/-p: Enable parallel page-index fetching
- --workers: Set max concurrent threads (default: 5, Engage API limit)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Add Integration Tests

**Files:**
- Create: `tests/integration/test_parallel_profile_fetcher.py`

**Step 1: Write integration tests**

```python
# tests/integration/test_parallel_profile_fetcher.py

"""Integration tests for ParallelProfileFetcherService.

Tests parallel profile fetching with real DuckDB storage.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mixpanel_data._internal.services.parallel_profile_fetcher import (
    ParallelProfileFetcherService,
)
from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data.types import ProfileBatchProgress


@pytest.fixture
def temp_db_path() -> Path:
    """Create a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        return Path(f.name)


@pytest.fixture
def storage(temp_db_path: Path) -> StorageEngine:
    """Create a real StorageEngine with temp database."""
    engine = StorageEngine(temp_db_path)
    yield engine
    engine.close()
    temp_db_path.unlink(missing_ok=True)


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create a mock API client with realistic responses."""
    client = MagicMock()
    return client


class TestParallelProfileFetcherIntegration:
    """Integration tests for parallel profile fetching."""

    def test_fetch_single_page_creates_table(
        self, mock_api_client: MagicMock, storage: StorageEngine
    ) -> None:
        """Single page fetch creates table with profiles."""
        mock_api_client.query_engage_page.return_value = {
            "results": [
                {"$distinct_id": "u1", "$properties": {"name": "Alice", "$last_seen": "2024-01-01"}},
                {"$distinct_id": "u2", "$properties": {"name": "Bob"}},
            ],
            "total": 2,
            "page_size": 1000,
            "page": 0,
            "session_id": "abc123",
        }

        fetcher = ParallelProfileFetcherService(mock_api_client, storage)
        result = fetcher.fetch_profiles(name="test_profiles")

        assert result.total_rows == 2
        assert result.successful_pages == 1
        assert result.failed_pages == 0

        # Verify table exists and has correct data
        tables = storage.list_tables()
        assert "test_profiles" in [t.name for t in tables]

    def test_fetch_multiple_pages_parallel(
        self, mock_api_client: MagicMock, storage: StorageEngine
    ) -> None:
        """Multiple pages are fetched and stored correctly."""
        def mock_response(page: int, **kwargs) -> dict:
            return {
                "results": [
                    {"$distinct_id": f"u{page}_1", "$properties": {"page": page}},
                    {"$distinct_id": f"u{page}_2", "$properties": {"page": page}},
                ],
                "total": 6,  # 3 pages
                "page_size": 2,
                "page": page,
                "session_id": "abc123",
            }

        mock_api_client.query_engage_page.side_effect = mock_response

        fetcher = ParallelProfileFetcherService(mock_api_client, storage)
        result = fetcher.fetch_profiles(name="test_profiles", max_workers=3)

        assert result.successful_pages == 3
        assert result.total_rows == 6

    def test_progress_callback_receives_all_pages(
        self, mock_api_client: MagicMock, storage: StorageEngine
    ) -> None:
        """Progress callback is invoked for each page."""
        mock_api_client.query_engage_page.return_value = {
            "results": [{"$distinct_id": "u1", "$properties": {}}],
            "total": 3,
            "page_size": 1,
            "page": 0,
            "session_id": "abc123",
        }

        progress_updates: list[ProfileBatchProgress] = []
        fetcher = ParallelProfileFetcherService(mock_api_client, storage)
        result = fetcher.fetch_profiles(
            name="test_profiles",
            on_batch_complete=lambda p: progress_updates.append(p),
        )

        assert len(progress_updates) == result.successful_pages + result.failed_pages
        assert all(p.total_pages == 3 for p in progress_updates)
```

**Step 2: Run integration tests**

Run: `just test tests/integration/test_parallel_profile_fetcher.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/integration/test_parallel_profile_fetcher.py
git commit -m "$(cat <<'EOF'
test(integration): add parallel profile fetcher integration tests

Add integration tests verifying:
- Single page fetch creates table correctly
- Multiple pages fetched and stored in parallel
- Progress callbacks receive all page updates

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Update Documentation

**Files:**
- Modify: `context/implementation-phase-post-mortems/phase-011-parallel-export-postmortem.md`

**Step 1: Add profile parallelization completion note**

Add a section at the end of the post-mortem documenting the profile implementation.

**Step 2: Run full test suite**

Run: `just check`
Expected: All checks pass

**Step 3: Final commit**

```bash
git add context/implementation-phase-post-mortems/phase-011-parallel-export-postmortem.md
git commit -m "$(cat <<'EOF'
docs: document parallel profile fetching implementation

Update post-mortem with profile parallelization completion notes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add ProfileBatchProgress and ParallelProfileFetchResult types | types.py, test_types.py |
| 2 | Add query_engage_page API method | api_client.py, test_api_client.py |
| 3 | Create ParallelProfileFetcherService | parallel_profile_fetcher.py, test_parallel_profile_fetcher.py |
| 4 | Integrate into FetcherService | fetcher.py, test_fetcher_service.py |
| 5 | Integrate into Workspace | workspace.py, test_workspace.py |
| 6 | Add CLI flags | fetch.py, test_fetch_commands.py |
| 7 | Integration tests | test_parallel_profile_fetcher.py (integration) |
| 8 | Documentation | post-mortem update |

**Estimated new tests:** ~40 tests
**Expected coverage:** >90%
