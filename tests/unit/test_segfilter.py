"""Unit tests for Filter-to-segfilter conversion.

Tests the ``build_segfilter_entry`` function which converts ``Filter``
objects into the legacy segfilter dict format used by flows step filters.
"""

from __future__ import annotations

import pytest

from mixpanel_headless._internal.segfilter import (
    RESOURCE_TYPE_MAP,
    _convert_date_format,
    build_segfilter_entry,
)
from mixpanel_headless.types import Filter

# =============================================================================
# String Operators
# =============================================================================


class TestSegfilterStringOperators:
    """Conversion of string-typed Filter operators to segfilter format."""

    def test_equals(self) -> None:
        """Filter.equals produces operator '==' with list operand."""
        f = Filter.equals("country", "US")
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "=="
        assert result["filter"]["operand"] == ["US"]

    def test_equals_multi_value(self) -> None:
        """Filter.equals with a list produces operator '==' with list operand."""
        f = Filter.equals("country", ["US", "UK"])
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "=="
        assert result["filter"]["operand"] == ["US", "UK"]

    def test_not_equals(self) -> None:
        """Filter.not_equals produces operator '!=' with list operand."""
        f = Filter.not_equals("country", "US")
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "!="
        assert result["filter"]["operand"] == ["US"]

    def test_contains(self) -> None:
        """Filter.contains produces operator 'in' with string operand."""
        f = Filter.contains("name", "john")
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "in"
        assert result["filter"]["operand"] == "john"

    def test_not_contains(self) -> None:
        """Filter.not_contains produces operator 'not in' with string operand."""
        f = Filter.not_contains("name", "john")
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "not in"
        assert result["filter"]["operand"] == "john"

    def test_is_set(self) -> None:
        """Filter.is_set produces operator 'set' with empty string operand."""
        f = Filter.is_set("email")
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "set"
        assert result["filter"]["operand"] == ""

    def test_is_not_set(self) -> None:
        """Filter.is_not_set produces operator 'not set' with empty string operand."""
        f = Filter.is_not_set("email")
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "not set"
        assert result["filter"]["operand"] == ""


# =============================================================================
# Number Operators
# =============================================================================


