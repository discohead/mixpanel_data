"""Unit tests for OAuth callback server (T017).

Tests the callback server that receives the OAuth authorization code
from the browser redirect during the PKCE flow.

Verifies:
- Binds to first available port in [19284-19287]
- Returns code+state from query params
- Validates state match
- Handles error params from provider
- Times out after configured duration
- Sends HTML response to browser
- Uses ``localhost`` in redirect URI
"""
# ruff: noqa: ARG001, ARG005

from __future__ import annotations

import contextlib
import threading
import time

import httpx
import pytest

from mixpanel_headless._internal.auth.callback_server import (
    CallbackResult,
    start_callback_server,
)
from mixpanel_headless.exceptions import OAuthError


class TestCallbackResult:
    """Tests for the CallbackResult frozen dataclass."""

    def test_fields_accessible(self) -> None:
        """Verify code and state fields are accessible on the frozen dataclass."""
        result = CallbackResult(code="abc123", state="xyz789")
        assert result.code == "abc123"
        assert result.state == "xyz789"

    def test_frozen(self) -> None:
        """Verify that CallbackResult is immutable (frozen dataclass)."""
        result = CallbackResult(code="abc", state="def")
        with pytest.raises(AttributeError):
            result.code = "new"  # type: ignore[misc]


class TestStartCallbackServer:
    """Tests for the start_callback_server function."""

    def test_returns_code_and_state_from_query_params(self) -> None:
        """Verify the server parses code and state from the redirect query params.

        Starts the server in a background thread, simulates a browser redirect
        with code and state query parameters, and checks the returned result.
        """
        state = "test-state-123"
        result_holder: list[tuple[CallbackResult, int]] = []
        error_holder: list[Exception] = []

        def run_server() -> None:
            """Run the callback server in a thread."""
            try:
                result = start_callback_server(state=state, timeout=10.0)
                result_holder.append(result)
            except Exception as exc:
                error_holder.append(exc)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        # Give the server time to bind
        time.sleep(0.3)

        # Simulate the OAuth redirect
        resp = httpx.get(
            "http://localhost:19284/callback",
            params={"code": "auth-code-456", "state": state},
            follow_redirects=False,
        )

        thread.join(timeout=5.0)
        assert not error_holder, f"Server raised: {error_holder[0]}"
        assert len(result_holder) == 1
        cb_result, port = result_holder[0]
        assert cb_result.code == "auth-code-456"
        assert cb_result.state == state
        assert port == 19284
        assert resp.status_code == 200

    def test_html_response_sent_to_browser(self) -> None:
        """Verify the server sends an HTML page back to the browser on success."""
        state = "html-test"
        result_holder: list[tuple[CallbackResult, int]] = []

        def run_server() -> None:
            """Run the callback server in a thread."""
            result_holder.append(start_callback_server(state=state, timeout=10.0))

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        time.sleep(0.3)

        resp = httpx.get(
            "http://localhost:19284/callback",
            params={"code": "code1", "state": state},
            follow_redirects=False,
        )

        thread.join(timeout=5.0)
        assert "text/html" in resp.headers.get("content-type", "")
        assert "success" in resp.text.lower() or "authorized" in resp.text.lower()

    def test_state_mismatch_raises_oauth_error(self) -> None:
        """Verify that a state mismatch causes OAuthError with OAUTH_TOKEN_ERROR code."""
        state = "expected-state"
        result_holder: list[tuple[CallbackResult, int]] = []
        error_holder: list[Exception] = []

        def run_server() -> None:
            """Run the callback server in a thread."""
            try:
                result_holder.append(start_callback_server(state=state, timeout=10.0))
            except Exception as exc:
                error_holder.append(exc)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        time.sleep(0.3)

        # Send mismatched state
        httpx.get(
            "http://localhost:19284/callback",
            params={"code": "code1", "state": "wrong-state"},
            follow_redirects=False,
        )

        thread.join(timeout=5.0)
        assert len(error_holder) == 1
        assert isinstance(error_holder[0], OAuthError)
        assert "state" in str(error_holder[0]).lower()

    def test_error_param_raises_oauth_error(self) -> None:
        """Verify that an error param from the provider raises OAuthError."""
        state = "error-test"
        error_holder: list[Exception] = []

        def run_server() -> None:
            """Run the callback server in a thread."""
            try:
                start_callback_server(state=state, timeout=10.0)
            except Exception as exc:
                error_holder.append(exc)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        time.sleep(0.3)

        httpx.get(
            "http://localhost:19284/callback",
            params={
                "error": "access_denied",
                "error_description": "User denied access",
            },
            follow_redirects=False,
        )

        thread.join(timeout=5.0)
        assert len(error_holder) == 1
        assert isinstance(error_holder[0], OAuthError)
        assert "access_denied" in str(error_holder[0])

    def test_timeout_raises_oauth_error(self) -> None:
        """Verify that exceeding the timeout raises OAuthError with OAUTH_TIMEOUT code."""
        state = "timeout-test"
        error_holder: list[Exception] = []

        def run_server() -> None:
            """Run the callback server in a thread."""
            try:
                start_callback_server(state=state, timeout=0.5)
            except Exception as exc:
                error_holder.append(exc)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        thread.join(timeout=5.0)

        assert len(error_holder) == 1
        err = error_holder[0]
        assert isinstance(err, OAuthError)
        assert err.code == "OAUTH_TIMEOUT"

    def test_tries_next_port_when_first_is_busy(self) -> None:
        """Verify the server tries ports 19284-19287 and uses the first available."""
        import socket

        # Occupy port 19284
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 19284))
        sock.listen(1)

        try:
            state = "port-fallback"
            result_holder: list[tuple[CallbackResult, int]] = []

            def run_server() -> None:
                """Run the callback server in a thread."""
                result_holder.append(start_callback_server(state=state, timeout=10.0))

            thread = threading.Thread(target=run_server, daemon=True)
            thread.start()
            time.sleep(0.3)

            # Must be on port 19285 since 19284 is occupied
            httpx.get(
                "http://localhost:19285/callback",
                params={"code": "fallback-code", "state": state},
                follow_redirects=False,
            )

            thread.join(timeout=5.0)
            assert len(result_holder) == 1
            cb_result, port = result_holder[0]
            assert port == 19285
            assert cb_result.code == "fallback-code"
        finally:
            sock.close()

    def test_all_ports_busy_raises_oauth_error(self) -> None:
        """Verify OAuthError with OAUTH_PORT_ERROR if all ports are occupied."""
        import socket

        socks: list[socket.socket] = []
        ports = [19284, 19285, 19286, 19287]
        try:
            for p in ports:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", p))
                s.listen(1)
                socks.append(s)

            with pytest.raises(OAuthError) as exc_info:
                start_callback_server(state="all-busy", timeout=5.0)
            assert exc_info.value.code == "OAUTH_PORT_ERROR"
        finally:
            for s in socks:
                s.close()

    def test_redirect_uri_uses_localhost(self) -> None:
        """Verify the redirect URI uses 'localhost' (not 127.0.0.1).

        OAuth providers require consistent redirect URIs. We use localhost
        for the redirect URI while binding to 127.0.0.1.
        """
        state = "localhost-test"
        result_holder: list[tuple[CallbackResult, int]] = []

        def run_server() -> None:
            """Run the callback server in a thread."""
            result_holder.append(start_callback_server(state=state, timeout=10.0))

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        time.sleep(0.3)

        # Use localhost (not 127.0.0.1) to match the redirect URI
        resp = httpx.get(
            "http://localhost:19284/callback",
            params={"code": "local-code", "state": state},
            follow_redirects=False,
        )

        thread.join(timeout=5.0)
        assert len(result_holder) == 1
        assert resp.status_code == 200


