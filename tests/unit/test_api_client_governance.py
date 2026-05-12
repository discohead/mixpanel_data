# ruff: noqa: ARG001, ARG005
"""Unit tests for Schema Governance API client methods (Phase 028).

Tests for:
- Schema Enforcement: get, init, update, replace, delete
- Data Auditing: run_audit, run_audit_events_only
- Data Volume Anomalies: list, update, bulk_update
- Event Deletion Requests: list, create, cancel, preview_filters
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.session import Session
from mixpanel_headless.exceptions import MixpanelHeadlessError
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
# Domain 15 — Schema Enforcement
# =============================================================================


class TestGetSchemaEnforcement:
    """Tests for get_schema_enforcement() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """get_schema_enforcement() returns the enforcement config dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample enforcement config."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "id": 1,
                        "ruleEvent": "Warn and Accept",
                        "state": "ingested",
                        "notificationEmails": ["admin@example.com"],
                        "events": [],
                        "commonProperties": [],
                        "userProperties": [],
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_schema_enforcement()

        assert result["ruleEvent"] == "Warn and Accept"
        assert result["state"] == "ingested"

    def test_with_fields_param(self, oauth_credentials: Session) -> None:
        """get_schema_enforcement(fields=...) passes fields query parameter."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "ruleEvent": "Warn and Accept",
                        "state": "ingested",
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_schema_enforcement(fields="ruleEvent,state")

        assert "fields=ruleEvent" in captured_urls[0] or "fields=" in captured_urls[0]

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """get_schema_enforcement() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={"status": "ok", "results": {}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_schema_enforcement()

        assert captured_methods[0] == "GET"

    def test_uses_correct_path(self, oauth_credentials: Session) -> None:
        """get_schema_enforcement() hits data-definitions/schema/ endpoint."""
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
            client.get_schema_enforcement()

        assert "/data-definitions/schema/" in captured_urls[0]


class TestInitSchemaEnforcement:
    """Tests for init_schema_enforcement() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """init_schema_enforcement() returns the created config dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "id": 1,
                        "ruleEvent": "Warn and Drop",
                        "state": "planned",
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.init_schema_enforcement({"ruleEvent": "Warn and Drop"})

        assert result["ruleEvent"] == "Warn and Drop"
        assert captured[0][0] == "POST"
        assert captured[0][1]["ruleEvent"] == "Warn and Drop"

    def test_uses_correct_path(self, oauth_credentials: Session) -> None:
        """init_schema_enforcement() hits data-definitions/schema/ endpoint."""
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
            client.init_schema_enforcement({"ruleEvent": "Warn and Accept"})

        assert "/data-definitions/schema/" in captured_urls[0]


class TestUpdateSchemaEnforcement:
    """Tests for update_schema_enforcement() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """update_schema_enforcement() returns the updated config dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "ruleEvent": "Warn and Hide",
                        "notificationEmails": ["new@example.com"],
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_schema_enforcement(
                {
                    "ruleEvent": "Warn and Hide",
                    "notificationEmails": ["new@example.com"],
                }
            )

        assert result["ruleEvent"] == "Warn and Hide"
        assert captured[0][0] == "PATCH"

    def test_partial_body(self, oauth_credentials: Session) -> None:
        """update_schema_enforcement() sends only provided fields."""
        captured_bodies: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body."""
            captured_bodies.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_schema_enforcement(
                {"notificationEmails": ["only@example.com"]}
            )

        assert captured_bodies[0] == {"notificationEmails": ["only@example.com"]}


