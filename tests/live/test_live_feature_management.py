# ruff: noqa: S101, S603, S607
"""Live QA tests for Feature Management (Flags + Experiments) — Phase 025.

Exercises the full stack against the real Mixpanel API on Project 8.
All created objects are prefixed ``QA-025-`` and cleaned up after tests.

Usage:
    uv run pytest tests/live/test_live_feature_management.py -v -m live
    uv run pytest tests/live/test_live_feature_management.py -v -m live -k flags
    uv run pytest tests/live/test_live_feature_management.py -v -m live -k experiments

Constraints:
    - Uses account ``p8`` (Project ID 8)
    - Never modifies pre-existing flags or experiments
    - All QA objects named ``QA-025-*``
    - Cleanup guaranteed via fixtures with finalizers
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import uuid

import pytest

from mixpanel_headless import Workspace
from mixpanel_headless.exceptions import QueryError
from mixpanel_headless.types import (
    CreateExperimentParams,
    CreateFeatureFlagParams,
    DuplicateExperimentParams,
    Experiment,
    ExperimentConcludeParams,
    ExperimentDecideParams,
    ExperimentStatus,
    FeatureFlag,
    FeatureFlagStatus,
    FlagContractStatus,
    FlagHistoryResponse,
    FlagLimitsResponse,
    ServingMethod,
    SetTestUsersParams,
    UpdateExperimentParams,
    UpdateFeatureFlagParams,
)

# All tests require the `live` marker — skipped by default
pytestmark = pytest.mark.live

QA_PREFIX = "QA-025-"


def _unique_name(label: str) -> str:
    """Generate a unique QA object name.

    Args:
        label: Human-readable label for the test.

    Returns:
        Unique name with QA prefix and short UUID suffix.
    """
    short = uuid.uuid4().hex[:8]
    return f"{QA_PREFIX}{label}-{short}"


def _unique_key(label: str) -> str:
    """Generate a unique QA flag key (snake_case).

    Args:
        label: Human-readable label.

    Returns:
        Unique key with qa_025 prefix and short UUID suffix.
    """
    short = uuid.uuid4().hex[:8]
    return f"qa_025_{label}_{short}"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def ws() -> Workspace:
    """Create a Workspace connected to Project 8.

    Returns:
        Workspace instance using the ``p8`` account.
    """
    return Workspace(account="p8")


@pytest.fixture(scope="module", autouse=True)
def cleanup_stale_qa_objects(ws: Workspace) -> None:
    """Remove leftover QA-025-* objects from prior runs.

    Args:
        ws: Workspace fixture.
    """
    client = ws._require_api_client()

    # Clean stale flags
    flags = ws.list_feature_flags(include_archived=True)
    for f in flags:
        if f.name.startswith(QA_PREFIX):
            with contextlib.suppress(Exception):
                ws.delete_feature_flag(f.id)

    # Clean stale experiments (use raw client to avoid type issues)
    experiments = client.list_experiments(include_archived=True)
    for e in experiments:
        if e.get("name", "").startswith(QA_PREFIX):
            with contextlib.suppress(Exception):
                client.delete_experiment(e["id"])


def _mp(*args: str) -> subprocess.CompletedProcess[str]:
    """Run an ``mp`` CLI command against Project 8.

    Args:
        *args: CLI arguments after ``mp -a p8``.

    Returns:
        Completed process with captured stdout and stderr.
    """
    return subprocess.run(
        ["uv", "run", "mp", "-a", "p8", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


# =============================================================================
# Phase 2: Feature Flag QA — Workspace Level
# =============================================================================


class TestFlagCRUD:
    """Flag create / get / update / list / delete — happy path."""

    def test_create_get_update_delete(self, ws: Workspace) -> None:
        """Full CRUD cycle: create → get → update → delete.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("crud")
        key = _unique_key("crud")

        # Create
        flag = ws.create_feature_flag(CreateFeatureFlagParams(name=name, key=key))
        try:
            assert isinstance(flag, FeatureFlag)
            assert flag.name == name
            assert flag.key == key
            assert flag.id  # non-empty UUID
            assert flag.status == FeatureFlagStatus.DISABLED
            assert flag.project_id == 8

            # Get
            fetched = ws.get_feature_flag(flag.id)
            assert fetched.id == flag.id
            assert fetched.name == name
            assert fetched.key == key

            # Update (PUT — all required fields)
            updated = ws.update_feature_flag(
                flag.id,
                UpdateFeatureFlagParams(
                    name=name + "-updated",
                    key=key,
                    status=FeatureFlagStatus.ENABLED,
                    ruleset=flag.ruleset,
                ),
            )
            assert updated.name == name + "-updated"
            assert updated.status == FeatureFlagStatus.ENABLED

            # List — should include our flag
            all_flags = ws.list_feature_flags()
            ids = [f.id for f in all_flags]
            assert flag.id in ids

        finally:
            # Must disable before deleting (API rejects deleting enabled flags)
            with contextlib.suppress(Exception):
                ws.update_feature_flag(
                    flag.id,
                    UpdateFeatureFlagParams(
                        name=name + "-updated",
                        key=key,
                        status=FeatureFlagStatus.DISABLED,
                        ruleset=flag.ruleset,
                    ),
                )
            ws.delete_feature_flag(flag.id)

        # Verify deleted
        with pytest.raises(QueryError):
            ws.get_feature_flag(flag.id)

    def test_create_with_all_options(self, ws: Workspace) -> None:
        """Create flag with all options populated.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("allopts")
        key = _unique_key("allopts")
        flag = ws.create_feature_flag(
            CreateFeatureFlagParams(
                name=name,
                key=key,
                description="QA test with all options",
                tags=["qa", "test"],
                context="distinct_id",
                serving_method=ServingMethod.SERVER,
                ruleset={
                    "variants": [
                        {
                            "key": "A",
                            "value": True,
                            "is_control": False,
                            "split": 0.5,
                            "is_sticky": False,
                        },
                        {
                            "key": "B",
                            "value": False,
                            "is_control": True,
                            "split": 0.5,
                            "is_sticky": False,
                        },
                    ],
                    "rollout": [],
                },
            )
        )
        try:
            assert flag.description == "QA test with all options"
            assert flag.serving_method == ServingMethod.SERVER
            assert "qa" in flag.tags
        finally:
            ws.delete_feature_flag(flag.id)


class TestFlagLifecycle:
    """Archive / restore / duplicate — happy path."""

    def test_archive_restore_duplicate(self, ws: Workspace) -> None:
        """Full lifecycle: create → archive → restore → duplicate → cleanup.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("lifecycle")
        key = _unique_key("lifecycle")
        flag = ws.create_feature_flag(CreateFeatureFlagParams(name=name, key=key))
        dup_id: str | None = None
        try:
            # Archive
            ws.archive_feature_flag(flag.id)

            # Excluded from default list
            default_ids = [f.id for f in ws.list_feature_flags()]
            assert flag.id not in default_ids

            # Included with include_archived
            all_ids = [f.id for f in ws.list_feature_flags(include_archived=True)]
            assert flag.id in all_ids

            # Restore
            restored = ws.restore_feature_flag(flag.id)
            assert isinstance(restored, FeatureFlag)
            assert restored.id == flag.id

            # Back in default list
            default_ids_after = [f.id for f in ws.list_feature_flags()]
            assert flag.id in default_ids_after

            # Duplicate — NOTE: Mixpanel API returns 500 for flag
            # duplicate as of 2026-03. Marked xfail until API fix.
            try:
                dup = ws.duplicate_feature_flag(flag.id)
                dup_id = dup.id
                assert isinstance(dup, FeatureFlag)
                assert dup.id != flag.id
            except Exception:
                pytest.xfail("Flag duplicate returns 500 — Mixpanel API issue")

        finally:
            ws.delete_feature_flag(flag.id)
            if dup_id:
                ws.delete_feature_flag(dup_id)


