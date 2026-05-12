"""Unit tests for Workspace.query_user() profiles mode (T012).

Tests cover sequential query execution and the public query_user() method
in profiles mode. Each test mocks api_client.export_profiles_page() to
return controlled ProfilePageResult responses.

Coverage:
- Default limit=1 returns 1 profile
- Explicit limit fetches correct number via pagination
- Property selection reduces DataFrame columns
- sort_by/sort_order passed to API
- search param passed to API
- distinct_id lookup
- distinct_ids batch lookup
- group_id queries group profiles
- as_of passes timestamp
- result.total equals len(profiles)
- result.df has correct column schema
- Empty result returns empty DataFrame with correct columns
- Credentials check raises ConfigError when None
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
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
# Mock data
# =============================================================================

RAW_PROFILE_1 = _make_raw_profile("user_001", plan="premium", email="alice@example.com")
RAW_PROFILE_2 = _make_raw_profile("user_002", plan="free", email="bob@example.com")
RAW_PROFILE_3 = _make_raw_profile("user_003", plan="premium", email="carol@example.com")


# =============================================================================
# Test: Default limit=1 returns 1 profile + total count
# =============================================================================


class TestQueryUserDefaultLimit:
    """Tests for query_user() default limit=1 behavior."""

    def test_default_limit_returns_single_profile(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Default limit=1 returns exactly 1 profile from the result."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1, RAW_PROFILE_2],
            total=500,
            has_more=True,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            assert isinstance(result, UserQueryResult)
            assert result.mode == "profiles"
            assert len(result.profiles) == 1
            assert result.profiles[0]["distinct_id"] == "user_001"
        finally:
            ws.close()

    def test_default_limit_total_equals_len_profiles(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Default limit=1 returns total == len(profiles) == 1."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=5432,
            has_more=True,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            assert result.total == 1
            assert result.total == len(result.profiles)
        finally:
            ws.close()

    def test_default_limit_fetches_only_one_page(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Default limit=1 should fetch only page 0, not paginate further."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1, RAW_PROFILE_2],
            total=5000,
            has_more=True,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles")

            assert mock_api_client.export_profiles_page.call_count == 1
        finally:
            ws.close()


# =============================================================================
# Test: Explicit limit fetches correct number via pagination
# =============================================================================


class TestQueryUserExplicitLimit:
    """Tests for query_user() with explicit limit and pagination."""

    def test_limit_truncates_to_requested_count(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Explicit limit=2 returns exactly 2 profiles even if page has more."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1, RAW_PROFILE_2, RAW_PROFILE_3],
            total=500,
            has_more=True,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", limit=2)

            assert len(result.profiles) == 2
        finally:
            ws.close()

    def test_pagination_fetches_multiple_pages(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Limit exceeding page size triggers sequential pagination."""
        page_0 = _make_page_result(
            profiles=[RAW_PROFILE_1],
            page=0,
            total=3,
            page_size=1,
            session_id="sess_xyz",
            has_more=True,
        )
        page_1 = _make_page_result(
            profiles=[RAW_PROFILE_2],
            page=1,
            total=3,
            page_size=1,
            session_id="sess_xyz",
            has_more=True,
        )
        page_2 = _make_page_result(
            profiles=[RAW_PROFILE_3],
            page=2,
            total=3,
            page_size=1,
            session_id="sess_xyz",
            has_more=False,
        )
        mock_api_client.export_profiles_page.side_effect = [page_0, page_1, page_2]

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", limit=3)

            assert len(result.profiles) == 3
            assert mock_api_client.export_profiles_page.call_count == 3
        finally:
            ws.close()

    def test_pagination_stops_when_limit_reached(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Pagination stops after collecting enough profiles for the limit."""
        page_0 = _make_page_result(
            profiles=[RAW_PROFILE_1, RAW_PROFILE_2],
            page=0,
            total=100,
            page_size=2,
            session_id="sess_stop",
            has_more=True,
        )

        mock_api_client.export_profiles_page.side_effect = [page_0]

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", limit=2)

            assert len(result.profiles) == 2
            # Should not fetch page 1 since limit already met
            assert mock_api_client.export_profiles_page.call_count == 1
        finally:
            ws.close()

    def test_limit_none_fetches_all_profiles(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """limit=100_000 fetches all pages until has_more is False."""
        page_0 = _make_page_result(
            profiles=[RAW_PROFILE_1],
            page=0,
            total=2,
            page_size=1,
            session_id="sess_all",
            has_more=True,
        )
        page_1 = _make_page_result(
            profiles=[RAW_PROFILE_2],
            page=1,
            total=2,
            page_size=1,
            session_id="sess_all",
            has_more=False,
        )
        mock_api_client.export_profiles_page.side_effect = [page_0, page_1]

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", limit=100_000)

            assert len(result.profiles) == 2
            assert mock_api_client.export_profiles_page.call_count == 2
        finally:
            ws.close()


# =============================================================================
# Test: Property selection reduces DataFrame columns
# =============================================================================


class TestQueryUserPropertySelection:
    """Tests for query_user() output_properties / properties param."""

    def test_properties_passed_to_api(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """properties param is forwarded as output_properties to export_profiles_page()."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", properties=["$email", "plan"])

            call_kwargs = mock_api_client.export_profiles_page.call_args
            # output_properties should be passed as a keyword argument
            assert call_kwargs.kwargs.get("output_properties") == ["$email", "plan"]
        finally:
            ws.close()

    def test_properties_none_sends_no_output_properties(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """properties=None should not set output_properties (returns all)."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", properties=None)

            call_kwargs = mock_api_client.export_profiles_page.call_args
            assert call_kwargs.kwargs.get("output_properties") is None
        finally:
            ws.close()


# =============================================================================
# Test: sort_by/sort_order passed to API
# =============================================================================


class TestQueryUserSorting:
    """Tests for query_user() sort_by and sort_order parameters."""

    def test_sort_by_passed_as_sort_key(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """sort_by is translated to sort_key in the API call."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", sort_by="$last_seen")

            call_kwargs = mock_api_client.export_profiles_page.call_args
            assert call_kwargs.kwargs.get("sort_key") == 'properties["$last_seen"]'
        finally:
            ws.close()

    def test_sort_order_passed_to_api(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """sort_order is forwarded directly to export_profiles_page()."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", sort_by="revenue", sort_order="ascending")

            call_kwargs = mock_api_client.export_profiles_page.call_args
            assert call_kwargs.kwargs.get("sort_order") == "ascending"
        finally:
            ws.close()

    def test_default_sort_order_is_descending(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Default sort_order is 'descending' when sort_by is provided."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", sort_by="$last_seen")

            call_kwargs = mock_api_client.export_profiles_page.call_args
            assert call_kwargs.kwargs.get("sort_order") == "descending"
        finally:
            ws.close()

    def test_sort_by_escapes_double_quotes(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """sort_by with double quotes is escaped in sort_key."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", sort_by='weird"prop')

            call_kwargs = mock_api_client.export_profiles_page.call_args
            assert call_kwargs.kwargs.get("sort_key") == 'properties["weird\\"prop"]'
        finally:
            ws.close()

    def test_sort_by_escapes_backslashes(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """sort_by with backslashes is escaped in sort_key."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", sort_by="back\\slash")

            call_kwargs = mock_api_client.export_profiles_page.call_args
            assert call_kwargs.kwargs.get("sort_key") == 'properties["back\\\\slash"]'
        finally:
            ws.close()


# =============================================================================
# Test: search param passed to API
# =============================================================================


class TestQueryUserSearch:
    """Tests for query_user() search parameter."""

    def test_search_passed_to_api(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """search string is forwarded to export_profiles_page()."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", search="alice")

            call_kwargs = mock_api_client.export_profiles_page.call_args
            assert call_kwargs.kwargs.get("search") == "alice"
        finally:
            ws.close()

    def test_search_none_by_default(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Default search is None (not sent to API)."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles")

            call_kwargs = mock_api_client.export_profiles_page.call_args
            assert call_kwargs.kwargs.get("search") is None
        finally:
            ws.close()


