"""Unit tests for _transform_retention_result()."""

from __future__ import annotations

from typing import Any

import pytest

from mixpanel_headless._internal.services.live_query import _transform_retention_result
from mixpanel_headless.exceptions import QueryError
from mixpanel_headless.types import RetentionQueryResult

# =============================================================================
# Shared fixtures
# =============================================================================

_BOOKMARK_PARAMS: dict[str, Any] = {"sections": {}, "displayOptions": {}}


def _mock_response(**overrides: Any) -> dict[str, Any]:
    """Build a mock retention API response with sensible defaults.

    Args:
        **overrides: Keys to override in the default response dict.

    Returns:
        A dict mimicking the retention query response shape.
    """
    defaults: dict[str, Any] = {
        "computed_at": "2025-01-15T12:00:00",
        "date_range": {"from_date": "2025-01-01", "to_date": "2025-01-31"},
        "series": {
            "Signup and then Login": {
                "2025-01-01": {
                    "first": 100,
                    "counts": [100, 50, 25],
                    "rates": [1.0, 0.5, 0.25],
                },
                "2025-01-02": {
                    "first": 80,
                    "counts": [80, 40],
                    "rates": [1.0, 0.5],
                },
                "$average": {
                    "first": 90,
                    "counts": [90, 45, 22],
                    "rates": [1.0, 0.5, 0.244],
                },
            }
        },
        "meta": {"sampling_factor": 1.0},
    }
    defaults.update(overrides)
    return defaults


# =============================================================================
# TestTransformRetentionBasic (T017)
# =============================================================================


class TestTransformRetentionBasic:
    """Tests for _transform_retention_result basic response parsing."""

    def test_returns_retention_query_result(self) -> None:
        """Return type is RetentionQueryResult."""
        result = _transform_retention_result(_mock_response(), _BOOKMARK_PARAMS)

        assert isinstance(result, RetentionQueryResult)

    def test_computed_at_extracted(self) -> None:
        """computed_at is extracted from the raw response."""
        result = _transform_retention_result(_mock_response(), _BOOKMARK_PARAMS)

        assert result.computed_at == "2025-01-15T12:00:00"

    def test_from_date_extracted(self) -> None:
        """from_date is extracted from raw['date_range']."""
        result = _transform_retention_result(_mock_response(), _BOOKMARK_PARAMS)

        assert result.from_date == "2025-01-01"

    def test_to_date_extracted(self) -> None:
        """to_date is extracted from raw['date_range']."""
        result = _transform_retention_result(_mock_response(), _BOOKMARK_PARAMS)

        assert result.to_date == "2025-01-31"

    def test_cohorts_extracted_from_series(self) -> None:
        """Cohorts are extracted from series, excluding $average."""
        result = _transform_retention_result(_mock_response(), _BOOKMARK_PARAMS)

        assert "2025-01-01" in result.cohorts
        assert "2025-01-02" in result.cohorts
        assert len(result.cohorts) == 2

    def test_cohort_data_structure(self) -> None:
        """Each cohort entry contains first, counts, and rates."""
        result = _transform_retention_result(_mock_response(), _BOOKMARK_PARAMS)

        cohort = result.cohorts["2025-01-01"]
        assert cohort["first"] == 100
        assert cohort["counts"] == [100, 50, 25]
        assert cohort["rates"] == [1.0, 0.5, 0.25]

    def test_average_extracted_from_series(self) -> None:
        """Average is extracted from series['$average']."""
        result = _transform_retention_result(_mock_response(), _BOOKMARK_PARAMS)

        assert result.average["first"] == 90
        assert result.average["counts"] == [90, 45, 22]
        assert result.average["rates"] == [1.0, 0.5, 0.244]

    def test_average_excluded_from_cohorts(self) -> None:
        """$average key does not appear in cohorts dict."""
        result = _transform_retention_result(_mock_response(), _BOOKMARK_PARAMS)

        assert "$average" not in result.cohorts

    def test_params_preserved(self) -> None:
        """params field preserves the bookmark_params argument."""
        result = _transform_retention_result(_mock_response(), _BOOKMARK_PARAMS)

        assert result.params == _BOOKMARK_PARAMS

    def test_meta_extracted(self) -> None:
        """meta is extracted from raw['meta']."""
        result = _transform_retention_result(_mock_response(), _BOOKMARK_PARAMS)

        assert result.meta == {"sampling_factor": 1.0}


# =============================================================================
# TestTransformRetentionErrors (T018)
# =============================================================================


