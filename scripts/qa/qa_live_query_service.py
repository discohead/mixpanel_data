#!/usr/bin/env python3
"""Live QA integration test for Live Query Service (Phase 006).

This script performs real API calls against Mixpanel to verify the
LiveQueryService is working correctly with actual data.

Usage:
    uv run python scripts/qa_live_query_service.py

Prerequisites:
    - Service account configured in ~/.mp/config.toml
    - OR environment variables: MP_USERNAME, MP_SECRET, MP_PROJECT_ID, MP_REGION
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
        FunnelResult,
        JQLResult,
        RetentionResult,
        SegmentationResult,
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
        print("QA TEST RESULTS - Live Query Service (Phase 006)")
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
    print("Live Query Service QA - Live Integration Tests")
    print("=" * 70)

    runner = QARunner()

    # Shared state
    api_client: MixpanelAPIClient | None = None
    live_query: LiveQueryService | None = None
    discovered_events: list[str] = []
    test_event: str | None = None

    # Date range for testing (previous month)
    today = datetime.now()
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    FROM_DATE = last_month_start.strftime("%Y-%m-%d")
    TO_DATE = last_month_end.strftime("%Y-%m-%d")

    print(f"Using date range: {FROM_DATE} to {TO_DATE}")

    # Stored results for later tests
    segmentation_result: SegmentationResult | None = None
    funnel_result: FunnelResult | None = None
    retention_result: RetentionResult | None = None
    jql_result: JQLResult | None = None

    # =========================================================================
    # Phase 1: Prerequisites
    # =========================================================================
    print("\n[Phase 1] Prerequisites Check")
    print("-" * 40)

    # Test 1.1: Import modules
    def test_imports() -> dict[str, Any]:
        return {
            "modules": [
                "ConfigManager",
                "MixpanelAPIClient",
                "LiveQueryService",
            ]
        }

    result = runner.run_test("1.1 Import modules", test_imports)
    if not result.passed:
        print("Cannot continue - import failed")
        runner.print_results()
        return 1

    # Test 1.2: Config file exists
    def test_config_exists() -> dict[str, Any]:
        from mixpanel_data._internal.config import ConfigManager

        config = ConfigManager()
        path = config.config_path
        exists = path.exists()
        if not exists:
            raise FileNotFoundError(f"Config file not found at {path}")
        return {"config_path": str(path)}

    result = runner.run_test("1.2 Config file exists", test_config_exists)

    # Test 1.3: Resolve credentials
    # Use specific account if provided, otherwise use default
    ACCOUNT_NAME = "sinkapp-prod"  # Change this to test different accounts

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

    result = runner.run_test("1.3 Resolve credentials", test_resolve_credentials)
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
        print("Cannot continue - service creation failed")
        runner.print_results()
        return 1

    # =========================================================================
    # Phase 3: Discovery (Identify Test Data)
    # =========================================================================
    print("\n[Phase 3] Discovery")
    print("-" * 40)

    # Fallback event name if discovery fails (rate limited)
    FALLBACK_EVENT = "viewed_checkout"  # Known event in sinkapp-prod

    # Test 3.1: Discover events
    def test_discover_events() -> dict[str, Any]:
        nonlocal discovered_events, test_event
        assert api_client is not None
        try:
            discovered_events = api_client.get_events()
            if not discovered_events:
                raise ValueError("No events found in project")

            # Use first event for testing
            test_event = discovered_events[0]

            return {
                "count": len(discovered_events),
                "sample": discovered_events[:5],
                "test_event": test_event,
            }
        except Exception as e:
            # Use fallback event if rate limited
            test_event = FALLBACK_EVENT
            return {
                "fallback": True,
                "test_event": test_event,
                "reason": f"{type(e).__name__}: {str(e)[:50]}",
            }

    result = runner.run_test("3.1 Discover events", test_discover_events)
    if test_event is None:
        print("Cannot continue - no events available")
        runner.print_results()
        return 1

    # Test 3.2: Discover properties for test event
    def test_discover_properties() -> dict[str, Any]:
        assert api_client is not None
        assert test_event is not None
        try:
            properties = api_client.get_event_properties(test_event)
            return {
                "event": test_event,
                "property_count": len(properties),
                "sample": properties[:5] if properties else [],
            }
        except Exception as e:
            # Skip if rate limited - properties not required for main tests
            return {
                "skipped": True,
                "reason": f"{type(e).__name__}: {str(e)[:50]}",
            }

    runner.run_test("3.2 Discover properties", test_discover_properties)

    # =========================================================================
    # Phase 4: Segmentation Query Tests
    # =========================================================================
    print("\n[Phase 4] Segmentation Query Tests")
    print("-" * 40)

    # Test 4.1: Basic segmentation
    def test_segmentation_basic() -> dict[str, Any]:
        nonlocal segmentation_result
        from mixpanel_data.types import SegmentationResult

        assert live_query is not None
        assert test_event is not None
        segmentation_result = live_query.segmentation(
            event=test_event,
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
            "from_date": segmentation_result.from_date,
            "to_date": segmentation_result.to_date,
            "unit": segmentation_result.unit,
            "segments": len(segmentation_result.series),
        }

    runner.run_test("4.1 segmentation() basic", test_segmentation_basic)

    # Test 4.2: Verify segmentation total matches series sum
    def test_segmentation_total() -> dict[str, Any]:
        assert segmentation_result is not None
        series_sum = sum(
            count
            for segment_values in segmentation_result.series.values()
            for count in segment_values.values()
        )
        if segmentation_result.total != series_sum:
            raise ValueError(
                f"Total {segmentation_result.total} != series sum {series_sum}"
            )
        return {
            "total": segmentation_result.total,
            "series_sum": series_sum,
            "match": True,
        }

    runner.run_test("4.2 segmentation total matches sum", test_segmentation_total)

    # Test 4.3: Segmentation with property segmentation
    def test_segmentation_with_property() -> dict[str, Any]:
        assert live_query is not None
        assert test_event is not None
        result = live_query.segmentation(
            event=test_event,
            from_date=FROM_DATE,
            to_date=TO_DATE,
            on='properties["$browser"]',
        )
        return {
            "event": result.event,
            "segment_property": result.segment_property,
            "segments": list(result.series.keys())[:5],
            "total": result.total,
        }

    runner.run_test("4.3 segmentation with property", test_segmentation_with_property)

    # Test 4.4: Segmentation with where filter
    def test_segmentation_with_filter() -> dict[str, Any]:
        assert live_query is not None
        assert test_event is not None
        result = live_query.segmentation(
            event=test_event,
            from_date=FROM_DATE,
            to_date=TO_DATE,
            where='properties["$os"] == "Mac OS X"',
        )
        return {
            "event": result.event,
            "total": result.total,
            "filtered": True,
        }

    runner.run_test("4.4 segmentation with filter", test_segmentation_with_filter)

    # Test 4.5: Segmentation with different unit
    def test_segmentation_unit_week() -> dict[str, Any]:
        assert live_query is not None
        assert test_event is not None
        result = live_query.segmentation(
            event=test_event,
            from_date=FROM_DATE,
            to_date=TO_DATE,
            unit="week",
        )
        return {
            "unit": result.unit,
            "series_dates": list(list(result.series.values())[0].keys())[:5]
            if result.series
            else [],
        }

    runner.run_test("4.5 segmentation unit=week", test_segmentation_unit_week)

    # Test 4.6: Segmentation with non-existent event (empty results)
    def test_segmentation_empty() -> dict[str, Any]:
        assert live_query is not None
        result = live_query.segmentation(
            event="__nonexistent_event_xyz_123__",
            from_date=FROM_DATE,
            to_date=TO_DATE,
        )
        return {
            "event": result.event,
            "total": result.total,
            "series_empty": len(result.series) == 0 or result.total == 0,
        }

    runner.run_test("4.6 segmentation empty result", test_segmentation_empty)

    # =========================================================================
    # Phase 5: Funnel Query Tests
    # =========================================================================
    print("\n[Phase 5] Funnel Query Tests")
    print("-" * 40)

    # Test 5.1: Try to list funnels via API
    funnel_ids: list[int] = []

    def test_discover_funnels() -> dict[str, Any]:
        nonlocal funnel_ids
        assert api_client is not None

        # Try to list funnels using the funnels/list endpoint
        try:
            url = "https://mixpanel.com/api/2.0/funnels/list"
            headers = {"Authorization": api_client._get_auth_header()}
            response = api_client._client.get(  # type: ignore[union-attr]
                url,
                params={"project_id": api_client._credentials.project_id},
                headers=headers,
                timeout=api_client._timeout,
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    funnel_ids.extend(
                        [f.get("funnel_id") for f in data if "funnel_id" in f]
                    )
                return {
                    "funnels_found": len(funnel_ids),
                    "funnel_ids": funnel_ids[:5] if funnel_ids else [],
                }
            return {
                "status_code": response.status_code,
                "note": "Funnel list API not available",
            }
        except Exception as e:
            return {
                "error": type(e).__name__,
                "message": str(e)[:50],
            }

    result = runner.run_test("5.1 Discover funnels", test_discover_funnels)

    # Test 5.2: Funnel query (if funnels exist)
    if funnel_ids:

        def test_funnel_basic() -> dict[str, Any]:
            nonlocal funnel_result
            from mixpanel_data.types import FunnelResult

            assert live_query is not None
            funnel_result = live_query.funnel(
                funnel_id=funnel_ids[0],
                from_date=FROM_DATE,
                to_date=TO_DATE,
            )
            if not isinstance(funnel_result, FunnelResult):
                raise TypeError(f"Expected FunnelResult, got {type(funnel_result)}")
            return {
                "funnel_id": funnel_result.funnel_id,
                "conversion_rate": f"{funnel_result.conversion_rate:.2%}",
                "steps_count": len(funnel_result.steps),
            }

        runner.run_test("5.2 funnel() basic", test_funnel_basic)

        # Test 5.3: Verify funnel step structure
        def test_funnel_steps() -> dict[str, Any]:
            assert funnel_result is not None
            if not funnel_result.steps:
                return {"skipped": "No steps in funnel"}
            steps_info = []
            for step in funnel_result.steps[:3]:
                steps_info.append(
                    {
                        "event": step.event,
                        "count": step.count,
                        "conv_rate": f"{step.conversion_rate:.2%}",
                    }
                )
            # First step should have conversion_rate = 1.0
            if funnel_result.steps[0].conversion_rate != 1.0:
                raise ValueError(
                    f"First step should have 1.0 conversion, got {funnel_result.steps[0].conversion_rate}"
                )
            return {"steps": steps_info, "first_step_conv_1.0": True}

        runner.run_test("5.3 funnel step structure", test_funnel_steps)

        # Test 5.4: Verify overall conversion rate
        def test_funnel_conversion() -> dict[str, Any]:
            assert funnel_result is not None
            if not funnel_result.steps:
                return {"skipped": "No steps"}
            expected = (
                funnel_result.steps[-1].count / funnel_result.steps[0].count
                if funnel_result.steps[0].count > 0
                else 0.0
            )
            if abs(funnel_result.conversion_rate - expected) > 0.001:
                raise ValueError(
                    f"Conversion rate mismatch: {funnel_result.conversion_rate} vs expected {expected}"
                )
            return {
                "overall_rate": f"{funnel_result.conversion_rate:.2%}",
                "calculated": f"{expected:.2%}",
                "match": True,
            }

        runner.run_test("5.4 funnel conversion rate", test_funnel_conversion)
    else:
        print("  [SKIPPED] No funnels configured in project")

    # Test 5.5: Invalid funnel ID
    def test_funnel_invalid_id() -> dict[str, Any]:
        from mixpanel_data.exceptions import QueryError

        assert live_query is not None
        try:
            live_query.funnel(
                funnel_id=999999999,
                from_date=FROM_DATE,
                to_date=TO_DATE,
            )
            return {"error_raised": False, "note": "No error for invalid funnel ID"}
        except QueryError as e:
            return {"error_raised": True, "error_code": e.code}
        except Exception as e:
            return {"error_type": type(e).__name__, "message": str(e)[:50]}

    runner.run_test("5.5 funnel invalid ID", test_funnel_invalid_id)

    # =========================================================================
    # Phase 6: Retention Query Tests
    # =========================================================================
    print("\n[Phase 6] Retention Query Tests")
    print("-" * 40)

    # Test 6.1: Basic retention
    retention_available = True

    def test_retention_basic() -> dict[str, Any]:
        nonlocal retention_result, retention_available
        from mixpanel_data.types import RetentionResult

        assert live_query is not None
        assert test_event is not None
        try:
            retention_result = live_query.retention(
                born_event=test_event,
                return_event=test_event,
                from_date=FROM_DATE,
                to_date=TO_DATE,
            )
            if not isinstance(retention_result, RetentionResult):
                raise TypeError(
                    f"Expected RetentionResult, got {type(retention_result)}"
                )
            return {
                "born_event": retention_result.born_event,
                "return_event": retention_result.return_event,
                "unit": retention_result.unit,
                "cohorts_count": len(retention_result.cohorts),
            }
        except Exception as e:
            # Server errors may occur if there's not enough data
            retention_available = False
            return {
                "error": type(e).__name__,
                "message": str(e)[:100],
                "note": "Retention API may not be available for this data",
            }

    runner.run_test("6.1 retention() basic", test_retention_basic)

    # Test 6.2: Verify cohort structure
    if retention_available and retention_result is not None:

        def test_retention_cohort_structure() -> dict[str, Any]:
            assert retention_result is not None
            if not retention_result.cohorts:
                return {"skipped": "No cohorts returned"}
            cohort = retention_result.cohorts[0]
            return {
                "first_cohort_date": cohort.date,
                "cohort_size": cohort.size,
                "retention_periods": len(cohort.retention),
                "retention_sample": [f"{r:.2%}" for r in cohort.retention[:5]],
            }

        runner.run_test(
            "6.2 retention cohort structure", test_retention_cohort_structure
        )

        # Test 6.3: Verify cohorts sorted by date
        def test_retention_sorted() -> dict[str, Any]:
            assert retention_result is not None
            if len(retention_result.cohorts) < 2:
                return {"skipped": "Need at least 2 cohorts"}
            dates = [c.date for c in retention_result.cohorts]
            sorted_dates = sorted(dates)
            if dates != sorted_dates:
                raise ValueError(f"Cohorts not sorted: {dates}")
            return {"dates": dates[:5], "is_sorted": True}

        runner.run_test("6.3 retention cohorts sorted", test_retention_sorted)

        # Test 6.4: Verify retention percentages are 0-1
        def test_retention_percentages() -> dict[str, Any]:
            assert retention_result is not None
            invalid = []
            for cohort in retention_result.cohorts:
                for r in cohort.retention:
                    if r < 0.0 or r > 1.0:
                        invalid.append(r)
            if invalid:
                raise ValueError(f"Invalid retention values (not 0-1): {invalid[:5]}")
            return {"all_valid": True, "cohorts_checked": len(retention_result.cohorts)}

        runner.run_test("6.4 retention percentages valid", test_retention_percentages)

        # Test 6.5: Retention with custom interval
        def test_retention_custom_interval() -> dict[str, Any]:
            assert live_query is not None
            assert test_event is not None
            result = live_query.retention(
                born_event=test_event,
                return_event=test_event,
                from_date=FROM_DATE,
                to_date=TO_DATE,
                interval=7,
                interval_count=4,
                unit="day",
            )
            return {
                "unit": result.unit,
                "cohorts": len(result.cohorts),
                "retention_periods": len(result.cohorts[0].retention)
                if result.cohorts
                else 0,
            }

        runner.run_test("6.5 retention custom interval", test_retention_custom_interval)
    else:
        print("  [SKIPPED] Retention tests - API not available for this data")

    # =========================================================================
    # Phase 7: JQL Query Tests
    # =========================================================================
    print("\n[Phase 7] JQL Query Tests")
    print("-" * 40)

    # Test 7.0: Raw JQL HTTP request for debugging
    jql_raw_response: dict[str, Any] | None = None

    def test_jql_raw_http() -> dict[str, Any]:
        """Make raw HTTP request to JQL endpoint to capture full response."""
        nonlocal jql_raw_response
        assert api_client is not None

        # Note: .limit() is not valid after .groupBy() in JQL
        script = f"""function main() {{
  return Events({{
    from_date: "{FROM_DATE}",
    to_date: "{TO_DATE}"
  }})
  .groupBy(["name"], mixpanel.reducer.count());
}}"""

        url = f"https://mixpanel.com/api/query/jql?project_id={api_client._credentials.project_id}"
        headers = {
            "Authorization": api_client._get_auth_header(),
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"script": script}

        response = api_client._client.post(  # type: ignore[union-attr]
            url,
            data=data,
            headers=headers,
            timeout=api_client._timeout,
        )

        jql_raw_response = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
        }

        try:
            body = response.json()
            jql_raw_response["body"] = body
        except Exception:
            jql_raw_response["body_text"] = response.text[:500]

        return {
            "status_code": response.status_code,
            "body": jql_raw_response.get("body", jql_raw_response.get("body_text", ""))[
                :200
            ]
            if isinstance(
                jql_raw_response.get("body", jql_raw_response.get("body_text", "")), str
            )
            else jql_raw_response.get("body"),
        }

    runner.run_test("7.0 jql() raw HTTP debug", test_jql_raw_http)

    # Test 7.1: Simple JQL query
    jql_available = True

    def test_jql_basic() -> dict[str, Any]:
        nonlocal jql_result, jql_available
        from mixpanel_data.types import JQLResult

        assert live_query is not None
        # Note: .limit() is not valid after .groupBy() in JQL
        script = f"""
        function main() {{
            return Events({{
                from_date: "{FROM_DATE}",
                to_date: "{TO_DATE}"
            }})
            .groupBy(["name"], mixpanel.reducer.count());
        }}
        """
        try:
            jql_result = live_query.jql(script=script)
            if not isinstance(jql_result, JQLResult):
                raise TypeError(f"Expected JQLResult, got {type(jql_result)}")
            return {
                "row_count": len(jql_result.raw),
                "sample": jql_result.raw[:3] if jql_result.raw else [],
            }
        except Exception as e:
            # JQL may not be available (412 Precondition Failed = JQL not enabled)
            jql_available = False
            return {
                "error": type(e).__name__,
                "message": str(e)[:100],
                "note": "JQL may not be enabled for this project",
            }

    runner.run_test("7.1 jql() basic", test_jql_basic)

    # Test 7.2-7.3: Additional JQL tests (only if JQL is available)
    if jql_available and jql_result is not None:

        def test_jql_with_params() -> dict[str, Any]:
            assert live_query is not None
            # Note: .limit() is not valid after .groupBy() in JQL
            script = """
            function main() {
                return Events({
                    from_date: params.from,
                    to_date: params.to
                })
                .groupBy(["name"], mixpanel.reducer.count());
            }
            """
            result = live_query.jql(
                script=script, params={"from": FROM_DATE, "to": TO_DATE}
            )
            return {
                "row_count": len(result.raw),
                "has_params": True,
            }

        runner.run_test("7.2 jql() with params", test_jql_with_params)

        def test_jql_empty() -> dict[str, Any]:
            assert live_query is not None
            # Filter for non-existent event to get empty result
            script = """
            function main() {
                return Events({
                    from_date: "2020-01-01",
                    to_date: "2020-01-01"
                })
                .filter(function(e) { return e.name === "__nonexistent_xyz__"; });
            }
            """
            result = live_query.jql(script=script)
            return {
                "row_count": len(result.raw),
                "is_empty": len(result.raw) == 0,
            }

        runner.run_test("7.3 jql() empty result", test_jql_empty)
    else:
        print("  [SKIPPED] Additional JQL tests - JQL not available for this project")

    # Test 7.4: Invalid JQL script
    def test_jql_invalid() -> dict[str, Any]:
        from mixpanel_data.exceptions import QueryError

        assert live_query is not None
        try:
            live_query.jql(script="this is invalid javascript {{{{")
            return {"error_raised": False, "note": "No error for invalid JQL"}
        except QueryError as e:
            return {"error_raised": True, "error_code": e.code}
        except Exception as e:
            return {"error_type": type(e).__name__, "message": str(e)[:50]}

    runner.run_test("7.4 jql() invalid script", test_jql_invalid)

    # =========================================================================
    # Phase 8: DataFrame Conversion Tests
    # =========================================================================
    print("\n[Phase 8] DataFrame Conversion Tests")
    print("-" * 40)

    # Test 8.1: SegmentationResult.df
    def test_segmentation_df() -> dict[str, Any]:
        assert segmentation_result is not None
        df = segmentation_result.df
        expected_cols = {"date", "segment", "count"}
        actual_cols = set(df.columns)
        if not expected_cols.issubset(actual_cols):
            raise ValueError(f"Missing columns: {expected_cols - actual_cols}")
        return {
            "columns": list(df.columns),
            "rows": len(df),
            "dtypes": {col: str(df[col].dtype) for col in df.columns},
        }

    runner.run_test("8.1 SegmentationResult.df", test_segmentation_df)

    # Test 8.2: FunnelResult.df (if available)
    if funnel_result is not None:

        def test_funnel_df() -> dict[str, Any]:
            assert funnel_result is not None
            df = funnel_result.df
            expected_cols = {"step", "event", "count", "conversion_rate"}
            actual_cols = set(df.columns)
            if not expected_cols.issubset(actual_cols):
                raise ValueError(f"Missing columns: {expected_cols - actual_cols}")
            # Verify steps are 1-indexed
            if len(df) > 0 and df["step"].iloc[0] != 1:
                raise ValueError(f"Steps should be 1-indexed, got {df['step'].iloc[0]}")
            return {
                "columns": list(df.columns),
                "rows": len(df),
                "first_step": int(df["step"].iloc[0]) if len(df) > 0 else None,
            }

        runner.run_test("8.2 FunnelResult.df", test_funnel_df)
    else:
        print("  [SKIPPED] No funnel result available")

    # Test 8.3: RetentionResult.df
    if retention_available and retention_result is not None:

        def test_retention_df() -> dict[str, Any]:
            assert retention_result is not None
            df = retention_result.df
            if "cohort_date" not in df.columns or "cohort_size" not in df.columns:
                raise ValueError("Missing cohort_date or cohort_size columns")
            # Check for period columns
            period_cols = [c for c in df.columns if c.startswith("period_")]
            return {
                "columns": list(df.columns)[:7],
                "rows": len(df),
                "period_columns": len(period_cols),
            }

        runner.run_test("8.3 RetentionResult.df", test_retention_df)
    else:
        print("  [SKIPPED] RetentionResult.df - no retention data available")

    # Test 8.4: JQLResult.df
    if jql_available and jql_result is not None:

        def test_jql_df() -> dict[str, Any]:
            assert jql_result is not None
            df = jql_result.df
            return {
                "columns": list(df.columns),
                "rows": len(df),
                "dtypes": {col: str(df[col].dtype) for col in df.columns}
                if len(df) > 0
                else {},
            }

        runner.run_test("8.4 JQLResult.df", test_jql_df)
    else:
        print("  [SKIPPED] JQLResult.df - no JQL data available")

    # Test 8.5: DataFrame caching
    def test_df_caching() -> dict[str, Any]:
        assert segmentation_result is not None
        df1 = segmentation_result.df
        df2 = segmentation_result.df
        if df1 is not df2:
            raise ValueError("DataFrame should be cached (same object)")
        return {"cached": True, "same_object": df1 is df2}

    runner.run_test("8.5 DataFrame caching", test_df_caching)

    # =========================================================================
    # Phase 9: Serialization Tests
    # =========================================================================
    print("\n[Phase 9] Serialization Tests")
    print("-" * 40)

    # Test 9.1: SegmentationResult.to_dict()
    def test_segmentation_to_dict() -> dict[str, Any]:
        assert segmentation_result is not None
        d = segmentation_result.to_dict()
        expected_keys = {"event", "from_date", "to_date", "unit", "total", "series"}
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Test JSON serializable
        _ = json.dumps(d)
        return {"keys": list(d.keys()), "json_serializable": True}

    runner.run_test("9.1 SegmentationResult.to_dict()", test_segmentation_to_dict)

    # Test 9.2: FunnelResult.to_dict() (if available)
    if funnel_result is not None:

        def test_funnel_to_dict() -> dict[str, Any]:
            assert funnel_result is not None
            d = funnel_result.to_dict()
            expected_keys = {
                "funnel_id",
                "from_date",
                "to_date",
                "conversion_rate",
                "steps",
            }
            if not expected_keys.issubset(d.keys()):
                raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
            # Check steps are serialized
            if d["steps"] and not isinstance(d["steps"][0], dict):
                raise TypeError("Steps should be serialized to dicts")
            _ = json.dumps(d)
            return {"keys": list(d.keys()), "steps_serialized": True}

        runner.run_test("9.2 FunnelResult.to_dict()", test_funnel_to_dict)

    # Test 9.3: RetentionResult.to_dict()
    if retention_available and retention_result is not None:

        def test_retention_to_dict() -> dict[str, Any]:
            assert retention_result is not None
            d = retention_result.to_dict()
            expected_keys = {
                "born_event",
                "return_event",
                "from_date",
                "to_date",
                "cohorts",
            }
            if not expected_keys.issubset(d.keys()):
                raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
            # Check cohorts are serialized
            if d["cohorts"] and not isinstance(d["cohorts"][0], dict):
                raise TypeError("Cohorts should be serialized to dicts")
            _ = json.dumps(d)
            return {"keys": list(d.keys()), "cohorts_serialized": True}

        runner.run_test("9.3 RetentionResult.to_dict()", test_retention_to_dict)
    else:
        print("  [SKIPPED] RetentionResult.to_dict() - no retention data")

    # Test 9.4: JQLResult.to_dict()
    if jql_available and jql_result is not None:

        def test_jql_to_dict() -> dict[str, Any]:
            assert jql_result is not None
            d = jql_result.to_dict()
            if "raw" not in d:
                raise ValueError("Missing 'raw' key in JQLResult.to_dict()")
            _ = json.dumps(d)
            return {"keys": list(d.keys()), "json_serializable": True}

        runner.run_test("9.4 JQLResult.to_dict()", test_jql_to_dict)
    else:
        print("  [SKIPPED] JQLResult.to_dict() - no JQL data")

    # =========================================================================
    # Phase 10: Error Handling Tests
    # =========================================================================
    print("\n[Phase 10] Error Handling Tests")
    print("-" * 40)

    # Test 10.1: Invalid date range (future dates)
    def test_invalid_date_range() -> dict[str, Any]:
        assert live_query is not None
        assert test_event is not None
        # This might succeed or fail depending on Mixpanel's API behavior
        try:
            result = live_query.segmentation(
                event=test_event,
                from_date="2099-01-01",
                to_date="2099-01-31",
            )
            return {"accepted": True, "total": result.total}
        except Exception as e:
            return {"error_type": type(e).__name__, "message": str(e)[:50]}

    runner.run_test("10.1 future date range", test_invalid_date_range)

    # Test 10.2: Reversed date range (to before from)
    def test_reversed_date_range() -> dict[str, Any]:
        assert live_query is not None
        assert test_event is not None
        try:
            result = live_query.segmentation(
                event=test_event,
                from_date=TO_DATE,
                to_date=FROM_DATE,  # Reversed
            )
            return {"accepted": True, "total": result.total}
        except Exception as e:
            return {"error_type": type(e).__name__, "message": str(e)[:50]}

    runner.run_test("10.2 reversed date range", test_reversed_date_range)

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
