"""Property-based tests for bookmark builder delegation wiring.

Uses Hypothesis to verify that ``_build_query_params()`` correctly
delegates to the extracted builder functions. These tests confirm
that the wiring between the composed method and the standalone
helpers is correct across randomized inputs.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless._internal.bookmark_builders import (
    build_filter_entry,
    build_filter_section,
    build_group_section,
    build_time_section,
)
from mixpanel_headless.types import Filter, GroupBy
from tests.conftest import make_session

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

# =============================================================================
# Strategies
# =============================================================================

date_strs = st.from_regex(
    r"20[2-3][0-9]-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])", fullmatch=True
)
time_units = st.sampled_from(["hour", "day", "week", "month", "quarter"])
positive_ints = st.integers(min_value=1, max_value=365)
event_names = st.text(
    min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N", "P"))
)
property_names = st.text(
    min_size=1, max_size=30, alphabet=st.characters(categories=("L", "N"))
)


def _make_workspace() -> Workspace:
    """Create a Workspace with mocked config for testing.

    Returns:
        Workspace instance with mock credentials.
    """
    creds = make_session(
        username="test",
        secret="secret",
        project_id="12345",
        region="us",
    )
    mgr = MagicMock()
    mgr.config_version.return_value = 1
    mgr.resolve_credentials.return_value = creds
    return Workspace(session=_TEST_SESSION)


# =============================================================================
# Wiring Tests: build_time_section matches _build_query_params
# =============================================================================


class TestTimeSectionEquivalence:
    """Verify build_time_section() matches _build_query_params() time output."""

    @given(unit=time_units, last=positive_ints)
    @settings(max_examples=50)
    def test_relative_range_equivalence(self, unit: str, last: int) -> None:
        """Relative time range: build_time_section matches inline code.

        Args:
            unit: Time unit.
            last: Number of days for relative range.
        """
        ws = _make_workspace()
        params = ws._build_query_params(
            events=["TestEvent"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=last,
            unit=unit,  # type: ignore[arg-type]
            group_by=None,
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        direct = build_time_section(from_date=None, to_date=None, last=last, unit=unit)  # type: ignore[arg-type]
        assert params["sections"]["time"] == direct

    @given(
        from_date=date_strs,
        to_date=date_strs,
        unit=time_units,
    )
    @settings(max_examples=50)
    def test_absolute_range_equivalence(
        self, from_date: str, to_date: str, unit: str
    ) -> None:
        """Absolute time range: build_time_section matches inline code.

        Args:
            from_date: Start date string.
            to_date: End date string.
            unit: Time unit.
        """
        # Ensure from_date <= to_date for valid date range
        if from_date > to_date:
            from_date, to_date = to_date, from_date

        ws = _make_workspace()
        params = ws._build_query_params(
            events=["TestEvent"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=from_date,
            to_date=to_date,
            last=30,
            unit=unit,  # type: ignore[arg-type]
            group_by=None,
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        direct = build_time_section(
            from_date=from_date,
            to_date=to_date,
            last=30,
            unit=unit,  # type: ignore[arg-type]
        )
        assert params["sections"]["time"] == direct


# =============================================================================
# Wiring Tests: build_filter_section matches _build_query_params
# =============================================================================


class TestFilterSectionEquivalence:
    """Verify build_filter_section() matches _build_query_params() filter output."""

    @given(prop=property_names, value=property_names)
    @settings(max_examples=50)
    def test_single_filter_equivalence(self, prop: str, value: str) -> None:
        """Single filter: build_filter_section matches inline code.

        Args:
            prop: Property name.
            value: Filter value.
        """
        f = Filter.equals(prop, value)
        ws = _make_workspace()
        params = ws._build_query_params(
            events=["TestEvent"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=f,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        direct = build_filter_section(f)
        assert params["sections"]["filter"] == direct

    def test_none_filter_equivalence(self) -> None:
        """None filter: build_filter_section returns empty list.

        Matches _build_query_params behavior with where=None.
        """
        ws = _make_workspace()
        params = ws._build_query_params(
            events=["TestEvent"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        direct = build_filter_section(None)
        assert params["sections"]["filter"] == direct == []


# =============================================================================
# Wiring Tests: build_group_section matches _build_query_params
# =============================================================================


class TestGroupSectionEquivalence:
    """Verify build_group_section() matches _build_query_params() group output."""

    @given(prop=property_names)
    @settings(max_examples=50)
    def test_string_group_equivalence(self, prop: str) -> None:
        """String group_by: build_group_section matches inline code.

        Args:
            prop: Property name.
        """
        ws = _make_workspace()
        params = ws._build_query_params(
            events=["TestEvent"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=prop,
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        direct = build_group_section(prop)
        assert params["sections"]["group"] == direct

    @given(
        prop=property_names,
        bucket_size=st.floats(
            min_value=0.1, max_value=1000.0, allow_nan=False, allow_infinity=False
        ),
        bucket_min=st.floats(
            min_value=-1000.0, max_value=0.0, allow_nan=False, allow_infinity=False
        ),
        bucket_max=st.floats(
            min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(max_examples=30)
    def test_groupby_with_buckets_equivalence(
        self,
        prop: str,
        bucket_size: float,
        bucket_min: float,
        bucket_max: float,
    ) -> None:
        """GroupBy with buckets: build_group_section matches inline code.

        Args:
            prop: Property name.
            bucket_size: Bucket width.
            bucket_min: Minimum bucket value.
            bucket_max: Maximum bucket value.
        """
        g = GroupBy(
            prop,
            property_type="number",
            bucket_size=bucket_size,
            bucket_min=bucket_min,
            bucket_max=bucket_max,
        )
        ws = _make_workspace()
        params = ws._build_query_params(
            events=["TestEvent"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=g,
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        direct = build_group_section(g)
        assert params["sections"]["group"] == direct

    def test_none_group_equivalence(self) -> None:
        """None group_by: build_group_section returns empty list.

        Matches _build_query_params behavior with group_by=None.
        """
        ws = _make_workspace()
        params = ws._build_query_params(
            events=["TestEvent"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        direct = build_group_section(None)
        assert params["sections"]["group"] == direct == []


# =============================================================================
# Round-trip invariants for Filter.list_contains
# =============================================================================


# Subproperty names: any non-empty identifier-like string. Hypothesis-generated
# kwargs require valid Python identifiers, so restrict alphabet accordingly.
_subprop_names = st.text(
    min_size=1,
    max_size=10,
    alphabet=st.characters(categories=["L"]),  # letters only
)


class TestListContainsRoundTrip:
    """Round-trip invariants for ``Filter.list_contains`` serialization."""

    @given(
        prop=property_names,
        pairs=st.dictionaries(
            keys=_subprop_names,
            values=st.text(min_size=1, max_size=20),
            min_size=1,
            max_size=5,
        ),
        quantifier=st.sampled_from(["any", "all"]),
    )
    @settings(max_examples=50)
    def test_kwargs_shape_invariants(
        self, prop: str, pairs: dict[str, str], quantifier: str
    ) -> None:
        """Kwargs shorthand always emits the listItemFilters wire shape."""
        f = Filter.list_contains(prop, quantifier=quantifier, **pairs)  # type: ignore[arg-type]
        entry = build_filter_entry(f)
        assert entry["filterType"] == "object"
        assert entry["defaultType"] == "object"
        assert entry["filterJoinType"] == "list"
        assert entry["listQuantifier"] == quantifier
        assert entry["filterOperator"] == "true"
        assert entry["filterValue"] is True
        assert entry["dataset"] == "$mixpanel"
        assert entry["value"] == prop
        assert len(entry["listItemFilters"]) == len(pairs)
        for sub in entry["listItemFilters"]:
            assert sub["dataset"] == "$mixpanel"
            assert sub["filterOperator"] == "equals"
            assert sub["filterType"] == "string"
            # Each sub's value+filterValue should appear in the original pairs dict
            assert sub["value"] in pairs
            assert sub["filterValue"] == [pairs[sub["value"]]]
        # Completeness: every original kwarg must show up exactly once.
        # set() de-duplicates if Hypothesis ever picks the same value
        # for two keys; the count check above handles the per-key side.
        emitted_keys = {sub["value"] for sub in entry["listItemFilters"]}
        assert emitted_keys == set(pairs.keys())
