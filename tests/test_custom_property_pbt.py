"""Property-based tests for custom property query types using Hypothesis.

These tests verify invariants of PropertyInput, InlineCustomProperty,
CustomPropertyRef, and _build_composed_properties that should hold for
all valid inputs. Covers tasks T062-T067.

Usage:
    # Run with default profile (100 examples)
    pytest tests/test_custom_property_pbt.py

    # Run with dev profile (10 examples)
    HYPOTHESIS_PROFILE=dev pytest tests/test_custom_property_pbt.py

    # Run with CI profile (200 examples, deterministic)
    HYPOTHESIS_PROFILE=ci pytest tests/test_custom_property_pbt.py
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from mixpanel_headless._internal.bookmark_builders import _build_composed_properties
from mixpanel_headless.types import (
    CustomPropertyRef,
    InlineCustomProperty,
    PropertyInput,
)

# =============================================================================
# Custom Strategies (T062-T063)
# =============================================================================

# T062: valid_property_input — non-empty name, valid type/resource_type literals
_property_types = st.sampled_from(["string", "number", "boolean", "datetime", "list"])
_resource_types = st.sampled_from(["event", "user"])

_non_empty_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())


@st.composite
def valid_property_input(draw: st.DrawFn) -> PropertyInput:
    """Strategy that produces a valid PropertyInput with arbitrary fields.

    Draws:
        name: Non-empty printable string (1-50 chars).
        type: One of the 5 valid property type literals.
        resource_type: Either "event" or "user".

    Returns:
        A fully constructed PropertyInput instance.
    """
    name = draw(_non_empty_names)
    prop_type = draw(_property_types)
    res_type = draw(_resource_types)
    return PropertyInput(name=name, type=prop_type, resource_type=res_type)  # type: ignore[arg-type]


# T063: valid_input_key — single uppercase letter A-Z
valid_input_key = st.sampled_from([chr(c) for c in range(ord("A"), ord("Z") + 1)])

# T063: valid_inputs_dict — dict of 1-5 entries mapping valid keys to valid PropertyInput
_unique_keys = st.lists(
    valid_input_key,
    min_size=1,
    max_size=5,
    unique=True,
)


@st.composite
def valid_inputs_dict(draw: st.DrawFn) -> dict[str, PropertyInput]:
    """Strategy that produces a dict of 1-5 valid input key/PropertyInput pairs.

    Draws:
        keys: 1-5 unique uppercase letters (A-Z).
        values: A valid PropertyInput for each key.

    Returns:
        Dict mapping uppercase letters to PropertyInput instances.
    """
    keys = draw(_unique_keys)
    inputs: dict[str, PropertyInput] = {}
    for key in keys:
        inputs[key] = draw(valid_property_input())
    return inputs


# Non-empty formula strings for InlineCustomProperty
_formulas = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Zs")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

# Optional property_type for InlineCustomProperty
_optional_property_types = st.one_of(
    st.none(),
    st.sampled_from(["string", "number", "boolean", "datetime"]),
)

# resource_type for InlineCustomProperty (plural form)
_icp_resource_types = st.sampled_from(["events", "people"])


# =============================================================================
# T064: PropertyInput round-trip invariants
# =============================================================================


class TestPropertyInputPBT:
    """Property-based tests for PropertyInput construction (T064)."""

    @given(prop=valid_property_input())
    def test_property_input_round_trip(self, prop: PropertyInput) -> None:
        """All PropertyInput field values survive construction unchanged.

        Verifies that the frozen dataclass preserves the exact name, type,
        and resource_type values that were passed in.

        Args:
            prop: A randomly generated valid PropertyInput.
        """
        reconstructed = PropertyInput(
            name=prop.name,
            type=prop.type,
            resource_type=prop.resource_type,
        )
        assert reconstructed.name == prop.name
        assert reconstructed.type == prop.type
        assert reconstructed.resource_type == prop.resource_type

    @given(prop=valid_property_input())
    def test_property_input_is_frozen(self, prop: PropertyInput) -> None:
        """PropertyInput instances are immutable (frozen dataclass).

        Args:
            prop: A randomly generated valid PropertyInput.
        """
        try:
            prop.name = "mutated"  # type: ignore[misc]
            raise AssertionError("Expected AttributeError for frozen dataclass")
        except AttributeError:
            pass

    @given(name=_non_empty_names)
    def test_property_input_defaults(self, name: str) -> None:
        """PropertyInput defaults to type='string' and resource_type='event'.

        Args:
            name: A non-empty property name.
        """
        prop = PropertyInput(name=name)
        assert prop.type == "string"
        assert prop.resource_type == "event"


# =============================================================================
# T065: InlineCustomProperty preserves formula and inputs
# =============================================================================


class TestInlineCustomPropertyPBT:
    """Property-based tests for InlineCustomProperty construction (T065)."""

    @given(
        formula=_formulas,
        inputs=valid_inputs_dict(),
        property_type=_optional_property_types,
        resource_type=_icp_resource_types,
    )
    def test_inline_custom_property_preserves_formula_and_inputs(
        self,
        formula: str,
        inputs: dict[str, PropertyInput],
        property_type: str | None,
        resource_type: str,  # Literal["events", "people"] at runtime
    ) -> None:
        """InlineCustomProperty construction preserves formula and inputs.

        Verifies that the formula string, inputs dict, property_type, and
        resource_type are all stored exactly as provided.

        Args:
            formula: A non-empty formula expression.
            inputs: Dict of 1-5 valid input key/PropertyInput pairs.
            property_type: Optional result type literal.
            resource_type: Data domain ("events" or "people").
        """
        icp = InlineCustomProperty(
            formula=formula,
            inputs=inputs,
            property_type=property_type,  # type: ignore[arg-type]
            resource_type=resource_type,  # type: ignore[arg-type]
        )
        assert icp.formula == formula
        assert icp.inputs == inputs
        assert icp.property_type == property_type
        assert icp.resource_type == resource_type

    @given(
        formula=_formulas,
        inputs=valid_inputs_dict(),
    )
    def test_inline_custom_property_defaults(
        self,
        formula: str,
        inputs: dict[str, PropertyInput],
    ) -> None:
        """InlineCustomProperty defaults: property_type=None, resource_type='events'.

        Args:
            formula: A non-empty formula expression.
            inputs: Dict of 1-5 valid input key/PropertyInput pairs.
        """
        icp = InlineCustomProperty(formula=formula, inputs=inputs)
        assert icp.property_type is None
        assert icp.resource_type == "events"

    @given(
        formula=_formulas,
        properties=st.dictionaries(
            keys=valid_input_key,
            values=_non_empty_names,
            min_size=1,
            max_size=5,
        ),
    )
    def test_numeric_classmethod_sets_number_types(
        self,
        formula: str,
        properties: dict[str, str],
    ) -> None:
        """InlineCustomProperty.numeric sets all inputs to type='number'.

        Verifies the convenience constructor creates PropertyInput entries
        with type='number' and sets property_type='number'.

        Args:
            formula: A non-empty formula expression.
            properties: Dict mapping variable letters to property names.
        """
        icp = InlineCustomProperty.numeric(formula, **properties)
        assert icp.formula == formula
        assert icp.property_type == "number"
        for key, name in properties.items():
            assert key in icp.inputs
            assert icp.inputs[key].name == name
            assert icp.inputs[key].type == "number"
            assert icp.inputs[key].resource_type == "event"


# =============================================================================
# T066: _build_composed_properties keys match
# =============================================================================


class TestBuildComposedPropertiesPBT:
    """Property-based tests for _build_composed_properties (T066-T067)."""

    @given(inputs=valid_inputs_dict())
    def test_build_composed_properties_keys_match(
        self, inputs: dict[str, PropertyInput]
    ) -> None:
        """_build_composed_properties output keys match input keys exactly.

        The set of keys in the output dict must be identical to the set
        of keys in the input dict.

        Args:
            inputs: Dict of 1-5 valid input key/PropertyInput pairs.
        """
        result = _build_composed_properties(inputs)
        assert set(result.keys()) == set(inputs.keys())

    # =========================================================================
    # T067: _build_composed_properties required fields
    # =========================================================================

    @given(inputs=valid_inputs_dict())
    def test_build_composed_properties_required_fields(
        self, inputs: dict[str, PropertyInput]
    ) -> None:
        """Output values have required fields: value, type, resourceType.

        Each entry in the composed properties dict must contain exactly
        the three required keys, and their values must match the
        corresponding PropertyInput fields.

        Args:
            inputs: Dict of 1-5 valid input key/PropertyInput pairs.
        """
        result = _build_composed_properties(inputs)
        required_keys = {"value", "type", "resourceType"}

        for key, entry in result.items():
            assert set(entry.keys()) == required_keys
            prop = inputs[key]
            assert entry["value"] == prop.name
            assert entry["type"] == prop.type
            assert entry["resourceType"] == prop.resource_type


# =============================================================================
# CustomPropertyRef invariants
# =============================================================================


class TestCustomPropertyRefPBT:
    """Property-based tests for CustomPropertyRef construction."""

    @given(ref_id=st.integers(min_value=1, max_value=10_000_000))
    def test_custom_property_ref_preserves_id(self, ref_id: int) -> None:
        """CustomPropertyRef preserves the integer ID through construction.

        Args:
            ref_id: A positive integer ID.
        """
        ref = CustomPropertyRef(id=ref_id)
        assert ref.id == ref_id

    @given(ref_id=st.integers(min_value=1, max_value=10_000_000))
    def test_custom_property_ref_is_frozen(self, ref_id: int) -> None:
        """CustomPropertyRef instances are immutable (frozen dataclass).

        Args:
            ref_id: A positive integer ID.
        """
        ref = CustomPropertyRef(id=ref_id)
        try:
            ref.id = 999  # type: ignore[misc]
            raise AssertionError("Expected AttributeError for frozen dataclass")
        except AttributeError:
            pass
