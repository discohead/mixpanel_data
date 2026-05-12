"""Integration tests for Workspace.query_retention().

Tests cover:
- T019: Workspace integration — mocking insights_query() to verify the API
  call body, response transformation, and RetentionQueryResult fields.
- ConfigError when credentials are missing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.types import RetentionQueryResult

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


MOCK_RETENTION_RESPONSE: dict[str, Any] = {
    "computed_at": "2025-01-15T12:00:00",
    "date_range": {"from_date": "2025-01-01", "to_date": "2025-01-31"},
    "series": {
        "Signup and then Login": {
            "2025-01-01": {
                "first": 100,
                "counts": [100, 50, 25],
                "rates": [1.0, 0.5, 0.25],
            },
            "$average": {
                "first": 100,
                "counts": [100, 50, 25],
                "rates": [1.0, 0.5, 0.25],
            },
        }
    },
    "meta": {"sampling_factor": 1.0},
}
"""Canonical mock response for a retention query."""


# =============================================================================
# T019: Workspace integration tests
# =============================================================================


class TestQueryRetentionIntegration:
    """Tests for query_retention() integration with mocked API.

    Verifies that query_retention() sends the correct body to
    insights_query(), and that the response is correctly transformed
    into a RetentionQueryResult.
    """

    def test_correct_body_sent_to_api(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T019-body: query_retention() sends body with bookmark, project_id, queryLimits."""
        mock_api_client.insights_query.return_value = MOCK_RETENTION_RESPONSE
        ws = workspace_factory()
        try:
            ws.query_retention("Signup", "Login")

            mock_api_client.insights_query.assert_called_once()
            body = mock_api_client.insights_query.call_args[0][0]

            assert "bookmark" in body
            assert "project_id" in body
            assert "queryLimits" in body
            assert body["project_id"] == 12345
        finally:
            ws.close()

    def test_result_is_retention_query_result(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T019-type: query_retention() returns a RetentionQueryResult instance."""
        mock_api_client.insights_query.return_value = MOCK_RETENTION_RESPONSE
        ws = workspace_factory()
        try:
            result = ws.query_retention("Signup", "Login")

            assert isinstance(result, RetentionQueryResult)
        finally:
            ws.close()

    def test_result_has_cohorts(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T019-cohorts: result cohorts has the right date keys (excluding $average)."""
        mock_api_client.insights_query.return_value = MOCK_RETENTION_RESPONSE
        ws = workspace_factory()
        try:
            result = ws.query_retention("Signup", "Login")

            assert "2025-01-01" in result.cohorts
            assert "$average" not in result.cohorts
            cohort = result.cohorts["2025-01-01"]
            assert cohort["first"] == 100
            assert cohort["counts"] == [100, 50, 25]
            assert cohort["rates"] == [1.0, 0.5, 0.25]
        finally:
            ws.close()

    def test_result_has_average(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T019-average: result average is populated from $average series entry."""
        mock_api_client.insights_query.return_value = MOCK_RETENTION_RESPONSE
        ws = workspace_factory()
        try:
            result = ws.query_retention("Signup", "Login")

            assert result.average is not None
            assert result.average["first"] == 100
            assert result.average["counts"] == [100, 50, 25]
            assert result.average["rates"] == [1.0, 0.5, 0.25]
        finally:
            ws.close()

    def test_result_has_params(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T019-params: result params is a non-empty dict with sections key."""
        mock_api_client.insights_query.return_value = MOCK_RETENTION_RESPONSE
        ws = workspace_factory()
        try:
            result = ws.query_retention("Signup", "Login")

            assert isinstance(result.params, dict)
            assert len(result.params) > 0
            assert "sections" in result.params
        finally:
            ws.close()


# =============================================================================
# Config error tests
# =============================================================================


# TestQueryRetentionConfigError removed in B1 (Fix 10): Workspace.__init__
# now always populates ``_credentials`` via the v3 session shim.


# =============================================================================
# T-US2: Per-event filters in workspace integration
# =============================================================================


class TestQueryRetentionWithFilters:
    """Tests for per-event filters sent through query_retention()."""

    def test_per_event_filters_sent_to_api(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Per-event filters on RetentionEvent must appear in bookmark behaviors."""
        from mixpanel_headless.types import Filter, RetentionEvent

        mock_api_client.insights_query.return_value = MOCK_RETENTION_RESPONSE
        ws = workspace_factory()
        try:
            born = RetentionEvent(
                "Signup",
                filters=[Filter.equals("source", "organic")],
            )
            ws.query_retention(born, "Login")

            body = mock_api_client.insights_query.call_args[0][0]
            bookmark = body["bookmark"]
            behaviors = bookmark["sections"]["show"][0]["behavior"]["behaviors"]
            assert len(behaviors[0]["filters"]) > 0
        finally:
            ws.close()


# =============================================================================
# T-US4: build_retention_params integration
# =============================================================================


class TestBuildRetentionParams:
    """Tests for build_retention_params() as a standalone method."""

    def test_returns_dict_not_result(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_retention_params must return a dict, not a RetentionQueryResult."""
        ws = workspace_factory()
        try:
            result = ws.build_retention_params("Signup", "Login")
            assert isinstance(result, dict)
            assert not isinstance(result, RetentionQueryResult)
        finally:
            ws.close()

    def test_has_sections_and_display_options(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Result must have 'sections' and 'displayOptions' keys."""
        ws = workspace_factory()
        try:
            result = ws.build_retention_params("Signup", "Login")
            assert "sections" in result
            assert "displayOptions" in result
        finally:
            ws.close()

    def test_no_api_call_made(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """build_retention_params must not make any API call."""
        ws = workspace_factory()
        try:
            ws.build_retention_params("Signup", "Login")
            mock_api_client.insights_query.assert_not_called()
        finally:
            ws.close()

    def test_consistency_with_query_retention(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """build_retention_params output must match the bookmark sent by query_retention."""
        mock_api_client.insights_query.return_value = MOCK_RETENTION_RESPONSE
        ws = workspace_factory()
        try:
            params = ws.build_retention_params("Signup", "Login")

            ws.query_retention("Signup", "Login")
            body = mock_api_client.insights_query.call_args[0][0]
            bookmark = body["bookmark"]

            assert params == bookmark
        finally:
            ws.close()


# =============================================================================
# T-US5: Validation integration
# =============================================================================


class TestQueryRetentionValidationIntegration:
    """Tests for fail-fast validation preventing API calls."""

    def test_validation_error_before_api_call(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """Empty born_event must be caught by RetentionEvent.__post_init__ without calling the API."""
        ws = workspace_factory()
        try:
            with pytest.raises(
                ValueError, match="RetentionEvent.event must be a non-empty"
            ):
                ws.query_retention("", "Login")
            mock_api_client.insights_query.assert_not_called()
        finally:
            ws.close()
