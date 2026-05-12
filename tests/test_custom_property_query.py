"""End-to-end tests for custom properties across query engines (Phase 037).

Exercises the full pipeline from typed arguments through build_params(),
build_funnel_params(), and build_retention_params() to verify custom
property bookmark JSON output.

Task IDs: T023, T032, T038-T040, T044-T045
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.exceptions import QueryError
from mixpanel_headless.types import (
    CustomPropertyRef,
    Filter,
    GroupBy,
    InlineCustomProperty,
    Metric,
)
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
# Fixtures
# =============================================================================


@pytest.fixture
def ws() -> Workspace:
    """Create a Workspace instance with mocked dependencies."""
    creds = make_session(username="u", secret="s", project_id="1", region="us")
    mgr = MagicMock()
    mgr.config_version.return_value = 1
    mgr.resolve_credentials.return_value = creds
    return Workspace(session=_TEST_SESSION, _api_client=MagicMock())


# =============================================================================
# T023: E2E group_by with custom properties (US1)
# =============================================================================


class TestGroupByCustomPropertyE2E:
    """E2E tests for custom property in group_by across query engines."""

    def test_build_params_with_custom_property_ref_group_by(
        self, ws: Workspace
    ) -> None:
        """build_params with CustomPropertyRef in group_by."""
        params = ws.build_params(
            "Purchase",
            group_by=GroupBy(property=CustomPropertyRef(42), property_type="number"),
        )

        group = params["sections"]["group"]
        assert len(group) == 1
        assert group[0]["customPropertyId"] == 42

    def test_build_params_with_inline_group_by(self, ws: Workspace) -> None:
        """build_params with InlineCustomProperty in group_by."""
        icp = InlineCustomProperty.numeric("A * B", A="price", B="qty")
        params = ws.build_params(
            "Purchase",
            group_by=GroupBy(property=icp, property_type="number"),
        )

        group = params["sections"]["group"]
        assert len(group) == 1
        assert "customProperty" in group[0]
        assert group[0]["customProperty"]["displayFormula"] == "A * B"

    def test_build_funnel_params_with_custom_property_group_by(
        self, ws: Workspace
    ) -> None:
        """build_funnel_params with CustomPropertyRef in group_by."""
        params = ws.build_funnel_params(
            ["Signup", "Purchase"],
            group_by=GroupBy(property=CustomPropertyRef(42), property_type="number"),
        )

        group = params["sections"]["group"]
        assert len(group) == 1
        assert group[0]["customPropertyId"] == 42

    def test_build_retention_params_with_custom_property_group_by(
        self, ws: Workspace
    ) -> None:
        """build_retention_params with CustomPropertyRef in group_by."""
        params = ws.build_retention_params(
            "Signup",
            "Login",
            group_by=GroupBy(property=CustomPropertyRef(42), property_type="number"),
        )

        group = params["sections"]["group"]
        assert len(group) == 1
        assert group[0]["customPropertyId"] == 42


# =============================================================================
# T032: E2E filter with custom properties (US2)
# =============================================================================


class TestFilterCustomPropertyE2E:
    """E2E tests for custom property in filter across query engines."""

    def test_build_params_with_custom_property_ref_filter(self, ws: Workspace) -> None:
        """build_params with CustomPropertyRef in filter."""
        params = ws.build_params(
            "Purchase",
            where=Filter.greater_than(property=CustomPropertyRef(42), value=100),
        )

        filters = params["sections"]["filter"]
        assert len(filters) == 1
        assert filters[0]["customPropertyId"] == 42
        assert "value" not in filters[0]

    def test_build_params_with_inline_filter(self, ws: Workspace) -> None:
        """build_params with InlineCustomProperty in filter."""
        icp = InlineCustomProperty.numeric("A * B", A="price", B="qty")
        params = ws.build_params(
            "Purchase",
            where=Filter.greater_than(property=icp, value=1000),
        )

        filters = params["sections"]["filter"]
        assert len(filters) == 1
        assert "customProperty" in filters[0]
        assert filters[0]["customProperty"]["displayFormula"] == "A * B"


# =============================================================================
# T038-T040: E2E measurement with custom properties (US3)
# =============================================================================


class TestMeasurementCustomPropertyE2E:
    """E2E tests for custom property in Metric.property."""

    def test_build_params_with_custom_property_ref_measurement(
        self, ws: Workspace
    ) -> None:
        """T038: build_params with Metric(property=CustomPropertyRef(...))."""
        params = ws.build_params(
            Metric("Purchase", math="average", property=CustomPropertyRef(42)),
        )

        measurement = params["sections"]["show"][0]["measurement"]
        assert measurement["property"]["customPropertyId"] == 42
        assert measurement["property"]["resourceType"] == "events"

    def test_build_params_with_inline_measurement(self, ws: Workspace) -> None:
        """T039: build_params with Metric(property=InlineCustomProperty.numeric(...))."""
        icp = InlineCustomProperty.numeric("A * B", A="price", B="quantity")
        params = ws.build_params(
            Metric("Purchase", math="average", property=icp),
        )

        measurement = params["sections"]["show"][0]["measurement"]
        prop = measurement["property"]
        assert "customProperty" in prop
        assert prop["customProperty"]["displayFormula"] == "A * B"
        assert prop["resourceType"] == "events"

    def test_build_funnel_params_with_custom_property_measurement(
        self, ws: Workspace
    ) -> None:
        """T040: build_funnel_params with custom property math_property."""
        # Funnels use math_property (top-level), not Metric.property
        # Custom property in funnel measurement is not supported via
        # math_property (it's always a string). This test verifies
        # the plain string path still works in funnels.
        params = ws.build_funnel_params(
            ["Signup", "Purchase"],
            math="average",
            math_property="amount",
        )

        measurement = params["sections"]["show"][0]["measurement"]
        assert measurement["property"]["name"] == "amount"


# =============================================================================
# T044-T045: Combined positions E2E tests (Phase 6)
# =============================================================================


class TestCombinedPositions:
    """Tests for custom properties in multiple positions simultaneously."""

    def test_ref_in_group_by_and_inline_in_filter(self, ws: Workspace) -> None:
        """T044: CustomPropertyRef in group_by + InlineCustomProperty in where."""
        icp = InlineCustomProperty.numeric("A * B", A="price", B="qty")
        params = ws.build_params(
            "Purchase",
            group_by=GroupBy(property=CustomPropertyRef(42), property_type="number"),
            where=Filter.greater_than(property=icp, value=100),
        )

        group = params["sections"]["group"]
        filters = params["sections"]["filter"]
        assert group[0]["customPropertyId"] == 42
        assert "customProperty" in filters[0]

    def test_all_three_positions(self, ws: Workspace) -> None:
        """T045: All three positions simultaneously (Metric + group_by + where)."""
        revenue = InlineCustomProperty.numeric("A * B", A="price", B="qty")
        params = ws.build_params(
            Metric("Purchase", math="average", property=CustomPropertyRef(99)),
            group_by=GroupBy(
                property=revenue,
                property_type="number",
                bucket_size=100,
                bucket_min=0,
                bucket_max=1000,
            ),
            where=Filter.greater_than(property=revenue, value=50),
        )

        # Measurement
        measurement = params["sections"]["show"][0]["measurement"]
        assert measurement["property"]["customPropertyId"] == 99

        # Group
        group = params["sections"]["group"]
        assert "customProperty" in group[0]
        assert group[0]["customBucket"]["bucketSize"] == 100

        # Filter
        filters = params["sections"]["filter"]
        assert "customProperty" in filters[0]


# =============================================================================
# list_custom_properties error handling
# =============================================================================


class TestListCustomPropertiesErrorHandling:
    """Tests for QueryError re-raise with HTTP context preservation."""

    def test_display_formula_corruption_preserves_context(self, ws: Workspace) -> None:
        """Re-raised QueryError for displayFormula corruption preserves HTTP context."""
        original = QueryError(
            "serialization failed",
            status_code=500,
            response_body={"field": "displayFormula"},
            request_method="GET",
            request_url="https://mixpanel.com/api/app/custom-properties",
            request_params={"project_id": "1"},
        )
        ws._api_client.list_custom_properties.side_effect = original  # type: ignore[union-attr]

        with pytest.raises(QueryError, match="displayFormula") as exc_info:
            ws.list_custom_properties()

        raised = exc_info.value
        assert raised is not original
        assert raised.status_code == 500
        assert raised.response_body == {"field": "displayFormula"}
        assert raised.request_method == "GET"
        assert raised.request_url == "https://mixpanel.com/api/app/custom-properties"
        assert raised.__cause__ is original

    def test_non_matching_query_error_reraised_unchanged(self, ws: Workspace) -> None:
        """QueryError without displayFormula field is re-raised unchanged."""
        original = QueryError(
            "some other error",
            status_code=400,
            response_body={"field": "somethingElse"},
        )
        ws._api_client.list_custom_properties.side_effect = original  # type: ignore[union-attr]

        with pytest.raises(QueryError) as exc_info:
            ws.list_custom_properties()

        assert exc_info.value is original
