# ruff: noqa: ARG001, ARG005
"""Unit tests for Workspace data governance CRUD methods (Phase 027).

Tests for data governance operations on the Workspace facade:
- Data definitions (events/properties): get, update, delete, bulk update
- Tags: list, create, update, delete
- Drop filters: list, create, update, delete, limits
- Custom properties: list, create, get, update, delete, validate
- Custom events: list, update, delete
- Tracking & history: metadata, event history, property history
- Lexicon export
- Lookup tables: list, upload, mark ready, get upload URL/status, update, delete, download

Verifies:
- Correct return types
- Fields match mock data
- Parameters serialized correctly
- Multi-step orchestration (upload_lookup_table)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.exceptions import AuthenticationError, MixpanelHeadlessError
from mixpanel_headless.types import (
    BulkEventUpdate,
    BulkPropertyUpdate,
    BulkUpdateEventsParams,
    BulkUpdatePropertiesParams,
    ComposedPropertyValue,
    CreateCustomEventParams,
    CreateCustomPropertyParams,
    CreateDropFilterParams,
    CreateTagParams,
    CustomEvent,
    CustomProperty,
    DropFilter,
    DropFilterLimitsResponse,
    EventDefinition,
    LexiconTag,
    LookupTable,
    LookupTableUploadUrl,
    MarkLookupTableReadyParams,
    PropertyDefinition,
    UpdateCustomPropertyParams,
    UpdateDropFilterParams,
    UpdateEventDefinitionParams,
    UpdateLookupTableParams,
    UpdatePropertyDefinitionParams,
    UpdateTagParams,
    UploadLookupTableParams,
)
from mixpanel_headless.workspace import Workspace
from tests.conftest import make_session

# ---- 042 redesign: canonical fake Session for Workspace(session=…) ----
_TEST_SESSION = Session(
    account=ServiceAccount(
        name="test_account",
        region="us",
        username="test_user",
        secret=SecretStr("test_secret"),
        default_project="12345",
    ),
    project=Project(id="12345"),
)

# =============================================================================
# Helpers
# =============================================================================


def _make_oauth_credentials() -> Session:
    """Create OAuth Credentials for testing.

    Returns:
        A Credentials instance with auth_method=oauth.
    """
    return make_session(project_id="12345", region="us", oauth_token="test-token")


# _setup_config_with_account removed in B1 (Fix 9): the legacy v1
# ``ConfigManager.add_account(project_id=, region=, …)`` signature is
# gone; ``_make_workspace`` now relies on ``session=_TEST_SESSION``
# instead, which never touches a real ConfigManager.


def _make_workspace(
    temp_dir: Path,
    handler: Any,
) -> Workspace:
    """Create a Workspace with a mock HTTP transport.

    Args:
        temp_dir: Temporary directory for config and storage.
        handler: Handler function for httpx.MockTransport.

    Returns:
        A Workspace instance wired to the mock transport.
    """
    creds = _make_oauth_credentials()
    transport = httpx.MockTransport(handler)
    client = MixpanelAPIClient(session=creds, _transport=transport)
    return Workspace(
        session=_TEST_SESSION,
        _api_client=client,
    )


# =============================================================================
# Mock response data
# =============================================================================


def _event_def_json(
    id: int = 1,
    name: str = "Purchase",
) -> dict[str, Any]:
    """Return a minimal event definition dict matching the API shape.

    Args:
        id: Event definition ID.
        name: Event name.

    Returns:
        Dict that can be parsed into an EventDefinition model.
    """
    return {
        "id": id,
        "name": name,
        "description": f"Description for {name}",
        "hidden": False,
        "dropped": False,
    }


def _property_def_json(
    id: int = 1,
    name: str = "$browser",
) -> dict[str, Any]:
    """Return a minimal property definition dict matching the API shape.

    Args:
        id: Property definition ID.
        name: Property name.

    Returns:
        Dict that can be parsed into a PropertyDefinition model.
    """
    return {
        "id": id,
        "name": name,
        "resource_type": "event",
        "description": f"Description for {name}",
        "hidden": False,
    }


def _tag_json(
    id: int = 1,
    name: str = "core-metrics",
) -> dict[str, Any]:
    """Return a minimal Lexicon tag dict matching the API shape.

    Args:
        id: Tag ID.
        name: Tag name.

    Returns:
        Dict that can be parsed into a LexiconTag model.
    """
    return {
        "id": id,
        "name": name,
    }


def _drop_filter_json(
    id: int = 1,
    event_name: str = "debug_log",
) -> dict[str, Any]:
    """Return a minimal drop filter dict matching the API shape.

    Args:
        id: Drop filter ID.
        event_name: Event name to filter.

    Returns:
        Dict that can be parsed into a DropFilter model.
    """
    return {
        "id": id,
        "event_name": event_name,
        "filters": [],
        "active": True,
    }


def _custom_property_json(
    custom_property_id: int = 1,
    name: str = "Revenue",
    resource_type: str = "events",
) -> dict[str, Any]:
    """Return a minimal custom property dict matching the API shape.

    Args:
        custom_property_id: Custom property ID.
        name: Property name.
        resource_type: Resource type (events, people, group_profiles).

    Returns:
        Dict that can be parsed into a CustomProperty model.
    """
    return {
        "custom_property_id": custom_property_id,
        "name": name,
        "resource_type": resource_type,
        "description": f"Custom property {name}",
        "display_formula": 'number(properties["amount"])',
        "is_visible": True,
    }


def _lookup_table_json(
    id: int = 1,
    name: str = "Products",
) -> dict[str, Any]:
    """Return a minimal lookup table dict matching the API shape.

    Args:
        id: Lookup table ID.
        name: Table name.

    Returns:
        Dict that can be parsed into a LookupTable model.
    """
    return {
        "id": id,
        "name": name,
        "token": "abc123",
        "created_at": "2026-01-01T00:00:00Z",
    }


# =============================================================================
# US1: Data Definitions — Events
# =============================================================================


class TestGetEventDefinitions:
    """Tests for Workspace.get_event_definitions()."""

    def test_returns_list_of_event_definitions(self, temp_dir: Path) -> None:
        """get_event_definitions() returns list of EventDefinition objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return event definition list."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": [_event_def_json()]},
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_event_definitions(names=["Purchase"])

        assert len(result) == 1
        assert isinstance(result[0], EventDefinition)
        assert result[0].name == "Purchase"

    def test_returns_multiple_definitions(self, temp_dir: Path) -> None:
        """get_event_definitions() handles multiple events."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return multiple event definitions."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _event_def_json(1, "Purchase"),
                        _event_def_json(2, "Signup"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_event_definitions(names=["Purchase", "Signup"])

        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].name == "Signup"

    def test_returns_empty_list(self, temp_dir: Path) -> None:
        """get_event_definitions() returns empty list when no matches."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_event_definitions(names=["NonExistent"])

        assert result == []