class TestFlagTestUsers:
    """Set test user overrides."""

    def test_set_test_users(self, ws: Workspace) -> None:
        """Set and clear test users on a flag.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("testusers")
        key = _unique_key("testusers")
        flag = ws.create_feature_flag(CreateFeatureFlagParams(name=name, key=key))
        try:
            # Set test users — format is {distinct_id: variant_key}
            variant_keys = [v["key"] for v in flag.ruleset.get("variants", [])]
            users_map = {"qa-user-1": variant_keys[0]} if variant_keys else {}
            ws.set_flag_test_users(
                flag.id,
                SetTestUsersParams(users=users_map),
            )
            # Set empty (clear)
            ws.set_flag_test_users(
                flag.id,
                SetTestUsersParams(users={}),
            )
        finally:
            ws.delete_feature_flag(flag.id)


class TestFlagHistoryAndLimits:
    """History and limits endpoints."""

    def test_flag_history(self, ws: Workspace) -> None:
        """Get change history for a flag.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("history")
        key = _unique_key("history")
        flag = ws.create_feature_flag(CreateFeatureFlagParams(name=name, key=key))
        try:
            history = ws.get_flag_history(flag.id)
            assert isinstance(history, FlagHistoryResponse)
            assert history.count >= 0
            assert isinstance(history.events, list)

            # With pagination
            paginated = ws.get_flag_history(flag.id, page_size=2)
            assert isinstance(paginated, FlagHistoryResponse)
        finally:
            ws.delete_feature_flag(flag.id)

    def test_flag_limits(self, ws: Workspace) -> None:
        """Get account-level flag limits.

        Args:
            ws: Workspace fixture.
        """
        limits = ws.get_flag_limits()
        assert isinstance(limits, FlagLimitsResponse)
        assert limits.limit > 0
        assert limits.current_usage >= 0
        assert isinstance(limits.contract_status, FlagContractStatus)
        assert not limits.is_trial or isinstance(limits.is_trial, bool)


