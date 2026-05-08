"""Functional tests for the new v3 CLI command groups (T054-T058).

Covers ``mp account``, ``mp project``, ``mp workspace``, ``mp session``,
``mp config`` plus the new globals (``--account``, ``--project``,
``--workspace``, ``--target``).

Reference: specs/042-auth-architecture-redesign/contracts/cli-commands.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless.cli.main import app


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate $HOME and MP_CONFIG_PATH for hermetic CLI tests."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))


@pytest.fixture
def runner() -> CliRunner:
    """A Typer CliRunner."""
    return CliRunner()


class TestAccountCli:
    """``mp account`` subcommands."""

    def test_list_empty(self, runner: CliRunner) -> None:
        """Empty config prints '(no accounts configured)'."""
        result = runner.invoke(app, ["account", "list"])
        assert result.exit_code == 0, result.output
        assert "no accounts configured" in result.output

    def test_add_service_account_via_env(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``mp account add --type service_account`` uses MP_SECRET from env."""
        monkeypatch.setenv("MP_SECRET", "team-secret")
        result = runner.invoke(
            app,
            [
                "account",
                "add",
                "team",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u",
                "--project",
                "3713224",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "team" in result.output
        assert "service_account" in result.output

    def test_add_oauth_browser(self, runner: CliRunner) -> None:
        """``mp account add --type oauth_browser`` needs no extra fields."""
        result = runner.invoke(
            app,
            ["account", "add", "personal", "--type", "oauth_browser", "--region", "us"],
        )
        assert result.exit_code == 0, result.output

    def test_add_oauth_token_with_env(self, runner: CliRunner) -> None:
        """``mp account add --type oauth_token --token-env`` is accepted."""
        result = runner.invoke(
            app,
            [
                "account",
                "add",
                "ci",
                "--type",
                "oauth_token",
                "--region",
                "us",
                "--token-env",
                "MP_OAUTH_TOKEN",
                "--project",
                "3713224",
            ],
        )
        assert result.exit_code == 0, result.output

    def test_add_invalid_type_exits_nonzero(self, runner: CliRunner) -> None:
        """Bad ``--type`` exits with non-zero code and prints to stderr."""
        result = runner.invoke(
            app,
            ["account", "add", "x", "--type", "magic", "--region", "us"],
        )
        assert result.exit_code != 0

    def test_use_promotes_active(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``mp account use NAME`` writes [active].account."""
        monkeypatch.setenv("MP_SECRET", "s")
        runner.invoke(
            app,
            [
                "account",
                "add",
                "a",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u",
                "--project",
                "3713224",
            ],
        )
        runner.invoke(
            app, ["account", "add", "b", "--type", "oauth_browser", "--region", "us"]
        )
        result = runner.invoke(app, ["account", "use", "b"])
        assert result.exit_code == 0
        active = ConfigManager().get_active().account
        assert active == "b"

    def test_remove_simple(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``mp account remove NAME`` removes an unreferenced account."""
        monkeypatch.setenv("MP_SECRET", "s")
        runner.invoke(
            app,
            [
                "account",
                "add",
                "a",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u",
                "--project",
                "3713224",
            ],
        )
        result = runner.invoke(app, ["account", "remove", "a"])
        assert result.exit_code == 0


class TestAccountAdd043Relaxations:
    """Phase 043 relaxations to ``mp account add``.

    Per AIE-115 (US3), ``--project`` is optional for ``service_account``
    and ``oauth_token`` types — the user can leave it blank and configure
    the active project later via ``mp project use ID``.
    """

    def test_service_account_without_project_succeeds(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SA add without ``--project`` works; account has no default_project."""
        # Make sure MP_PROJECT_ID isn't set in the test env, so the absence
        # of --project really exercises the no-project path.
        monkeypatch.delenv("MP_PROJECT_ID", raising=False)
        monkeypatch.setenv("MP_SECRET", "team-secret")
        result = runner.invoke(
            app,
            [
                "account",
                "add",
                "team",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u",
            ],
        )
        assert result.exit_code == 0, result.output
        cm = ConfigManager()
        assert cm.get_account("team").default_project is None

    def test_oauth_token_without_project_succeeds(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """oauth_token add without ``--project`` works; no default_project."""
        monkeypatch.delenv("MP_PROJECT_ID", raising=False)
        monkeypatch.setenv("MP_OAUTH_TOKEN", "ey.x")
        result = runner.invoke(
            app,
            [
                "account",
                "add",
                "ci",
                "--type",
                "oauth_token",
                "--region",
                "us",
            ],
        )
        assert result.exit_code == 0, result.output
        cm = ConfigManager()
        assert cm.get_account("ci").default_project is None

    def test_account_add_help_includes_login_tip(self, runner: CliRunner) -> None:
        """``mp account add --help`` epilog mentions ``mp login``.

        Per cli-commands.md §2.2, the help epilog steers new users toward
        the guided ``mp login`` while keeping ``mp account add`` available
        for scripted setups.
        """
        result = runner.invoke(app, ["account", "add", "--help"])
        assert result.exit_code == 0, result.output
        # Match the catalog wording loosely — exact phrasing locked by
        # the implementation, not the test.
        assert "mp login" in result.output
        assert "guided" in result.output.lower() or "tip" in result.output.lower()


class TestAccountAddRegionProbe:
    """``mp account add`` without ``--region`` probes us → eu → in (043 / AIE-114).

    The CLI builds the credential header, hands it to
    :func:`region_probe.probe_region` with a region-scoped
    ``client_factory``, prints one stderr line per attempt, and persists
    the resolved region. With ``--region`` supplied, the probe is
    skipped entirely.
    """

    def test_sa_without_region_probes_and_persists_resolved_region(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No ``--region`` → CLI probes; account record reflects probed region."""
        from mixpanel_headless._internal.auth import region_probe as rp_mod

        monkeypatch.setenv("MP_SECRET", "team-secret")
        captured: dict[str, object] = {}

        def _spy_probe(
            client_factory: object,
            headers: dict[str, str],
            *,
            timeout_seconds: float = 5.0,
            order: tuple[str, ...] = ("us", "eu", "in"),
        ) -> rp_mod.RegionProbeResult:
            captured["headers"] = dict(headers)
            captured["order"] = order
            return rp_mod.RegionProbeResult(
                region="eu", attempts=[("us", 401), ("eu", 200)]
            )

        monkeypatch.setattr(rp_mod, "probe_region", _spy_probe)

        result = runner.invoke(
            app,
            [
                "account",
                "add",
                "my-eu-sa",
                "--type",
                "service_account",
                "--username",
                "u",
            ],
        )
        assert result.exit_code == 0, result.output
        cm = ConfigManager()
        assert cm.get_account("my-eu-sa").region == "eu"
        # Header carries the SA Basic auth value.
        headers = captured["headers"]
        assert isinstance(headers, dict)
        assert "Authorization" in headers
        auth_value = headers["Authorization"]
        assert isinstance(auth_value, str)
        assert auth_value.startswith("Basic ")

    def test_sa_with_explicit_region_skips_probe(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit ``--region us`` → ``probe_region`` is never called."""
        from mixpanel_headless._internal.auth import region_probe as rp_mod

        monkeypatch.setenv("MP_SECRET", "s")
        called = {"count": 0}

        def _no_probe(*args: object, **kwargs: object) -> object:
            called["count"] += 1
            raise AssertionError("probe_region must not be called when --region is set")

        monkeypatch.setattr(rp_mod, "probe_region", _no_probe)

        result = runner.invoke(
            app,
            [
                "account",
                "add",
                "team",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u",
            ],
        )
        assert result.exit_code == 0, result.output
        assert called["count"] == 0

    def test_probe_failure_surfaces_e1_message(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All-region probe failure → exit 2 with E-1 wording in stderr."""
        from mixpanel_headless._internal.auth import region_probe as rp_mod
        from mixpanel_headless.exceptions import RegionProbeError

        monkeypatch.setenv("MP_SECRET", "s")

        def _fail(*args: object, **kwargs: object) -> object:
            raise RegionProbeError(
                "Credential not valid in any region.",
                attempts=[
                    ("us", 401, "Unauthorized"),
                    ("eu", 401, "Unauthorized"),
                    ("in", 401, "Unauthorized"),
                ],
            )

        monkeypatch.setattr(rp_mod, "probe_region", _fail)

        result = runner.invoke(
            app,
            [
                "account",
                "add",
                "bad-sa",
                "--type",
                "service_account",
                "--username",
                "u",
            ],
        )
        # E-1 is an AuthenticationError-class failure → exit 2.
        from mixpanel_headless.cli.utils import ExitCode

        assert result.exit_code == ExitCode.AUTH_ERROR, result.output
        # E-1 phrasing — the per-region attempts and the suggested fix.
        assert "us: 401" in result.output
        assert "eu: 401" in result.output
        assert "in: 401" in result.output
        assert "--region" in result.output

    def test_all_network_failures_render_distinct_message(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All-network probe failure → distinct CLI handler with connectivity hint.

        When every region returns status 0 (DNS / TLS / connect refused),
        the orchestrator raises :class:`RegionProbeNetworkError`. The
        CLI's ``RegionProbeNetworkError`` branch must catch it before
        the generic handler and render "check your network" instead of
        "verify your credentials". A user who is offline gets
        misdirected by the credential-flavored hint otherwise.
        """
        from mixpanel_headless._internal.auth import region_probe as rp_mod
        from mixpanel_headless.cli.utils import ExitCode
        from mixpanel_headless.exceptions import RegionProbeNetworkError

        monkeypatch.setenv("MP_SECRET", "s")

        def _all_network(*args: object, **kwargs: object) -> object:
            raise RegionProbeNetworkError(
                "Could not reach any Mixpanel region — every probe failed at "
                "the network layer (DNS, TLS, or connect refused).",
                attempts=[
                    ("us", 0, "ConnectError: dns lookup failed"),
                    ("eu", 0, "ConnectError: dns lookup failed"),
                    ("in", 0, "ConnectError: dns lookup failed"),
                ],
            )

        monkeypatch.setattr(rp_mod, "probe_region", _all_network)

        result = runner.invoke(
            app,
            [
                "account",
                "add",
                "offline-sa",
                "--type",
                "service_account",
                "--username",
                "u",
            ],
        )
        assert result.exit_code == ExitCode.AUTH_ERROR, result.output
        # Connectivity hint, not the credential-verify hint.
        assert "Could not reach any Mixpanel region" in result.output
        assert "network" in result.output.lower()
        # Per-region body must surface the network-error reason so the
        # user can see DNS vs TLS vs connect-refused at a glance.
        assert "ConnectError" in result.output
        # The credential-verify hint from the generic handler must NOT
        # leak into the network case (the whole point of the subclass).
        assert "verify the username and secret" not in result.output


class TestAccountAddDerivedName:
    """Phase 043 / AIE-116: ``mp account add`` derives NAME from /me.

    For service_account / oauth_token, omitting the positional NAME
    triggers a /me lookup and slugifies the first organization to
    pick the local account name. For oauth_browser the CLI refuses
    and points the user at ``mp login`` (the orchestrator handles the
    PKCE-then-derive flow).
    """

    def test_sa_without_name_derives_from_first_org(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SA add without NAME → name slugified from the first org."""
        from mixpanel_headless._internal import api_client as api_client_mod

        monkeypatch.setenv("MP_SECRET", "team-secret")

        def _fake_me(self: object) -> dict[str, object]:
            return {
                "user_id": 1,
                "user_email": "u@example.com",
                "organizations": {"100": {"id": 100, "name": "Acme Corp"}},
                "projects": {},
            }

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)
        result = runner.invoke(
            app,
            [
                "account",
                "add",
                # NO positional name
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u",
            ],
        )
        assert result.exit_code == 0, result.output
        cm = ConfigManager()
        assert "acme-corp" in {s.name for s in cm.list_accounts()}

    def test_sa_without_name_collision_appends_suffix(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two SA adds against the same org slug → ``acme-corp`` + ``acme-corp-2``."""
        from mixpanel_headless._internal import api_client as api_client_mod

        monkeypatch.setenv("MP_SECRET", "s")

        def _fake_me(self: object) -> dict[str, object]:
            return {
                "user_id": 1,
                "user_email": "u@example.com",
                "organizations": {"100": {"id": 100, "name": "Acme Corp"}},
                "projects": {},
            }

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)

        # First add → acme-corp
        first = runner.invoke(
            app,
            [
                "account",
                "add",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u1",
            ],
        )
        assert first.exit_code == 0, first.output

        # Second add against same org slug → acme-corp-2
        second = runner.invoke(
            app,
            [
                "account",
                "add",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u2",
            ],
        )
        assert second.exit_code == 0, second.output

        cm = ConfigManager()
        names = {s.name for s in cm.list_accounts()}
        assert "acme-corp" in names
        assert "acme-corp-2" in names

    def test_explicit_name_skips_derivation(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Passing ``foo`` as positional NAME wins over the derivation path."""
        from mixpanel_headless._internal import api_client as api_client_mod

        monkeypatch.setenv("MP_SECRET", "s")
        called = {"count": 0}

        def _spy_me(self: object) -> dict[str, object]:
            # If NAME is supplied, derivation should not run, so /me
            # should NOT be called by accounts.add. (It can still be
            # called by other discovery paths, but not the derive_name
            # path.)
            called["count"] += 1
            return {"user_id": 1, "organizations": {}, "projects": {}}

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _spy_me)
        result = runner.invoke(
            app,
            [
                "account",
                "add",
                "foo",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u",
            ],
        )
        assert result.exit_code == 0, result.output
        cm = ConfigManager()
        assert cm.get_account("foo").type == "service_account"
        assert called["count"] == 0, "/me should not be called when NAME is explicit"

    def test_oauth_browser_without_name_refuses(self, runner: CliRunner) -> None:
        """``mp account add --type oauth_browser`` (no NAME) refuses with hint."""
        result = runner.invoke(
            app,
            ["account", "add", "--type", "oauth_browser", "--region", "us"],
        )
        assert result.exit_code != 0, result.output
        assert "mp login" in result.output


class TestProjectListScopeHint:
    """``mp project list`` extends the 403 message with the scope hint.

    Per AIE-115 (US3) error catalog E-10, when a service account hits
    /me without the ``user_details`` scope the CLI must spell out which
    scope to enable instead of the generic "lacks /me permission" line.
    """

    def test_project_list_403_for_service_account_surfaces_scope_hint(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A 403 from /me on an SA prints E-10 wording and exits non-zero."""
        from mixpanel_headless._internal import api_client as api_client_mod
        from mixpanel_headless.exceptions import QueryError

        monkeypatch.setenv("MP_SECRET", "s")
        runner.invoke(
            app,
            [
                "account",
                "add",
                "limited-sa",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u",
                "--project",
                "1111111",
            ],
        )

        def _raise_403(self: object) -> dict[str, object]:
            raise QueryError("Permission denied", status_code=403)

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _raise_403)
        result = runner.invoke(app, ["project", "list"])
        assert result.exit_code != 0, result.output
        # E-10 key phrases — wording locked but not snapped end-to-end so
        # ANSI styling drift in @handle_errors doesn't break the test.
        assert "user_details" in result.output
        assert "Settings" in result.output
        assert "Service Accounts" in result.output


class TestAccountLoginNoBrowser:
    """``mp account login NAME --no-browser`` MUST propagate ``open_browser=False``.

    Regression: the library function ``accounts.login(name, open_browser=False)``
    is independently tested, but a CLI wiring bug could silently swallow
    ``--no-browser`` and still try to launch the system browser, which hangs
    in headless / SSH / CI contexts. This test pins the propagation contract
    so a future Typer signature change is caught immediately.
    """

    def test_no_browser_flag_propagates_to_namespace_login(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--no-browser`` forwards to ``accounts_ns.login(open_browser=False)``."""
        from mixpanel_headless import accounts as accounts_ns

        # Seed an oauth_browser account so the CLI command type-checks pass.
        runner.invoke(
            app,
            [
                "account",
                "add",
                "personal",
                "--type",
                "oauth_browser",
                "--region",
                "us",
            ],
        )

        captured: dict[str, object] = {}

        def _spy_login(name: str, *, open_browser: bool = True) -> object:
            captured["name"] = name
            captured["open_browser"] = open_browser
            # Return a minimal OAuthLoginResult so the CLI handler can render.
            from datetime import datetime, timezone

            from mixpanel_headless.types import OAuthLoginResult

            return OAuthLoginResult(
                account_name=name,
                user=None,
                expires_at=datetime.now(timezone.utc),
                tokens_path=Path("/tmp/test/tokens.json"),
                client_path=Path("/tmp/test/client.json"),
            )

        monkeypatch.setattr(accounts_ns, "login", _spy_login)

        # Default (no flag) → open_browser=True
        result = runner.invoke(app, ["account", "login", "personal"])
        assert result.exit_code == 0, result.output
        assert captured["open_browser"] is True

        # With --no-browser → open_browser=False
        result = runner.invoke(app, ["account", "login", "personal", "--no-browser"])
        assert result.exit_code == 0, result.output
        assert captured["open_browser"] is False


class TestProjectCli:
    """``mp project`` subcommands."""

    def test_show_when_no_active(self, runner: CliRunner) -> None:
        """Empty config → '(no active project)'."""
        result = runner.invoke(app, ["project", "show"])
        assert result.exit_code == 0
        assert "no active project" in result.output

    def test_use_writes_active_account_default_project(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``mp project use ID`` writes the active account's ``default_project``.

        Project lives on the account (FR-012), not in ``[active]``.
        """
        monkeypatch.setenv("MP_SECRET", "s")
        runner.invoke(
            app,
            [
                "account",
                "add",
                "a",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u",
                "--project",
                "1111111",
            ],
        )
        result = runner.invoke(app, ["project", "use", "3713224"])
        assert result.exit_code == 0
        cm = ConfigManager()
        # The active account's default_project was updated.
        assert cm.get_account("a").default_project == "3713224"

    def test_use_without_active_account_errors(self, runner: CliRunner) -> None:
        """``mp project use ID`` with no active account exits non-zero."""
        result = runner.invoke(app, ["project", "use", "3713224"])
        assert result.exit_code != 0


class TestProjectCliList:
    """``mp project list`` enumerates from /me (FR-047 + cli-commands.md §4.1)."""

    def _seed_account_and_me_cache(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        *,
        default_project: str | None = "1111111",
    ) -> None:
        """Add a service account + pre-populate the /me disk cache.

        Args:
            runner: Typer CliRunner.
            monkeypatch: pytest monkeypatch fixture.
            default_project: Active account's default_project; pass None
                to exercise the FR-047 "no project configured" path.
                ``service_account`` requires ``--project`` at add time;
                we strip it post-hoc via ConfigManager when None.
        """
        from mixpanel_headless._internal.me import (
            MeCache,
            MeProjectInfo,
            MeResponse,
        )

        monkeypatch.setenv("MP_SECRET", "s")
        result = runner.invoke(
            app,
            [
                "account",
                "add",
                "team",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u",
                "--project",
                "1111111",
            ],
        )
        assert result.exit_code == 0, result.output
        cm = ConfigManager()
        if default_project is None:
            cm.update_account("team", default_project=None)
        elif default_project != "1111111":
            cm.update_account("team", default_project=default_project)

        # Pre-populate MeCache for "team" with two accessible projects.
        cache = MeCache(account_name="team")
        cache.put(
            MeResponse(
                user_id=42,
                user_email="u@example.com",
                projects={
                    "1111111": MeProjectInfo(
                        name="Alpha", organization_id=100, timezone="US/Pacific"
                    ),
                    "2222222": MeProjectInfo(
                        name="Beta", organization_id=100, timezone="US/Pacific"
                    ),
                },
            )
        )

    def test_list_enumerates_from_me_cache_by_default(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``mp project list`` MUST list projects from /me, not just print active.

        Regression: prior implementation echoed only ``default_project``
        unless ``--remote`` was passed, defeating the documented
        ``needs_project`` bootstrap flow.
        """
        self._seed_account_and_me_cache(runner, monkeypatch)
        result = runner.invoke(app, ["project", "list"])
        assert result.exit_code == 0, result.output
        assert "1111111" in result.output
        assert "2222222" in result.output
        assert "Alpha" in result.output
        assert "Beta" in result.output

    def test_list_marks_active_project(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The active account's ``default_project`` is marked with ``*``."""
        self._seed_account_and_me_cache(runner, monkeypatch)
        result = runner.invoke(app, ["project", "list"])
        assert result.exit_code == 0, result.output
        # Active line starts with '*' marker.
        active_line = next(
            line for line in result.output.splitlines() if "1111111" in line
        )
        assert active_line.lstrip().startswith("*")
        # Non-active line does not.
        other_line = next(
            line for line in result.output.splitlines() if "2222222" in line
        )
        assert not other_line.lstrip().startswith("*")

    def test_list_works_without_default_project_configured(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-047: ``mp project list`` MUST work with only auth configured.

        No ``default_project`` on the account → enumeration via /me must
        still succeed (the bootstrap path the plugin's ``needs_project``
        state depends on).
        """
        self._seed_account_and_me_cache(runner, monkeypatch, default_project=None)
        result = runner.invoke(app, ["project", "list"])
        assert result.exit_code == 0, result.output
        assert "1111111" in result.output
        assert "2222222" in result.output

    def test_list_refresh_bypasses_cache(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--refresh`` forces a /me re-fetch instead of using the disk cache.

        ``--refresh`` is the single canonical name (matches the Python API
        :meth:`Workspace.projects(refresh=)`); there is no ``--remote`` alias.
        """
        self._seed_account_and_me_cache(runner, monkeypatch)
        from mixpanel_headless._internal import me as me_mod

        call_log: list[bool] = []

        def _spy_fetch(
            self: object, *, force_refresh: bool = False
        ) -> me_mod.MeResponse:
            call_log.append(force_refresh)
            cache = self._cache  # type: ignore[attr-defined]  # noqa: SLF001
            cached: me_mod.MeResponse | None = cache.get()
            assert cached is not None  # seeded by the fixture
            return cached

        monkeypatch.setattr(me_mod.MeService, "fetch", _spy_fetch)

        result_refresh = runner.invoke(app, ["project", "list", "--refresh"])
        assert result_refresh.exit_code == 0, result_refresh.output
        assert any(call_log), "--refresh did not force a refetch"

    def test_list_remote_alias_removed(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--remote`` is not a valid option — usage exits with a usage error."""
        self._seed_account_and_me_cache(runner, monkeypatch)
        result = runner.invoke(app, ["project", "list", "--remote"])
        # Typer maps unknown options to exit code 2 with "No such option".
        assert result.exit_code == 2
        assert "--remote" in result.output


class TestWorkspaceCli:
    """``mp workspace`` subcommands."""

    def test_show_when_unset(self, runner: CliRunner) -> None:
        """``mp workspace show`` prints auto-resolution hint when unset."""
        result = runner.invoke(app, ["workspace", "show"])
        assert result.exit_code == 0
        assert "auto-resolved" in result.output

    def test_use_writes_active(self, runner: CliRunner) -> None:
        """``mp workspace use N`` writes [active].workspace."""
        result = runner.invoke(app, ["workspace", "use", "42"])
        assert result.exit_code == 0
        active = ConfigManager().get_active().workspace
        assert active == 42


class TestSessionCli:
    """``mp session`` (no subcommand) prints active state."""

    def test_session_default_format(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`mp session` prints contract-formatted four-line summary."""
        monkeypatch.setenv("MP_SECRET", "s")
        runner.invoke(
            app,
            [
                "account",
                "add",
                "a",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u",
                "--project",
                "3713224",
            ],
        )
        result = runner.invoke(app, ["session"])
        assert result.exit_code == 0
        # Contract §7: capitalized labels, four lines (account / project /
        # workspace / user) with type+region annotation on the account.
        assert "Account:" in result.output
        assert "Project:" in result.output
        assert "Workspace:" in result.output
        assert "User:" in result.output
        assert "service_account" in result.output  # account type annotation
        assert "us" in result.output  # region annotation

    def test_session_json_format(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``mp session --format json`` emits the contract structured payload."""
        monkeypatch.setenv("MP_SECRET", "s")
        runner.invoke(
            app,
            [
                "account",
                "add",
                "a",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u",
                "--project",
                "3713224",
            ],
        )
        result = runner.invoke(app, ["session", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output.strip())
        # Contract §7: account is a structured {name, type, region} object
        # so callers can inspect type/region without a follow-up command.
        assert payload["account"]["name"] == "a"
        assert payload["account"]["type"] == "service_account"
        assert payload["account"]["region"] == "us"
        assert payload["project"]["id"] == "3713224"


class TestConfigCli:
    """``mp config`` does not exist as a CLI command group.

    A ``~/.mp/config.toml`` with unknown keys fails at the Pydantic
    validation layer with a generic-but-honest "unexpected key" error
    and the user is told to delete and re-add.
    """

    def test_no_mp_config_command(self, runner: CliRunner) -> None:
        """``mp config`` (or ``mp config convert``) → "No such command"."""
        result = runner.invoke(app, ["config", "convert"])
        assert result.exit_code != 0
        assert "no such command" in result.output.lower() or "config" in result.output


class TestGlobals:
    """The new global options behave as documented."""

    def test_target_with_account_exits(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--target`` combined with ``--account`` exits with code 3."""
        monkeypatch.setenv("MP_SECRET", "s")
        runner.invoke(
            app,
            [
                "account",
                "add",
                "a",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u",
                "--project",
                "3713224",
            ],
        )
        result = runner.invoke(
            app,
            ["--target", "ecom", "--account", "a", "session"],
        )
        assert result.exit_code == 3

    def test_target_with_project_exits(self, runner: CliRunner) -> None:
        """``--target`` combined with ``--project`` exits with code 3."""
        result = runner.invoke(
            app,
            ["--target", "ecom", "--project", "3018488", "session"],
        )
        assert result.exit_code == 3

    def test_workspace_global_accepted(self, runner: CliRunner) -> None:
        """``--workspace`` is accepted as a global override."""
        result = runner.invoke(app, ["--workspace", "42", "session"])
        assert result.exit_code == 0


class TestErrorRendering:
    """The ``handle_errors`` decorator must not Rich-eat ``[brackets]`` in messages."""

    def test_configerror_preserves_block_brackets_in_output(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """ConfigError messages containing ``[accounts.NAME]`` round-trip intact.

        The ConfigError raised when validating a malformed account block
        embeds ``[accounts.NAME]`` in its message. Rich would otherwise
        parse those brackets as markup tags and silently elide them,
        leaving users with ``Invalid  block:`` (note the double space) and
        no clue which block is bad. We must escape the message before
        handing it to the Rich console.
        """
        config_path = tmp_path / ".mp" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        # Legacy v2 account block — surfaces brackets in the error message.
        config_path.write_text(
            "[accounts.fake-shack]\n"
            'username = "u"\n'
            'secret = "s"\n'
            'project_id = "111"\n'
            'region = "us"\n',
            encoding="utf-8",
        )

        result = runner.invoke(app, ["account", "list"])

        assert result.exit_code != 0
        assert "[accounts.fake-shack]" in result.output