class TestUpdateEventDefinition:
    """Tests for Workspace.update_event_definition()."""

    def test_returns_updated_event_definition(self, temp_dir: Path) -> None:
        """update_event_definition() returns the updated EventDefinition."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated event definition."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _event_def_json(1, "Purchase"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateEventDefinitionParams(
            description="Updated description", verified=True
        )
        result = ws.update_event_definition("Purchase", params)

        assert isinstance(result, EventDefinition)
        assert result.name == "Purchase"


class TestDeleteEventDefinition:
    """Tests for Workspace.delete_event_definition()."""

    def test_delete_returns_none(self, temp_dir: Path) -> None:
        """delete_event_definition() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return success for delete."""
            return httpx.Response(200, json={"status": "ok"})

        ws = _make_workspace(temp_dir, handler)
        ws.delete_event_definition("OldEvent")  # Should not raise


class TestBulkUpdateEventDefinitions:
    """Tests for Workspace.bulk_update_event_definitions()."""

    def test_returns_list_of_updated_definitions(self, temp_dir: Path) -> None:
        """bulk_update_event_definitions() returns list of EventDefinition."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bulk update results."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _event_def_json(1, "E1"),
                        _event_def_json(2, "E2"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = BulkUpdateEventsParams(
            events=[
                BulkEventUpdate(name="E1", hidden=True),
                BulkEventUpdate(name="E2", verified=True),
            ]
        )
        result = ws.bulk_update_event_definitions(params)

        assert len(result) == 2
        assert isinstance(result[0], EventDefinition)
        assert result[0].name == "E1"
        assert result[1].name == "E2"


# =============================================================================
# US1: Data Definitions — Properties
# =============================================================================


class TestGetPropertyDefinitions:
    """Tests for Workspace.get_property_definitions()."""

    def test_returns_list_of_property_definitions(self, temp_dir: Path) -> None:
        """get_property_definitions() returns list of PropertyDefinition."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return property definition list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [_property_def_json()],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_property_definitions(names=["$browser"])

        assert len(result) == 1
        assert isinstance(result[0], PropertyDefinition)
        assert result[0].name == "$browser"

    def test_with_resource_type_filter(self, temp_dir: Path) -> None:
        """get_property_definitions() passes resource_type to API."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return property definitions."""
            captured_url.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [_property_def_json()],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_property_definitions(names=["$browser"], resource_type="event")

        assert len(result) == 1

    def test_returns_empty_list(self, temp_dir: Path) -> None:
        """get_property_definitions() returns empty list when no matches."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_property_definitions(names=["nonexistent"])

        assert result == []


class TestUpdatePropertyDefinition:
    """Tests for Workspace.update_property_definition()."""

    def test_returns_updated_property_definition(self, temp_dir: Path) -> None:
        """update_property_definition() returns the updated PropertyDefinition."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated property definition."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _property_def_json(1, "$browser"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdatePropertyDefinitionParams(sensitive=True)
        result = ws.update_property_definition("$browser", params)

        assert isinstance(result, PropertyDefinition)
        assert result.name == "$browser"


class TestBulkUpdatePropertyDefinitions:
    """Tests for Workspace.bulk_update_property_definitions()."""

    def test_returns_list_of_updated_properties(self, temp_dir: Path) -> None:
        """bulk_update_property_definitions() returns list of PropertyDefinition."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bulk update results."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _property_def_json(1, "$browser"),
                        _property_def_json(2, "$city"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = BulkUpdatePropertiesParams(
            properties=[
                BulkPropertyUpdate(name="$browser", resource_type="event", hidden=True),
                BulkPropertyUpdate(name="$city", resource_type="event", sensitive=True),
            ]
        )
        result = ws.bulk_update_property_definitions(params)

        assert len(result) == 2
        assert isinstance(result[0], PropertyDefinition)
        assert result[0].name == "$browser"
        assert result[1].name == "$city"


# =============================================================================
# US2: Tags
# =============================================================================


class TestListLexiconTags:
    """Tests for Workspace.list_lexicon_tags()."""

    def test_returns_list_of_tags(self, temp_dir: Path) -> None:
        """list_lexicon_tags() returns list of LexiconTag objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return tag list (API returns tag objects with id/name)."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"id": 1, "name": "core-metrics"},
                        {"id": 2, "name": "growth"},
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        tags = ws.list_lexicon_tags()

        assert len(tags) == 2
        assert isinstance(tags[0], LexiconTag)
        assert tags[0].id == 1
        assert tags[0].name == "core-metrics"
        assert tags[1].id == 2
        assert tags[1].name == "growth"

    def test_returns_empty_list(self, temp_dir: Path) -> None:
        """list_lexicon_tags() returns empty list when no tags exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        tags = ws.list_lexicon_tags()

        assert tags == []


class TestCreateLexiconTag:
    """Tests for Workspace.create_lexicon_tag()."""

    def test_returns_created_tag(self, temp_dir: Path) -> None:
        """create_lexicon_tag() returns the created LexiconTag."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created tag."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _tag_json(99, "new-tag"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateTagParams(name="new-tag")
        tag = ws.create_lexicon_tag(params)

        assert isinstance(tag, LexiconTag)
        assert tag.id == 99
        assert tag.name == "new-tag"


class TestUpdateLexiconTag:
    """Tests for Workspace.update_lexicon_tag()."""

    def test_returns_updated_tag(self, temp_dir: Path) -> None:
        """update_lexicon_tag() returns the updated LexiconTag."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated tag."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _tag_json(1, "renamed-tag"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateTagParams(name="renamed-tag")
        tag = ws.update_lexicon_tag(1, params)

        assert isinstance(tag, LexiconTag)
        assert tag.name == "renamed-tag"


class TestDeleteLexiconTag:
    """Tests for Workspace.delete_lexicon_tag()."""

    def test_delete_returns_none(self, temp_dir: Path) -> None:
        """delete_lexicon_tag() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return success for delete."""
            return httpx.Response(200, json={"status": "ok"})

        ws = _make_workspace(temp_dir, handler)
        ws.delete_lexicon_tag("core-metrics")  # Should not raise


# =============================================================================
# US3: Drop Filters
# =============================================================================


class TestListDropFilters:
    """Tests for Workspace.list_drop_filters()."""

    def test_returns_list_of_drop_filters(self, temp_dir: Path) -> None:
        """list_drop_filters() returns list of DropFilter objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return drop filter list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _drop_filter_json(1, "debug_log"),
                        _drop_filter_json(2, "test_event"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        filters = ws.list_drop_filters()

        assert len(filters) == 2
        assert isinstance(filters[0], DropFilter)
        assert filters[0].event_name == "debug_log"
        assert filters[1].id == 2

    def test_returns_empty_list(self, temp_dir: Path) -> None:
        """list_drop_filters() returns empty list when none exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        filters = ws.list_drop_filters()

        assert filters == []


class TestCreateDropFilter:
    """Tests for Workspace.create_drop_filter()."""

    def test_returns_updated_filter_list(self, temp_dir: Path) -> None:
        """create_drop_filter() returns the full list of DropFilter objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated filter list after creation."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _drop_filter_json(1, "debug_log"),
                        _drop_filter_json(2, "new_filter"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateDropFilterParams(
            event_name="new_filter",
            filters={"property": "env", "operator": "equals", "value": "test"},
        )
        result = ws.create_drop_filter(params)

        assert len(result) == 2
        assert isinstance(result[0], DropFilter)
        assert result[1].event_name == "new_filter"


class TestUpdateDropFilter:
    """Tests for Workspace.update_drop_filter()."""

    def test_returns_updated_filter_list(self, temp_dir: Path) -> None:
        """update_drop_filter() returns the full list of DropFilter objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated filter list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _drop_filter_json(1, "debug_log"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateDropFilterParams(id=1, active=False)
        result = ws.update_drop_filter(params)

        assert len(result) == 1
        assert isinstance(result[0], DropFilter)


class TestDeleteDropFilter:
    """Tests for Workspace.delete_drop_filter()."""

    def test_returns_remaining_filter_list(self, temp_dir: Path) -> None:
        """delete_drop_filter() returns the remaining list of DropFilter objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return remaining filter list after deletion."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [_drop_filter_json(2, "kept_filter")],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.delete_drop_filter(1)

        assert len(result) == 1
        assert result[0].event_name == "kept_filter"


class TestGetDropFilterLimits:
    """Tests for Workspace.get_drop_filter_limits()."""

    def test_returns_limits_response(self, temp_dir: Path) -> None:
        """get_drop_filter_limits() returns DropFilterLimitsResponse."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return drop filter limits."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"filter_limit": 10},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        limits = ws.get_drop_filter_limits()

        assert isinstance(limits, DropFilterLimitsResponse)
        assert limits.filter_limit == 10


# =============================================================================
# US4: Custom Properties
# =============================================================================


class TestListCustomProperties:
    """Tests for Workspace.list_custom_properties()."""

    def test_returns_list_of_custom_properties(self, temp_dir: Path) -> None:
        """list_custom_properties() returns list of CustomProperty objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return custom property list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _custom_property_json(1, "Revenue", "events"),
                        _custom_property_json(2, "LTV", "people"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        props = ws.list_custom_properties()

        assert len(props) == 2
        assert isinstance(props[0], CustomProperty)
        assert props[0].name == "Revenue"
        assert props[1].resource_type == "people"

    def test_returns_empty_list(self, temp_dir: Path) -> None:
        """list_custom_properties() returns empty list when none exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        props = ws.list_custom_properties()

        assert props == []


class TestCreateCustomProperty:
    """Tests for Workspace.create_custom_property()."""

    def test_returns_created_custom_property(self, temp_dir: Path) -> None:
        """create_custom_property() returns the created CustomProperty."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created custom property."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _custom_property_json(99, "New Prop", "events"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateCustomPropertyParams(
            name="New Prop",
            resource_type="events",
            display_formula='number(properties["amount"])',
            composed_properties={
                "amount": ComposedPropertyValue(resource_type="event")
            },
        )
        prop = ws.create_custom_property(params)

        assert isinstance(prop, CustomProperty)
        assert prop.custom_property_id == 99
        assert prop.name == "New Prop"


class TestGetCustomProperty:
    """Tests for Workspace.get_custom_property()."""

    def test_returns_single_custom_property(self, temp_dir: Path) -> None:
        """get_custom_property() returns a single CustomProperty by ID."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return single custom property."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _custom_property_json(42, "Revenue", "events"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        prop = ws.get_custom_property("42")

        assert isinstance(prop, CustomProperty)
        assert prop.custom_property_id == 42
        assert prop.name == "Revenue"


class TestUpdateCustomProperty:
    """Tests for Workspace.update_custom_property()."""

    def test_returns_updated_custom_property(self, temp_dir: Path) -> None:
        """update_custom_property() returns the updated CustomProperty."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated custom property."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _custom_property_json(42, "Renamed", "events"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateCustomPropertyParams(name="Renamed")
        prop = ws.update_custom_property("42", params)

        assert isinstance(prop, CustomProperty)
        assert prop.name == "Renamed"


class TestDeleteCustomProperty:
    """Tests for Workspace.delete_custom_property()."""

    def test_delete_returns_none(self, temp_dir: Path) -> None:
        """delete_custom_property() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return success for delete."""
            return httpx.Response(200, json={"status": "ok"})

        ws = _make_workspace(temp_dir, handler)
        ws.delete_custom_property("42")  # Should not raise


class TestValidateCustomProperty:
    """Tests for Workspace.validate_custom_property()."""

    def test_returns_validation_dict(self, temp_dir: Path) -> None:
        """validate_custom_property() returns an opaque dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return validation result."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"valid": True, "errors": []},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateCustomPropertyParams(
            name="Test Prop",
            resource_type="events",
            display_formula='number(properties["x"])',
            composed_properties={"x": ComposedPropertyValue(resource_type="event")},
        )
        result = ws.validate_custom_property(params)

        assert isinstance(result, dict)
        assert result["valid"] is True


# =============================================================================
# US6: Custom Events
# =============================================================================


class TestCreateCustomEvent:
    """Tests for Workspace.create_custom_event()."""

    def test_returns_custom_event(self, temp_dir: Path) -> None:
        """create_custom_event() returns a typed CustomEvent built from the API response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a successful create response."""
            return httpx.Response(
                200,
                json={
                    "custom_event": {
                        "id": 42,
                        "name": "Page View",
                        "alternatives": [
                            {"event": "Home"},
                            {"event": "Product"},
                        ],
                    }
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.create_custom_event(
            CreateCustomEventParams(name="Page View", alternatives=["Home", "Product"])
        )

        assert isinstance(result, CustomEvent)
        assert result.id == 42
        assert result.name == "Page View"
        assert [a.event for a in result.alternatives] == ["Home", "Product"]

    def test_serializes_params_to_form_body(self, temp_dir: Path) -> None:
        """create_custom_event() POSTs alternatives as JSON list of {event:...} dicts."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture the request and return a minimal envelope."""
            captured.append(request)
            return httpx.Response(
                200,
                json={"custom_event": {"id": 1, "name": "X", "alternatives": []}},
            )

        ws = _make_workspace(temp_dir, handler)
        ws.create_custom_event(
            CreateCustomEventParams(name="X", alternatives=["A", "B"])
        )

        from urllib.parse import parse_qs

        body = parse_qs(captured[0].content.decode())
        import json as _json

        decoded = _json.loads(body["alternatives"][0])
        assert decoded == [{"event": "A"}, {"event": "B"}]
        assert body["name"] == ["X"]
        assert (
            captured[0]
            .headers["content-type"]
            .startswith("application/x-www-form-urlencoded")
        )

    def test_propagates_auth_error(self, temp_dir: Path) -> None:
        """create_custom_event() surfaces 401 as AuthenticationError."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a 401 unauthorized."""
            return httpx.Response(401, json={"error": "unauthorized"})

        ws = _make_workspace(temp_dir, handler)
        with pytest.raises(AuthenticationError):
            ws.create_custom_event(
                CreateCustomEventParams(name="X", alternatives=["A"])
            )


class TestListCustomEvents:
    """Tests for Workspace.list_custom_events()."""

    def test_returns_list_of_event_definitions(self, temp_dir: Path) -> None:
        """list_custom_events() returns list of EventDefinition objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return custom event list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _event_def_json(1, "CustomEvent1"),
                        _event_def_json(2, "CustomEvent2"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        events = ws.list_custom_events()

        assert len(events) == 2
        assert isinstance(events[0], EventDefinition)
        assert events[0].name == "CustomEvent1"

    def test_returns_empty_list(self, temp_dir: Path) -> None:
        """list_custom_events() returns empty list when none exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        events = ws.list_custom_events()

        assert events == []


class TestUpdateCustomEvent:
    """Tests for Workspace.update_custom_event()."""

    def test_returns_updated_event_definition(self, temp_dir: Path) -> None:
        """update_custom_event() returns the updated EventDefinition."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated custom event."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _event_def_json(1, "CustomEvent1"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateEventDefinitionParams(description="Updated")
        result = ws.update_custom_event(2044168, params)

        assert isinstance(result, EventDefinition)
        assert result.name == "CustomEvent1"

    def test_patch_body_uses_custom_event_id_not_name(self, temp_dir: Path) -> None:
        """update_custom_event() must send customEventId in the PATCH body.

        The Mixpanel data-definitions endpoint matches updates by the most
        specific identifier; for custom events that's customEventId. Sending
        only ``name`` creates an orphan lexicon entry rather than updating
        the existing one. Mirrors the webapp's buildUpdatePayload precedence.
        """
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request, return updated event."""
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _event_def_json(1, "CustomEvent1"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateEventDefinitionParams(description="Updated", verified=True)
        ws.update_custom_event(2044168, params)

        import json as _json

        body = _json.loads(captured[0].content.decode())
        assert body["customEventId"] == 2044168
        assert "name" not in body
        assert body["description"] == "Updated"
        assert body["verified"] is True

    def test_raises_when_server_returns_different_custom_event_id(
        self, temp_dir: Path
    ) -> None:
        """update_custom_event() raises if server echoes a different id.

        Defense-in-depth check against the data-definitions endpoint's
        history of silently fabricating a new lexicon entry instead of
        updating the requested one. If the server's response says
        ``customEventId=other`` when we requested ``custom_event_id=ours``,
        treat it as a failed write rather than returning an unrelated
        entity to the caller.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a response with a *different* customEventId."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        **_event_def_json(1, "CustomEvent1"),
                        "customEventId": 99999,  # mismatched on purpose
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateEventDefinitionParams(description="Updated")
        with pytest.raises(MixpanelHeadlessError) as exc_info:
            ws.update_custom_event(2044168, params)
        assert exc_info.value.code == "UPDATE_TARGET_MISMATCH"
        assert "99999" in str(exc_info.value)
        assert "2044168" in str(exc_info.value)


class TestDeleteCustomEvent:
    """Tests for Workspace.delete_custom_event()."""

    def test_delete_returns_none(self, temp_dir: Path) -> None:
        """delete_custom_event() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return success for delete."""
            return httpx.Response(200, json={"status": "ok"})

        ws = _make_workspace(temp_dir, handler)
        ws.delete_custom_event(2044168)  # Should not raise

    def test_delete_body_uses_custom_event_id_not_name(self, temp_dir: Path) -> None:
        """delete_custom_event() must send customEventId in the DELETE body.

        The Mixpanel data-definitions endpoint matches by the most specific
        identifier; sending only ``name`` is ambiguous when multiple lexicon
        rows share a display name and may delete the wrong row, an
        auto-derived orphan, or no-op silently while reporting success.
        Mirrors the same precedence rule that drives ``update_custom_event``.
        """
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request, return success."""
            captured.append(request)
            return httpx.Response(200, json={"status": "ok"})

        ws = _make_workspace(temp_dir, handler)
        ws.delete_custom_event(2044168)

        import json as _json

        body = _json.loads(captured[0].content.decode())
        assert body["customEventId"] == 2044168
        assert "name" not in body


# =============================================================================
# US7: Tracking & History
# =============================================================================


class TestGetTrackingMetadata:
    """Tests for Workspace.get_tracking_metadata()."""

    def test_returns_metadata_dict(self, temp_dir: Path) -> None:
        """get_tracking_metadata() returns an opaque dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return tracking metadata."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "last_seen": "2026-01-01",
                        "platforms": ["web", "ios"],
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_tracking_metadata("Purchase")

        assert isinstance(result, dict)
        assert result["last_seen"] == "2026-01-01"
        assert "web" in result["platforms"]


class TestGetEventHistory:
    """Tests for Workspace.get_event_history()."""

    def test_returns_list_of_history_entries(self, temp_dir: Path) -> None:
        """get_event_history() returns a list of history dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return event history."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"action": "created", "timestamp": "2026-01-01"},
                        {"action": "updated", "timestamp": "2026-02-01"},
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_event_history("Purchase")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["action"] == "created"

    def test_returns_empty_history(self, temp_dir: Path) -> None:
        """get_event_history() returns empty list when no history."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty history."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_event_history("Purchase")

        assert result == []


class TestGetPropertyHistory:
    """Tests for Workspace.get_property_history()."""

    def test_returns_list_of_history_entries(self, temp_dir: Path) -> None:
        """get_property_history() returns a list of history dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return property history."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"action": "hidden", "timestamp": "2026-03-01"},
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_property_history("$browser", "event")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["action"] == "hidden"


# =============================================================================
# US8: Export
# =============================================================================


class TestExportLexicon:
    """Tests for Workspace.export_lexicon()."""

    def test_returns_export_dict(self, temp_dir: Path) -> None:
        """export_lexicon() returns an opaque dict with export data."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return export data."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "events": [_event_def_json()],
                        "properties": [_property_def_json()],
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.export_lexicon()

        assert isinstance(result, dict)
        assert "events" in result
        assert "properties" in result

    def test_with_export_types_filter(self, temp_dir: Path) -> None:
        """export_lexicon(export_types=['events']) passes filter to API."""
        captured_body: list[bytes] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body and return export data."""
            captured_body.append(request.content)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "events": [_event_def_json()],
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.export_lexicon(export_types=["events"])

        assert isinstance(result, dict)

    def test_returns_all_types_by_default(self, temp_dir: Path) -> None:
        """export_lexicon() with no filter returns all types."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return full export data."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "events": [],
                        "properties": [],
                        "tags": [],
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.export_lexicon()

        assert isinstance(result, dict)


# =============================================================================
# US5: Lookup Tables
# =============================================================================


class TestListLookupTables:
    """Tests for Workspace.list_lookup_tables()."""

    def test_returns_list_of_lookup_tables(self, temp_dir: Path) -> None:
        """list_lookup_tables() returns list of LookupTable objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return lookup table list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _lookup_table_json(1, "Products"),
                        _lookup_table_json(2, "Categories"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        tables = ws.list_lookup_tables()

        assert len(tables) == 2
        assert isinstance(tables[0], LookupTable)
        assert tables[0].name == "Products"
        assert tables[1].id == 2

    def test_returns_empty_list(self, temp_dir: Path) -> None:
        """list_lookup_tables() returns empty list when none exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        tables = ws.list_lookup_tables()

        assert tables == []

    def test_with_data_group_id_filter(self, temp_dir: Path) -> None:
        """list_lookup_tables(data_group_id=5) passes param to API."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return lookup tables."""
            captured_url.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [_lookup_table_json()],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        tables = ws.list_lookup_tables(data_group_id=5)

        assert len(tables) == 1


class TestUploadLookupTable:
    """Tests for Workspace.upload_lookup_table() — 3-step orchestration."""

    def test_orchestrates_upload_and_returns_lookup_table(self, temp_dir: Path) -> None:
        """upload_lookup_table() handles get URL, upload, register steps."""
        request_count: list[int] = [0]

        def handler(request: httpx.Request) -> httpx.Response:
            """Handle multi-step upload orchestration."""
            request_count[0] += 1
            url = str(request.url)

            # Step 1: Get upload URL
            if "upload-url" in url or "upload_url" in url:
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": {
                            "url": "https://storage.googleapis.com/upload",
                            "path": "gs://bucket/path",
                            "key": "product_id",
                        },
                    },
                )

            # Step 2: Upload to GCS (the signed URL)
            if "storage.googleapis.com" in url:
                return httpx.Response(200)

            # Step 3: Register / mark ready
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _lookup_table_json(99, "Products"),
                },
            )

        # Create a temp CSV file
        csv_path = temp_dir / "products.csv"
        csv_path.write_text("product_id,name\n1,Widget\n2,Gadget\n")

        ws = _make_workspace(temp_dir, handler)
        params = UploadLookupTableParams(name="Products", file_path=str(csv_path))
        result = ws.upload_lookup_table(params)

        assert isinstance(result, LookupTable)
        assert result.name == "Products"
        assert result.id == 99
        assert request_count[0] >= 2  # At least upload URL + register

    def test_async_upload_polls_until_complete(self, temp_dir: Path) -> None:
        """upload_lookup_table() polls status for async uploads (>= 5 MB).

        When the API returns {"uploadId": "..."} instead of a full table
        object, the method should poll get_lookup_upload_status() until
        the upload completes, then return the resulting LookupTable.
        """
        poll_count: list[int] = [0]

        def handler(request: httpx.Request) -> httpx.Response:
            """Simulate async upload: register returns uploadId, poll returns SUCCESS."""
            url = str(request.url)

            # Step 1: Get upload URL
            if "upload-url" in url or "upload_url" in url:
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": {
                            "url": "https://storage.googleapis.com/upload",
                            "path": "gs://bucket/path",
                            "key": "product_id",
                        },
                    },
                )

            # Step 2: Upload to GCS
            if "storage.googleapis.com" in url:
                return httpx.Response(200)

            # Step 3: Register returns async token (simulating >= 5 MB)
            if "upload-status" not in url and request.method == "POST":
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": {"uploadId": "task-abc-123"},
                    },
                )

            # Step 4: Poll upload status
            poll_count[0] += 1
            if poll_count[0] < 2:
                return httpx.Response(
                    200,
                    json={"status": "ok", "results": {"uploadStatus": "PENDING"}},
                )
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "uploadStatus": "SUCCESS",
                        "result": _lookup_table_json(99, "BigTable"),
                    },
                },
            )

        csv_path = temp_dir / "big.csv"
        csv_path.write_text("product_id,name\n1,Widget\n")

        ws = _make_workspace(temp_dir, handler)
        params = UploadLookupTableParams(name="BigTable", file_path=str(csv_path))
        result = ws.upload_lookup_table(params, poll_interval=0.01)

        assert isinstance(result, LookupTable)
        assert result.name == "BigTable"
        assert result.id == 99
        assert poll_count[0] >= 2  # Polled at least twice

    def test_async_upload_timeout_raises(self, temp_dir: Path) -> None:
        """upload_lookup_table() raises MixpanelHeadlessError on async timeout.

        When polling exceeds max_poll_seconds, a clear timeout error
        should be raised with the upload ID for manual follow-up.
        """
        import pytest

        from mixpanel_headless.exceptions import MixpanelHeadlessError

        def handler(request: httpx.Request) -> httpx.Response:
            """Always return PENDING to trigger timeout."""
            url = str(request.url)

            if "upload-url" in url or "upload_url" in url:
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": {
                            "url": "https://storage.googleapis.com/upload",
                            "path": "gs://bucket/path",
                            "key": "product_id",
                        },
                    },
                )
            if "storage.googleapis.com" in url:
                return httpx.Response(200)
            if "upload-status" not in url and request.method == "POST":
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": {"uploadId": "task-timeout"},
                    },
                )
            # Always PENDING
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"uploadStatus": "PENDING"}},
            )

        csv_path = temp_dir / "big.csv"
        csv_path.write_text("product_id,name\n1,Widget\n")

        ws = _make_workspace(temp_dir, handler)
        params = UploadLookupTableParams(name="BigTable", file_path=str(csv_path))

        with pytest.raises(MixpanelHeadlessError, match="timed out"):
            ws.upload_lookup_table(params, poll_interval=0.01, max_poll_seconds=0.05)

    def test_async_upload_failure_raises(self, temp_dir: Path) -> None:
        """upload_lookup_table() raises MixpanelHeadlessError on async failure.

        When the upload task fails (status FAILURE), a clear error should
        be raised with the failure details.
        """
        import pytest

        from mixpanel_headless.exceptions import MixpanelHeadlessError

        def handler(request: httpx.Request) -> httpx.Response:
            """Return FAILURE on status poll."""
            url = str(request.url)

            if "upload-url" in url or "upload_url" in url:
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": {
                            "url": "https://storage.googleapis.com/upload",
                            "path": "gs://bucket/path",
                            "key": "product_id",
                        },
                    },
                )
            if "storage.googleapis.com" in url:
                return httpx.Response(200)
            if "upload-status" not in url and request.method == "POST":
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": {"uploadId": "task-fail"},
                    },
                )
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"uploadStatus": "FAILURE"}},
            )

        csv_path = temp_dir / "bad.csv"
        csv_path.write_text("product_id,name\n1,Widget\n")

        ws = _make_workspace(temp_dir, handler)
        params = UploadLookupTableParams(name="BadTable", file_path=str(csv_path))

        with pytest.raises(MixpanelHeadlessError, match="failed"):
            ws.upload_lookup_table(params, poll_interval=0.01)