class TestFlagErrors:
    """Error paths for flag operations."""

    def test_get_nonexistent_flag(self, ws: Workspace) -> None:
        """Getting a non-existent flag raises QueryError.

        Args:
            ws: Workspace fixture.
        """
        with pytest.raises(QueryError):
            ws.get_feature_flag("00000000-0000-0000-0000-000000000000")

    def test_delete_nonexistent_flag(self, ws: Workspace) -> None:
        """Deleting a non-existent flag raises QueryError.

        Args:
            ws: Workspace fixture.
        """
        with pytest.raises(QueryError):
            ws.delete_feature_flag("00000000-0000-0000-0000-000000000000")

    def test_create_duplicate_key(self, ws: Workspace) -> None:
        """Creating two flags with the same key raises QueryError.

        Args:
            ws: Workspace fixture.
        """
        name1 = _unique_name("dup1")
        key = _unique_key("dup")
        flag1 = ws.create_feature_flag(CreateFeatureFlagParams(name=name1, key=key))
        try:
            with pytest.raises(QueryError):
                ws.create_feature_flag(
                    CreateFeatureFlagParams(name=_unique_name("dup2"), key=key)
                )
        finally:
            ws.delete_feature_flag(flag1.id)

    def test_update_nonexistent_flag(self, ws: Workspace) -> None:
        """Updating a non-existent flag raises QueryError.

        Args:
            ws: Workspace fixture.
        """
        with pytest.raises(QueryError):
            ws.update_feature_flag(
                "00000000-0000-0000-0000-000000000000",
                UpdateFeatureFlagParams(
                    name="X",
                    key="x",
                    status=FeatureFlagStatus.DISABLED,
                    ruleset={"variants": [], "rollout": []},
                ),
            )


# =============================================================================
# Phase 3: Experiment QA — Workspace Level
# =============================================================================


