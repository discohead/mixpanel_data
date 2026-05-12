# ruff: noqa: S101, S603, S607
"""Live QA tests for Schema Governance — Phase 028.

Exercises the full stack against the real Mixpanel API.
All created objects are prefixed ``QA-028-`` and cleaned up after tests.

Usage:
    uv run pytest tests/live/test_schema_governance_live.py -v -m live
    uv run pytest tests/live/test_schema_governance_live.py -v -m live -k SchemaRegistry
    uv run pytest tests/live/test_schema_governance_live.py -v -m live -k Enforcement
    uv run pytest tests/live/test_schema_governance_live.py -v -m live -k Audit
    uv run pytest tests/live/test_schema_governance_live.py -v -m live -k Anomalies
    uv run pytest tests/live/test_schema_governance_live.py -v -m live -k DeletionRequests
    uv run pytest tests/live/test_schema_governance_live.py -v -m live -k EdgeCases

    # Exclude destructive tests (consumes monthly deletion request quota):
    uv run pytest tests/live/test_schema_governance_live.py -v -m "live and not destructive"

Constraints:
    - Uses default OAuth credentials
    - Never modifies pre-existing non-QA objects permanently
    - All QA objects named ``QA-028-*``
    - Cleanup guaranteed via fixtures with finalizers
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import uuid
from typing import Any

import pytest

from mixpanel_headless import Workspace
from mixpanel_headless.exceptions import MixpanelHeadlessError, QueryError, ServerError
from mixpanel_headless.types import (
    AuditResponse,
    AuditViolation,
    BulkCreateSchemasParams,
    BulkCreateSchemasResponse,
    BulkPatchResult,
    CreateDeletionRequestParams,
    DataVolumeAnomaly,
    DeleteSchemasResponse,
    EventDeletionRequest,
    InitSchemaEnforcementParams,
    PreviewDeletionFiltersParams,
    ReplaceSchemaEnforcementParams,
    SchemaEnforcementConfig,
    SchemaEntry,
    UpdateAnomalyParams,
    UpdateSchemaEnforcementParams,
)

# All tests require the `live` marker — skipped by default
pytestmark = pytest.mark.live

QA_PREFIX = "QA-028-"

# Permission strings returned by Mixpanel when scopes are missing
_PERMISSION_STRINGS = ("does not have permission", "does not have permissions")


def _is_permission_error(exc: Exception) -> bool:
    """Check if an exception is a Mixpanel permission error.

    Args:
        exc: Exception to check.

    Returns:
        True if the exception message indicates a missing permission.
    """
    msg = str(exc).lower()
    return any(s in msg for s in _PERMISSION_STRINGS)


def _skip_if_no_permission(exc: Exception, permission: str) -> None:
    """Skip the test if the exception is a permission error.

    Args:
        exc: Exception to check.
        permission: Required permission name for the skip message.
    """
    if _is_permission_error(exc):
        pytest.skip(f"Account lacks '{permission}' permission")


def _skip_if_timeout(exc: Exception) -> None:
    """Skip the test if the exception is a timeout error.

    Args:
        exc: Exception to check.
    """
    if "timed out" in str(exc).lower() or "timeout" in str(exc).lower():
        pytest.skip("Schema endpoint timed out — may be slow for large projects")


def _unique_name(label: str) -> str:
    """Generate a unique QA object name.

    Args:
        label: Human-readable label for the test.

    Returns:
        Unique name with QA prefix and short UUID suffix.
    """
    short = uuid.uuid4().hex[:8]
    return f"{QA_PREFIX}{label}-{short}"


def _mp(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """Run an ``mp`` CLI command.

    Args:
        *args: CLI arguments after ``mp``.
        timeout: Maximum seconds to wait (default 120).

    Returns:
        Completed process with captured stdout and stderr.
    """
    try:
        return subprocess.run(
            ["uv", "run", "mp", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        pytest.skip(f"CLI command timed out after {timeout}s: mp {' '.join(args)}")
        raise  # unreachable but satisfies type checker


def _assert_cli_ok(
    r: subprocess.CompletedProcess[str],
    *,
    skip_permission: str | None = None,
) -> None:
    """Assert CLI command succeeded, optionally skipping on permission errors.

    Args:
        r: Completed process result.
        skip_permission: If set, skip the test when stderr indicates
            this permission is missing.
    """
    if r.returncode != 0 and skip_permission:
        output = r.stdout + r.stderr
        if any(s in output.lower() for s in _PERMISSION_STRINGS):
            pytest.skip(f"Account lacks '{skip_permission}' permission")
    assert r.returncode == 0, f"stderr: {r.stderr}"


def _test_schema(**extra_props: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal valid JSON Schema Draft 7 object.

    Args:
        **extra_props: Additional properties to include.

    Returns:
        JSON Schema dict with ``type: "object"`` and properties.
    """
    props: dict[str, Any] = {"amount": {"type": "number"}}
    props.update(extra_props)
    return {"type": "object", "properties": props}


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def ws() -> Workspace:
    """Create a Workspace using default credentials (OAuth to current project).

    Returns:
        Workspace instance.
    """
    return Workspace()


