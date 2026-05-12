"""Tests for bookmark builder functions.

Verifies that the extracted builder functions in bookmark_builders.py
produce the correct bookmark JSON structures for time sections,
date ranges, filter sections, group sections, and filter entries.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import patch

import pytest

from mixpanel_headless._internal.bookmark_builders import (
    build_date_range,
    build_filter_entry,
    build_filter_section,
    build_group_section,
    build_time_section,
    patch_custom_property_filters_for_transform,
)
from mixpanel_headless.types import (
    CohortBreakdown,
    CustomPropertyRef,
    Filter,
    GroupBy,
    InlineCustomProperty,
    ListItemGroupMode,
    PropertyInput,
)


class TestBuildTimeSection:
    """Tests for build_time_section() — sections.time array building."""

    def test_absolute_range_from_and_to(self) -> None:
        """Both from_date and to_date produce a 'between' entry with value list."""
        result = build_time_section(
            from_date="2025-01-01",
            to_date="2025-01-31",
            last=30,
            unit="day",
        )
        assert len(result) == 1
        entry = result[0]
        assert entry["dateRangeType"] == "between"
        assert entry["unit"] == "day"
        assert entry["value"] == ["2025-01-01", "2025-01-31"]
        assert "window" not in entry

    def test_from_only_fills_today(self) -> None:
        """Only from_date fills to_date with today's date."""
        with patch("mixpanel_headless._internal.bookmark_builders.date") as mock_date:
            mock_date.today.return_value = date(2025, 6, 15)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = build_time_section(
                from_date="2025-01-01",
                to_date=None,
                last=30,
                unit="week",
            )
        assert len(result) == 1
        entry = result[0]
        assert entry["dateRangeType"] == "between"
        assert entry["unit"] == "week"
        assert entry["value"] == ["2025-01-01", "2025-06-15"]

    def test_relative_range_last_n(self) -> None:
        """Neither from_date nor to_date produces 'in the last' entry."""
        result = build_time_section(
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
        )
        assert len(result) == 1
        entry = result[0]
        assert entry["dateRangeType"] == "in the last"
        assert entry["unit"] == "day"
        assert entry["window"] == {"unit": "day", "value": 30}
        assert "value" not in entry

    def test_relative_range_custom_last(self) -> None:
        """Relative range with custom last value and unit."""
        result = build_time_section(
            from_date=None,
            to_date=None,
            last=7,
            unit="hour",
        )
        entry = result[0]
        assert entry["dateRangeType"] == "in the last"
        assert entry["unit"] == "hour"
        assert entry["window"]["value"] == 7

    def test_returns_single_element_list(self) -> None:
        """Result is always a list with exactly one element."""
        for kwargs in [
            {
                "from_date": "2025-01-01",
                "to_date": "2025-01-31",
                "last": 30,
                "unit": "day",
            },
            {"from_date": "2025-01-01", "to_date": None, "last": 30, "unit": "day"},
            {"from_date": None, "to_date": None, "last": 30, "unit": "day"},
        ]:
            result = build_time_section(**kwargs)  # type: ignore[arg-type]
            assert isinstance(result, list)
            assert len(result) == 1


class TestBuildDateRange:
    """Tests for build_date_range() — flat date range for flows."""

    def test_relative_last_n(self) -> None:
        """Neither date produces 'in the last' type with $now."""
        result = build_date_range(
            from_date=None,
            to_date=None,
            last=30,
        )
        assert result["type"] == "in the last"
        assert result["from_date"] == {"unit": "day", "value": 30}
        assert result["to_date"] == "$now"

    def test_absolute_range(self) -> None:
        """Both dates produce 'between' type with raw date strings."""
        result = build_date_range(
            from_date="2025-01-01",
            to_date="2025-03-31",
            last=30,
        )
        assert result["type"] == "between"
        assert result["from_date"] == "2025-01-01"
        assert result["to_date"] == "2025-03-31"

    def test_relative_custom_last(self) -> None:
        """Custom last value in relative range."""
        result = build_date_range(
            from_date=None,
            to_date=None,
            last=7,
        )
        assert result["from_date"]["value"] == 7
        assert result["from_date"]["unit"] == "day"


class TestBuildFilterSection:
    """Tests for build_filter_section() — sections.filter array building."""

    def test_none_returns_empty(self) -> None:
        """None where clause returns empty list."""
        result = build_filter_section(None)
        assert result == []

    def test_single_filter(self) -> None:
        """Single Filter produces one-element list."""
        f = Filter.equals("country", "US")
        result = build_filter_section(f)
        assert len(result) == 1
        assert result[0]["value"] == "country"
        assert result[0]["filterOperator"] == "equals"

    def test_multiple_filters(self) -> None:
        """List of Filters produces matching-length list."""
        filters = [
            Filter.equals("country", "US"),
            Filter.greater_than("age", 18),
        ]
        result = build_filter_section(filters)
        assert len(result) == 2
        assert result[0]["value"] == "country"
        assert result[0]["filterOperator"] == "equals"
        assert result[1]["value"] == "age"
        assert result[1]["filterOperator"] == "is greater than"

    def test_single_filter_entry_structure(self) -> None:
        """Filter entry has all required keys."""
        f = Filter.equals("country", "US")
        result = build_filter_section(f)
        entry = result[0]
        assert "resourceType" in entry
        assert "filterType" in entry
        assert "defaultType" in entry
        assert "value" in entry
        assert "filterValue" in entry
        assert "filterOperator" in entry


