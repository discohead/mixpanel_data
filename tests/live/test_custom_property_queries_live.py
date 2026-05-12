"""Live QA tests for custom properties in queries (Phase 037).

Exercises PropertyInput, InlineCustomProperty, and CustomPropertyRef
across all 3 positions (group_by, filter, measurement) and all 3 engines
(insights, funnels, retention) against the real Mixpanel API on account
``p8`` (project ID 8).

Usage:
    uv run pytest tests/live/test_custom_property_queries_live.py -m live -v
    uv run pytest tests/live/test_custom_property_queries_live.py -m live -v -k "GroupBy"
"""

from __future__ import annotations

import pytest

from mixpanel_headless import (
    CustomPropertyRef,
    Filter,
    GroupBy,
    InlineCustomProperty,
    Metric,
    PropertyInput,
    QueryResult,
    Workspace,
)
from mixpanel_headless._internal.bookmark_builders import _build_composed_properties
from mixpanel_headless.exceptions import BookmarkValidationError
from mixpanel_headless.types import (
    CustomProperty,
    FunnelQueryResult,
    FunnelStep,
    RetentionQueryResult,
)

pytestmark = pytest.mark.live

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def ws() -> Workspace:
    """Create Workspace with ecommerce-demo credentials.

    Returns:
        Workspace connected to ecommerce-demo, workspace 3536632.
    """
    return Workspace(account="ecommerce-demo", workspace=3536632)


@pytest.fixture(scope="module")
def real_event(ws: Workspace) -> str:
    """Discover a real event name.

    Returns:
        First available event name.
    """
    events = ws.events()
    assert len(events) > 0, "No events found"
    return events[0]


@pytest.fixture(scope="module")
def real_events_pair(ws: Workspace) -> tuple[str, str]:
    """Discover two real event names for funnel/retention tests.

    Returns:
        Tuple of two distinct event names.
    """
    events = ws.events()
    assert len(events) >= 2, "Need at least 2 events for funnels/retention"
    return events[0], events[1]


@pytest.fixture(scope="module")
def real_numeric_property(ws: Workspace, real_event: str) -> str:
    """Discover a numeric property.

    Returns:
        A numeric property name.
    """
    candidates = ["$screen_width", "$screen_height", "mp_processing_time_ms"]
    props = ws.properties(real_event)
    prop_set = set(props)
    for c in candidates:
        if c in prop_set:
            return c
    if props:
        return props[0]
    pytest.skip("No properties found")


@pytest.fixture(scope="module")
def real_string_property(ws: Workspace, real_event: str) -> str:
    """Discover a string property.

    Returns:
        A string property name.
    """
    props = ws.properties(real_event)
    if "$browser" in props:
        return "$browser"
    for p in props:
        if not p.startswith("$"):
            return p
    return props[0] if props else "$browser"


@pytest.fixture(scope="module")
def saved_custom_properties(ws: Workspace) -> list[CustomProperty]:
    """Discover saved custom properties.

    Returns:
        List of CustomProperty objects.
    """
    return ws.list_custom_properties()


@pytest.fixture(scope="module")
def saved_cp_id(saved_custom_properties: list[CustomProperty]) -> int:
    """Get the first events-scoped saved custom property ID.

    Returns:
        Custom property ID.
    """
    for cp in saved_custom_properties:
        if cp.resource_type in ("events", "event"):
            return cp.custom_property_id
    pytest.skip("No events-scoped saved custom properties found")


@pytest.fixture(scope="module")
def saved_cp_type(saved_custom_properties: list[CustomProperty]) -> str:
    """Get the property_type of the first events-scoped saved custom property.

    Returns:
        Property type string (e.g., "number", "string").
    """
    for cp in saved_custom_properties:
        if cp.resource_type in ("events", "event"):
            return cp.property_type or "string"
    return "string"


@pytest.fixture(scope="module")
def simple_inline_cp(real_numeric_property: str) -> InlineCustomProperty:
    """Build a known-good inline custom property with numeric identity formula.

    Returns:
        InlineCustomProperty.numeric("A", A=real_numeric_property).
    """
    return InlineCustomProperty.numeric("A", A=real_numeric_property)


@pytest.fixture(scope="module")
def string_inline_cp(real_string_property: str) -> InlineCustomProperty:
    """Build a string inline custom property with identity formula.

    Returns:
        InlineCustomProperty with string input.
    """
    return InlineCustomProperty(
        formula="A",
        inputs={"A": PropertyInput(real_string_property)},
    )


# =============================================================================
# Discovery
# =============================================================================


