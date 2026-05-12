"""Unit tests for Workspace.build_user_params() / _resolve_and_build_user_params().

Tests cover T011: parameter builder validation and translation for the
query_user() engine. The method under test does not exist yet -- these
tests are written first (TDD) and are expected to fail until the
implementation is added.

Coverage areas:
1. Filter translation to engage ``where`` param
2. Cohort routing (saved ID -> filter_by_cohort with ``{"id": N}``,
   CohortDefinition -> filter_by_cohort with ``{"raw_cohort": ...}``)
3. Property selection -> output_properties
4. sort_by -> sort_key translation (e.g. ``"ltv"`` -> ``properties["ltv"]``)
5. as_of string -> Unix timestamp conversion
6. distinct_id / distinct_ids handling
7. group_id -> data_group_id
8. search passthrough
9. Raw string where passthrough
10. Validation errors raised as BookmarkValidationError
"""

from __future__ import annotations

import calendar
import json
from datetime import date
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import BookmarkValidationError, Filter, Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.types import CohortCriteria, CohortDefinition

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
    """Factory for creating Workspace instances with mocked dependencies.

    Returns:
        Callable that creates Workspace instances with injected mocks.
    """

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


@pytest.fixture
def ws(workspace_factory: Callable[..., Workspace]) -> Workspace:
    """Create a default Workspace with mocked dependencies.

    Returns:
        Workspace instance ready for build_user_params() calls.
    """
    return workspace_factory()


# =============================================================================
# 1. Filter translation to engage where param
# =============================================================================


class TestFilterTranslation:
    """Tests for Filter objects being translated to engage selector strings."""

    def test_single_equals_filter(self, ws: Workspace) -> None:
        """A single Filter.equals() produces a selector string in the where param."""
        params = ws.build_user_params(
            where=Filter.equals("plan", "premium"),
        )
        assert "where" in params
        assert 'properties["plan"] == "premium"' in params["where"]

    def test_multiple_filters_and_combined(self, ws: Workspace) -> None:
        """Multiple Filter objects in a list are AND-combined in the selector."""
        params = ws.build_user_params(
            where=[
                Filter.equals("plan", "premium"),
                Filter.is_set("email"),
            ],
        )
        where = params["where"]
        assert 'properties["plan"] == "premium"' in where
        assert 'defined(properties["email"])' in where
        assert " and " in where

    def test_greater_than_filter(self, ws: Workspace) -> None:
        """Filter.greater_than() translates to > selector syntax."""
        params = ws.build_user_params(
            where=Filter.greater_than("ltv", 100),
        )
        assert 'properties["ltv"] > 100' in params["where"]

    def test_less_than_filter(self, ws: Workspace) -> None:
        """Filter.less_than() translates to < selector syntax."""
        params = ws.build_user_params(
            where=Filter.less_than("age", 30),
        )
        assert 'properties["age"] < 30' in params["where"]

    def test_contains_filter(self, ws: Workspace) -> None:
        """Filter.contains() translates to 'in' selector syntax."""
        params = ws.build_user_params(
            where=Filter.contains("email", "corp"),
        )
        assert '"corp" in properties["email"]' in params["where"]

    def test_not_contains_filter(self, ws: Workspace) -> None:
        """Filter.not_contains() translates to 'not in' selector syntax."""
        params = ws.build_user_params(
            where=Filter.not_contains("email", "gmail"),
        )
        assert 'not "gmail" in properties["email"]' in params["where"]

    def test_between_filter(self, ws: Workspace) -> None:
        """Filter.between() translates to >= and <= selector syntax."""
        params = ws.build_user_params(
            where=Filter.between("age", 18, 65),
        )
        where = params["where"]
        assert 'properties["age"] >= 18' in where
        assert 'properties["age"] <= 65' in where

    def test_is_set_filter(self, ws: Workspace) -> None:
        """Filter.is_set() translates to defined() selector syntax."""
        params = ws.build_user_params(
            where=Filter.is_set("email"),
        )
        assert 'defined(properties["email"])' in params["where"]

    def test_is_not_set_filter(self, ws: Workspace) -> None:
        """Filter.is_not_set() translates to not defined() selector syntax."""
        params = ws.build_user_params(
            where=Filter.is_not_set("phone"),
        )
        assert 'not defined(properties["phone"])' in params["where"]

    def test_is_true_filter(self, ws: Workspace) -> None:
        """Filter.is_true() translates to == true selector syntax."""
        params = ws.build_user_params(
            where=Filter.is_true("active"),
        )
        assert 'properties["active"] == true' in params["where"]

    def test_is_false_filter(self, ws: Workspace) -> None:
        """Filter.is_false() translates to == false selector syntax."""
        params = ws.build_user_params(
            where=Filter.is_false("churned"),
        )
        assert 'properties["churned"] == false' in params["where"]

    def test_multi_value_equals_filter(self, ws: Workspace) -> None:
        """Filter.equals() with multiple values produces OR-chained selector."""
        params = ws.build_user_params(
            where=Filter.equals("plan", ["premium", "enterprise"]),
        )
        where = params["where"]
        assert 'properties["plan"] == "premium"' in where
        assert 'properties["plan"] == "enterprise"' in where
        assert " or " in where

    def test_no_where_omits_param(self, ws: Workspace) -> None:
        """When where is None, the where param should not be present."""
        params = ws.build_user_params()
        assert "where" not in params or params.get("where") is None

    def test_single_filter_not_in_list(self, ws: Workspace) -> None:
        """A single Filter (not wrapped in list) is accepted directly."""
        params = ws.build_user_params(
            where=Filter.equals("plan", "premium"),
        )
        assert 'properties["plan"] == "premium"' in params["where"]


