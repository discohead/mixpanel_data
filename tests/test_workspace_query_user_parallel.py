"""Unit tests for parallel profile fetching in Workspace.query_user() (T021).

Tests cover _execute_user_query_parallel() which extends query_user() with
concurrent page fetching via ThreadPoolExecutor. The method dispatches
pages 1..N in parallel after fetching page 0 sequentially for metadata.

Coverage:
- Single-page result skips parallel overhead (just returns page 0)
- Multi-page parallel fetch collects all profiles
- Limit-aware dispatch: fetches only ceil(limit/page_size) pages
- Failed page handling: returns partial results with meta["failed_pages"]
- Worker cap enforcement: values > 5 silently reduced to 5
- Rate limit warning when pages > 48
- parallel=True with mode="aggregate" produces validation error U18
- Early exit when limit reached mid-fetch
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.exceptions import (
    AuthenticationError,
    BookmarkValidationError,
    QueryError,
    RateLimitError,
    ServerError,
)
from mixpanel_headless.types import ProfilePageResult, UserQueryResult

# ---- 042 redesign: canonical fake Session for Workspace(session=…) ----
_TEST_SESSION = Session(
    account=ServiceAccount(
        name="test_account",
        region="us",
        username="test_user",
        secret=SecretStr("test_secret"),
        default_project="12345",
    ),
    project=Project(id="12345"),
)

if TYPE_CHECKING:
    from collections.abc import Callable


# =============================================================================
# Helpers
# =============================================================================


def _make_raw_profile(
    distinct_id: str,
    last_seen: str = "2025-01-15T10:00:00",
    **extra_props: Any,
) -> dict[str, Any]:
    """Build a raw Mixpanel API profile dict.

    Args:
        distinct_id: The user's distinct ID.
        last_seen: ISO timestamp for $last_seen.
        **extra_props: Additional profile properties.

    Returns:
        Profile dict in raw Mixpanel Engage API format.
    """
    props: dict[str, Any] = {"$last_seen": last_seen}
    props.update(extra_props)
    return {"$distinct_id": distinct_id, "$properties": props}


def _make_page_result(
    profiles: list[dict[str, Any]],
    *,
    page: int = 0,
    total: int = 100,
    page_size: int = 1000,
    session_id: str | None = "sess_abc123",
    has_more: bool = False,
) -> ProfilePageResult:
    """Build a ProfilePageResult for mocking export_profiles_page().

    Args:
        profiles: List of raw profile dicts for this page.
        page: Zero-based page index.
        total: Total matching profiles across all pages.
        page_size: Profiles per page.
        session_id: Pagination session ID.
        has_more: Whether more pages exist.

    Returns:
        ProfilePageResult with the given data.
    """
    return ProfilePageResult(
        profiles=profiles,
        page=page,
        total=total,
        page_size=page_size,
        session_id=session_id,
        has_more=has_more,
    )


def _make_profiles_batch(
    start_index: int,
    count: int,
) -> list[dict[str, Any]]:
    """Build a batch of raw profile dicts with sequential IDs.

    Args:
        start_index: Starting index for user IDs (user_000, user_001, ...).
        count: Number of profiles to generate.

    Returns:
        List of raw profile dicts.
    """
    return [
        _make_raw_profile(f"user_{start_index + i:03d}", plan="free")
        for i in range(count)
    ]


def _page_side_effect_factory(
    total: int,
    page_size: int,
    session_id: str = "sess_parallel",
    fail_pages: set[int] | None = None,
) -> Any:
    """Create a side_effect callable for export_profiles_page mocking.

    Returns a function that, given page and session_id kwargs, returns
    the appropriate ProfilePageResult. If a page is in fail_pages, an
    Exception is raised instead.

    Args:
        total: Total number of profiles across all pages.
        page_size: Number of profiles per page.
        session_id: Session ID to return in page results.
        fail_pages: Set of page numbers that should raise an Exception.

    Returns:
        Callable suitable for use as mock side_effect.
    """
    num_pages = math.ceil(total / page_size) if total > 0 else 1

    def _side_effect(
        *_args: Any,
        page: int = 0,
        **_kwargs: Any,
    ) -> ProfilePageResult:
        """Return a ProfilePageResult for the requested page.

        Args:
            *args: Positional arguments (ignored for flexibility).
            page: Zero-based page index.
            **kwargs: Additional keyword arguments (ignored).

        Returns:
            ProfilePageResult for the requested page.

        Raises:
            Exception: If page is in fail_pages set.
        """
        if fail_pages and page in fail_pages:
            raise Exception(f"Simulated failure on page {page}")

        start_idx = page * page_size
        remaining = total - start_idx
        count = min(page_size, remaining) if remaining > 0 else 0
        profiles = _make_profiles_batch(start_idx, count)
        has_more = page < num_pages - 1

        return _make_page_result(
            profiles=profiles,
            page=page,
            total=total,
            page_size=page_size,
            session_id=session_id,
            has_more=has_more,
        )

    return _side_effect


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create mock API client for testing."""
    from mixpanel_headless._internal.api_client import MixpanelAPIClient

    client = MagicMock(spec=MixpanelAPIClient)
    client.close = MagicMock()
    return client


