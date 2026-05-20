"""Unit tests for the atomic-write helper, credential-read helpers, and stdin reader.

Tests three pieces of :mod:`mixpanel_headless._internal.io_utils`:

* :func:`atomic_write_bytes` — the foundation under all token / config
  writes that must survive a mid-write crash without leaving the on-disk
  file in a partial state.
* :func:`read_credential_bytes` / :func:`read_credential_text` — the
  read-side mirror that refuses to traverse a symlink in the final
  path component (``O_NOFOLLOW`` on POSIX) and refuses to read files
  with group/world bits set. Surfaces structural failures as
  :class:`CredentialPathError` so silent-degradation call sites can
  log security-relevant rejections distinctly from generic I/O errors.
* :func:`read_capped_secret_from_stdin` — the bounded reader shared
  by ``mp account add --secret-stdin`` and the ``mp login`` orchestrator.

Verifies (writes):
- Writes bytes to a fresh path with default 0o600 mode
- Accepts owner-only restrictive modes (0o400, 0o600)
- Rejects modes that grant group/world access (0o644, 0o660, 0o604)
- Atomically replaces existing file content
- Tmp file is cleaned up after a successful write
- Tmp file is cleaned up after a failed write (no leak)
- Failure during replace preserves the prior file content
- Replacing an existing file with looser perms resets to the requested mode
- O_EXCL prevents collision with a stale tmp from same pid+tid
- Empty payload still produces a file (not a missing one)
- Missing parent directory propagates a FileNotFoundError to the caller

Verifies (reads):
- ``CredentialPathError`` is an ``OSError`` subclass (existing handlers keep working)
- Returns bytes from a plain 0o600 file
- Rejects a symlink whose target is attacker-controlled
- Rejects a symlink whose target is a legitimate owned 0o600 file
  (rejection is structural, not based on target metadata)
- Rejects a dangling symlink as the same error class (proves we fail at
  the symlink check, not at "file not found")
- Rejects files with any of the 0o077 mode bits set
- Accepts 0o400 and 0o600 modes
- ``FileNotFoundError`` for a missing non-symlink path propagates verbatim
- No fd leak across many rejections (symlink branch and mode branch)
- Text variant round-trips UTF-8 and raises UnicodeDecodeError on bad bytes

Verifies (stdin):
- Stdin reader returns whitespace-stripped value at the cap boundary
- Stdin reader rejects payloads exceeding the cap with ConfigError
- Stdin reader rejects empty / whitespace-only stdin with ConfigError
"""

from __future__ import annotations

import io
import os
import platform
import stat
import threading
from pathlib import Path
from unittest.mock import patch

import psutil
import pytest

from mixpanel_headless._internal.io_utils import (
    SECRET_STDIN_MAX_BYTES,
    CredentialPathError,
    atomic_write_bytes,
    read_capped_secret_from_stdin,
    read_credential_bytes,
    read_credential_text,
)
from mixpanel_headless.exceptions import ConfigError


def _tmp_glob(target: Path) -> list[Path]:
    """Return any leftover ``<name>.tmp.*`` siblings of ``target``.

    Args:
        target: The intended final path of the atomic write.

    Returns:
        Sorted list of leftover tmp paths in ``target.parent``.
    """
    return sorted(target.parent.glob(f"{target.name}.tmp.*"))


