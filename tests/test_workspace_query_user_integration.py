"""Integration tests for Workspace.query_user() behavioral filtering (T020) and
cross-engine composition (T024).

T020 covers US3 (behavioral filtering via CohortDefinition):
- CohortDefinition.all_of with did_event routes to filter_by_cohort with raw_cohort
- CohortDefinition.any_of produces correct OR structure
- Saved cohort by ID routes to filter_by_cohort with id
- Combined cohort + where filters work together
- cohort + Filter.in_cohort() in where produces validation error U2
- CohortDefinition serialization failure produces validation error U24

T024 covers US5 (cross-engine composition):
- result.distinct_ids returns list usable for downstream operations
- result.df composes with pandas operations (groupby, merge, describe)
- Filter objects work identically across query() and query_user()
- cohort ID from funnel analysis works as query_user(cohort=ID)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from pydantic import SecretStr

from mixpanel_headless import (
    CohortCriteria,
    CohortDefinition,
    Filter,
    Workspace,
)
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.exceptions import BookmarkValidationError
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


# =============================================================================
# Mock data
# =============================================================================

RAW_PROFILE_PREMIUM = _make_raw_profile(
    "user_001", plan="premium", email="alice@example.com", revenue=150.0
)
RAW_PROFILE_FREE = _make_raw_profile(
    "user_002", plan="free", email="bob@example.com", revenue=0.0
)
RAW_PROFILE_ENTERPRISE = _make_raw_profile(
    "user_003", plan="enterprise", email="carol@example.com", revenue=500.0
)
RAW_PROFILE_PREMIUM_2 = _make_raw_profile(
    "user_004", plan="premium", email="dave@example.com", revenue=200.0
)
RAW_PROFILE_NO_PLAN = _make_raw_profile(
    "user_005", email="eve@example.com", revenue=50.0
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
# T020: Behavioral filtering tests (US3)
# =============================================================================


class TestBehavioralFilteringAllOf:
    """Tests for CohortDefinition.all_of routing to filter_by_cohort with raw_cohort."""

    def test_all_of_did_event_routes_to_raw_cohort(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """CohortDefinition.all_of(did_event(...)) sets filter_by_cohort with raw_cohort key."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        cohort = CohortDefinition.all_of(
            CohortCriteria.did_event("Purchase", at_least=3, within_days=30),
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", cohort=cohort, limit=1)

            call_kwargs = mock_api_client.export_profiles_page.call_args
            fbc_raw = call_kwargs.kwargs.get("filter_by_cohort")
            assert fbc_raw is not None

            fbc = json.loads(fbc_raw)
            assert "raw_cohort" in fbc
            assert "selector" in fbc["raw_cohort"]
            assert "behaviors" in fbc["raw_cohort"]
        finally:
            ws.close()

    def test_all_of_did_event_behavior_contains_event_name(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """The raw_cohort behaviors dict references the correct event name."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        cohort = CohortDefinition.all_of(
            CohortCriteria.did_event("Purchase", at_least=1, within_days=7),
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", cohort=cohort, limit=1)

            call_kwargs = mock_api_client.export_profiles_page.call_args
            fbc = json.loads(call_kwargs.kwargs["filter_by_cohort"])
            behaviors = fbc["raw_cohort"]["behaviors"]
            # At least one behavior entry references "Purchase"
            # Structure: behaviors.bhvr_N.count.event_selector.event
            behavior_events = [
                b.get("count", {}).get("event_selector", {}).get("event")
                for b in behaviors.values()
            ]
            assert "Purchase" in behavior_events
        finally:
            ws.close()

    def test_all_of_selector_uses_and_operator(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """CohortDefinition.all_of produces a selector with AND operator."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        cohort = CohortDefinition.all_of(
            CohortCriteria.did_event("Purchase", at_least=1, within_days=7),
            CohortCriteria.has_property("plan", "premium"),
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", cohort=cohort, limit=1)

            call_kwargs = mock_api_client.export_profiles_page.call_args
            fbc = json.loads(call_kwargs.kwargs["filter_by_cohort"])
            selector = fbc["raw_cohort"]["selector"]
            assert selector.get("operator") == "and"
        finally:
            ws.close()


class TestBehavioralFilteringAnyOf:
    """Tests for CohortDefinition.any_of producing correct OR structure."""

    def test_any_of_produces_or_selector(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """CohortDefinition.any_of produces a selector with OR operator."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM, RAW_PROFILE_FREE],
            total=2,
        )

        cohort = CohortDefinition.any_of(
            CohortCriteria.did_event("Purchase", at_least=1, within_days=30),
            CohortCriteria.has_property("plan", "premium"),
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", cohort=cohort, limit=2)

            call_kwargs = mock_api_client.export_profiles_page.call_args
            fbc = json.loads(call_kwargs.kwargs["filter_by_cohort"])
            selector = fbc["raw_cohort"]["selector"]
            assert selector.get("operator") == "or"
        finally:
            ws.close()

    def test_any_of_has_correct_number_of_children(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """CohortDefinition.any_of selector has one child per criterion."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        cohort = CohortDefinition.any_of(
            CohortCriteria.did_event("Purchase", at_least=1, within_days=30),
            CohortCriteria.has_property("plan", "premium"),
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", cohort=cohort, limit=1)

            call_kwargs = mock_api_client.export_profiles_page.call_args
            fbc = json.loads(call_kwargs.kwargs["filter_by_cohort"])
            selector = fbc["raw_cohort"]["selector"]
            assert len(selector.get("children", [])) == 2
        finally:
            ws.close()

    def test_any_of_routes_to_raw_cohort_not_id(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """CohortDefinition.any_of uses raw_cohort key, not id key."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        cohort = CohortDefinition.any_of(
            CohortCriteria.did_event("Signup", at_least=1, within_days=7),
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", cohort=cohort, limit=1)

            call_kwargs = mock_api_client.export_profiles_page.call_args
            fbc = json.loads(call_kwargs.kwargs["filter_by_cohort"])
            assert "raw_cohort" in fbc
            assert "id" not in fbc
        finally:
            ws.close()


class TestBehavioralFilteringSavedCohort:
    """Tests for saved cohort by ID routing to filter_by_cohort with id."""

    def test_int_cohort_routes_to_id(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """cohort=12345 sets filter_by_cohort with id key."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", cohort=12345, limit=1)

            call_kwargs = mock_api_client.export_profiles_page.call_args
            fbc_raw = call_kwargs.kwargs.get("filter_by_cohort")
            assert fbc_raw is not None

            fbc = json.loads(fbc_raw)
            assert fbc == {"id": 12345}
        finally:
            ws.close()

    def test_int_cohort_has_no_raw_cohort_key(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """cohort=int uses id key only, no raw_cohort key."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", cohort=99999, limit=1)

            call_kwargs = mock_api_client.export_profiles_page.call_args
            fbc = json.loads(call_kwargs.kwargs["filter_by_cohort"])
            assert "raw_cohort" not in fbc
        finally:
            ws.close()

    def test_int_cohort_sets_include_all_users(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """When cohort is provided, include_all_users is sent to the API."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", cohort=12345, limit=1)

            call_kwargs = mock_api_client.export_profiles_page.call_args
            assert "include_all_users" in call_kwargs.kwargs
        finally:
            ws.close()


class TestBehavioralFilteringCombinedCohortAndWhere:
    """Tests for combined cohort + where filters working together."""

    def test_cohort_plus_where_filter_both_applied(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """cohort + where=Filter.equals() sends both filter_by_cohort and where selector."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(
                mode="profiles",
                cohort=12345,
                where=Filter.equals("plan", "premium", resource_type="people"),
                limit=1,
            )

            call_kwargs = mock_api_client.export_profiles_page.call_args
            # Both filter_by_cohort and where should be set
            assert call_kwargs.kwargs.get("filter_by_cohort") is not None
            assert call_kwargs.kwargs.get("where") is not None
        finally:
            ws.close()

    def test_cohort_definition_plus_where_filter_both_applied(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """CohortDefinition + where=Filter sends both raw_cohort and where selector."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        cohort = CohortDefinition.all_of(
            CohortCriteria.did_event("Purchase", at_least=1, within_days=30),
        )

        ws = workspace_factory()
        try:
            ws.query_user(
                mode="profiles",
                cohort=cohort,
                where=Filter.equals("plan", "premium", resource_type="people"),
                limit=1,
            )

            call_kwargs = mock_api_client.export_profiles_page.call_args
            fbc = json.loads(call_kwargs.kwargs["filter_by_cohort"])
            assert "raw_cohort" in fbc
            assert call_kwargs.kwargs.get("where") is not None
        finally:
            ws.close()

    def test_cohort_plus_multiple_where_filters(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """cohort + list of where Filters sends filter_by_cohort and combined where selector."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(
                mode="profiles",
                cohort=12345,
                where=[
                    Filter.equals("plan", "premium", resource_type="people"),
                    Filter.greater_than("revenue", 100, resource_type="people"),
                ],
                limit=1,
            )

            call_kwargs = mock_api_client.export_profiles_page.call_args
            assert call_kwargs.kwargs.get("filter_by_cohort") is not None
            assert call_kwargs.kwargs.get("where") is not None
        finally:
            ws.close()


class TestBehavioralFilteringCohortPlusInCohortError:
    """Tests for cohort + Filter.in_cohort() producing validation error U2."""

    def test_cohort_param_plus_in_cohort_filter_raises_u2(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Using both cohort= param and Filter.in_cohort() in where raises U2."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="profiles",
                    cohort=12345,
                    where=Filter.in_cohort(67890),
                    limit=1,
                )

            error_codes = [e.code for e in exc_info.value.errors]
            assert "U2" in error_codes
        finally:
            ws.close()

    def test_cohort_definition_plus_in_cohort_filter_raises_u2(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Using CohortDefinition + Filter.in_cohort() in where raises U2."""
        cohort = CohortDefinition.all_of(
            CohortCriteria.did_event("Purchase", at_least=1, within_days=30),
        )

        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="profiles",
                    cohort=cohort,
                    where=Filter.in_cohort(67890),
                    limit=1,
                )

            error_codes = [e.code for e in exc_info.value.errors]
            assert "U2" in error_codes
        finally:
            ws.close()

    def test_u2_error_message_mentions_mutually_exclusive(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """U2 error message explains that cohort and in_cohort are mutually exclusive."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_user(
                    mode="profiles",
                    cohort=12345,
                    where=Filter.in_cohort(67890),
                    limit=1,
                )

            u2_errors = [e for e in exc_info.value.errors if e.code == "U2"]
            assert len(u2_errors) == 1
            assert "mutually exclusive" in u2_errors[0].message.lower()
        finally:
            ws.close()


class TestBehavioralFilteringCohortSerializationError:
    """Tests for CohortDefinition serialization failure producing U24."""

    def test_cohort_to_dict_failure_raises_u24(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """CohortDefinition whose to_dict() raises produces validation error U24."""
        broken_cohort = CohortDefinition.all_of(
            CohortCriteria.did_event("Purchase", at_least=1, within_days=30),
        )

        # Patch to_dict to simulate a serialization failure
        with patch.object(
            CohortDefinition,
            "to_dict",
            side_effect=RuntimeError("serialization failed"),
        ):
            ws = workspace_factory()
            try:
                with pytest.raises(BookmarkValidationError) as exc_info:
                    ws.query_user(mode="profiles", cohort=broken_cohort, limit=1)

                error_codes = [e.code for e in exc_info.value.errors]
                assert "U24" in error_codes
            finally:
                ws.close()

    def test_u24_error_message_contains_exception_detail(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """U24 error message includes the underlying exception message."""
        broken_cohort = CohortDefinition.all_of(
            CohortCriteria.did_event("Signup", at_least=1, within_days=7),
        )

        with patch.object(
            CohortDefinition,
            "to_dict",
            side_effect=ValueError("bad selector node"),
        ):
            ws = workspace_factory()
            try:
                with pytest.raises(BookmarkValidationError) as exc_info:
                    ws.query_user(mode="profiles", cohort=broken_cohort, limit=1)

                u24_errors = [e for e in exc_info.value.errors if e.code == "U24"]
                assert len(u24_errors) == 1
                assert "bad selector node" in u24_errors[0].message
            finally:
                ws.close()


# =============================================================================
# T024: Cross-engine composition tests (US5)
# =============================================================================


class TestCrossEngineDistinctIds:
    """Tests for result.distinct_ids returning a list usable for downstream operations."""

    def test_distinct_ids_returns_list_of_strings(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """result.distinct_ids is a list[str] from profile results."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM, RAW_PROFILE_FREE, RAW_PROFILE_ENTERPRISE],
            total=3,
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", limit=3)

            ids = result.distinct_ids
            assert isinstance(ids, list)
            assert all(isinstance(i, str) for i in ids)
            assert ids == ["user_001", "user_002", "user_003"]
        finally:
            ws.close()

    def test_distinct_ids_usable_for_subsequent_query(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """distinct_ids from one query can be passed to a subsequent query_user(distinct_ids=)."""
        # First query returns some profiles
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM, RAW_PROFILE_ENTERPRISE],
            total=2,
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result1 = ws.query_user(mode="profiles", limit=2)
            ids = result1.distinct_ids

            # Second query uses those IDs
            mock_api_client.export_profiles_page.return_value = _make_page_result(
                profiles=[RAW_PROFILE_PREMIUM, RAW_PROFILE_ENTERPRISE],
                total=2,
                has_more=False,
            )
            result2 = ws.query_user(mode="profiles", distinct_ids=ids, limit=100_000)

            assert len(result2.profiles) == 2
            assert result2.distinct_ids == ids
        finally:
            ws.close()

    def test_distinct_ids_empty_for_empty_result(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Empty result returns empty distinct_ids list."""
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
            assert isinstance(result.distinct_ids, list)
        finally:
            ws.close()

    def test_distinct_ids_length_matches_profiles(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """distinct_ids length equals number of returned profiles."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM, RAW_PROFILE_FREE],
            total=100,
            has_more=True,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", limit=2)

            assert len(result.distinct_ids) == len(result.profiles)
        finally:
            ws.close()


class TestCrossEngineDataFrameComposition:
    """Tests for result.df composing with pandas operations."""

    def test_df_supports_groupby(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """result.df can be grouped by a property column."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[
                RAW_PROFILE_PREMIUM,
                RAW_PROFILE_FREE,
                RAW_PROFILE_ENTERPRISE,
                RAW_PROFILE_PREMIUM_2,
            ],
            total=4,
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", limit=4)

            df = result.df
            grouped = df.groupby("plan").size()
            assert grouped["premium"] == 2
            assert grouped["free"] == 1
            assert grouped["enterprise"] == 1
        finally:
            ws.close()

    def test_df_supports_describe(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """result.df supports pandas describe() for numeric summaries."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[
                RAW_PROFILE_PREMIUM,
                RAW_PROFILE_FREE,
                RAW_PROFILE_ENTERPRISE,
            ],
            total=3,
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", limit=3)

            df = result.df
            desc = df["revenue"].describe()
            assert desc["count"] == 3
            assert desc["min"] == 0.0
            assert desc["max"] == 500.0
        finally:
            ws.close()

    def test_df_supports_merge_with_external_data(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """result.df can be merged with an external DataFrame on distinct_id."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM, RAW_PROFILE_FREE],
            total=2,
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", limit=2)

            # Simulate external data (e.g., from a funnel result)
            external_df = pd.DataFrame(
                {
                    "distinct_id": ["user_001", "user_002"],
                    "converted": [True, False],
                }
            )

            merged = result.df.merge(external_df, on="distinct_id")
            assert len(merged) == 2
            assert "converted" in merged.columns
            assert (
                bool(
                    merged.loc[merged["distinct_id"] == "user_001", "converted"].iloc[0]
                )
                is True
            )
        finally:
            ws.close()

    def test_df_supports_filtering(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """result.df supports boolean indexing for filtering rows."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[
                RAW_PROFILE_PREMIUM,
                RAW_PROFILE_FREE,
                RAW_PROFILE_ENTERPRISE,
            ],
            total=3,
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", limit=3)

            df = result.df
            premium_users = df[df["plan"] == "premium"]
            assert len(premium_users) == 1
            assert premium_users.iloc[0]["distinct_id"] == "user_001"
        finally:
            ws.close()

    def test_df_is_pandas_dataframe(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """result.df returns a proper pandas DataFrame instance."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles")

            assert isinstance(result.df, pd.DataFrame)
        finally:
            ws.close()


class TestCrossEngineFilterConsistency:
    """Tests for Filter objects working identically across query() and query_user()."""

    def test_filter_equals_accepted_by_query_user(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Filter.equals() can be passed to query_user(where=) without error."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="profiles",
                where=Filter.equals("plan", "premium", resource_type="people"),
                limit=1,
            )

            assert isinstance(result, UserQueryResult)
            assert len(result.profiles) == 1
        finally:
            ws.close()

    def test_filter_list_accepted_by_query_user(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """A list of Filters can be passed to query_user(where=) without error."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="profiles",
                where=[
                    Filter.equals("plan", "premium", resource_type="people"),
                    Filter.greater_than("revenue", 100, resource_type="people"),
                ],
                limit=1,
            )

            assert isinstance(result, UserQueryResult)
        finally:
            ws.close()

    def test_filter_equals_accepted_by_build_user_params(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Filter.equals() is valid syntax for build_user_params(where=)."""
        ws = workspace_factory()
        try:
            params = ws.build_user_params(
                where=Filter.equals("plan", "premium", resource_type="people"),
            )

            assert isinstance(params, dict)
            assert "where" in params
        finally:
            ws.close()

    def test_filter_list_accepted_by_build_user_params(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """A list of Filters is valid syntax for build_user_params(where=)."""
        ws = workspace_factory()
        try:
            params = ws.build_user_params(
                where=[
                    Filter.equals("plan", "premium", resource_type="people"),
                    Filter.greater_than("revenue", 100, resource_type="people"),
                ],
            )

            assert isinstance(params, dict)
            assert "where" in params
        finally:
            ws.close()

    def test_filter_produces_where_selector_string(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Filter objects produce a where selector string in the API call."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(
                mode="profiles",
                where=Filter.equals("plan", "premium", resource_type="people"),
                limit=1,
            )

            call_kwargs = mock_api_client.export_profiles_page.call_args
            where_val = call_kwargs.kwargs.get("where")
            assert isinstance(where_val, str)
            assert "plan" in where_val
        finally:
            ws.close()


class TestCrossEngineCohortIdFromFunnel:
    """Tests for cohort ID from funnel analysis working as query_user(cohort=ID)."""

    def test_funnel_cohort_id_as_query_user_cohort(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """A cohort ID (simulating output from funnel analysis) works with query_user()."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM, RAW_PROFILE_FREE],
            total=2,
            has_more=False,
        )

        # Simulate a cohort ID obtained from funnel analysis
        funnel_cohort_id = 42

        ws = workspace_factory()
        try:
            result = ws.query_user(
                mode="profiles", cohort=funnel_cohort_id, limit=100_000
            )

            assert isinstance(result, UserQueryResult)
            assert len(result.profiles) == 2

            call_kwargs = mock_api_client.export_profiles_page.call_args
            fbc = json.loads(call_kwargs.kwargs["filter_by_cohort"])
            assert fbc == {"id": 42}
        finally:
            ws.close()

    def test_cohort_id_result_has_composable_distinct_ids(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Result from cohort-filtered query has distinct_ids for downstream use."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM, RAW_PROFILE_ENTERPRISE],
            total=2,
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", cohort=42, limit=100_000)

            ids = result.distinct_ids
            assert len(ids) == 2
            assert "user_001" in ids
            assert "user_003" in ids
        finally:
            ws.close()

    def test_cohort_id_result_df_supports_analysis(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """Result from cohort-filtered query has a DataFrame supporting analysis."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM, RAW_PROFILE_ENTERPRISE],
            total=2,
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", cohort=42, limit=100_000)

            df = result.df
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            total_revenue = df["revenue"].sum()
            assert total_revenue == 650.0
        finally:
            ws.close()

    def test_cohort_id_include_all_users_false_by_default(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,  # noqa: ARG002
    ) -> None:
        """include_all_users defaults to False when filtering by cohort ID."""
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[RAW_PROFILE_PREMIUM],
            total=1,
        )

        ws = workspace_factory()
        try:
            ws.query_user(mode="profiles", cohort=42, limit=1)

            call_kwargs = mock_api_client.export_profiles_page.call_args
            assert call_kwargs.kwargs.get("include_all_users") is False
        finally:
            ws.close()
