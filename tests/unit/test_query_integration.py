"""Integration tests for Workspace.query() end-to-end with mocked HTTP.

Tests the full flow: query() -> validate -> build params -> API call -> transform -> QueryResult.
Uses MagicMock for API client to simulate Mixpanel responses.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Filter, Formula, Metric, Workspace
from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.exceptions import QueryError
from mixpanel_headless.types import QueryResult

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
# Fixtures
# =============================================================================


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create mock API client for testing."""
    client = MagicMock(spec=MixpanelAPIClient)
    client.close = MagicMock()
    return client


@pytest.fixture
def ws(mock_config_manager: MagicMock, mock_api_client: MagicMock) -> Workspace:
    """Create Workspace with mocked API client for integration testing."""
    workspace = Workspace(session=_TEST_SESSION)
    workspace._api_client = mock_api_client
    return workspace


TIMESERIES_RESPONSE: dict[str, Any] = {
    "computed_at": "2024-01-31T12:00:00+00:00",
    "date_range": {
        "from_date": "2024-01-01T00:00:00-07:00",
        "to_date": "2024-01-31T23:59:59.999000-07:00",
    },
    "headers": ["$metric"],
    "series": {
        "Login [Total Events]": {
            "2024-01-01T00:00:00-07:00": 100,
            "2024-01-02T00:00:00-07:00": 200,
            "2024-01-03T00:00:00-07:00": 150,
        },
    },
    "meta": {
        "min_sampling_factor": 1.0,
        "is_segmentation_limit_hit": False,
        "sub_query_count": 1,
    },
}

TOTAL_RESPONSE: dict[str, Any] = {
    "computed_at": "2024-01-31T12:00:00+00:00",
    "date_range": {
        "from_date": "2024-01-01T00:00:00-07:00",
        "to_date": "2024-01-31T23:59:59.999000-07:00",
    },
    "headers": ["$metric"],
    "series": {
        "Login [Unique Users]": {"all": 3551},
    },
    "meta": {
        "min_sampling_factor": 1.0,
        "is_segmentation_limit_hit": False,
    },
}

EMPTY_RESPONSE: dict[str, Any] = {
    "computed_at": "2024-01-31T12:00:00+00:00",
    "date_range": {
        "from_date": "2024-01-01T00:00:00-07:00",
        "to_date": "2024-01-31T23:59:59.999000-07:00",
    },
    "headers": ["$metric"],
    "series": {},
    "meta": {},
}


# =============================================================================
# T009: End-to-end query with mocked HTTP response (timeseries)
# =============================================================================