class TestSegfilterNumberOperators:
    """Conversion of number-typed Filter operators to segfilter format."""

    def test_greater_than(self) -> None:
        """Filter.greater_than produces operator '>' with stringified operand."""
        f = Filter.greater_than("amount", 50)
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == ">"
        assert result["filter"]["operand"] == "50"

    def test_less_than(self) -> None:
        """Filter.less_than produces operator '<' with stringified operand."""
        f = Filter.less_than("amount", 50)
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "<"
        assert result["filter"]["operand"] == "50"

    def test_operand_stringified_int(self) -> None:
        """Numeric integer values are stringified in segfilter output."""
        f = Filter.greater_than("count", 100)
        result = build_segfilter_entry(f)

        assert result["filter"]["operand"] == "100"
        assert isinstance(result["filter"]["operand"], str)

    def test_operand_stringified_float(self) -> None:
        """Numeric float values are stringified in segfilter output."""
        f = Filter.greater_than("price", 9.99)
        result = build_segfilter_entry(f)

        assert result["filter"]["operand"] == "9.99"
        assert isinstance(result["filter"]["operand"], str)

    def test_between(self) -> None:
        """Filter.between produces operator '><' with stringified list operand."""
        f = Filter.between("amount", 10, 100)
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "><"
        assert result["filter"]["operand"] == ["10", "100"]

    def test_number_is_set(self) -> None:
        """Number is_set uses 'is set' operator with empty string operand.

        Note: Filter.is_set always creates a string-typed filter, so this
        test constructs a number-typed filter directly to verify the number
        operator mapping handles is_set correctly.
        """
        f = Filter(
            _property="score",
            _operator="is set",
            _value=None,
            _property_type="number",
            _resource_type="events",
        )
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "is set"
        assert result["filter"]["operand"] == ""

    def test_number_is_not_set(self) -> None:
        """Number is_not_set uses 'is not set' operator with empty string operand."""
        f = Filter(
            _property="score",
            _operator="is not set",
            _value=None,
            _property_type="number",
            _resource_type="events",
        )
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "is not set"
        assert result["filter"]["operand"] == ""

    def test_equals_number(self) -> None:
        """Number 'equals' maps to '==' with stringified operand."""
        f = Filter(
            _property="count",
            _operator="equals",
            _value=42,
            _property_type="number",
            _resource_type="events",
        )
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "=="
        assert result["filter"]["operand"] == "42"

    def test_is_equal_to_number(self) -> None:
        """Number 'is equal to' maps to '==' with stringified operand.

        Exercises segfilter's backward-compat dispatch for the
        ``"is equal to"`` alias (no Filter classmethod produces this
        value, hence the type: ignore).
        """
        f = Filter(
            _property="count",
            _operator="is equal to",  # type: ignore[arg-type]
            _value=42,
            _property_type="number",
            _resource_type="events",
        )
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "=="
        assert result["filter"]["operand"] == "42"

    def test_not_equals_number(self) -> None:
        """Number 'does not equal' maps to '!=' with stringified operand."""
        f = Filter(
            _property="count",
            _operator="does not equal",
            _value=7,
            _property_type="number",
            _resource_type="events",
        )
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "!="
        assert result["filter"]["operand"] == "7"

    def test_is_at_least(self) -> None:
        """Number 'is at least' maps to '>=' with stringified operand."""
        f = Filter(
            _property="count",
            _operator="is at least",
            _value=5,
            _property_type="number",
            _resource_type="events",
        )
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == ">="
        assert result["filter"]["operand"] == "5"

    def test_is_at_most(self) -> None:
        """Number 'is at most' maps to '<=' with stringified operand."""
        f = Filter(
            _property="count",
            _operator="is at most",
            _value=10,
            _property_type="number",
            _resource_type="events",
        )
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "<="
        assert result["filter"]["operand"] == "10"

    def test_not_between(self) -> None:
        """Number 'not between' maps to '!><' with stringified list operand."""
        f = Filter(
            _property="amount",
            _operator="not between",
            _value=[10, 100],  # type: ignore[arg-type]  # testing runtime int list
            _property_type="number",
            _resource_type="events",
        )
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "!><"
        assert result["filter"]["operand"] == ["10", "100"]


# =============================================================================
# Boolean Operators
# =============================================================================


class TestSegfilterBooleanOperators:
    """Conversion of boolean-typed Filter operators to segfilter format."""

    def test_is_true(self) -> None:
        """Filter.is_true produces operand 'true' with NO 'operator' key."""
        f = Filter.is_true("verified")
        result = build_segfilter_entry(f)

        assert result["filter"]["operand"] == "true"
        assert "operator" not in result["filter"]

    def test_is_false(self) -> None:
        """Filter.is_false produces operand 'false' with NO 'operator' key."""
        f = Filter.is_false("verified")
        result = build_segfilter_entry(f)

        assert result["filter"]["operand"] == "false"
        assert "operator" not in result["filter"]


# =============================================================================
# Datetime Operators
# =============================================================================


