"""Atomic on-disk write primitive, credential-read helpers, and bounded stdin reader.

Every persisted credential / config write goes through
:func:`atomic_write_bytes` so a SIGKILL or power loss between
``open()`` and ``rename()`` cannot leave a half-written file in place
of the prior good copy. The implementation uses ``O_EXCL`` (no
``umask`` handoff — process-global, not thread-safe) plus
``os.replace`` (POSIX-atomic same-filesystem rename).

Durability (``fsync``) is intentionally NOT performed: this helper
guarantees atomicity-on-success, not survival across power loss
mid-write. Adding ``fsync`` would cost 5–50 ms per CLI invocation
for no win in the realistic failure modes for a desktop CLI.

:func:`read_credential_bytes` / :func:`read_credential_text` are the
read-side mirror. On POSIX they open with ``O_NOFOLLOW`` so the
kernel refuses to traverse a symlink at the final path component,
then verify via ``fstat`` that the file mode is owner-only. Same-UID
symlink attacks (CI runners with shared ``$HOME``, container images
with shared mounts, compromised local tooling running as the user)
are the threat model — see :class:`CredentialPathError` for what
gets raised and the helper docstrings for what's deliberately out of
scope (hard links, intermediate-component symlinks under ``0o700``
ancestors, attacker-controlled ``$HOME``).

:func:`read_capped_secret_from_stdin` is the shared stdin reader for
service-account secrets and OAuth bearers. The cap rejects multi-MB
pastes (e.g. an SSH key piped by mistake) before the value reaches
the credential store.
"""

from __future__ import annotations

import errno
import os
import stat
import sys
import threading
from pathlib import Path

from mixpanel_headless.exceptions import ConfigError

__all__ = [
    "CredentialPathError",
    "atomic_write_bytes",
    "read_capped_secret_from_stdin",
    "read_credential_bytes",
    "read_credential_text",
]


SECRET_STDIN_MAX_BYTES = 64 * 1024
"""Hard ceiling on a single secret read from stdin.

Real service-account secrets are < 1 KiB and OAuth bearers are < 8 KiB.
A larger payload is almost always the wrong file being piped — a key
bundle, a JSON dump, a tarball. Reject loudly rather than silently
swallowing it into a credential field.
"""


