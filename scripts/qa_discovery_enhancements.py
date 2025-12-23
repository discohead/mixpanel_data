#!/usr/bin/env python3
"""Live QA integration test for Discovery & Query Enhancements (Phase 007).

This script performs real API calls against Mixpanel to verify the
new discovery and query methods added in the 007-discovery-enhancements branch:

Discovery Service:
- list_funnels() - List saved funnels (cached)
- list_cohorts() - List saved cohorts (cached)
- list_top_events() - Today's top events (NOT cached)

Live Query Service:
- event_counts() - Multi-event time-series
- property_counts() - Property value breakdown time-series

Usage:
    uv run python scripts/qa_discovery_enhancements.py

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
    from mixpanel_data._internal.services.discovery import DiscoveryService
    from mixpanel_data._internal.services.live_query import LiveQueryService
    from mixpanel_data.types import (
        EventCountsResult,
        FunnelInfo,
        PropertyCountsResult,
        SavedCohort,
        TopEvent,
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
        print("QA TEST RESULTS - Discovery & Query Enhancements (Phase 007)")
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
    print("Discovery & Query Enhancements QA - Live Integration Tests")
    print("=" * 70)

    runner = QARunner()

    # Shared state
    api_client: MixpanelAPIClient | None = None
    discovery: DiscoveryService | None = None
    live_query: LiveQueryService | None = None

    # Account to use
    ACCOUNT_NAME = "sinkapp-prod"

    # Date range for testing (previous month)
    today = datetime.now()
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    FROM_DATE = last_month_start.strftime("%Y-%m-%d")
    TO_DATE = last_month_end.strftime("%Y-%m-%d")

    print(f"Using date range: {FROM_DATE} to {TO_DATE}")
    print(f"Using account: {ACCOUNT_NAME}")

    # Stored results for later tests
    funnels: list[FunnelInfo] = []
    cohorts: list[SavedCohort] = []
    top_events: list[TopEvent] = []
    event_counts_result: EventCountsResult | None = None
    property_counts_result: PropertyCountsResult | None = None
    discovered_events: list[str] = []

    # =========================================================================
    # Phase 1: Prerequisites
    # =========================================================================
    print("\n[Phase 1] Prerequisites Check")
    print("-" * 40)

    # Test 1.1: Import modules
    def test_imports() -> dict[str, Any]:
        from mixpanel_data._internal.api_client import MixpanelAPIClient  # noqa: F401
        from mixpanel_data._internal.config import ConfigManager  # noqa: F401
        from mixpanel_data._internal.services.discovery import (
            DiscoveryService,  # noqa: F401
        )
        from mixpanel_data._internal.services.live_query import (
            LiveQueryService,  # noqa: F401
        )
        from mixpanel_data.types import (
            EventCountsResult,  # noqa: F401
            FunnelInfo,  # noqa: F401
            PropertyCountsResult,  # noqa: F401
            SavedCohort,  # noqa: F401
            TopEvent,  # noqa: F401
        )

        return {"modules": ["All new types and services imported successfully"]}

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

    # Test 2.2: Create DiscoveryService
    def test_create_discovery() -> dict[str, Any]:
        nonlocal discovery
        from mixpanel_data._internal.services.discovery import DiscoveryService

        assert api_client is not None
        discovery = DiscoveryService(api_client)
        return {"status": "service created", "cache_size": len(discovery._cache)}

    result = runner.run_test("2.2 Create DiscoveryService", test_create_discovery)
    if not result.passed:
        print("Cannot continue - discovery service creation failed")
        runner.print_results()
        return 1

    # Test 2.3: Create LiveQueryService
    def test_create_live_query() -> dict[str, Any]:
        nonlocal live_query
        from mixpanel_data._internal.services.live_query import LiveQueryService

        assert api_client is not None
        live_query = LiveQueryService(api_client)
        return {"status": "service created"}

    result = runner.run_test("2.3 Create LiveQueryService", test_create_live_query)
    if not result.passed:
        print("Cannot continue - live query service creation failed")
        runner.print_results()
        return 1

    # Test 2.4: Discover events for later tests
    def test_discover_events() -> dict[str, Any]:
        nonlocal discovered_events
        assert discovery is not None
        discovered_events = discovery.list_events()
        return {
            "count": len(discovered_events),
            "sample": discovered_events[:5] if discovered_events else [],
        }

    runner.run_test("2.4 Discover events", test_discover_events)

    # =========================================================================
    # Phase 3: list_funnels() Tests
    # =========================================================================
    print("\n[Phase 3] list_funnels() Tests")
    print("-" * 40)

    # Test 3.1: list_funnels() basic call
    def test_list_funnels() -> dict[str, Any]:
        nonlocal funnels
        from mixpanel_data.types import FunnelInfo

        assert discovery is not None
        funnels = discovery.list_funnels()
        if not isinstance(funnels, list):
            raise TypeError(f"Expected list, got {type(funnels)}")
        if funnels and not isinstance(funnels[0], FunnelInfo):
            raise TypeError(f"Expected FunnelInfo, got {type(funnels[0])}")
        return {
            "count": len(funnels),
            "sample": [{"id": f.funnel_id, "name": f.name} for f in funnels[:3]]
            if funnels
            else [],
        }

    runner.run_test("3.1 list_funnels() basic", test_list_funnels)

    # Test 3.2: list_funnels() returns sorted by name
    def test_funnels_sorted() -> dict[str, Any]:
        if not funnels:
            return {"skipped": "No funnels in project"}
        names = [f.name for f in funnels]
        sorted_names = sorted(names)
        if names != sorted_names:
            raise ValueError(f"Funnels not sorted: {names[:5]}")
        return {"is_sorted": True, "names": names[:5]}

    runner.run_test("3.2 list_funnels() sorted by name", test_funnels_sorted)

    # Test 3.3: list_funnels() caching
    def test_funnels_caching() -> dict[str, Any]:
        assert discovery is not None
        cache_key = ("list_funnels",)
        if cache_key not in discovery._cache:
            raise ValueError("list_funnels() result not cached")
        # Call again - should use cache
        funnels2 = discovery.list_funnels()
        if funnels2 != funnels:
            raise ValueError("Cached result doesn't match original")
        return {"cache_key": str(cache_key), "cache_hit": True}

    runner.run_test("3.3 list_funnels() caching", test_funnels_caching)

    # Test 3.4: FunnelInfo.to_dict()
    def test_funnel_info_to_dict() -> dict[str, Any]:
        if not funnels:
            return {"skipped": "No funnels in project"}
        funnel = funnels[0]
        d = funnel.to_dict()
        expected_keys = {"funnel_id", "name"}
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        _ = json.dumps(d)
        return {"keys": list(d.keys()), "json_serializable": True}

    runner.run_test("3.4 FunnelInfo.to_dict()", test_funnel_info_to_dict)

    # =========================================================================
    # Phase 4: list_cohorts() Tests
    # =========================================================================
    print("\n[Phase 4] list_cohorts() Tests")
    print("-" * 40)

    # Test 4.1: list_cohorts() basic call
    def test_list_cohorts() -> dict[str, Any]:
        nonlocal cohorts
        from mixpanel_data.types import SavedCohort

        assert discovery is not None
        cohorts = discovery.list_cohorts()
        if not isinstance(cohorts, list):
            raise TypeError(f"Expected list, got {type(cohorts)}")
        if cohorts and not isinstance(cohorts[0], SavedCohort):
            raise TypeError(f"Expected SavedCohort, got {type(cohorts[0])}")
        return {
            "count": len(cohorts),
            "sample": [
                {"id": c.id, "name": c.name, "count": c.count} for c in cohorts[:3]
            ]
            if cohorts
            else [],
        }

    runner.run_test("4.1 list_cohorts() basic", test_list_cohorts)

    # Test 4.2: list_cohorts() returns sorted by name
    def test_cohorts_sorted() -> dict[str, Any]:
        if not cohorts:
            return {"skipped": "No cohorts in project"}
        names = [c.name for c in cohorts]
        sorted_names = sorted(names)
        if names != sorted_names:
            raise ValueError(f"Cohorts not sorted: {names[:5]}")
        return {"is_sorted": True, "names": names[:5]}

    runner.run_test("4.2 list_cohorts() sorted by name", test_cohorts_sorted)

    # Test 4.3: list_cohorts() caching
    def test_cohorts_caching() -> dict[str, Any]:
        assert discovery is not None
        cache_key = ("list_cohorts",)
        if cache_key not in discovery._cache:
            raise ValueError("list_cohorts() result not cached")
        # Call again - should use cache
        cohorts2 = discovery.list_cohorts()
        if cohorts2 != cohorts:
            raise ValueError("Cached result doesn't match original")
        return {"cache_key": str(cache_key), "cache_hit": True}

    runner.run_test("4.3 list_cohorts() caching", test_cohorts_caching)

    # Test 4.4: SavedCohort has all expected fields
    def test_saved_cohort_fields() -> dict[str, Any]:
        if not cohorts:
            return {"skipped": "No cohorts in project"}
        cohort = cohorts[0]
        # Verify all expected fields are present
        fields = {
            "id": cohort.id,
            "name": cohort.name,
            "count": cohort.count,
            "description": cohort.description,
            "created": cohort.created,
            "is_visible": cohort.is_visible,
        }
        # Verify types
        if not isinstance(cohort.id, int):
            raise TypeError(f"id should be int, got {type(cohort.id)}")
        if not isinstance(cohort.count, int):
            raise TypeError(f"count should be int, got {type(cohort.count)}")
        if not isinstance(cohort.is_visible, bool):
            raise TypeError(f"is_visible should be bool, got {type(cohort.is_visible)}")
        return {"fields": list(fields.keys()), "all_present": True}

    runner.run_test("4.4 SavedCohort fields", test_saved_cohort_fields)

    # Test 4.5: SavedCohort.to_dict()
    def test_saved_cohort_to_dict() -> dict[str, Any]:
        if not cohorts:
            return {"skipped": "No cohorts in project"}
        cohort = cohorts[0]
        d = cohort.to_dict()
        expected_keys = {"id", "name", "count", "description", "created", "is_visible"}
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        _ = json.dumps(d)
        return {"keys": list(d.keys()), "json_serializable": True}

    runner.run_test("4.5 SavedCohort.to_dict()", test_saved_cohort_to_dict)

    # =========================================================================
    # Phase 5: list_top_events() Tests
    # =========================================================================
    print("\n[Phase 5] list_top_events() Tests")
    print("-" * 40)

    # Test 5.1: list_top_events() basic call
    def test_list_top_events() -> dict[str, Any]:
        nonlocal top_events
        from mixpanel_data.types import TopEvent

        assert discovery is not None
        top_events = discovery.list_top_events()
        if not isinstance(top_events, list):
            raise TypeError(f"Expected list, got {type(top_events)}")
        if top_events and not isinstance(top_events[0], TopEvent):
            raise TypeError(f"Expected TopEvent, got {type(top_events[0])}")
        return {
            "count": len(top_events),
            "sample": [
                {
                    "event": e.event,
                    "count": e.count,
                    "change": f"{e.percent_change:.1%}",
                }
                for e in top_events[:3]
            ]
            if top_events
            else [],
        }

    runner.run_test("5.1 list_top_events() basic", test_list_top_events)

    # Test 5.2: list_top_events() NOT cached
    def test_top_events_not_cached() -> dict[str, Any]:
        assert discovery is not None
        # Top events should NOT be cached
        cache_keys = [k for k in discovery._cache if "top_events" in str(k)]
        if cache_keys:
            raise ValueError(f"Top events should not be cached: {cache_keys}")
        return {"not_cached": True}

    runner.run_test("5.2 list_top_events() NOT cached", test_top_events_not_cached)

    # Test 5.3: TopEvent has all expected fields
    def test_top_event_fields() -> dict[str, Any]:
        if not top_events:
            return {"skipped": "No events today"}
        event = top_events[0]
        # Verify all expected fields
        fields = {
            "event": event.event,
            "count": event.count,
            "percent_change": event.percent_change,
        }
        # Verify types
        if not isinstance(event.event, str):
            raise TypeError(f"event should be str, got {type(event.event)}")
        if not isinstance(event.count, int):
            raise TypeError(f"count should be int, got {type(event.count)}")
        if not isinstance(event.percent_change, int | float):
            raise TypeError(
                f"percent_change should be float, got {type(event.percent_change)}"
            )
        return {"fields": list(fields.keys()), "all_present": True}

    runner.run_test("5.3 TopEvent fields", test_top_event_fields)

    # Test 5.4: TopEvent.to_dict()
    def test_top_event_to_dict() -> dict[str, Any]:
        if not top_events:
            return {"skipped": "No events today"}
        event = top_events[0]
        d = event.to_dict()
        expected_keys = {"event", "count", "percent_change"}
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        _ = json.dumps(d)
        return {"keys": list(d.keys()), "json_serializable": True}

    runner.run_test("5.4 TopEvent.to_dict()", test_top_event_to_dict)

    # Test 5.5: list_top_events() with type parameter
    def test_top_events_with_type() -> dict[str, Any]:
        assert discovery is not None
        result_unique = discovery.list_top_events(type="unique")
        return {
            "type": "unique",
            "count": len(result_unique),
            "sample": [e.event for e in result_unique[:3]] if result_unique else [],
        }

    runner.run_test("5.5 list_top_events(type=unique)", test_top_events_with_type)

    # Test 5.6: list_top_events() with limit parameter
    def test_top_events_with_limit() -> dict[str, Any]:
        assert discovery is not None
        result = discovery.list_top_events(limit=5)
        if len(result) > 5:
            raise ValueError(f"Expected at most 5 events, got {len(result)}")
        return {
            "limit": 5,
            "returned": len(result),
        }

    runner.run_test("5.6 list_top_events(limit=5)", test_top_events_with_limit)

    # =========================================================================
    # Phase 6: event_counts() Tests
    # =========================================================================
    print("\n[Phase 6] event_counts() Tests")
    print("-" * 40)

    # Test 6.1: event_counts() basic call
    def test_event_counts_basic() -> dict[str, Any]:
        nonlocal event_counts_result
        from mixpanel_data.types import EventCountsResult

        assert live_query is not None
        if not discovered_events:
            return {"skipped": "No events available"}

        # Use first two events for multi-event query
        test_events = discovered_events[:2]
        event_counts_result = live_query.event_counts(
            events=test_events,
            from_date=FROM_DATE,
            to_date=TO_DATE,
        )
        if not isinstance(event_counts_result, EventCountsResult):
            raise TypeError(
                f"Expected EventCountsResult, got {type(event_counts_result)}"
            )
        return {
            "events": event_counts_result.events,
            "from_date": event_counts_result.from_date,
            "to_date": event_counts_result.to_date,
            "unit": event_counts_result.unit,
            "type": event_counts_result.type,
            "series_keys": list(event_counts_result.series.keys())[:3],
        }

    runner.run_test("6.1 event_counts() basic", test_event_counts_basic)

    # Test 6.2: EventCountsResult series structure
    def test_event_counts_series() -> dict[str, Any]:
        if event_counts_result is None:
            return {"skipped": "No event counts result"}
        series = event_counts_result.series
        if not isinstance(series, dict):
            raise TypeError(f"series should be dict, got {type(series)}")
        # Check that each event has a dict of date -> count
        for event_name, date_counts in series.items():
            if not isinstance(date_counts, dict):
                raise TypeError(
                    f"date_counts for {event_name} should be dict, got {type(date_counts)}"
                )
            # Check first date entry
            if date_counts:
                first_date = next(iter(date_counts.keys()))
                first_count = date_counts[first_date]
                if not isinstance(first_count, int | float):
                    raise TypeError(f"count should be numeric, got {type(first_count)}")
        return {
            "events_in_series": list(series.keys()),
            "structure": "valid",
        }

    runner.run_test("6.2 event_counts() series structure", test_event_counts_series)

    # Test 6.3: EventCountsResult.df
    def test_event_counts_df() -> dict[str, Any]:
        if event_counts_result is None:
            return {"skipped": "No event counts result"}
        df = event_counts_result.df
        expected_cols = {"date", "event", "count"}
        actual_cols = set(df.columns)
        if not expected_cols.issubset(actual_cols):
            raise ValueError(f"Missing columns: {expected_cols - actual_cols}")
        return {
            "columns": list(df.columns),
            "rows": len(df),
            "dtypes": {col: str(df[col].dtype) for col in df.columns},
        }

    runner.run_test("6.3 EventCountsResult.df", test_event_counts_df)

    # Test 6.4: EventCountsResult.df caching
    def test_event_counts_df_caching() -> dict[str, Any]:
        if event_counts_result is None:
            return {"skipped": "No event counts result"}
        df1 = event_counts_result.df
        df2 = event_counts_result.df
        if df1 is not df2:
            raise ValueError("DataFrame should be cached (same object)")
        return {"cached": True, "same_object": True}

    runner.run_test("6.4 EventCountsResult.df caching", test_event_counts_df_caching)

    # Test 6.5: EventCountsResult.to_dict()
    def test_event_counts_to_dict() -> dict[str, Any]:
        if event_counts_result is None:
            return {"skipped": "No event counts result"}
        d = event_counts_result.to_dict()
        expected_keys = {"events", "from_date", "to_date", "unit", "type", "series"}
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        _ = json.dumps(d)
        return {"keys": list(d.keys()), "json_serializable": True}

    runner.run_test("6.5 EventCountsResult.to_dict()", test_event_counts_to_dict)

    # Test 6.6: event_counts() with different unit
    def test_event_counts_unit_week() -> dict[str, Any]:
        assert live_query is not None
        if not discovered_events:
            return {"skipped": "No events available"}
        result = live_query.event_counts(
            events=discovered_events[:1],
            from_date=FROM_DATE,
            to_date=TO_DATE,
            unit="week",
        )
        return {
            "unit": result.unit,
            "date_sample": list(list(result.series.values())[0].keys())[:3]
            if result.series
            else [],
        }

    runner.run_test("6.6 event_counts(unit=week)", test_event_counts_unit_week)

    # Test 6.7: event_counts() with type=unique
    def test_event_counts_type_unique() -> dict[str, Any]:
        assert live_query is not None
        if not discovered_events:
            return {"skipped": "No events available"}
        result = live_query.event_counts(
            events=discovered_events[:1],
            from_date=FROM_DATE,
            to_date=TO_DATE,
            type="unique",
        )
        return {
            "type": result.type,
            "events": result.events,
        }

    runner.run_test("6.7 event_counts(type=unique)", test_event_counts_type_unique)

    # =========================================================================
    # Phase 7: property_counts() Tests
    # =========================================================================
    print("\n[Phase 7] property_counts() Tests")
    print("-" * 40)

    # Test 7.1: property_counts() basic call
    def test_property_counts_basic() -> dict[str, Any]:
        nonlocal property_counts_result
        from mixpanel_data.types import PropertyCountsResult

        assert live_query is not None
        if not discovered_events:
            return {"skipped": "No events available"}

        test_event = discovered_events[0]
        property_counts_result = live_query.property_counts(
            event=test_event,
            property_name="$browser",
            from_date=FROM_DATE,
            to_date=TO_DATE,
        )
        if not isinstance(property_counts_result, PropertyCountsResult):
            raise TypeError(
                f"Expected PropertyCountsResult, got {type(property_counts_result)}"
            )
        return {
            "event": property_counts_result.event,
            "property_name": property_counts_result.property_name,
            "from_date": property_counts_result.from_date,
            "to_date": property_counts_result.to_date,
            "unit": property_counts_result.unit,
            "type": property_counts_result.type,
            "series_keys": list(property_counts_result.series.keys())[:5],
        }

    runner.run_test("7.1 property_counts() basic", test_property_counts_basic)

    # Test 7.2: PropertyCountsResult series structure
    def test_property_counts_series() -> dict[str, Any]:
        if property_counts_result is None:
            return {"skipped": "No property counts result"}
        series = property_counts_result.series
        if not isinstance(series, dict):
            raise TypeError(f"series should be dict, got {type(series)}")
        # Check that each value has a dict of date -> count
        for value, date_counts in series.items():
            if not isinstance(date_counts, dict):
                raise TypeError(
                    f"date_counts for {value} should be dict, got {type(date_counts)}"
                )
            # Check first date entry
            if date_counts:
                first_date = next(iter(date_counts.keys()))
                first_count = date_counts[first_date]
                if not isinstance(first_count, int | float):
                    raise TypeError(f"count should be numeric, got {type(first_count)}")
        return {
            "values_in_series": list(series.keys())[:5],
            "structure": "valid",
        }

    runner.run_test(
        "7.2 property_counts() series structure", test_property_counts_series
    )

    # Test 7.3: PropertyCountsResult.df
    def test_property_counts_df() -> dict[str, Any]:
        if property_counts_result is None:
            return {"skipped": "No property counts result"}
        df = property_counts_result.df
        expected_cols = {"date", "value", "count"}
        actual_cols = set(df.columns)
        if not expected_cols.issubset(actual_cols):
            raise ValueError(f"Missing columns: {expected_cols - actual_cols}")
        return {
            "columns": list(df.columns),
            "rows": len(df),
            "unique_values": df["value"].nunique() if len(df) > 0 else 0,
        }

    runner.run_test("7.3 PropertyCountsResult.df", test_property_counts_df)

    # Test 7.4: PropertyCountsResult.df caching
    def test_property_counts_df_caching() -> dict[str, Any]:
        if property_counts_result is None:
            return {"skipped": "No property counts result"}
        df1 = property_counts_result.df
        df2 = property_counts_result.df
        if df1 is not df2:
            raise ValueError("DataFrame should be cached (same object)")
        return {"cached": True, "same_object": True}

    runner.run_test(
        "7.4 PropertyCountsResult.df caching", test_property_counts_df_caching
    )

    # Test 7.5: PropertyCountsResult.to_dict()
    def test_property_counts_to_dict() -> dict[str, Any]:
        if property_counts_result is None:
            return {"skipped": "No property counts result"}
        d = property_counts_result.to_dict()
        expected_keys = {
            "event",
            "property_name",
            "from_date",
            "to_date",
            "unit",
            "type",
            "series",
        }
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        _ = json.dumps(d)
        return {"keys": list(d.keys()), "json_serializable": True}

    runner.run_test("7.5 PropertyCountsResult.to_dict()", test_property_counts_to_dict)

    # Test 7.6: property_counts() with specific values filter
    def test_property_counts_with_values() -> dict[str, Any]:
        assert live_query is not None
        if not discovered_events:
            return {"skipped": "No events available"}
        result = live_query.property_counts(
            event=discovered_events[0],
            property_name="$browser",
            from_date=FROM_DATE,
            to_date=TO_DATE,
            values=["Chrome", "Safari"],
        )
        # Should only have requested values (if they exist)
        return {
            "requested_values": ["Chrome", "Safari"],
            "returned_values": list(result.series.keys()),
        }

    runner.run_test(
        "7.6 property_counts(values=[...])", test_property_counts_with_values
    )

    # Test 7.7: property_counts() with limit
    def test_property_counts_with_limit() -> dict[str, Any]:
        assert live_query is not None
        if not discovered_events:
            return {"skipped": "No events available"}
        result = live_query.property_counts(
            event=discovered_events[0],
            property_name="$browser",
            from_date=FROM_DATE,
            to_date=TO_DATE,
            limit=3,
        )
        value_count = len(result.series)
        if value_count > 3:
            raise ValueError(f"Expected at most 3 values, got {value_count}")
        return {
            "limit": 3,
            "returned": value_count,
        }

    runner.run_test("7.7 property_counts(limit=3)", test_property_counts_with_limit)

    # =========================================================================
    # Phase 8: Edge Cases & Error Handling
    # =========================================================================
    print("\n[Phase 8] Edge Cases & Error Handling")
    print("-" * 40)

    # Test 8.1: event_counts() with non-existent event (should return empty series)
    def test_event_counts_nonexistent() -> dict[str, Any]:
        assert live_query is not None
        result = live_query.event_counts(
            events=["__nonexistent_event_xyz_123__"],
            from_date=FROM_DATE,
            to_date=TO_DATE,
        )
        # Should succeed but with empty/zero counts
        return {
            "events": result.events,
            "series_empty": len(result.series) == 0
            or all(sum(counts.values()) == 0 for counts in result.series.values()),
        }

    runner.run_test(
        "8.1 event_counts() non-existent event", test_event_counts_nonexistent
    )

    # Test 8.2: property_counts() with non-existent property
    def test_property_counts_nonexistent_prop() -> dict[str, Any]:
        assert live_query is not None
        if not discovered_events:
            return {"skipped": "No events available"}
        result = live_query.property_counts(
            event=discovered_events[0],
            property_name="__nonexistent_prop_xyz_123__",
            from_date=FROM_DATE,
            to_date=TO_DATE,
        )
        return {
            "event": result.event,
            "property_name": result.property_name,
            "series_count": len(result.series),
        }

    runner.run_test(
        "8.2 property_counts() non-existent property",
        test_property_counts_nonexistent_prop,
    )

    # Test 8.3: Clear cache and verify funnel/cohort refetch
    def test_cache_clear_refetch() -> dict[str, Any]:
        assert discovery is not None
        cache_before = len(discovery._cache)
        discovery.clear_cache()
        cache_after = len(discovery._cache)
        if cache_after != 0:
            raise ValueError(f"Cache not cleared: {cache_after} entries")
        # Refetch funnels
        funnels2 = discovery.list_funnels()
        if ("list_funnels",) not in discovery._cache:
            raise ValueError("Cache not repopulated after clear")
        return {
            "cache_before": cache_before,
            "cache_after_clear": cache_after,
            "cache_after_refetch": len(discovery._cache),
            "funnels_count": len(funnels2),
        }

    runner.run_test("8.3 cache clear and refetch", test_cache_clear_refetch)

    # =========================================================================
    # Cleanup
    # =========================================================================
    print("\n[Cleanup]")
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
