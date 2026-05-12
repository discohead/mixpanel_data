"""Unit tests for UserQueryResult type.

Tests cover (T003):
    - Construction with all fields, defaults, and overrides
    - Frozen dataclass immutability
    - DataFrame construction from profiles (column schema, $-prefix stripping,
      alphabetical property sorting)
    - DataFrame from aggregate data (metric/value schema, segmented schema)
    - Empty profiles producing empty DataFrame with correct columns
    - distinct_ids property
    - value property
    - Mode-aware behavior (profiles vs aggregate)
    - to_dict() serialization
    - Lazy caching via object.__setattr__
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import pytest

from mixpanel_headless.types import UserQueryResult

# =============================================================================
# Helpers
# =============================================================================


def _make_result(**overrides: Any) -> UserQueryResult:
    """Build a default-valid UserQueryResult in profiles mode for testing.

    Args:
        **overrides: Field overrides to apply on top of defaults.

    Returns:
        UserQueryResult instance with sensible defaults.
    """
    defaults: dict[str, Any] = {
        "computed_at": "2025-01-15T10:00:00",
        "total": 0,
        "profiles": [],
        "params": {},
        "meta": {},
        "mode": "profiles",
        "aggregate_data": None,
    }
    defaults.update(overrides)
    return UserQueryResult(**defaults)


def _sample_profiles() -> list[dict[str, Any]]:
    """Build sample profile dicts for testing.

    Returns two profiles with a mix of built-in ($-prefixed) and custom
    properties. Matches the normalized format produced by transform_profile().

    Returns:
        List of normalized profile dicts.
    """
    return [
        {
            "distinct_id": "user_001",
            "last_seen": "2025-01-14T08:30:00",
            "properties": {
                "$email": "alice@example.com",
                "$city": "San Francisco",
                "plan": "premium",
                "ltv": 299.99,
            },
        },
        {
            "distinct_id": "user_002",
            "last_seen": "2025-01-13T12:00:00",
            "properties": {
                "$email": "bob@example.com",
                "$city": "New York",
                "plan": "free",
                "ltv": 0,
                "referral_source": "organic",
            },
        },
    ]


def _single_profile() -> list[dict[str, Any]]:
    """Build a single profile for minimal testing.

    Returns:
        List containing one profile dict.
    """
    return [
        {
            "distinct_id": "user_solo",
            "last_seen": "2025-01-15T00:00:00",
            "properties": {
                "$email": "solo@example.com",
                "plan": "trial",
            },
        },
    ]


# =============================================================================
# Construction
# =============================================================================


class TestUserQueryResultConstruction:
    """Tests for UserQueryResult construction and defaults."""

    def test_construct_profiles_mode_with_defaults(self) -> None:
        """_make_result() produces a valid profiles-mode instance."""
        r = _make_result()
        assert r.computed_at == "2025-01-15T10:00:00"
        assert r.total == 0
        assert r.profiles == []
        assert r.params == {}
        assert r.meta == {}
        assert r.mode == "profiles"
        assert r.aggregate_data is None

    def test_construct_aggregate_mode(self) -> None:
        """Aggregate mode construction preserves all fields."""
        r = _make_result(
            mode="aggregate",
            total=5000,
            aggregate_data=5000,
            profiles=[],
        )
        assert r.mode == "aggregate"
        assert r.total == 5000
        assert r.aggregate_data == 5000
        assert r.profiles == []

    def test_construct_with_profiles(self) -> None:
        """Profiles are preserved after construction."""
        profiles = _sample_profiles()
        r = _make_result(profiles=profiles, total=2)
        assert len(r.profiles) == 2
        assert r.profiles[0]["distinct_id"] == "user_001"
        assert r.profiles[1]["distinct_id"] == "user_002"

    def test_construct_with_all_overrides(self) -> None:
        """Overriding every field works correctly."""
        r = _make_result(
            computed_at="2025-02-01T12:00:00",
            total=100,
            profiles=_single_profile(),
            params={"where": 'properties["plan"] == "premium"'},
            meta={"session_id": "abc123", "pages_fetched": 1},
            mode="profiles",
            aggregate_data=None,
        )
        assert r.computed_at == "2025-02-01T12:00:00"
        assert r.total == 100
        assert len(r.profiles) == 1
        assert "where" in r.params
        assert r.meta["session_id"] == "abc123"
        assert r.mode == "profiles"
        assert r.aggregate_data is None

    def test_construct_with_dict_aggregate_data(self) -> None:
        """aggregate_data can be a dict (segmented results)."""
        seg_data: dict[str, Any] = {"cohort_123": 42, "cohort_456": 78}
        r = _make_result(
            mode="aggregate",
            aggregate_data=seg_data,
        )
        assert isinstance(r.aggregate_data, dict)
        assert r.aggregate_data["cohort_123"] == 42

    def test_construct_with_int_aggregate_data(self) -> None:
        """aggregate_data can be an int (count result)."""
        r = _make_result(mode="aggregate", aggregate_data=500)
        assert r.aggregate_data == 500

    def test_construct_with_float_aggregate_data(self) -> None:
        """aggregate_data can be a float (mean/sum result)."""
        r = _make_result(mode="aggregate", aggregate_data=123.45)
        assert r.aggregate_data == 123.45


# =============================================================================
# Immutability
# =============================================================================


class TestUserQueryResultImmutability:
    """Tests for UserQueryResult frozen dataclass immutability."""

    def test_cannot_set_computed_at(self) -> None:
        """Setting computed_at on a frozen instance must raise."""
        r = _make_result()
        with pytest.raises(AttributeError):
            r.computed_at = "new"  # type: ignore[misc]

    def test_cannot_set_total(self) -> None:
        """Setting total on a frozen instance must raise."""
        r = _make_result()
        with pytest.raises(AttributeError):
            r.total = 99  # type: ignore[misc]

    def test_cannot_set_profiles(self) -> None:
        """Setting profiles on a frozen instance must raise."""
        r = _make_result()
        with pytest.raises(AttributeError):
            r.profiles = []  # type: ignore[misc]

    def test_cannot_set_mode(self) -> None:
        """Setting mode on a frozen instance must raise."""
        r = _make_result()
        with pytest.raises(AttributeError):
            r.mode = "aggregate"  # type: ignore[misc]

    def test_cannot_set_aggregate_data(self) -> None:
        """Setting aggregate_data on a frozen instance must raise."""
        r = _make_result()
        with pytest.raises(AttributeError):
            r.aggregate_data = 42  # type: ignore[misc]

    def test_cannot_set_params(self) -> None:
        """Setting params on a frozen instance must raise."""
        r = _make_result()
        with pytest.raises(AttributeError):
            r.params = {}  # type: ignore[misc]

    def test_cannot_set_meta(self) -> None:
        """Setting meta on a frozen instance must raise."""
        r = _make_result()
        with pytest.raises(AttributeError):
            r.meta = {}  # type: ignore[misc]


# =============================================================================
# DataFrame: Profiles Mode
# =============================================================================


class TestUserQueryResultProfilesDf:
    """Tests for UserQueryResult.df in profiles mode."""

    def test_df_columns_contain_distinct_id_and_last_seen(self) -> None:
        """DataFrame always starts with distinct_id and last_seen columns."""
        r = _make_result(profiles=_sample_profiles(), total=2)
        df = r.df
        cols = list(df.columns)
        assert cols[0] == "distinct_id"
        assert cols[1] == "last_seen"

    def test_df_dollar_prefix_stripped(self) -> None:
        """Built-in $-prefixed properties have $ stripped in column names."""
        r = _make_result(profiles=_sample_profiles(), total=2)
        df = r.df
        cols = list(df.columns)
        # $email -> email, $city -> city
        assert "email" in cols
        assert "city" in cols
        assert "$email" not in cols
        assert "$city" not in cols

    def test_df_properties_sorted_alphabetically(self) -> None:
        """Property columns after distinct_id and last_seen are alphabetical."""
        r = _make_result(profiles=_sample_profiles(), total=2)
        df = r.df
        cols = list(df.columns)
        # First two are fixed: distinct_id, last_seen
        property_cols = cols[2:]
        assert property_cols == sorted(property_cols)

    def test_df_row_count_matches_profiles(self) -> None:
        """DataFrame has one row per profile."""
        profiles = _sample_profiles()
        r = _make_result(profiles=profiles, total=2)
        df = r.df
        assert len(df) == len(profiles)

    def test_df_distinct_id_values(self) -> None:
        """distinct_id column contains the correct values."""
        r = _make_result(profiles=_sample_profiles(), total=2)
        df = r.df
        assert list(df["distinct_id"]) == ["user_001", "user_002"]

    def test_df_last_seen_values(self) -> None:
        """last_seen column contains the correct values."""
        r = _make_result(profiles=_sample_profiles(), total=2)
        df = r.df
        assert list(df["last_seen"]) == [
            "2025-01-14T08:30:00",
            "2025-01-13T12:00:00",
        ]

    def test_df_property_values_preserved(self) -> None:
        """Property values are correctly mapped to columns."""
        r = _make_result(profiles=_sample_profiles(), total=2)
        df = r.df
        assert df["email"].iloc[0] == "alice@example.com"
        assert df["plan"].iloc[0] == "premium"
        assert df["ltv"].iloc[0] == 299.99

    def test_df_missing_property_is_nan(self) -> None:
        """Properties not present on a profile are NaN."""
        r = _make_result(profiles=_sample_profiles(), total=2)
        df = r.df
        # referral_source only on user_002, should be NaN for user_001
        assert pd.isna(df["referral_source"].iloc[0])
        assert df["referral_source"].iloc[1] == "organic"

    def test_df_single_profile(self) -> None:
        """DataFrame works with a single profile."""
        r = _make_result(profiles=_single_profile(), total=1)
        df = r.df
        assert len(df) == 1
        assert df["distinct_id"].iloc[0] == "user_solo"

    def test_df_profile_no_properties(self) -> None:
        """Profile with empty properties dict produces only distinct_id and last_seen."""
        profiles = [
            {
                "distinct_id": "bare_user",
                "last_seen": "2025-01-01T00:00:00",
                "properties": {},
            },
        ]
        r = _make_result(profiles=profiles, total=1)
        df = r.df
        assert len(df) == 1
        assert list(df.columns) == ["distinct_id", "last_seen"]

    def test_df_all_dollar_prefixed_properties(self) -> None:
        """All $-prefixed properties are stripped and sorted."""
        profiles = [
            {
                "distinct_id": "u1",
                "last_seen": "2025-01-01T00:00:00",
                "properties": {
                    "$browser": "Chrome",
                    "$os": "macOS",
                    "$app_version": "3.2",
                },
            },
        ]
        r = _make_result(profiles=profiles, total=1)
        df = r.df
        # After stripping $: app_version, browser, os — alphabetical
        property_cols = list(df.columns)[2:]
        assert property_cols == ["app_version", "browser", "os"]

    def test_df_mixed_types_in_properties(self) -> None:
        """Properties with mixed types (str, int, float, bool) are preserved."""
        profiles = [
            {
                "distinct_id": "u1",
                "last_seen": "2025-01-01T00:00:00",
                "properties": {
                    "name": "Alice",
                    "age": 30,
                    "score": 95.5,
                    "active": True,
                },
            },
        ]
        r = _make_result(profiles=profiles, total=1)
        df = r.df
        assert df["name"].iloc[0] == "Alice"
        assert df["age"].iloc[0] == 30
        assert df["score"].iloc[0] == 95.5
        assert df["active"].iloc[0] == True  # noqa: E712 — pandas returns np.True_


# =============================================================================
# DataFrame: Empty Profiles
# =============================================================================


class TestUserQueryResultEmptyProfilesDf:
    """Tests for UserQueryResult.df with empty profiles."""

    def test_empty_profiles_produces_empty_dataframe(self) -> None:
        """Empty profiles list produces a DataFrame with zero rows."""
        r = _make_result(profiles=[], total=0)
        df = r.df
        assert len(df) == 0

    def test_empty_profiles_has_correct_columns(self) -> None:
        """Empty profiles DataFrame still has distinct_id and last_seen columns."""
        r = _make_result(profiles=[], total=0)
        df = r.df
        assert "distinct_id" in df.columns
        assert "last_seen" in df.columns

    def test_empty_profiles_total_nonzero(self) -> None:
        """Empty profiles with nonzero total (limit=0 edge case) still works."""
        r = _make_result(profiles=[], total=5000)
        df = r.df
        assert len(df) == 0
        assert r.total == 5000


# =============================================================================
# DataFrame: Aggregate Mode (unsegmented)
# =============================================================================


class TestUserQueryResultAggregateDf:
    """Tests for UserQueryResult.df in aggregate mode (unsegmented)."""

    def test_aggregate_count_df_columns(self) -> None:
        """Unsegmented aggregate DataFrame has metric and value columns."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=5000,
            total=5000,
            meta={"action": "count()"},
        )
        df = r.df
        assert list(df.columns) == ["metric", "value"]

    def test_aggregate_count_df_single_row(self) -> None:
        """Unsegmented count aggregate produces one row."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=5000,
            total=5000,
            meta={"action": "count()"},
        )
        df = r.df
        assert len(df) == 1

    def test_aggregate_count_df_values(self) -> None:
        """Count aggregate value appears in the DataFrame."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=5000,
            total=5000,
            meta={"action": "count()"},
        )
        df = r.df
        assert df["value"].iloc[0] == 5000

    def test_aggregate_float_df_values(self) -> None:
        """Float aggregate (mean/sum) value is preserved in DataFrame."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=123.45,
            total=500,
            meta={"action": "mean(ltv)"},
        )
        df = r.df
        assert df["value"].iloc[0] == 123.45

    def test_aggregate_zero_value(self) -> None:
        """Zero aggregate value is correctly represented, not treated as None."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=0,
            total=0,
            meta={"action": "count()"},
        )
        df = r.df
        assert len(df) == 1
        assert df["value"].iloc[0] == 0


