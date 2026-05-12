# ruff: noqa: S101
"""Live QA tests for query_user() against the real Mixpanel Engage API.

Exercises every ``query_user()`` code path against the active Mixpanel
project.  All tests are **read-only** — no profiles are created, updated,
or deleted.

Usage:
    uv run pytest tests/live/test_live_query_user.py -v -m live
    uv run pytest tests/live/test_live_query_user.py -v -m live -k profiles
    uv run pytest tests/live/test_live_query_user.py -v -m live -k aggregate

Pre-requisites:
    - Active OAuth token: ``mp account login NAME``
    - Project switched to target project with profiles
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from mixpanel_headless import (
    BookmarkValidationError,
    Filter,
    Workspace,
)
from mixpanel_headless.types import UserQueryResult

# All tests require the `live` marker — skipped by default
pytestmark = pytest.mark.live


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def ws() -> Iterator[Workspace]:
    """Live Workspace connected to the active project.

    Yields:
        Workspace instance using default credentials.
    """
    workspace = Workspace()
    yield workspace
    workspace.close()


# =============================================================================
# CATEGORY 1: Bug Verification (3 tests)
# =============================================================================


class TestBugVerification:
    """Tests that verify discovered bugs are fixed."""

    def test_sort_by_does_not_raise_query_error(self, ws: Workspace) -> None:
        """L1.01 — sort_by with $last_seen must not raise a QueryError.

        The sort_key must be passed to the API in wrapped format
        (``properties["$last_seen"]``), not raw ``$last_seen``.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(
            mode="profiles",
            sort_by="$last_seen",
            sort_order="descending",
            limit=3,
        )
        assert result.total > 0
        assert len(result.profiles) == 3

    def test_sort_by_parallel_matches_sequential(self, ws: Workspace) -> None:
        """L1.02 — parallel and sequential paths return same profiles for sort_by.

        Both code paths must send sort_key in the same format so
        results are consistent.

        Args:
            ws: Workspace fixture.
        """
        common_kwargs = {
            "mode": "profiles",
            "sort_by": "$last_seen",
            "sort_order": "descending",
            "limit": 5,
        }
        seq = ws.query_user(parallel=False, **common_kwargs)  # type: ignore[arg-type]
        par = ws.query_user(parallel=True, **common_kwargs)  # type: ignore[arg-type]

        # Both should return same total and same number of profiles.
        # Exact profile ordering may differ between API sessions.
        assert seq.total == par.total
        assert len(seq.profiles) == len(par.profiles)

    def test_aggregate_count_returns_value(self, ws: Workspace) -> None:
        """L1.03 — aggregate mode returns an integer count without error.

        The engage_stats endpoint must use the correct URL path
        (``/engage/stats``) and not send rejected parameters.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(mode="aggregate")
        assert result.mode == "aggregate"
        assert result.value is not None
        assert isinstance(result.value, int)
        assert result.value > 0


# =============================================================================
# CATEGORY 2: Profiles Mode — Core (8 tests)
# =============================================================================


class TestProfilesCore:
    """Core profiles-mode queries."""

    def test_default_limit_one_returns_single_profile(self, ws: Workspace) -> None:
        """L2.01 — default query returns 1 profile with total == 1.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(mode="profiles")
        assert len(result.profiles) == 1
        assert result.total == len(result.profiles)
        assert result.mode == "profiles"

    def test_explicit_limit_returns_exact_count(self, ws: Workspace) -> None:
        """L2.02 — explicit limit=10 returns exactly 10 profiles.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(mode="profiles", limit=10)
        assert len(result.profiles) == 10
        assert result.total == len(result.profiles)

    def test_filter_is_set_reduces_total(self, ws: Workspace) -> None:
        """L2.03 — filtering by is_set($email) returns fewer profiles than unfiltered.

        Uses aggregate mode to compare full population counts, since
        profiles mode total equals len(profiles) which is capped by limit.

        Args:
            ws: Workspace fixture.
        """
        unfiltered = ws.query_user(mode="aggregate")
        filtered = ws.query_user(mode="aggregate", where=Filter.is_set("$email"))
        assert filtered.value is not None
        assert unfiltered.value is not None
        assert filtered.value < unfiltered.value

    def test_filter_equals_returns_matching_profiles(self, ws: Workspace) -> None:
        """L2.04 — equals filter returns profiles with matching property values.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(
            mode="profiles",
            where=Filter.equals("$browser", "Chrome"),
            properties=["$browser"],
            limit=5,
        )
        assert result.total > 0
        for profile in result.profiles:
            props = profile.get("properties", {})
            assert props.get("$browser") == "Chrome"

    def test_properties_selection_limits_columns(self, ws: Workspace) -> None:
        """L2.05 — requesting specific properties limits DataFrame columns.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(mode="profiles", properties=["$email", "$name"], limit=3)
        cols = set(result.df.columns)
        expected = {"distinct_id", "last_seen", "email", "name"}
        assert cols == expected

    def test_search_returns_relevant_results(self, ws: Workspace) -> None:
        """L2.06 — search for 'mixpanel.com' returns profiles with matching data.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(
            mode="profiles",
            search="mixpanel.com",
            properties=["$email"],
            limit=10,
        )
        assert result.total > 0
        # At least one profile should have mixpanel in the email
        emails = [
            p.get("properties", {}).get("$email", "")
            for p in result.profiles
            if p.get("properties", {}).get("$email")
        ]
        assert any("mixpanel" in (e or "").lower() for e in emails)

    def test_distinct_id_lookup_returns_one_profile(self, ws: Workspace) -> None:
        """L2.07 — looking up a known distinct_id returns exactly that profile.

        Args:
            ws: Workspace fixture.
        """
        # First get a distinct_id to look up
        seed = ws.query_user(mode="profiles", limit=1)
        known_id = seed.distinct_ids[0]

        result = ws.query_user(mode="profiles", distinct_id=known_id)
        assert len(result.profiles) == 1
        assert result.distinct_ids[0] == known_id

    def test_distinct_ids_batch_lookup(self, ws: Workspace) -> None:
        """L2.08 — batch lookup by multiple distinct_ids returns all of them.

        Args:
            ws: Workspace fixture.
        """
        seed = ws.query_user(mode="profiles", limit=3)
        ids = seed.distinct_ids
        assert len(ids) == 3

        result = ws.query_user(mode="profiles", distinct_ids=ids, limit=len(ids))
        assert set(result.distinct_ids) == set(ids)


