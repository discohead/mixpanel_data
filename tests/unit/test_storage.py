"""Unit tests for module-level storage helpers in :mod:`auth.storage`.

Covers:
- :func:`account_dir` rejects path-traversal-shaped names.
- :func:`account_dir` honors ``MP_OAUTH_STORAGE_DIR`` (Fix 7 symmetric root).
- :func:`_storage_root` resolves at call time (test isolation).
- :func:`ensure_account_dir` creates the dir with mode ``0o700``.
"""

from __future__ import annotations

import os
import platform
import stat
from pathlib import Path

import pytest

from mixpanel_headless._internal.auth.storage import (
    _storage_root,
    account_dir,
    ensure_account_dir,
)


class TestAccountDirNameValidation:
    """``account_dir`` defends against path-traversal-shaped account names."""

    @pytest.mark.parametrize(
        "malicious",
        [
            "../etc",
            "a/b",
            "a\x00b",
            "..",
            ".",
            "name with space",
            "",
            "/absolute",
            "../../escape",
            "name/with/slashes",
            "tab\there",
            "newline\nhere",
            "name?",
            "name*glob",
            "x" * 65,  # exceeds 64-char limit
        ],
    )
    def test_account_dir_rejects_invalid_names(self, malicious: str) -> None:
        """Each malicious name raises ``ValueError`` rather than expanding to a path."""
        with pytest.raises(ValueError):
            account_dir(malicious)

    @pytest.mark.parametrize(
        "valid",
        [
            "team",
            "personal",
            "user-name",
            "user_name",
            "abc123",
            "a",
            "X" * 64,  # exactly at the 64-char limit
            "MIXED_Case-123",
        ],
    )
    def test_account_dir_accepts_valid_names(
        self, valid: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Valid names round-trip into a child of ``<root>/accounts/``."""
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))
        result = account_dir(valid)
        assert result == tmp_path / "accounts" / valid


class TestStorageRoot:
    """``_storage_root`` honors ``MP_OAUTH_STORAGE_DIR`` and resolves lazily."""

    def test_env_var_overrides_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``MP_OAUTH_STORAGE_DIR`` takes precedence over ``$HOME/.mp``."""
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))
        assert _storage_root() == tmp_path

    def test_default_is_home_dot_mp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no env override, the root is ``$HOME/.mp``."""
        monkeypatch.delenv("MP_OAUTH_STORAGE_DIR", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        assert _storage_root() == tmp_path / ".mp"

    def test_resolves_lazily(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Setting the env var after import takes effect on the next call."""
        monkeypatch.delenv("MP_OAUTH_STORAGE_DIR", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        first = _storage_root()
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path / "alt"))
        second = _storage_root()
        assert first != second
        assert second == tmp_path / "alt"