# =============================================================================
# 2. Cohort routing
# =============================================================================


class TestCohortRouting:
    """Tests for cohort parameter routing to filter_by_cohort."""

    def test_saved_cohort_id(self, ws: Workspace) -> None:
        """Integer cohort ID routes to filter_by_cohort with 'id' key."""
        params = ws.build_user_params(cohort=12345)
        assert "filter_by_cohort" in params
        fbc = params["filter_by_cohort"]
        # The value may be a dict or a JSON-encoded string
        if isinstance(fbc, str):
            fbc = json.loads(fbc)
        assert fbc["id"] == 12345

    def test_cohort_definition_routes_to_raw_cohort(self, ws: Workspace) -> None:
        """CohortDefinition routes to filter_by_cohort with 'raw_cohort' key."""
        defn = CohortDefinition.all_of(
            CohortCriteria.has_property("plan", "premium"),
        )
        params = ws.build_user_params(cohort=defn)
        assert "filter_by_cohort" in params
        fbc = params["filter_by_cohort"]
        if isinstance(fbc, str):
            fbc = json.loads(fbc)
        assert "raw_cohort" in fbc
        # The raw_cohort should be the serialized definition
        assert isinstance(fbc["raw_cohort"], dict)

    def test_cohort_definition_includes_to_dict_output(self, ws: Workspace) -> None:
        """CohortDefinition's raw_cohort value matches sanitized to_dict().

        The workspace sanitizes inline cohorts via ``_sanitize_raw_cohort()``
        to remove ``selector: None`` entries that crash the Mixpanel API.
        """
        from mixpanel_headless.types import _sanitize_raw_cohort

        defn = CohortDefinition.all_of(
            CohortCriteria.has_property("plan", "premium"),
            CohortCriteria.did_event("Purchase", at_least=3, within_days=30),
        )
        expected = _sanitize_raw_cohort(defn.to_dict())
        params = ws.build_user_params(cohort=defn)
        fbc = params["filter_by_cohort"]
        if isinstance(fbc, str):
            fbc = json.loads(fbc)
        assert fbc["raw_cohort"] == expected

    def test_filter_in_cohort_extracts_to_filter_by_cohort(self, ws: Workspace) -> None:
        """Filter.in_cohort() in where list extracts to filter_by_cohort."""
        params = ws.build_user_params(
            where=[
                Filter.in_cohort(789),
                Filter.equals("plan", "premium"),
            ],
        )
        # The cohort filter should be extracted to filter_by_cohort
        assert "filter_by_cohort" in params
        fbc = params["filter_by_cohort"]
        if isinstance(fbc, str):
            fbc = json.loads(fbc)
        assert fbc["id"] == 789
        # Remaining property filter should stay in where
        assert 'properties["plan"] == "premium"' in params["where"]

    def test_no_cohort_omits_filter_by_cohort(self, ws: Workspace) -> None:
        """When no cohort is provided, filter_by_cohort should be absent."""
        params = ws.build_user_params(
            where=Filter.equals("plan", "premium"),
        )
        assert "filter_by_cohort" not in params


