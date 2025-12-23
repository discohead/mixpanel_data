#!/usr/bin/env python3
"""Live QA integration test for Query Service Enhancements (Phase 008).

This script performs real API calls against Mixpanel to verify the
new query methods added in the 008-query-service-enhancements branch:

Live Query Service:
- activity_feed() - User event history
- insights() - Saved Insights reports
- frequency() - Event frequency/addiction analysis
- segmentation_numeric() - Numeric property bucketing
- segmentation_sum() - Sum numeric property values
- segmentation_average() - Average numeric property values

Usage:
    uv run python scripts/qa_query_service_enhancements.py

Prerequisites:
    - Service account configured in ~/.mp/config.toml
    - Account name: sinkapp-prod
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient
    from mixpanel_data._internal.services.live_query import LiveQueryService
    from mixpanel_data.types import (
        ActivityFeedResult,
        FrequencyResult,
        InsightsResult,
        NumericAverageResult,
        NumericBucketResult,
        NumericSumResult,
    )


@dataclass
class TestResult:
    """Result of a single test case."""

    name: str
    passed: bool
    message: str
    duration_ms: float
    details: dict[str, Any] | None = None


class QARunner:
    """Runs QA tests and collects results."""

    def __init__(self) -> None:
        self.results: list[TestResult] = []

    def run_test(
        self, name: str, test_fn: Any, *args: Any, **kwargs: Any
    ) -> TestResult:
        """Run a single test and record the result."""
        start = time.perf_counter()
        try:
            result = test_fn(*args, **kwargs)
            duration = (time.perf_counter() - start) * 1000
            test_result = TestResult(
                name=name,
                passed=True,
                message="PASS",
                duration_ms=duration,
                details=result if isinstance(result, dict) else None,
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            test_result = TestResult(
                name=name,
                passed=False,
                message=f"FAIL: {type(e).__name__}: {e}",
                duration_ms=duration,
            )
        self.results.append(test_result)
        return test_result

    def print_results(self) -> None:
        """Print summary of all test results."""
        print("\n" + "=" * 70)
        print("QA TEST RESULTS - Query Service Enhancements (Phase 008)")
        print("=" * 70)

        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed

        for result in self.results:
            status = "✓" if result.passed else "✗"
            print(f"\n{status} {result.name} ({result.duration_ms:.1f}ms)")
            if not result.passed:
                print(f"  {result.message}")
            elif result.details:
                for key, value in result.details.items():
                    if isinstance(value, list) and len(value) > 5:
                        print(f"  {key}: [{len(value)} items] {value[:5]}...")
                    elif isinstance(value, dict) and len(value) > 3:
                        keys = list(value.keys())[:3]
                        print(f"  {key}: {{{len(value)} keys}} {keys}...")
                    else:
                        print(f"  {key}: {value}")

        print("\n" + "-" * 70)
        print(f"SUMMARY: {passed}/{len(self.results)} tests passed")
        if failed > 0:
            print(f"         {failed} tests FAILED")
        print("-" * 70)


def main() -> int:
    """Run all QA tests."""
    print("Query Service Enhancements QA - Live Integration Tests")
    print("=" * 70)

    runner = QARunner()

    # Shared state
    api_client: MixpanelAPIClient | None = None
    live_query: LiveQueryService | None = None

    # Account to use
    ACCOUNT_NAME = "sinkapp-prod"

    # Test data
    INSIGHTS_BOOKMARK_ID = 44592511
    ACTIVITY_DISTINCT_ID = "$device:60FB1D2E-2BE7-45AD-8887-53C397DE6234"
    NUMERIC_EVENT = "Added Entity"
    NUMERIC_PROPERTY = 'properties["$screen_height"]'

    # Date range for testing (previous month)
    today = datetime.now()
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    FROM_DATE = last_month_start.strftime("%Y-%m-%d")
    TO_DATE = last_month_end.strftime("%Y-%m-%d")

    print(f"Using date range: {FROM_DATE} to {TO_DATE}")
    print(f"Using account: {ACCOUNT_NAME}")
    print(f"Insights bookmark_id: {INSIGHTS_BOOKMARK_ID}")
    print(f"Activity distinct_id: {ACTIVITY_DISTINCT_ID}")
    print(f"Numeric test: event={NUMERIC_EVENT}, property={NUMERIC_PROPERTY}")

    # Stored results for later tests
    activity_result: ActivityFeedResult | None = None
    insights_result: InsightsResult | None = None
    frequency_result: FrequencyResult | None = None
    numeric_bucket_result: NumericBucketResult | None = None
    numeric_sum_result: NumericSumResult | None = None
    numeric_avg_result: NumericAverageResult | None = None

    # =========================================================================
    # Phase 1: Prerequisites
    # =========================================================================
    print("\n[Phase 1] Prerequisites Check")
    print("-" * 40)

    # Test 1.1: Import modules
    def test_imports() -> dict[str, Any]:
        from mixpanel_data._internal.api_client import MixpanelAPIClient  # noqa: F401
        from mixpanel_data._internal.config import ConfigManager  # noqa: F401
        from mixpanel_data._internal.services.live_query import (
            LiveQueryService,  # noqa: F401
        )
        from mixpanel_data.types import (
            ActivityFeedResult,  # noqa: F401
            FrequencyResult,  # noqa: F401
            InsightsResult,  # noqa: F401
            NumericAverageResult,  # noqa: F401
            NumericBucketResult,  # noqa: F401
            NumericSumResult,  # noqa: F401
            UserEvent,  # noqa: F401
        )

        return {"modules": ["All Phase 008 types and services imported successfully"]}

    result = runner.run_test("1.1 Import modules", test_imports)
    if not result.passed:
        print("Cannot continue - import failed")
        runner.print_results()
        return 1

    # Test 1.2: Resolve credentials
    def test_resolve_credentials() -> dict[str, Any]:
        from mixpanel_data._internal.config import ConfigManager

        config = ConfigManager()
        creds = config.resolve_credentials(account=ACCOUNT_NAME)
        return {
            "account": ACCOUNT_NAME,
            "username": creds.username[:10] + "...",
            "project_id": creds.project_id,
            "region": creds.region,
        }

    result = runner.run_test("1.2 Resolve credentials", test_resolve_credentials)
    if not result.passed:
        print("Cannot continue - no credentials available")
        runner.print_results()
        return 1

    # =========================================================================
    # Phase 2: Setup Components
    # =========================================================================
    print("\n[Phase 2] Setup Components")
    print("-" * 40)

    # Test 2.1: Create API client
    def test_create_client() -> dict[str, Any]:
        nonlocal api_client
        from mixpanel_data._internal.api_client import MixpanelAPIClient
        from mixpanel_data._internal.config import ConfigManager

        config = ConfigManager()
        creds = config.resolve_credentials(account=ACCOUNT_NAME)
        api_client = MixpanelAPIClient(creds)
        api_client.__enter__()
        return {"status": "client created"}

    result = runner.run_test("2.1 Create API client", test_create_client)
    if not result.passed:
        print("Cannot continue - client creation failed")
        runner.print_results()
        return 1

    # Test 2.2: Create LiveQueryService
    def test_create_live_query() -> dict[str, Any]:
        nonlocal live_query
        from mixpanel_data._internal.services.live_query import LiveQueryService

        assert api_client is not None
        live_query = LiveQueryService(api_client)
        return {"status": "service created"}

    result = runner.run_test("2.2 Create LiveQueryService", test_create_live_query)
    if not result.passed:
        print("Cannot continue - live query service creation failed")
        runner.print_results()
        return 1

    # =========================================================================
    # Phase 3: activity_feed() Tests
    # =========================================================================
    print("\n[Phase 3] activity_feed() Tests")
    print("-" * 40)

    # Test 3.1: Basic activity_feed call
    def test_activity_feed_basic() -> dict[str, Any]:
        nonlocal activity_result
        from mixpanel_data.types import ActivityFeedResult

        assert live_query is not None
        activity_result = live_query.activity_feed(
            distinct_ids=[ACTIVITY_DISTINCT_ID],
        )
        if not isinstance(activity_result, ActivityFeedResult):
            raise TypeError(f"Expected ActivityFeedResult, got {type(activity_result)}")
        return {
            "distinct_ids": activity_result.distinct_ids,
            "event_count": len(activity_result.events),
            "from_date": activity_result.from_date,
            "to_date": activity_result.to_date,
        }

    runner.run_test("3.1 activity_feed() basic", test_activity_feed_basic)

    # Test 3.2: Verify UserEvent structure
    def test_user_event_structure() -> dict[str, Any]:
        from mixpanel_data.types import UserEvent

        if activity_result is None or not activity_result.events:
            return {"skipped": "No events returned"}
        event = activity_result.events[0]
        if not isinstance(event, UserEvent):
            raise TypeError(f"Expected UserEvent, got {type(event)}")
        # Verify time is datetime with UTC
        if not isinstance(event.time, datetime):
            raise TypeError(f"time should be datetime, got {type(event.time)}")
        if event.time.tzinfo is None:
            raise ValueError("time should have timezone info")
        return {
            "event_name": event.event,
            "time": event.time.isoformat(),
            "time_has_tz": event.time.tzinfo is not None,
            "properties_keys": list(event.properties.keys())[:5],
        }

    runner.run_test("3.2 UserEvent structure", test_user_event_structure)

    # Test 3.3: activity_feed with date range
    def test_activity_feed_with_dates() -> dict[str, Any]:
        assert live_query is not None
        result = live_query.activity_feed(
            distinct_ids=[ACTIVITY_DISTINCT_ID],
            from_date=FROM_DATE,
            to_date=TO_DATE,
        )
        return {
            "from_date": result.from_date,
            "to_date": result.to_date,
            "event_count": len(result.events),
        }

    runner.run_test("3.3 activity_feed() with dates", test_activity_feed_with_dates)

    # Test 3.4: activity_feed with non-existent distinct_id
    def test_activity_feed_empty() -> dict[str, Any]:
        assert live_query is not None
        result = live_query.activity_feed(
            distinct_ids=["__nonexistent_user_xyz_123__"],
        )
        return {
            "distinct_ids": result.distinct_ids,
            "event_count": len(result.events),
            "is_empty": len(result.events) == 0,
        }

    runner.run_test("3.4 activity_feed() empty result", test_activity_feed_empty)

    # Test 3.5: ActivityFeedResult.df structure
    def test_activity_feed_df() -> dict[str, Any]:
        if activity_result is None:
            return {"skipped": "No activity result"}
        df = activity_result.df
        if len(df) == 0:
            return {"skipped": "Empty DataFrame"}
        expected_cols = {"event", "time", "distinct_id"}
        actual_cols = set(df.columns)
        if not expected_cols.issubset(actual_cols):
            raise ValueError(f"Missing columns: {expected_cols - actual_cols}")
        return {
            "columns": list(df.columns)[:7],
            "rows": len(df),
            "has_event": "event" in df.columns,
            "has_time": "time" in df.columns,
            "has_distinct_id": "distinct_id" in df.columns,
        }

    runner.run_test("3.5 ActivityFeedResult.df", test_activity_feed_df)

    # Test 3.6: ActivityFeedResult.df caching
    def test_activity_feed_df_caching() -> dict[str, Any]:
        if activity_result is None:
            return {"skipped": "No activity result"}
        df1 = activity_result.df
        df2 = activity_result.df
        if df1 is not df2:
            raise ValueError("DataFrame should be cached (same object)")
        return {"cached": True, "same_object": True}

    runner.run_test("3.6 ActivityFeedResult.df caching", test_activity_feed_df_caching)

    # Test 3.7: ActivityFeedResult.to_dict()
    def test_activity_feed_to_dict() -> dict[str, Any]:
        if activity_result is None:
            return {"skipped": "No activity result"}
        d = activity_result.to_dict()
        expected_keys = {
            "distinct_ids",
            "from_date",
            "to_date",
            "event_count",
            "events",
        }
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        _ = json.dumps(d)
        return {"keys": list(d.keys()), "json_serializable": True}

    runner.run_test("3.7 ActivityFeedResult.to_dict()", test_activity_feed_to_dict)

    # Test 3.8: UserEvent.to_dict()
    def test_user_event_to_dict() -> dict[str, Any]:
        if activity_result is None or not activity_result.events:
            return {"skipped": "No events"}
        event = activity_result.events[0]
        d = event.to_dict()
        expected_keys = {"event", "time", "properties"}
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        _ = json.dumps(d)
        return {"keys": list(d.keys()), "json_serializable": True}

    runner.run_test("3.8 UserEvent.to_dict()", test_user_event_to_dict)

    # =========================================================================
    # Phase 4: insights() Tests
    # =========================================================================
    print("\n[Phase 4] insights() Tests")
    print("-" * 40)

    # Test 4.1: Basic insights call
    def test_insights_basic() -> dict[str, Any]:
        nonlocal insights_result
        from mixpanel_data.types import InsightsResult

        assert live_query is not None
        insights_result = live_query.insights(bookmark_id=INSIGHTS_BOOKMARK_ID)
        if not isinstance(insights_result, InsightsResult):
            raise TypeError(f"Expected InsightsResult, got {type(insights_result)}")
        return {
            "bookmark_id": insights_result.bookmark_id,
            "computed_at": insights_result.computed_at[:30] + "..."
            if len(insights_result.computed_at) > 30
            else insights_result.computed_at,
            "from_date": insights_result.from_date,
            "to_date": insights_result.to_date,
        }

    runner.run_test("4.1 insights() basic", test_insights_basic)

    # Test 4.2: InsightsResult metadata
    def test_insights_metadata() -> dict[str, Any]:
        if insights_result is None:
            return {"skipped": "No insights result"}
        return {
            "has_computed_at": bool(insights_result.computed_at),
            "has_from_date": bool(insights_result.from_date),
            "has_to_date": bool(insights_result.to_date),
            "headers": insights_result.headers,
            "series_keys": list(insights_result.series.keys())[:5],
        }

    runner.run_test("4.2 InsightsResult metadata", test_insights_metadata)

    # Test 4.3: InsightsResult series structure
    def test_insights_series() -> dict[str, Any]:
        if insights_result is None:
            return {"skipped": "No insights result"}
        series = insights_result.series
        if not isinstance(series, dict):
            raise TypeError(f"series should be dict, got {type(series)}")
        # Check structure: {event: {date: count}}
        for event_name, date_counts in series.items():
            if not isinstance(date_counts, dict):
                raise TypeError(
                    f"date_counts for {event_name} should be dict, got {type(date_counts)}"
                )
            if date_counts:
                first_date = next(iter(date_counts.keys()))
                first_count = date_counts[first_date]
                if not isinstance(first_count, int | float):
                    raise TypeError(f"count should be numeric, got {type(first_count)}")
        return {
            "events_in_series": list(series.keys())[:5],
            "structure": "valid",
        }

    runner.run_test("4.3 InsightsResult series", test_insights_series)

    # Test 4.4: InsightsResult.df
    def test_insights_df() -> dict[str, Any]:
        if insights_result is None:
            return {"skipped": "No insights result"}
        df = insights_result.df
        expected_cols = {"date", "event", "count"}
        actual_cols = set(df.columns)
        if not expected_cols.issubset(actual_cols):
            raise ValueError(f"Missing columns: {expected_cols - actual_cols}")
        return {
            "columns": list(df.columns),
            "rows": len(df),
        }

    runner.run_test("4.4 InsightsResult.df", test_insights_df)

    # Test 4.5: InsightsResult.df caching
    def test_insights_df_caching() -> dict[str, Any]:
        if insights_result is None:
            return {"skipped": "No insights result"}
        df1 = insights_result.df
        df2 = insights_result.df
        if df1 is not df2:
            raise ValueError("DataFrame should be cached (same object)")
        return {"cached": True, "same_object": True}

    runner.run_test("4.5 InsightsResult.df caching", test_insights_df_caching)

    # Test 4.6: InsightsResult.to_dict()
    def test_insights_to_dict() -> dict[str, Any]:
        if insights_result is None:
            return {"skipped": "No insights result"}
        d = insights_result.to_dict()
        expected_keys = {
            "bookmark_id",
            "computed_at",
            "from_date",
            "to_date",
            "headers",
            "series",
        }
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        _ = json.dumps(d)
        return {"keys": list(d.keys()), "json_serializable": True}

    runner.run_test("4.6 InsightsResult.to_dict()", test_insights_to_dict)

    # Test 4.7: Invalid bookmark_id
    def test_insights_invalid_id() -> dict[str, Any]:
        from mixpanel_data.exceptions import QueryError

        assert live_query is not None
        try:
            live_query.insights(bookmark_id=999999999)
            return {"error_raised": False, "note": "No error for invalid bookmark"}
        except QueryError as e:
            return {"error_raised": True, "error_code": e.code}
        except Exception as e:
            return {"error_type": type(e).__name__, "message": str(e)[:50]}

    runner.run_test("4.7 insights() invalid bookmark", test_insights_invalid_id)

    # =========================================================================
    # Phase 5: frequency() Tests
    # =========================================================================
    print("\n[Phase 5] frequency() Tests")
    print("-" * 40)

    # Test 5.1: Basic frequency call
    def test_frequency_basic() -> dict[str, Any]:
        nonlocal frequency_result
        from mixpanel_data.types import FrequencyResult

        assert live_query is not None
        frequency_result = live_query.frequency(
            from_date=FROM_DATE,
            to_date=TO_DATE,
        )
        if not isinstance(frequency_result, FrequencyResult):
            raise TypeError(f"Expected FrequencyResult, got {type(frequency_result)}")
        return {
            "event": frequency_result.event,
            "from_date": frequency_result.from_date,
            "to_date": frequency_result.to_date,
            "unit": frequency_result.unit,
            "addiction_unit": frequency_result.addiction_unit,
            "data_keys": list(frequency_result.data.keys())[:3],
        }

    runner.run_test("5.1 frequency() basic", test_frequency_basic)

    # Test 5.2: FrequencyResult data structure
    def test_frequency_data() -> dict[str, Any]:
        if frequency_result is None:
            return {"skipped": "No frequency result"}
        data = frequency_result.data
        if not isinstance(data, dict):
            raise TypeError(f"data should be dict, got {type(data)}")
        # Check structure: {date: [count_1, count_2, ...]}
        for date_str, counts in data.items():
            if not isinstance(counts, list):
                raise TypeError(f"counts for {date_str} should be list")
            if counts and not isinstance(counts[0], int):
                raise TypeError(f"count values should be int, got {type(counts[0])}")
        # Sample first entry
        sample_date = next(iter(data.keys())) if data else None
        sample_counts = data[sample_date][:5] if sample_date else []
        return {
            "date_count": len(data),
            "sample_date": sample_date,
            "sample_counts": sample_counts,
            "structure": "valid",
        }

    runner.run_test("5.2 FrequencyResult data structure", test_frequency_data)

    # Test 5.3: frequency() with event filter
    def test_frequency_with_event() -> dict[str, Any]:
        assert live_query is not None
        result = live_query.frequency(
            from_date=FROM_DATE,
            to_date=TO_DATE,
            event=NUMERIC_EVENT,
        )
        return {
            "event": result.event,
            "data_keys_count": len(result.data),
        }

    runner.run_test("5.3 frequency() with event", test_frequency_with_event)

    # Test 5.4: frequency() with unit=week
    def test_frequency_unit_week() -> dict[str, Any]:
        assert live_query is not None
        result = live_query.frequency(
            from_date=FROM_DATE,
            to_date=TO_DATE,
            unit="week",
        )
        return {
            "unit": result.unit,
            "data_keys_count": len(result.data),
        }

    runner.run_test("5.4 frequency(unit=week)", test_frequency_unit_week)

    # Test 5.5: frequency() with addiction_unit=day
    def test_frequency_addiction_day() -> dict[str, Any]:
        assert live_query is not None
        result = live_query.frequency(
            from_date=FROM_DATE,
            to_date=TO_DATE,
            addiction_unit="day",
        )
        return {
            "addiction_unit": result.addiction_unit,
            "data_keys_count": len(result.data),
        }

    runner.run_test("5.5 frequency(addiction_unit=day)", test_frequency_addiction_day)

    # Test 5.6: FrequencyResult.df
    def test_frequency_df() -> dict[str, Any]:
        if frequency_result is None:
            return {"skipped": "No frequency result"}
        df = frequency_result.df
        if "date" not in df.columns:
            raise ValueError("Missing 'date' column")
        # Check for period columns
        period_cols = [c for c in df.columns if c.startswith("period_")]
        return {
            "columns": list(df.columns)[:7],
            "rows": len(df),
            "period_columns": len(period_cols),
        }

    runner.run_test("5.6 FrequencyResult.df", test_frequency_df)

    # Test 5.7: FrequencyResult.df caching
    def test_frequency_df_caching() -> dict[str, Any]:
        if frequency_result is None:
            return {"skipped": "No frequency result"}
        df1 = frequency_result.df
        df2 = frequency_result.df
        if df1 is not df2:
            raise ValueError("DataFrame should be cached (same object)")
        return {"cached": True, "same_object": True}

    runner.run_test("5.7 FrequencyResult.df caching", test_frequency_df_caching)

    # Test 5.8: FrequencyResult.to_dict()
    def test_frequency_to_dict() -> dict[str, Any]:
        if frequency_result is None:
            return {"skipped": "No frequency result"}
        d = frequency_result.to_dict()
        expected_keys = {
            "event",
            "from_date",
            "to_date",
            "unit",
            "addiction_unit",
            "data",
        }
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        _ = json.dumps(d)
        return {"keys": list(d.keys()), "json_serializable": True}

    runner.run_test("5.8 FrequencyResult.to_dict()", test_frequency_to_dict)

    # =========================================================================
    # Phase 6: segmentation_numeric() Tests
    # =========================================================================
    print("\n[Phase 6] segmentation_numeric() Tests")
    print("-" * 40)

    # Test 6.1: Basic segmentation_numeric call
    def test_numeric_bucket_basic() -> dict[str, Any]:
        nonlocal numeric_bucket_result
        from mixpanel_data.types import NumericBucketResult

        assert live_query is not None
        numeric_bucket_result = live_query.segmentation_numeric(
            event=NUMERIC_EVENT,
            from_date=FROM_DATE,
            to_date=TO_DATE,
            on=NUMERIC_PROPERTY,
        )
        if not isinstance(numeric_bucket_result, NumericBucketResult):
            raise TypeError(
                f"Expected NumericBucketResult, got {type(numeric_bucket_result)}"
            )
        return {
            "event": numeric_bucket_result.event,
            "from_date": numeric_bucket_result.from_date,
            "to_date": numeric_bucket_result.to_date,
            "property_expr": numeric_bucket_result.property_expr,
            "unit": numeric_bucket_result.unit,
            "buckets": list(numeric_bucket_result.series.keys())[:5],
        }

    runner.run_test("6.1 segmentation_numeric() basic", test_numeric_bucket_basic)

    # Test 6.2: NumericBucketResult series structure
    def test_numeric_bucket_series() -> dict[str, Any]:
        if numeric_bucket_result is None:
            return {"skipped": "No numeric bucket result"}
        series = numeric_bucket_result.series
        if not isinstance(series, dict):
            raise TypeError(f"series should be dict, got {type(series)}")
        # Check structure: {bucket_range: {date: count}}
        for bucket, date_counts in series.items():
            if not isinstance(date_counts, dict):
                raise TypeError(f"date_counts for {bucket} should be dict")
            if date_counts:
                first_date = next(iter(date_counts.keys()))
                first_count = date_counts[first_date]
                if not isinstance(first_count, int | float):
                    raise TypeError(f"count should be numeric, got {type(first_count)}")
        return {
            "bucket_count": len(series),
            "bucket_samples": list(series.keys())[:3],
            "structure": "valid",
        }

    runner.run_test("6.2 NumericBucketResult series", test_numeric_bucket_series)

    # Test 6.3: NumericBucketResult.df
    def test_numeric_bucket_df() -> dict[str, Any]:
        if numeric_bucket_result is None:
            return {"skipped": "No numeric bucket result"}
        df = numeric_bucket_result.df
        expected_cols = {"date", "bucket", "count"}
        actual_cols = set(df.columns)
        if not expected_cols.issubset(actual_cols):
            raise ValueError(f"Missing columns: {expected_cols - actual_cols}")
        return {
            "columns": list(df.columns),
            "rows": len(df),
        }

    runner.run_test("6.3 NumericBucketResult.df", test_numeric_bucket_df)

    # Test 6.4: NumericBucketResult.df caching
    def test_numeric_bucket_df_caching() -> dict[str, Any]:
        if numeric_bucket_result is None:
            return {"skipped": "No numeric bucket result"}
        df1 = numeric_bucket_result.df
        df2 = numeric_bucket_result.df
        if df1 is not df2:
            raise ValueError("DataFrame should be cached (same object)")
        return {"cached": True, "same_object": True}

    runner.run_test(
        "6.4 NumericBucketResult.df caching", test_numeric_bucket_df_caching
    )

    # Test 6.5: NumericBucketResult.to_dict()
    def test_numeric_bucket_to_dict() -> dict[str, Any]:
        if numeric_bucket_result is None:
            return {"skipped": "No numeric bucket result"}
        d = numeric_bucket_result.to_dict()
        expected_keys = {
            "event",
            "from_date",
            "to_date",
            "property_expr",
            "unit",
            "series",
        }
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        _ = json.dumps(d)
        return {"keys": list(d.keys()), "json_serializable": True}

    runner.run_test("6.5 NumericBucketResult.to_dict()", test_numeric_bucket_to_dict)

    # =========================================================================
    # Phase 7: segmentation_sum() Tests
    # =========================================================================
    print("\n[Phase 7] segmentation_sum() Tests")
    print("-" * 40)

    # Test 7.1: Basic segmentation_sum call
    def test_numeric_sum_basic() -> dict[str, Any]:
        nonlocal numeric_sum_result
        from mixpanel_data.types import NumericSumResult

        assert live_query is not None
        numeric_sum_result = live_query.segmentation_sum(
            event=NUMERIC_EVENT,
            from_date=FROM_DATE,
            to_date=TO_DATE,
            on=NUMERIC_PROPERTY,
        )
        if not isinstance(numeric_sum_result, NumericSumResult):
            raise TypeError(
                f"Expected NumericSumResult, got {type(numeric_sum_result)}"
            )
        return {
            "event": numeric_sum_result.event,
            "from_date": numeric_sum_result.from_date,
            "to_date": numeric_sum_result.to_date,
            "property_expr": numeric_sum_result.property_expr,
            "unit": numeric_sum_result.unit,
            "computed_at": numeric_sum_result.computed_at,
            "result_dates": list(numeric_sum_result.results.keys())[:5],
        }

    runner.run_test("7.1 segmentation_sum() basic", test_numeric_sum_basic)

    # Test 7.2: NumericSumResult results structure
    def test_numeric_sum_results() -> dict[str, Any]:
        if numeric_sum_result is None:
            return {"skipped": "No numeric sum result"}
        results = numeric_sum_result.results
        if not isinstance(results, dict):
            raise TypeError(f"results should be dict, got {type(results)}")
        # Check structure: {date: sum_value}
        for _date_str, value in results.items():
            if not isinstance(value, int | float):
                raise TypeError(f"sum value should be numeric, got {type(value)}")
        # Sample values
        sample_dates = list(results.keys())[:3]
        sample_values = [results[d] for d in sample_dates]
        return {
            "date_count": len(results),
            "sample_dates": sample_dates,
            "sample_sums": sample_values,
            "structure": "valid",
        }

    runner.run_test("7.2 NumericSumResult results", test_numeric_sum_results)

    # Test 7.3: NumericSumResult.df
    def test_numeric_sum_df() -> dict[str, Any]:
        if numeric_sum_result is None:
            return {"skipped": "No numeric sum result"}
        df = numeric_sum_result.df
        expected_cols = {"date", "sum"}
        actual_cols = set(df.columns)
        if not expected_cols.issubset(actual_cols):
            raise ValueError(f"Missing columns: {expected_cols - actual_cols}")
        return {
            "columns": list(df.columns),
            "rows": len(df),
        }

    runner.run_test("7.3 NumericSumResult.df", test_numeric_sum_df)

    # Test 7.4: NumericSumResult.df caching
    def test_numeric_sum_df_caching() -> dict[str, Any]:
        if numeric_sum_result is None:
            return {"skipped": "No numeric sum result"}
        df1 = numeric_sum_result.df
        df2 = numeric_sum_result.df
        if df1 is not df2:
            raise ValueError("DataFrame should be cached (same object)")
        return {"cached": True, "same_object": True}

    runner.run_test("7.4 NumericSumResult.df caching", test_numeric_sum_df_caching)

    # Test 7.5: NumericSumResult.to_dict()
    def test_numeric_sum_to_dict() -> dict[str, Any]:
        if numeric_sum_result is None:
            return {"skipped": "No numeric sum result"}
        d = numeric_sum_result.to_dict()
        expected_keys = {
            "event",
            "from_date",
            "to_date",
            "property_expr",
            "unit",
            "results",
        }
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        _ = json.dumps(d)
        return {"keys": list(d.keys()), "json_serializable": True}

    runner.run_test("7.5 NumericSumResult.to_dict()", test_numeric_sum_to_dict)

    # =========================================================================
    # Phase 8: segmentation_average() Tests
    # =========================================================================
    print("\n[Phase 8] segmentation_average() Tests")
    print("-" * 40)

    # Test 8.1: Basic segmentation_average call
    def test_numeric_avg_basic() -> dict[str, Any]:
        nonlocal numeric_avg_result
        from mixpanel_data.types import NumericAverageResult

        assert live_query is not None
        numeric_avg_result = live_query.segmentation_average(
            event=NUMERIC_EVENT,
            from_date=FROM_DATE,
            to_date=TO_DATE,
            on=NUMERIC_PROPERTY,
        )
        if not isinstance(numeric_avg_result, NumericAverageResult):
            raise TypeError(
                f"Expected NumericAverageResult, got {type(numeric_avg_result)}"
            )
        return {
            "event": numeric_avg_result.event,
            "from_date": numeric_avg_result.from_date,
            "to_date": numeric_avg_result.to_date,
            "property_expr": numeric_avg_result.property_expr,
            "unit": numeric_avg_result.unit,
            "result_dates": list(numeric_avg_result.results.keys())[:5],
        }

    runner.run_test("8.1 segmentation_average() basic", test_numeric_avg_basic)

    # Test 8.2: NumericAverageResult results structure
    def test_numeric_avg_results() -> dict[str, Any]:
        if numeric_avg_result is None:
            return {"skipped": "No numeric average result"}
        results = numeric_avg_result.results
        if not isinstance(results, dict):
            raise TypeError(f"results should be dict, got {type(results)}")
        # Check structure: {date: average_value} - None is valid for no data
        numeric_count = 0
        none_count = 0
        for _date_str, value in results.items():
            if value is None:
                none_count += 1
            elif isinstance(value, int | float):
                numeric_count += 1
            else:
                raise TypeError(
                    f"average value should be numeric or None, got {type(value)}"
                )
        # Sample non-None values
        sample_dates = list(results.keys())[:5]
        sample_values = [
            f"{results[d]:.2f}" if results[d] is not None else "None"
            for d in sample_dates
        ]
        return {
            "date_count": len(results),
            "numeric_values": numeric_count,
            "none_values": none_count,
            "sample_dates": sample_dates,
            "sample_averages": sample_values,
            "structure": "valid",
        }

    runner.run_test("8.2 NumericAverageResult results", test_numeric_avg_results)

    # Test 8.3: NumericAverageResult.df
    def test_numeric_avg_df() -> dict[str, Any]:
        if numeric_avg_result is None:
            return {"skipped": "No numeric average result"}
        df = numeric_avg_result.df
        expected_cols = {"date", "average"}
        actual_cols = set(df.columns)
        if not expected_cols.issubset(actual_cols):
            raise ValueError(f"Missing columns: {expected_cols - actual_cols}")
        return {
            "columns": list(df.columns),
            "rows": len(df),
        }

    runner.run_test("8.3 NumericAverageResult.df", test_numeric_avg_df)

    # Test 8.4: NumericAverageResult.df caching
    def test_numeric_avg_df_caching() -> dict[str, Any]:
        if numeric_avg_result is None:
            return {"skipped": "No numeric average result"}
        df1 = numeric_avg_result.df
        df2 = numeric_avg_result.df
        if df1 is not df2:
            raise ValueError("DataFrame should be cached (same object)")
        return {"cached": True, "same_object": True}

    runner.run_test("8.4 NumericAverageResult.df caching", test_numeric_avg_df_caching)

    # Test 8.5: NumericAverageResult.to_dict()
    def test_numeric_avg_to_dict() -> dict[str, Any]:
        if numeric_avg_result is None:
            return {"skipped": "No numeric average result"}
        d = numeric_avg_result.to_dict()
        expected_keys = {
            "event",
            "from_date",
            "to_date",
            "property_expr",
            "unit",
            "results",
        }
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        _ = json.dumps(d)
        return {"keys": list(d.keys()), "json_serializable": True}

    runner.run_test("8.5 NumericAverageResult.to_dict()", test_numeric_avg_to_dict)

    # =========================================================================
    # Phase 9: Cross-Cutting Tests
    # =========================================================================
    print("\n[Phase 9] Cross-Cutting Tests")
    print("-" * 40)

    # Test 9.1: All result types JSON serializable
    def test_all_json_serializable() -> dict[str, Any]:
        results_to_check = [
            ("ActivityFeedResult", activity_result),
            ("InsightsResult", insights_result),
            ("FrequencyResult", frequency_result),
            ("NumericBucketResult", numeric_bucket_result),
            ("NumericSumResult", numeric_sum_result),
            ("NumericAverageResult", numeric_avg_result),
        ]
        serializable = []
        for name, result in results_to_check:
            if result is not None:
                try:
                    d = result.to_dict()
                    _ = json.dumps(d)
                    serializable.append(name)
                except Exception as e:
                    raise ValueError(f"{name} not JSON serializable: {e}") from e
        return {"serializable_types": serializable}

    runner.run_test("9.1 All results JSON serializable", test_all_json_serializable)

    # =========================================================================
    # Phase 10: Error Handling Tests
    # =========================================================================
    print("\n[Phase 10] Error Handling Tests")
    print("-" * 40)

    # Test 10.1: activity_feed with empty list
    def test_activity_feed_empty_list() -> dict[str, Any]:
        assert live_query is not None
        try:
            result = live_query.activity_feed(distinct_ids=[])
            return {
                "accepted": True,
                "event_count": len(result.events),
            }
        except Exception as e:
            return {"error_type": type(e).__name__, "message": str(e)[:50]}

    runner.run_test("10.1 activity_feed() empty list", test_activity_feed_empty_list)

    # =========================================================================
    # Phase 11: Cleanup
    # =========================================================================
    print("\n[Phase 11] Cleanup")
    print("-" * 40)

    def test_cleanup() -> dict[str, Any]:
        nonlocal api_client
        if api_client:
            api_client.__exit__(None, None, None)
            api_client = None
        return {"status": "cleaned up"}

    runner.run_test("Cleanup API client", test_cleanup)

    # =========================================================================
    # Results
    # =========================================================================
    runner.print_results()

    # Return exit code
    failed = sum(1 for r in runner.results if not r.passed)
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