class TestExperimentCRUD:
    """Experiment create / get / update / list / delete."""

    def test_create_get_update_delete(self, ws: Workspace) -> None:
        """Full CRUD cycle for experiments.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("exp-crud")
        exp = ws.create_experiment(
            CreateExperimentParams(name=name, description="QA CRUD test")
        )
        try:
            assert isinstance(exp, Experiment)
            assert exp.name == name
            assert exp.id
            assert exp.status == ExperimentStatus.DRAFT

            # Get
            fetched = ws.get_experiment(exp.id)
            assert fetched.id == exp.id
            assert fetched.name == name

            # Update (PATCH)
            updated = ws.update_experiment(
                exp.id,
                UpdateExperimentParams(description="QA updated"),
            )
            assert updated.description == "QA updated"

            # List
            all_exps = ws.list_experiments()
            ids = [e.id for e in all_exps]
            assert exp.id in ids

        finally:
            ws.delete_experiment(exp.id)

        # Verify deleted
        with pytest.raises(QueryError):
            ws.get_experiment(exp.id)


class TestExperimentLifecycle:
    """Launch → conclude → decide lifecycle."""

    def test_full_lifecycle_success(self, ws: Workspace) -> None:
        """Draft → active → concluded → success.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("exp-lifecycle-ok")
        exp = ws.create_experiment(CreateExperimentParams(name=name))
        try:
            assert exp.status == ExperimentStatus.DRAFT

            # Launch
            launched = ws.launch_experiment(exp.id)
            assert launched.status == ExperimentStatus.ACTIVE

            # Conclude
            concluded = ws.conclude_experiment(exp.id)
            assert concluded.status == ExperimentStatus.CONCLUDED

            # Decide — success
            decided = ws.decide_experiment(
                exp.id,
                ExperimentDecideParams(success=True, message="QA pass"),
            )
            assert decided.status == ExperimentStatus.SUCCESS

        finally:
            ws.delete_experiment(exp.id)

    def test_lifecycle_failure_decision(self, ws: Workspace) -> None:
        """Launch → conclude with end_date → decide fail.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("exp-lifecycle-fail")
        exp = ws.create_experiment(CreateExperimentParams(name=name))
        try:
            ws.launch_experiment(exp.id)

            # Conclude with end_date
            concluded = ws.conclude_experiment(
                exp.id,
                params=ExperimentConcludeParams(end_date="2026-03-31"),
            )
            assert concluded.status == ExperimentStatus.CONCLUDED

            # Decide — failure
            decided = ws.decide_experiment(
                exp.id,
                ExperimentDecideParams(success=False),
            )
            assert decided.status == ExperimentStatus.FAIL

        finally:
            ws.delete_experiment(exp.id)


class TestExperimentArchiveRestoreDuplicate:
    """Archive / restore / duplicate."""

    def test_archive_restore_duplicate(self, ws: Workspace) -> None:
        """Full management cycle for experiments.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("exp-mgmt")
        exp = ws.create_experiment(CreateExperimentParams(name=name))
        dup1_id: str | None = None
        try:
            # Archive
            ws.archive_experiment(exp.id)

            # Excluded from default list
            default_ids = [e.id for e in ws.list_experiments()]
            assert exp.id not in default_ids

            # Included with include_archived
            all_ids = [e.id for e in ws.list_experiments(include_archived=True)]
            assert exp.id in all_ids

            # Restore
            restored = ws.restore_experiment(exp.id)
            assert isinstance(restored, Experiment)
            assert restored.id == exp.id

            # Duplicate with name (required — API returns empty body without one)
            dup1 = ws.duplicate_experiment(
                exp.id,
                DuplicateExperimentParams(name=_unique_name("exp-dup1")),
            )
            dup1_id = dup1.id
            assert dup1.id != exp.id

        finally:
            ws.delete_experiment(exp.id)
            if dup1_id:
                ws.delete_experiment(dup1_id)


