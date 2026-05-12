"""Structural/behavioral correctness and PBT edge case tests for query_user().

Tiers 4 and 5 from the QA plan: behavioral correctness of parallel page
ordering, fallback paths, aggregate computed_at semantics, credential
check ordering, plus property-based and edge-case tests for filter
translation, profile transformation, and DataFrame construction.

These tests document existing behavior (including known hazards) and
verify structural invariants that example-based tests do not cover.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless._internal.query.user_builders import (
    _format_value,
    filters_to_selector,
)
from mixpanel_headless._internal.transforms import transform_profile
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
        start_index: Starting index for user IDs (user_000, user_001, ...).
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
# TIER 4: Structural / Behavioral Correctness
# =============================================================================


class TestParallelPageOrderingPreserved:
    """T4.01: Verify profiles appear in page order despite out-of-order completion."""

    def test_parallel_page_ordering_preserved_across_futures(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Profiles from parallel pages are assembled in page order.

        The parallel path uses sorted(page_results.keys()) to ensure
        profiles from page 0 come first, page 1 second, etc., regardless
        of the order in which futures complete.
        """
        total = 500
        page_size = 100
        num_pages = math.ceil(total / page_size)  # 5

        # Track call order to verify pages are requested
        call_order: list[int] = []

        def _side_effect(
            *_args: Any,
            page: int = 0,
            **_kwargs: Any,
        ) -> ProfilePageResult:
            """Return page results, tracking call order.

            Args:
                *_args: Ignored positional args.
                page: Zero-based page index.
                **_kwargs: Ignored keyword args.

            Returns:
                ProfilePageResult for the requested page.
            """
            call_order.append(page)
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
                session_id="sess_order",
                has_more=has_more,
            )

        mock_api_client.export_profiles_page.side_effect = _side_effect

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            # Verify profiles are in page order: user_000..user_099 (page 0),
            # user_100..user_199 (page 1), etc.
            for i, profile in enumerate(result.profiles):
                expected_id = f"user_{i:03d}"
                assert profile["distinct_id"] == expected_id, (
                    f"Profile at index {i} should be {expected_id}, "
                    f"got {profile['distinct_id']}"
                )
        finally:
            ws.close()


class TestParallelLimit1FallsBackToSequential:
    """T4.02: parallel=True with limit=1 falls back to sequential path."""

    def test_parallel_limit_1_falls_back_to_sequential(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """limit=1 with parallel=True uses sequential path.

        The code at workspace.py:9074 checks ``if parallel and limit != 1``
        so limit=1 always takes the sequential path, which sets
        ``meta["parallel"] = False``.
        """
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=[_make_raw_profile("user_solo", plan="premium")],
            total=5000,
            page_size=1000,
            has_more=True,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=1)

            assert result.meta["parallel"] is False
            assert len(result.profiles) == 1
            # Only one API call should have been made
            assert mock_api_client.export_profiles_page.call_count == 1
        finally:
            ws.close()


