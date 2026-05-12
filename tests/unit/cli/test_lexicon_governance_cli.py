# ruff: noqa: ARG001, ARG005
"""Tests for lexicon governance CLI commands.

Tests cover the governance-related lexicon subcommands:

Enforcement:
- enforcement get: Get schema enforcement settings
- enforcement init: Initialize schema enforcement
- enforcement update: Update schema enforcement (PATCH)
- enforcement replace: Replace schema enforcement (PUT)
- enforcement delete: Delete schema enforcement

Audit:
- audit: Run schema audit to find violations
- audit --events-only: Run event-only audit

Anomalies:
- anomalies list: List data volume anomalies
- anomalies update: Update a single anomaly
- anomalies bulk-update: Bulk-update anomalies

Deletion Requests:
- deletion-requests list: List event deletion requests
- deletion-requests create: Create an event deletion request
- deletion-requests cancel: Cancel a pending deletion request
- deletion-requests preview: Preview deletion filter results
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import typer.testing

from mixpanel_headless.cli.main import app

runner = typer.testing.CliRunner()


# =============================================================================
# Enforcement
# =============================================================================


class TestEnforcementGet:
    """Tests for mp lexicon enforcement get."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful get returns JSON dict of enforcement settings."""
        mock_ws = MagicMock()
        mock_ws.get_schema_enforcement.return_value = MagicMock(
            model_dump=lambda **kw: {
                "ruleEvent": "Warn and Accept",
                "enabled": True,
            }
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["lexicon", "enforcement", "get"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ruleEvent"] == "Warn and Accept"
        assert data["enabled"] is True

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_passes_fields_filter(self, mock_get_ws: MagicMock) -> None:
        """Passing --fields includes it in the workspace call."""
        mock_ws = MagicMock()
        mock_ws.get_schema_enforcement.return_value = MagicMock(
            model_dump=lambda **kw: {"enabled": True}
        )
        mock_get_ws.return_value = mock_ws

        runner.invoke(
            app, ["lexicon", "enforcement", "get", "--fields", "enabled,ruleEvent"]
        )
        mock_ws.get_schema_enforcement.assert_called_once_with(
            fields="enabled,ruleEvent"
        )


class TestEnforcementInit:
    """Tests for mp lexicon enforcement init."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_init_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful init returns JSON dict."""
        mock_ws = MagicMock()
        mock_ws.init_schema_enforcement.return_value = {
            "ruleEvent": "Warn and Accept",
            "initialized": True,
        }
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["lexicon", "enforcement", "init", "--rule-event", "Warn and Accept"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ruleEvent"] == "Warn and Accept"
        assert data["initialized"] is True


class TestEnforcementUpdate:
    """Tests for mp lexicon enforcement update."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_update_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful update returns JSON dict."""
        mock_ws = MagicMock()
        mock_ws.update_schema_enforcement.return_value = {
            "ruleEvent": "Reject",
            "enabled": True,
        }
        mock_get_ws.return_value = mock_ws

        body = json.dumps({"ruleEvent": "Reject"})
        result = runner.invoke(
            app,
            ["lexicon", "enforcement", "update", "--body", body],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ruleEvent"] == "Reject"

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_update_invalid_json_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --body exits with code 3 (INVALID_ARGS)."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["lexicon", "enforcement", "update", "--body", "not-json"],
        )
        assert result.exit_code == 3


class TestEnforcementReplace:
    """Tests for mp lexicon enforcement replace."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_replace_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful replace returns JSON dict."""
        mock_ws = MagicMock()
        mock_ws.replace_schema_enforcement.return_value = {
            "ruleEvent": "Block",
            "enabled": False,
        }
        mock_get_ws.return_value = mock_ws

        body = json.dumps(
            {
                "ruleEvent": "Block",
                "commonProperties": [],
                "userProperties": [],
                "events": [],
                "notificationEmails": ["admin@example.com"],
            }
        )
        result = runner.invoke(
            app,
            ["lexicon", "enforcement", "replace", "--body", body],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ruleEvent"] == "Block"
        assert data["enabled"] is False

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_replace_invalid_json_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --body exits with code 3 (INVALID_ARGS)."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["lexicon", "enforcement", "replace", "--body", "{bad"],
        )
        assert result.exit_code == 3


class TestEnforcementDelete:
    """Tests for mp lexicon enforcement delete."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_delete_confirms_and_succeeds(self, mock_get_ws: MagicMock) -> None:
        """Successful delete prompts for confirmation and exits with code 0."""
        mock_ws = MagicMock()
        mock_ws.delete_schema_enforcement.return_value = None
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["lexicon", "enforcement", "delete"], input="y\n")
        assert result.exit_code == 0
        mock_ws.delete_schema_enforcement.assert_called_once()

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_delete_aborts_on_no(self, mock_get_ws: MagicMock) -> None:
        """Delete aborts when user declines confirmation."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["lexicon", "enforcement", "delete"], input="n\n")
        assert result.exit_code != 0
        mock_ws.delete_schema_enforcement.assert_not_called()


# =============================================================================
# Audit
# =============================================================================


class TestLexiconAudit:
    """Tests for mp lexicon audit."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_audit_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful audit returns JSON with violations and computed_at."""
        mock_ws = MagicMock()
        audit_data = {
            "violations": [
                {
                    "violation": "Unexpected Event",
                    "name": "Debug",
                    "count": 5,
                },
            ],
            "computed_at": "2026-04-01T12:00:00Z",
        }
        mock_audit = MagicMock()
        mock_audit.model_dump.return_value = audit_data
        mock_ws.run_audit.return_value = mock_audit
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["lexicon", "audit"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "violations" in data
        assert "computed_at" in data
        assert len(data["violations"]) == 1
        assert data["violations"][0]["violation"] == "Unexpected Event"
        assert data["violations"][0]["name"] == "Debug"
        assert data["violations"][0]["count"] == 5
        assert data["computed_at"] == "2026-04-01T12:00:00Z"

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_audit_calls_run_audit(self, mock_get_ws: MagicMock) -> None:
        """Without --events-only, calls run_audit on the workspace."""
        mock_ws = MagicMock()
        mock_ws.run_audit.return_value = MagicMock(
            violations=[], computed_at="2026-04-01T12:00:00Z"
        )
        mock_get_ws.return_value = mock_ws

        runner.invoke(app, ["lexicon", "audit"])
        mock_ws.run_audit.assert_called_once()

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_audit_events_only(self, mock_get_ws: MagicMock) -> None:
        """With --events-only, calls run_audit_events_only."""
        mock_ws = MagicMock()
        mock_ws.run_audit_events_only.return_value = MagicMock(
            violations=[], computed_at="2026-04-01T12:00:00Z"
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["lexicon", "audit", "--events-only"])
        assert result.exit_code == 0
        mock_ws.run_audit_events_only.assert_called_once()


# =============================================================================
# Anomalies
# =============================================================================


class TestAnomaliesList:
    """Tests for mp lexicon anomalies list."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_returns_json_list(self, mock_get_ws: MagicMock) -> None:
        """Successful list returns JSON list of anomalies."""
        mock_ws = MagicMock()
        mock_ws.list_data_volume_anomalies.return_value = [
            MagicMock(
                model_dump=lambda **kw: {
                    "id": 1,
                    "status": "open",
                    "anomalyClass": "Event",
                    "name": "DebugEvent",
                }
            ),
            MagicMock(
                model_dump=lambda **kw: {
                    "id": 2,
                    "status": "dismissed",
                    "anomalyClass": "Property",
                    "name": "test_prop",
                }
            ),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["lexicon", "anomalies", "list"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["status"] == "open"

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_passes_status_filter(self, mock_get_ws: MagicMock) -> None:
        """Passing --status includes it in query_params."""
        mock_ws = MagicMock()
        mock_ws.list_data_volume_anomalies.return_value = []
        mock_get_ws.return_value = mock_ws

        runner.invoke(app, ["lexicon", "anomalies", "list", "--status", "open"])
        mock_ws.list_data_volume_anomalies.assert_called_once_with(
            query_params={"status": "open"}
        )


class TestAnomaliesUpdate:
    """Tests for mp lexicon anomalies update."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_update_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful update returns JSON dict."""
        mock_ws = MagicMock()
        mock_ws.update_anomaly.return_value = {
            "id": 123,
            "status": "dismissed",
            "anomalyClass": "Event",
        }
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "lexicon",
                "anomalies",
                "update",
                "--id",
                "123",
                "--status",
                "dismissed",
                "--anomaly-class",
                "Event",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == 123
        assert data["status"] == "dismissed"
        assert data["anomalyClass"] == "Event"


class TestAnomaliesBulkUpdate:
    """Tests for mp lexicon anomalies bulk-update."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_bulk_update_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful bulk update returns JSON dict."""
        mock_ws = MagicMock()
        mock_ws.bulk_update_anomalies.return_value = {
            "updated": 3,
            "status": "dismissed",
        }
        mock_get_ws.return_value = mock_ws

        body = json.dumps(
            {
                "anomalies": [
                    {"id": 1, "anomalyClass": "Event"},
                    {"id": 2, "anomalyClass": "Event"},
                    {"id": 3, "anomalyClass": "Property"},
                ],
                "status": "dismissed",
            }
        )
        result = runner.invoke(
            app,
            ["lexicon", "anomalies", "bulk-update", "--body", body],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["updated"] == 3

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_bulk_update_invalid_json_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --body exits with code 3 (INVALID_ARGS)."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["lexicon", "anomalies", "bulk-update", "--body", "not-json"],
        )
        assert result.exit_code == 3


# =============================================================================
# Deletion Requests
# =============================================================================


class TestDeletionRequestsList:
    """Tests for mp lexicon deletion-requests list."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_returns_json_list(self, mock_get_ws: MagicMock) -> None:
        """Successful list returns JSON list of deletion requests."""
        mock_ws = MagicMock()
        mock_ws.list_deletion_requests.return_value = [
            MagicMock(
                model_dump=lambda **kw: {
                    "id": 1,
                    "eventName": "OldEvent",
                    "status": "pending",
                    "fromDate": "2026-01-01",
                    "toDate": "2026-01-31",
                }
            ),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["lexicon", "deletion-requests", "list"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["eventName"] == "OldEvent"
        assert data[0]["status"] == "pending"


class TestDeletionRequestsCreate:
    """Tests for mp lexicon deletion-requests create."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_create_returns_json_list(self, mock_get_ws: MagicMock) -> None:
        """Successful create returns JSON list of created requests."""
        mock_ws = MagicMock()
        mock_ws.create_deletion_request.return_value = [
            MagicMock(
                model_dump=lambda **kw: {
                    "id": 42,
                    "eventName": "Test",
                    "status": "pending",
                    "fromDate": "2026-01-01",
                    "toDate": "2026-01-31",
                }
            ),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "lexicon",
                "deletion-requests",
                "create",
                "--event-name",
                "Test",
                "--from-date",
                "2026-01-01",
                "--to-date",
                "2026-01-31",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["eventName"] == "Test"
        assert data[0]["id"] == 42

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_create_with_invalid_filters_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --filters exits with code 3 (INVALID_ARGS)."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "lexicon",
                "deletion-requests",
                "create",
                "--event-name",
                "Test",
                "--from-date",
                "2026-01-01",
                "--to-date",
                "2026-01-31",
                "--filters",
                "not-json",
            ],
        )
        assert result.exit_code == 3


class TestDeletionRequestsCancel:
    """Tests for mp lexicon deletion-requests cancel."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_cancel_returns_json_list(self, mock_get_ws: MagicMock) -> None:
        """Successful cancel returns JSON list."""
        mock_ws = MagicMock()
        mock_ws.cancel_deletion_request.return_value = [
            MagicMock(
                model_dump=lambda **kw: {
                    "id": 42,
                    "eventName": "Test",
                    "status": "cancelled",
                }
            ),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["lexicon", "deletion-requests", "cancel", "42"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["status"] == "cancelled"

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_cancel_passes_id_to_workspace(self, mock_get_ws: MagicMock) -> None:
        """Request ID is passed as an integer to the workspace method."""
        mock_ws = MagicMock()
        mock_ws.cancel_deletion_request.return_value = []
        mock_get_ws.return_value = mock_ws

        runner.invoke(app, ["lexicon", "deletion-requests", "cancel", "42"])
        mock_ws.cancel_deletion_request.assert_called_once_with(request_id=42)


class TestDeletionRequestsPreview:
    """Tests for mp lexicon deletion-requests preview."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_preview_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful preview returns JSON list of matching data."""
        mock_ws = MagicMock()
        mock_ws.preview_deletion_filters.return_value = [
            {"eventName": "Test", "count": 150, "fromDate": "2026-01-01"},
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "lexicon",
                "deletion-requests",
                "preview",
                "--event-name",
                "Test",
                "--from-date",
                "2026-01-01",
                "--to-date",
                "2026-01-31",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["eventName"] == "Test"
        assert data[0]["count"] == 150

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_preview_with_invalid_filters_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --filters exits with code 3 (INVALID_ARGS)."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "lexicon",
                "deletion-requests",
                "preview",
                "--event-name",
                "Test",
                "--from-date",
                "2026-01-01",
                "--to-date",
                "2026-01-31",
                "--filters",
                "{bad",
            ],
        )
        assert result.exit_code == 3
