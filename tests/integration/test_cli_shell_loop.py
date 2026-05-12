"""CLI shell-loop iteration test (T080, US7).

Verifies that ``mp --project ID command...`` is a per-command override —
it does NOT mutate the persisted ``[active]`` block. This is the unix-style
composition contract: shell loops can iterate over project IDs without
leaving global state changed afterwards.

Reference: specs/042-auth-architecture-redesign/spec.md US7.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _mp(
    *args: str, env: dict[str, str], stdin: str | None = None
) -> tuple[int, str, str]:
    """Run ``mp`` (via ``uv run``) with ``args`` + ``env``; return (rc, stdout, stderr)."""
    result = subprocess.run(
        ["uv", "run", "mp", *args],
        capture_output=True,
        text=True,
        env=env,
        input=stdin,
        check=False,
        cwd=str(REPO_ROOT),
    )
    return result.returncode, result.stdout, result.stderr


@pytest.fixture
def cli_env(tmp_path: Path) -> Generator[dict[str, str], None, None]:
    """Tmp-home env with PATH preserved so ``uv`` resolves."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path),
        "MP_CONFIG_PATH": str(tmp_path / ".mp" / "config.toml"),
    }
    for key in ("VIRTUAL_ENV", "PYTHONUSERBASE", "PYTHONHOME"):
        if key in os.environ:
            env[key] = os.environ[key]
    yield env


class TestCliShellLoop:
    """``mp --project P <cmd>`` is per-command — does NOT mutate [active]."""

    def test_per_command_override_does_not_mutate_active(
        self,
        cli_env: dict[str, str],
        tmp_path: Path,
    ) -> None:
        """Issue several --project overrides and confirm [active] stays put."""
        # Seed: one account with default_project = "100"
        env = {**cli_env, "MP_SECRET": "secret"}
        rc, _, err = _mp(
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
            "100",
            env=env,
        )
        assert rc == 0, err

        # Capture initial active state. Contract §7: account is a
        # nested {name, type, region} object and project is a nested
        # {id, name, organization} object; parse the JSON instead of
        # substring-matching to be robust to formatting changes.
        rc, before_out, _ = _mp("session", "--format", "json", env=cli_env)
        assert rc == 0
        before_payload = json.loads(before_out)
        assert before_payload["account"]["name"] == "team"
        assert before_payload["project"]["id"] == "100"

        # Loop: per-command --project overrides, three different projects.
        # The global --project flag is wired into Workspace construction;
        # for the `session` command (which is config-only), it doesn't
        # change displayed output, but the command must still exit 0
        # — the override doesn't get rejected as invalid.
        for project_id in ("200", "300", "400"):
            rc, _out, err = _mp(
                "--project", project_id, "session", "--format", "json", env=cli_env
            )
            assert rc == 0, err

        # After the loop: [active] still shows the original project.
        rc, after_out, _ = _mp("session", "--format", "json", env=cli_env)
        assert rc == 0
        after_payload = json.loads(after_out)
        assert after_payload["account"]["name"] == "team"
        # Persisted default_project on the account is still 100.
        assert after_payload["project"]["id"] == "100"
        # And specifically NOT the override values.
        for stale in ("200", "300", "400"):
            assert after_payload["project"]["id"] != stale
