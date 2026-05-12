"""Integration tests for Workspace.query_funnel() and build_funnel_params().

Tests cover three areas:
- T021: Validation integration — verifying that invalid inputs raise
  BookmarkValidationError with expected error codes.
- T022: Execution path — mocking insights_query() to verify the API
  call body, response transformation, and FunnelQueryResult fields.
- T023: build_funnel_params() — verifying it returns a dict (not a
  result object), produces the same params as query_funnel would,
  and never calls the API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from mixpanel_headless import Workspace
from mixpanel_headless.exceptions import BookmarkValidationError
from mixpanel_headless.types import FunnelQueryResult
from tests.conftest import make_session

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
            "session": make_session(),
            "_api_client": mock_api_client,
        }
        defaults.update(kwargs)
        return Workspace(**defaults)

    return factory


MOCK_FUNNEL_RESPONSE: dict[str, Any] = {
    "computed_at": "2025-01-15T12:00:00",
    "date_range": {"from_date": "2025-01-01", "to_date": "2025-01-31"},
    "headers": ["$funnel"],
    "series": {
        "steps": [
            {
                "event": "Signup",
                "count": 1000,
                "step_conv_ratio": 1.0,
                "overall_conv_ratio": 1.0,
                "avg_time": 0.0,
                "avg_time_from_start": 0.0,
            },
            {
                "event": "Purchase",
                "count": 120,
                "step_conv_ratio": 0.12,
                "overall_conv_ratio": 0.12,
                "avg_time": 86400.0,
                "avg_time_from_start": 86400.0,
            },
        ]
    },
    "meta": {"sampling_factor": 1.0},
}
"""Canonical mock response for a two-step funnel query."""


# =============================================================================
# T021: Validation integration tests
# =============================================================================


# TestQueryFunnelConfigError removed in B1 (Fix 10): Workspace.__init__
# now always populates ``_credentials`` via the v3 session shim, so the
# "no credentials" path is unreachable.


class TestQueryFunnelValidation:
    """Tests for query_funnel() validation integration.

    Verifies that invalid inputs raise BookmarkValidationError with the
    correct error codes before any API call is made.
    """

    def test_fewer_than_two_steps_raises_f1(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T021-F1: A single-step funnel raises BookmarkValidationError with F1 code."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_funnel(steps=["A"])

            error_codes = [e.code for e in exc_info.value.errors]
            assert "F1_MIN_STEPS" in error_codes
            mock_api_client.insights_query.assert_not_called()
        finally:
            ws.close()

    def test_empty_event_name_raises_f2(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T021-F2: An empty event name is caught by FunnelStep.__post_init__."""
        ws = workspace_factory()
        try:
            with pytest.raises(
                ValueError, match="FunnelStep.event must be a non-empty"
            ):
                ws.query_funnel(steps=["Signup", ""])

            mock_api_client.insights_query.assert_not_called()
        finally:
            ws.close()

    def test_negative_conversion_window_raises_f3(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T021-F3: Negative conversion_window raises BookmarkValidationError."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_funnel(steps=["A", "B"], conversion_window=-1)

            error_codes = [e.code for e in exc_info.value.errors]
            assert "F3_CONVERSION_WINDOW_POSITIVE" in error_codes
            mock_api_client.insights_query.assert_not_called()
        finally:
            ws.close()

    def test_invalid_math_raises_validation_error(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T021-math: Invalid math type raises BookmarkValidationError at Layer 2."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_funnel(
                    steps=["A", "B"],
                    math="invalid_math",  # type: ignore[arg-type]
                )

            error_codes = [e.code for e in exc_info.value.errors]
            assert "B9_INVALID_MATH" in error_codes
            mock_api_client.insights_query.assert_not_called()
        finally:
            ws.close()

    def test_empty_event_caught_at_construction(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T021-multi: Empty event name is caught by FunnelStep.__post_init__ before validation."""
        ws = workspace_factory()
        try:
            with pytest.raises(
                ValueError, match="FunnelStep.event must be a non-empty"
            ):
                ws.query_funnel(steps=[""], conversion_window=0)

            mock_api_client.insights_query.assert_not_called()
        finally:
            ws.close()

    def test_multiple_validation_errors_collected(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T021-multi: Multiple validation errors still collected in single BookmarkValidationError."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.query_funnel(
                    steps=["ValidEvent"],  # passes __post_init__
                    conversion_window=0,  # F3: must be positive
                    from_date="bad-date",  # V8: invalid format
                )

            err = exc_info.value
            error_codes = {e.code for e in err.errors}
            assert "F1_MIN_STEPS" in error_codes  # only 1 step
            assert "F3_CONVERSION_WINDOW_POSITIVE" in error_codes
            assert err.error_count >= 2
            mock_api_client.insights_query.assert_not_called()
        finally:
            ws.close()


# =============================================================================
# T022: Execution path tests
# =============================================================================


class TestQueryFunnelExecution:
    """Tests for query_funnel() execution path with mocked API.

    Verifies that query_funnel() sends the correct body to
    insights_query(), and that the response is correctly transformed
    into a FunnelQueryResult.
    """

    def test_correct_body_sent_to_api(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T022-body: query_funnel() sends body with bookmark, project_id, queryLimits."""
        mock_api_client.insights_query.return_value = MOCK_FUNNEL_RESPONSE
        ws = workspace_factory()
        try:
            ws.query_funnel(["Signup", "Purchase"])

            mock_api_client.insights_query.assert_called_once()
            body = mock_api_client.insights_query.call_args[0][0]

            assert "bookmark" in body
            assert "project_id" in body
            assert "queryLimits" in body
            assert body["project_id"] == 12345
            assert body["queryLimits"] == {"limit": 3000}
        finally:
            ws.close()

    def test_bookmark_params_in_body(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T022-bookmark: bookmark in body contains sections and displayOptions."""
        mock_api_client.insights_query.return_value = MOCK_FUNNEL_RESPONSE
        ws = workspace_factory()
        try:
            ws.query_funnel(["Signup", "Purchase"])

            body = mock_api_client.insights_query.call_args[0][0]
            bookmark = body["bookmark"]

            assert "sections" in bookmark
            assert "displayOptions" in bookmark
        finally:
            ws.close()

    def test_result_is_funnel_query_result(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T022-type: query_funnel() returns a FunnelQueryResult instance."""
        mock_api_client.insights_query.return_value = MOCK_FUNNEL_RESPONSE
        ws = workspace_factory()
        try:
            result = ws.query_funnel(["Signup", "Purchase"])

            assert isinstance(result, FunnelQueryResult)
        finally:
            ws.close()

    def test_result_fields_from_mock_response(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T022-fields: FunnelQueryResult fields match mock response data."""
        mock_api_client.insights_query.return_value = MOCK_FUNNEL_RESPONSE
        ws = workspace_factory()
        try:
            result = ws.query_funnel(["Signup", "Purchase"])

            assert result.computed_at == "2025-01-15T12:00:00"
            assert result.from_date == "2025-01-01"
            assert result.to_date == "2025-01-31"
            assert result.meta == {"sampling_factor": 1.0}
        finally:
            ws.close()

    def test_result_steps_data(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T022-steps: steps_data contains correct step-level information."""
        mock_api_client.insights_query.return_value = MOCK_FUNNEL_RESPONSE
        ws = workspace_factory()
        try:
            result = ws.query_funnel(["Signup", "Purchase"])

            assert len(result.steps_data) == 2

            step1 = result.steps_data[0]
            assert step1["event"] == "Signup"
            assert step1["count"] == 1000
            assert step1["step_conv_ratio"] == 1.0
            assert step1["overall_conv_ratio"] == 1.0

            step2 = result.steps_data[1]
            assert step2["event"] == "Purchase"
            assert step2["count"] == 120
            assert step2["step_conv_ratio"] == 0.12
            assert step2["overall_conv_ratio"] == 0.12
            assert step2["avg_time"] == 86400.0
        finally:
            ws.close()

    def test_result_overall_conversion_rate(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T022-conversion: overall_conversion_rate matches last step ratio."""
        mock_api_client.insights_query.return_value = MOCK_FUNNEL_RESPONSE
        ws = workspace_factory()
        try:
            result = ws.query_funnel(["Signup", "Purchase"])

            assert result.overall_conversion_rate == pytest.approx(0.12)
        finally:
            ws.close()

    def test_result_params_preserved(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T022-params: params dict is preserved in FunnelQueryResult for debugging."""
        mock_api_client.insights_query.return_value = MOCK_FUNNEL_RESPONSE
        ws = workspace_factory()
        try:
            result = ws.query_funnel(["Signup", "Purchase"])

            assert isinstance(result.params, dict)
            assert "sections" in result.params
            assert "displayOptions" in result.params
        finally:
            ws.close()


# =============================================================================
# T023: build_funnel_params tests
# =============================================================================


class TestBuildFunnelParamsVsQueryFunnel:
    """Tests for build_funnel_params() vs query_funnel() consistency.

    Verifies that build_funnel_params() returns a dict (not a result
    object), produces the same params structure as query_funnel, never
    calls the API, and raises BookmarkValidationError for invalid inputs.
    """

    def test_returns_dict_not_result(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T023-type: build_funnel_params() returns a plain dict."""
        ws = workspace_factory()
        try:
            params = ws.build_funnel_params(["Signup", "Purchase"])

            assert isinstance(params, dict)
            assert not isinstance(params, FunnelQueryResult)
        finally:
            ws.close()

    def test_params_structure_matches_query_funnel(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T023-consistency: build_funnel_params() produces same params as query_funnel()."""
        mock_api_client.insights_query.return_value = MOCK_FUNNEL_RESPONSE

        ws = workspace_factory()
        try:
            built_params = ws.build_funnel_params(["Signup", "Purchase"])

            ws.query_funnel(["Signup", "Purchase"])
            body = mock_api_client.insights_query.call_args[0][0]
            query_params = body["bookmark"]

            assert built_params == query_params
        finally:
            ws.close()

    def test_no_api_call_made(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T023-no-api: build_funnel_params() does not call the API."""
        ws = workspace_factory()
        try:
            ws.build_funnel_params(["Signup", "Purchase"])

            mock_api_client.insights_query.assert_not_called()
        finally:
            ws.close()

    def test_raises_validation_error_for_invalid_inputs(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T023-validation: build_funnel_params() raises BookmarkValidationError."""
        ws = workspace_factory()
        try:
            with pytest.raises(BookmarkValidationError) as exc_info:
                ws.build_funnel_params(steps=["A"])

            error_codes = [e.code for e in exc_info.value.errors]
            assert "F1_MIN_STEPS" in error_codes
            mock_api_client.insights_query.assert_not_called()
        finally:
            ws.close()

    def test_params_has_sections_and_display_options(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T023-keys: build_funnel_params() result has sections and displayOptions."""
        ws = workspace_factory()
        try:
            params = ws.build_funnel_params(["Signup", "Purchase"])

            assert "sections" in params
            assert "displayOptions" in params
        finally:
            ws.close()
