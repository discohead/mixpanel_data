"""Integration tests for cohort behaviors in Workspace methods.

Tests cover:
- T007: ``query_flow()`` ``where=`` parameter with cohort filters
  (acceptance of cohort filters, rejection of non-cohort filters).
- T041: ``_resolve_and_build_params()`` type guard accepting
  ``CohortMetric`` alongside ``str``, ``Metric``, and ``Formula``.

Uses the same Workspace fixture pattern as ``test_workspace_funnel.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.types import (
    CohortBreakdown,
    CohortCriteria,
    CohortDefinition,
    CohortMetric,
    Filter,
    Formula,
    Metric,
)

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


# =============================================================================
# Helpers
# =============================================================================


def _simple_cohort_def() -> CohortDefinition:
    """Create a minimal CohortDefinition for testing.

    Returns:
        CohortDefinition with a single ``did_event`` criterion.
    """
    return CohortDefinition(
        CohortCriteria.did_event("Purchase", at_least=1, within_days=30)
    )


# =============================================================================
# T007: query_flow where= parameter
# =============================================================================


class TestQueryFlowWhere:
    """Tests for query_flow where= parameter (T007).

    Verifies that ``query_flow()`` and ``build_flow_params()`` accept
    cohort filters in ``where=`` and reject non-cohort filters.
    """

    def test_cohort_filter_accepted_in_build_flow_params(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T007: build_flow_params accepts cohort filter in where=."""
        ws = workspace_factory()
        try:
            result = ws.build_flow_params(
                "Login",
                where=Filter.in_cohort(123, "Power Users"),
            )
            assert "filter_by_cohort" in result
        finally:
            ws.close()

    def test_cohort_filter_id_in_flow_params(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T007: filter_by_cohort has correct cohort id."""
        ws = workspace_factory()
        try:
            result = ws.build_flow_params(
                "Login",
                where=Filter.in_cohort(456, "Active"),
            )
            assert result["filter_by_cohort"]["id"] == 456
        finally:
            ws.close()

    def test_cohort_filter_name_in_flow_params(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T007: filter_by_cohort has correct cohort name."""
        ws = workspace_factory()
        try:
            result = ws.build_flow_params(
                "Login",
                where=Filter.in_cohort(456, "Active"),
            )
            assert result["filter_by_cohort"]["name"] == "Active"
        finally:
            ws.close()

    def test_not_in_cohort_filter_negated_true(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T007: not_in_cohort sets negated=True in filter_by_cohort."""
        ws = workspace_factory()
        try:
            result = ws.build_flow_params(
                "Login",
                where=Filter.not_in_cohort(789, "Bots"),
            )
            assert result["filter_by_cohort"]["negated"] is True
        finally:
            ws.close()

    def test_property_filter_produces_filter_by_event(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T007: Property filter in flow where= produces filter_by_event."""
        ws = workspace_factory()
        try:
            result = ws.build_flow_params(
                "Login",
                where=Filter.equals("country", "US"),
            )
            assert "filter_by_event" in result
            assert result["filter_by_event"]["operator"] == "and"
            assert len(result["filter_by_event"]["children"]) == 1
        finally:
            ws.close()

    def test_mixed_cohort_and_property_filters(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T007: Mixed cohort + property filters produce both filter keys."""
        ws = workspace_factory()
        try:
            result = ws.build_flow_params(
                "Login",
                where=[
                    Filter.in_cohort(123, "PU"),
                    Filter.equals("country", "US"),
                ],
            )
            assert "filter_by_cohort" in result
            assert "filter_by_event" in result
            assert result["filter_by_cohort"]["name"] == "PU"
            assert len(result["filter_by_event"]["children"]) == 1
        finally:
            ws.close()

    def test_no_where_produces_no_filter_by_cohort(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T007: No where= parameter produces no filter_by_cohort key."""
        ws = workspace_factory()
        try:
            result = ws.build_flow_params("Login")
            assert "filter_by_cohort" not in result
        finally:
            ws.close()

    def test_no_api_call_for_build_flow_params(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T007: build_flow_params does not make API calls."""
        ws = workspace_factory()
        try:
            ws.build_flow_params("Login", where=Filter.in_cohort(123))
            mock_api_client.request.assert_not_called()
        finally:
            ws.close()


# =============================================================================
# T041: _resolve_and_build_params type guard for CohortMetric
# =============================================================================


class TestResolveAndBuildParamsCohortMetric:
    """Tests for _resolve_and_build_params() accepting CohortMetric (T041).

    Verifies that the type guard in ``_resolve_and_build_params()``
    correctly dispatches ``CohortMetric`` objects alongside ``str``,
    ``Metric``, and ``Formula``.
    """

    def test_cohort_metric_alone_returns_dict(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T041: CohortMetric alone produces a valid params dict."""
        ws = workspace_factory()
        try:
            result = ws.build_params(CohortMetric(123, "Power Users"))
            assert isinstance(result, dict)
            assert "sections" in result
            assert "displayOptions" in result
        finally:
            ws.close()

    def test_cohort_metric_has_show_section(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T041: CohortMetric produces non-empty sections.show."""
        ws = workspace_factory()
        try:
            result = ws.build_params(CohortMetric(123, "PU"))
            assert len(result["sections"]["show"]) > 0
        finally:
            ws.close()

    def test_cohort_metric_show_behavior_type_cohort(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T041: CohortMetric show entry has behavior.type='cohort'."""
        ws = workspace_factory()
        try:
            result = ws.build_params(CohortMetric(123, "PU"))
            behavior = result["sections"]["show"][0]["behavior"]
            assert behavior["type"] == "cohort"
        finally:
            ws.close()

    def test_cohort_metric_in_sequence_with_string(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T041: CohortMetric in sequence with string event is accepted."""
        ws = workspace_factory()
        try:
            result = ws.build_params([CohortMetric(123, "PU"), "Login"])
            assert len(result["sections"]["show"]) == 2
        finally:
            ws.close()

    def test_cohort_metric_in_sequence_with_metric(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T041: CohortMetric in sequence with Metric is accepted."""
        ws = workspace_factory()
        try:
            result = ws.build_params(
                [
                    CohortMetric(123, "PU"),
                    Metric("Login", math="unique"),
                ]
            )
            assert len(result["sections"]["show"]) == 2
        finally:
            ws.close()

    def test_cohort_metric_in_sequence_with_formula(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T041: CohortMetric with Formula in sequence is accepted."""
        ws = workspace_factory()
        try:
            result = ws.build_params(
                [
                    CohortMetric(123, "PU"),
                    Metric("Login"),
                    Formula("A/B", label="Ratio"),
                ]
            )
            assert "sections" in result
        finally:
            ws.close()

    def test_cohort_metric_no_api_call(
        self,
        workspace_factory: Callable[..., Workspace],
        mock_api_client: MagicMock,
    ) -> None:
        """T041: build_params with CohortMetric does not call API."""
        ws = workspace_factory()
        try:
            ws.build_params(CohortMetric(123, "PU"))
            mock_api_client.insights_query.assert_not_called()
        finally:
            ws.close()

    def test_inline_cohort_metric_rejected_cm5(self) -> None:
        """CM5: Inline CohortDefinition in CohortMetric raises at construction."""
        cohort_def = _simple_cohort_def()
        with pytest.raises(
            ValueError,
            match="CohortMetric does not support inline CohortDefinition",
        ):
            CohortMetric(cohort_def, "Active")

    def test_cohort_metric_with_group_by_accepted(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T041: CohortMetric with group_by produces both show and group."""
        ws = workspace_factory()
        try:
            result = ws.build_params(
                CohortMetric(123, "PU"),
                group_by="platform",
            )
            assert len(result["sections"]["show"]) > 0
            assert len(result["sections"]["group"]) > 0
        finally:
            ws.close()

    def test_cohort_metric_with_where_accepted(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T041: CohortMetric with where= filter produces both show and filter."""
        ws = workspace_factory()
        try:
            result = ws.build_params(
                CohortMetric(123, "PU"),
                where=Filter.in_cohort(456, "Other"),
            )
            assert len(result["sections"]["show"]) > 0
            assert len(result["sections"]["filter"]) > 0
        finally:
            ws.close()

    def test_cohort_metric_with_cohort_breakdown(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T041: CohortMetric with CohortBreakdown produces both show and group."""
        ws = workspace_factory()
        try:
            result = ws.build_params(
                CohortMetric(123, "PU"),
                group_by=CohortBreakdown(456, "Other Cohort"),
            )
            assert len(result["sections"]["show"]) > 0
            assert len(result["sections"]["group"]) > 0
        finally:
            ws.close()