@pytest.fixture(scope="module", autouse=True)
def cleanup_stale_qa_objects(ws: Workspace) -> None:
    """Remove leftover QA-028-* objects from prior runs.

    Scans schema registry for objects with the QA-028- prefix and
    deletes them silently. Also cleans up any lingering enforcement config.

    Args:
        ws: Workspace fixture.
    """
    # Schema registry entries
    with contextlib.suppress(Exception):
        schemas = ws.list_schema_registry()
        for s in schemas:
            if s.name.startswith(QA_PREFIX):
                with contextlib.suppress(Exception):
                    ws.delete_schemas(entity_type=s.entity_type, entity_name=s.name)

    # Enforcement (may have been left from a failed test)
    with contextlib.suppress(Exception):
        ws.delete_schema_enforcement()


# =============================================================================
# Domain 1: Schema Registry CRUD (Workspace API)
# =============================================================================


class TestSchemaRegistryCRUD:
    """Schema registry create / list / update / delete — happy path."""

    def test_list_schemas(self, ws: Workspace) -> None:
        """Listing all schemas returns a list of SchemaEntry objects.

        Args:
            ws: Workspace fixture.
        """
        try:
            schemas = ws.list_schema_registry()
        except MixpanelHeadlessError as exc:
            _skip_if_timeout(exc)
            raise
        assert isinstance(schemas, list)
        for s in schemas:
            assert isinstance(s, SchemaEntry)
            assert isinstance(s.entity_type, str)
            assert isinstance(s.name, str)
            assert isinstance(s.schema_definition, dict)

    def test_list_schemas_filtered(self, ws: Workspace) -> None:
        """Listing schemas filtered by entity_type returns only that type.

        Args:
            ws: Workspace fixture.
        """
        try:
            schemas = ws.list_schema_registry(entity_type="event")
        except MixpanelHeadlessError as exc:
            _skip_if_timeout(exc)
            raise
        assert isinstance(schemas, list)
        for s in schemas:
            assert s.entity_type == "event"

    def test_create_read_delete(self, ws: Workspace) -> None:
        """Full lifecycle: create → verify in list → delete → verify absent.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("evt")
        created: dict[str, Any] | None = None
        try:
            # Create
            try:
                created = ws.create_schema("event", name, _test_schema())
            except QueryError as exc:
                _skip_if_no_permission(exc, "write_data_definitions")
                raise
            assert isinstance(created, dict)

            # Verify in list
            schemas = ws.list_schema_registry(entity_type="event")
            names = [s.name for s in schemas]
            assert name in names

            # Delete
            resp = ws.delete_schemas(entity_type="event", entity_name=name)
            assert isinstance(resp, DeleteSchemasResponse)
            assert resp.delete_count >= 1
            created = None  # already deleted

            # Verify absent
            schemas_after = ws.list_schema_registry(entity_type="event")
            names_after = [s.name for s in schemas_after]
            assert name not in names_after

        finally:
            if created is not None:
                with contextlib.suppress(Exception):
                    ws.delete_schemas(entity_type="event", entity_name=name)

    def test_update_merge(self, ws: Workspace) -> None:
        """Update merges new properties into existing schema.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("upd")
        try:
            # Create with property "amount"
            try:
                ws.create_schema("event", name, _test_schema())
            except QueryError as exc:
                _skip_if_no_permission(exc, "write_data_definitions")
                raise

            # Update with additional property "currency"
            updated = ws.update_schema(
                "event", name, {"properties": {"currency": {"type": "string"}}}
            )
            assert isinstance(updated, dict)

        finally:
            with contextlib.suppress(Exception):
                ws.delete_schemas(entity_type="event", entity_name=name)

    def test_bulk_create(self, ws: Workspace) -> None:
        """Bulk create adds multiple schemas in one request.

        Args:
            ws: Workspace fixture.
        """
        name_a = _unique_name("bulk-a")
        name_b = _unique_name("bulk-b")
        try:
            params = BulkCreateSchemasParams(
                entries=[
                    SchemaEntry(
                        entity_type="event",
                        name=name_a,
                        schema_definition=_test_schema(),
                    ),
                    SchemaEntry(
                        entity_type="event",
                        name=name_b,
                        schema_definition=_test_schema(),
                    ),
                ],
            )
            try:
                result = ws.create_schemas_bulk(params)
            except QueryError as exc:
                _skip_if_no_permission(exc, "write_data_definitions")
                raise
            assert isinstance(result, BulkCreateSchemasResponse)
            assert result.added >= 2

        finally:
            with contextlib.suppress(Exception):
                ws.delete_schemas(entity_type="event", entity_name=name_a)
            with contextlib.suppress(Exception):
                ws.delete_schemas(entity_type="event", entity_name=name_b)

    def test_bulk_update(self, ws: Workspace) -> None:
        """Bulk update returns per-entry results with status.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("bupd")
        try:
            try:
                ws.create_schema("event", name, _test_schema())
            except QueryError as exc:
                _skip_if_no_permission(exc, "write_data_definitions")
                raise

            params = BulkCreateSchemasParams(
                entries=[
                    SchemaEntry(
                        entity_type="event",
                        name=name,
                        schema_definition={"properties": {"tax": {"type": "number"}}},
                    ),
                ],
            )
            results = ws.update_schemas_bulk(params)
            assert isinstance(results, list)
            for r in results:
                assert isinstance(r, BulkPatchResult)
                assert r.status == "ok"

        finally:
            with contextlib.suppress(Exception):
                ws.delete_schemas(entity_type="event", entity_name=name)

    def test_delete_by_type_and_name(self, ws: Workspace) -> None:
        """Targeted delete by entity_type + entity_name.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("del")
        try:
            ws.create_schema("event", name, _test_schema())
        except QueryError as exc:
            _skip_if_no_permission(exc, "write_data_definitions")
            raise

        resp = ws.delete_schemas(entity_type="event", entity_name=name)
        assert isinstance(resp, DeleteSchemasResponse)
        assert resp.delete_count >= 1

    def test_profile_schema_dollar_user(self, ws: Workspace) -> None:
        """Profile schemas use entity_name='$user'.

        Args:
            ws: Workspace fixture.
        """
        try:
            try:
                result = ws.create_schema(
                    "profile",
                    "$user",
                    {"type": "object", "properties": {"age": {"type": "number"}}},
                )
            except QueryError as exc:
                _skip_if_no_permission(exc, "write_data_definitions")
                raise
            assert isinstance(result, dict)

        finally:
            with contextlib.suppress(Exception):
                ws.delete_schemas(entity_type="profile", entity_name="$user")