# =============================================================================
# CATEGORY 3: Profiles Mode — Sorting (3 tests)
# =============================================================================


class TestProfilesSorting:
    """Sorting behaviour in profiles mode."""

    def test_sort_by_last_seen_descending(self, ws: Workspace) -> None:
        """L3.01 — sort_by $last_seen descending returns most-recent first.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(
            mode="profiles",
            sort_by="$last_seen",
            sort_order="descending",
            limit=10,
        )
        dates = result.df["last_seen"].tolist()
        # Each date should be >= the next (descending)
        for i in range(len(dates) - 1):
            if dates[i] is not None and dates[i + 1] is not None:
                assert dates[i] >= dates[i + 1]

    def test_sort_by_ascending(self, ws: Workspace) -> None:
        """L3.02 — sort_by $last_seen ascending returns oldest first.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(
            mode="profiles",
            sort_by="$last_seen",
            sort_order="ascending",
            limit=10,
        )
        dates = result.df["last_seen"].tolist()
        for i in range(len(dates) - 1):
            if dates[i] is not None and dates[i + 1] is not None:
                assert dates[i] <= dates[i + 1]

    def test_sort_by_custom_property(self, ws: Workspace) -> None:
        """L3.03 — sort_by $email ascending returns alphabetical order.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(
            mode="profiles",
            sort_by="$email",
            sort_order="ascending",
            where=Filter.is_set("$email"),
            properties=["$email"],
            limit=10,
        )
        emails = result.df["email"].tolist()
        for i in range(len(emails) - 1):
            if emails[i] is not None and emails[i + 1] is not None:
                assert emails[i] <= emails[i + 1]


# =============================================================================
# CATEGORY 4: Cohort Filtering (3 tests)
# =============================================================================


class TestCohortFiltering:
    """Filtering by saved cohort ID."""

    @pytest.fixture(scope="class")
    def cohort_id(self, ws: Workspace) -> int:
        """Get the first available cohort ID.

        Args:
            ws: Workspace fixture.

        Returns:
            Integer cohort ID.
        """
        cohorts = ws.cohorts()
        assert len(cohorts) > 0, "No cohorts in project"
        return cohorts[0].id

    def test_saved_cohort_by_id(self, ws: Workspace, cohort_id: int) -> None:
        """L4.01 — filtering by saved cohort ID returns profiles.

        Args:
            ws: Workspace fixture.
            cohort_id: First available cohort ID.
        """
        result = ws.query_user(cohort=cohort_id, limit=5)
        assert result.total > 0

    def test_saved_cohort_reduces_total(self, ws: Workspace, cohort_id: int) -> None:
        """L4.02 — cohort filter total is <= unfiltered total.

        Args:
            ws: Workspace fixture.
            cohort_id: First available cohort ID.
        """
        unfiltered = ws.query_user()
        cohort_filtered = ws.query_user(cohort=cohort_id, limit=1)
        assert cohort_filtered.total <= unfiltered.total

    def test_cohort_plus_where_filter(self, ws: Workspace, cohort_id: int) -> None:
        """L4.03 — combining cohort + where filter narrows results further.

        Args:
            ws: Workspace fixture.
            cohort_id: First available cohort ID.
        """
        cohort_only = ws.query_user(cohort=cohort_id, limit=1)
        combined = ws.query_user(
            cohort=cohort_id,
            where=Filter.is_set("$email"),
            limit=1,
        )
        assert combined.total <= cohort_only.total


# =============================================================================
# CATEGORY 5: Parallel Fetching (4 tests)
# =============================================================================


class TestParallelFetching:
    """Parallel pagination mode."""

    def test_parallel_returns_same_total_as_sequential(self, ws: Workspace) -> None:
        """L5.01 — parallel and sequential modes report the same total.

        Args:
            ws: Workspace fixture.
        """
        seq = ws.query_user(mode="profiles", limit=100, parallel=False)
        par = ws.query_user(mode="profiles", limit=100, parallel=True)
        assert seq.total == par.total

    def test_parallel_large_fetch(self, ws: Workspace) -> None:
        """L5.02 — parallel fetch of 3000 profiles returns all of them.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(mode="profiles", limit=3000, parallel=True, workers=3)
        assert len(result.profiles) == 3000
        assert result.meta.get("parallel") is True
        assert result.meta.get("pages_fetched", 0) >= 3

    def test_parallel_metadata_complete(self, ws: Workspace) -> None:
        """L5.03 — parallel result metadata contains all expected keys.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(mode="profiles", limit=2000, parallel=True, workers=5)
        meta = result.meta
        assert "session_id" in meta
        assert "pages_fetched" in meta
        assert "failed_pages" in meta
        assert "parallel" in meta
        assert "workers" in meta

    def test_parallel_limit_1_uses_sequential(self, ws: Workspace) -> None:
        """L5.04 — parallel=True with limit=1 falls back to sequential.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(mode="profiles", parallel=True, limit=1)
        assert result.meta.get("parallel") is False
        assert len(result.profiles) == 1


