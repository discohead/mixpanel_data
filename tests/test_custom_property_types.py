"""Unit tests for custom property query types (Phase 037).

Tests for PropertyInput, InlineCustomProperty, and CustomPropertyRef
frozen dataclasses, plus the PropertySpec type alias. Covers construction,
defaults, immutability, the InlineCustomProperty.numeric() convenience
constructor, and fail-fast validation (CP1-CP6).

Task IDs: T001-T005, T047-T056
"""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.exceptions import BookmarkValidationError
from mixpanel_headless.types import (
    CustomPropertyRef,
    Filter,
    GroupBy,
    InlineCustomProperty,
    Metric,
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
# T001: PropertyInput construction tests
# =============================================================================


class TestPropertyInput:
    """Tests for PropertyInput frozen dataclass construction."""

    def test_minimal_construction(self) -> None:
        """PropertyInput can be constructed with just a name."""
        pi = PropertyInput("price")

        assert pi.name == "price"
        assert pi.type == "string"
        assert pi.resource_type == "event"

    def test_explicit_number_type(self) -> None:
        """PropertyInput accepts explicit number type."""
        pi = PropertyInput("amount", type="number")

        assert pi.name == "amount"
        assert pi.type == "number"
        assert pi.resource_type == "event"

    def test_user_resource_type(self) -> None:
        """PropertyInput accepts user resource_type."""
        pi = PropertyInput("email", resource_type="user")

        assert pi.name == "email"
        assert pi.type == "string"
        assert pi.resource_type == "user"

    @pytest.mark.parametrize(
        "prop_type",
        ["string", "number", "boolean", "datetime", "list"],
    )
    def test_all_valid_types(self, prop_type: str) -> None:
        """PropertyInput accepts all 5 valid property types."""
        pi = PropertyInput("prop", type=prop_type)  # type: ignore[arg-type]

        assert pi.type == prop_type

    def test_all_fields_explicit(self) -> None:
        """PropertyInput accepts all fields set explicitly."""
        pi = PropertyInput("revenue", type="number", resource_type="user")

        assert pi.name == "revenue"
        assert pi.type == "number"
        assert pi.resource_type == "user"


# =============================================================================
# T002: InlineCustomProperty construction tests
# =============================================================================


class TestInlineCustomProperty:
    """Tests for InlineCustomProperty frozen dataclass construction."""

    def test_minimal_construction(self) -> None:
        """InlineCustomProperty can be constructed with formula + single input."""
        icp = InlineCustomProperty(
            formula="A",
            inputs={"A": PropertyInput("price")},
        )

        assert icp.formula == "A"
        assert len(icp.inputs) == 1
        assert icp.inputs["A"].name == "price"
        assert icp.property_type is None
        assert icp.resource_type == "events"

    def test_full_construction(self) -> None:
        """InlineCustomProperty accepts all fields explicitly."""
        icp = InlineCustomProperty(
            formula="A * B",
            inputs={
                "A": PropertyInput("price", type="number"),
                "B": PropertyInput("quantity", type="number"),
            },
            property_type="number",
            resource_type="people",
        )

        assert icp.formula == "A * B"
        assert len(icp.inputs) == 2
        assert icp.property_type == "number"
        assert icp.resource_type == "people"


# =============================================================================
# T003: InlineCustomProperty.numeric() convenience constructor tests
# =============================================================================


class TestInlineCustomPropertyNumeric:
    """Tests for InlineCustomProperty.numeric() classmethod."""

    def test_multi_input(self) -> None:
        """numeric() creates an all-number InlineCustomProperty with multiple inputs."""
        icp = InlineCustomProperty.numeric("A * B", A="price", B="quantity")

        assert icp.formula == "A * B"
        assert len(icp.inputs) == 2
        assert icp.inputs["A"].name == "price"
        assert icp.inputs["A"].type == "number"
        assert icp.inputs["A"].resource_type == "event"
        assert icp.inputs["B"].name == "quantity"
        assert icp.inputs["B"].type == "number"
        assert icp.property_type == "number"
        assert icp.resource_type == "events"

    def test_single_input(self) -> None:
        """numeric() works with a single input."""
        icp = InlineCustomProperty.numeric("A", A="revenue")

        assert icp.formula == "A"
        assert len(icp.inputs) == 1
        assert icp.inputs["A"].name == "revenue"
        assert icp.inputs["A"].type == "number"
        assert icp.property_type == "number"


# =============================================================================
# T004: CustomPropertyRef construction tests
# =============================================================================


class TestCustomPropertyRef:
    """Tests for CustomPropertyRef frozen dataclass construction."""

    def test_stores_integer_id(self) -> None:
        """CustomPropertyRef stores the given integer ID."""
        ref = CustomPropertyRef(42)

        assert ref.id == 42

    def test_large_id(self) -> None:
        """CustomPropertyRef handles large IDs."""
        ref = CustomPropertyRef(999999)

        assert ref.id == 999999


# =============================================================================
# T005: Immutability tests
# =============================================================================


class TestImmutability:
    """Tests that all three types are frozen (immutable)."""

    def test_property_input_frozen(self) -> None:
        """PropertyInput raises FrozenInstanceError on attribute assignment."""
        pi = PropertyInput("price")

        with pytest.raises(dataclasses.FrozenInstanceError):
            pi.name = "other"  # type: ignore[misc]

    def test_inline_custom_property_frozen(self) -> None:
        """InlineCustomProperty raises FrozenInstanceError on attribute assignment."""
        icp = InlineCustomProperty(
            formula="A",
            inputs={"A": PropertyInput("price")},
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            icp.formula = "B"  # type: ignore[misc]

    def test_custom_property_ref_frozen(self) -> None:
        """CustomPropertyRef raises FrozenInstanceError on attribute assignment."""
        ref = CustomPropertyRef(42)

        with pytest.raises(dataclasses.FrozenInstanceError):
            ref.id = 99  # type: ignore[misc]


# =============================================================================
# Type widening backward compatibility tests
# =============================================================================


class TestTypeWidening:
    """Tests that widened types still accept plain strings (backward compat)."""

    def test_metric_property_accepts_string(self) -> None:
        """Metric.property still accepts plain string."""
        m = Metric("Purchase", math="average", property="amount")

        assert m.property == "amount"

    def test_metric_property_accepts_custom_property_ref(self) -> None:
        """Metric.property accepts CustomPropertyRef."""
        m = Metric("Purchase", math="average", property=CustomPropertyRef(42))

        assert isinstance(m.property, CustomPropertyRef)
        assert m.property.id == 42

    def test_metric_property_accepts_inline_custom_property(self) -> None:
        """Metric.property accepts InlineCustomProperty."""
        icp = InlineCustomProperty.numeric("A * B", A="price", B="qty")
        m = Metric("Purchase", math="average", property=icp)

        assert isinstance(m.property, InlineCustomProperty)

    def test_group_by_property_accepts_string(self) -> None:
        """GroupBy.property still accepts plain string."""
        g = GroupBy("country")

        assert g.property == "country"

    def test_group_by_property_accepts_custom_property_ref(self) -> None:
        """GroupBy.property accepts CustomPropertyRef."""
        g = GroupBy(property=CustomPropertyRef(42), property_type="number")

        assert isinstance(g.property, CustomPropertyRef)

    def test_group_by_property_accepts_inline_custom_property(self) -> None:
        """GroupBy.property accepts InlineCustomProperty."""
        icp = InlineCustomProperty.numeric("A", A="revenue")
        g = GroupBy(property=icp, property_type="number")

        assert isinstance(g.property, InlineCustomProperty)

    def test_filter_equals_accepts_custom_property_ref(self) -> None:
        """Filter.equals() accepts CustomPropertyRef in property position."""
        f = Filter.equals(property=CustomPropertyRef(42), value="Enterprise")

        assert isinstance(f._property, CustomPropertyRef)

    def test_filter_greater_than_accepts_inline(self) -> None:
        """Filter.greater_than() accepts InlineCustomProperty."""
        icp = InlineCustomProperty.numeric("A * B", A="price", B="qty")
        f = Filter.greater_than(property=icp, value=100)

        assert isinstance(f._property, InlineCustomProperty)

    def test_filter_is_set_accepts_custom_property_ref(self) -> None:
        """Filter.is_set() accepts CustomPropertyRef."""
        f = Filter.is_set(property=CustomPropertyRef(42))

        assert isinstance(f._property, CustomPropertyRef)


# =============================================================================
# T047-T056: Fail-fast validation tests (US5, CP1-CP6)
# =============================================================================


@pytest.fixture
def ws() -> Workspace:
    """Create a Workspace instance with mocked dependencies."""
    creds = make_session(username="u", secret="s", project_id="1", region="us")
    mgr = MagicMock()
    mgr.config_version.return_value = 1
    mgr.resolve_credentials.return_value = creds
    return Workspace(session=_TEST_SESSION, _api_client=MagicMock())


class TestCustomPropertyValidationCP1:
    """T047: CP1 — CustomPropertyRef.id must be positive."""

    def test_zero_id_in_group_by(self, ws: Workspace) -> None:
        """CustomPropertyRef(0) in group_by raises validation error."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                "Purchase",
                group_by=GroupBy(property=CustomPropertyRef(0), property_type="number"),
            )

    def test_negative_id(self, ws: Workspace) -> None:
        """CustomPropertyRef(-1) raises validation error."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                "Purchase",
                group_by=GroupBy(
                    property=CustomPropertyRef(-1), property_type="number"
                ),
            )


class TestCustomPropertyValidationCP2:
    """T048: CP2 — InlineCustomProperty with empty formula."""

    def test_empty_formula(self, ws: Workspace) -> None:
        """Empty formula raises validation error."""
        icp = InlineCustomProperty(
            formula="",
            inputs={"A": PropertyInput("price")},
        )

        with pytest.raises(BookmarkValidationError, match="non-empty"):
            ws.build_params(
                "Purchase",
                group_by=GroupBy(property=icp, property_type="string"),
            )

    def test_whitespace_only_formula(self, ws: Workspace) -> None:
        """Whitespace-only formula raises validation error."""
        icp = InlineCustomProperty(
            formula="   ",
            inputs={"A": PropertyInput("price")},
        )

        with pytest.raises(BookmarkValidationError, match="non-empty"):
            ws.build_params(
                "Purchase",
                group_by=GroupBy(property=icp, property_type="string"),
            )


class TestCustomPropertyValidationCP3:
    """T049: CP3 — InlineCustomProperty with empty inputs dict."""

    def test_empty_inputs(self, ws: Workspace) -> None:
        """Empty inputs dict raises validation error."""
        icp = InlineCustomProperty(formula="A", inputs={})

        with pytest.raises(BookmarkValidationError, match="at least one input"):
            ws.build_params(
                "Purchase",
                group_by=GroupBy(property=icp, property_type="string"),
            )


class TestCustomPropertyValidationCP4:
    """T050: CP4 — InlineCustomProperty input keys must be single uppercase A-Z."""

    @pytest.mark.parametrize("key", ["a", "AB", "1", "aa"])
    def test_invalid_keys(self, key: str, ws: Workspace) -> None:
        """Invalid input keys raise validation error."""
        icp = InlineCustomProperty(
            formula="A",
            inputs={key: PropertyInput("price")},
        )

        with pytest.raises(BookmarkValidationError, match="uppercase"):
            ws.build_params(
                "Purchase",
                group_by=GroupBy(property=icp, property_type="string"),
            )


class TestCustomPropertyValidationCP5:
    """T051: CP5 — Formula exceeds 20,000 chars."""

    def test_formula_too_long(self, ws: Workspace) -> None:
        """Formula > 20,000 chars raises validation error."""
        icp = InlineCustomProperty(
            formula="A" * 20_001,
            inputs={"A": PropertyInput("price")},
        )

        with pytest.raises(BookmarkValidationError, match="20,000"):
            ws.build_params(
                "Purchase",
                group_by=GroupBy(property=icp, property_type="string"),
            )

    def test_formula_at_boundary_passes(self, ws: Workspace) -> None:
        """Formula at exactly 20,000 chars passes validation."""
        icp = InlineCustomProperty(
            formula="A" * 20_000,
            inputs={"A": PropertyInput("price")},
        )

        # Should NOT raise — exactly at the limit
        params = ws.build_params(
            "Purchase",
            group_by=GroupBy(property=icp, property_type="string"),
        )
        assert "sections" in params


class TestCustomPropertyValidationCP6:
    """T052: CP6 — PropertyInput with empty name."""

    def test_empty_property_name(self, ws: Workspace) -> None:
        """Empty PropertyInput.name raises validation error."""
        icp = InlineCustomProperty(
            formula="A",
            inputs={"A": PropertyInput("")},
        )

        with pytest.raises(BookmarkValidationError, match="empty property name"):
            ws.build_params(
                "Purchase",
                group_by=GroupBy(property=icp, property_type="string"),
            )


class TestCustomPropertyValidationValid:
    """T053: Valid custom properties pass validation."""

    def test_valid_inline_passes(self, ws: Workspace) -> None:
        """Valid InlineCustomProperty passes validation without errors."""
        icp = InlineCustomProperty.numeric("A * B", A="price", B="quantity")
        # Should not raise
        ws.build_params(
            "Purchase",
            group_by=GroupBy(property=icp, property_type="number"),
        )

    def test_valid_ref_passes(self, ws: Workspace) -> None:
        """Valid CustomPropertyRef passes validation without errors."""
        # Should not raise
        ws.build_params(
            "Purchase",
            group_by=GroupBy(property=CustomPropertyRef(42), property_type="number"),
        )


class TestCustomPropertyValidationFilterPosition:
    """T054: CP validation in filter (where) position."""

    def test_invalid_ref_in_filter(self, ws: Workspace) -> None:
        """CustomPropertyRef(0) in filter raises validation error."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                "Purchase",
                where=Filter.greater_than(property=CustomPropertyRef(0), value=100),
            )


class TestCustomPropertyValidationMeasurementPosition:
    """T055: CP validation in Metric.property position."""

    def test_invalid_ref_in_metric(self, ws: Workspace) -> None:
        """CustomPropertyRef(0) in Metric.property raises validation error."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                Metric("Purchase", math="average", property=CustomPropertyRef(0)),
            )