def atomic_write_bytes(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    """Atomically write ``data`` to ``path`` with the requested file mode.

    Writes ``data`` to a sibling ``<name>.tmp.<pid>.<tid>`` path created
    via ``os.open(O_EXCL)``, then ``os.replace``s it onto ``path``. On
    POSIX, ``os.replace`` is atomic on the same filesystem — readers
    observe either the prior file or the new file, never a mix.

    The tmp filename embeds both the process ID and the OS thread ID so
    concurrent writers (threads or async tasks) within the same process
    pick distinct tmp paths and do not collide on the EXCL guard.

    On any failure between tmp creation and the rename, the tmp file is
    cleaned up and the original ``path`` is left untouched.

    Parent directories are NOT created — callers are responsible for
    ensuring ``path.parent`` exists with appropriate permissions.

    The tmp file is always created with mode ``0o600`` (owner-only)
    regardless of the requested ``mode`` — only the final file picks up
    ``mode`` via :func:`os.fchmod`. This guarantees the on-disk view is
    never wider than ``0o600`` for the brief window the tmp file exists,
    even if the caller asked for a more restrictive final mode like
    ``0o400``.

    Args:
        path: Destination file path. Will be created or replaced.
        data: Bytes to write.
        mode: POSIX file mode applied to the final file. Defaults to
            ``0o600`` (owner read/write only) — the right default for
            credential / config material. Must NOT grant any group or
            world bits (``mode & 0o077`` must be ``0``); this helper
            only ever writes credential-bearing files. Ignored on
            Windows where POSIX modes have no real-world effect.

    Raises:
        ValueError: If ``mode`` grants any group or world access (any
            bit in ``0o077`` is set). Defense-in-depth: every internal
            caller passes ``0o600``, but the API is private to
            ``_internal`` and a future caller asking for ``0o644``
            would silently leak a credential file.
        FileExistsError: If a stale tmp file from the same pid+tid is
            already present at the computed tmp path. The target is not
            touched.
        FileNotFoundError: If ``path.parent`` does not exist.
        OSError: If the underlying write or rename fails (disk full,
            permission denied, cross-device link, etc.).
    """
    if mode & 0o077:
        raise ValueError(
            f"atomic_write_bytes mode must not grant group/world access; "
            f"got {oct(mode)}"
        )
    tmp_path = path.parent / f"{path.name}.tmp.{os.getpid()}.{threading.get_ident()}"
    # Always create the tmp file owner-only (literal 0o600). The caller's
    # requested ``mode`` is applied via fchmod below, after we've validated
    # it and proved we own the fd. Passing a literal here keeps the
    # ``os.open`` mode statically bounded, which both makes intent obvious
    # and stops static analyzers from flagging this as overly permissive.
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        try:
            if hasattr(os, "fchmod"):
                os.fchmod(fd, mode)
            # ``os.write`` may return a short count on certain
            # filesystems / signal interruptions — loop until every
            # byte has been written so we never leave a truncated
            # config / token file in the rename path.
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                if written <= 0:  # pragma: no cover — POSIX guarantees > 0
                    raise OSError("os.write returned non-positive count")
                view = view[written:]
        finally:
            os.close(fd)
        os.replace(str(tmp_path), str(path))
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


class CredentialPathError(OSError):
    """Raised when a credential file fails a structural safety check.

    Subclass of :class:`OSError` so existing ``except OSError`` handlers
    at the credential call sites (``config.py``, ``bridge.py``,
    ``token_resolver.py``, ``storage.py``, ``me.py``) continue to catch
    it and translate to their domain exceptions (``ConfigError``,
    ``OAuthError``) without code changes. Call sites that want to
    distinguish a deliberate refusal (symlink, lax mode) from incidental
    I/O failure (missing file, EACCES on a legit file) can
    ``except CredentialPathError`` separately and log at WARNING — the
    silent-degradation sites in ``storage.py`` and ``me.py`` use this
    distinction so a symlink-attack signal isn't lost in a
    "corrupted cache, ignoring" path.
    """


def _open_credential_fd(path: Path) -> int:
    """Open ``path`` read-only, refusing to traverse a final-component symlink.

    On POSIX, uses ``os.open(O_RDONLY | O_NOFOLLOW)`` so the kernel
    surfaces ``ELOOP`` when the final component is a symlink. We catch
    that ``ELOOP`` and re-raise as :class:`CredentialPathError` with a
    message naming the path explicitly so logs don't show the bare
    "Too many levels of symbolic links" the kernel emits.

    On platforms without ``O_NOFOLLOW`` (Windows), falls back to
    :meth:`Path.is_symlink` before opening. TOCTOU-vulnerable in
    theory; not in the threat model.

    Args:
        path: File to open.

    Returns:
        The open file descriptor. Caller MUST close.

    Raises:
        CredentialPathError: The final path component is a symlink.
        FileNotFoundError: The path does not exist (non-symlink case).
        OSError: Any other open failure (EACCES, EISDIR, ...).
    """
    if hasattr(os, "O_NOFOLLOW"):
        try:
            return os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise CredentialPathError(
                    errno.ELOOP,
                    f"Refusing to read credential at symlink: {path}",
                    str(path),
                ) from exc
            raise
    # Windows fallback. The ``is_symlink`` check is TOCTOU-vulnerable —
    # an attacker could swap a regular file for a symlink between this
    # check and the open. Windows is not in the threat model for the
    # same-UID-attacker scenario (creating symlinks requires elevated
    # privileges or developer mode), so we accept the residual risk.
    if path.is_symlink():
        raise CredentialPathError(
            errno.ELOOP,
            f"Refusing to read credential at symlink: {path}",
            str(path),
        )
    return os.open(str(path), os.O_RDONLY)


def _enforce_owner_only_mode(fd: int, path: Path) -> None:
    """Raise ``CredentialPathError`` if the open file's mode has group/world bits.

    The check runs on ``fstat(fd)``, NOT a fresh ``path.stat()``. The fd
    pins the inode at the moment of open, so an attacker cannot swap
    the file out from under the check — there is no TOCTOU window.

    Skipped on platforms without :func:`os.fstat` mode semantics
    (Windows reports a stub mode).

    Args:
        fd: Open file descriptor.
        path: The path used at open time (for the error message only).

    Raises:
        CredentialPathError: Mode has any of the ``0o077`` bits set.
    """
    if not hasattr(os, "fchmod"):  # Windows proxy — no real POSIX mode.
        return
    file_mode = stat.S_IMODE(os.fstat(fd).st_mode)
    if file_mode & 0o077:
        raise CredentialPathError(
            errno.EPERM,
            (
                f"Refusing to read credential with mode {oct(file_mode)} "
                f"(group/world bits set): {path}"
            ),
            str(path),
        )


def read_credential_bytes(path: Path) -> bytes:
    """Read bytes from ``path`` while refusing symlinks and lax modes.

    POSIX: opens with ``O_NOFOLLOW`` so the kernel rejects a symlinked
    final component (``ELOOP``); then ``fstat``s the fd and rejects any
    file mode with the ``0o077`` bits set. Both rejections raise
    :class:`CredentialPathError` (an :class:`OSError` subclass).

    Out of scope:
        - Hard links. ``O_NOFOLLOW`` does not detect them. A hard-link
          attack requires write access to a directory in the target
          path AND read access to the target file, which is strictly
          stronger than the same-UID symlink threat we're defending.
        - Intermediate symlinks in ancestor paths. Ancestor dirs are
          managed at ``0o700`` by ``ensure_account_dir`` and
          ``_ensure_dir``, which excludes the insertion vector.
        - Attacker-controlled ``$HOME``. If :meth:`Path.home` itself
          is influenced (some CI setups override ``$HOME``), the leaf
          check is moot. That's a deployment posture, not an
          in-process check.

    Args:
        path: File to read.

    Returns:
        The file contents as bytes.

    Raises:
        CredentialPathError: ``path`` is a symlink, or the file mode
            has group/world bits set.
        FileNotFoundError: ``path`` does not exist (non-symlink case).
        OSError: Any other I/O failure (EACCES, EISDIR, ...).
    """
    fd = _open_credential_fd(path)
    try:
        _enforce_owner_only_mode(fd, path)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def read_credential_text(path: Path, *, encoding: str = "utf-8") -> str:
    """UTF-8 (by default) wrapper around :func:`read_credential_bytes`.

    Args:
        path: File to read.
        encoding: Text encoding. Defaults to ``utf-8``; every credential
            file in this codebase is UTF-8 by construction.

    Returns:
        Decoded file contents.

    Raises:
        CredentialPathError: ``path`` fails a structural safety check.
        UnicodeDecodeError: File bytes are not valid in ``encoding``.
        FileNotFoundError: ``path`` does not exist.
        OSError: Any other I/O failure.
    """
    return read_credential_bytes(path).decode(encoding)


def read_capped_secret_from_stdin() -> str:
    """Read a single secret value from stdin (up to ``SECRET_STDIN_MAX_BYTES``).

    Reads ALL bytes up to the cap, strips trailing whitespace (which
    ``pass``, ``cat``, ``echo`` typically append), and rejects payloads
    larger than the cap rather than returning a quietly-corrupted prefix.
    Used by ``mp account add --secret-stdin`` and the ``mp login``
    orchestrator's SA / oauth_token re-collection paths.

    Returns:
        The decoded secret string with surrounding whitespace stripped.

    Raises:
        ConfigError: When stdin is empty (``CONFIG_ERROR``) or exceeds
            ``SECRET_STDIN_MAX_BYTES`` (``CONFIG_ERROR`` with a hint to
            pipe a single secret rather than a key bundle). The CLI's
            ``@handle_errors`` decorator maps this to the standard
            ``CONFIG_ERROR`` exit code.
    """
    raw = sys.stdin.buffer.read(SECRET_STDIN_MAX_BYTES + 1)
    if len(raw) > SECRET_STDIN_MAX_BYTES:
        raise ConfigError(
            f"stdin payload exceeds {SECRET_STDIN_MAX_BYTES} bytes; "
            f"refusing to truncate. Pipe a single secret, not a key bundle."
        )
    value = raw.decode("utf-8", errors="strict").strip()
    if not value:
        raise ConfigError("Secret is empty (stdin read returned no content).")
    return value