class TestParallelPageSizeZeroFallback:
    """T4.04: page_size=0 from API falls back to 1000, no ZeroDivisionError."""

    def test_parallel_page_size_zero_fallback(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """page_size=0 from API is guarded by ``or 1000`` fallback.

        The code at workspace.py:9290 has ``page0.page_size or 1000``
        which prevents ZeroDivisionError when computing pages_needed.
        """
        profiles = _make_profiles_batch(0, 5)
        mock_api_client.export_profiles_page.return_value = _make_page_result(
            profiles=profiles,
            page=0,
            total=5,
            page_size=0,  # Pathological value
            session_id="sess_zero",
            has_more=False,
        )

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            # Should not raise ZeroDivisionError
            assert len(result.profiles) == 5
        finally:
            ws.close()


class TestParallelPageSizeNoneFallback:
    """T4.05: page_size=None from API falls back to 1000."""

    def test_parallel_page_size_none_fallback(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """page_size=None from API is guarded by ``or 1000`` fallback.

        The ``or 1000`` guard at workspace.py:9290 handles both 0 and
        None since both are falsy.
        """
        profiles = _make_profiles_batch(0, 3)

        # ProfilePageResult with page_size=None requires constructing
        # with a valid int, so we mock the attribute directly
        page_result = _make_page_result(
            profiles=profiles,
            page=0,
            total=3,
            page_size=1000,  # Placeholder
            session_id="sess_none_ps",
            has_more=False,
        )
        # Override page_size to None to simulate the edge case
        object.__setattr__(page_result, "page_size", None)

        mock_api_client.export_profiles_page.return_value = page_result

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="profiles", parallel=True, limit=100_000)

            # Should not crash
            assert len(result.profiles) == 3
        finally:
            ws.close()


class TestAggregateComputedAtFromAPI:
    """T4.06: computed_at from API response is used when present."""

    def test_aggregate_computed_at_from_api_preferred(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """When API returns computed_at, the result uses that value.

        The aggregate path uses ``response.get("computed_at", fallback)``
        so the API value takes precedence over a local timestamp.
        """
        mock_api_client.engage_stats.return_value = {
            "results": 42,
            "status": "ok",
            "computed_at": "2025-01-01T00:00:00Z",
        }

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="aggregate")

            assert result.computed_at == "2025-01-01T00:00:00Z"
        finally:
            ws.close()


class TestAggregateComputedAtFallback:
    """T4.07: computed_at falls back to local timestamp when API omits it."""

    def test_aggregate_computed_at_fallback_when_api_omits(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """When API response lacks computed_at, a local ISO timestamp is used.

        The code at workspace.py uses ``response.get("computed_at",
        datetime.now(timezone.utc).isoformat())`` as fallback.
        """
        mock_api_client.engage_stats.return_value = {
            "results": 42,
            "status": "ok",
            # No "computed_at" key
        }

        ws = workspace_factory()
        try:
            result = ws.query_user(mode="aggregate")

            assert isinstance(result.computed_at, str)
            assert len(result.computed_at) > 0
            # Should look like an ISO timestamp (contains T separator)
            assert "T" in result.computed_at
        finally:
            ws.close()


# TestCredentialCheckBeforeValidation removed in B1 (Fix 10):
# Workspace.__init__ now always populates ``_credentials`` via the v3
# session shim, so the "no credentials" branch can no longer fire.


# =============================================================================
# TIER 5: Edge Cases & PBT
# =============================================================================


class TestPbtFormatValueSpecialChars:
    """T5.01: _format_value never crashes on special characters."""

    @given(
        s=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "S", "Z"),
                whitelist_characters='"\\' + "\n\r\0",
            ),
            min_size=0,
            max_size=50,
        ),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_pbt_format_value_special_chars_never_crash(self, s: str) -> None:
        """_format_value(s) always returns a quoted string for any input.

        Strings containing double quotes, backslashes, newlines, null
        bytes, and emoji are all valid inputs. The result must always
        start and end with a double quote character.
        """
        result = _format_value(s)
        assert isinstance(result, str)
        assert result.startswith('"')
        assert result.endswith('"')

    @given(s=st.text(min_size=0, max_size=100))
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_pbt_format_value_arbitrary_text_never_crash(self, s: str) -> None:
        """_format_value handles arbitrary Unicode text without crashing.

        This broader strategy exercises the full Unicode range.
        """
        result = _format_value(s)
        assert isinstance(result, str)
        assert result.startswith('"')
        assert result.endswith('"')


class TestFiltersToSelectorOrAndPrecedence:
    """T5.02: OR/AND precedence with parenthesized multi-value equals."""

    def test_filters_to_selector_or_and_precedence(self) -> None:
        """Multi-value equals combined with AND produces correct precedence.

        ``Filter.equals("plan", ["free", "trial"])`` translates to
        ``(properties["plan"] == "free" or properties["plan"] == "trial")``.

        Combined with ``Filter.is_set("email")`` via AND, the result is:
        ``(...) and defined(...)``

        The parentheses ensure correct semantics:
        ``("free" OR "trial") AND has email``
        """
        f1 = Filter.equals("plan", ["free", "trial"])
        f2 = Filter.is_set("email")

        result = filters_to_selector([f1, f2])

        # OR clause is wrapped in parentheses for correct precedence
        expected = (
            '(properties["plan"] == "free" or '
            'properties["plan"] == "trial") and '
            'defined(properties["email"])'
        )
        assert result == expected, (
            f"Expected exact selector string:\n  {expected}\nGot:\n  {result}"
        )


class TestTransformProfileMissingDistinctId:
    """T5.03: transform_profile with missing $distinct_id."""

    def test_transform_profile_missing_distinct_id(self) -> None:
        """Profile without $distinct_id gets empty string as distinct_id.

        The code uses ``profile.get("$distinct_id", "")`` so a missing
        key produces an empty string, not a KeyError.
        """
        raw = {"$properties": {"plan": "free"}}
        result = transform_profile(raw)

        assert result["distinct_id"] == ""
        assert result["last_seen"] is None
        assert result["properties"] == {"plan": "free"}


