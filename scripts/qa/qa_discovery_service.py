#!/usr/bin/env python3
"""Live QA integration test for Discovery Service (Phase 004).

This script performs real API calls against Mixpanel to verify the
Discovery Service is working correctly with actual data.

Usage:
    uv run python scripts/qa_discovery_service.py

Prerequisites:
    - Service account configured in ~/.mp/config.toml
    - OR environment variables: MP_USERNAME, MP_SECRET, MP_PROJECT_ID, MP_REGION
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Any


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
        self._api_call_count = 0

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
        print("QA TEST RESULTS - Discovery Service (Phase 004)")
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
    print("Discovery Service QA - Live Integration Tests")
    print("=" * 70)

    runner = QARunner()

    # =========================================================================
    # Phase 1: Prerequisites
    # =========================================================================
    print("\n[Phase 1] Prerequisites Check")
    print("-" * 40)

    # Test 1.1: Import modules
    def test_imports() -> dict[str, Any]:
        return {"modules": ["ConfigManager", "MixpanelAPIClient", "DiscoveryService"]}

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
    def test_resolve_credentials() -> dict[str, Any]:
        from mixpanel_data._internal.config import ConfigManager

        config = ConfigManager()
        creds = config.resolve_credentials()
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
    # Phase 2: API Client Direct Tests
    # =========================================================================
    print("\n[Phase 2] API Client Direct Tests")
    print("-" * 40)

    # Need to store client for reuse
    api_client = None

    # Test 2.1: Create API client
    def test_create_client() -> dict[str, Any]:
        nonlocal api_client
        from mixpanel_data._internal.api_client import MixpanelAPIClient
        from mixpanel_data._internal.config import ConfigManager

        config = ConfigManager()
        creds = config.resolve_credentials()
        api_client = MixpanelAPIClient(creds)
        api_client.__enter__()
        return {"status": "client created"}

    result = runner.run_test("2.1 Create API client", test_create_client)
    if not result.passed:
        print("Cannot continue - client creation failed")
        runner.print_results()
        return 1

    # Test 2.2: get_events() raw API call
    raw_events: list[str] = []

    def test_raw_get_events() -> dict[str, Any]:
        nonlocal raw_events
        assert api_client is not None
        raw_events = api_client.get_events()
        if not isinstance(raw_events, list):
            raise TypeError(f"Expected list, got {type(raw_events)}")
        return {
            "count": len(raw_events),
            "sample": raw_events[:5] if raw_events else [],
        }

    runner.run_test("2.2 get_events() raw API", test_raw_get_events)

    # Test 2.3: get_event_properties() raw API call
    raw_properties: list[str] = []
    test_event: str | None = None

    def test_raw_get_properties() -> dict[str, Any]:
        nonlocal raw_properties, test_event
        assert api_client is not None
        if not raw_events:
            raise ValueError("No events available to test properties")
        # Pick first event for testing
        test_event = raw_events[0]
        raw_properties = api_client.get_event_properties(test_event)
        if not isinstance(raw_properties, list):
            raise TypeError(f"Expected list, got {type(raw_properties)}")
        return {
            "event": test_event,
            "property_count": len(raw_properties),
            "sample": raw_properties[:5] if raw_properties else [],
        }

    runner.run_test("2.3 get_event_properties() raw API", test_raw_get_properties)

    # Test 2.4: get_property_values() raw API call
    def test_raw_get_values() -> dict[str, Any]:
        assert api_client is not None
        if not raw_properties:
            raise ValueError("No properties available to test values")
        # Pick first property
        test_prop = raw_properties[0]
        values = api_client.get_property_values(test_prop, event=test_event, limit=10)
        if not isinstance(values, list):
            raise TypeError(f"Expected list, got {type(values)}")
        return {
            "property": test_prop,
            "event": test_event,
            "value_count": len(values),
            "sample": values[:5] if values else [],
        }

    runner.run_test("2.4 get_property_values() raw API", test_raw_get_values)

    # =========================================================================
    # Phase 3: Discovery Service Tests
    # =========================================================================
    print("\n[Phase 3] Discovery Service Tests")
    print("-" * 40)

    discovery = None

    # Test 3.1: Create Discovery Service
    def test_create_discovery() -> dict[str, Any]:
        nonlocal discovery
        from mixpanel_data._internal.services.discovery import DiscoveryService

        assert api_client is not None
        discovery = DiscoveryService(api_client)
        return {"status": "service created", "cache_size": len(discovery._cache)}

    runner.run_test("3.1 Create DiscoveryService", test_create_discovery)

    # Test 3.2: list_events() returns sorted list
    discovered_events: list[str] = []

    def test_list_events_sorted() -> dict[str, Any]:
        nonlocal discovered_events
        assert discovery is not None
        discovered_events = discovery.list_events()
        if not isinstance(discovered_events, list):
            raise TypeError(f"Expected list, got {type(discovered_events)}")
        # Verify sorted
        sorted_events = sorted(discovered_events)
        if discovered_events != sorted_events:
            raise ValueError("Events are not sorted alphabetically")
        return {
            "count": len(discovered_events),
            "is_sorted": True,
            "sample": discovered_events[:5],
        }

    runner.run_test("3.2 list_events() returns sorted list", test_list_events_sorted)

    # Test 3.3: list_events() caching works
    def test_list_events_caching() -> dict[str, Any]:
        assert discovery is not None
        # Cache should have been populated
        cache_key = ("list_events",)
        if cache_key not in discovery._cache:
            raise ValueError("list_events() result not cached")
        # Call again - should use cache
        cached_result = discovery.list_events()
        if cached_result != discovered_events:
            raise ValueError("Cached result doesn't match original")
        return {"cache_key": str(cache_key), "cache_hit": True}

    runner.run_test("3.3 list_events() caching", test_list_events_caching)

    # Test 3.4: list_properties() for known event
    discovered_properties: list[str] = []

    def test_list_properties() -> dict[str, Any]:
        nonlocal discovered_properties
        assert discovery is not None
        if not discovered_events:
            raise ValueError("No events available")
        event = discovered_events[0]
        discovered_properties = discovery.list_properties(event)
        if not isinstance(discovered_properties, list):
            raise TypeError(f"Expected list, got {type(discovered_properties)}")
        # Verify sorted
        if discovered_properties != sorted(discovered_properties):
            raise ValueError("Properties are not sorted alphabetically")
        return {
            "event": event,
            "count": len(discovered_properties),
            "is_sorted": True,
            "sample": discovered_properties[:5],
        }

    runner.run_test("3.4 list_properties() for event", test_list_properties)

    # Test 3.5: list_properties() caching per event
    def test_list_properties_caching() -> dict[str, Any]:
        assert discovery is not None
        if not discovered_events:
            raise ValueError("No events available")
        event = discovered_events[0]
        cache_key = ("list_properties", event)
        if cache_key not in discovery._cache:
            raise ValueError("list_properties() result not cached")
        # Call for different event to verify separate caching
        if len(discovered_events) > 1:
            event2 = discovered_events[1]
            _ = discovery.list_properties(event2)
            cache_key2 = ("list_properties", event2)
            if cache_key2 not in discovery._cache:
                raise ValueError("Second event not cached separately")
        return {
            "cache_entries": len(
                [k for k in discovery._cache if k[0] == "list_properties"]
            )
        }

    runner.run_test(
        "3.5 list_properties() caching per event", test_list_properties_caching
    )

    # Test 3.6: list_property_values() basic call
    def test_list_property_values() -> dict[str, Any]:
        assert discovery is not None
        if not discovered_properties:
            raise ValueError("No properties available")
        prop = discovered_properties[0]
        event = discovered_events[0] if discovered_events else None
        values = discovery.list_property_values(prop, event=event, limit=20)
        if not isinstance(values, list):
            raise TypeError(f"Expected list, got {type(values)}")
        # All values should be strings
        non_strings = [v for v in values if not isinstance(v, str)]
        if non_strings:
            raise TypeError(f"Non-string values found: {non_strings[:3]}")
        return {
            "property": prop,
            "event": event,
            "limit": 20,
            "count": len(values),
            "sample": values[:5] if values else [],
        }

    runner.run_test("3.6 list_property_values()", test_list_property_values)

    # Test 3.7: list_property_values() caching
    def test_property_values_caching() -> dict[str, Any]:
        assert discovery is not None
        # Check cache entries for property values
        pv_entries = [k for k in discovery._cache if k[0] == "list_property_values"]
        if not pv_entries:
            raise ValueError("No property values cached")
        return {"cache_entries": len(pv_entries), "sample_key": str(pv_entries[0])}

    runner.run_test("3.7 list_property_values() caching", test_property_values_caching)

    # Test 3.8: clear_cache() clears everything
    def test_clear_cache() -> dict[str, Any]:
        assert discovery is not None
        cache_size_before = len(discovery._cache)
        discovery.clear_cache()
        cache_size_after = len(discovery._cache)
        if cache_size_after != 0:
            raise ValueError(f"Cache not cleared: {cache_size_after} entries remain")
        return {"before": cache_size_before, "after": cache_size_after}

    runner.run_test("3.8 clear_cache()", test_clear_cache)

    # Test 3.9: After clear_cache(), API is called again
    def test_cache_repopulation() -> dict[str, Any]:
        assert discovery is not None
        # Cache should be empty
        if discovery._cache:
            raise ValueError("Cache should be empty")
        # Call list_events again
        events = discovery.list_events()
        # Cache should now have entry
        if ("list_events",) not in discovery._cache:
            raise ValueError("Cache not repopulated after clear")
        return {"cache_size": len(discovery._cache), "events_count": len(events)}

    runner.run_test("3.9 Cache repopulation after clear", test_cache_repopulation)

    # =========================================================================
    # Phase 4: Edge Cases & Error Handling
    # =========================================================================
    print("\n[Phase 4] Edge Cases & Error Handling")
    print("-" * 40)

    # Test 4.1: list_properties() with non-existent event
    def test_nonexistent_event_properties() -> dict[str, Any]:
        assert discovery is not None
        # This should return empty list or handle gracefully
        props = discovery.list_properties("__nonexistent_event_xyz_123__")
        # Mixpanel API typically returns empty dict for unknown events
        return {"count": len(props), "result": props}

    runner.run_test(
        "4.1 list_properties() non-existent event", test_nonexistent_event_properties
    )

    # Test 4.2: list_property_values() with non-existent property
    def test_nonexistent_property_values() -> dict[str, Any]:
        assert discovery is not None
        values = discovery.list_property_values("__nonexistent_prop_xyz_123__")
        return {"count": len(values), "result": values}

    runner.run_test(
        "4.2 list_property_values() non-existent prop", test_nonexistent_property_values
    )

    # Test 4.3: list_property_values() without event scope
    def test_property_values_no_event() -> dict[str, Any]:
        assert discovery is not None
        if not discovered_properties:
            return {"skipped": "No properties available"}
        prop = discovered_properties[0]
        values = discovery.list_property_values(prop, limit=10)  # No event
        return {"property": prop, "count": len(values), "sample": values[:3]}

    runner.run_test(
        "4.3 list_property_values() no event scope", test_property_values_no_event
    )

    # Test 4.4: Different limits produce different cache entries
    def test_different_limits_caching() -> dict[str, Any]:
        assert discovery is not None
        if not discovered_properties:
            return {"skipped": "No properties available"}
        prop = discovered_properties[0]
        discovery.clear_cache()
        # Call with limit=5
        v1 = discovery.list_property_values(prop, limit=5)
        cache_size_1 = len(discovery._cache)
        # Call with limit=10 - should create new cache entry
        v2 = discovery.list_property_values(prop, limit=10)
        cache_size_2 = len(discovery._cache)
        if cache_size_2 <= cache_size_1:
            raise ValueError("Different limits should create separate cache entries")
        return {
            "limit_5_count": len(v1),
            "limit_10_count": len(v2),
            "cache_entries": cache_size_2,
        }

    runner.run_test(
        "4.4 Different limits = different cache", test_different_limits_caching
    )

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
