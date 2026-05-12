# ruff: noqa: ARG001, ARG005
"""Unit tests for Data Governance API client methods (Phase 027).

Tests for:
- Data Definitions: event/property definitions, tags, tracking metadata, history, export
- Custom Properties: CRUD + validate
- Drop Filters: CRUD + limits
- Lookup Tables: CRUD + upload/download workflows
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.session import Session
from mixpanel_headless.exceptions import MixpanelHeadlessError, QueryError
from tests.conftest import make_session

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def oauth_credentials() -> Session:
    """Create OAuth credentials for App API testing."""
    return make_session(project_id="12345", region="us", oauth_token="test-oauth-token")


def create_mock_client(
    credentials: Session,
    handler: Callable[[httpx.Request], httpx.Response],
) -> MixpanelAPIClient:
    """Create a client with mock transport (no workspace ID set).

    Data governance endpoints use maybe_scoped_path which defaults to project-scoped.

    Args:
        credentials: Authentication credentials.
        handler: Mock HTTP handler function.

    Returns:
        MixpanelAPIClient configured with mock transport.
    """
    transport = httpx.MockTransport(handler)
    return MixpanelAPIClient(session=credentials, _transport=transport)


# =============================================================================
# Domain 9 — Data Definitions (US1 + US2)
# =============================================================================


class TestGetEventDefinitions:
    """Tests for get_event_definitions() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """get_event_definitions() returns a list of event definition dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample event definitions."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"name": "Signup", "description": "User signed up"},
                        {"name": "Login", "description": "User logged in"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_event_definitions(["Signup", "Login"])

        assert len(result) == 2
        assert result[0]["name"] == "Signup"
        assert result[1]["name"] == "Login"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """get_event_definitions() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_event_definitions(["Signup"])

        assert "/data-definitions/events/" in captured_urls[0]

    def test_query_params(self, oauth_credentials: Session) -> None:
        """get_event_definitions() passes name[] query params."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_event_definitions(["Signup", "Login"])

        url = captured_urls[0]
        assert "name%5B%5D=Signup" in url or "name[]=Signup" in url

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """get_event_definitions() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_event_definitions(["Signup"])

        assert captured_methods[0] == "GET"


class TestUpdateEventDefinition:
    """Tests for update_event_definition() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """update_event_definition() returns the updated event definition dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"name": "Signup", "description": "Updated"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_event_definition(
                "Signup", {"event_name": "Signup", "description": "Updated"}
            )

        assert captured[0][0] == "PATCH"
        assert result["description"] == "Updated"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """update_event_definition() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"name": "Signup"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_event_definition("Signup", {"event_name": "Signup"})

        assert "/data-definitions/events/" in captured_urls[0]


class TestDeleteEventDefinition:
    """Tests for delete_event_definition() API client method."""

    def test_returns_none(self, oauth_credentials: Session) -> None:
        """delete_event_definition() returns None on success."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(200, json={"status": "ok"})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_event_definition("Signup")

        assert captured[0][0] == "DELETE"
        assert captured[0][1] == {"name": "Signup"}

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """delete_event_definition() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok"})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_event_definition("Signup")

        assert "/data-definitions/events/" in captured_urls[0]


class TestBulkUpdateEventDefinitions:
    """Tests for bulk_update_event_definitions() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """bulk_update_event_definitions() returns a list of updated dicts."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"name": "Signup", "description": "Bulk updated"},
                        {"name": "Login", "description": "Bulk updated"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.bulk_update_event_definitions(
                {"events": [{"name": "Signup"}, {"name": "Login"}]}
            )

        assert captured[0][0] == "PATCH"
        assert len(result) == 2

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """bulk_update_event_definitions() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.bulk_update_event_definitions({"events": []})

        assert "/data-definitions/events/" in captured_urls[0]