class TestQueryTimeseries:
    """Integration tests for timeseries query mode."""

    def test_basic_query_returns_query_result(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """query("Login") returns a QueryResult."""
        mock_api_client.insights_query.return_value = TIMESERIES_RESPONSE
        result = ws.query("Login")
        assert isinstance(result, QueryResult)

    def test_basic_query_computed_at(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """QueryResult has computed_at from response."""
        mock_api_client.insights_query.return_value = TIMESERIES_RESPONSE
        result = ws.query("Login")
        assert result.computed_at == "2024-01-31T12:00:00+00:00"

    def test_basic_query_date_range(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """QueryResult extracts nested date_range fields."""
        mock_api_client.insights_query.return_value = TIMESERIES_RESPONSE
        result = ws.query("Login")
        assert "2024-01-01" in result.from_date
        assert "2024-01-31" in result.to_date

    def test_basic_query_series(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """QueryResult contains the series data."""
        mock_api_client.insights_query.return_value = TIMESERIES_RESPONSE
        result = ws.query("Login")
        assert "Login [Total Events]" in result.series

    def test_basic_query_df_shape(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """Timeseries DataFrame has 3 rows and date/event/count columns."""
        mock_api_client.insights_query.return_value = TIMESERIES_RESPONSE
        result = ws.query("Login")
        df = result.df
        assert len(df) == 3
        assert list(df.columns) == ["date", "event", "count"]

    def test_query_passes_bookmark_params(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """insights_query is called with correct body structure."""
        mock_api_client.insights_query.return_value = TIMESERIES_RESPONSE
        ws.query("Login")
        call_args = mock_api_client.insights_query.call_args
        body = call_args[1]["body"] if "body" in call_args[1] else call_args[0][0]
        assert "bookmark" in body
        assert "project_id" in body
        assert body["project_id"] == 12345
        assert "queryLimits" in body

    def test_result_params_populated(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """QueryResult.params contains the bookmark dict."""
        mock_api_client.insights_query.return_value = TIMESERIES_RESPONSE
        result = ws.query("Login")
        assert isinstance(result.params, dict)
        assert "sections" in result.params

    def test_result_meta_populated(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """QueryResult.meta contains response metadata."""
        mock_api_client.insights_query.return_value = TIMESERIES_RESPONSE
        result = ws.query("Login")
        assert "min_sampling_factor" in result.meta


# =============================================================================
# T009b: Query with non-existent event (empty response)
# =============================================================================


class TestQueryNonExistentEvent:
    """Tests for query with non-existent event name."""

    def test_empty_response_no_exception(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """Query with non-existent event returns empty DataFrame, no exception."""
        mock_api_client.insights_query.return_value = EMPTY_RESPONSE
        result = ws.query("NonExistentEvent")
        assert isinstance(result, QueryResult)
        assert len(result.df) == 0

    def test_empty_response_has_metadata(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """Empty result still has computed_at and date range."""
        mock_api_client.insights_query.return_value = EMPTY_RESPONSE
        result = ws.query("NonExistentEvent")
        assert result.computed_at == "2024-01-31T12:00:00+00:00"


# =============================================================================
# T033: Multi-event integration (US4)
# =============================================================================


MULTI_EVENT_RESPONSE: dict[str, Any] = {
    "computed_at": "2024-01-31T12:00:00+00:00",
    "date_range": {
        "from_date": "2024-01-01T00:00:00-07:00",
        "to_date": "2024-01-31T23:59:59.999000-07:00",
    },
    "headers": ["$metric"],
    "series": {
        "Signup [Unique Users]": {"2024-01-01": 50},
        "Login [Unique Users]": {"2024-01-01": 200},
        "Purchase [Unique Users]": {"2024-01-01": 30},
    },
    "meta": {},
}


class TestMultiEventIntegration:
    """Integration tests for multi-event queries."""

    def test_multi_event_df_has_all_metrics(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """Multi-event query returns DataFrame with all metrics."""
        mock_api_client.insights_query.return_value = MULTI_EVENT_RESPONSE
        result = ws.query(["Signup", "Login", "Purchase"], math="unique")
        assert len(result.df) == 3
        events = set(result.df["event"])
        assert len(events) == 3


# =============================================================================
# T037: Formula integration (US5)
# =============================================================================


FORMULA_RESPONSE: dict[str, Any] = {
    "computed_at": "2024-01-31T12:00:00+00:00",
    "date_range": {
        "from_date": "2024-01-01T00:00:00-07:00",
        "to_date": "2024-01-07T23:59:59.999000-07:00",
    },
    "headers": ["$metric"],
    "series": {
        "Conversion Rate": {"2024-01-01": 15.5, "2024-01-02": 18.2},
    },
    "meta": {},
}


class TestFormulaIntegration:
    """Integration tests for formula queries."""

    def test_formula_query_result(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """Formula query returns result with formula series."""
        from mixpanel_headless import Metric

        mock_api_client.insights_query.return_value = FORMULA_RESPONSE
        result = ws.query(
            [Metric("Signup", math="unique"), Metric("Purchase", math="unique")],
            formula="(B / A) * 100",
            formula_label="Conversion Rate",
        )
        assert "Conversion Rate" in result.series
        assert len(result.df) == 2


# =============================================================================
# T046: Total mode integration (US7)
# =============================================================================


class TestTotalModeIntegration:
    """Integration tests for total mode queries."""

    def test_total_mode_single_row(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """Total mode returns single row per metric."""
        mock_api_client.insights_query.return_value = TOTAL_RESPONSE
        result = ws.query("Login", math="unique", mode="total")
        df = result.df
        assert len(df) == 1
        assert list(df.columns) == ["event", "count"]
        assert df.iloc[0]["count"] == 3551


# =============================================================================
# T050: Query result persistence (US8)
# =============================================================================


class TestQueryPersistence:
    """Tests for query result debugging and persistence."""

    def test_result_params_can_create_bookmark(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """result.params contains the bookmark dict suitable for create_bookmark."""
        mock_api_client.insights_query.return_value = TIMESERIES_RESPONSE
        result = ws.query("Login", math="unique", last=7)
        # Params should have sections and displayOptions
        assert "sections" in result.params
        assert "displayOptions" in result.params
        assert "show" in result.params["sections"]


# =============================================================================
# Response validation in _transform_query_result
# =============================================================================


class TestTransformQueryResultValidation:
    """Tests for error handling in _transform_query_result."""

    def test_error_as_200_raises_query_error(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """API returning error in 200 response raises QueryError."""
        error_response: dict[str, Any] = {
            "error": "invalid query",
            "status": "fail",
        }
        mock_api_client.insights_query.return_value = error_response
        with pytest.raises(QueryError, match="Insights query failed: invalid query"):
            ws.query("Login")

    def test_missing_series_raises_query_error(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """Response missing 'series' key raises QueryError."""
        malformed_response: dict[str, Any] = {
            "computed_at": "2024-01-31T12:00:00+00:00",
            "date_range": {"from_date": "2024-01-01", "to_date": "2024-01-31"},
            "headers": [],
            "meta": {},
        }
        mock_api_client.insights_query.return_value = malformed_response
        with pytest.raises(QueryError, match="missing 'series' key"):
            ws.query("Login")

    def test_valid_response_no_error(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """Valid response with series key succeeds."""
        mock_api_client.insights_query.return_value = TIMESERIES_RESPONSE
        result = ws.query("Login")
        assert isinstance(result, QueryResult)
        assert "Login [Total Events]" in result.series


# =============================================================================
# Formula-in-list integration tests
# =============================================================================


class TestFormulaInListIntegration:
    """Tests for Formula objects in the events list via ws.query()."""

    def test_formula_in_list_produces_correct_params(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """Formula in events list produces formula show clause."""
        mock_api_client.insights_query.return_value = TIMESERIES_RESPONSE
        result = ws.query(
            [
                Metric("Signup", math="unique"),
                Metric("Purchase", math="unique"),
                Formula("(B / A) * 100", label="Conversion %"),
            ],
        )
        show = result.params["sections"]["show"]
        assert len(show) == 3
        assert show[0]["behavior"]["name"] == "Signup"
        assert show[1]["behavior"]["name"] == "Purchase"
        assert show[2]["type"] == "formula"
        assert show[2]["definition"] == "(B / A) * 100"
        assert show[2]["name"] == "Conversion %"

    def test_formula_in_list_hides_metrics(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """Metrics are hidden when Formula is in the list."""
        mock_api_client.insights_query.return_value = TIMESERIES_RESPONSE
        result = ws.query(
            [Metric("A", math="unique"), Metric("B", math="unique"), Formula("A / B")],
        )
        show = result.params["sections"]["show"]
        assert show[0]["isHidden"] is True
        assert show[1]["isHidden"] is True

    def test_filters_combinator_in_query(
        self, ws: Workspace, mock_api_client: MagicMock
    ) -> None:
        """Metric with filters_combinator='any' emits correct params."""
        mock_api_client.insights_query.return_value = TIMESERIES_RESPONSE
        result = ws.query(
            Metric(
                "Login",
                filters=[Filter.equals("$browser", "Chrome")],
                filters_combinator="any",
            ),
        )
        behavior = result.params["sections"]["show"][0]["behavior"]
        assert behavior["filtersDeterminer"] == "any"


# =============================================================================
# T054d: build_params() does not invoke API
# =============================================================================


class TestBuildParamsNoApiCall:
    """T054d: build_params() does not invoke the API."""

    def test_does_not_call_api(self, ws: Workspace, mock_api_client: MagicMock) -> None:
        """build_params() returns params without calling API client."""
        result = ws.build_params("Login")
        mock_api_client.insights_query.assert_not_called()
        assert isinstance(result, dict)

    def test_works_without_credentials(self, mock_config_manager: MagicMock) -> None:
        """build_params() does not require live credentials."""
        workspace = Workspace(session=_TEST_SESSION)
        # No _api_client set at all
        result = workspace.build_params("Login")
        assert "sections" in result
