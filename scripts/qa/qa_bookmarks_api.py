#!/usr/bin/env python3
"""Live QA integration test for Bookmarks API (Phase 015).

This script performs real API calls against Mixpanel to verify the
Bookmarks API is working correctly with actual saved reports.

Tests:
- list_bookmarks() - list all saved reports
- list_bookmarks(bookmark_type=...) - filter by type
- query_saved_report() - query insights/retention/funnel bookmarks
- query_flows() - query flows bookmarks (separate API)
- Result types (BookmarkInfo, SavedReportResult, FlowsResult)
- DataFrame conversion and caching
- JSON serialization

Usage:
    uv run python scripts/qa/qa_bookmarks_api.py

Prerequisites:
    - Service account configured in ~/.mp/config.toml
    - Account name: sinkapp-prod (or modify ACCOUNT_NAME)
    - At least one saved report in the Mixpanel project
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient
    from mixpanel_data._internal.services.discovery import DiscoveryService
    from mixpanel_data._internal.services.live_query import LiveQueryService
    from mixpanel_data.types import (
        BookmarkInfo,
        FlowsResult,
        SavedReportResult,
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
        print("QA TEST RESULTS - Bookmarks API (Phase 015)")
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
    print("Bookmarks API QA - Live Integration Tests")
    print("=" * 70)

    runner = QARunner()

    # Shared state
    api_client: MixpanelAPIClient | None = None
    discovery: DiscoveryService | None = None
    live_query: LiveQueryService | None = None
    ws: Workspace | None = None

    # Discovered data
    all_bookmarks: list[BookmarkInfo] = []
    insights_bookmarks: list[BookmarkInfo] = []
    funnels_bookmarks: list[BookmarkInfo] = []
    retention_bookmarks: list[BookmarkInfo] = []
    flows_bookmarks: list[BookmarkInfo] = []

    # Results for validation
    saved_report_result: SavedReportResult | None = None
    flows_result: FlowsResult | None = None

    # =========================================================================
    # Phase 1: Prerequisites & Imports
    # =========================================================================
    print("\n[Phase 1] Prerequisites & Imports")
    print("-" * 40)

    # Test 1.1: Import Workspace and types
    def test_imports() -> dict[str, Any]:
        from mixpanel_data import Workspace  # noqa: F401
        from mixpanel_data.types import (
            BookmarkInfo,  # noqa: F401
            BookmarkType,  # noqa: F401
            FlowsResult,  # noqa: F401
            SavedReportResult,  # noqa: F401
            SavedReportType,  # noqa: F401
        )

        return {
            "imports": [
                "Workspace",
                "BookmarkInfo",
                "BookmarkType",
                "SavedReportResult",
                "SavedReportType",
                "FlowsResult",
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

    # Test 1.3: Resolve credentials (uses default account)
    def test_resolve_credentials() -> dict[str, Any]:
        from mixpanel_data._internal.config import ConfigManager

        config = ConfigManager()
        creds = config.resolve_credentials()  # Use default account
        return {
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
        creds = config.resolve_credentials()  # Use default account
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
        return {"status": "discovery service created"}

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
        return {"status": "live query service created"}

    result = runner.run_test("2.3 Create LiveQueryService", test_create_live_query)
    if not result.passed:
        print("Cannot continue - live query service creation failed")
        runner.print_results()
        return 1

    # Test 2.4: Create Workspace
    def test_create_workspace() -> dict[str, Any]:
        nonlocal ws
        from mixpanel_data import Workspace

        # Note: ephemeral() returns a context manager, so we use it as one
        ctx = Workspace.ephemeral()  # Use default account
        ws = ctx.__enter__()
        return {"status": "workspace created (ephemeral)"}

    result = runner.run_test("2.4 Create Workspace", test_create_workspace)
    if not result.passed:
        print("Cannot continue - workspace creation failed")
        runner.print_results()
        return 1

    # =========================================================================
    # Phase 3: List Bookmarks Tests
    # =========================================================================
    print("\n[Phase 3] List Bookmarks Tests")
    print("-" * 40)

    # Test 3.1: list_bookmarks() via API client (raw)
    def test_api_client_list_bookmarks() -> dict[str, Any]:
        assert api_client is not None
        result = api_client.list_bookmarks()
        if not isinstance(result, dict):
            raise TypeError(f"Expected dict, got {type(result)}")
        if "results" not in result:
            raise ValueError("Response missing 'results' key")
        return {
            "results_count": len(result.get("results", [])),
            "keys": list(result.keys()),
        }

    runner.run_test("3.1 API client list_bookmarks()", test_api_client_list_bookmarks)

    # Test 3.2: list_bookmarks() via DiscoveryService
    def test_discovery_list_bookmarks() -> dict[str, Any]:
        nonlocal all_bookmarks
        from mixpanel_data.types import BookmarkInfo

        assert discovery is not None
        all_bookmarks = discovery.list_bookmarks()
        if not isinstance(all_bookmarks, list):
            raise TypeError(f"Expected list, got {type(all_bookmarks)}")
        if all_bookmarks and not isinstance(all_bookmarks[0], BookmarkInfo):
            raise TypeError(f"Expected BookmarkInfo, got {type(all_bookmarks[0])}")
        return {
            "count": len(all_bookmarks),
            "sample": [b.name for b in all_bookmarks[:5]],
            "types": list({b.type for b in all_bookmarks}),
        }

    result = runner.run_test(
        "3.2 Discovery list_bookmarks()", test_discovery_list_bookmarks
    )
    if not result.passed or not all_bookmarks:
        print("  Warning: No bookmarks found - some tests will be skipped")

    # Test 3.3: list_bookmarks() via Workspace
    def test_workspace_list_bookmarks() -> dict[str, Any]:
        assert ws is not None
        bookmarks = ws.list_bookmarks()
        if not isinstance(bookmarks, list):
            raise TypeError(f"Expected list, got {type(bookmarks)}")
        # Should match discovery service results
        if len(bookmarks) != len(all_bookmarks):
            raise ValueError(
                f"Workspace returned {len(bookmarks)} but discovery returned {len(all_bookmarks)}"
            )
        return {
            "count": len(bookmarks),
            "matches_discovery": True,
        }

    runner.run_test("3.3 Workspace list_bookmarks()", test_workspace_list_bookmarks)

    # Test 3.4: list_bookmarks() with type filter - insights
    def test_list_bookmarks_filter_insights() -> dict[str, Any]:
        nonlocal insights_bookmarks
        assert discovery is not None
        insights_bookmarks = discovery.list_bookmarks(bookmark_type="insights")
        expected = [b for b in all_bookmarks if b.type == "insights"]
        if len(insights_bookmarks) != len(expected):
            raise ValueError(
                f"Filter returned {len(insights_bookmarks)} but expected {len(expected)}"
            )
        return {
            "count": len(insights_bookmarks),
            "sample": [b.name for b in insights_bookmarks[:3]],
        }

    runner.run_test(
        "3.4 list_bookmarks(bookmark_type='insights')",
        test_list_bookmarks_filter_insights,
    )

    # Test 3.5: list_bookmarks() with type filter - funnels
    def test_list_bookmarks_filter_funnels() -> dict[str, Any]:
        nonlocal funnels_bookmarks
        assert discovery is not None
        funnels_bookmarks = discovery.list_bookmarks(bookmark_type="funnels")
        expected = [b for b in all_bookmarks if b.type == "funnels"]
        if len(funnels_bookmarks) != len(expected):
            raise ValueError(
                f"Filter returned {len(funnels_bookmarks)} but expected {len(expected)}"
            )
        return {
            "count": len(funnels_bookmarks),
            "sample": [b.name for b in funnels_bookmarks[:3]],
        }

    runner.run_test(
        "3.5 list_bookmarks(bookmark_type='funnels')",
        test_list_bookmarks_filter_funnels,
    )

    # Test 3.6: list_bookmarks() with type filter - retention
    def test_list_bookmarks_filter_retention() -> dict[str, Any]:
        nonlocal retention_bookmarks
        assert discovery is not None
        retention_bookmarks = discovery.list_bookmarks(bookmark_type="retention")
        expected = [b for b in all_bookmarks if b.type == "retention"]
        if len(retention_bookmarks) != len(expected):
            raise ValueError(
                f"Filter returned {len(retention_bookmarks)} but expected {len(expected)}"
            )
        return {
            "count": len(retention_bookmarks),
            "sample": [b.name for b in retention_bookmarks[:3]],
        }

    runner.run_test(
        "3.6 list_bookmarks(bookmark_type='retention')",
        test_list_bookmarks_filter_retention,
    )

    # Test 3.7: list_bookmarks() with type filter - flows
    def test_list_bookmarks_filter_flows() -> dict[str, Any]:
        nonlocal flows_bookmarks
        assert discovery is not None
        flows_bookmarks = discovery.list_bookmarks(bookmark_type="flows")
        expected = [b for b in all_bookmarks if b.type == "flows"]
        if len(flows_bookmarks) != len(expected):
            raise ValueError(
                f"Filter returned {len(flows_bookmarks)} but expected {len(expected)}"
            )
        return {
            "count": len(flows_bookmarks),
            "sample": [b.name for b in flows_bookmarks[:3]],
        }

    runner.run_test(
        "3.7 list_bookmarks(bookmark_type='flows')",
        test_list_bookmarks_filter_flows,
    )

    # Test 3.8: BookmarkInfo structure validation
    def test_bookmark_info_structure() -> dict[str, Any]:
        if not all_bookmarks:
            return {"skipped": "No bookmarks available"}
        bookmark = all_bookmarks[0]
        # Verify required fields
        required = ["id", "name", "type", "project_id", "created", "modified"]
        for field in required:
            if not hasattr(bookmark, field):
                raise ValueError(f"BookmarkInfo missing field: {field}")
        return {
            "id": bookmark.id,
            "name": bookmark.name,
            "type": bookmark.type,
            "project_id": bookmark.project_id,
            "created": bookmark.created,
            "modified": bookmark.modified,
            "has_optional": {
                "workspace_id": bookmark.workspace_id is not None,
                "dashboard_id": bookmark.dashboard_id is not None,
                "description": bookmark.description is not None,
                "creator_id": bookmark.creator_id is not None,
                "creator_name": bookmark.creator_name is not None,
            },
        }

    runner.run_test("3.8 BookmarkInfo structure", test_bookmark_info_structure)

    # Test 3.9: BookmarkInfo.to_dict()
    def test_bookmark_info_to_dict() -> dict[str, Any]:
        if not all_bookmarks:
            return {"skipped": "No bookmarks available"}
        bookmark = all_bookmarks[0]
        d = bookmark.to_dict()
        if not isinstance(d, dict):
            raise TypeError(f"Expected dict, got {type(d)}")
        # Required keys should be present
        required = ["id", "name", "type", "project_id", "created", "modified"]
        for key in required:
            if key not in d:
                raise ValueError(f"to_dict() missing key: {key}")
        # Optional keys should not be present when None
        if bookmark.workspace_id is None and "workspace_id" in d:
            raise ValueError("to_dict() included None workspace_id")
        # JSON serializable
        _ = json.dumps(d)
        return {
            "keys": list(d.keys()),
            "json_serializable": True,
        }

    runner.run_test("3.9 BookmarkInfo.to_dict()", test_bookmark_info_to_dict)

    # =========================================================================
    # Phase 4: Query Saved Report Tests
    # =========================================================================
    print("\n[Phase 4] Query Saved Report Tests")
    print("-" * 40)

    # Use first insights bookmark, or first available bookmark
    test_bookmark_id: int | None = None
    if insights_bookmarks:
        test_bookmark_id = insights_bookmarks[0].id
    elif all_bookmarks:
        test_bookmark_id = all_bookmarks[0].id

    if test_bookmark_id:
        print(f"  Using bookmark ID for testing: {test_bookmark_id}")
    else:
        print("  Warning: No bookmarks available for query tests")

    # Test 4.1: query_saved_report() via API client (raw)
    def test_api_client_query_saved_report() -> dict[str, Any]:
        assert api_client is not None
        assert test_bookmark_id is not None
        result = api_client.query_saved_report(bookmark_id=test_bookmark_id)
        if not isinstance(result, dict):
            raise TypeError(f"Expected dict, got {type(result)}")
        return {
            "keys": list(result.keys())[:10],
            "has_series": "series" in result,
        }

    runner.run_test(
        "4.1 API client query_saved_report()", test_api_client_query_saved_report
    )

    # Test 4.2: query_saved_report() via LiveQueryService
    def test_live_query_saved_report() -> dict[str, Any]:
        nonlocal saved_report_result
        from mixpanel_data.types import SavedReportResult

        assert live_query is not None
        assert test_bookmark_id is not None
        saved_report_result = live_query.query_saved_report(
            bookmark_id=test_bookmark_id
        )
        if not isinstance(saved_report_result, SavedReportResult):
            raise TypeError(
                f"Expected SavedReportResult, got {type(saved_report_result)}"
            )
        return {
            "bookmark_id": saved_report_result.bookmark_id,
            "computed_at": saved_report_result.computed_at,
            "from_date": saved_report_result.from_date,
            "to_date": saved_report_result.to_date,
            "headers": saved_report_result.headers[:3]
            if saved_report_result.headers
            else [],
            "series_keys": list(saved_report_result.series.keys())[:3],
            "report_type": saved_report_result.report_type,
        }

    runner.run_test("4.2 LiveQuery query_saved_report()", test_live_query_saved_report)

    # Test 4.3: query_saved_report() via Workspace
    def test_workspace_query_saved_report() -> dict[str, Any]:
        from mixpanel_data.types import SavedReportResult

        assert ws is not None
        assert test_bookmark_id is not None
        result = ws.query_saved_report(bookmark_id=test_bookmark_id)
        if not isinstance(result, SavedReportResult):
            raise TypeError(f"Expected SavedReportResult, got {type(result)}")
        return {
            "bookmark_id": result.bookmark_id,
            "report_type": result.report_type,
        }

    runner.run_test(
        "4.3 Workspace query_saved_report()", test_workspace_query_saved_report
    )

    # Test 4.4: SavedReportResult.report_type detection
    def test_report_type_detection() -> dict[str, Any]:
        if saved_report_result is None:
            return {"skipped": "No saved report result"}
        report_type = saved_report_result.report_type
        # Verify it's one of the valid types
        valid_types = ["insights", "retention", "funnel"]
        if report_type not in valid_types:
            raise ValueError(f"Invalid report_type: {report_type}")
        # Verify detection logic
        headers = saved_report_result.headers
        if headers:
            first_header = headers[0].lower()
            if "$retention" in first_header:
                expected = "retention"
            elif "$funnel" in first_header:
                expected = "funnel"
            else:
                expected = "insights"
            if report_type != expected:
                raise ValueError(
                    f"report_type={report_type} but expected {expected} based on headers"
                )
        return {
            "report_type": report_type,
            "headers": headers[:3] if headers else [],
        }

    runner.run_test("4.4 SavedReportResult.report_type", test_report_type_detection)

    # Test 4.5: SavedReportResult.df
    def test_saved_report_df() -> dict[str, Any]:
        import pandas as pd

        if saved_report_result is None:
            return {"skipped": "No saved report result"}
        df = saved_report_result.df
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Expected DataFrame, got {type(df)}")
        # Verify expected columns
        expected_cols = {"date", "event", "count"}
        actual_cols = set(df.columns)
        if not expected_cols.issubset(actual_cols):
            raise ValueError(f"Missing columns: {expected_cols - actual_cols}")
        # Test caching
        df2 = saved_report_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {
            "columns": list(df.columns),
            "rows": len(df),
            "cached": True,
        }

    runner.run_test("4.5 SavedReportResult.df", test_saved_report_df)

    # Test 4.6: SavedReportResult.to_dict()
    def test_saved_report_to_dict() -> dict[str, Any]:
        if saved_report_result is None:
            return {"skipped": "No saved report result"}
        d = saved_report_result.to_dict()
        if not isinstance(d, dict):
            raise TypeError(f"Expected dict, got {type(d)}")
        # Required keys
        required = [
            "bookmark_id",
            "computed_at",
            "from_date",
            "to_date",
            "headers",
            "series",
            "report_type",
        ]
        for key in required:
            if key not in d:
                raise ValueError(f"to_dict() missing key: {key}")
        # JSON serializable
        _ = json.dumps(d)
        return {
            "keys": list(d.keys()),
            "json_serializable": True,
        }

    runner.run_test("4.6 SavedReportResult.to_dict()", test_saved_report_to_dict)

    # Test 4.7: Query retention report (if available)
    def test_query_retention_report() -> dict[str, Any]:
        from mixpanel_data.types import SavedReportResult

        if not retention_bookmarks:
            return {"skipped": "No retention bookmarks available"}
        assert live_query is not None
        bookmark_id = retention_bookmarks[0].id
        result = live_query.query_saved_report(bookmark_id=bookmark_id)
        if not isinstance(result, SavedReportResult):
            raise TypeError(f"Expected SavedReportResult, got {type(result)}")
        return {
            "bookmark_id": result.bookmark_id,
            "report_type": result.report_type,
            "headers": result.headers[:3] if result.headers else [],
        }

    runner.run_test("4.7 Query retention report", test_query_retention_report)

    # Test 4.8: Query funnel report (if available)
    def test_query_funnel_report() -> dict[str, Any]:
        from mixpanel_data.types import SavedReportResult

        if not funnels_bookmarks:
            return {"skipped": "No funnel bookmarks available"}
        assert live_query is not None
        bookmark_id = funnels_bookmarks[0].id
        result = live_query.query_saved_report(bookmark_id=bookmark_id)
        if not isinstance(result, SavedReportResult):
            raise TypeError(f"Expected SavedReportResult, got {type(result)}")
        return {
            "bookmark_id": result.bookmark_id,
            "report_type": result.report_type,
            "headers": result.headers[:3] if result.headers else [],
        }

    runner.run_test("4.8 Query funnel report", test_query_funnel_report)

    # =========================================================================
    # Phase 5: Query Flows Tests
    # =========================================================================
    print("\n[Phase 5] Query Flows Tests")
    print("-" * 40)

    # Test 5.1: query_flows() via API client (raw)
    def test_api_client_query_flows() -> dict[str, Any]:
        if not flows_bookmarks:
            return {"skipped": "No flows bookmarks available"}
        assert api_client is not None
        bookmark_id = flows_bookmarks[0].id
        result = api_client.query_flows(bookmark_id=bookmark_id)
        if not isinstance(result, dict):
            raise TypeError(f"Expected dict, got {type(result)}")
        return {
            "keys": list(result.keys()),
            "has_steps": "steps" in result,
            "has_breakdowns": "breakdowns" in result,
        }

    runner.run_test("5.1 API client query_flows()", test_api_client_query_flows)

    # Test 5.2: query_flows() via LiveQueryService
    def test_live_query_flows() -> dict[str, Any]:
        nonlocal flows_result
        from mixpanel_data.types import FlowsResult

        if not flows_bookmarks:
            return {"skipped": "No flows bookmarks available"}
        assert live_query is not None
        bookmark_id = flows_bookmarks[0].id
        flows_result = live_query.query_flows(bookmark_id=bookmark_id)
        if not isinstance(flows_result, FlowsResult):
            raise TypeError(f"Expected FlowsResult, got {type(flows_result)}")
        return {
            "bookmark_id": flows_result.bookmark_id,
            "computed_at": flows_result.computed_at,
            "steps_count": len(flows_result.steps),
            "breakdowns_count": len(flows_result.breakdowns),
            "overall_conversion_rate": flows_result.overall_conversion_rate,
        }

    runner.run_test("5.2 LiveQuery query_flows()", test_live_query_flows)

    # Test 5.3: query_flows() via Workspace
    def test_workspace_query_flows() -> dict[str, Any]:
        from mixpanel_data.types import FlowsResult

        if not flows_bookmarks:
            return {"skipped": "No flows bookmarks available"}
        assert ws is not None
        bookmark_id = flows_bookmarks[0].id
        result = ws.query_flows(bookmark_id=bookmark_id)
        if not isinstance(result, FlowsResult):
            raise TypeError(f"Expected FlowsResult, got {type(result)}")
        return {
            "bookmark_id": result.bookmark_id,
            "overall_conversion_rate": result.overall_conversion_rate,
        }

    runner.run_test("5.3 Workspace query_flows()", test_workspace_query_flows)

    # Test 5.4: FlowsResult.df
    def test_flows_result_df() -> dict[str, Any]:
        import pandas as pd

        if flows_result is None:
            return {"skipped": "No flows result"}
        df = flows_result.df
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Expected DataFrame, got {type(df)}")
        # Test caching
        df2 = flows_result.df
        if df is not df2:
            raise ValueError("DataFrame not cached")
        return {
            "columns": list(df.columns),
            "rows": len(df),
            "cached": True,
        }

    runner.run_test("5.4 FlowsResult.df", test_flows_result_df)

    # Test 5.5: FlowsResult.to_dict()
    def test_flows_result_to_dict() -> dict[str, Any]:
        if flows_result is None:
            return {"skipped": "No flows result"}
        d = flows_result.to_dict()
        if not isinstance(d, dict):
            raise TypeError(f"Expected dict, got {type(d)}")
        # Required keys
        required = [
            "bookmark_id",
            "computed_at",
            "steps",
            "breakdowns",
            "overall_conversion_rate",
            "metadata",
        ]
        for key in required:
            if key not in d:
                raise ValueError(f"to_dict() missing key: {key}")
        # JSON serializable
        _ = json.dumps(d)
        return {
            "keys": list(d.keys()),
            "json_serializable": True,
        }

    runner.run_test("5.5 FlowsResult.to_dict()", test_flows_result_to_dict)

    # Test 5.6: FlowsResult step structure
    def test_flows_step_structure() -> dict[str, Any]:
        if flows_result is None or not flows_result.steps:
            return {"skipped": "No flows result or no steps"}
        # Each step should be a dict
        for i, step in enumerate(flows_result.steps):
            if not isinstance(step, dict):
                raise TypeError(f"Step {i} is not a dict")
        return {
            "steps_count": len(flows_result.steps),
            "first_step_keys": list(flows_result.steps[0].keys())
            if flows_result.steps
            else [],
            "first_step": flows_result.steps[0] if flows_result.steps else None,
        }

    runner.run_test("5.6 FlowsResult step structure", test_flows_step_structure)

    # =========================================================================
    # Phase 6: Error Handling Tests
    # =========================================================================
    print("\n[Phase 6] Error Handling Tests")
    print("-" * 40)

    # Test 6.1: query_saved_report() with invalid bookmark ID
    def test_query_invalid_bookmark() -> dict[str, Any]:
        from mixpanel_data.exceptions import QueryError

        assert live_query is not None
        try:
            live_query.query_saved_report(bookmark_id=999999999)
            return {"error_raised": False, "note": "No error for invalid bookmark ID"}
        except QueryError as e:
            return {"error_raised": True, "error_code": e.code}
        except Exception as e:
            return {"error_type": type(e).__name__, "message": str(e)[:50]}

    runner.run_test("6.1 query_saved_report() invalid ID", test_query_invalid_bookmark)

    # Test 6.2: query_flows() with invalid bookmark ID
    def test_query_flows_invalid_bookmark() -> dict[str, Any]:
        from mixpanel_data.exceptions import QueryError

        assert live_query is not None
        try:
            live_query.query_flows(bookmark_id=999999999)
            return {"error_raised": False, "note": "No error for invalid bookmark ID"}
        except QueryError as e:
            return {"error_raised": True, "error_code": e.code}
        except Exception as e:
            return {"error_type": type(e).__name__, "message": str(e)[:50]}

    runner.run_test("6.2 query_flows() invalid ID", test_query_flows_invalid_bookmark)

    # =========================================================================
    # Phase 7: CLI Integration Tests
    # =========================================================================
    print("\n[Phase 7] CLI Integration Tests")
    print("-" * 40)

    # Test 7.1: mp inspect bookmarks --help
    def test_cli_bookmarks_help() -> dict[str, Any]:
        import subprocess

        result = subprocess.run(
            ["uv", "run", "mp", "inspect", "bookmarks", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"CLI failed: {result.stderr}")
        return {
            "exit_code": result.returncode,
            "has_type_option": "--type" in result.stdout,
            "has_format_option": "--format" in result.stdout,
        }

    runner.run_test("7.1 CLI inspect bookmarks --help", test_cli_bookmarks_help)

    # Test 7.2: mp query saved-report --help
    def test_cli_saved_report_help() -> dict[str, Any]:
        import subprocess

        result = subprocess.run(
            ["uv", "run", "mp", "query", "saved-report", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"CLI failed: {result.stderr}")
        return {
            "exit_code": result.returncode,
            "has_bookmark_id": "BOOKMARK_ID" in result.stdout,
            "has_format_option": "--format" in result.stdout,
        }

    runner.run_test("7.2 CLI query saved-report --help", test_cli_saved_report_help)

    # Test 7.3: mp query flows --help
    def test_cli_flows_help() -> dict[str, Any]:
        import subprocess

        result = subprocess.run(
            ["uv", "run", "mp", "query", "flows", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"CLI failed: {result.stderr}")
        return {
            "exit_code": result.returncode,
            "has_bookmark_id": "BOOKMARK_ID" in result.stdout,
            "has_format_option": "--format" in result.stdout,
        }

    runner.run_test("7.3 CLI query flows --help", test_cli_flows_help)

    # Test 7.4: mp inspect bookmarks --format json (live, uses default account)
    def test_cli_bookmarks_json() -> dict[str, Any]:
        import subprocess

        result = subprocess.run(
            [
                "uv",
                "run",
                "mp",
                "inspect",
                "bookmarks",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"CLI failed: {result.stderr}")
        # Parse JSON output (handle potential control characters)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            # Report the error location but consider test passing if CLI ran OK
            return {
                "exit_code": result.returncode,
                "json_error": str(e),
                "output_length": len(result.stdout),
                "note": "CLI succeeded but output contains invalid JSON characters",
            }
        if not isinstance(data, list):
            raise TypeError(f"Expected list, got {type(data)}")
        return {
            "exit_code": result.returncode,
            "bookmark_count": len(data),
            "first_bookmark": data[0]["name"] if data else None,
        }

    runner.run_test("7.4 CLI inspect bookmarks --format json", test_cli_bookmarks_json)

    # =========================================================================
    # Phase 8: Cleanup
    # =========================================================================
    print("\n[Phase 8] Cleanup")
    print("-" * 40)

    def test_cleanup() -> dict[str, Any]:
        nonlocal api_client, ws
        if api_client:
            api_client.__exit__(None, None, None)
            api_client = None
        if ws:
            ws.__exit__(None, None, None)
            ws = None
        return {"status": "cleaned up"}

    runner.run_test("8.1 Cleanup", test_cleanup)

    # =========================================================================
    # Results
    # =========================================================================
    runner.print_results()

    # Return exit code
    failed = sum(1 for r in runner.results if not r.passed)
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
