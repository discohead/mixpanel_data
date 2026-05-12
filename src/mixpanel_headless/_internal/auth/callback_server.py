"""OAuth callback server for receiving authorization codes.

Implements a minimal HTTP server that listens for the OAuth 2.0 authorization
code redirect from the browser. The server binds to ``127.0.0.1`` on the first
available port in ``[19284, 19285, 19286, 19287]`` and waits for the
authorization server to redirect the browser with ``code`` and ``state``
query parameters.

Example:
    ```python
    from mixpanel_headless._internal.auth.callback_server import (
        CallbackResult,
        start_callback_server,
    )

    result, port = start_callback_server(state="random-state", timeout=300.0)
    print(f"Got code: {result.code} on port {port}")
    ```
"""

from __future__ import annotations

import html as html_mod
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from mixpanel_headless.exceptions import OAuthError

#: Ports to attempt binding to, in order.
CALLBACK_PORTS: list[int] = [19284, 19285, 19286, 19287]

_SUCCESS_HTML = """<!DOCTYPE html>
<html>
<head><title>Authorization Successful</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 2em;">
<h1>&#10004; Successfully Authorized</h1>
<p>You can close this browser tab and return to the terminal.</p>
</body>
</html>"""

_ERROR_HTML = """<!DOCTYPE html>
<html>
<head><title>Authorization Error</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 2em;">
<h1>&#10008; Authorization Error</h1>
<p>{message}</p>
<p>Please close this tab and try again.</p>
</body>
</html>"""


@dataclass(frozen=True)
class CallbackResult:
    """Immutable result from an OAuth authorization callback.

    Contains the authorization code and state parameter received from
    the OAuth provider's redirect.

    Attributes:
        code: The authorization code from the OAuth provider.
        state: The state parameter for CSRF validation.

    Example:
        ```python
        result = CallbackResult(code="abc123", state="xyz789")
        assert result.code == "abc123"
        ```
    """

    code: str
    """The authorization code from the OAuth provider."""

    state: str
    """The state parameter for CSRF validation."""


def start_callback_server(
    state: str,
    timeout: float = 300.0,
    port: int | None = None,
) -> tuple[CallbackResult, int]:
    """Start a local HTTP server to receive the OAuth callback.

    When ``port`` is provided, binds only to that specific port (no scanning).
    This avoids TOCTOU races when the caller has already probed for an
    available port. When ``port`` is ``None``, tries ports 19284-19287 on
    ``127.0.0.1`` in order. Once bound, the server waits for a single GET
    request containing ``code`` and ``state`` query parameters. The ``state``
    must match the provided value (CSRF protection). An HTML page is returned
    to the browser indicating success or failure.

    Args:
        state: The expected state parameter for CSRF validation.
        timeout: Maximum seconds to wait for the callback (default 300).
        port: Specific port to bind to. When provided, only this port is
            attempted and no scanning occurs. When ``None``, ports
            19284-19287 are tried in order.

    Returns:
        A tuple of ``(CallbackResult, port)`` where ``port`` is the bound port.

    Raises:
        OAuthError: If all ports are busy (``OAUTH_PORT_ERROR``), the
            requested port is unavailable, the callback times out
            (``OAUTH_TIMEOUT``), the state doesn't match, or the provider
            returns an error parameter.

    Example:
        ```python
        result, port = start_callback_server(state="my-state", timeout=60.0)
        redirect_uri = f"http://localhost:{port}/callback"
        ```
    """
    # Try to bind to the first available port
    server: HTTPServer | None = None
    bound_port: int = 0

    if port is not None:
        # Bind to the exact requested port — no scanning
        try:
            server = _create_server(port)
            bound_port = port
        except OSError as exc:
            raise OAuthError(
                f"OAuth callback port {port} is no longer available. "
                "Another process may have claimed it. Please try again.",
                code="OAUTH_PORT_ERROR",
                details={"port": port},
            ) from exc
    else:
        for candidate in CALLBACK_PORTS:
            try:
                server = _create_server(candidate)
                bound_port = candidate
                break
            except OSError:
                continue

    if server is None:
        raise OAuthError(
            "All OAuth callback ports (19284-19287) are busy. "
            "Close other applications using these ports and try again.",
            code="OAUTH_PORT_ERROR",
            details={"ports": CALLBACK_PORTS},
        )

    server.timeout = timeout

    # The handler stores results on the server instance
    handler_state: dict[str, Any] = {
        "result": None,
        "error": None,
    }
    # Attach to server so handler can access it
    server._handler_state = handler_state  # type: ignore[attr-defined]
    server._expected_state = state  # type: ignore[attr-defined]

    # Handle one request (blocking, with timeout)
    server.handle_request()
    server.server_close()

    error = handler_state.get("error")
    if error is not None:
        raise error

    result = handler_state.get("result")
    if result is None:
        raise OAuthError(
            f"OAuth callback timed out after {timeout} seconds. "
            "Please try again and complete the authorization in your browser.",
            code="OAUTH_TIMEOUT",
            details={"timeout_seconds": timeout},
        )

    return result, bound_port