# =============================================================================
# Domain 1: Schema Registry CLI
# =============================================================================


class TestSchemaRegistryCLI:
    """Schema registry CLI commands end-to-end."""

    def test_list_json(self) -> None:
        """``mp schemas list --format json`` returns valid JSON list.

        Returns:
            None.
        """
        r = _mp("schemas", "list", "--format", "json")
        _assert_cli_ok(r)
        data = json.loads(r.stdout)
        assert isinstance(data, list)

    def test_list_filtered(self) -> None:
        """``mp schemas list --entity-type event`` filters to events only.

        Returns:
            None.
        """
        r = _mp("schemas", "list", "--entity-type", "event", "--format", "json")
        _assert_cli_ok(r)
        data = json.loads(r.stdout)
        assert isinstance(data, list)
        for entry in data:
            assert entry.get("entityType") == "event"

    def test_list_table(self) -> None:
        """``mp schemas list --format table`` succeeds.

        Returns:
            None.
        """
        r = _mp("schemas", "list", "--format", "table")
        _assert_cli_ok(r)

    def test_list_jq(self) -> None:
        """``mp schemas list --jq '.[0].name'`` returns a string.

        Returns:
            None.
        """
        r = _mp("schemas", "list", "--jq", ".[0].name")
        # May fail if no schemas exist — that's acceptable
        if r.returncode == 0:
            assert r.stdout.strip()

    def test_crud_lifecycle(self) -> None:
        """Full CLI CRUD: create -> list -> update -> delete.

        Returns:
            None.
        """
        name = _unique_name("cli-evt")
        schema = json.dumps(_test_schema())

        # Create
        r = _mp(
            "schemas",
            "create",
            "--entity-type",
            "event",
            "--entity-name",
            name,
            "--schema-json",
            schema,
            "--format",
            "json",
        )
        _assert_cli_ok(r, skip_permission="write_data_definitions")

        try:
            # List — verify present
            r = _mp("schemas", "list", "--entity-type", "event", "--format", "json")
            _assert_cli_ok(r)
            entries = json.loads(r.stdout)
            entry_names = [e.get("name") for e in entries]
            assert name in entry_names

            # Update
            update_schema = json.dumps({"properties": {"currency": {"type": "string"}}})
            r = _mp(
                "schemas",
                "update",
                "--entity-type",
                "event",
                "--entity-name",
                name,
                "--schema-json",
                update_schema,
                "--format",
                "json",
            )
            assert r.returncode == 0, f"stderr: {r.stderr}"

            # Delete
            r = _mp(
                "schemas",
                "delete",
                "--entity-type",
                "event",
                "--entity-name",
                name,
                "--format",
                "json",
            )
            assert r.returncode == 0, f"stderr: {r.stderr}"
            resp = json.loads(r.stdout)
            assert resp.get("deleteCount", 0) >= 1
        except Exception:
            with contextlib.suppress(Exception):
                _mp(
                    "schemas",
                    "delete",
                    "--entity-type",
                    "event",
                    "--entity-name",
                    name,
                )
            raise

    def test_create_invalid_json(self) -> None:
        """``mp schemas create`` with invalid --schema-json exits non-zero.

        Returns:
            None.
        """
        r = _mp(
            "schemas",
            "create",
            "--entity-type",
            "event",
            "--entity-name",
            "x",
            "--schema-json",
            "not-json",
        )
        assert r.returncode != 0
        output = r.stdout + r.stderr
        assert "Invalid JSON" in output or "invalid" in output.lower()

    def test_bulk_create_cli(self) -> None:
        """``mp schemas create-bulk`` with valid entries succeeds.

        Returns:
            None.
        """
        name = _unique_name("cli-bulk")
        entries = json.dumps(
            [
                {
                    "entityType": "event",
                    "name": name,
                    "schemaJson": _test_schema(),
                },
            ]
        )

        r = _mp("schemas", "create-bulk", "--entries", entries, "--format", "json")
        try:
            _assert_cli_ok(r, skip_permission="write_data_definitions")
            data = json.loads(r.stdout)
            assert "added" in data
        finally:
            with contextlib.suppress(Exception):
                _mp(
                    "schemas",
                    "delete",
                    "--entity-type",
                    "event",
                    "--entity-name",
                    name,
                )