class TestReplaceSchemaEnforcement:
    """Tests for replace_schema_enforcement() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """replace_schema_enforcement() returns the replaced config dict."""
        captured: list[tuple[str, Any]] = []

        full_body = {
            "ruleEvent": "Warn and Drop",
            "notificationEmails": ["admin@example.com"],
            "events": [{"name": "Signup"}],
            "commonProperties": [{"name": "utm_source"}],
            "userProperties": [{"name": "$email"}],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={"status": "ok", "results": full_body},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.replace_schema_enforcement(full_body)

        assert result["ruleEvent"] == "Warn and Drop"
        assert captured[0][0] == "PUT"
        assert captured[0][1] == full_body

    def test_uses_correct_path(self, oauth_credentials: Session) -> None:
        """replace_schema_enforcement() hits data-definitions/schema/ endpoint."""
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
            client.replace_schema_enforcement({"ruleEvent": "Warn and Accept"})

        assert "/data-definitions/schema/" in captured_urls[0]


class TestDeleteSchemaEnforcement:
    """Tests for delete_schema_enforcement() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """delete_schema_enforcement() returns the response dict."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"deleted": True}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.delete_schema_enforcement()

        assert result["deleted"] is True
        assert captured_methods[0] == "DELETE"

    def test_uses_correct_path(self, oauth_credentials: Session) -> None:
        """delete_schema_enforcement() hits data-definitions/schema/ endpoint."""
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
            client.delete_schema_enforcement()

        assert "/data-definitions/schema/" in captured_urls[0]


# =============================================================================
# Domain 15 — Data Auditing
# =============================================================================


class TestRunAudit:
    """Tests for run_audit() API client method."""

    def test_returns_parsed_response(self, oauth_credentials: Session) -> None:
        """run_audit() returns raw response with 2-element array in results."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return audit response with 2-element array."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        [
                            {
                                "violation": "Unexpected Event",
                                "name": "bad_event",
                                "count": 42,
                            },
                            {
                                "violation": "Missing Property",
                                "name": "utm_source",
                                "event": "Signup",
                                "count": 10,
                            },
                        ],
                        {"computed_at": "2026-01-01T00:00:00Z"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.run_audit()

        # The raw response is a 2-element array
        assert isinstance(result, list)
        assert len(result) == 2
        # First element is violations list
        assert len(result[0]) == 2
        assert result[0][0]["violation"] == "Unexpected Event"
        # Second element is metadata
        assert result[1]["computed_at"] == "2026-01-01T00:00:00Z"

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """run_audit() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={"status": "ok", "results": [[], {"computed_at": "2026-01-01"}]},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.run_audit()

        assert captured_methods[0] == "GET"

    def test_uses_correct_path(self, oauth_credentials: Session) -> None:
        """run_audit() hits data-definitions/audit/ endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": [[], {"computed_at": "2026-01-01"}]},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.run_audit()

        assert "/data-definitions/audit/" in captured_urls[0]

    def test_empty_violations(self, oauth_credentials: Session) -> None:
        """run_audit() handles empty violations list."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return audit response with no violations."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [[], {"computed_at": "2026-01-01T12:00:00Z"}],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.run_audit()

        assert result[0] == []
        assert result[1]["computed_at"] == "2026-01-01T12:00:00Z"

    def test_non_list_results_raises(self, oauth_credentials: Session) -> None:
        """run_audit() raises MixpanelHeadlessError when results is not a list."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return non-list results."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"unexpected": "dict"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError, match="expected list"):
            client.run_audit()


class TestRunAuditEventsOnly:
    """Tests for run_audit_events_only() API client method."""

    def test_returns_parsed_response(self, oauth_credentials: Session) -> None:
        """run_audit_events_only() returns raw response with 2-element array."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return events-only audit response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        [
                            {
                                "violation": "Unexpected Event",
                                "name": "rogue_event",
                                "count": 100,
                            },
                        ],
                        {"computed_at": "2026-01-02T00:00:00Z"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.run_audit_events_only()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0][0]["violation"] == "Unexpected Event"
        assert result[1]["computed_at"] == "2026-01-02T00:00:00Z"

    def test_uses_correct_path(self, oauth_credentials: Session) -> None:
        """run_audit_events_only() hits data-definitions/audit-events-only/ endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": [[], {"computed_at": "2026-01-01"}]},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.run_audit_events_only()

        assert "/data-definitions/audit-events-only/" in captured_urls[0]

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """run_audit_events_only() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={"status": "ok", "results": [[], {"computed_at": "2026-01-01"}]},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.run_audit_events_only()

        assert captured_methods[0] == "GET"

    def test_non_list_results_raises(self, oauth_credentials: Session) -> None:
        """run_audit_events_only() raises MixpanelHeadlessError when results is not a list."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return non-list results."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"unexpected": "dict"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError, match="expected list"):
            client.run_audit_events_only()


# =============================================================================
# Domain 15 — Data Volume Anomalies
# =============================================================================