# =============================================================================
# 3. Property selection -> output_properties
# =============================================================================


class TestPropertySelection:
    """Tests for properties parameter mapping to output_properties."""

    def test_properties_maps_to_output_properties(self, ws: Workspace) -> None:
        """Properties list maps to output_properties in params."""
        params = ws.build_user_params(
            mode="profiles",
            properties=["$email", "$name", "plan"],
        )
        assert "output_properties" in params
        output = params["output_properties"]
        if isinstance(output, str):
            output = json.loads(output)
        assert "$email" in output
        assert "$name" in output
        assert "plan" in output

    def test_no_properties_omits_output_properties(self, ws: Workspace) -> None:
        """When properties is None, output_properties should not be present."""
        params = ws.build_user_params()
        assert "output_properties" not in params

    def test_properties_preserves_dollar_prefix(self, ws: Workspace) -> None:
        """Dollar-prefixed property names are passed through unchanged."""
        params = ws.build_user_params(
            mode="profiles",
            properties=["$email", "$last_seen"],
        )
        output = params["output_properties"]
        if isinstance(output, str):
            output = json.loads(output)
        assert "$email" in output
        assert "$last_seen" in output


# =============================================================================
# 4. sort_by -> sort_key translation
# =============================================================================


class TestSortByTranslation:
    """Tests for sort_by parameter translation to sort_key."""

    def test_sort_by_translates_to_sort_key(self, ws: Workspace) -> None:
        """sort_by='ltv' translates to sort_key='properties[\"ltv\"]'."""
        params = ws.build_user_params(mode="profiles", sort_by="ltv")
        assert "sort_key" in params
        assert params["sort_key"] == 'properties["ltv"]'

    def test_sort_by_with_dollar_prefix(self, ws: Workspace) -> None:
        """sort_by='$last_seen' translates with dollar prefix preserved."""
        params = ws.build_user_params(mode="profiles", sort_by="$last_seen")
        assert params["sort_key"] == 'properties["$last_seen"]'

    def test_no_sort_by_omits_sort_key(self, ws: Workspace) -> None:
        """When sort_by is None, sort_key should not be present."""
        params = ws.build_user_params()
        assert "sort_key" not in params

    def test_sort_order_passthrough(self, ws: Workspace) -> None:
        """sort_order is passed through to params."""
        params = ws.build_user_params(
            mode="profiles",
            sort_by="ltv",
            sort_order="ascending",
        )
        assert params["sort_order"] == "ascending"

    def test_default_sort_order_is_descending(self, ws: Workspace) -> None:
        """Default sort_order is 'descending'."""
        params = ws.build_user_params(mode="profiles", sort_by="ltv")
        assert params["sort_order"] == "descending"


# =============================================================================
# 5. as_of string -> Unix timestamp conversion
# =============================================================================


class TestAsOfConversion:
    """Tests for as_of parameter conversion to Unix timestamp."""

    def test_as_of_date_string_to_timestamp(self, ws: Workspace) -> None:
        """as_of='2025-01-01' converts to Unix timestamp (midnight UTC)."""
        params = ws.build_user_params(mode="profiles", as_of="2025-01-01")
        assert "as_of_timestamp" in params
        expected = calendar.timegm(date(2025, 1, 1).timetuple())
        assert params["as_of_timestamp"] == expected

    def test_as_of_integer_passthrough(self, ws: Workspace) -> None:
        """as_of=1704067200 (int) passes through directly as as_of_timestamp."""
        params = ws.build_user_params(mode="profiles", as_of=1704067200)
        assert "as_of_timestamp" in params
        assert params["as_of_timestamp"] == 1704067200

    def test_no_as_of_omits_timestamp(self, ws: Workspace) -> None:
        """When as_of is None, as_of_timestamp should not be present."""
        params = ws.build_user_params()
        assert "as_of_timestamp" not in params

    def test_as_of_date_produces_correct_epoch(self, ws: Workspace) -> None:
        """Verify the epoch value for a known date (2024-06-15)."""
        params = ws.build_user_params(mode="profiles", as_of="2024-06-15")
        expected = calendar.timegm(date(2024, 6, 15).timetuple())
        assert params["as_of_timestamp"] == expected


# =============================================================================
# 6. distinct_id / distinct_ids handling
# =============================================================================