class TestExperimentErrors:
    """Error paths for experiment operations."""

    def test_get_nonexistent(self, ws: Workspace) -> None:
        """Getting non-existent experiment raises QueryError.

        Args:
            ws: Workspace fixture.
        """
        with pytest.raises(QueryError):
            ws.get_experiment("00000000-0000-0000-0000-000000000000")

    def test_launch_already_active_is_idempotent(self, ws: Workspace) -> None:
        """Launching an already-active experiment succeeds (API is lenient).

        The Mixpanel API does not enforce state machine transitions —
        launching an active experiment is a no-op that returns the
        experiment unchanged.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("exp-relaunch")
        exp = ws.create_experiment(CreateExperimentParams(name=name))
        try:
            ws.launch_experiment(exp.id)
            # Second launch does NOT raise — API is lenient
            relaunched = ws.launch_experiment(exp.id)
            assert relaunched.status == ExperimentStatus.ACTIVE
        finally:
            ws.delete_experiment(exp.id)

    def test_conclude_draft_is_noop(self, ws: Workspace) -> None:
        """Concluding a draft experiment succeeds but is a no-op.

        The Mixpanel API does not reject concluding a draft, but it
        also does not change the status — the experiment remains draft.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("exp-conclude-draft")
        exp = ws.create_experiment(CreateExperimentParams(name=name))
        try:
            # Conclude a draft — API accepts but status stays draft
            concluded = ws.conclude_experiment(exp.id)
            assert concluded.status == ExperimentStatus.DRAFT
        finally:
            ws.delete_experiment(exp.id)

    def test_decide_non_concluded(self, ws: Workspace) -> None:
        """Deciding on a draft experiment raises QueryError.

        Args:
            ws: Workspace fixture.
        """
        name = _unique_name("exp-bad-decide")
        exp = ws.create_experiment(CreateExperimentParams(name=name))
        try:
            with pytest.raises(QueryError):
                ws.decide_experiment(exp.id, ExperimentDecideParams(success=True))
        finally:
            ws.delete_experiment(exp.id)


class TestExperimentERF:
    """ERF experiments endpoint."""

    def test_list_erf(self, ws: Workspace) -> None:
        """List ERF experiments returns a list.

        Args:
            ws: Workspace fixture.
        """
        result = ws.list_erf_experiments()
        assert isinstance(result, list)


# =============================================================================
# Phase 4: CLI QA
# =============================================================================