class TestBuildGroupSection:
    """Tests for build_group_section() — sections.group array building."""

    def test_none_returns_empty(self) -> None:
        """None group_by returns empty list."""
        result = build_group_section(None)
        assert result == []

    def test_string_group_by(self) -> None:
        """String group_by produces standard group entry."""
        result = build_group_section("country")
        assert len(result) == 1
        entry = result[0]
        assert entry["value"] == "country"
        assert entry["propertyName"] == "country"
        assert entry["resourceType"] == "events"
        assert entry["propertyType"] == "string"
        assert entry["propertyDefaultType"] == "string"

    def test_groupby_object(self) -> None:
        """GroupBy object produces entry with correct property type."""
        g = GroupBy("revenue", property_type="number")
        result = build_group_section(g)
        assert len(result) == 1
        entry = result[0]
        assert entry["value"] == "revenue"
        assert entry["propertyName"] == "revenue"
        assert entry["propertyType"] == "number"
        assert entry["propertyDefaultType"] == "number"

    def test_groupby_with_buckets(self) -> None:
        """GroupBy with bucket_size produces customBucket entry."""
        g = GroupBy(
            "amount",
            property_type="number",
            bucket_size=10,
            bucket_min=0,
            bucket_max=100,
        )
        result = build_group_section(g)
        entry = result[0]
        assert "customBucket" in entry
        assert entry["customBucket"]["bucketSize"] == 10
        assert entry["customBucket"]["min"] == 0
        assert entry["customBucket"]["max"] == 100

    def test_groupby_bucket_size_only(self) -> None:
        """GroupBy with bucket_size but no min/max omits min/max keys."""
        g = GroupBy("amount", property_type="number", bucket_size=10)
        result = build_group_section(g)
        entry = result[0]
        assert "customBucket" in entry
        assert entry["customBucket"]["bucketSize"] == 10
        assert "min" not in entry["customBucket"]
        assert "max" not in entry["customBucket"]

    def test_multiple_groups_mixed(self) -> None:
        """List of mixed strings and GroupBy produces correct entries."""
        groups: list[str | GroupBy | CohortBreakdown] = [
            "country",
            GroupBy("revenue", property_type="number"),
        ]
        result = build_group_section(groups)
        assert len(result) == 2
        assert result[0]["value"] == "country"
        assert result[0]["propertyType"] == "string"
        assert result[1]["value"] == "revenue"
        assert result[1]["propertyType"] == "number"

    def test_invalid_type_raises_typeerror(self) -> None:
        """Invalid group_by element type raises TypeError."""
        with pytest.raises(
            TypeError,
            match="group_by elements must be str, GroupBy, CohortBreakdown, or FrequencyBreakdown",
        ):
            build_group_section(123)  # type: ignore[arg-type]

    def test_invalid_element_in_list_raises_typeerror(self) -> None:
        """Invalid element inside list raises TypeError."""
        with pytest.raises(
            TypeError,
            match="group_by elements must be str, GroupBy, CohortBreakdown, or FrequencyBreakdown",
        ):
            build_group_section(["country", 42])  # type: ignore[list-item]


class TestBuildFilterEntry:
    """Tests for build_filter_entry() — individual filter dict conversion."""

    def test_string_filter(self) -> None:
        """String equals filter produces correct entry."""
        f = Filter.equals("country", "US")
        entry = build_filter_entry(f)
        assert entry["resourceType"] == "events"
        assert entry["filterType"] == "string"
        assert entry["defaultType"] == "string"
        assert entry["value"] == "country"
        assert entry["filterValue"] == ["US"]
        assert entry["filterOperator"] == "equals"
        assert "filterDateUnit" not in entry

    def test_number_filter(self) -> None:
        """Numeric greater-than filter produces correct entry."""
        f = Filter.greater_than("age", 18)
        entry = build_filter_entry(f)
        assert entry["filterType"] == "number"
        assert entry["defaultType"] == "number"
        assert entry["value"] == "age"
        assert entry["filterValue"] == 18
        assert entry["filterOperator"] == "is greater than"
        assert "filterDateUnit" not in entry

    def test_boolean_filter(self) -> None:
        """Boolean true filter produces correct entry."""
        f = Filter.is_true("verified")
        entry = build_filter_entry(f)
        assert entry["filterType"] == "boolean"
        assert entry["defaultType"] == "boolean"
        assert entry["value"] == "verified"
        assert entry["filterValue"] is None
        assert entry["filterOperator"] == "true"
        assert "filterDateUnit" not in entry

    def test_datetime_filter_with_date_unit(self) -> None:
        """Relative date filter includes filterDateUnit."""
        f = Filter.in_the_last("$time", 7, "day")
        entry = build_filter_entry(f)
        assert entry["filterType"] == "datetime"
        assert entry["defaultType"] == "datetime"
        assert entry["value"] == "$time"
        assert entry["filterValue"] == 7
        assert entry["filterOperator"] == "was in the"
        assert entry["filterDateUnit"] == "day"

    def test_datetime_filter_without_date_unit(self) -> None:
        """Absolute date filter does not include filterDateUnit."""
        f = Filter.on("created", "2025-01-15")
        entry = build_filter_entry(f)
        assert entry["filterType"] == "datetime"
        assert entry["filterOperator"] == "was on"
        assert "filterDateUnit" not in entry

    def test_people_resource_type(self) -> None:
        """Filter with resource_type='people' sets resourceType correctly."""
        f = Filter.equals("plan", "premium", resource_type="people")
        entry = build_filter_entry(f)
        assert entry["resourceType"] == "people"

    def test_custom_property_ref_omits_value(self) -> None:
        """CustomPropertyRef filter does not include 'value' by default."""
        ref = CustomPropertyRef(90553)
        f = Filter.is_set(ref)
        entry = build_filter_entry(f)
        assert entry["customPropertyId"] == 90553
        assert "value" not in entry
        assert entry["dataset"] == "$mixpanel"

    def test_inline_custom_property_omits_value(self) -> None:
        """InlineCustomProperty filter does not include 'value' by default."""
        icp = InlineCustomProperty(
            formula="A",
            inputs={"A": PropertyInput(name="price", type="number")},
            property_type="number",
        )
        f = Filter.greater_than(icp, 1000)
        entry = build_filter_entry(f)
        assert "customProperty" in entry
        assert "value" not in entry
        assert entry["dataset"] == "$mixpanel"