class TestTransformRetentionErrors:
    """Tests for _transform_retention_result error handling."""

    def test_error_response_raises_query_error(self) -> None:
        """Response containing 'error' key raises QueryError with message."""
        error_response: dict[str, Any] = {"error": "invalid query"}

        with pytest.raises(QueryError, match="invalid query"):
            _transform_retention_result(error_response, _BOOKMARK_PARAMS)

    def test_error_response_includes_status_code(self) -> None:
        """QueryError from error response has status_code=200 (leaked HTTP 200 error)."""
        error_response: dict[str, Any] = {"error": "bad params"}

        with pytest.raises(QueryError) as exc_info:
            _transform_retention_result(error_response, _BOOKMARK_PARAMS)

        assert exc_info.value.status_code == 200

    def test_error_response_includes_response_body(self) -> None:
        """QueryError from error response includes the raw response as response_body."""
        error_response: dict[str, Any] = {"error": "timeout"}

        with pytest.raises(QueryError) as exc_info:
            _transform_retention_result(error_response, _BOOKMARK_PARAMS)

        assert exc_info.value.response_body == error_response

    def test_error_response_includes_request_body(self) -> None:
        """QueryError from error response includes bookmark_params as request_body."""
        error_response: dict[str, Any] = {"error": "bad filter"}
        params: dict[str, Any] = {"sections": {"filters": "invalid"}}

        with pytest.raises(QueryError) as exc_info:
            _transform_retention_result(error_response, params)

        assert exc_info.value.request_body == params

    def test_missing_series_raises_query_error(self) -> None:
        """Missing series key raises QueryError."""
        raw: dict[str, Any] = {
            "computed_at": "2025-01-15T12:00:00",
            "date_range": {"from_date": "2025-01-01", "to_date": "2025-01-31"},
            "meta": {},
        }

        with pytest.raises(QueryError, match="missing 'series' key"):
            _transform_retention_result(raw, _BOOKMARK_PARAMS)

    def test_empty_series_produces_empty_cohorts(self) -> None:
        """Empty series produces empty cohorts dict."""
        raw = _mock_response(series={})

        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)

        assert result.cohorts == {}
        assert result.average == {}

    def test_multiple_series_keys_raises_query_error(self) -> None:
        """Multiple top-level series keys raise QueryError (segmented data)."""
        raw = _mock_response(
            series={
                "metric_a": {
                    "2025-01-01": {"first": 10, "counts": [10], "rates": [1.0]}
                },
                "metric_b": {"2025-01-01": {"first": 5, "counts": [5], "rates": [1.0]}},
            }
        )

        with pytest.raises(QueryError, match="segmented series"):
            _transform_retention_result(raw, _BOOKMARK_PARAMS)

    def test_overall_wrapper_is_unwrapped(self) -> None:
        """$overall key in cohort data is unwrapped correctly."""
        raw = _mock_response(
            series={
                "Signup and then Login": {
                    "$overall": {
                        "2025-01-01": {
                            "first": 100,
                            "counts": [100, 50],
                            "rates": [1.0, 0.5],
                        },
                        "$average": {
                            "first": 100,
                            "counts": [100, 50],
                            "rates": [1.0, 0.5],
                        },
                    }
                }
            }
        )

        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)

        assert "2025-01-01" in result.cohorts
        assert result.average["first"] == 100

    def test_segmented_response_extracts_segments(self) -> None:
        """Response with $overall + named segments populates segments dict."""
        raw = _mock_response(
            series={
                "Signup and then Login": {
                    "$overall": {
                        "2025-01-01": {
                            "first": 100,
                            "counts": [100, 50],
                            "rates": [1.0, 0.5],
                        },
                        "$average": {
                            "first": 100,
                            "counts": [100, 50],
                            "rates": [1.0, 0.5],
                        },
                    },
                    "iOS": {
                        "2025-01-01": {
                            "first": 60,
                            "counts": [60, 30],
                            "rates": [1.0, 0.5],
                        },
                        "$average": {
                            "first": 60,
                            "counts": [60, 30],
                            "rates": [1.0, 0.5],
                        },
                    },
                    "Android": {
                        "2025-01-01": {
                            "first": 40,
                            "counts": [40, 20],
                            "rates": [1.0, 0.5],
                        },
                        "$average": {
                            "first": 40,
                            "counts": [40, 20],
                            "rates": [1.0, 0.5],
                        },
                    },
                }
            }
        )

        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)

        assert "iOS" in result.segments
        assert "Android" in result.segments
        assert "iOS" in result.segment_averages
        assert "Android" in result.segment_averages

    def test_segmented_response_cohorts_from_overall(self) -> None:
        """Segmented response uses $overall for primary cohorts field."""
        raw = _mock_response(
            series={
                "Signup and then Login": {
                    "$overall": {
                        "2025-01-01": {
                            "first": 100,
                            "counts": [100, 50],
                            "rates": [1.0, 0.5],
                        },
                    },
                    "iOS": {
                        "2025-01-01": {
                            "first": 60,
                            "counts": [60, 30],
                            "rates": [1.0, 0.5],
                        },
                    },
                }
            }
        )

        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)

        assert result.cohorts["2025-01-01"]["first"] == 100