class TestSegfilterDatetimeOperators:
    """Conversion of datetime-typed Filter operators to segfilter format."""

    def test_on(self) -> None:
        """Filter.on produces operator '==' with MM/DD/YYYY operand."""
        f = Filter.on("$time", "2026-01-15")
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "=="
        assert result["filter"]["operand"] == "01/15/2026"

    def test_not_on(self) -> None:
        """Filter.not_on produces operator '!=' with MM/DD/YYYY operand."""
        f = Filter.not_on("$time", "2026-01-15")
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "!="
        assert result["filter"]["operand"] == "01/15/2026"

    def test_before(self) -> None:
        """Filter.before produces operator '>' with MM/DD/YYYY operand."""
        f = Filter.before("$time", "2026-01-15")
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == ">"
        assert result["filter"]["operand"] == "01/15/2026"

    def test_since(self) -> None:
        """Filter.since produces operator '<' with MM/DD/YYYY operand."""
        f = Filter.since("$time", "2026-01-15")
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "<"
        assert result["filter"]["operand"] == "01/15/2026"

    def test_in_the_last(self) -> None:
        """Filter.in_the_last produces operator '>' with quantity and unit."""
        f = Filter.in_the_last("$time", 7, "day")
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == ">"
        assert result["filter"]["operand"] == 7
        assert result["filter"]["unit"] == "days"

    def test_not_in_the_last(self) -> None:
        """Filter.not_in_the_last produces operator '>' with quantity and unit."""
        f = Filter.not_in_the_last("$time", 3, "week")
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == ">"
        assert result["filter"]["operand"] == 3
        assert result["filter"]["unit"] == "weeks"

    def test_date_between(self) -> None:
        """Filter.date_between produces operator '><' with MM/DD/YYYY list."""
        f = Filter.date_between("$time", "2026-01-01", "2026-01-31")
        result = build_segfilter_entry(f)

        assert result["filter"]["operator"] == "><"
        assert result["filter"]["operand"] == ["01/01/2026", "01/31/2026"]

    def test_date_format_conversion(self) -> None:
        """YYYY-MM-DD dates are converted to MM/DD/YYYY in output."""
        f = Filter.on("$time", "2026-03-05")
        result = build_segfilter_entry(f)

        assert result["filter"]["operand"] == "03/05/2026"

    def test_no_unit_for_absolute_dates(self) -> None:
        """Absolute date filters do NOT have a 'unit' key in filter dict."""
        f = Filter.on("$time", "2026-01-15")
        result = build_segfilter_entry(f)

        assert "unit" not in result["filter"]

    def test_in_the_last_hour_unit(self) -> None:
        """Relative date with hour unit pluralizes to 'hours'."""
        f = Filter.in_the_last("$time", 24, "hour")
        result = build_segfilter_entry(f)

        assert result["filter"]["unit"] == "hours"

    def test_in_the_last_month_unit(self) -> None:
        """Relative date with month unit pluralizes to 'months'."""
        f = Filter.in_the_last("$time", 3, "month")
        result = build_segfilter_entry(f)

        assert result["filter"]["unit"] == "months"


# =============================================================================
# Resource Type Mapping
# =============================================================================


class TestSegfilterResourceTypeMapping:
    """Mapping of Filter._resource_type to segfilter property.source."""

    def test_events_maps_to_properties(self) -> None:
        """resource_type 'events' maps to property.source 'properties'."""
        f = Filter.equals("country", "US", resource_type="events")
        result = build_segfilter_entry(f)

        assert result["property"]["source"] == "properties"

    def test_people_maps_to_user(self) -> None:
        """resource_type 'people' maps to property.source 'user'."""
        f = Filter.equals("plan", "premium", resource_type="people")
        result = build_segfilter_entry(f)

        assert result["property"]["source"] == "user"

    def test_resource_type_map_constant(self) -> None:
        """RESOURCE_TYPE_MAP contains expected entries."""
        assert RESOURCE_TYPE_MAP["events"] == "properties"
        assert RESOURCE_TYPE_MAP["people"] == "user"


# =============================================================================
# Output Structure
# =============================================================================