class TestNewFilterOperatorsInBuilder:
    """T030: Tests for new filter operators in build_filter_entry() output."""

    def test_not_between_filter_operator(self) -> None:
        """not_between filter produces 'not between' filterOperator."""
        f = Filter.not_between("age", 18, 65)
        entry = build_filter_entry(f)
        assert entry["filterOperator"] == "not between"
        assert entry["filterType"] == "number"
        assert entry["filterValue"] == [18, 65]

    def test_starts_with_filter_operator(self) -> None:
        """starts_with filter produces 'starts with' filterOperator."""
        f = Filter.starts_with("url", "https://")
        entry = build_filter_entry(f)
        assert entry["filterOperator"] == "starts with"
        assert entry["filterType"] == "string"
        assert entry["filterValue"] == "https://"

    def test_ends_with_filter_operator(self) -> None:
        """ends_with filter produces 'ends with' filterOperator."""
        f = Filter.ends_with("email", "@example.com")
        entry = build_filter_entry(f)
        assert entry["filterOperator"] == "ends with"
        assert entry["filterType"] == "string"
        assert entry["filterValue"] == "@example.com"

    def test_date_not_between_filter_operator(self) -> None:
        """date_not_between filter produces 'was not between' filterOperator."""
        f = Filter.date_not_between("created", "2024-01-01", "2024-06-30")
        entry = build_filter_entry(f)
        assert entry["filterOperator"] == "was not between"
        assert entry["filterType"] == "datetime"
        assert entry["filterValue"] == ["2024-01-01", "2024-06-30"]
        assert "filterDateUnit" not in entry

    def test_in_the_next_filter_operator(self) -> None:
        """in_the_next filter produces 'was in the next' filterOperator."""
        f = Filter.in_the_next("expires", 7, "day")
        entry = build_filter_entry(f)
        assert entry["filterOperator"] == "was in the next"
        assert entry["filterType"] == "datetime"
        assert entry["filterValue"] == 7
        assert entry["filterDateUnit"] == "day"

    def test_at_least_filter_operator(self) -> None:
        """at_least filter produces 'is at least' filterOperator."""
        f = Filter.at_least("score", 80)
        entry = build_filter_entry(f)
        assert entry["filterOperator"] == "is at least"
        assert entry["filterType"] == "number"
        assert entry["filterValue"] == 80

    def test_at_most_filter_operator(self) -> None:
        """at_most filter produces 'is at most' filterOperator."""
        f = Filter.at_most("errors", 5)
        entry = build_filter_entry(f)
        assert entry["filterOperator"] == "is at most"
        assert entry["filterType"] == "number"
        assert entry["filterValue"] == 5


class TestPatchCustomPropertyFiltersForTransform:
    """Tests for the server-compat sentinel injection.

    The server's ``transform_insights_filters_to_funnels()`` crashes
    with ``KeyError`` on custom property filters that lack ``"value"``.
    ``patch_custom_property_filters_for_transform()`` adds
    ``"value": None`` so the transform survives.
    """

    def test_adds_value_to_custom_property_ref(self) -> None:
        """Adds 'value': None for customPropertyId entries."""
        entries = [{"customPropertyId": 90553, "filterOperator": "is set"}]
        result = patch_custom_property_filters_for_transform(entries)
        assert result[0]["value"] is None

    def test_adds_value_to_inline_custom_property(self) -> None:
        """Adds 'value': None for customProperty entries."""
        entries = [{"customProperty": {"formula": "A"}, "filterOperator": ">"}]
        result = patch_custom_property_filters_for_transform(entries)
        assert result[0]["value"] is None

    def test_does_not_overwrite_existing_value(self) -> None:
        """Does not touch entries that already have 'value'."""
        entries = [{"value": "country", "filterOperator": "equals"}]
        patch_custom_property_filters_for_transform(entries)
        assert entries[0]["value"] == "country"

    def test_leaves_regular_filters_alone(self) -> None:
        """Regular property filters (with 'value') are untouched."""
        entries: list[dict[str, Any]] = [
            {"value": "country", "filterOperator": "equals"},
            {"customPropertyId": 42, "filterOperator": "is set"},
        ]
        patch_custom_property_filters_for_transform(entries)
        assert entries[0]["value"] == "country"
        assert entries[1]["value"] is None

    def test_empty_list(self) -> None:
        """Empty list returns empty list."""
        assert patch_custom_property_filters_for_transform([]) == []


# =============================================================================
# T015: build_time_comparison() builder tests
# =============================================================================