class TestAccountDirHonorsStorageRoot:
    """``account_dir`` routes through ``_storage_root`` (Fix 7)."""

    def test_account_dir_under_env_var_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``MP_OAUTH_STORAGE_DIR=/tmp/x → account_dir('foo') = /tmp/x/accounts/foo/``."""
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path / "root"))
        assert account_dir("foo") == tmp_path / "root" / "accounts" / "foo"

    def test_account_dir_default_under_home_dot_mp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No env var → ``$HOME/.mp/accounts/foo/``."""
        monkeypatch.delenv("MP_OAUTH_STORAGE_DIR", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        assert account_dir("foo") == tmp_path / ".mp" / "accounts" / "foo"


class TestEnsureAccountDir:
    """``ensure_account_dir`` creates the per-account directory with mode 0o700."""

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX file permissions not available on Windows",
    )
    def test_creates_with_mode_0o700(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The created directory has mode ``0o700``."""
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))
        path = ensure_account_dir("foo")
        assert path.is_dir()
        assert stat.S_IMODE(path.stat().st_mode) == 0o700

    def test_idempotent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Calling twice does not raise; the directory persists."""
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))
        ensure_account_dir("foo")
        path = ensure_account_dir("foo")
        assert path.is_dir()

    def test_rejects_invalid_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invalid names propagate ``ValueError`` from :func:`account_dir`."""
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))
        with pytest.raises(ValueError):
            ensure_account_dir("../etc")


class TestOAuthStorageSymlinkRejection:
    """``OAuthStorage._read_file`` refuses symlinks; ``_check_and_fix_permissions``
    refuses to chmod through them.

    Regression for the same-UID symlink attack. The read path uses
    :func:`read_credential_text`, which raises
    :class:`CredentialPathError`; the silent-degradation contract
    (``_read_file`` returns ``None`` and logs WARNING) is preserved so
    a re-fetch still happens — but the rejection is now visible in logs.

    The chmod path is independently dangerous: today
    ``_check_and_fix_permissions`` does ``path.stat()`` (follows symlink)
    + ``path.chmod()`` (chmods the target), so an attacker who plants
    a 0o644 file gets it tightened to 0o600 just before the read. The
    fix uses ``lstat()`` and bails on symlinks — we assert the target
    file's mode is left untouched.
    """

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX symlink + mode semantics required",
    )
    def test_read_symlinked_tokens_returns_none_and_warns(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A symlinked tokens file is refused; ``_read_file`` returns None + WARNING."""
        import logging

        from mixpanel_headless._internal.auth.storage import OAuthStorage

        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))
        attacker = tmp_path / "attacker.json"
        attacker.write_text('{"access_token":"stolen"}', encoding="utf-8")
        attacker.chmod(0o600)
        storage = OAuthStorage()
        storage._ensure_dir()
        target = storage._tokens_path("us")
        target.symlink_to(attacker)

        caplog.set_level(logging.WARNING)
        result = storage.load_tokens("us")
        assert result is None
        assert any(
            "symlink" in rec.message.lower() or "refusing" in rec.message.lower()
            for rec in caplog.records
        ), f"expected WARNING log mentioning symlink/refusing, got: {caplog.text}"

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX symlink + mode semantics required",
    )
    def test_check_and_fix_permissions_does_not_chmod_through_symlink(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The buggy chmod-through-symlink primitive is killed.

        Before the fix: ``_check_and_fix_permissions`` followed the
        symlink and chmodded the target to 0o600, silently tightening
        the attacker's file right before the (then-unsafe) read.

        After: ``lstat`` detects the symlink, logs a warning, and
        leaves the target file's mode untouched.
        """
        from mixpanel_headless._internal.auth.storage import OAuthStorage

        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))
        attacker = tmp_path / "attacker.json"
        attacker.write_text("x", encoding="utf-8")
        attacker.chmod(0o644)
        original_mode = stat.S_IMODE(attacker.stat().st_mode)
        assert original_mode == 0o644

        storage = OAuthStorage()
        storage._ensure_dir()
        target = storage._tokens_path("us")
        target.symlink_to(attacker)

        storage._check_and_fix_permissions(target)
        # Target file mode unchanged — no chmod side effect via the symlink.
        assert stat.S_IMODE(attacker.stat().st_mode) == original_mode

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX symlink + mode semantics required",
    )
    def test_dangling_symlink_returns_none_and_warns(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Dangling symlink at the credential path is refused with WARNING."""
        import logging

        from mixpanel_headless._internal.auth.storage import OAuthStorage

        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))
        storage = OAuthStorage()
        storage._ensure_dir()
        target = storage._tokens_path("us")
        target.symlink_to(tmp_path / "missing.json")

        caplog.set_level(logging.WARNING)
        result = storage.load_tokens("us")
        assert result is None
        assert any(
            "symlink" in rec.message.lower() or "refusing" in rec.message.lower()
            for rec in caplog.records
        ), f"expected WARNING log mentioning symlink/refusing, got: {caplog.text}"

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX symlink + mode semantics required",
    )
    def test_check_and_fix_permissions_uses_fchmod_not_chmod(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The chmod-through-symlink TOCTOU is closed via open+fchmod.

        Confirm by patching ``Path.chmod`` to fail loudly — if the code
        still reaches it, the test fails. The fchmod-on-fd path doesn't
        go through ``Path.chmod``.
        """
        from unittest.mock import patch

        from mixpanel_headless._internal.auth.storage import OAuthStorage

        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))
        storage = OAuthStorage()
        storage._ensure_dir()
        target = storage._tokens_path("us")
        target.write_text("{}", encoding="utf-8")
        target.chmod(0o644)  # set up lax mode to trigger the repair path

        with patch.object(
            Path, "chmod", side_effect=AssertionError("Path.chmod called!")
        ):
            # _check_and_fix_permissions must NOT call Path.chmod anywhere.
            storage._check_and_fix_permissions(target)
        # Verify the file was actually chmodded via the fchmod path.
        assert stat.S_IMODE(target.stat().st_mode) == 0o600

    def test_windows_skip_does_not_crash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On platforms without ``os.O_NOFOLLOW`` or ``os.fchmod``,
        ``_check_and_fix_permissions`` is a no-op rather than an
        ``AttributeError`` crash.

        Regression: an earlier revision of the SEC-331 follow-up
        used ``os.O_NOFOLLOW | os.O_DIRECTORY`` at the call site,
        which evaluated at construction time. On Windows that raises
        ``AttributeError`` before the function body runs. We simulate
        the platform via ``monkeypatch.delattr`` so the test exercises
        the same code path that would run on a real Windows interpreter.
        """
        from mixpanel_headless._internal.auth.storage import OAuthStorage

        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))
        storage = OAuthStorage()
        storage._ensure_dir()
        target = storage._tokens_path("us")
        target.write_text("{}", encoding="utf-8")
        # Pretend O_NOFOLLOW doesn't exist (Windows posture).
        monkeypatch.delattr(os, "O_NOFOLLOW", raising=False)
        # Must not raise.
        storage._check_and_fix_permissions(target)