class TestDistinctIdHandling:
    """Tests for distinct_id and distinct_ids parameter handling."""

    def test_distinct_id_passthrough(self, ws: Workspace) -> None:
        """distinct_id is passed through to params."""
        params = ws.build_user_params(mode="profiles", distinct_id="user_abc123")
        assert params["distinct_id"] == "user_abc123"

    def test_distinct_ids_passthrough(self, ws: Workspace) -> None:
        """distinct_ids is passed through to params."""
        params = ws.build_user_params(
            mode="profiles",
            distinct_ids=["user_1", "user_2", "user_3"],
        )
        distinct_ids = params["distinct_ids"]
        if isinstance(distinct_ids, str):
            distinct_ids = json.loads(distinct_ids)
        assert distinct_ids == ["user_1", "user_2", "user_3"]

    def test_no_distinct_id_omits_param(self, ws: Workspace) -> None:
        """When neither distinct_id nor distinct_ids provided, both are absent."""
        params = ws.build_user_params()
        assert "distinct_id" not in params
        assert "distinct_ids" not in params


# =============================================================================
# 7. group_id -> data_group_id
# =============================================================================


class TestGroupIdTranslation:
    """Tests for group_id parameter translation to data_group_id."""

    def test_group_id_maps_to_data_group_id(self, ws: Workspace) -> None:
        """group_id='companies' translates to data_group_id='companies'."""
        params = ws.build_user_params(group_id="companies")
        assert "data_group_id" in params
        assert params["data_group_id"] == "companies"

    def test_no_group_id_omits_data_group_id(self, ws: Workspace) -> None:
        """When group_id is None, data_group_id should not be present."""
        params = ws.build_user_params()
        assert "data_group_id" not in params


# =============================================================================
# 8. search passthrough
# =============================================================================


class TestSearchPassthrough:
    """Tests for search parameter passthrough."""

    def test_search_passthrough(self, ws: Workspace) -> None:
        """search string is passed through to params."""
        params = ws.build_user_params(mode="profiles", search="alice@example.com")
        assert params["search"] == "alice@example.com"

    def test_no_search_omits_param(self, ws: Workspace) -> None:
        """When search is None, it should not be present in params."""
        params = ws.build_user_params()
        assert "search" not in params


# =============================================================================
# 9. Raw string where passthrough
# =============================================================================


class TestRawStringWhere:
    """Tests for raw selector string passthrough in where parameter."""

    def test_raw_string_where_passthrough(self, ws: Workspace) -> None:
        """A raw selector string is passed directly to the where param."""
        raw = 'properties["plan"] == "premium" and properties["ltv"] > 100'
        params = ws.build_user_params(where=raw)
        assert params["where"] == raw

    def test_raw_string_not_translated(self, ws: Workspace) -> None:
        """A raw string is not modified or re-translated."""
        raw = 'user["custom_field"] == "value"'
        params = ws.build_user_params(where=raw)
        assert params["where"] == raw


# =============================================================================
# 10. Validation errors raised as BookmarkValidationError
# =============================================================================


