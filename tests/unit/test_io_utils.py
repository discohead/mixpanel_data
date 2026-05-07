"""Unit tests for the atomic-write helper and the stdin secret reader.

Tests :func:`mixpanel_headless._internal.io_utils.atomic_write_bytes`, the
foundation under all token / config writes that must survive a mid-write
crash without leaving the on-disk file in a partial state, and
:func:`read_capped_secret_from_stdin`, the bounded reader shared by
``mp account add --secret-stdin`` and the ``mp login`` orchestrator.

Verifies:
- Writes bytes to a fresh path with default 0o600 mode
- Writes bytes with a custom mode
- Atomically replaces existing file content
- Tmp file is cleaned up after a successful write
- Tmp file is cleaned up after a failed write (no leak)
- Failure during replace preserves the prior file content
- Replacing an existing file with looser perms resets to the requested mode
- O_EXCL prevents collision with a stale tmp from same pid+tid
- Empty payload still produces a file (not a missing one)
- Missing parent directory propagates a FileNotFoundError to the caller
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

import pytest

from mixpanel_headless._internal.io_utils import (
    SECRET_STDIN_MAX_BYTES,
    atomic_write_bytes,
    read_capped_secret_from_stdin,
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
    def test_writes_bytes_with_custom_mode(self, temp_dir: Path) -> None:
        """An explicit mode is honored on the final file."""
        target = temp_dir / "config.toml"
        atomic_write_bytes(target, b"x", mode=0o644)
        assert stat.S_IMODE(target.stat().st_mode) == 0o644

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
