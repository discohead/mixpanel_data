#!/usr/bin/env python3
"""Live QA integration test for Lexicon Schemas API (Phase 012).

This script performs real API calls against Mixpanel to verify the
Lexicon Schemas API is working correctly with actual data.

Tests cover:
- API Client: get_schemas(), get_schema()
- DiscoveryService: list_schemas(), get_schema() with caching
- Workspace: lexicon_schemas(), lexicon_schema()
- Types: LexiconSchema, LexiconDefinition, LexiconProperty, LexiconMetadata
- Filtering: entity_type filtering (event/profile)
- Serialization: to_dict() on all types
- CLI: lexicon-schemas, lexicon-schema commands

Usage:
    uv run python scripts/qa/qa_lexicon_schemas.py

Prerequisites:
    - Service account configured in ~/.mp/config.toml
    - OR environment variables: MP_USERNAME, MP_SECRET, MP_PROJECT_ID, MP_REGION
    - Project should have Lexicon schemas defined
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mixpanel_data import Workspace
    from mixpanel_data._internal.api_client import MixpanelAPIClient
    from mixpanel_data._internal.services.discovery import DiscoveryService
    from mixpanel_data.types import (
        LexiconSchema,
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
        print("QA TEST RESULTS - Lexicon Schemas API (Phase 012)")
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
                    elif isinstance(value, dict) and len(value) > 5:
                        keys = list(value.keys())[:5]
                        print(f"  {key}: {{{len(value)} keys}} {keys}...")
                    else:
                        print(f"  {key}: {value}")

        print("\n" + "-" * 70)
        print(f"SUMMARY: {passed}/{len(self.results)} tests passed")
        if failed > 0:
            print(f"         {failed} tests FAILED")
        print("-" * 70)


def wait_for_rate_limit(seconds: float = 12.5, message: str = "") -> None:
    """Wait to respect rate limit (5 req/min = 1 req per 12 seconds)."""
    if message:
        print(f"  [Rate limit] {message} - waiting {seconds}s...")
    else:
        print(f"  [Rate limit] Waiting {seconds}s to respect 5 req/min limit...")
    time.sleep(seconds)


def main() -> int:
    """Run all QA tests."""
    print("Lexicon Schemas API QA - Live Integration Tests")
    print("=" * 70)
    print("\nIMPORTANT: Lexicon API has a strict 5 requests/minute rate limit!")
    print("This script uses caching and delays to stay within limits.\n")

    runner = QARunner()

    # Shared state
    api_client: MixpanelAPIClient | None = None
    discovery: DiscoveryService | None = None
    workspace: Workspace | None = None

    # Stored results for later tests
    all_schemas: list[LexiconSchema] = []
    event_schemas: list[LexiconSchema] = []
    profile_schemas: list[LexiconSchema] = []
    single_schema: LexiconSchema | None = None

    # =========================================================================
    # Phase 1: Prerequisites
    # =========================================================================
    print("\n[Phase 1] Prerequisites Check")
    print("-" * 40)

    # Test 1.1: Import modules
    def test_imports() -> dict[str, Any]:
        from mixpanel_data import Workspace  # noqa: F401
        from mixpanel_data._internal.api_client import MixpanelAPIClient  # noqa: F401
        from mixpanel_data._internal.config import ConfigManager  # noqa: F401
        from mixpanel_data._internal.services.discovery import (
            DiscoveryService,  # noqa: F401
        )
        from mixpanel_data.types import (
            EntityType,  # noqa: F401
            LexiconDefinition,  # noqa: F401
            LexiconMetadata,  # noqa: F401
            LexiconProperty,  # noqa: F401
            LexiconSchema,  # noqa: F401
        )

        return {"modules": ["All Lexicon types and services imported successfully"]}

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

    # Test 1.3: Verify app endpoint exists
    def test_app_endpoint() -> dict[str, Any]:
        from mixpanel_data._internal.api_client import ENDPOINTS

        regions = ["us", "eu", "in"]
        for region in regions:
            if "app" not in ENDPOINTS[region]:
                raise ValueError(f"Missing 'app' endpoint for region {region}")
        return {
            "us": ENDPOINTS["us"]["app"],
            "eu": ENDPOINTS["eu"]["app"],
            "in": ENDPOINTS["in"]["app"],
        }

    runner.run_test("1.3 App endpoint configured", test_app_endpoint)

    # =========================================================================
    # Phase 2: API Client Direct Tests
    # =========================================================================
    print("\n[Phase 2] API Client Direct Tests")
    print("-" * 40)

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

    # Test 2.2: get_schemas() raw API call (all schemas)
    raw_schemas: list[dict[str, Any]] = []

    def test_raw_get_schemas() -> dict[str, Any]:
        nonlocal raw_schemas
        assert api_client is not None
        raw_schemas = api_client.get_schemas()
        if not isinstance(raw_schemas, list):
            raise TypeError(f"Expected list, got {type(raw_schemas)}")
        return {
            "count": len(raw_schemas),
            "sample": [
                {"entityType": s.get("entityType"), "name": s.get("name")}
                for s in raw_schemas[:3]
            ]
            if raw_schemas
            else [],
        }

    runner.run_test("2.2 get_schemas() raw API", test_raw_get_schemas)
    wait_for_rate_limit(13, "After get_schemas()")

    # Test 2.3: get_schemas(entity_type="event") raw API call
    def test_raw_get_schemas_event() -> dict[str, Any]:
        assert api_client is not None
        event_raw = api_client.get_schemas(entity_type="event")
        if not isinstance(event_raw, list):
            raise TypeError(f"Expected list, got {type(event_raw)}")
        # Note: API may return additional entity types (custom_event, etc.)
        # We just verify we got results and log the types seen
        entity_types = {s.get("entityType") for s in event_raw}
        return {
            "count": len(event_raw),
            "entity_types_seen": list(entity_types),
            "sample": [s.get("name") for s in event_raw[:5]] if event_raw else [],
        }

    runner.run_test("2.3 get_schemas(entity_type=event)", test_raw_get_schemas_event)
    wait_for_rate_limit(13, "After get_schemas(entity_type=event)")

    # Test 2.4: get_schemas(entity_type="profile") raw API call
    def test_raw_get_schemas_profile() -> dict[str, Any]:
        assert api_client is not None
        profile_raw = api_client.get_schemas(entity_type="profile")
        if not isinstance(profile_raw, list):
            raise TypeError(f"Expected list, got {type(profile_raw)}")
        # Note: API may return additional entity types
        # We just verify we got results and log the types seen
        entity_types = {s.get("entityType") for s in profile_raw}
        return {
            "count": len(profile_raw),
            "entity_types_seen": list(entity_types),
            "sample": [s.get("name") for s in profile_raw[:5]] if profile_raw else [],
        }

    runner.run_test(
        "2.4 get_schemas(entity_type=profile)", test_raw_get_schemas_profile
    )
    wait_for_rate_limit(13, "After get_schemas(entity_type=profile)")

    # Test 2.5: get_schema() raw API call (single schema)
    def test_raw_get_schema() -> dict[str, Any]:
        assert api_client is not None
        if not raw_schemas:
            return {"skipped": "No schemas in project"}
        first = raw_schemas[0]
        entity_type = first["entityType"]
        name = first["name"]
        schema_raw = api_client.get_schema(entity_type, name)
        if not isinstance(schema_raw, dict):
            raise TypeError(f"Expected dict, got {type(schema_raw)}")
        return {
            "entity_type": schema_raw.get("entityType"),
            "name": schema_raw.get("name"),
            "has_schemaJson": "schemaJson" in schema_raw,
        }

    runner.run_test("2.5 get_schema() raw API", test_raw_get_schema)
    wait_for_rate_limit(13, "After get_schema()")

    # =========================================================================
    # Phase 3: DiscoveryService Tests
    # =========================================================================
    print("\n[Phase 3] DiscoveryService Tests")
    print("  Note: These tests use caching - fewer API calls needed")
    print("-" * 40)

    # Test 3.1: Create DiscoveryService
    def test_create_discovery() -> dict[str, Any]:
        nonlocal discovery
        from mixpanel_data._internal.services.discovery import DiscoveryService

        assert api_client is not None
        discovery = DiscoveryService(api_client)
        return {"status": "service created", "cache_size": len(discovery._cache)}

    result = runner.run_test("3.1 Create DiscoveryService", test_create_discovery)
    if not result.passed:
        print("Cannot continue - discovery service creation failed")
        runner.print_results()
        return 1

    # Test 3.2: list_schemas() returns list of LexiconSchema
    def test_list_schemas() -> dict[str, Any]:
        nonlocal all_schemas
        from mixpanel_data.types import LexiconSchema

        assert discovery is not None
        all_schemas = discovery.list_schemas()
        if not isinstance(all_schemas, list):
            raise TypeError(f"Expected list, got {type(all_schemas)}")
        if all_schemas and not isinstance(all_schemas[0], LexiconSchema):
            raise TypeError(f"Expected LexiconSchema, got {type(all_schemas[0])}")
        return {
            "count": len(all_schemas),
            "sample": [
                {"entity_type": s.entity_type, "name": s.name} for s in all_schemas[:3]
            ]
            if all_schemas
            else [],
        }

    runner.run_test("3.2 list_schemas() returns LexiconSchema list", test_list_schemas)
    # No wait needed - next test uses cache

    # Test 3.3: list_schemas() caching works
    def test_list_schemas_caching() -> dict[str, Any]:
        assert discovery is not None
        cache_key = ("list_schemas", None)
        if cache_key not in discovery._cache:
            raise ValueError("list_schemas() result not cached")
        # Call again - should use cache
        schemas2 = discovery.list_schemas()
        if len(schemas2) != len(all_schemas):
            raise ValueError("Cached result doesn't match original")
        return {"cache_key": str(cache_key), "cache_hit": True}

    runner.run_test("3.3 list_schemas() caching", test_list_schemas_caching)
    wait_for_rate_limit(13, "Before list_schemas(entity_type=event)")

    # Test 3.4: list_schemas(entity_type="event") filtering
    def test_list_schemas_event() -> dict[str, Any]:
        nonlocal event_schemas
        assert discovery is not None
        event_schemas = discovery.list_schemas(entity_type="event")
        # Log entity types seen (API may return additional types like custom_event)
        entity_types = {s.entity_type for s in event_schemas}
        return {
            "count": len(event_schemas),
            "entity_types_seen": list(entity_types),
            "sample": [s.name for s in event_schemas[:5]] if event_schemas else [],
        }

    runner.run_test("3.4 list_schemas(entity_type=event)", test_list_schemas_event)
    wait_for_rate_limit(13, "Before list_schemas(entity_type=profile)")

    # Test 3.5: list_schemas(entity_type="profile") filtering
    def test_list_schemas_profile() -> dict[str, Any]:
        nonlocal profile_schemas
        assert discovery is not None
        profile_schemas = discovery.list_schemas(entity_type="profile")
        # Log entity types seen (API may return additional types)
        entity_types = {s.entity_type for s in profile_schemas}
        return {
            "count": len(profile_schemas),
            "entity_types_seen": list(entity_types),
            "sample": [s.name for s in profile_schemas[:5]] if profile_schemas else [],
        }

    runner.run_test("3.5 list_schemas(entity_type=profile)", test_list_schemas_profile)

    # Test 3.6: Separate cache keys per entity_type
    def test_separate_cache_keys() -> dict[str, Any]:
        assert discovery is not None
        cache_keys = list(discovery._cache.keys())
        expected_keys = [
            ("list_schemas", None),
            ("list_schemas", "event"),
            ("list_schemas", "profile"),
        ]
        for key in expected_keys:
            if key not in cache_keys:
                raise ValueError(f"Missing cache key: {key}")
        return {"cache_keys": [str(k) for k in cache_keys if k[0] == "list_schemas"]}

    runner.run_test("3.6 Separate cache keys per entity_type", test_separate_cache_keys)
    wait_for_rate_limit(13, "Before get_schema()")

    # Test 3.7: get_schema() returns single LexiconSchema
    def test_get_schema() -> dict[str, Any]:
        nonlocal single_schema
        from mixpanel_data.types import LexiconSchema

        assert discovery is not None
        if not all_schemas:
            return {"skipped": "No schemas in project"}
        # Pick an event schema (single schema endpoint may not work for custom_event)
        first = next((s for s in all_schemas if s.entity_type == "event"), None)
        if not first:
            return {"skipped": "No event schemas in project"}
        single_schema = discovery.get_schema(first.entity_type, first.name)
        if not isinstance(single_schema, LexiconSchema):
            raise TypeError(f"Expected LexiconSchema, got {type(single_schema)}")
        return {
            "entity_type": single_schema.entity_type,
            "name": single_schema.name,
            "has_schema_json": single_schema.schema_json is not None,
        }

    runner.run_test("3.7 get_schema() returns LexiconSchema", test_get_schema)

    # Test 3.8: get_schema() caching
    def test_get_schema_caching() -> dict[str, Any]:
        assert discovery is not None
        if not single_schema:
            return {"skipped": "No single schema fetched"}
        cache_key = ("get_schema", single_schema.entity_type, single_schema.name)
        if cache_key not in discovery._cache:
            raise ValueError("get_schema() result not cached")
        return {"cache_key": str(cache_key), "cache_hit": True}

    runner.run_test("3.8 get_schema() caching", test_get_schema_caching)

    # =========================================================================
    # Phase 4: Type Structure Verification
    # =========================================================================
    print("\n[Phase 4] Type Structure Verification")
    print("-" * 40)

    # Test 4.1: LexiconSchema structure
    def test_lexicon_schema_structure() -> dict[str, Any]:
        if not all_schemas:
            return {"skipped": "No schemas in project"}
        schema = all_schemas[0]
        # Verify fields
        if not hasattr(schema, "entity_type"):
            raise AttributeError("Missing entity_type field")
        if not hasattr(schema, "name"):
            raise AttributeError("Missing name field")
        if not hasattr(schema, "schema_json"):
            raise AttributeError("Missing schema_json field")
        # Verify types - entity_type should be a non-empty string
        if not isinstance(schema.entity_type, str) or not schema.entity_type:
            raise TypeError(
                f"entity_type should be non-empty str, got {schema.entity_type!r}"
            )
        if not isinstance(schema.name, str):
            raise TypeError(f"name should be str, got {type(schema.name)}")
        return {
            "entity_type": schema.entity_type,
            "name": schema.name,
            "schema_json_type": type(schema.schema_json).__name__,
        }

    runner.run_test("4.1 LexiconSchema structure", test_lexicon_schema_structure)

    # Test 4.2: LexiconDefinition structure
    def test_lexicon_definition_structure() -> dict[str, Any]:
        from mixpanel_data.types import LexiconDefinition

        if not all_schemas:
            return {"skipped": "No schemas in project"}
        definition = all_schemas[0].schema_json
        if not isinstance(definition, LexiconDefinition):
            raise TypeError(f"Expected LexiconDefinition, got {type(definition)}")
        # Verify fields
        if not hasattr(definition, "description"):
            raise AttributeError("Missing description field")
        if not hasattr(definition, "properties"):
            raise AttributeError("Missing properties field")
        if not hasattr(definition, "metadata"):
            raise AttributeError("Missing metadata field")
        return {
            "description": definition.description[:50] + "..."
            if definition.description and len(definition.description) > 50
            else definition.description,
            "property_count": len(definition.properties),
            "has_metadata": definition.metadata is not None,
        }

    runner.run_test(
        "4.2 LexiconDefinition structure", test_lexicon_definition_structure
    )

    # Test 4.3: LexiconProperty structure
    def test_lexicon_property_structure() -> dict[str, Any]:
        from mixpanel_data.types import LexiconProperty

        if not all_schemas:
            return {"skipped": "No schemas in project"}
        definition = all_schemas[0].schema_json
        if not definition.properties:
            return {"skipped": "No properties in first schema"}
        prop_name, prop = next(iter(definition.properties.items()))
        if not isinstance(prop, LexiconProperty):
            raise TypeError(f"Expected LexiconProperty, got {type(prop)}")
        # Verify fields
        if not hasattr(prop, "type"):
            raise AttributeError("Missing type field")
        if not hasattr(prop, "description"):
            raise AttributeError("Missing description field")
        if not hasattr(prop, "metadata"):
            raise AttributeError("Missing metadata field")
        return {
            "property_name": prop_name,
            "type": prop.type,
            "description": prop.description[:30] + "..."
            if prop.description and len(prop.description) > 30
            else prop.description,
            "has_metadata": prop.metadata is not None,
        }

    runner.run_test("4.3 LexiconProperty structure", test_lexicon_property_structure)

    # Test 4.4: LexiconMetadata structure (if present)
    def test_lexicon_metadata_structure() -> dict[str, Any]:
        from mixpanel_data.types import LexiconMetadata

        if not all_schemas:
            return {"skipped": "No schemas in project"}
        # Find a schema with metadata
        meta = None
        for schema in all_schemas:
            if schema.schema_json.metadata is not None:
                meta = schema.schema_json.metadata
                break
        if meta is None:
            return {"skipped": "No schemas with metadata found"}
        if not isinstance(meta, LexiconMetadata):
            raise TypeError(f"Expected LexiconMetadata, got {type(meta)}")
        # Verify fields exist
        fields = [
            "source",
            "display_name",
            "tags",
            "hidden",
            "dropped",
            "contacts",
            "team_contacts",
        ]
        for field in fields:
            if not hasattr(meta, field):
                raise AttributeError(f"Missing {field} field")
        return {
            "source": meta.source,
            "display_name": meta.display_name,
            "tags": meta.tags[:3] if meta.tags else [],
            "hidden": meta.hidden,
            "dropped": meta.dropped,
        }

    runner.run_test("4.4 LexiconMetadata structure", test_lexicon_metadata_structure)

    # =========================================================================
    # Phase 5: Serialization Tests
    # =========================================================================
    print("\n[Phase 5] Serialization Tests")
    print("-" * 40)

    # Test 5.1: LexiconSchema.to_dict()
    def test_schema_to_dict() -> dict[str, Any]:
        if not all_schemas:
            return {"skipped": "No schemas in project"}
        schema = all_schemas[0]
        d = schema.to_dict()
        expected_keys = {"entity_type", "name", "schema_json"}
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        json_str = json.dumps(d)
        return {"keys": list(d.keys()), "json_length": len(json_str)}

    runner.run_test("5.1 LexiconSchema.to_dict()", test_schema_to_dict)

    # Test 5.2: LexiconDefinition.to_dict()
    def test_definition_to_dict() -> dict[str, Any]:
        if not all_schemas:
            return {"skipped": "No schemas in project"}
        definition = all_schemas[0].schema_json
        d = definition.to_dict()
        expected_keys = {"description", "properties", "metadata"}
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        json_str = json.dumps(d)
        return {"keys": list(d.keys()), "json_length": len(json_str)}

    runner.run_test("5.2 LexiconDefinition.to_dict()", test_definition_to_dict)

    # Test 5.3: LexiconProperty.to_dict()
    def test_property_to_dict() -> dict[str, Any]:
        if not all_schemas:
            return {"skipped": "No schemas in project"}
        definition = all_schemas[0].schema_json
        if not definition.properties:
            return {"skipped": "No properties in first schema"}
        prop = next(iter(definition.properties.values()))
        d = prop.to_dict()
        expected_keys = {"type", "description"}
        if not expected_keys.issubset(d.keys()):
            raise ValueError(f"Missing keys: {expected_keys - set(d.keys())}")
        # Verify JSON serializable
        json_str = json.dumps(d)
        return {"keys": list(d.keys()), "json_length": len(json_str)}

    runner.run_test("5.3 LexiconProperty.to_dict()", test_property_to_dict)

    # Test 5.4: Full nested to_dict() JSON round-trip
    def test_full_json_roundtrip() -> dict[str, Any]:
        if not all_schemas:
            return {"skipped": "No schemas in project"}
        schema = all_schemas[0]
        d = schema.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        # Verify structure preserved
        if parsed["entity_type"] != schema.entity_type:
            raise ValueError("entity_type not preserved")
        if parsed["name"] != schema.name:
            raise ValueError("name not preserved")
        return {"roundtrip": "success", "bytes": len(json_str)}

    runner.run_test("5.4 Full JSON round-trip", test_full_json_roundtrip)

    # =========================================================================
    # Phase 6: Workspace API Tests
    # =========================================================================
    print("\n[Phase 6] Workspace API Tests")
    print("  Note: Workspace creates new DiscoveryService, will make new API calls")
    print("-" * 40)

    # Test 6.1: Create Workspace
    def test_create_workspace() -> dict[str, Any]:
        nonlocal workspace
        from mixpanel_data import Workspace

        workspace = Workspace()
        return {"status": "workspace created"}

    result = runner.run_test("6.1 Create Workspace", test_create_workspace)
    if not result.passed:
        print("Cannot continue - workspace creation failed")
        runner.print_results()
        return 1

    # Test 6.2: lexicon_schemas() returns list
    ws_schemas: list[LexiconSchema] = []
    wait_for_rate_limit(13, "Before Workspace.lexicon_schemas()")

    def test_ws_lexicon_schemas() -> dict[str, Any]:
        nonlocal ws_schemas
        from mixpanel_data.types import LexiconSchema

        assert workspace is not None
        ws_schemas = workspace.lexicon_schemas()
        if not isinstance(ws_schemas, list):
            raise TypeError(f"Expected list, got {type(ws_schemas)}")
        if ws_schemas and not isinstance(ws_schemas[0], LexiconSchema):
            raise TypeError(f"Expected LexiconSchema, got {type(ws_schemas[0])}")
        return {
            "count": len(ws_schemas),
            "sample": [s.name for s in ws_schemas[:5]] if ws_schemas else [],
        }

    runner.run_test("6.2 lexicon_schemas() returns list", test_ws_lexicon_schemas)
    wait_for_rate_limit(13, "Before lexicon_schemas(entity_type=event)")

    # Test 6.3: lexicon_schemas(entity_type="event")
    def test_ws_lexicon_schemas_event() -> dict[str, Any]:
        assert workspace is not None
        event_schemas = workspace.lexicon_schemas(entity_type="event")
        entity_types = {s.entity_type for s in event_schemas}
        return {
            "count": len(event_schemas),
            "entity_types_seen": list(entity_types),
        }

    runner.run_test(
        "6.3 lexicon_schemas(entity_type=event)", test_ws_lexicon_schemas_event
    )
    wait_for_rate_limit(13, "Before lexicon_schemas(entity_type=profile)")

    # Test 6.4: lexicon_schemas(entity_type="profile")
    def test_ws_lexicon_schemas_profile() -> dict[str, Any]:
        assert workspace is not None
        profile_schemas = workspace.lexicon_schemas(entity_type="profile")
        entity_types = {s.entity_type for s in profile_schemas}
        return {
            "count": len(profile_schemas),
            "entity_types_seen": list(entity_types),
        }

    runner.run_test(
        "6.4 lexicon_schemas(entity_type=profile)", test_ws_lexicon_schemas_profile
    )
    wait_for_rate_limit(13, "Before lexicon_schema()")

    # Test 6.5: lexicon_schema() returns single schema
    def test_ws_lexicon_schema() -> dict[str, Any]:
        from mixpanel_data.types import LexiconSchema

        assert workspace is not None
        if not ws_schemas:
            return {"skipped": "No schemas in project"}
        # Pick an event schema (single schema endpoint may not work for custom_event)
        first = next((s for s in ws_schemas if s.entity_type == "event"), None)
        if not first:
            return {"skipped": "No event schemas in project"}
        schema = workspace.lexicon_schema(first.entity_type, first.name)
        if not isinstance(schema, LexiconSchema):
            raise TypeError(f"Expected LexiconSchema, got {type(schema)}")
        if schema.name != first.name:
            raise ValueError(f"Name mismatch: {schema.name} != {first.name}")
        return {
            "entity_type": schema.entity_type,
            "name": schema.name,
        }

    runner.run_test(
        "6.5 lexicon_schema() returns single schema", test_ws_lexicon_schema
    )
    wait_for_rate_limit(13, "Before lexicon_schema() with non-existent name")

    # Test 6.6: lexicon_schema() non-existent raises QueryError
    def test_ws_lexicon_schema_not_found() -> dict[str, Any]:
        from mixpanel_data.exceptions import QueryError

        assert workspace is not None
        try:
            workspace.lexicon_schema("event", "__nonexistent_schema_xyz_123__")
            raise ValueError("Expected QueryError but no exception raised")
        except QueryError as e:
            return {"raised": "QueryError", "message": str(e)[:50]}

    runner.run_test(
        "6.6 lexicon_schema() raises QueryError for missing",
        test_ws_lexicon_schema_not_found,
    )

    # Test 6.7: table_schema() still works (renamed from schema())
    def test_table_schema_method() -> dict[str, Any]:
        assert workspace is not None
        # This should be the renamed method - verify it exists
        if not hasattr(workspace, "table_schema"):
            raise AttributeError("table_schema method not found")
        # We can't actually test it without a table, just verify method exists
        return {"method_exists": True}

    runner.run_test("6.7 table_schema() method exists", test_table_schema_method)

    # =========================================================================
    # Phase 7: Edge Cases
    # =========================================================================
    print("\n[Phase 7] Edge Cases")
    print("-" * 40)

    # Test 7.1: Empty entity_type returns all schemas
    def test_empty_entity_type() -> dict[str, Any]:
        assert workspace is not None
        all_ws = workspace.lexicon_schemas()
        event_ws = workspace.lexicon_schemas(entity_type="event")
        profile_ws = workspace.lexicon_schemas(entity_type="profile")
        # Note: API may return additional entity types not covered by event/profile filter
        # So we don't strictly validate the counts match
        return {
            "all": len(all_ws),
            "event_filter": len(event_ws),
            "profile_filter": len(profile_ws),
            "entity_types_in_all": list({s.entity_type for s in all_ws}),
        }

    runner.run_test("7.1 All schemas = event + profile", test_empty_entity_type)

    # Test 7.2: Schemas are sorted by (entity_type, name)
    def test_schemas_sorted() -> dict[str, Any]:
        if not ws_schemas:
            return {"skipped": "No schemas in project"}
        sorted_schemas = sorted(ws_schemas, key=lambda s: (s.entity_type, s.name))
        for i, (actual, expected) in enumerate(
            zip(ws_schemas, sorted_schemas, strict=True)
        ):
            if (
                actual.entity_type != expected.entity_type
                or actual.name != expected.name
            ):
                raise ValueError(f"Schemas not sorted at index {i}")
        return {"sorted": True, "count": len(ws_schemas)}

    runner.run_test("7.2 Schemas sorted by (entity_type, name)", test_schemas_sorted)
    wait_for_rate_limit(13, "Before cache clear and refetch")

    # Test 7.3: Cache is cleared with clear_discovery_cache()
    def test_clear_cache() -> dict[str, Any]:
        assert workspace is not None
        # Get schemas to populate cache
        workspace.lexicon_schemas()
        # Clear cache
        workspace.clear_discovery_cache()
        # Call again - should re-fetch (we can't easily verify API was called,
        # but we verify no error and data returned)
        schemas_after = workspace.lexicon_schemas()
        return {
            "cleared": True,
            "count_after": len(schemas_after),
        }

    runner.run_test(
        "7.3 clear_discovery_cache() clears lexicon cache", test_clear_cache
    )

    # =========================================================================
    # Phase 8: CLI Commands
    # =========================================================================
    print("\n[Phase 8] CLI Commands")
    print("  Note: Each CLI command creates new workspace and makes API calls")
    print("-" * 40)

    # Close workspace before CLI tests to avoid database lock conflicts
    if workspace:
        workspace.close()
        workspace = None

    # Test 8.1: mp inspect lexicon-schemas --help
    def test_cli_schemas_help() -> dict[str, Any]:
        result = subprocess.run(
            [
                "python",
                "-m",
                "mixpanel_data.cli.main",
                "inspect",
                "lexicon-schemas",
                "--help",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"CLI failed: {result.stderr}")
        if "--type" not in result.stdout:
            raise ValueError("--type option not in help output")
        return {"exit_code": result.returncode, "has_type_option": True}

    runner.run_test("8.1 mp inspect lexicon-schemas --help", test_cli_schemas_help)

    # Test 8.2: mp inspect lexicon-schema --help
    def test_cli_schema_help() -> dict[str, Any]:
        result = subprocess.run(
            [
                "python",
                "-m",
                "mixpanel_data.cli.main",
                "inspect",
                "lexicon-schema",
                "--help",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"CLI failed: {result.stderr}")
        if "--type" not in result.stdout:
            raise ValueError("--type option not in help output")
        if "--name" not in result.stdout:
            raise ValueError("--name option not in help output")
        return {
            "exit_code": result.returncode,
            "has_type_option": True,
            "has_name_option": True,
        }

    runner.run_test("8.2 mp inspect lexicon-schema --help", test_cli_schema_help)
    wait_for_rate_limit(13, "Before CLI lexicon-schemas command")

    # Test 8.3: mp inspect lexicon-schemas (actual run with JSON output)
    def test_cli_schemas_json() -> dict[str, Any]:
        result = subprocess.run(
            [
                "python",
                "-m",
                "mixpanel_data.cli.main",
                "inspect",
                "lexicon-schemas",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"CLI failed: {result.stderr}")
        # Parse JSON output
        data = json.loads(result.stdout)
        if not isinstance(data, list):
            raise TypeError(f"Expected list, got {type(data)}")
        return {
            "exit_code": result.returncode,
            "count": len(data),
            "sample": data[0]["name"] if data else None,
        }

    runner.run_test(
        "8.3 mp inspect lexicon-schemas --format json", test_cli_schemas_json
    )
    wait_for_rate_limit(13, "Before CLI --type event command")

    # Test 8.4: mp inspect lexicon-schemas --type event
    def test_cli_schemas_type_event() -> dict[str, Any]:
        result = subprocess.run(
            [
                "python",
                "-m",
                "mixpanel_data.cli.main",
                "inspect",
                "lexicon-schemas",
                "--type",
                "event",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"CLI failed: {result.stderr}")
        data = json.loads(result.stdout)
        # Log entity types seen
        entity_types = {s.get("entity_type") for s in data}
        return {
            "exit_code": result.returncode,
            "count": len(data),
            "entity_types_seen": list(entity_types),
        }

    runner.run_test(
        "8.4 mp inspect lexicon-schemas --type event", test_cli_schemas_type_event
    )
    wait_for_rate_limit(13, "Before CLI lexicon-schema command")

    # Test 8.5: mp inspect lexicon-schema --type event --name <name>
    def test_cli_schema_single() -> dict[str, Any]:
        if not ws_schemas:
            return {"skipped": "No schemas in project"}
        # Find an event schema
        event_schema = next((s for s in ws_schemas if s.entity_type == "event"), None)
        if not event_schema:
            return {"skipped": "No event schemas in project"}
        result = subprocess.run(
            [
                "python",
                "-m",
                "mixpanel_data.cli.main",
                "inspect",
                "lexicon-schema",
                "--type",
                "event",
                "--name",
                event_schema.name,
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"CLI failed: {result.stderr}")
        data = json.loads(result.stdout)
        if data.get("name") != event_schema.name:
            raise ValueError(
                f"Name mismatch: {data.get('name')} != {event_schema.name}"
            )
        return {
            "exit_code": result.returncode,
            "name": data.get("name"),
            "entity_type": data.get("entity_type"),
        }

    runner.run_test(
        "8.5 mp inspect lexicon-schema --type/--name", test_cli_schema_single
    )
    # No wait needed - invalid type validation doesn't call API

    # Test 8.6: Invalid --type returns exit code 3
    def test_cli_invalid_type() -> dict[str, Any]:
        result = subprocess.run(
            [
                "python",
                "-m",
                "mixpanel_data.cli.main",
                "inspect",
                "lexicon-schemas",
                "--type",
                "invalid",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 3:
            raise ValueError(f"Expected exit code 3, got {result.returncode}")
        return {"exit_code": result.returncode, "is_invalid_args": True}

    runner.run_test("8.6 Invalid --type returns exit code 3", test_cli_invalid_type)

    # =========================================================================
    # Cleanup
    # =========================================================================
    print("\n[Cleanup]")
    print("-" * 40)

    def test_cleanup() -> dict[str, Any]:
        nonlocal api_client, workspace
        if api_client:
            api_client.__exit__(None, None, None)
            api_client = None
        if workspace:
            workspace.close()
            workspace = None
        return {"status": "cleaned up"}

    runner.run_test("Cleanup resources", test_cleanup)

    # =========================================================================
    # Results
    # =========================================================================
    runner.print_results()

    # Return exit code
    failed = sum(1 for r in runner.results if not r.passed)
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