class TestCallbackHtmlSecurity:
    """Tests for HTML security in callback responses."""

    def test_state_mismatch_does_not_leak_expected_state(self) -> None:
        """Verify that the browser HTML does NOT contain the expected state value."""
        state = "secret-csrf-state-12345"
        response_holder: list[httpx.Response] = []

        def run_server() -> None:
            """Run the callback server in a thread."""
            with contextlib.suppress(OAuthError):
                start_callback_server(state=state, timeout=10.0)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        time.sleep(0.3)

        resp = httpx.get(
            "http://localhost:19284/callback",
            params={"code": "code1", "state": "wrong-state"},
            follow_redirects=False,
        )
        response_holder.append(resp)

        thread.join(timeout=5.0)
        html_body = resp.text
        # The expected state must NOT appear in the browser HTML
        assert state not in html_body
        # But the error page should still indicate a failure
        assert "Authorization" in html_body or "mismatch" in html_body

    def test_provider_error_description_is_html_escaped(self) -> None:
        """Verify that provider error_description is HTML-escaped in the response."""
        state = "escape-test"
        response_holder: list[httpx.Response] = []

        def run_server() -> None:
            """Run the callback server in a thread."""
            with contextlib.suppress(OAuthError):
                start_callback_server(state=state, timeout=10.0)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        time.sleep(0.3)

        xss_payload = '<script>alert("xss")</script>'
        resp = httpx.get(
            "http://localhost:19284/callback",
            params={
                "error": "server_error",
                "error_description": xss_payload,
            },
            follow_redirects=False,
        )
        response_holder.append(resp)

        thread.join(timeout=5.0)
        html_body = resp.text
        # Raw script tag must NOT appear in HTML — it should be escaped
        assert "<script>" not in html_body
        assert "&lt;script&gt;" in html_body