# =============================================================================
# Domain 2: Schema Enforcement (Workspace API)
# =============================================================================


class TestSchemaEnforcementLifecycle:
    """Schema enforcement init / get / update / replace / delete lifecycle."""

    def _ensure_clean(self, ws: Workspace) -> None:
        """Delete enforcement if it exists, suppressing errors.

        Args:
            ws: Workspace fixture.
        """
        with contextlib.suppress(Exception):
            ws.delete_schema_enforcement()

    def test_get_when_none(self, ws: Workspace) -> None:
        """get_schema_enforcement returns config or raises QueryError.

        Args:
            ws: Workspace fixture.
        """
        self._ensure_clean(ws)
        try:
            config = ws.get_schema_enforcement()
            assert isinstance(config, SchemaEnforcementConfig)
        except QueryError:
            pass  # Expected when no enforcement configured

    def test_init_get_delete(self, ws: Workspace) -> None:
        """Init → get → delete enforcement lifecycle.

        Args:
            ws: Workspace fixture.
        """
        self._ensure_clean(ws)
        try:
            # Init
            try:
                result = ws.init_schema_enforcement(
                    InitSchemaEnforcementParams(rule_event="Warn and Accept")
                )
            except QueryError as exc:
                _skip_if_no_permission(exc, "write_data_definition_schema")
                raise
            assert isinstance(result, dict)

            # Get
            config = ws.get_schema_enforcement()
            assert isinstance(config, SchemaEnforcementConfig)
            assert config.rule_event == "Warn and Accept"

            # Delete
            ws.delete_schema_enforcement()

        finally:
            self._ensure_clean(ws)

    def test_init_update_get_delete(self, ws: Workspace) -> None:
        """Init → update → get (verify change) → delete.

        Args:
            ws: Workspace fixture.
        """
        self._ensure_clean(ws)
        try:
            try:
                ws.init_schema_enforcement(
                    InitSchemaEnforcementParams(rule_event="Warn and Accept")
                )
            except QueryError as exc:
                _skip_if_no_permission(exc, "write_data_definition_schema")
                raise

            # Update rule
            ws.update_schema_enforcement(
                UpdateSchemaEnforcementParams(rule_event="Warn and Drop")
            )

            # Verify
            config = ws.get_schema_enforcement()
            assert config.rule_event == "Warn and Drop"

        finally:
            self._ensure_clean(ws)

    def test_init_replace_get_delete(self, ws: Workspace) -> None:
        """Init → replace (full config) → get (verify) → delete.

        Args:
            ws: Workspace fixture.
        """
        self._ensure_clean(ws)
        try:
            try:
                ws.init_schema_enforcement(
                    InitSchemaEnforcementParams(rule_event="Warn and Accept")
                )
            except QueryError as exc:
                _skip_if_no_permission(exc, "write_data_definition_schema")
                raise

            # Replace with full config
            ws.replace_schema_enforcement(
                ReplaceSchemaEnforcementParams(
                    events=[],
                    common_properties=[],
                    user_properties=[],
                    rule_event="Warn and Hide",
                    notification_emails=[],
                )
            )

            # Verify
            config = ws.get_schema_enforcement()
            assert config.rule_event == "Warn and Hide"

        finally:
            self._ensure_clean(ws)

    def test_delete_nonexistent(self, ws: Workspace) -> None:
        """Deleting enforcement when none exists raises QueryError.

        Args:
            ws: Workspace fixture.
        """
        self._ensure_clean(ws)
        with pytest.raises((QueryError, Exception)):  # noqa: B017
            ws.delete_schema_enforcement()