class TestTransformProfileCompletelyEmpty:
    """T5.04: transform_profile with completely empty dict."""

    def test_transform_profile_completely_empty(self) -> None:
        """Empty dict produces a valid normalized profile with defaults.

        Missing $distinct_id defaults to empty string, missing
        $properties defaults to empty dict, missing $last_seen
        defaults to None.
        """
        result = transform_profile({})

        assert result["distinct_id"] == ""
        assert result["last_seen"] is None
        assert result["properties"] == {}


class TestDfProfilesVaryingPropertySetsUnionColumns:
    """T5.05: DataFrame has union of all property columns across profiles."""

    def test_df_profiles_varying_property_sets_union_columns(self) -> None:
        """Profiles with different property sets produce union of all columns.

        Profile 1 has ``{"a": 1}``, profile 2 has ``{"b": 2}``, profile 3
        has ``{"a": 3, "c": 4}``. The DataFrame should have columns
        ``["distinct_id", "last_seen", "a", "b", "c"]`` with NaN for
        missing values.
        """
        profiles = [
            {
                "distinct_id": "user_1",
                "last_seen": "2025-01-01T00:00:00",
                "properties": {"a": 1},
            },
            {
                "distinct_id": "user_2",
                "last_seen": "2025-01-02T00:00:00",
                "properties": {"b": 2},
            },
            {
                "distinct_id": "user_3",
                "last_seen": "2025-01-03T00:00:00",
                "properties": {"a": 3, "c": 4},
            },
        ]
        result = UserQueryResult(
            computed_at="2025-01-15T10:00:00",
            total=3,
            profiles=profiles,
            params={},
            meta={},
            mode="profiles",
            aggregate_data=None,
        )
        df = result.df

        # All property columns should be present
        assert set(df.columns) == {"distinct_id", "last_seen", "a", "b", "c"}

        # Column order: distinct_id, last_seen, then alphabetical
        assert list(df.columns) == ["distinct_id", "last_seen", "a", "b", "c"]

        # Missing values should be NaN
        assert pd.isna(df.loc[df["distinct_id"] == "user_1", "b"].iloc[0])
        assert pd.isna(df.loc[df["distinct_id"] == "user_1", "c"].iloc[0])
        assert pd.isna(df.loc[df["distinct_id"] == "user_2", "a"].iloc[0])
        assert pd.isna(df.loc[df["distinct_id"] == "user_2", "c"].iloc[0])
        assert pd.isna(df.loc[df["distinct_id"] == "user_3", "b"].iloc[0])

        # Present values should be correct
        assert df.loc[df["distinct_id"] == "user_1", "a"].iloc[0] == 1
        assert df.loc[df["distinct_id"] == "user_2", "b"].iloc[0] == 2
        assert df.loc[df["distinct_id"] == "user_3", "a"].iloc[0] == 3
        assert df.loc[df["distinct_id"] == "user_3", "c"].iloc[0] == 4


class TestDfPropertyNamedDistinctIdCollision:
    """T5.06: Property named 'distinct_id' overwrites top-level distinct_id."""

    def test_df_property_named_distinct_id_collision(self) -> None:
        """Property 'distinct_id' in properties dict overwrites top-level value.

        In _build_profiles_df (types.py:10770-10772), the code first sets
        ``row["distinct_id"]`` from the top-level profile key, then
        iterates over properties and overwrites it if a ``distinct_id``
        key exists in properties.

        This documents a data collision hazard: the property value wins
        over the top-level distinct_id.
        """
        profiles = [
            {
                "distinct_id": "real_id",
                "last_seen": "2025-01-01T00:00:00",
                "properties": {"distinct_id": "collision_id", "plan": "free"},
            },
        ]
        result = UserQueryResult(
            computed_at="2025-01-15T10:00:00",
            total=1,
            profiles=profiles,
            params={},
            meta={},
            mode="profiles",
            aggregate_data=None,
        )
        df = result.df

        # The property value overwrites the top-level distinct_id
        # because _build_profiles_df iterates properties AFTER setting
        # the top-level distinct_id
        actual_id = df["distinct_id"].iloc[0]
        assert actual_id == "collision_id", (
            f"Expected property 'distinct_id' to overwrite top-level, "
            f"but got {actual_id!r}. "
            f"If this fails, the collision behavior has changed."
        )