# =============================================================================
# DataFrame: Aggregate Mode (segmented)
# =============================================================================


class TestUserQueryResultSegmentedAggregateDf:
    """Tests for UserQueryResult.df in aggregate mode with segmentation."""

    def test_segmented_df_columns(self) -> None:
        """Segmented aggregate DataFrame has segment and value columns."""
        seg_data: dict[str, Any] = {"cohort_123": 42, "cohort_456": 78}
        r = _make_result(
            mode="aggregate",
            aggregate_data=seg_data,
            total=120,
            meta={"action": "count()", "segmented": True},
        )
        df = r.df
        assert list(df.columns) == ["segment", "value"]

    def test_segmented_df_row_count(self) -> None:
        """Segmented aggregate has one row per segment."""
        seg_data: dict[str, Any] = {"cohort_A": 10, "cohort_B": 20, "cohort_C": 30}
        r = _make_result(
            mode="aggregate",
            aggregate_data=seg_data,
            total=60,
            meta={"action": "count()", "segmented": True},
        )
        df = r.df
        assert len(df) == 3

    def test_segmented_df_values(self) -> None:
        """Segment names and values are correctly mapped."""
        seg_data: dict[str, Any] = {"cohort_123": 42, "cohort_456": 78}
        r = _make_result(
            mode="aggregate",
            aggregate_data=seg_data,
            total=120,
            meta={"action": "count()", "segmented": True},
        )
        df = r.df
        segments = set(df["segment"].tolist())
        assert segments == {"cohort_123", "cohort_456"}
        # Check specific values
        row_123 = df[df["segment"] == "cohort_123"]
        assert row_123["value"].iloc[0] == 42

    def test_segmented_single_segment(self) -> None:
        """Single-segment aggregation produces one row."""
        seg_data: dict[str, Any] = {"only_segment": 99}
        r = _make_result(
            mode="aggregate",
            aggregate_data=seg_data,
            total=99,
            meta={"action": "count()", "segmented": True},
        )
        df = r.df
        assert len(df) == 1
        assert df["segment"].iloc[0] == "only_segment"
        assert df["value"].iloc[0] == 99


