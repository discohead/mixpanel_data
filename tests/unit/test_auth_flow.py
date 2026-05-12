"""Unit tests for OAuthFlow orchestrator (T019).

Tests the OAuthFlow class which orchestrates the full OAuth 2.0 PKCE
authorization flow for Mixpanel.

Verifies:
- Full login sequence (mock all external deps)
- Token exchange POST with correct form params
- Handles missing refresh_token
- Preserves project_id through flow
- Region-specific OAuth base URLs (us/eu/in)
"""
# ruff: noqa: ARG001, ARG005

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import SecretStr

from mixpanel_headless._internal.auth.callback_server import CallbackResult
from mixpanel_headless._internal.auth.flow import OAuthFlow, _parse_pasted_redirect
from mixpanel_headless._internal.auth.storage import OAuthStorage
from mixpanel_headless._internal.auth.token import OAuthClientInfo, OAuthTokens
from mixpanel_headless.exceptions import OAuthError


def _make_token_response(
    *,
    access_token: str = "access-tok-123",
    refresh_token: str | None = "refresh-tok-456",
    expires_in: int = 3600,
    scope: str = "projects analysis",
    token_type: str = "Bearer",
) -> dict[str, object]:
    """Create a mock token endpoint response dict.

    Args:
        access_token: Access token value.
        refresh_token: Refresh token value, or None to omit.
        expires_in: Token lifetime in seconds.
        scope: Granted scopes.
        token_type: Token type string.

    Returns:
        Dictionary matching the OAuth token endpoint response shape.
    """
    data: dict[str, object] = {
        "access_token": access_token,
        "expires_in": expires_in,
        "scope": scope,
        "token_type": token_type,
    }
    if refresh_token is not None:
        data["refresh_token"] = refresh_token
    return data


def _make_client_info(
    *,
    client_id: str = "test-client-id",
    region: str = "us",
    redirect_uri: str = "http://localhost:19284/callback",
) -> OAuthClientInfo:
    """Create an OAuthClientInfo fixture.

    Args:
        client_id: Client identifier.
        region: Mixpanel region.
        redirect_uri: Registered redirect URI.

    Returns:
        Configured OAuthClientInfo instance.
    """
    return OAuthClientInfo(
        client_id=client_id,
        region=region,
        redirect_uri=redirect_uri,
        scope="projects analysis",
        created_at=datetime.now(timezone.utc),
    )


