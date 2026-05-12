"""Unit tests for custom property bookmark builder helpers (Phase 037).

Tests for _build_composed_properties(), build_group_section(),
and build_filter_entry() with custom property dispatch.

Task IDs: T006, T017-T022, T026-T031, T034-T037
"""

from __future__ import annotations

from pydantic import SecretStr

from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless._internal.bookmark_builders import (
    _build_composed_properties,
    build_filter_entry,
    build_group_section,
)
from mixpanel_headless.types import (
    CohortBreakdown,
    CustomPropertyRef,
    Filter,
    GroupBy,
    InlineCustomProperty,
    PropertyInput,
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
# T006: _build_composed_properties() tests
# =============================================================================


class TestBuildComposedProperties:
    """Tests for _build_composed_properties() helper function."""

    def test_single_input(self) -> None:
        """Single input produces a single-entry dict with correct fields."""
        inputs = {"A": PropertyInput("price", type="number")}

        result = _build_composed_properties(inputs)

        assert result == {
            "A": {
                "value": "price",
                "type": "number",
                "resourceType": "event",
            },
        }

    def test_multiple_inputs(self) -> None:
        """Multiple inputs produce correctly keyed entries."""
        inputs = {
            "A": PropertyInput("price", type="number"),
            "B": PropertyInput("quantity", type="number"),
        }

        result = _build_composed_properties(inputs)

        assert len(result) == 2
        assert result["A"]["value"] == "price"
        assert result["B"]["value"] == "quantity"
        assert result["A"]["type"] == "number"
        assert result["B"]["type"] == "number"
        assert result["A"]["resourceType"] == "event"
        assert result["B"]["resourceType"] == "event"

    def test_user_resource_type_preserved(self) -> None:
        """User resource_type is preserved in the output."""
        inputs = {"A": PropertyInput("email", type="string", resource_type="user")}

        result = _build_composed_properties(inputs)

        assert result["A"]["resourceType"] == "user"

    def test_default_values(self) -> None:
        """Default PropertyInput values (string type, event resource) are preserved."""
        inputs = {"A": PropertyInput("country")}

        result = _build_composed_properties(inputs)

        assert result["A"] == {
            "value": "country",
            "type": "string",
            "resourceType": "event",
        }


# =============================================================================
# T017-T022: build_group_section() with custom properties (US1)
# =============================================================================


class TestBuildGroupSectionCustomProperties:
    """Tests for build_group_section() with custom property dispatch."""

    def test_plain_string_unchanged(self) -> None:
        """T017: Plain string group_by produces unchanged output (backward compat)."""
        result = build_group_section("country")

        assert len(result) == 1
        assert result[0]["value"] == "country"
        assert result[0]["propertyName"] == "country"
        assert result[0]["resourceType"] == "events"

    def test_custom_property_ref(self) -> None:
        """T018: GroupBy with CustomPropertyRef produces customPropertyId, no value/propertyName."""
        g = GroupBy(property=CustomPropertyRef(42), property_type="number")

        result = build_group_section(g)

        assert len(result) == 1
        entry = result[0]
        assert entry["customPropertyId"] == 42
        assert entry["propertyType"] == "number"
        assert entry["resourceType"] == "events"
        assert entry["dataset"] == "$mixpanel"
        assert entry["isHidden"] is False
        assert "propertyName" not in entry

    def test_inline_custom_property(self) -> None:
        """T019: GroupBy with InlineCustomProperty produces customProperty dict."""
        icp = InlineCustomProperty.numeric("A * B", A="price", B="quantity")
        g = GroupBy(property=icp, property_type="number")

        result = build_group_section(g)

        assert len(result) == 1
        entry = result[0]
        assert "customProperty" in entry
        cp = entry["customProperty"]
        assert cp["displayFormula"] == "A * B"
        assert "A" in cp["composedProperties"]
        assert "B" in cp["composedProperties"]
        assert cp["composedProperties"]["A"]["value"] == "price"
        assert cp["propertyType"] == "number"
        assert cp["resourceType"] == "events"
        assert entry["propertyType"] == "number"
        assert entry["resourceType"] == "events"
        assert entry["dataset"] == "$mixpanel"
        assert entry["isHidden"] is False
        assert "propertyName" not in entry

    def test_bucketing_with_custom_property_ref(self) -> None:
        """T020: Bucketing works with CustomPropertyRef."""
        g = GroupBy(
            property=CustomPropertyRef(42),
            property_type="number",
            bucket_size=100,
            bucket_min=0,
            bucket_max=1000,
        )

        result = build_group_section(g)

        entry = result[0]
        assert entry["customPropertyId"] == 42
        assert entry["customBucket"] == {
            "bucketSize": 100,
            "min": 0,
            "max": 1000,
        }

    def test_bucketing_with_inline_custom_property(self) -> None:
        """T020: Bucketing works with InlineCustomProperty."""
        icp = InlineCustomProperty.numeric("A * B", A="price", B="qty")
        g = GroupBy(
            property=icp,
            property_type="number",
            bucket_size=50,
            bucket_min=0,
            bucket_max=500,
        )

        result = build_group_section(g)

        entry = result[0]
        assert "customProperty" in entry
        assert entry["customBucket"] == {
            "bucketSize": 50,
            "min": 0,
            "max": 500,
        }

    def test_inline_property_type_overrides_group_by(self) -> None:
        """T021: InlineCustomProperty.property_type overrides GroupBy.property_type."""
        icp = InlineCustomProperty(
            formula='IFS(A > 1000, "Enterprise", TRUE, "Free")',
            inputs={"A": PropertyInput("amount", type="number")},
            property_type="string",
        )
        g = GroupBy(property=icp, property_type="number")

        result = build_group_section(g)

        entry = result[0]
        # Inline's property_type="string" overrides GroupBy's "number"
        assert entry["customProperty"]["propertyType"] == "string"
        assert entry["propertyType"] == "string"

    def test_inline_property_type_none_falls_back(self) -> None:
        """T021b: InlineCustomProperty.property_type=None falls back to GroupBy.property_type."""
        icp = InlineCustomProperty(
            formula="A",
            inputs={"A": PropertyInput("revenue", type="number")},
            property_type=None,
        )
        g = GroupBy(property=icp, property_type="number")

        result = build_group_section(g)

        entry = result[0]
        assert entry["customProperty"]["propertyType"] == "number"
        assert entry["propertyType"] == "number"

    def test_mixed_group_by_list(self) -> None:
        """T022: Mixed group_by list with plain string, CustomPropertyRef, InlineCustomProperty."""
        groups: list[str | GroupBy | CohortBreakdown] = [
            "country",
            GroupBy(property=CustomPropertyRef(42), property_type="number"),
            GroupBy(
                property=InlineCustomProperty.numeric("A", A="revenue"),
                property_type="number",
            ),
        ]

        result = build_group_section(groups)

        assert len(result) == 3
        # Plain string
        assert result[0]["value"] == "country"
        # CustomPropertyRef
        assert result[1]["customPropertyId"] == 42
        # InlineCustomProperty
        assert "customProperty" in result[2]


# =============================================================================
# T026-T031: build_filter_entry() with custom properties (US2)
# =============================================================================


class TestBuildFilterEntryCustomProperties:
    """Tests for build_filter_entry() with custom property dispatch."""

    def test_plain_string_unchanged(self) -> None:
        """T026: Plain string filter produces unchanged output (backward compat)."""
        f = Filter.equals("country", "US")

        entry = build_filter_entry(f)

        assert entry["value"] == "country"
        assert entry["filterOperator"] == "equals"
        assert "customPropertyId" not in entry
        assert "customProperty" not in entry

    def test_custom_property_ref(self) -> None:
        """T027: CustomPropertyRef produces customPropertyId, no value field."""
        f = Filter.greater_than(property=CustomPropertyRef(42), value=100)

        entry = build_filter_entry(f)

        assert entry["customPropertyId"] == 42
        assert entry["filterOperator"] == "is greater than"
        assert entry["filterValue"] == 100
        assert "value" not in entry

    def test_inline_custom_property(self) -> None:
        """T028: InlineCustomProperty produces customProperty dict, no value field."""
        icp = InlineCustomProperty.numeric("A * B", A="price", B="quantity")
        f = Filter.greater_than(property=icp, value=1000)

        entry = build_filter_entry(f)

        assert "customProperty" in entry
        cp = entry["customProperty"]
        assert cp["displayFormula"] == "A * B"
        assert "A" in cp["composedProperties"]
        assert cp["propertyType"] == "number"
        assert cp["resourceType"] == "events"
        assert entry["filterValue"] == 1000
        assert entry["filterOperator"] == "is greater than"
        assert "value" not in entry

    def test_inline_filter_type_uses_property_type(self) -> None:
        """T029: InlineCustomProperty filterType/defaultType uses property_type."""
        icp = InlineCustomProperty(
            formula="A",
            inputs={"A": PropertyInput("email", type="string")},
            property_type="string",
        )
        f = Filter.equals(property=icp, value="test")

        entry = build_filter_entry(f)

        assert entry["filterType"] == "string"
        assert entry["defaultType"] == "string"

    def test_custom_property_ref_preserves_resource_type(self) -> None:
        """T030: CustomPropertyRef preserves Filter's resource_type."""
        f = Filter.equals(
            property=CustomPropertyRef(42),
            value="admin",
            resource_type="people",
        )

        entry = build_filter_entry(f)

        assert entry["resourceType"] == "people"
        assert entry["customPropertyId"] == 42

    def test_inline_uses_own_resource_type(self) -> None:
        """T031: InlineCustomProperty uses its own resource_type in filter entry."""
        icp = InlineCustomProperty(
            formula="A",
            inputs={"A": PropertyInput("email", resource_type="user")},
            property_type="string",
            resource_type="people",
        )
        f = Filter.equals(property=icp, value="test")

        entry = build_filter_entry(f)

        assert entry["customProperty"]["resourceType"] == "people"
        assert entry["resourceType"] == "people"

    def test_inline_property_type_none_uses_filter_default(self) -> None:
        """InlineCustomProperty with property_type=None falls back to Filter's type."""
        icp = InlineCustomProperty(
            formula="A",
            inputs={"A": PropertyInput("price", type="number")},
            property_type=None,
        )
        f = Filter.greater_than(property=icp, value=100)

        entry = build_filter_entry(f)

        # greater_than sets _property_type="number"; None falls back to it
        assert entry["filterType"] == "number"
        assert entry["defaultType"] == "number"


# =============================================================================
# T034-T037: Measurement property builder tests (US3)
# =============================================================================


class TestMeasurementPropertyBuilder:
    """Tests for measurement property section in bookmark params.

    These tests verify the measurement dict directly from workspace
    _build_query_params output.
    """

    def test_plain_string_measurement_unchanged(self) -> None:
        """T034: Plain string Metric.property produces unchanged measurement (backward compat)."""
        from unittest.mock import MagicMock

        from mixpanel_headless import Workspace
        from mixpanel_headless.types import Metric

        creds = make_session(username="u", secret="s", project_id="1", region="us")
        mgr = MagicMock()
        mgr.config_version.return_value = 1
        mgr.resolve_credentials.return_value = creds
        ws = Workspace(session=_TEST_SESSION, _api_client=MagicMock())

        params = ws.build_params(
            Metric("Purchase", math="average", property="amount"),
        )

        measurement = params["sections"]["show"][0]["measurement"]
        assert measurement["property"] == {
            "name": "amount",
            "resourceType": "events",
        }

    def test_custom_property_ref_in_measurement(self) -> None:
        """T035: CustomPropertyRef in measurement produces customPropertyId."""
        from unittest.mock import MagicMock

        from mixpanel_headless import Workspace
        from mixpanel_headless.types import Metric

        creds = make_session(username="u", secret="s", project_id="1", region="us")
        mgr = MagicMock()
        mgr.config_version.return_value = 1
        mgr.resolve_credentials.return_value = creds
        ws = Workspace(session=_TEST_SESSION, _api_client=MagicMock())

        params = ws.build_params(
            Metric("Purchase", math="average", property=CustomPropertyRef(42)),
        )

        measurement = params["sections"]["show"][0]["measurement"]
        prop = measurement["property"]
        assert prop["customPropertyId"] == 42
        assert prop["resourceType"] == "events"
        assert prop.get("name") is not None  # name present for server compat

    def test_inline_custom_property_in_measurement(self) -> None:
        """T036: InlineCustomProperty in measurement produces customProperty dict."""
        from unittest.mock import MagicMock

        from mixpanel_headless import Workspace
        from mixpanel_headless.types import Metric

        creds = make_session(username="u", secret="s", project_id="1", region="us")
        mgr = MagicMock()
        mgr.config_version.return_value = 1
        mgr.resolve_credentials.return_value = creds
        ws = Workspace(session=_TEST_SESSION, _api_client=MagicMock())

        icp = InlineCustomProperty.numeric("A * B", A="price", B="quantity")
        params = ws.build_params(
            Metric("Purchase", math="average", property=icp),
        )

        measurement = params["sections"]["show"][0]["measurement"]
        prop = measurement["property"]
        assert "customProperty" in prop
        assert prop["customProperty"]["displayFormula"] == "A * B"
        assert prop["resourceType"] == "events"
        assert prop.get("name") is not None  # name present for server compat

    def test_top_level_math_property_string_unchanged(self) -> None:
        """T037: Top-level math_property as plain string produces unchanged measurement."""
        from unittest.mock import MagicMock

        from mixpanel_headless import Workspace

        creds = make_session(username="u", secret="s", project_id="1", region="us")
        mgr = MagicMock()
        mgr.config_version.return_value = 1
        mgr.resolve_credentials.return_value = creds
        ws = Workspace(session=_TEST_SESSION, _api_client=MagicMock())

        params = ws.build_params(
            "Purchase",
            math="average",
            math_property="amount",
        )

        measurement = params["sections"]["show"][0]["measurement"]
        assert measurement["property"] == {
            "name": "amount",
            "resourceType": "events",
        }