def _anomaly_json(
    id: int = 1,
    event_name: str = "Signup",
    status: str = "open",
    anomaly_class: str = "Event",
) -> dict[str, Any]:
    """Return a minimal anomaly dict matching the API shape.

    Args:
        id: Anomaly ID.
        event_name: Event name.
        status: Anomaly status.
        anomaly_class: Class of anomaly.

    Returns:
        Dict that can be parsed into a DataVolumeAnomaly model.
    """
    return {
        "id": id,
        "timestamp": "2026-01-01T00:00:00Z",
        "actualCount": 5000,
        "predictedUpper": 3000,
        "predictedLower": 1000,
        "percentVariance": "66.7%",
        "status": status,
        "project": 12345,
        "event": 1,
        "eventName": event_name,
        "property": None,
        "propertyName": None,
        "metric": None,
        "metricName": None,
        "metricType": None,
        "primaryType": None,
        "driftTypes": None,
        "anomalyClass": anomaly_class,
    }


class TestListDataVolumeAnomalies:
    """Tests for list_data_volume_anomalies() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """list_data_volume_anomalies() returns a list of anomaly dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return anomaly list nested in results.anomalies."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "anomalies": [
                            _anomaly_json(1, "Signup"),
                            _anomaly_json(2, "Login"),
                        ],
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_data_volume_anomalies()

        assert len(result) == 2
        assert result[0]["eventName"] == "Signup"
        assert result[1]["eventName"] == "Login"

    def test_with_query_params(self, oauth_credentials: Session) -> None:
        """list_data_volume_anomalies() passes query parameters."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"anomalies": [_anomaly_json(1)]},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_data_volume_anomalies(query_params={"status": "open"})

        assert "status=open" in captured_urls[0]

    def test_empty_list(self, oauth_credentials: Session) -> None:
        """list_data_volume_anomalies() returns empty list when no anomalies."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty anomalies list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"anomalies": []},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_data_volume_anomalies()

        assert result == []

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """list_data_volume_anomalies() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"anomalies": []}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_data_volume_anomalies()

        assert captured_methods[0] == "GET"

    def test_uses_correct_path(self, oauth_credentials: Session) -> None:
        """list_data_volume_anomalies() hits data-definitions/data-volume-anomalies/."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"anomalies": []}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_data_volume_anomalies()

        assert "/data-definitions/data-volume-anomalies/" in captured_urls[0]

    def test_missing_anomalies_key_raises(self, oauth_credentials: Session) -> None:
        """list_data_volume_anomalies() raises when 'anomalies' key is missing."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return response without anomalies key."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"items": []}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with (
            client,
            pytest.raises(MixpanelHeadlessError, match="missing 'anomalies' key"),
        ):
            client.list_data_volume_anomalies()


class TestUpdateAnomaly:
    """Tests for update_anomaly() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """update_anomaly() returns the response dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"updated": True}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_anomaly(
                {"id": 123, "status": "dismissed", "anomalyClass": "Event"}
            )

        assert result["updated"] is True
        assert captured[0][0] == "PATCH"
        assert captured[0][1]["id"] == 123
        assert captured[0][1]["status"] == "dismissed"
        assert captured[0][1]["anomalyClass"] == "Event"

    def test_uses_correct_path(self, oauth_credentials: Session) -> None:
        """update_anomaly() hits data-definitions/data-volume-anomalies/ endpoint."""
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
            client.update_anomaly(
                {"id": 1, "status": "dismissed", "anomalyClass": "Event"}
            )

        url = captured_urls[0]
        assert "/data-definitions/data-volume-anomalies/" in url
        assert "/bulk/" not in url


class TestBulkUpdateAnomalies:
    """Tests for bulk_update_anomalies() API client method."""

    def test_returns_dict(self, oauth_credentials: Session) -> None:
        """bulk_update_anomalies() returns the response dict."""
        captured: list[tuple[str, Any]] = []

        body = {
            "anomalies": [
                {"id": 1, "anomalyClass": "Event"},
                {"id": 2, "anomalyClass": "Property"},
            ],
            "status": "dismissed",
        }

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"updated": 2}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.bulk_update_anomalies(body)

        assert result["updated"] == 2
        assert captured[0][0] == "PATCH"
        assert len(captured[0][1]["anomalies"]) == 2

    def test_uses_correct_path(self, oauth_credentials: Session) -> None:
        """bulk_update_anomalies() hits data-definitions/data-volume-anomalies/bulk/."""
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
            client.bulk_update_anomalies(
                {
                    "anomalies": [{"id": 1, "anomalyClass": "Event"}],
                    "status": "dismissed",
                }
            )

        assert "/data-definitions/data-volume-anomalies/bulk/" in captured_urls[0]


# =============================================================================
# Domain 15 — Event Deletion Requests
# =============================================================================


def _deletion_request_json(
    id: int = 1,
    event_name: str = "bad_event",
    status: str = "Submitted",
) -> dict[str, Any]:
    """Return a minimal deletion request dict matching the API shape.

    Args:
        id: Request ID.
        event_name: Event name to delete.
        status: Request status.

    Returns:
        Dict that can be parsed into an EventDeletionRequest model.
    """
    return {
        "id": id,
        "displayName": None,
        "eventName": event_name,
        "fromDate": "2026-01-01",
        "toDate": "2026-01-31",
        "filters": None,
        "status": status,
        "deletedEventsCount": 0,
        "created": "2026-01-15T00:00:00Z",
        "requestingUser": {"id": 1, "email": "admin@example.com"},
    }


class TestListDeletionRequests:
    """Tests for list_deletion_requests() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """list_deletion_requests() returns a list of deletion request dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return deletion requests list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _deletion_request_json(1, "event_a"),
                        _deletion_request_json(2, "event_b"),
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_deletion_requests()

        assert len(result) == 2
        assert result[0]["eventName"] == "event_a"
        assert result[1]["eventName"] == "event_b"

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """list_deletion_requests() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={"status": "ok", "results": []},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_deletion_requests()

        assert captured_methods[0] == "GET"

    def test_uses_correct_path(self, oauth_credentials: Session) -> None:
        """list_deletion_requests() hits data-definitions/events/deletion-requests/."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": []},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_deletion_requests()

        assert "/data-definitions/events/deletion-requests/" in captured_urls[0]


class TestCreateDeletionRequest:
    """Tests for create_deletion_request() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """create_deletion_request() returns the updated full list."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _deletion_request_json(1, "existing_event"),
                        _deletion_request_json(2, "new_event"),
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_deletion_request(
                {
                    "eventName": "new_event",
                    "fromDate": "2026-01-01",
                    "toDate": "2026-01-31",
                }
            )

        assert len(result) == 2
        assert captured[0][0] == "POST"
        assert captured[0][1]["eventName"] == "new_event"

    def test_uses_correct_path(self, oauth_credentials: Session) -> None:
        """create_deletion_request() hits data-definitions/events/deletion-requests/."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": []},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_deletion_request(
                {"eventName": "e", "fromDate": "2026-01-01", "toDate": "2026-01-31"}
            )

        assert "/data-definitions/events/deletion-requests/" in captured_urls[0]