class TestCustomPropertyValidationFunnelRetention:
    """T056: CP validation in funnel group_by and retention where."""

    def test_invalid_ref_in_funnel_group_by(self, ws: Workspace) -> None:
        """CustomPropertyRef(0) in funnel group_by raises validation error."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_funnel_params(
                ["Signup", "Purchase"],
                group_by=GroupBy(property=CustomPropertyRef(0), property_type="number"),
            )

    def test_invalid_ref_in_retention_group_by(self, ws: Workspace) -> None:
        """CustomPropertyRef(0) in retention group_by raises validation error."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_retention_params(
                "Signup",
                "Login",
                group_by=GroupBy(property=CustomPropertyRef(0), property_type="number"),
            )

    def test_invalid_ref_in_funnel_where(self, ws: Workspace) -> None:
        """CustomPropertyRef(0) in funnel where raises validation error."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_funnel_params(
                ["Signup", "Purchase"],
                where=Filter.greater_than(property=CustomPropertyRef(0), value=100),
            )

    def test_invalid_ref_in_retention_where(self, ws: Workspace) -> None:
        """CustomPropertyRef(0) in retention where raises validation error."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_retention_params(
                "Signup",
                "Login",
                where=Filter.greater_than(property=CustomPropertyRef(0), value=100),
            )
