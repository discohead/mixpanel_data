"""Unit tests for Workspace governance methods (Phase 028).

Tests for schema enforcement, data auditing, data volume anomalies,
and event deletion request operations on the Workspace facade.
Each method delegates to MixpanelAPIClient and returns typed objects.

Verifies:
- Schema Enforcement: get, init, update, replace, delete
- Data Auditing: run_audit, run_audit_events_only
- Data Volume Anomalies: list, update, bulk_update
- Event Deletion Requests: list, create, cancel, preview_filters
"""

# ruff: noqa: ARG001, ARG005

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from pydantic import SecretStr

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.types import (
    AuditResponse,
    AuditViolation,
    BulkAnomalyEntry,
    BulkUpdateAnomalyParams,
    CreateDeletionRequestParams,
    DataVolumeAnomaly,
    EventDeletionRequest,
    InitSchemaEnforcementParams,
    PreviewDeletionFiltersParams,
    ReplaceSchemaEnforcementParams,
    SchemaEnforcementConfig,
    UpdateAnomalyParams,
    UpdateSchemaEnforcementParams,
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


def _enforcement_json() -> dict[str, Any]:
    """Return a minimal enforcement config dict matching the API shape.

    Returns:
        Dict that can be parsed into a SchemaEnforcementConfig model.
    """
    return {
        "id": 1,
        "ruleEvent": "Warn and Accept",
        "state": "ingested",
        "notificationEmails": ["admin@example.com"],
        "events": [],
        "commonProperties": [],
        "userProperties": [],
    }


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


# =============================================================================
# Schema Enforcement
# =============================================================================


class TestGetSchemaEnforcement:
    """Tests for Workspace.get_schema_enforcement() method."""

    def test_returns_typed_config(self, temp_dir: Path) -> None:
        """get_schema_enforcement() returns a SchemaEnforcementConfig."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return enforcement config."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": _enforcement_json()},
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_schema_enforcement()

        assert isinstance(result, SchemaEnforcementConfig)
        assert result.rule_event == "Warn and Accept"
        assert result.state == "ingested"
        assert result.id == 1

    def test_with_fields(self, temp_dir: Path) -> None:
        """get_schema_enforcement(fields=...) returns partial config."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return partial enforcement config."""
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

        ws = _make_workspace(temp_dir, handler)
        result = ws.get_schema_enforcement(fields="ruleEvent,state")

        assert isinstance(result, SchemaEnforcementConfig)
        assert result.rule_event == "Warn and Accept"


class TestInitSchemaEnforcement:
    """Tests for Workspace.init_schema_enforcement() method."""

    def test_returns_dict(self, temp_dir: Path) -> None:
        """init_schema_enforcement() returns a dict response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return init response."""
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

        ws = _make_workspace(temp_dir, handler)
        params = InitSchemaEnforcementParams(rule_event="Warn and Drop")
        result = ws.init_schema_enforcement(params)

        assert isinstance(result, dict)
        assert result["ruleEvent"] == "Warn and Drop"


class TestUpdateSchemaEnforcement:
    """Tests for Workspace.update_schema_enforcement() method."""

    def test_returns_dict(self, temp_dir: Path) -> None:
        """update_schema_enforcement() returns a dict response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return update response."""
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

        ws = _make_workspace(temp_dir, handler)
        params = UpdateSchemaEnforcementParams(
            rule_event="Warn and Hide",
            notification_emails=["new@example.com"],
        )
        result = ws.update_schema_enforcement(params)

        assert isinstance(result, dict)
        assert result["ruleEvent"] == "Warn and Hide"


class TestReplaceSchemaEnforcement:
    """Tests for Workspace.replace_schema_enforcement() method."""

    def test_returns_dict(self, temp_dir: Path) -> None:
        """replace_schema_enforcement() returns a dict response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return replace response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "ruleEvent": "Warn and Drop",
                        "notificationEmails": ["admin@example.com"],
                        "events": [{"name": "Signup"}],
                        "commonProperties": [{"name": "utm_source"}],
                        "userProperties": [{"name": "$email"}],
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = ReplaceSchemaEnforcementParams(
            rule_event="Warn and Drop",
            notification_emails=["admin@example.com"],
            events=[{"name": "Signup"}],
            common_properties=[{"name": "utm_source"}],
            user_properties=[{"name": "$email"}],
        )
        result = ws.replace_schema_enforcement(params)

        assert isinstance(result, dict)
        assert result["ruleEvent"] == "Warn and Drop"


class TestDeleteSchemaEnforcement:
    """Tests for Workspace.delete_schema_enforcement() method."""

    def test_returns_dict(self, temp_dir: Path) -> None:
        """delete_schema_enforcement() returns a dict response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return delete response."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"deleted": True}},
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.delete_schema_enforcement()

        assert isinstance(result, dict)
        assert result["deleted"] is True


# =============================================================================
# Data Auditing
# =============================================================================


class TestRunAudit:
    """Tests for Workspace.run_audit() method."""

    def test_returns_audit_response(self, temp_dir: Path) -> None:
        """run_audit() returns an AuditResponse with parsed violations."""

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

        ws = _make_workspace(temp_dir, handler)
        result = ws.run_audit()

        assert isinstance(result, AuditResponse)
        assert len(result.violations) == 2
        assert isinstance(result.violations[0], AuditViolation)
        assert result.violations[0].violation == "Unexpected Event"
        assert result.violations[0].name == "bad_event"
        assert result.violations[0].count == 42
        assert result.violations[1].violation == "Missing Property"
        assert result.violations[1].event == "Signup"
        assert result.computed_at == "2026-01-01T00:00:00Z"

    def test_empty_violations(self, temp_dir: Path) -> None:
        """run_audit() handles empty violations list."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return audit with no violations."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [[], {"computed_at": "2026-01-01T12:00:00Z"}],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.run_audit()

        assert isinstance(result, AuditResponse)
        assert result.violations == []
        assert result.computed_at == "2026-01-01T12:00:00Z"

    def test_empty_response_returns_empty_audit(self, temp_dir: Path) -> None:
        """run_audit() returns empty AuditResponse when API returns empty list.

        Args:
            temp_dir: Pytest tmp_path fixture.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty results list."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": []},
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.run_audit()

        assert isinstance(result, AuditResponse)
        assert result.violations == []
        assert result.computed_at == ""


