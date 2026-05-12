#!/usr/bin/env python3
"""Live QA integration test for Workspace Facade.

This script performs real API calls against Mixpanel to verify the
Workspace facade class which is the unified entry point for all
Mixpanel data operations.

Tests:
- Construction modes (standard, context manager)
- Discovery methods (events, properties, funnels, cohorts, top_events)
- Streaming methods (stream_events, stream_profiles)
- Live query methods (segmentation, funnel, retention, jql, etc.)
- Escape hatches (api)
- Error handling (ConfigError, AccountNotFoundError)

Usage:
    uv run python scripts/qa_workspace.py

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
    from mixpanel_headless.types import (
        ActivityFeedResult,
        EventCountsResult,
        FrequencyResult,
        FunnelInfo,
        FunnelResult,
        InsightsResult,
        JQLResult,
        NumericAverageResult,
        NumericBucketResult,
        NumericSumResult,
        PropertyCountsResult,
        RetentionResult,
        SegmentationResult,
    )
    from mixpanel_headless.workspace import Workspace


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
        print("QA TEST RESULTS - Workspace Facade")
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
    print("Workspace Facade QA - Live Integration Tests")
    print("=" * 70)

    runner = QARunner()

    # Shared state
    ws: Workspace | None = None

    # Account to use
    ACCOUNT_NAME = "sinkapp-prod"

    # Known test data (from existing QA scripts)
    # Use "Added Entity" as the main event since it has data in sinkapp-prod
    KNOWN_EVENT = "Added Entity"
    NUMERIC_EVENT = "Added Entity"
    KNOWN_PROPERTY = "$screen_height"
    NUMERIC_PROPERTY = 'properties["$screen_height"]'
    INSIGHTS_BOOKMARK_ID = 44592511
    ACTIVITY_DISTINCT_ID = "$device:60FB1D2E-2BE7-45AD-8887-53C397DE6234"

    # Date range for testing (previous month)
    today = datetime.now()
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    FROM_DATE = last_month_start.strftime("%Y-%m-%d")
    TO_DATE = last_month_end.strftime("%Y-%m-%d")

    print(f"Using date range: {FROM_DATE} to {TO_DATE}")
    print(f"Using account: {ACCOUNT_NAME}")
    print(f"Known event: {KNOWN_EVENT}")
    print(f"Numeric test: event={NUMERIC_EVENT}, property={NUMERIC_PROPERTY}")

    # Stored results for later tests
    discovered_funnels: list[FunnelInfo] = []
    segmentation_result: SegmentationResult | None = None
    event_counts_result: EventCountsResult | None = None
    property_counts_result: PropertyCountsResult | None = None
    funnel_result: FunnelResult | None = None
    retention_result: RetentionResult | None = None
    jql_result: JQLResult | None = None
    activity_result: ActivityFeedResult | None = None
    insights_result: InsightsResult | None = None
    frequency_result: FrequencyResult | None = None
    numeric_bucket_result: NumericBucketResult | None = None
    numeric_sum_result: NumericSumResult | None = None
    numeric_avg_result: NumericAverageResult | None = None

    # =========================================================================
    # Phase 1: Prerequisites & Imports
    # =========================================================================
    print("\n[Phase 1] Prerequisites & Imports")
    print("-" * 40)

    # Test 1.1: Import Workspace from public API
    def test_import_workspace() -> dict[str, Any]:
        from mixpanel_headless import Workspace  # noqa: F401

        return {"module": "mixpanel_headless.Workspace imported successfully"}

    result = runner.run_test("1.1 Import Workspace", test_import_workspace)
    if not result.passed:
        print("Cannot continue - import failed")
        runner.print_results()
        return 1

    # Test 1.2: Import result types
    def test_import_types() -> dict[str, Any]:
        from mixpanel_headless.types import (
            ActivityFeedResult,  # noqa: F401
            EventCountsResult,  # noqa: F401
            FrequencyResult,  # noqa: F401
            FunnelInfo,  # noqa: F401
            FunnelResult,  # noqa: F401
            InsightsResult,  # noqa: F401
            JQLResult,  # noqa: F401
            NumericAverageResult,  # noqa: F401
            NumericBucketResult,  # noqa: F401
            NumericSumResult,  # noqa: F401
            PropertyCountsResult,  # noqa: F401
            RetentionResult,  # noqa: F401
            SavedCohort,  # noqa: F401
            SegmentationResult,  # noqa: F401
            TopEvent,  # noqa: F401
            WorkspaceInfo,  # noqa: F401
        )

        return {"types": "All result types imported successfully"}

    runner.run_test("1.2 Import result types", test_import_types)

    # Test 1.3: Import exceptions
    def test_import_exceptions() -> dict[str, Any]:
        from mixpanel_headless.exceptions import (
            AccountNotFoundError,  # noqa: F401
            ConfigError,  # noqa: F401
        )

        return {"exceptions": "All exception types imported successfully"}

    runner.run_test("1.3 Import exceptions", test_import_exceptions)

    # Test 1.4: Verify account exists
    def test_verify_account() -> dict[str, Any]:
        from mixpanel_headless._internal.config import ConfigManager

        config = ConfigManager()
        creds = config.resolve_credentials(account=ACCOUNT_NAME)
        return {
            "account": ACCOUNT_NAME,
            "project_id": creds.project_id,
            "region": creds.region,
        }

    result = runner.run_test("1.4 Verify account exists", test_verify_account)
    if not result.passed:
        print("Cannot continue - account not configured")
        runner.print_results()
        return 1

    # =========================================================================
    # Phase 2: Construction Modes
    # =========================================================================
    print("\n[Phase 2] Construction Modes")
    print("-" * 40)

    # Test 2.1: Standard construction
    def test_standard_construction() -> dict[str, Any]:
        nonlocal ws
        from mixpanel_headless import Workspace

        ws = Workspace(account=ACCOUNT_NAME)
        return {
            "created": True,
        }

    result = runner.run_test("2.1 Standard construction", test_standard_construction)
    if not result.passed:
        print("Cannot continue - workspace creation failed")
        runner.print_results()
        return 1

    # Test 2.2: Context manager
    def test_context_manager() -> dict[str, Any]:
        from mixpanel_headless import Workspace

        with Workspace(account=ACCOUNT_NAME) as ctx_ws:
            events = ctx_ws.events()
        return {
            "context_worked": True,
            "events_discovered": len(events),
        }

    runner.run_test("2.2 Context manager", test_context_manager)

    # Test 2.3: Error - Invalid account
    def test_invalid_account_error() -> dict[str, Any]:
        from mixpanel_headless import Workspace
        from mixpanel_headless.exceptions import AccountNotFoundError

        try:
            Workspace(account="nonexistent_account_xyz_12345")
            raise AssertionError("Should have raised AccountNotFoundError")
        except AccountNotFoundError as e:
            return {"error_code": e.code, "raised": True}

    runner.run_test("2.3 Error: Invalid account", test_invalid_account_error)

    # =========================================================================
    # Phase 3: Discovery Methods
    # =========================================================================
    print("\n[Phase 3] Discovery Methods")
    print("-" * 40)

    # Test 3.1: events()
    def test_events() -> dict[str, Any]:
        assert ws is not None
        events = ws.events()
        if not isinstance(events, list):
            raise TypeError(f"Expected list, got {type(events)}")
        # Check sorted
        is_sorted = events == sorted(events)
        return {
            "count": len(events),
            "is_sorted": is_sorted,
            "sample": events[:5] if events else [],
        }

    runner.run_test("3.1 events()", test_events)

    # Test 3.2: properties()
    def test_properties() -> dict[str, Any]:
        assert ws is not None
        props = ws.properties(KNOWN_EVENT)
        if not isinstance(props, list):
            raise TypeError(f"Expected list, got {type(props)}")
        is_sorted = props == sorted(props)
        return {
            "event": KNOWN_EVENT,
            "count": len(props),
            "is_sorted": is_sorted,
            "sample": props[:5] if props else [],
        }

    runner.run_test("3.2 properties()", test_properties)

    # Test 3.3: property_values()
    def test_property_values() -> dict[str, Any]:
        assert ws is not None
        values = ws.property_values(KNOWN_PROPERTY, event=KNOWN_EVENT, limit=10)
        if not isinstance(values, list):
            raise TypeError(f"Expected list, got {type(values)}")
        return {
            "property": KNOWN_PROPERTY,
            "event": KNOWN_EVENT,
            "count": len(values),
            "sample": values[:5] if values else [],
        }

    runner.run_test("3.3 property_values()", test_property_values)

    # Test 3.4: funnels()
    def test_funnels() -> dict[str, Any]:
        nonlocal discovered_funnels
        from mixpanel_headless.types import FunnelInfo

        assert ws is not None
        funnels = ws.funnels()
        if not isinstance(funnels, list):
            raise TypeError(f"Expected list, got {type(funnels)}")
        if funnels and not isinstance(funnels[0], FunnelInfo):
            raise TypeError(f"Expected FunnelInfo, got {type(funnels[0])}")
        discovered_funnels = funnels
        return {
            "count": len(funnels),
            "sample": [f.name for f in funnels[:3]] if funnels else [],
        }

    runner.run_test("3.4 funnels()", test_funnels)

    # Test 3.5: cohorts()
    def test_cohorts() -> dict[str, Any]:
        from mixpanel_headless.types import SavedCohort

        assert ws is not None
        cohorts = ws.cohorts()
        if not isinstance(cohorts, list):
            raise TypeError(f"Expected list, got {type(cohorts)}")
        if cohorts and not isinstance(cohorts[0], SavedCohort):
            raise TypeError(f"Expected SavedCohort, got {type(cohorts[0])}")
        return {
            "count": len(cohorts),
            "sample": [c.name for c in cohorts[:3]] if cohorts else [],
        }

    runner.run_test("3.5 cohorts()", test_cohorts)

    # Test 3.6: top_events()
    def test_top_events() -> dict[str, Any]:
        from mixpanel_headless.types import TopEvent

        assert ws is not None
        top = ws.top_events(limit=5)
        if not isinstance(top, list):
            raise TypeError(f"Expected list, got {type(top)}")
        if top and not isinstance(top[0], TopEvent):
            raise TypeError(f"Expected TopEvent, got {type(top[0])}")
        return {
            "count": len(top),
            "events": [t.event for t in top],
        }

    runner.run_test("3.6 top_events()", test_top_events)

    # Test 3.7: clear_discovery_cache()
    def test_clear_discovery_cache() -> dict[str, Any]:
        assert ws is not None
        # Call events to populate cache
        ws.events()
        # Clear cache
        ws.clear_discovery_cache()
        # Verify by accessing internal service (cache should be empty)
        cache_cleared = len(ws._discovery_service._cache) == 0
        return {
            "cleared": cache_cleared,
        }

    runner.run_test("3.7 clear_discovery_cache()", test_clear_discovery_cache)

    # =========================================================================
    # Phase 4: Live Query Methods
    # =========================================================================
    print("\n[Phase 4] Live Query Methods")
    print("-" * 40)

    # Test 4.1: segmentation()
    def test_segmentation() -> dict[str, Any]:
        nonlocal segmentation_result
        from mixpanel_headless.types import SegmentationResult

        assert ws is not None
        segmentation_result = ws.segmentation(
            event=KNOWN_EVENT,
            from_date=FROM_DATE,
            to_date=TO_DATE,
        )
        if not isinstance(segmentation_result, SegmentationResult):
            raise TypeError(
                f"Expected SegmentationResult, got {type(segmentation_result)}"
            )
        return {
            "event": segmentation_result.event,
            "total": segmentation_result.total,
            "unit": segmentation_result.unit,
            "series_keys": list(segmentation_result.series.keys())[:3],
        }

    runner.run_test("4.1 segmentation()", test_segmentation)

    # Test 4.2: event_counts()
    def test_event_counts() -> dict[str, Any]:
        nonlocal event_counts_result
        from mixpanel_headless.types import EventCountsResult

        assert ws is not None
        event_counts_result = ws.event_counts(
            events=[KNOWN_EVENT],
            from_date=FROM_DATE,
            to_date=TO_DATE,
        )
        if not isinstance(event_counts_result, EventCountsResult):
            raise TypeError(
                f"Expected EventCountsResult, got {type(event_counts_result)}"
            )
        return {
            "events": event_counts_result.events,
            "unit": event_counts_result.unit,
            "series_keys": list(event_counts_result.series.keys()),
        }

    runner.run_test("4.2 event_counts()", test_event_counts)

    # Test 4.3: property_counts()
    def test_property_counts() -> dict[str, Any]:
        nonlocal property_counts_result
        from mixpanel_headless.types import PropertyCountsResult

        assert ws is not None
        property_counts_result = ws.property_counts(
            event=KNOWN_EVENT,
            property_name=KNOWN_PROPERTY,
            from_date=FROM_DATE,
            to_date=TO_DATE,
            limit=5,
        )
        if not isinstance(property_counts_result, PropertyCountsResult):
            raise TypeError(
                f"Expected PropertyCountsResult, got {type(property_counts_result)}"
            )
        return {
            "event": property_counts_result.event,
            "property": property_counts_result.property_name,
            "series_keys": list(property_counts_result.series.keys())[:5],
        }

    runner.run_test("4.3 property_counts()", test_property_counts)

    # Test 4.4: funnel() - only if funnels exist
    def test_funnel() -> dict[str, Any]:
        nonlocal funnel_result
        from mixpanel_headless.types import FunnelResult

        assert ws is not None
        if not discovered_funnels:
            return {"skipped": "No funnels available"}

        funnel_id = discovered_funnels[0].funnel_id
        funnel_result = ws.funnel(
            funnel_id=funnel_id,
            from_date=FROM_DATE,
            to_date=TO_DATE,
        )
        if not isinstance(funnel_result, FunnelResult):
            raise TypeError(f"Expected FunnelResult, got {type(funnel_result)}")
        return {
            "funnel_id": funnel_result.funnel_id,
            "funnel_name": funnel_result.funnel_name,
            "conversion_rate": f"{funnel_result.conversion_rate:.2%}",
            "steps": len(funnel_result.steps),
        }

    runner.run_test("4.4 funnel()", test_funnel)

    # Test 4.5: retention()
    def test_retention() -> dict[str, Any]:
        nonlocal retention_result
        from mixpanel_headless.types import RetentionResult

        assert ws is not None
        retention_result = ws.retention(
            born_event=KNOWN_EVENT,
            return_event=KNOWN_EVENT,
            from_date=FROM_DATE,
            to_date=TO_DATE,
            interval_count=5,
        )
        if not isinstance(retention_result, RetentionResult):
            raise TypeError(f"Expected RetentionResult, got {type(retention_result)}")
        return {
            "born_event": retention_result.born_event,
            "return_event": retention_result.return_event,
            "unit": retention_result.unit,
            "cohorts": len(retention_result.cohorts),
        }

    runner.run_test("4.5 retention()", test_retention)

    # Test 4.6: jql()
    def test_jql() -> dict[str, Any]:
        nonlocal jql_result
        from mixpanel_headless.types import JQLResult

        assert ws is not None
        script = f"""
        function main() {{
            return Events({{
                from_date: "{FROM_DATE}",
                to_date: "{TO_DATE}"
            }})
            .groupBy(["name"], mixpanel.reducer.count())
            .filter(function(r) {{ return r.value > 0; }});
        }}
        """
        jql_result = ws.jql(script=script)
        if not isinstance(jql_result, JQLResult):
            raise TypeError(f"Expected JQLResult, got {type(jql_result)}")
        return {
            "raw_count": len(jql_result.raw),
            "sample": jql_result.raw[:3] if jql_result.raw else [],
        }

    runner.run_test("4.6 jql()", test_jql)

    # Test 4.7: activity_feed()
    def test_activity_feed() -> dict[str, Any]:
        nonlocal activity_result
        from mixpanel_headless.types import ActivityFeedResult

        assert ws is not None
        activity_result = ws.activity_feed(
            distinct_ids=[ACTIVITY_DISTINCT_ID],
        )
        if not isinstance(activity_result, ActivityFeedResult):
            raise TypeError(f"Expected ActivityFeedResult, got {type(activity_result)}")
        return {
            "distinct_ids": activity_result.distinct_ids,
            "event_count": len(activity_result.events),
        }

    runner.run_test("4.7 activity_feed()", test_activity_feed)

    # Test 4.8: insights()
    def test_insights() -> dict[str, Any]:
        nonlocal insights_result
        from mixpanel_headless.types import InsightsResult

        assert ws is not None
        insights_result = ws.insights(bookmark_id=INSIGHTS_BOOKMARK_ID)
        if not isinstance(insights_result, InsightsResult):
            raise TypeError(f"Expected InsightsResult, got {type(insights_result)}")
        return {
            "bookmark_id": insights_result.bookmark_id,
            "from_date": insights_result.from_date,
            "to_date": insights_result.to_date,
            "series_keys": list(insights_result.series.keys())[:3],
        }

    runner.run_test("4.8 insights()", test_insights)

    # Test 4.9: frequency()
    def test_frequency() -> dict[str, Any]:
        nonlocal frequency_result
        from mixpanel_headless.types import FrequencyResult

        assert ws is not None
        frequency_result = ws.frequency(
            from_date=FROM_DATE,
            to_date=TO_DATE,
            event=KNOWN_EVENT,
        )
        if not isinstance(frequency_result, FrequencyResult):
            raise TypeError(f"Expected FrequencyResult, got {type(frequency_result)}")
        return {
            "event": frequency_result.event,
            "unit": frequency_result.unit,
            "addiction_unit": frequency_result.addiction_unit,
            "data_keys": list(frequency_result.data.keys())[:3],
        }

    runner.run_test("4.9 frequency()", test_frequency)

    # Test 4.10: segmentation_numeric()
    def test_segmentation_numeric() -> dict[str, Any]:
        nonlocal numeric_bucket_result
        from mixpanel_headless.types import NumericBucketResult

        assert ws is not None
        numeric_bucket_result = ws.segmentation_numeric(
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
            "property_expr": numeric_bucket_result.property_expr,
            "buckets": list(numeric_bucket_result.series.keys())[:3],
        }

    runner.run_test("4.10 segmentation_numeric()", test_segmentation_numeric)

    # Test 4.11: segmentation_sum()
    def test_segmentation_sum() -> dict[str, Any]:
        nonlocal numeric_sum_result
        from mixpanel_headless.types import NumericSumResult

        assert ws is not None
        numeric_sum_result = ws.segmentation_sum(
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
            "property_expr": numeric_sum_result.property_expr,
            "result_dates": list(numeric_sum_result.results.keys())[:3],
        }

    runner.run_test("4.11 segmentation_sum()", test_segmentation_sum)

    # Test 4.12: segmentation_average()
    def test_segmentation_average() -> dict[str, Any]:
        nonlocal numeric_avg_result
        from mixpanel_headless.types import NumericAverageResult

        assert ws is not None
        numeric_avg_result = ws.segmentation_average(
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
            "property_expr": numeric_avg_result.property_expr,
            "result_dates": list(numeric_avg_result.results.keys())[:3],
        }

    runner.run_test("4.12 segmentation_average()", test_segmentation_average)

    # =========================================================================
    # Phase 5: Result Type Validation
    # =========================================================================
    print("\n[Phase 5] Result Type Validation")
    print("-" * 40)

    # Test 5.1: SegmentationResult.df
    def test_segmentation_df() -> dict[str, Any]:
        if segmentation_result is None:
            return {"skipped": "No segmentation result"}
        df = segmentation_result.df
        expected = {"date", "segment", "count"}
        actual = set(df.columns)
        if not expected.issubset(actual):
            raise ValueError(f"Missing columns: {expected - actual}")
        # Test caching
        df2 = segmentation_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {"columns": list(df.columns), "rows": len(df), "cached": True}

    runner.run_test("5.1 SegmentationResult.df", test_segmentation_df)

    # Test 5.2: EventCountsResult.df
    def test_event_counts_df() -> dict[str, Any]:
        if event_counts_result is None:
            return {"skipped": "No event counts result"}
        df = event_counts_result.df
        expected = {"date", "event", "count"}
        actual = set(df.columns)
        if not expected.issubset(actual):
            raise ValueError(f"Missing columns: {expected - actual}")
        df2 = event_counts_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {"columns": list(df.columns), "rows": len(df), "cached": True}

    runner.run_test("5.2 EventCountsResult.df", test_event_counts_df)

    # Test 5.3: PropertyCountsResult.df
    def test_property_counts_df() -> dict[str, Any]:
        if property_counts_result is None:
            return {"skipped": "No property counts result"}
        df = property_counts_result.df
        expected = {"date", "value", "count"}
        actual = set(df.columns)
        if not expected.issubset(actual):
            raise ValueError(f"Missing columns: {expected - actual}")
        df2 = property_counts_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {"columns": list(df.columns), "rows": len(df), "cached": True}

    runner.run_test("5.3 PropertyCountsResult.df", test_property_counts_df)

    # Test 5.4: FunnelResult.df
    def test_funnel_df() -> dict[str, Any]:
        if funnel_result is None:
            return {"skipped": "No funnel result"}
        df = funnel_result.df
        expected = {"step", "event", "count", "conversion_rate"}
        actual = set(df.columns)
        if not expected.issubset(actual):
            raise ValueError(f"Missing columns: {expected - actual}")
        df2 = funnel_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {"columns": list(df.columns), "rows": len(df), "cached": True}

    runner.run_test("5.4 FunnelResult.df", test_funnel_df)

    # Test 5.5: RetentionResult.df
    def test_retention_df() -> dict[str, Any]:
        if retention_result is None:
            return {"skipped": "No retention result"}
        df = retention_result.df
        expected = {"cohort_date", "cohort_size"}
        actual = set(df.columns)
        if not expected.issubset(actual):
            raise ValueError(f"Missing columns: {expected - actual}")
        df2 = retention_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {"columns": list(df.columns)[:5], "rows": len(df), "cached": True}

    runner.run_test("5.5 RetentionResult.df", test_retention_df)

    # Test 5.6: JQLResult.df
    def test_jql_df() -> dict[str, Any]:
        if jql_result is None:
            return {"skipped": "No JQL result"}
        df = jql_result.df
        df2 = jql_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {"columns": list(df.columns), "rows": len(df), "cached": True}

    runner.run_test("5.6 JQLResult.df", test_jql_df)

    # Test 5.7: ActivityFeedResult.df
    def test_activity_feed_df() -> dict[str, Any]:
        if activity_result is None:
            return {"skipped": "No activity result"}
        df = activity_result.df
        expected = {"event", "time", "distinct_id"}
        actual = set(df.columns)
        if not expected.issubset(actual):
            raise ValueError(f"Missing columns: {expected - actual}")
        df2 = activity_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {"columns": list(df.columns)[:5], "rows": len(df), "cached": True}

    runner.run_test("5.7 ActivityFeedResult.df", test_activity_feed_df)

    # Test 5.8: InsightsResult.df
    def test_insights_df() -> dict[str, Any]:
        if insights_result is None:
            return {"skipped": "No insights result"}
        df = insights_result.df
        expected = {"date", "event", "count"}
        actual = set(df.columns)
        if not expected.issubset(actual):
            raise ValueError(f"Missing columns: {expected - actual}")
        df2 = insights_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {"columns": list(df.columns), "rows": len(df), "cached": True}

    runner.run_test("5.8 InsightsResult.df", test_insights_df)

    # Test 5.9: FrequencyResult.df
    def test_frequency_df() -> dict[str, Any]:
        if frequency_result is None:
            return {"skipped": "No frequency result"}
        df = frequency_result.df
        if "date" not in df.columns:
            raise ValueError("Missing 'date' column")
        df2 = frequency_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {"columns": list(df.columns)[:5], "rows": len(df), "cached": True}

    runner.run_test("5.9 FrequencyResult.df", test_frequency_df)

    # Test 5.10: NumericBucketResult.df
    def test_numeric_bucket_df() -> dict[str, Any]:
        if numeric_bucket_result is None:
            return {"skipped": "No numeric bucket result"}
        df = numeric_bucket_result.df
        expected = {"date", "bucket", "count"}
        actual = set(df.columns)
        if not expected.issubset(actual):
            raise ValueError(f"Missing columns: {expected - actual}")
        df2 = numeric_bucket_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {"columns": list(df.columns), "rows": len(df), "cached": True}

    runner.run_test("5.10 NumericBucketResult.df", test_numeric_bucket_df)

    # Test 5.11: NumericSumResult.df
    def test_numeric_sum_df() -> dict[str, Any]:
        if numeric_sum_result is None:
            return {"skipped": "No numeric sum result"}
        df = numeric_sum_result.df
        expected = {"date", "sum"}
        actual = set(df.columns)
        if not expected.issubset(actual):
            raise ValueError(f"Missing columns: {expected - actual}")
        df2 = numeric_sum_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {"columns": list(df.columns), "rows": len(df), "cached": True}

    runner.run_test("5.11 NumericSumResult.df", test_numeric_sum_df)

    # Test 5.12: NumericAverageResult.df
    def test_numeric_avg_df() -> dict[str, Any]:
        if numeric_avg_result is None:
            return {"skipped": "No numeric average result"}
        df = numeric_avg_result.df
        expected = {"date", "average"}
        actual = set(df.columns)
        if not expected.issubset(actual):
            raise ValueError(f"Missing columns: {expected - actual}")
        df2 = numeric_avg_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {"columns": list(df.columns), "rows": len(df), "cached": True}

    runner.run_test("5.12 NumericAverageResult.df", test_numeric_avg_df)

    # Test 5.13: All results JSON serializable
    def test_all_json_serializable() -> dict[str, Any]:
        results_to_check = [
            ("SegmentationResult", segmentation_result),
            ("EventCountsResult", event_counts_result),
            ("PropertyCountsResult", property_counts_result),
            ("FunnelResult", funnel_result),
            ("RetentionResult", retention_result),
            ("JQLResult", jql_result),
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

    runner.run_test("5.13 All results JSON serializable", test_all_json_serializable)

    # =========================================================================
    # Phase 6: Escape Hatches
    # =========================================================================
    print("\n[Phase 6] Escape Hatches")
    print("-" * 40)

    # Test 6.1: .api property
    def test_api_property() -> dict[str, Any]:
        from mixpanel_headless._internal.api_client import MixpanelAPIClient

        assert ws is not None
        api = ws.api
        if not isinstance(api, MixpanelAPIClient):
            raise TypeError(f"Expected MixpanelAPIClient, got {type(api)}")
        return {
            "type": type(api).__name__,
            "has_credentials": api._credentials is not None,
        }

    runner.run_test("6.1 .api property", test_api_property)

    # =========================================================================
    # Phase 7: Cleanup
    # =========================================================================
    print("\n[Phase 7] Cleanup")
    print("-" * 40)

    # Test 7.1: Close workspace
    def test_close_workspace() -> dict[str, Any]:
        nonlocal ws
        assert ws is not None
        ws.close()
        # Verify close is idempotent
        ws.close()
        ws = None
        return {"closed": True, "idempotent": True}

    runner.run_test("7.1 Close workspace", test_close_workspace)

    # =========================================================================
    # Results
    # =========================================================================
    runner.print_results()

    # Return exit code
    failed = sum(1 for r in runner.results if not r.passed)
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