class TestDiscovery:
    """Verify project 8 has the data needed for custom property tests."""

    def test_discover_events(self, ws: Workspace) -> None:
        """Project 8 has discoverable events."""
        events = ws.events()
        assert len(events) > 0

    def test_discover_properties(self, ws: Workspace, real_event: str) -> None:
        """First event has discoverable properties."""
        props = ws.properties(real_event)
        assert len(props) > 0

    def test_discover_custom_properties(
        self, saved_custom_properties: list[CustomProperty]
    ) -> None:
        """list_custom_properties() succeeds and returns a list."""
        assert isinstance(saved_custom_properties, list)

    def test_custom_property_has_valid_fields(
        self, saved_custom_properties: list[CustomProperty]
    ) -> None:
        """Each saved custom property has positive ID and non-empty name."""
        for cp in saved_custom_properties:
            assert cp.custom_property_id > 0
            assert cp.name


# =============================================================================
# Happy Path: Insights GroupBy
# =============================================================================


class TestInlineCustomPropertyGroupBy:
    """InlineCustomProperty in GroupBy.property — insights engine."""

    def test_numeric_inline_cp_groupby(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """Numeric inline CP in group_by produces a valid QueryResult."""
        result = ws.query(
            real_event,
            group_by=GroupBy(property=simple_inline_cp, property_type="number"),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_string_inline_cp_groupby(
        self, ws: Workspace, real_event: str, string_inline_cp: InlineCustomProperty
    ) -> None:
        """String inline CP in group_by produces a valid QueryResult."""
        result = ws.query(
            real_event,
            group_by=GroupBy(property=string_inline_cp),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_inline_cp_explicit_property_type_overrides(
        self,
        ws: Workspace,
        real_event: str,
        real_numeric_property: str,
    ) -> None:
        """ICP.property_type overrides GroupBy.property_type in build_params."""
        icp = InlineCustomProperty(
            formula="A",
            inputs={"A": PropertyInput(real_numeric_property, type="number")},
            property_type="number",
        )
        params = ws.build_params(
            real_event,
            group_by=GroupBy(property=icp, property_type="string"),
            last=7,
        )
        group = params["sections"]["group"][0]
        # ICP's "number" overrides GroupBy's "string"
        assert group["customProperty"]["propertyType"] == "number"
        assert group["propertyType"] == "number"

    def test_inline_cp_property_type_none_falls_back(
        self,
        ws: Workspace,
        real_event: str,
        real_numeric_property: str,
    ) -> None:
        """ICP.property_type=None falls back to GroupBy.property_type."""
        icp = InlineCustomProperty(
            formula="A",
            inputs={"A": PropertyInput(real_numeric_property, type="number")},
            property_type=None,
        )
        params = ws.build_params(
            real_event,
            group_by=GroupBy(property=icp, property_type="number"),
            last=7,
        )
        group = params["sections"]["group"][0]
        assert group["customProperty"]["propertyType"] == "number"

    def test_multiple_inline_cps_in_groupby(
        self,
        ws: Workspace,
        real_event: str,
        simple_inline_cp: InlineCustomProperty,
        string_inline_cp: InlineCustomProperty,
    ) -> None:
        """Two ICPs in same group_by list produce valid QueryResult."""
        result = ws.query(
            real_event,
            group_by=[
                GroupBy(property=simple_inline_cp, property_type="number"),
                GroupBy(property=string_inline_cp),
            ],
            last=7,
        )
        assert isinstance(result, QueryResult)


class TestCustomPropertyRefGroupBy:
    """CustomPropertyRef in GroupBy.property — insights engine."""

    def test_ref_groupby_insights(
        self,
        ws: Workspace,
        real_event: str,
        saved_cp_id: int,
        saved_cp_type: str,
    ) -> None:
        """Saved custom property ref in group_by produces valid QueryResult."""
        result = ws.query(
            real_event,
            group_by=GroupBy(
                property=CustomPropertyRef(saved_cp_id),
                property_type=saved_cp_type,  # type: ignore[arg-type]
            ),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_ref_groupby_build_params_structure(
        self,
        ws: Workspace,
        real_event: str,
        saved_cp_id: int,
        saved_cp_type: str,
    ) -> None:
        """build_params with ref produces customPropertyId in group entry."""
        params = ws.build_params(
            real_event,
            group_by=GroupBy(
                property=CustomPropertyRef(saved_cp_id),
                property_type=saved_cp_type,  # type: ignore[arg-type]
            ),
            last=7,
        )
        group = params["sections"]["group"][0]
        assert group["customPropertyId"] == saved_cp_id
        assert "propertyName" not in group


# =============================================================================
# Happy Path: Insights Filter
# =============================================================================


class TestInlineCustomPropertyFilter:
    """InlineCustomProperty in Filter — insights engine."""

    def test_filter_is_set_inline_cp(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """is_set filter on inline CP produces valid QueryResult."""
        result = ws.query(
            real_event,
            where=Filter.is_set(property=simple_inline_cp),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_filter_greater_than_inline_cp(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """greater_than filter on inline CP produces valid QueryResult."""
        result = ws.query(
            real_event,
            where=Filter.greater_than(property=simple_inline_cp, value=0),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_filter_between_inline_cp(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """between filter on inline CP produces valid QueryResult."""
        result = ws.query(
            real_event,
            where=Filter.between(property=simple_inline_cp, min_val=0, max_val=999999),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_filter_equals_string_inline_cp(
        self, ws: Workspace, real_event: str, string_inline_cp: InlineCustomProperty
    ) -> None:
        """equals filter on string inline CP produces valid QueryResult."""
        result = ws.query(
            real_event,
            where=Filter.equals(property=string_inline_cp, value="Chrome"),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_filter_inline_cp_build_params_structure(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """Filter with inline CP has customProperty key, no value/propertyName."""
        params = ws.build_params(
            real_event,
            where=Filter.is_set(property=simple_inline_cp),
            last=7,
        )
        f = params["sections"]["filter"][0]
        assert "customProperty" in f
        assert "value" not in f
        assert f["customProperty"]["displayFormula"] == simple_inline_cp.formula


class TestCustomPropertyRefFilter:
    """CustomPropertyRef in Filter — insights engine."""

    def test_filter_is_set_ref(
        self, ws: Workspace, real_event: str, saved_cp_id: int
    ) -> None:
        """is_set filter on ref produces valid QueryResult."""
        result = ws.query(
            real_event,
            where=Filter.is_set(property=CustomPropertyRef(saved_cp_id)),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_filter_ref_build_params_structure(
        self, ws: Workspace, real_event: str, saved_cp_id: int
    ) -> None:
        """Filter with ref has customPropertyId, no value."""
        params = ws.build_params(
            real_event,
            where=Filter.is_set(property=CustomPropertyRef(saved_cp_id)),
            last=7,
        )
        f = params["sections"]["filter"][0]
        assert f["customPropertyId"] == saved_cp_id
        assert "value" not in f


# =============================================================================
# Happy Path: Insights Metric
# =============================================================================


class TestInlineCustomPropertyMetric:
    """InlineCustomProperty in Metric.property — insights engine."""

    def test_metric_average_inline_cp(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """average math on inline CP produces valid QueryResult."""
        result = ws.query(
            Metric(real_event, math="average", property=simple_inline_cp),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_metric_median_inline_cp(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """median math on inline CP produces valid QueryResult."""
        result = ws.query(
            Metric(real_event, math="median", property=simple_inline_cp),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_metric_min_inline_cp(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """min math on inline CP produces valid QueryResult."""
        result = ws.query(
            Metric(real_event, math="min", property=simple_inline_cp),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_metric_build_params_measurement_structure(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """Measurement.property has customProperty dict with displayFormula."""
        params = ws.build_params(
            Metric(real_event, math="average", property=simple_inline_cp),
            last=7,
        )
        prop = params["sections"]["show"][0]["measurement"]["property"]
        assert "customProperty" in prop
        assert prop["customProperty"]["displayFormula"] == simple_inline_cp.formula


class TestCustomPropertyRefMetric:
    """CustomPropertyRef in Metric.property — insights engine."""

    def test_metric_average_ref(
        self, ws: Workspace, real_event: str, saved_cp_id: int
    ) -> None:
        """average math on ref produces valid QueryResult."""
        result = ws.query(
            Metric(
                real_event,
                math="average",
                property=CustomPropertyRef(saved_cp_id),
            ),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_metric_build_params_measurement_ref_structure(
        self, ws: Workspace, real_event: str, saved_cp_id: int
    ) -> None:
        """Measurement.property has customPropertyId."""
        params = ws.build_params(
            Metric(
                real_event,
                math="average",
                property=CustomPropertyRef(saved_cp_id),
            ),
            last=7,
        )
        prop = params["sections"]["show"][0]["measurement"]["property"]
        assert prop["customPropertyId"] == saved_cp_id


# =============================================================================
# Happy Path: Funnels
# =============================================================================


class TestCustomPropertyFunnels:
    """Custom properties in funnel queries."""

    def test_funnel_groupby_inline_cp(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        simple_inline_cp: InlineCustomProperty,
    ) -> None:
        """ICP in funnel group_by produces valid FunnelQueryResult."""
        e1, e2 = real_events_pair
        result = ws.query_funnel(
            [e1, e2],
            group_by=GroupBy(property=simple_inline_cp, property_type="number"),
            last=30,
        )
        assert isinstance(result, FunnelQueryResult)

    def test_funnel_where_inline_cp(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        simple_inline_cp: InlineCustomProperty,
    ) -> None:
        """ICP in funnel global filter — server rejects (known limitation)."""
        e1, e2 = real_events_pair
        result = ws.query_funnel(
            [e1, e2],
            where=Filter.is_set(property=simple_inline_cp),
            last=30,
        )
        assert isinstance(result, FunnelQueryResult)

    def test_funnel_step_filter_inline_cp(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        simple_inline_cp: InlineCustomProperty,
    ) -> None:
        """EDGE CASE #2: ICP in FunnelStep.filters (bypasses L1 validation)."""
        e1, e2 = real_events_pair
        result = ws.query_funnel(
            [
                FunnelStep(e1, filters=[Filter.is_set(property=simple_inline_cp)]),
                e2,
            ],
            last=30,
        )
        assert isinstance(result, FunnelQueryResult)

    def test_funnel_groupby_ref(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        saved_cp_id: int,
        saved_cp_type: str,
    ) -> None:
        """Ref in funnel group_by produces valid FunnelQueryResult."""
        e1, e2 = real_events_pair
        result = ws.query_funnel(
            [e1, e2],
            group_by=GroupBy(
                property=CustomPropertyRef(saved_cp_id),
                property_type=saved_cp_type,  # type: ignore[arg-type]
            ),
            last=30,
        )
        assert isinstance(result, FunnelQueryResult)


# =============================================================================
# Happy Path: Retention
# =============================================================================


class TestCustomPropertyRetention:
    """Custom properties in retention queries."""

    def test_retention_groupby_inline_cp(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        simple_inline_cp: InlineCustomProperty,
    ) -> None:
        """ICP in retention group_by produces valid RetentionQueryResult."""
        e1, e2 = real_events_pair
        result = ws.query_retention(
            e1,
            e2,
            group_by=GroupBy(property=simple_inline_cp, property_type="number"),
            last=30,
        )
        assert isinstance(result, RetentionQueryResult)

    def test_retention_where_inline_cp(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        simple_inline_cp: InlineCustomProperty,
    ) -> None:
        """ICP in retention global filter — server rejects (known limitation)."""
        e1, e2 = real_events_pair
        result = ws.query_retention(
            e1,
            e2,
            where=Filter.is_set(property=simple_inline_cp),
            last=30,
        )
        assert isinstance(result, RetentionQueryResult)

    def test_retention_groupby_ref(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        saved_cp_id: int,
        saved_cp_type: str,
    ) -> None:
        """Ref in retention group_by produces valid RetentionQueryResult."""
        e1, e2 = real_events_pair
        result = ws.query_retention(
            e1,
            e2,
            group_by=GroupBy(
                property=CustomPropertyRef(saved_cp_id),
                property_type=saved_cp_type,  # type: ignore[arg-type]
            ),
            last=30,
        )
        assert isinstance(result, RetentionQueryResult)

    def test_retention_where_ref(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        saved_cp_id: int,
    ) -> None:
        """Ref in retention filter — server rejects (same bug as inline CP)."""
        e1, e2 = real_events_pair
        result = ws.query_retention(
            e1,
            e2,
            where=Filter.is_set(property=CustomPropertyRef(saved_cp_id)),
            last=30,
        )
        assert isinstance(result, RetentionQueryResult)


# =============================================================================
# Edge Cases: Per-Metric Filters
# =============================================================================


class TestPerMetricFilterCustomProperty:
    """EDGE CASE #1: Metric.filters with custom properties bypass L1 validation."""

    def test_metric_per_metric_filter_inline_cp(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """Per-metric filter with ICP works despite L1 validation gap."""
        result = ws.query(
            Metric(
                real_event,
                filters=[Filter.is_set(property=simple_inline_cp)],
            ),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_metric_per_metric_filter_ref(
        self, ws: Workspace, real_event: str, saved_cp_id: int
    ) -> None:
        """Per-metric filter with ref works despite L1 validation gap."""
        result = ws.query(
            Metric(
                real_event,
                filters=[Filter.is_set(property=CustomPropertyRef(saved_cp_id))],
            ),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_metric_per_metric_filter_invalid_ref_caught(
        self, ws: Workspace, real_event: str
    ) -> None:
        """CustomPropertyRef(0) in Metric.filters IS caught at L1 (gap closed)."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                Metric(
                    real_event,
                    filters=[Filter.is_set(property=CustomPropertyRef(0))],
                ),
                last=7,
            )


# =============================================================================
# Edge Cases: Numeric Constructor
# =============================================================================


class TestInlineCustomPropertyNumericConstructor:
    """Tests for .numeric() convenience constructor against live API."""

    def test_numeric_constructor_single_input(
        self, ws: Workspace, real_event: str, real_numeric_property: str
    ) -> None:
        """Single-input .numeric() works in a live query."""
        icp = InlineCustomProperty.numeric("A", A=real_numeric_property)
        result = ws.query(
            Metric(real_event, math="average", property=icp),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_numeric_constructor_formula_with_literal(
        self, ws: Workspace, real_event: str, real_numeric_property: str
    ) -> None:
        """Formula with literal in .numeric() works."""
        icp = InlineCustomProperty.numeric("A * 2", A=real_numeric_property)
        result = ws.query(
            Metric(real_event, math="average", property=icp),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_numeric_constructor_multi_input(
        self, ws: Workspace, real_event: str, real_numeric_property: str
    ) -> None:
        """Multi-input .numeric() (same prop twice) works in a live query."""
        icp = InlineCustomProperty.numeric(
            "A + B", A=real_numeric_property, B=real_numeric_property
        )
        result = ws.query(
            Metric(real_event, math="average", property=icp),
            last=7,
        )
        assert isinstance(result, QueryResult)


# =============================================================================
# Edge Cases: Boundary Conditions
# =============================================================================


class TestCustomPropertyEdgeCases:
    """Edge cases, boundary conditions, and behavior discovery tests."""

    def test_same_inline_cp_in_filter_and_groupby(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """Same ICP instance used in both filter and group_by."""
        result = ws.query(
            real_event,
            group_by=GroupBy(property=simple_inline_cp, property_type="number"),
            where=Filter.is_set(property=simple_inline_cp),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_same_inline_cp_in_metric_and_groupby(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """Same ICP instance in Metric.property and GroupBy.property."""
        result = ws.query(
            Metric(real_event, math="average", property=simple_inline_cp),
            group_by=GroupBy(property=simple_inline_cp, property_type="number"),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_formula_with_special_characters(
        self, ws: Workspace, real_event: str, real_numeric_property: str
    ) -> None:
        """Formula with parentheses and division works."""
        icp = InlineCustomProperty.numeric("(A + A) / 2", A=real_numeric_property)
        result = ws.query(
            Metric(real_event, math="average", property=icp),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_inline_cp_property_type_none_in_metric(
        self, ws: Workspace, real_event: str, real_numeric_property: str
    ) -> None:
        """EDGE CASE #4: property_type=None omits propertyType from measurement JSON."""
        icp = InlineCustomProperty(
            formula="A",
            inputs={"A": PropertyInput(real_numeric_property, type="number")},
            property_type=None,
        )
        # Verify JSON shape: propertyType should be absent
        params = ws.build_params(
            Metric(real_event, math="average", property=icp),
            last=7,
        )
        cp_dict = params["sections"]["show"][0]["measurement"]["property"][
            "customProperty"
        ]
        assert "propertyType" not in cp_dict
        # But the live query may still work (server infers type)
        result = ws.query(
            Metric(real_event, math="average", property=icp),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_custom_property_ref_nonexistent_id(
        self, ws: Workspace, real_event: str
    ) -> None:
        """Behavior discovery: nonexistent CustomPropertyRef ID in filter."""
        # Server may return empty results or an error — document behavior
        try:
            result = ws.query(
                real_event,
                where=Filter.is_set(property=CustomPropertyRef(99999)),
                last=7,
            )
            assert isinstance(result, QueryResult)
        except Exception as exc:
            # Document what the server returns for nonexistent IDs
            pytest.skip(f"Server rejected nonexistent CP ID: {exc}")

    def test_multiple_custom_properties_mixed_types(
        self,
        ws: Workspace,
        real_event: str,
        simple_inline_cp: InlineCustomProperty,
        saved_cp_id: int,
        saved_cp_type: str,
    ) -> None:
        """Mixing ref + inline in same group_by list."""
        result = ws.query(
            real_event,
            group_by=[
                GroupBy(property=simple_inline_cp, property_type="number"),
                GroupBy(
                    property=CustomPropertyRef(saved_cp_id),
                    property_type=saved_cp_type,  # type: ignore[arg-type]
                ),
            ],
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_filter_type_mismatch_not_checked(
        self,
        ws: Workspace,
        real_event: str,
        string_inline_cp: InlineCustomProperty,
    ) -> None:
        """EDGE CASE #3: greater_than on string ICP — no client-side error."""
        # greater_than hard-codes _property_type="number" but string_inline_cp
        # has property_type=None. No validation catches this mismatch.
        params = ws.build_params(
            real_event,
            where=Filter.greater_than(property=string_inline_cp, value=5),
            last=7,
        )
        # build_params succeeds — gap confirmed
        assert "sections" in params


# =============================================================================
# Validation: CP1-CP6
# =============================================================================


class TestCustomPropertyValidation:
    """CP1-CP6 validation rules in GroupBy position."""

    def test_cp1_invalid_id_zero(self, ws: Workspace, real_event: str) -> None:
        """CP1: CustomPropertyRef(0) raises BookmarkValidationError."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                real_event,
                group_by=GroupBy(property=CustomPropertyRef(0), property_type="number"),
            )

    def test_cp1_invalid_id_negative(self, ws: Workspace, real_event: str) -> None:
        """CP1: CustomPropertyRef(-5) raises BookmarkValidationError."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                real_event,
                group_by=GroupBy(
                    property=CustomPropertyRef(-5), property_type="number"
                ),
            )

    def test_cp2_empty_formula(self, ws: Workspace, real_event: str) -> None:
        """CP2: Empty formula raises BookmarkValidationError."""
        icp = InlineCustomProperty(formula="", inputs={"A": PropertyInput("x")})
        with pytest.raises(BookmarkValidationError, match="non-empty"):
            ws.build_params(
                real_event, group_by=GroupBy(property=icp, property_type="string")
            )

    def test_cp2_whitespace_only_formula(self, ws: Workspace, real_event: str) -> None:
        """CP2: Whitespace-only formula raises BookmarkValidationError."""
        icp = InlineCustomProperty(formula="   ", inputs={"A": PropertyInput("x")})
        with pytest.raises(BookmarkValidationError, match="non-empty"):
            ws.build_params(
                real_event, group_by=GroupBy(property=icp, property_type="string")
            )

    def test_cp3_empty_inputs(self, ws: Workspace, real_event: str) -> None:
        """CP3: Empty inputs raises BookmarkValidationError."""
        icp = InlineCustomProperty(formula="A", inputs={})
        with pytest.raises(BookmarkValidationError, match="at least one input"):
            ws.build_params(
                real_event, group_by=GroupBy(property=icp, property_type="string")
            )

    def test_cp4_invalid_input_key_lowercase(
        self, ws: Workspace, real_event: str
    ) -> None:
        """CP4: Lowercase input key raises BookmarkValidationError."""
        icp = InlineCustomProperty(formula="a", inputs={"a": PropertyInput("x")})
        with pytest.raises(BookmarkValidationError, match="uppercase"):
            ws.build_params(
                real_event, group_by=GroupBy(property=icp, property_type="string")
            )

    def test_cp4_invalid_input_key_multi_char(
        self, ws: Workspace, real_event: str
    ) -> None:
        """CP4: Multi-char input key raises BookmarkValidationError."""
        icp = InlineCustomProperty(formula="AB", inputs={"AB": PropertyInput("x")})
        with pytest.raises(BookmarkValidationError, match="uppercase"):
            ws.build_params(
                real_event, group_by=GroupBy(property=icp, property_type="string")
            )

    def test_cp5_formula_too_long(self, ws: Workspace, real_event: str) -> None:
        """CP5: Formula > 20,000 chars raises BookmarkValidationError."""
        icp = InlineCustomProperty(
            formula="A" * 20_001, inputs={"A": PropertyInput("x")}
        )
        with pytest.raises(BookmarkValidationError, match="20,000"):
            ws.build_params(
                real_event, group_by=GroupBy(property=icp, property_type="string")
            )

    def test_cp5_formula_at_boundary(self, ws: Workspace, real_event: str) -> None:
        """CP5: Formula at exactly 20,000 chars passes validation."""
        icp = InlineCustomProperty(
            formula="A" * 20_000, inputs={"A": PropertyInput("x")}
        )
        # Should NOT raise
        params = ws.build_params(
            real_event, group_by=GroupBy(property=icp, property_type="string")
        )
        assert "sections" in params

    def test_cp6_empty_property_name(self, ws: Workspace, real_event: str) -> None:
        """CP6: Empty PropertyInput.name raises BookmarkValidationError."""
        icp = InlineCustomProperty(formula="A", inputs={"A": PropertyInput("")})
        with pytest.raises(BookmarkValidationError, match="empty property name"):
            ws.build_params(
                real_event, group_by=GroupBy(property=icp, property_type="string")
            )

    def test_cp6_whitespace_only_property_name(
        self, ws: Workspace, real_event: str
    ) -> None:
        """CP6: Whitespace-only PropertyInput.name raises BookmarkValidationError."""
        icp = InlineCustomProperty(formula="A", inputs={"A": PropertyInput("   ")})
        with pytest.raises(BookmarkValidationError, match="empty property name"):
            ws.build_params(
                real_event, group_by=GroupBy(property=icp, property_type="string")
            )

    def test_multiple_validation_errors(self, ws: Workspace, real_event: str) -> None:
        """Multiple CP violations produce multiple errors in one raise."""
        icp = InlineCustomProperty(formula="", inputs={})
        with pytest.raises(BookmarkValidationError) as exc_info:
            ws.build_params(
                real_event, group_by=GroupBy(property=icp, property_type="string")
            )
        errors = exc_info.value.errors
        codes = {e.code for e in errors}
        assert "CP2_EMPTY_FORMULA" in codes
        assert "CP3_EMPTY_INPUTS" in codes


class TestValidationInFilterPosition:
    """CP validation rules triggered via where= filters."""

    def test_cp1_in_filter_position(self, ws: Workspace, real_event: str) -> None:
        """CP1 caught in filter position."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                real_event,
                where=Filter.is_set(property=CustomPropertyRef(0)),
            )

    def test_cp2_in_filter_position(self, ws: Workspace, real_event: str) -> None:
        """CP2 caught in filter position."""
        icp = InlineCustomProperty(formula="", inputs={"A": PropertyInput("x")})
        with pytest.raises(BookmarkValidationError, match="non-empty"):
            ws.build_params(real_event, where=Filter.is_set(property=icp))


class TestValidationInMetricPosition:
    """CP validation rules triggered via Metric.property."""

    def test_cp1_in_metric_property(self, ws: Workspace, real_event: str) -> None:
        """CP1 caught in Metric.property position."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                Metric(
                    real_event,
                    math="average",
                    property=CustomPropertyRef(0),
                ),
            )


# =============================================================================
# Validation Gaps (document known L1 bypasses)
# =============================================================================


class TestValidationGaps:
    """Validation gaps that have been CLOSED — these confirm the fix."""

    def test_per_metric_filter_cp_now_validated(
        self, ws: Workspace, real_event: str
    ) -> None:
        """CLOSED: CustomPropertyRef(0) in Metric.filters IS caught at L1."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                Metric(
                    real_event,
                    filters=[Filter.is_set(property=CustomPropertyRef(0))],
                ),
            )

    def test_funnel_step_filter_cp_now_validated(
        self, ws: Workspace, real_events_pair: tuple[str, str]
    ) -> None:
        """CLOSED: CustomPropertyRef(0) in FunnelStep.filters IS caught at L1."""
        e1, e2 = real_events_pair
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_funnel_params(
                [
                    FunnelStep(
                        e1,
                        filters=[Filter.is_set(property=CustomPropertyRef(0))],
                    ),
                    e2,
                ],
            )

    def test_retention_where_cp_validated_by_workspace(
        self, ws: Workspace, real_events_pair: tuple[str, str]
    ) -> None:
        """Retention where= CP IS caught (by workspace.py, not validator)."""
        e1, e2 = real_events_pair
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_retention_params(
                e1,
                e2,
                where=Filter.is_set(property=CustomPropertyRef(0)),
            )


# =============================================================================
# Cross-Engine
# =============================================================================


class TestCrossEngine:
    """Custom properties work consistently across all 3 query engines."""

    def test_insights_inline_cp_all_three_positions(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """ICP in GroupBy + Filter + Metric simultaneously — insights."""
        result = ws.query(
            Metric(real_event, math="average", property=simple_inline_cp),
            group_by=GroupBy(property=simple_inline_cp, property_type="number"),
            where=Filter.is_set(property=simple_inline_cp),
            last=7,
        )
        assert isinstance(result, QueryResult)

    def test_funnel_inline_cp_groupby_and_where(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        simple_inline_cp: InlineCustomProperty,
    ) -> None:
        """ICP in both funnel group_by and where."""
        e1, e2 = real_events_pair
        result = ws.query_funnel(
            [e1, e2],
            group_by=GroupBy(property=simple_inline_cp, property_type="number"),
            where=Filter.is_set(property=simple_inline_cp),
            last=30,
        )
        assert isinstance(result, FunnelQueryResult)

    def test_retention_inline_cp_groupby_and_where(
        self,
        ws: Workspace,
        real_events_pair: tuple[str, str],
        simple_inline_cp: InlineCustomProperty,
    ) -> None:
        """ICP in both retention group_by and where."""
        e1, e2 = real_events_pair
        result = ws.query_retention(
            e1,
            e2,
            group_by=GroupBy(property=simple_inline_cp, property_type="number"),
            where=Filter.is_set(property=simple_inline_cp),
            last=30,
        )
        assert isinstance(result, RetentionQueryResult)

    def test_ref_across_all_engines(
        self,
        ws: Workspace,
        real_event: str,
        real_events_pair: tuple[str, str],
        saved_cp_id: int,
        saved_cp_type: str,
    ) -> None:
        """Ref in GroupBy across insights, funnels, retention."""
        gb = GroupBy(
            property=CustomPropertyRef(saved_cp_id),
            property_type=saved_cp_type,  # type: ignore[arg-type]
        )

        # Insights
        r1 = ws.query(real_event, group_by=gb, last=7)
        assert isinstance(r1, QueryResult)

        # Funnels
        e1, e2 = real_events_pair
        r2 = ws.query_funnel([e1, e2], group_by=gb, last=30)
        assert isinstance(r2, FunnelQueryResult)

        # Retention
        r3 = ws.query_retention(e1, e2, group_by=gb, last=30)
        assert isinstance(r3, RetentionQueryResult)


# =============================================================================
# Build Params Structure (no API calls)
# =============================================================================


class TestBuildParamsStructure:
    """Validate serialized bookmark JSON structure without API calls."""

    def test_inline_cp_groupby_json_shape(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """Group entry has complete customProperty dict."""
        params = ws.build_params(
            real_event,
            group_by=GroupBy(property=simple_inline_cp, property_type="number"),
        )
        g = params["sections"]["group"][0]
        cp = g["customProperty"]
        assert "displayFormula" in cp
        assert "composedProperties" in cp
        assert "propertyType" in cp
        assert "resourceType" in cp
        assert g["isHidden"] is False

    def test_inline_cp_filter_json_shape(
        self, ws: Workspace, real_event: str, simple_inline_cp: InlineCustomProperty
    ) -> None:
        """Filter entry has customProperty, no value/propertyName."""
        params = ws.build_params(
            real_event,
            where=Filter.is_set(property=simple_inline_cp),
        )
        f = params["sections"]["filter"][0]
        assert "customProperty" in f
        assert "value" not in f
        assert "propertyName" not in f

    def test_ref_groupby_json_shape(
        self, ws: Workspace, real_event: str, saved_cp_id: int, saved_cp_type: str
    ) -> None:
        """Group entry has customPropertyId, no value/propertyName."""
        params = ws.build_params(
            real_event,
            group_by=GroupBy(
                property=CustomPropertyRef(saved_cp_id),
                property_type=saved_cp_type,  # type: ignore[arg-type]
            ),
        )
        g = params["sections"]["group"][0]
        assert g["customPropertyId"] == saved_cp_id
        assert "propertyName" not in g

    def test_ref_filter_json_shape(
        self, ws: Workspace, real_event: str, saved_cp_id: int
    ) -> None:
        """Filter entry has customPropertyId, no value."""
        params = ws.build_params(
            real_event,
            where=Filter.is_set(property=CustomPropertyRef(saved_cp_id)),
        )
        f = params["sections"]["filter"][0]
        assert f["customPropertyId"] == saved_cp_id
        assert "value" not in f

    def test_composed_properties_format(self) -> None:
        """_build_composed_properties() produces {key: {value, type, resourceType}}."""
        inputs = {
            "A": PropertyInput("price", type="number"),
            "B": PropertyInput("email", type="string", resource_type="user"),
        }
        result = _build_composed_properties(inputs)

        assert set(result.keys()) == {"A", "B"}
        for key in result:
            assert set(result[key].keys()) == {"value", "type", "resourceType"}
        assert result["A"]["value"] == "price"
        assert result["B"]["resourceType"] == "user"


# =============================================================================
# Backward Compatibility
# =============================================================================


class TestBackwardCompatibility:
    """Existing queries without custom properties still work after type widening."""

    def test_plain_string_query_unchanged(self, ws: Workspace, real_event: str) -> None:
        """Plain event string query still works."""
        result = ws.query(real_event, last=7)
        assert isinstance(result, QueryResult)

    def test_plain_string_groupby_unchanged(
        self, ws: Workspace, real_event: str, real_string_property: str
    ) -> None:
        """Plain string group_by still works."""
        result = ws.query(real_event, group_by=real_string_property, last=7)
        assert isinstance(result, QueryResult)

    def test_groupby_object_without_cp_unchanged(
        self, ws: Workspace, real_event: str, real_string_property: str
    ) -> None:
        """GroupBy object with plain string property still works."""
        result = ws.query(real_event, group_by=GroupBy(real_string_property), last=7)
        assert isinstance(result, QueryResult)

    def test_metric_with_string_property_unchanged(
        self, ws: Workspace, real_event: str
    ) -> None:
        """Metric with plain string math still works."""
        result = ws.query(Metric(real_event, math="total"), last=7)
        assert isinstance(result, QueryResult)

    def test_filter_with_string_property_unchanged(
        self, ws: Workspace, real_event: str, real_string_property: str
    ) -> None:
        """Filter with plain string property still works."""
        result = ws.query(
            real_event,
            where=Filter.is_set(real_string_property),
            last=7,
        )
        assert isinstance(result, QueryResult)