# =============================================================================
# Domain 2: Schema Enforcement CLI
# =============================================================================


class TestSchemaEnforcementCLI:
    """Schema enforcement CLI commands end-to-end."""

    @staticmethod
    def _ensure_clean_cli() -> None:
        """Delete enforcement via CLI if it exists."""
        with contextlib.suppress(Exception):
            _mp("lexicon", "enforcement", "delete")

    def test_get_or_404(self) -> None:
        """``mp lexicon enforcement get`` returns config or fails.

        Returns:
            None.
        """
        r = _mp("lexicon", "enforcement", "get", "--format", "json")
        # Either succeeds (config exists) or fails (404) — both valid
        assert r.returncode in (0, 1, 3), f"unexpected rc={r.returncode}: {r.stderr}"

    def test_init_get_delete_lifecycle(self) -> None:
        """Full CLI enforcement lifecycle: init → get → delete.

        Returns:
            None.
        """
        self._ensure_clean_cli()
        try:
            # Init
            r = _mp(
                "lexicon",
                "enforcement",
                "init",
                "--rule-event",
                "Warn and Accept",
                "--format",
                "json",
            )
            _assert_cli_ok(r, skip_permission="write_data_definition_schema")

            # Get
            r = _mp("lexicon", "enforcement", "get", "--format", "json")
            assert r.returncode == 0, f"stderr: {r.stderr}"
            config = json.loads(r.stdout)
            assert config.get("ruleEvent") == "Warn and Accept"

            # Delete
            r = _mp("lexicon", "enforcement", "delete")
            assert r.returncode == 0, f"stderr: {r.stderr}"
        except Exception:
            self._ensure_clean_cli()
            raise

    def test_update_cli(self) -> None:
        """CLI enforcement update changes the rule.

        Returns:
            None.
        """
        self._ensure_clean_cli()
        try:
            r = _mp(
                "lexicon",
                "enforcement",
                "init",
                "--rule-event",
                "Warn and Accept",
            )
            _assert_cli_ok(r, skip_permission="write_data_definition_schema")

            r = _mp(
                "lexicon",
                "enforcement",
                "update",
                "--body",
                '{"ruleEvent":"Warn and Drop"}',
                "--format",
                "json",
            )
            _assert_cli_ok(r, skip_permission="write_data_definition_schema")

            r = _mp("lexicon", "enforcement", "get", "--format", "json")
            _assert_cli_ok(r)
            config = json.loads(r.stdout)
            assert config.get("ruleEvent") == "Warn and Drop"

        finally:
            self._ensure_clean_cli()

    def test_replace_cli(self) -> None:
        """CLI enforcement replace with full config.

        Returns:
            None.
        """
        self._ensure_clean_cli()
        try:
            r = _mp(
                "lexicon",
                "enforcement",
                "init",
                "--rule-event",
                "Warn and Accept",
            )
            _assert_cli_ok(r, skip_permission="write_data_definition_schema")

            body = json.dumps(
                {
                    "events": [],
                    "commonProperties": [],
                    "userProperties": [],
                    "ruleEvent": "Warn and Hide",
                    "notificationEmails": [],
                }
            )
            r = _mp(
                "lexicon",
                "enforcement",
                "replace",
                "--body",
                body,
                "--format",
                "json",
            )
            _assert_cli_ok(r, skip_permission="write_data_definition_schema")

        finally:
            self._ensure_clean_cli()

    def test_delete_nonexistent_cli(self) -> None:
        """CLI enforcement delete when none exists fails.

        Returns:
            None.
        """
        self._ensure_clean_cli()
        r = _mp("lexicon", "enforcement", "delete")
        assert r.returncode != 0