# =============================================================================
# TestTransformRetentionNonDictSeries (T056)
# =============================================================================


class TestTransformRetentionNonDictSeries:
    """Tests for _transform_retention_result when series is not a dict."""

    def test_series_as_list_raises_query_error(self) -> None:
        """series=[] raises QueryError with descriptive message."""
        raw = _mock_response(series=[])

        with pytest.raises(QueryError, match="series.*list.*expected dict"):
            _transform_retention_result(raw, _BOOKMARK_PARAMS)

    def test_series_as_string_raises_query_error(self) -> None:
        """series='pending' raises QueryError."""
        raw = _mock_response(series="pending")

        with pytest.raises(QueryError, match="series.*str.*expected dict"):
            _transform_retention_result(raw, _BOOKMARK_PARAMS)

    def test_series_as_int_raises_query_error(self) -> None:
        """series=0 raises QueryError."""
        raw = _mock_response(series=0)

        with pytest.raises(QueryError, match="series.*int.*expected dict"):
            _transform_retention_result(raw, _BOOKMARK_PARAMS)

    def test_non_dict_metric_value_raises_query_error(self) -> None:
        """series={'metric': 'error string'} raises QueryError."""
        raw = _mock_response(series={"Signup and then Login": "error: timeout"})

        with pytest.raises(QueryError, match="not a dict.*got str"):
            _transform_retention_result(raw, _BOOKMARK_PARAMS)

    def test_non_dict_metric_value_as_list_raises_query_error(self) -> None:
        """series={'metric': [1, 2]} raises QueryError."""
        raw = _mock_response(series={"Signup and then Login": [1, 2, 3]})

        with pytest.raises(QueryError, match="not a dict.*got list"):
            _transform_retention_result(raw, _BOOKMARK_PARAMS)


# =============================================================================
# TestTransformRetentionSegments (T055)
# =============================================================================


_SEGMENTED_SERIES: dict[str, Any] = {
    "Signup and then Login": {
        "$overall": {
            "2025-01-01": {
                "first": 200,
                "counts": [200, 100],
                "rates": [1.0, 0.5],
            },
            "$average": {
                "first": 200,
                "counts": [200, 100],
                "rates": [1.0, 0.5],
            },
        },
        "iOS": {
            "2025-01-01": {
                "first": 120,
                "counts": [120, 60],
                "rates": [1.0, 0.5],
            },
            "$average": {
                "first": 120,
                "counts": [120, 60],
                "rates": [1.0, 0.5],
            },
        },
        "Android": {
            "2025-01-01": {
                "first": 80,
                "counts": [80, 40],
                "rates": [1.0, 0.5],
            },
            "$average": {
                "first": 80,
                "counts": [80, 40],
                "rates": [1.0, 0.5],
            },
        },
    }
}


class TestTransformRetentionSegments:
    """Tests for segmented retention response parsing (T055)."""

    def test_segments_dict_has_correct_keys(self) -> None:
        """Segment names match response keys (excluding $overall)."""
        raw = _mock_response(series=_SEGMENTED_SERIES)
        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)

        assert sorted(result.segments.keys()) == ["Android", "iOS"]

    def test_segment_cohort_data_preserved(self) -> None:
        """Each segment's cohort data (first, counts, rates) is intact."""
        raw = _mock_response(series=_SEGMENTED_SERIES)
        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)

        ios_cohort = result.segments["iOS"]["2025-01-01"]
        assert ios_cohort["first"] == 120
        assert ios_cohort["counts"] == [120, 60]
        assert ios_cohort["rates"] == [1.0, 0.5]

    def test_segment_averages_extracted(self) -> None:
        """$average within each segment goes to segment_averages."""
        raw = _mock_response(series=_SEGMENTED_SERIES)
        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)

        assert result.segment_averages["iOS"]["first"] == 120
        assert result.segment_averages["Android"]["first"] == 80

    def test_unsegmented_response_has_empty_segments(self) -> None:
        """Unsegmented response (no $overall) has empty segments dict."""
        raw = _mock_response()
        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)

        assert result.segments == {}
        assert result.segment_averages == {}

    def test_overall_only_response_has_empty_segments(self) -> None:
        """Response with $overall but no named segments has empty segments."""
        raw = _mock_response(
            series={
                "Signup and then Login": {
                    "$overall": {
                        "2025-01-01": {
                            "first": 100,
                            "counts": [100, 50],
                            "rates": [1.0, 0.5],
                        },
                    }
                }
            }
        )
        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)

        assert result.segments == {}
        assert result.segment_averages == {}