def _create_server(port: int) -> HTTPServer:
    """Create an HTTPServer bound to the given port.

    Args:
        port: Port number to bind to on 127.0.0.1.

    Returns:
        Configured HTTPServer instance.

    Raises:
        OSError: If the port is already in use.
    """
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    return server


class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the OAuth callback redirect.

    Parses the authorization code and state from query parameters,
    validates the state, and sends an HTML response to the browser.
    """

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET request from OAuth redirect.

        Parses query parameters, validates state, and stores the result
        on the server's ``_handler_state`` dict.
        """
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        handler_state: dict[str, Any] = self.server._handler_state  # type: ignore[attr-defined]
        expected_state: str = self.server._expected_state  # type: ignore[attr-defined]

        # Check for error from provider
        error_param = params.get("error")
        if error_param:
            error_desc = params.get("error_description", [""])[0]
            error_code = error_param[0]
            message = f"OAuth provider returned error: {error_code}"
            if error_desc:
                message += f" - {error_desc}"

            # Escape provider-supplied values to prevent HTML injection
            self._send_html(
                _ERROR_HTML.format(message=html_mod.escape(message)),
                status=400,
            )
            handler_state["error"] = OAuthError(
                message,
                code="OAUTH_TOKEN_ERROR",
                details={"error": error_code, "error_description": error_desc},
            )
            return

        # Extract code and state
        code_list = params.get("code")
        state_list = params.get("state")

        if not code_list or not state_list:
            message = "Missing 'code' or 'state' parameter in callback"
            self._send_html(
                _ERROR_HTML.format(message=html_mod.escape(message)), status=400
            )
            handler_state["error"] = OAuthError(
                message,
                code="OAUTH_TOKEN_ERROR",
            )
            return

        received_state = state_list[0]
        if received_state != expected_state:
            # Don't leak the expected state to the browser — keep details
            # only in the server-side exception for debugging.
            browser_message = "State parameter mismatch. Authorization failed."
            self._send_html(
                _ERROR_HTML.format(message=html_mod.escape(browser_message)),
                status=400,
            )
            handler_state["error"] = OAuthError(
                "State mismatch: possible CSRF attack.",
                code="OAUTH_TOKEN_ERROR",
                details={
                    "expected_state": expected_state,
                    "received_state": received_state,
                },
            )
            return

        # Success
        self._send_html(_SUCCESS_HTML, status=200)
        handler_state["result"] = CallbackResult(
            code=code_list[0],
            state=received_state,
        )

    def _send_html(self, html: str, *, status: int = 200) -> None:
        """Send an HTML response to the browser.

        Args:
            html: HTML content to send.
            status: HTTP status code.
        """
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stderr logging from BaseHTTPRequestHandler.

        Args:
            format: Log format string (unused).
            *args: Log arguments (unused).
        """
        # Silence the default access log to avoid polluting terminal output
        pass