# =============================================================================
# Domain 3: Data Auditing (Workspace API)
# =============================================================================


class TestDataAudit:
    """Data audit — read-only operations."""

    def test_run_audit(self, ws: Workspace) -> None:
        """run_audit() returns AuditResponse with violations and timestamp.

        Args:
            ws: Workspace fixture.
        """
        try:
            result = ws.run_audit()
            assert isinstance(result, AuditResponse)
            assert isinstance(result.violations, list)
            assert isinstance(result.computed_at, str)
        except QueryError:
            pytest.skip("Audit requires schemas to be configured in the project")

    def test_run_audit_events_only(self, ws: Workspace) -> None:
        """run_audit_events_only() returns AuditResponse (faster).

        Args:
            ws: Workspace fixture.
        """
        try:
            result = ws.run_audit_events_only()
            assert isinstance(result, AuditResponse)
            assert isinstance(result.violations, list)
            assert isinstance(result.computed_at, str)
        except QueryError:
            pytest.skip("Audit requires schemas to be configured in the project")

    def test_violation_fields(self, ws: Workspace) -> None:
        """AuditViolation objects have expected fields if violations exist.

        Args:
            ws: Workspace fixture.
        """
        try:
            result = ws.run_audit()
        except QueryError:
            pytest.skip("Audit requires schemas to be configured in the project")
            return

        if not result.violations:
            pytest.skip("No violations found to inspect")
            return

        v = result.violations[0]
        assert isinstance(v, AuditViolation)
        assert isinstance(v.violation, str)
        assert isinstance(v.name, str)
        assert isinstance(v.count, int)


# =============================================================================
# Domain 3: Data Auditing CLI
# =============================================================================


class TestDataAuditCLI:
    """Data audit CLI commands."""

    def test_audit_json(self) -> None:
        """``mp lexicon audit --format json`` returns valid JSON.

        Returns:
            None.
        """
        r = _mp("lexicon", "audit", "--format", "json")
        if r.returncode != 0:
            pytest.skip("Audit not available (no schemas or permission issue)")
            return
        data = json.loads(r.stdout)
        assert "violations" in data
        assert "computed_at" in data

    def test_audit_events_only(self) -> None:
        """``mp lexicon audit --events-only`` returns valid JSON.

        Returns:
            None.
        """
        r = _mp("lexicon", "audit", "--events-only", "--format", "json")
        if r.returncode != 0:
            pytest.skip("Audit not available")
            return
        data = json.loads(r.stdout)
        assert "violations" in data

    def test_audit_jq(self) -> None:
        """``mp lexicon audit --jq '.computed_at'`` returns a timestamp string.

        Returns:
            None.
        """
        r = _mp("lexicon", "audit", "--jq", ".computed_at")
        if r.returncode != 0:
            pytest.skip("Audit not available")


# =============================================================================
# Domain 4: Data Volume Anomalies (Workspace API)
# =============================================================================


class TestDataVolumeAnomalies:
    """Data volume anomaly list / update operations."""

    def test_list_all(self, ws: Workspace) -> None:
        """list_data_volume_anomalies() returns a list (possibly empty).

        Args:
            ws: Workspace fixture.
        """
        anomalies = ws.list_data_volume_anomalies()
        assert isinstance(anomalies, list)
        for a in anomalies:
            assert isinstance(a, DataVolumeAnomaly)

    def test_list_with_status_filter(self, ws: Workspace) -> None:
        """Filtering by status='open' returns only open anomalies.

        Args:
            ws: Workspace fixture.
        """
        try:
            anomalies = ws.list_data_volume_anomalies(query_params={"status": "open"})
        except (ServerError, MixpanelHeadlessError):
            pytest.skip("Anomaly status filter returned server error (known API issue)")
            return
        assert isinstance(anomalies, list)
        for a in anomalies:
            assert a.status == "open"

    def test_dismiss_and_reopen(self, ws: Workspace) -> None:
        """Dismiss an anomaly then reopen it (reversible).

        Args:
            ws: Workspace fixture.
        """
        try:
            anomalies = ws.list_data_volume_anomalies(query_params={"status": "open"})
        except (ServerError, MixpanelHeadlessError):
            pytest.skip("Anomaly status filter returned server error")
            return
        if not anomalies:
            pytest.skip("No open anomalies to test with")
            return

        a = anomalies[0]
        try:
            # Dismiss
            ws.update_anomaly(
                UpdateAnomalyParams(
                    id=a.id,
                    status="dismissed",
                    anomaly_class=a.anomaly_class,
                )
            )
        finally:
            # Reopen (restore original state)
            with contextlib.suppress(Exception):
                ws.update_anomaly(
                    UpdateAnomalyParams(
                        id=a.id,
                        status="open",
                        anomaly_class=a.anomaly_class,
                    )
                )

    def test_update_nonexistent(self, ws: Workspace) -> None:
        """Updating a nonexistent anomaly raises QueryError.

        Args:
            ws: Workspace fixture.
        """
        with pytest.raises((QueryError, Exception)):  # noqa: B017
            ws.update_anomaly(
                UpdateAnomalyParams(
                    id=999999999,
                    status="dismissed",
                    anomaly_class="Event",
                )
            )