# =============================================================================
# DataFrame: Aggregate Mode with None
# =============================================================================


class TestUserQueryResultAggregateNoneDf:
    """Tests for UserQueryResult.df when aggregate_data is None."""

    def test_aggregate_mode_none_data_produces_empty_df(self) -> None:
        """aggregate_data=None in aggregate mode produces empty DataFrame."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=None,
            total=0,
        )
        df = r.df
        assert len(df) == 0


# =============================================================================
# Lazy Caching
# =============================================================================


class TestUserQueryResultDfCaching:
    """Tests for UserQueryResult.df lazy caching via object.__setattr__."""

    def test_df_cached_profiles_mode(self) -> None:
        """Second df access in profiles mode returns same cached object."""
        r = _make_result(profiles=_sample_profiles(), total=2)
        df1 = r.df
        df2 = r.df
        assert df1 is df2

    def test_df_cached_aggregate_mode(self) -> None:
        """Second df access in aggregate mode returns same cached object."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=100,
            total=100,
        )
        df1 = r.df
        df2 = r.df
        assert df1 is df2

    def test_df_cached_empty_profiles(self) -> None:
        """Caching works for empty profiles (caches the empty DataFrame)."""
        r = _make_result(profiles=[], total=0)
        df1 = r.df
        df2 = r.df
        assert df1 is df2

    def test_df_cache_is_initially_none(self) -> None:
        """_df_cache starts as None before first df access."""
        r = _make_result()
        assert r._df_cache is None

    def test_df_cache_populated_after_access(self) -> None:
        """_df_cache is populated after first df access."""
        r = _make_result(profiles=_sample_profiles(), total=2)
        _ = r.df
        assert r._df_cache is not None