# =============================================================================
# CATEGORY 6: Aggregate Mode (4 tests)
# =============================================================================


class TestAggregateMode:
    """Aggregate mode queries via engage_stats."""

    def test_aggregate_count_all_profiles(self, ws: Workspace) -> None:
        """L6.01 — aggregate count returns a positive integer.

        Args:
            ws: Workspace fixture.
        """
        agg = ws.query_user(mode="aggregate")
        assert agg.value is not None
        assert agg.value > 0
        assert isinstance(agg.value, int)

    def test_aggregate_count_with_filter(self, ws: Workspace) -> None:
        """L6.02 — filtered aggregate count is less than unfiltered.

        Args:
            ws: Workspace fixture.
        """
        all_count = ws.query_user(mode="aggregate")
        filtered = ws.query_user(mode="aggregate", where=Filter.is_set("$email"))
        assert filtered.value is not None
        assert all_count.value is not None
        assert filtered.value < all_count.value

    def test_aggregate_segmented_by_cohort(self, ws: Workspace) -> None:
        """L6.03 — segmented aggregate returns a DataFrame with segment/value columns.

        Args:
            ws: Workspace fixture.
        """
        cohorts = ws.cohorts()
        assert len(cohorts) >= 2, "Need at least 2 cohorts"
        cids = [cohorts[0].id, cohorts[1].id]
        result = ws.query_user(mode="aggregate", segment_by=cids)
        df = result.df
        assert "segment" in df.columns
        assert "value" in df.columns
        assert len(df) > 0

    def test_aggregate_extremes_with_property(self, ws: Workspace) -> None:
        """L6.04 — aggregate extremes on a numeric property returns a dict.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(
            mode="aggregate",
            aggregate="extremes",
            aggregate_property="SFDC Company Size",
        )
        assert isinstance(result.aggregate_data, dict)
        assert "max" in result.aggregate_data
        assert "min" in result.aggregate_data

    def test_aggregate_numeric_summary_with_property(self, ws: Workspace) -> None:
        """L6.05 — numeric_summary returns count, mean, var, sum_of_squares.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(
            mode="aggregate",
            aggregate="numeric_summary",
            aggregate_property="SFDC Company Size",
        )
        assert isinstance(result.aggregate_data, dict)
        assert "count" in result.aggregate_data
        assert "mean" in result.aggregate_data
        assert "var" in result.aggregate_data
        assert "sum_of_squares" in result.aggregate_data

    def test_aggregate_percentile_with_property(self, ws: Workspace) -> None:
        """L6.06 — percentile returns percentile and result keys.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(
            mode="aggregate",
            aggregate="percentile",
            aggregate_property="SFDC Company Size",
            percentile=50,
        )
        assert isinstance(result.aggregate_data, dict)
        assert "percentile" in result.aggregate_data
        assert result.aggregate_data["percentile"] == 50
        assert "result" in result.aggregate_data

    def test_aggregate_extremes_df_has_structured_columns(self, ws: Workspace) -> None:
        """L6.07 — extremes DataFrame has metric + result key columns.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(
            mode="aggregate",
            aggregate="extremes",
            aggregate_property="SFDC Company Size",
        )
        df = result.df
        assert len(df) == 1
        assert "metric" in df.columns
        assert "max" in df.columns
        assert "min" in df.columns


