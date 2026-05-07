"""LoC budget regression test for the v3 auth subsystem (T119, FR-067).

Keeps the auth subsystem from accumulating drift unbounded. Adding a
new auth file or a major code dump will fail this test, prompting the
PR author to either (a) justify the new ceiling or (b) refactor.

Scope (auth subsystem):
    - ``src/mixpanel_headless/_internal/auth/*.py`` (excluding ``__init__.py``)
    - ``src/mixpanel_headless/_internal/config.py``
    - ``src/mixpanel_headless/accounts.py`` — public auth namespace
      (added to scope post-043 after the orchestrator landed: the
      original budget excluded it on the assumption it stayed a thin
      facade, but the ``mp login`` orchestrator pushed it past 1500
      lines and the budget guard would otherwise miss further growth).
    - The five v3 CLI command groups:
      ``cli/commands/{account, project, workspace, target, session}.py``

Note: ``cli/commands/config_cmd.py`` was originally in scope but the
file was deleted along with ``mp config convert`` (Phase 10 dropped per
"alpha free to break").

The ``api_client.py`` file is intentionally OUT of scope: it has
accumulated 8000+ lines of entity-CRUD methods (dashboards / reports /
cohorts / flags / experiments / alerts / data governance) that have
nothing to do with auth. The original spec budget assumed an
api_client split that didn't happen and is out of scope here.

Current ballpark after the 043 rescue: 21 files / ~8,200 LoC.
Re-run ``wc -l`` against ``_auth_subsystem_files()`` to get a fresh
number; the budgets below carry ~7% headroom so a single cleanup
PR doesn't trip the test, but a substantial bloat does.
"""

from __future__ import annotations

import glob
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _auth_subsystem_files() -> list[Path]:
    """Return all files in scope for the auth-subsystem LoC budget."""
    auth_pkg = [
        Path(p)
        for p in glob.glob(str(REPO_ROOT / "src/mixpanel_headless/_internal/auth/*.py"))
        if not p.endswith("__init__.py")
    ]
    return sorted(
        [
            *auth_pkg,
            REPO_ROOT / "src/mixpanel_headless/_internal/config.py",
            REPO_ROOT / "src/mixpanel_headless/accounts.py",
            REPO_ROOT / "src/mixpanel_headless/cli/commands/account.py",
            REPO_ROOT / "src/mixpanel_headless/cli/commands/project.py",
            REPO_ROOT / "src/mixpanel_headless/cli/commands/workspace.py",
            REPO_ROOT / "src/mixpanel_headless/cli/commands/target.py",
            REPO_ROOT / "src/mixpanel_headless/cli/commands/session.py",
        ]
    )


class TestLocBudget:
    """FR-067: keep the auth subsystem within a defensible size envelope."""

    FILE_COUNT_CAP = 20
    """Maximum number of auth-subsystem files. A 21st file fails this test."""

    LOC_CAP = 8800
    """Maximum total LoC across the auth subsystem (~7% headroom over current).

    Bumped 6500 → 6700 → 8800 by 043 (frictionless-auth):
    - 6500 → 6700 covered the two new files
      (``_internal/auth/region_probe.py``, ``_internal/auth/naming.py``)
      plus the relaxations in ``cli/commands/account.py`` /
      ``_internal/config.py`` / ``_internal/me.py``.
    - 6700 → 8800 added ``accounts.py`` (1500+ lines after the
      ``login_unified`` orchestrator landed) to the scope so the
      orchestrator's growth is also guarded going forward.
    See ``specs/043-frictionless-auth/plan.md`` §"Scale/Scope" and the
    rescue plan at ``~/.claude/plans/thoroughly-and-rigorously-and-gentle-lemur.md``.
    """

    def test_file_count_cap(self) -> None:
        """No more than ``FILE_COUNT_CAP`` files comprise the auth subsystem."""
        files = _auth_subsystem_files()
        # Every listed file must exist; if not, the budget is stale.
        missing = [f for f in files if not f.exists()]
        assert not missing, f"Budget references missing files: {missing}"
        assert len(files) <= self.FILE_COUNT_CAP, (
            f"Auth subsystem grew to {len(files)} files (cap {self.FILE_COUNT_CAP}). "
            "Either justify raising the cap or refactor."
        )

    def test_total_loc_cap(self) -> None:
        """Total LoC stays under ``LOC_CAP`` across all auth-subsystem files."""
        files = _auth_subsystem_files()
        total = sum(
            len(f.read_text(encoding="utf-8").splitlines()) for f in files if f.exists()
        )
        assert total <= self.LOC_CAP, (
            f"Auth subsystem total LoC {total} exceeds budget {self.LOC_CAP}. "
            "Per-file breakdown:\n"
            + "\n".join(
                f"  {f.relative_to(REPO_ROOT)}: "
                f"{len(f.read_text(encoding='utf-8').splitlines())}"
                for f in files
                if f.exists()
            )
        )