# =============================================================================
# distinct_ids property
# =============================================================================


class TestUserQueryResultDistinctIds:
    """Tests for UserQueryResult.distinct_ids property."""

    def test_distinct_ids_from_profiles(self) -> None:
        """distinct_ids returns list of distinct_id strings from profiles."""
        r = _make_result(profiles=_sample_profiles(), total=2)
        assert r.distinct_ids == ["user_001", "user_002"]

    def test_distinct_ids_single_profile(self) -> None:
        """distinct_ids works with a single profile."""
        r = _make_result(profiles=_single_profile(), total=1)
        assert r.distinct_ids == ["user_solo"]

    def test_distinct_ids_empty_profiles(self) -> None:
        """distinct_ids returns empty list when no profiles."""
        r = _make_result(profiles=[], total=0)
        assert r.distinct_ids == []

    def test_distinct_ids_aggregate_mode_returns_empty(self) -> None:
        """distinct_ids returns empty list in aggregate mode."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=100,
            total=100,
            profiles=[],
        )
        assert r.distinct_ids == []

    def test_distinct_ids_returns_list_type(self) -> None:
        """distinct_ids returns a list, not a generator or other iterable."""
        r = _make_result(profiles=_sample_profiles(), total=2)
        result = r.distinct_ids
        assert isinstance(result, list)

    def test_distinct_ids_preserves_order(self) -> None:
        """distinct_ids preserves the order of profiles."""
        profiles = [
            {"distinct_id": "z_user", "last_seen": "", "properties": {}},
            {"distinct_id": "a_user", "last_seen": "", "properties": {}},
            {"distinct_id": "m_user", "last_seen": "", "properties": {}},
        ]
        r = _make_result(profiles=profiles, total=3)
        assert r.distinct_ids == ["z_user", "a_user", "m_user"]


# =============================================================================
# value property
# =============================================================================


class TestUserQueryResultValue:
    """Tests for UserQueryResult.value property."""

    def test_value_int_aggregate(self) -> None:
        """value returns int aggregate result."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=5000,
            total=5000,
        )
        assert r.value == 5000

    def test_value_float_aggregate(self) -> None:
        """value returns float aggregate result."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=123.45,
            total=500,
        )
        assert r.value == 123.45

    def test_value_zero_aggregate(self) -> None:
        """value returns 0 for zero aggregate (not None)."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=0,
            total=0,
        )
        assert r.value == 0
        assert r.value is not None

    def test_value_profiles_mode_returns_none(self) -> None:
        """value returns None in profiles mode."""
        r = _make_result(
            mode="profiles",
            profiles=_sample_profiles(),
            total=2,
        )
        assert r.value is None

    def test_value_segmented_aggregate_returns_none(self) -> None:
        """value returns None for segmented aggregate (dict, not scalar)."""
        seg_data: dict[str, Any] = {"cohort_123": 42, "cohort_456": 78}
        r = _make_result(
            mode="aggregate",
            aggregate_data=seg_data,
            total=120,
        )
        assert r.value is None

    def test_value_none_aggregate_data(self) -> None:
        """value returns None when aggregate_data is None."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=None,
            total=0,
        )
        assert r.value is None


# =============================================================================
# Mode-aware behavior
# =============================================================================


class TestUserQueryResultModeAware:
    """Tests for UserQueryResult mode-aware dispatch."""

    def test_profiles_mode_df_has_profile_columns(self) -> None:
        """Profiles mode df has distinct_id, last_seen, and property columns."""
        r = _make_result(profiles=_sample_profiles(), total=2, mode="profiles")
        df = r.df
        assert "distinct_id" in df.columns
        assert "last_seen" in df.columns
        assert len(df) == 2

    def test_aggregate_mode_df_has_metric_columns(self) -> None:
        """Aggregate mode df has metric/value or segment/value columns."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=100,
            total=100,
        )
        df = r.df
        assert "metric" in df.columns or "segment" in df.columns
        assert "value" in df.columns

    def test_profiles_mode_value_is_none(self) -> None:
        """value property is None in profiles mode."""
        r = _make_result(mode="profiles", profiles=_sample_profiles(), total=2)
        assert r.value is None

    def test_aggregate_mode_distinct_ids_is_empty(self) -> None:
        """distinct_ids is empty in aggregate mode."""
        r = _make_result(mode="aggregate", aggregate_data=100, total=100)
        assert r.distinct_ids == []

    def test_profiles_mode_distinct_ids_populated(self) -> None:
        """distinct_ids is populated in profiles mode."""
        r = _make_result(mode="profiles", profiles=_sample_profiles(), total=2)
        assert len(r.distinct_ids) == 2

    def test_aggregate_mode_value_populated(self) -> None:
        """value is populated in aggregate mode with scalar data."""
        r = _make_result(mode="aggregate", aggregate_data=42, total=42)
        assert r.value == 42