# =============================================================================
# CATEGORY 7: Result Type & DataFrame (5 tests)
# =============================================================================


class TestResultTypeAndDataFrame:
    """UserQueryResult structure and DataFrame behavior."""

    def test_df_columns_have_distinct_id_first(self, ws: Workspace) -> None:
        """L7.01 — DataFrame columns start with distinct_id then last_seen.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(mode="profiles", limit=5)
        assert result.df.columns[0] == "distinct_id"
        assert result.df.columns[1] == "last_seen"

    def test_df_dollar_prefix_stripped(self, ws: Workspace) -> None:
        """L7.02 — $-prefixed property names are stripped in the DataFrame.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(mode="profiles", properties=["$email", "$name"], limit=3)
        cols = set(result.df.columns)
        assert "email" in cols
        assert "name" in cols
        assert "$email" not in cols
        assert "$name" not in cols

    def test_distinct_ids_property_returns_list(self, ws: Workspace) -> None:
        """L7.03 — distinct_ids property returns a list of the right length.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(mode="profiles", limit=5)
        assert isinstance(result.distinct_ids, list)
        assert len(result.distinct_ids) == 5

    def test_to_dict_is_json_serializable(self, ws: Workspace) -> None:
        """L7.04 — to_dict() output is JSON-serializable.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(limit=3)
        serialized = json.dumps(result.to_dict())
        assert isinstance(serialized, str)
        # Round-trip check
        parsed = json.loads(serialized)
        assert parsed["total"] == result.total

    def test_result_df_composable_with_pandas(self, ws: Workspace) -> None:
        """L7.05 — result DataFrame works with standard pandas operations.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(mode="profiles", limit=100, properties=["$email"])
        # groupby should work
        grouped = result.df.groupby("email").size()
        assert len(grouped) > 0
        # describe should work
        described = result.df.describe()
        assert described is not None


# =============================================================================
# CATEGORY 8: Cross-Engine Composition (2 tests)
# =============================================================================


class TestCrossEngineComposition:
    """Using query_user results in subsequent calls."""

    def test_distinct_ids_from_query_user_usable_in_subsequent_call(
        self, ws: Workspace
    ) -> None:
        """L8.01 — distinct_ids from one query can feed a second lookup.

        Args:
            ws: Workspace fixture.
        """
        r1 = ws.query_user(mode="profiles", limit=3)
        r2 = ws.query_user(
            mode="profiles", distinct_ids=r1.distinct_ids, limit=len(r1.distinct_ids)
        )
        assert set(r2.distinct_ids) == set(r1.distinct_ids)

    def test_build_user_params_matches_query_user_params(self, ws: Workspace) -> None:
        """L8.02 — build_user_params produces the same params as query_user uses.

        Args:
            ws: Workspace fixture.
        """
        kwargs = {
            "mode": "profiles",
            "where": Filter.is_set("$email"),
            "properties": ["$email"],
        }
        build_params = ws.build_user_params(**kwargs)  # type: ignore[arg-type]
        result = ws.query_user(**kwargs, limit=1)  # type: ignore[arg-type]
        assert result.params == build_params


# =============================================================================
# CATEGORY 9: Error Handling (4 tests)
# =============================================================================


class TestErrorHandling:
    """Error paths and edge cases."""

    def test_validation_error_on_invalid_args(self, ws: Workspace) -> None:
        """L9.01 — passing both distinct_id and distinct_ids raises BookmarkValidationError.

        Args:
            ws: Workspace fixture.
        """
        with pytest.raises(BookmarkValidationError):
            ws.query_user(distinct_id="a", distinct_ids=["b"])

    def test_empty_result_from_impossible_filter(self, ws: Workspace) -> None:
        """L9.02 — an impossible filter returns zero profiles and empty DataFrame.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(
            mode="profiles",
            where='properties["nonexistent_prop_xyz_abc_123"] == "impossible"',
        )
        assert result.total == 0
        assert result.profiles == []
        assert result.df.empty

    def test_result_total_always_int(self, ws: Workspace) -> None:
        """L9.03 — result.total is always an int.

        Args:
            ws: Workspace fixture.
        """
        result = ws.query_user(limit=1)
        assert isinstance(result.total, int)

    def test_rate_limit_not_hit_with_small_queries(self, ws: Workspace) -> None:
        """L9.04 — five sequential small queries succeed without rate limiting.

        Args:
            ws: Workspace fixture.
        """
        for _ in range(5):
            result = ws.query_user(limit=1)
            assert isinstance(result, UserQueryResult)