class TestSegfilterStructure:
    """Structural validation of segfilter output dicts."""

    def test_top_level_keys(self) -> None:
        """Output dict has 'property', 'type', 'selected_property_type', 'filter'."""
        f = Filter.equals("country", "US")
        result = build_segfilter_entry(f)

        assert "property" in result
        assert "type" in result
        assert "selected_property_type" in result
        assert "filter" in result

    def test_property_structure(self) -> None:
        """property dict contains 'name', 'source', 'type'."""
        f = Filter.equals("country", "US")
        result = build_segfilter_entry(f)

        prop = result["property"]
        assert prop["name"] == "country"
        assert prop["source"] == "properties"
        assert prop["type"] == "string"

    def test_type_consistency(self) -> None:
        """type, selected_property_type, and property.type are all the same."""
        f = Filter.greater_than("amount", 50)
        result = build_segfilter_entry(f)

        assert result["type"] == "number"
        assert result["selected_property_type"] == "number"
        assert result["property"]["type"] == "number"

    def test_boolean_type_consistency(self) -> None:
        """Boolean filters have 'boolean' in all type fields."""
        f = Filter.is_true("verified")
        result = build_segfilter_entry(f)

        assert result["type"] == "boolean"
        assert result["selected_property_type"] == "boolean"
        assert result["property"]["type"] == "boolean"

    def test_datetime_type_consistency(self) -> None:
        """Datetime filters have 'datetime' in all type fields."""
        f = Filter.on("$time", "2026-01-15")
        result = build_segfilter_entry(f)

        assert result["type"] == "datetime"
        assert result["selected_property_type"] == "datetime"
        assert result["property"]["type"] == "datetime"

    def test_property_name_preserved(self) -> None:
        """The property name from the Filter is used as-is."""
        f = Filter.equals("$browser", "Chrome")
        result = build_segfilter_entry(f)

        assert result["property"]["name"] == "$browser"


# =============================================================================
# Helper Functions
# =============================================================================


class TestConvertDateFormat:
    """Tests for _convert_date_format helper."""

    def test_standard_conversion(self) -> None:
        """YYYY-MM-DD converts to MM/DD/YYYY."""
        assert _convert_date_format("2026-01-15") == "01/15/2026"

    def test_leading_zeros_preserved(self) -> None:
        """Month and day leading zeros are preserved."""
        assert _convert_date_format("2026-03-05") == "03/05/2026"

    def test_december(self) -> None:
        """December date converts correctly."""
        assert _convert_date_format("2025-12-31") == "12/31/2025"


# =============================================================================
# Edge Cases
# =============================================================================


class TestSegfilterEdgeCases:
    """Edge-case coverage for segfilter conversion."""

    def test_unknown_operator_raises(self) -> None:
        """Unknown operator for a property type raises ValueError."""
        f = Filter(
            _property="x",
            _operator="magical_unicorn",  # type: ignore[arg-type]
            _value="y",
            _property_type="string",
            _resource_type="events",
        )
        with pytest.raises(ValueError, match="Unknown string operator"):
            build_segfilter_entry(f)

    def test_unknown_number_operator_raises(self) -> None:
        """Unknown number operator raises ValueError."""
        f = Filter(
            _property="x",
            _operator="magical_unicorn",  # type: ignore[arg-type]
            _value=1,
            _property_type="number",
            _resource_type="events",
        )
        with pytest.raises(ValueError, match="Unknown number operator"):
            build_segfilter_entry(f)

    def test_unknown_datetime_operator_raises(self) -> None:
        """Unknown datetime operator raises ValueError."""
        f = Filter(
            _property="x",
            _operator="magical_unicorn",  # type: ignore[arg-type]
            _value="2026-01-01",
            _property_type="datetime",
            _resource_type="events",
        )
        with pytest.raises(ValueError, match="Unknown datetime operator"):
            build_segfilter_entry(f)

    def test_unknown_property_type_raises(self) -> None:
        """Unknown property type raises ValueError."""
        f = Filter(
            _property="x",
            _operator="equals",
            _value="y",
            _property_type="list",
            _resource_type="events",
        )
        with pytest.raises(ValueError, match="Unsupported property type"):
            build_segfilter_entry(f)