class TestBuildTimeComparison:
    """Tests for build_time_comparison() — timeComparison dict building."""

    def test_relative_produces_correct_dict(self) -> None:
        """Relative time comparison produces {"type": "relative", "value": unit}."""
        from mixpanel_headless._internal.bookmark_builders import build_time_comparison
        from mixpanel_headless.types import TimeComparison

        tc = TimeComparison.relative("month")
        result = build_time_comparison(tc)
        assert result == {"type": "relative", "value": "month"}

    def test_absolute_start_produces_correct_dict(self) -> None:
        """Absolute-start produces {"type": "absolute-start", "value": date}."""
        from mixpanel_headless._internal.bookmark_builders import build_time_comparison
        from mixpanel_headless.types import TimeComparison

        tc = TimeComparison.absolute_start("2026-01-01")
        result = build_time_comparison(tc)
        assert result == {"type": "absolute-start", "value": "2026-01-01"}

    def test_absolute_end_produces_correct_dict(self) -> None:
        """Absolute-end produces {"type": "absolute-end", "value": date}."""
        from mixpanel_headless._internal.bookmark_builders import build_time_comparison
        from mixpanel_headless.types import TimeComparison

        tc = TimeComparison.absolute_end("2026-12-31")
        result = build_time_comparison(tc)
        assert result == {"type": "absolute-end", "value": "2026-12-31"}

    def test_relative_day_unit(self) -> None:
        """Relative with unit='day' produces correct value."""
        from mixpanel_headless._internal.bookmark_builders import build_time_comparison
        from mixpanel_headless.types import TimeComparison

        tc = TimeComparison.relative("day")
        result = build_time_comparison(tc)
        assert result["value"] == "day"

    def test_relative_year_unit(self) -> None:
        """Relative with unit='year' produces correct value."""
        from mixpanel_headless._internal.bookmark_builders import build_time_comparison
        from mixpanel_headless.types import TimeComparison

        tc = TimeComparison.relative("year")
        result = build_time_comparison(tc)
        assert result["value"] == "year"


# =============================================================================
# T022: build_frequency_group_entry() builder tests (US4)
# =============================================================================


class TestBuildFrequencyGroupEntry:
    """Tests for build_frequency_group_entry() — frequency breakdown dict.

    Expected API format (from audit report section 2.2.1):

    .. code-block:: json

        {
          "dataset": "$mixpanel",
          "behavior": {
            "aggregationOperator": "total",
            "event": {"label": "Purchase", "value": "Purchase"},
            "behaviorType": "$frequency",
            "filters": [],
            "filtersOperator": "and",
            "dateRange": null
          },
          "value": "Purchase Frequency",
          "resourceType": "people",
          "propertyType": "number",
          "dataGroupId": null,
          "customBucket": {"bucketSize": 1, "min": 0, "max": 10, "disabled": false}
        }
    """

    def test_basic_structure(self) -> None:
        """FrequencyBreakdown produces correct group entry structure."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_group_entry,
        )
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown("Purchase")
        result = build_frequency_group_entry(fb)
        assert result["dataset"] == "$mixpanel"
        assert result["resourceType"] == "people"
        assert result["propertyType"] == "number"
        assert result["dataGroupId"] is None

    def test_behavior_dict_structure(self) -> None:
        """Behavior dict contains behaviorType, event object, and defaults."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_group_entry,
        )
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown("Purchase")
        result = build_frequency_group_entry(fb)
        behavior = result["behavior"]
        assert behavior["behaviorType"] == "$frequency"
        assert behavior["aggregationOperator"] == "total"
        assert behavior["event"] == {"label": "Purchase", "value": "Purchase"}
        assert behavior["filters"] == []
        assert behavior["filtersOperator"] == "and"
        assert behavior["dateRange"] is None

    def test_behaviortype_not_at_top_level(self) -> None:
        """behaviorType must be inside behavior, not at the top level."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_group_entry,
        )
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown("Purchase")
        result = build_frequency_group_entry(fb)
        assert "behaviorType" not in result
        assert result["behavior"]["behaviorType"] == "$frequency"

    def test_custom_bucket_default_values(self) -> None:
        """Default bucket config uses camelCase in customBucket object."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_group_entry,
        )
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown("Purchase")
        result = build_frequency_group_entry(fb)
        bucket = result["customBucket"]
        assert bucket["bucketSize"] == 1
        assert bucket["min"] == 0
        assert bucket["max"] == 10
        assert bucket["disabled"] is False

    def test_custom_bucket_values(self) -> None:
        """Custom bucket params are reflected in customBucket object."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_group_entry,
        )
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown("Purchase", bucket_size=5, bucket_min=0, bucket_max=50)
        result = build_frequency_group_entry(fb)
        bucket = result["customBucket"]
        assert bucket["bucketSize"] == 5
        assert bucket["min"] == 0
        assert bucket["max"] == 50
        assert bucket["disabled"] is False

    def test_value_label_from_event_name(self) -> None:
        """Value field defaults to '<event> Frequency' when no label set."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_group_entry,
        )
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown("Purchase")
        result = build_frequency_group_entry(fb)
        assert result["value"] == "Purchase Frequency"

    def test_label_overrides_value(self) -> None:
        """Custom label overrides the default value field."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_group_entry,
        )
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown("Purchase", label="Buy Count")
        result = build_frequency_group_entry(fb)
        assert result["value"] == "Buy Count"

    def test_no_top_level_label_key(self) -> None:
        """Label is expressed via value field, not a separate label key."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_group_entry,
        )
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown("Purchase", label="Buy Count")
        result = build_frequency_group_entry(fb)
        assert "label" not in result

    def test_no_snake_case_bucket_keys_in_behavior(self) -> None:
        """Old snake_case bucket keys must not appear in behavior dict."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_group_entry,
        )
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown("Purchase", bucket_size=5, bucket_min=0, bucket_max=50)
        result = build_frequency_group_entry(fb)
        behavior = result["behavior"]
        assert "bucket_size" not in behavior
        assert "bucket_min" not in behavior
        assert "bucket_max" not in behavior

    def test_event_object_uses_event_name_not_display_label(self) -> None:
        """Event object label/value must use raw event name, not display label."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_group_entry,
        )
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown("Purchase", label="Buy Count")
        result = build_frequency_group_entry(fb)
        assert result["behavior"]["event"] == {
            "label": "Purchase",
            "value": "Purchase",
        }
        assert result["value"] == "Buy Count"

    def test_data_group_id_default_none(self) -> None:
        """dataGroupId defaults to None when not specified."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_group_entry,
        )
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown("Purchase")
        result = build_frequency_group_entry(fb)
        assert result["dataGroupId"] is None

    def test_data_group_id_threaded(self) -> None:
        """dataGroupId is threaded when passed explicitly."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_group_entry,
        )
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown("Purchase")
        result = build_frequency_group_entry(fb, data_group_id=5)
        assert result["dataGroupId"] == 5


