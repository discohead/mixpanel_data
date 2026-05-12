"""Property-based tests for retention query types using Hypothesis.

These tests verify invariants of RetentionEvent, RetentionQueryResult,
and _build_retention_params that should hold for all possible inputs,
catching edge cases that example-based tests miss.

Usage:
    # Run with default profile (100 examples)
    pytest tests/test_types_retention_pbt.py

    # Run with dev profile (10 examples, verbose)
    HYPOTHESIS_PROFILE=dev pytest tests/test_types_retention_pbt.py

    # Run with CI profile (200 examples, deterministic)
    HYPOTHESIS_PROFILE=ci pytest tests/test_types_retention_pbt.py
"""

from __future__ import annotations

import dataclasses
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.types import RetentionEvent, RetentionQueryResult
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
# Custom Strategies
# =============================================================================

# Strategy for event names (non-empty visible characters only)
event_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())


@st.composite
def cohort_dicts(
    draw: st.DrawFn,
) -> dict[str, dict[str, Any]]:
    """Generate random cohort dicts matching RetentionQueryResult.cohorts shape.

    Each cohort has a date key mapping to a dict with ``first`` (cohort size),
    ``counts`` (list of retained user counts), and ``rates`` (list of retention
    rates derived from counts/first).

    Args:
        draw: Hypothesis draw function for composing strategies.

    Returns:
        A dict mapping date strings to cohort data dicts.
    """
    n_cohorts = draw(st.integers(min_value=0, max_value=5))
    cohorts: dict[str, dict[str, Any]] = {}
    for i in range(n_cohorts):
        date = f"2025-01-{i + 1:02d}"
        n_buckets = draw(st.integers(min_value=0, max_value=10))
        first = draw(st.integers(min_value=1, max_value=1000))
        counts = [
            draw(st.integers(min_value=0, max_value=first)) for _ in range(n_buckets)
        ]
        rates = [c / first if first > 0 else 0.0 for c in counts]
        cohorts[date] = {"first": first, "counts": counts, "rates": rates}
    return cohorts


# =============================================================================
# Helpers
# =============================================================================


def _make_workspace() -> Workspace:
    """Create a Workspace instance with mocked dependencies.

    Uses dependency injection so no real credentials or network access
    are needed.  Built as a plain function (not a pytest fixture) so it
    can be called inside ``@given``-decorated tests without triggering
    Hypothesis's ``function_scoped_fixture`` health check.

    Returns:
        A Workspace with mocked ConfigManager and MixpanelAPIClient.
    """
    creds = make_session(
        username="test_user",
        secret="test_secret",
        project_id="12345",
        region="us",
    )
    manager = MagicMock()
    manager.config_version.return_value = 1
    manager.resolve_credentials.return_value = creds
    client = MagicMock(spec=MixpanelAPIClient)
    client.close = MagicMock()
    return Workspace(
        session=_TEST_SESSION,
        _api_client=client,
    )


# =============================================================================
# T051: RetentionEvent Property Tests
# =============================================================================


class TestRetentionEventPBT:
    """Property-based tests for RetentionEvent frozen dataclass.

    Verifies immutability, equality, and field preservation invariants
    that should hold for all possible RetentionEvent instances.
    """

    @given(event=event_names)
    def test_immutability(self, event: str) -> None:
        """Setting any attribute on a frozen RetentionEvent raises an error.

        Generates random RetentionEvent instances and verifies that
        assigning to any of the three fields (event, filters,
        filters_combinator) raises ``FrozenInstanceError``.
        """
        re = RetentionEvent(event=event)
        with pytest.raises(dataclasses.FrozenInstanceError):
            re.event = "other"  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            re.filters = []  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            re.filters_combinator = "any"  # type: ignore[misc]

    @given(event=event_names)
    def test_equality(self, event: str) -> None:
        """Two RetentionEvent instances with the same arguments are equal.

        Frozen dataclasses generate ``__eq__`` based on field values,
        so structurally identical instances must compare equal.
        """
        a = RetentionEvent(event=event)
        b = RetentionEvent(event=event)
        assert a == b

    @given(event=event_names)
    def test_field_preservation(self, event: str) -> None:
        """The event field is preserved exactly as given across random strings.

        Verifies that no normalization, stripping, or transformation
        occurs on the event name during construction.
        """
        re = RetentionEvent(event=event)
        assert re.event == event


