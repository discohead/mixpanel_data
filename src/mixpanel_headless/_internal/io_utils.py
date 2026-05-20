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
read-side mirror. On POSIX they walk every path component with
``openat(O_NOFOLLOW | O_CLOEXEC)`` so the kernel refuses to traverse
a symlink at any component (final OR intermediate). After open, the
fd is ``fstat``ed for three structural invariants: regular file
(rejects FIFOs/devices), owner-only mode (no group/world bits), and
size at most :data:`MAX_CREDENTIAL_BYTES`. Same-UID symlink attacks
(CI runners with shared ``$HOME``, container images with shared
mounts, compromised local tooling running as the user) are the
threat model — see :class:`CredentialPathError` for what gets raised
and the helper docstrings for what's deliberately out of scope (hard
links, attacker-controlled ``$HOME``).

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
    "MAX_CREDENTIAL_BYTES",
    "CredentialPathError",
    "atomic_write_bytes",
    "read_capped_secret_from_stdin",
    "read_credential_bytes",
    "read_credential_text",
    "reject_if_symlink",
]


SECRET_STDIN_MAX_BYTES = 64 * 1024
"""Hard ceiling on a single secret read from stdin.

Real service-account secrets are < 1 KiB and OAuth bearers are < 8 KiB.
A larger payload is almost always the wrong file being piped — a key
bundle, a JSON dump, a tarball. Reject loudly rather than silently
swallowing it into a credential field.
"""


MAX_CREDENTIAL_BYTES = 1 << 20
"""Hard ceiling on a credential file's size.

Realistic credential files in this codebase:

* ``config.toml`` — < 5 KB
* per-account ``tokens.json`` — < 2 KB
* per-region ``oauth/tokens_<region>.json`` and ``client_<region>.json`` — < 2 KB
* per-account ``me.json`` — < 10 KB
* Cowork bridge ``auth.json`` — < 5 KB

1 MiB is 100× the largest realistic file. Anything larger is either
a runaway write, a corrupted file, or an attacker-planted blob aimed
at OOM-ing the CLI. Reject before reading the bytes.
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


def reject_if_symlink(path: Path) -> None:
    """Raise :class:`CredentialPathError` if ``path`` itself is a symlink.

    Companion to :func:`read_credential_bytes` for call sites that check
    path existence (``Path.exists()``) before reading. ``Path.exists``
    follows symlinks and returns ``False`` for dangling links, so a
    dangling symlink at the credential path short-circuits the read
    helper entirely — the symlink-attack signal disappears.

    This helper restores the signal: ``lstat`` the path, raise if it's
    a symlink (dangling or live), return silently otherwise. Missing
    paths (``FileNotFoundError`` from ``lstat``) are intentionally a
    no-op — the existence check is the caller's concern.

    Args:
        path: Credential file path to probe.

    Raises:
        CredentialPathError: ``path`` is a symlink.
    """
    try:
        st = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(st.st_mode):
        raise CredentialPathError(
            errno.ELOOP,
            f"Refusing to read credential at symlink: {path}",
            str(path),
        )


_LEAF_OPEN_FLAGS = (
    (os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    if hasattr(os, "O_NOFOLLOW")
    else os.O_RDONLY
)
"""Flags used when opening the leaf component of a credential path.