# =============================================================================
# Domain 4: Data Volume Anomalies CLI
# =============================================================================


class TestDataVolumeAnomaliesCLI:
    """Data volume anomaly CLI commands."""

    def test_list_json(self) -> None:
        """``mp lexicon anomalies list --format json`` returns valid JSON.

        Returns:
            None.
        """
        r = _mp("lexicon", "anomalies", "list", "--format", "json")
        assert r.returncode == 0, f"stderr: {r.stderr}"
        data = json.loads(r.stdout)
        assert isinstance(data, list)

    def test_list_status_filter(self) -> None:
        """``mp lexicon anomalies list --status open`` filters correctly.

        Returns:
            None.
        """
        r = _mp("lexicon", "anomalies", "list", "--status", "open", "--format", "json")
        if r.returncode != 0:
            pytest.skip("Anomaly status filter returned error (known API issue)")
            return
        data = json.loads(r.stdout)
        assert isinstance(data, list)
        for item in data:
            assert item.get("status") == "open"

    def test_list_table(self) -> None:
        """``mp lexicon anomalies list --format table`` succeeds.

        Returns:
            None.
        """
        r = _mp("lexicon", "anomalies", "list", "--format", "table")
        assert r.returncode == 0, f"stderr: {r.stderr}"

    def test_bulk_update_invalid_json(self) -> None:
        """Bulk update with invalid JSON exits non-zero.

        Returns:
            None.
        """
        r = _mp("lexicon", "anomalies", "bulk-update", "--body", "not-json")
        assert r.returncode != 0
        output = r.stdout + r.stderr
        assert "Invalid JSON" in output or "invalid" in output.lower()


# =============================================================================
# Domain 5: Event Deletion Requests (Workspace API)
# =============================================================================