# =============================================================================
# TestTransformRetentionDateNormalization (T056)
# =============================================================================


class TestTransformRetentionDateNormalization:
    """Tests for cohort date key normalization (T056)."""

    def test_iso_timestamp_keys_normalized(self) -> None:
        """ISO timestamp cohort keys are normalized to YYYY-MM-DD."""
        raw = _mock_response(
            series={
                "Signup and then Login": {
                    "2025-01-01T00:00:00+00:00": {
                        "first": 100,
                        "counts": [100, 50],
                        "rates": [1.0, 0.5],
                    },
                    "$average": {
                        "first": 100,
                        "counts": [100, 50],
                        "rates": [1.0, 0.5],
                    },
                }
            }
        )

        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)

        assert "2025-01-01" in result.cohorts
        assert "2025-01-01T00:00:00+00:00" not in result.cohorts

    def test_plain_date_keys_unchanged(self) -> None:
        """Plain YYYY-MM-DD cohort keys are preserved as-is."""
        raw = _mock_response()
        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)

        assert "2025-01-01" in result.cohorts
        assert "2025-01-02" in result.cohorts

    def test_segment_date_keys_normalized(self) -> None:
        """ISO timestamp keys are normalized within segment cohort data."""
        raw = _mock_response(
            series={
                "Signup and then Login": {
                    "$overall": {
                        "2025-01-01T00:00:00+00:00": {
                            "first": 100,
                            "counts": [100, 50],
                            "rates": [1.0, 0.5],
                        },
                    },
                    "iOS": {
                        "2025-01-01T00:00:00+00:00": {
                            "first": 60,
                            "counts": [60, 30],
                            "rates": [1.0, 0.5],
                        },
                    },
                }
            }
        )

        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)

        assert "2025-01-01" in result.cohorts
        assert "2025-01-01" in result.segments["iOS"]


# =============================================================================
# TestTransformRetentionFormatVariations (T054)
# =============================================================================


class TestTransformRetentionFormatVariations:
    """Tests for response format variations (T054)."""

    def test_direct_cohort_dict(self) -> None:
        """Direct cohort dict format (no wrapper) is parsed correctly."""
        raw = _mock_response()
        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)
        assert len(result.cohorts) == 2

    def test_missing_date_range_uses_defaults(self) -> None:
        """Missing date_range produces empty from_date/to_date."""
        raw = _mock_response()
        del raw["date_range"]
        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)
        assert result.from_date == ""
        assert result.to_date == ""

    def test_missing_meta_uses_empty_dict(self) -> None:
        """Missing meta produces empty dict."""
        raw = _mock_response()
        del raw["meta"]
        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)
        assert result.meta == {}

    def test_missing_computed_at_uses_empty_string(self) -> None:
        """Missing computed_at produces empty string."""
        raw = _mock_response()
        del raw["computed_at"]
        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)
        assert result.computed_at == ""

    def test_series_without_average(self) -> None:
        """Series without $average produces empty average dict."""
        raw = _mock_response(
            series={
                "Signup and then Login": {
                    "2025-01-01": {
                        "first": 100,
                        "counts": [100, 50],
                        "rates": [1.0, 0.5],
                    },
                }
            }
        )
        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)
        assert result.average == {}
        assert len(result.cohorts) == 1

    def test_single_cohort_response(self) -> None:
        """Single cohort date in series is handled correctly."""
        raw = _mock_response(
            series={
                "Signup and then Login": {
                    "2025-01-01": {
                        "first": 50,
                        "counts": [50, 25],
                        "rates": [1.0, 0.5],
                    },
                    "$average": {
                        "first": 50,
                        "counts": [50, 25],
                        "rates": [1.0, 0.5],
                    },
                }
            }
        )
        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)
        assert len(result.cohorts) == 1
        assert "2025-01-01" in result.cohorts

    def test_empty_metric_wrapper(self) -> None:
        """Empty dict inside metric wrapper produces empty cohorts."""
        raw = _mock_response(series={"Signup and then Login": {}})
        result = _transform_retention_result(raw, _BOOKMARK_PARAMS)
        assert result.cohorts == {}
        assert result.average == {}