# =============================================================================
# to_dict() serialization
# =============================================================================


class TestUserQueryResultToDict:
    """Tests for UserQueryResult.to_dict() serialization."""

    def test_to_dict_contains_all_fields(self) -> None:
        """to_dict() includes all public fields."""
        r = _make_result()
        d = r.to_dict()
        assert "computed_at" in d
        assert "total" in d
        assert "profiles" in d
        assert "params" in d
        assert "meta" in d
        assert "mode" in d
        assert "aggregate_data" in d

    def test_to_dict_values_match_fields(self) -> None:
        """to_dict() values match the instance fields."""
        r = _make_result(
            computed_at="2025-02-01T12:00:00",
            total=42,
            profiles=_single_profile(),
            params={"where": "plan == premium"},
            meta={"session_id": "xyz"},
            mode="profiles",
            aggregate_data=None,
        )
        d = r.to_dict()
        assert d["computed_at"] == "2025-02-01T12:00:00"
        assert d["total"] == 42
        assert len(d["profiles"]) == 1
        assert d["params"]["where"] == "plan == premium"
        assert d["meta"]["session_id"] == "xyz"
        assert d["mode"] == "profiles"
        assert d["aggregate_data"] is None

    def test_to_dict_with_aggregate_data(self) -> None:
        """to_dict() serializes aggregate data correctly."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=123.45,
            total=500,
        )
        d = r.to_dict()
        assert d["aggregate_data"] == 123.45
        assert d["mode"] == "aggregate"

    def test_to_dict_with_segmented_aggregate(self) -> None:
        """to_dict() serializes segmented aggregate dict."""
        seg_data: dict[str, Any] = {"cohort_123": 42, "cohort_456": 78}
        r = _make_result(
            mode="aggregate",
            aggregate_data=seg_data,
            total=120,
        )
        d = r.to_dict()
        assert d["aggregate_data"] == {"cohort_123": 42, "cohort_456": 78}

    def test_to_dict_is_json_serializable(self) -> None:
        """to_dict() output can be JSON-serialized."""
        r = _make_result(
            profiles=_single_profile(),
            total=1,
            params={"where": "plan == premium"},
            meta={"session_id": "abc"},
        )
        d = r.to_dict()
        json_str = json.dumps(d)
        assert "user_solo" in json_str
        assert "plan == premium" in json_str

    def test_to_dict_aggregate_json_serializable(self) -> None:
        """Aggregate to_dict() output can be JSON-serialized."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=42,
            total=42,
        )
        d = r.to_dict()
        json_str = json.dumps(d)
        assert "42" in json_str

    def test_to_dict_does_not_include_df_cache(self) -> None:
        """to_dict() must not include the internal _df_cache field."""
        r = _make_result(profiles=_sample_profiles(), total=2)
        _ = r.df  # populate cache
        d = r.to_dict()
        assert "_df_cache" not in d

    def test_to_dict_empty_result(self) -> None:
        """to_dict() works for a completely empty result."""
        r = _make_result()
        d = r.to_dict()
        assert d["total"] == 0
        assert d["profiles"] == []
        assert d["aggregate_data"] is None


