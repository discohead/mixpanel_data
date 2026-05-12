"""Regression tests for the two ``flow.py`` fixes shipped with the two-shot flow.

1. Default ``OAuthFlow().http_client`` timeout is bumped above httpx's 5s
   default so cold SOCKS5h handshakes (Cowork) succeed on first call.
2. Paste-reader event-queue race is fixed via ``threading.Event`` —
   errors from the paste reader propagate within milliseconds instead
   of waiting 310s for the callback timeout.
"""

from __future__ import annotations

import io
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from mixpanel_headless._internal.auth.flow import OAuthFlow
from mixpanel_headless._internal.auth.storage import OAuthStorage
from mixpanel_headless._internal.auth.token import OAuthClientInfo
from mixpanel_headless.exceptions import OAuthError


def _fake_dcr(
    http_client: Any, region: str, redirect_uri: str, storage: Any
) -> OAuthClientInfo:
    """Stub for ``ensure_client_registered`` — returns a canned client info."""
    del http_client, storage
    return OAuthClientInfo(
        client_id="test_client",
        region=region,
        redirect_uri=redirect_uri,
        scope="read",
        created_at=datetime.now(timezone.utc),
    )


class TestDefaultTimeoutBumped:
    """``OAuthFlow()._http_client.timeout`` must exceed httpx 5s default."""

    def test_default_read_timeout_at_least_10s(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Read timeout must be >= 10s — accommodates SOCKS handshake + slow /me."""
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))
        flow = OAuthFlow(region="us", storage=OAuthStorage())
        timeout = flow._http_client.timeout  # noqa: SLF001 — testing internal state
        assert timeout.read is not None
        assert timeout.read >= 10.0, f"Read timeout {timeout.read}s too short"

    def test_default_connect_timeout_at_least_5s(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Connect timeout must be >= 5s — DNS + TCP through SOCKS proxy."""
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))
        flow = OAuthFlow(region="us", storage=OAuthStorage())
        timeout = flow._http_client.timeout  # noqa: SLF001
        assert timeout.connect is not None
        assert timeout.connect >= 5.0, f"Connect timeout {timeout.connect}s too short"

    def test_explicit_http_client_passes_through(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Caller-supplied http_client is NOT replaced by the bumped default."""
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))
        custom = httpx.Client(timeout=httpx.Timeout(2.0))
        flow = OAuthFlow(region="us", storage=OAuthStorage(), http_client=custom)
        try:
            assert flow._http_client is custom  # noqa: SLF001
        finally:
            custom.close()


class TestPasteReaderRaceFix:
    """Paste-reader errors must propagate fast, not wait 310s for callback."""

    def test_empty_stdin_with_no_browser_raises_fast(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``open_browser=False`` + empty stdin → fast OAUTH_PASTE_ERROR.

        Pre-fix: paste reader put OAUTH_PASTE_ERROR into ``error_q``,
        but the main thread was blocked on ``result_q.get(timeout=310.0)``
        — so the user waited 5 minutes for a synchronous error to surface.
        Post-fix: ``threading.Event`` wakes the main thread within ms.
        """
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))

        # Force isatty() to return True so the paste reader thread starts.
        fake_stdin = io.StringIO("")
        fake_stdin.isatty = lambda: True  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", fake_stdin)

        from mixpanel_headless._internal.auth import flow as flow_mod

        def _blocking_callback_server(*args: Any, **kwargs: Any) -> Any:
            """Block past the test budget — forces paste reader to win."""
            del args, kwargs
            time.sleep(60)
            raise RuntimeError("unreachable")

        monkeypatch.setattr(
            flow_mod, "start_callback_server", _blocking_callback_server
        )
        monkeypatch.setattr(flow_mod, "ensure_client_registered", _fake_dcr)

        flow = OAuthFlow(region="us", storage=OAuthStorage())
        started = time.monotonic()
        with pytest.raises(OAuthError) as exc:
            flow.login(open_browser=False)
        elapsed = time.monotonic() - started

        assert elapsed < 5.0, f"Took {elapsed:.2f}s — race-fix regression?"
        assert exc.value.code in (
            "OAUTH_PASTE_ERROR",
            "OAUTH_TOKEN_ERROR",
        ), f"Got unexpected code: {exc.value.code}"

    def test_non_tty_stdin_skips_paste_reader(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Non-TTY stdin + ``open_browser=False`` skips the paste reader entirely."""
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))

        fake_stdin = io.StringIO("")
        fake_stdin.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", fake_stdin)

        from mixpanel_headless._internal.auth import flow as flow_mod

        callback_called = {"hit": False}

        def _quick_timeout_server(*args: Any, **kwargs: Any) -> Any:
            """Record being called, then raise quickly so the test resolves."""
            del args, kwargs
            callback_called["hit"] = True
            time.sleep(0.5)
            raise OAuthError("test timeout", code="OAUTH_TIMEOUT")

        monkeypatch.setattr(flow_mod, "start_callback_server", _quick_timeout_server)
        monkeypatch.setattr(flow_mod, "ensure_client_registered", _fake_dcr)

        flow = OAuthFlow(region="us", storage=OAuthStorage())
        with pytest.raises(OAuthError):
            flow.login(open_browser=False)
        assert callback_called["hit"]
