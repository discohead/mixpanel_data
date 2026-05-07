"""Dynamic Client Registration for Mixpanel OAuth.

Implements RFC 7591 Dynamic Client Registration to obtain a client_id
from the Mixpanel authorization server. Client registrations are cached
per-region via OAuthStorage to avoid redundant network calls.

Example:
    ```python
    import httpx
    from mixpanel_headless._internal.auth.client_registration import (
        ensure_client_registered,
    )
    from mixpanel_headless._internal.auth.storage import OAuthStorage

    storage = OAuthStorage()
    client = httpx.Client()
    info = ensure_client_registered(
        http_client=client,
        region="us",
        redirect_uri="http://localhost:19284/callback",
        storage=storage,
    )
    print(f"Client ID: {info.client_id}")
    ```
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from mixpanel_headless._internal.auth.storage import OAuthStorage
from mixpanel_headless._internal.auth.token import OAuthClientInfo
from mixpanel_headless.exceptions import OAuthError

#: OAuth base URLs keyed by Mixpanel region.
OAUTH_BASE_URLS: dict[str, str] = {
    "us": "https://mixpanel.com/oauth/",
    "eu": "https://eu.mixpanel.com/oauth/",
    "in": "https://in.mixpanel.com/oauth/",
}

#: Scopes sent in the DCR request body for server-side validation.
#: Advisory only — DCR does NOT store these on the application model.
#: The created app has an empty scope field, meaning all scopes are allowed.
_DEFAULT_SCOPE: str = (
    "projects analysis events insights segmentation retention "
    "data:read funnels flows data_definitions dashboard_reports bookmarks"
)


def ensure_client_registered(
    http_client: httpx.Client,
    region: str,
    redirect_uri: str,
    storage: OAuthStorage,
) -> OAuthClientInfo:
    """Ensure a Dynamic Client Registration exists for the given region.

    Checks the local cache (via OAuthStorage) first. If a cached client
    exists with a matching ``redirect_uri``, it is returned immediately.
    Otherwise, a new registration is performed via POST to the Mixpanel
    ``mcp/register/`` endpoint and the result is cached.

    Args:
        http_client: An httpx.Client instance for making HTTP requests.
        region: Mixpanel data residency region (``us``, ``eu``, or ``in``).
        redirect_uri: The OAuth redirect URI to register.
        storage: OAuthStorage instance for caching client info.

    Returns:
        The registered (or cached) OAuthClientInfo.

    Raises:
        OAuthError: If the registration request fails (network error,
            non-200 status, or rate limiting with ``OAUTH_REGISTRATION_ERROR``).

    Example:
        ```python
        info = ensure_client_registered(
            http_client=httpx.Client(),
            region="us",
            redirect_uri="http://localhost:19284/callback",
            storage=OAuthStorage(),
        )
        print(info.client_id)
        ```
    """
    # Check cache
    cached = storage.load_client_info(region)
    if cached is not None and cached.redirect_uri == redirect_uri:
        return cached

    # Register new client
    if region not in OAUTH_BASE_URLS:
        raise OAuthError(
            f"Unknown region: {region!r}. Must be one of: "
            f"{', '.join(sorted(OAUTH_BASE_URLS.keys()))}",
            code="OAUTH_REGISTRATION_ERROR",
        )
    base_url = OAUTH_BASE_URLS[region]
    register_url = f"{base_url}mcp/register/"

    body: dict[str, object] = {
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": _DEFAULT_SCOPE,
    }

    try:
        response = http_client.post(register_url, json=body)
    except httpx.HTTPError as exc:
        raise OAuthError(
            f"Client registration request failed: {exc}",
            code="OAUTH_REGISTRATION_ERROR",
            details={"region": region, "url": register_url},
        ) from exc

    if response.status_code == 429:
        raise OAuthError(
            "Client registration rate limited. Please try again later.",
            code="OAUTH_REGISTRATION_ERROR",
            details={
                "region": region,
                "status_code": 429,
                "retry_after": response.headers.get("Retry-After"),
            },
        )

    if not response.is_success:
        raise OAuthError(
            f"Client registration failed with status {response.status_code}: "
            f"{response.text}",
            code="OAUTH_REGISTRATION_ERROR",
            details={
                "region": region,
                "status_code": response.status_code,
                "response_body": response.text,
            },
        )

    try:
        data = response.json()
        client_id = str(data["client_id"])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise OAuthError(
            f"Invalid registration response: {exc}",
            code="OAUTH_REGISTRATION_ERROR",
            details={
                "region": region,
                "response_body": response.text,
            },
        ) from exc

    client_info = OAuthClientInfo(
        client_id=client_id,
        region=region,
        redirect_uri=redirect_uri,
        scope=_DEFAULT_SCOPE,
        created_at=datetime.now(timezone.utc),
    )

    # Cache for future use
    storage.save_client_info(client_info)

    return client_info