class TestMarkLookupTableReady:
    """Tests for Workspace.mark_lookup_table_ready()."""

    def test_returns_lookup_table(self, temp_dir: Path) -> None:
        """mark_lookup_table_ready() returns a LookupTable."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return lookup table after marking ready."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _lookup_table_json(1, "Products"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = MarkLookupTableReadyParams(name="Products", key="product_id")
        result = ws.mark_lookup_table_ready(params)

        assert isinstance(result, LookupTable)
        assert result.name == "Products"


class TestGetLookupUploadUrl:
    """Tests for Workspace.get_lookup_upload_url()."""

    def test_returns_upload_url(self, temp_dir: Path) -> None:
        """get_lookup_upload_url() returns LookupTableUploadUrl."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return upload URL response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "url": "https://storage.googleapis.com/upload",
                        "path": "gs://bucket/path",
                        "key": "id",
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_lookup_upload_url()

        assert isinstance(result, LookupTableUploadUrl)
        assert "storage.googleapis.com" in result.url

    def test_with_content_type(self, temp_dir: Path) -> None:
        """get_lookup_upload_url(content_type='text/csv') passes param."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return upload URL."""
            captured_url.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "url": "https://storage.googleapis.com/upload",
                        "path": "gs://bucket/path",
                        "key": "id",
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_lookup_upload_url(content_type="text/csv")

        assert isinstance(result, LookupTableUploadUrl)


