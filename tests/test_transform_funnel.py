"""Unit tests for _transform_funnel_result() and _extract_funnel_steps_from_series()."""

from __future__ import annotations

from typing import Any

import pytest

from mixpanel_headless._internal.services.live_query import (
    _extract_funnel_steps_from_series,
    _transform_funnel_result,
)
from mixpanel_headless.exceptions import QueryError
from mixpanel_headless.types import FunnelQueryResult

# =============================================================================
# Shared fixtures
# =============================================================================

_SAMPLE_STEPS: list[dict[str, Any]] = [
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

_MOCK_RESPONSE: dict[str, Any] = {
    "computed_at": "2025-01-15T12:00:00",
    "date_range": {"from_date": "2025-01-01", "to_date": "2025-01-31"},
    "headers": ["$funnel"],
    "series": {
        "steps": _SAMPLE_STEPS,
    },
    "meta": {"sampling_factor": 1.0},
}

_BOOKMARK_PARAMS: dict[str, Any] = {"sections": {}, "displayOptions": {}}


# =============================================================================
# TestExtractFunnelStepsFromSeries (T020b)
# =============================================================================


class TestExtractFunnelStepsFromSeries:
    """Tests for _extract_funnel_steps_from_series helper."""

    def test_direct_list_input(self) -> None:
        """Direct list input is returned unchanged."""
        steps = [{"event": "Signup", "count": 100}]

        result = _extract_funnel_steps_from_series(steps)

        assert result is steps

    def test_dict_with_steps_key(self) -> None:
        """Dict containing 'steps' key returns the steps list."""
        series = {"steps": _SAMPLE_STEPS}

        result = _extract_funnel_steps_from_series(series)

        assert result is _SAMPLE_STEPS

    def test_segmented_overall_dict_with_steps(self) -> None:
        """Segmented response with '$overall' dict containing 'steps' returns those steps."""
        inner_steps = [{"event": "Login", "count": 500}]
        series = {"$overall": {"steps": inner_steps}}

        result = _extract_funnel_steps_from_series(series)

        assert result is inner_steps

    def test_segmented_overall_as_list(self) -> None:
        """Segmented response where '$overall' is a list returns that list."""
        overall_list: list[dict[str, Any]] = [{"event": "Signup", "count": 200}]
        series = {"$overall": overall_list}

        result = _extract_funnel_steps_from_series(series)

        assert result is overall_list

    def test_empty_dict_returns_empty_list(self) -> None:
        """Empty dict returns an empty list."""
        result = _extract_funnel_steps_from_series({})

        assert result == []

    def test_non_dict_int_returns_empty_list(self) -> None:
        """Non-dict input (int) returns an empty list."""
        result = _extract_funnel_steps_from_series(42)

        assert result == []

    def test_non_dict_string_returns_empty_list(self) -> None:
        """Non-dict input (string) returns an empty list."""
        result = _extract_funnel_steps_from_series("not a dict")

        assert result == []

    def test_non_dict_none_returns_empty_list(self) -> None:
        """Non-dict input (None) returns an empty list."""
        result = _extract_funnel_steps_from_series(None)

        assert result == []

    def test_steps_key_preferred_over_overall(self) -> None:
        """When both 'steps' and '$overall' keys exist, 'steps' takes precedence."""
        direct_steps = [{"event": "Direct", "count": 1}]
        overall_steps = [{"event": "Overall", "count": 2}]
        series = {
            "steps": direct_steps,
            "$overall": {"steps": overall_steps},
        }

        result = _extract_funnel_steps_from_series(series)

        assert result is direct_steps

    def test_empty_list_input(self) -> None:
        """Empty list input is returned unchanged."""
        result = _extract_funnel_steps_from_series([])

        assert result == []

    def test_dict_with_non_list_steps_falls_through(self) -> None:
        """Dict where 'steps' value is not a list falls through to '$overall' check."""
        series: dict[str, Any] = {
            "steps": "not a list",
            "$overall": [{"event": "Fallback"}],
        }

        result = _extract_funnel_steps_from_series(series)

        assert result == [{"event": "Fallback"}]

    def test_dict_with_unrelated_keys_returns_empty(self) -> None:
        """Dict with keys other than 'steps' and '$overall' returns empty list."""
        series = {"foo": "bar", "baz": [1, 2, 3]}

        with pytest.warns(UserWarning, match="unrecognized format"):
            result = _extract_funnel_steps_from_series(series)

        assert result == []

    # -----------------------------------------------------------------
    # Insights API nested series format (lines 367-437)
    # -----------------------------------------------------------------

    def test_insights_canonical_format(self) -> None:
        """Canonical insights API format extracts step data correctly."""
        series = {
            "Signup through Purchase": {
                "count": {
                    "1. Signup": {"all": 1000},
                    "2. Purchase": {"all": 120},
                },
                "step_conv_ratio": {
                    "1. Signup": {"all": 1.0},
                    "2. Purchase": {"all": 0.12},
                },
                "overall_conv_ratio": {
                    "1. Signup": {"all": 1.0},
                    "2. Purchase": {"all": 0.12},
                },
                "avg_time": {
                    "1. Signup": {"all": 0},
                    "2. Purchase": {"all": 86400},
                },
                "avg_time_from_start": {
                    "1. Signup": {"all": 0},
                    "2. Purchase": {"all": 86400},
                },
            }
        }

        result = _extract_funnel_steps_from_series(series)

        assert len(result) == 2
        assert result[0]["event"] == "Signup"
        assert result[0]["count"] == 1000
        assert result[0]["step_conv_ratio"] == 1.0
        assert result[1]["event"] == "Purchase"
        assert result[1]["count"] == 120
        assert result[1]["overall_conv_ratio"] == 0.12
        assert result[1]["avg_time"] == 86400

    def test_insights_format_numeric_sorting_10_plus_steps(self) -> None:
        """Steps with 10+ entries sort numerically, not lexicographically."""
        count_data = {f"{i}. Step{i}": {"all": 1000 - i * 100} for i in range(1, 12)}
        series = {"Funnel": {"count": count_data}}

        result = _extract_funnel_steps_from_series(series)

        assert len(result) == 11
        # Step 10 should come after step 9, not after step 1
        assert result[0]["event"] == "Step1"
        assert result[8]["event"] == "Step9"
        assert result[9]["event"] == "Step10"
        assert result[10]["event"] == "Step11"

    def test_insights_segmented_format_with_overall(self) -> None:
        """Segmented format extracts $overall metrics."""
        series = {
            "Signup through Purchase": {
                "$overall": {
                    "count": {
                        "1. Signup": {"all": 500},
                        "2. Purchase": {"all": 60},
                    },
                    "step_conv_ratio": {
                        "1. Signup": {"all": 1.0},
                        "2. Purchase": {"all": 0.12},
                    },
                    "overall_conv_ratio": {
                        "1. Signup": {"all": 1.0},
                        "2. Purchase": {"all": 0.12},
                    },
                    "avg_time": {},
                    "avg_time_from_start": {},
                },
                "Chrome": {
                    "count": {"1. Signup": {"all": 300}},
                },
            }
        }

        result = _extract_funnel_steps_from_series(series)

        assert len(result) == 2
        assert result[0]["event"] == "Signup"
        assert result[0]["count"] == 500

    def test_insights_format_missing_metrics_default_to_zero(self) -> None:
        """Missing metric keys default to 0."""
        series = {
            "Funnel": {
                "count": {
                    "1. Signup": {"all": 100},
                    "2. Purchase": {"all": 10},
                },
                # No step_conv_ratio, overall_conv_ratio, avg_time, avg_time_from_start
            }
        }

        result = _extract_funnel_steps_from_series(series)

        assert len(result) == 2
        assert result[0]["step_conv_ratio"] == 0
        assert result[0]["overall_conv_ratio"] == 0
        assert result[0]["avg_time"] == 0
        assert result[0]["avg_time_from_start"] == 0

    def test_insights_format_non_prefixed_step_names(self) -> None:
        """Step names without numeric prefix are used as-is."""
        series = {
            "Funnel": {
                "count": {
                    "Signup": {"all": 100},
                    "Purchase": {"all": 10},
                },
            }
        }

        result = _extract_funnel_steps_from_series(series)

        assert len(result) == 2
        # Without numeric prefix, sorted by fallback key
        events = [s["event"] for s in result]
        assert "Signup" in events
        assert "Purchase" in events

    def test_insights_format_scalar_step_data(self) -> None:
        """Scalar metric values (not wrapped in {"all": val}) are returned directly."""
        series = {
            "Funnel": {
                "count": {
                    "1. Signup": 1000,
                    "2. Purchase": 120,
                },
            }
        }

        result = _extract_funnel_steps_from_series(series)

        assert len(result) == 2
        assert result[0]["count"] == 1000
        assert result[1]["count"] == 120

    def test_insights_format_non_dict_count_returns_empty(self) -> None:
        """Non-dict count data returns empty list."""
        series = {"Funnel": {"count": "not a dict"}}

        result = _extract_funnel_steps_from_series(series)

        assert result == []

    def test_insights_trends_format(self) -> None:
        """Trends format with date-keyed sub-dicts extracts from first date."""
        series = {
            "Signup through Purchase": {
                "2025-01-01": {
                    "count": {
                        "1. Signup": {"all": 100},
                        "2. Purchase": {"all": 12},
                    },
                },
                "2025-01-02": {
                    "count": {
                        "1. Signup": {"all": 90},
                    },
                },
            }
        }

        result = _extract_funnel_steps_from_series(series)

        assert len(result) == 2
        assert result[0]["event"] == "Signup"


# =============================================================================
# TestTransformFunnelResult (T020)
# =============================================================================


class TestTransformFunnelResult:
    """Tests for _transform_funnel_result."""

    def test_returns_funnel_query_result(self) -> None:
        """Return type is FunnelQueryResult."""
        result = _transform_funnel_result(_MOCK_RESPONSE, _BOOKMARK_PARAMS)

        assert isinstance(result, FunnelQueryResult)

    def test_computed_at_extracted(self) -> None:
        """computed_at is extracted from the raw response."""
        result = _transform_funnel_result(_MOCK_RESPONSE, _BOOKMARK_PARAMS)

        assert result.computed_at == "2025-01-15T12:00:00"

    def test_from_date_extracted(self) -> None:
        """from_date is extracted from raw['date_range']."""
        result = _transform_funnel_result(_MOCK_RESPONSE, _BOOKMARK_PARAMS)

        assert result.from_date == "2025-01-01"

    def test_to_date_extracted(self) -> None:
        """to_date is extracted from raw['date_range']."""
        result = _transform_funnel_result(_MOCK_RESPONSE, _BOOKMARK_PARAMS)

        assert result.to_date == "2025-01-31"

    def test_steps_data_populated_from_series(self) -> None:
        """steps_data is populated via _extract_funnel_steps_from_series."""
        result = _transform_funnel_result(_MOCK_RESPONSE, _BOOKMARK_PARAMS)

        assert result.steps_data == _SAMPLE_STEPS
        assert len(result.steps_data) == 2
        assert result.steps_data[0]["event"] == "Signup"
        assert result.steps_data[1]["event"] == "Purchase"

    def test_series_preserved_as_raw_data(self) -> None:
        """series field preserves the raw series dict from the response."""
        result = _transform_funnel_result(_MOCK_RESPONSE, _BOOKMARK_PARAMS)

        assert result.series == {"steps": _SAMPLE_STEPS}

    def test_params_preserved_as_bookmark_params(self) -> None:
        """params field preserves the bookmark_params argument."""
        result = _transform_funnel_result(_MOCK_RESPONSE, _BOOKMARK_PARAMS)

        assert result.params == _BOOKMARK_PARAMS

    def test_meta_extracted(self) -> None:
        """meta is extracted from raw['meta']."""
        result = _transform_funnel_result(_MOCK_RESPONSE, _BOOKMARK_PARAMS)

        assert result.meta == {"sampling_factor": 1.0}

    def test_error_response_raises_query_error(self) -> None:
        """Response containing 'error' key raises QueryError."""
        error_response: dict[str, Any] = {"error": "invalid query"}

        with pytest.raises(QueryError, match="invalid query"):
            _transform_funnel_result(error_response, _BOOKMARK_PARAMS)

    def test_error_response_includes_status_code(self) -> None:
        """QueryError from error response has status_code=200 (leaked HTTP 200 error)."""
        error_response: dict[str, Any] = {"error": "bad params"}

        with pytest.raises(QueryError) as exc_info:
            _transform_funnel_result(error_response, _BOOKMARK_PARAMS)

        assert exc_info.value.status_code == 200

    def test_error_response_includes_response_body(self) -> None:
        """QueryError from error response includes the raw response as response_body."""
        error_response: dict[str, Any] = {"error": "timeout"}

        with pytest.raises(QueryError) as exc_info:
            _transform_funnel_result(error_response, _BOOKMARK_PARAMS)

        assert exc_info.value.response_body == error_response

    def test_error_response_includes_request_body(self) -> None:
        """QueryError from error response includes bookmark_params as request_body."""
        error_response: dict[str, Any] = {"error": "bad filter"}
        params = {"sections": {"filters": "invalid"}}

        with pytest.raises(QueryError) as exc_info:
            _transform_funnel_result(error_response, params)

        assert exc_info.value.request_body == params

    def test_missing_date_range_defaults_to_empty_strings(self) -> None:
        """Missing date_range defaults from_date and to_date to empty strings."""
        raw: dict[str, Any] = {
            "computed_at": "2025-01-15T12:00:00",
            "series": {"steps": []},
            "meta": {},
        }

        result = _transform_funnel_result(raw, _BOOKMARK_PARAMS)

        assert result.from_date == ""
        assert result.to_date == ""

    def test_missing_series_raises_query_error(self) -> None:
        """Missing series key raises QueryError."""
        raw: dict[str, Any] = {
            "computed_at": "2025-01-15T12:00:00",
            "date_range": {"from_date": "2025-01-01", "to_date": "2025-01-31"},
            "meta": {},
        }

        with pytest.raises(QueryError, match="missing 'series' key"):
            _transform_funnel_result(raw, _BOOKMARK_PARAMS)

    def test_missing_meta_defaults_to_empty_dict(self) -> None:
        """Missing meta key defaults to empty dict."""
        raw: dict[str, Any] = {
            "computed_at": "2025-01-15T12:00:00",
            "date_range": {"from_date": "2025-01-01", "to_date": "2025-01-31"},
            "series": {"steps": []},
        }

        result = _transform_funnel_result(raw, _BOOKMARK_PARAMS)

        assert result.meta == {}

    def test_missing_computed_at_defaults_to_empty_string(self) -> None:
        """Missing computed_at key defaults to empty string."""
        raw: dict[str, Any] = {
            "date_range": {"from_date": "2025-01-01", "to_date": "2025-01-31"},
            "series": {"steps": []},
            "meta": {},
        }

        result = _transform_funnel_result(raw, _BOOKMARK_PARAMS)

        assert result.computed_at == ""

    def test_minimal_raw_response(self) -> None:
        """Minimal response with series key produces valid result with defaults."""
        raw: dict[str, Any] = {"series": {}}

        result = _transform_funnel_result(raw, {})

        assert isinstance(result, FunnelQueryResult)
        assert result.computed_at == ""
        assert result.from_date == ""
        assert result.to_date == ""
        assert result.steps_data == []
        assert result.series == {}
        assert result.params == {}
        assert result.meta == {}

    def test_empty_response_raises_query_error(self) -> None:
        """Completely empty response raises QueryError due to missing series."""
        with pytest.raises(QueryError, match="missing 'series' key"):
            _transform_funnel_result({}, {})

    def test_segmented_series_extracts_overall_steps(self) -> None:
        """Segmented series with '$overall' dict correctly extracts steps."""
        steps = [{"event": "View", "count": 500}]
        raw: dict[str, Any] = {
            "computed_at": "2025-02-01T00:00:00",
            "date_range": {"from_date": "2025-02-01", "to_date": "2025-02-28"},
            "series": {"$overall": {"steps": steps}},
            "meta": {},
        }

        result = _transform_funnel_result(raw, _BOOKMARK_PARAMS)

        assert result.steps_data == steps

    def test_series_preserved_even_when_segmented(self) -> None:
        """series field preserves the raw segmented dict, not just the extracted steps."""
        segmented_series: dict[str, Any] = {
            "$overall": {"steps": [{"event": "A"}]},
            "segment_1": {"steps": [{"event": "B"}]},
        }
        raw: dict[str, Any] = {
            "computed_at": "2025-03-01T00:00:00",
            "date_range": {"from_date": "2025-03-01", "to_date": "2025-03-31"},
            "series": segmented_series,
            "meta": {},
        }

        result = _transform_funnel_result(raw, _BOOKMARK_PARAMS)

        assert result.series is segmented_series