class TestCancelDeletionRequest:
    """Tests for cancel_deletion_request() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """cancel_deletion_request() returns the updated full list."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [_deletion_request_json(1, "remaining")],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.cancel_deletion_request(42)

        assert len(result) == 1
        assert captured[0][0] == "DELETE"
        assert captured[0][1]["id"] == 42

    def test_sends_json_body_with_id(self, oauth_credentials: Session) -> None:
        """cancel_deletion_request() sends JSON body with id field."""
        captured_bodies: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body."""
            captured_bodies.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={"status": "ok", "results": []},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.cancel_deletion_request(99)

        assert captured_bodies[0] == {"id": 99}

    def test_uses_correct_path(self, oauth_credentials: Session) -> None:
        """cancel_deletion_request() hits data-definitions/events/deletion-requests/."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": []},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.cancel_deletion_request(1)

        assert "/data-definitions/events/deletion-requests/" in captured_urls[0]


class TestPreviewDeletionFilters:
    """Tests for preview_deletion_filters() API client method."""

    def test_returns_list(self, oauth_credentials: Session) -> None:
        """preview_deletion_filters() returns a list of filter dicts."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"property": "country", "op": "equals", "value": "US"},
                        {"property": "platform", "op": "equals", "value": "iOS"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.preview_deletion_filters(
                {
                    "eventName": "Signup",
                    "fromDate": "2026-01-01",
                    "toDate": "2026-01-31",
                    "filters": {"country": "US"},
                }
            )

        assert len(result) == 2
        assert captured[0][0] == "POST"
        assert captured[0][1]["eventName"] == "Signup"

    def test_uses_correct_path(self, oauth_credentials: Session) -> None:
        """preview_deletion_filters() hits deletion-requests/preview-filters/."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": []},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.preview_deletion_filters(
                {"eventName": "e", "fromDate": "2026-01-01", "toDate": "2026-01-31"}
            )

        assert (
            "/data-definitions/events/deletion-requests/preview-filters/"
            in captured_urls[0]
        )