# =============================================================================
# T022: build_frequency_filter_entry() builder tests (US4)
# =============================================================================


class TestBuildFrequencyFilterEntry:
    """Tests for build_frequency_filter_entry() — frequency filter dict."""

    def test_basic_structure(self) -> None:
        """FrequencyFilter produces correct filter entry structure."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_filter_entry,
        )
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter("Login", value=5)
        result = build_frequency_filter_entry(ff)
        assert result["resourceType"] == "people"
        assert result["behaviorType"] == "$frequency"
        assert "customProperty" in result
        behavior = result["customProperty"]["behavior"]
        assert behavior["event"] == "Login"
        assert behavior["aggregation"] == "total"
        assert behavior["filterOperator"] == "is at least"
        assert behavior["filterValue"] == 5

    def test_custom_operator(self) -> None:
        """Custom operator is reflected in output."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_filter_entry,
        )
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter("Login", operator="is greater than", value=10)
        result = build_frequency_filter_entry(ff)
        behavior = result["customProperty"]["behavior"]
        assert behavior["filterOperator"] == "is greater than"
        assert behavior["filterValue"] == 10

    def test_with_date_range(self) -> None:
        """Date range is included when set."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_filter_entry,
        )
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter(
            "Login", value=5, date_range_value=30, date_range_unit="day"
        )
        result = build_frequency_filter_entry(ff)
        behavior = result["customProperty"]["behavior"]
        assert "dateRange" in behavior
        assert behavior["dateRange"]["value"] == 30
        assert behavior["dateRange"]["unit"] == "day"

    def test_without_date_range(self) -> None:
        """Date range is omitted when not set."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_filter_entry,
        )
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter("Login", value=5)
        result = build_frequency_filter_entry(ff)
        behavior = result["customProperty"]["behavior"]
        assert "dateRange" not in behavior

    def test_with_event_filters(self) -> None:
        """Event filters are included when set."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_filter_entry,
        )
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter(
            "Purchase",
            value=1,
            event_filters=[Filter.equals("country", "US")],
        )
        result = build_frequency_filter_entry(ff)
        behavior = result["customProperty"]["behavior"]
        assert "eventFilters" in behavior
        assert len(behavior["eventFilters"]) == 1
        assert behavior["eventFilters"][0]["value"] == "country"
        assert behavior["eventFilters"][0]["filterOperator"] == "equals"

    def test_without_event_filters(self) -> None:
        """Event filters key is omitted when not set."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_filter_entry,
        )
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter("Login", value=5)
        result = build_frequency_filter_entry(ff)
        behavior = result["customProperty"]["behavior"]
        assert "eventFilters" not in behavior

    def test_label_included(self) -> None:
        """Label is included in output when set."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_filter_entry,
        )
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter("Login", value=5, label="Active Users")
        result = build_frequency_filter_entry(ff)
        assert result["label"] == "Active Users"

    def test_label_omitted_when_none(self) -> None:
        """Label key is omitted when label is None."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_filter_entry,
        )
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter("Login", value=5)
        result = build_frequency_filter_entry(ff)
        assert "label" not in result

    def test_multiple_event_filters(self) -> None:
        """Multiple event filters each produce a filter entry."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_filter_entry,
        )
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter(
            "Purchase",
            value=3,
            event_filters=[
                Filter.equals("country", "US"),
                Filter.greater_than("amount", 10),
            ],
        )
        result = build_frequency_filter_entry(ff)
        behavior = result["customProperty"]["behavior"]
        assert len(behavior["eventFilters"]) == 2
        assert behavior["eventFilters"][0]["filterOperator"] == "equals"
        assert behavior["eventFilters"][1]["filterOperator"] == "is greater than"


# =============================================================================
# T022: build_group_section handles FrequencyBreakdown (US4)
# =============================================================================


class TestBuildGroupSectionFrequency:
    """Tests for build_group_section() handling FrequencyBreakdown."""

    def test_frequency_breakdown_in_group_section(self) -> None:
        """FrequencyBreakdown produces frequency group entry in section."""
        from mixpanel_headless.types import FrequencyBreakdown

        result = build_group_section(FrequencyBreakdown("Purchase"))
        assert len(result) == 1
        assert result[0]["resourceType"] == "people"
        assert result[0]["behavior"]["behaviorType"] == "$frequency"

    def test_mixed_groupby_and_frequency(self) -> None:
        """List with GroupBy and FrequencyBreakdown produces correct entries."""
        from mixpanel_headless.types import FrequencyBreakdown

        result = build_group_section(["country", FrequencyBreakdown("Purchase")])
        assert len(result) == 2
        assert result[0]["value"] == "country"
        assert result[0]["propertyType"] == "string"
        assert result[1]["resourceType"] == "people"
        assert result[1]["behavior"]["behaviorType"] == "$frequency"

    def test_data_group_id_threaded_to_frequency(self) -> None:
        """data_group_id is threaded into frequency group entries."""
        from mixpanel_headless.types import FrequencyBreakdown

        result = build_group_section(FrequencyBreakdown("Purchase"), data_group_id=5)
        assert result[0]["dataGroupId"] == 5


# =============================================================================
# T022: build_filter_section handles FrequencyFilter (US4)
# =============================================================================


class TestBuildFilterSectionFrequency:
    """Tests for build_filter_section() handling FrequencyFilter."""

    def test_frequency_filter_in_filter_section(self) -> None:
        """FrequencyFilter produces frequency filter entry in section."""
        from mixpanel_headless.types import FrequencyFilter

        result = build_filter_section(FrequencyFilter("Login", value=5))
        assert len(result) == 1
        assert result[0]["resourceType"] == "people"
        assert result[0]["behaviorType"] == "$frequency"

    def test_mixed_filter_and_frequency(self) -> None:
        """List with Filter and FrequencyFilter produces correct entries."""
        from mixpanel_headless.types import FrequencyFilter

        result = build_filter_section(
            [Filter.equals("country", "US"), FrequencyFilter("Login", value=5)]
        )
        assert len(result) == 2
        assert result[0]["value"] == "country"
        assert result[0]["filterOperator"] == "equals"
        assert result[1]["resourceType"] == "people"
        assert result[1]["behaviorType"] == "$frequency"


# =============================================================================
# T033: data_group_id threading through builders
# =============================================================================


class TestBuildGroupSectionDataGroupId:
    """Tests for data_group_id threading through build_group_section (T033)."""

    def test_custom_property_ref_group_with_data_group_id(self) -> None:
        """GroupBy with CustomPropertyRef and data_group_id=5 produces dataGroupId: 5."""
        ref = CustomPropertyRef(id=42)
        gb = GroupBy(property=ref)
        result = build_group_section(gb, data_group_id=5)
        assert len(result) == 1
        assert result[0]["dataGroupId"] == 5

    def test_custom_property_ref_group_without_data_group_id(self) -> None:
        """GroupBy with CustomPropertyRef without data_group_id produces dataGroupId: None."""
        ref = CustomPropertyRef(id=42)
        gb = GroupBy(property=ref)
        result = build_group_section(gb)
        assert len(result) == 1
        assert result[0]["dataGroupId"] is None

    def test_inline_custom_property_group_with_data_group_id(self) -> None:
        """GroupBy with InlineCustomProperty and data_group_id=3 produces dataGroupId: 3."""
        prop = InlineCustomProperty(
            formula="A",
            inputs={"A": PropertyInput(name="price", resource_type="event")},
        )
        gb = GroupBy(property=prop, property_type="number")
        result = build_group_section(gb, data_group_id=3)
        assert len(result) == 1
        assert result[0]["dataGroupId"] == 3

    def test_cohort_breakdown_group_with_data_group_id(self) -> None:
        """CohortBreakdown with data_group_id=7 threads to both cohort entry and group entry."""
        cb = CohortBreakdown(123, "Power Users")
        result = build_group_section(cb, data_group_id=7)
        assert len(result) == 1
        # Top-level group entry
        assert result[0]["dataGroupId"] == 7
        # Cohort entries inside
        for cohort in result[0]["cohorts"]:
            assert cohort["data_group_id"] == 7

    def test_string_group_unaffected_by_data_group_id(self) -> None:
        """String group_by does not have dataGroupId field (simple property entries)."""
        result = build_group_section("country", data_group_id=5)
        assert len(result) == 1
        # String entries use a simpler format without dataGroupId
        assert "dataGroupId" not in result[0]

    def test_none_group_returns_empty(self) -> None:
        """None group_by returns empty list regardless of data_group_id."""
        result = build_group_section(None, data_group_id=5)
        assert result == []


# =========================================================================
# T039: build_flow_property_filter — flow property filter builder (US8)
# =========================================================================


class TestBuildFlowPropertyFilter:
    """Tests for build_flow_property_filter() — filter_by_event structure."""

    def test_single_filter_structure(self) -> None:
        """Single Filter produces correct filter_by_event structure."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_flow_property_filter,
        )

        result = build_flow_property_filter([Filter.equals("country", "US")])
        assert result["operator"] == "and"
        assert len(result["children"]) == 1
        child = result["children"][0]
        assert child["filterOperator"] == "equals"
        assert child["filterType"] == "string"
        assert child["propertyName"] == "country"
        assert child["filterValue"] == ["US"]
        assert child["resourceType"] == "events"

    def test_multiple_filters_produce_children(self) -> None:
        """Multiple Filters produce a children array with one entry per filter."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_flow_property_filter,
        )

        result = build_flow_property_filter(
            [
                Filter.equals("country", "US"),
                Filter.greater_than("age", 18),
            ]
        )
        assert result["operator"] == "and"
        assert len(result["children"]) == 2
        assert result["children"][0]["propertyName"] == "country"
        assert result["children"][1]["propertyName"] == "age"

    def test_filter_entry_uses_build_filter_entry(self) -> None:
        """Each child uses build_filter_entry structure (resourceType, filterType, etc.)."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_flow_property_filter,
        )

        result = build_flow_property_filter([Filter.contains("name", "test")])
        child = result["children"][0]
        assert "resourceType" in child
        assert "filterType" in child
        assert "filterOperator" in child
        assert "filterValue" in child
        assert "propertyName" in child

    def test_custom_property_ref_raises_type_error(self) -> None:
        """build_flow_property_filter rejects CustomPropertyRef properties."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_flow_property_filter,
        )
        from mixpanel_headless.types import CustomPropertyRef

        f = Filter(
            _property=CustomPropertyRef(id=123),
            _operator="equals",
            _value=["high"],
            _property_type="string",
            _resource_type="events",
        )
        with pytest.raises(TypeError, match="custom property refs"):
            build_flow_property_filter([f])

    def test_empty_list_raises_value_error(self) -> None:
        """build_flow_property_filter rejects empty filter list."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_flow_property_filter,
        )

        with pytest.raises(ValueError, match="requires at least one filter"):
            build_flow_property_filter([])


