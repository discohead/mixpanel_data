"""Unit tests for Dynamic Client Registration (T018).

Tests the ensure_client_registered function which implements
Dynamic Client Registration (RFC 7591) for Mixpanel OAuth.

Verifies:
- POST to ``{base_url}mcp/register/`` with correct body
- Parses client_id from response
- Caches result per region (checks OAuthStorage)
- Re-registers if redirect_uri changes
- Handles 429 rate limit
"""
# ruff: noqa: ARG001, ARG005

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from mixpanel_headless._internal.auth.client_registration import (
    ensure_client_registered,
)
from mixpanel_headless._internal.auth.storage import OAuthStorage
from mixpanel_headless._internal.auth.token import OAuthClientInfo
from mixpanel_headless.exceptions import OAuthError


def _make_register_transport(
    *,
    client_id: str = "registered-client-id",
    status_code: int = 201,
) -> httpx.MockTransport:
    """Create a mock transport that simulates the registration endpoint.

    Args:
        client_id: The client_id to return in the response.
        status_code: HTTP status code to return.

    Returns:
        An httpx.MockTransport configured for registration responses.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        """Handle mock HTTP request.

        Args:
            request: The incoming HTTP request.

        Returns:
            Mock HTTP response.
        """
        if status_code == 429:
            return httpx.Response(
                status_code=429,
                json={"error": "rate_limited"},
                headers={"Retry-After": "60"},
            )
        return httpx.Response(
            status_code=status_code,
            json={"client_id": client_id},
        )

    return httpx.MockTransport(handler)


class TestEnsureClientRegistered:
    """Tests for the ensure_client_registered function."""

    def test_posts_to_register_endpoint(self, tmp_path: Path) -> None:
        """Verify that a POST is made to ``{base_url}mcp/register/``.

        Captures the request URL and method to verify correct endpoint usage.
        """
        captured_requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request and return success.

            Args:
                request: The incoming request.

            Returns:
                Mock success response.
            """
            captured_requests.append(request)
            return httpx.Response(201, json={"client_id": "cid-1"})

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        ensure_client_registered(
            http_client=client,
            region="us",
            redirect_uri="http://localhost:19284/callback",
            storage=storage,
        )

        assert len(captured_requests) == 1
        req = captured_requests[0]
        assert req.method == "POST"
        assert str(req.url) == "https://mixpanel.com/oauth/mcp/register/"

    def test_correct_request_body(self, tmp_path: Path) -> None:
        """Verify the registration POST body contains required fields.

        The body must include redirect_uris, grant_types, response_types,
        token_endpoint_auth_method, and scope.
        """
        import json

        captured_body: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body and return success.

            Args:
                request: The incoming request.

            Returns:
                Mock success response.
            """
            body: dict[str, object] = json.loads(request.content)
            captured_body.append(body)
            return httpx.Response(201, json={"client_id": "cid-1"})

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        ensure_client_registered(
            http_client=client,
            region="us",
            redirect_uri="http://localhost:19284/callback",
            storage=storage,
        )

        assert len(captured_body) == 1
        body = captured_body[0]
        assert body["redirect_uris"] == ["http://localhost:19284/callback"]
        assert body["grant_types"] == ["authorization_code", "refresh_token"]
        assert body["response_types"] == ["code"]
        assert body["token_endpoint_auth_method"] == "none"
        assert isinstance(body.get("scope"), str)
        # Scope should contain key scopes
        scope_str = str(body["scope"])
        assert "projects" in scope_str
        assert "analysis" in scope_str

    def test_parses_client_id_from_response(self, tmp_path: Path) -> None:
        """Verify client_id is correctly parsed from the registration response."""
        transport = _make_register_transport(client_id="parsed-client-id")
        client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        result = ensure_client_registered(
            http_client=client,
            region="us",
            redirect_uri="http://localhost:19284/callback",
            storage=storage,
        )

        assert isinstance(result, OAuthClientInfo)
        assert result.client_id == "parsed-client-id"
        assert result.region == "us"
        assert result.redirect_uri == "http://localhost:19284/callback"

    def test_caches_result_per_region(self, tmp_path: Path) -> None:
        """Verify that a cached client is returned without making a new request.

        After the first registration, subsequent calls for the same region
        should return the cached client without hitting the network.
        """
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            """Count calls and return success.

            Args:
                request: The incoming request.

            Returns:
                Mock success response.
            """
            nonlocal call_count
            call_count += 1
            return httpx.Response(201, json={"client_id": "cached-cid"})

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        # First call registers
        result1 = ensure_client_registered(
            http_client=client,
            region="us",
            redirect_uri="http://localhost:19284/callback",
            storage=storage,
        )
        assert call_count == 1

        # Second call uses cache
        result2 = ensure_client_registered(
            http_client=client,
            region="us",
            redirect_uri="http://localhost:19284/callback",
            storage=storage,
        )
        assert call_count == 1  # No new request
        assert result2.client_id == result1.client_id

    def test_re_registers_if_redirect_uri_changes(self, tmp_path: Path) -> None:
        """Verify re-registration occurs when the redirect_uri changes.

        If the cached client has a different redirect_uri than requested,
        a new registration must be performed.
        """
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            """Count calls and return success.

            Args:
                request: The incoming request.

            Returns:
                Mock success response with incremented client_id.
            """
            nonlocal call_count
            call_count += 1
            return httpx.Response(201, json={"client_id": f"cid-{call_count}"})

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        # First registration
        result1 = ensure_client_registered(
            http_client=client,
            region="us",
            redirect_uri="http://localhost:19284/callback",
            storage=storage,
        )
        assert call_count == 1
        assert result1.client_id == "cid-1"

        # Changed redirect_uri triggers re-registration
        result2 = ensure_client_registered(
            http_client=client,
            region="us",
            redirect_uri="http://localhost:19285/callback",
            storage=storage,
        )
        assert call_count == 2
        assert result2.client_id == "cid-2"
        assert result2.redirect_uri == "http://localhost:19285/callback"

    def test_handles_429_rate_limit(self, tmp_path: Path) -> None:
        """Verify that HTTP 429 raises OAuthError with OAUTH_REGISTRATION_ERROR code."""
        transport = _make_register_transport(status_code=429)
        client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        with pytest.raises(OAuthError) as exc_info:
            ensure_client_registered(
                http_client=client,
                region="us",
                redirect_uri="http://localhost:19284/callback",
                storage=storage,
            )
        assert exc_info.value.code == "OAUTH_REGISTRATION_ERROR"

    def test_eu_region_uses_eu_base_url(self, tmp_path: Path) -> None:
        """Verify that EU region uses eu.mixpanel.com base URL."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return success.

            Args:
                request: The incoming request.

            Returns:
                Mock success response.
            """
            captured_urls.append(str(request.url))
            return httpx.Response(201, json={"client_id": "eu-cid"})

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        ensure_client_registered(
            http_client=client,
            region="eu",
            redirect_uri="http://localhost:19284/callback",
            storage=storage,
        )

        assert captured_urls[0] == "https://eu.mixpanel.com/oauth/mcp/register/"

    def test_in_region_uses_in_base_url(self, tmp_path: Path) -> None:
        """Verify that IN region uses in.mixpanel.com base URL."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return success.

            Args:
                request: The incoming request.

            Returns:
                Mock success response.
            """
            captured_urls.append(str(request.url))
            return httpx.Response(201, json={"client_id": "in-cid"})

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        ensure_client_registered(
            http_client=client,
            region="in",
            redirect_uri="http://localhost:19284/callback",
            storage=storage,
        )

        assert captured_urls[0] == "https://in.mixpanel.com/oauth/mcp/register/"

    def test_accepts_200_status_code(self, tmp_path: Path) -> None:
        """Verify that HTTP 200 is also accepted for backward compatibility.

        The real DCR endpoint returns 201, but some servers may return 200.
        Both are valid success responses.
        """
        transport = _make_register_transport(client_id="cid-200", status_code=200)
        client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        result = ensure_client_registered(
            http_client=client,
            region="us",
            redirect_uri="http://localhost:19284/callback",
            storage=storage,
        )

        assert result.client_id == "cid-200"

    def test_accepts_201_status_code(self, tmp_path: Path) -> None:
        """Verify that HTTP 201 Created is accepted.

        The Mixpanel DCR endpoint returns 201 for newly registered clients.
        """
        transport = _make_register_transport(client_id="cid-201", status_code=201)
        client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        result = ensure_client_registered(
            http_client=client,
            region="us",
            redirect_uri="http://localhost:19284/callback",
            storage=storage,
        )

        assert result.client_id == "cid-201"


class TestEnsureClientRegisteredRobustness:
    """Tests for handling malformed registration responses."""

    def test_registration_response_missing_client_id(self, tmp_path: Path) -> None:
        """Verify OAuthError when the 200 response body is missing client_id.

        A successful HTTP status but an empty JSON body should raise
        OAuthError with OAUTH_REGISTRATION_ERROR code.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 with empty JSON body.

            Args:
                request: The incoming request.

            Returns:
                Response with no client_id field.
            """
            return httpx.Response(200, json={})

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        with pytest.raises(OAuthError) as exc_info:
            ensure_client_registered(
                http_client=client,
                region="us",
                redirect_uri="http://localhost:19284/callback",
                storage=storage,
            )
        assert exc_info.value.code == "OAUTH_REGISTRATION_ERROR"

    def test_registration_non_json_response(self, tmp_path: Path) -> None:
        """Verify OAuthError when the 200 response body is HTML, not JSON.

        Some proxies or error pages may return HTML even with a 200 status.
        The function should raise OAuthError, not JSONDecodeError.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 with HTML body.

            Args:
                request: The incoming request.

            Returns:
                HTML response instead of JSON.
            """
            return httpx.Response(
                200,
                content=b"<html><body>Oops</body></html>",
                headers={"content-type": "text/html"},
            )

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        storage = OAuthStorage(storage_dir=tmp_path)

        with pytest.raises(OAuthError) as exc_info:
            ensure_client_registered(
                http_client=client,
                region="us",
                redirect_uri="http://localhost:19284/callback",
                storage=storage,
            )
        assert exc_info.value.code == "OAUTH_REGISTRATION_ERROR"


class TestEnsureClientRegisteredRegionValidation:
    """Tests for region validation in ensure_client_registered."""

    def test_invalid_region_raises_oauth_error(self, tmp_path: Path) -> None:
        """Verify that an invalid region raises OAuthError before making any request."""
        client = httpx.Client(
            transport=httpx.MockTransport(
                lambda _req: httpx.Response(200, json={"client_id": "nope"})
            )
        )
        storage = OAuthStorage(storage_dir=tmp_path)

        with pytest.raises(OAuthError) as exc_info:
            ensure_client_registered(
                http_client=client,
                region="xx",
                redirect_uri="http://localhost:19284/callback",
                storage=storage,
            )
        assert exc_info.value.code == "OAUTH_REGISTRATION_ERROR"
        assert "xx" in str(exc_info.value)