class TestAtomicWriteBytes:
    """Tests for :func:`atomic_write_bytes`."""

    def test_writes_bytes_with_default_mode(self, temp_dir: Path) -> None:
        """A new file is written with the requested content and 0o600 mode."""
        target = temp_dir / "config.toml"
        atomic_write_bytes(target, b"hello world")
        assert target.read_bytes() == b"hello world"
        if platform.system() != "Windows":
            assert stat.S_IMODE(target.stat().st_mode) == 0o600

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX file permissions not available on Windows",
    )
    def test_writes_bytes_with_owner_only_mode(self, temp_dir: Path) -> None:
        """A restrictive owner-only mode (0o400) is honored on the final file."""
        target = temp_dir / "config.toml"
        atomic_write_bytes(target, b"x", mode=0o400)
        assert stat.S_IMODE(target.stat().st_mode) == 0o400

    @pytest.mark.parametrize("bad_mode", [0o644, 0o660, 0o604, 0o666, 0o777])
    def test_rejects_group_or_world_bits(self, temp_dir: Path, bad_mode: int) -> None:
        """Modes granting group or world access are rejected before any I/O.

        Defense-in-depth: every internal caller passes 0o600, but the API
        is private to ``_internal`` and a future caller asking for 0o644
        would silently leak a credential file. The check fires at function
        entry, so no tmp file is created on rejection.
        """
        target = temp_dir / "config.toml"
        with pytest.raises(ValueError, match="group/world access"):
            atomic_write_bytes(target, b"x", mode=bad_mode)
        assert not target.exists()
        assert _tmp_glob(target) == []

    def test_replaces_existing_file_atomically(self, temp_dir: Path) -> None:
        """Writing to an existing path swaps content; old content is gone."""
        target = temp_dir / "config.toml"
        target.write_bytes(b"old")
        atomic_write_bytes(target, b"new")
        assert target.read_bytes() == b"new"

    def test_no_tmp_file_left_after_success(self, temp_dir: Path) -> None:
        """The tmp file is renamed away — no .tmp.* siblings remain."""
        target = temp_dir / "config.toml"
        atomic_write_bytes(target, b"x")
        assert _tmp_glob(target) == []

    def test_no_tmp_file_left_after_replace_failure(self, temp_dir: Path) -> None:
        """A failure during ``os.replace`` cleans up the tmp file."""
        target = temp_dir / "config.toml"
        with (
            patch(
                "mixpanel_headless._internal.io_utils.os.replace",
                side_effect=OSError("simulated"),
            ),
            pytest.raises(OSError, match="simulated"),
        ):
            atomic_write_bytes(target, b"x")
        assert _tmp_glob(target) == []
        assert not target.exists()

    def test_failure_preserves_existing_file(self, temp_dir: Path) -> None:
        """A failure mid-replace leaves the prior file content intact."""
        target = temp_dir / "config.toml"
        target.write_bytes(b"original")
        with (
            patch(
                "mixpanel_headless._internal.io_utils.os.replace",
                side_effect=OSError("simulated"),
            ),
            pytest.raises(OSError, match="simulated"),
        ):
            atomic_write_bytes(target, b"new")
        assert target.read_bytes() == b"original"
        assert _tmp_glob(target) == []

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX file permissions not available on Windows",
    )
    def test_replacing_existing_resets_mode(self, temp_dir: Path) -> None:
        """Replacing a 0o644 file results in the requested mode (0o600)."""
        target = temp_dir / "config.toml"
        target.write_bytes(b"old")
        target.chmod(0o644)
        atomic_write_bytes(target, b"new")
        assert stat.S_IMODE(target.stat().st_mode) == 0o600

    def test_excl_collision_does_not_touch_target(self, temp_dir: Path) -> None:
        """A stale tmp from the same pid+tid causes O_EXCL to refuse overwrite.

        The pre-existing target (if any) MUST remain untouched; the helper
        must not silently overwrite a stale tmp it didn't create.
        """
        target = temp_dir / "config.toml"
        target.write_bytes(b"original")
        # Pre-place the exact tmp path the helper will choose.
        stale_tmp = temp_dir / f"config.toml.tmp.{os.getpid()}.{threading.get_ident()}"
        stale_tmp.write_bytes(b"stale")
        with pytest.raises(FileExistsError):
            atomic_write_bytes(target, b"new")
        assert target.read_bytes() == b"original"

    def test_writes_empty_bytes(self, temp_dir: Path) -> None:
        """Writing zero bytes produces an empty file (not a missing one)."""
        target = temp_dir / "empty.toml"
        atomic_write_bytes(target, b"")
        assert target.exists()
        assert target.read_bytes() == b""

    def test_missing_parent_directory_raises(self, temp_dir: Path) -> None:
        """The helper does NOT create parent directories; caller's job."""
        target = temp_dir / "nonexistent" / "config.toml"
        with pytest.raises(FileNotFoundError):
            atomic_write_bytes(target, b"x")
        # No leak in the (existing) temp_dir either.
        assert list(temp_dir.glob("**/config.toml.tmp.*")) == []