class TestFilterListContains:
    """Tests for Filter.list_contains — list-of-object subproperty filters."""

    def test_kwargs_shorthand_produces_two_inner_equals(self) -> None:
        """Keyword arguments expand to one equals sub-filter per pair."""
        f = Filter.list_contains("cart", Brand="nike", Category="hats")
        entry = build_filter_entry(f)
        assert entry["filterType"] == "object"
        assert entry["filterJoinType"] == "list"
        assert len(entry["listItemFilters"]) == 2
        sub_values = {
            (s["value"], tuple(s["filterValue"])) for s in entry["listItemFilters"]
        }
        assert sub_values == {("Brand", ("nike",)), ("Category", ("hats",))}
        for sub in entry["listItemFilters"]:
            assert sub["filterOperator"] == "equals"
            assert sub["filterType"] == "string"

    def test_positional_filter_instances_preserve_operators(self) -> None:
        """Explicit Filter args support any operator the wire format allows."""
        f = Filter.list_contains(
            "cart",
            Filter.equals("Brand", "nike"),
            Filter.greater_than("Price", 50),
        )
        entry = build_filter_entry(f)
        assert len(entry["listItemFilters"]) == 2
        ops = {s["filterOperator"] for s in entry["listItemFilters"]}
        assert ops == {"equals", "is greater than"}

    def test_default_quantifier_is_any(self) -> None:
        """Quantifier defaults to 'any' (≥1 list item must match)."""
        f = Filter.list_contains("cart", Brand="nike")
        entry = build_filter_entry(f)
        assert entry["listQuantifier"] == "any"

    def test_quantifier_all(self) -> None:
        """quantifier='all' propagates to listQuantifier."""
        f = Filter.list_contains("cart", Brand="nike", quantifier="all")
        entry = build_filter_entry(f)
        assert entry["listQuantifier"] == "all"

    def test_inner_items_have_dataset(self) -> None:
        """The wire format requires dataset='$mixpanel' on each inner filter."""
        f = Filter.list_contains("cart", Brand="nike", Category="hats")
        entry = build_filter_entry(f)
        for sub in entry["listItemFilters"]:
            assert sub["dataset"] == "$mixpanel"

    def test_outer_constants(self) -> None:
        """Outer dict carries fixed wire-format constants for list-contains filters."""
        f = Filter.list_contains("cart", Brand="nike")
        entry = build_filter_entry(f)
        assert entry["dataset"] == "$mixpanel"
        assert entry["value"] == "cart"
        assert entry["resourceType"] == "events"
        assert entry["filterType"] == "object"
        assert entry["defaultType"] == "object"
        assert entry["filterJoinType"] == "list"
        assert entry["filterOperator"] == "true"
        assert entry["filterValue"] is True

    def test_resource_type_propagates(self) -> None:
        """resource_type='people' overrides the default 'events'."""
        f = Filter.list_contains("attrs", role="admin", resource_type="people")
        entry = build_filter_entry(f)
        assert entry["resourceType"] == "people"

    def test_zero_conditions_raises(self) -> None:
        """No sub-conditions raises ValueError."""
        with pytest.raises(ValueError, match="at least one"):
            Filter.list_contains("cart")

    def test_mixing_kwargs_and_positional_raises(self) -> None:
        """Mixing positional Filter args and keyword equals raises ValueError."""
        with pytest.raises(ValueError, match="either"):
            Filter.list_contains(
                "cart", Filter.equals("Brand", "nike"), Category="hats"
            )

    def test_nested_list_contains_raises(self) -> None:
        """A list_contains filter inside another list_contains raises ValueError."""
        inner = Filter.list_contains("inner", X="y")
        with pytest.raises(ValueError, match="nested"):
            Filter.list_contains("cart", inner)

    def test_via_build_filter_section(self) -> None:
        """End-to-end through dispatch in build_filter_section."""
        f = Filter.list_contains("cart", Brand="nike")
        section = build_filter_section(f)
        assert len(section) == 1
        assert section[0]["filterType"] == "object"
        assert len(section[0]["listItemFilters"]) == 1

    def test_kwargs_inherit_outer_resource_type_people(self) -> None:
        """Keyword shorthand propagates resource_type='people' to inner equals filters.

        Regression: previously the kwargs path called ``cls.equals(k, v)``
        with no resource_type override, hardcoding inner filters to
        ``"events"`` even when the outer filter targeted ``"people"``.
        """
        f = Filter.list_contains("addresses", resource_type="people", City="Brooklyn")
        assert f._resource_type == "people"
        assert f._list_item_filters is not None
        assert all(sub._resource_type == "people" for sub in f._list_item_filters)
        section = build_filter_section(f)
        assert section[0]["resourceType"] == "people"
        for sub_entry in section[0]["listItemFilters"]:
            assert sub_entry["resourceType"] == "people"

    def test_post_init_rejects_list_contains_without_filters(self) -> None:
        """Direct construction with _operator='list_contains' but no filters raises."""
        with pytest.raises(ValueError, match="_list_item_filters"):
            Filter(
                _property="cart",
                _operator="list_contains",
                _value=None,
                _property_type="object",
                _resource_type="events",
                _list_item_filters=None,
                _list_item_quantifier="any",
            )

    def test_post_init_rejects_list_contains_without_quantifier(self) -> None:
        """Direct construction with _operator='list_contains' but no quantifier raises."""
        with pytest.raises(ValueError, match="_list_item_quantifier"):
            Filter(
                _property="cart",
                _operator="list_contains",
                _value=None,
                _property_type="object",
                _resource_type="events",
                _list_item_filters=(Filter.equals("Brand", "nike"),),
                _list_item_quantifier=None,
            )

    def test_quantifier_runtime_rejects_invalid(self) -> None:
        """Filter.list_contains rejects quantifier values outside any/all."""
        with pytest.raises(ValueError, match="quantifier"):
            Filter.list_contains("cart", quantifier="nope", X="y")  # type: ignore[arg-type]

    def test_kwargs_value_must_be_str_or_list(self) -> None:
        """Filter.list_contains rejects non-str/list kwarg values at construction."""
        with pytest.raises(TypeError, match="Price"):
            Filter.list_contains("cart", Price=99.99)  # type: ignore[arg-type]

    def test_kwargs_empty_key_rejected(self) -> None:
        """Filter.list_contains rejects empty kwarg keys.

        Uses a dynamically-typed dict + ``# type: ignore`` because mypy
        sees the empty key as a potential overlap with the
        ``quantifier``/``resource_type`` kwargs and refuses on str type
        grounds — irrelevant here since we're testing the runtime guard.
        """
        bad_kwargs: dict[str, str | list[str]] = {"": "value"}
        with pytest.raises(ValueError, match="non-empty"):
            Filter.list_contains("cart", **bad_kwargs)  # type: ignore[arg-type]