class TestOAuthFlowLogin:
    """Tests for OAuthFlow.login() full sequence."""

    @patch("mixpanel_headless._internal.auth.flow.webbrowser")
    @patch("mixpanel_headless._internal.auth.flow.start_callback_server")
    @patch("mixpanel_headless._internal.auth.flow.ensure_client_registered")
    def test_full_login_sequence(
        self,
        mock_register: MagicMock,
        mock_callback: MagicMock,
        mock_browser: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verify the full login flow: register -> browser -> callback -> exchange.

        Mocks client registration, callback server, browser open, and token exchange.
        """
        # Setup mocks
        client_info = _make_client_info()
        mock_register.return_value = client_info
        mock_callback.return_value = (
            CallbackResult(code="auth-code-xyz", state="any"),
            19284,
        )
        mock_browser.open.return_value = True

        token_response = _make_token_response()

        def handle_request(request: httpx.Request) -> httpx.Response:
            """Handle token exchange request.

            Args:
                request: The incoming HTTP request.

            Returns:
                Mock token response.
            """
            return httpx.Response(200, json=token_response)

        transport = httpx.MockTransport(handle_request)
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        tokens = flow.login()

        assert tokens.access_token.get_secret_value() == "access-tok-123"
        assert tokens.refresh_token is not None
        assert tokens.refresh_token.get_secret_value() == "refresh-tok-456"
        mock_browser.open.assert_called_once()

    # test_preserves_project_id removed in B2 (T044): the legacy
    # ``OAuthTokens.project_id`` field is gone; ``OAuthFlow.login`` no
    # longer accepts a ``project_id`` kwarg. Project ID lives on
    # ``Account.default_project`` in v3.

    @patch("mixpanel_headless._internal.auth.flow.webbrowser")
    @patch("mixpanel_headless._internal.auth.flow.start_callback_server")
    @patch("mixpanel_headless._internal.auth.flow.ensure_client_registered")
    def test_handles_missing_refresh_token(
        self,
        mock_register: MagicMock,
        mock_callback: MagicMock,
        mock_browser: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verify login succeeds when the token response has no refresh_token."""
        mock_register.return_value = _make_client_info()
        mock_callback.return_value = (
            CallbackResult(code="code1", state="s"),
            19284,
        )
        mock_browser.open.return_value = True

        token_resp = _make_token_response(refresh_token=None)
        transport = httpx.MockTransport(
            lambda _req: httpx.Response(200, json=token_resp)
        )
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        tokens = flow.login()

        assert tokens.access_token.get_secret_value() == "access-tok-123"
        assert tokens.refresh_token is None

    @patch("mixpanel_headless._internal.auth.flow.webbrowser")
    @patch("mixpanel_headless._internal.auth.flow.start_callback_server")
    @patch("mixpanel_headless._internal.auth.flow.ensure_client_registered")
    def test_open_browser_false_skips_webbrowser_and_prints_url(
        self,
        mock_register: MagicMock,
        mock_callback: MagicMock,
        mock_browser: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``login(open_browser=False)`` MUST NOT call webbrowser.open.

        The authorize URL must be printed to stderr instead so headless
        / SSH callers (and the documented ``mp account login --no-browser``
        flag) can copy it manually.
        """
        mock_register.return_value = _make_client_info()
        mock_callback.return_value = (
            CallbackResult(code="code1", state="s"),
            19284,
        )

        token_resp = _make_token_response()
        transport = httpx.MockTransport(
            lambda _req: httpx.Response(200, json=token_resp)
        )
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        flow.login(open_browser=False)

        mock_browser.open.assert_not_called()
        captured = capsys.readouterr()
        assert "Open this URL in your browser" in captured.err
        # Authorize URL is for the configured region's OAuth host.
        assert "https://" in captured.err


class TestParsePastedRedirect:
    """Unit tests for the ``--no-browser`` paste parser."""

    def test_full_redirect_url(self) -> None:
        """A full ``http://localhost:.../callback?code=&state=`` URL parses cleanly."""
        result = _parse_pasted_redirect(
            "http://localhost:19284/callback?code=ABC&state=XYZ",
            expected_state="XYZ",
        )
        assert result.code == "ABC"
        assert result.state == "XYZ"

    def test_query_string_only(self) -> None:
        """A bare ``code=...&state=...`` (no leading ``?`` or URL) parses cleanly."""
        result = _parse_pasted_redirect("code=ABC&state=XYZ", expected_state="XYZ")
        assert result.code == "ABC"

    def test_query_string_with_leading_question_mark(self) -> None:
        """A pasted ``?code=...&state=...`` (browser address-bar fragment) works."""
        result = _parse_pasted_redirect("?code=ABC&state=XYZ", expected_state="XYZ")
        assert result.code == "ABC"

    def test_whitespace_is_stripped(self) -> None:
        """Leading / trailing whitespace from the paste is ignored."""
        result = _parse_pasted_redirect(
            "  http://localhost:19284/callback?code=ABC&state=XYZ\n",
            expected_state="XYZ",
        )
        assert result.code == "ABC"

    def test_empty_paste_raises(self) -> None:
        """An empty paste surfaces a clear error."""
        with pytest.raises(OAuthError, match="Empty paste"):
            _parse_pasted_redirect("   \n", expected_state="XYZ")

    def test_state_mismatch_raises(self) -> None:
        """A pasted state that doesn't match the session is rejected (CSRF).

        Without this check a hostile party could trick the user into pasting
        an attacker-generated code.
        """
        with pytest.raises(OAuthError, match="State mismatch"):
            _parse_pasted_redirect("code=ABC&state=ATTACKER", expected_state="XYZ")

    def test_missing_code_raises(self) -> None:
        """``state=`` without ``code=`` is unparseable."""
        with pytest.raises(OAuthError, match="missing `code` or `state`"):
            _parse_pasted_redirect("state=XYZ", expected_state="XYZ")

    def test_missing_state_raises(self) -> None:
        """``code=`` without ``state=`` is unparseable (CSRF guard)."""
        with pytest.raises(OAuthError, match="missing `code` or `state`"):
            _parse_pasted_redirect("code=ABC", expected_state="XYZ")

    def test_oauth_error_param_surfaces(self) -> None:
        """A redirect with ``?error=...`` (user denied / etc.) surfaces the error."""
        with pytest.raises(OAuthError, match="access_denied"):
            _parse_pasted_redirect(
                "http://localhost:19284/callback?error=access_denied&state=XYZ",
                expected_state="XYZ",
            )

    def test_oauth_error_with_description_includes_description(self) -> None:
        """``error_description`` is appended to the surfaced error message."""
        with pytest.raises(OAuthError, match="user cancelled"):
            _parse_pasted_redirect(
                "?error=access_denied&error_description=user+cancelled&state=XYZ",
                expected_state="XYZ",
            )


class TestOAuthFlowPasteFallback:
    """``OAuthFlow.login(open_browser=False)`` accepts a pasted redirect URL.

    Mixpanel's ``redirect_uri_allowed`` (in ``webapp/oauth/models.py``)
    permits any ``http://localhost:<port>/`` URL, so the OAuth provider
    issues a normal redirect even when no local server is listening on
    the bound port. The user copies the URL from the failed-to-load tab
    and pastes it back to the still-running CLI process.
    """

    @patch("mixpanel_headless._internal.auth.flow.webbrowser")
    @patch("mixpanel_headless._internal.auth.flow.start_callback_server")
    @patch("mixpanel_headless._internal.auth.flow.ensure_client_registered")
    def test_paste_fallback_succeeds_when_callback_blocked(
        self,
        mock_register: MagicMock,
        mock_callback: MagicMock,
        mock_browser: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """A successful paste produces tokens even if the local callback never fires.

        Stub ``start_callback_server`` to block past the test's lifetime
        so the paste path is the only one that completes — proves the
        race resolves on whichever completer wins, not on the callback
        always firing first.
        """
        import threading

        mock_register.return_value = _make_client_info()

        # Block the callback "indefinitely" — daemon thread will be torn
        # down when the test process exits.
        block_forever = threading.Event()

        def _blocked_callback(*args: object, **kwargs: object) -> object:
            block_forever.wait(timeout=60.0)
            raise OAuthError("test: callback never fires")

        mock_callback.side_effect = _blocked_callback

        # Drive stdin via monkeypatch so the paste reader sees the redirect URL.
        # Use the actual generated state by hooking into PkceChallenge / state
        # generation: simplest approach is to capture the authorize URL and
        # extract state from it.
        captured_state: list[str] = []
        original_build = OAuthFlow._build_authorize_url

        def _capturing_build(self: object, **kw: object) -> str:
            captured_state.append(str(kw["state"]))
            return original_build(self, **kw)  # type: ignore[arg-type]

        monkeypatch.setattr(OAuthFlow, "_build_authorize_url", _capturing_build)

        # Provide a stdin that yields the redirect URL once state is known.
        # The paste reader thread reads via sys.stdin.readline(), so we need
        # to stub sys.stdin in the flow module.
        class _DeferredStdin:
            """Stdin that blocks until state is captured, then emits the URL."""

            def readline(self) -> str:
                # Wait for the authorize URL build (which captures state).
                for _ in range(200):
                    if captured_state:
                        break
                    time.sleep(0.01)
                state = captured_state[0]
                return (
                    f"http://localhost:19284/callback?code=PASTED_CODE&state={state}\n"
                )

        import sys
        import time

        monkeypatch.setattr(sys, "stdin", _DeferredStdin())

        token_resp = _make_token_response(access_token="from-paste")
        captured_form: list[bytes] = []

        def _handle(request: httpx.Request) -> httpx.Response:
            captured_form.append(request.content)
            return httpx.Response(200, json=token_resp)

        http_client = httpx.Client(transport=httpx.MockTransport(_handle))
        storage = OAuthStorage(storage_dir=tmp_path)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        tokens = flow.login(open_browser=False)

        assert tokens.access_token.get_secret_value() == "from-paste"
        # The token-exchange POST must include the pasted code.
        assert b"code=PASTED_CODE" in captured_form[0]
        mock_browser.open.assert_not_called()

        # Allow the blocked callback thread to exit cleanly.
        block_forever.set()


class TestOAuthFlowTokenExchange:
    """Tests for the token exchange step."""

    def test_exchange_posts_correct_form_params(self, tmp_path: Path) -> None:
        """Verify the token exchange POST contains the correct form parameters.

        Must include grant_type, code, redirect_uri, client_id, code_verifier.
        """
        captured_requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request and return token response.

            Args:
                request: The incoming request.

            Returns:
                Mock token response.
            """
            captured_requests.append(request)
            return httpx.Response(200, json=_make_token_response())

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        flow.exchange_code(
            code="auth-code",
            verifier="test-verifier-string",
            client_id="my-client",
            redirect_uri="http://localhost:19284/callback",
        )

        assert len(captured_requests) == 1
        req = captured_requests[0]
        assert req.method == "POST"
        # Parse form body
        body = req.content.decode("utf-8")
        assert "grant_type=authorization_code" in body
        assert "code=auth-code" in body
        assert "client_id=my-client" in body
        assert "code_verifier=test-verifier-string" in body
        assert "redirect_uri=" in body

    def test_exchange_uses_correct_url_for_region(self, tmp_path: Path) -> None:
        """Verify the token exchange URL is region-specific."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return token response.

            Args:
                request: The incoming request.

            Returns:
                Mock token response.
            """
            captured_urls.append(str(request.url))
            return httpx.Response(200, json=_make_token_response())

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)

        for region, expected_host in [
            ("us", "mixpanel.com"),
            ("eu", "eu.mixpanel.com"),
            ("in", "in.mixpanel.com"),
        ]:
            captured_urls.clear()
            storage = OAuthStorage(storage_dir=tmp_path / region)
            flow = OAuthFlow(region=region, storage=storage, http_client=http_client)
            flow.exchange_code(
                code="c",
                verifier="v",
                client_id="cid",
                redirect_uri="http://localhost:19284/callback",
            )
            assert expected_host in captured_urls[0]
            assert (
                "/oauth/token/" in captured_urls[0]
                or "/oauth/token" in captured_urls[0]
            )

    def test_exchange_error_raises_oauth_error(self, tmp_path: Path) -> None:
        """Verify that a failed token exchange raises OAuthError."""
        transport = httpx.MockTransport(
            lambda _req: httpx.Response(
                400, json={"error": "invalid_grant", "error_description": "Bad code"}
            )
        )
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        with pytest.raises(OAuthError) as exc_info:
            flow.exchange_code(
                code="bad-code",
                verifier="v",
                client_id="cid",
                redirect_uri="http://localhost:19284/callback",
            )
        assert exc_info.value.code == "OAUTH_TOKEN_ERROR"


class TestOAuthFlowRefresh:
    """Tests for OAuthFlow.refresh_tokens()."""

    def test_refresh_posts_correct_params(self, tmp_path: Path) -> None:
        """Verify the refresh POST contains grant_type=refresh_token and client_id."""
        captured_requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request and return token response.

            Args:
                request: The incoming request.

            Returns:
                Mock token response.
            """
            captured_requests.append(request)
            return httpx.Response(200, json=_make_token_response())

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        tokens = OAuthTokens(
            access_token=SecretStr("old-access"),
            refresh_token=SecretStr("old-refresh"),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            scope="projects",
            token_type="Bearer",
            project_id="123",
        )

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        new_tokens = flow.refresh_tokens(tokens=tokens, client_id="cid")

        assert len(captured_requests) == 1
        body = captured_requests[0].content.decode("utf-8")
        assert "grant_type=refresh_token" in body
        assert "refresh_token=old-refresh" in body
        assert "client_id=cid" in body
        assert new_tokens.access_token.get_secret_value() == "access-tok-123"

    def test_refresh_invalid_grant_raises_revoked(self, tmp_path: Path) -> None:
        """``invalid_grant`` from the IdP → distinct ``OAUTH_REFRESH_REVOKED`` code.

        A refresh token that the IdP rejects is permanently dead — the user must
        re-run the browser flow, not just retry. The distinct error code lets
        downstream callers (CLI, plugin) emit the precise recovery hint instead
        of suggesting a generic retry.
        """
        transport = httpx.MockTransport(
            lambda _req: httpx.Response(400, json={"error": "invalid_grant"})
        )
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        tokens = OAuthTokens(
            access_token=SecretStr("old"),
            refresh_token=SecretStr("bad-refresh"),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            scope="projects",
            token_type="Bearer",
        )

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        with pytest.raises(OAuthError) as exc_info:
            flow.refresh_tokens(tokens=tokens, client_id="cid", account_name="personal")
        assert exc_info.value.code == "OAUTH_REFRESH_REVOKED"
        # Actionable hint embeds the account name so the user knows which
        # `mp account login` to re-run.
        assert "personal" in exc_info.value.message
        assert "mp account login personal" in exc_info.value.message

    def test_refresh_transient_5xx_raises_generic_error(self, tmp_path: Path) -> None:
        """A 5xx from the IdP keeps the generic ``OAUTH_REFRESH_ERROR`` code.

        Distinguishing transient failures from permanent ones (revoked refresh)
        is the whole point of the split — a retry would help here, not re-login.
        """
        transport = httpx.MockTransport(
            lambda _req: httpx.Response(503, text="Service Unavailable")
        )
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        tokens = OAuthTokens(
            access_token=SecretStr("old"),
            refresh_token=SecretStr("good-refresh"),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            scope="projects",
            token_type="Bearer",
        )

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        with pytest.raises(OAuthError) as exc_info:
            flow.refresh_tokens(tokens=tokens, client_id="cid")
        assert exc_info.value.code == "OAUTH_REFRESH_ERROR"

    def test_refresh_without_refresh_token_raises(self, tmp_path: Path) -> None:
        """Verify that refreshing without a refresh_token raises OAuthError."""
        transport = httpx.MockTransport(
            lambda _req: httpx.Response(200, json=_make_token_response())
        )
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        tokens = OAuthTokens(
            access_token=SecretStr("old"),
            refresh_token=None,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            scope="projects",
            token_type="Bearer",
        )

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        with pytest.raises(OAuthError) as exc_info:
            flow.refresh_tokens(tokens=tokens, client_id="cid")
        assert exc_info.value.code == "OAUTH_REFRESH_ERROR"


class TestOAuthFlowGetValidToken:
    """Tests for OAuthFlow.get_valid_token() token lifecycle management."""

    def test_returns_current_token_if_not_expired(self, tmp_path: Path) -> None:
        """Verify that a non-expired token is returned immediately without refresh."""
        transport = httpx.MockTransport(
            lambda _req: httpx.Response(500, text="should not be called")
        )
        http_client = httpx.Client(transport=transport)

        storage = OAuthStorage(storage_dir=tmp_path)
        valid_tokens = OAuthTokens(
            access_token=SecretStr("valid-access-token"),
            refresh_token=SecretStr("valid-refresh-token"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scope="projects analysis",
            token_type="Bearer",
            project_id="12345",
        )
        client_info = _make_client_info()
        storage.save_tokens(valid_tokens, region="us")
        storage.save_client_info(client_info)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        result = flow.get_valid_token(region="us")

        assert result == "valid-access-token"

    def test_auto_refreshes_expired_token(self, tmp_path: Path) -> None:
        """Verify that an expired token triggers a refresh and returns the new token."""
        transport = httpx.MockTransport(
            lambda _req: httpx.Response(200, json=_make_token_response())
        )
        http_client = httpx.Client(transport=transport)

        storage = OAuthStorage(storage_dir=tmp_path)
        expired_tokens = OAuthTokens(
            access_token=SecretStr("expired-access"),
            refresh_token=SecretStr("valid-refresh"),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            scope="projects analysis",
            token_type="Bearer",
            project_id="12345",
        )
        client_info = _make_client_info()
        storage.save_tokens(expired_tokens, region="us")
        storage.save_client_info(client_info)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        result = flow.get_valid_token(region="us")

        assert result == "access-tok-123"

    def test_persists_refreshed_tokens(self, tmp_path: Path) -> None:
        """Verify that refreshed tokens are saved back to storage."""
        transport = httpx.MockTransport(
            lambda _req: httpx.Response(200, json=_make_token_response())
        )
        http_client = httpx.Client(transport=transport)

        storage = OAuthStorage(storage_dir=tmp_path)
        expired_tokens = OAuthTokens(
            access_token=SecretStr("expired-access"),
            refresh_token=SecretStr("valid-refresh"),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            scope="projects analysis",
            token_type="Bearer",
            project_id="12345",
        )
        client_info = _make_client_info()
        storage.save_tokens(expired_tokens, region="us")
        storage.save_client_info(client_info)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        flow.get_valid_token(region="us")

        # Verify the new token was persisted
        reloaded = storage.load_tokens(region="us")
        assert reloaded is not None
        assert reloaded.access_token.get_secret_value() == "access-tok-123"

    def test_raises_revoked_if_refresh_fails_invalid_grant(
        self, tmp_path: Path
    ) -> None:
        """An ``invalid_grant`` response routes through the new
        ``OAUTH_REFRESH_REVOKED`` code rather than the generic refresh-error code,
        so callers can prompt the user to re-login instead of suggesting retry."""
        transport = httpx.MockTransport(
            lambda _req: httpx.Response(400, json={"error": "invalid_grant"})
        )
        http_client = httpx.Client(transport=transport)

        storage = OAuthStorage(storage_dir=tmp_path)
        expired_tokens = OAuthTokens(
            access_token=SecretStr("expired-access"),
            refresh_token=SecretStr("bad-refresh"),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            scope="projects analysis",
            token_type="Bearer",
        )
        client_info = _make_client_info()
        storage.save_tokens(expired_tokens, region="us")
        storage.save_client_info(client_info)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        with pytest.raises(OAuthError) as exc_info:
            flow.get_valid_token(region="us")
        assert exc_info.value.code == "OAUTH_REFRESH_REVOKED"

    def test_raises_oauth_error_if_no_tokens_exist(self, tmp_path: Path) -> None:
        """Verify that missing tokens raises OAuthError with OAUTH_TOKEN_ERROR."""
        transport = httpx.MockTransport(
            lambda _req: httpx.Response(500, text="should not be called")
        )
        http_client = httpx.Client(transport=transport)

        storage = OAuthStorage(storage_dir=tmp_path)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        with pytest.raises(OAuthError) as exc_info:
            flow.get_valid_token(region="us")
        assert exc_info.value.code == "OAUTH_TOKEN_ERROR"

    def test_raises_oauth_error_if_no_client_info_for_refresh(
        self, tmp_path: Path
    ) -> None:
        """Verify error when tokens are expired but no client info exists for refresh."""
        transport = httpx.MockTransport(
            lambda _req: httpx.Response(200, json=_make_token_response())
        )
        http_client = httpx.Client(transport=transport)

        storage = OAuthStorage(storage_dir=tmp_path)
        expired_tokens = OAuthTokens(
            access_token=SecretStr("expired-access"),
            refresh_token=SecretStr("valid-refresh"),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            scope="projects analysis",
            token_type="Bearer",
        )
        storage.save_tokens(expired_tokens, region="us")
        # Intentionally NOT saving client_info

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        with pytest.raises(OAuthError) as exc_info:
            flow.get_valid_token(region="us")
        assert exc_info.value.code == "OAUTH_REFRESH_ERROR"


class TestOAuthFlowRegionUrls:
    """Tests for region-specific OAuth base URLs."""

    @patch("mixpanel_headless._internal.auth.flow.webbrowser")
    @patch("mixpanel_headless._internal.auth.flow.start_callback_server")
    @patch("mixpanel_headless._internal.auth.flow.ensure_client_registered")
    def test_eu_region_authorize_url(
        self,
        mock_register: MagicMock,
        mock_callback: MagicMock,
        mock_browser: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verify the EU region uses eu.mixpanel.com for the authorize URL."""
        mock_register.return_value = _make_client_info(region="eu")
        mock_callback.return_value = (
            CallbackResult(code="c", state="s"),
            19284,
        )
        mock_browser.open.return_value = True

        opened_urls: list[str] = []

        def _capture_url(url: str) -> bool:
            """Capture opened URL and return True to indicate success."""
            opened_urls.append(url)
            return True

        mock_browser.open.side_effect = _capture_url

        transport = httpx.MockTransport(
            lambda _req: httpx.Response(200, json=_make_token_response())
        )
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        flow = OAuthFlow(region="eu", storage=storage, http_client=http_client)
        flow.login()

        assert len(opened_urls) == 1
        assert "eu.mixpanel.com" in opened_urls[0]


class TestOAuthFlowNetworkErrors:
    """Tests for network error handling in exchange_code and refresh_tokens."""

    def test_exchange_code_timeout(self, tmp_path: Path) -> None:
        """Verify exchange_code raises OAuthError on timeout.

        A network timeout during token exchange should be wrapped in
        OAuthError with OAUTH_TOKEN_ERROR code.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Raise TimeoutException.

            Args:
                request: The incoming request.

            Returns:
                Never returns.

            Raises:
                httpx.TimeoutException: Always.
            """
            raise httpx.TimeoutException("test timeout")

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        with pytest.raises(OAuthError) as exc_info:
            flow.exchange_code(
                code="c",
                verifier="v",
                client_id="cid",
                redirect_uri="http://localhost:19284/callback",
            )
        assert exc_info.value.code == "OAUTH_TOKEN_ERROR"

    def test_exchange_code_connection_error(self, tmp_path: Path) -> None:
        """Verify exchange_code raises OAuthError on connection failure.

        A connection error (e.g. DNS resolution failure) should be wrapped
        in OAuthError with OAUTH_TOKEN_ERROR code.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Raise ConnectError.

            Args:
                request: The incoming request.

            Returns:
                Never returns.

            Raises:
                httpx.ConnectError: Always.
            """
            raise httpx.ConnectError("test connection error")

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        with pytest.raises(OAuthError) as exc_info:
            flow.exchange_code(
                code="c",
                verifier="v",
                client_id="cid",
                redirect_uri="http://localhost:19284/callback",
            )
        assert exc_info.value.code == "OAUTH_TOKEN_ERROR"

    def test_exchange_code_non_json_response(self, tmp_path: Path) -> None:
        """Verify exchange_code raises OAuthError for non-JSON 200 response.

        A proxy or misconfigured server might return HTML on success.
        The function should raise OAuthError, not a raw exception.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return HTML body.

            Args:
                request: The incoming request.

            Returns:
                HTML response.
            """
            return httpx.Response(
                200,
                content=b"<html>error</html>",
                headers={"content-type": "text/html"},
            )

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        with pytest.raises(OAuthError) as exc_info:
            flow.exchange_code(
                code="c",
                verifier="v",
                client_id="cid",
                redirect_uri="http://localhost:19284/callback",
            )
        assert exc_info.value.code == "OAUTH_TOKEN_ERROR"

    def test_exchange_code_missing_access_token_in_response(
        self, tmp_path: Path
    ) -> None:
        """Verify exchange_code raises OAuthError when access_token is missing.

        A valid JSON response missing ``access_token`` should raise
        OAuthError, not a raw KeyError.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return JSON with missing access_token.

            Args:
                request: The incoming request.

            Returns:
                JSON response without access_token.
            """
            return httpx.Response(200, json={"scope": "x"})

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        with pytest.raises(OAuthError) as exc_info:
            flow.exchange_code(
                code="c",
                verifier="v",
                client_id="cid",
                redirect_uri="http://localhost:19284/callback",
            )
        assert exc_info.value.code == "OAUTH_TOKEN_ERROR"

    def test_refresh_tokens_timeout(self, tmp_path: Path) -> None:
        """Verify refresh_tokens raises OAuthError on timeout.

        A network timeout during token refresh should be wrapped in
        OAuthError with OAUTH_REFRESH_ERROR code.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Raise TimeoutException.

            Args:
                request: The incoming request.

            Returns:
                Never returns.

            Raises:
                httpx.TimeoutException: Always.
            """
            raise httpx.TimeoutException("test timeout")

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        tokens = OAuthTokens(
            access_token=SecretStr("old"),
            refresh_token=SecretStr("old-refresh"),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            scope="projects",
            token_type="Bearer",
        )

        flow = OAuthFlow(region="us", storage=storage, http_client=http_client)
        with pytest.raises(OAuthError) as exc_info:
            flow.refresh_tokens(tokens=tokens, client_id="cid")
        assert exc_info.value.code == "OAUTH_REFRESH_ERROR"


class TestOAuthFlowRegionValidation:
    """Tests for region validation in OAuthFlow.__init__."""

    def test_invalid_region_raises_oauth_error(self, tmp_path: Path) -> None:
        """Verify that an invalid region raises OAuthError with OAUTH_CONFIG_ERROR."""
        with pytest.raises(OAuthError) as exc_info:
            OAuthFlow(region="uk", storage=OAuthStorage(storage_dir=tmp_path))
        assert exc_info.value.code == "OAUTH_CONFIG_ERROR"
        assert "uk" in str(exc_info.value)

    def test_uppercase_region_raises_oauth_error(self, tmp_path: Path) -> None:
        """Verify that an uppercase region is rejected (case-sensitive)."""
        with pytest.raises(OAuthError) as exc_info:
            OAuthFlow(region="US", storage=OAuthStorage(storage_dir=tmp_path))
        assert exc_info.value.code == "OAUTH_CONFIG_ERROR"

    def test_empty_region_raises_oauth_error(self, tmp_path: Path) -> None:
        """Verify that an empty region is rejected."""
        with pytest.raises(OAuthError) as exc_info:
            OAuthFlow(region="", storage=OAuthStorage(storage_dir=tmp_path))
        assert exc_info.value.code == "OAUTH_CONFIG_ERROR"

    @pytest.mark.parametrize("region", ["us", "eu", "in"])
    def test_valid_regions_accepted(self, tmp_path: Path, region: str) -> None:
        """Verify that valid regions are accepted without error."""
        flow = OAuthFlow(region=region, storage=OAuthStorage(storage_dir=tmp_path))
        assert flow.region == region