class TestValidationErrors:
    """Tests for validation errors raised as BookmarkValidationError."""

    def test_distinct_id_and_distinct_ids_conflict(self, ws: Workspace) -> None:
        """Providing both distinct_id and distinct_ids raises BookmarkValidationError (U1)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(
                distinct_id="user_1",
                distinct_ids=["user_2"],
            )
        errors = exc_info.value.errors
        codes = [e.code for e in errors]
        assert "U1" in codes

    def test_cohort_and_filter_in_cohort_conflict(self, ws: Workspace) -> None:
        """Providing both cohort param and Filter.in_cohort() raises error (U2)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(
                cohort=123,
                where=Filter.in_cohort(456),
            )
        errors = exc_info.value.errors
        codes = [e.code for e in errors]
        assert "U2" in codes

    def test_empty_sort_by_raises_error(self, ws: Workspace) -> None:
        """Empty string sort_by raises BookmarkValidationError (U5)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(sort_by="")
        errors = exc_info.value.errors
        codes = [e.code for e in errors]
        assert "U5" in codes

    def test_invalid_as_of_date_raises_error(self, ws: Workspace) -> None:
        """Invalid date string for as_of raises BookmarkValidationError (U6)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(as_of="not-a-date")
        errors = exc_info.value.errors
        codes = [e.code for e in errors]
        assert "U6" in codes

    def test_include_all_users_without_cohort_raises_error(self, ws: Workspace) -> None:
        """include_all_users=True without cohort raises BookmarkValidationError (U7)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(include_all_users=True)
        errors = exc_info.value.errors
        codes = [e.code for e in errors]
        assert "U7" in codes

    def test_not_in_cohort_filter_raises_error(self, ws: Workspace) -> None:
        """Filter.not_in_cohort() in where raises BookmarkValidationError (U12)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(where=Filter.not_in_cohort(123))
        errors = exc_info.value.errors
        codes = [e.code for e in errors]
        assert "U12" in codes

    def test_multiple_in_cohort_filters_raises_error(self, ws: Workspace) -> None:
        """Multiple Filter.in_cohort() in where list raises BookmarkValidationError (U13)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(
                where=[
                    Filter.in_cohort(100),
                    Filter.in_cohort(200),
                ],
            )
        errors = exc_info.value.errors
        codes = [e.code for e in errors]
        assert "U13" in codes

    def test_empty_distinct_ids_raises_error(self, ws: Workspace) -> None:
        """Empty distinct_ids list raises BookmarkValidationError (U4)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(distinct_ids=[])
        errors = exc_info.value.errors
        codes = [e.code for e in errors]
        assert "U4" in codes

    def test_multiple_validation_errors_collected(self, ws: Workspace) -> None:
        """Multiple violations are collected into a single BookmarkValidationError."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(
                distinct_id="user_1",
                distinct_ids=["user_2"],
                sort_by="",
                include_all_users=True,
            )
        errors = exc_info.value.errors
        codes = [e.code for e in errors]
        # Should contain at least U1 (distinct conflict), U5 (empty sort_by),
        # and U7 (include_all without cohort)
        assert "U1" in codes
        assert "U5" in codes
        assert "U7" in codes


# =============================================================================
# Aggregate mode param construction
# =============================================================================


class TestAggregateModeParams:
    """Tests for mode='aggregate' parameter construction."""

    def test_aggregate_count_action(self, ws: Workspace) -> None:
        """mode='aggregate' with default count produces action='count()'."""
        params = ws.build_user_params(mode="aggregate")
        assert params.get("action") == "count()"

    def test_aggregate_numeric_summary_action(self, ws: Workspace) -> None:
        """mode='aggregate', aggregate='numeric_summary' produces correct action string."""
        params = ws.build_user_params(
            mode="aggregate",
            aggregate="numeric_summary",
            aggregate_property="ltv",
        )
        assert params.get("action") == 'numeric_summary(properties["ltv"])'

    def test_aggregate_extremes_action(self, ws: Workspace) -> None:
        """mode='aggregate', aggregate='extremes' produces correct action string."""
        params = ws.build_user_params(
            mode="aggregate",
            aggregate="extremes",
            aggregate_property="revenue",
        )
        assert params.get("action") == 'extremes(properties["revenue"])'

    def test_aggregate_percentile_action(self, ws: Workspace) -> None:
        """mode='aggregate', aggregate='percentile' produces correct action string."""
        params = ws.build_user_params(
            mode="aggregate",
            aggregate="percentile",
            aggregate_property="age",
            percentile=50,
        )
        assert params.get("action") == 'percentile(properties["age"], 50)'

    def test_aggregate_without_property_raises_error(self, ws: Workspace) -> None:
        """aggregate='extremes' without aggregate_property raises error (U14)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(
                mode="aggregate",
                aggregate="extremes",
            )
        codes = [e.code for e in exc_info.value.errors]
        assert "U14" in codes

    def test_aggregate_count_with_property_raises_error(self, ws: Workspace) -> None:
        """aggregate='count' with aggregate_property raises error (U15)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(
                mode="aggregate",
                aggregate="count",
                aggregate_property="ltv",
            )
        codes = [e.code for e in exc_info.value.errors]
        assert "U15" in codes

    def test_segment_by_maps_to_segment_by_cohorts(self, ws: Workspace) -> None:
        """segment_by cohort IDs map to segment_by_cohorts dict."""
        params = ws.build_user_params(
            mode="aggregate",
            segment_by=[123, 456],
        )
        assert "segment_by_cohorts" in params

    def test_segment_by_requires_aggregate_mode(self, ws: Workspace) -> None:
        """segment_by with mode='profiles' raises error (U16)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(
                mode="profiles",
                segment_by=[123],
            )
        codes = [e.code for e in exc_info.value.errors]
        assert "U16" in codes