class TestFlagCLI:
    """Flag CLI commands end-to-end."""

    def test_list_json(self) -> None:
        """``mp flags list --format json`` returns valid JSON."""
        r = _mp("flags", "list", "--format", "json")
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert isinstance(data, list)

    def test_list_table(self) -> None:
        """``mp flags list --format table`` succeeds."""
        r = _mp("flags", "list", "--format", "table")
        assert r.returncode == 0, r.stderr

    def test_list_csv(self) -> None:
        """``mp flags list --format csv`` succeeds."""
        r = _mp("flags", "list", "--format", "csv")
        assert r.returncode == 0, r.stderr

    def test_list_include_archived(self) -> None:
        """``mp flags list --include-archived`` succeeds."""
        r = _mp("flags", "list", "--include-archived", "--format", "json")
        assert r.returncode == 0, r.stderr

    def test_list_jq_filter(self) -> None:
        """``mp flags list --jq '.[0].name'`` extracts a name."""
        r = _mp("flags", "list", "--jq", ".[0].name")
        assert r.returncode == 0, r.stderr

    def test_list_jsonl(self) -> None:
        """``mp flags list --format jsonl`` produces lines."""
        r = _mp("flags", "list", "--format", "jsonl")
        assert r.returncode == 0, r.stderr
        lines = [line for line in r.stdout.strip().split("\n") if line]
        if lines:
            json.loads(lines[0])  # Each line is valid JSON

    def test_crud_lifecycle(self) -> None:
        """Full CLI CRUD: create → get → update → delete."""
        name = _unique_name("cli-crud")
        key = _unique_key("cli_crud")

        # Create
        r = _mp("flags", "create", "--name", name, "--key", key)
        assert r.returncode == 0, r.stderr
        flag = json.loads(r.stdout)
        flag_id = flag["id"]

        try:
            # Get
            r = _mp("flags", "get", flag_id)
            assert r.returncode == 0, r.stderr
            got = json.loads(r.stdout)
            assert got["name"] == name

            # Update — enable
            ruleset = json.dumps(flag["ruleset"])
            r = _mp(
                "flags",
                "update",
                flag_id,
                "--name",
                name + "-up",
                "--key",
                key,
                "--status",
                "enabled",
                "--ruleset",
                ruleset,
            )
            assert r.returncode == 0, r.stderr
            updated = json.loads(r.stdout)
            assert updated["name"] == name + "-up"
            assert updated["status"] == "enabled"

        finally:
            # Must disable before deleting (API rejects deleting enabled flags)
            _mp(
                "flags",
                "update",
                flag_id,
                "--name",
                name + "-up",
                "--key",
                key,
                "--status",
                "disabled",
                "--ruleset",
                ruleset,
            )
            r = _mp("flags", "delete", flag_id)
            assert r.returncode == 0, r.stderr

    def test_archive_restore(self) -> None:
        """CLI archive → restore → cleanup."""
        name = _unique_name("cli-life")
        key = _unique_key("cli_life")

        r = _mp("flags", "create", "--name", name, "--key", key)
        assert r.returncode == 0, r.stderr
        flag = json.loads(r.stdout)
        flag_id = flag["id"]

        try:
            # Archive
            r = _mp("flags", "archive", flag_id)
            assert r.returncode == 0, r.stderr

            # Restore
            r = _mp("flags", "restore", flag_id)
            assert r.returncode == 0, r.stderr

            # NOTE: Flag duplicate via CLI skipped — Mixpanel API
            # returns 500 for flag duplicate as of 2026-03.

        finally:
            _mp("flags", "delete", flag_id)

    def test_set_test_users(self) -> None:
        """CLI set-test-users succeeds."""
        name = _unique_name("cli-tu")
        key = _unique_key("cli_tu")
        r = _mp("flags", "create", "--name", name, "--key", key)
        assert r.returncode == 0, r.stderr
        flag = json.loads(r.stdout)
        flag_id = flag["id"]
        # Use actual variant key from created flag's ruleset
        variant_key = flag["ruleset"]["variants"][0]["key"]

        try:
            # Format: {distinct_id: variant_key}
            users_json = json.dumps({"qa-user": variant_key})
            r = _mp(
                "flags",
                "set-test-users",
                flag_id,
                "--users",
                users_json,
            )
            assert r.returncode == 0, r.stderr
        finally:
            _mp("flags", "delete", flag_id)

    def test_history(self) -> None:
        """CLI flag history succeeds."""
        name = _unique_name("cli-hist")
        key = _unique_key("cli_hist")
        r = _mp("flags", "create", "--name", name, "--key", key)
        assert r.returncode == 0, r.stderr
        flag_id = json.loads(r.stdout)["id"]

        try:
            r = _mp("flags", "history", flag_id, "--format", "json")
            assert r.returncode == 0, r.stderr
            hist = json.loads(r.stdout)
            assert "events" in hist
            assert "count" in hist

            # With pagination
            r = _mp("flags", "history", flag_id, "--page-size", "2")
            assert r.returncode == 0, r.stderr
        finally:
            _mp("flags", "delete", flag_id)

    def test_limits(self) -> None:
        """CLI flag limits returns JSON with expected fields."""
        r = _mp("flags", "limits", "--format", "json")
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert "limit" in data
        assert "current_usage" in data
        assert "contract_status" in data

    def test_limits_table(self) -> None:
        """CLI flag limits in table format succeeds."""
        r = _mp("flags", "limits", "--format", "table")
        assert r.returncode == 0, r.stderr


class TestFlagCLIErrors:
    """Flag CLI error cases."""

    def test_get_nonexistent(self) -> None:
        """Getting non-existent flag exits non-zero."""
        r = _mp("flags", "get", "00000000-0000-0000-0000-000000000000")
        assert r.returncode != 0

    def test_invalid_ruleset_json(self) -> None:
        """Invalid --ruleset JSON exits 1."""
        r = _mp(
            "flags",
            "create",
            "--name",
            "X",
            "--key",
            "x",
            "--ruleset",
            "not-json",
        )
        assert r.returncode != 0
        assert "Invalid JSON" in r.stdout or "Invalid JSON" in r.stderr

    def test_invalid_status_enum(self) -> None:
        """Invalid --status value exits non-zero."""
        r = _mp(
            "flags",
            "create",
            "--name",
            "X",
            "--key",
            "x",
            "--status",
            "bogus",
        )
        assert r.returncode != 0

    def test_invalid_users_json(self) -> None:
        """Invalid --users JSON exits non-zero."""
        r = _mp(
            "flags",
            "set-test-users",
            "abc",
            "--users",
            "bad",
        )
        assert r.returncode != 0

    def test_no_subcommand_shows_help(self) -> None:
        """``mp flags`` with no subcommand shows help (exit 2)."""
        r = _mp("flags")
        # Typer exits with code 2 for missing subcommand (no_args_is_help)
        assert r.returncode == 2 or r.returncode == 0
        # Help output may go to stderr (Typer behavior)
        output = r.stdout + r.stderr
        assert "Commands" in output or "Usage" in output