``O_NOFOLLOW`` rejects a symlinked leaf with ``ELOOP``. ``O_CLOEXEC``
prevents a forked subprocess from inheriting the live credential fd.
``O_NONBLOCK`` prevents a FIFO-at-the-credential-path attack from
hanging the open (POSIX ignores ``O_NONBLOCK`` on regular files; we
clear it after open as hygiene).
"""

_DIR_OPEN_FLAGS = (
    (os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    if hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")
    else os.O_RDONLY
)
"""Flags used for every intermediate dirfd opened during the walk."""


def _open_credential_fd(path: Path) -> int:
    """Open ``path`` read-only with symlink defense scoped to the user's home tree.

    Threat model: a same-UID attacker can plant symlinks anywhere they
    have write access — practically, anywhere under :func:`Path.home`
    (or the configured ``MP_OAUTH_STORAGE_DIR`` / ``MP_CONFIG_PATH`` /
    ``MP_AUTH_FILE`` trees, if those env vars point inside their reach).
    Outside those trees, paths typically traverse system-owned dirs
    (``/var``, ``/private``, ``/Users``) that the user trusts the OS to
    have set up correctly.

    Strategy:

    * If ``path`` is under :func:`Path.home`: dirfd-walk from ``home``
      down to the leaf, with ``O_NOFOLLOW`` at every component. A
      symlink anywhere in the walk raises :class:`CredentialPathError`.
    * Otherwise: open the leaf only, with ``O_NOFOLLOW`` (same as the
      original PR's behavior). The user has explicitly configured an
      out-of-home credential path and accepts that intermediate-symlink
      defense doesn't apply there.

    The dirfd walk uses Python's ``os.open(part, ..., dir_fd=parent)``
    (``openat`` semantics). Each step is atomic w.r.t. the previously
    pinned dirfd, so the walk is TOCTOU-free.

    All opens — root, intermediate, and leaf — use ``O_CLOEXEC`` so
    no descendant subprocess can inherit a live credential fd.

    Windows fallback (no ``O_NOFOLLOW``): single :meth:`Path.is_symlink`
    probe before opening. TOCTOU-vulnerable in theory; not in the
    threat model.

    Args:
        path: File to open.

    Returns:
        The open file descriptor for the credential file. Caller MUST close.

    Raises:
        CredentialPathError: A component of the path (under home) is a
            symlink, or the leaf is a symlink.
        FileNotFoundError: A component does not exist.
        OSError: Any other open failure (EACCES, EISDIR, ...).
    """
    if not hasattr(os, "O_NOFOLLOW"):
        # Windows fallback.
        if path.is_symlink():
            raise CredentialPathError(
                errno.ELOOP,
                f"Refusing to read credential at symlink: {path}",
                str(path),
            )
        return os.open(str(path), os.O_RDONLY)

    abs_path = path if path.is_absolute() else Path.cwd() / path
    home = Path.home()
    try:
        relative_parts = abs_path.relative_to(home).parts
    except ValueError:
        # Path is outside HOME — out-of-tree configured path. Apply
        # leaf-only O_NOFOLLOW.
        return _open_leaf_only(abs_path)

    if not relative_parts:
        # ``abs_path`` IS the home dir — degenerate case (no credential
        # file lives there). Apply leaf-only and let the structural
        # checks downstream sort it out.
        return _open_leaf_only(abs_path)

    # Walk from HOME down with O_NOFOLLOW at every step.
    home_fd = os.open(str(home), os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    current_dirfd = home_fd
    try:
        for i, part in enumerate(relative_parts):
            is_leaf = i == len(relative_parts) - 1
            flags = _LEAF_OPEN_FLAGS if is_leaf else _DIR_OPEN_FLAGS
            try:
                next_fd = os.open(part, flags, dir_fd=current_dirfd)
            except OSError as exc:
                # Linux: O_NOFOLLOW on a symlink → ELOOP.
                # macOS: O_NOFOLLOW + O_DIRECTORY on a symlink → ENOTDIR
                # (the symlink itself isn't a directory file type, so the
                # O_DIRECTORY check fires before any symlink-resolution
                # logic). Verify via lstat before claiming "symlink".
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    bad_path = home / Path(*relative_parts[: i + 1])
                    try:
                        st = bad_path.lstat()
                    except FileNotFoundError:
                        raise
                    if stat.S_ISLNK(st.st_mode):
                        raise CredentialPathError(
                            errno.ELOOP,
                            (f"Refusing to read credential at symlink: {bad_path}"),
                            str(path),
                        ) from exc
                raise
            if is_leaf:
                os.close(current_dirfd)
                current_dirfd = -1
                return next_fd
            os.close(current_dirfd)
            current_dirfd = next_fd
        # Unreachable — the loop always returns when is_leaf is True.
        raise CredentialPathError(  # pragma: no cover
            errno.ENOENT, f"Path walk did not reach a leaf: {path}", str(path)
        )
    except BaseException:
        if current_dirfd != -1:
            os.close(current_dirfd)
        raise


def _open_leaf_only(path: Path) -> int:
    """Open ``path`` with ``O_NOFOLLOW`` on the leaf component only.

    Used when the path is outside :func:`Path.home` — typically an
    explicit env-var override (``MP_CONFIG_PATH``, ``MP_AUTH_FILE``,
    ``MP_OAUTH_STORAGE_DIR``) where the user has opted into a non-home
    location. Same protection level as the original PR.

    Args:
        path: File to open.

    Returns:
        The open file descriptor.

    Raises:
        CredentialPathError: The leaf component is a symlink.
        OSError: Any other open failure.
    """
    try:
        return os.open(str(path), _LEAF_OPEN_FLAGS)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise CredentialPathError(
                errno.ELOOP,
                f"Refusing to read credential at symlink: {path}",
                str(path),
            ) from exc
        raise


def _enforce_credential_file_invariants(fd: int, path: Path) -> None:
    """Raise :class:`CredentialPathError` if the open file fails any structural check.

    Three invariants, all evaluated against ``os.fstat(fd)`` (NOT a
    fresh ``path.stat()``). The fd pins the inode at the moment of
    open, so an attacker cannot swap the file out from under any of
    the checks — there is no TOCTOU window.

    1. Regular file (``S_ISREG``). Rejects FIFOs, devices, sockets,
       directories — anything an attacker might substitute to either
       hang the CLI (FIFO with no writer) or feed it an unbounded
       byte stream.
    2. Owner-only mode (no bits in ``0o077``). Rejects files with
       group or world read/write/execute permission.
    3. Size at most :data:`MAX_CREDENTIAL_BYTES`. Rejects oversized
       files that would OOM the read loop.

    Skipped on platforms without :func:`os.fstat` mode semantics
    (Windows reports a stub mode).

    Args:
        fd: Open file descriptor.
        path: The path used at open time (for the error message only).

    Raises:
        CredentialPathError: Any invariant fails.
    """
    if not hasattr(os, "fstat"):  # Windows proxy — no real POSIX stat.
        return
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        raise CredentialPathError(
            errno.EINVAL,
            f"Refusing to read credential: not a regular file: {path}",
            str(path),
        )
    file_mode = stat.S_IMODE(st.st_mode)
    if file_mode & 0o077:
        raise CredentialPathError(
            errno.EPERM,
            (
                f"Refusing to read credential with mode {oct(file_mode)} "
                f"(group/world bits set): {path}"
            ),
            str(path),
        )
    if st.st_size > MAX_CREDENTIAL_BYTES:
        raise CredentialPathError(
            errno.EFBIG,
            (
                f"Refusing to read credential: size {st.st_size} exceeds "
                f"cap {MAX_CREDENTIAL_BYTES}: {path}"
            ),
            str(path),
        )


def read_credential_bytes(path: Path) -> bytes:
    """Read bytes from ``path`` while refusing every known structural attack.

    POSIX: opens via :func:`_open_credential_fd` (dirfd-walked
    ``openat`` with ``O_NOFOLLOW`` at every component, plus
    ``O_CLOEXEC`` and ``O_NONBLOCK`` on the leaf), then enforces three
    invariants via :func:`_enforce_credential_file_invariants` (regular
    file, owner-only mode, size at most :data:`MAX_CREDENTIAL_BYTES`).
    Any failure raises :class:`CredentialPathError`.

    After the regular-file check passes, ``O_NONBLOCK`` is cleared on
    the fd via ``fcntl`` so the read loop has standard blocking
    semantics. (``O_NONBLOCK`` is ignored on regular files per POSIX,
    but clearing it is hygiene against future refactors that might
    swap the fd to something the flag matters for.)

    Out of scope:
        - Hard links. ``O_NOFOLLOW`` does not detect them. A hard-link
          attack requires write access to a directory in the target
          path AND read access to the target file, which is strictly
          stronger than the same-UID symlink threat we're defending.
        - Attacker-controlled ``$HOME``. If :meth:`Path.home` itself
          is influenced (some CI setups override ``$HOME``), the
          dirfd walk starts from a root chosen by the attacker. That's
          a deployment posture, not an in-process check.

    Args:
        path: File to read.

    Returns:
        The file contents as bytes.

    Raises:
        CredentialPathError: ``path`` (or any ancestor) is a symlink,
            the file is not regular, the mode has group/world bits,
            or the size exceeds :data:`MAX_CREDENTIAL_BYTES`.
        FileNotFoundError: A component of ``path`` does not exist.
        OSError: Any other I/O failure (EACCES, EISDIR, ...).
    """
    fd = _open_credential_fd(path)
    try:
        _enforce_credential_file_invariants(fd, path)
        # Clear O_NONBLOCK on the fd. POSIX ignores it on regular
        # files, but clearing keeps the fd's flag set tidy and avoids
        # surprises if a future refactor reads from a non-regular fd.
        if hasattr(os, "O_NONBLOCK"):
            import fcntl

            current = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, current & ~os.O_NONBLOCK)
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