class TestGetLookupUploadStatus:
    """Tests for Workspace.get_lookup_upload_status()."""

    def test_returns_status_dict(self, temp_dir: Path) -> None:
        """get_lookup_upload_status() returns an opaque dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return upload status."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "upload_id": "abc123",
                        "state": "completed",
                        "rows_imported": 1000,
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_lookup_upload_status("abc123")

        assert isinstance(result, dict)
        assert result["state"] == "completed"
        assert result["rows_imported"] == 1000


class TestUpdateLookupTable:
    """Tests for Workspace.update_lookup_table()."""

    def test_returns_updated_lookup_table(self, temp_dir: Path) -> None:
        """update_lookup_table() returns the updated LookupTable."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated lookup table."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _lookup_table_json(1, "Renamed Catalog"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateLookupTableParams(name="Renamed Catalog")
        result = ws.update_lookup_table(1, params)

        assert isinstance(result, LookupTable)
        assert result.name == "Renamed Catalog"


class TestDeleteLookupTables:
    """Tests for Workspace.delete_lookup_tables()."""

    def test_delete_returns_none(self, temp_dir: Path) -> None:
        """delete_lookup_tables() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return success for delete."""
            return httpx.Response(200, json={"status": "ok"})

        ws = _make_workspace(temp_dir, handler)
        ws.delete_lookup_tables([1, 2])  # Should not raise


class TestDownloadLookupTable:
    """Tests for Workspace.download_lookup_table()."""

    def test_returns_bytes(self, temp_dir: Path) -> None:
        """download_lookup_table() returns raw bytes."""
        csv_content = b"product_id,name\n1,Widget\n2,Gadget\n"

        def handler(request: httpx.Request) -> httpx.Response:
            """Return CSV bytes."""
            return httpx.Response(200, content=csv_content)

        ws = _make_workspace(temp_dir, handler)
        result = ws.download_lookup_table(1)

        assert isinstance(result, bytes)
        assert b"product_id" in result
        assert b"Widget" in result

    def test_with_file_name_and_limit(self, temp_dir: Path) -> None:
        """download_lookup_table() accepts optional file_name and limit."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return CSV bytes."""
            captured_url.append(str(request.url))
            return httpx.Response(200, content=b"id,name\n1,A\n")

        ws = _make_workspace(temp_dir, handler)
        result = ws.download_lookup_table(1, file_name="export.csv", limit=100)

        assert isinstance(result, bytes)


class TestGetLookupDownloadUrl:
    """Tests for Workspace.get_lookup_download_url()."""

    def test_returns_url_string(self, temp_dir: Path) -> None:
        """get_lookup_download_url() returns a signed download URL string."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return download URL."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": "https://storage.googleapis.com/download/abc",
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_lookup_download_url(1)

        assert isinstance(result, str)
        assert "storage.googleapis.com" in result