# =============================================================================
# Test: distinct_id lookup
# =============================================================================


class TestQueryUserDistinctId:
    """Tests for query_user() distinct_id single-user lookup."""

    def test_distinct_id_passed_to_api(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """distinct_id is converted to a where selector for the API."""
        target_profile = _make_raw_profile("user_target", plan="enterprise")
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[target_profile],
            total=1,
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", distinct_id="user_target")

            assert len(result.profiles) == 1
            assert result.profiles[0]["distinct_id"] == "user_target"
            # Verify the API was called (exact param assertion depends on impl)
            mock_api_client.export_profiles_page.assert_called_once()
        finally:
            ws.close()


# =============================================================================
# Test: distinct_ids batch lookup
# =============================================================================


class TestQueryUserDistinctIds:
    """Tests for query_user() distinct_ids batch lookup."""

    def test_distinct_ids_batch_returns_matching_profiles(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """distinct_ids returns profiles for each requested ID."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1, RAW_PROFILE_2],
            total=2,
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="profiles",
                distinct_ids=["user_001", "user_002"],
                limit=100_000,
            )

            assert len(result.profiles) == 2
            ids = [p["distinct_id"] for p in result.profiles]
            assert "user_001" in ids
            assert "user_002" in ids
        finally:
            ws.close()


# =============================================================================
# Test: group_id queries group profiles
# =============================================================================


class TestQueryUserGroupId:
    """Tests for query_user() group_id parameter."""

    def test_group_id_passed_to_api(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """group_id is forwarded to export_profiles_page() for group profile queries."""
        company_profile = _make_raw_profile("company_001", name="Acme Corp")
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[company_profile],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", group_id="companies")

            call_kwargs = mock_api_client.export_profiles_page.call_args
            assert call_kwargs.kwargs.get("group_id") == "companies"
        finally:
            ws.close()


# =============================================================================
# Test: as_of passes timestamp
# =============================================================================


class TestQueryUserAsOf:
    """Tests for query_user() as_of point-in-time parameter."""

    def test_as_of_unix_timestamp_passed_to_api(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """as_of with Unix int is forwarded as as_of_timestamp."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", as_of=1704067200)

            call_kwargs = mock_api_client.export_profiles_page.call_args
            assert call_kwargs.kwargs.get("as_of_timestamp") == 1704067200
        finally:
            ws.close()

    def test_as_of_date_string_converted_to_timestamp(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """as_of with YYYY-MM-DD string is converted to Unix timestamp."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", as_of="2024-01-01")

            call_kwargs = mock_api_client.export_profiles_page.call_args
            as_of_ts = call_kwargs.kwargs.get("as_of_timestamp")
            # Should be a Unix timestamp (integer), not a string
            assert isinstance(as_of_ts, int)
            assert as_of_ts > 0
        finally:
            ws.close()


# =============================================================================
# Test: result.total equals len(profiles)
# =============================================================================


class TestQueryUserTotalCount:
    """Tests for result.total equalling len(profiles)."""

    def test_total_equals_len_profiles_with_limit_1(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """result.total equals len(profiles), not the API's full population count."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=99999,
            has_more=True,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")  # default limit=1

            assert result.total == 1
            assert result.total == len(result.profiles)
        finally:
            ws.close()

    def test_total_equals_len_profiles_with_explicit_limit(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """result.total equals len(profiles) even when API reports more."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1, RAW_PROFILE_2, RAW_PROFILE_3],
            total=10000,
            has_more=True,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", limit=2)

            assert result.total == 2
            assert result.total == len(result.profiles)
        finally:
            ws.close()

    def test_total_matches_profiles_when_all_fetched(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """When all profiles fit in one page, total equals len(profiles)."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1, RAW_PROFILE_2],
            total=2,
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", limit=100_000)

            assert result.total == 2
            assert result.total == len(result.profiles)
        finally:
            ws.close()


# =============================================================================
# Test: result.df has correct column schema
# =============================================================================


class TestQueryUserDataFrame:
    """Tests for result.df column schema and content."""

    def test_df_has_distinct_id_first_column(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """DataFrame first column is always 'distinct_id'."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            df = result.df
            assert df.columns[0] == "distinct_id"
        finally:
            ws.close()

    def test_df_has_last_seen_second_column(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """DataFrame second column is always 'last_seen'."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            df = result.df
            assert df.columns[1] == "last_seen"
        finally:
            ws.close()

    def test_df_strips_dollar_prefix_from_properties(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Built-in Mixpanel properties have $ prefix stripped in DataFrame columns."""
        profile = _make_raw_profile(
            "user_dollar",
            **{"$email": "test@example.com", "$city": "SF"},
        )
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[profile],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            df = result.df
            assert "email" in df.columns
            assert "city" in df.columns
            assert "$email" not in df.columns
            assert "$city" not in df.columns
        finally:
            ws.close()

    def test_df_remaining_columns_sorted_alphabetically(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Property columns after distinct_id and last_seen are alphabetically sorted."""
        profile = _make_raw_profile(
            "user_sort",
            plan="premium",
            age=30,
            email="z@example.com",
        )
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[profile],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            df = result.df
            columns = list(df.columns)
            # First two are fixed: distinct_id, last_seen
            assert columns[0] == "distinct_id"
            assert columns[1] == "last_seen"
            # Remaining should be alphabetical
            remaining = columns[2:]
            assert remaining == sorted(remaining)
        finally:
            ws.close()

    def test_df_row_count_matches_profiles(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """DataFrame has exactly one row per returned profile."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1, RAW_PROFILE_2],
            total=2,
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", limit=2)

            assert len(result.df) == 2
        finally:
            ws.close()


# =============================================================================
# Test: Empty result returns empty DataFrame with correct columns
# =============================================================================


class TestQueryUserEmptyResult:
    """Tests for query_user() when no profiles match."""

    def test_empty_result_returns_empty_dataframe(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Empty result set produces a DataFrame with zero rows."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[],
            total=0,
            has_more=False,
            session_id=None,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            assert len(result.profiles) == 0
            assert result.total == 0
            assert len(result.df) == 0
        finally:
            ws.close()

    def test_empty_result_df_has_correct_columns(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Empty DataFrame still has distinct_id and last_seen columns."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[],
            total=0,
            has_more=False,
            session_id=None,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            df = result.df
            assert "distinct_id" in df.columns
            assert "last_seen" in df.columns
        finally:
            ws.close()

    def test_empty_result_distinct_ids_is_empty_list(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Empty result has an empty distinct_ids list."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[],
            total=0,
            has_more=False,
            session_id=None,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            assert result.distinct_ids == []
        finally:
            ws.close()


# =============================================================================
# Test: Credentials check raises ConfigError when None
# =============================================================================


class TestQueryUserConfigError:
    """Tests for query_user() with missing/valid credentials."""

    # test_no_credentials_raises_config_error removed in B1 (Fix 10):
    # Workspace.__init__ now always populates _credentials via the v3
    # session shim, so the "no credentials" path is unreachable.

    def test_config_error_not_raised_with_valid_credentials(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """query_user() does not raise ConfigError when credentials exist."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            # Should not raise
            result = ws.query_user(mode="profiles")
            assert isinstance(result, UserQueryResult)
        finally:
            ws.close()


# =============================================================================
# Test: Result type and metadata
# =============================================================================


class TestQueryUserResultMetadata:
    """Tests for UserQueryResult structure and metadata fields."""

    def test_result_is_user_query_result(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """query_user() returns a UserQueryResult instance."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            assert isinstance(result, UserQueryResult)
        finally:
            ws.close()

    def test_result_mode_is_profiles(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Profiles mode query returns mode='profiles'."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            assert result.mode == "profiles"
        finally:
            ws.close()

    def test_result_has_computed_at(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Result includes a computed_at timestamp string."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            assert isinstance(result.computed_at, str)
            assert len(result.computed_at) > 0
        finally:
            ws.close()

    def test_result_has_params_dict(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Result includes the params dict used for the API call."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            assert isinstance(result.params, dict)
        finally:
            ws.close()

    def test_result_has_meta_dict(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Result includes a meta dict with execution metadata."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            assert isinstance(result.meta, dict)
        finally:
            ws.close()

    def test_result_aggregate_data_is_none_for_profiles_mode(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """aggregate_data is None for profiles mode results."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            assert result.aggregate_data is None
        finally:
            ws.close()


# =============================================================================
# Test: Profile normalization via transform_profile
# =============================================================================


class TestQueryUserProfileNormalization:
    """Tests verifying profiles are normalized via transform_profile()."""

    def test_profiles_have_distinct_id_key(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Normalized profiles have 'distinct_id' (not '$distinct_id')."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            profile = result.profiles[0]
            assert "distinct_id" in profile
            assert "$distinct_id" not in profile
        finally:
            ws.close()

    def test_profiles_have_last_seen_key(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Normalized profiles have 'last_seen' (not '$last_seen')."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            profile = result.profiles[0]
            assert "last_seen" in profile
        finally:
            ws.close()

    def test_profiles_have_properties_dict(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Normalized profiles have a 'properties' dict without reserved keys."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            profile = result.profiles[0]
            assert "properties" in profile
            assert isinstance(profile["properties"], dict)
            # $last_seen should be extracted, not in properties
            assert "$last_seen" not in profile["properties"]
        finally:
            ws.close()

    def test_profile_properties_preserved(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Custom properties are preserved in the normalized profile."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_1],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            profile = result.profiles[0]
            assert profile["properties"]["plan"] == "premium"
            assert profile["properties"]["email"] == "alice@example.com"
        finally:
            ws.close()


# =============================================================================
# Test: Pagination session_id forwarding
# =============================================================================


class TestQueryUserPaginationSessionId:
    """Tests for session_id handling during pagination."""

    def test_first_page_called_without_session_id(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """First page request has session_id=None."""
        page_0 = _make_page_result(
            profiles=[RAW_PROFILE_1],
            page=0,
            total=2,
            page_size=1,
            session_id="sess_first",
            has_more=True,
        )
        page_1 = _make_page_result(
            profiles=[RAW_PROFILE_2],
            page=1,
            total=2,
            page_size=1,
            session_id="sess_first",
            has_more=False,
        )
        mock_api_client.export_profiles_page.side_effect = [page_0, page_1]

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", limit=2)

            first_call = mock_api_client.export_profiles_page.call_args_list[0]
            # First page should not pass a session_id (or pass None)
            first_page_arg = (
                first_call.args[0] if first_call.args else first_call.kwargs.get("page")
            )
            assert first_page_arg == 0
        finally:
            ws.close()

    def test_subsequent_pages_use_session_id(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Subsequent page requests use the session_id from page 0."""
        page_0 = _make_page_result(
            profiles=[RAW_PROFILE_1],
            page=0,
            total=2,
            page_size=1,
            session_id="sess_paginate",
            has_more=True,
        )
        page_1 = _make_page_result(
            profiles=[RAW_PROFILE_2],
            page=1,
            total=2,
            page_size=1,
            session_id="sess_paginate",
            has_more=False,
        )
        mock_api_client.export_profiles_page.side_effect = [page_0, page_1]

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", limit=2)

            second_call = mock_api_client.export_profiles_page.call_args_list[1]
            # Second page should pass the session_id from page 0
            session_id = second_call.kwargs.get("session_id") or (
                second_call.args[1] if len(second_call.args) > 1 else None
            )
            assert session_id == "sess_paginate"
        finally:
            ws.close()


# =============================================================================
# PR #118 review fixes — ValueError wrapping and aggregate escaping
# =============================================================================


class TestQueryUserValueErrorWrapping:
    """Tests for ValueError→BookmarkValidationError wrapping (#9)."""

    def test_unsupported_filter_operator_raises_bookmark_error(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Unsupported filter operator raises BookmarkValidationError."""
        f = Filter("prop", "unsupported_op", "val")  # type: ignore[arg-type]
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError):
                ws.query_user(
                    mode="profiles",
                    where=f,
                )
        finally:
            ws.close()


class TestQueryUserAggregatePropertyEscaping:
    """Tests for aggregate_property escaping in action strings."""

    def test_aggregate_property_with_double_quote(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """aggregate_property with double quote is escaped in action."""
        mock_api_client.engage_stats.return_value = {"results": 42}

        ws = workspace_factory()
        try:
            ws.query_user(
                mode="aggregate",
                aggregate="extremes",
                aggregate_property='has"quote',
            )

            call_kwargs = mock_api_client.engage_stats.call_args
            assert call_kwargs.kwargs.get("action") == (
                'extremes(properties["has\\"quote"])'
            )
        finally:
            ws.close()