# =============================================================================
# Mode-specific profile-only params with aggregate mode
# =============================================================================


class TestModeSpecificValidation:
    """Tests for params that only apply to mode='profiles'."""

    def test_sort_by_in_aggregate_mode_raises_error(self, ws: Workspace) -> None:
        """sort_by with mode='aggregate' raises error (U19)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(
                mode="aggregate",
                sort_by="ltv",
            )
        codes = [e.code for e in exc_info.value.errors]
        assert "U19" in codes

    def test_search_in_aggregate_mode_raises_error(self, ws: Workspace) -> None:
        """search with mode='aggregate' raises error (U20)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(
                mode="aggregate",
                search="alice",
            )
        codes = [e.code for e in exc_info.value.errors]
        assert "U20" in codes

    def test_distinct_id_in_aggregate_mode_raises_error(self, ws: Workspace) -> None:
        """distinct_id with mode='aggregate' raises error (U21)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(
                mode="aggregate",
                distinct_id="user_1",
            )
        codes = [e.code for e in exc_info.value.errors]
        assert "U21" in codes

    def test_properties_in_aggregate_mode_raises_error(self, ws: Workspace) -> None:
        """properties with mode='aggregate' raises error (U22)."""
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_user_params(
                mode="aggregate",
                properties=["$email"],
            )
        codes = [e.code for e in exc_info.value.errors]
        assert "U22" in codes


# =============================================================================
# Combined param scenarios
# =============================================================================


class TestCombinedScenarios:
    """Tests for realistic multi-parameter combinations."""

    def test_full_profile_query_params(self, ws: Workspace) -> None:
        """A full profile query produces all expected params."""
        params = ws.build_user_params(
            mode="profiles",
            where=[
                Filter.equals("plan", "premium"),
                Filter.greater_than("ltv", 100),
            ],
            properties=["$email", "$name", "plan", "ltv"],
            sort_by="ltv",
            sort_order="descending",
            search="alice",
        )
        # where has both filters AND-combined
        assert "where" in params
        assert 'properties["plan"] == "premium"' in params["where"]
        assert 'properties["ltv"] > 100' in params["where"]
        # output_properties set
        output = params["output_properties"]
        if isinstance(output, str):
            output = json.loads(output)
        assert "$email" in output
        # sort_key translated
        assert params["sort_key"] == 'properties["ltv"]'
        assert params["sort_order"] == "descending"
        # search passthrough
        assert params["search"] == "alice"

    def test_cohort_with_where_filters(self, ws: Workspace) -> None:
        """cohort param combined with property where filters both appear."""
        params = ws.build_user_params(
            cohort=12345,
            where=Filter.equals("plan", "premium"),
        )
        assert "filter_by_cohort" in params
        assert 'properties["plan"] == "premium"' in params["where"]

    def test_include_all_users_with_cohort(self, ws: Workspace) -> None:
        """include_all_users=True with cohort does not raise error."""
        params = ws.build_user_params(
            cohort=12345,
            include_all_users=True,
        )
        assert "filter_by_cohort" in params

    def test_group_id_with_filters(self, ws: Workspace) -> None:
        """group_id combined with where filters produces correct params."""
        params = ws.build_user_params(
            mode="profiles",
            group_id="companies",
            where=Filter.greater_than("arr", 50000),
            sort_by="arr",
            sort_order="descending",
        )
        assert params["data_group_id"] == "companies"
        assert 'properties["arr"] > 50000' in params["where"]
        assert params["sort_key"] == 'properties["arr"]'

    def test_as_of_with_distinct_id(self, ws: Workspace) -> None:
        """as_of combined with distinct_id produces both params."""
        params = ws.build_user_params(
            mode="profiles",
            as_of="2025-01-01",
            distinct_id="user_123",
        )
        assert "as_of_timestamp" in params
        assert params["distinct_id"] == "user_123"

    def test_valid_params_do_not_raise(self, ws: Workspace) -> None:
        """Valid parameter combinations complete without raising."""
        # Should not raise
        ws.build_user_params(
            mode="profiles",
            where=Filter.equals("plan", "premium"),
            properties=["$email"],
            sort_by="ltv",
            sort_order="ascending",
        )

    def test_empty_call_returns_dict(self, ws: Workspace) -> None:
        """Calling build_user_params() with no arguments returns a dict."""
        params = ws.build_user_params()
        assert isinstance(params, dict)