@pytest.fixture
def workspace_factory(
    mock_api_client: MagicMock,
) -> Callable[..., Workspace]:
    """Factory for creating Workspace instances with mocked dependencies."""

    def factory(**kwargs: Any) -> Workspace:
        """Create a Workspace with mocked config and API client.

        Args:
            **kwargs: Overrides for default Workspace constructor arguments.

        Returns:
            Workspace instance with mocked dependencies.
        """
        defaults: dict[str, Any] = {
            "session": _TEST_SESSION,
            "_api_client": mock_api_client,
        }
        defaults.update(kwargs)
        return Workspace(**defaults)

    return factory


# =============================================================================
# Test: Single-page result skips parallel overhead
# =============================================================================


class TestParallelSinglePageSkip:
    """Tests that single-page results skip parallel dispatch entirely."""

    def test_single_page_returns_all_profiles_without_threading(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """When all profiles fit in page 0, no parallel dispatch occurs."""
        profiles = _make_profiles_batch(0, 3)
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=profiles,
            page=0,
            total=3,
            page_size=1000,
            session_id="sess_single",
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            assert isinstance(result, UserQueryResult)
            assert len(result.profiles) == 3
            # Only page 0 should be fetched — no parallel pages dispatched
            assert mock_api_client.export_profiles_page.call_count == 1
        finally:
            ws.close()

    def test_single_page_meta_shows_one_page_fetched(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Meta reports pages_fetched=1 when result fits in single page."""
        profiles = _make_profiles_batch(0, 5)
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=profiles,
            page=0,
            total=5,
            page_size=1000,
            session_id="sess_meta",
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            assert result.meta["pages_fetched"] == 1
        finally:
            ws.close()

    def test_single_page_total_preserved(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Total count reflects API total even for single-page results."""
        profiles = _make_profiles_batch(0, 2)
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=profiles,
            page=0,
            total=2,
            page_size=1000,
            session_id="sess_total",
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            assert result.total == 2
        finally:
            ws.close()


# =============================================================================
# Test: Multi-page parallel fetch collects all profiles
# =============================================================================


class TestParallelMultiPageFetch:
    """Tests that multi-page parallel fetching collects all profiles."""

    def test_parallel_fetch_collects_all_profiles(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Parallel fetch across multiple pages returns all profiles."""
        total = 250
        page_size = 100
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            assert len(result.profiles) == total
            assert result.total == total
        finally:
            ws.close()

    def test_parallel_fetch_calls_correct_page_count(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Parallel fetch makes exactly ceil(limit/page_size) API calls."""
        total = 250
        page_size = 100
        expected_pages = math.ceil(total / page_size)  # 3
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", parallel=True, limit=total)

            assert mock_api_client.export_profiles_page.call_count == expected_pages
        finally:
            ws.close()

    def test_parallel_meta_indicates_parallel_mode(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Meta dict includes parallel=True for parallel execution."""
        total = 200
        page_size = 100
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            assert result.meta["parallel"] is True
        finally:
            ws.close()

    def test_parallel_meta_reports_pages_fetched(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Meta reports total pages fetched including page 0."""
        total = 500
        page_size = 100
        expected_pages = math.ceil(total / page_size)  # 5
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=total)

            assert result.meta["pages_fetched"] == expected_pages
        finally:
            ws.close()

    def test_parallel_preserves_session_id_in_meta(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Meta includes the session_id from page 0 response."""
        total = 200
        page_size = 100
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size, session_id="sess_keepme"
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            assert result.meta["session_id"] == "sess_keepme"
        finally:
            ws.close()

    def test_parallel_subsequent_pages_use_session_id_from_page_0(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """All parallel page requests use the session_id obtained from page 0."""
        total = 300
        page_size = 100
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size, session_id="sess_shared"
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", parallel=True, limit=100_000)

            # All calls after page 0 should pass session_id
            calls = mock_api_client.export_profiles_page.call_args_list
            for c in calls[1:]:
                session_kwarg = c.kwargs.get("session_id")
                assert session_kwarg == "sess_shared", (
                    f"Expected session_id='sess_shared' but got {session_kwarg!r} "
                    f"in call {c}"
                )
        finally:
            ws.close()

    def test_parallel_profiles_are_normalized(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Profiles from parallel pages are normalized via transform_profile."""
        total = 200
        page_size = 100
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            # All profiles should be normalized (distinct_id, not $distinct_id)
            for profile in result.profiles:
                assert "distinct_id" in profile
                assert "$distinct_id" not in profile
                assert "last_seen" in profile
                assert "properties" in profile
        finally:
            ws.close()

    def test_parallel_result_is_user_query_result(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Parallel execution returns a proper UserQueryResult instance."""
        total = 200
        page_size = 100
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            assert isinstance(result, UserQueryResult)
            assert result.mode == "profiles"
            assert result.aggregate_data is None
        finally:
            ws.close()


# =============================================================================
# Test: Limit-aware dispatch fetches only ceil(limit/page_size) pages
# =============================================================================


class TestParallelLimitAwareDispatch:
    """Tests that parallel dispatch is limit-aware, not total-aware."""

    def test_limit_fewer_than_total_dispatches_fewer_pages(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """With limit=150 and page_size=100, only 2 pages are fetched (not 5)."""
        total = 500
        page_size = 100
        limit = 150
        expected_pages = math.ceil(limit / page_size)  # 2
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", parallel=True, limit=limit)

            assert mock_api_client.export_profiles_page.call_count == expected_pages
        finally:
            ws.close()

    def test_limit_truncates_result_to_requested_count(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Result is truncated to exactly the limit count."""
        total = 500
        page_size = 100
        limit = 150
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=limit)

            assert len(result.profiles) == limit
        finally:
            ws.close()

    def test_limit_total_equals_len_profiles(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """result.total equals len(profiles), not the API's full count."""
        total = 5000
        page_size = 1000
        limit = 100
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=limit)

            assert result.total == len(result.profiles)
            assert result.total == limit
        finally:
            ws.close()

    def test_limit_exactly_page_size_fetches_one_page(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """limit equal to page_size fetches exactly 1 page (page 0 only)."""
        total = 5000
        page_size = 1000
        limit = 1000
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=limit)

            # ceil(1000/1000) = 1, so only page 0
            assert mock_api_client.export_profiles_page.call_count == 1
            assert len(result.profiles) == limit
        finally:
            ws.close()

    def test_limit_one_more_than_page_size_fetches_two_pages(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """limit=page_size+1 requires page 0 + one parallel page."""
        total = 5000
        page_size = 1000
        limit = 1001
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=limit)

            # ceil(1001/1000) = 2
            assert mock_api_client.export_profiles_page.call_count == 2
            assert len(result.profiles) == limit
        finally:
            ws.close()

    def test_limit_none_fetches_all_pages(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """limit=total fetches all pages based on total."""
        total = 350
        page_size = 100
        expected_pages = math.ceil(total / page_size)  # 4
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=total)

            assert mock_api_client.export_profiles_page.call_count == expected_pages
            assert len(result.profiles) == total
        finally:
            ws.close()


# =============================================================================
# Test: Failed page handling returns partial results with meta["failed_pages"]
# =============================================================================


class TestParallelFailedPageHandling:
    """Tests graceful handling of per-page failures during parallel fetch."""

    def test_failed_page_returns_partial_results(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """When a page fails, remaining pages' profiles are still returned."""
        total = 300
        page_size = 100
        fail_pages = {1}  # Page 1 fails
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size, fail_pages=fail_pages
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            # Should have profiles from pages 0 and 2 (200 profiles)
            # Page 1 failed, so its 100 profiles are missing
            assert len(result.profiles) == 200
        finally:
            ws.close()

    def test_failed_page_recorded_in_meta(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Failed page numbers are recorded in meta['failed_pages']."""
        total = 300
        page_size = 100
        fail_pages = {2}
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size, fail_pages=fail_pages
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            assert "failed_pages" in result.meta
            assert 2 in result.meta["failed_pages"]
        finally:
            ws.close()

    def test_multiple_failed_pages_all_recorded(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Multiple failed pages are all listed in meta['failed_pages']."""
        total = 500
        page_size = 100
        fail_pages = {1, 3}
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size, fail_pages=fail_pages
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            assert "failed_pages" in result.meta
            for fp in fail_pages:
                assert fp in result.meta["failed_pages"]
        finally:
            ws.close()

    def test_failed_page_logs_warning(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Failed pages emit a warning-level log message."""
        total = 200
        page_size = 100
        fail_pages = {1}
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size, fail_pages=fail_pages
        )

        ws = workspace_factory()
        try:
            with caplog.at_level(logging.WARNING):
                ws.query_user(mode="profiles", parallel=True, limit=100_000)

            warning_messages = [
                r.message for r in caplog.records if r.levelno >= logging.WARNING
            ]
            assert any(
                "page" in msg.lower() or "fail" in msg.lower()
                for msg in warning_messages
            ), f"Expected a warning about failed page, got: {warning_messages}"
        finally:
            ws.close()

    def test_no_failed_pages_meta_absent_or_empty(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """When all pages succeed, failed_pages is absent or empty in meta."""
        total = 200
        page_size = 100
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            failed = result.meta.get("failed_pages", [])
            assert len(failed) == 0
        finally:
            ws.close()

    def test_total_equals_len_profiles_despite_failed_pages(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """result.total equals len(profiles) even when pages fail."""
        total = 300
        page_size = 100
        fail_pages = {1}
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size, fail_pages=fail_pages
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            assert result.total == len(result.profiles)
        finally:
            ws.close()


# =============================================================================
# Test: Worker cap enforcement (values > 5 silently reduced to 5)
# =============================================================================


class TestParallelWorkerCap:
    """Tests that worker count is validated and capped."""

    def test_workers_above_5_raises_validation_error(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """workers > 5 triggers validation error U23."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(mode="profiles", parallel=True, workers=10, limit=100_000)

            errors = exc_info.value.errors
            codes = [e.code for e in errors]
            assert "U23" in codes
        finally:
            ws.close()

    def test_workers_0_raises_validation_error(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """workers=0 triggers validation error U23."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(mode="profiles", parallel=True, workers=0, limit=100_000)

            errors = exc_info.value.errors
            codes = [e.code for e in errors]
            assert "U23" in codes
        finally:
            ws.close()

    def test_workers_negative_raises_validation_error(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Negative workers triggers validation error U23."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(mode="profiles", parallel=True, workers=-1, limit=100_000)

            errors = exc_info.value.errors
            codes = [e.code for e in errors]
            assert "U23" in codes
        finally:
            ws.close()

    def test_workers_5_accepted(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """workers=5 (maximum valid) is accepted without error."""
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=50, page_size=1000
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="profiles", parallel=True, workers=5, limit=100_000
            )

            assert isinstance(result, UserQueryResult)
        finally:
            ws.close()

    def test_workers_1_accepted(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """workers=1 (minimum valid) is accepted without error."""
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=50, page_size=1000
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="profiles", parallel=True, workers=1, limit=100_000
            )

            assert isinstance(result, UserQueryResult)
        finally:
            ws.close()


# =============================================================================
# Test: Rate limit warning when pages > 48
# =============================================================================


class TestParallelRateLimitWarning:
    """Tests that a rate limit warning is logged when pages exceed 48."""

    def test_49_pages_emits_rate_limit_warning(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Requesting 49+ pages logs a rate limit warning."""
        # 49 pages of 100 = 4900 total profiles
        total = 4900
        page_size = 100
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            with caplog.at_level(logging.WARNING):
                ws.query_user(mode="profiles", parallel=True, limit=100_000)

            warning_messages = [
                r.message for r in caplog.records if r.levelno >= logging.WARNING
            ]
            assert any(
                "rate" in msg.lower() or "48" in msg for msg in warning_messages
            ), f"Expected rate limit warning for 49 pages, got: {warning_messages}"
        finally:
            ws.close()

    def test_48_pages_no_rate_limit_warning(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Requesting exactly 48 pages does not emit a rate limit warning."""
        # 48 pages of 100 = 4800 total profiles
        total = 4800
        page_size = 100
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            with caplog.at_level(logging.WARNING):
                ws.query_user(mode="profiles", parallel=True, limit=total)

            warning_messages = [
                r.message for r in caplog.records if r.levelno >= logging.WARNING
            ]
            rate_warnings = [
                msg for msg in warning_messages if "rate" in msg.lower() or "48" in msg
            ]
            assert len(rate_warnings) == 0, (
                f"Did not expect rate limit warning for 48 pages, got: {rate_warnings}"
            )
        finally:
            ws.close()

    def test_limit_reduces_pages_below_threshold_no_warning(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """When limit reduces dispatched pages below 48, no warning is emitted."""
        total = 10000
        page_size = 100
        # limit=100 -> ceil(100/100) = 1 page -> no warning
        limit = 100
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            with caplog.at_level(logging.WARNING):
                ws.query_user(mode="profiles", parallel=True, limit=limit)

            warning_messages = [
                r.message for r in caplog.records if r.levelno >= logging.WARNING
            ]
            rate_warnings = [
                msg for msg in warning_messages if "rate" in msg.lower() or "48" in msg
            ]
            assert len(rate_warnings) == 0
        finally:
            ws.close()


# =============================================================================
# Test: parallel=True with mode="aggregate" produces validation error U18
# =============================================================================


class TestParallelAggregateValidation:
    """Tests that parallel=True + mode='aggregate' raises U18 error."""

    def test_parallel_with_aggregate_raises_u18(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """parallel=True + mode='aggregate' raises BookmarkValidationError with U18."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(parallel=True, mode="aggregate")

            errors = exc_info.value.errors
            codes = [e.code for e in errors]
            assert "U18" in codes
        finally:
            ws.close()

    def test_parallel_with_aggregate_error_message_mentions_profiles(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """U18 error message explains parallel only applies to profiles mode."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(parallel=True, mode="aggregate")

            errors = exc_info.value.errors
            u18_errors = [e for e in errors if e.code == "U18"]
            assert len(u18_errors) == 1
            assert "profiles" in u18_errors[0].message.lower()
        finally:
            ws.close()

    def test_parallel_false_with_aggregate_accepted(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """parallel=False + mode='aggregate' does not trigger U18."""
        # Set up a mock for the aggregate stats endpoint
        mock_api_client.engage_stats.return_value = {
            "results": 42,
            "status": "ok",
            "computed_at": "2025-01-15T10:00:00",
        }

        ws = workspace_factory()
        try:
            # Should not raise U18 — parallel defaults to False
            result = ws.query_user(mode="aggregate")
            assert isinstance(result, UserQueryResult)
        finally:
            ws.close()


# =============================================================================
# Test: Early exit when limit reached mid-fetch
# =============================================================================


class TestParallelEarlyExitOnLimit:
    """Tests that parallel fetching truncates to limit after collection."""

    def test_limit_truncates_after_parallel_collection(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Final result is truncated to limit even if more profiles were fetched."""
        total = 500
        page_size = 100
        limit = 250
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=limit)

            assert len(result.profiles) == limit
        finally:
            ws.close()

    def test_limit_within_first_page_no_parallel_dispatch(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """limit smaller than page_size needs only page 0."""
        total = 5000
        page_size = 1000
        limit = 50
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=limit)

            # ceil(50/1000) = 1, only page 0
            assert mock_api_client.export_profiles_page.call_count == 1
            assert len(result.profiles) == limit
        finally:
            ws.close()

    def test_limit_1_default_with_parallel_returns_single_profile(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Default limit=1 with parallel=True returns exactly 1 profile."""
        total = 5000
        page_size = 1000
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True)  # default limit=1

            assert len(result.profiles) == 1
            assert mock_api_client.export_profiles_page.call_count == 1
        finally:
            ws.close()

    def test_limit_causes_partial_last_page(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Limit requiring partial last page truncates correctly."""
        total = 500
        page_size = 100
        limit = 350  # 3.5 pages -> ceil = 4 pages, but truncated to 350
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=limit)

            assert len(result.profiles) == limit
            # ceil(350/100) = 4 pages
            assert mock_api_client.export_profiles_page.call_count == math.ceil(
                limit / page_size
            )
        finally:
            ws.close()

    def test_limit_exceeds_total_returns_all_available(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """When limit exceeds total, all available profiles are returned."""
        total = 150
        page_size = 100
        limit = 500  # More than total
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=limit)

            # Can only return what's available
            assert len(result.profiles) == total
            assert result.total == total
        finally:
            ws.close()


# =============================================================================
# Test: Computed_at and result structure
# =============================================================================


class TestParallelResultStructure:
    """Tests for result structure consistency in parallel mode."""

    def test_result_has_computed_at_timestamp(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Parallel result includes a non-empty computed_at timestamp."""
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=200, page_size=100
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            assert isinstance(result.computed_at, str)
            assert len(result.computed_at) > 0
        finally:
            ws.close()

    def test_result_has_params_dict(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Parallel result includes the params dict used for the query."""
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=200, page_size=100
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            assert isinstance(result.params, dict)
        finally:
            ws.close()

    def test_result_df_has_correct_columns(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Parallel result DataFrame has distinct_id as first column."""
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=200, page_size=100
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            df = result.df
            assert df.columns[0] == "distinct_id"
            assert df.columns[1] == "last_seen"
        finally:
            ws.close()

    def test_result_df_row_count_matches_profiles(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """DataFrame row count matches the number of returned profiles."""
        total = 250
        page_size = 100
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            assert len(result.df) == total
        finally:
            ws.close()

    def test_distinct_ids_property_matches_profiles(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """result.distinct_ids list matches profile distinct_id values."""
        total = 150
        page_size = 100
        mock_api_client.export_profiles_page.side_effect = _page_side_effect_factory(
            total=total, page_size=page_size
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            profile_ids = [p["distinct_id"] for p in result.profiles]
            assert result.distinct_ids == profile_ids
        finally:
            ws.close()


# =============================================================================
# Test: Systemic exceptions propagate immediately from parallel execution
# =============================================================================


class TestParallelErrorPropagation:
    """Tests that systemic exceptions propagate immediately from parallel fetch.

    The parallel path re-raises AuthenticationError, RateLimitError,
    ServerError, and QueryError instead of silently catching them as
    transient per-page failures. This ensures callers see the real error
    rather than receiving partial results with failed_pages metadata.
    """

    def test_authentication_error_propagates(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """AuthenticationError on page 1 propagates instead of being caught.

        Args:
            self: Test instance.
            workspace_factory: Factory for creating Workspace with mocked deps.
            mock_api_client: Mocked MixpanelAPIClient instance.
        """
        page0 = _make_page_result(
            profiles=_make_profiles_batch(0, 100),
            page=0,
            total=500,
            page_size=100,
            session_id="sess_auth",
            has_more=True,
        )
        mock_api_client.export_profiles_page.side_effect = [
            page0,
            AuthenticationError(message="bad creds", status_code=401),
        ]

        ws = workspace_factory()
        try:
            with pytest.raises(AuthenticationError, match="bad creds"):
                ws.query_user(mode="profiles", parallel=True, limit=5000, workers=2)
        finally:
            ws.close()

    def test_rate_limit_error_propagates(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """RateLimitError on page 1 propagates instead of being caught.

        Args:
            self: Test instance.
            workspace_factory: Factory for creating Workspace with mocked deps.
            mock_api_client: Mocked MixpanelAPIClient instance.
        """
        page0 = _make_page_result(
            profiles=_make_profiles_batch(0, 100),
            page=0,
            total=500,
            page_size=100,
            session_id="sess_rate",
            has_more=True,
        )
        mock_api_client.export_profiles_page.side_effect = [
            page0,
            RateLimitError(message="throttled", status_code=429),
        ]

        ws = workspace_factory()
        try:
            with pytest.raises(RateLimitError, match="throttled"):
                ws.query_user(mode="profiles", parallel=True, limit=5000, workers=2)
        finally:
            ws.close()

    def test_server_error_propagates(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """ServerError on page 1 propagates instead of being caught.

        Args:
            self: Test instance.
            workspace_factory: Factory for creating Workspace with mocked deps.
            mock_api_client: Mocked MixpanelAPIClient instance.
        """
        page0 = _make_page_result(
            profiles=_make_profiles_batch(0, 100),
            page=0,
            total=500,
            page_size=100,
            session_id="sess_server",
            has_more=True,
        )
        mock_api_client.export_profiles_page.side_effect = [
            page0,
            ServerError(message="server down", status_code=500),
        ]

        ws = workspace_factory()
        try:
            with pytest.raises(ServerError, match="server down"):
                ws.query_user(mode="profiles", parallel=True, limit=5000, workers=2)
        finally:
            ws.close()

    def test_query_error_propagates(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """QueryError on page 1 propagates instead of being caught.

        Args:
            self: Test instance.
            workspace_factory: Factory for creating Workspace with mocked deps.
            mock_api_client: Mocked MixpanelAPIClient instance.
        """
        page0 = _make_page_result(
            profiles=_make_profiles_batch(0, 100),
            page=0,
            total=500,
            page_size=100,
            session_id="sess_query",
            has_more=True,
        )
        mock_api_client.export_profiles_page.side_effect = [
            page0,
            QueryError(message="bad query", status_code=400),
        ]

        ws = workspace_factory()
        try:
            with pytest.raises(QueryError, match="bad query"):
                ws.query_user(mode="profiles", parallel=True, limit=5000, workers=2)
        finally:
            ws.close()