class TestAtomicWriteResilience:
    """Resilience tests — the file is never observed in a partial state.

    These complement :class:`TestAtomicWriteBytes` by simulating realistic
    failure modes (mid-write, mid-rename, signal-style abort) and verifying
    the on-disk invariant: a reader either sees the prior file content or
    the new content — never a half-written hybrid.
    """

    def test_simulated_kill_between_write_and_replace_preserves_old(
        self, temp_dir: Path
    ) -> None:
        """If the process dies between ``os.write`` and ``os.replace`` the
        prior file content survives.

        We simulate the ``SIGKILL`` window by patching ``os.replace`` to
        raise ``KeyboardInterrupt`` (mimicking a delivered signal). The
        prior file content MUST still be readable, and no tmp file may
        leak — the caller could otherwise be tricked into believing the
        write succeeded by spotting the tmp.
        """
        target = temp_dir / "config.toml"
        target.write_bytes(b"OLD_CONTENT")
        with (
            patch(
                "mixpanel_headless._internal.io_utils.os.replace",
                side_effect=KeyboardInterrupt("simulated SIGKILL"),
            ),
            pytest.raises(KeyboardInterrupt),
        ):
            atomic_write_bytes(target, b"NEW_CONTENT")
        assert target.read_bytes() == b"OLD_CONTENT"
        assert _tmp_glob(target) == []

    def test_simulated_kill_during_write_preserves_old(self, temp_dir: Path) -> None:
        """A failure during ``os.write`` itself preserves the prior file.

        The tmp file may have been partially written, but the rename
        never happened, so the target is untouched. The half-written tmp
        is cleaned up so a future invocation doesn't trip on it.
        """
        target = temp_dir / "config.toml"
        target.write_bytes(b"OLD_CONTENT")
        with (
            patch(
                "mixpanel_headless._internal.io_utils.os.write",
                side_effect=OSError("disk full"),
            ),
            pytest.raises(OSError, match="disk full"),
        ):
            atomic_write_bytes(target, b"NEW_CONTENT")
        assert target.read_bytes() == b"OLD_CONTENT"
        assert _tmp_glob(target) == []

    def test_concurrent_writes_use_distinct_tmp_paths(self, temp_dir: Path) -> None:
        """Concurrent writers from different OS threads pick distinct tmp paths.

        The tmp filename embeds ``threading.get_ident()``, so two threads
        writing to the same target never collide on EXCL — each writes
        its own tmp and races to ``os.replace``. The "winner" is whichever
        rename runs last; both writers report success.
        """
        import threading

        target = temp_dir / "config.toml"
        results: list[BaseException | None] = [None, None]

        def write_a() -> None:
            try:
                atomic_write_bytes(target, b"A" * 1024)
            except BaseException as exc:  # pragma: no cover — defensive
                results[0] = exc

        def write_b() -> None:
            try:
                atomic_write_bytes(target, b"B" * 1024)
            except BaseException as exc:  # pragma: no cover — defensive
                results[1] = exc

        ta = threading.Thread(target=write_a)
        tb = threading.Thread(target=write_b)
        ta.start()
        tb.start()
        ta.join()
        tb.join()

        assert results == [None, None]
        # Final content is one of A's or B's; never a mix.
        final = target.read_bytes()
        assert final == b"A" * 1024 or final == b"B" * 1024
        assert _tmp_glob(target) == []


_POSIX_ONLY = pytest.mark.skipif(
    platform.system() == "Windows",
    reason="POSIX file permissions / O_NOFOLLOW semantics not available on Windows",
)


def _write_owner_only(path: Path, data: bytes) -> Path:
    """Write ``data`` to ``path`` and chmod it to 0o600.

    The cred-read helper rejects anything wider than 0o600. Many tests
    create fixture files via ``Path.write_bytes`` which honors the
    process umask (typically 0o644), so they'd fail the mode check
    before exercising the property under test. This helper makes the
    intent explicit: "a normal credential file at rest".
    """
    path.write_bytes(data)
    if platform.system() != "Windows":
        path.chmod(0o600)
    return path


class TestCredentialPathError:
    """Locks the contract that ``CredentialPathError`` is an ``OSError`` subclass."""

    def test_is_oserror_subclass(self) -> None:
        """Existing ``except OSError`` handlers MUST catch ``CredentialPathError``.

        The call sites in ``config.py``, ``bridge.py``, ``token_resolver.py``,
        ``storage.py``, and ``me.py`` already catch ``OSError`` and translate
        to domain exceptions. If ``CredentialPathError`` ever drifts out of
        that hierarchy, those handlers silently miss every symlink-attack
        rejection — exactly the failure mode we're trying to prevent.
        """
        assert issubclass(CredentialPathError, OSError)

    def test_carries_errno_and_path(self) -> None:
        """The exception preserves ``errno`` (for log triage) and the path."""
        exc = CredentialPathError(40, "symlink rejected", "/tmp/foo")
        assert exc.errno == 40
        assert exc.filename == "/tmp/foo"
        assert "symlink rejected" in str(exc)