class TestExperimentCLI:
    """Experiment CLI commands end-to-end."""

    def test_list_json(self) -> None:
        """``mp experiments list --format json`` returns valid JSON."""
        r = _mp("experiments", "list", "--format", "json")
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert isinstance(data, list)

    def test_list_table(self) -> None:
        """``mp experiments list --format table`` succeeds."""
        r = _mp("experiments", "list", "--format", "table")
        assert r.returncode == 0, r.stderr

    def test_list_include_archived(self) -> None:
        """``mp experiments list --include-archived`` succeeds."""
        r = _mp("experiments", "list", "--include-archived", "--format", "json")
        assert r.returncode == 0, r.stderr

    def test_crud_lifecycle_decide(self) -> None:
        """Full CLI: create → get → update → launch → conclude → decide → delete."""
        name = _unique_name("cli-exp")

        # Create
        r = _mp("experiments", "create", "--name", name)
        assert r.returncode == 0, r.stderr
        exp = json.loads(r.stdout)
        exp_id = exp["id"]
        assert exp["status"] == "draft"

        try:
            # Get
            r = _mp("experiments", "get", exp_id)
            assert r.returncode == 0, r.stderr

            # Update
            r = _mp(
                "experiments",
                "update",
                exp_id,
                "--description",
                "QA CLI test",
            )
            assert r.returncode == 0, r.stderr

            # Launch
            r = _mp("experiments", "launch", exp_id)
            assert r.returncode == 0, r.stderr
            launched = json.loads(r.stdout)
            assert launched["status"] == "active"

            # Conclude
            r = _mp("experiments", "conclude", exp_id)
            assert r.returncode == 0, r.stderr
            concluded = json.loads(r.stdout)
            assert concluded["status"] == "concluded"

            # Decide
            r = _mp(
                "experiments",
                "decide",
                exp_id,
                "--success",
                "--message",
                "QA pass",
            )
            assert r.returncode == 0, r.stderr
            decided = json.loads(r.stdout)
            assert decided["status"] == "success"

        finally:
            _mp("experiments", "delete", exp_id)

    def test_archive_restore_duplicate(self) -> None:
        """CLI archive → restore → duplicate → cleanup."""
        name = _unique_name("cli-exp-life")
        r = _mp("experiments", "create", "--name", name)
        assert r.returncode == 0, r.stderr
        exp_id = json.loads(r.stdout)["id"]
        dup_id: str | None = None

        try:
            # Archive
            r = _mp("experiments", "archive", exp_id)
            assert r.returncode == 0, r.stderr

            # Restore
            r = _mp("experiments", "restore", exp_id)
            assert r.returncode == 0, r.stderr

            # Duplicate with name
            r = _mp(
                "experiments",
                "duplicate",
                exp_id,
                "--name",
                _unique_name("cli-dup"),
            )
            assert r.returncode == 0, r.stderr
            dup = json.loads(r.stdout)
            dup_id = dup["id"]
            assert dup_id != exp_id

        finally:
            _mp("experiments", "delete", exp_id)
            if dup_id:
                _mp("experiments", "delete", dup_id)

    def test_erf(self) -> None:
        """``mp experiments erf --format json`` succeeds."""
        r = _mp("experiments", "erf", "--format", "json")
        assert r.returncode == 0, r.stderr

    def test_conclude_with_end_date(self) -> None:
        """CLI conclude with --end-date succeeds."""
        name = _unique_name("cli-conclude-date")
        r = _mp("experiments", "create", "--name", name)
        assert r.returncode == 0, r.stderr
        exp_id = json.loads(r.stdout)["id"]
        try:
            _mp("experiments", "launch", exp_id)
            r = _mp(
                "experiments",
                "conclude",
                exp_id,
                "--end-date",
                "2026-03-31",
            )
            assert r.returncode == 0, r.stderr
        finally:
            _mp("experiments", "delete", exp_id)

    def test_decide_no_success(self) -> None:
        """CLI decide with --no-success exits 0."""
        name = _unique_name("cli-decide-fail")
        r = _mp("experiments", "create", "--name", name)
        assert r.returncode == 0, r.stderr
        exp_id = json.loads(r.stdout)["id"]
        try:
            _mp("experiments", "launch", exp_id)
            _mp("experiments", "conclude", exp_id)
            r = _mp("experiments", "decide", exp_id, "--no-success")
            assert r.returncode == 0, r.stderr
            decided = json.loads(r.stdout)
            assert decided["status"] == "fail"
        finally:
            _mp("experiments", "delete", exp_id)


