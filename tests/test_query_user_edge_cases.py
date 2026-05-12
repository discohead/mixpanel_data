"""Edge-case and bug-hunting tests for query_user() (Tiers 1-3).

QA tests targeting gaps in the existing 562-test suite: silent data
corruption, crash paths with unhelpful errors, and validation bypasses.

Tier 1 — Data Corruption / Silent Wrong Results (8 tests)
Tier 2 — Crash Paths / Assertion Bombs (8 tests)
Tier 3 — Validation Gaps (12 tests)

Some tests are **expected to fail** because they expose real bugs or
document intentionally-risky behavior. These are annotated with
``pytest.mark.xfail`` and comments explaining the root cause.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless._internal.query.user_builders import filter_to_selector
from mixpanel_headless._internal.query.user_validators import (
    validate_user_args,
    validate_user_params,
)
from mixpanel_headless.exceptions import BookmarkValidationError
from mixpanel_headless.types import Filter, ProfilePageResult, UserQueryResult

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
        start_index: Starting index for user IDs.
        count: Number of profiles to generate.

    Returns:
        List of raw profile dicts.
    """
    return [
        _make_raw_profile(f"user_{start_index + i:03d}", plan="free")
        for i in range(count)
    ]


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
# TIER 1 — DATA CORRUPTION / SILENT WRONG RESULTS
# =============================================================================