class TestRunAuditEventsOnly:
    """Tests for Workspace.run_audit_events_only() method."""

    def test_returns_audit_response(self, temp_dir: Path) -> None:
        """run_audit_events_only() returns an AuditResponse."""

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

        ws = _make_workspace(temp_dir, handler)
        result = ws.run_audit_events_only()

        assert isinstance(result, AuditResponse)
        assert len(result.violations) == 1
        assert result.violations[0].violation == "Unexpected Event"
        assert result.violations[0].name == "rogue_event"
        assert result.computed_at == "2026-01-02T00:00:00Z"

    def test_empty_response_returns_empty_audit(self, temp_dir: Path) -> None:
        """run_audit_events_only() returns empty AuditResponse when empty.

        Args:
            temp_dir: Pytest tmp_path fixture.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty results list."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": []},
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.run_audit_events_only()

        assert isinstance(result, AuditResponse)
        assert result.violations == []
        assert result.computed_at == ""


# =============================================================================
# Data Volume Anomalies
# =============================================================================


class TestListDataVolumeAnomalies:
    """Tests for Workspace.list_data_volume_anomalies() method."""

    def test_returns_typed_list(self, temp_dir: Path) -> None:
        """list_data_volume_anomalies() returns list of DataVolumeAnomaly."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return anomaly list."""
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

        ws = _make_workspace(temp_dir, handler)
        result = ws.list_data_volume_anomalies()

        assert len(result) == 2
        assert isinstance(result[0], DataVolumeAnomaly)
        assert result[0].id == 1
        assert result[0].event_name == "Signup"
        assert result[0].status == "open"
        assert result[0].anomaly_class == "Event"
        assert isinstance(result[1], DataVolumeAnomaly)
        assert result[1].id == 2
        assert result[1].event_name == "Login"

    def test_empty_list(self, temp_dir: Path) -> None:
        """list_data_volume_anomalies() returns empty list when none exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty anomaly list."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"anomalies": []}},
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.list_data_volume_anomalies()

        assert result == []

    def test_with_query_params(self, temp_dir: Path) -> None:
        """list_data_volume_anomalies(query_params=...) passes filters."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return anomalies."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"anomalies": [_anomaly_json(1)]},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.list_data_volume_anomalies(query_params={"status": "open"})

        assert len(result) == 1
        assert "status=open" in captured_urls[0]


