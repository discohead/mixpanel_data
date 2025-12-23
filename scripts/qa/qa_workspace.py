#!/usr/bin/env python3
"""Live QA integration test for Phase 009 Workspace Facade.

This script performs real API calls against Mixpanel to verify the
Workspace facade class which is the unified entry point for all
Mixpanel data operations.

Tests:
- Construction modes (standard, ephemeral, open, context manager)
- Discovery methods (events, properties, funnels, cohorts, top_events)
- Fetching methods (fetch_events, fetch_profiles)
- Local query methods (sql, sql_scalar, sql_rows)
- Live query methods (segmentation, funnel, retention, jql, etc.)
- Introspection methods (info, tables, schema)
- Table management (drop, drop_all)
- Escape hatches (connection, api)
- Error handling (ConfigError, AccountNotFoundError, TableExistsError, etc.)

Usage:
    uv run python scripts/qa_workspace.py

Prerequisites:
    - Service account configured in ~/.mp/config.toml
    - Account name: sinkapp-prod
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mixpanel_data.types import (
        ActivityFeedResult,
        EventCountsResult,
        FetchResult,
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
    from mixpanel_data.workspace import Workspace


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
        print("QA TEST RESULTS - Workspace Facade (Phase 009)")
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
    temp_db_path: Path | None = None

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

    # Use a small date range for fetch tests (to limit data)
    FETCH_DATE = last_month_start.strftime("%Y-%m-%d")

    print(f"Using date range: {FROM_DATE} to {TO_DATE}")
    print(f"Fetch test date: {FETCH_DATE}")
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
    fetch_events_result: FetchResult | None = None
    fetch_profiles_result: FetchResult | None = None

    # =========================================================================
    # Phase 1: Prerequisites & Imports
    # =========================================================================
    print("\n[Phase 1] Prerequisites & Imports")
    print("-" * 40)

    # Test 1.1: Import Workspace from public API
    def test_import_workspace() -> dict[str, Any]:
        from mixpanel_data import Workspace  # noqa: F401

        return {"module": "mixpanel_data.Workspace imported successfully"}

    result = runner.run_test("1.1 Import Workspace", test_import_workspace)
    if not result.passed:
        print("Cannot continue - import failed")
        runner.print_results()
        return 1

    # Test 1.2: Import result types
    def test_import_types() -> dict[str, Any]:
        from mixpanel_data.types import (
            ActivityFeedResult,  # noqa: F401
            ColumnInfo,  # noqa: F401
            EventCountsResult,  # noqa: F401
            FetchResult,  # noqa: F401
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
            TableInfo,  # noqa: F401
            TableSchema,  # noqa: F401
            TopEvent,  # noqa: F401
            WorkspaceInfo,  # noqa: F401
        )

        return {"types": "All result types imported successfully"}

    runner.run_test("1.2 Import result types", test_import_types)

    # Test 1.3: Import exceptions
    def test_import_exceptions() -> dict[str, Any]:
        from mixpanel_data.exceptions import (
            AccountNotFoundError,  # noqa: F401
            ConfigError,  # noqa: F401
            TableExistsError,  # noqa: F401
            TableNotFoundError,  # noqa: F401
        )

        return {"exceptions": "All exception types imported successfully"}

    runner.run_test("1.3 Import exceptions", test_import_exceptions)

    # Test 1.4: Verify account exists
    def test_verify_account() -> dict[str, Any]:
        from mixpanel_data._internal.config import ConfigManager

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
        nonlocal ws, temp_db_path
        from mixpanel_data import Workspace

        # Create temp directory for test database
        temp_dir = Path(tempfile.mkdtemp())
        temp_db_path = temp_dir / "qa_workspace_test.db"

        ws = Workspace(account=ACCOUNT_NAME, path=temp_db_path)
        return {
            "created": True,
            "path": str(temp_db_path),
        }

    result = runner.run_test("2.1 Standard construction", test_standard_construction)
    if not result.passed:
        print("Cannot continue - workspace creation failed")
        runner.print_results()
        return 1

    # Test 2.2: Context manager
    def test_context_manager() -> dict[str, Any]:
        from mixpanel_data import Workspace

        temp_path = Path(tempfile.mkdtemp()) / "context_test.db"
        with Workspace(account=ACCOUNT_NAME, path=temp_path) as ctx_ws:
            info = ctx_ws.info()
            tables = info.tables
        return {
            "context_worked": True,
            "tables_accessed": len(tables),
        }

    runner.run_test("2.2 Context manager", test_context_manager)

    # Test 2.3: Ephemeral mode with cleanup verification
    def test_ephemeral_mode() -> dict[str, Any]:
        from mixpanel_data import Workspace

        captured_path: Path | None = None
        with Workspace.ephemeral(account=ACCOUNT_NAME) as eph_ws:
            # Capture the temp path
            captured_path = eph_ws._storage.path
            info = eph_ws.info()
            project_id = info.project_id

        # Verify cleanup
        cleanup_verified = captured_path is None or not captured_path.exists()
        return {
            "ephemeral_worked": True,
            "project_id": project_id,
            "path_was_temp": captured_path is not None,
            "cleanup_verified": cleanup_verified,
        }

    runner.run_test("2.3 Ephemeral mode with cleanup", test_ephemeral_mode)

    # Test 2.4: Query-only mode (Workspace.open)
    def test_query_only_mode() -> dict[str, Any]:
        from mixpanel_data import Workspace

        # First create a database with data
        temp_path = Path(tempfile.mkdtemp()) / "open_test.db"
        with Workspace(account=ACCOUNT_NAME, path=temp_path):
            # Just create empty - we'll test querying
            pass

        # Now open in query-only mode
        open_ws = Workspace.open(temp_path)
        try:
            info = open_ws.info()
            # Project should be "unknown" since no credentials
            project_unknown = info.project_id == "unknown"
            return {
                "open_worked": True,
                "project_unknown": project_unknown,
                "tables": info.tables,
            }
        finally:
            open_ws.close()

    runner.run_test("2.4 Query-only mode (Workspace.open)", test_query_only_mode)

    # Test 2.5: Error - Invalid account
    def test_invalid_account_error() -> dict[str, Any]:
        from mixpanel_data import Workspace
        from mixpanel_data.exceptions import AccountNotFoundError

        try:
            Workspace(account="nonexistent_account_xyz_12345")
            raise AssertionError("Should have raised AccountNotFoundError")
        except AccountNotFoundError as e:
            return {"error_code": e.code, "raised": True}

    runner.run_test("2.5 Error: Invalid account", test_invalid_account_error)

    # Test 2.6: Error - Workspace.open with non-existent path
    def test_open_nonexistent_error() -> dict[str, Any]:
        from mixpanel_data import Workspace

        try:
            Workspace.open("/nonexistent/path/to/database.db")
            raise AssertionError("Should have raised FileNotFoundError")
        except FileNotFoundError:
            return {"raised": True}

    runner.run_test("2.6 Error: Open non-existent path", test_open_nonexistent_error)

    # Test 2.7: Error - API access on query-only workspace
    def test_api_access_query_only_error() -> dict[str, Any]:
        from mixpanel_data import Workspace
        from mixpanel_data.exceptions import ConfigError

        temp_path = Path(tempfile.mkdtemp()) / "api_test.db"
        # Create database first
        with Workspace(account=ACCOUNT_NAME, path=temp_path):
            pass

        # Open in query-only mode
        open_ws = Workspace.open(temp_path)
        try:
            # Try to access API method
            open_ws.events()
            raise AssertionError("Should have raised ConfigError")
        except ConfigError as e:
            return {"error_code": e.code, "raised": True}
        finally:
            open_ws.close()

    runner.run_test(
        "2.7 Error: API on query-only workspace", test_api_access_query_only_error
    )

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
        from mixpanel_data.types import FunnelInfo

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
        from mixpanel_data.types import SavedCohort

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
        from mixpanel_data.types import TopEvent

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
    # Phase 4: Fetching & Local Queries
    # =========================================================================
    print("\n[Phase 4] Fetching & Local Queries")
    print("-" * 40)

    # Test 4.1: fetch_events()
    def test_fetch_events() -> dict[str, Any]:
        nonlocal fetch_events_result
        from mixpanel_data.types import FetchResult

        assert ws is not None
        fetch_events_result = ws.fetch_events(
            name="qa_events",
            from_date=FETCH_DATE,
            to_date=FETCH_DATE,
            events=[KNOWN_EVENT],
            progress=False,
        )
        if not isinstance(fetch_events_result, FetchResult):
            raise TypeError(f"Expected FetchResult, got {type(fetch_events_result)}")
        return {
            "table": fetch_events_result.table,
            "rows": fetch_events_result.rows,
            "type": fetch_events_result.type,
            "date_range": fetch_events_result.date_range,
            "duration": f"{fetch_events_result.duration_seconds:.2f}s",
        }

    runner.run_test("4.1 fetch_events()", test_fetch_events)

    # Test 4.2: fetch_profiles()
    def test_fetch_profiles() -> dict[str, Any]:
        nonlocal fetch_profiles_result
        from mixpanel_data.types import FetchResult

        assert ws is not None
        # Use a where clause to limit results
        fetch_profiles_result = ws.fetch_profiles(
            name="qa_profiles",
            progress=False,
        )
        if not isinstance(fetch_profiles_result, FetchResult):
            raise TypeError(f"Expected FetchResult, got {type(fetch_profiles_result)}")
        return {
            "table": fetch_profiles_result.table,
            "rows": fetch_profiles_result.rows,
            "type": fetch_profiles_result.type,
            "date_range": fetch_profiles_result.date_range,  # Should be None
            "duration": f"{fetch_profiles_result.duration_seconds:.2f}s",
        }

    runner.run_test("4.2 fetch_profiles()", test_fetch_profiles)

    # Test 4.3: TableExistsError
    def test_table_exists_error() -> dict[str, Any]:
        from mixpanel_data.exceptions import TableExistsError

        assert ws is not None
        try:
            ws.fetch_events(
                name="qa_events",  # Already exists
                from_date=FETCH_DATE,
                to_date=FETCH_DATE,
                progress=False,
            )
            raise AssertionError("Should have raised TableExistsError")
        except TableExistsError as e:
            return {"error_code": e.code, "raised": True}

    runner.run_test("4.3 Error: TableExistsError", test_table_exists_error)

    # Test 4.4: sql() - DataFrame query
    def test_sql_dataframe() -> dict[str, Any]:
        import pandas as pd

        assert ws is not None
        df = ws.sql("SELECT * FROM qa_events LIMIT 10")
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Expected DataFrame, got {type(df)}")
        return {
            "columns": list(df.columns),
            "rows": len(df),
        }

    runner.run_test("4.4 sql() DataFrame", test_sql_dataframe)

    # Test 4.5: sql_scalar()
    def test_sql_scalar() -> dict[str, Any]:
        assert ws is not None
        count = ws.sql_scalar("SELECT COUNT(*) FROM qa_events")
        if not isinstance(count, int):
            raise TypeError(f"Expected int, got {type(count)}")
        return {
            "count": count,
        }

    runner.run_test("4.5 sql_scalar()", test_sql_scalar)

    # Test 4.6: sql_rows()
    def test_sql_rows() -> dict[str, Any]:
        assert ws is not None
        rows = ws.sql_rows("SELECT event_name FROM qa_events LIMIT 5")
        if not isinstance(rows, list):
            raise TypeError(f"Expected list, got {type(rows)}")
        if rows and not isinstance(rows[0], tuple):
            raise TypeError(f"Expected tuple, got {type(rows[0])}")
        return {
            "count": len(rows),
            "sample": rows[:3] if rows else [],
        }

    runner.run_test("4.6 sql_rows()", test_sql_rows)

    # Test 4.7: JSON property querying
    def test_json_property_query() -> dict[str, Any]:
        assert ws is not None
        df = ws.sql("""
            SELECT
                event_name,
                json_extract_string(properties, '$.$browser') as browser
            FROM qa_events
            WHERE json_extract_string(properties, '$.$browser') IS NOT NULL
            LIMIT 5
        """)
        return {
            "columns": list(df.columns),
            "rows": len(df),
            "has_browser_col": "browser" in df.columns,
        }

    runner.run_test("4.7 JSON property query", test_json_property_query)

    # =========================================================================
    # Phase 5: Live Query Methods
    # =========================================================================
    print("\n[Phase 5] Live Query Methods")
    print("-" * 40)

    # Test 5.1: segmentation()
    def test_segmentation() -> dict[str, Any]:
        nonlocal segmentation_result
        from mixpanel_data.types import SegmentationResult

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

    runner.run_test("5.1 segmentation()", test_segmentation)

    # Test 5.2: event_counts()
    def test_event_counts() -> dict[str, Any]:
        nonlocal event_counts_result
        from mixpanel_data.types import EventCountsResult

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

    runner.run_test("5.2 event_counts()", test_event_counts)

    # Test 5.3: property_counts()
    def test_property_counts() -> dict[str, Any]:
        nonlocal property_counts_result
        from mixpanel_data.types import PropertyCountsResult

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

    runner.run_test("5.3 property_counts()", test_property_counts)

    # Test 5.4: funnel() - only if funnels exist
    def test_funnel() -> dict[str, Any]:
        nonlocal funnel_result
        from mixpanel_data.types import FunnelResult

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

    runner.run_test("5.4 funnel()", test_funnel)

    # Test 5.5: retention()
    def test_retention() -> dict[str, Any]:
        nonlocal retention_result
        from mixpanel_data.types import RetentionResult

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

    runner.run_test("5.5 retention()", test_retention)

    # Test 5.6: jql()
    def test_jql() -> dict[str, Any]:
        nonlocal jql_result
        from mixpanel_data.types import JQLResult

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

    runner.run_test("5.6 jql()", test_jql)

    # Test 5.7: activity_feed()
    def test_activity_feed() -> dict[str, Any]:
        nonlocal activity_result
        from mixpanel_data.types import ActivityFeedResult

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

    runner.run_test("5.7 activity_feed()", test_activity_feed)

    # Test 5.8: insights()
    def test_insights() -> dict[str, Any]:
        nonlocal insights_result
        from mixpanel_data.types import InsightsResult

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

    runner.run_test("5.8 insights()", test_insights)

    # Test 5.9: frequency()
    def test_frequency() -> dict[str, Any]:
        nonlocal frequency_result
        from mixpanel_data.types import FrequencyResult

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

    runner.run_test("5.9 frequency()", test_frequency)

    # Test 5.10: segmentation_numeric()
    def test_segmentation_numeric() -> dict[str, Any]:
        nonlocal numeric_bucket_result
        from mixpanel_data.types import NumericBucketResult

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

    runner.run_test("5.10 segmentation_numeric()", test_segmentation_numeric)

    # Test 5.11: segmentation_sum()
    def test_segmentation_sum() -> dict[str, Any]:
        nonlocal numeric_sum_result
        from mixpanel_data.types import NumericSumResult

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

    runner.run_test("5.11 segmentation_sum()", test_segmentation_sum)

    # Test 5.12: segmentation_average()
    def test_segmentation_average() -> dict[str, Any]:
        nonlocal numeric_avg_result
        from mixpanel_data.types import NumericAverageResult

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

    runner.run_test("5.12 segmentation_average()", test_segmentation_average)

    # =========================================================================
    # Phase 6: Result Type Validation
    # =========================================================================
    print("\n[Phase 6] Result Type Validation")
    print("-" * 40)

    # Test 6.1: SegmentationResult.df
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

    runner.run_test("6.1 SegmentationResult.df", test_segmentation_df)

    # Test 6.2: EventCountsResult.df
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

    runner.run_test("6.2 EventCountsResult.df", test_event_counts_df)

    # Test 6.3: PropertyCountsResult.df
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

    runner.run_test("6.3 PropertyCountsResult.df", test_property_counts_df)

    # Test 6.4: FunnelResult.df
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

    runner.run_test("6.4 FunnelResult.df", test_funnel_df)

    # Test 6.5: RetentionResult.df
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

    runner.run_test("6.5 RetentionResult.df", test_retention_df)

    # Test 6.6: JQLResult.df
    def test_jql_df() -> dict[str, Any]:
        if jql_result is None:
            return {"skipped": "No JQL result"}
        df = jql_result.df
        df2 = jql_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {"columns": list(df.columns), "rows": len(df), "cached": True}

    runner.run_test("6.6 JQLResult.df", test_jql_df)

    # Test 6.7: ActivityFeedResult.df
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

    runner.run_test("6.7 ActivityFeedResult.df", test_activity_feed_df)

    # Test 6.8: InsightsResult.df
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

    runner.run_test("6.8 InsightsResult.df", test_insights_df)

    # Test 6.9: FrequencyResult.df
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

    runner.run_test("6.9 FrequencyResult.df", test_frequency_df)

    # Test 6.10: NumericBucketResult.df
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

    runner.run_test("6.10 NumericBucketResult.df", test_numeric_bucket_df)

    # Test 6.11: NumericSumResult.df
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

    runner.run_test("6.11 NumericSumResult.df", test_numeric_sum_df)

    # Test 6.12: NumericAverageResult.df
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

    runner.run_test("6.12 NumericAverageResult.df", test_numeric_avg_df)

    # Test 6.13: All results JSON serializable
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
            ("FetchResult (events)", fetch_events_result),
            ("FetchResult (profiles)", fetch_profiles_result),
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

    runner.run_test("6.13 All results JSON serializable", test_all_json_serializable)

    # =========================================================================
    # Phase 7: Introspection Methods
    # =========================================================================
    print("\n[Phase 7] Introspection Methods")
    print("-" * 40)

    # Test 7.1: info()
    def test_info() -> dict[str, Any]:
        from mixpanel_data.types import WorkspaceInfo

        assert ws is not None
        info = ws.info()
        if not isinstance(info, WorkspaceInfo):
            raise TypeError(f"Expected WorkspaceInfo, got {type(info)}")
        return {
            "path": str(info.path) if info.path else None,
            "project_id": info.project_id,
            "region": info.region,
            "account": info.account,
            "tables": info.tables,
            "size_mb": f"{info.size_mb:.2f}",
        }

    runner.run_test("7.1 info()", test_info)

    # Test 7.2: tables()
    def test_tables() -> dict[str, Any]:
        from mixpanel_data.types import TableInfo

        assert ws is not None
        tables = ws.tables()
        if not isinstance(tables, list):
            raise TypeError(f"Expected list, got {type(tables)}")
        if tables and not isinstance(tables[0], TableInfo):
            raise TypeError(f"Expected TableInfo, got {type(tables[0])}")
        return {
            "count": len(tables),
            "tables": [
                {"name": t.name, "type": t.type, "rows": t.row_count} for t in tables
            ],
        }

    runner.run_test("7.2 tables()", test_tables)

    # Test 7.3: schema()
    def test_schema() -> dict[str, Any]:
        from mixpanel_data.types import TableSchema

        assert ws is not None
        schema = ws.schema("qa_events")
        if not isinstance(schema, TableSchema):
            raise TypeError(f"Expected TableSchema, got {type(schema)}")
        return {
            "table_name": schema.table_name,
            "column_count": len(schema.columns),
            "columns": [c.name for c in schema.columns],
        }

    runner.run_test("7.3 schema()", test_schema)

    # Test 7.4: schema() error - non-existent table
    def test_schema_error() -> dict[str, Any]:
        from mixpanel_data.exceptions import TableNotFoundError

        assert ws is not None
        try:
            ws.schema("nonexistent_table_xyz")
            raise AssertionError("Should have raised TableNotFoundError")
        except TableNotFoundError as e:
            return {"error_code": e.code, "raised": True}

    runner.run_test("7.4 Error: schema() non-existent", test_schema_error)

    # =========================================================================
    # Phase 8: Table Management
    # =========================================================================
    print("\n[Phase 8] Table Management")
    print("-" * 40)

    # Test 8.1: drop() error - non-existent table
    def test_drop_error() -> dict[str, Any]:
        from mixpanel_data.exceptions import TableNotFoundError

        assert ws is not None
        try:
            ws.drop("nonexistent_table_xyz")
            raise AssertionError("Should have raised TableNotFoundError")
        except TableNotFoundError as e:
            return {"error_code": e.code, "raised": True}

    runner.run_test("8.1 Error: drop() non-existent", test_drop_error)

    # Test 8.2: drop() single table
    def test_drop_single() -> dict[str, Any]:
        assert ws is not None
        # First check table exists
        tables_before = [t.name for t in ws.tables()]
        if "qa_profiles" not in tables_before:
            return {"skipped": "qa_profiles not in tables"}
        ws.drop("qa_profiles")
        tables_after = [t.name for t in ws.tables()]
        return {
            "dropped": "qa_profiles",
            "tables_before": tables_before,
            "tables_after": tables_after,
        }

    runner.run_test("8.2 drop() single table", test_drop_single)

    # Test 8.3: drop_all()
    def test_drop_all() -> dict[str, Any]:
        assert ws is not None
        tables_before = [t.name for t in ws.tables()]
        ws.drop_all()
        tables_after = [t.name for t in ws.tables()]
        return {
            "tables_before": tables_before,
            "tables_after": tables_after,
            "all_dropped": len(tables_after) == 0,
        }

    runner.run_test("8.3 drop_all()", test_drop_all)

    # =========================================================================
    # Phase 9: Escape Hatches
    # =========================================================================
    print("\n[Phase 9] Escape Hatches")
    print("-" * 40)

    # Test 9.1: .connection property
    def test_connection_property() -> dict[str, Any]:
        import duckdb

        assert ws is not None
        conn = ws.connection
        if not isinstance(conn, duckdb.DuckDBPyConnection):
            raise TypeError(f"Expected DuckDBPyConnection, got {type(conn)}")
        # Execute a simple query
        result = conn.execute("SELECT 1 + 1 AS sum").fetchone()
        return {
            "type": type(conn).__name__,
            "query_result": result[0] if result else None,
        }

    runner.run_test("9.1 .connection property", test_connection_property)

    # Test 9.2: .api property
    def test_api_property() -> dict[str, Any]:
        from mixpanel_data._internal.api_client import MixpanelAPIClient

        assert ws is not None
        api = ws.api
        if not isinstance(api, MixpanelAPIClient):
            raise TypeError(f"Expected MixpanelAPIClient, got {type(api)}")
        return {
            "type": type(api).__name__,
            "has_credentials": api._credentials is not None,
        }

    runner.run_test("9.2 .api property", test_api_property)

    # Test 9.3: Direct SQL via .connection
    def test_direct_sql() -> dict[str, Any]:
        assert ws is not None
        conn = ws.connection
        # Create a temp table and query it
        conn.execute("CREATE TEMP TABLE test_direct AS SELECT 42 AS value")
        result = conn.execute("SELECT value FROM test_direct").fetchone()
        conn.execute("DROP TABLE test_direct")
        return {
            "query_worked": True,
            "value": result[0] if result else None,
        }

    runner.run_test("9.3 Direct SQL via .connection", test_direct_sql)

    # Test 9.4: .api error on query-only workspace
    def test_api_error_query_only() -> dict[str, Any]:
        from mixpanel_data import Workspace
        from mixpanel_data.exceptions import ConfigError

        temp_path = Path(tempfile.mkdtemp()) / "api_error_test.db"
        # Create database first
        with Workspace(account=ACCOUNT_NAME, path=temp_path):
            pass

        open_ws = Workspace.open(temp_path)
        try:
            _ = open_ws.api
            raise AssertionError("Should have raised ConfigError")
        except ConfigError as e:
            return {"error_code": e.code, "raised": True}
        finally:
            open_ws.close()

    runner.run_test("9.4 Error: .api on query-only", test_api_error_query_only)

    # =========================================================================
    # Phase 10: Cleanup
    # =========================================================================
    print("\n[Phase 10] Cleanup")
    print("-" * 40)

    # Test 10.1: Close workspace
    def test_close_workspace() -> dict[str, Any]:
        nonlocal ws
        assert ws is not None
        ws.close()
        # Verify close is idempotent
        ws.close()
        ws = None
        return {"closed": True, "idempotent": True}

    runner.run_test("10.1 Close workspace", test_close_workspace)

    # Test 10.2: Cleanup temp files
    def test_cleanup_temp_files() -> dict[str, Any]:
        if temp_db_path and temp_db_path.exists():
            temp_db_path.unlink()
            if temp_db_path.parent.exists():
                temp_db_path.parent.rmdir()
        return {"cleaned_up": True}

    runner.run_test("10.2 Cleanup temp files", test_cleanup_temp_files)

    # =========================================================================
    # Results
    # =========================================================================
    runner.print_results()

    # Return exit code
    failed = sum(1 for r in runner.results if not r.passed)
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