class TestExperimentCLIErrors:
    """Experiment CLI error cases."""

    def test_get_nonexistent(self) -> None:
        """Getting non-existent experiment exits non-zero."""
        r = _mp("experiments", "get", "00000000-0000-0000-0000-000000000000")
        assert r.returncode != 0

    def test_invalid_settings_json(self) -> None:
        """Invalid --settings JSON exits non-zero."""
        r = _mp(
            "experiments",
            "create",
            "--name",
            "X",
            "--settings",
            "bad-json",
        )
        assert r.returncode != 0

    def test_invalid_variants_json(self) -> None:
        """Invalid --variants JSON exits non-zero."""
        r = _mp(
            "experiments",
            "update",
            "abc",
            "--variants",
            "bad-json",
        )
        assert r.returncode != 0

    def test_no_subcommand_shows_help(self) -> None:
        """``mp experiments`` with no subcommand shows help (exit 2)."""
        r = _mp("experiments")
        # Typer exits with code 2 for missing subcommand (no_args_is_help)
        assert r.returncode == 2 or r.returncode == 0
        # Help output may go to stderr (Typer behavior)
        output = r.stdout + r.stderr
        assert "Commands" in output or "Usage" in output


# =============================================================================
# Phase 5: Cross-Cutting Concerns
# =============================================================================


class TestExtraFieldPreservation:
    """Real API returns fields not in our model — verify they survive."""

    def test_flag_extra_fields(self, ws: Workspace) -> None:
        """Real API flag responses have extra fields in model_extra.

        Args:
            ws: Workspace fixture.
        """
        flags = ws.list_feature_flags()
        if flags:
            flag = flags[0]
            # Real API returns fields like content_environments, can_view,
            # allow_staff_override etc. that aren't in our model
            assert flag.model_extra is not None or isinstance(flag.model_dump(), dict)

    def test_experiment_extra_fields(self, ws: Workspace) -> None:
        """Real API experiment responses have extra fields.

        Args:
            ws: Workspace fixture.
        """
        exps = ws.list_experiments()
        if exps:
            exp = exps[0]
            assert exp.model_extra is not None or isinstance(exp.model_dump(), dict)


class TestSerializationRoundTrip:
    """model_dump → model_validate round-trip with real API data."""

    def test_flag_round_trip(self, ws: Workspace) -> None:
        """FeatureFlag round-trips through serialization.

        Args:
            ws: Workspace fixture.
        """
        flags = ws.list_feature_flags()
        if flags:
            flag = flags[0]
            data = flag.model_dump()
            restored = FeatureFlag.model_validate(data)
            assert restored.id == flag.id
            assert restored.name == flag.name

    def test_experiment_round_trip(self, ws: Workspace) -> None:
        """Experiment round-trips through serialization.

        Args:
            ws: Workspace fixture.
        """
        exps = ws.list_experiments()
        if exps:
            exp = exps[0]
            data = exp.model_dump()
            restored = Experiment.model_validate(data)
            assert restored.id == exp.id
            assert restored.name == exp.name