class TestUpdateAnomaly:
    """Tests for Workspace.update_anomaly() method."""

    def test_returns_dict(self, temp_dir: Path) -> None:
        """update_anomaly() returns a dict response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return update response."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"updated": True}},
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateAnomalyParams(id=123, status="dismissed", anomaly_class="Event")
        result = ws.update_anomaly(params)

        assert isinstance(result, dict)
        assert result["updated"] is True


class TestBulkUpdateAnomalies:
    """Tests for Workspace.bulk_update_anomalies() method."""

    def test_returns_dict(self, temp_dir: Path) -> None:
        """bulk_update_anomalies() returns a dict response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bulk update response."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"updated": 2}},
            )

        ws = _make_workspace(temp_dir, handler)
        params = BulkUpdateAnomalyParams(
            anomalies=[
                BulkAnomalyEntry(id=1, anomaly_class="Event"),
                BulkAnomalyEntry(id=2, anomaly_class="Property"),
            ],
            status="dismissed",
        )
        result = ws.bulk_update_anomalies(params)

        assert isinstance(result, dict)
        assert result["updated"] == 2


# =============================================================================
# Event Deletion Requests
# =============================================================================


class TestListDeletionRequests:
    """Tests for Workspace.list_deletion_requests() method."""

    def test_returns_typed_list(self, temp_dir: Path) -> None:
        """list_deletion_requests() returns list of EventDeletionRequest."""

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

        ws = _make_workspace(temp_dir, handler)
        result = ws.list_deletion_requests()

        assert len(result) == 2
        assert isinstance(result[0], EventDeletionRequest)
        assert result[0].id == 1
        assert result[0].event_name == "event_a"
        assert result[0].status == "Submitted"
        assert isinstance(result[1], EventDeletionRequest)
        assert result[1].id == 2

    def test_empty_list(self, temp_dir: Path) -> None:
        """list_deletion_requests() returns empty list when none exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty list."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": []},
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.list_deletion_requests()

        assert result == []


class TestCreateDeletionRequest:
    """Tests for Workspace.create_deletion_request() method."""

    def test_returns_typed_list(self, temp_dir: Path) -> None:
        """create_deletion_request() returns updated list of EventDeletionRequest."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated deletion requests list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _deletion_request_json(1, "existing"),
                        _deletion_request_json(2, "new_event"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateDeletionRequestParams(
            event_name="new_event",
            from_date="2026-01-01",
            to_date="2026-01-31",
        )
        result = ws.create_deletion_request(params)

        assert len(result) == 2
        assert isinstance(result[0], EventDeletionRequest)
        assert isinstance(result[1], EventDeletionRequest)
        assert result[1].event_name == "new_event"


class TestCancelDeletionRequest:
    """Tests for Workspace.cancel_deletion_request() method."""

    def test_returns_typed_list(self, temp_dir: Path) -> None:
        """cancel_deletion_request() returns updated list of EventDeletionRequest."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated list after cancellation."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [_deletion_request_json(1, "remaining")],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.cancel_deletion_request(request_id=42)

        assert len(result) == 1
        assert isinstance(result[0], EventDeletionRequest)
        assert result[0].event_name == "remaining"


class TestPreviewDeletionFilters:
    """Tests for Workspace.preview_deletion_filters() method."""

    def test_returns_list_of_dicts(self, temp_dir: Path) -> None:
        """preview_deletion_filters() returns list of filter dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return preview filters response."""
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

        ws = _make_workspace(temp_dir, handler)
        params = PreviewDeletionFiltersParams(
            event_name="Signup",
            from_date="2026-01-01",
            to_date="2026-01-31",
        )
        result = ws.preview_deletion_filters(params)

        assert len(result) == 2
        assert isinstance(result, list)
        assert result[0]["property"] == "country"
        assert result[1]["property"] == "platform"

    def test_empty_filters(self, temp_dir: Path) -> None:
        """preview_deletion_filters() returns empty list when no filters match."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty filters list."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": []},
            )

        ws = _make_workspace(temp_dir, handler)
        params = PreviewDeletionFiltersParams(
            event_name="NoMatch",
            from_date="2026-01-01",
            to_date="2026-01-31",
        )
        result = ws.preview_deletion_filters(params)

        assert result == []
