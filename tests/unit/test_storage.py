"""Unit tests for module-level storage helpers in :mod:`auth.storage`.

Covers:
- :func:`account_dir` rejects path-traversal-shaped names.
- :func:`account_dir` honors ``MP_OAUTH_STORAGE_DIR`` (Fix 7 symmetric root).
- :func:`_storage_root` resolves at call time (test isolation).
- :func:`ensure_account_dir` creates the dir with mode ``0o700``.
"""

from __future__ import annotations

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