class TestTier1DataCorruption:
    """Tests for silent wrong results that produce bad data without errors."""

    def test_t1_01_parallel_sort_key_unwrapped_same_as_sequential(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Both paths pass sort_key in wrapped properties["name"] format.

        The Mixpanel Engage API requires sort_key in the
        ``properties["name"]`` selector format, NOT the raw property
        name. Both sequential and parallel paths must pass this format
        through unchanged.
        """
        total = 200
        page_size = 100

        def side_effect(
            *_args: Any,
            page: int = 0,
            **_kwargs: Any,
        ) -> ProfilePageResult:
            """Return profiles for the given page.

            Args:
                *_args: Positional arguments (ignored).
                page: Zero-based page index.
                **_kwargs: Keyword arguments (ignored).

            Returns:
                ProfilePageResult for the requested page.
            """
            start = page * page_size
            count = min(page_size, total - start)
            return _make_page_result(
                profiles=_make_profiles_batch(start, count),
                page=page,
                total=total,
                page_size=page_size,
                session_id="sess_sort",
                has_more=page < math.ceil(total / page_size) - 1,
            )

        mock_api_client.export_profiles_page.side_effect = side_effect

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", sort_by="ltv", parallel=True, limit=100_000)

            calls = mock_api_client.export_profiles_page.call_args_list
            for call in calls:
                sort_key_arg = call.kwargs.get("sort_key")
                assert sort_key_arg == 'properties["ltv"]', (
                    f'Expected wrapped sort_key properties["ltv"] '
                    f"but got {sort_key_arg!r}. "
                    f'API requires properties["name"] format.'
                )
        finally:
            ws.close()

    def test_t1_02_property_name_collision_dollar_and_custom(
        self,
    ) -> None:
        """Dollar-prefixed and custom property with same base name collide.

        When a profile has both ``$email`` and ``email`` in properties,
        the DataFrame builder strips the ``$`` prefix, causing a column
        name collision. Documents which value wins (last-write-wins).
        """
        result = UserQueryResult(
            computed_at="2025-01-01T00:00:00Z",
            total=1,
            profiles=[
                {
                    "distinct_id": "u1",
                    "last_seen": "2025-01-01",
                    "properties": {
                        "$email": "builtin@x.com",
                        "email": "custom@x.com",
                    },
                }
            ],
            params={},
            meta={},
            mode="profiles",
        )

        df = result.df
        # After $-stripping, both map to "email" — only one column survives
        email_cols = [c for c in df.columns if c == "email"]
        assert len(email_cols) == 1, (
            f"Expected exactly one 'email' column, got {len(email_cols)}. "
            f"Dollar-prefix stripping causes silent data loss."
        )
        # Document which value wins: custom overwrites builtin (last-write-wins)
        # The loop processes $email first -> row["email"] = "builtin@x.com"
        # Then email -> row["email"] = "custom@x.com" (overwrites)
        email_value = df["email"].iloc[0]
        assert email_value in ("builtin@x.com", "custom@x.com"), (
            f"Unexpected email value: {email_value!r}"
        )

    def test_t1_03_parallel_failed_pages_total_vs_len_mismatch(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Parallel failed pages cause total vs len(profiles) mismatch.

        When pages fail in parallel mode, the result silently has fewer
        profiles than ``result.total`` indicates. Documents silent data
        loss with no error raised.
        """
        total = 500
        page_size = 100
        fail_pages = {2, 3}

        def side_effect(
            *_args: Any,
            page: int = 0,
            **_kwargs: Any,
        ) -> ProfilePageResult:
            """Return profiles or raise for failed pages.

            Args:
                *_args: Positional arguments (ignored).
                page: Zero-based page index.
                **_kwargs: Keyword arguments (ignored).

            Returns:
                ProfilePageResult for the requested page.

            Raises:
                Exception: For pages in fail_pages set.
            """
            if page in fail_pages:
                raise Exception(f"Simulated failure on page {page}")
            start = page * page_size
            count = min(page_size, total - start)
            return _make_page_result(
                profiles=_make_profiles_batch(start, count),
                page=page,
                total=total,
                page_size=page_size,
                session_id="sess_fail",
                has_more=page < math.ceil(total / page_size) - 1,
            )

        mock_api_client.export_profiles_page.side_effect = side_effect

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            # Total equals len(profiles), not the API total
            assert len(result.profiles) == 300, (
                "Expected 300 profiles (500 - 2*100 failed pages)"
            )
            assert result.total == len(result.profiles)
            assert sorted(result.meta["failed_pages"]) == [2, 3]
        finally:
            ws.close()

    def test_t1_04_parallel_all_pages_fail_returns_page0_only(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """When all parallel pages fail, only page 0 data is returned.

        No exception is raised despite losing 80% of the data.
        Documents silent data loss.
        """
        total = 500
        page_size = 100
        fail_pages = {1, 2, 3, 4}

        def side_effect(
            *_args: Any,
            page: int = 0,
            **_kwargs: Any,
        ) -> ProfilePageResult:
            """Return profiles or raise for failed pages.

            Args:
                *_args: Positional arguments (ignored).
                page: Zero-based page index.
                **_kwargs: Keyword arguments (ignored).

            Returns:
                ProfilePageResult for the requested page.

            Raises:
                Exception: For pages in fail_pages set.
            """
            if page in fail_pages:
                raise Exception(f"Simulated failure on page {page}")
            start = page * page_size
            count = min(page_size, total - start)
            return _make_page_result(
                profiles=_make_profiles_batch(start, count),
                page=page,
                total=total,
                page_size=page_size,
                session_id="sess_allfail",
                has_more=page < math.ceil(total / page_size) - 1,
            )

        mock_api_client.export_profiles_page.side_effect = side_effect

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            assert len(result.profiles) == 100, (
                "Only page 0 profiles should be returned"
            )
            assert result.total == len(result.profiles)
            assert sorted(result.meta["failed_pages"]) == [1, 2, 3, 4]
        finally:
            ws.close()

    def test_t1_05_distinct_ids_keyerror_on_missing_key(
        self,
    ) -> None:
        """Accessing distinct_ids raises KeyError when profile lacks key.

        The ``distinct_ids`` property uses ``p["distinct_id"]`` (bracket
        access) uses ``.get("distinct_id", "")`` to match
        ``_build_profiles_df`` behavior. A missing key returns an empty
        string instead of raising KeyError.
        """
        result = UserQueryResult(
            computed_at="2025-01-01T00:00:00Z",
            total=1,
            profiles=[
                {
                    "last_seen": "2025-01-01",
                    "properties": {},
                    # NOTE: no "distinct_id" key
                }
            ],
            params={},
            meta={},
            mode="profiles",
        )

        ids = result.distinct_ids
        assert ids == [""]

    def test_t1_06_sequential_empty_page_does_not_infinite_loop(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Sequential pagination with empty pages + has_more=True terminates.

        If the API returns has_more=True but empty profiles, the loop
        should eventually terminate (via the empty-profiles break or
        limit). This test caps at 10 calls to prevent actual infinite
        loops during testing.

        KNOWN BUG: The while loop at workspace.py:8910 only checks
        ``result.has_more`` and the limit — it never checks whether
        the returned page was empty. This causes an infinite loop when
        the API returns empty pages with has_more=True.
        """
        call_count = 0
        max_calls = 10

        def side_effect(
            *_args: Any,
            page: int = 0,
            **_kwargs: Any,
        ) -> ProfilePageResult:
            """Return one profile for page 0, then empty pages with has_more.

            Args:
                *_args: Positional arguments (ignored).
                page: Zero-based page index.
                **_kwargs: Keyword arguments (ignored).

            Returns:
                ProfilePageResult with profiles or empty list.

            Raises:
                RuntimeError: If call_count exceeds max_calls threshold.
            """
            nonlocal call_count
            call_count += 1
            if call_count > max_calls:
                raise RuntimeError(
                    f"Loop guard: exceeded {max_calls} calls, likely infinite loop"
                )
            if page == 0:
                return _make_page_result(
                    profiles=[_make_raw_profile("user_000")],
                    page=0,
                    total=100,
                    page_size=1000,
                    session_id="sess_loop",
                    has_more=True,
                )
            # Subsequent pages: empty but claim more exist
            return _make_page_result(
                profiles=[],
                page=page,
                total=100,
                page_size=1000,
                session_id="sess_loop",
                has_more=True,
            )

        mock_api_client.export_profiles_page.side_effect = side_effect

        ws = workspace_factory()
        try:
            # limit=100_000 means "fetch all" — tests loop termination
            # If the implementation doesn't guard against empty pages,
            # this will hit the RuntimeError from the loop guard.
            result = ws.query_user(mode="profiles", limit=100_000)
            # If we get here, the loop terminated on its own (fixed)
            assert len(result.profiles) >= 1
        finally:
            ws.close()

    def test_t1_07_sequential_limit_equals_page_size_no_extra_fetch(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """When limit equals page_size, no second page fetch occurs.

        The ``>=`` check in ``if limit is not None and len(profiles) >= limit``
        should catch the boundary correctly, preventing an extra API call.
        """
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=_make_profiles_batch(0, 1000),
            page=0,
            total=5000,
            page_size=1000,
            session_id="sess_boundary",
            has_more=True,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", limit=1000)

            assert mock_api_client.export_profiles_page.call_count == 1, (
                "Should fetch only page 0 when limit equals page_size"
            )
            assert len(result.profiles) == 1000
        finally:
            ws.close()

    def test_t1_08_parallel_session_id_none_with_has_more_true(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Parallel workers use session_id=None when page 0 returns None.

        When the API returns ``session_id=None`` on page 0 but
        ``has_more=True``, parallel workers call subsequent pages with
        ``session_id=None``. Documents that this is technically valid
        but may produce inconsistent pagination.
        """
        total = 200
        page_size = 100

        def side_effect(
            *_args: Any,
            page: int = 0,
            **_kwargs: Any,
        ) -> ProfilePageResult:
            """Return profiles with session_id=None.

            Args:
                *_args: Positional arguments (ignored).
                page: Zero-based page index.
                **_kwargs: Keyword arguments (ignored).

            Returns:
                ProfilePageResult with session_id=None.
            """
            start = page * page_size
            count = min(page_size, total - start)
            return _make_page_result(
                profiles=_make_profiles_batch(start, count),
                page=page,
                total=total,
                page_size=page_size,
                session_id=None,
                has_more=page < math.ceil(total / page_size) - 1,
            )

        mock_api_client.export_profiles_page.side_effect = side_effect

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            # Should still return all profiles
            assert len(result.profiles) == total
            # Meta should reflect None session_id
            assert result.meta["session_id"] is None
            # Verify workers were called with session_id=None
            for call in mock_api_client.export_profiles_page.call_args_list[1:]:
                assert call.kwargs.get("session_id") is None
        finally:
            ws.close()


# =============================================================================
# TIER 2 — CRASH PATHS / ASSERTION BOMBS
# =============================================================================


class TestTier2CrashPaths:
    """Tests for code paths that crash with unhelpful errors."""

    def test_t2_01_cohort_extraction_raises_validation_error_on_malformed_filter(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Malformed cohort filter value raises BookmarkValidationError.

        When a Filter passes ``_is_cohort_filter`` (value is a list of
        dicts) but the dict is missing the ``"cohort"`` key, the
        extraction raises ``BookmarkValidationError`` with code
        ``U_COHORT``.
        """
        # Construct a Filter that passes _is_cohort_filter but has
        # wrong internal structure
        malformed_filter = Filter(
            _property="$cohorts",
            _operator="contains",
            _value=[{"not_cohort": True}],
            _property_type="list",
        )

        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.build_user_params(where=malformed_filter)
            assert any(e.code == "U_COHORT" for e in exc_info.value.errors)
        finally:
            ws.close()

    def test_t2_02_json_loads_malformed_output_properties_sequential(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Malformed JSON in output_properties crashes with JSONDecodeError.

        The sequential path at workspace.py:8879 does
        ``json.loads(raw_output)`` without wrapping the error.
        """
        ws = workspace_factory()
        try:
            # Manually build params with invalid JSON
            params: dict[str, Any] = {
                "output_properties": "not valid json",
            }
            with pytest.raises(json.JSONDecodeError):
                ws._execute_user_query_sequential(params, limit=1)
        finally:
            ws.close()

    def test_t2_03_json_loads_malformed_distinct_ids_parallel(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Malformed JSON in distinct_ids crashes _build_page_kwargs.

        The parallel path at workspace.py:9406 does
        ``json.loads(val)`` on distinct_ids without error wrapping.
        """
        ws = workspace_factory()
        try:
            params: dict[str, Any] = {
                "distinct_ids": "broken json",
            }
            with pytest.raises(json.JSONDecodeError):
                ws._build_page_kwargs(params)
        finally:
            ws.close()

    def test_t2_04_json_loads_malformed_segment_by_cohorts_aggregate(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Malformed JSON in segment_by_cohorts crashes aggregate execution.

        The aggregate path at workspace.py:9224 does
        ``json.loads(raw)`` without error wrapping.
        """
        ws = workspace_factory()
        try:
            params: dict[str, Any] = {
                "segment_by_cohorts": "{invalid json",
            }
            with pytest.raises(json.JSONDecodeError):
                ws._execute_user_aggregate(params)
        finally:
            ws.close()

    def test_t2_05_filter_to_selector_unsupported_operator(
        self,
    ) -> None:
        """Unsupported filter operator raises ValueError.

        Verifies the catch-all at user_builders.py:142 raises a clear
        ValueError with the operator name.
        """
        f = Filter(
            _property="fake",
            _operator="unknown_op",  # type: ignore[arg-type]
            _value=None,
            _property_type="string",
        )

        with pytest.raises(ValueError, match="Unsupported filter operator.*unknown_op"):
            filter_to_selector(f)

    def test_t2_06_filter_to_selector_equals_non_list_value(
        self,
    ) -> None:
        """Equals operator with non-list value triggers ValueError.

        The type check at user_builders.py raises ValueError when
        ``isinstance(value, list)`` fails. This is production-safe
        (not stripped by ``python -O`` like bare assert).
        """
        f = Filter(
            _property="plan",
            _operator="equals",
            _value="string_not_list",
            _property_type="string",
        )

        with pytest.raises(ValueError, match="Expected list"):
            filter_to_selector(f)

    def test_t2_07_filter_to_selector_between_wrong_length(
        self,
    ) -> None:
        """Between operator with wrong list length triggers ValueError.

        The type check at user_builders.py raises ValueError when
        the value is not a list of length 2. A 3-element list fails.
        """
        between_val: list[int | float] = [1, 2, 3]
        f = Filter(
            _property="amount",
            _operator="is between",
            _value=between_val,
            _property_type="number",
        )

        with pytest.raises(ValueError, match="Expected list"):
            filter_to_selector(f)

    def test_t2_08_aggregate_response_missing_results_key(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Engage stats response without 'results' key produces None.

        When the API returns ``{"status": "ok"}`` without a ``results``
        key, ``response.get("results")`` returns None. The result should
        not crash but have ``aggregate_data=None`` and ``value=None``.
        """
        mock_api_client.engage_stats.return_value = {"status": "ok"}

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="aggregate")

            assert result.aggregate_data is None
            assert result.value is None
        finally:
            ws.close()


# =============================================================================
# TIER 3 — VALIDATION GAPS
# =============================================================================


class TestTier3ValidationGaps:
    """Tests for inputs that bypass or slip through validation."""

    def test_t3_01_sort_by_injection_with_double_quote(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Sort_by with double quote is escaped in the selector.

        ``build_user_params`` escapes double quotes in property names
        to prevent selector injection.
        """
        ws = workspace_factory()
        try:
            params = ws.build_user_params(mode="profiles", sort_by='foo"bar')

            sort_key = params["sort_key"]
            assert sort_key == 'properties["foo\\"bar"]', (
                f"Expected escaped quote in selector, got {sort_key!r}"
            )
        finally:
            ws.close()

    def test_t3_02_sort_by_injection_with_close_bracket(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Sort_by with close bracket is escaped in the selector.

        Passing ``"]`` as sort_by escapes the double quote to prevent
        selector injection.
        """
        ws = workspace_factory()
        try:
            params = ws.build_user_params(mode="profiles", sort_by='"]')

            sort_key = params["sort_key"]
            assert sort_key == 'properties["\\"]"]', (
                f"Expected escaped selector, got {sort_key!r}"
            )
        finally:
            ws.close()

    def test_t3_03_empty_where_list_no_where_param(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Empty where list produces no 'where' key in params.

        ``filters_to_selector([])`` returns ``""``, which is falsy.
        The guard ``if selector:`` catches it and skips setting the key.
        """
        ws = workspace_factory()
        try:
            params = ws.build_user_params(where=[])

            assert "where" not in params, (
                "Empty filter list should not produce a 'where' param"
            )
        finally:
            ws.close()

    def test_t3_04_where_raw_string_with_cohort_int(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Raw string where + cohort int produces both params.

        When ``where`` is a raw string and ``cohort`` is an int, both
        ``where`` and ``filter_by_cohort`` are set in params. This
        combination is untested but valid.
        """
        ws = workspace_factory()
        try:
            params = ws.build_user_params(
                where='properties["plan"] == "premium"',
                cohort=42,
            )

            assert params["where"] == 'properties["plan"] == "premium"'
            assert "filter_by_cohort" in params
            parsed = json.loads(params["filter_by_cohort"])
            assert parsed["id"] == 42
        finally:
            ws.close()

    def test_t3_05_validate_user_params_up2_dead_code_with_json_string(
        self,
    ) -> None:
        """UP2 is dead code because filter_by_cohort is always a JSON string.

        ``validate_user_params`` checks ``isinstance(fbc, dict)`` for
        UP2, but ``_resolve_and_build_user_params`` always stores
        ``filter_by_cohort`` as a JSON *string* (via ``json.dumps``).
        The isinstance check never matches, making UP2 unreachable
        in normal flow.
        """
        errors = validate_user_params({"filter_by_cohort": '{"id": 42}'})

        # UP2 passes because the isinstance(fbc, dict) check skips strings
        up2_errors = [e for e in errors if e.code == "UP2"]
        assert len(up2_errors) == 0, (
            "UP2 should not trigger for JSON strings — the isinstance(dict) "
            "check makes it dead code in normal flow"
        )

    def test_t3_06_include_all_users_with_in_cohort_filter_accepted(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """include_all_users + Filter.in_cohort does not raise U7.

        U7 now checks both ``cohort is None`` and ``in_cohort_count == 0``,
        so ``Filter.in_cohort(42)`` satisfies the cohort requirement
        without needing the ``cohort`` param.
        """
        ws = workspace_factory()
        try:
            # Should NOT raise — in_cohort filter satisfies the cohort requirement
            params = ws.build_user_params(
                where=Filter.in_cohort(42),
                include_all_users=True,
            )
            assert "include_all_users" in params
        finally:
            ws.close()

    def test_t3_07_as_of_integer_zero_accepted(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """as_of=0 (Unix epoch) is accepted, not treated as falsy.

        Zero is a valid Unix timestamp (1970-01-01T00:00:00Z). The
        ``if as_of is not None`` check correctly passes 0 through.
        """
        ws = workspace_factory()
        try:
            params = ws.build_user_params(mode="profiles", as_of=0)

            assert params["as_of_timestamp"] == 0, (
                "as_of=0 should be treated as valid timestamp, not skipped"
            )
        finally:
            ws.close()

    def test_t3_08_as_of_negative_integer_accepted(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """as_of=-1 is accepted without validation.

        Negative Unix timestamps are technically valid (pre-1970) but
        no validation rejects them. Documents that negative timestamps
        pass through unchecked.
        """
        ws = workspace_factory()
        try:
            params = ws.build_user_params(mode="profiles", as_of=-1)

            assert params["as_of_timestamp"] == -1, (
                "Negative timestamps pass through without validation"
            )
        finally:
            ws.close()

    def test_t3_09_validate_action_malformed_string_rejected(
        self,
    ) -> None:
        """UP4 regex rejects malformed action strings.

        The refactored ``_ACTION_RE`` requires structured action
        formats: ``count()``, ``extremes(properties["prop"])``,
        ``percentile(properties["prop"], N)``, or
        ``numeric_summary(properties["prop"])``. A bare function
        call like ``extremes(None)`` that omits the required
        ``properties["..."]`` wrapper is correctly rejected.
        """
        errors = validate_user_params({"action": "extremes(None)"})

        up4_errors = [e for e in errors if e.code == "UP4"]
        assert len(up4_errors) == 1, (
            "Expected UP4 to reject: 'extremes(None)' does not match "
            'the required properties["..."] format'
        )

    def test_t3_10_workers_6_raises_u23(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """workers=6 triggers validation error U23.

        U23 enforces ``1 <= workers <= 5``. This test verifies the
        upper boundary is checked.
        """
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.build_user_params(workers=6)

            codes = [e.code for e in exc_info.value.errors]
            assert "U23" in codes
        finally:
            ws.close()

    def test_t3_11_limit_zero_raises_u3(
        self,
    ) -> None:
        """limit=0 triggers validation error U3.

        U3 checks ``limit <= 0``, catching zero as invalid. Tested
        via ``validate_user_args`` directly since ``build_user_params``
        does not accept a ``limit`` parameter (limit is only used at
        query execution time).
        """
        errors = validate_user_args(limit=0)

        codes = [e.code for e in errors]
        assert "U3" in codes

    def test_t3_12_limit_negative_raises_u3(
        self,
    ) -> None:
        """limit=-5 triggers validation error U3.

        Negative limits are invalid per U3. Tested via
        ``validate_user_args`` directly.
        """
        errors = validate_user_args(limit=-5)

        codes = [e.code for e in errors]
        assert "U3" in codes