# =============================================================================
# to_table_dict (inherited from ResultWithDataFrame)
# =============================================================================


class TestUserQueryResultToTableDict:
    """Tests for UserQueryResult.to_table_dict() inherited method."""

    def test_to_table_dict_profiles_mode(self) -> None:
        """to_table_dict() returns list of row dicts in profiles mode."""
        r = _make_result(profiles=_sample_profiles(), total=2)
        rows = r.to_table_dict()
        assert isinstance(rows, list)
        assert len(rows) == 2
        assert rows[0]["distinct_id"] == "user_001"

    def test_to_table_dict_aggregate_mode(self) -> None:
        """to_table_dict() returns list of row dicts in aggregate mode."""
        r = _make_result(
            mode="aggregate",
            aggregate_data=100,
            total=100,
        )
        rows = r.to_table_dict()
        assert isinstance(rows, list)
        assert len(rows) == 1

    def test_to_table_dict_empty(self) -> None:
        """to_table_dict() returns empty list for empty result."""
        r = _make_result(profiles=[], total=0)
        rows = r.to_table_dict()
        assert rows == []


# =============================================================================
# Edge Cases
# =============================================================================


class TestUserQueryResultEdgeCases:
    """Tests for UserQueryResult edge cases and boundary conditions."""

    def test_profile_with_none_property_value(self) -> None:
        """Profile with a None property value is preserved as NaN in DataFrame."""
        profiles = [
            {
                "distinct_id": "u1",
                "last_seen": "2025-01-01T00:00:00",
                "properties": {"email": None, "plan": "free"},
            },
        ]
        r = _make_result(profiles=profiles, total=1)
        df = r.df
        assert pd.isna(df["email"].iloc[0])
        assert df["plan"].iloc[0] == "free"

    def test_profile_with_unicode_property_names(self) -> None:
        """Profile with unicode property names is handled."""
        profiles = [
            {
                "distinct_id": "u1",
                "last_seen": "2025-01-01T00:00:00",
                "properties": {"nombre": "Carlos", "ciudad": "Madrid"},
            },
        ]
        r = _make_result(profiles=profiles, total=1)
        df = r.df
        assert "nombre" in df.columns
        assert df["nombre"].iloc[0] == "Carlos"

    def test_profile_with_empty_distinct_id(self) -> None:
        """Profile with empty string distinct_id is preserved."""
        profiles = [
            {
                "distinct_id": "",
                "last_seen": "2025-01-01T00:00:00",
                "properties": {},
            },
        ]
        r = _make_result(profiles=profiles, total=1)
        df = r.df
        assert df["distinct_id"].iloc[0] == ""

    def test_large_total_with_few_profiles(self) -> None:
        """total can be much larger than len(profiles) (limit scenario)."""
        r = _make_result(
            profiles=_single_profile(),
            total=50000,
        )
        assert r.total == 50000
        assert len(r.profiles) == 1
        assert len(r.df) == 1

    def test_profile_with_nested_property_value(self) -> None:
        """Profile with a nested dict property value is preserved."""
        profiles = [
            {
                "distinct_id": "u1",
                "last_seen": "2025-01-01T00:00:00",
                "properties": {
                    "address": {"city": "SF", "state": "CA"},
                    "plan": "premium",
                },
            },
        ]
        r = _make_result(profiles=profiles, total=1)
        df = r.df
        assert isinstance(df["address"].iloc[0], dict)

    def test_profile_with_list_property_value(self) -> None:
        """Profile with a list property value is preserved."""
        profiles = [
            {
                "distinct_id": "u1",
                "last_seen": "2025-01-01T00:00:00",
                "properties": {
                    "tags": ["vip", "beta"],
                    "plan": "premium",
                },
            },
        ]
        r = _make_result(profiles=profiles, total=1)
        df = r.df
        assert df["tags"].iloc[0] == ["vip", "beta"]

    def test_many_profiles_column_consistency(self) -> None:
        """Profiles with varying property sets produce consistent columns."""
        profiles = [
            {
                "distinct_id": f"u{i}",
                "last_seen": "2025-01-01T00:00:00",
                "properties": {"common": "yes", f"unique_{i}": i},
            }
            for i in range(5)
        ]
        r = _make_result(profiles=profiles, total=5)
        df = r.df
        assert len(df) == 5
        assert "common" in df.columns
        # Each unique_N column should exist
        for i in range(5):
            assert f"unique_{i}" in df.columns