# =============================================================================
# T052: RetentionQueryResult Property Tests
# =============================================================================


class TestRetentionQueryResultPBT:
    """Property-based tests for RetentionQueryResult.

    Verifies DataFrame shape, column presence, and deterministic
    conversion invariants across randomly generated cohort data.
    """

    @given(cohorts=cohort_dicts())
    def test_df_row_count_matches_cohorts(
        self, cohorts: dict[str, dict[str, Any]]
    ) -> None:
        """DataFrame row count equals sum of bucket counts across all cohorts.

        Each cohort contributes ``len(counts)`` rows to the DataFrame,
        so the total row count must equal the sum across all cohorts.
        """
        result = RetentionQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date="2025-01-01",
            to_date="2025-01-31",
            cohorts=cohorts,
        )
        expected_rows = sum(len(c["counts"]) for c in cohorts.values())
        assert len(result.df) == expected_rows

    @given(cohorts=cohort_dicts())
    def test_df_always_has_four_columns(
        self, cohorts: dict[str, dict[str, Any]]
    ) -> None:
        """DataFrame always has exactly 4 columns: cohort_date, bucket, count, rate.

        Regardless of input shape (empty cohorts, zero buckets, many
        buckets), the column set must be exactly these four in order.
        """
        result = RetentionQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date="2025-01-01",
            to_date="2025-01-31",
            cohorts=cohorts,
        )
        expected_columns = ["cohort_date", "bucket", "count", "rate"]
        assert list(result.df.columns) == expected_columns

    @given(cohorts=cohort_dicts())
    def test_deterministic_conversion(self, cohorts: dict[str, dict[str, Any]]) -> None:
        """Calling .df twice on the same instance returns identical DataFrames.

        The cached DataFrame must be structurally identical across
        repeated accesses, ensuring deterministic conversion.
        """
        result = RetentionQueryResult(
            computed_at="2025-01-01T00:00:00",
            from_date="2025-01-01",
            to_date="2025-01-31",
            cohorts=cohorts,
        )
        df1 = result.df
        df2 = result.df
        pd.testing.assert_frame_equal(df1, df2)


# =============================================================================
# T053: _build_retention_params Property Tests
# =============================================================================


class TestBuildRetentionParamsPBT:
    """Property-based tests for Workspace.build_retention_params output structure.

    Verifies that for any valid born/return event name inputs, the output
    always has the expected top-level structure, behavior count, and chart
    type values.

    Uses ``_make_workspace()`` instead of pytest fixtures to avoid
    Hypothesis's ``function_scoped_fixture`` health check.
    """

    @given(
        born=event_names,
        ret=event_names,
    )
    def test_always_has_sections_and_display_options(self, born: str, ret: str) -> None:
        """For any valid born/return event names, result has sections and displayOptions.

        These two top-level keys are required for the bookmark JSON to be
        valid. They must always be present regardless of event names.
        """
        ws = _make_workspace()
        result = ws.build_retention_params(born, ret)
        assert "sections" in result
        assert "displayOptions" in result

    @given(
        born=event_names,
        ret=event_names,
    )
    def test_behavior_count_always_two(self, born: str, ret: str) -> None:
        """The behaviors list always has exactly 2 entries (born + return).

        Retention queries always require exactly one born event and one
        return event, so the behaviors array must always have length 2.
        """
        ws = _make_workspace()
        result = ws.build_retention_params(born, ret)
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert len(behaviors) == 2

    @given(mode=st.sampled_from(["curve", "trends", "table"]))
    def test_chart_type_always_valid(self, mode: str) -> None:
        """chartType is always one of 'retention-curve', 'line', or 'table'.

        Each mode maps to a specific chart type. The mapping must produce
        only valid chart type strings for the retention report.
        """
        ws = _make_workspace()
        result = ws.build_retention_params("Signup", "Login", mode=mode)  # type: ignore[arg-type]
        valid_chart_types = {"retention-curve", "line", "table"}
        assert result["displayOptions"]["chartType"] in valid_chart_types