class TestReadCredentialBytes:
    """Tests for :func:`read_credential_bytes`."""

    def test_reads_plain_owner_only_file(self, temp_dir: Path) -> None:
        """Happy path: a normal 0o600 file returns its bytes verbatim."""
        target = _write_owner_only(temp_dir / "creds.json", b'{"k":"v"}')
        assert read_credential_bytes(target) == b'{"k":"v"}'

    def test_reads_empty_file(self, temp_dir: Path) -> None:
        """An empty 0o600 file returns ``b''`` rather than raising."""
        target = _write_owner_only(temp_dir / "empty", b"")
        assert read_credential_bytes(target) == b""

    @_POSIX_ONLY
    def test_rejects_symlink_to_attacker_file(self, temp_dir: Path) -> None:
        """A symlink whose target is an attacker-controlled file is refused.

        This is the threat the security review flagged: an attacker with
        same-UID write access to ``/tmp`` plants ``/tmp/evil.json`` and
        symlinks the credential path to it. The kernel surfaces ``ELOOP``
        via ``O_NOFOLLOW``; we re-raise as ``CredentialPathError`` with
        the symlink path named in the message.
        """
        attacker = temp_dir / "attacker.json"
        _write_owner_only(attacker, b'{"stolen":"data"}')
        link = temp_dir / "creds.json"
        link.symlink_to(attacker)
        with pytest.raises(CredentialPathError, match="symlink"):
            read_credential_bytes(link)

    @_POSIX_ONLY
    def test_rejects_symlink_to_legitimate_owned_file(self, temp_dir: Path) -> None:
        """Rejection is structural — even a 0o600 owned target is refused.

        Proves the check fires on path shape, not on a heuristic about
        the target's metadata. A reader that "looks safe because the
        target file is owner-only" would still be exploitable: the
        attacker chooses the target file from whatever they can write,
        not from what passes a permission check.
        """
        legit = _write_owner_only(temp_dir / "legit.json", b'{"k":"v"}')
        assert stat.S_IMODE(legit.stat().st_mode) == 0o600
        link = temp_dir / "creds.json"
        link.symlink_to(legit)
        with pytest.raises(CredentialPathError, match="symlink"):
            read_credential_bytes(link)

    @_POSIX_ONLY
    def test_rejects_dangling_symlink(self, temp_dir: Path) -> None:
        """A symlink to a nonexistent target raises ``CredentialPathError``,
        not ``FileNotFoundError`` — proves we fail at the symlink check
        before any "does the target exist" lookup.
        """
        link = temp_dir / "creds.json"
        link.symlink_to(temp_dir / "nonexistent.json")
        with pytest.raises(CredentialPathError, match="symlink"):
            read_credential_bytes(link)

    @_POSIX_ONLY
    @pytest.mark.parametrize("bad_mode", [0o640, 0o660, 0o604, 0o644, 0o666, 0o777])
    def test_rejects_lax_mode(self, temp_dir: Path, bad_mode: int) -> None:
        """Any file with group or world bits set is refused.

        Defense-in-depth against an attacker who can write to the
        credential file directly (so ``O_NOFOLLOW`` is a no-op) but only
        with a lax mode — typically the case when umask was wrong during
        a manual edit. ``atomic_write_bytes`` already enforces 0o600 on
        the write side, so any lax-mode credential file in the wild
        is either tampering or a hand-edit.
        """
        target = temp_dir / "creds.json"
        target.write_bytes(b"x")
        target.chmod(bad_mode)
        with pytest.raises(CredentialPathError, match="mode"):
            read_credential_bytes(target)

    @_POSIX_ONLY
    @pytest.mark.parametrize("good_mode", [0o400, 0o600])
    def test_accepts_owner_only_modes(self, temp_dir: Path, good_mode: int) -> None:
        """0o400 (read-only) and 0o600 (read/write) both pass the mode check."""
        target = temp_dir / "creds.json"
        target.write_bytes(b"ok")
        target.chmod(good_mode)
        assert read_credential_bytes(target) == b"ok"

    def test_propagates_filenotfound(self, temp_dir: Path) -> None:
        """A missing non-symlink path raises ``FileNotFoundError``, NOT
        ``CredentialPathError`` — preserves the existing ``except OSError``
        control flow at call sites that check ``path.exists()`` first.
        """
        missing = temp_dir / "does-not-exist.json"
        with pytest.raises(FileNotFoundError):
            read_credential_bytes(missing)

    @_POSIX_ONLY
    def test_no_fd_leak_on_symlink_rejection(self, temp_dir: Path) -> None:
        """Many symlink rejections do not accumulate open file descriptors.

        The ``O_NOFOLLOW`` open fails before any fd is returned to us;
        the kernel cleans up. We verify by sampling ``Process.num_fds``
        before and after — any growth indicates a fd leak in the
        rejection path (e.g., if a future refactor opens a probe fd
        before the symlink check and forgets to close it).
        """
        link = temp_dir / "creds.json"
        link.symlink_to(temp_dir / "nonexistent.json")
        proc = psutil.Process()
        before = proc.num_fds()
        for _ in range(200):
            with pytest.raises(CredentialPathError):
                read_credential_bytes(link)
        after = proc.num_fds()
        # Allow a small slack for unrelated test infra (logging file
        # handlers, etc.) — a leak in our helper would show hundreds.
        assert after - before < 5, f"fd leak: {before} -> {after}"

    @_POSIX_ONLY
    def test_no_fd_leak_on_mode_rejection(self, temp_dir: Path) -> None:
        """The mode-check rejection path closes the fd before raising."""
        target = temp_dir / "creds.json"
        target.write_bytes(b"x")
        target.chmod(0o644)
        proc = psutil.Process()
        before = proc.num_fds()
        for _ in range(200):
            with pytest.raises(CredentialPathError):
                read_credential_bytes(target)
        after = proc.num_fds()
        assert after - before < 5, f"fd leak: {before} -> {after}"