class TestGroupByListItem:
    """Tests for GroupBy.list_item — break down by a list-item subproperty."""

    def test_basic_string_sub_emits_listItemGroup(self) -> None:
        """list_item('cart','Brand') produces the listItemGroup wire shape."""
        g = GroupBy.list_item("cart", "Brand")
        section = build_group_section(g)
        assert len(section) == 1
        entry = section[0]
        assert entry["dataset"] == "$mixpanel"
        assert entry["value"] == "cart"
        assert entry["resourceType"] == "events"
        assert entry["joinPropertyType"] == "list"
        assert entry["propertyType"] == "object"
        assert entry["listItemGroup"] == {
            "resourceType": "event",
            "propertyName": "Brand",
            "propertyDefaultType": "string",
            "propertyType": "string",
        }

    def test_number_sub_type(self) -> None:
        """sub_type='number' propagates into listItemGroup."""
        g = GroupBy.list_item("cart", "Price", sub_type="number")
        entry = build_group_section(g)[0]
        assert entry["listItemGroup"]["propertyType"] == "number"
        assert entry["listItemGroup"]["propertyDefaultType"] == "number"

    def test_pins_list_item_mode_set(self) -> None:
        """The classmethod sets ``_list_item_mode`` and leaves property_type as default."""
        g = GroupBy.list_item("cart", "Brand")
        assert g._list_item_mode is not None
        assert g._list_item_mode.sub == "Brand"
        assert g._list_item_mode.sub_type == "string"
        assert g.property_type == "string"  # default; wire builder hardcodes "object"

    def test_rejects_bucketing(self) -> None:
        """list_item with bucket_size raises in __post_init__."""
        with pytest.raises(ValueError, match="bucketing"):
            GroupBy(
                property="cart",
                bucket_size=10,
                _list_item_mode=ListItemGroupMode(sub="Price", sub_type="number"),
            )

    def test_rejects_non_string_property_on_list_item(self) -> None:
        """``_list_item_mode`` set but property is not a plain str raises (GB5)."""
        ref = CustomPropertyRef(id=42)
        with pytest.raises(ValueError, match="plain str"):
            GroupBy(
                property=ref,
                _list_item_mode=ListItemGroupMode(sub="Brand", sub_type="string"),
            )

    def test_list_item_mode_validates_empty_sub(self) -> None:
        """``ListItemGroupMode`` rejects empty/whitespace sub names."""
        with pytest.raises(ValueError, match="non-empty"):
            ListItemGroupMode(sub="", sub_type="string")
        with pytest.raises(ValueError, match="non-empty"):
            ListItemGroupMode(sub="   ", sub_type="string")

    def test_list_item_mode_validates_sub_type_content(self) -> None:
        """``ListItemGroupMode`` rejects sub_type values outside CustomPropertyType."""
        with pytest.raises(ValueError, match="sub_type"):
            ListItemGroupMode(sub="Brand", sub_type="bogus")  # type: ignore[arg-type]

    def test_list_item_runtime_rejects_bad_sub_type(self) -> None:
        """``GroupBy.list_item`` propagates ListItemGroupMode validation at construction."""
        with pytest.raises(ValueError, match="sub_type"):
            GroupBy.list_item("cart", "Brand", sub_type="bogus")  # type: ignore[arg-type]

    def test_list_item_runtime_rejects_empty_sub(self) -> None:
        """``GroupBy.list_item`` propagates ListItemGroupMode empty-sub validation."""
        with pytest.raises(ValueError, match="non-empty"):
            GroupBy.list_item("cart", "")

    def test_via_build_group_section_in_list(self) -> None:
        """list_item GroupBy mixed with other groups in a list."""
        groups: list[str | GroupBy] = [
            "platform",
            GroupBy.list_item("cart", "Brand"),
        ]
        section = build_group_section(groups)
        assert len(section) == 2
        assert section[0]["value"] == "platform"
        assert "listItemGroup" in section[1]
