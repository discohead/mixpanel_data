"""Unit tests for the bookmark validation engine.

Tests both Layer 1 (validate_query_args) and Layer 2 (validate_bookmark)
validation functions, plus the error types and fuzzy matching.
"""

from __future__ import annotations

from typing import Any

import pytest

from mixpanel_headless._internal.validation import (
    _suggest,
    validate_bookmark,
    validate_query_args,
)
from mixpanel_headless.exceptions import BookmarkValidationError, ValidationError
from mixpanel_headless.types import GroupBy, Metric

# =============================================================================
# Helpers
# =============================================================================


def _valid_args(**overrides: Any) -> dict[str, Any]:
    """Return valid query args with optional overrides."""
    defaults: dict[str, Any] = {
        "events": ["Login"],
        "math": "total",
        "math_property": None,
        "per_user": None,
        "from_date": None,
        "to_date": None,
        "last": 30,
        "has_formula": False,
        "rolling": None,
        "cumulative": False,
        "group_by": None,
    }
    defaults.update(overrides)
    return defaults


def _minimal_bookmark(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid bookmark params dict with optional overrides."""
    bookmark: dict[str, Any] = {
        "sections": {
            "show": [
                {
                    "behavior": {
                        "type": "event",
                        "resourceType": "events",
                        "value": {"name": "Login"},
                    },
                    "measurement": {
                        "math": "total",
                    },
                }
            ],
            "time": [{"unit": "day", "dateRangeType": "in the last", "value": 30}],
            "filter": [],
            "group": [],
        },
        "displayOptions": {
            "chartType": "line",
            "analysis": "linear",
        },
    }
    bookmark.update(overrides)
    return bookmark


# =============================================================================
# ValidationError tests
# =============================================================================


class TestValidationError:
    """Tests for the ValidationError dataclass."""

    def test_to_dict_basic(self) -> None:
        """to_dict returns expected structure."""
        err = ValidationError(path="math", message="bad", code="V1")
        d = err.to_dict()
        assert d["path"] == "math"
        assert d["message"] == "bad"
        assert d["code"] == "V1"
        assert d["severity"] == "error"
        assert "suggestion" not in d
        assert "fix" not in d

    def test_to_dict_with_suggestion(self) -> None:
        """to_dict includes suggestion when present."""
        err = ValidationError(path="p", message="m", suggestion=("total", "unique"))
        d = err.to_dict()
        assert d["suggestion"] == ["total", "unique"]

    def test_to_dict_with_fix(self) -> None:
        """to_dict includes fix when present."""
        err = ValidationError(path="p", message="m", fix={"math": "total"})
        d = err.to_dict()
        assert d["fix"] == {"math": "total"}

    def test_str_error(self) -> None:
        """str() shows [ERROR] prefix."""
        err = ValidationError(path="math", message="bad math")
        assert "[ERROR]" in str(err)
        assert "math" in str(err)

    def test_str_warning(self) -> None:
        """str() shows [WARNING] prefix for warnings."""
        err = ValidationError(path="x", message="warn", severity="warning")
        assert "[WARNING]" in str(err)

    def test_str_with_suggestion(self) -> None:
        """str() includes 'Did you mean' when suggestion present."""
        err = ValidationError(path="p", message="bad", suggestion=("good",))
        assert "Did you mean 'good'?" in str(err)

    def test_frozen(self) -> None:
        """ValidationError is frozen (immutable)."""
        err = ValidationError(path="p", message="m")
        with pytest.raises(AttributeError):
            err.path = "new"  # type: ignore[misc]


class TestBookmarkValidationError:
    """Tests for the BookmarkValidationError exception."""

    def test_inherits_from_base(self) -> None:
        """BookmarkValidationError is a MixpanelHeadlessError."""
        from mixpanel_headless.exceptions import MixpanelHeadlessError

        err = BookmarkValidationError([ValidationError(path="p", message="m")])
        assert isinstance(err, MixpanelHeadlessError)

    def test_error_count(self) -> None:
        """error_count counts severity='error' items."""
        err = BookmarkValidationError(
            [
                ValidationError(path="a", message="m1"),
                ValidationError(path="b", message="m2", severity="warning"),
                ValidationError(path="c", message="m3"),
            ]
        )
        assert err.error_count == 2
        assert err.warning_count == 1

    def test_errors_tuple(self) -> None:
        """errors property returns tuple."""
        items = [ValidationError(path="p", message="m")]
        err = BookmarkValidationError(items)
        assert isinstance(err.errors, tuple)
        assert len(err.errors) == 1

    def test_to_dict(self) -> None:
        """to_dict serializes all errors."""
        err = BookmarkValidationError(
            [ValidationError(path="p", message="m", code="V1")]
        )
        d = err.to_dict()
        assert d["code"] == "BOOKMARK_VALIDATION_ERROR"
        assert d["details"]["error_count"] == 1
        assert len(d["details"]["errors"]) == 1
        assert d["details"]["errors"][0]["code"] == "V1"

    def test_message_contains_errors(self) -> None:
        """String message lists the error details."""
        err = BookmarkValidationError(
            [ValidationError(path="math", message="bad math")]
        )
        assert "bad math" in str(err)
        assert "1 error(s)" in str(err)


# =============================================================================
# Fuzzy matching tests
# =============================================================================


class TestFuzzyMatching:
    """Tests for the _suggest helper."""

    def test_close_match(self) -> None:
        """Finds close match for typo."""
        result = _suggest("totl", frozenset({"total", "unique", "average"}))
        assert result is not None
        assert "total" in result

    def test_no_match(self) -> None:
        """Returns None for completely different value."""
        result = _suggest("zzzzz", frozenset({"total", "unique"}))
        assert result is None

    def test_returns_tuple(self) -> None:
        """Result is a tuple of strings."""
        result = _suggest("averge", frozenset({"average", "median"}))
        assert result is not None
        assert isinstance(result, tuple)


# =============================================================================
# Layer 1: validate_query_args tests
# =============================================================================


class TestValidateQueryArgsLayer1:
    """Tests for Layer 1 argument validation."""

    def test_valid_args_no_errors(self) -> None:
        """Valid arguments produce empty error list."""
        errors = validate_query_args(**_valid_args())
        assert errors == []

    def test_v0_no_events(self) -> None:
        """V0: Empty events list produces error."""
        errors = validate_query_args(**_valid_args(events=[]))
        assert any(e.code == "V0_NO_EVENTS" for e in errors)

    def test_v1_math_requires_property(self) -> None:
        """V1: Property math without property produces error."""
        errors = validate_query_args(**_valid_args(math="average"))
        assert any(e.code == "V1_MATH_REQUIRES_PROPERTY" for e in errors)

    def test_v1_valid_with_property(self) -> None:
        """V1: Property math with property is valid."""
        errors = validate_query_args(
            **_valid_args(math="average", math_property="amount")
        )
        assert not any(e.code == "V1_MATH_REQUIRES_PROPERTY" for e in errors)

    def test_v2_rejects_property(self) -> None:
        """V2: Non-property math with property produces error."""
        errors = validate_query_args(
            **_valid_args(math="unique", math_property="amount")
        )
        assert any(e.code == "V2_MATH_REJECTS_PROPERTY" for e in errors)

    def test_v2_total_allows_property(self) -> None:
        """V2: 'total' math allows property (optional)."""
        errors = validate_query_args(
            **_valid_args(math="total", math_property="amount")
        )
        assert not any(e.code == "V2_MATH_REJECTS_PROPERTY" for e in errors)

    def test_v3_per_user_incompatible(self) -> None:
        """V3: per_user with DAU produces error."""
        errors = validate_query_args(**_valid_args(math="dau", per_user="average"))
        assert any(e.code == "V3_PER_USER_INCOMPATIBLE" for e in errors)

    def test_v3b_per_user_requires_property(self) -> None:
        """V3b: per_user without property produces error."""
        errors = validate_query_args(**_valid_args(math="total", per_user="average"))
        assert any(e.code == "V3B_PER_USER_REQUIRES_PROPERTY" for e in errors)

    def test_v4_formula_min_events(self) -> None:
        """V4: Formula with 1 event produces error."""
        errors = validate_query_args(**_valid_args(has_formula=True, events=["Login"]))
        assert any(e.code == "V4_FORMULA_MIN_EVENTS" for e in errors)

    def test_v4_formula_with_two_events(self) -> None:
        """V4: Formula with 2 events is valid."""
        errors = validate_query_args(
            **_valid_args(has_formula=True, events=["Login", "Signup"])
        )
        assert not any(e.code == "V4_FORMULA_MIN_EVENTS" for e in errors)

    def test_v5_rolling_cumulative_exclusive(self) -> None:
        """V5: Rolling and cumulative together produces error."""
        errors = validate_query_args(**_valid_args(rolling=7, cumulative=True))
        assert any(e.code == "V5_ROLLING_CUMULATIVE_EXCLUSIVE" for e in errors)

    def test_v6_rolling_positive(self) -> None:
        """V6: Non-positive rolling produces error."""
        errors = validate_query_args(**_valid_args(rolling=0))
        assert any(e.code == "V6_ROLLING_POSITIVE" for e in errors)

    def test_v7_last_positive(self) -> None:
        """V7: Non-positive last produces error."""
        errors = validate_query_args(**_valid_args(last=0))
        assert any(e.code == "V7_LAST_POSITIVE" for e in errors)

    def test_v8_from_date_format(self) -> None:
        """V8: Bad from_date format produces error."""
        errors = validate_query_args(**_valid_args(from_date="01/01/2024"))
        assert any(e.code == "V8_DATE_FORMAT" for e in errors)

    def test_v8_valid_date(self) -> None:
        """V8: Valid YYYY-MM-DD format passes."""
        errors = validate_query_args(
            **_valid_args(from_date="2024-01-01", to_date="2024-01-31")
        )
        assert not any(e.code == "V8_DATE_FORMAT" for e in errors)

    def test_v9_to_requires_from(self) -> None:
        """V9: to_date without from_date produces error."""
        errors = validate_query_args(**_valid_args(to_date="2024-01-31"))
        assert any(e.code == "V9_TO_REQUIRES_FROM" for e in errors)

    def test_v10_date_last_exclusive(self) -> None:
        """V10: from_date with non-default last produces error."""
        errors = validate_query_args(**_valid_args(from_date="2024-01-01", last=7))
        assert any(e.code == "V10_DATE_LAST_EXCLUSIVE" for e in errors)

    def test_v10_default_last_with_dates_ok(self) -> None:
        """V10: Default last (30) with dates is OK."""
        errors = validate_query_args(
            **_valid_args(from_date="2024-01-01", to_date="2024-01-31")
        )
        assert not any(e.code == "V10_DATE_LAST_EXCLUSIVE" for e in errors)

    def test_v11_bucket_requires_size(self) -> None:
        """V11: bucket_min without bucket_size produces error."""
        errors = validate_query_args(
            **_valid_args(
                group_by=GroupBy(
                    property="revenue",
                    property_type="number",
                    bucket_min=0,
                )
            )
        )
        assert any(e.code == "V11_BUCKET_REQUIRES_SIZE" for e in errors)

    def test_v12_bucket_size_positive(self) -> None:
        """V12: Non-positive bucket_size is rejected by GroupBy.__post_init__."""
        with pytest.raises(ValueError, match="bucket_size must be positive"):
            GroupBy(
                property="revenue",
                property_type="number",
                bucket_size=0,
                bucket_min=0,
                bucket_max=100,
            )

    def test_v12b_bucket_requires_number(self) -> None:
        """V12b: bucket_size with non-number type produces error."""
        errors = validate_query_args(
            **_valid_args(
                group_by=GroupBy(
                    property="country",
                    property_type="string",
                    bucket_size=10,
                    bucket_min=0,
                    bucket_max=100,
                )
            )
        )
        assert any(e.code == "V12B_BUCKET_REQUIRES_NUMBER" for e in errors)

    def test_v13_metric_math_property(self) -> None:
        """V13: Metric with property math and no property is rejected by __post_init__."""
        with pytest.raises(ValueError, match="requires a property"):
            Metric("Purchase", math="average")

    def test_v13_valid_metric(self) -> None:
        """V13: Metric with property math and property is valid."""
        errors = validate_query_args(
            **_valid_args(
                events=[Metric("Purchase", math="average", property="amount")]
            )
        )
        assert not any(e.code == "V13_METRIC_MATH_PROPERTY" for e in errors)

    def test_collects_all_errors(self) -> None:
        """Multiple violations produce multiple errors."""
        # Use a plain string event so top-level math validation (V1) fires;
        # events=[] would skip V1 because no plain events consume top-level math.
        errors = validate_query_args(
            **_valid_args(
                events=["Login"],
                math="average",
                last=-1,
            )
        )
        codes = {e.code for e in errors}
        assert "V1_MATH_REQUIRES_PROPERTY" in codes
        assert "V7_LAST_POSITIVE" in codes


# =============================================================================
# Layer 2: validate_bookmark tests
# =============================================================================


class TestValidateBookmarkLayer2:
    """Tests for Layer 2 bookmark structure validation."""

    def test_valid_bookmark_no_errors(self) -> None:
        """Valid bookmark produces empty error list."""
        errors = validate_bookmark(_minimal_bookmark())
        assert errors == []

    def test_b1_missing_sections(self) -> None:
        """B1: Missing sections produces error."""
        errors = validate_bookmark({"displayOptions": {"chartType": "line"}})
        assert any(e.code == "B1_MISSING_SECTIONS" for e in errors)

    def test_b2_missing_display_options(self) -> None:
        """B2: Missing displayOptions produces error."""
        errors = validate_bookmark(
            {"sections": {"show": [{"behavior": {"type": "event"}}]}}
        )
        assert any(e.code == "B2_MISSING_DISPLAY_OPTIONS" for e in errors)

    def test_b3_missing_show(self) -> None:
        """B3: Missing show produces error."""
        errors = validate_bookmark(
            {
                "sections": {"time": [], "filter": []},
                "displayOptions": {"chartType": "line"},
            }
        )
        assert any(e.code == "B3_MISSING_SHOW" for e in errors)

    def test_b4_show_empty(self) -> None:
        """B4: Empty show list produces error."""
        errors = validate_bookmark(
            {
                "sections": {"show": []},
                "displayOptions": {"chartType": "line"},
            }
        )
        assert any(e.code == "B4_SHOW_EMPTY" for e in errors)

    def test_b5_invalid_chart_type(self) -> None:
        """B5: Invalid chartType produces error with suggestions."""
        bm = _minimal_bookmark()
        bm["displayOptions"]["chartType"] = "barchart"
        errors = validate_bookmark(bm)
        chart_errors = [e for e in errors if e.code == "B5_INVALID_CHART_TYPE"]
        assert len(chart_errors) == 1
        assert chart_errors[0].suggestion is not None
        assert "bar" in chart_errors[0].suggestion

    def test_b5_missing_chart_type(self) -> None:
        """B5: Missing chartType produces error."""
        bm = _minimal_bookmark()
        del bm["displayOptions"]["chartType"]
        errors = validate_bookmark(bm)
        assert any(e.code == "B5_INVALID_CHART_TYPE" for e in errors)

    def test_b6_missing_behavior(self) -> None:
        """B6: Show clause without behavior produces error."""
        bm = _minimal_bookmark()
        bm["sections"]["show"] = [{"measurement": {"math": "total"}}]
        errors = validate_bookmark(bm)
        assert any(e.code == "B6_MISSING_BEHAVIOR" for e in errors)

    def test_b9_invalid_math(self) -> None:
        """B9: Invalid math type produces error with suggestions."""
        bm = _minimal_bookmark()
        bm["sections"]["show"][0]["measurement"]["math"] = "totl"
        errors = validate_bookmark(bm)
        math_errors = [e for e in errors if e.code == "B9_INVALID_MATH"]
        assert len(math_errors) == 1
        assert math_errors[0].suggestion is not None
        assert "total" in math_errors[0].suggestion

    def test_b10_math_missing_property(self) -> None:
        """B10: Property math without property produces warning."""
        bm = _minimal_bookmark()
        bm["sections"]["show"][0]["measurement"]["math"] = "average"
        errors = validate_bookmark(bm)
        prop_errors = [e for e in errors if e.code == "B10_MATH_MISSING_PROPERTY"]
        assert len(prop_errors) == 1
        assert prop_errors[0].severity == "warning"
        assert prop_errors[0].fix is not None

    def test_b12_invalid_time_unit(self) -> None:
        """B12: Invalid time unit produces error."""
        bm = _minimal_bookmark()
        bm["sections"]["time"] = [{"unit": "fortnite"}]
        errors = validate_bookmark(bm)
        assert any(e.code == "B12_INVALID_TIME_UNIT" for e in errors)

    def test_b14_invalid_filter_type(self) -> None:
        """B14: Invalid filterType produces error."""
        bm = _minimal_bookmark()
        bm["sections"]["filter"] = [
            {
                "filterType": "nope",
                "filterOperator": "equals",
                "value": "country",
                "filterValue": ["US"],
            }
        ]
        errors = validate_bookmark(bm)
        assert any(e.code == "B14_INVALID_FILTER_TYPE" for e in errors)

    def test_b15_invalid_filter_operator_warning(self) -> None:
        """B15: Invalid filterOperator produces warning."""
        bm = _minimal_bookmark()
        bm["sections"]["filter"] = [
            {
                "filterType": "string",
                "filterOperator": "approximately",
                "value": "country",
                "filterValue": ["US"],
            }
        ]
        errors = validate_bookmark(bm)
        op_errors = [e for e in errors if e.code == "B15_INVALID_FILTER_OPERATOR"]
        assert len(op_errors) == 1
        assert op_errors[0].severity == "warning"

    def test_b15_insights_date_operators_valid(self) -> None:
        """B15: InsightsDateRangeType operators pass validation."""
        insights_date_ops = [
            "was on",
            "was not on",
            "was in the",
            "was not in the",
            "was between",
            "was not between",
            "was less than",
            "was before",
            "was since",
            "was in the next",
        ]
        for op in insights_date_ops:
            bm = _minimal_bookmark()
            bm["sections"]["filter"] = [
                {
                    "filterType": "datetime",
                    "filterOperator": op,
                    "value": "created",
                    "filterValue": "2024-01-01",
                }
            ]
            errors = validate_bookmark(bm)
            op_errors = [e for e in errors if e.code == "B15_INVALID_FILTER_OPERATOR"]
            assert len(op_errors) == 0, (
                f"Operator {op!r} should be valid but got B15 warning"
            )

    def test_b18_missing_filter_property(self) -> None:
        """B18: Filter without property identifier produces error."""
        bm = _minimal_bookmark()
        bm["sections"]["filter"] = [
            {
                "filterType": "string",
                "filterOperator": "equals",
                "filterValue": ["US"],
            }
        ]
        errors = validate_bookmark(bm)
        assert any(e.code == "B18_MISSING_FILTER_PROPERTY" for e in errors)

    def test_b18_custom_property_id_passes(self) -> None:
        """B18: Filter with customPropertyId passes validation."""
        bm = _minimal_bookmark()
        bm["sections"]["filter"] = [
            {
                "filterType": "string",
                "filterOperator": "equals",
                "filterValue": ["US"],
                "customPropertyId": 42,
                "resourceType": "events",
            }
        ]
        errors = validate_bookmark(bm)
        assert not any(e.code == "B18_MISSING_FILTER_PROPERTY" for e in errors)

    def test_b18_custom_property_dict_passes(self) -> None:
        """B18: Filter with customProperty dict passes validation."""
        bm = _minimal_bookmark()
        bm["sections"]["filter"] = [
            {
                "filterType": "string",
                "filterOperator": "equals",
                "filterValue": ["US"],
                "customProperty": {
                    "displayFormula": "A",
                    "composedProperties": {},
                },
                "resourceType": "events",
            }
        ]
        errors = validate_bookmark(bm)
        assert not any(e.code == "B18_MISSING_FILTER_PROPERTY" for e in errors)

    def test_formula_show_clause_valid(self) -> None:
        """Formula show clauses are accepted."""
        bm = _minimal_bookmark()
        bm["sections"]["show"].append(
            {"formula": {"definition": "(A/B)*100", "name": "Rate"}}
        )
        errors = validate_bookmark(bm)
        assert not any(e.code == "B6_MISSING_BEHAVIOR" for e in errors)

    def test_valid_filter_passes(self) -> None:
        """Valid filter clause produces no errors."""
        bm = _minimal_bookmark()
        bm["sections"]["filter"] = [
            {
                "filterType": "string",
                "filterOperator": "equals",
                "value": "country",
                "filterValue": ["US"],
                "resourceType": "events",
            }
        ]
        errors = validate_bookmark(bm)
        filter_errors = [
            e
            for e in errors
            if e.code.startswith("B14")
            or e.code.startswith("B15")
            or e.code.startswith("B18")
        ]
        assert filter_errors == []

    def test_valid_group_passes(self) -> None:
        """Valid group clause produces no errors."""
        bm = _minimal_bookmark()
        bm["sections"]["group"] = [
            {
                "propertyName": "platform",
                "propertyType": "string",
                "resourceType": "events",
            }
        ]
        errors = validate_bookmark(bm)
        group_errors = [e for e in errors if e.code.startswith("B17")]
        assert group_errors == []


class TestValidateMeasurementFunnelContext:
    """Tests for _validate_measurement with bookmark_type='funnels'."""

    def test_funnel_math_accepted(self) -> None:
        """Valid funnel math types produce no errors when bookmark_type='funnels'."""
        funnel_math_types = [
            "conversion_rate_unique",
            "conversion_rate_total",
            "conversion_rate_session",
            "unique",
            "total",
            "general",
            "session",
            "conversion_rate",
        ]
        for math_type in funnel_math_types:
            bm = _minimal_funnel_bookmark(math=math_type)
            errors = validate_bookmark(bm, bookmark_type="funnels")
            math_errors = [e for e in errors if e.code == "B9_INVALID_MATH"]
            assert math_errors == [], f"math='{math_type}' should be valid for funnels"

    def test_insights_only_math_rejected_in_funnel_context(self) -> None:
        """Insights-only math types are rejected when bookmark_type='funnels'."""
        insights_only = ["dau", "wau", "mau", "cumulative_unique"]
        for math_type in insights_only:
            bm = _minimal_funnel_bookmark(math=math_type)
            errors = validate_bookmark(bm, bookmark_type="funnels")
            math_errors = [e for e in errors if e.code == "B9_INVALID_MATH"]
            assert len(math_errors) == 1, (
                f"math='{math_type}' should be invalid for funnels"
            )

    def test_funnel_math_rejected_in_insights_context(self) -> None:
        """Funnel-specific math types are rejected in default insights context."""
        funnel_only = [
            "conversion_rate",
            "conversion_rate_session",
            "general",
            "session",
        ]
        for math_type in funnel_only:
            bm = _minimal_bookmark()
            bm["sections"]["show"][0]["measurement"]["math"] = math_type
            errors = validate_bookmark(bm, bookmark_type="insights")
            math_errors = [e for e in errors if e.code == "B9_INVALID_MATH"]
            assert len(math_errors) == 1, (
                f"math='{math_type}' should be invalid for insights"
            )

    def test_funnel_math_with_suggestion(self) -> None:
        """Invalid funnel math produces suggestion from funnel math set."""
        bm = _minimal_funnel_bookmark(math="conversion_rate_uniqu")
        errors = validate_bookmark(bm, bookmark_type="funnels")
        math_errors = [e for e in errors if e.code == "B9_INVALID_MATH"]
        assert len(math_errors) == 1
        assert math_errors[0].suggestion is not None
        assert "conversion_rate_unique" in math_errors[0].suggestion


def _minimal_funnel_bookmark(
    math: str = "conversion_rate_unique",
) -> dict[str, Any]:
    """Return a minimal valid funnel bookmark params dict."""
    return {
        "sections": {
            "show": [
                {
                    "behavior": {
                        "type": "funnel",
                        "behaviors": [
                            {"name": "Signup", "resourceType": "events"},
                            {"name": "Purchase", "resourceType": "events"},
                        ],
                    },
                    "measurement": {
                        "math": math,
                    },
                }
            ],
            "time": [{"unit": "day", "dateRangeType": "in the last"}],
            "filter": [],
            "group": [],
            "formula": [],
        },
        "displayOptions": {
            "chartType": "funnel-steps",
        },
    }


# =============================================================================
# T036: data_group_id validation for insights
# =============================================================================


class TestDataGroupIdValidationInsights:
    """Tests for data_group_id validation in validate_query_args (T036)."""

    def test_valid_data_group_id(self) -> None:
        """Positive integer data_group_id passes validation."""
        errors = validate_query_args(**_valid_args(data_group_id=5))
        assert not any(e.code == "DG1_INVALID_DATA_GROUP_ID" for e in errors)

    def test_none_data_group_id(self) -> None:
        """None data_group_id passes validation (optional parameter)."""
        errors = validate_query_args(**_valid_args(data_group_id=None))
        assert not any(e.code == "DG1_INVALID_DATA_GROUP_ID" for e in errors)

    def test_zero_data_group_id(self) -> None:
        """data_group_id=0 fails validation (must be positive)."""
        errors = validate_query_args(**_valid_args(data_group_id=0))
        dg_errors = [e for e in errors if e.code == "DG1_INVALID_DATA_GROUP_ID"]
        assert len(dg_errors) == 1
        assert dg_errors[0].path == "data_group_id"

    def test_negative_data_group_id(self) -> None:
        """Negative data_group_id fails validation."""
        errors = validate_query_args(**_valid_args(data_group_id=-1))
        dg_errors = [e for e in errors if e.code == "DG1_INVALID_DATA_GROUP_ID"]
        assert len(dg_errors) == 1

    def test_data_group_id_true_rejected(self) -> None:
        """data_group_id=True is rejected (bool is subtype of int)."""
        errors = validate_query_args(**_valid_args(data_group_id=True))
        dg_errors = [e for e in errors if e.code == "DG1_INVALID_DATA_GROUP_ID"]
        assert len(dg_errors) == 1

    def test_data_group_id_false_rejected(self) -> None:
        """data_group_id=False is rejected (bool is subtype of int)."""
        errors = validate_query_args(**_valid_args(data_group_id=False))
        dg_errors = [e for e in errors if e.code == "DG1_INVALID_DATA_GROUP_ID"]
        assert len(dg_errors) == 1


# =============================================================================
# Layer 2: sorting block validation
# =============================================================================


class TestValidateSortingBlock:
    """Tests for the optional ``params['sorting']`` block validator.

    The sorting block is mirrored from Mixpanel's server-side
    ``SortByColumnsConfig`` / ``SortByValueConfig`` Pydantic schema. Bookmarks
    that pass create-time but contain a malformed sorting block fail later at
    query-time with messages like ``"sorting.bar.SortByColumnsConfig.sortBy
    must be 'column'"``. These tests lock in client-side rejection of the
    same shapes the server rejects.
    """

    def test_sorting_omitted_no_errors(self) -> None:
        """Bookmark without a 'sorting' key produces no sorting errors."""
        errors = validate_bookmark(_minimal_bookmark())
        sort_errors = [e for e in errors if e.code.startswith("S")]
        assert sort_errors == []

    def test_sorting_empty_dict_no_errors(self) -> None:
        """``sorting: {}`` is valid (no per-chart-type overrides)."""
        bm = _minimal_bookmark()
        bm["sorting"] = {}
        errors = validate_bookmark(bm)
        sort_errors = [e for e in errors if e.code.startswith("S")]
        assert sort_errors == []

    def test_sorting_canonical_column_config_passes(self) -> None:
        """Canonical ``sortBy='column'`` config with empty colSortAttrs passes."""
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "bar": {"sortBy": "column", "colSortAttrs": []},
        }
        errors = validate_bookmark(bm)
        sort_errors = [e for e in errors if e.code.startswith("S")]
        assert sort_errors == []

    def test_sorting_value_config_with_attrs_passes(self) -> None:
        """``sortBy='value'`` with non-empty colSortAttrs passes."""
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "bar": {
                "sortBy": "column",
                "colSortAttrs": [
                    {
                        "sortBy": "value",
                        "sortOrder": "asc",
                        "valueField": "averageValue",
                    }
                ],
            },
        }
        errors = validate_bookmark(bm)
        sort_errors = [e for e in errors if e.code.startswith("S")]
        assert sort_errors == []

    def test_sorting_invalid_sort_by_caught(self) -> None:
        """``sortBy`` outside {'column','value'} raises S1_INVALID_SORT_BY."""
        bm = _minimal_bookmark()
        bm["sorting"] = {"bar": {"sortBy": "totally bogus", "colSortAttrs": []}}
        errors = validate_bookmark(bm)
        s1 = [e for e in errors if e.code == "S1_INVALID_SORT_BY"]
        assert len(s1) == 1
        assert s1[0].path == "sorting.bar.sortBy"

    def test_sorting_extra_segmentation_field_caught(self) -> None:
        """Server rejects unknown fields like ``segmentation`` — so do we."""
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "bar": {
                "sortBy": "value",
                "segmentation": "value",
                "colSortAttrs": [],
            }
        }
        errors = validate_bookmark(bm)
        extra = [e for e in errors if e.code == "S3_UNKNOWN_FIELD"]
        assert len(extra) == 1
        assert extra[0].path == "sorting.bar.segmentation"

    def test_sorting_missing_col_sort_attrs_caught(self) -> None:
        """``colSortAttrs`` is required (server marks 'Field required')."""
        bm = _minimal_bookmark()
        bm["sorting"] = {"bar": {"sortBy": "value"}}
        errors = validate_bookmark(bm)
        missing = [e for e in errors if e.code == "S2_MISSING_COL_SORT_ATTRS"]
        assert len(missing) == 1
        assert missing[0].path == "sorting.bar.colSortAttrs"

    def test_sorting_collects_missing_col_sort_attrs_and_extra_segmentation(
        self,
    ) -> None:
        """Two malformed sort configs produce four errors total.

        Each chart-type config (``bar``, ``funnel-steps``) is missing
        ``colSortAttrs`` AND carries an extra ``segmentation`` field.
        The validator must collect all four errors — no per-config
        short-circuit — so callers can fix the whole bookmark in one pass.
        """
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "bar": {
                "sortBy": "value",
                "sortOrder": "asc",
                "segmentation": "value",
            },
            "funnel-steps": {
                "sortBy": "value",
                "sortOrder": "asc",
                "segmentation": "value",
            },
        }
        errors = validate_bookmark(bm)
        # Two missing colSortAttrs (one per chart-type config)
        missing = [e for e in errors if e.code == "S2_MISSING_COL_SORT_ATTRS"]
        assert len(missing) == 2
        # Two extra "segmentation" fields (one per chart-type config).
        # ``sortOrder`` is part of the canonical sort config (declared on
        # ``SortByValueConfig``, tolerated on ``SortByColumnsConfig``) so
        # it is NOT flagged.
        extra_segs = [
            e
            for e in errors
            if e.code == "S3_UNKNOWN_FIELD" and e.path.endswith(".segmentation")
        ]
        assert len(extra_segs) == 2

    def test_sorting_unknown_chart_type_warning(self) -> None:
        """Unknown chart-type key (e.g. typo 'barz') produces a warning."""
        bm = _minimal_bookmark()
        bm["sorting"] = {"barz": {"sortBy": "column", "colSortAttrs": []}}
        errors = validate_bookmark(bm)
        unknown = [e for e in errors if e.code == "S4_UNKNOWN_CHART_TYPE"]
        assert len(unknown) == 1
        assert unknown[0].severity == "warning"
        assert unknown[0].suggestion is not None
        assert "bar" in unknown[0].suggestion

    def test_sorting_chart_config_must_be_dict(self) -> None:
        """Per-chart-type sorting value must be a dict, not a string/list."""
        bm = _minimal_bookmark()
        bm["sorting"] = {"bar": "asc"}
        errors = validate_bookmark(bm)
        type_err = [e for e in errors if e.code == "S5_NOT_A_DICT"]
        assert len(type_err) == 1
        assert type_err[0].path == "sorting.bar"

    def test_sorting_block_must_be_dict(self) -> None:
        """The top-level ``sorting`` value must be a dict."""
        bm = _minimal_bookmark()
        bm["sorting"] = ["asc"]
        errors = validate_bookmark(bm)
        type_err = [e for e in errors if e.code == "S5_NOT_A_DICT"]
        assert len(type_err) == 1
        assert type_err[0].path == "sorting"

    def test_sorting_invalid_col_sort_attr_sort_order(self) -> None:
        """``colSortAttrs[i].sortOrder`` outside {'asc','desc'} caught."""
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "bar": {
                "sortBy": "column",
                "colSortAttrs": [
                    {"sortBy": "value", "sortOrder": "ascending", "valueField": "x"}
                ],
            }
        }
        errors = validate_bookmark(bm)
        order_err = [e for e in errors if e.code == "S6_INVALID_SORT_ORDER"]
        assert len(order_err) == 1

    def test_sorting_col_sort_attrs_must_be_list(self) -> None:
        """``colSortAttrs`` must be a list. Code is ``S7_NOT_A_LIST``."""
        bm = _minimal_bookmark()
        bm["sorting"] = {"bar": {"sortBy": "column", "colSortAttrs": {}}}
        errors = validate_bookmark(bm)
        not_a_list = [e for e in errors if e.code == "S7_NOT_A_LIST"]
        assert len(not_a_list) == 1
        assert not_a_list[0].path == "sorting.bar.colSortAttrs"

    def test_sorting_value_config_with_canonical_top_level_fields_passes(
        self,
    ) -> None:
        """``sortOrder``/``valueField``/``viewNLimit`` are valid at the
        sort-config level (not just inside ``colSortAttrs``).

        ``SortByValueConfig`` declares them explicitly; ``SortByColumnsConfig``
        tolerates them via ``Ignore[T]``. Layer 2 must not flag them as
        ``S3_UNKNOWN_FIELD`` — the Pydantic schema would accept them, so
        rejecting them here would create a behavioral split between
        ``create_bookmark`` (Pydantic) and ``update_bookmark`` (Layer 2).
        """
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "bar": {
                "sortBy": "value",
                "sortOrder": "asc",
                "valueField": "averageValue",
                "viewNLimit": 50,
                "colSortAttrs": [],
            }
        }
        errors = validate_bookmark(bm)
        sort_errors = [e for e in errors if e.code.startswith("S")]
        assert sort_errors == []

    def test_sorting_lift_comparison_value_accepted(self) -> None:
        """Deprecated ``sortBy='liftComparisonValue'`` must not be rejected.

        ``SortByValueConfig.sortBy`` accepts the deprecated alias; older
        saved bookmarks carry it. Layer 2 used to raise ``S1_INVALID_SORT_BY``
        on it, false-rejecting valid bookmarks.
        """
        bm = _minimal_bookmark()
        bm["sorting"] = {"bar": {"sortBy": "liftComparisonValue", "colSortAttrs": []}}
        errors = validate_bookmark(bm)
        s1 = [e for e in errors if e.code == "S1_INVALID_SORT_BY"]
        assert s1 == []

    def test_sorting_line_flat_label_config_accepted(self) -> None:
        """Line charts accept ``FlatLabelSortConfig`` (no colSortAttrs).

        Mirrors ``analytics/lib/common/mxpnl/report/bookmarks/insights/
        sorting.py:122`` — ``line: Optional[FlatOrColumnSortConfig]``
        admits ``FlatLabelSortConfig`` (``sortBy='label'``) and
        ``FlatValueSortConfig`` alongside the column/value SortConfig.
        Rejecting the flat shape would create a behavioral split: the
        Pydantic schema (Layer 1) accepts it for ``create_bookmark``,
        so the fallback validator (Layer 2) used by ``update_bookmark``
        must accept it too.
        """
        bm = _minimal_bookmark()
        bm["sorting"] = {"line": {"sortBy": "label", "sortOrder": "asc"}}
        errors = validate_bookmark(bm)
        sort_errors = [e for e in errors if e.code.startswith("S")]
        assert sort_errors == []

    def test_sorting_line_flat_value_config_accepted(self) -> None:
        """Line charts accept ``FlatValueSortConfig`` (no colSortAttrs)."""
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "line": {
                "sortBy": "value",
                "sortOrder": "desc",
                "valueField": "averageValue",
            }
        }
        errors = validate_bookmark(bm)
        sort_errors = [e for e in errors if e.code.startswith("S")]
        assert sort_errors == []

    def test_sorting_line_column_config_still_requires_col_sort_attrs(
        self,
    ) -> None:
        """Line + ``sortBy='column'`` is ``SortByColumnsConfig`` —
        ``colSortAttrs`` is still required (this is not the flat path).
        """
        bm = _minimal_bookmark()
        bm["sorting"] = {"line": {"sortBy": "column"}}
        errors = validate_bookmark(bm)
        missing = [e for e in errors if e.code == "S2_MISSING_COL_SORT_ATTRS"]
        assert len(missing) == 1
        assert missing[0].path == "sorting.line.colSortAttrs"

    def test_sorting_line_invalid_sort_by_caught(self) -> None:
        """Line ``sortBy`` must still be one of the four valid values.

        The line-specific union accepts ``label`` in addition to the
        normal ``column``/``value``/``liftComparisonValue``, but bogus
        values must still be rejected.
        """
        bm = _minimal_bookmark()
        bm["sorting"] = {"line": {"sortBy": "totally bogus", "sortOrder": "asc"}}
        errors = validate_bookmark(bm)
        s1 = [e for e in errors if e.code == "S1_INVALID_SORT_BY"]
        assert len(s1) == 1
        assert s1[0].path == "sorting.line.sortBy"

    def test_sorting_non_line_label_still_rejected(self) -> None:
        """``sortBy='label'`` is invalid at the top level for non-line charts.

        Only ``line`` admits the flat configs; ``bar``/``pie``/etc. must
        be ``SortConfig`` (column/value/liftComparisonValue).
        """
        bm = _minimal_bookmark()
        bm["sorting"] = {"bar": {"sortBy": "label", "colSortAttrs": []}}
        errors = validate_bookmark(bm)
        s1 = [e for e in errors if e.code == "S1_INVALID_SORT_BY"]
        assert len(s1) == 1
        assert s1[0].path == "sorting.bar.sortBy"

    def test_col_sort_attr_missing_sort_by_caught(self) -> None:
        """``colSortAttrs[i]`` must declare ``sortBy``.

        Mirrors canonical ``FlatSortConfig`` discriminator: ``sortBy``
        is required on both ``FlatLabelSortConfig`` and
        ``FlatValueSortConfig``. An entry like ``{"sortOrder": "asc"}``
        cannot be discriminated and would fail at render time.
        """
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "bar": {
                "sortBy": "column",
                "colSortAttrs": [{"sortOrder": "asc"}],
            }
        }
        errors = validate_bookmark(bm)
        missing = [e for e in errors if e.code == "S8_MISSING_SORT_BY"]
        assert len(missing) == 1
        assert missing[0].path == "sorting.bar.colSortAttrs[0].sortBy"

    def test_col_sort_attr_invalid_sort_by_caught(self) -> None:
        """``colSortAttrs[i].sortBy`` must be in {label, value, liftComparisonValue}.

        ``FlatSortConfig`` does not admit ``"column"`` (that's a
        top-level discriminator only). A bogus value must be rejected.
        """
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "bar": {
                "sortBy": "column",
                "colSortAttrs": [{"sortBy": "bogus", "sortOrder": "asc"}],
            }
        }
        errors = validate_bookmark(bm)
        s1 = [e for e in errors if e.code == "S1_INVALID_SORT_BY"]
        assert len(s1) == 1
        assert s1[0].path == "sorting.bar.colSortAttrs[0].sortBy"

    def test_col_sort_attr_column_sort_by_rejected(self) -> None:
        """``"column"`` is a top-level-only ``sortBy``; rejected inside colSortAttrs."""
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "bar": {
                "sortBy": "column",
                "colSortAttrs": [{"sortBy": "column", "sortOrder": "asc"}],
            }
        }
        errors = validate_bookmark(bm)
        s1 = [e for e in errors if e.code == "S1_INVALID_SORT_BY"]
        assert len(s1) == 1
        assert s1[0].path == "sorting.bar.colSortAttrs[0].sortBy"

    def test_col_sort_attr_missing_sort_order_caught(self) -> None:
        """``colSortAttrs[i]`` must declare ``sortOrder``.

        Both ``FlatLabelSortConfig`` and ``FlatValueSortConfig`` mark
        ``sortOrder`` as required; an entry that omits it fails server-
        side validation at render time.
        """
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "bar": {
                "sortBy": "column",
                "colSortAttrs": [{"sortBy": "value", "valueField": "x"}],
            }
        }
        errors = validate_bookmark(bm)
        missing = [e for e in errors if e.code == "S9_MISSING_SORT_ORDER"]
        assert len(missing) == 1
        assert missing[0].path == "sorting.bar.colSortAttrs[0].sortOrder"

    def test_col_sort_attr_label_sort_by_accepted(self) -> None:
        """``sortBy='label'`` is valid inside ``colSortAttrs`` (FlatLabelSortConfig)."""
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "bar": {
                "sortBy": "column",
                "colSortAttrs": [{"sortBy": "label", "sortOrder": "asc"}],
            }
        }
        errors = validate_bookmark(bm)
        sort_errors = [e for e in errors if e.code.startswith("S")]
        assert sort_errors == []

    # ------------------------------------------------------------------
    # Layer 1 / Layer 2 parity regressions (gap tests for Phase 1)
    # ------------------------------------------------------------------

    def test_sorting_invalid_top_level_sort_order_rejected(self) -> None:
        """Top-level ``sortOrder`` value is validated (was Layer-2 gap).

        Previously ``{sortBy: value, sortOrder: ascending, colSortAttrs: []}``
        was accepted by Layer 2 (only the value was unchecked) but rejected
        by Layer 1 — a behavioral split. With unification both reject.
        """
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "bar": {
                "sortBy": "value",
                "sortOrder": "ascending",
                "colSortAttrs": [],
            }
        }
        errors = validate_bookmark(bm)
        s6 = [e for e in errors if e.code == "S6_INVALID_SORT_ORDER"]
        assert len(s6) == 1
        assert s6[0].path == "sorting.bar.sortOrder"

    def test_sorting_unhashable_sort_by_does_not_crash(self) -> None:
        """``sortBy`` as a list/dict no longer raises raw ``TypeError``.

        Previously ``sort_by in frozenset(...)`` crashed when sort_by was
        unhashable. The unified Pydantic path returns a typed error.
        """
        bm = _minimal_bookmark()
        bm["sorting"] = {"bar": {"sortBy": [], "colSortAttrs": []}}
        errors = validate_bookmark(bm)
        s1 = [e for e in errors if e.code == "S1_INVALID_SORT_BY"]
        assert len(s1) == 1
        assert s1[0].path == "sorting.bar.sortBy"

    def test_sorting_col_sort_attrs_none_rejected(self) -> None:
        """``colSortAttrs: None`` is rejected (not silently accepted).

        Previously Layer 2 treated ``"colSortAttrs" in config`` as True
        for ``None``-valued keys and skipped both S2 and S7 checks. The
        unified path catches it as a list_type error → S7.
        """
        bm = _minimal_bookmark()
        bm["sorting"] = {"bar": {"sortBy": "column", "colSortAttrs": None}}
        errors = validate_bookmark(bm)
        s7 = [e for e in errors if e.code == "S7_NOT_A_LIST"]
        assert len(s7) == 1
        assert s7[0].path == "sorting.bar.colSortAttrs"

    def test_sorting_line_flat_missing_sort_order_caught(self) -> None:
        """Line ``{sortBy: 'label'}`` (no sortOrder) → S9 at top level."""
        bm = _minimal_bookmark()
        bm["sorting"] = {"line": {"sortBy": "label"}}
        errors = validate_bookmark(bm)
        s9 = [e for e in errors if e.code == "S9_MISSING_SORT_ORDER"]
        assert len(s9) == 1
        assert s9[0].path == "sorting.line.sortOrder"

    def test_sorting_line_flat_extra_field_caught(self) -> None:
        """Flat-path ``segmentation`` extra field caught (was uncovered)."""
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "line": {"sortBy": "label", "sortOrder": "asc", "segmentation": "x"}
        }
        errors = validate_bookmark(bm)
        s3 = [e for e in errors if e.code == "S3_UNKNOWN_FIELD"]
        assert len(s3) == 1
        assert s3[0].path == "sorting.line.segmentation"

    def test_sorting_line_label_with_col_sort_attrs_rejected(self) -> None:
        """``line + label + colSortAttrs=[]`` is invalid.

        ``label`` is unique to flat path; ``colSortAttrs`` is unique to
        SortConfig path. Combining them is contradictory — discriminator
        routes by sortBy and Pydantic rejects extra ``colSortAttrs``.
        """
        bm = _minimal_bookmark()
        bm["sorting"] = {
            "line": {"sortBy": "label", "sortOrder": "asc", "colSortAttrs": []}
        }
        errors = validate_bookmark(bm)
        # FlatLabelSortConfig forbids colSortAttrs
        s3 = [e for e in errors if e.code == "S3_UNKNOWN_FIELD"]
        assert len(s3) == 1
        assert s3[0].path == "sorting.line.colSortAttrs"

    def test_sorting_line_value_with_col_sort_attrs_routes_to_sort_config(
        self,
    ) -> None:
        """``line + value + colSortAttrs=[]`` is valid (SortByValueConfig path)."""
        bm = _minimal_bookmark()
        bm["sorting"] = {"line": {"sortBy": "value", "colSortAttrs": []}}
        errors = validate_bookmark(bm)
        sort_errors = [e for e in errors if e.code.startswith("S")]
        assert sort_errors == []