class TestReadCredentialText:
    """Tests for :func:`read_credential_text` — UTF-8 wrapper over the bytes helper."""

    def test_reads_utf8(self, temp_dir: Path) -> None:
        """Happy path: UTF-8 round-trips."""
        target = _write_owner_only(temp_dir / "creds.toml", "café".encode())
        assert read_credential_text(target) == "café"

    def test_rejects_invalid_utf8(self, temp_dir: Path) -> None:
        """Invalid UTF-8 raises ``UnicodeDecodeError`` — preserves the
        existing call-site behavior in ``storage.py`` where the bare
        ``except (UnicodeDecodeError, ...)`` handler logs and returns None.
        """
        target = _write_owner_only(temp_dir / "creds.toml", b"\xff\xfe\xfd")
        with pytest.raises(UnicodeDecodeError):
            read_credential_text(target)

    @_POSIX_ONLY
    def test_rejects_symlink_same_as_bytes_variant(self, temp_dir: Path) -> None:
        """Delegation contract: the text wrapper inherits all structural checks."""
        target = _write_owner_only(temp_dir / "real.toml", b"x = 1")
        link = temp_dir / "creds.toml"
        link.symlink_to(target)
        with pytest.raises(CredentialPathError, match="symlink"):
            read_credential_text(link)


def _stub_stdin(monkeypatch: pytest.MonkeyPatch, payload: bytes) -> None:
    """Replace ``sys.stdin.buffer`` with a BytesIO carrying ``payload``."""
    import sys

    fake = io.BytesIO(payload)

    class _FakeStdin:
        buffer = fake

    monkeypatch.setattr(sys, "stdin", _FakeStdin())


class TestReadCappedSecretFromStdin:
    """Tests for :func:`read_capped_secret_from_stdin`."""

    def test_returns_stripped_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A normal piped secret is returned with surrounding whitespace stripped."""
        _stub_stdin(monkeypatch, b"  s3cret-value\n")
        assert read_capped_secret_from_stdin() == "s3cret-value"

    def test_accepts_payload_at_cap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A payload exactly at the cap is accepted (boundary check)."""
        payload = b"A" * SECRET_STDIN_MAX_BYTES
        _stub_stdin(monkeypatch, payload)
        result = read_capped_secret_from_stdin()
        assert len(result) == SECRET_STDIN_MAX_BYTES

    def test_rejects_payload_over_cap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A payload exceeding the cap raises ConfigError mentioning the limit."""
        _stub_stdin(monkeypatch, b"A" * (SECRET_STDIN_MAX_BYTES + 1))
        with pytest.raises(ConfigError) as exc_info:
            read_capped_secret_from_stdin()
        assert str(SECRET_STDIN_MAX_BYTES) in exc_info.value.message
        assert "key bundle" in exc_info.value.message

    def test_rejects_empty_stdin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An empty stdin raises ConfigError with the empty-secret message."""
        _stub_stdin(monkeypatch, b"")
        with pytest.raises(ConfigError) as exc_info:
            read_capped_secret_from_stdin()
        assert "empty" in exc_info.value.message.lower()

    def test_rejects_whitespace_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Whitespace-only stdin (newlines / tabs) is treated as empty."""
        _stub_stdin(monkeypatch, b"   \n\t\n")
        with pytest.raises(ConfigError):
            read_capped_secret_from_stdin()