class TestGetPropertyDefinitions:
    """Tests for get_property_definitions() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """get_property_definitions() returns a list of property definition dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample property definitions."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"name": "plan_type", "type": "string"},
                        {"name": "age", "type": "number"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_property_definitions(["plan_type", "age"])

        assert len(result) == 2
        assert result[0]["name"] == "plan_type"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """get_property_definitions() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_property_definitions(["plan_type"])

        assert "/data-definitions/properties/" in captured_urls[0]

    def test_resource_type_param(self, oauth_credentials: Session) -> None:
        """get_property_definitions() passes resource_type query param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_property_definitions(["plan_type"], resource_type="event")

        assert "resource_type=event" in captured_urls[0]


class TestUpdatePropertyDefinition:
    """Tests for update_property_definition() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """update_property_definition() returns the updated property dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"name": "plan_type", "description": "Updated"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_property_definition(
                "plan_type", {"name": "plan_type", "description": "Updated"}
            )

        assert captured[0][0] == "PATCH"
        assert result["description"] == "Updated"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """update_property_definition() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"name": "plan_type"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_property_definition("plan_type", {"name": "plan_type"})

        assert "/data-definitions/properties/" in captured_urls[0]


class TestBulkUpdatePropertyDefinitions:
    """Tests for bulk_update_property_definitions() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """bulk_update_property_definitions() returns a list of updated dicts."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"name": "plan_type", "description": "Bulk updated"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.bulk_update_property_definitions(
                {"properties": [{"name": "plan_type"}]}
            )

        assert captured[0][0] == "PATCH"
        assert len(result) == 1

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """bulk_update_property_definitions() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.bulk_update_property_definitions({"properties": []})

        assert "/data-definitions/properties/" in captured_urls[0]


class TestListLexiconTags:
    """Tests for list_lexicon_tags() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """list_lexicon_tags() returns a list of tag dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample tags."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"id": 1, "name": "core"},
                        {"id": 2, "name": "deprecated"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_lexicon_tags()

        assert len(result) == 2
        assert result[0]["name"] == "core"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """list_lexicon_tags() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_lexicon_tags()

        assert "/data-definitions/tags/" in captured_urls[0]

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """list_lexicon_tags() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_lexicon_tags()

        assert captured_methods[0] == "GET"


class TestCreateLexiconTag:
    """Tests for create_lexicon_tag() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """create_lexicon_tag() returns the created tag dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": 10, "name": "new-tag"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_lexicon_tag({"name": "new-tag"})

        assert captured[0][0] == "POST"
        assert result["id"] == 10
        assert result["name"] == "new-tag"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """create_lexicon_tag() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 1, "name": "x"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_lexicon_tag({"name": "x"})

        assert "/data-definitions/tags/" in captured_urls[0]


class TestUpdateLexiconTag:
    """Tests for update_lexicon_tag() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """update_lexicon_tag() returns the updated tag dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": 5, "name": "renamed-tag"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_lexicon_tag(5, {"name": "renamed-tag"})

        assert captured[0][0] == "PATCH"
        assert result["name"] == "renamed-tag"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """update_lexicon_tag() targets the correct tag ID in URL."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 5, "name": "x"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_lexicon_tag(5, {"name": "x"})

        assert "/data-definitions/tags/5/" in captured_urls[0]


class TestDeleteLexiconTag:
    """Tests for delete_lexicon_tag() API client method."""

    def test_returns_none(self, oauth_credentials: Session) -> None:
        """delete_lexicon_tag() returns None on success."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(200, json={"status": "ok"})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_lexicon_tag("old-tag")

        assert captured[0][0] == "POST"
        assert captured[0][1] == {"delete": True, "name": "old-tag"}

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """delete_lexicon_tag() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok"})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_lexicon_tag("old-tag")

        assert "/data-definitions/tags/" in captured_urls[0]


class TestGetTrackingMetadata:
    """Tests for get_tracking_metadata() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """get_tracking_metadata() returns tracking metadata dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample tracking metadata."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "event_name": "Signup",
                        "is_tracked": True,
                        "last_seen": "2026-01-01",
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_tracking_metadata("Signup")

        assert result["event_name"] == "Signup"
        assert result["is_tracked"] is True

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """get_tracking_metadata() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_tracking_metadata("Signup")

        assert "/data-definitions/events/tracking-metadata/" in captured_urls[0]
        assert "event_name=Signup" in captured_urls[0]


class TestGetEventHistory:
    """Tests for get_event_history() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """get_event_history() returns a list of history entry dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample event history."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"action": "created", "timestamp": "2026-01-01"},
                        {"action": "updated", "timestamp": "2026-01-15"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_event_history("Signup")

        assert len(result) == 2
        assert result[0]["action"] == "created"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """get_event_history() includes event name in URL path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_event_history("Signup")

        assert "/data-definitions/events/Signup/history/" in captured_urls[0]


class TestGetPropertyHistory:
    """Tests for get_property_history() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """get_property_history() returns a list of history entry dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample property history."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"action": "created", "timestamp": "2026-01-01"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_property_history("plan_type", "event")

        assert len(result) == 1
        assert result[0]["action"] == "created"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """get_property_history() includes property name in URL path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_property_history("plan_type", "event")

        assert "/data-definitions/properties/plan_type/history/" in captured_urls[0]
        assert "entity_type=event" in captured_urls[0]


class TestExportLexicon:
    """Tests for export_lexicon() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """export_lexicon() returns an export dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample export response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "events": [{"name": "Signup"}],
                        "properties": [{"name": "plan_type"}],
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.export_lexicon()

        assert "events" in result
        assert "properties" in result

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """export_lexicon() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": {}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.export_lexicon()

        assert "/data-definitions/export/" in captured_urls[0]

    def test_export_types_param(self, oauth_credentials: Session) -> None:
        """export_lexicon(export_types=[...]) passes JSON-encoded export_type param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": {}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.export_lexicon(export_types=["All Events and Properties"])

        url = captured_urls[0]
        assert "export_type=" in url
        assert "All" in url  # JSON-encoded value in URL

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """export_lexicon() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": {}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.export_lexicon()

        assert captured_methods[0] == "GET"


# =============================================================================
# Domain 10 — Custom Properties (US4)
# =============================================================================


class TestListCustomProperties:
    """Tests for list_custom_properties() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """list_custom_properties() returns a list of custom property dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample custom properties."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"id": "cp-1", "name": "Lifetime Value"},
                        {"id": "cp-2", "name": "Days Since Signup"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_custom_properties()

        assert len(result) == 2
        assert result[0]["name"] == "Lifetime Value"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """list_custom_properties() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_custom_properties()

        assert "/custom_properties/" in captured_urls[0]

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """list_custom_properties() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_custom_properties()

        assert captured_methods[0] == "GET"


class TestCreateCustomProperty:
    """Tests for create_custom_property() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """create_custom_property() returns the created custom property dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": "cp-new", "name": "New Prop"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_custom_property({"name": "New Prop"})

        assert captured[0][0] == "POST"
        assert result["id"] == "cp-new"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """create_custom_property() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": "cp-1"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_custom_property({"name": "X"})

        assert "/custom_properties/" in captured_urls[0]


class TestGetCustomProperty:
    """Tests for get_custom_property() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """get_custom_property() returns the custom property dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample custom property."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": "cp-42", "name": "My Prop"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_custom_property("cp-42")

        assert result["id"] == "cp-42"
        assert result["name"] == "My Prop"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """get_custom_property() includes property ID in URL path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": "cp-42"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_custom_property("cp-42")

        assert "/custom_properties/cp-42/" in captured_urls[0]


class TestUpdateCustomProperty:
    """Tests for update_custom_property() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """update_custom_property() sends PUT and returns updated dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": "cp-42", "name": "Updated Prop"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_custom_property("cp-42", {"name": "Updated Prop"})

        assert captured[0][0] == "PUT"
        assert result["name"] == "Updated Prop"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """update_custom_property() includes property ID in URL path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": "cp-42"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_custom_property("cp-42", {"name": "X"})

        assert "/custom_properties/cp-42/" in captured_urls[0]


class TestDeleteCustomProperty:
    """Tests for delete_custom_property() API client method."""

    def test_returns_none(self, oauth_credentials: Session) -> None:
        """delete_custom_property() returns None on success."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method."""
            captured_methods.append(request.method)
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_custom_property("cp-42")

        assert captured_methods[0] == "DELETE"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """delete_custom_property() includes property ID in URL path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_custom_property("cp-42")

        assert "/custom_properties/cp-42/" in captured_urls[0]


class TestValidateCustomProperty:
    """Tests for validate_custom_property() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """validate_custom_property() sends POST and returns validation result."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"valid": True, "errors": []},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.validate_custom_property({"name": "Test Prop"})

        assert captured[0][0] == "POST"
        assert result["valid"] is True

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """validate_custom_property() targets validate endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"valid": True}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.validate_custom_property({"name": "X"})

        assert "/custom_properties/validate/" in captured_urls[0]


# =============================================================================
# Domain 12 — Drop Filters (US3)
# =============================================================================


class TestListDropFilters:
    """Tests for list_drop_filters() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """list_drop_filters() returns a list of drop filter dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample drop filters."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"id": 1, "event_name": "debug_event"},
                        {"id": 2, "event_name": "test_event"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_drop_filters()

        assert len(result) == 2
        assert result[0]["event_name"] == "debug_event"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """list_drop_filters() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_drop_filters()

        assert "/data-definitions/events/drop-filters/" in captured_urls[0]

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """list_drop_filters() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_drop_filters()

        assert captured_methods[0] == "GET"


class TestCreateDropFilter:
    """Tests for create_drop_filter() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """create_drop_filter() returns the full list after mutation."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"id": 1, "event_name": "debug_event"},
                        {"id": 2, "event_name": "new_filter"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_drop_filter({"event_name": "new_filter"})

        assert captured[0][0] == "POST"
        assert len(result) == 2

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """create_drop_filter() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_drop_filter({"event_name": "x"})

        assert "/data-definitions/events/drop-filters/" in captured_urls[0]


class TestUpdateDropFilter:
    """Tests for update_drop_filter() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """update_drop_filter() returns the full list after mutation."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"id": 1, "event_name": "updated_filter"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_drop_filter(
                {"id": 1, "event_name": "updated_filter"}
            )

        assert captured[0][0] == "PATCH"
        assert len(result) == 1

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """update_drop_filter() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_drop_filter({"id": 1})

        assert "/data-definitions/events/drop-filters/" in captured_urls[0]


class TestDeleteDropFilter:
    """Tests for delete_drop_filter() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """delete_drop_filter() returns the full list after deletion."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"id": 2, "event_name": "remaining_filter"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.delete_drop_filter(1)

        assert captured[0][0] == "DELETE"
        assert captured[0][1] == {"id": 1}
        assert len(result) == 1

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """delete_drop_filter() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_drop_filter(1)

        assert "/data-definitions/events/drop-filters/" in captured_urls[0]


class TestGetDropFilterLimits:
    """Tests for get_drop_filter_limits() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """get_drop_filter_limits() returns a limits dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample limits."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"max_filters": 10, "current_count": 3},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_drop_filter_limits()

        assert result["max_filters"] == 10
        assert result["current_count"] == 3

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """get_drop_filter_limits() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": {}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_drop_filter_limits()

        assert "/data-definitions/events/drop-filters/limits/" in captured_urls[0]

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """get_drop_filter_limits() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": {}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_drop_filter_limits()

        assert captured_methods[0] == "GET"


# =============================================================================
# Domain 13 — Lookup Tables (US5)
# =============================================================================


class TestListLookupTables:
    """Tests for list_lookup_tables() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """list_lookup_tables() returns a list of lookup table dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample lookup tables."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"data_group_id": 1, "name": "Plans"},
                        {"data_group_id": 2, "name": "Regions"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_lookup_tables()

        assert len(result) == 2
        assert result[0]["name"] == "Plans"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """list_lookup_tables() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_lookup_tables()

        assert "/data-definitions/lookup-tables/" in captured_urls[0]

    def test_data_group_id_param(self, oauth_credentials: Session) -> None:
        """list_lookup_tables(data_group_id=5) passes query param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_lookup_tables(data_group_id=5)

        assert "data-group-id=5" in captured_urls[0]

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """list_lookup_tables() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_lookup_tables()

        assert captured_methods[0] == "GET"


class TestGetLookupUploadUrl:
    """Tests for get_lookup_upload_url() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """get_lookup_upload_url() returns dict with url, path, key."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample upload URL response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "url": "https://storage.googleapis.com/upload",
                        "path": "/uploads/abc",
                        "key": "abc-123",
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_lookup_upload_url()

        assert "url" in result
        assert "path" in result
        assert "key" in result

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """get_lookup_upload_url() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"url": "", "path": "", "key": ""}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_lookup_upload_url()

        assert "/data-definitions/lookup-tables/upload-url/" in captured_urls[0]

    def test_content_type_param(self, oauth_credentials: Session) -> None:
        """get_lookup_upload_url(content_type='text/csv') passes param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"url": "", "path": "", "key": ""}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_lookup_upload_url(content_type="text/csv")

        url = captured_urls[0]
        assert "content-type=text" in url or "content-type=text%2Fcsv" in url


class TestUploadToSignedUrl:
    """Tests for upload_to_signed_url() API client method."""

    def test_returns_none(self, oauth_credentials: Session) -> None:
        """upload_to_signed_url() returns None on success."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and URL."""
            captured.append((request.method, str(request.url)))
            return httpx.Response(200)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.upload_to_signed_url(
                "https://storage.googleapis.com/upload", b"col1,col2\na,b"
            )

        assert captured[0][0] == "PUT"

    def test_targets_external_url(self, oauth_credentials: Session) -> None:
        """upload_to_signed_url() sends PUT to the provided external URL."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.upload_to_signed_url(
                "https://storage.googleapis.com/bucket/key", b"data"
            )

        assert "storage.googleapis.com" in captured_urls[0]


class TestRegisterLookupTable:
    """Tests for register_lookup_table() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """register_lookup_table() returns the registered lookup table dict."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and content type."""
            captured.append((request.method, request.headers.get("content-type", "")))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"data_group_id": 10, "name": "New Table"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.register_lookup_table(
                {"name": "New Table", "gcs_path": "/uploads/abc"}
            )

        assert captured[0][0] == "POST"
        assert result["data_group_id"] == 10

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """register_lookup_table() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"data_group_id": 1}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.register_lookup_table({"name": "X"})

        assert "/data-definitions/lookup-tables/" in captured_urls[0]


# =============================================================================
# Custom Events — create
# =============================================================================


class TestCreateCustomEvent:
    """Tests for create_custom_event() API client method."""

    def test_posts_form_encoded_body(self, oauth_credentials: Session) -> None:
        """create_custom_event() POSTs an application/x-www-form-urlencoded body."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture the request, return a custom_event envelope."""
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    "custom_event": {
                        "id": 99,
                        "name": "Page View",
                        "alternatives": [{"event": "Home"}],
                    }
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_custom_event(
                {"name": "Page View", "alternatives": '[{"event": "Home"}]'}
            )

        from urllib.parse import parse_qs

        req = captured[0]
        assert req.method == "POST"
        assert req.url.path.endswith("/custom_events/")
        assert req.headers["content-type"].startswith(
            "application/x-www-form-urlencoded"
        )
        body = parse_qs(req.content.decode())
        assert body["name"] == ["Page View"]
        assert json.loads(body["alternatives"][0]) == [{"event": "Home"}]
        assert result["id"] == 99
        assert result["name"] == "Page View"

    def test_unwraps_custom_event_envelope(self, oauth_credentials: Session) -> None:
        """create_custom_event() unwraps {custom_event: {...}} into the inner dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a {custom_event: ...} envelope."""
            return httpx.Response(
                200,
                json={
                    "custom_event": {
                        "id": 1,
                        "name": "X",
                        "alternatives": [],
                    }
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_custom_event({"name": "X", "alternatives": "[]"})

        assert result == {"id": 1, "name": "X", "alternatives": []}

    def test_unwraps_results_then_custom_event_envelope(
        self, oauth_credentials: Session
    ) -> None:
        """create_custom_event() unwraps both {results: ...} and {custom_event: ...}."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a doubly-wrapped envelope."""
            return httpx.Response(
                200,
                json={
                    "results": {
                        "custom_event": {
                            "id": 2,
                            "name": "Y",
                            "alternatives": [],
                        }
                    }
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_custom_event({"name": "Y", "alternatives": "[]"})

        assert result["id"] == 2
        assert result["name"] == "Y"

    def test_uses_maybe_scoped_path_project_default(
        self, oauth_credentials: Session
    ) -> None:
        """create_custom_event() uses project-scoped path by default."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture the URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"custom_event": {"id": 1, "name": "X", "alternatives": []}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_custom_event({"name": "X", "alternatives": "[]"})

        assert "/projects/12345/custom_events/" in captured_urls[0]

    def test_workspace_scoped_path_when_workspace_id_set(
        self, oauth_credentials: Session
    ) -> None:
        """create_custom_event() honors workspace ID when set on the client."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture the URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"custom_event": {"id": 1, "name": "X", "alternatives": []}},
            )

        client = create_mock_client(oauth_credentials, handler)
        client.set_workspace_id(77)
        with client:
            client.create_custom_event({"name": "X", "alternatives": "[]"})

        assert "/workspaces/77/custom_events/" in captured_urls[0]

    def test_400_raises_query_error(self, oauth_credentials: Session) -> None:
        """create_custom_event() raises QueryError on 400 (e.g. duplicate name)."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a 400 error."""
            return httpx.Response(400, json={"error": "duplicate name"})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(QueryError):
            client.create_custom_event({"name": "X", "alternatives": "[]"})

    def test_422_raises_query_error_with_form_body_in_context(
        self, oauth_credentials: Session
    ) -> None:
        """create_custom_event() raises QueryError on 422 and preserves the form body."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a 422 validation error."""
            return httpx.Response(422, json={"error": "alternative not found"})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(QueryError) as exc_info:
            client.create_custom_event(
                {"name": "X", "alternatives": '[{"event": "Unknown"}]'}
            )
        # Form-body callers should still get the form payload echoed in the
        # exception so debugging the rejected request is possible.
        assert exc_info.value.request_body == {
            "name": "X",
            "alternatives": '[{"event": "Unknown"}]',
        }

    def test_non_dict_response_raises_mixpanel_headless_error(
        self, oauth_credentials: Session
    ) -> None:
        """create_custom_event() raises MixpanelHeadlessError if response isn't a dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a non-dict JSON response."""
            return httpx.Response(200, json=[1, 2, 3])

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError):
            client.create_custom_event({"name": "X", "alternatives": "[]"})

    def test_non_json_response_raises_mixpanel_headless_error(
        self, oauth_credentials: Session
    ) -> None:
        """create_custom_event() raises MixpanelHeadlessError with INVALID_RESPONSE.

        The error must carry ``code="INVALID_RESPONSE"`` (so callers can
        distinguish "server returned junk" from other failures) and the
        message must include the request method and URL fragment so the
        failure is debuggable from the exception alone.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a 200 with non-JSON body."""
            return httpx.Response(200, content=b"not json at all")

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError) as exc_info:
            client.create_custom_event({"name": "X", "alternatives": "[]"})
        assert exc_info.value.code == "INVALID_RESPONSE"
        message = str(exc_info.value)
        assert "POST" in message
        assert "/custom_events/" in message

    def test_retries_on_429(self, oauth_credentials: Session) -> None:
        """create_custom_event() retries through app_request on 429."""
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 429 once, then 200."""
            attempts.append(1)
            if len(attempts) == 1:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "0"},
                    json={"error": "rate limited"},
                )
            return httpx.Response(
                200,
                json={"custom_event": {"id": 1, "name": "X", "alternatives": []}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_custom_event({"name": "X", "alternatives": "[]"})

        assert len(attempts) == 2  # one retry then success
        assert result["id"] == 1

    def test_wraps_httpx_transport_error(self, oauth_credentials: Session) -> None:
        """create_custom_event() surfaces httpx.HTTPError as MixpanelHeadlessError."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Raise a transport-level ConnectError."""
            raise httpx.ConnectError("connection refused")

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError):
            client.create_custom_event({"name": "X", "alternatives": "[]"})


# =============================================================================
# Custom Events — update
# =============================================================================


class TestUpdateCustomEvent:
    """Tests for update_custom_event() API client method."""

    def test_patch_body_uses_custom_event_id_not_name(
        self, oauth_credentials: Session
    ) -> None:
        """update_custom_event() sends customEventId in the PATCH body.

        The data-definitions endpoint matches by the most specific identifier;
        sending only ``name`` creates an orphan lexicon entry instead of
        updating the existing one.
        """
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request, return success."""
            captured.append(request)
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 1, "name": "X"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_custom_event(2044168, {"description": "Updated"})

        body = json.loads(captured[0].content.decode())
        assert body["customEventId"] == 2044168
        assert "name" not in body

    def test_422_raises_query_error(self, oauth_credentials: Session) -> None:
        """update_custom_event() raises QueryError on 422 (validation error)."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a 422 validation error."""
            return httpx.Response(422, json={"error": "unknown customEventId"})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(QueryError):
            client.update_custom_event(999_999_999, {"description": "X"})

    def test_returns_target_mismatch_when_response_id_differs(
        self, oauth_credentials: Session
    ) -> None:
        """update_custom_event() raises UPDATE_TARGET_MISMATCH on echo mismatch.

        Defense-in-depth: if the server echoes back a customEventId that
        differs from what we requested, treat it as a failure rather than
        returning an unrelated entity.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return success but with a mismatched customEventId."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "id": 1,
                        "name": "X",
                        "customEventId": 99999,  # mismatched
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError) as exc_info:
            client.update_custom_event(2044168, {"description": "X"})
        assert exc_info.value.code == "UPDATE_TARGET_MISMATCH"
        assert "99999" in str(exc_info.value)
        assert "2044168" in str(exc_info.value)

    def test_returns_dict_when_response_id_matches(
        self, oauth_credentials: Session
    ) -> None:
        """update_custom_event() returns the dict when customEventId matches."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return success with the matching customEventId."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "id": 1,
                        "name": "X",
                        "customEventId": 2044168,
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_custom_event(2044168, {"description": "X"})
        assert result["customEventId"] == 2044168


# =============================================================================
# Custom Events — delete
# =============================================================================


class TestDeleteCustomEvent:
    """Tests for delete_custom_event() API client method."""

    def test_body_uses_custom_event_id_not_name(
        self, oauth_credentials: Session
    ) -> None:
        """delete_custom_event() sends customEventId in the DELETE body.

        The data-definitions endpoint matches by the most specific
        identifier; sending only ``name`` is ambiguous when display names
        collide and may delete the wrong row.
        """
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request, return success."""
            captured.append(request)
            return httpx.Response(200, json={"status": "ok"})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_custom_event(2044168)

        assert captured[0].method == "DELETE"
        body = json.loads(captured[0].content.decode())
        assert body["customEventId"] == 2044168
        assert "name" not in body

    def test_uses_maybe_scoped_path_project_default(
        self, oauth_credentials: Session
    ) -> None:
        """delete_custom_event() uses project-scoped data-definitions path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture the URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok"})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_custom_event(42)

        assert "/projects/12345/data-definitions/events/" in captured_urls[0]

    def test_workspace_scoped_path_when_workspace_id_set(
        self, oauth_credentials: Session
    ) -> None:
        """delete_custom_event() honors workspace ID when set on the client."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture the URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok"})

        client = create_mock_client(oauth_credentials, handler)
        client.set_workspace_id(77)
        with client:
            client.delete_custom_event(42)

        assert "/workspaces/77/data-definitions/events/" in captured_urls[0]

    def test_404_raises_query_error(self, oauth_credentials: Session) -> None:
        """delete_custom_event() raises QueryError on 404 (unknown id)."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a 404 not found."""
            return httpx.Response(404, json={"error": "not found"})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(QueryError):
            client.delete_custom_event(999_999_999)


class TestMarkLookupTableReady:
    """Tests for mark_lookup_table_ready() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """mark_lookup_table_ready() returns the lookup table dict."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and content type."""
            captured.append((request.method, request.headers.get("content-type", "")))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"data_group_id": 10, "status": "ready"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.mark_lookup_table_ready(
                {"data_group_id": "10", "status": "ready"}
            )

        assert captured[0][0] == "POST"
        assert result["status"] == "ready"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """mark_lookup_table_ready() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"data_group_id": 1}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.mark_lookup_table_ready({"data_group_id": "1"})

        assert "/data-definitions/lookup-tables/" in captured_urls[0]


class TestGetLookupUploadStatus:
    """Tests for get_lookup_upload_status() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """get_lookup_upload_status() returns status dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample upload status."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"upload_id": "u-123", "state": "complete"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_lookup_upload_status("u-123")

        assert result["upload_id"] == "u-123"
        assert result["state"] == "complete"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """get_lookup_upload_status() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_lookup_upload_status("u-123")

        assert "/data-definitions/lookup-tables/upload-status/" in captured_urls[0]
        assert "upload-id=u-123" in captured_urls[0]


class TestUpdateLookupTable:
    """Tests for update_lookup_table() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """update_lookup_table() sends PATCH and returns updated dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"data_group_id": 5, "name": "Updated Table"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_lookup_table(5, {"name": "Updated Table"})

        assert captured[0][0] == "PATCH"
        assert result["name"] == "Updated Table"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """update_lookup_table() sends data_group_id in JSON body."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and body."""
            captured.append((str(request.url), json.loads(request.content)))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"data_group_id": 5}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_lookup_table(5, {"name": "X"})

        assert "/data-definitions/lookup-tables/" in captured[0][0]
        assert captured[0][1]["data-group-id"] == 5
        assert captured[0][1]["name"] == "X"


class TestDeleteLookupTables:
    """Tests for delete_lookup_tables() API client method."""

    def test_returns_none(self, oauth_credentials: Session) -> None:
        """delete_lookup_tables() returns None on success."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(200, json={"status": "ok"})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_lookup_tables([1, 2, 3])

        assert captured[0][0] == "DELETE"
        assert captured[0][1] == {"data-group-ids": [1, 2, 3]}

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """delete_lookup_tables() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok"})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_lookup_tables([1])

        assert "/data-definitions/lookup-tables/" in captured_urls[0]


class TestDownloadLookupTable:
    """Tests for download_lookup_table() API client method."""

    def test_returns_bytes(self, oauth_credentials: Session) -> None:
        """download_lookup_table() returns raw bytes."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return CSV bytes."""
            return httpx.Response(
                200,
                content=b"col1,col2\nval1,val2",
                headers={"content-type": "text/csv"},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.download_lookup_table(5)

        assert isinstance(result, bytes)
        assert b"col1,col2" in result

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """download_lookup_table() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, content=b"data")

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.download_lookup_table(5)

        assert "/data-definitions/lookup-tables/download/" in captured_urls[0]
        assert "data-group-id=5" in captured_urls[0]

    def test_optional_params(self, oauth_credentials: Session) -> None:
        """download_lookup_table() passes optional file_name and limit params."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, content=b"data")

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.download_lookup_table(5, file_name="export.csv", limit=100)

        url = captured_urls[0]
        assert "file-name=export.csv" in url
        assert "limit=100" in url


class TestGetLookupDownloadUrl:
    """Tests for get_lookup_download_url() API client method."""

    def test_returns_str(self, oauth_credentials: Session) -> None:
        """get_lookup_download_url() returns a URL string."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return download URL response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": "https://storage.googleapis.com/download/abc",
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_lookup_download_url(5)

        assert isinstance(result, str)
        assert "storage.googleapis.com" in result

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """get_lookup_download_url() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": "https://example.com"},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_lookup_download_url(5)

        assert "/data-definitions/lookup-tables/download-url/" in captured_urls[0]
        assert "data-group-id=5" in captured_urls[0]

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """get_lookup_download_url() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={"status": "ok", "results": "https://example.com"},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_lookup_download_url(5)

        assert captured_methods[0] == "GET"


# =============================================================================
# Error-Path Tests
# =============================================================================


class TestExportLexiconAsyncStringResponse:
    """Tests for export_lexicon() handling async string responses."""

    def test_export_lexicon_async_string_response(
        self, oauth_credentials: Session
    ) -> None:
        """Test export_lexicon handles async string response from API.

        When the Mixpanel API returns a plain string (e.g., an async export status
        message) instead of a dict, export_lexicon() should wrap it in a dict
        with ``status`` and ``message`` keys.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a string result instead of a dict."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": "Export in progress",
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.export_lexicon()

        assert result == {"status": "pending", "message": "Export in progress"}


class TestGetLookupUploadUrlMissingKeys:
    """Tests for get_lookup_upload_url() response validation."""

    def test_get_lookup_upload_url_missing_keys(
        self, oauth_credentials: Session
    ) -> None:
        """Test get_lookup_upload_url raises MixpanelHeadlessError when keys are missing.

        The response dict must contain ``url``, ``path``, and ``key`` fields.
        When any are missing, the method should raise MixpanelHeadlessError to signal
        an invalid API response.

        Note: This test validates the fix that adds key validation to
        get_lookup_upload_url(). It will fail until the fix is applied.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a response missing required keys."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"url": "https://example.com"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError):
            client.get_lookup_upload_url()


class TestUploadToSignedUrlNetworkFailure:
    """Tests for upload_to_signed_url() network error handling."""

    def test_upload_to_signed_url_network_failure(
        self, oauth_credentials: Session
    ) -> None:
        """Test upload_to_signed_url wraps ConnectError in MixpanelHeadlessError.

        When the PUT request to the signed URL fails with a network error
        (e.g., ``httpx.ConnectError``), the method should catch it and raise
        ``MixpanelHeadlessError`` instead.

        Note: This test validates the fix that adds ConnectError handling to
        upload_to_signed_url(). It will fail until the fix is applied.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Simulate a network failure by raising ConnectError."""
            raise httpx.ConnectError("Connection refused")

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError):
            client.upload_to_signed_url(
                "https://storage.example.com/upload", b"col1,col2\na,b"
            )


class TestRegisterLookupTableNonJsonResponse:
    """Tests for register_lookup_table() non-JSON response handling."""

    def test_register_lookup_table_non_json_response(
        self, oauth_credentials: Session
    ) -> None:
        """Test register_lookup_table raises MixpanelHeadlessError for non-JSON 200 response.

        When the server returns a 200 response with a body that is not valid JSON,
        ``register_lookup_table()`` should raise ``MixpanelHeadlessError`` instead of
        propagating the raw JSON decode error.

        Note: This test validates the fix that adds try/except around response.json()
        in register_lookup_table(). It will fail until the fix is applied.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a non-JSON 200 response."""
            return httpx.Response(
                200,
                text="<html>Server Error</html>",
                headers={"content-type": "text/html"},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError):
            client.register_lookup_table({"name": "Test Table"})
