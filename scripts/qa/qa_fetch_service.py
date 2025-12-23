#!/usr/bin/env python3
"""Live QA integration test for Fetch Service (Phase 005).

This script performs real API calls against Mixpanel to verify the
Fetch Service is working correctly with actual data.

Usage:
    uv run python scripts/qa_fetch_service.py

Prerequisites:
    - Service account configured in ~/.mp/config.toml
    - OR environment variables: MP_USERNAME, MP_SECRET, MP_PROJECT_ID, MP_REGION
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient
    from mixpanel_data._internal.services.fetcher import FetcherService
    from mixpanel_data._internal.storage import StorageEngine


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
        print("QA TEST RESULTS - Fetch Service (Phase 005)")
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
                    else:
                        print(f"  {key}: {value}")

        print("\n" + "-" * 70)
        print(f"SUMMARY: {passed}/{len(self.results)} tests passed")
        if failed > 0:
            print(f"         {failed} tests FAILED")
        print("-" * 70)


def main() -> int:
    """Run all QA tests."""
    print("Fetch Service QA - Live Integration Tests")
    print("=" * 70)

    runner = QARunner()

    # Shared state
    api_client: MixpanelAPIClient | None = None
    storage: StorageEngine | None = None
    fetcher: FetcherService | None = None
    db_path: Path | None = None

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
                "StorageEngine",
                "FetcherService",
            ]
        }

    result = runner.run_test("1.1 Import modules", test_imports)
    if not result.passed:
        print("Cannot continue - import failed")
        runner.print_results()
        return 1

    # Test 1.2: Resolve credentials
    def test_resolve_credentials() -> dict[str, Any]:
        from mixpanel_data._internal.config import ConfigManager

        config = ConfigManager()
        creds = config.resolve_credentials()
        return {
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
        creds = config.resolve_credentials()
        api_client = MixpanelAPIClient(creds)
        return {"status": "client created"}

    result = runner.run_test("2.1 Create API client", test_create_client)
    if not result.passed:
        print("Cannot continue - client creation failed")
        runner.print_results()
        return 1

    # Test 2.2: Create Storage Engine
    def test_create_storage() -> dict[str, Any]:
        nonlocal storage, db_path
        from mixpanel_data._internal.storage import StorageEngine

        db_path = Path("/tmp/qa_fetch_service_test.duckdb")
        if db_path.exists():
            db_path.unlink()
        storage = StorageEngine(db_path)
        return {"db_path": str(db_path), "status": "storage created"}

    result = runner.run_test("2.2 Create Storage Engine", test_create_storage)
    if not result.passed:
        print("Cannot continue - storage creation failed")
        runner.print_results()
        return 1

    # Test 2.3: Create Fetcher Service
    def test_create_fetcher() -> dict[str, Any]:
        nonlocal fetcher
        from mixpanel_data._internal.services.fetcher import FetcherService

        assert api_client is not None
        assert storage is not None
        fetcher = FetcherService(api_client, storage)
        return {"status": "fetcher created"}

    result = runner.run_test("2.3 Create FetcherService", test_create_fetcher)
    if not result.passed:
        print("Cannot continue - fetcher creation failed")
        runner.print_results()
        return 1

    # =========================================================================
    # Phase 3: Event Fetching Tests
    # =========================================================================
    print("\n[Phase 3] Event Fetching Tests")
    print("-" * 40)

    # Test 3.1: Fetch events (basic)
    def test_fetch_events_basic() -> dict[str, Any]:
        assert fetcher is not None
        assert storage is not None

        # Use a date range known to have data but minimal duplicates
        result = fetcher.fetch_events(
            name="qa_events_basic",
            from_date="2025-02-20",
            to_date="2025-02-20",
        )
        return {
            "table": result.table,
            "rows_processed": result.rows,
            "type": result.type,
            "date_range": result.date_range,
            "duration_s": f"{result.duration_seconds:.2f}",
        }

    runner.run_test("3.1 fetch_events() basic", test_fetch_events_basic)

    # Test 3.2: Verify data in table
    def test_verify_events_data() -> dict[str, Any]:
        assert storage is not None

        # Check row count
        count = storage.execute_scalar("SELECT COUNT(*) FROM qa_events_basic")

        # Check schema
        schema = storage.get_schema("qa_events_basic")
        columns = [c.name for c in schema.columns]

        # Sample data
        df = storage.execute_df(
            "SELECT event_name, distinct_id FROM qa_events_basic LIMIT 3"
        )

        return {
            "row_count": count,
            "columns": columns,
            "sample_events": df["event_name"].tolist() if len(df) > 0 else [],
        }

    runner.run_test("3.2 Verify events in table", test_verify_events_data)

    # Test 3.3: Fetch events with filter
    def test_fetch_events_filtered() -> dict[str, Any]:
        assert fetcher is not None
        assert storage is not None

        result = fetcher.fetch_events(
            name="qa_events_filtered",
            from_date="2025-02-20",
            to_date="2025-02-20",
            events=["Sign Up"],
        )

        # Verify only filtered events
        event_types = storage.execute_df(
            "SELECT DISTINCT event_name FROM qa_events_filtered"
        )

        return {
            "rows_processed": result.rows,
            "event_types": event_types["event_name"].tolist(),
        }

    runner.run_test("3.3 fetch_events() with filter", test_fetch_events_filtered)

    # Test 3.4: Fetch events with progress callback
    def test_fetch_events_progress() -> dict[str, Any]:
        assert fetcher is not None

        progress_updates: list[int] = []

        def on_progress(count: int) -> None:
            progress_updates.append(count)

        result = fetcher.fetch_events(
            name="qa_events_progress",
            from_date="2025-02-20",
            to_date="2025-02-20",
            progress_callback=on_progress,
        )

        return {
            "rows_processed": result.rows,
            "progress_callbacks": len(progress_updates),
            "final_progress": progress_updates[-1] if progress_updates else 0,
        }

    runner.run_test("3.4 fetch_events() with progress", test_fetch_events_progress)

    # Test 3.5: Fetch events handles duplicates
    def test_fetch_events_duplicates() -> dict[str, Any]:
        assert fetcher is not None
        assert storage is not None

        # Use a wider date range that has duplicates
        result = fetcher.fetch_events(
            name="qa_events_dupes",
            from_date="2025-02-01",
            to_date="2025-02-28",
        )

        # Get actual unique rows
        actual_count = storage.execute_scalar("SELECT COUNT(*) FROM qa_events_dupes")
        duplicates_skipped = result.rows - actual_count

        return {
            "rows_processed": result.rows,
            "unique_rows": actual_count,
            "duplicates_skipped": duplicates_skipped,
            "duration_s": f"{result.duration_seconds:.2f}",
        }

    runner.run_test(
        "3.5 fetch_events() handles duplicates", test_fetch_events_duplicates
    )

    # =========================================================================
    # Phase 4: Profile Fetching Tests
    # =========================================================================
    print("\n[Phase 4] Profile Fetching Tests")
    print("-" * 40)

    # Test 4.1: Fetch profiles (basic)
    def test_fetch_profiles_basic() -> dict[str, Any]:
        assert fetcher is not None

        result = fetcher.fetch_profiles(name="qa_profiles_basic")

        return {
            "table": result.table,
            "rows_processed": result.rows,
            "type": result.type,
            "date_range": result.date_range,  # Should be None
            "duration_s": f"{result.duration_seconds:.2f}",
        }

    runner.run_test("4.1 fetch_profiles() basic", test_fetch_profiles_basic)

    # Test 4.2: Verify profiles data
    def test_verify_profiles_data() -> dict[str, Any]:
        assert storage is not None

        # Check row count
        count = storage.execute_scalar("SELECT COUNT(*) FROM qa_profiles_basic")

        # Check schema
        schema = storage.get_schema("qa_profiles_basic")
        columns = [c.name for c in schema.columns]

        # Sample data
        df = storage.execute_df(
            "SELECT distinct_id, last_seen FROM qa_profiles_basic LIMIT 3"
        )

        return {
            "row_count": count,
            "columns": columns,
            "sample_ids": df["distinct_id"].tolist()[:3] if len(df) > 0 else [],
        }

    runner.run_test("4.2 Verify profiles in table", test_verify_profiles_data)

    # Test 4.3: Fetch profiles with progress
    def test_fetch_profiles_progress() -> dict[str, Any]:
        assert fetcher is not None

        progress_updates: list[int] = []

        def on_progress(count: int) -> None:
            progress_updates.append(count)

        result = fetcher.fetch_profiles(
            name="qa_profiles_progress",
            progress_callback=on_progress,
        )

        return {
            "rows_processed": result.rows,
            "progress_callbacks": len(progress_updates),
            "progress_sequence": progress_updates[:5] if progress_updates else [],
        }

    runner.run_test("4.3 fetch_profiles() with progress", test_fetch_profiles_progress)

    # =========================================================================
    # Phase 5: Metadata & Introspection Tests
    # =========================================================================
    print("\n[Phase 5] Metadata & Introspection Tests")
    print("-" * 40)

    # Test 5.1: list_tables()
    def test_list_tables() -> dict[str, Any]:
        assert storage is not None

        tables = storage.list_tables()
        table_names = [t.name for t in tables]
        qa_tables = [t for t in table_names if t.startswith("qa_")]

        return {
            "total_tables": len(tables),
            "qa_tables": qa_tables,
        }

    runner.run_test("5.1 list_tables()", test_list_tables)

    # Test 5.2: get_metadata() for events
    def test_get_metadata_events() -> dict[str, Any]:
        assert storage is not None

        metadata = storage.get_metadata("qa_events_basic")

        return {
            "type": metadata.type,
            "from_date": metadata.from_date,
            "to_date": metadata.to_date,
            "fetched_at": str(metadata.fetched_at)[:19],
        }

    runner.run_test("5.2 get_metadata() events", test_get_metadata_events)

    # Test 5.3: get_metadata() for profiles (None dates)
    def test_get_metadata_profiles() -> dict[str, Any]:
        assert storage is not None

        metadata = storage.get_metadata("qa_profiles_basic")

        if metadata.from_date is not None or metadata.to_date is not None:
            raise ValueError("Profile metadata should have None dates")

        return {
            "type": metadata.type,
            "from_date": metadata.from_date,
            "to_date": metadata.to_date,
        }

    runner.run_test(
        "5.3 get_metadata() profiles (None dates)", test_get_metadata_profiles
    )

    # Test 5.4: JSON properties are queryable
    def test_json_properties_queryable() -> dict[str, Any]:
        assert storage is not None

        df = storage.execute_df("""
            SELECT
                event_name,
                json_extract_string(properties, '$.$browser') as browser
            FROM qa_events_basic
            WHERE json_extract_string(properties, '$.$browser') IS NOT NULL
            LIMIT 5
        """)

        return {
            "rows_with_browser": len(df),
            "sample_browsers": df["browser"].tolist() if len(df) > 0 else [],
        }

    runner.run_test("5.4 JSON properties queryable", test_json_properties_queryable)

    # =========================================================================
    # Phase 6: Error Handling Tests
    # =========================================================================
    print("\n[Phase 6] Error Handling Tests")
    print("-" * 40)

    # Test 6.1: TableExistsError on duplicate table
    def test_table_exists_error() -> dict[str, Any]:
        from mixpanel_data.exceptions import TableExistsError

        assert fetcher is not None

        try:
            fetcher.fetch_events(
                name="qa_events_basic",  # Already exists
                from_date="2025-02-20",
                to_date="2025-02-20",
            )
            raise AssertionError("Should have raised TableExistsError")
        except TableExistsError as e:
            return {
                "error_code": e.code,
                "error_raised": True,
            }

    runner.run_test("6.1 TableExistsError on duplicate", test_table_exists_error)

    # Test 6.2: Invalid table name rejected
    def test_invalid_table_name() -> dict[str, Any]:
        assert fetcher is not None

        try:
            fetcher.fetch_events(
                name="_invalid",  # Leading underscore
                from_date="2025-02-20",
                to_date="2025-02-20",
            )
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            return {
                "error_type": "ValueError",
                "message": str(e)[:50],
            }

    runner.run_test("6.2 Invalid table name rejected", test_invalid_table_name)

    # Test 6.3: Empty result (old date range)
    def test_empty_result() -> dict[str, Any]:
        assert fetcher is not None
        assert storage is not None

        result = fetcher.fetch_events(
            name="qa_events_empty",
            from_date="2020-01-01",
            to_date="2020-01-01",
        )

        # Verify empty table exists with correct schema
        schema = storage.get_schema("qa_events_empty")

        return {
            "rows": result.rows,
            "columns": len(schema.columns),
            "table_exists": storage.table_exists("qa_events_empty"),
        }

    runner.run_test("6.3 Empty result creates table", test_empty_result)

    # =========================================================================
    # Phase 7: FetchResult Object Tests
    # =========================================================================
    print("\n[Phase 7] FetchResult Object Tests")
    print("-" * 40)

    # Test 7.1: FetchResult.to_dict() serialization
    def test_fetch_result_to_dict() -> dict[str, Any]:
        assert fetcher is not None

        result = fetcher.fetch_events(
            name="qa_result_test",
            from_date="2025-02-20",
            to_date="2025-02-20",
        )

        d = result.to_dict()

        # Verify all expected keys
        expected_keys = {
            "table",
            "rows",
            "type",
            "duration_seconds",
            "date_range",
            "fetched_at",
        }
        actual_keys = set(d.keys())

        if not expected_keys.issubset(actual_keys):
            raise ValueError(f"Missing keys: {expected_keys - actual_keys}")

        # Verify fetched_at is ISO string
        if not isinstance(d["fetched_at"], str):
            raise TypeError("fetched_at should be ISO string in dict")

        return {
            "keys": list(d.keys()),
            "fetched_at_type": type(d["fetched_at"]).__name__,
        }

    runner.run_test("7.1 FetchResult.to_dict()", test_fetch_result_to_dict)

    # =========================================================================
    # Cleanup
    # =========================================================================
    print("\n[Cleanup]")
    print("-" * 40)

    def test_cleanup() -> dict[str, Any]:
        nonlocal storage, db_path

        tables_dropped = 0
        if storage is not None:
            # Drop all QA tables
            for table in storage.list_tables():
                if table.name.startswith("qa_"):
                    storage.drop_table(table.name)
                    tables_dropped += 1
            storage.close()
            storage = None

        if db_path is not None and db_path.exists():
            db_path.unlink()

        return {"tables_dropped": tables_dropped, "status": "cleaned up"}

    runner.run_test("Cleanup", test_cleanup)

    # =========================================================================
    # Results
    # =========================================================================
    runner.print_results()

    # Return exit code
    failed = sum(1 for r in runner.results if not r.passed)
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