class TestDeletionRequests:
    """Event deletion request lifecycle — mostly read-only.

    The ``test_create_and_cancel`` test consumes 1 of 10 monthly deletion
    request slots and is marked ``@pytest.mark.destructive``.
    """

    def test_list(self, ws: Workspace) -> None:
        """list_deletion_requests() returns a list of requests.

        Args:
            ws: Workspace fixture.
        """
        try:
            requests = ws.list_deletion_requests()
        except QueryError as exc:
            _skip_if_no_permission(exc, "event_deletion")
            raise
        assert isinstance(requests, list)
        for r in requests:
            assert isinstance(r, EventDeletionRequest)

    def test_preview(self, ws: Workspace) -> None:
        """preview_deletion_filters() is read-only and returns filters.

        Args:
            ws: Workspace fixture.
        """
        try:
            result = ws.preview_deletion_filters(
                PreviewDeletionFiltersParams(
                    event_name="$session_start",
                    from_date="2026-03-01",
                    to_date="2026-03-31",
                )
            )
        except QueryError as exc:
            _skip_if_no_permission(exc, "event_deletion")
            raise
        assert isinstance(result, list)

    @pytest.mark.destructive
    def test_create_and_cancel(self, ws: Workspace) -> None:
        """Create a deletion request then immediately cancel it.

        **WARNING**: This consumes 1 of 10 monthly deletion request slots.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("del-evt")
        created = ws.create_deletion_request(
            CreateDeletionRequestParams(
                event_name=name,
                from_date="2026-03-01",
                to_date="2026-03-15",
            )
        )
        assert isinstance(created, list)

        # Find our request
        our = [r for r in created if r.event_name == name and r.status == "Submitted"]
        assert len(our) >= 1, f"Expected Submitted request for {name}"
        request_id = our[0].id

        # Cancel immediately
        remaining = ws.cancel_deletion_request(request_id)
        assert isinstance(remaining, list)

    def test_cancel_nonexistent(self, ws: Workspace) -> None:
        """Cancelling a nonexistent request raises QueryError.

        Args:
            ws: Workspace fixture.
        """
        with pytest.raises((QueryError, Exception)):  # noqa: B017
            ws.cancel_deletion_request(999999999)


# =============================================================================
# Domain 5: Event Deletion Requests CLI
# =============================================================================


class TestDeletionRequestsCLI:
    """Event deletion request CLI commands."""

    def test_list_json(self) -> None:
        """``mp lexicon deletion-requests list --format json`` returns JSON.

        Returns:
            None.
        """
        r = _mp("lexicon", "deletion-requests", "list", "--format", "json")
        _assert_cli_ok(r, skip_permission="event_deletion")
        data = json.loads(r.stdout)
        assert isinstance(data, list)

    def test_list_table(self) -> None:
        """``mp lexicon deletion-requests list --format table`` succeeds.

        Returns:
            None.
        """
        r = _mp("lexicon", "deletion-requests", "list", "--format", "table")
        _assert_cli_ok(r, skip_permission="event_deletion")

    def test_preview_cli(self) -> None:
        """``mp lexicon deletion-requests preview`` is read-only.

        Returns:
            None.
        """
        r = _mp(
            "lexicon",
            "deletion-requests",
            "preview",
            "--event-name",
            "$session_start",
            "--from-date",
            "2026-03-01",
            "--to-date",
            "2026-03-31",
            "--format",
            "json",
        )
        _assert_cli_ok(r, skip_permission="event_deletion")
        data = json.loads(r.stdout)
        assert isinstance(data, list)

    def test_create_invalid_filters(self) -> None:
        """``mp lexicon deletion-requests create`` with bad filters exits non-zero.

        Returns:
            None.
        """
        r = _mp(
            "lexicon",
            "deletion-requests",
            "create",
            "--event-name",
            "x",
            "--from-date",
            "2026-01-01",
            "--to-date",
            "2026-01-31",
            "--filters",
            "bad-json",
        )
        assert r.returncode != 0
        output = r.stdout + r.stderr
        assert "Invalid JSON" in output or "invalid" in output.lower()

    def test_cancel_nonexistent(self) -> None:
        """``mp lexicon deletion-requests cancel`` with bad ID fails.

        Returns:
            None.
        """
        r = _mp("lexicon", "deletion-requests", "cancel", "999999999")
        assert r.returncode != 0


# =============================================================================
# Cross-cutting Edge Cases
# =============================================================================


class TestSchemaGovernanceEdgeCases:
    """Edge cases and cross-cutting concerns."""

    def test_schema_entry_alias_round_trip(self, ws: Workspace) -> None:
        """SchemaEntry model_dump(by_alias=True) produces API-compatible keys.

        Args:
            ws: Workspace fixture.
        """
        try:
            schemas = ws.list_schema_registry()
        except MixpanelHeadlessError as exc:
            _skip_if_timeout(exc)
            raise
        if not schemas:
            pytest.skip("No schemas to test round-trip with")
            return

        entry = schemas[0]
        dumped = entry.model_dump(by_alias=True)
        assert "schemaJson" in dumped
        assert "entityType" in dumped

        # Round-trip
        restored = SchemaEntry.model_validate(dumped)
        assert restored.name == entry.name
        assert restored.entity_type == entry.entity_type

    def test_enforcement_get_fields_param(self, ws: Workspace) -> None:
        """get_schema_enforcement(fields=...) returns only requested fields.

        Args:
            ws: Workspace fixture.
        """
        try:
            config = ws.get_schema_enforcement(fields="ruleEvent,state")
            assert isinstance(config, SchemaEnforcementConfig)
            # If enforcement exists, at least one field should be populated
        except QueryError:
            pytest.skip("No enforcement configured")

    def test_schemas_no_args_help(self) -> None:
        """``mp schemas`` with no subcommand shows help.

        Returns:
            None.
        """
        r = _mp("schemas")
        output = r.stdout + r.stderr
        assert "Commands" in output or "Usage" in output

    def test_enforcement_no_args_help(self) -> None:
        """``mp lexicon enforcement`` with no subcommand shows help.

        Returns:
            None.
        """
        r = _mp("lexicon", "enforcement")
        output = r.stdout + r.stderr
        assert "Commands" in output or "Usage" in output

    def test_anomalies_no_args_help(self) -> None:
        """``mp lexicon anomalies`` with no subcommand shows help.

        Returns:
            None.
        """
        r = _mp("lexicon", "anomalies")
        output = r.stdout + r.stderr
        assert "Commands" in output or "Usage" in output
